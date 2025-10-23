"""
Configuration management for the AI Trading Agent application.

Supports multiple environments (development, testing, production) with
environment-specific settings and multi-account configuration.
"""

from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class BaseConfig(BaseSettings):
    """Base configuration with common settings for all environments."""

    # Application
    APP_NAME: str = "AI Trading Agent"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", description="Environment: development, testing, production")
    DEBUG: bool = Field(default=False, description="Debug mode")

    # API Server
    API_HOST: str = Field(default="0.0.0.0", description="API server host")
    API_PORT: int = Field(default=3000, description="API server port")
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173", description="CORS allowed origins (comma-separated)")

    # Database
    DATABASE_URL: str = Field(default="postgresql://trading_user:trading_password@postgres:5432/trading_db", description="Database connection URL")
    DATABASE_ECHO: bool = Field(default=False, description="Echo SQL queries")
    DATABASE_POOL_SIZE: int = Field(default=20, description="Database connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, description="Database max overflow connections")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    LOG_FORMAT: str = Field(default="json", description="Log format: json or text")
    LOG_DIR: str = Field(default="logs", description="Directory for log files")

    # AsterDEX Configuration
    ASTERDEX_API_KEY: str = Field(default="", description="AsterDEX API key")
    ASTERDEX_API_SECRET: str = Field(default="", description="AsterDEX API secret")
    ASTERDEX_BASE_URL: str = Field(default="https://fapi.asterdex.com", description="AsterDEX base URL")
    ASTERDEX_NETWORK: str = Field(default="mainnet", description="AsterDEX network: mainnet or testnet")

    # OpenRouter Configuration
    OPENROUTER_API_KEY: str = Field(default="", description="OpenRouter API key")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1", description="OpenRouter base URL")
    OPENROUTER_REFERER: str = Field(default="trading-agent", description="OpenRouter referer")
    OPENROUTER_APP_TITLE: str = Field(default="trading-agent", description="OpenRouter app title")

    # Trading Configuration
    LLM_MODEL: str = Field(default="x-ai/grok-4", description="LLM model to use")
    ASSETS: str = Field(default="BTC,ETH,SOL", description="Assets to trade (comma-separated)")
    INTERVAL: str = Field(default="1h", description="Trading interval: 5m, 1h, 4h, 1d")
    LEVERAGE: float = Field(default=2.0, description="Trading leverage (2x-5x recommended)")
    MAX_POSITION_SIZE_USD: float = Field(default=10000.0, description="Maximum position size in USD")

    # Multi-Account Configuration
    MULTI_ACCOUNT_MODE: bool = Field(default=False, description="Enable multi-account mode")
    ACCOUNT_IDS: str = Field(default="", description="Account IDs (comma-separated)")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    DATABASE_ECHO: bool = True
    DATABASE_URL: str = "postgresql://trading_user:trading_password@postgres:5432/trading_db"


class TestingConfig(BaseConfig):
    """Testing environment configuration."""

    ENVIRONMENT: str = "testing"
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    DATABASE_ECHO: bool = False
    DATABASE_URL: str = "sqlite:///:memory:"
    API_PORT: int = 8000


class ProductionConfig(BaseConfig):
    """Production environment configuration."""

    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "ERROR"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 50
    DATABASE_MAX_OVERFLOW: int = 20


def get_config() -> BaseConfig:
    """
    Get configuration based on ENVIRONMENT variable.

    Returns:
        BaseConfig: Configuration object for the current environment
    """
    import os

    environment = os.getenv("ENVIRONMENT", "development").lower()

    config_map = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
    }

    config_class = config_map.get(environment, DevelopmentConfig)
    return config_class()


# Global configuration instance
config = get_config()

