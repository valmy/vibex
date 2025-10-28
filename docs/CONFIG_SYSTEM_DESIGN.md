# Configuration System Design: Validation, Reloading & Caching

**Document Version**: 1.0
**Date**: 2025-10-27
**Status**: Design Phase (Implementation Pending)
**Scope**: Configuration Validation, Hot-Reloading, and Caching System

---

## 1. Executive Summary

This document outlines the design for enhancing the current configuration management system with three key features:

1. **Configuration Validation** - Validate configuration at startup and runtime
2. **Configuration Reloading** - Hot-reload configuration without restart
3. **Configuration Caching** - Cache frequently accessed config values

---

## 2. Current State Analysis

### 2.1 Existing Architecture

**Current Implementation**:
- `backend/src/app/core/config.py` - Pydantic BaseSettings with 3 environment profiles
- `backend/.env` - Environment variables file
- Global `config` instance loaded at startup
- Used throughout: services, routes, database, logging

**Current Limitations**:
- ❌ No validation of required fields at startup
- ❌ No hot-reload capability
- ❌ No caching layer
- ❌ No runtime configuration updates
- ❌ No configuration change notifications

### 2.2 Usage Patterns

Configuration is accessed in:
- `backend/src/app/main.py` - App initialization
- `backend/src/app/services/market_data/service.py` - Service initialization
- `backend/src/app/services/llm_service.py` - LLM configuration
- `backend/src/app/db/session.py` - Database configuration
- All API routes - Logging and error handling

---

## 3. System Design

### 3.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         ConfigurationManager (Singleton)            │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │                                                      │  │
│  │  ┌─────────────────────────────────────────────┐   │  │
│  │  │  ConfigValidator                           │   │  │
│  │  │  - Validate required fields                │   │  │
│  │  │  - Validate field types                    │   │  │
│  │  │  - Validate field ranges                   │   │  │
│  │  │  - Custom validation rules                 │   │  │
│  │  └─────────────────────────────────────────────┘   │  │
│  │                                                      │  │
│  │  ┌─────────────────────────────────────────────┐   │  │
│  │  │  ConfigCache                               │   │  │
│  │  │  - In-memory cache with TTL                │   │  │
│  │  │  - Cache invalidation                      │   │  │
│  │  │  - Cache statistics                        │   │  │
│  │  └─────────────────────────────────────────────┘   │  │
│  │                                                      │  │
│  │  ┌─────────────────────────────────────────────┐   │  │
│  │  │  ConfigReloader                            │   │  │
│  │  │  - Watch .env file changes                 │   │  │
│  │  │  - Reload configuration                    │   │  │
│  │  │  - Notify subscribers                      │   │  │
│  │  │  - Rollback on error                       │   │  │
│  │  └─────────────────────────────────────────────┘   │  │
│  │                                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Component Specifications

#### 3.2.1 ConfigValidator

**Purpose**: Validate configuration values at startup and runtime

**Responsibilities**:
- Validate required fields are present
- Validate field types match expected types
- Validate field values are within acceptable ranges
- Validate API keys format
- Validate URLs are valid
-- Validate leverage limits (1.0-25.0)
-- Validate position size limits (20.0-100000.0 USD)
-- Validate intervals are supported (1m, 3m, 5m, 15m, 1h, 4h, 1d)
- Validate assets are non-empty
- Validate database URL format

**Key Methods**:
```python
class ConfigValidator:
    def validate_all(config: BaseConfig) -> List[ValidationError]
    def validate_required_fields(config: BaseConfig) -> List[ValidationError]
    def validate_field_types(config: BaseConfig) -> List[ValidationError]
    def validate_field_ranges(config: BaseConfig) -> List[ValidationError]
    def validate_api_keys(config: BaseConfig) -> List[ValidationError]
    def validate_urls(config: BaseConfig) -> List[ValidationError]
    def validate_trading_params(config: BaseConfig) -> List[ValidationError]
```

**Validation Rules**:
- Required: ASTERDEX_API_KEY, ASTERDEX_API_SECRET, OPENROUTER_API_KEY, DATABASE_URL
- Leverage: 1.0 ≤ value ≤ 25.0
- Position Size: 20.0 ≤ value ≤ 100000.0
- Intervals: Must be in {1m, 3m, 5m, 15m, 1h, 4h, 1d}
- Assets: Non-empty comma-separated list
- URLs: Accepts HTTP/HTTPS and database URLs (postgresql, mysql, sqlite, mongodb)
- API Keys: Non-empty strings

