"""
Trading decision schemas for LLM-generated decisions.

This module contains the CANONICAL schemas for the entire trading system. These schemas
are used by:
- LLMService: For generating structured trading decisions
- ContextBuilderService: For building trading context
- DecisionValidator: For validating trading decisions
- All API endpoints: For request/response validation

SCHEMA UNIFICATION (2025-11-02):
This module is the single source of truth for all trading-related schemas. Previously,
there were duplicate schemas in app.schemas.context which have been removed. All code
should import schemas from this module.

KEY SCHEMA CHANGES:
- TechnicalIndicators: Uses flat structure (ema_20, ema_50, macd, etc.) instead of nested
- RiskMetrics: Uses var_95, max_drawdown, correlation_risk, concentration_risk
- PerformanceMetrics: Simplified to total_pnl, win_rate, avg_win, avg_loss, max_drawdown, sharpe_ratio
- AccountContext: active_strategy is now required (not Optional)
- MarketContext: No longer has symbol field (symbol is in TradingContext)
- PositionSummary: Uses 'size' instead of 'quantity', 'percentage_pnl' instead of 'unrealized_pnl_percent'
- TradeHistory: Uses 'size' instead of 'quantity'

MIGRATION NOTES:
If you find code importing from app.schemas.context, update it to import from this module instead.
The old context.py file has been deleted and should not be used.
"""

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Any

from pydantic import BaseModel, Field


class PositionAdjustment(BaseModel):
    """Position adjustment details."""

    adjustment_type: Literal["increase", "decrease"] = Field(
        ..., description="Type of position adjustment"
    )
    adjustment_amount_usd: float = Field(
        ..., gt=0, description="Amount to adjust position by (in USD)"
    )
    adjustment_percentage: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage of current position to adjust"
    )
    new_tp_price: Optional[float] = Field(
        None, gt=0, description="New take-profit price after adjustment"
    )
    new_sl_price: Optional[float] = Field(
        None, gt=0, description="New stop-loss price after adjustment"
    )


class OrderAdjustment(BaseModel):
    """Order adjustment details for TP/SL modifications."""

    adjust_tp: bool = Field(default=False, description="Whether to adjust take-profit")
    adjust_sl: bool = Field(default=False, description="Whether to adjust stop-loss")
    new_tp_price: Optional[float] = Field(None, gt=0, description="New take-profit price")
    new_sl_price: Optional[float] = Field(None, gt=0, description="New stop-loss price")
    cancel_tp: bool = Field(default=False, description="Cancel existing take-profit order")
    cancel_sl: bool = Field(default=False, description="Cancel existing stop-loss order")


class AssetDecision(BaseModel):
    """Trading decision for a single asset."""

    asset: str = Field(..., description="Trading pair symbol")
    action: Literal["buy", "sell", "hold", "adjust_position", "close_position", "adjust_orders"] = (
        Field(..., description="Trading action")
    )
    allocation_usd: float = Field(..., ge=0, description="Allocation amount in USD")
    position_adjustment: Optional[PositionAdjustment] = Field(
        None, description="Position adjustment details (for adjust_position action)"
    )
    order_adjustment: Optional[OrderAdjustment] = Field(
        None, description="Order adjustment details (for adjust_orders action)"
    )
    tp_price: Optional[float] = Field(None, gt=0, description="Take-profit price")
    sl_price: Optional[float] = Field(None, gt=0, description="Stop-loss price")
    exit_plan: str = Field(..., description="Exit strategy description")
    rationale: str = Field(..., description="Decision reasoning")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score")
    risk_level: Literal["low", "medium", "high"] = Field(..., description="Risk assessment")

    def validate_action_requirements(self) -> List[str]:
        """Validate that required fields are present for specific actions."""
        errors = []

        if self.action == "adjust_position" and not self.position_adjustment:
            errors.append("position_adjustment is required for adjust_position action")

        if self.action == "adjust_orders" and not self.order_adjustment:
            errors.append("order_adjustment is required for adjust_orders action")

        if self.action in ["buy", "sell"] and self.allocation_usd <= 0:
            errors.append("allocation_usd must be greater than 0 for buy/sell actions")

        if self.action == "hold" and self.allocation_usd > 0:
            errors.append("allocation_usd should be 0 for hold action")

        return errors

    def validate_price_logic(self, current_price: float) -> List[str]:
        """Validate take-profit and stop-loss price logic."""
        errors = []

        if self.action == "buy":
            if self.tp_price and self.tp_price <= current_price:
                errors.append("Take-profit price must be higher than current price for buy orders")
            if self.sl_price and self.sl_price >= current_price:
                errors.append("Stop-loss price must be lower than current price for buy orders")

        elif self.action == "sell":
            if self.tp_price and self.tp_price >= current_price:
                errors.append("Take-profit price must be lower than current price for sell orders")
            if self.sl_price and self.sl_price <= current_price:
                errors.append("Stop-loss price must be higher than current price for sell orders")

        return errors


