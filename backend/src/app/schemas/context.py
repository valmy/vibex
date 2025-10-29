"""
Context schemas for LLM decision engine.

Defines data structures for market context, account context, and trading context.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from .trading_decision import TradingStrategy, StrategyRiskParameters
from ..services.technical_analysis.schemas import TechnicalIndicators


class PricePoint(BaseModel):
    """Price point with timestamp."""

    timestamp: datetime
    price: float
    volume: float


class MarketContext(BaseModel):
    """Market data context for trading decisions."""

    symbol: str = Field(..., description="Trading pair symbol")
    current_price: float = Field(..., gt=0, description="Current market price")
    price_change_24h: float = Field(..., description="24h price change percentage")
    volume_24h: float = Field(..., ge=0, description="24h trading volume")
    funding_rate: Optional[float] = Field(None, description="Current funding rate")
    open_interest: Optional[float] = Field(None, ge=0, description="Open interest")
    price_history: List[PricePoint] = Field(default_factory=list, description="Recent price history")
    volatility: float = Field(..., ge=0, description="Price volatility")
    technical_indicators: Optional[TechnicalIndicators] = Field(None, description="Technical analysis indicators")
    data_freshness: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Data timestamp")


class PositionSummary(BaseModel):
    """Summary of an open position."""

    symbol: str
    side: str  # long or short
    entry_price: float
    current_price: float
    quantity: float
    leverage: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class TradeHistory(BaseModel):
    """Recent trade history."""

    symbol: str
    side: str  # buy or sell
    quantity: float
    price: float
    total_cost: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    timestamp: datetime


class PerformanceMetrics(BaseModel):
    """Account performance metrics."""

    total_pnl: float
    total_pnl_percent: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: float
    trades_count: int
    winning_trades: int
    losing_trades: int


class RiskMetrics(BaseModel):
    """Risk assessment metrics."""

    current_exposure: float = Field(..., description="Current risk exposure as percentage of balance")
    available_capital: float = Field(..., description="Available capital for new positions")
    max_position_size: float = Field(..., description="Maximum allowed position size")
    daily_pnl: float = Field(..., description="Today's PnL")
    daily_loss_limit: float = Field(..., description="Daily loss limit")
    correlation_risk: float = Field(default=0.0, description="Portfolio correlation risk")


class AccountContext(BaseModel):
    """Account state context for trading decisions."""

    account_id: int
    balance_usd: float = Field(..., ge=0, description="Account balance in USD")
    available_balance: float = Field(..., ge=0, description="Available balance for trading")
    total_pnl: float = Field(..., description="Total unrealized PnL")
    open_positions: List[PositionSummary] = Field(default_factory=list, description="Open positions")
    recent_performance: PerformanceMetrics = Field(..., description="Recent performance metrics")
    risk_exposure: float = Field(..., ge=0, le=100, description="Current risk exposure percentage")
    max_position_size: float = Field(..., gt=0, description="Maximum position size in USD")
    active_strategy: Optional[TradingStrategy] = Field(None, description="Currently active trading strategy")
    risk_metrics: RiskMetrics = Field(..., description="Risk assessment metrics")


class TradingContext(BaseModel):
    """Complete context for trading decisions."""

    symbol: str
    account_id: int
    market_data: MarketContext
    account_state: AccountContext
    recent_trades: List[TradeHistory] = Field(default_factory=list, description="Recent trade history")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Context timestamp")


class ContextValidationResult(BaseModel):
    """Result of context validation."""

    is_valid: bool
    missing_data: List[str] = Field(default_factory=list)
    stale_data: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    data_age_seconds: float = Field(..., description="Age of the oldest data in seconds")