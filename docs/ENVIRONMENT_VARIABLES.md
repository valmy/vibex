# Environment Variables Reference

## Overview

This document provides a comprehensive reference for all environment variables used in the LLM Decision Engine system.

## Required Variables

### API Keys and Authentication

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM access | `sk-or-v1-...` | ✅ |
| `ASTERDEX_API_KEY` | AsterDEX API key for trading | `your_api_key` | ✅ |
| `ASTERDEX_API_SECRET` | AsterDEX API secret for trading | `your_api_secret` | ✅ |
| `SECRET_KEY` | JWT signing secret key | `random_32_char_string` | ✅ |

### Database Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://user:pass@host:5432/db` | ✅ |
| `DATABASE_POOL_SIZE` | Connection pool size | `20` | ❌ |
| `DATABASE_MAX_OVERFLOW` | Max overflow connections | `10` | ❌ |
| `DATABASE_ECHO` | Echo SQL queries | `false` | ❌ |

## Application Settings

### Server Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ENVIRONMENT` | Environment mode | `development` | ❌ |
| `DEBUG` | Enable debug mode | `false` | ❌ |
| `API_HOST` | Server host address | `0.0.0.0` | ❌ |
| `API_PORT` | Server port | `3000` | ❌ |
| `CORS_ORIGINS` | Allowed CORS origins | `*` | ❌ |

### Logging Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LOG_LEVEL` | Logging level | `INFO` | ❌ |
| `LOG_FORMAT` | Log format (json/text) | `json` | ❌ |
| `LOG_DIR` | Log directory path | `logs` | ❌ |

## LLM Decision Engine Settings

### Core Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LLM_MODEL` | Default LLM model | `x-ai/grok-4` | ❌ |
| `LLM_CACHE_ENABLED` | Enable LLM response caching | `true` | ❌ |
| `LLM_CACHE_TTL` | LLM cache TTL (seconds) | `300` | ❌ |
| `DECISION_CACHE_TTL` | Decision cache TTL (seconds) | `300` | ❌ |
| `CONTEXT_CACHE_TTL` | Context cache TTL (seconds) | `180` | ❌ |

### Circuit Breaker Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CIRCUIT_BREAKER_ENABLED` | Enable circuit breaker | `true` | ❌ |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Failure threshold | `5` | ❌ |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | Recovery timeout (seconds) | `60` | ❌ |
| `CIRCUIT_BREAKER_EXPECTED_EXCEPTION` | Expected exception types | `LLMServiceError` | ❌ |

### Rate Limiting

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `RATE_LIMIT_ENABLED` | Enable rate limiting | `true` | ❌ |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Requests per minute | `60` | ❌ |
| `RATE_LIMIT_BURST_SIZE` | Burst size | `10` | ❌ |

## Trading Configuration

### Basic Trading Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ASSETS` | Trading assets (comma-separated) | `BTC,ETH,SOL` | ❌ |
| `INTERVAL` | Trading interval | `1h` | ❌ |
| `LONG_INTERVAL` | Long-term interval | `4h` | ❌ |
| `LEVERAGE` | Default leverage | `2.0` | ❌ |
| `MAX_POSITION_SIZE_USD` | Max position size | `10000.0` | ❌ |

### Risk Management

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEFAULT_RISK_PER_TRADE` | Default risk per trade (%) | `2.0` | ❌ |
| `MAX_DAILY_LOSS` | Max daily loss (%) | `5.0` | ❌ |
| `DEFAULT_STOP_LOSS` | Default stop loss (%) | `3.0` | ❌ |
| `DEFAULT_TAKE_PROFIT_RATIO` | Default TP ratio | `2.0` | ❌ |

## Multi-Account Configuration

### Multi-Account Mode

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MULTI_ACCOUNT_MODE` | Enable multi-account mode | `false` | ❌ |
| `ACCOUNT_IDS` | Account IDs (comma-separated) | - | ❌ |

### Per-Account Settings

For each account ID in `ACCOUNT_IDS`, you can set:

