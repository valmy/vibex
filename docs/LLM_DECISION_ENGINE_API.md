# LLM Decision Engine API Documentation

## Overview

The LLM Decision Engine provides AI-powered trading decisions for perpetual futures trading across multiple assets. It analyzes market data, technical indicators, and account state to generate comprehensive portfolio-level trading recommendations.

**Key Features:**
- Multi-asset analysis across all configured assets (BTC, ETH, SOL, etc.)
- Portfolio-level decision making with capital allocation optimization
- Support for multiple trading strategies (conservative, aggressive, scalping, swing, DCA)
- Real-time decision generation with validation and risk management
- Comprehensive decision history and performance tracking

## Base URL

```
http://localhost:3000/api/v1
```

## Authentication

All endpoints require authentication via API key or session token (implementation-specific).

## Multi-Asset Decision Structure

### TradingDecision Schema

```json
{
  "decisions": [
    {
      "asset": "BTCUSDT",
      "action": "buy",
      "allocation_usd": 5000.0,
      "tp_price": 52000.0,
      "sl_price": 48000.0,
      "exit_plan": "Take profit at resistance, stop loss below support",
      "rationale": "Strong bullish momentum with RSI oversold recovery",
      "confidence": 85.0,
      "risk_level": "medium"
    },
    {
      "asset": "ETHUSDT",
      "action": "hold",
      "allocation_usd": 0.0,
      "tp_price": null,
      "sl_price": null,
      "exit_plan": "Wait for clearer trend confirmation",
      "rationale": "Consolidating near key support, awaiting breakout",
      "confidence": 60.0,
      "risk_level": "low"
    }
  ],
  "portfolio_rationale": "Focus on BTC strength while monitoring ETH consolidation. Total allocation 50% of available capital to maintain risk management.",
  "total_allocation_usd": 5000.0,
  "portfolio_risk_level": "medium",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### AssetDecision Fields

- **asset** (string): Trading pair symbol (e.g., "BTCUSDT")
- **action** (string): Trading action - one of:
  - `buy`: Open new long position
  - `sell`: Open new short position
  - `hold`: No action, maintain current state
  - `adjust_position`: Modify existing position size
  - `close_position`: Close existing position
  - `adjust_orders`: Modify TP/SL orders only
- **allocation_usd** (float): Capital to allocate in USD (0 for hold/close actions)
- **position_adjustment** (object, optional): Details for adjust_position action
- **order_adjustment** (object, optional): Details for adjust_orders action
- **tp_price** (float, optional): Take-profit price target
- **sl_price** (float, optional): Stop-loss price level
- **exit_plan** (string): Description of exit strategy
- **rationale** (string): Reasoning for this asset's decision
- **confidence** (float): Confidence score 0-100
- **risk_level** (string): Risk assessment - "low", "medium", or "high"

### Portfolio-Level Fields

- **portfolio_rationale** (string): Overall trading strategy across all assets
- **total_allocation_usd** (float): Sum of all asset allocations
- **portfolio_risk_level** (string): Overall portfolio risk - "low", "medium", or "high"

## API Endpoints

### 1. Generate Trading Decision

Generate AI-powered trading decisions for multiple assets.

**Endpoint:** `POST /decisions/generate`

**Request Body:**

```json
{
  "account_id": 1,
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "force_refresh": false
}
```

**Parameters:**
- `account_id` (integer, required): Trading account identifier
- `symbols` (array, optional): List of asset symbols to analyze. If omitted, uses all assets from `$ASSETS` environment variable
- `force_refresh` (boolean, optional): Skip cache and generate fresh decision. Default: false

**Response:** `200 OK`

```json
{
  "decision": {
    "decisions": [
      {
        "asset": "BTCUSDT",
        "action": "buy",
        "allocation_usd": 5000.0,
        "tp_price": 52000.0,
        "sl_price": 48000.0,
        "exit_plan": "Take profit at resistance, stop loss below support",
        "rationale": "Strong bullish momentum with RSI oversold recovery",
        "confidence": 85.0,
        "risk_level": "medium"
      }
    ],
    "portfolio_rationale": "Focus on BTC strength while monitoring other assets",
    "total_allocation_usd": 5000.0,
    "portfolio_risk_level": "medium",
    "timestamp": "2025-01-15T10:30:00Z"
  },
  "context": {
    "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "account_id": 1,
    "market_data": {
      "assets": {
        "BTCUSDT": {
          "symbol": "BTCUSDT",
          "current_price": 50000.0,
          "price_change_24h": 2.5,
          "volume_24h": 1500000000.0,
          "volatility": 0.025
        }
      }
    }
  },
  "validation": {
    "is_valid": true,
    "errors": [],
    "warnings": []
  },
  "metadata": {
    "generation_time_ms": 2500,
    "model_used": "x-ai/grok-4",
    "strategy": "conservative_swing",
    "cached": false
  }
}
```

**Error Responses:**

```json
{
  "error": "Insufficient market data",
  "details": "Unable to fetch data for SOLUSDT",
  "code": "CONTEXT_BUILDING_ERROR"
}
```

### 2. Get Decision History

Retrieve historical trading decisions for an account.

**Endpoint:** `GET /decisions/history`

**Query Parameters:**
- `account_id` (integer, required): Trading account identifier
- `symbol` (string, optional): Filter by specific asset symbol
- `limit` (integer, optional): Maximum number of decisions to return. Default: 50, Max: 200
- `offset` (integer, optional): Pagination offset. Default: 0
- `start_date` (string, optional): Filter decisions after this date (ISO 8601)
- `end_date` (string, optional): Filter decisions before this date (ISO 8601)

**Example Request:**

```
GET /decisions/history?account_id=1&symbol=BTCUSDT&limit=10
```

**Response:** `200 OK`

```json
{
  "decisions": [
    {
      "id": 123,
      "account_id": 1,
      "decision": {
        "decisions": [...],
        "portfolio_rationale": "...",
        "total_allocation_usd": 5000.0
      },
      "timestamp": "2025-01-15T10:30:00Z",
      "strategy_used": "conservative_swing",
      "model_used": "x-ai/grok-4",
      "executed": true,
      "outcome": {
        "pnl": 250.0,
        "pnl_percentage": 5.0,
        "closed_at": "2025-01-16T14:20:00Z"
      }
    }
  ],
  "total_count": 45,
  "page": 1,
  "page_size": 10
}
```

### 3. Validate Decision

Validate a trading decision without executing it.

**Endpoint:** `POST /decisions/validate`

**Request Body:**

```json
{
  "decision": {
    "decisions": [
      {
        "asset": "BTCUSDT",
        "action": "buy",
        "allocation_usd": 5000.0,
        "tp_price": 52000.0,
        "sl_price": 48000.0,
        "exit_plan": "Standard exit",
        "rationale": "Test decision",
        "confidence": 75.0,
        "risk_level": "medium"
      }
    ],
    "portfolio_rationale": "Test portfolio strategy",
    "total_allocation_usd": 5000.0,
    "portfolio_risk_level": "medium"
  },
  "context": {
    "account_id": 1,
    "symbols": ["BTCUSDT"]
  }
}
```

**Response:** `200 OK`

```json
{
  "is_valid": true,
  "errors": [],
  "warnings": [
    "Allocation exceeds 50% of available capital"
  ],
  "risk_assessment": {
    "portfolio_risk_score": 6.5,
    "concentration_risk": 0.5,
    "leverage_risk": 0.3
  }
}
```

### 4. Get Available Strategies

List all available trading strategies.

**Endpoint:** `GET /strategies/available`

**Response:** `200 OK`

```json
{
  "strategies": [
    {
      "strategy_id": "conservative_swing",
      "strategy_name": "Conservative Swing Trading",
      "strategy_type": "swing",
      "description": "Low-risk swing trading with strict risk management",
      "risk_parameters": {
        "max_risk_per_trade": 2.0,
        "max_daily_loss": 5.0,
        "stop_loss_percentage": 3.0,
        "take_profit_ratio": 2.5,
        "max_leverage": 2.0
      },
      "max_positions": 3,
      "timeframe_preference": ["4h", "1d"]
    }
  ]
}
```

### 5. Get Account Strategy

Get the current strategy assigned to an account.

**Endpoint:** `GET /strategies/account/{account_id}`

**Response:** `200 OK`

```json
{
  "account_id": 1,
  "strategy": {
    "strategy_id": "conservative_swing",
    "strategy_name": "Conservative Swing Trading",
    "strategy_type": "swing",
    "is_active": true,
    "assigned_at": "2025-01-10T08:00:00Z"
  },
  "performance": {
    "total_trades": 25,
    "win_rate": 68.0,
    "total_pnl": 1250.0,
    "sharpe_ratio": 1.8
  }
}
```

### 6. Switch Account Strategy

Change the trading strategy for an account.

**Endpoint:** `POST /strategies/account/{account_id}/switch`

**Request Body:**

```json
{
  "strategy_id": "aggressive_scalping"
}
```

**Response:** `200 OK`

```json
{
  "success": true,
  "message": "Strategy switched successfully",
  "previous_strategy": "conservative_swing",
  "new_strategy": "aggressive_scalping",
  "effective_at": "2025-01-15T10:35:00Z"
}
```

### 7. Get Decision Metrics

Get performance metrics for decision generation.

**Endpoint:** `GET /decisions/metrics`

**Query Parameters:**
- `account_id` (integer, optional): Filter by account
- `timeframe` (string, optional): Time period - "1h", "24h", "7d", "30d". Default: "24h"

**Response:** `200 OK`

```json
{
  "timeframe": "24h",
  "metrics": {
    "total_decisions": 48,
    "decisions_executed": 42,
    "execution_rate": 87.5,
    "avg_generation_time_ms": 2300,
    "avg_confidence": 78.5,
    "validation_success_rate": 95.8,
    "model_usage": {
      "x-ai/grok-4": 45,
      "openai/gpt-4": 3
    },
    "api_costs_usd": 2.45
  },
  "performance": {
    "total_pnl": 850.0,
    "win_rate": 65.0,
    "avg_trade_duration_hours": 18.5,
    "best_performing_asset": "BTCUSDT",
    "worst_performing_asset": "SOLUSDT"
  }
}
```

### 8. Get Strategy Performance

Get detailed performance metrics for a specific strategy.

**Endpoint:** `GET /strategies/{strategy_id}/performance`

**Query Parameters:**
- `timeframe` (string, optional): Time period - "7d", "30d", "90d", "1y". Default: "30d"

**Response:** `200 OK`

```json
{
  "strategy_id": "conservative_swing",
  "timeframe": "30d",
  "performance": {
    "total_trades": 125,
    "winning_trades": 85,
    "losing_trades": 40,
    "win_rate": 68.0,
    "total_pnl": 5250.0,
    "avg_win": 125.0,
    "avg_loss": -75.0,
    "profit_factor": 2.33,
    "sharpe_ratio": 1.85,
    "max_drawdown": -450.0,
    "avg_trade_duration_hours": 24.5
  },
  "asset_breakdown": {
    "BTCUSDT": {
      "trades": 50,
      "win_rate": 72.0,
      "pnl": 2500.0
    },
    "ETHUSDT": {
      "trades": 45,
      "win_rate": 66.7,
      "pnl": 1800.0
    }
  }
}
```

## Common Usage Scenarios

### Scenario 1: Generate Decision for All Configured Assets

```python
import httpx

