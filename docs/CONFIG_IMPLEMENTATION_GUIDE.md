# Configuration System Implementation Guide

**Document Version**: 1.0
**Date**: 2025-10-27
**Status**: Implementation Guide (Ready for Development)

---

## 1. Implementation Overview

This guide provides step-by-step instructions for implementing the Configuration Validation, Reloading, and Caching system.

---

## 2. Phase 1: Configuration Validator

### 2.1 File: `backend/src/app/core/config_validator.py`

**Responsibilities**:
- Validate required fields
- Validate field types
- Validate field ranges
- Validate API keys and URLs
- Validate trading parameters

**Key Classes**:
```python
class ValidationRule:
    """Base class for validation rules"""
    field_name: str
    description: str
    async def validate(value: Any) -> Optional[str]  # Returns error message

class ConfigValidator:
    """Main validator class"""
    def __init__(self)
    async def validate_all(config: BaseConfig) -> List[str]
    async def validate_required_fields(config: BaseConfig) -> List[str]
    async def validate_field_types(config: BaseConfig) -> List[str]
    async def validate_field_ranges(config: BaseConfig) -> List[str]
    async def validate_api_keys(config: BaseConfig) -> List[str]
    async def validate_urls(config: BaseConfig) -> List[str]
    async def validate_trading_params(config: BaseConfig) -> List[str]
```

**Validation Rules to Implement**:
1. Required fields: ASTERDEX_API_KEY, ASTERDEX_API_SECRET, OPENROUTER_API_KEY, DATABASE_URL
2. Type validation: Ensure types match (str, int, float, bool)
3. Range validation: Leverage (1.0-25.0), Position Size (20.0-100000.0)
4. Interval validation: Must be in {1m, 3m, 5m, 15m, 1h, 4h, 1d}
5. Assets validation: Non-empty comma-separated list
6. URL validation: Accepts HTTP/HTTPS and database URLs (postgresql, mysql, sqlite, mongodb)
7. API key validation: Non-empty strings (no format check to avoid leaking info)

**Error Handling**:
- Collect all validation errors
- Return list of error messages
- Raise ConfigValidationError if critical errors

---

## 3. Phase 2: Configuration Cache

### 3.1 File: `backend/src/app/core/config_cache.py`

**Responsibilities**:
- Store configuration values in memory
- Implement TTL-based expiration
- Provide cache statistics
- Support cache invalidation

**Key Classes**:
```python
class CacheEntry:
    """Represents a cached value"""
    value: Any
    created_at: datetime
    ttl: int
    hits: int

    def is_expired(self) -> bool

class CacheStats:
    """Cache statistics"""
    total_hits: int
    total_misses: int
    hit_rate: float
    entries_count: int
    memory_usage: int

class ConfigCache:
    """Main cache class"""
    def __init__(self, default_ttl: int = 3600)
    def get(key: str, default=None) -> Any
    def set(key: str, value: Any, ttl: int = None) -> None
    def invalidate(key: str) -> None
    def invalidate_all() -> None
    def get_stats(self) -> CacheStats
    def is_expired(key: str) -> bool
    def cleanup_expired(self) -> int
```

**Cache Strategy**:
- Default TTL: 3600 seconds (1 hour)
- Cached keys: ASSETS, INTERVAL, LONG_INTERVAL, LLM_MODEL, LEVERAGE, MAX_POSITION_SIZE_USD
- Cleanup: Periodic cleanup of expired entries
- Thread-safe: Use asyncio.Lock for concurrent access

**Implementation Notes**:
- Use dict to store entries
- Implement cleanup task (runs every 5 minutes)
- Track statistics for monitoring
- Support partial invalidation

---

## 4. Phase 3: Configuration Reloader

### 4.1 File: `backend/src/app/core/config_reloader.py`

**Responsibilities**:
- Watch .env file for changes
- Detect configuration changes
- Reload configuration
- Notify subscribers
- Maintain change history