| Variable Pattern | Description | Example |
|------------------|-------------|---------|
| `ASTERDEX_API_KEY_{account_id}` | Account-specific AsterDEX key | `ASTERDEX_API_KEY_account1` |
| `ASTERDEX_API_SECRET_{account_id}` | Account-specific AsterDEX secret | `ASTERDEX_API_SECRET_account1` |
| `OPENROUTER_API_KEY_{account_id}` | Account-specific OpenRouter key | `OPENROUTER_API_KEY_account1` |
| `LLM_MODEL_{account_id}` | Account-specific LLM model | `LLM_MODEL_account1` |
| `LEVERAGE_{account_id}` | Account-specific leverage | `LEVERAGE_account1` |
| `MAX_POSITION_SIZE_USD_{account_id}` | Account-specific position size | `MAX_POSITION_SIZE_USD_account1` |

## Performance Settings

### Application Performance

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `UVICORN_WORKERS` | Number of worker processes | `1` | ❌ |
| `UVICORN_WORKER_CONNECTIONS` | Worker connections | `1000` | ❌ |
| `UVICORN_BACKLOG` | Connection backlog | `2048` | ❌ |
| `UVICORN_KEEPALIVE` | Keep-alive timeout | `5` | ❌ |

### Cache Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` | ❌ |
| `CACHE_DEFAULT_TTL` | Default cache TTL | `300` | ❌ |
| `CACHE_MAX_ENTRIES` | Max cache entries | `10000` | ❌ |
| `CACHE_CLEANUP_INTERVAL` | Cleanup interval (seconds) | `3600` | ❌ |

### Memory Management

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MAX_MEMORY_MB` | Max memory usage (MB) | `2048` | ❌ |
| `GC_THRESHOLD_0` | GC threshold 0 | `700` | ❌ |
| `GC_THRESHOLD_1` | GC threshold 1 | `10` | ❌ |
| `GC_THRESHOLD_2` | GC threshold 2 | `10` | ❌ |

## External Service Configuration

### OpenRouter Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENROUTER_BASE_URL` | OpenRouter API base URL | `https://openrouter.ai/api/v1` | ❌ |
| `OPENROUTER_REFERER` | HTTP referer header | `trading-agent` | ❌ |
| `OPENROUTER_APP_TITLE` | Application title | `AI Trading Agent` | ❌ |
| `OPENROUTER_TIMEOUT` | Request timeout (seconds) | `30` | ❌ |
| `OPENROUTER_MAX_RETRIES` | Max retry attempts | `3` | ❌ |

### AsterDEX Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ASTERDEX_BASE_URL` | AsterDEX API base URL | `https://fapi.asterdex.com` | ❌ |
| `ASTERDEX_NETWORK` | Network (mainnet/testnet) | `mainnet` | ❌ |
| `ASTERDEX_TIMEOUT` | Request timeout (seconds) | `10` | ❌ |
| `ASTERDEX_MAX_RETRIES` | Max retry attempts | `3` | ❌ |

## Monitoring and Alerting

### Monitoring Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MONITORING_ENABLED` | Enable monitoring | `true` | ❌ |
| `METRICS_ENABLED` | Enable metrics collection | `true` | ❌ |
| `HEALTH_CHECK_INTERVAL` | Health check interval (seconds) | `30` | ❌ |
| `PERFORMANCE_MONITORING_INTERVAL` | Performance check interval | `300` | ❌ |

### Alerting Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ALERTS_ENABLED` | Enable alerting | `true` | ❌ |
| `ALERT_EMAIL_ENABLED` | Enable email alerts | `false` | ❌ |
| `ALERT_SLACK_ENABLED` | Enable Slack alerts | `false` | ❌ |
| `ALERT_WEBHOOK_URL` | Webhook URL for alerts | - | ❌ |
| `SMTP_HOST` | SMTP server host | - | ❌ |
| `SMTP_PORT` | SMTP server port | `587` | ❌ |
| `SMTP_USERNAME` | SMTP username | - | ❌ |
| `SMTP_PASSWORD` | SMTP password | - | ❌ |
| `ALERT_EMAIL_FROM` | Alert sender email | - | ❌ |
| `ALERT_EMAIL_TO` | Alert recipient email | - | ❌ |

## Security Settings

