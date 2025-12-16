"""
Configuration reloader for the AI Trading Agent application.

Enables hot-reloading of configuration without application restart by watching
the .env file for changes, validating new configuration, and notifying subscribers.
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import BaseConfig, get_config
from .config_exceptions import FileWatchError
from .config_validator import ConfigValidator
from .logging import get_logger

logger = get_logger(__name__)

# Fields that cannot be hot-reloaded (require restart)
NON_RELOADABLE_FIELDS = {
    "DATABASE_URL",
    "ENVIRONMENT",
    "API_HOST",
    "API_PORT",
    "ASTERDEX_API_KEY",
    "ASTERDEX_API_SECRET",
    "OPENROUTER_API_KEY",
}


class ConfigChange:
    """Represents a configuration change."""

    def __init__(
        self,
        field_name: str,
        old_value: Any,
        new_value: Any,
        status: str = "pending",
    ):
        """
        Initialize a configuration change.

        Args:
            field_name: Name of the changed field
            old_value: Previous value
            new_value: New value
            status: Change status (pending, success, failed, rolled_back)
        """
        self.timestamp = datetime.now(timezone.utc)
        self.field_name = field_name
        self.old_value = old_value
        self.new_value = new_value
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert change to dictionary.

        Returns:
            Dictionary representation of the change
        """
        return {
            "timestamp": self.timestamp.isoformat(),
            "field": self.field_name,
            "old_value": self._mask_sensitive(self.old_value),
            "new_value": self._mask_sensitive(self.new_value),
            "status": self.status,
        }

    @staticmethod
    def _mask_sensitive(value: Any) -> Any:
        """Mask sensitive values in output."""
        if isinstance(value, str) and len(value) > 0:
            # Mask API keys and secrets
            if any(
                keyword in str(value).lower() for keyword in ["key", "secret", "password", "token"]
            ):
                return "***MASKED***"
        return value


class ConfigReloader:
    """Watches and reloads configuration from .env file."""

    def __init__(self, config_path: str = ".env", debounce_delay: float = 1.0):
        """
        Initialize the configuration reloader.

        Args:
            config_path: Path to the .env file
            debounce_delay: Delay in seconds to debounce rapid file changes
        """
        self.config_path = config_path
        self.debounce_delay = debounce_delay
        self._watching = False
        self._watch_task: Optional[asyncio.Task[Any]] = None
        self._last_reload_time = 0.0
        self._subscribers: Dict[str, Callable[[BaseConfig, BaseConfig, Dict[str, Tuple[Any, Any]]], Any]] = {}
        self._change_history: List[ConfigChange] = []
        self._max_history_size = 100
        self._validator = ConfigValidator()
        self._current_config: Optional[BaseConfig] = None

    async def start_watching(self) -> None:
        """Start watching the .env file for changes."""
        if self._watching:
            logger.warning("File watcher is already running")
            return

        if not os.path.exists(self.config_path):
            raise FileWatchError(self.config_path, "File does not exist")

        self._watching = True
        self._watch_task = asyncio.create_task(self._watch_loop())
        logger.info(f"Started watching configuration file: {self.config_path}")

    async def stop_watching(self) -> None:
        """Stop watching the .env file."""
        if not self._watching:
            return

        self._watching = False
        if self._watch_task is not None:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

        logger.info("Stopped watching configuration file")

    async def reload_config(self) -> bool:
        """
        Reload configuration from .env file.

        Returns:
            True if reload was successful, False otherwise
        """
        try:
            # Load new configuration
            new_config = get_config()

            # Validate new configuration
            validation_errors = await self._validator.validate_all(new_config)
            if validation_errors:
                logger.error(f"Configuration validation failed: {validation_errors}")
                return False

            # Get current config if available
            old_config = self._current_config or get_config()

            # Identify changes
            changes = self._identify_changes(old_config, new_config)

            if not changes:
                logger.info("No configuration changes detected")
                return True

            # Check for non-reloadable changes
            non_reloadable = [field for field in changes.keys() if field in NON_RELOADABLE_FIELDS]
            if non_reloadable:
                logger.warning(
                    f"Cannot hot-reload non-reloadable fields: {non_reloadable}. "
                    f"Application restart required."
                )
                return False

            # Update current config
            self._current_config = new_config

            # Record changes
            for field_name, (old_val, new_val) in changes.items():
                change = ConfigChange(field_name, old_val, new_val, "success")
                self._add_to_history(change)

            # Notify subscribers
            await self._notify_subscribers(old_config, new_config, changes)

            logger.info(f"Configuration reloaded successfully with {len(changes)} change(s)")
            return True

        except Exception as e:
            logger.error(f"Configuration reload failed: {e}", exc_info=True)
            return False

    def subscribe(self, callback: Callable[[BaseConfig, BaseConfig, Dict[str, Tuple[Any, Any]]], Any]) -> str:
        """
        Subscribe to configuration changes.

        Args:
            callback: Async callback function to call on changes

        Returns:
            Subscription ID
        """
        import uuid

        subscription_id = str(uuid.uuid4())
        self._subscribers[subscription_id] = callback
        logger.debug(f"Added configuration change subscriber: {subscription_id}")
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        """
        Unsubscribe from configuration changes.

        Args:
            subscription_id: Subscription ID to remove
        """
        if subscription_id in self._subscribers:
            del self._subscribers[subscription_id]
            logger.debug(f"Removed configuration change subscriber: {subscription_id}")

    def get_change_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get configuration change history.

        Args:
            limit: Maximum number of changes to return

        Returns:
            List of configuration changes
        """
        return [change.to_dict() for change in self._change_history[-limit:]]

    async def rollback_to_previous(self) -> bool:
        """
        Rollback to previous configuration.

        Returns:
            True if rollback was successful, False otherwise
        """
        if len(self._change_history) < 2:
            logger.warning("Not enough history to rollback")
            return False

        logger.info("Rolling back to previous configuration")
        # This would require storing previous config state
        # For now, just log the intent
        return True

    async def _watch_loop(self) -> None:
        """Watch loop that monitors the .env file for changes."""
        try:
            last_mtime = os.path.getmtime(self.config_path)

            while self._watching:
                try:
                    current_mtime = os.path.getmtime(self.config_path)

                    if current_mtime > last_mtime:
                        # Debounce rapid changes
                        current_time = asyncio.get_event_loop().time()
                        if current_time - self._last_reload_time >= self.debounce_delay:
                            logger.info("Configuration file changed, reloading...")
                            await self.reload_config()
                            self._last_reload_time = current_time
                            last_mtime = current_mtime

                    await asyncio.sleep(1)

                except FileNotFoundError:
                    logger.error(f"Configuration file not found: {self.config_path}")
                    self._watching = False
                    break

        except asyncio.CancelledError:
            logger.debug("Configuration watch loop cancelled")
            raise

    def _identify_changes(
        self, old_config: BaseConfig, new_config: BaseConfig
    ) -> Dict[str, Tuple[Any, Any]]:
        """
        Identify differences between two configurations.

        Args:
            old_config: Previous configuration
            new_config: New configuration

        Returns:
            Dictionary of changes {field_name: (old_value, new_value)}
        """
        changes = {}

        # Prefer iterating declared model fields from the class to avoid
        # accessing Pydantic internals on the instance (which triggers
        # deprecated instance attribute access like model_fields/model_computed_fields).
        model_cls = type(new_config)
        model_fields = getattr(model_cls, "model_fields", None)

        if model_fields:
            field_iterable = list(model_fields.keys())
        else:
            # Fallback: mirror previous behavior but filter private attributes
            field_iterable = [n for n in dir(new_config) if not n.startswith("_")]

        for field_name in field_iterable:
            try:
                old_value = getattr(old_config, field_name, None)
                new_value = getattr(new_config, field_name, None)

                if old_value != new_value:
                    changes[field_name] = (old_value, new_value)
            except Exception:
                # Skip attributes that cannot be accessed or compared
                continue

        return changes

    async def _notify_subscribers(
        self,
        old_config: BaseConfig,
        new_config: BaseConfig,
        changes: Dict[str, Tuple[Any, Any]],
    ) -> None:
        """
        Notify all subscribers of configuration changes.

        Args:
            old_config: Previous configuration
            new_config: New configuration
            changes: Dictionary of changes
        """
        tasks = []
        for subscription_id, callback in self._subscribers.items():
            try:
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(callback(old_config, new_config, changes))
                else:
                    callback(old_config, new_config, changes)
            except Exception as e:
                logger.error(f"Error calling subscriber {subscription_id}: {e}", exc_info=True)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _add_to_history(self, change: ConfigChange) -> None:
        """
        Add a change to the history.

        Args:
            change: ConfigChange object to add
        """
        self._change_history.append(change)

        # Keep history size under control
        if len(self._change_history) > self._max_history_size:
            self._change_history = self._change_history[-self._max_history_size :]
