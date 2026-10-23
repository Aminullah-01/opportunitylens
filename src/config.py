"""Configuration management for OpportunityLens.

Loads application settings and credentials from environment variables using
python-dotenv. Snowflake and AI provider credentials are loaded safely but
connections are intentionally deferred to future phases.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if it exists
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


@dataclass(frozen=True)
class AppConfig:
    """Application metadata and general runtime configuration."""

    APP_NAME: str = "OpportunityLens"
    APP_TAGLINE: str = "Find opportunities. Understand your chances. Take your next step."
    APP_VERSION: str = "0.6.0-phase6"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() in ("true", "1", "yes")

    # Target event & category details
    HACKATHON_EVENT: str = "Hacktoberfest Hack Day Gombe"
    HACKATHON_CATEGORY: str = "Best Open-Source AI Project with Snowflake"


@dataclass(frozen=True)
class SnowflakeConfig:
    """Snowflake credentials placeholder configuration for Phase 2/3.

    Note: Connections to Snowflake are intentionally disabled during Phase 1.
    """

    account: str = os.getenv("SNOWFLAKE_ACCOUNT", "")
    user: str = os.getenv("SNOWFLAKE_USER", "")
    password: str = os.getenv("SNOWFLAKE_PASSWORD", "")
    role: str = os.getenv("SNOWFLAKE_ROLE", "")
    warehouse: str = os.getenv("SNOWFLAKE_WAREHOUSE", "")
    database: str = os.getenv("SNOWFLAKE_DATABASE", "")
    schema: str = os.getenv("SNOWFLAKE_SCHEMA", "")

    @property
    def is_configured(self) -> bool:
        """Check if all necessary Snowflake credentials are provided."""
        return bool(self.account and self.user and self.password and self.database)


@dataclass(frozen=True)
class AIConfig:
    """AI Provider configuration for Phase 4."""

    hf_api_key: str = os.getenv("HF_API_KEY", "")
    model_name: str = os.getenv(
        "HF_MODEL_ID",
        os.getenv("AI_MODEL_NAME", "meta-llama/Llama-3.2-3B-Instruct"),
    )
    provider: str = os.getenv("HF_PROVIDER", "hf-inference")
    openai_api_base: str = os.getenv(
        "OPENAI_API_BASE", "https://api-inference.huggingface.co/v1"
    )
    ai_enabled: bool = os.getenv("AI_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    timeout_seconds: int = int(os.getenv("AI_TIMEOUT_SECONDS", "20"))
    max_output_tokens: int = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "500"))

    @property
    def is_configured(self) -> bool:
        """Check if AI provider credentials are provided and AI is enabled."""
        return bool(self.ai_enabled and self.hf_api_key)


@dataclass(frozen=True)
class QualityConfig:
    """Data quality and verification configuration for Phase 5."""

    stale_threshold_days: int = int(os.getenv("QUALITY_STALE_DAYS", "30"))
    network_enabled: bool = os.getenv("QUALITY_NETWORK_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    timeout_seconds: float = float(os.getenv("QUALITY_TIMEOUT_SECONDS", "5.0"))
    max_redirects: int = int(os.getenv("QUALITY_MAX_REDIRECTS", "3"))


@dataclass(frozen=True)
class MonitoringConfig:
    """Operational monitoring and audit runner configuration for Phase 6."""

    reports_dir: Path = Path(
        os.getenv("MONITORING_REPORTS_DIR", str(BASE_DIR / "reports" / "audit"))
    )
    notifications_enabled: bool = os.getenv(
        "MONITORING_NOTIFICATIONS_ENABLED", "false"
    ).lower() in ("true", "1", "yes")
    health_timeout_seconds: float = float(
        os.getenv("MONITORING_HEALTH_TIMEOUT_SECONDS", "5.0")
    )
    lock_file: Path = Path(
        os.getenv(
            "MONITORING_LOCK_FILE",
            str(BASE_DIR / "reports" / "audit" / ".audit_runner.lock"),
        )
    )


@dataclass(frozen=True)
class IngestionConfig:
    """Ingestion pipeline and real-data collection configuration."""

    network_enabled: bool = os.getenv("INGESTION_NETWORK_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    timeout_seconds: float = float(os.getenv("INGESTION_TIMEOUT_SECONDS", "30.0"))
    connect_timeout_seconds: float = float(
        os.getenv("INGESTION_CONNECT_TIMEOUT_SECONDS", "5.0")
    )
    read_timeout_seconds: float = float(
        os.getenv("INGESTION_READ_TIMEOUT_SECONDS", "25.0")
    )
    max_retries: int = int(os.getenv("INGESTION_MAX_RETRIES", "3"))
    retry_backoff_factor: float = float(
        os.getenv("INGESTION_RETRY_BACKOFF_FACTOR", "0.5")
    )
    user_agent: str = os.getenv(
        "INGESTION_USER_AGENT",
        "OpportunityLens-Collector/1.0 (+https://github.com/opportunitylens)",
    )
    max_records_per_source: int = int(os.getenv("INGESTION_MAX_RECORDS_PER_SOURCE", "50"))
    rate_limit_delay_seconds: float = float(
        os.getenv("INGESTION_RATE_LIMIT_DELAY", "0.5")
    )
    demo_mode: bool = os.getenv("OPPORTUNITYLENS_DEMO_MODE", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    @property
    def timeout_tuple(self) -> tuple[float, float]:
        """Return (connect_timeout, read_timeout) tuple for HTTP requests."""
        return (self.connect_timeout_seconds, self.read_timeout_seconds)


# Global configuration instances
app_config = AppConfig()
snowflake_config = SnowflakeConfig()
ai_config = AIConfig()
quality_config = QualityConfig()
monitoring_config = MonitoringConfig()
ingestion_config = IngestionConfig()

__all__ = [
    "AppConfig",
    "SnowflakeConfig",
    "AIConfig",
    "QualityConfig",
    "MonitoringConfig",
    "IngestionConfig",
    "app_config",
    "snowflake_config",
    "ai_config",
    "quality_config",
    "monitoring_config",
    "ingestion_config",
]

