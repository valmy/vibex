# Strategy Configuration Guide

## Overview

The LLM Decision Engine supports multiple trading strategies that can be assigned to different accounts. This guide covers how to configure, customize, and manage trading strategies effectively.

## Predefined Strategies

### 1. Conservative Strategy

**Strategy ID:** `conservative`

**Characteristics:**
- Low risk tolerance
- Longer timeframes
- Smaller position sizes
- Higher take-profit ratios

**Configuration:**
```json
{
  "strategy_id": "conservative",
  "strategy_name": "Conservative Trading",
  "strategy_type": "conservative",
  "prompt_template": "Analyze {symbol} with a conservative approach. Focus on strong support/resistance levels, low volatility periods, and high-probability setups. Prioritize capital preservation over aggressive gains. Consider longer timeframes (4h, 1d) and look for confirmation from multiple indicators before recommending any position.",
  "risk_parameters": {
    "max_risk_per_trade": 1.0,
    "max_daily_loss": 3.0,
    "stop_loss_percentage": 2.0,
    "take_profit_ratio": 3.0,
    "max_leverage": 1.5,
    "cooldown_period": 3600
  },
  "timeframe_preference": ["4h", "1d"],
  "max_positions": 2,
  "position_sizing": "fixed",
  "is_active": true
}
```

**Best For:**
- Risk-averse traders
- Stable market conditions
- Long-term capital preservation
- Beginners

### 2. Aggressive Strategy

**Strategy ID:** `aggressive`

**Characteristics:**
- Higher risk tolerance
- Shorter timeframes
- Larger position sizes
- Quick profit-taking

**Configuration:**
```json
{
  "strategy_id": "aggressive",
  "strategy_name": "Aggressive Trading",
  "strategy_type": "aggressive",
  "prompt_template": "Analyze {symbol} with an aggressive trading approach. Look for momentum breakouts, trend continuations, and high-volatility opportunities. Use shorter timeframes (15m, 1h) for quick entries and exits. Focus on maximizing profit potential while managing risk through position sizing and stop losses.",
  "risk_parameters": {
    "max_risk_per_trade": 5.0,
    "max_daily_loss": 10.0,
    "stop_loss_percentage": 4.0,
    "take_profit_ratio": 2.0,
    "max_leverage": 5.0,
    "cooldown_period": 300
  },
  "timeframe_preference": ["15m", "1h"],
  "max_positions": 5,
  "position_sizing": "percentage",
  "is_active": true
}
```

**Best For:**
- Experienced traders
- High-volatility markets
- Active trading sessions
- Risk-tolerant accounts

### 3. Scalping Strategy

**Strategy ID:** `scalping`

**Characteristics:**
- Very short timeframes
- Quick in-and-out trades
- Small profit targets
- High frequency

**Configuration:**
```json
{
  "strategy_id": "scalping",
  "strategy_name": "Scalping Strategy",
  "strategy_type": "scalping",
  "prompt_template": "Analyze {symbol} for scalping opportunities. Focus on very short-term price movements (1m, 5m timeframes), order book dynamics, and micro-trends. Look for quick profit opportunities with tight stop losses. Prioritize high-liquidity periods and avoid major news events.",
  "risk_parameters": {
    "max_risk_per_trade": 0.5,
    "max_daily_loss": 2.0,
    "stop_loss_percentage": 1.0,
    "take_profit_ratio": 1.5,
    "max_leverage": 3.0,
    "cooldown_period": 60
  },
  "timeframe_preference": ["1m", "5m"],
  "max_positions": 3,
  "position_sizing": "fixed",
  "is_active": true
}
```

**Best For:**
- High-frequency trading
- Liquid markets
- Low-latency environments
- Experienced scalpers

### 4. Swing Trading Strategy

**Strategy ID:** `swing`

**Characteristics:**
- Medium-term positions
- Trend-following approach
- Balanced risk/reward
- Technical analysis focus

