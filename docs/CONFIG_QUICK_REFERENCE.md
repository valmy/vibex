# Configuration System - Quick Reference

**Date**: 2025-10-27  
**Version**: 1.0

---

## 📚 Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| CONFIG_SYSTEM_DESIGN.md | High-level architecture | Architects, Tech Leads |
| CONFIG_IMPLEMENTATION_GUIDE.md | Step-by-step implementation | Developers |
| CONFIG_API_SPECIFICATION.md | REST API endpoints | API Consumers, Frontend |
| CONFIG_SYSTEM_SUMMARY.md | Complete overview | Everyone |
| CONFIG_QUICK_REFERENCE.md | Quick lookup | Everyone |

---

## 🏗️ System Components

### ConfigValidator
**File**: `backend/src/app/core/config_validator.py`

```python
class ConfigValidator:
    async def validate_all(config) -> List[str]
    async def validate_required_fields(config) -> List[str]
    async def validate_field_types(config) -> List[str]
    async def validate_field_ranges(config) -> List[str]
    async def validate_api_keys(config) -> List[str]
    async def validate_urls(config) -> List[str]
    async def validate_trading_params(config) -> List[str]
```

**Validates**:
- Required fields (API keys, database URL)
- Field types (str, int, float, bool)
- Field ranges (leverage 1.0-5.0, position size 100-100000)
- Intervals (5m, 1h, 4h, 1d)
- Assets (non-empty list)
- URLs (valid HTTP/HTTPS)

---

### ConfigCache
**File**: `backend/src/app/core/config_cache.py`

```python
class ConfigCache:
    def get(key: str, default=None) -> Any
    def set(key: str, value: Any, ttl: int = 3600) -> None
    def invalidate(key: str) -> None
    def invalidate_all() -> None
    def get_stats() -> CacheStats
    def is_expired(key: str) -> bool
```

**Features**:
- TTL-based expiration (default: 1 hour)
- Cache statistics (hit/miss ratio)
- Thread-safe access
- Automatic cleanup

**Cached Keys**:
- ASSETS
- INTERVAL
- LONG_INTERVAL
- LLM_MODEL
- LEVERAGE
- MAX_POSITION_SIZE_USD

---

### ConfigReloader
**File**: `backend/src/app/core/config_reloader.py`

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

**Features**:
- Watch .env file for changes
- Detect configuration changes
- Validate before applying
- Notify subscribers
- Maintain change history
- Rollback support

---

### ConfigurationManager
**File**: `backend/src/app/core/config_manager.py`

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

**Responsibilities**:
- Orchestrate all components
- Provide unified interface
- Manage lifecycle
- Report status

---

## 🔄 Reload Workflow

```
.env file change
    ↓
Load new config
    ↓
Validate
    ↓
Compare with current
    ↓
Check if hot-reloadable
    ↓
Update cache
    ↓
Notify subscribers
    ↓
Services update state
    ↓
Log change
```

---

## ✅ Validation Rules

### Required Fields
```
ASTERDEX_API_KEY
ASTERDEX_API_SECRET
OPENROUTER_API_KEY
DATABASE_URL
```

### Range Validations
```
LEVERAGE: 1.0 ≤ x ≤ 5.0
MAX_POSITION_SIZE_USD: 100 ≤ x ≤ 100000
```

### Enum Validations
```
INTERVAL: {5m, 1h, 4h, 1d}
LONG_INTERVAL: {5m, 1h, 4h, 1d}
ENVIRONMENT: {development, testing, production}
```

---

## 🔄 Hot-Reloadable Fields

✅ Can reload without restart:
- LLM_MODEL
- ASSETS
- INTERVAL
- LONG_INTERVAL
- LOG_LEVEL
- LEVERAGE
- MAX_POSITION_SIZE_USD

❌ Requires restart:
- DATABASE_URL
- ENVIRONMENT
- API_HOST
- API_PORT
- ASTERDEX_API_KEY
- ASTERDEX_API_SECRET
- OPENROUTER_API_KEY

---

## 🔌 API Endpoints

