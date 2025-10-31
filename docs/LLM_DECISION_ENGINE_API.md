# LLM Decision Engine API Documentation

## Overview

The LLM Decision Engine API provides comprehensive endpoints for AI-powered trading decision generation, strategy management, and system monitoring. This API integrates with OpenRouter to access multiple LLM models and provides structured trading decisions with validation and risk management.

## Base URL

```
http://localhost:3000/api/v1
```

## Authentication

All API endpoints require proper authentication. Include your API key in the request headers:

```http
Authorization: Bearer YOUR_API_KEY
```

## Rate Limiting

- **Decision Generation**: 60 requests per minute per account
- **Batch Operations**: 10 requests per minute per account
- **General Endpoints**: 100 requests per minute per IP

## Response Format

All API responses follow a consistent format:

```json
{
  "success": true,
  "data": {...},
  "message": "Operation completed successfully",
  "timestamp": "2025-10-31T10:00:00Z"
}
```

Error responses:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {...}
  },
  "timestamp": "2025-10-31T10:00:00Z"
}
```

## Decision Engine Endpoints

### Generate Trading Decision

Generate an AI-powered trading decision for a specific symbol and account.

**Endpoint:** `POST /decisions/generate`

**Request Body:**
```json
{
  "symbol": "BTCUSDT",
  "account_id": 1,
  "strategy_override": "aggressive",
  "force_refresh": false,
  "ab_test_name": "grok_vs_gpt_test"
}
```

**Response:**
```json
{
  "decision": {
    "asset": "BTCUSDT",
    "action": "buy",
    "allocation_usd": 1000.0,
    "tp_price": 52000.0,
    "sl_price": 48000.0,
    "exit_plan": "Take profit at resistance, stop loss below support",
    "rationale": "Strong bullish momentum with RSI oversold bounce...",
    "confidence": 85.5,
    "risk_level": "medium",
    "timestamp": "2025-10-31T10:00:00Z"
  },
  "validation": {
    "is_valid": true,
    "errors": [],
    "warnings": ["High volatility detected"],
    "validation_time_ms": 15
  },
  "context": {
    "market_conditions": "bullish",
    "strategy_used": "aggressive",
    "model_used": "x-ai/grok-4"
  },
  "metadata": {
    "processing_time_ms": 2500,
    "cache_hit": false,
    "decision_id": "dec_123456789"
  }
}
```

**Parameters:**
- `symbol` (required): Trading pair symbol (e.g., "BTCUSDT")
- `account_id` (required): Account identifier
- `strategy_override` (optional): Override default strategy
- `force_refresh` (optional): Force refresh of cached data
- `ab_test_name` (optional): A/B test identifier

**Rate Limit:** 60 requests/minute per account

### Batch Decision Generation

Generate decisions for multiple symbols concurrently.

**Endpoint:** `POST /decisions/batch`

**Request Body:**
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "account_id": 1,
  "strategy_override": "conservative",
  "force_refresh": false
}
```

**Response:**
```json
{
  "results": [
    {
      "symbol": "BTCUSDT",
      "decision": {...},
      "validation": {...},
      "success": true
    },
    {
      "symbol": "ETHUSDT",
      "decision": {...},
      "validation": {...},
      "success": true
    },
    {
      "symbol": "SOLUSDT",
      "error": "Insufficient market data",
      "success": false
    }
  ],
  "summary": {
    "total_requested": 3,
    "successful": 2,
    "failed": 1,
    "processing_time_ms": 4200
  }
}
```

**Limits:** Maximum 20 symbols per batch request

### Decision History

Retrieve historical decisions with filtering and pagination.

**Endpoint:** `GET /decisions/history/{account_id}`

**Query Parameters:**
- `symbol` (optional): Filter by symbol
- `limit` (optional): Number of results (1-1000, default: 100)
- `page` (optional): Page number (default: 1)
- `start_date` (optional): Start date filter (ISO 8601)
- `end_date` (optional): End date filter (ISO 8601)

**Example Request:**
```
GET /decisions/history/1?symbol=BTCUSDT&limit=50&page=1&start_date=2025-10-01T00:00:00Z
```

**Response:**
```json
{
  "decisions": [
    {
      "decision_id": "dec_123456789",
      "symbol": "BTCUSDT",
      "action": "buy",
      "allocation_usd": 1000.0,
      "confidence": 85.5,
      "timestamp": "2025-10-31T10:00:00Z",
      "strategy_used": "aggressive",
      "outcome": "pending"
    }
  ],
  "total_count": 150,
  "page": 1,
  "page_size": 50
}
```