### Authentication & Authorization

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ALGORITHM` | JWT algorithm | `HS256` | ❌ |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration | `30` | ❌ |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiration | `7` | ❌ |
| `PASSWORD_MIN_LENGTH` | Minimum password length | `8` | ❌ |

### Security Headers

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SECURITY_HEADERS_ENABLED` | Enable security headers | `true` | ❌ |
| `HSTS_MAX_AGE` | HSTS max age | `31536000` | ❌ |
| `CSP_POLICY` | Content Security Policy | `default-src 'self'` | ❌ |

## Development Settings

### Development Mode

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEV_MODE` | Enable development mode | `false` | ❌ |
| `AUTO_RELOAD` | Enable auto-reload | `false` | ❌ |
| `MOCK_EXTERNAL_APIS` | Mock external APIs | `false` | ❌ |
| `SEED_DATA_ENABLED` | Load seed data | `false` | ❌ |

### Testing Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TEST_DATABASE_URL` | Test database URL | - | ❌ |
| `TEST_MODE` | Enable test mode | `false` | ❌ |
| `PYTEST_TIMEOUT` | Test timeout (seconds) | `300` | ❌ |

## Environment-Specific Examples

### Development Environment

```bash
# .env.development
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
LLM_CACHE_ENABLED=true
MOCK_EXTERNAL_APIS=false
AUTO_RELOAD=true
```

### Testing Environment

```bash
# .env.testing
ENVIRONMENT=testing
DEBUG=false
LOG_LEVEL=WARNING
TEST_MODE=true
DATABASE_URL=postgresql://test_user:test_pass@localhost:5432/test_db
MOCK_EXTERNAL_APIS=true
```

### Production Environment

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
SECURITY_HEADERS_ENABLED=true
MONITORING_ENABLED=true
ALERTS_ENABLED=true
UVICORN_WORKERS=4
```

## Validation Rules

### Required Combinations

Some variables must be set together:

```bash
# Multi-account mode requires account IDs
MULTI_ACCOUNT_MODE=true
ACCOUNT_IDS=account1,account2

# Email alerts require SMTP configuration
ALERT_EMAIL_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=password
ALERT_EMAIL_FROM=alerts@example.com
ALERT_EMAIL_TO=admin@example.com
```

### Format Requirements

| Variable | Format | Example |
|----------|--------|---------|
| `DATABASE_URL` | PostgreSQL URL | `postgresql://user:pass@host:port/db` |
| `REDIS_URL` | Redis URL | `redis://host:port/db` |
| `CORS_ORIGINS` | Comma-separated URLs | `https://app.com,https://admin.com` |
| `ASSETS` | Comma-separated symbols | `BTC,ETH,SOL,ADA` |
| `ACCOUNT_IDS` | Comma-separated IDs | `account1,account2,account3` |

### Value Constraints

| Variable | Constraint | Valid Range |
|----------|------------|-------------|
| `API_PORT` | Integer | 1-65535 |
| `LEVERAGE` | Float | 1.0-10.0 |
| `MAX_POSITION_SIZE_USD` | Float | > 0 |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Integer | 1-1000 |
| `UVICORN_WORKERS` | Integer | 1-16 |
| `DATABASE_POOL_SIZE` | Integer | 1-100 |

## Configuration Validation

The system validates configuration on startup:

```python
# Example validation errors
ConfigurationError: OPENROUTER_API_KEY is required
ConfigurationError: DATABASE_URL format is invalid
ConfigurationError: LEVERAGE must be between 1.0 and 10.0
ConfigurationError: Multi-account mode requires ACCOUNT_IDS
```

## Best Practices

### Security
- Never commit `.env` files to version control
- Use strong, unique values for `SECRET_KEY`
- Rotate API keys regularly
- Use environment-specific configurations

### Performance
- Set appropriate cache TTL values
- Configure database pool sizes based on load
- Use Redis for caching in production
- Monitor memory usage and adjust limits

### Monitoring
- Enable comprehensive monitoring in production
- Set up alerting for critical metrics
- Use structured logging with JSON format
- Configure appropriate log levels

### Development
- Use `.env.example` as a template
- Document any new environment variables
- Test with different configurations
- Validate configuration changes