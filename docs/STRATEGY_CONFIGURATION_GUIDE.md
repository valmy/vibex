# Strategy Configuration Guide for Perpetual Futures DEX Trading

## Overview

This guide is tailored for AI-powered trading bots on AsterDex perpetual futures DEX. Strategies are optimized for short-term trading with 5-minute candles as the primary timeframe, complemented by 4-hour candles for trend context. All strategies account for leverage, funding rates, and AsterDex's competitive fee structure (0.005% maker, 0.04% taker).

---

## Predefined Strategies

### 1. Conservative Perpetual Strategy

**Strategy ID:** `conservative_perps`

**Characteristics:**

- Low risk tolerance with leverage awareness
- 5m entries, 4h trend confirmation
- Small position sizes with 2-3x leverage
- Prioritizes limit orders (maker fees)
- High take-profit ratios to offset funding costs

**Configuration:**

```json
{
  "strategy_id": "conservative_perps",
  "strategy_name": "Conservative Perps",
  "strategy_type": "conservative",
  "prompt_template": "Analyze {symbol} perpetual futures conservatively. Use 5m timeframe for precise entries but confirm bias on 4h trend. Focus on strong support/resistance, funding rate direction, and liquidation cluster avoidance. Prioritize limit orders (maker) for fee efficiency. Current funding rate: {funding_rate}%. Target 3:1+ reward/risk to offset holding costs. Maximum 2 concurrent positions.",
  "risk_parameters": {
    "max_risk_per_trade": 0.5,
    "max_daily_loss": 2.0,
    "stop_loss_percentage": 1.5,
    "take_profit_ratio": 3.0,
    "max_leverage": 3.0,
    "cooldown_period": 600,
    "max_funding_rate_bps": 5.0
  },
  "timeframe_preference": ["5m", "15m", "4h"],
  "max_positions": 2,
  "position_sizing": "volatility_adjusted",
  "order_preference": "maker_only",
  "funding_rate_threshold": 0.05,
  "is_active": true
}
```

**Best For:**

- Risk-averse traders in leveraged markets
- High funding rate environments
- Account preservation
- Avoiding liquidation risk

---

### 2. Aggressive Perpetual Strategy

**Strategy ID:** `aggressive_perps`

**Characteristics:**

- High risk tolerance for volatile moves
- 5m primary, 1h for structure
- Up to 15x leverage
- Taker orders accepted for breakout speed
- Quick profit-taking to minimize funding fees

**Configuration:**

```json
{
  "strategy_id": "aggressive_perps",
  "strategy_name": "Aggressive Perps",
  "strategy_type": "aggressive",
  "prompt_template": "Analyze {symbol} for aggressive perpetual futures trading on 5m timeframe. Hunt for momentum breakouts, funding rate squeezes, and liquidation hunts. Accept taker fees for immediate entries on confirmed breaks. Monitor open interest changes and funding rate: {funding_rate}%. Use 15x max leverage with 2% stop loss. Target 2:1 risk/reward, exit within 4-6 hours to limit funding. Obey daily loss limits strictly.",
  "risk_parameters": {
    "max_risk_per_trade": 2.0,
    "max_daily_loss": 8.0,
    "stop_loss_percentage": 2.0,
    "take_profit_ratio": 2.0,
    "max_leverage": 15.0,
    "cooldown_period": 120,
    "max_funding_rate_bps": 15.0
  },
  "timeframe_preference": ["5m", "15m", "1h"],
  "max_positions": 4,
  "position_sizing": "percentage",
  "order_preference": "taker_accepted",
  "funding_rate_threshold": 0.15,
  "is_active": true
}
```

**Best For:**

- Experienced perps traders
- High-volatility breakouts
- Active session trading (avoid holding through funding)
- Capitalizing on liquidation cascades

---

### 3. Scalping Perpetual Strategy

**Strategy ID:** `scalping_perps`

**Characteristics:**

- Ultra-short 5m/1m entries
- 5-10x leverage
- Strict maker order focus for fee edge
- Aim for 0.1-0.3% profit per trade
- High frequency, minimal duration

**Configuration:**