**Configuration:**
```json
{
  "strategy_id": "swing",
  "strategy_name": "Swing Trading",
  "strategy_type": "swing",
  "prompt_template": "Analyze {symbol} for swing trading opportunities. Focus on medium-term trends (1h, 4h timeframes), support/resistance levels, and momentum indicators. Look for trend continuations and reversals with clear entry/exit points. Balance risk and reward with appropriate position sizing.",
  "risk_parameters": {
    "max_risk_per_trade": 3.0,
    "max_daily_loss": 6.0,
    "stop_loss_percentage": 3.0,
    "take_profit_ratio": 2.5,
    "max_leverage": 3.0,
    "cooldown_period": 1800
  },
  "timeframe_preference": ["1h", "4h"],
  "max_positions": 4,
  "position_sizing": "volatility_adjusted",
  "is_active": true
}
```

**Best For:**
- Medium-term trading
- Trending markets
- Balanced approach
- Technical traders

### 5. DCA (Dollar Cost Averaging) Strategy

**Strategy ID:** `dca`

**Characteristics:**
- Gradual position building
- Long-term accumulation
- Lower volatility impact
- Systematic approach

**Configuration:**
```json
{
  "strategy_id": "dca",
  "strategy_name": "Dollar Cost Averaging",
  "strategy_type": "dca",
  "prompt_template": "Analyze {symbol} for DCA opportunities. Focus on long-term trends, fundamental strength, and accumulation zones. Recommend gradual position building during dips and systematic profit-taking during rallies. Use longer timeframes (4h, 1d) and emphasize consistency over timing.",
  "risk_parameters": {
    "max_risk_per_trade": 2.0,
    "max_daily_loss": 4.0,
    "stop_loss_percentage": 5.0,
    "take_profit_ratio": 4.0,
    "max_leverage": 2.0,
    "cooldown_period": 7200
  },
  "timeframe_preference": ["4h", "1d"],
  "max_positions": 3,
  "position_sizing": "fixed",
  "is_active": true
}
```

**Best For:**
- Long-term investors
- Volatile markets
- Systematic accumulation
- Risk management

## Custom Strategy Creation

### Strategy Configuration Parameters

#### Basic Information
- **strategy_id**: Unique identifier (auto-generated if not provided)
- **strategy_name**: Human-readable name
- **strategy_type**: Classification (conservative, aggressive, scalping, swing, dca, custom)

#### Prompt Template
The prompt template is the core of your strategy. It defines how the LLM analyzes market conditions.

**Template Variables:**
- `{symbol}`: Trading pair symbol
- `{timeframe}`: Current timeframe
- `{market_condition}`: Current market condition
- `{account_balance}`: Available balance
- `{risk_exposure}`: Current risk exposure

**Example Custom Template:**
```
Analyze {symbol} using a momentum-based approach. Current market condition is {market_condition}.
Account has {account_balance} USD available with {risk_exposure}% current exposure.

Focus on:
1. RSI divergences on {timeframe} timeframe
2. Volume confirmation for breakouts
3. Support/resistance levels from higher timeframes
4. Risk management based on current exposure

Provide clear entry, exit, and risk management recommendations.
```

#### Risk Parameters

```json
{
  "max_risk_per_trade": 2.5,        // Maximum risk per trade (%)
  "max_daily_loss": 5.0,            // Maximum daily loss limit (%)
  "stop_loss_percentage": 3.0,      // Default stop loss (%)
  "take_profit_ratio": 2.0,         // Risk/reward ratio
  "max_leverage": 3.0,              // Maximum leverage allowed
  "cooldown_period": 1800           // Cooldown between trades (seconds)
}
```

#### Position Sizing Methods

**1. Fixed Sizing**
```json
{
  "position_sizing": "fixed",
  "fixed_amount_usd": 1000.0
}
```

**2. Percentage Sizing**
```json
{
  "position_sizing": "percentage",
  "percentage_of_balance": 10.0
}
```

**3. Kelly Criterion**
```json
{
  "position_sizing": "kelly",
  "kelly_fraction": 0.25
}
```