#### 3.2.2 ConfigCache

**Purpose**: Cache frequently accessed configuration values

**Responsibilities**:
- Store configuration values in memory
- Implement TTL-based expiration
- Provide cache hit/miss statistics
- Support cache invalidation
- Thread-safe access

**Key Methods**:
```python
class ConfigCache:
    def get(key: str, default=None) -> Any
    def set(key: str, value: Any, ttl: int = 3600) -> None
    def invalidate(key: str) -> None
    def invalidate_all() -> None
    def get_stats() -> CacheStats
    def is_expired(key: str) -> bool
```

**Cache Strategy**:
- Default TTL: 3600 seconds (1 hour)
- Cached values: Frequently accessed config (ASSETS, INTERVAL, LLM_MODEL)
- Cache invalidation: On configuration reload
- Statistics: Hit rate, miss rate, evictions

#### 3.2.3 ConfigReloader

**Purpose**: Enable hot-reloading of configuration without restart

**Responsibilities**:
- Watch .env file for changes
- Detect configuration changes
- Reload configuration
- Validate new configuration
- Notify subscribers of changes
- Rollback on validation failure
- Maintain change history

**Key Methods**:
```python
class ConfigReloader:
    async def start_watching() -> None
    async def stop_watching() -> None
    async def reload_config() -> bool
    def subscribe(callback: Callable) -> str
    def unsubscribe(subscription_id: str) -> None
    def get_change_history() -> List[ConfigChange]
    async def rollback_to_previous() -> bool
```

**Change Notification**:
- Subscribers notified of configuration changes
- Callback signature: `async def on_config_change(old_config, new_config, changes: Dict)`
- Changes dict contains: `{field_name: (old_value, new_value)}`

#### 3.2.4 ConfigurationManager

**Purpose**: Orchestrate all configuration operations

**Responsibilities**:
- Manage validator, cache, and reloader
- Provide unified configuration interface
- Handle initialization and shutdown
- Manage configuration lifecycle
- Provide configuration status

**Key Methods**:
```python
class ConfigurationManager:
    async def initialize() -> None
    async def shutdown() -> None
    def get_config() -> BaseConfig
    def get_cached(key: str) -> Any
    def validate_config(config: BaseConfig) -> bool
    async def reload_config() -> bool
    def subscribe_to_changes(callback: Callable) -> str
    def get_status() -> ConfigStatus
```

---

## 4. Implementation Details

### 4.1 File Structure

```
backend/src/app/core/
├── config.py                    # Existing (unchanged)
├── config_validator.py          # NEW - Validation logic
├── config_cache.py              # NEW - Caching logic
├── config_reloader.py           # NEW - Reloading logic
├── config_manager.py            # NEW - Orchestration
└── config_exceptions.py         # NEW - Config-specific exceptions
```

### 4.2 Exception Hierarchy

```python
ConfigurationError (existing)
├── ConfigValidationError
│   ├── MissingRequiredFieldError
│   ├── InvalidFieldTypeError
│   ├── InvalidFieldValueError
│   └── InvalidConfigurationError
├── ConfigReloadError
│   ├── FileWatchError
│   └── ReloadFailedError
└── ConfigCacheError
    └── CacheOperationError
```

### 4.3 Integration Points

**Startup Sequence**:
1. Load configuration (existing)
2. Initialize ConfigurationManager
3. Validate configuration
4. Initialize cache
5. Start file watcher (optional, configurable)
6. Initialize services

**Shutdown Sequence**:
1. Stop file watcher
2. Flush cache
3. Shutdown ConfigurationManager

**Service Integration**:
- Services subscribe to configuration changes
- Services update internal state on reload
- Services validate new configuration before applying

---

## 5. Configuration Reload Scenarios

### 5.1 Supported Reloads

**Hot-Reloadable**:
- ✅ LLM_MODEL - Update LLM model without restart
- ✅ ASSETS - Add/remove trading assets
- ✅ INTERVAL - Change trading interval
- ✅ LOG_LEVEL - Change logging level
- ✅ LEVERAGE - Update leverage limits
- ✅ MAX_POSITION_SIZE_USD - Update position size limits