**Key Classes**:
```python
class ConfigChange:
    """Represents a configuration change"""
    timestamp: datetime
    field_name: str
    old_value: Any
    new_value: Any
    status: str  # "success", "failed", "rolled_back"

class ConfigReloader:
    """Main reloader class"""
    def __init__(self, config_path: str = ".env")
    async def start_watching(self) -> None
    async def stop_watching(self) -> None
    async def reload_config(self) -> bool
    def subscribe(callback: Callable) -> str
    def unsubscribe(subscription_id: str) -> None
    def get_change_history(self) -> List[ConfigChange]
    async def rollback_to_previous(self) -> bool
```

**File Watching Strategy**:
- Use watchfiles library for file monitoring
- Watch .env file for modifications
- Debounce rapid changes (wait 1 second)
- Handle file not found gracefully

**Reload Workflow**:
1. Detect file change
2. Load new configuration
3. Validate new configuration
4. Compare with current configuration
5. Check if changes are hot-reloadable
6. Update cache
7. Notify subscribers
8. Log changes

**Subscriber Notification**:
```python
async def on_config_change(
    old_config: BaseConfig,
    new_config: BaseConfig,
    changes: Dict[str, Tuple[Any, Any]]
) -> None:
    """Called when configuration changes"""
    pass
```

---

## 5. Phase 4: Configuration Manager

### 5.1 File: `backend/src/app/core/config_manager.py`

**Responsibilities**:
- Orchestrate validator, cache, and reloader
- Provide unified configuration interface
- Handle initialization and shutdown
- Manage configuration lifecycle

**Key Classes**:
```python
class ConfigStatus:
    """Configuration status"""
    is_valid: bool
    last_validated: datetime
    validation_errors: List[str]
    cache_stats: CacheStats
    is_watching: bool
    last_reload: datetime

class ConfigurationManager:
    """Main manager class (Singleton)"""
    def __init__(self)
    async def initialize(self) -> None
    async def shutdown(self) -> None
    def get_config(self) -> BaseConfig
    def get_cached(key: str) -> Any
    def validate_config(config: BaseConfig) -> bool
    async def reload_config(self) -> bool
    def subscribe_to_changes(callback: Callable) -> str
    def get_status(self) -> ConfigStatus
```

**Initialization Sequence**:
1. Load configuration
2. Validate configuration
3. Initialize cache
4. Initialize reloader
5. Start file watcher (if enabled)
6. Log initialization complete

**Shutdown Sequence**:
1. Stop file watcher
2. Flush cache
3. Unsubscribe all listeners
4. Log shutdown complete

---

## 6. Phase 5: Exception Handling

### 6.1 File: `backend/src/app/core/config_exceptions.py`

**Exception Hierarchy**:
```python
class ConfigValidationError(ConfigurationError):
    """Configuration validation failed"""
    errors: List[str]

class MissingRequiredFieldError(ConfigValidationError):
    """Required field is missing"""
    field_name: str

class InvalidFieldTypeError(ConfigValidationError):
    """Field has invalid type"""
    field_name: str
    expected_type: str
    actual_type: str

class InvalidFieldValueError(ConfigValidationError):
    """Field has invalid value"""
    field_name: str
    value: Any
    reason: str

class ConfigReloadError(ConfigurationError):
    """Configuration reload failed"""
    reason: str

class FileWatchError(ConfigReloadError):
    """File watching failed"""
    file_path: str

class CacheOperationError(ConfigurationError):
    """Cache operation failed"""
    operation: str
```

---

## 7. Integration with Existing Code

### 7.1 Update `backend/src/app/core/__init__.py`

```python
from .config import config, get_config
from .config_manager import ConfigurationManager, get_config_manager
from .config_validator import ConfigValidator
from .config_cache import ConfigCache
from .config_reloader import ConfigReloader
from .config_exceptions import (
    ConfigValidationError,
    ConfigReloadError,
    CacheOperationError,
)

__all__ = [
    "config",
    "get_config",
    "ConfigurationManager",
    "get_config_manager",
    "ConfigValidator",
    "ConfigCache",
    "ConfigReloader",
    "ConfigValidationError",
    "ConfigReloadError",
    "CacheOperationError",
]
```