async def generate_multi_asset_decision(account_id: int):
    """Generate decision for all assets in $ASSETS environment variable."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3000/api/v1/decisions/generate",
            json={"account_id": account_id}
        )
        return response.json()

# Usage
decision_result = await generate_multi_asset_decision(account_id=1)
print(f"Portfolio strategy: {decision_result['decision']['portfolio_rationale']}")
print(f"Total allocation: ${decision_result['decision']['total_allocation_usd']}")

for asset_decision in decision_result['decision']['decisions']:
    print(f"{asset_decision['asset']}: {asset_decision['action']} - {asset_decision['rationale']}")
```

### Scenario 2: Generate Decision for Specific Assets

```python
async def generate_specific_assets_decision(account_id: int, symbols: list[str]):
    """Generate decision for specific assets only."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3000/api/v1/decisions/generate",
            json={
                "account_id": account_id,
                "symbols": symbols
            }
        )
        return response.json()

# Usage - analyze only BTC and ETH
decision_result = await generate_specific_assets_decision(
    account_id=1,
    symbols=["BTCUSDT", "ETHUSDT"]
)
```

### Scenario 3: Filter Decision History by Asset

```python
async def get_btc_decision_history(account_id: int, limit: int = 20):
    """Get decision history for BTC only."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:3000/api/v1/decisions/history",
            params={
                "account_id": account_id,
                "symbol": "BTCUSDT",
                "limit": limit
            }
        )
        return response.json()

# Usage
btc_history = await get_btc_decision_history(account_id=1)
print(f"Found {btc_history['total_count']} BTC decisions")
```

### Scenario 4: Switch Strategy and Generate New Decision

```python
async def switch_strategy_and_decide(account_id: int, new_strategy: str):
    """Switch trading strategy and generate fresh decision."""
    async with httpx.AsyncClient() as client:
        # Switch strategy
        await client.post(
            f"http://localhost:3000/api/v1/strategies/account/{account_id}/switch",
            json={"strategy_id": new_strategy}
        )

        # Generate new decision with updated strategy
        response = await client.post(
            "http://localhost:3000/api/v1/decisions/generate",
            json={
                "account_id": account_id,
                "force_refresh": True  # Skip cache
            }
        )
        return response.json()

# Usage
decision = await switch_strategy_and_decide(
    account_id=1,
    new_strategy="aggressive_scalping"
)
```

### Scenario 5: Validate Custom Decision Before Execution

```python
async def validate_custom_decision(decision_data: dict, account_id: int):
    """Validate a custom trading decision."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3000/api/v1/decisions/validate",
            json={
                "decision": decision_data,
                "context": {"account_id": account_id}
            }
        )
        validation = response.json()

        if not validation['is_valid']:
            print("Validation errors:")
            for error in validation['errors']:
                print(f"  - {error}")

        if validation['warnings']:
            print("Warnings:")
            for warning in validation['warnings']:
                print(f"  - {warning}")

        return validation