### Validate Decision

Validate a trading decision without executing it.

**Endpoint:** `POST /decisions/validate`

**Request Body:**
```json
{
  "asset": "BTCUSDT",
  "action": "buy",
  "allocation_usd": 1000.0,
  "tp_price": 52000.0,
  "sl_price": 48000.0,
  "exit_plan": "Take profit at resistance",
  "rationale": "Strong bullish momentum",
  "confidence": 85.5,
  "risk_level": "medium"
}
```

**Response:**
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": ["High volatility detected"],
  "validation_time_ms": 15,
  "rules_checked": [
    "allocation_limit",
    "price_consistency",
    "risk_exposure",
    "position_sizing"
  ]
}
```

## Strategy Management Endpoints

### Get Available Strategies

Retrieve all available trading strategies.

**Endpoint:** `GET /strategies/available`

**Query Parameters:**
- `include_inactive` (optional): Include inactive strategies (default: false)

**Response:**
```json
{
  "strategies": [
    {
      "strategy_id": "conservative",
      "strategy_name": "Conservative Trading",
      "strategy_type": "conservative",
      "risk_parameters": {
        "max_risk_per_trade": 2.0,
        "max_daily_loss": 5.0,
        "stop_loss_percentage": 3.0,
        "take_profit_ratio": 2.0,
        "max_leverage": 2.0
      },
      "timeframe_preference": ["4h", "1d"],
      "max_positions": 2,
      "is_active": true
    }
  ],
  "total_count": 5,
  "active_count": 5,
  "inactive_count": 0
}
```

### Get Account Strategy

Get the currently assigned strategy for an account.

**Endpoint:** `GET /strategies/account/{account_id}`

**Response:**
```json
{
  "strategy_id": "aggressive",
  "strategy_name": "Aggressive Trading",
  "strategy_type": "aggressive",
  "assigned_at": "2025-10-31T09:00:00Z",
  "assigned_by": "system",
  "risk_parameters": {...},
  "performance_summary": {
    "total_pnl": 1250.50,
    "win_rate": 68.5,
    "trades_count": 23
  }
}
```

### Switch Account Strategy

Change the strategy assignment for an account.

**Endpoint:** `POST /strategies/account/{account_id}/switch`

**Request Body:**
```json
{
  "strategy_id": "conservative",
  "switch_reason": "Risk reduction requested",
  "switched_by": "user_123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Strategy switched to conservative",
  "account_id": 1,
  "previous_strategy": "aggressive",
  "new_strategy": "conservative",
  "switch_reason": "Risk reduction requested",
  "switched_at": "2025-10-31T10:00:00Z"
}
```

### Create Custom Strategy

Create a new custom trading strategy.

**Endpoint:** `POST /strategies/custom`

**Request Body:**
```json
{
  "strategy_name": "My Custom Strategy",
  "prompt_template": "Analyze {symbol} with focus on momentum indicators...",
  "risk_parameters": {
    "max_risk_per_trade": 3.0,
    "max_daily_loss": 8.0,
    "stop_loss_percentage": 4.0,
    "take_profit_ratio": 2.5,
    "max_leverage": 3.0
  },
  "timeframe_preference": ["1h", "4h"],
  "max_positions": 3,
  "position_sizing": "percentage"
}
```

**Response:**
```json
{
  "strategy_id": "my_custom_strategy_20251031_100000",
  "strategy_name": "My Custom Strategy",
  "created_at": "2025-10-31T10:00:00Z",
  "is_active": true,
  "validation_result": {
    "is_valid": true,
    "warnings": []
  }
}
```

### Get Strategy Performance

Get performance metrics for a specific strategy.

**Endpoint:** `GET /strategies/{strategy_id}/performance`

**Query Parameters:**
- `timeframe` (optional): Performance timeframe (7d, 30d, 90d, default: 7d)

**Response:**
```json
{
  "strategy_id": "aggressive",
  "timeframe": "7d",
  "performance": {
    "total_pnl": 1250.50,
    "total_pnl_percent": 12.5,
    "win_rate": 68.5,
    "profit_factor": 2.3,
    "sharpe_ratio": 1.8,
    "max_drawdown": 350.0,
    "trades_count": 23,
    "winning_trades": 16,
    "losing_trades": 7,
    "avg_win": 125.0,
    "avg_loss": -85.0
  },
  "risk_metrics": {
    "current_exposure": 15.5,
    "max_exposure_reached": 25.0,
    "risk_adjusted_return": 8.2
  }
}
```

## Monitoring Endpoints

### System Health

Get comprehensive system health status.

**Endpoint:** `GET /monitoring/health/system`

**Response:**
```json
{
  "overall_status": "healthy",
  "components": {
    "decision_engine": {
      "status": "healthy",
      "response_time_ms": 150,
      "consecutive_failures": 0,
      "circuit_breaker_open": false
    },
    "llm_service": {
      "status": "healthy",
      "current_model": "x-ai/grok-4",
      "response_time_ms": 2200,
      "consecutive_failures": 0
    },
    "strategy_manager": {
      "status": "healthy",
      "total_strategies": 5,
      "active_strategies": 5
    }
  },
  "uptime_seconds": 86400,
  "last_check": "2025-10-31T10:00:00Z",
  "issues": []
}
```

### Performance Metrics

Get comprehensive performance metrics for all system components.

**Endpoint:** `GET /monitoring/performance`

**Query Parameters:**
- `timeframe_hours` (optional): Hours to look back (1-168, default: 24)

**Response:**
```json
{
  "decision_engine": {
    "total_requests": 1250,
    "successful_requests": 1198,
    "failed_requests": 52,
    "avg_response_time_ms": 2100,
    "requests_per_hour": 52.1,
    "error_rate": 4.16,
    "cache_hit_rate": 35.2
  },
  "llm_service": {
    "total_requests": 1198,
    "successful_requests": 1185,
    "failed_requests": 13,
    "avg_response_time_ms": 2200,
    "total_cost_usd": 15.75,
    "cost_per_request": 0.0133
  }
}
```

### Model Management

Get LLM model management information.

**Endpoint:** `GET /monitoring/models`

**Response:**
```json
{
  "current_model": "x-ai/grok-4",
  "available_models": [
    "openai/gpt-4o",
    "x-ai/grok-4",
    "deepseek/deepseek-r1"
  ],
  "model_performance": {
    "x-ai/grok-4": {
      "total_requests": 850,
      "avg_response_time_ms": 2200,
      "success_rate": 98.8,
      "cost_per_request": 0.015
    },
    "openai/gpt-4o": {
      "total_requests": 348,
      "avg_response_time_ms": 1800,
      "success_rate": 99.1,
      "cost_per_request": 0.025
    }
  }
}
```

### Switch LLM Model

Switch to a different LLM model.

**Endpoint:** `POST /monitoring/models/{model_name}/switch`

**Response:**
```json
{
  "message": "Successfully switched to model 'openai/gpt-4o'",
  "previous_model": "x-ai/grok-4",
  "current_model": "openai/gpt-4o",
  "switch_time": "2025-10-31T10:00:00Z"
}
```

## Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `VALIDATION_ERROR` | Request validation failed | 400 |
| `RATE_LIMIT_EXCEEDED` | Rate limit exceeded | 429 |
| `STRATEGY_NOT_FOUND` | Strategy not found | 404 |
| `ACCOUNT_NOT_FOUND` | Account not found | 404 |
| `INSUFFICIENT_DATA` | Insufficient market data | 400 |
| `LLM_SERVICE_ERROR` | LLM service unavailable | 503 |
| `DECISION_VALIDATION_FAILED` | Decision validation failed | 400 |
| `INTERNAL_ERROR` | Internal server error | 500 |

## WebSocket Endpoints

### Real-time Decision Stream

Connect to real-time decision updates for an account.

**Endpoint:** `WS /decisions/stream/{account_id}`

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:3000/api/v1/decisions/stream/1');

ws.onopen = function() {
    // Subscribe to symbols
    ws.send(JSON.stringify({
        type: 'subscribe',
        symbols: ['BTCUSDT', 'ETHUSDT']
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```