**4. Volatility Adjusted**
```json
{
  "position_sizing": "volatility_adjusted",
  "base_percentage": 5.0,
  "volatility_multiplier": 0.5
}
```

### Creating a Custom Strategy

#### API Request Example

```bash
curl -X POST "http://localhost:3000/api/v1/strategies/custom" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "Momentum Breakout Strategy",
    "prompt_template": "Analyze {symbol} for momentum breakout opportunities...",
    "risk_parameters": {
      "max_risk_per_trade": 3.0,
      "max_daily_loss": 7.0,
      "stop_loss_percentage": 2.5,
      "take_profit_ratio": 2.5,
      "max_leverage": 4.0,
      "cooldown_period": 900
    },
    "timeframe_preference": ["15m", "1h", "4h"],
    "max_positions": 3,
    "position_sizing": "volatility_adjusted"
  }'
```

#### Python Example

```python
def create_momentum_strategy(client):
    strategy_config = {
        "strategy_name": "Momentum Breakout Strategy",
        "prompt_template": """
        Analyze {symbol} for momentum breakout opportunities on {timeframe} timeframe.

        Key Analysis Points:
        1. Look for volume-confirmed breakouts above resistance
        2. Check RSI for momentum confirmation (>60 for bullish)
        3. Ensure price is above key moving averages
        4. Verify support levels for stop loss placement

        Current market condition: {market_condition}
        Available balance: {account_balance} USD
        Current risk exposure: {risk_exposure}%

        Provide specific entry price, stop loss, and take profit levels.
        """,
        "risk_parameters": {
            "max_risk_per_trade": 3.0,
            "max_daily_loss": 7.0,
            "stop_loss_percentage": 2.5,
            "take_profit_ratio": 2.5,
            "max_leverage": 4.0,
            "cooldown_period": 900
        },
        "timeframe_preference": ["15m", "1h", "4h"],
        "max_positions": 3,
        "position_sizing": "volatility_adjusted"
    }

    response = client.create_custom_strategy(strategy_config)
    return response
```

## Strategy Assignment and Management

### Assigning Strategies to Accounts

#### Single Account Assignment

```python
# Assign strategy to account
client.assign_strategy_to_account(
    account_id=1,
    strategy_id="aggressive",
    assigned_by="trader_123",
    switch_reason="Market conditions favor aggressive approach"
)
```

#### Bulk Assignment

```python
# Assign strategies to multiple accounts
assignments = [
    {"account_id": 1, "strategy_id": "aggressive"},
    {"account_id": 2, "strategy_id": "conservative"},
    {"account_id": 3, "strategy_id": "swing"}
]

for assignment in assignments:
    client.assign_strategy_to_account(**assignment)
```

### Strategy Switching

#### Manual Switch

```python
# Switch strategy based on market conditions
def switch_strategy_based_on_volatility(client, account_id, volatility):
    if volatility > 5.0:
        # High volatility - use conservative approach
        client.switch_strategy(account_id, "conservative", "High volatility detected")
    elif volatility < 2.0:
        # Low volatility - use aggressive approach
        client.switch_strategy(account_id, "aggressive", "Low volatility opportunity")
    else:
        # Medium volatility - use swing strategy
        client.switch_strategy(account_id, "swing", "Balanced market conditions")
```

#### Automated Switch Based on Performance

```python
def auto_switch_based_on_performance(client, account_id):
    # Get current strategy performance
    current_strategy = client.get_account_strategy(account_id)
    performance = client.get_strategy_performance(
        current_strategy["strategy_id"],
        timeframe="7d"
    )

    # Switch if performance is poor
    if performance["win_rate"] < 40.0 or performance["total_pnl_percent"] < -5.0:
        # Switch to more conservative strategy
        if current_strategy["strategy_id"] != "conservative":
            client.switch_strategy(
                account_id,
                "conservative",
                f"Poor performance: {performance['win_rate']}% win rate"
            )
```

## Strategy Performance Monitoring

### Key Performance Metrics