# Usage
custom_decision = {
    "decisions": [
        {
            "asset": "BTCUSDT",
            "action": "buy",
            "allocation_usd": 10000.0,
            "tp_price": 55000.0,
            "sl_price": 48000.0,
            "exit_plan": "Standard exit",
            "rationale": "Custom analysis",
            "confidence": 80.0,
            "risk_level": "high"
        }
    ],
    "portfolio_rationale": "High conviction BTC trade",
    "total_allocation_usd": 10000.0,
    "portfolio_risk_level": "high"
}

validation = await validate_custom_decision(custom_decision, account_id=1)
```

### Scenario 6: Monitor Decision Performance

```python
async def monitor_decision_performance(account_id: int):
    """Monitor decision generation and trading performance."""
    async with httpx.AsyncClient() as client:
        # Get decision metrics
        metrics_response = await client.get(
            "http://localhost:3000/api/v1/decisions/metrics",
            params={"account_id": account_id, "timeframe": "24h"}
        )
        metrics = metrics_response.json()

        print(f"24h Performance Summary:")
        print(f"  Total decisions: {metrics['metrics']['total_decisions']}")
        print(f"  Execution rate: {metrics['metrics']['execution_rate']}%")
        print(f"  Avg confidence: {metrics['metrics']['avg_confidence']}")
        print(f"  Win rate: {metrics['performance']['win_rate']}%")
        print(f"  Total P&L: ${metrics['performance']['total_pnl']}")

        return metrics