**Message Types:**

**Connection Confirmation:**
```json
{
  "type": "connection",
  "message": "Connected to decision stream for account 1",
  "account_id": 1,
  "timestamp": "2025-10-31T10:00:00Z"
}
```

**Decision Update:**
```json
{
  "type": "decision",
  "account_id": 1,
  "symbol": "BTCUSDT",
  "decision": {...},
  "timestamp": "2025-10-31T10:00:00Z"
}
```

**Subscription Confirmation:**
```json
{
  "type": "subscription",
  "message": "Subscribed to 2 symbols",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "timestamp": "2025-10-31T10:00:00Z"
}
```

## SDK Examples

### Python SDK Example

```python
import requests
import json

class LLMDecisionEngineClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def generate_decision(self, symbol, account_id, strategy_override=None):
        """Generate a trading decision."""
        url = f"{self.base_url}/decisions/generate"
        data = {
            "symbol": symbol,
            "account_id": account_id,
            "strategy_override": strategy_override
        }

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def get_account_strategy(self, account_id):
        """Get current strategy for account."""
        url = f"{self.base_url}/strategies/account/{account_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def switch_strategy(self, account_id, strategy_id, reason=None):
        """Switch account strategy."""
        url = f"{self.base_url}/strategies/account/{account_id}/switch"
        data = {
            "strategy_id": strategy_id,
            "switch_reason": reason or "API request"
        }

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

# Usage example
client = LLMDecisionEngineClient(
    base_url="http://localhost:3000/api/v1",
    api_key="your_api_key"
)

# Generate decision
decision = client.generate_decision("BTCUSDT", 1, "aggressive")
print(f"Decision: {decision['decision']['action']} {decision['decision']['asset']}")

# Switch strategy
result = client.switch_strategy(1, "conservative", "Risk reduction")
print(f"Strategy switched: {result['message']}")
```