#### Profitability Metrics
- **Total P&L**: Absolute profit/loss
- **P&L Percentage**: Return on investment
- **Win Rate**: Percentage of winning trades
- **Profit Factor**: Gross profit / Gross loss
- **Average Win/Loss**: Average profit per winning/losing trade

#### Risk Metrics
- **Sharpe Ratio**: Risk-adjusted return
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Risk-Adjusted Return**: Return per unit of risk
- **Volatility**: Standard deviation of returns

#### Efficiency Metrics
- **Trade Frequency**: Number of trades per period
- **Hold Time**: Average position duration
- **Capital Utilization**: Percentage of capital actively used

### Performance Analysis Example

```python
def analyze_strategy_performance(client, strategy_id, timeframe="30d"):
    # Get performance data
    performance = client.get_strategy_performance(strategy_id, timeframe)

    # Calculate additional metrics
    risk_reward_ratio = performance["avg_win"] / abs(performance["avg_loss"])
    expectancy = (performance["win_rate"] / 100 * performance["avg_win"]) + \
                ((100 - performance["win_rate"]) / 100 * performance["avg_loss"])

    # Performance assessment
    assessment = {
        "overall_rating": "good" if performance["profit_factor"] > 1.5 else "poor",
        "risk_assessment": "low" if performance["max_drawdown"] < 1000 else "high",
        "consistency": "high" if performance["win_rate"] > 60 else "low",
        "efficiency": "high" if performance["sharpe_ratio"] > 1.0 else "low"
    }

    return {
        "performance": performance,
        "calculated_metrics": {
            "risk_reward_ratio": risk_reward_ratio,
            "expectancy": expectancy
        },
        "assessment": assessment
    }
```

## Strategy Optimization

### A/B Testing Strategies

#### Setting Up A/B Tests

```python
def setup_strategy_ab_test(client, account_ids, strategy_a, strategy_b, duration_days=7):
    # Split accounts between strategies
    mid_point = len(account_ids) // 2
    group_a = account_ids[:mid_point]
    group_b = account_ids[mid_point:]

    # Assign strategies
    for account_id in group_a:
        client.switch_strategy(account_id, strategy_a, f"A/B test group A")

    for account_id in group_b:
        client.switch_strategy(account_id, strategy_b, f"A/B test group B")

    return {
        "test_start": datetime.now(),
        "duration_days": duration_days,
        "group_a": {"accounts": group_a, "strategy": strategy_a},
        "group_b": {"accounts": group_b, "strategy": strategy_b}
    }
```

#### Analyzing A/B Test Results

```python
def analyze_ab_test_results(client, test_config):
    results = {}

    for group_name, group_data in [("group_a", test_config["group_a"]),
                                   ("group_b", test_config["group_b"])]:
        group_performance = []

        for account_id in group_data["accounts"]:
            perf = client.get_account_performance(account_id, "7d")
            group_performance.append(perf)

        # Calculate group averages
        avg_pnl = sum(p["total_pnl_percent"] for p in group_performance) / len(group_performance)
        avg_win_rate = sum(p["win_rate"] for p in group_performance) / len(group_performance)

        results[group_name] = {
            "strategy": group_data["strategy"],
            "avg_pnl_percent": avg_pnl,
            "avg_win_rate": avg_win_rate,
            "account_count": len(group_data["accounts"])
        }

    # Determine winner
    winner = "group_a" if results["group_a"]["avg_pnl_percent"] > results["group_b"]["avg_pnl_percent"] else "group_b"

    return {
        "results": results,
        "winner": winner,
        "winning_strategy": results[winner]["strategy"]
    }
```

### Parameter Optimization

#### Risk Parameter Tuning