**Requires Restart**:
- ❌ DATABASE_URL - Database connection
- ❌ ENVIRONMENT - Environment type
- ❌ API_HOST - Server host
- ❌ API_PORT - Server port
- ❌ ASTERDEX_API_KEY/SECRET - API credentials (security)
- ❌ OPENROUTER_API_KEY - API credentials (security)

### 5.2 Reload Workflow

```
1. Detect .env file change
   ↓
2. Load new configuration
   ↓
3. Validate new configuration
   ↓
4. Compare with current configuration
   ↓
5. Identify changed fields
   ↓
6. Check if changes are hot-reloadable
   ↓
7. If not hot-reloadable:
   - Log warning
   - Reject reload
   - Notify user
   ↓
8. If hot-reloadable:
   - Update cache
   - Notify subscribers
   - Services update state
   ↓
9. Log configuration change
```

---

## 6. API Endpoints (Future)

### 6.1 Configuration Management Endpoints

```
GET  /api/v1/admin/config              # Get current configuration
GET  /api/v1/admin/config/status       # Get configuration status
POST /api/v1/admin/config/reload       # Trigger configuration reload
GET  /api/v1/admin/config/history      # Get configuration change history
GET  /api/v1/admin/config/cache/stats  # Get cache statistics
POST /api/v1/admin/config/cache/clear  # Clear configuration cache
POST /api/v1/admin/config/validate     # Validate configuration
```

---

## 7. Monitoring & Observability

### 7.1 Metrics

- Configuration reload count
- Configuration validation failures
- Cache hit/miss ratio
- Configuration change frequency
- Reload duration
- Validation duration

### 7.2 Logging

- Configuration loaded
- Configuration validated
- Configuration reloaded
- Configuration validation failed
- Configuration change detected
- Reload failed/succeeded
- Cache operations

---

## 8. Security Considerations

### 8.1 Sensitive Fields

- ASTERDEX_API_KEY
- ASTERDEX_API_SECRET
- OPENROUTER_API_KEY
- DATABASE_URL (contains password)

**Protection**:
- Never log sensitive values
- Mask in logs and responses
- Prevent reload of sensitive fields
- Validate API key format only

### 8.2 Access Control

- Configuration endpoints require admin role
- Configuration changes logged with user info
- Configuration reload requires explicit permission

---

## 9. Testing Strategy

### 9.1 Unit Tests

- ConfigValidator: Test all validation rules
- ConfigCache: Test TTL, invalidation, statistics
- ConfigReloader: Test file watching, reload logic
- ConfigurationManager: Test orchestration

### 9.2 Integration Tests

- Configuration reload with service updates
- Cache invalidation on reload
- Subscriber notifications
- Rollback on validation failure

### 9.3 End-to-End Tests

- Full reload workflow
- Multiple subscribers
- Concurrent access
- Error scenarios

---

## 10. Future Enhancements

1. **Configuration Profiles** - Support multiple profiles (dev, staging, prod)
2. **Configuration Versioning** - Track configuration versions
3. **Configuration Rollback** - Rollback to previous configuration
4. **Configuration Encryption** - Encrypt sensitive values
5. **Remote Configuration** - Load from remote server
6. **Feature Flags** - Dynamic feature toggling
7. **A/B Testing** - Configuration-based A/B testing
8. **Configuration Audit** - Audit trail of changes

---

## 11. Implementation Roadmap

**Phase 1** (Week 1):
- ConfigValidator implementation
- ConfigCache implementation
- Unit tests

**Phase 2** (Week 2):
- ConfigReloader implementation
- ConfigurationManager implementation
- Integration tests

**Phase 3** (Week 3):
- API endpoints
- Admin dashboard
- E2E tests

**Phase 4** (Week 4):
- Monitoring & observability
- Documentation
- Performance optimization

---

## 12. Success Criteria

- ✅ All configuration values validated at startup
- ✅ Configuration can be reloaded without restart
- ✅ Configuration changes cached for performance
- ✅ Services notified of configuration changes
- ✅ 95%+ cache hit rate for frequently accessed values
- ✅ Configuration reload completes in <1 second
- ✅ Zero data loss during reload
- ✅ Comprehensive test coverage (>90%)

---

## 13. References

- Current Config: `backend/src/app/core/config.py`
- Exceptions: `backend/src/app/core/exceptions.py`
- Main App: `backend/src/app/main.py`
- Services: `backend/src/app/services/`

---

**Document Status**: Ready for Implementation
**Next Step**: Create implementation tasks based on this design