### JavaScript SDK Example

```javascript
class LLMDecisionEngineClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async generateDecision(symbol, accountId, strategyOverride = null) {
        const response = await fetch(`${this.baseUrl}/decisions/generate`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                symbol,
                account_id: accountId,
                strategy_override: strategyOverride
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    async getSystemHealth() {
        const response = await fetch(`${this.baseUrl}/monitoring/health/system`, {
            headers: this.headers
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    async batchDecisions(symbols, accountId) {
        const response = await fetch(`${this.baseUrl}/decisions/batch`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                symbols,
                account_id: accountId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }
}

// Usage example
const client = new LLMDecisionEngineClient(
    'http://localhost:3000/api/v1',
    'your_api_key'
);

// Generate decision
try {
    const decision = await client.generateDecision('BTCUSDT', 1, 'aggressive');
    console.log('Decision:', decision.decision.action, decision.decision.asset);
} catch (error) {
    console.error('Error generating decision:', error);
}

// Check system health
try {
    const health = await client.getSystemHealth();
    console.log('System status:', health.overall_status);
} catch (error) {
    console.error('Error checking health:', error);
}
```

## Best Practices

### 1. Error Handling

Always implement proper error handling for API calls:

```python
try:
    decision = client.generate_decision("BTCUSDT", 1)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 429:
        print("Rate limit exceeded, waiting...")
        time.sleep(60)
    elif e.response.status_code == 503:
        print("LLM service unavailable, using fallback...")
    else:
        print(f"API error: {e}")
```

### 2. Caching and Rate Limiting

- Cache decision results when appropriate
- Implement exponential backoff for rate limit handling
- Use batch endpoints for multiple symbols

### 3. Strategy Management

- Monitor strategy performance regularly
- Switch strategies based on market conditions
- Validate custom strategies before deployment

### 4. Monitoring and Alerting

- Set up health check monitoring
- Monitor performance metrics
- Configure alerts for system issues

### 5. Security

- Store API keys securely
- Use HTTPS in production
- Implement proper authentication
- Validate all inputs

## Troubleshooting

### Common Issues

**1. Rate Limit Exceeded (429)**
- Implement exponential backoff
- Use batch endpoints for multiple requests
- Monitor your request frequency

**2. LLM Service Unavailable (503)**
- Check system health endpoint
- Implement fallback mechanisms
- Monitor LLM service status

**3. Decision Validation Failed (400)**
- Check decision parameters
- Validate against business rules
- Review risk parameters

**4. Insufficient Market Data (400)**
- Ensure market data services are running
- Check symbol availability
- Verify data freshness

### Performance Optimization

**1. Use Caching**
- Enable decision caching for repeated requests
- Cache context data when possible
- Monitor cache hit rates

**2. Batch Operations**
- Use batch endpoints for multiple symbols
- Process decisions concurrently
- Optimize request patterns

**3. Strategy Optimization**
- Monitor strategy performance
- Adjust risk parameters based on results
- Use A/B testing for strategy comparison

## Support

For technical support and questions:

- **Documentation**: Check this API documentation
- **Health Endpoint**: Monitor `/monitoring/health/system`
- **Logs**: Check application logs for detailed error information
- **Performance**: Monitor `/monitoring/performance` for system metrics

## Changelog

### Version 1.0.0 (2025-10-31)
- Initial release of LLM Decision Engine API
- Decision generation endpoints
- Strategy management system
- Comprehensive monitoring and analytics
- WebSocket support for real-time updates
- Multi-model LLM support
- A/B testing framework