```json
{
  "strategy_id": "scalping_perps",
  "strategy_name": "Perps Scalping",
  "strategy_type": "scalping",
  "prompt_template": "Scalp {symbol} perpetuals on 1m/5m timeframes. Focus on order book imbalances, micro-divergences, and funding rate arbitrage. USE LIMIT ORDERS ONLY (maker fee 0.005%). Target 0.2% profit with 0.15% stop. Avoid trading 5 minutes before/after funding. Current funding: {funding_rate}bps. Max hold time: 30 minutes. Check liquidation heatmap for cluster avoidance.",
  "risk_parameters": {
    "max_risk_per_trade": 0.25,
    "max_daily_loss": 1.5,
    "stop_loss_percentage": 0.15,
    "take_profit_ratio": 1.3,
    "max_leverage": 10.0,
    "cooldown_period": 30,
    "max_funding_rate_bps": 3.0
  },
  "timeframe_preference": ["1m", "5m"],
  "max_positions": 3,
  "position_sizing": "fixed",
  "order_preference": "maker_only",
  "funding_rate_threshold": 0.03,
  "is_active": true
}
```

**Best For:**

- High-frequency perps trading
- Liquid major pairs (BTC, ETH)
- Fee-sensitive strategies
- Low-volatility range periods

---

### 4. Swing Perpetual Strategy

**Strategy ID:** `swing_perps`

**Characteristics:**

- 5m entry, 4h trend riding
- 3-5x leverage
- Holds 6-24 hours (1-2 funding payments)
- Balanced maker/taker usage
- Focus on funding rate trends

**Configuration:**

```json
{
  "strategy_id": "swing_perps",
  "strategy_name": "Swing Perps",
  "strategy_type": "swing",
  "prompt_template": "Swing trade {symbol} perps: use 5m for precision entry, 4h for trend direction. Hold 6-18 hours max. Monitor funding rate trend: {funding_rate}bps. Target 2.5:1 R:R. Use 3-5x leverage. Place limit orders at premium/discount to avoid taker fees. Calculate liquidation price before entry: must be >15% away. Exit if funding flips against position for 2 consecutive periods.",
  "risk_parameters": {
    "max_risk_per_trade": 1.5,
    "max_daily_loss": 5.0,
    "stop_loss_percentage": 2.5,
    "take_profit_ratio": 2.5,
    "max_leverage": 5.0,
    "cooldown_period": 300,
    "max_funding_rate_bps": 8.0
  },
  "timeframe_preference": ["5m", "15m", "4h"],
  "max_positions": 3,
  "position_sizing": "volatility_adjusted",
  "order_preference": "maker_preferred",
  "funding_rate_threshold": 0.08,
  "is_active": true
}
```

**Best For:**

- Medium-term trend following
- Positive funding rate harvesting
- Avoiding excessive leverage
- Balanced risk/reward

---

### 5. DCA Hedging Strategy

**Strategy ID:** `dca_hedge`

**Characteristics:**

- Systematic position building
- 15m intervals for DCA
- 1-2x leverage only
- Used for hedging or gradual exposure
- Strict limit orders

**Configuration:**

```json
{
  "strategy_id": "dca_hedge",
  "strategy_name": "Perps DCA Hedge",
  "strategy_type": "dca",
  "prompt_template": "Execute DCA for {symbol} perps: place limit orders every 15m at 0.5% increments. Use 1x leverage ONLY. Current funding {funding_rate}bps - avoid if >10bps. Hedge spot exposure or build gradual directional position. Max 5 entry orders, then take profit at +3% from average entry. No stop loss - manual intervention only. Maker orders essential.",
  "risk_parameters": {
    "max_risk_per_trade": 1.0,
    "max_daily_loss": 3.0,
    "stop_loss_percentage": 0,
    "take_profit_ratio": 3.0,
    "max_leverage": 1.0,
    "cooldown_period": 900,
    "max_funding_rate_bps": 10.0
  },
  "timeframe_preference": ["15m", "1h"],
  "max_positions": 1,
  "position_sizing": "fixed",
  "order_preference": "maker_only",
  "funding_rate_threshold": 0.10,
  "is_active": true
}
```

**Best For:**

- Hedging spot positions
- Gradual exposure building
- High funding rate avoidance
- Low-leverage accumulation

---

## DEX-Specific Configuration

### Fee Optimization Settings

The system automatically retrieves fee tiers from the account configuration (`maker_fee_bps` and `taker_fee_bps`). Strategies use this information to:

