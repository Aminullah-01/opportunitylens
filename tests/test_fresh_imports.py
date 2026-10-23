"""Regression tests for clean configuration and application imports.

Verifies that all configuration symbols are cleanly exported, no circular
dependencies exist, and modules import cleanly in fresh Python processes.
"""

from __future__ import annotations

import subprocess
import sys


def test_config_exports():
    """Verify all expected configuration classes and instances are exported."""
    from src.config import (
        AIConfig,
        AppConfig,
        IngestionConfig,
        MonitoringConfig,
        QualityConfig,
        SnowflakeConfig,
        ai_config,
        app_config,
        ingestion_config,
        monitoring_config,
        quality_config,
        snowflake_config,
    )

    assert isinstance(app_config, AppConfig)
    assert isinstance(snowflake_config, SnowflakeConfig)
    assert isinstance(ai_config, AIConfig)
    assert isinstance(quality_config, QualityConfig)
    assert isinstance(monitoring_config, MonitoringConfig)
    assert isinstance(ingestion_config, IngestionConfig)

    assert quality_config.stale_threshold_days >= 1
    assert isinstance(quality_config.network_enabled, bool)
    assert monitoring_config.health_timeout_seconds > 0
    assert ingestion_config.timeout_seconds > 0


def test_config_all_manifest():
    """Verify __all__ is accurate and complete."""
    import src.config as config_mod

    assert hasattr(config_mod, "__all__")
    for name in config_mod.__all__:
        assert hasattr(config_mod, name), f"Symbol {name} listed in __all__ but missing"


def test_no_circular_imports():
    """Verify modules across the application can be imported without cycles."""
    import importlib

    modules = [
        "src.config",
        "src.analytics",
        "src.demo_data",
        "src.db",
        "src.matching",
        "src.ai",
        "src.quality",
        "src.ingestion",
        "src.ingestion.sources",
    ]
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None


def test_fresh_subprocess_import():
    """Spawn a clean Python process and ensure app and config import cleanly."""
    cmd = [
        sys.executable,
        "-c",
        (
            "from src.config import "
            "app_config, snowflake_config, ai_config, quality_config, monitoring_config; "
            "import app; "
            "print('OK')"
        ),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"Process import failed: {result.stderr}"
    assert "OK" in result.stdout
