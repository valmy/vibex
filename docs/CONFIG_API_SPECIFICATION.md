# Configuration Management API Specification

**Document Version**: 1.0  
**Date**: 2025-10-27  
**Status**: API Specification (Future Implementation)

---

## 1. Overview

This document specifies the REST API endpoints for configuration management. These endpoints will be implemented in Phase 3 of the Configuration System implementation.

---

## 2. Authentication

All endpoints require admin authentication (to be implemented):
- Header: `Authorization: Bearer <admin_token>`
- Role: `admin`

---

## 3. Endpoints

### 3.1 Get Current Configuration

**Endpoint**: `GET /api/v1/admin/config`

**Description**: Retrieve current configuration (sensitive values masked)

**Response**:
```json
{
  "status": "success",
  "data": {
    "environment": "development",
    "debug": true,
    "app_name": "AI Trading Agent",
    "app_version": "1.0.0",
    "api_host": "0.0.0.0",
    "api_port": 3000,
    "database_url": "postgresql://***:***@localhost:5432/trading_db",
    "log_level": "DEBUG",
    "log_format": "json",
    "asterdex_api_key": "***",
    "asterdex_api_secret": "***",
    "asterdex_base_url": "https://fapi.asterdex.com",
    "asterdex_network": "mainnet",
    "openrouter_api_key": "***",
    "openrouter_base_url": "https://openrouter.ai/api/v1",
    "llm_model": "deepseek/deepseek-chat-v3-0324:free",
    "assets": "BTC,ETH,SOL,ASTER",
    "interval": "1h",
    "long_interval": "4h",
    "leverage": 2.0,
    "max_position_size_usd": 10000.0,
    "multi_account_mode": false
  }
}
```

**Status Codes**:
- 200: Success
- 401: Unauthorized
- 403: Forbidden

---

### 3.2 Get Configuration Status

**Endpoint**: `GET /api/v1/admin/config/status`

**Description**: Get configuration validation status and cache statistics

**Response**:
```json
{
  "status": "success",
  "data": {
    "is_valid": true,
    "last_validated": "2025-10-27T15:30:00Z",
    "validation_errors": [],
    "cache_stats": {
      "total_hits": 1250,
      "total_misses": 50,
      "hit_rate": 0.962,
      "entries_count": 12,
      "memory_usage_bytes": 4096
    },
    "is_watching": true,
    "last_reload": "2025-10-27T14:00:00Z",
    "reload_count": 3,
    "last_change": {
      "timestamp": "2025-10-27T14:00:00Z",
      "field": "LLM_MODEL",
      "old_value": "x-ai/grok-4",
      "new_value": "deepseek/deepseek-chat-v3-0324:free",
      "status": "success"
    }
  }
}
```

**Status Codes**:
- 200: Success
- 401: Unauthorized
- 403: Forbidden

---

### 3.3 Reload Configuration

**Endpoint**: `POST /api/v1/admin/config/reload`

**Description**: Trigger configuration reload from .env file

**Request Body**:
```json
{
  "validate": true,
  "notify_services": true
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "reloaded": true,
    "changes": {
      "LLM_MODEL": {
        "old_value": "x-ai/grok-4",
        "new_value": "deepseek/deepseek-chat-v3-0324:free"
      },
      "ASSETS": {
        "old_value": "BTC,ETH,SOL",
        "new_value": "BTC,ETH,SOL,ASTER"
      }
    },
    "validation_errors": [],
    "services_notified": 5,
    "reload_duration_ms": 245
  }
}
```

**Status Codes**:
- 200: Success
- 400: Validation failed
- 401: Unauthorized
- 403: Forbidden
- 500: Reload failed

---

### 3.4 Get Configuration Change History

**Endpoint**: `GET /api/v1/admin/config/history`

**Description**: Get configuration change history

**Query Parameters**:
- `limit`: Number of records (default: 50, max: 500)
- `offset`: Pagination offset (default: 0)
- `field`: Filter by field name (optional)
- `status`: Filter by status (success/failed/rolled_back)

**Response**:
```json
{
  "status": "success",
  "data": {
    "total": 15,
    "limit": 50,
    "offset": 0,
    "changes": [
      {
        "timestamp": "2025-10-27T14:00:00Z",
        "field": "LLM_MODEL",
        "old_value": "x-ai/grok-4",
        "new_value": "deepseek/deepseek-chat-v3-0324:free",
        "status": "success",
        "duration_ms": 245,
        "user": "admin@example.com"
      }
    ]
  }
}
```

**Status Codes**:
- 200: Success
- 401: Unauthorized
- 403: Forbidden

---

### 3.5 Get Cache Statistics

**Endpoint**: `GET /api/v1/admin/config/cache/stats`

**Description**: Get detailed cache statistics