```python
def optimize_risk_parameters(client, strategy_id, account_id):
    base_strategy = client.get_strategy(strategy_id)

    # Test different risk levels
    risk_levels = [1.0, 2.0, 3.0, 4.0, 5.0]
    results = []

    for risk_level in risk_levels:
        # Create test strategy with different risk
        test_strategy = base_strategy.copy()
        test_strategy["risk_parameters"]["max_risk_per_trade"] = risk_level
        test_strategy["strategy_name"] = f"Test Risk {risk_level}%"

        # Create and test strategy
        test_id = client.create_custom_strategy(test_strategy)["strategy_id"]

        # Simulate or backtest (placeholder)
        simulated_performance = simulate_strategy_performance(test_strategy)

        results.append({
            "risk_level": risk_level,
            "performance": simulated_performance,
            "sharpe_ratio": simulated_performance["sharpe_ratio"]
        })

    # Find optimal risk level
    optimal = max(results, key=lambda x: x["sharpe_ratio"])

    return optimal
```

## Best Practices

### 1. Strategy Design Principles

#### Clear Objectives
- Define specific goals (profit target, risk tolerance)
- Align with market conditions
- Consider account size and experience level

#### Risk Management
- Always define maximum risk per trade
- Set daily loss limits
- Use appropriate position sizing
- Implement cooldown periods

#### Backtesting and Validation
- Test strategies on historical data
- Validate with paper trading
- Monitor live performance closely
- Adjust based on results

### 2. Prompt Engineering

#### Effective Prompt Structure
```
1. Context Setting
   - Market condition
   - Timeframe
   - Account status

2. Analysis Instructions
   - Specific indicators to check
   - Key levels to identify
   - Risk factors to consider

3. Decision Framework
   - Entry criteria
   - Exit criteria
   - Risk management rules

4. Output Format
   - Required decision fields
   - Confidence levels
   - Rationale requirements
```

#### Example High-Quality Prompt

```
Analyze {symbol} for trading opportunities on {timeframe} timeframe.

MARKET CONTEXT:
- Current condition: {market_condition}
- Account balance: {account_balance} USD
- Current exposure: {risk_exposure}%
- Maximum risk per trade: 2.5%

TECHNICAL ANALYSIS REQUIREMENTS:
1. Price Action: Check for breakouts, reversals, or continuation patterns
2. Volume: Confirm moves with volume analysis
3. Indicators: Use RSI (14), MACD, and EMA (20, 50) for confirmation
4. Support/Resistance: Identify key levels for entry and exit

RISK MANAGEMENT:
- Stop loss must be below recent swing low (long) or above swing high (short)
- Take profit should target 2:1 risk/reward minimum
- Consider position size based on volatility and account exposure

OUTPUT REQUIREMENTS:
- Specific entry price with rationale
- Clear stop loss and take profit levels
- Position size recommendation
- Confidence score (1-100)
- Risk assessment (low/medium/high)

Focus on high-probability setups with clear risk/reward profiles.
```

### 3. Strategy Lifecycle Management

#### Development Phase
1. **Research and Design**
   - Market analysis
   - Strategy hypothesis
   - Risk parameter definition

2. **Implementation**
   - Prompt template creation
   - Parameter configuration
   - Validation testing

3. **Testing**
   - Backtesting on historical data
   - Paper trading validation
   - Small-scale live testing

#### Production Phase
1. **Deployment**
   - Account assignment
   - Performance monitoring
   - Risk oversight

2. **Optimization**
   - Performance analysis
   - Parameter tuning
   - A/B testing

3. **Maintenance**
   - Regular review
   - Market adaptation
   - Strategy updates

#### Retirement Phase
1. **Performance Decline Detection**
   - Monitoring key metrics
   - Identifying degradation
   - Root cause analysis

2. **Graceful Shutdown**
   - Position closure
   - Account reassignment
   - Strategy deactivation

### 4. Common Pitfalls and Solutions

#### Over-Optimization
**Problem**: Strategy performs well in backtesting but fails in live trading
**Solution**:
- Use out-of-sample testing
- Implement walk-forward analysis
- Focus on robust parameters

#### Insufficient Risk Management
**Problem**: Large losses due to inadequate risk controls
**Solution**:
- Always define maximum risk limits
- Implement circuit breakers
- Monitor correlation risk

