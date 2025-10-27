"""
Configuration manager for the AI Trading Agent application.

Orchestrates configuration validation, caching, and reloading as a singleton,
providing a unified interface for configuration management.
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .config import BaseConfig, get_config
from .config_cache import ConfigCache, CacheStats
from .config_exceptions import ConfigValidationError
from .config_reloader import ConfigReloader
from .config_validator import ConfigValidator
from .logging import get_logger

logger = get_logger(__name__)


class ConfigStatus:
    """Configuration status information."""

    def __init__(
        self,
        is_valid: bool = False,
        last_validated: Optional[datetime] = None,
        validation_errors: Optional[List[str]] = None,
        cache_stats: Optional[CacheStats] = None,
        is_watching: bool = False,
        last_reload: Optional[datetime] = None,
        reload_count: int = 0,
    ):
        """
        Initialize configuration status.

        Args:
            is_valid: Whether configuration is valid
            last_validated: Last validation timestamp
            validation_errors: List of validation errors
            cache_stats: Cache statistics
            is_watching: Whether file watching is active
            last_reload: Last reload timestamp
            reload_count: Number of reloads performed
        """
        self.is_valid = is_valid
        self.last_validated = last_validated
        self.validation_errors = validation_errors or []
        self.cache_stats = cache_stats
        self.is_watching = is_watching
        self.last_reload = last_reload
        self.reload_count = reload_count

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert status to dictionary.

        Returns:
            Dictionary representation of status
        """
        return {
            "is_valid": self.is_valid,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
            "validation_errors": self.validation_errors,
            "cache_stats": self.cache_stats.to_dict() if self.cache_stats else None,
            "is_watching": self.is_watching,
            "last_reload": self.last_reload.isoformat() if self.last_reload else None,
            "reload_count": self.reload_count,
        }


class ConfigurationManager:
    """Singleton manager for configuration validation, caching, and reloading."""

    _instance: Optional["ConfigurationManager"] = None

    def __new__(cls) -> "ConfigurationManager":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the configuration manager."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._config = get_config()
        self._validator = ConfigValidator()
        self._cache = ConfigCache()
        self._reloader = ConfigReloader()
        self._is_initialized = False
        self._last_validated: Optional[datetime] = None
        self._validation_errors: List[str] = []
        self._reload_count = 0

    async def initialize(self) -> None:
        """
        Initialize the configuration manager.

        Validates configuration, initializes cache, and starts file watcher.
        """
        if self._is_initialized:
            logger.warning("Configuration manager is already initialized")
            return

        try:
            logger.info("Initializing configuration manager...")

            # Validate configuration
            self._validation_errors = await self._validator.validate_all(self._config)
            self._last_validated = datetime.utcnow()

            if self._validation_errors:
                logger.error(
                    f"Configuration validation failed with {len(self._validation_errors)} error(s)"
                )
                raise ConfigValidationError(
                    "Configuration validation failed", self._validation_errors
                )

            logger.info("Configuration validated successfully")

            # Initialize cache
            await self._cache.start_cleanup_task()
            logger.info("Configuration cache initialized")

            # Initialize reloader
            try:
                await self._reloader.start_watching()
                logger.info("Configuration file watcher started")
            except Exception as e:
                logger.warning(f"Failed to start file watcher: {e}")
                # Don't fail initialization if file watching fails

            self._is_initialized = True
            logger.info("Configuration manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize configuration manager: {e}", exc_info=True)
            raise

    async def shutdown(self) -> None:
        """Shutdown the configuration manager."""
        if not self._is_initialized:
            return

        try:
            logger.info("Shutting down configuration manager...")

            # Stop file watcher
            await self._reloader.stop_watching()

            # Stop cache cleanup task
            await self._cache.stop_cleanup_task()

            # Invalidate cache
            await self._cache.invalidate_all()

            self._is_initialized = False
            logger.info("Configuration manager shut down successfully")

        except Exception as e:
            logger.error(f"Error during configuration manager shutdown: {e}", exc_info=True)

    def get_config(self) -> BaseConfig:
        """
        Get the current configuration.

        Returns:
            Current configuration object
        """
        return self._config

    async def get_cached(self, key: str, default: Any = None) -> Any:
        """
        Get a cached configuration value.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        return await self._cache.get(key, default)

    async def set_cached(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a cached configuration value.

        Args:
            key: Configuration key
            value: Value to cache
            ttl: Time to live in seconds
        """
        await self._cache.set(key, value, ttl)

    async def validate_config(self, config: Optional[BaseConfig] = None) -> bool:
        """
        Validate configuration.

        Args:
            config: Configuration to validate (uses current if not specified)

        Returns:
            True if valid, False otherwise
        """
        config = config or self._config
        self._validation_errors = await self._validator.validate_all(config)
        self._last_validated = datetime.utcnow()
        return len(self._validation_errors) == 0

    async def reload_config(self) -> bool:
        """
        Reload configuration from .env file.

        Returns:
            True if reload was successful, False otherwise
        """
        success = await self._reloader.reload_config()
        if success:
            self._reload_count += 1
        return success

    def subscribe_to_changes(self, callback: Callable) -> str:
        """
        Subscribe to configuration changes.

        Args:
            callback: Async callback function

        Returns:
            Subscription ID
        """
        return self._reloader.subscribe(callback)

    def unsubscribe_from_changes(self, subscription_id: str) -> None:
        """
        Unsubscribe from configuration changes.

        Args:
            subscription_id: Subscription ID
        """
        self._reloader.unsubscribe(subscription_id)

    async def get_status(self) -> ConfigStatus:
        """
        Get configuration status.

        Returns:
            ConfigStatus object
        """
        cache_stats = await self._cache.get_stats()
        return ConfigStatus(
            is_valid=len(self._validation_errors) == 0,
            last_validated=self._last_validated,
            validation_errors=self._validation_errors,
            cache_stats=cache_stats,
            is_watching=self._reloader._watching,
            reload_count=self._reload_count,
        )

    async def invalidate_cache(self, key: Optional[str] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            key: Specific key to invalidate (invalidates all if not specified)
        """
        if key:
            await self._cache.invalidate(key)
        else:
            await self._cache.invalidate_all()

    def get_change_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get configuration change history.

        Args:
            limit: Maximum number of changes to return

        Returns:
            List of configuration changes
        """
        return self._reloader.get_change_history(limit)


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """
    Get the global configuration manager instance.

    Returns:
        ConfigurationManager singleton instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager

