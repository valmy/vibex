"""
Unit tests for the configuration manager.

Tests orchestration of validator, cache, and reloader components.
"""

import pytest

from app.core.config import BaseConfig
from app.core.config_manager import ConfigStatus, ConfigurationManager, get_config_manager


@pytest.fixture
def manager():
    """Create a configuration manager instance."""
    # Reset singleton for testing
    ConfigurationManager._instance = None
    return get_config_manager()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manager_singleton(manager):
    """Test that ConfigurationManager is a singleton."""
    manager2 = get_config_manager()
    assert manager is manager2


@pytest.mark.asyncio
async def test_manager_get_config(manager):
    """Test getting configuration from manager."""
    config = manager.get_config()
    assert isinstance(config, BaseConfig)


@pytest.mark.asyncio
async def test_manager_validate_config(manager):
    """Test configuration validation."""
    config = manager.get_config()
    is_valid = await manager.validate_config(config)
    assert isinstance(is_valid, bool)


@pytest.mark.asyncio
async def test_manager_cache_operations(manager):
    """Test cache operations through manager."""
    # Set a value
    await manager.set_cached("test_key", "test_value", ttl=3600)

    # Get the value
    value = await manager.get_cached("test_key")
    assert value == "test_value"

    # Get non-existent value
    value = await manager.get_cached("nonexistent", default="default")
    assert value == "default"


@pytest.mark.asyncio
async def test_manager_invalidate_cache(manager):
    """Test cache invalidation through manager."""
    # Set a value
    await manager.set_cached("test_key", "test_value")

    # Invalidate specific key
    await manager.invalidate_cache("test_key")

    # Value should be gone
    value = await manager.get_cached("test_key")
    assert value is None


@pytest.mark.asyncio
async def test_manager_invalidate_all_cache(manager):
    """Test invalidating all cache entries."""
    # Set multiple values
    await manager.set_cached("key1", "value1")
    await manager.set_cached("key2", "value2")

    # Invalidate all
    await manager.invalidate_cache()

    # All values should be gone
    assert await manager.get_cached("key1") is None
    assert await manager.get_cached("key2") is None


@pytest.mark.asyncio
async def test_manager_subscribe_to_changes(manager):
    """Test subscribing to configuration changes."""
    callback_called = False

    async def callback(old_config, new_config, changes):
        nonlocal callback_called
        callback_called = True

    subscription_id = manager.subscribe_to_changes(callback)
    assert subscription_id is not None


@pytest.mark.asyncio
async def test_manager_unsubscribe_from_changes(manager):
    """Test unsubscribing from configuration changes."""

    async def callback(old_config, new_config, changes):
        pass

    subscription_id = manager.subscribe_to_changes(callback)
    manager.unsubscribe_from_changes(subscription_id)

    # Should not raise an error
    manager.unsubscribe_from_changes(subscription_id)


@pytest.mark.asyncio
async def test_manager_get_status(manager):
    """Test getting configuration status."""
    status = await manager.get_status()
    assert isinstance(status, ConfigStatus)
    assert hasattr(status, "is_valid")
    assert hasattr(status, "cache_stats")


@pytest.mark.asyncio
async def test_manager_get_change_history(manager):
    """Test getting configuration change history."""
    history = manager.get_change_history()
    assert isinstance(history, list)


@pytest.mark.asyncio
async def test_manager_initialize(manager):
    """Test manager initialization."""
    await manager.initialize()
    assert manager._is_initialized


@pytest.mark.asyncio
async def test_manager_shutdown(manager):
    """Test manager shutdown."""
    await manager.initialize()
    await manager.shutdown()
    assert not manager._is_initialized


@pytest.mark.asyncio
async def test_manager_double_initialize(manager):
    """Test that double initialization is handled gracefully."""
    await manager.initialize()
    # Should not raise an error
    await manager.initialize()


@pytest.mark.asyncio
async def test_manager_shutdown_without_init(manager):
    """Test shutdown without initialization."""
    # Should not raise an error
    await manager.shutdown()


def test_config_status_to_dict():
    """Test converting ConfigStatus to dictionary."""
    status = ConfigStatus(
        is_valid=True,
        validation_errors=[],
        is_watching=True,
        reload_count=5,
    )

    status_dict = status.to_dict()
    assert status_dict["is_valid"] is True
    assert status_dict["validation_errors"] == []
    assert status_dict["is_watching"] is True
    assert status_dict["reload_count"] == 5


def test_config_status_with_errors():
    """Test ConfigStatus with validation errors."""
    errors = ["Error 1", "Error 2"]
    status = ConfigStatus(
        is_valid=False,
        validation_errors=errors,
    )

    assert status.is_valid is False
    assert status.validation_errors == errors


@pytest.mark.asyncio
async def test_manager_reload_config(manager):
    """Test configuration reload through manager."""
    # This test would require mocking file changes
    # For now, we just test that reload_config returns a boolean
    result = await manager.reload_config()
    assert isinstance(result, bool)