class TradingDecision(BaseModel):
    """Multi-asset structured trading decision from LLM for perpetual futures.

    This schema represents a portfolio-level trading decision that can include
    decisions for multiple assets simultaneously. The LLM analyzes all configured
    assets and provides a comprehensive trading strategy across the portfolio.
    """

    decisions: List[AssetDecision] = Field(..., description="Trading decisions for each asset")
    portfolio_rationale: str = Field(
        ..., description="Overall trading strategy and reasoning across assets"
    )
    total_allocation_usd: float = Field(..., ge=0, description="Total allocation across all assets")
    portfolio_risk_level: Literal["low", "medium", "high"] = Field(
        ..., description="Overall portfolio risk assessment"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def validate_portfolio_allocation(self) -> List[str]:
        """Validate that individual allocations sum to total allocation."""
        errors = []

        individual_sum = sum(decision.allocation_usd for decision in self.decisions)

        # Allow small floating point differences
        if abs(individual_sum - self.total_allocation_usd) > 0.01:
            errors.append(
                f"Individual allocations (${individual_sum:.2f}) do not match "
                f"total allocation (${self.total_allocation_usd:.2f})"
            )

        return errors

    def get_decision_for_asset(self, asset: str) -> Optional[AssetDecision]:
        """Get decision for a specific asset."""
        for decision in self.decisions:
            if decision.asset == asset:
                return decision
        return None

    def get_active_decisions(self) -> List[AssetDecision]:
        """Get all non-hold decisions."""
        return [d for d in self.decisions if d.action != "hold"]

    def validate_all_decisions(self, market_prices: Dict[str, float]) -> List[str]:
        """Validate all asset decisions against current market prices."""
        all_errors = []

        # Validate portfolio allocation
        all_errors.extend(self.validate_portfolio_allocation())

        # Validate each asset decision
        for decision in self.decisions:
            # Validate action requirements
            all_errors.extend(
                [f"{decision.asset}: {error}" for error in decision.validate_action_requirements()]
            )

            # Validate price logic if market price available
            if decision.asset in market_prices:
                all_errors.extend(
                    [
                        f"{decision.asset}: {error}"
                        for error in decision.validate_price_logic(market_prices[decision.asset])
                    ]
                )

        return all_errors


class TechnicalIndicatorsSet(BaseModel):
    """Set of technical indicators for a specific timeframe."""

    ema_20: Optional[List[float]] = Field(None, description="20-period EMA")
    ema_50: Optional[List[float]] = Field(None, description="50-period EMA")
    macd: Optional[List[float]] = Field(None, description="MACD value")
    macd_signal: Optional[List[float]] = Field(None, description="MACD signal line")
    rsi: Optional[List[float]] = Field(None, description="RSI values")
    bb_upper: Optional[List[float]] = Field(None, description="Bollinger Bands upper")
    bb_lower: Optional[List[float]] = Field(None, description="Bollinger Bands lower")
    bb_middle: Optional[List[float]] = Field(None, description="Bollinger Bands middle")
    atr: Optional[List[float]] = Field(None, description="Average True Range")


class TechnicalIndicators(BaseModel):
    """Technical indicators for market analysis.

    Contains two sets of indicators: one for the primary trading interval
    and one for a longer-term interval for trend analysis.
    """

    interval: TechnicalIndicatorsSet = Field(
        ..., description="Indicators for the primary trading interval"
    )
    long_interval: TechnicalIndicatorsSet = Field(
        ..., description="Indicators for the longer-term trend interval"
    )


class PricePoint(BaseModel):
    """Price point with timestamp."""

    timestamp: datetime
    price: float = Field(..., gt=0)
    volume: Optional[float] = Field(None, ge=0)


class AssetMarketData(BaseModel):
    """Market data for a single asset."""

    symbol: str = Field(..., description="Trading pair symbol")
    current_price: float = Field(..., gt=0)
    price_change_24h: float
    volume_24h: float = Field(..., ge=0)
    funding_rate: Optional[float] = None
    open_interest: Optional[float] = Field(None, ge=0)
    price_history: List[PricePoint] = Field(default_factory=list)
    volatility: float = Field(..., ge=0)
    technical_indicators: TechnicalIndicators

    def validate_data_freshness(self, max_age_minutes: int = 5) -> bool:
        """Validate that market data is fresh enough for trading decisions."""
        if not self.price_history:
            return False

        latest_data = max(self.price_history, key=lambda x: x.timestamp)
        # Handle both timezone-aware and timezone-naive datetimes
        now = datetime.now(timezone.utc)
        latest_timestamp = latest_data.timestamp
        if latest_timestamp.tzinfo is None:
            latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
        age_minutes = (now - latest_timestamp).total_seconds() / 60
        return age_minutes <= max_age_minutes

    def get_price_trend(self) -> str:
        """Determine price trend based on recent price history."""
        if len(self.price_history) < 2:
            return "insufficient_data"

        recent_prices = [
            p.price for p in sorted(self.price_history, key=lambda x: x.timestamp)[-5:]
        ]

        if len(recent_prices) < 2:
            return "insufficient_data"

        trend_score = sum(
            1 if recent_prices[i] > recent_prices[i - 1] else -1
            for i in range(1, len(recent_prices))
        )

        if trend_score > 0:
            return "bullish"
        elif trend_score < 0:
            return "bearish"
        else:
            return "sideways"

    def has_sufficient_indicators(self) -> bool:
        """Check if sufficient technical indicators are available."""
        indicators = self.technical_indicators.interval
        required_indicators = [
            indicators.ema_20,
            indicators.ema_50,
            indicators.rsi,
            indicators.macd,
        ]
        return sum(1 for ind in required_indicators if ind is not None) >= 3


class MarketContext(BaseModel):
    """Multi-asset market data context for perpetual futures trading decisions.

    Contains market data for all configured assets that the LLM will analyze
    to make portfolio-level trading decisions.
    """

    assets: Dict[str, AssetMarketData] = Field(..., description="Market data for each asset symbol")
    market_sentiment: Optional[str] = Field(
        None, description="Overall market sentiment (bullish/bearish/neutral)"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def get_asset_data(self, symbol: str) -> Optional[AssetMarketData]:
        """Get market data for a specific asset."""
        return self.assets.get(symbol)

    def validate_all_data_freshness(self, max_age_minutes: int = 5) -> Dict[str, bool]:
        """Validate data freshness for all assets."""
        return {
            symbol: data.validate_data_freshness(max_age_minutes)
            for symbol, data in self.assets.items()
        }

    def get_portfolio_trends(self) -> Dict[str, str]:
        """Get price trends for all assets."""
        return {symbol: data.get_price_trend() for symbol, data in self.assets.items()}

    def has_sufficient_data(self) -> bool:
        """Check if all assets have sufficient data."""
        return all(data.has_sufficient_indicators() for data in self.assets.values())


class PositionSummary(BaseModel):
    """Summary of an open position."""

    symbol: str
    side: Literal["long", "short"]
    size: float = Field(..., gt=0)
    entry_price: float = Field(..., gt=0)
    current_price: float = Field(..., gt=0)
    unrealized_pnl: float
    percentage_pnl: float


class PerformanceMetrics(BaseModel):
    """Performance metrics for account."""

    total_pnl: float
    win_rate: float = Field(..., ge=0, le=100)
    avg_win: float
    avg_loss: float
    max_drawdown: float
    sharpe_ratio: Optional[float] = None


class StrategyRiskParameters(BaseModel):
    """Risk management parameters for trading strategies."""

    max_risk_per_trade: float = Field(..., ge=0, le=100, description="Max risk per trade (%)")
    max_daily_loss: float = Field(..., ge=0, le=100, description="Max daily loss (%)")
    stop_loss_percentage: float = Field(..., ge=0, le=50, description="Default stop loss (%)")
    take_profit_ratio: float = Field(default=2.0, ge=1.0, description="Risk/reward ratio")
    max_leverage: float = Field(default=2.0, ge=1.0, le=20.0, description="Maximum leverage")
    cooldown_period: int = Field(default=300, ge=0, description="Cooldown between trades (seconds)")
    max_funding_rate_bps: float = Field(
        default=0.0, ge=0, description="Max funding rate (bps) before blocking trades"
    )
    liquidation_buffer: float = Field(
        default=0.0, ge=0, description="Buffer from liquidation price for stop loss (%)"
    )


class TradingStrategy(BaseModel):
    """Trading strategy configuration."""

    strategy_id: str = Field(..., description="Unique strategy identifier")
    strategy_name: str = Field(..., description="Human-readable strategy name")
    strategy_type: Literal[
        "conservative",
        "aggressive",
        "scalping",
        "swing",
        "dca",
        "custom",
        "conservative_perps",
        "aggressive_perps",
        "scalping_perps",
        "swing_perps",
        "dca_hedge",
    ] = Field(..., description="Strategy type classification")
    prompt_template: str = Field(..., description="LLM prompt template for this strategy")
    risk_parameters: StrategyRiskParameters = Field(..., description="Risk management parameters")
    timeframe_preference: List[str] = Field(
        default=["1h", "4h"], description="Preferred timeframes for analysis"
    )
    max_positions: int = Field(default=3, ge=1, description="Maximum concurrent positions")
    position_sizing: Literal["fixed", "percentage", "kelly", "volatility_adjusted"] = Field(
        default="percentage", description="Position sizing method"
    )
    order_preference: Literal["maker_only", "taker_accepted", "maker_preferred", "any"] = Field(
        default="any", description="Preference for order types to manage fees"
    )
    funding_rate_threshold: float = Field(
        default=0.0,
        ge=0,
        description="Funding rate threshold to consider before entering a trade (%)",
    )
    is_active: bool = Field(default=True, description="Whether strategy is active")

    def validate_strategy_constraints(self) -> List[str]:
        """Validate strategy configuration constraints."""
        errors = []

        # Validate timeframe preferences
        valid_timeframes = [
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "8h",
            "12h",
            "1d",
            "3d",
            "1w",
        ]
        for tf in self.timeframe_preference:
            if tf not in valid_timeframes:
                errors.append(f"Invalid timeframe: {tf}")

        # Validate risk parameters consistency
        if self.risk_parameters.max_risk_per_trade > self.risk_parameters.max_daily_loss:
            errors.append("max_risk_per_trade cannot exceed max_daily_loss")

        # Strategy-specific validations
        if self.strategy_type == "scalping" and not any(
            tf in ["1m", "5m", "15m"] for tf in self.timeframe_preference
        ):
            errors.append("Scalping strategy should include short timeframes (1m, 5m, 15m)")

        if self.strategy_type == "swing" and not any(
            tf in ["4h", "1d"] for tf in self.timeframe_preference
        ):
            errors.append("Swing strategy should include longer timeframes (4h, 1d)")

        return errors

    def get_default_prompt_template(self) -> str:
        """Get default prompt template based on strategy type."""
        templates = {
            "conservative": "Focus on capital preservation with low-risk entries. Prioritize strong support/resistance levels.",
            "aggressive": "Look for high-probability setups with strong momentum. Accept higher risk for greater returns.",
            "scalping": "Identify quick profit opportunities on short timeframes. Focus on tight spreads and quick exits.",
            "swing": "Analyze medium-term trends and key levels. Hold positions for days to weeks.",
            "dca": "Implement dollar-cost averaging strategy. Focus on accumulation during favorable conditions.",
        }
        return templates.get(
            self.strategy_type, "Analyze market conditions and provide trading recommendations."
        )


class AccountContext(BaseModel):
    """Account state context for decisions."""

    account_id: int
    balance_usd: float = Field(..., ge=0)
    available_balance: float = Field(..., ge=0)
    total_pnl: float
    open_positions: List[PositionSummary] = Field(default_factory=list)
    recent_performance: PerformanceMetrics
    risk_exposure: float = Field(..., ge=0, le=100)
    max_position_size: float = Field(..., gt=0)
    maker_fee_bps: float = Field(default=5.0, ge=0)
    taker_fee_bps: float = Field(default=20.0, ge=0)
    active_strategy: TradingStrategy

    def can_open_new_position(self, allocation_usd: float) -> bool:
        """Check if account can open a new position with given allocation."""
        # Check available balance
        if allocation_usd > self.available_balance:
            return False

        # Check position count limit
        if len(self.open_positions) >= self.active_strategy.max_positions:
            return False

        # Check position size limit
        if allocation_usd > self.max_position_size:
            return False

        return True

    def get_position_for_symbol(self, symbol: str) -> Optional[PositionSummary]:
        """Get existing position for a symbol."""
        for position in self.open_positions:
            if position.symbol == symbol:
                return position
        return None

    def calculate_total_exposure(self) -> float:
        """Calculate total exposure across all positions."""
        return sum(pos.size * pos.current_price for pos in self.open_positions)

    def is_within_risk_limits(self, additional_allocation: float = 0) -> bool:
        """Check if account is within risk limits."""
        total_exposure = self.calculate_total_exposure() + additional_allocation
        max_exposure = self.balance_usd * (
            self.active_strategy.risk_parameters.max_daily_loss / 100
        )
        return total_exposure <= max_exposure


class TradeHistory(BaseModel):
    """Historical trade information."""

    symbol: str
    side: Literal["buy", "sell"]
    size: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    timestamp: datetime
    pnl: Optional[float] = None


class RiskMetrics(BaseModel):
    """Risk metrics for decision context.

    CANONICAL FIELDS (as of 2025-11-02):
    - var_95: Value at Risk at 95% confidence level
    - max_drawdown: Maximum drawdown percentage
    - correlation_risk: Portfolio correlation risk (0-100%)
    - concentration_risk: Position concentration risk (0-100%)

    These are the only fields that should be used. Previous versions had different
    fields (current_exposure, available_capital, max_position_size, daily_pnl, daily_loss_limit)
    which have been removed during schema unification.
    """

    var_95: float = Field(..., description="Value at Risk (95%)")
    max_drawdown: float = Field(..., description="Maximum drawdown")
    correlation_risk: float = Field(..., ge=0, le=100, description="Portfolio correlation risk")
    concentration_risk: float = Field(..., ge=0, le=100, description="Position concentration risk")


class TradingContext(BaseModel):
    """Complete multi-asset context for trading decisions.

    CANONICAL SCHEMA (as of 2025-11-02, updated for multi-asset support):
    This is the single source of truth for trading context throughout the system.
    Used by:
    - ContextBuilderService: To build complete trading context
    - LLMService: To generate trading decisions
    - DecisionValidator: To validate decisions
    - All API endpoints: For request/response validation

    MULTI-ASSET SUPPORT:
    - symbols: List of asset symbols to analyze (e.g., ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    - market_data: Contains AssetMarketData for each symbol
    - recent_trades: Grouped by asset symbol for per-asset trade history
    """

    symbols: List[str] = Field(..., description="List of asset symbols to analyze")
    account_id: int
    timeframes: List[str] = Field(..., description="Timeframes used for analysis [primary, long]")
    market_data: MarketContext
    account_state: AccountContext
    recent_trades: Dict[str, List[TradeHistory]] = Field(
        default_factory=lambda: {}, description="Recent trades grouped by asset symbol"
    )
    risk_metrics: RiskMetrics
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    errors: List[str] = Field([], description="Errors encountered during context building")

    def validate_context_completeness(self) -> List[str]:
        """Validate that context has sufficient data for decision making."""
        errors = []

        # Check market data completeness for all assets
        if not self.market_data.has_sufficient_data():
            errors.append("Insufficient technical indicators for one or more assets")

        # Check data freshness for all assets
        freshness_results = self.market_data.validate_all_data_freshness()
        stale_assets = [symbol for symbol, is_fresh in freshness_results.items() if not is_fresh]
        if stale_assets:
            errors.append(f"Market data is too old for assets: {', '.join(stale_assets)}")

        # Check account state
        if self.account_state.available_balance <= 0:
            errors.append("No available balance for trading")

        if not self.account_state.active_strategy.is_active:
            errors.append("Account strategy is not active")

        return errors

    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of the trading context for logging."""
        # Get portfolio trends
        trends = self.market_data.get_portfolio_trends()

        # Calculate average price change across assets
        avg_price_change = (
            sum(asset_data.price_change_24h for asset_data in self.market_data.assets.values())
            / len(self.market_data.assets)
            if self.market_data.assets
            else 0.0
        )

        return {
            "symbols": self.symbols,
            "account_id": self.account_id,
            "num_assets": len(self.symbols),
            "avg_price_change_24h": avg_price_change,
            "portfolio_trends": trends,
            "available_balance": self.account_state.available_balance,
            "open_positions": len(self.account_state.open_positions),
            "strategy": self.account_state.active_strategy.strategy_name,
            "risk_exposure": self.account_state.risk_exposure,
            "market_sentiment": self.market_data.market_sentiment,
        }

    def is_ready_for_decision(self) -> bool:
        """Check if context is ready for making trading decisions."""
        return len(self.validate_context_completeness()) == 0

    def get_asset_context(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get context data for a specific asset."""
        asset_data = self.market_data.get_asset_data(symbol)
        if not asset_data:
            return None

        return {
            "symbol": symbol,
            "current_price": asset_data.current_price,
            "price_change_24h": asset_data.price_change_24h,
            "volume_24h": asset_data.volume_24h,
            "volatility": asset_data.volatility,
            "trend": asset_data.get_price_trend(),
            "recent_trades": self.recent_trades.get(symbol, []),
        }


class StrategyPerformance(BaseModel):
    """Strategy performance tracking model."""

    strategy_id: str
    total_trades: int = Field(..., ge=0)
    winning_trades: int = Field(..., ge=0)
    losing_trades: int = Field(..., ge=0)
    win_rate: float = Field(..., ge=0, le=100)
    total_pnl: float
    avg_win: float
    avg_loss: float
    max_win: float
    max_loss: float
    max_drawdown: float
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    profit_factor: float = Field(..., gt=0)
    avg_trade_duration_hours: float = Field(..., ge=0)
    total_volume_traded: float = Field(..., ge=0)
    total_fees_paid: float = Field(default=0.0, ge=0)
    total_funding_paid: float = Field(default=0.0)
    total_liquidations: int = Field(default=0, ge=0)
    start_date: datetime
    end_date: datetime
    period_days: int = Field(..., gt=0)

    def calculate_roi(self, initial_capital: float) -> float:
        """Calculate return on investment percentage."""
        if initial_capital <= 0:
            return 0.0
        return (self.total_pnl / initial_capital) * 100

    def get_performance_grade(self) -> str:
        """Get performance grade based on multiple metrics."""
        score = 0

        # Win rate scoring (0-25 points)
        if self.win_rate >= 70:
            score += 25
        elif self.win_rate >= 60:
            score += 20
        elif self.win_rate >= 50:
            score += 15
        elif self.win_rate >= 40:
            score += 10

        # Profit factor scoring (0-25 points)
        if self.profit_factor >= 2.0:
            score += 25
        elif self.profit_factor >= 1.5:
            score += 20
        elif self.profit_factor >= 1.2:
            score += 15
        elif self.profit_factor >= 1.0:
            score += 10

        # Sharpe ratio scoring (0-25 points)
        if self.sharpe_ratio and self.sharpe_ratio >= 2.0:
            score += 25
        elif self.sharpe_ratio and self.sharpe_ratio >= 1.5:
            score += 20
        elif self.sharpe_ratio and self.sharpe_ratio >= 1.0:
            score += 15
        elif self.sharpe_ratio and self.sharpe_ratio >= 0.5:
            score += 10

        # Total PnL scoring (0-25 points)
        if self.total_pnl > 0:
            score += 25
        elif self.total_pnl >= -100:
            score += 15
        elif self.total_pnl >= -500:
            score += 10

        # Grade assignment
        if score >= 85:
            return "A+"
        elif score >= 75:
            return "A"
        elif score >= 65:
            return "B+"
        elif score >= 55:
            return "B"
        elif score >= 45:
            return "C+"
        elif score >= 35:
            return "C"
        elif score >= 25:
            return "D"
        else:
            return "F"

    def needs_attention(self) -> bool:
        """Check if strategy performance needs attention."""
        # Check for concerning patterns
        if self.win_rate < 30:
            return True
        if self.profit_factor < 0.8:
            return True
        if self.max_drawdown < -1000:  # Significant drawdown
            return True
        if self.total_trades > 10 and self.total_pnl < -500:
            return True

        return False


class StrategyComparison(BaseModel):
    """Model for comparing multiple strategies."""

    strategies: List[StrategyPerformance]
    comparison_period_days: int = Field(..., gt=0)
    best_performing_strategy: str
    ranking_criteria: Literal["total_pnl", "win_rate", "sharpe_ratio", "profit_factor"] = Field(
        default="sharpe_ratio"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StrategyAssignment(BaseModel):
    """Model for tracking strategy assignments to accounts."""

    account_id: int
    strategy_id: str
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_by: Optional[str] = Field(None, description="User who assigned the strategy")
    is_active: bool = Field(default=True)
    previous_strategy_id: Optional[str] = Field(None, description="Previously assigned strategy")
    switch_reason: Optional[str] = Field(None, description="Reason for strategy switch")


class StrategyMetrics(BaseModel):
    """Real-time metrics for strategy performance tracking."""

    strategy_id: str
    account_id: int
    current_positions: int = Field(..., ge=0)
    total_allocated: float = Field(..., ge=0)
    unrealized_pnl: float
    realized_pnl_today: float
    trades_today: int = Field(..., ge=0)
    last_trade_time: Optional[datetime] = None
    risk_utilization: float = Field(..., ge=0, le=100, description="% of risk budget used")
    cooldown_remaining: int = Field(default=0, ge=0, description="Cooldown seconds remaining")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class StrategyAlert(BaseModel):
    """Alert model for strategy performance issues."""

    strategy_id: str
    account_id: int
    alert_type: Literal[
        "performance_degradation", "risk_limit_exceeded", "consecutive_losses", "drawdown_limit"
    ] = Field(..., description="Type of alert")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Alert severity"
    )
    message: str = Field(..., description="Alert message")
    threshold_value: Optional[float] = Field(None, description="Threshold that triggered the alert")
    current_value: Optional[float] = Field(
        None, description="Current value that exceeded threshold"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = Field(default=False)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


class ValidationResult(BaseModel):
    """Result of decision validation process."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validation_time_ms: float
    rules_checked: List[str] = Field(default_factory=list)


class RiskValidationResult(BaseModel):
    """Result of risk validation checks."""

    passed: bool
    risk_score: float = Field(..., ge=0, le=100)
    risk_factors: List[str] = Field(default_factory=list)
    max_position_exceeded: bool = Field(default=False)
    daily_loss_limit_exceeded: bool = Field(default=False)
    correlation_risk_high: bool = Field(default=False)
    leverage_exceeded: bool = Field(default=False)


class UsageMetrics(BaseModel):
    """LLM service usage metrics."""

    total_requests: int = Field(..., ge=0)
    successful_requests: int = Field(..., ge=0)
    failed_requests: int = Field(..., ge=0)
    avg_response_time_ms: float = Field(..., ge=0)
    total_cost_usd: float = Field(..., ge=0)
    cost_per_request: float = Field(..., ge=0)
    requests_per_hour: float = Field(..., ge=0)
    error_rate: float = Field(..., ge=0, le=100)
    uptime_percentage: float = Field(..., ge=0, le=100)
    period_start: datetime
    period_end: datetime


class HealthStatus(BaseModel):
    """Health status of LLM service."""

    is_healthy: bool
    response_time_ms: Optional[float] = None
    last_successful_request: Optional[datetime] = None
    consecutive_failures: int = Field(default=0, ge=0)
    circuit_breaker_open: bool = Field(default=False)
    available_models: List[str] = Field(default_factory=list)
    current_model: Optional[str] = None
    error_message: Optional[str] = None


class DecisionResult(BaseModel):
    """Result of decision generation process."""

    decision: TradingDecision
    context: TradingContext
    validation_passed: bool
    validation_errors: List[str] = Field(default_factory=list)
    processing_time_ms: float
    model_used: str
    api_cost: Optional[float] = None
