"""
Unit tests for the configuration validator.

Tests all validation rules including required fields, types, ranges, and formats.
"""

import pytest

from app.core.config import BaseConfig
from app.core.config_validator import ConfigValidator


@pytest.fixture
def validator():
    """Create a validator instance."""
    return ConfigValidator()


@pytest.fixture
def valid_config():
    """Create a valid configuration for testing."""
    return BaseConfig(
        APP_NAME="Test App",
        APP_VERSION="1.0.0",
        ENVIRONMENT="development",
        DEBUG=True,
        API_HOST="0.0.0.0",
        API_PORT=3000,
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        LOG_LEVEL="INFO",
        LOG_FORMAT="json",
        ASTERDEX_API_KEY="test_key",
        ASTERDEX_API_SECRET="test_secret",
        ASTERDEX_BASE_URL="https://fapi.asterdex.com",
        OPENROUTER_API_KEY="test_router_key",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        LLM_MODEL="x-ai/grok-4",
        ASSETS="BTC,ETH,SOL",
        INTERVAL="1h",
        LONG_INTERVAL="4h",
        LEVERAGE=2.0,
        MAX_POSITION_SIZE_USD=10000.0,
    )


@pytest.mark.asyncio
async def test_validate_all_with_valid_config(validator, valid_config):
    """Test validation of a valid configuration."""
    errors = await validator.validate_all(valid_config)
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_validate_required_fields_missing(validator):
    """Test validation fails when required fields are missing."""
    config = BaseConfig(
        ASTERDEX_API_KEY="",  # Empty required field
        ASTERDEX_API_SECRET="test",
        OPENROUTER_API_KEY="test",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
    )
    errors = await validator.validate_required_fields(config)
    assert len(errors) > 0
    assert any("ASTERDEX_API_KEY" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_field_types(validator, valid_config):
    """Test field type validation."""
    # Modify config to have wrong type
    valid_config.API_PORT = "3000"  # Should be int
    errors = await validator.validate_field_types(valid_config)
    assert len(errors) > 0
    assert any("API_PORT" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_leverage_range(validator, valid_config):
    """Test leverage range validation."""
    # Test too low
    valid_config.LEVERAGE = 0.5
    errors = await validator.validate_field_ranges(valid_config)
    assert len(errors) > 0
    assert any("LEVERAGE" in error for error in errors)

    # Test too high (above updated max 25.0)
    valid_config.LEVERAGE = 30.0
    errors = await validator.validate_field_ranges(valid_config)
    assert len(errors) > 0
    assert any("LEVERAGE" in error for error in errors)

    # Test valid
    valid_config.LEVERAGE = 2.0
    errors = await validator.validate_field_ranges(valid_config)
    assert not any("LEVERAGE" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_position_size_range(validator, valid_config):
    """Test position size range validation."""
    # Test too low (below updated min 20.0)
    valid_config.MAX_POSITION_SIZE_USD = 10.0
    errors = await validator.validate_field_ranges(valid_config)
    assert len(errors) > 0
    assert any("MAX_POSITION_SIZE_USD" in error for error in errors)

    # Test too high
    valid_config.MAX_POSITION_SIZE_USD = 200000.0
    errors = await validator.validate_field_ranges(valid_config)
    assert len(errors) > 0
    assert any("MAX_POSITION_SIZE_USD" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_api_port_range(validator, valid_config):
    """Test API port range validation."""
    # Test invalid port
    valid_config.API_PORT = 70000
    errors = await validator.validate_field_ranges(valid_config)
    assert len(errors) > 0
    assert any("API_PORT" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_api_keys(validator, valid_config):
    """Test API key validation."""
    # Test empty API key
    valid_config.ASTERDEX_API_KEY = ""
    errors = await validator.validate_api_keys(valid_config)
    assert len(errors) > 0
    assert any("ASTERDEX_API_KEY" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_urls(validator, valid_config):
    """Test URL validation."""
    # Test invalid URL
    valid_config.ASTERDEX_BASE_URL = "not-a-url"
    errors = await validator.validate_urls(valid_config)
    assert len(errors) > 0
    assert any("ASTERDEX_BASE_URL" in error for error in errors)

    # Test valid URL
    valid_config.ASTERDEX_BASE_URL = "https://fapi.asterdex.com"
    errors = await validator.validate_urls(valid_config)
    assert not any("ASTERDEX_BASE_URL" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_interval(validator, valid_config):
    """Test interval validation."""
    # Test invalid interval
    valid_config.INTERVAL = "6h"
    errors = await validator.validate_trading_params(valid_config)
    assert len(errors) > 0
    assert any("INTERVAL" in error for error in errors)

    # Test valid intervals
    for interval in ["5m", "1h", "2h", "4h", "1d"]:
        valid_config.INTERVAL = interval
        errors = await validator.validate_trading_params(valid_config)
        assert not any("INTERVAL" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_assets(validator, valid_config):
    """Test assets validation."""
    # Test empty assets
    valid_config.ASSETS = ""
    errors = await validator.validate_trading_params(valid_config)
    assert len(errors) > 0
    assert any("ASSETS" in error for error in errors)

    # Test valid assets
    valid_config.ASSETS = "BTC,ETH,SOL"
    errors = await validator.validate_trading_params(valid_config)
    assert not any("ASSETS" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_log_level(validator, valid_config):
    """Test log level validation."""
    # Test invalid log level
    valid_config.LOG_LEVEL = "INVALID"
    errors = await validator.validate_trading_params(valid_config)
    assert len(errors) > 0
    assert any("LOG_LEVEL" in error for error in errors)

    # Test valid log levels
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        valid_config.LOG_LEVEL = level
        errors = await validator.validate_trading_params(valid_config)
        assert not any("LOG_LEVEL" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_environment(validator, valid_config):
    """Test environment validation."""
    # Test invalid environment
    valid_config.ENVIRONMENT = "staging"
    errors = await validator.validate_trading_params(valid_config)
    assert len(errors) > 0
    assert any("ENVIRONMENT" in error for error in errors)

    # Test valid environments
    for env in ["development", "testing", "production"]:
        valid_config.ENVIRONMENT = env
        errors = await validator.validate_trading_params(valid_config)
        assert not any("ENVIRONMENT" in error for error in errors)


@pytest.mark.asyncio
async def test_validate_network(validator, valid_config):
    """Test network validation."""
    # Test invalid network
    valid_config.ASTERDEX_NETWORK = "devnet"
    errors = await validator.validate_trading_params(valid_config)
    assert len(errors) > 0
    assert any("ASTERDEX_NETWORK" in error for error in errors)

    # Test valid networks
    for network in ["mainnet", "testnet"]:
        valid_config.ASTERDEX_NETWORK = network
        errors = await validator.validate_trading_params(valid_config)
        assert not any("ASTERDEX_NETWORK" in error for error in errors)


def test_is_valid_url():
    """Test URL validation helper."""
    validator = ConfigValidator()

    # Test valid URLs
    assert validator._is_valid_url("https://example.com")
    assert validator._is_valid_url("http://localhost:8000")
    assert validator._is_valid_url("https://api.example.com/v1")

    # Test invalid URLs
    assert not validator._is_valid_url("not-a-url")
    assert not validator._is_valid_url("ftp://example.com")
    assert not validator._is_valid_url("")
