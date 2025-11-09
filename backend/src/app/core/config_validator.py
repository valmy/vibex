"""
Configuration validator for the AI Trading Agent application.

Validates configuration values at startup and runtime, ensuring all required fields
are present, have correct types, and are within acceptable ranges.
"""

from typing import List
from urllib.parse import urlparse

from .config import BaseConfig
from .logging import get_logger

logger = get_logger(__name__)


class ConfigValidator:
    """Validates configuration values."""

    # Required fields that must be present
    REQUIRED_FIELDS = {
        "ASTERDEX_API_KEY",
        "ASTERDEX_API_SECRET",
        "OPENROUTER_API_KEY",
        "DATABASE_URL",
        "SECRET_KEY",
        "ALGORITHM",
    }

    # Field type expectations
    FIELD_TYPES = {
        "APP_NAME": str,
        "APP_VERSION": str,
        "ENVIRONMENT": str,
        "DEBUG": bool,
        "API_HOST": str,
        "API_PORT": int,
        "CORS_ORIGINS": str,
        "DATABASE_URL": str,
        "DATABASE_ECHO": bool,
        "DATABASE_POOL_SIZE": int,
        "DATABASE_MAX_OVERFLOW": int,
        "LOG_LEVEL": str,
        "LOG_FORMAT": str,
        "LOG_DIR": str,
        "ASTERDEX_API_KEY": str,
        "ASTERDEX_API_SECRET": str,
        "ASTERDEX_BASE_URL": str,
        "ASTERDEX_NETWORK": str,
        "OPENROUTER_API_KEY": str,
        "OPENROUTER_BASE_URL": str,
        "OPENROUTER_REFERER": str,
        "OPENROUTER_APP_TITLE": str,
        "LLM_MODEL": str,
        "ASSETS": str,
        "INTERVAL": str,
        "LONG_INTERVAL": str,
        "LEVERAGE": float,
        "MAX_POSITION_SIZE_USD": float,
        "MULTI_ACCOUNT_MODE": bool,
        "ACCOUNT_IDS": str,
        "SECRET_KEY": str,
        "ALGORITHM": str,
    }

    # Valid values for specific fields
    VALID_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"}
    VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    VALID_ENVIRONMENTS = {"development", "testing", "production"}
    VALID_NETWORKS = {"mainnet", "testnet"}

    # Range constraints
    LEVERAGE_MIN = 1.0
    LEVERAGE_MAX = 25.0
    POSITION_SIZE_MIN = 20.0
    POSITION_SIZE_MAX = 100000.0
    API_PORT_MIN = 1
    API_PORT_MAX = 65535

    async def validate_all(self, config: BaseConfig) -> List[str]:
        """
        Validate all configuration aspects.

        Args:
            config: Configuration object to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        errors.extend(await self.validate_required_fields(config))
        errors.extend(await self.validate_field_types(config))
        errors.extend(await self.validate_field_ranges(config))
        errors.extend(await self.validate_api_keys(config))
        errors.extend(await self.validate_urls(config))
        errors.extend(await self.validate_trading_params(config))

        if errors:
            logger.warning(f"Configuration validation failed with {len(errors)} error(s)")
            for error in errors:
                logger.warning(f"  - {error}")

        return errors

    async def validate_required_fields(self, config: BaseConfig) -> List[str]:
        """
        Validate that all required fields are present and non-empty.

        Args:
            config: Configuration object to validate

        Returns:
            List of validation error messages
        """
        errors = []
        for field_name in self.REQUIRED_FIELDS:
            if not hasattr(config, field_name):
                errors.append(f"Required field '{field_name}' is missing")
                continue

            value = getattr(config, field_name)
            if not value or (isinstance(value, str) and not value.strip()):
                errors.append(f"Required field '{field_name}' is empty")

        return errors

    async def validate_field_types(self, config: BaseConfig) -> List[str]:
        """
        Validate that all fields have correct types.

        Args:
            config: Configuration object to validate

        Returns:
            List of validation error messages
        """
        errors = []
        for field_name, expected_type in self.FIELD_TYPES.items():
            if not hasattr(config, field_name):
                continue

            value = getattr(config, field_name)
            if value is None:
                continue

            if not isinstance(value, expected_type):
                actual_type = type(value).__name__
                expected_name = expected_type.__name__
                errors.append(
                    f"Field '{field_name}' has invalid type. "
                    f"Expected {expected_name}, got {actual_type}"
                )

        return errors

    async def validate_field_ranges(self, config: BaseConfig) -> List[str]:
        """
        Validate that field values are within acceptable ranges.

        Args:
            config: Configuration object to validate

        Returns:
            List of validation error messages
        """
        errors = []

        # Validate LEVERAGE
        if hasattr(config, "LEVERAGE"):
            leverage = config.LEVERAGE
            if not (self.LEVERAGE_MIN <= leverage <= self.LEVERAGE_MAX):
                errors.append(
                    f"LEVERAGE must be between {self.LEVERAGE_MIN} and {self.LEVERAGE_MAX}, "
                    f"got {leverage}"
                )

        # Validate MAX_POSITION_SIZE_USD
        if hasattr(config, "MAX_POSITION_SIZE_USD"):
            position_size = config.MAX_POSITION_SIZE_USD
            if not (self.POSITION_SIZE_MIN <= position_size <= self.POSITION_SIZE_MAX):
                errors.append(
                    f"MAX_POSITION_SIZE_USD must be between {self.POSITION_SIZE_MIN} and "
                    f"{self.POSITION_SIZE_MAX}, got {position_size}"
                )

        # Validate API_PORT
        if hasattr(config, "API_PORT"):
            port = config.API_PORT
            if not (self.API_PORT_MIN <= port <= self.API_PORT_MAX):
                errors.append(
                    f"API_PORT must be between {self.API_PORT_MIN} and {self.API_PORT_MAX}, "
                    f"got {port}"
                )

        # Validate DATABASE_POOL_SIZE
        if hasattr(config, "DATABASE_POOL_SIZE"):
            pool_size = config.DATABASE_POOL_SIZE
            if pool_size < 1:
                errors.append(f"DATABASE_POOL_SIZE must be at least 1, got {pool_size}")

        return errors

    async def validate_api_keys(self, config: BaseConfig) -> List[str]:
        """
        Validate API key format and presence.

        Args:
            config: Configuration object to validate

        Returns:
            List of validation error messages
        """
        errors = []

        # Validate ASTERDEX_API_KEY
        if hasattr(config, "ASTERDEX_API_KEY"):
            if not config.ASTERDEX_API_KEY or not isinstance(config.ASTERDEX_API_KEY, str):
                errors.append("ASTERDEX_API_KEY must be a non-empty string")

        # Validate ASTERDEX_API_SECRET
        if hasattr(config, "ASTERDEX_API_SECRET"):
            if not config.ASTERDEX_API_SECRET or not isinstance(config.ASTERDEX_API_SECRET, str):
                errors.append("ASTERDEX_API_SECRET must be a non-empty string")

        # Validate OPENROUTER_API_KEY
        if hasattr(config, "OPENROUTER_API_KEY"):
            if not config.OPENROUTER_API_KEY or not isinstance(config.OPENROUTER_API_KEY, str):
                errors.append("OPENROUTER_API_KEY must be a non-empty string")

        # Validate SECRET_KEY
        if hasattr(config, "SECRET_KEY"):
            if not config.SECRET_KEY or not isinstance(config.SECRET_KEY, str):
                errors.append("SECRET_KEY must be a non-empty string")

        return errors

    async def validate_urls(self, config: BaseConfig) -> List[str]:
        """
        Validate URL format for URL fields.

        Args:
            config: Configuration object to validate

        Returns:
            List of validation error messages
        """
        errors = []
        url_fields = {
            "ASTERDEX_BASE_URL": (
                config.ASTERDEX_BASE_URL if hasattr(config, "ASTERDEX_BASE_URL") else None
            ),
            "OPENROUTER_BASE_URL": (
                config.OPENROUTER_BASE_URL if hasattr(config, "OPENROUTER_BASE_URL") else None
            ),
            "DATABASE_URL": config.DATABASE_URL if hasattr(config, "DATABASE_URL") else None,
        }

        for field_name, url in url_fields.items():
            if url and not self._is_valid_url(url):
                errors.append(f"Field '{field_name}' has invalid URL format: {url}")

        return errors

    async def validate_trading_params(self, config: BaseConfig) -> List[str]:
        """
        Validate trading-specific parameters.

        Args:
            config: Configuration object to validate

        Returns:
            List of validation error messages
        """
        errors = []

        # Validate INTERVAL
        if hasattr(config, "INTERVAL"):
            if config.INTERVAL not in self.VALID_INTERVALS:
                errors.append(
                    f"INTERVAL must be one of {self.VALID_INTERVALS}, got {config.INTERVAL}"
                )

        # Validate LONG_INTERVAL
        if hasattr(config, "LONG_INTERVAL"):
            if config.LONG_INTERVAL not in self.VALID_INTERVALS:
                errors.append(
                    f"LONG_INTERVAL must be one of {self.VALID_INTERVALS}, "
                    f"got {config.LONG_INTERVAL}"
                )

        # Validate ASSETS
        if hasattr(config, "ASSETS"):
            assets = config.ASSETS.strip()
            if not assets:
                errors.append("ASSETS must be a non-empty comma-separated list")
            else:
                asset_list = [a.strip() for a in assets.split(",")]
                if not all(asset for asset in asset_list):
                    errors.append("ASSETS contains empty values")

        # Validate LOG_LEVEL
        if hasattr(config, "LOG_LEVEL"):
            if config.LOG_LEVEL not in self.VALID_LOG_LEVELS:
                errors.append(
                    f"LOG_LEVEL must be one of {self.VALID_LOG_LEVELS}, got {config.LOG_LEVEL}"
                )

        # Validate ENVIRONMENT
        if hasattr(config, "ENVIRONMENT"):
            if config.ENVIRONMENT not in self.VALID_ENVIRONMENTS:
                errors.append(
                    f"ENVIRONMENT must be one of {self.VALID_ENVIRONMENTS}, "
                    f"got {config.ENVIRONMENT}"
                )

        # Validate ASTERDEX_NETWORK
        if hasattr(config, "ASTERDEX_NETWORK"):
            if config.ASTERDEX_NETWORK not in self.VALID_NETWORKS:
                errors.append(
                    f"ASTERDEX_NETWORK must be one of {self.VALID_NETWORKS}, "
                    f"got {config.ASTERDEX_NETWORK}"
                )

        return errors

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """
        Check if a URL is valid.

        Args:
            url: URL string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            result = urlparse(url)
            # Check if scheme and netloc are present
            # Allow http, https, and database URLs (postgresql, mysql, sqlite, etc.)
            valid_schemes = {"http", "https", "postgresql", "mysql", "sqlite", "mongodb"}
            return all([result.scheme in valid_schemes, result.netloc or result.path])
        except Exception:
            return False
