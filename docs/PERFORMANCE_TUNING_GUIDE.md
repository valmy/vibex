# Performance Tuning Guide

## Overview

This guide covers performance optimization techniques for the LLM Decision Engine to ensure optimal response times, resource utilization, and system scalability.

## Key Performance Metrics

### Target Performance Goals
- Decision generation: < 5 seconds
- API response time: < 2 seconds
- Cache hit rate: > 30%
- System uptime: > 99.5%
- Memory usage: < 2GB per instance
- CPU utilization: < 80% average

### Monitoring Commands
```bash
# Check system performance
curl http://localhost:3000/api/v1/monitoring/performance

# Monitor cache performance
curl http://localhost:3000/api/v1/decisions/cache/stats

# Check system health
curl http://localhost:3000/api/v1/monitoring/health/system
```

## Decision Engine Optimization

### 1. Caching Strategy

**Enable Decision Caching:**
```python
# Use cached decisions when appropriate
decision = client.generate_decision(
    "BTCUSDT",
    account_id=1,
    force_refresh=False  # Use cache if available
)
```

**Cache Configuration:**
```python
# Optimal cache settings
CACHE_SETTINGS = {
    "decision_cache_ttl": 300,      # 5 minutes for decisions
    "context_cache_ttl": 180,       # 3 minutes for context
    "market_data_cache_ttl": 60,    # 1 minute for market data
    "max_cache_entries": 1000       # Limit memory usage
}
```

### 2. Batch Processing

**Use Batch Endpoints:**
```python
# Instead of multiple single requests
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
batch_results = client.batch_decisions(symbols, account_id=1)

# Process results efficiently
for result in batch_results:
    if result["success"]:
        process_decision(result["decision"])
```

### 3. Async Processing

**Implement Async Patterns:**
```python
import asyncio
import aiohttp

async def generate_decisions_async(symbols, account_id):
    async with aiohttp.ClientSession() as session:
        tasks = []

        for symbol in symbols:
            task = generate_single_decision(session, symbol, account_id)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

## LLM Service Optimization

### 1. Model Selection

**Choose Optimal Models:**
```python
# Performance vs Cost trade-offs
MODEL_PERFORMANCE = {
    "x-ai/grok-4": {
        "avg_response_time": 2200,  # ms
        "cost_per_request": 0.015,  # USD
        "quality_score": 9.2
    },
    "openai/gpt-4o": {
        "avg_response_time": 1800,  # ms
        "cost_per_request": 0.025,  # USD
        "quality_score": 9.5
    }
}
```

### 2. Prompt Optimization

**Efficient Prompt Templates:**
```python
# ✅ Optimized prompt (concise but effective)
optimized_prompt = """
Analyze {symbol} for trading on {timeframe}.
Market: {market_condition} | Balance: {account_balance} USD

Quick analysis:
1. RSI momentum check
2. Support/resistance levels
3. Volume confirmation
4. Risk/reward (min 2:1)

Provide: action, entry, stop_loss, take_profit, confidence.
"""

# ❌ Avoid overly complex prompts
complex_prompt = """
[Very long detailed prompt with excessive instructions...]
"""
```

### 3. Connection Pooling

**Optimize HTTP Connections:**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class OptimizedLLMClient:
    def __init__(self):
        self.session = requests.Session()

        # Configure connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 503, 504]
            )
        )

        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
```

## Database Optimization

### 1. Query Optimization

**Add Strategic Indexes:**
```sql
-- Decision history queries
CREATE INDEX CONCURRENTLY idx_decisions_account_timestamp
ON decisions(account_id, timestamp DESC);

-- Symbol-based queries
CREATE INDEX CONCURRENTLY idx_decisions_symbol_timestamp
ON decisions(symbol, timestamp DESC);

-- Strategy performance queries
CREATE INDEX CONCURRENTLY idx_decisions_strategy_timestamp
ON decisions(strategy_id, timestamp DESC);
```

### 2. Connection Management

**Optimize Database Connections:**
```python
# Database connection pool settings
DATABASE_CONFIG = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True
}
```

### 3. Data Retention

**Implement Data Cleanup:**
```sql
-- Clean old decision data (keep 90 days)
DELETE FROM decisions
WHERE timestamp < NOW() - INTERVAL '90 days';

-- Archive old performance data
INSERT INTO performance_archive
SELECT * FROM performance_metrics
WHERE timestamp < NOW() - INTERVAL '30 days';

DELETE FROM performance_metrics
WHERE timestamp < NOW() - INTERVAL '30 days';
```

## Memory Management

### 1. Cache Size Limits

**Configure Memory Limits:**
```python
MEMORY_LIMITS = {
    "max_decision_cache_mb": 100,
    "max_context_cache_mb": 50,
    "max_market_data_cache_mb": 30,
    "cleanup_threshold_mb": 200
}

def cleanup_memory_if_needed():
    current_usage = get_memory_usage()

    if current_usage > MEMORY_LIMITS["cleanup_threshold_mb"]:
        clear_old_cache_entries()
        force_garbage_collection()
```

### 2. Garbage Collection

**Optimize Python GC:**
```python
import gc

# Tune garbage collection
gc.set_threshold(700, 10, 10)

# Periodic cleanup
def periodic_cleanup():
    gc.collect()
    clear_expired_caches()

# Schedule cleanup every 30 minutes
schedule.every(30).minutes.do(periodic_cleanup)
```

## Network Optimization

### 1. Request Compression

**Enable Compression:**
```python
# Enable gzip compression
headers = {
    "Accept-Encoding": "gzip, deflate",
    "Content-Encoding": "gzip"
}

# Compress large payloads
import gzip
import json

def compress_request_data(data):
    json_data = json.dumps(data).encode('utf-8')
    return gzip.compress(json_data)
```

### 2. Connection Reuse

**Implement Keep-Alive:**
```python
# Configure keep-alive connections
session = requests.Session()
session.headers.update({
    "Connection": "keep-alive",
    "Keep-Alive": "timeout=30, max=100"
})
```

## Monitoring and Alerting

### 1. Performance Monitoring

**Set Up Automated Monitoring:**
```python
def monitor_performance():
    metrics = get_performance_metrics()

    alerts = []

    # Check response times
    if metrics["avg_response_time_ms"] > 5000:
        alerts.append("High response time detected")

    # Check error rates
    if metrics["error_rate"] > 5.0:
        alerts.append("High error rate detected")

    # Check cache performance
    if metrics["cache_hit_rate"] < 20.0:
        alerts.append("Low cache hit rate")

    # Check memory usage
    if metrics["memory_usage_mb"] > 1500:
        alerts.append("High memory usage")

    return alerts
```

### 2. Automated Scaling

**Implement Auto-scaling Logic:**
```python
def auto_scale_decision():
    current_load = get_current_load()

    if current_load > 80:
        # Scale up
        return "scale_up"
    elif current_load < 20:
        # Scale down
        return "scale_down"
    else:
        # Maintain current scale
        return "maintain"
```

## Best Practices Summary

### 1. Development Practices
- Use async/await for I/O operations
- Implement proper caching strategies
- Optimize database queries
- Monitor performance continuously

### 2. Deployment Practices
- Use connection pooling
- Enable compression
- Configure appropriate timeouts
- Implement circuit breakers

### 3. Maintenance Practices
- Regular cache cleanup
- Database maintenance
- Performance monitoring
- Capacity planning

### 4. Troubleshooting
- Monitor key metrics
- Set up alerting
- Implement graceful degradation
- Plan for failure scenarios