# Usage
performance = await monitor_decision_performance(account_id=1)
```

## Integration Guide

### Step 1: Environment Configuration

Configure the `$ASSETS` environment variable with your desired trading pairs:

```bash
export ASSETS="BTCUSDT,ETHUSDT,SOLUSDT"
```

### Step 2: Initialize Decision Engine Client

```python
from typing import Optional
import httpx

class DecisionEngineClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def generate_decision(
        self,
        account_id: int,
        symbols: Optional[list[str]] = None,
        force_refresh: bool = False
    ):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/decisions/generate",
                json={
                    "account_id": account_id,
                    "symbols": symbols,
                    "force_refresh": force_refresh
                },
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

# Usage
client = DecisionEngineClient("http://localhost:3000/api/v1")
decision = await client.generate_decision(account_id=1)
```

### Step 3: Process Multi-Asset Decisions

```python
def process_trading_decision(decision_result: dict):
    """Process and execute trading decisions."""
    decision = decision_result['decision']

    print(f"Portfolio Strategy: {decision['portfolio_rationale']}")
    print(f"Total Allocation: ${decision['total_allocation_usd']}")
    print(f"Portfolio Risk: {decision['portfolio_risk_level']}")
    print()

    for asset_decision in decision['decisions']:
        asset = asset_decision['asset']
        action = asset_decision['action']

        if action == 'buy':
            print(f"🟢 {asset}: BUY ${asset_decision['allocation_usd']}")
            print(f"   TP: ${asset_decision['tp_price']}, SL: ${asset_decision['sl_price']}")
            print(f"   Rationale: {asset_decision['rationale']}")
            print(f"   Confidence: {asset_decision['confidence']}%")
            # Execute buy order

        elif action == 'sell':
            print(f"🔴 {asset}: SELL ${asset_decision['allocation_usd']}")
            # Execute sell order

        elif action == 'hold':
            print(f"⚪ {asset}: HOLD")
            print(f"   Rationale: {asset_decision['rationale']}")

        elif action == 'adjust_position':
            print(f"🔵 {asset}: ADJUST POSITION")
            # Execute position adjustment

        elif action == 'close_position':
            print(f"🟠 {asset}: CLOSE POSITION")
            # Execute position close

        print()