1. **Calculate Break-even**: Ensure expected profit exceeds trading costs.
2. **Select Order Type**: High-frequency strategies (Scalping) may prefer Maker orders to minimize fees (0.005% vs 0.04%).
3. **Adjust Position Sizing**: Account for entry/exit costs in risk calculations.

```json
"order_preference": "limit",  // Prefer limit orders to capture maker rebates/lower fees
"fee_structure": {
  "maker": 0.00005, // 0.005% (5 bps) - Configured in Account settings
  "taker": 0.0004   // 0.04% (20 bps) - Configured in Account settings
}
```

### Funding Rate Management

The `StrategyManager` monitors funding rates and can automatically switch strategies to adapt to the funding regime:

1. **High Positive Funding (> 0.05%)**: Longs pay shorts.
    - *Action*: Switch from trend-following Long strategies (Aggressive/Swing) to **Scalping** (reduce holding time) or **Neutral** strategies.
2. **High Negative Funding (< -0.05%)**: Shorts pay longs.
    - *Action*: Switch to **DCA** (accumulate Longs to capture funding) or **Neutral** strategies.

This logic is enforced by the `switch_by_funding_regime` method in the Strategy Manager.

---

## Custom Strategy Creation

### Perpetual-Specific Prompt Template

**Template Variables for Perps:**

- `{symbol}`: Perpetual pair (e.g., BTC-USD)
- `{funding_rate}`: Current funding rate (bps)
- `{open_interest}`: Open interest change (%)
- `{liquidation_clusters}`: Key liquidation levels
- `{leverage}`: Current position leverage

**Example Prompt:**

```
Trade {symbol} perps on 5m timeframe.

FUNDING & LIQUIDITY:
- Current funding: {funding_rate}bps
- Open interest change: {open_interest}%
- Avoid liquidation clusters: {liquidation_clusters}

ACCOUNT STATE:
- Available margin: {account_balance} USD
- Current exposure: {risk_exposure}%
- Max leverage: {leverage}x

EXECUTION RULES:
1. Use LIMIT orders only (save 0.035% vs taker)
2. Stop loss must be beyond liquidation cluster
3. Target 3:1 R:R minimum
4. Max hold: 8 hours (1 funding period)
5. If funding >10bps against position, exit early

OUTPUT: Entry, SL, TP, size (USD), order type (limit/market), confidence (1-100)
```

### Risk Parameters for Leveraged Trading

```json
{
  "risk_parameters": {
    "max_risk_per_trade": 1.0,        // % of account per trade
    "max_daily_loss": 3.0,            // % of account before halt
    "stop_loss_percentage": 2.0,      // Position stop loss
    "take_profit_ratio": 2.5,         // Min reward/risk
    "max_leverage": 10.0,             // Max allowed leverage
    "cooldown_period": 180,           // Seconds between trades
    "max_funding_rate_bps": 8.0,      // Block if funding too high
    "liquidation_buffer": 0.15        // Stop must be 15% from liq price
  }
}
```

---

## Strategy Management for Perps

### Automated Strategy Switching by Funding

```python
def switch_by_funding_regime(client, account_id):
    """
    Switch strategies based on funding rate environment
    """
    avg_funding = get_average_funding_rate(hours=24)

    if avg_funding > 15:  # High positive funding
        # Short funding rate arbitrage
        client.switch_strategy(account_id, "swing_perps",
                             "High funding regime - favor shorts")
    elif avg_funding < -15:  # High negative funding
        # Long funding rate arbitrage
        client.switch_strategy(account_id, "swing_perps",
                             "Negative funding regime - favor longs")
    else:
        # Normal regime
        client.switch_strategy(account_id, "aggressive_perps",
                             "Neutral funding - momentum trading")
```

### Perps Performance Monitoring

```python
def analyze_perps_performance(client, strategy_id):
    """
    Perps-specific metrics
    """
    perf = client.get_strategy_performance(strategy_id)

    # Add perps-specific calculations
    funding_costs = perf.get("total_funding_paid", 0)
    fees = perf.get("total_fees_paid", 0)
    net_pnl = perf["total_pnl"] - (fees + funding_costs)

    return {
        "gross_pnl": perf["total_pnl"],
        "net_pnl": net_pnl,
        "fee_efficiency": (perf["total_pnl"] - fees) / perf["total_pnl"],
        "funding_impact": funding_costs / perf["total_pnl"],
        "liquidations_avoided": perf.get("liquidations_avoided", 0),
        "avg_leverage_used": perf.get("avg_leverage", 0)
    }
```