#### Strategy Drift
**Problem**: Strategy performance degrades over time
**Solution**:
- Regular performance reviews
- Market condition monitoring
- Adaptive parameter adjustment

#### Complexity Creep
**Problem**: Strategies become overly complex and hard to maintain
**Solution**:
- Keep strategies simple and focused
- Document all parameters and logic
- Regular strategy audits

## Troubleshooting

### Common Issues

#### Strategy Not Generating Decisions
1. Check strategy activation status
2. Verify account assignment
3. Review risk parameters (may be too restrictive)
4. Check market data availability

#### Poor Strategy Performance
1. Analyze market conditions vs strategy design
2. Review risk parameters
3. Check for over-optimization
4. Consider strategy switching

#### Validation Errors
1. Review prompt template for clarity
2. Check risk parameter consistency
3. Validate position sizing logic
4. Ensure proper error handling

### Debugging Tools

#### Strategy Performance Dashboard
```python
def create_strategy_dashboard(client, strategy_id):
    strategy = client.get_strategy(strategy_id)
    performance = client.get_strategy_performance(strategy_id, "30d")
    assignments = client.get_strategy_assignments(strategy_id)

    dashboard = {
        "strategy_info": strategy,
        "performance_metrics": performance,
        "account_assignments": assignments,
        "recent_decisions": client.get_recent_decisions(strategy_id, limit=10),
        "alerts": client.get_strategy_alerts(strategy_id=strategy_id)
    }

    return dashboard
```

#### Performance Comparison Tool
```python
def compare_strategy_performance(client, strategy_ids, timeframe="30d"):
    comparison = {}

    for strategy_id in strategy_ids:
        performance = client.get_strategy_performance(strategy_id, timeframe)
        comparison[strategy_id] = {
            "total_pnl_percent": performance["total_pnl_percent"],
            "win_rate": performance["win_rate"],
            "sharpe_ratio": performance["sharpe_ratio"],
            "max_drawdown": performance["max_drawdown"]
        }

    # Rank strategies
    ranked = sorted(comparison.items(),
                   key=lambda x: x[1]["sharpe_ratio"],
                   reverse=True)

    return {
        "comparison": comparison,
        "ranking": ranked,
        "best_strategy": ranked[0][0] if ranked else None
    }
```

## Advanced Topics

### Multi-Asset Strategy Coordination

```python
def coordinate_multi_asset_strategy(client, account_id, asset_groups):
    """
    Coordinate strategies across multiple asset groups
    """
    decisions = {}

    for group_name, assets in asset_groups.items():
        group_decisions = []

        for asset in assets:
            decision = client.generate_decision(asset, account_id)
            group_decisions.append(decision)

        # Analyze group correlation and adjust
        decisions[group_name] = optimize_group_allocation(group_decisions)

    return decisions
```

### Dynamic Strategy Switching

```python
def implement_dynamic_switching(client, account_id, market_indicators):
    """
    Automatically switch strategies based on market conditions
    """
    volatility = market_indicators["volatility"]
    trend_strength = market_indicators["trend_strength"]
    volume_profile = market_indicators["volume_profile"]

    # Strategy selection logic
    if volatility > 5.0 and trend_strength < 0.3:
        # High volatility, weak trend - use scalping
        target_strategy = "scalping"
    elif volatility < 2.0 and trend_strength > 0.7:
        # Low volatility, strong trend - use swing
        target_strategy = "swing"
    elif trend_strength > 0.8:
        # Very strong trend - use aggressive
        target_strategy = "aggressive"
    else:
        # Default to conservative
        target_strategy = "conservative"

    # Check if switch is needed
    current_strategy = client.get_account_strategy(account_id)
    if current_strategy["strategy_id"] != target_strategy:
        client.switch_strategy(
            account_id,
            target_strategy,
            f"Market conditions: vol={volatility}, trend={trend_strength}"
        )

    return target_strategy
```

This comprehensive guide covers all aspects of strategy configuration and management in the LLM Decision Engine. Use it as a reference for creating, optimizing, and managing trading strategies effectively.