### 7.2 Update `backend/src/app/main.py`

```python
from .core.config_manager import get_config_manager

# In startup event:
@app.on_event("startup")
async def startup_event():
    # Initialize configuration manager
    config_manager = get_config_manager()
    await config_manager.initialize()

    # Validate configuration
    if not config_manager.validate_config(config):
        raise ConfigValidationError("Configuration validation failed")

    # Subscribe to configuration changes
    config_manager.subscribe_to_changes(on_config_change)

# In shutdown event:
@app.on_event("shutdown")
async def shutdown_event():
    config_manager = get_config_manager()
    await config_manager.shutdown()
```

### 7.3 Service Integration

Services should subscribe to configuration changes:

```python
from ..core.config_manager import get_config_manager

class MarketDataService:
    def __init__(self):
        self.config_manager = get_config_manager()
        self.config_manager.subscribe_to_changes(self.on_config_change)

    async def on_config_change(self, old_config, new_config, changes):
        if "ASSETS" in changes or "INTERVAL" in changes:
            # Update service state
            self.assets = [asset.strip() for asset in new_config.ASSETS.split(",")]
            self.interval = new_config.INTERVAL
            logger.info(f"Configuration updated: {changes}")
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

**ConfigValidator Tests**:
- Test each validation rule
- Test with valid/invalid values
- Test error messages

**ConfigCache Tests**:
- Test get/set operations
- Test TTL expiration
- Test cache statistics
- Test invalidation

**ConfigReloader Tests**:
- Test file watching
- Test reload workflow
- Test subscriber notifications
- Test rollback

**ConfigurationManager Tests**:
- Test initialization
- Test shutdown
- Test integration of components

### 8.2 Integration Tests

- Configuration reload with service updates
- Cache invalidation on reload
- Subscriber notifications
- Error handling and rollback

### 8.3 Test Files

```
backend/tests/unit/
├── test_config_validator.py
├── test_config_cache.py
├── test_config_reloader.py
└── test_config_manager.py

backend/tests/integration/
└── test_config_integration.py
```

---

## 9. Configuration for Reloader

### 9.1 Environment Variables

```env
# Configuration Reloader Settings
CONFIG_WATCH_ENABLED=true          # Enable file watching
CONFIG_WATCH_INTERVAL=1            # Watch interval in seconds
CONFIG_CACHE_TTL=3600              # Cache TTL in seconds
CONFIG_VALIDATE_ON_STARTUP=true    # Validate on startup
CONFIG_VALIDATE_ON_RELOAD=true     # Validate on reload
CONFIG_HISTORY_SIZE=100            # Keep last N changes
```

---

## 10. Monitoring & Observability

### 10.1 Metrics to Track

- Configuration reload count
- Configuration validation failures
- Cache hit/miss ratio
- Configuration change frequency
- Reload duration
- Validation duration

### 10.2 Logging

- Configuration loaded
- Configuration validated
- Configuration reloaded
- Configuration validation failed
- Configuration change detected
- Reload failed/succeeded

---

## 11. Deployment Considerations

### 11.1 Production Deployment

- Disable file watching in production (use manual reload)
- Increase cache TTL in production
- Enable configuration validation
- Monitor configuration changes
- Audit trail of changes

### 11.2 Development Deployment

- Enable file watching
- Lower cache TTL
- Enable detailed logging
- Allow manual reload

---

## 12. Success Metrics

- ✅ All configuration values validated at startup
- ✅ Configuration reload completes in <1 second
- ✅ 95%+ cache hit rate
- ✅ Zero data loss during reload
- ✅ Services notified within 100ms
- ✅ >90% test coverage

---

## 13. Timeline

- **Week 1**: ConfigValidator + ConfigCache
- **Week 2**: ConfigReloader + ConfigurationManager
- **Week 3**: Integration + Testing
- **Week 4**: Documentation + Deployment

---

**Status**: Ready for Implementation
**Next Step**: Create implementation tasks and start Phase 1