### Configuration Management
```
GET    /api/v1/admin/config
GET    /api/v1/admin/config/status
POST   /api/v1/admin/config/reload
GET    /api/v1/admin/config/history
GET    /api/v1/admin/config/cache/stats
POST   /api/v1/admin/config/cache/clear
POST   /api/v1/admin/config/validate
POST   /api/v1/admin/config/rollback
```

---

## 📊 Cache Statistics

```json
{
  "total_hits": 1250,
  "total_misses": 50,
  "hit_rate": 0.962,
  "entries_count": 12,
  "memory_usage_bytes": 4096
}
```

---

## 🔐 Security

**Sensitive Fields** (never logged):
- ASTERDEX_API_KEY
- ASTERDEX_API_SECRET
- OPENROUTER_API_KEY
- DATABASE_URL

**Protection**:
- Mask in logs
- Mask in responses
- Prevent reload
- Require admin auth
- Audit trail

---

## 📈 Metrics

**Track**:
- Reload count
- Validation failures
- Cache hit/miss ratio
- Change frequency
- Reload duration
- Validation duration

---

## 🧪 Testing

**Unit Tests**:
- ConfigValidator
- ConfigCache
- ConfigReloader
- ConfigurationManager

**Integration Tests**:
- Full reload workflow
- Service updates
- Cache invalidation
- Subscriber notifications

**Test Files**:
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

## 🚀 Implementation Timeline

| Phase | Week | Tasks |
|-------|------|-------|
| 1 | 1 | ConfigValidator + ConfigCache |
| 2 | 2 | ConfigReloader + ConfigurationManager |
| 3 | 3 | API Endpoints + Integration |
| 4 | 4 | Testing + Documentation |

---

## 📝 Integration Checklist

- [ ] Update `backend/src/app/core/__init__.py`
- [ ] Update `backend/src/app/main.py` startup/shutdown
- [ ] Update services to subscribe to changes
- [ ] Add configuration validation at startup
- [ ] Add cache initialization
- [ ] Add file watcher initialization
- [ ] Add subscriber notifications
- [ ] Add API endpoints
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Update documentation

---

## 🎯 Success Criteria

- ✅ All config values validated at startup
- ✅ Configuration reloadable without restart
- ✅ 95%+ cache hit rate
- ✅ Reload completes in <1 second
- ✅ Zero data loss during reload
- ✅ >90% test coverage
- ✅ Services notified within 100ms

---

## 🔗 Related Files

**Current Configuration**:
- `backend/src/app/core/config.py`
- `backend/.env`
- `backend/.env.example`

**Exception Handling**:
- `backend/src/app/core/exceptions.py`

**Main Application**:
- `backend/src/app/main.py`

**Services**:
- `backend/src/app/services/market_data/service.py`
- `backend/src/app/services/llm_service.py`

---

## 💡 Key Concepts

**Singleton Pattern**: ConfigurationManager is a singleton for global access

**Subscriber Pattern**: Services subscribe to configuration changes

**TTL-Based Caching**: Automatic expiration of cached values

**File Watching**: Efficient file monitoring using watchfiles

**Validation First**: Validate before applying any changes

**Rollback Support**: Maintain history for rollback capability

**Async/Await**: Full async support for non-blocking operations

---

## 🆘 Common Questions

**Q: How often is cache cleaned?**
A: Every 5 minutes, expired entries are removed

**Q: What happens if validation fails?**
A: Reload is rejected, previous config remains active

**Q: Can I reload API keys?**
A: No, API keys require application restart for security

**Q: How many changes are kept in history?**
A: Last 100 changes (configurable)

**Q: What's the cache TTL?**
A: Default 1 hour (3600 seconds), configurable per key

---

## 📞 Support

For questions or issues:
1. Check CONFIG_SYSTEM_DESIGN.md for architecture
2. Check CONFIG_IMPLEMENTATION_GUIDE.md for implementation
3. Check CONFIG_API_SPECIFICATION.md for API details
4. Check CONFIG_SYSTEM_SUMMARY.md for overview

---

**Last Updated**: 2025-10-27  
**Version**: 1.0  
**Status**: Ready for Implementation

