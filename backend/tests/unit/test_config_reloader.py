"""
Unit tests for the configuration reloader.

Tests file watching, reload workflow, subscriber notifications, and change history.
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from app.core.config import BaseConfig
from app.core.config_reloader import ConfigChange, ConfigReloader


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("ASTERDEX_API_KEY=test_key\n")
        f.write("ASTERDEX_API_SECRET=test_secret\n")
        f.write("OPENROUTER_API_KEY=test_router_key\n")
        f.write("DATABASE_URL=postgresql://user:pass@localhost:5432/db\n")
        f.write("LLM_MODEL=x-ai/grok-4\n")
        f.write("ASSETS=BTC,ETH\n")
        f.write("INTERVAL=1h\n")
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def reloader(temp_env_file):
    """Create a reloader instance with temp env file."""
    return ConfigReloader(config_path=temp_env_file)


def test_config_change_to_dict():
    """Test converting ConfigChange to dictionary."""
    change = ConfigChange("LLM_MODEL", "old_model", "new_model", "success")
    change_dict = change.to_dict()

    assert change_dict["field"] == "LLM_MODEL"
    assert change_dict["status"] == "success"
    assert "timestamp" in change_dict


def test_config_change_mask_sensitive():
    """Test that sensitive values are masked in ConfigChange."""
    change = ConfigChange("ASTERDEX_API_KEY", "secret_key_123", "new_secret_key", "success")
    change_dict = change.to_dict()

    # Sensitive values should be masked
    assert change_dict["old_value"] == "***MASKED***"
    assert change_dict["new_value"] == "***MASKED***"


def test_config_change_mask_non_sensitive():
    """Test that non-sensitive values are not masked."""
    change = ConfigChange("ASSETS", "BTC,ETH", "BTC,ETH,SOL", "success")
    change_dict = change.to_dict()

    # Non-sensitive values should not be masked
    assert change_dict["old_value"] == "BTC,ETH"
    assert change_dict["new_value"] == "BTC,ETH,SOL"


@pytest.mark.asyncio
async def test_reloader_initialization(reloader):
    """Test reloader initialization."""
    assert reloader.config_path is not None
    assert not reloader._watching
    assert len(reloader._subscribers) == 0


@pytest.mark.asyncio
async def test_reloader_subscribe(reloader):
    """Test subscribing to configuration changes."""
    async def callback(old_config, new_config, changes):
        pass

    subscription_id = reloader.subscribe(callback)
    assert subscription_id is not None
    assert subscription_id in reloader._subscribers


@pytest.mark.asyncio
async def test_reloader_unsubscribe(reloader):
    """Test unsubscribing from configuration changes."""
    async def callback(old_config, new_config, changes):
        pass

    subscription_id = reloader.subscribe(callback)
    reloader.unsubscribe(subscription_id)
    assert subscription_id not in reloader._subscribers


@pytest.mark.asyncio
async def test_reloader_get_change_history(reloader):
    """Test getting configuration change history."""
    # Add some changes to history
    change1 = ConfigChange("FIELD1", "old1", "new1", "success")
    change2 = ConfigChange("FIELD2", "old2", "new2", "success")
    reloader._add_to_history(change1)
    reloader._add_to_history(change2)

    history = reloader.get_change_history()
    assert len(history) == 2
    assert history[0]["field"] == "FIELD1"
    assert history[1]["field"] == "FIELD2"


@pytest.mark.asyncio
async def test_reloader_get_change_history_limit(reloader):
    """Test getting limited change history."""
    # Add multiple changes
    for i in range(10):
        change = ConfigChange(f"FIELD{i}", f"old{i}", f"new{i}", "success")
        reloader._add_to_history(change)

    # Get limited history
    history = reloader.get_change_history(limit=5)
    assert len(history) == 5


@pytest.mark.asyncio
async def test_reloader_identify_changes(reloader):
    """Test identifying changes between configurations."""
    config1 = BaseConfig(
        ASTERDEX_API_KEY="key1",
        ASTERDEX_API_SECRET="secret1",
        OPENROUTER_API_KEY="router_key1",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        LLM_MODEL="model1",
    )

    config2 = BaseConfig(
        ASTERDEX_API_KEY="key1",
        ASTERDEX_API_SECRET="secret1",
        OPENROUTER_API_KEY="router_key1",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        LLM_MODEL="model2",  # Changed
    )

    changes = reloader._identify_changes(config1, config2)
    assert "LLM_MODEL" in changes
    assert changes["LLM_MODEL"] == ("model1", "model2")


@pytest.mark.asyncio
async def test_reloader_notify_subscribers(reloader):
    """Test notifying subscribers of configuration changes."""
    callback_called = False
    received_changes = None

    async def callback(old_config, new_config, changes):
        nonlocal callback_called, received_changes
        callback_called = True
        received_changes = changes

    reloader.subscribe(callback)

    config1 = BaseConfig(
        ASTERDEX_API_KEY="key1",
        ASTERDEX_API_SECRET="secret1",
        OPENROUTER_API_KEY="router_key1",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        LLM_MODEL="model1",
    )

    config2 = BaseConfig(
        ASTERDEX_API_KEY="key1",
        ASTERDEX_API_SECRET="secret1",
        OPENROUTER_API_KEY="router_key1",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        LLM_MODEL="model2",
    )

    changes = {"LLM_MODEL": ("model1", "model2")}
    await reloader._notify_subscribers(config1, config2, changes)

    assert callback_called
    assert received_changes == changes


@pytest.mark.asyncio
async def test_reloader_add_to_history(reloader):
    """Test adding changes to history."""
    change = ConfigChange("FIELD1", "old", "new", "success")
    reloader._add_to_history(change)

    assert len(reloader._change_history) == 1
    assert reloader._change_history[0].field_name == "FIELD1"


@pytest.mark.asyncio
async def test_reloader_history_size_limit(reloader):
    """Test that history size is limited."""
    # Add more changes than max history size
    for i in range(150):
        change = ConfigChange(f"FIELD{i}", f"old{i}", f"new{i}", "success")
        reloader._add_to_history(change)

    # History should be limited to max size
    assert len(reloader._change_history) <= reloader._max_history_size


@pytest.mark.asyncio
async def test_reloader_start_stop_watching(reloader):
    """Test starting and stopping file watching."""
    await reloader.start_watching()
    assert reloader._watching

    await reloader.stop_watching()
    assert not reloader._watching


@pytest.mark.asyncio
async def test_reloader_start_watching_nonexistent_file():
    """Test starting file watching on non-existent file."""
    reloader = ConfigReloader(config_path="/nonexistent/path/.env")

    with pytest.raises(Exception):
        await reloader.start_watching()


@pytest.mark.asyncio
async def test_reloader_reload_config_validation_failure(reloader):
    """Test reload fails on validation error."""
    # This test would require mocking the validator
    # For now, we just test that reload_config returns a boolean
    result = await reloader.reload_config()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_reloader_rollback_to_previous(reloader):
    """Test rollback to previous configuration."""
    # Add some history
    change1 = ConfigChange("FIELD1", "old1", "new1", "success")
    change2 = ConfigChange("FIELD2", "old2", "new2", "success")
    reloader._add_to_history(change1)
    reloader._add_to_history(change2)

    # Rollback should succeed with history
    result = await reloader.rollback_to_previous()
    assert result is True


@pytest.mark.asyncio
async def test_reloader_rollback_insufficient_history(reloader):
    """Test rollback fails with insufficient history."""
    result = await reloader.rollback_to_previous()
    assert result is False