---

## Best Practices for Perps DEX Trading

### 1. Fee Management

- **Always calculate fee impact**: On a 0.2% scalp, 0.04% taker fee = 20% of profit
- **Use post-only limit orders**: 0.005% maker fee saves 0.035% vs taker
- **Batch exits**: Close multiple positions in one order to save fees

### 2. Funding Rate Optimization

- **Avoid holding through funding** if rate >10bps against you
- **Fade extreme funding**: >25bps often mean-reverts
- **Track funding schedule**: 8-hour intervals, avoid entering 5min before

### 3. Liquidation Management

- **Set stops 15-20% from liquidation** price
- **Monitor margin ratio**: Keep >1500% when possible
- **Use isolated margin**: Prevent cross-position liquidation

### 4. Leverage Discipline

- **Start with 3x**: Test strategy before increasing
- **Scale leverage with conviction**: 10x+ only for high-confidence setups
- **Reduce leverage in drawdowns**: Protects from death spirals

### 5. DEX-Specific Considerations

- **Slippage**: Set max 20bps for market orders
- **Order book depth**: Check 2% depth before large orders
- **Gas costs**: Factor in L2 gas for order cancellations

---

## Troubleshooting Perps Issues

### High Funding Costs

**Symptom**: Eroding P&L despite good trades
**Solution**:

```python
def reduce_funding_exposure():
    # Add to strategy config
    "max_hold_time_hours": 6,
    "exit_before_funding": true,
    "funding_rate_threshold": 0.08
```

### Liquidation Near Misses

**Symptom**: Positions nearly liquidated
**Solution**:

- Increase `liquidation_buffer` to 0.20 (20%)
- Reduce `max_leverage` by 30%
- Enable `auto_deleverage` flag

### Fee Drag

**Symptom**: Fees >20% of gross P&L
**Solution**:

- Enforce `order_preference: "maker_only"`
- Increase `min_profit_target` to 0.5%
- Reduce trade frequency (increase `cooldown_period`)

---

## Advanced Perps Topics

### Funding Rate Arbitrage

```python
def funding_arbitrage_strategy(client, symbols):
    """
    Long on exchange with negative funding,
    Short on AsterDex if positive funding
    """
    opportunities = []
    for symbol in symbols:
        rate = get_funding_rate(symbol)
        if rate > 20:  # 0.20%
            # Short on AsterDex (receive funding)
            client.execute_perps_trade(
                symbol=symbol,
                side="short",
                leverage=5,
                reason=f"Funding arbitrage: +{rate}bps"
            )
```

### Open Interest Analysis

```json
{
  "oi_signal_weights": {
    "oi_increasing_price_increasing": 0.3,  // Bullish conviction
    "oi_decreasing_price_increasing": -0.5, // Weak hands leaving
    "oi_increasing_price_decreasing": -0.7, // Trapped longs
    "oi_decreasing_price_decreasing": 0.2   // Capitulation
  }
}
```

### Dynamic Leverage Based on Volatility

```python
def calculate_leverage(volatility_1h):
    """
    Reduce leverage in high vol environments
    """
    if volatility_1h > 5.0:  // >5% hourly range
        return 3.0
    elif volatility_1h > 3.0:
        return 5.0
    else:
        return 8.0
```

---

## Summary Checklist for Perps Strategies

✅ **Primary timeframe: 5m** for entries/exits
✅ **Long-term context: 4h** for trend bias
✅ **Fee optimization**: Prioritize 0.005% maker orders
✅ **Leverage caps**: 3x (conservative) to 15x (aggressive)
✅ **Funding awareness**: Block trades >10bps against position
✅ **Liquidation buffer**: Stop loss 15%+ from liq price
✅ **Hold time limits**: 30min (scalp) to 8hrs (swing)
✅ **Max positions**: 1-4 to avoid overexposure
✅ **Cooldown**: 30-600 seconds between trades
✅ **Daily loss limits**: 1.5-8% of account equity

Use this framework to deploy robust, fee-efficient strategies on AsterDex perpetual futures.
