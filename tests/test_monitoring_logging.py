"""Tests for operational logging and credential redaction."""

from __future__ import annotations

import json
from src.monitoring.logging import (
    OperationalLogger,
    op_logger,
    sanitize_data,
    sanitize_text,
)


def test_sanitize_text_bearer_token():
    """Verify Bearer tokens are redacted in log messages."""
    raw = "Request failed with Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    sanitized = sanitize_text(raw)
    assert "Bearer [REDACTED]" in sanitized
    assert "eyJhbGci" not in sanitized


def test_sanitize_text_hf_token():
    """Verify Hugging Face API tokens are redacted."""
    raw = "Using token hf_AbCdEf1234567890XyZ to query model"
    sanitized = sanitize_text(raw)
    assert "hf_[REDACTED]" in sanitized
    assert "AbCdEf1234567890XyZ" not in sanitized


def test_sanitize_text_password_key_value():
    """Verify password strings in key=value format are redacted."""
    raw = "Connect string user=john, password=SuperSecretPassword123, db=app"
    sanitized = sanitize_text(raw)
    assert "password=[REDACTED]" in sanitized
    assert "SuperSecretPassword123" not in sanitized


def test_sanitize_data_nested_dict():
    """Verify recursive dictionary secret sanitization."""
    raw = {
        "user": "test_user",
        "snowflake_password": "RealSecretPassword",
        "api_key": "hf_secrettoken12345",
        "nested": {
            "token": "secret_session_token",
            "safe_field": 42,
        },
        "list_items": [
            {"password": "pw1"},
            {"description": "Public scholarship info"},
        ],
    }
    cleaned = sanitize_data(raw)
    assert cleaned["user"] == "test_user"
    assert cleaned["snowflake_password"] == "[REDACTED]"
    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["token"] == "[REDACTED]"
    assert cleaned["nested"]["safe_field"] == 42
    assert cleaned["list_items"][0]["password"] == "[REDACTED]"
    assert cleaned["list_items"][1]["description"] == "Public scholarship info"


def test_op_logger_log():
    """Verify op_logger creates well-formed OperationalLogEntry."""
    entry = op_logger.log(
        component="test_component",
        operation="test_op",
        status="SUCCESS",
        message="Test message",
        duration_ms=45.67,
        records_processed=10,
        warnings_count=1,
        errors_count=0,
        details={"token": "super_secret"},
    )
    assert entry.component == "test_component"
    assert entry.operation == "test_op"
    assert entry.status == "SUCCESS"
    assert entry.duration_ms == 45.67
    assert entry.records_processed == 10
    assert entry.details["token"] == "[REDACTED]"

    json_str = entry.to_json()
    parsed = json.loads(json_str)
    assert parsed["component"] == "test_component"
    assert parsed["details"]["token"] == "[REDACTED]"


def test_measure_operation_context_manager():
    """Verify measure_operation context manager measures duration and catches errors."""
    logger = OperationalLogger(name="test_logger")

    # Success case
    with logger.measure_operation("comp", "success_op") as meta:
        meta["records_processed"] = 5
        meta["warnings_count"] = 0

    # Failure case
    try:
        with logger.measure_operation("comp", "failing_op") as meta:
            meta["records_processed"] = 2
            raise ValueError("Deliberate test error password=mysecret")
    except ValueError as exc:
        assert "password=mysecret" in str(exc)