# Usage
decision_result = await client.generate_decision(account_id=1)
process_trading_decision(decision_result)
```

### Step 4: Implement Error Handling

```python
from httpx import HTTPStatusError

async def safe_generate_decision(client: DecisionEngineClient, account_id: int):
    """Generate decision with comprehensive error handling."""
    try:
        decision = await client.generate_decision(account_id)
        return decision

    except HTTPStatusError as e:
        if e.response.status_code == 400:
            error_data = e.response.json()
            print(f"Bad request: {error_data.get('error')}")
            print(f"Details: {error_data.get('details')}")
        elif e.response.status_code == 500:
            print("Server error - decision generation failed")
        else:
            print(f"HTTP error: {e.response.status_code}")
        return None

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None

# Usage
decision = await safe_generate_decision(client, account_id=1)
if decision:
    process_trading_decision(decision)
```

## Best Practices

### 1. Cache Management

- Use `force_refresh=False` (default) for normal operations to benefit from caching
- Use `force_refresh=True` only when you need the most current analysis
- Cache is automatically invalidated on significant market changes

### 2. Symbol Filtering

- Omit `symbols` parameter to analyze all configured assets (recommended)
- Use `symbols` parameter only when you need to focus on specific assets
- Ensure symbols match your exchange's format (e.g., "BTCUSDT" not "BTC/USDT")

### 3. Strategy Selection

- Start with conservative strategies for new accounts
- Monitor performance metrics before switching to aggressive strategies
- Use strategy performance endpoints to compare effectiveness

### 4. Risk Management

- Always validate decisions before execution
- Monitor portfolio concentration risk across assets
- Set appropriate position size limits in strategy configuration
- Review validation warnings even when decisions are valid

### 5. Performance Monitoring

- Regularly check decision metrics to track system health
- Monitor API costs to optimize model usage
- Track win rates and P&L by asset and strategy
- Use decision history to analyze patterns and improve strategies

### 6. Error Handling

- Implement retry logic for transient failures
- Log all decision generation attempts for audit trail
- Have fallback strategies for when LLM services are unavailable
- Monitor validation error rates to identify configuration issues

## Rate Limits

- Decision generation: 60 requests per minute per account
- Decision history: 120 requests per minute
- Strategy operations: 30 requests per minute per account
- Metrics endpoints: 120 requests per minute

## Troubleshooting

### Issue: "Insufficient market data" error

**Solution:** Ensure all symbols in your request have available market data. Check that symbols are correctly formatted and supported by your exchange.

### Issue: High validation failure rate

**Solution:** Review your strategy risk parameters. Ensure they align with your account balance and market conditions. Check validation error messages for specific issues.

### Issue: Slow decision generation

**Solution:**
- Reduce the number of symbols being analyzed
- Check your LLM model selection (some models are faster than others)
- Ensure your technical analysis service is performing well
- Monitor API response times in metrics

### Issue: Inconsistent decisions

**Solution:**
- Check if you're using `force_refresh=True` too frequently
- Verify your strategy configuration is stable
- Review market volatility - high volatility can lead to varying decisions
- Check decision confidence scores - low confidence may indicate unclear market conditions

## Support

For additional support:
- Review the deployment guide: `docs/DEPLOYMENT_GUIDE.md`
- Check troubleshooting FAQ: `docs/TROUBLESHOOTING_FAQ.md`
- Review system logs in `logs/llm.log`
- Monitor system health via metrics endpoints
