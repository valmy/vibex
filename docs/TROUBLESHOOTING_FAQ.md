# LLM Decision Engine - Troubleshooting & FAQ

## Table of Contents

1. [Common Issues](#common-issues)
2. [Error Codes Reference](#error-codes-reference)
3. [Performance Issues](#performance-issues)
4. [Configuration Problems](#configuration-problems)
5. [API Integration Issues](#api-integration-issues)
6. [Strategy Management Issues](#strategy-management-issues)
7. [Monitoring and Debugging](#monitoring-and-debugging)
8. [Frequently Asked Questions](#frequently-asked-questions)
9. [Best Practices](#best-practices)
10. [Getting Help](#getting-help)

## Common Issues

### 1. Decision Generation Failures

#### Issue: "LLM Service Unavailable" (503 Error)

**Symptoms:**
- API returns 503 status code
- Error message: "LLM service unavailable"
- Decision generation requests fail consistently

**Causes:**
- OpenRouter API is down or experiencing issues
- Network connectivity problems
- API key issues or rate limiting
- Circuit breaker is open due to repeated failures

**Solutions:**

1. **Check OpenRouter API Status**
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        https://openrouter.ai/api/v1/models
   ```

2. **Verify API Key**
   ```bash
   # Check if API key is valid
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        https://openrouter.ai/api/v1/auth/key
   ```

3. **Check System Health**
   ```bash
   curl http://localhost:3000/api/v1/monitoring/health/system
   ```

4. **Reset Circuit Breaker**
   ```python
   # If circuit breaker is open, wait for automatic reset or restart service
   import time
   time.sleep(300)  # Wait 5 minutes for circuit breaker reset
   ```

5. **Check Network Connectivity**
   ```bash
   ping openrouter.ai
   nslookup openrouter.ai
   ```

#### Issue: "Rate Limit Exceeded" (429 Error)

**Symptoms:**
- API returns 429 status code
- Requests are being throttled
- Intermittent failures during high-volume periods

**Solutions:**

1. **Implement Exponential Backoff**
   ```python
   import time
   import random

   def make_request_with_backoff(client, max_retries=5):
       for attempt in range(max_retries):
           try:
               return client.generate_decision("BTCUSDT", 1)
           except RateLimitError:
               if attempt == max_retries - 1:
                   raise
               wait_time = (2 ** attempt) + random.uniform(0, 1)
               time.sleep(wait_time)
   ```

2. **Use Batch Endpoints**
   ```python
   # Instead of multiple single requests
   symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
   results = client.batch_decisions(symbols, account_id=1)
   ```

3. **Check Rate Limits**
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:3000/api/v1/monitoring/performance
   ```

#### Issue: "Decision Validation Failed" (400 Error)

**Symptoms:**
- Decisions are generated but fail validation
- Error messages about invalid parameters
- Inconsistent decision quality

**Solutions:**

1. **Check Decision Parameters**
   ```python
   # Validate decision manually
   decision = {
       "asset": "BTCUSDT",
       "action": "buy",
       "allocation_usd": 1000.0,
       "tp_price": 52000.0,
       "sl_price": 48000.0,
       "rationale": "Strong bullish momentum",
       "confidence": 85.5,
       "risk_level": "medium"
   }

   result = client.validate_decision(decision)
   print(result["errors"])
   ```

2. **Review Strategy Risk Parameters**
   ```python
   strategy = client.get_strategy("aggressive")
   print(strategy["risk_parameters"])

   # Check if parameters are too restrictive
   if strategy["risk_parameters"]["max_risk_per_trade"] < 1.0:
       print("Risk parameters may be too restrictive")
   ```

3. **Check Account Balance and Exposure**
   ```python
   account_info = client.get_account_info(1)
   print(f"Available balance: {account_info['available_balance']}")
   print(f"Current exposure: {account_info['risk_exposure']}%")
   ```

### 2. Strategy Management Issues

#### Issue: Strategy Not Generating Expected Decisions

**Symptoms:**
- Strategy is active but decisions don't match expectations
- Inconsistent decision patterns
- Strategy seems to ignore market conditions

**Solutions:**

1. **Review Prompt Template**
   ```python
   strategy = client.get_strategy("custom_strategy")
   print("Prompt Template:")
   print(strategy["prompt_template"])

   # Check for:
   # - Clear instructions
   # - Proper variable substitution
   # - Logical decision criteria
   ```

2. **Test with Different Market Conditions**
   ```python
   # Test strategy with various scenarios
   test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

   for symbol in test_symbols:
       decision = client.generate_decision(symbol, 1, strategy_override="custom_strategy")
       print(f"{symbol}: {decision['decision']['action']} - {decision['decision']['rationale']}")
   ```

3. **Check Strategy Performance**
   ```python
   performance = client.get_strategy_performance("custom_strategy", "7d")

   if performance["win_rate"] < 40:
       print("Strategy may need optimization")
   ```

#### Issue: Strategy Switching Not Working

**Symptoms:**
- Strategy switch requests succeed but behavior doesn't change
- Old strategy still being used for decisions
- Cache not being invalidated

**Solutions:**

1. **Clear Decision Cache**
   ```bash
   curl -X POST "http://localhost:3000/api/v1/decisions/cache/clear?account_id=1"
   ```

2. **Verify Strategy Assignment**
   ```python
   current_strategy = client.get_account_strategy(1)
   print(f"Current strategy: {current_strategy['strategy_id']}")

   # Check assignment history
   assignments = client.get_strategy_assignments()
   print(f"All assignments: {assignments}")
   ```

3. **Force Refresh on Next Decision**
   ```python
   decision = client.generate_decision(
       "BTCUSDT",
       1,
       force_refresh=True
   )
   ```

### 3. Performance Issues

#### Issue: Slow Decision Generation

**Symptoms:**
- Decision generation takes longer than 5 seconds
- Timeouts on API requests
- Poor user experience

**Solutions:**

1. **Check System Performance**
   ```bash
   curl http://localhost:3000/api/v1/monitoring/performance
   ```

2. **Analyze Response Times**
   ```python
   import time

   start_time = time.time()
   decision = client.generate_decision("BTCUSDT", 1)
   end_time = time.time()

   print(f"Decision generation took: {end_time - start_time:.2f} seconds")
   ```

3. **Optimize Context Building**
   ```python
   # Use cached context when possible
   decision = client.generate_decision(
       "BTCUSDT",
       1,
       force_refresh=False  # Use cached data
   )
   ```

4. **Check Cache Performance**
   ```bash
   curl http://localhost:3000/api/v1/decisions/cache/stats
   ```

#### Issue: High Memory Usage

**Symptoms:**
- System memory usage continuously increasing
- Out of memory errors
- Performance degradation over time

**Solutions:**

1. **Monitor Memory Usage**
   ```bash
   # Check system memory
   free -h

   # Check application memory
   ps aux | grep python
   ```

2. **Clear Old Caches**
   ```bash
   curl -X POST "http://localhost:3000/api/v1/decisions/cache/clear"
   ```

3. **Restart Services if Needed**
   ```bash
   # Restart the application
   cd backend && podman-compose restart backend
   ```

### 4. Configuration Issues

#### Issue: Environment Variables Not Loading

**Symptoms:**
- Configuration errors on startup
- Default values being used instead of environment variables
- API keys not being recognized

**Solutions:**

1. **Check Environment File**
   ```bash
   # Verify .env file exists and has correct format
   cat backend/.env

   # Check for common issues:
   # - Missing quotes around values with spaces
   # - Incorrect variable names
   # - Missing required variables
   ```

2. **Validate Configuration**
   ```python
   from app.core.config import get_settings

   settings = get_settings()
   print(f"OpenRouter API Key: {settings.openrouter_api_key[:10]}...")
   print(f"Database URL: {settings.database_url}")
   ```

3. **Check Configuration Loading**
   ```bash
   # Test configuration loading
   cd backend && uv run python -c "from app.core.config import get_settings; print(get_settings())"
   ```

#### Issue: Database Connection Problems

**Symptoms:**
- Database connection errors
- Migration failures
- Data persistence issues

**Solutions:**

1. **Check Database Status**
   ```bash
   # Check if PostgreSQL is running
   cd backend && podman-compose ps

   # Check database logs
   cd backend && podman-compose logs postgres
   ```

2. **Test Database Connection**
   ```bash
   # Test connection manually
   psql postgresql://trading_user:password@localhost:5432/trading_db
   ```

3. **Run Migrations**
   ```bash
   cd backend && uv run alembic upgrade head
   ```

4. **Reset Database if Needed**
   ```bash
   cd backend && podman-compose down -v
   cd backend && podman-compose up -d
   cd backend && uv run alembic upgrade head
   ```

## Error Codes Reference

### HTTP Status Codes

| Code | Meaning | Common Causes | Solutions |
|------|---------|---------------|-----------|
| 400 | Bad Request | Invalid parameters, validation errors | Check request format and parameters |
| 401 | Unauthorized | Missing or invalid API key | Verify authentication credentials |
| 403 | Forbidden | Insufficient permissions | Check account permissions |
| 404 | Not Found | Resource doesn't exist | Verify resource IDs and endpoints |
| 429 | Too Many Requests | Rate limit exceeded | Implement backoff, reduce request rate |
| 500 | Internal Server Error | Server-side error | Check logs, contact support |
| 503 | Service Unavailable | Service temporarily down | Wait and retry, check service status |

### Application Error Codes

| Code | Description | Typical Causes | Solutions |
|------|-------------|----------------|-----------|
| `VALIDATION_ERROR` | Request validation failed | Invalid input parameters | Check request format |
| `STRATEGY_NOT_FOUND` | Strategy doesn't exist | Wrong strategy ID | Verify strategy exists |
| `ACCOUNT_NOT_FOUND` | Account doesn't exist | Wrong account ID | Check account configuration |
| `INSUFFICIENT_DATA` | Not enough market data | Data service issues | Check market data services |
| `LLM_SERVICE_ERROR` | LLM service problem | OpenRouter API issues | Check LLM service status |
| `DECISION_VALIDATION_FAILED` | Decision validation error | Business rule violations | Review decision parameters |
| `RATE_LIMIT_EXCEEDED` | Too many requests | High request volume | Implement rate limiting |
| `CIRCUIT_BREAKER_OPEN` | Circuit breaker activated | Repeated service failures | Wait for reset or fix underlying issue |

## Performance Issues

### Identifying Performance Bottlenecks

#### 1. Decision Generation Latency

**Monitoring:**
```bash
# Check average response times
curl http://localhost:3000/api/v1/monitoring/performance | jq '.decision_engine.avg_response_time_ms'

# Monitor real-time performance
watch -n 5 'curl -s http://localhost:3000/api/v1/monitoring/performance | jq ".decision_engine.avg_response_time_ms"'
```

**Optimization:**
```python
# Use batch processing for multiple symbols
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT"]
batch_results = client.batch_decisions(symbols, account_id=1)

# Enable caching for repeated requests
decision = client.generate_decision("BTCUSDT", 1, force_refresh=False)
```

#### 2. Memory Usage Optimization

**Monitoring:**
```bash
# Check memory usage
curl http://localhost:3000/api/v1/decisions/cache/stats

# Monitor system memory
free -h && ps aux | grep python | head -5
```

**Optimization:**
```python
# Regular cache cleanup
def cleanup_old_data():
    # Clear old cache entries
    client.clear_cache()

    # Clear old alerts
    client.cleanup_old_alerts(max_age_hours=24)

# Schedule regular cleanup
import schedule
schedule.every(6).hours.do(cleanup_old_data)
```

#### 3. Database Performance

**Monitoring:**
```sql
-- Check slow queries
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Check database connections
SELECT count(*) as active_connections
FROM pg_stat_activity
WHERE state = 'active';
```

**Optimization:**
```sql
-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_decisions_account_timestamp
ON decisions(account_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_decisions_symbol_timestamp
ON decisions(symbol, timestamp DESC);
```

## Configuration Problems

### Environment Configuration Issues

#### Missing Required Variables

**Check Required Variables:**
```bash
# List of required environment variables
required_vars=(
    "OPENROUTER_API_KEY"
    "DATABASE_URL"
    "ASTERDX_API_KEY"
    "ASTERDX_API_SECRET"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Missing required variable: $var"
    else
        echo "$var is set"
    fi
done
```

**Template .env File:**
```bash
# Copy template and fill in values
cp backend/.env.example backend/.env

# Edit with your values
nano backend/.env
```

#### Configuration Validation

**Validate on Startup:**
```python
from app.core.config import get_settings
from app.core.config_validator import ConfigValidator

def validate_configuration():
    settings = get_settings()
    validator = ConfigValidator()

    errors = validator.validate_all(settings)
    if errors:
        print("Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("Configuration is valid")
    return True

# Run validation
if not validate_configuration():
    exit(1)
```

### Multi-Account Configuration

**Setup Multiple Accounts:**
```bash
# Enable multi-account mode
export MULTI_ACCOUNT_MODE=true
export ACCOUNT_IDS=account1,account2,account3

# Per-account API keys
export ASTERDX_API_KEY_account1=key1
export ASTERDX_API_SECRET_account1=secret1
export OPENROUTER_API_KEY_account1=router_key1

export ASTERDX_API_KEY_account2=key2
export ASTERDX_API_SECRET_account2=secret2
export OPENROUTER_API_KEY_account2=router_key2
```

**Validate Multi-Account Setup:**
```python
def validate_multi_account_config():
    settings = get_settings()

    if not settings.multi_account_mode:
        print("Multi-account mode is disabled")
        return True

    account_ids = settings.account_ids
    for account_id in account_ids:
        # Check if account-specific keys exist
        api_key = getattr(settings, f'asterdx_api_key_{account_id}', None)
        if not api_key:
            print(f"Missing API key for account: {account_id}")
            return False

    print(f"Multi-account configuration valid for {len(account_ids)} accounts")
    return True
```

## API Integration Issues

### Authentication Problems

#### Invalid API Key

**Symptoms:**
- 401 Unauthorized errors
- "Invalid API key" messages
- Authentication failures

**Solutions:**
```python
# Test API key validity
def test_api_key(api_key):
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers=headers
        )

        if response.status_code == 200:
            print("API key is valid")
            return True
        else:
            print(f"API key validation failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error testing API key: {e}")
        return False

# Test your key
test_api_key("your_api_key_here")
```

#### Request Format Issues

**Common Problems:**
```python
# ❌ Incorrect - missing required fields
bad_request = {
    "symbol": "BTCUSDT"
    # Missing account_id
}

# ✅ Correct - all required fields
good_request = {
    "symbol": "BTCUSDT",
    "account_id": 1,
    "force_refresh": False
}

# ❌ Incorrect - wrong data types
bad_request = {
    "symbol": "BTCUSDT",
    "account_id": "1",  # Should be integer
    "force_refresh": "false"  # Should be boolean
}

# ✅ Correct - proper data types
good_request = {
    "symbol": "BTCUSDT",
    "account_id": 1,
    "force_refresh": False
}
```

### Response Handling

#### Parsing JSON Responses

```python
import json

def handle_api_response(response):
    try:
        # Check status code first
        if response.status_code == 200:
            data = response.json()
            return data
        elif response.status_code == 429:
            print("Rate limit exceeded, implement backoff")
            return None
        elif response.status_code == 503:
            print("Service unavailable, try again later")
            return None
        else:
            print(f"API error: {response.status_code} - {response.text}")
            return None

    except json.JSONDecodeError:
        print("Invalid JSON response")
        return None
    except Exception as e:
        print(f"Error handling response: {e}")
        return None
```

#### Error Response Handling

```python
def handle_error_response(response):
    try:
        error_data = response.json()

        if "error" in error_data:
            error_info = error_data["error"]
            print(f"Error Code: {error_info.get('code', 'UNKNOWN')}")
            print(f"Message: {error_info.get('message', 'No message')}")

            if "details" in error_info:
                print("Details:")
                for key, value in error_info["details"].items():
                    print(f"  {key}: {value}")

        return error_data

    except Exception as e:
        print(f"Error parsing error response: {e}")
        return None
```

## Strategy Management Issues

### Strategy Creation Problems

#### Invalid Strategy Configuration

**Common Issues:**
```python
# ❌ Invalid risk parameters
invalid_strategy = {
    "strategy_name": "Test Strategy",
    "risk_parameters": {
        "max_risk_per_trade": 150.0,  # Too high (>100%)
        "stop_loss_percentage": -5.0,  # Negative value
        "take_profit_ratio": 0.5       # Less than 1.0
    }
}

# ✅ Valid risk parameters
valid_strategy = {
    "strategy_name": "Test Strategy",
    "risk_parameters": {
        "max_risk_per_trade": 3.0,     # Reasonable percentage
        "stop_loss_percentage": 2.5,   # Positive value
        "take_profit_ratio": 2.0       # Greater than 1.0
    }
}
```

#### Prompt Template Issues

**Common Problems:**
```python
# ❌ Poor prompt template
bad_prompt = "Trade {symbol}"  # Too vague

# ❌ Missing variable substitution
bad_prompt = "Analyze BTCUSDT for trading"  # Hardcoded symbol

# ✅ Good prompt template
good_prompt = """
Analyze {symbol} on {timeframe} timeframe for trading opportunities.

Market Context:
- Current condition: {market_condition}
- Account balance: {account_balance} USD
- Risk exposure: {risk_exposure}%

Analysis Requirements:
1. Check RSI for momentum (target: 30-70 range)
2. Identify support/resistance levels
3. Confirm with volume analysis
4. Assess risk/reward ratio (minimum 2:1)

Provide specific entry, stop loss, and take profit levels with clear rationale.
"""
```

### Strategy Performance Issues

#### Poor Win Rate

**Diagnosis:**
```python
def diagnose_strategy_performance(client, strategy_id):
    performance = client.get_strategy_performance(strategy_id, "30d")

    issues = []

    if performance["win_rate"] < 40:
        issues.append("Low win rate - strategy may be too aggressive")

    if performance["profit_factor"] < 1.2:
        issues.append("Poor profit factor - losses too large relative to wins")

    if performance["max_drawdown"] > 1000:
        issues.append("High drawdown - risk management may be inadequate")

    if performance["avg_win"] / abs(performance["avg_loss"]) < 1.5:
        issues.append("Poor risk/reward ratio")

    return issues

# Check strategy issues
issues = diagnose_strategy_performance(client, "aggressive")
for issue in issues:
    print(f"⚠️  {issue}")
```

**Solutions:**
```python
def optimize_strategy_parameters(client, strategy_id):
    strategy = client.get_strategy(strategy_id)
    performance = client.get_strategy_performance(strategy_id, "30d")

    optimizations = []

    # If win rate is low, reduce risk
    if performance["win_rate"] < 40:
        new_risk = strategy["risk_parameters"]["max_risk_per_trade"] * 0.8
        optimizations.append(("max_risk_per_trade", new_risk))

    # If drawdown is high, tighten stop losses
    if performance["max_drawdown"] > 1000:
        new_sl = strategy["risk_parameters"]["stop_loss_percentage"] * 0.8
        optimizations.append(("stop_loss_percentage", new_sl))

    # If profit factor is poor, increase take profit ratio
    if performance["profit_factor"] < 1.2:
        new_tp = strategy["risk_parameters"]["take_profit_ratio"] * 1.2
        optimizations.append(("take_profit_ratio", new_tp))

    return optimizations
```

## Monitoring and Debugging

### System Health Monitoring

#### Automated Health Checks

```python
import requests
import time
from datetime import datetime

def monitor_system_health(interval_seconds=300):
    """Monitor system health every 5 minutes"""

    while True:
        try:
            # Check system health
            response = requests.get("http://localhost:3000/api/v1/monitoring/health/system")

            if response.status_code == 200:
                health_data = response.json()

                if health_data["overall_status"] != "healthy":
                    print(f"⚠️  System unhealthy at {datetime.now()}")
                    print(f"Issues: {health_data['issues']}")

                    # Send alert (implement your alerting mechanism)
                    send_alert(f"System health issue: {health_data['issues']}")
                else:
                    print(f"✅ System healthy at {datetime.now()}")

            else:
                print(f"❌ Health check failed: {response.status_code}")
                send_alert(f"Health check endpoint failed: {response.status_code}")

        except Exception as e:
            print(f"❌ Health check error: {e}")
            send_alert(f"Health check error: {e}")

        time.sleep(interval_seconds)

def send_alert(message):
    """Implement your alerting mechanism here"""
    print(f"ALERT: {message}")
    # Could send email, Slack message, etc.
```

#### Performance Monitoring

```python
def monitor_performance_metrics():
    """Monitor key performance metrics"""

    response = requests.get("http://localhost:3000/api/v1/monitoring/performance")

    if response.status_code == 200:
        metrics = response.json()

        # Check decision engine performance
        de_metrics = metrics["decision_engine"]

        alerts = []

        if de_metrics["avg_response_time_ms"] > 5000:
            alerts.append("High decision latency detected")

        if de_metrics["error_rate"] > 10.0:
            alerts.append("High error rate detected")

        if de_metrics["cache_hit_rate"] < 20.0:
            alerts.append("Low cache hit rate")

        # Check LLM service performance
        llm_metrics = metrics["llm_service"]

        if llm_metrics["avg_response_time_ms"] > 10000:
            alerts.append("High LLM response time")

        if llm_metrics["cost_per_request"] > 0.05:
            alerts.append("High LLM costs detected")

        return alerts

    return ["Performance monitoring failed"]
```

### Debugging Tools

#### Decision Tracing

```python
def trace_decision_generation(client, symbol, account_id):
    """Trace the complete decision generation process"""

    print(f"🔍 Tracing decision generation for {symbol}, account {account_id}")

    # Step 1: Check account strategy
    try:
        strategy = client.get_account_strategy(account_id)
        print(f"✅ Strategy: {strategy['strategy_id']}")
    except Exception as e:
        print(f"❌ Strategy retrieval failed: {e}")
        return

    # Step 2: Generate decision with detailed logging
    try:
        start_time = time.time()
        decision_result = client.generate_decision(symbol, account_id)
        end_time = time.time()

        print(f"✅ Decision generated in {end_time - start_time:.2f}s")
        print(f"   Action: {decision_result['decision']['action']}")
        print(f"   Confidence: {decision_result['decision']['confidence']}")
        print(f"   Validation: {'✅' if decision_result['validation']['is_valid'] else '❌'}")

        if decision_result['validation']['errors']:
            print(f"   Errors: {decision_result['validation']['errors']}")

    except Exception as e:
        print(f"❌ Decision generation failed: {e}")

    # Step 3: Check system health
    try:
        health = client.get_system_health()
        print(f"✅ System health: {health['overall_status']}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
```

#### Log Analysis

```python
import re
from datetime import datetime, timedelta

def analyze_logs(log_file_path, hours_back=24):
    """Analyze application logs for issues"""

    cutoff_time = datetime.now() - timedelta(hours=hours_back)

    error_patterns = [
        r"ERROR.*decision.*generation",
        r"ERROR.*validation.*failed",
        r"ERROR.*strategy.*not.*found",
        r"ERROR.*rate.*limit",
        r"ERROR.*llm.*service"
    ]

    issues = {pattern: [] for pattern in error_patterns}

    try:
        with open(log_file_path, 'r') as f:
            for line in f:
                # Extract timestamp (assuming ISO format)
                timestamp_match = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', line)

                if timestamp_match:
                    timestamp_str = timestamp_match.group()
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                    if timestamp > cutoff_time:
                        for pattern in error_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                issues[pattern].append((timestamp, line.strip()))

        # Report findings
        for pattern, matches in issues.items():
            if matches:
                print(f"\n🔍 Pattern: {pattern}")
                print(f"   Found {len(matches)} matches:")
                for timestamp, line in matches[-5:]:  # Show last 5
                    print(f"   {timestamp}: {line}")

    except Exception as e:
        print(f"Error analyzing logs: {e}")

    return issues
```

## Frequently Asked Questions

### General Questions

**Q: How often should I monitor system health?**

A: Monitor system health continuously with automated checks every 5 minutes. Set up alerts for critical issues and review performance metrics daily.

**Q: What's the recommended number of concurrent accounts?**

A: The system is designed to handle 10+ concurrent accounts efficiently. Start with fewer accounts and scale up based on performance monitoring.

**Q: How do I backup decision history and strategy configurations?**

A: Decision history is stored in the PostgreSQL database. Use regular database backups:
```bash
pg_dump trading_db > backup_$(date +%Y%m%d).sql
```

### Strategy Questions

**Q: How do I know if a strategy is performing well?**

A: Monitor these key metrics:
- Win rate > 50%
- Profit factor > 1.5
- Sharpe ratio > 1.0
- Maximum drawdown < 10% of account balance

**Q: Can I run multiple strategies on the same account?**

A: No, each account can only have one active strategy at a time. However, you can switch strategies dynamically based on market conditions.

**Q: How do I create a strategy for specific market conditions?**

A: Use conditional logic in your prompt template:
```
If market volatility > 5%:
  - Use conservative position sizing
  - Tighten stop losses
  - Focus on high-probability setups

If trend strength > 0.8:
  - Use trend-following approach
  - Increase position sizes
  - Look for continuation patterns
```

### Technical Questions

**Q: Why are my decisions taking longer than 5 seconds?**

A: Common causes:
- High LLM API latency
- Complex prompt templates
- Insufficient caching
- Network connectivity issues

Solutions:
- Optimize prompt templates
- Enable caching
- Use batch processing
- Check network connectivity

**Q: How do I handle API rate limits?**

A: Implement exponential backoff and use batch endpoints:
```python
def handle_rate_limit(func, *args, **kwargs):
    max_retries = 5
    base_delay = 1

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
```

**Q: How do I optimize memory usage?**

A: Regular maintenance:
- Clear old cache entries
- Clean up old alerts
- Monitor memory usage
- Restart services periodically

### Configuration Questions

**Q: How do I set up multiple trading accounts?**

A: Enable multi-account mode and configure per-account settings:
```bash
export MULTI_ACCOUNT_MODE=true
export ACCOUNT_IDS=account1,account2

export ASTERDX_API_KEY_account1=key1
export ASTERDX_API_SECRET_account1=secret1
```

**Q: Can I use different LLM models for different accounts?**

A: Yes, configure per-account model preferences:
```bash
export LLM_MODEL_account1=x-ai/grok-4
export LLM_MODEL_account2=openai/gpt-4o
```

**Q: How do I configure custom risk parameters?**

A: Create custom strategies with specific risk parameters:
```python
custom_strategy = {
    "strategy_name": "Low Risk Strategy",
    "risk_parameters": {
        "max_risk_per_trade": 1.0,
        "max_daily_loss": 2.0,
        "stop_loss_percentage": 1.5,
        "take_profit_ratio": 3.0
    }
}
```

## Best Practices

### 1. Monitoring and Alerting

```python
# Set up comprehensive monitoring
def setup_monitoring():
    # Health checks every 5 minutes
    schedule.every(5).minutes.do(check_system_health)

    # Performance review every hour
    schedule.every().hour.do(review_performance_metrics)

    # Daily strategy performance review
    schedule.every().day.at("09:00").do(review_strategy_performance)

    # Weekly system maintenance
    schedule.every().sunday.at("02:00").do(system_maintenance)
```

### 2. Error Handling

```python
# Implement robust error handling
def robust_decision_generation(client, symbol, account_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.generate_decision(symbol, account_id)

        except RateLimitError:
            wait_time = (2 ** attempt) * 60  # Exponential backoff
            time.sleep(wait_time)

        except ValidationError as e:
            # Log validation error and return None
            logger.error(f"Validation error for {symbol}: {e}")
            return None

        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Final attempt failed for {symbol}: {e}")
                return None

            logger.warning(f"Attempt {attempt + 1} failed for {symbol}: {e}")
            time.sleep(30)  # Wait before retry

    return None
```

### 3. Performance Optimization

```python
# Optimize for performance
class OptimizedClient:
    def __init__(self):
        self.session = requests.Session()
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    def generate_decision_cached(self, symbol, account_id):
        cache_key = f"{symbol}_{account_id}"

        # Check cache first
        if cache_key in self.cache:
            cached_time, cached_result = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_result

        # Generate new decision
        result = self.generate_decision(symbol, account_id)

        # Cache result
        self.cache[cache_key] = (time.time(), result)

        return result
```

### 4. Security

```python
# Secure API key management
import os
from cryptography.fernet import Fernet

class SecureConfig:
    def __init__(self):
        self.encryption_key = os.environ.get('ENCRYPTION_KEY')
        self.cipher = Fernet(self.encryption_key) if self.encryption_key else None

    def get_api_key(self, service):
        encrypted_key = os.environ.get(f'{service}_API_KEY_ENCRYPTED')

        if encrypted_key and self.cipher:
            return self.cipher.decrypt(encrypted_key.encode()).decode()

        # Fallback to plain text (development only)
        return os.environ.get(f'{service}_API_KEY')
```

## Getting Help

### Support Channels

1. **Documentation**: Check this troubleshooting guide and API documentation
2. **Health Endpoints**: Use `/monitoring/health/system` for real-time status
3. **Logs**: Check application logs in `backend/logs/` directory
4. **Performance Metrics**: Monitor `/monitoring/performance` endpoint

### Reporting Issues

When reporting issues, include:

1. **Error Details**:
   - Exact error message
   - HTTP status code
   - Timestamp of occurrence

2. **System Information**:
   - System health status
   - Performance metrics
   - Configuration details (without sensitive data)

3. **Reproduction Steps**:
   - Exact API calls made
   - Request parameters
   - Expected vs actual behavior

4. **Logs**:
   - Relevant log entries
   - Error stack traces
   - System resource usage

### Emergency Procedures

#### System Down

1. Check system health endpoint
2. Review recent logs for errors
3. Restart services if needed:
   ```bash
   cd backend && podman-compose restart
   ```
4. Verify database connectivity
5. Check external service status (OpenRouter, AsterDEX)

#### Data Loss Prevention

1. Immediate database backup:
   ```bash
   pg_dump trading_db > emergency_backup_$(date +%Y%m%d_%H%M%S).sql
   ```
2. Stop all trading activities
3. Investigate root cause
4. Restore from backup if necessary

#### Security Incident

1. Immediately rotate API keys
2. Check access logs for unauthorized access
3. Review recent configuration changes
4. Update security credentials
5. Monitor for unusual activity

Remember: Always test fixes in a development environment before applying to production systems.