"""
Context Builder Service for LLM Decision Engine.

Aggregates market data, technical indicators, and account state to build
comprehensive context for trading decisions.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from statistics import stdev

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

# Removed unused import
from ...db.session import AsyncSessionLocal
from ...models.account import Account
from ...models.position import Position
from ...models.trade import Trade
from ...models.market_data import MarketData
from ...schemas.context import (
    TradingContext,
    MarketContext,
    AccountContext,
    PositionSummary,
    TradeHistory,
    PerformanceMetrics,
    RiskMetrics,
    PricePoint,
    ContextValidationResult,
)
from ...services.market_data.service import get_market_data_service
from ...services.technical_analysis.service import TechnicalAnalysisService
from ...services.technical_analysis.exceptions import InsufficientDataError as TAInsufficientDataError

logger = logging.getLogger(__name__)


class ContextBuilderError(Exception):
    """Base exception for context builder errors."""
    pass


class InsufficientMarketDataError(ContextBuilderError):
    """Raised when insufficient market data is available."""
    pass


class StaleDataError(ContextBuilderError):
    """Raised when data is too stale for reliable decisions."""
    pass


class ContextBuilderService:
    """Service for building comprehensive trading context."""

    # Configuration constants
    MAX_DATA_AGE_MINUTES = 15  # Maximum age for market data
    MIN_CANDLES_FOR_INDICATORS = 50  # Minimum candles for technical analysis
    DEFAULT_PRICE_HISTORY_LIMIT = 100  # Default number of price points
    RECENT_TRADES_LIMIT = 20  # Number of recent trades to include
    PERFORMANCE_LOOKBACK_DAYS = 30  # Days to look back for performance metrics

    def __init__(self):
        """Initialize the Context Builder Service."""
        self.market_data_service = get_market_data_service()
        self.technical_analysis_service = TechnicalAnalysisService()
        self._cache: Dict[str, Tuple[datetime, any]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes cache TTL

        logger.info("ContextBuilderService initialized")

    async def build_trading_context(
        self,
        symbol: str,
        account_id: int,
        timeframes: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> TradingContext:
        """
        Build complete trading context for decision making.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            account_id: Account ID
            timeframes: List of timeframes to analyze (defaults to ["1h", "4h"])
            force_refresh: Force refresh of cached data

        Returns:
            TradingContext object with all necessary data

        Raises:
            ContextBuilderError: If context building fails
            InsufficientMarketDataError: If insufficient market data
            StaleDataError: If data is too stale
        """
        if timeframes is None:
            timeframes = ["1h", "4h"]

        logger.info(f"Building trading context for {symbol}, account {account_id}")

        try:
            # Clean up expired cache entries
            self.cleanup_expired_cache()

            # Pre-validate data availability if not forcing refresh
            if not force_refresh:
                availability_check = await self.validate_context_data_availability(symbol, account_id)
                if not availability_check.is_valid:
                    # Try graceful degradation
                    degraded_context = self.handle_data_unavailability(symbol, account_id, availability_check)
                    if degraded_context:
                        logger.info(f"Using degraded context for {symbol}")
                        return degraded_context
                    else:
                        raise InsufficientMarketDataError(f"Data unavailable: {availability_check.missing_data}")

            # Build context components concurrently
            market_context_task = self.get_market_context(symbol, timeframes, force_refresh)
            account_context_task = self.get_account_context(account_id, force_refresh)
            recent_trades_task = self.get_recent_trades(account_id, symbol)

            market_context, account_context, recent_trades = await asyncio.gather(
                market_context_task,
                account_context_task,
                recent_trades_task,
                return_exceptions=True
            )

            # Check for exceptions
            if isinstance(market_context, Exception):
                raise market_context
            if isinstance(account_context, Exception):
                raise account_context
            if isinstance(recent_trades, Exception):
                logger.warning(f"Failed to get recent trades: {recent_trades}")
                recent_trades = []

            # Validate context
            validation_result = self._validate_context(market_context, account_context)
            if not validation_result.is_valid:
                logger.warning(f"Context validation warnings: {validation_result.warnings}")
                if validation_result.missing_data:
                    raise InsufficientMarketDataError(f"Missing data: {validation_result.missing_data}")
                if validation_result.stale_data:
                    raise StaleDataError(f"Stale data: {validation_result.stale_data}")

            context = TradingContext(
                symbol=symbol,
                account_id=account_id,
                market_data=market_context,
                account_state=account_context,
                recent_trades=recent_trades,
                timestamp=datetime.now(timezone.utc)
            )

            logger.info(f"Successfully built trading context for {symbol} (data age: {validation_result.data_age_seconds/60:.1f}min)")
            return context

        except Exception as e:
            logger.error(f"Failed to build trading context for {symbol}: {e}")
            raise ContextBuilderError(f"Context building failed: {str(e)}") from e

    async def get_market_context(
        self,
        symbol: str,
        timeframes: List[str],
        force_refresh: bool = False
    ) -> MarketContext:
        """
        Build market context with price data and technical indicators.

        Args:
            symbol: Trading pair symbol
            timeframes: List of timeframes to analyze
            force_refresh: Force refresh of cached data

        Returns:
            MarketContext object
        """
        cache_key = f"market_context_{symbol}_{'-'.join(timeframes)}"

        # Check cache first
        if not force_refresh and cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cached_time).total_seconds() < self._cache_ttl_seconds:
                logger.debug(f"Using cached market context for {symbol}")
                return cached_data

        logger.debug(f"Building market context for {symbol} with timeframes {timeframes}")

        async with AsyncSessionLocal() as db:
            # Get market data for primary timeframe (first in list)
            primary_timeframe = timeframes[0]
            market_data = await self.market_data_service.get_latest_market_data(
                db, symbol, primary_timeframe, self.DEFAULT_PRICE_HISTORY_LIMIT
            )

            if not market_data or len(market_data) < 10:
                raise InsufficientMarketDataError(f"Insufficient market data for {symbol}")

            # Sort by timestamp (oldest first for technical analysis)
            market_data.sort(key=lambda x: x.timestamp)

            # Get current price and calculate metrics
            latest_candle = market_data[-1]
            current_price = latest_candle.close

            # Calculate 24h price change
            price_24h_ago = market_data[-24].close if len(market_data) >= 24 else market_data[0].close
            price_change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100

            # Calculate volatility (standard deviation of returns)
            if len(market_data) >= 20:
                returns = []
                for i in range(1, min(21, len(market_data))):
                    prev_price = market_data[-i-1].close
                    curr_price = market_data[-i].close
                    returns.append((curr_price - prev_price) / prev_price)
                volatility = stdev(returns) * 100 if len(returns) > 1 else 0.0
            else:
                volatility = 0.0

            # Build price history
            price_history = [
                PricePoint(
                    timestamp=candle.timestamp,
                    price=candle.close,
                    volume=candle.volume
                )
                for candle in market_data[-50:]  # Last 50 points
            ]

            # Calculate technical indicators if we have enough data
            technical_indicators = None
            if len(market_data) >= self.MIN_CANDLES_FOR_INDICATORS:
                try:
                    technical_indicators = self.technical_analysis_service.calculate_all_indicators(market_data)
                    logger.debug(f"Calculated technical indicators for {symbol} with {len(market_data)} candles")
                except TAInsufficientDataError as e:
                    logger.warning(f"Insufficient data for technical indicators on {symbol}: {e}")
                    # Create partial indicators with available data
                    technical_indicators = self._create_partial_indicators(market_data)
                except Exception as e:
                    logger.error(f"Failed to calculate technical indicators for {symbol}: {e}")
                    # Graceful degradation - continue without indicators
                    technical_indicators = None
            else:
                logger.warning(f"Not enough candles for technical indicators on {symbol}: {len(market_data)} < {self.MIN_CANDLES_FOR_INDICATORS}")
                # Try to create basic indicators with available data
                technical_indicators = self._create_partial_indicators(market_data)

            # Get funding rate and open interest (mock data for now)
            # TODO: Implement actual funding rate and open interest fetching
            funding_rate = None
            open_interest = None

            # Calculate 24h volume
            volume_24h = sum(candle.volume for candle in market_data[-24:]) if len(market_data) >= 24 else latest_candle.volume

            market_context = MarketContext(
                symbol=symbol,
                current_price=current_price,
                price_change_24h=price_change_24h,
                volume_24h=volume_24h,
                funding_rate=funding_rate,
                open_interest=open_interest,
                price_history=price_history,
                volatility=volatility,
                technical_indicators=technical_indicators,
                data_freshness=latest_candle.timestamp
            )

            # Cache the result
            self._cache[cache_key] = (datetime.now(timezone.utc), market_context)

            return market_context

    async def get_account_context(
        self,
        account_id: int,
        force_refresh: bool = False
    ) -> AccountContext:
        """
        Build account context with balance, positions, and performance metrics.

        Args:
            account_id: Account ID
            force_refresh: Force refresh of cached data

        Returns:
            AccountContext object
        """
        cache_key = f"account_context_{account_id}"

        # Check cache first
        if not force_refresh and cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cached_time).total_seconds() < self._cache_ttl_seconds:
                logger.debug(f"Using cached account context for account {account_id}")
                return cached_data

        logger.debug(f"Building account context for account {account_id}")

        async with AsyncSessionLocal() as db:
            # Get account details
            account_result = await db.execute(select(Account).where(Account.id == account_id))
            account = account_result.scalar_one_or_none()

            if not account:
                raise ContextBuilderError(f"Account {account_id} not found")

            # Get open positions with enhanced position awareness
            positions_result = await db.execute(
                select(Position).where(
                    Position.account_id == account_id,
                    Position.status == "open"
                ).order_by(desc(Position.created_at))
            )
            positions = positions_result.scalars().all()

            # Convert positions to summaries with enhanced data
            position_summaries = []
            for pos in positions:
                # Calculate position age and performance
                position_age_hours = (datetime.now(timezone.utc) - pos.created_at).total_seconds() / 3600

                position_summary = PositionSummary(
                    symbol=pos.symbol,
                    side=pos.side,
                    entry_price=pos.entry_price,
                    current_price=pos.current_price,
                    quantity=pos.quantity,
                    leverage=pos.leverage,
                    unrealized_pnl=pos.unrealized_pnl,
                    unrealized_pnl_percent=pos.unrealized_pnl_percent,
                    stop_loss=pos.stop_loss,
                    take_profit=pos.take_profit
                )
                position_summaries.append(position_summary)

            # Calculate total unrealized PnL and position metrics
            total_pnl = sum(pos.unrealized_pnl for pos in positions)
            total_position_value = sum(pos.current_value for pos in positions)

            # Get recent performance metrics
            performance_metrics = await self._calculate_performance_metrics(db, account_id)

            # Calculate enhanced risk metrics with position awareness
            risk_metrics = await self._calculate_enhanced_risk_metrics(db, account, positions)

            # Calculate balance with position awareness
            balance_usd = await self._calculate_account_balance(db, account_id, positions)
            used_margin = sum(pos.entry_value / pos.leverage for pos in positions)
            available_balance = balance_usd - used_margin

            account_context = AccountContext(
                account_id=account_id,
                balance_usd=balance_usd,
                available_balance=max(0, available_balance),  # Ensure non-negative
                total_pnl=total_pnl,
                open_positions=position_summaries,
                recent_performance=performance_metrics,
                risk_exposure=risk_metrics.current_exposure,
                max_position_size=account.max_position_size_usd,
                active_strategy=None,  # TODO: implement strategy management
                risk_metrics=risk_metrics
            )

            # Cache the result
            self._cache[cache_key] = (datetime.now(timezone.utc), account_context)

            logger.debug(f"Built account context: balance=${balance_usd:.2f}, positions={len(positions)}, pnl=${total_pnl:.2f}")
            return account_context

    async def get_recent_trades(
        self,
        account_id: int,
        symbol: Optional[str] = None
    ) -> List[TradeHistory]:
        """
        Get recent trade history for the account.

        Args:
            account_id: Account ID
            symbol: Optional symbol filter

        Returns:
            List of recent trades
        """
        logger.debug(f"Getting recent trades for account {account_id}")

        async with AsyncSessionLocal() as db:
            query = select(Trade).where(Trade.account_id == account_id)

            if symbol:
                query = query.where(Trade.symbol == symbol)

            query = query.order_by(desc(Trade.created_at)).limit(self.RECENT_TRADES_LIMIT)

            result = await db.execute(query)
            trades = result.scalars().all()

            trade_history = [
                TradeHistory(
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    price=trade.price,
                    total_cost=trade.total_cost,
                    pnl=trade.pnl,
                    pnl_percent=trade.pnl_percent,
                    timestamp=trade.created_at
                )
                for trade in trades
            ]

            return trade_history

    async def _calculate_performance_metrics(
        self,
        db: AsyncSession,
        account_id: int
    ) -> PerformanceMetrics:
        """Calculate performance metrics for the account."""
        # Get trades from the last 30 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.PERFORMANCE_LOOKBACK_DAYS)

        result = await db.execute(
            select(Trade).where(
                Trade.account_id == account_id,
                Trade.created_at >= cutoff_date,
                Trade.pnl.isnot(None)
            )
        )
        trades = result.scalars().all()

        if not trades:
            return PerformanceMetrics(
                total_pnl=0.0,
                total_pnl_percent=0.0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                trades_count=0,
                winning_trades=0,
                losing_trades=0
            )

        # Calculate metrics
        total_pnl = sum(trade.pnl for trade in trades if trade.pnl)
        winning_trades = [trade for trade in trades if trade.pnl and trade.pnl > 0]
        losing_trades = [trade for trade in trades if trade.pnl and trade.pnl < 0]

        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        avg_win = sum(trade.pnl for trade in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(trade.pnl for trade in losing_trades) / len(losing_trades) if losing_trades else 0

        total_wins = sum(trade.pnl for trade in winning_trades) if winning_trades else 0
        total_losses = abs(sum(trade.pnl for trade in losing_trades)) if losing_trades else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Calculate max drawdown (simplified)
        running_pnl = 0
        peak = 0
        max_drawdown = 0
        for trade in trades:
            if trade.pnl:
                running_pnl += trade.pnl
                if running_pnl > peak:
                    peak = running_pnl
                drawdown = (peak - running_pnl) / peak * 100 if peak > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)

        # Mock total PnL percentage (TODO: calculate based on initial balance)
        total_pnl_percent = total_pnl / 10000.0 * 100  # Assuming 10k initial balance

        return PerformanceMetrics(
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            trades_count=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades)
        )

    async def _calculate_risk_metrics(
        self,
        db: AsyncSession,
        account: Account,
        positions: List[Position]
    ) -> RiskMetrics:
        """Calculate risk metrics for the account."""
        # Mock balance (TODO: implement actual balance fetching)
        balance = 10000.0

        # Calculate current exposure
        total_position_value = sum(pos.current_value for pos in positions)
        current_exposure = (total_position_value / balance) * 100 if balance > 0 else 0

        # Calculate available capital
        used_capital = sum(pos.entry_value for pos in positions)
        available_capital = balance - used_capital

        # Get today's PnL
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.sum(Trade.pnl)).where(
                Trade.account_id == account.id,
                Trade.created_at >= today_start,
                Trade.pnl.isnot(None)
            )
        )
        daily_pnl = result.scalar() or 0.0

        # Calculate daily loss limit (2% of balance by default)
        daily_loss_limit = balance * 0.02

        return RiskMetrics(
            current_exposure=current_exposure,
            available_capital=available_capital,
            max_position_size=account.max_position_size_usd,
            daily_pnl=daily_pnl,
            daily_loss_limit=daily_loss_limit,
            correlation_risk=0.0  # TODO: implement correlation calculation
        )

    async def _calculate_enhanced_risk_metrics(
        self,
        db: AsyncSession,
        account: Account,
        positions: List[Position]
    ) -> RiskMetrics:
        """Calculate enhanced risk metrics with position awareness."""
        # Mock balance (TODO: implement actual balance fetching)
        balance = 10000.0

        # Calculate current exposure with leverage consideration
        total_notional_value = sum(pos.current_value * pos.leverage for pos in positions)
        current_exposure = (total_notional_value / balance) * 100 if balance > 0 else 0

        # Calculate available capital considering margin requirements
        used_margin = sum(pos.entry_value / pos.leverage for pos in positions)
        available_capital = balance - used_margin

        # Get today's PnL with position-aware calculation
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.sum(Trade.pnl)).where(
                Trade.account_id == account.id,
                Trade.created_at >= today_start,
                Trade.pnl.isnot(None)
            )
        )
        realized_pnl = result.scalar() or 0.0

        # Add unrealized PnL from open positions
        unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
        daily_pnl = realized_pnl + unrealized_pnl

        # Calculate dynamic daily loss limit based on account risk settings
        daily_loss_limit = balance * account.risk_per_trade * 5  # 5x single trade risk as daily limit

        # Calculate correlation risk (simplified - based on symbol diversity)
        symbols = set(pos.symbol for pos in positions)
        correlation_risk = max(0, (len(positions) - len(symbols)) / len(positions) * 100) if positions else 0

        return RiskMetrics(
            current_exposure=min(current_exposure, 100.0),  # Cap at 100%
            available_capital=max(0, available_capital),
            max_position_size=account.max_position_size_usd,
            daily_pnl=daily_pnl,
            daily_loss_limit=daily_loss_limit,
            correlation_risk=correlation_risk
        )

    async def _calculate_account_balance(
        self,
        db: AsyncSession,
        account_id: int,
        positions: List[Position]
    ) -> float:
        """
        Calculate account balance with position awareness.

        Args:
            db: Database session
            account_id: Account ID
            positions: Current open positions

        Returns:
            Account balance in USD
        """
        # TODO: Implement actual balance fetching from exchange API
        # For now, use mock balance with position adjustments
        base_balance = 10000.0

        # Add unrealized PnL from positions
        unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)

        # Get realized PnL from closed trades
        result = await db.execute(
            select(func.sum(Trade.pnl)).where(
                Trade.account_id == account_id,
                Trade.pnl.isnot(None)
            )
        )
        realized_pnl = result.scalar() or 0.0

        # Calculate total balance
        total_balance = base_balance + realized_pnl + unrealized_pnl

        return max(0, total_balance)  # Ensure non-negative balance

    def _validate_context(
        self,
        market_context: MarketContext,
        account_context: AccountContext
    ) -> ContextValidationResult:
        """
        Validate the built context for completeness and freshness.

        Args:
            market_context: Market context to validate
            account_context: Account context to validate

        Returns:
            ContextValidationResult with validation details
        """
        missing_data = []
        stale_data = []
        warnings = []

        # Check market data freshness
        now = datetime.now(timezone.utc)
        data_age = (now - market_context.data_freshness).total_seconds()

        if data_age > self.MAX_DATA_AGE_MINUTES * 60:
            stale_data.append(f"Market data is {data_age/60:.1f} minutes old")

        # Check for missing technical indicators and validate their freshness
        if not market_context.technical_indicators:
            warnings.append("Technical indicators not available")
        else:
            # Validate indicator freshness and completeness
            indicator_warnings = self._validate_indicator_freshness(
                market_context.technical_indicators,
                market_context.data_freshness
            )
            warnings.extend(indicator_warnings)

        # Check for missing funding rate and open interest
        if market_context.funding_rate is None:
            warnings.append("Funding rate not available")
        if market_context.open_interest is None:
            warnings.append("Open interest not available")

        # Check account data
        if account_context.available_balance <= 0:
            warnings.append("No available balance for trading")

        is_valid = len(missing_data) == 0 and len(stale_data) == 0

        return ContextValidationResult(
            is_valid=is_valid,
            missing_data=missing_data,
            stale_data=stale_data,
            warnings=warnings,
            data_age_seconds=data_age
        )

    def _create_partial_indicators(self, market_data: List[MarketData]) -> Optional[any]:
        """
        Create partial technical indicators with available data.

        Args:
            market_data: Available market data

        Returns:
            Partial TechnicalIndicators object or None
        """
        try:
            from ...services.technical_analysis.schemas import (
                TechnicalIndicators, EMAOutput, MACDOutput, RSIOutput,
                BollingerBandsOutput, ATROutput
            )

            # Only create indicators if we have at least 20 candles
            if len(market_data) < 20:
                return None

            # Create basic indicators with reduced requirements
            close_prices = [candle.close for candle in market_data]

            # Simple moving average as EMA approximation
            if len(close_prices) >= 12:
                sma_12 = sum(close_prices[-12:]) / 12
                ema = EMAOutput(ema=sma_12, period=12)
            else:
                ema = EMAOutput(ema=None, period=12)

            # Basic RSI calculation if we have enough data
            if len(close_prices) >= 14:
                gains = []
                losses = []
                for i in range(1, min(15, len(close_prices))):
                    change = close_prices[i] - close_prices[i-1]
                    if change > 0:
                        gains.append(change)
                        losses.append(0)
                    else:
                        gains.append(0)
                        losses.append(abs(change))

                avg_gain = sum(gains) / len(gains) if gains else 0
                avg_loss = sum(losses) / len(losses) if losses else 1
                rs = avg_gain / avg_loss if avg_loss > 0 else 0
                rsi_value = 100 - (100 / (1 + rs)) if rs > 0 else 50
                rsi = RSIOutput(rsi=rsi_value, period=14)
            else:
                rsi = RSIOutput(rsi=None, period=14)

            # Create empty/null indicators for others
            macd = MACDOutput(macd=None, signal=None, histogram=None)
            bollinger_bands = BollingerBandsOutput(
                upper=None, middle=None, lower=None, period=20, std_dev=2.0
            )
            atr = ATROutput(atr=None, period=14)

            return TechnicalIndicators(
                ema=ema,
                macd=macd,
                rsi=rsi,
                bollinger_bands=bollinger_bands,
                atr=atr,
                candle_count=len(market_data)
            )

        except Exception as e:
            logger.error(f"Failed to create partial indicators: {e}")
            return None

    def _validate_indicator_freshness(self, technical_indicators: any, data_timestamp: datetime) -> List[str]:
        """
        Validate freshness of technical indicators.

        Args:
            technical_indicators: Technical indicators object
            data_timestamp: Timestamp of the underlying data

        Returns:
            List of validation warnings
        """
        warnings = []

        if not technical_indicators:
            warnings.append("No technical indicators available")
            return warnings

        # Check if indicators have actual values
        if hasattr(technical_indicators, 'ema') and technical_indicators.ema.ema is None:
            warnings.append("EMA indicator not available")

        if hasattr(technical_indicators, 'rsi') and technical_indicators.rsi.rsi is None:
            warnings.append("RSI indicator not available")

        if hasattr(technical_indicators, 'macd'):
            if (technical_indicators.macd.macd is None or
                technical_indicators.macd.signal is None):
                warnings.append("MACD indicator incomplete")

        if hasattr(technical_indicators, 'bollinger_bands'):
            if (technical_indicators.bollinger_bands.upper is None or
                technical_indicators.bollinger_bands.lower is None):
                warnings.append("Bollinger Bands indicator incomplete")

        if hasattr(technical_indicators, 'atr') and technical_indicators.atr.atr is None:
            warnings.append("ATR indicator not available")

        # Check data age for indicator reliability
        now = datetime.now(timezone.utc)
        data_age_minutes = (now - data_timestamp).total_seconds() / 60

        if data_age_minutes > 30:
            warnings.append(f"Technical indicators based on data {data_age_minutes:.1f} minutes old")

        return warnings

    def validate_data_freshness(
        self,
        data_timestamp: datetime,
        max_age_minutes: Optional[int] = None
    ) -> Tuple[bool, float]:
        """
        Validate data freshness.

        Args:
            data_timestamp: Timestamp of the data
            max_age_minutes: Maximum allowed age in minutes (uses default if None)

        Returns:
            Tuple of (is_fresh, age_in_minutes)
        """
        if max_age_minutes is None:
            max_age_minutes = self.MAX_DATA_AGE_MINUTES

        now = datetime.now(timezone.utc)
        age_seconds = (now - data_timestamp).total_seconds()
        age_minutes = age_seconds / 60

        is_fresh = age_minutes <= max_age_minutes

        return is_fresh, age_minutes

    def invalidate_cache_for_account(self, account_id: int):
        """
        Invalidate cache entries for a specific account.

        Args:
            account_id: Account ID to invalidate cache for
        """
        pattern = f"account_context_{account_id}"
        self.clear_cache(pattern)
        logger.info(f"Invalidated cache for account {account_id}")

    def invalidate_cache_for_symbol(self, symbol: str):
        """
        Invalidate cache entries for a specific symbol.

        Args:
            symbol: Symbol to invalidate cache for
        """
        pattern = f"market_context_{symbol}"
        self.clear_cache(pattern)
        logger.info(f"Invalidated cache for symbol {symbol}")

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        now = datetime.now(timezone.utc)
        total_entries = len(self._cache)
        expired_entries = 0

        for cached_time, _ in self._cache.values():
            if (now - cached_time).total_seconds() > self._cache_ttl_seconds:
                expired_entries += 1

        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "active_entries": total_entries - expired_entries,
            "cache_ttl_seconds": self._cache_ttl_seconds,
            "max_data_age_minutes": self.MAX_DATA_AGE_MINUTES
        }

    def cleanup_expired_cache(self):
        """Clean up expired cache entries."""
        now = datetime.now(timezone.utc)
        expired_keys = []

        for key, (cached_time, _) in self._cache.items():
            if (now - cached_time).total_seconds() > self._cache_ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

    async def validate_context_data_availability(
        self,
        symbol: str,
        account_id: int
    ) -> ContextValidationResult:
        """
        Validate data availability before building context.

        Args:
            symbol: Trading pair symbol
            account_id: Account ID

        Returns:
            ContextValidationResult with availability status
        """
        missing_data = []
        warnings = []

        try:
            async with AsyncSessionLocal() as db:
                # Check if account exists
                account_result = await db.execute(select(Account).where(Account.id == account_id))
                account = account_result.scalar_one_or_none()

                if not account:
                    missing_data.append(f"Account {account_id} not found")

                # Check market data availability
                market_data = await self.market_data_service.get_latest_market_data(
                    db, symbol, "1h", 10
                )

                if not market_data:
                    missing_data.append(f"No market data available for {symbol}")
                elif len(market_data) < 10:
                    warnings.append(f"Limited market data for {symbol}: {len(market_data)} candles")

                # Check data freshness
                if market_data:
                    latest_candle = max(market_data, key=lambda x: x.timestamp)
                    is_fresh, age_minutes = self.validate_data_freshness(latest_candle.timestamp)

                    if not is_fresh:
                        warnings.append(f"Market data for {symbol} is {age_minutes:.1f} minutes old")

                is_valid = len(missing_data) == 0
                data_age_seconds = age_minutes * 60 if market_data else 0

                return ContextValidationResult(
                    is_valid=is_valid,
                    missing_data=missing_data,
                    stale_data=[],
                    warnings=warnings,
                    data_age_seconds=data_age_seconds
                )

        except Exception as e:
            logger.error(f"Failed to validate data availability: {e}")
            return ContextValidationResult(
                is_valid=False,
                missing_data=[f"Data validation failed: {str(e)}"],
                stale_data=[],
                warnings=[],
                data_age_seconds=0
            )

    def handle_data_unavailability(
        self,
        symbol: str,
        account_id: int,
        validation_result: ContextValidationResult
    ) -> Optional[TradingContext]:
        """
        Handle data unavailability with graceful degradation.

        Args:
            symbol: Trading pair symbol
            account_id: Account ID
            validation_result: Validation result with issues

        Returns:
            Degraded TradingContext or None if critical data missing
        """
        if not validation_result.is_valid:
            logger.warning(f"Cannot create context for {symbol}: {validation_result.missing_data}")
            return None

        # If we have warnings but data is valid, we can create a degraded context
        if validation_result.warnings:
            logger.warning(f"Creating degraded context for {symbol}: {validation_result.warnings}")

            # Create minimal context with available data
            # This would be implemented based on specific degradation strategies
            # For now, return None to indicate degradation is not implemented
            return None

        return None

    def clear_cache(self, pattern: Optional[str] = None):
        """
        Clear cached data.

        Args:
            pattern: Optional pattern to match cache keys (clears all if None)
        """
        if pattern is None:
            self._cache.clear()
            logger.info("Cleared all context cache")
        else:
            keys_to_remove = [key for key in self._cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"Cleared {len(keys_to_remove)} cache entries matching '{pattern}'")


# Global service instance
_context_builder_service: Optional[ContextBuilderService] = None


def get_context_builder_service() -> ContextBuilderService:
    """Get or create the context builder service instance."""
    global _context_builder_service
    if _context_builder_service is None:
        _context_builder_service = ContextBuilderService()
    return _context_builder_service