**Response**:
```json
{
  "status": "success",
  "data": {
    "total_hits": 1250,
    "total_misses": 50,
    "hit_rate": 0.962,
    "entries_count": 12,
    "memory_usage_bytes": 4096,
    "entries": [
      {
        "key": "ASSETS",
        "hits": 450,
        "misses": 5,
        "created_at": "2025-10-27T10:00:00Z",
        "expires_at": "2025-10-27T11:00:00Z",
        "ttl_seconds": 3600
      }
    ]
  }
}
```

**Status Codes**:
- 200: Success
- 401: Unauthorized
- 403: Forbidden

---

### 3.6 Clear Configuration Cache

**Endpoint**: `POST /api/v1/admin/config/cache/clear`

**Description**: Clear configuration cache

**Request Body**:
```json
{
  "keys": ["ASSETS", "INTERVAL"]  // Optional: specific keys to clear
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "cleared": true,
    "keys_cleared": 2,
    "entries_remaining": 10
  }
}
```

**Status Codes**:
- 200: Success
- 401: Unauthorized
- 403: Forbidden

---

### 3.7 Validate Configuration

**Endpoint**: `POST /api/v1/admin/config/validate`

**Description**: Validate configuration without reloading

**Request Body**:
```json
{
  "config": {
    "leverage": 2.5,
    "max_position_size_usd": 15000.0,
    "assets": "BTC,ETH,SOL,ASTER"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "is_valid": true,
    "errors": [],
    "warnings": [],
    "validation_duration_ms": 125
  }
}
```

**Status Codes**:
- 200: Success
- 400: Validation failed
- 401: Unauthorized
- 403: Forbidden

---

### 3.8 Rollback Configuration

**Endpoint**: `POST /api/v1/admin/config/rollback`

**Description**: Rollback to previous configuration

**Request Body**:
```json
{
  "steps": 1  // Number of steps to rollback (default: 1)
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "rolled_back": true,
    "previous_config": {
      "llm_model": "x-ai/grok-4",
      "assets": "BTC,ETH,SOL"
    },
    "changes_reverted": 2
  }
}
```

**Status Codes**:
- 200: Success
- 400: Rollback failed
- 401: Unauthorized
- 403: Forbidden

---

## 4. Error Responses

### 4.1 Validation Error

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Configuration validation failed",
    "details": [
      "LEVERAGE must be between 1.0 and 5.0",
      "MAX_POSITION_SIZE_USD must be between 100 and 100000"
    ]
  }
}
```

### 4.2 Reload Error

```json
{
  "status": "error",
  "error": {
    "code": "RELOAD_ERROR",
    "message": "Configuration reload failed",
    "reason": "File not found: .env"
  }
}
```

### 4.3 Authorization Error

```json
{
  "status": "error",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required"
  }
}
```

---

## 5. WebSocket Events (Future)

### 5.1 Configuration Change Event

**Endpoint**: `WS /api/v1/admin/config/events`

**Event**: `config.changed`

```json
{
  "event": "config.changed",
  "timestamp": "2025-10-27T14:00:00Z",
  "changes": {
    "LLM_MODEL": {
      "old_value": "x-ai/grok-4",
      "new_value": "deepseek/deepseek-chat-v3-0324:free"
    }
  }
}
```

### 5.2 Validation Event

**Event**: `config.validation_failed`

```json
{
  "event": "config.validation_failed",
  "timestamp": "2025-10-27T14:00:00Z",
  "errors": [
    "LEVERAGE must be between 1.0 and 5.0"
  ]
}
```

---

## 6. Rate Limiting

- Configuration reload: 10 requests per minute
- Cache clear: 20 requests per minute
- Validation: 50 requests per minute
- History: 100 requests per minute

---

## 7. Audit Logging

All configuration changes are logged with:
- Timestamp
- User (admin email)
- Action (reload, validate, rollback)
- Changes made
- Status (success/failed)
- Duration

---

## 8. Response Headers

All responses include:
- `X-Request-ID`: Unique request identifier
- `X-Response-Time`: Response time in milliseconds
- `X-Config-Version`: Current configuration version

---

## 9. Pagination

List endpoints support pagination:
- `limit`: Items per page (default: 50, max: 500)
- `offset`: Pagination offset (default: 0)

Response includes:
- `total`: Total number of items
- `limit`: Items per page
- `offset`: Current offset
- `data`: Array of items

---

## 10. Filtering

History endpoint supports filtering:
- `field`: Filter by field name
- `status`: Filter by status (success/failed/rolled_back)
- `start_date`: Filter by start date (ISO 8601)
- `end_date`: Filter by end date (ISO 8601)

---

**Status**: Ready for Implementation  
**Next Step**: Implement endpoints in Phase 3

