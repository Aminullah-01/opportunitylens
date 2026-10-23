"""Unit tests for safe, SSRF-defended source link reachability checker."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.quality.models import VerificationStatus
from src.quality.source_checker import (
    SafeSourceChecker,
    is_safe_destination_ip,
    validate_url_syntax_and_destination,
)


def test_is_safe_destination_ip():
    """Verify that private, loopback, link-local, and cloud metadata IPs are blocked."""
    # Loopback
    assert is_safe_destination_ip("127.0.0.1")[0] is False
    assert is_safe_destination_ip("127.0.0.254")[0] is False
    assert is_safe_destination_ip("::1")[0] is False

    # Private
    assert is_safe_destination_ip("10.0.0.1")[0] is False
    assert is_safe_destination_ip("192.168.1.1")[0] is False
    assert is_safe_destination_ip("172.16.5.10")[0] is False

    # Cloud metadata / Link-local
    assert is_safe_destination_ip("169.254.169.254")[0] is False
    assert is_safe_destination_ip("169.254.1.1")[0] is False

    # Multicast & Broadcast
    assert is_safe_destination_ip("224.0.0.1")[0] is False
    assert is_safe_destination_ip("0.0.0.0")[0] is False

    # Public Routable IPs
    assert is_safe_destination_ip("8.8.8.8")[0] is True
    assert is_safe_destination_ip("93.184.216.34")[0] is True
    assert is_safe_destination_ip("1.1.1.1")[0] is True


def test_validate_url_syntax_and_destination_syntax():
    """Verify syntax checks before network or DNS calls."""
    # Empty or None
    assert validate_url_syntax_and_destination(None)[0] is False
    assert validate_url_syntax_and_destination("")[0] is False

    # Unsupported schemes
    assert validate_url_syntax_and_destination("ftp://example.com")[0] is False
    assert validate_url_syntax_and_destination("file:///etc/passwd")[0] is False
    assert validate_url_syntax_and_destination("javascript:alert(1)")[0] is False

    # Localhost explicitly blocked
    assert validate_url_syntax_and_destination("http://localhost:8000/app")[0] is False
    assert validate_url_syntax_and_destination("http://localhost.localdomain")[0] is False


def test_validate_url_destination_ssrf_dns_resolution():
    """Verify that hostnames resolving to private IPs are rejected."""
    # Mock DNS resolving evil-internal.com to 127.0.0.1
    mock_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
    with patch("socket.getaddrinfo", return_value=mock_addr):
        is_safe, ip, err = validate_url_syntax_and_destination("https://evil-internal.com/admin")
        assert is_safe is False
        assert "SSRF defense" in err

    # Mock DNS resolving public-site.ng to 102.134.1.5 (public Nigerian IP)
    mock_public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("102.134.1.5", 443))]
    with patch("socket.getaddrinfo", return_value=mock_public):
        is_safe, ip, err = validate_url_syntax_and_destination("https://nitda.gov.ng/3mtt")
        assert is_safe is True
        assert ip == "102.134.1.5"
        assert err is None


def test_checker_offline_mode():
    """Verify that network_enabled=False immediately aborts network access."""
    checker = SafeSourceChecker(network_enabled=False)
    res = checker.check_url("https://example.com/scholarship")
    assert res.is_reachable is False
    assert res.verification_status == VerificationStatus.NOT_CHECKED
    assert res.error_code == "NETWORK_DISABLED"


def test_checker_http_200_reachability():
    """Verify that HTTP 200 marks link reachable but leaves verification as NEEDS_REVIEW."""
    checker = SafeSourceChecker(network_enabled=True)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://example.com/apply"

    # Mock DNS and requests
    mock_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=mock_dns):
        with patch.object(checker, "_get_session") as mock_get_sess:
            mock_sess = MagicMock()
            mock_sess.head.return_value = mock_resp
            mock_get_sess.return_value = mock_sess

            result = checker.check_url("https://example.com/apply")
            assert result.is_reachable is True
            assert result.http_status == 200
            # Semantic: reachable does not prove verified legitimacy
            assert result.verification_status == VerificationStatus.NEEDS_REVIEW
            assert result.error_code is None


def test_checker_http_404_broken_link():
    """Verify that HTTP 404 is mapped to BROKEN_LINK."""
    checker = SafeSourceChecker(network_enabled=True)

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.url = "https://example.com/expired-grant"

    mock_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=mock_dns):
        with patch.object(checker, "_get_session") as mock_get_sess:
            mock_sess = MagicMock()
            mock_sess.head.return_value = mock_resp
            mock_get_sess.return_value = mock_sess

            result = checker.check_url("https://example.com/expired-grant")
            assert result.is_reachable is False
            assert result.http_status == 404
            assert result.verification_status == VerificationStatus.BROKEN_LINK
            assert result.error_code == "HTTP_404_NOT_FOUND"


def test_checker_http_403_and_429_unverifiable():
    """Verify that HTTP 403 / 429 are mapped to UNVERIFIABLE rather than broken."""
    checker = SafeSourceChecker(network_enabled=True)

    mock_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=mock_dns):
        with patch.object(checker, "_get_session") as mock_get_sess:
            mock_sess = MagicMock()
            # 403 Forbidden
            mock_resp_403 = MagicMock()
            mock_resp_403.status_code = 403
            mock_resp_403.url = "https://example.com/protected"
            mock_sess.head.return_value = mock_resp_403
            mock_sess.get.return_value = mock_resp_403
            mock_get_sess.return_value = mock_sess

            res403 = checker.check_url("https://example.com/protected")
            assert res403.is_reachable is False
            assert res403.verification_status == VerificationStatus.UNVERIFIABLE
            assert "RESTRICTED" in res403.error_code


def test_checker_timeout_handling():
    """Verify timeout exception mapping."""
    checker = SafeSourceChecker(network_enabled=True, timeout_seconds=2.0)

    mock_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=mock_dns):
        with patch.object(checker, "_get_session") as mock_get_sess:
            mock_sess = MagicMock()
            mock_sess.head.side_effect = requests.exceptions.Timeout("Connection timed out")
            mock_sess.get.side_effect = requests.exceptions.Timeout("Connection timed out")
            mock_get_sess.return_value = mock_sess

            result = checker.check_url("https://example.com/slow-endpoint")
            assert result.is_reachable is False
            assert result.verification_status == VerificationStatus.UNVERIFIABLE
            assert result.error_code == "REQUEST_TIMEOUT"


def test_checker_ssrf_redirect_intercept():
    """Verify that a redirect destination resolving to internal IP is intercepted and blocked."""
    checker = SafeSourceChecker(network_enabled=True)

    # Initial head returns a response whose final redirected URL points to 169.254.169.254
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "http://169.254.169.254/latest/meta-data/"

    mock_dns_public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]
    with patch("socket.getaddrinfo", return_value=mock_dns_public):
        with patch.object(checker, "_get_session") as mock_get_sess:
            mock_sess = MagicMock()
            mock_sess.head.return_value = mock_resp
            mock_get_sess.return_value = mock_sess

            result = checker.check_url("http://innocent-looking-redirector.com/go")
            assert result.is_reachable is False
            assert result.error_code == "UNSAFE_REDIRECT"
            assert result.verification_status == VerificationStatus.BROKEN_LINK
