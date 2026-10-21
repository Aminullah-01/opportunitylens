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
    APP_VERSION: str = "0.2.0-phase2"
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
    """AI Provider configuration for Phase 4.

    Note: Calls to AI providers are intentionally disabled during Phase 1.
    """

    hf_api_key: str = os.getenv("HF_API_KEY", "")
    model_name: str = os.getenv("AI_MODEL_NAME", "meta-llama/Llama-3.2-3B-Instruct")
    openai_api_base: str = os.getenv(
        "OPENAI_API_BASE", "https://api-inference.huggingface.co/v1"
    )

    @property
    def is_configured(self) -> bool:
        """Check if AI provider credentials are provided."""
        return bool(self.hf_api_key)


# Global configuration instances
app_config = AppConfig()
snowflake_config = SnowflakeConfig()
ai_config = AIConfig()
