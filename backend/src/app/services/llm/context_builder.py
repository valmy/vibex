"""
Context Builder Service for LLM Decision Engine.

Aggregates market data, technical indicators, and account state to build
comprehensive context for trading decisions.

SCHEMA UNIFICATION (2025-11-02):
This service now uses the CANONICAL schemas from app.schemas.trading_decision:
- TradingContext: Complete trading context
- MarketContext: Market data and technical indicators
- AccountContext: Account state and positions
- TechnicalIndicators: Flat structure (ema_20, ema_50, macd, etc.)
- RiskMetrics: var_95, max_drawdown, correlation_risk, concentration_risk
- PerformanceMetrics: total_pnl, win_rate, avg_win, avg_loss, max_drawdown, sharpe_ratio

Previously, this service used schemas from app.schemas.context which has been deleted.
All code should now import schemas from app.schemas.trading_decision.

KEY METHODS:
- build_trading_context(): Build complete trading context for decision making
- get_market_context(): Get market data and technical indicators
- get_account_context(): Get account state and positions
- validate_context_data_availability(): Validate data freshness and availability
- clear_cache(): Clear cached context data
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from statistics import stdev
from typing import Dict, List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.account import Account
from ...models.market_data import MarketData
from ...models.position import Position
from ...models.trade import Trade
from ...schemas.trading_decision import (
    AccountContext,
    MarketContext,
    PerformanceMetrics,
    PositionSummary,
    PricePoint,
    RiskMetrics,
    TechnicalIndicators,
    TechnicalIndicatorsSet,
    TradeHistory,
    TradingContext,
    TradingStrategy,
)
from ...services.market_data.service import get_market_data_service
from ...services.technical_analysis.exceptions import (
    InsufficientDataError as TAInsufficientDataError,
)
from ...services.technical_analysis.schemas import TechnicalIndicators as TATechnicalIndicators
from ...services.technical_analysis.service import TechnicalAnalysisService

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

    def __init__(self, db_session: AsyncSession = None):
        """Initialize the Context Builder Service.

        Args:
            db_session: Optional database session. If not provided, will use AsyncSessionLocal.
        """
        self.market_data_service = get_market_data_service()
        self.technical_analysis_service = TechnicalAnalysisService()
        self._cache: Dict[str, Tuple[datetime, any]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes cache TTL
        self._db_session = db_session

        logger.info("ContextBuilderService initialized")

    def cleanup_expired_cache(self):
        """Remove expired entries from the cache."""
        now = datetime.now(timezone.utc)
        expired_keys = []
        for key, (timestamp, _) in self._cache.items():
            if (now - timestamp).total_seconds() > self._cache_ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries.")

    def validate_data_freshness(
        self, timestamp: datetime, max_age_minutes: int = None
    ) -> Tuple[bool, float]:
        """Validate that data is fresh enough for trading decisions.

        Args:
            timestamp: Timestamp of the data
            max_age_minutes: Maximum age in minutes (uses MAX_DATA_AGE_MINUTES if not provided)

        Returns:
            Tuple of (is_fresh: bool, age_minutes: float)
        """
        if max_age_minutes is None:
            max_age_minutes = self.MAX_DATA_AGE_MINUTES

        # Handle both timezone-aware and timezone-naive datetimes
        now = datetime.now(timezone.utc)
        check_timestamp = timestamp
        if check_timestamp.tzinfo is None:
            check_timestamp = check_timestamp.replace(tzinfo=timezone.utc)

        age_minutes = (now - check_timestamp).total_seconds() / 60
        is_fresh = age_minutes <= max_age_minutes

        return is_fresh, age_minutes

    def _convert_technical_indicators(
        self, indicators: TATechnicalIndicators
    ) -> TechnicalIndicatorsSet:
        """Convert TA indicators to a TechnicalIndicatorsSet with the last 10 data points."""

        def get_last_10(
            series: Optional[List[Optional[float]]],
        ) -> Optional[List[float]]:
            """Safely get the last 10 non-null values from a series."""
            if not series:
                return None

            # Filter out None values and get the last 10
            non_null_series = [v for v in series if v is not None]
            return non_null_series[-10:]

        return TechnicalIndicatorsSet(
            ema_20=get_last_10(indicators.ema.ema),
            ema_50=get_last_10(indicators.ema_50.ema if indicators.ema_50 else None),
            macd=get_last_10(indicators.macd.macd),
            macd_signal=get_last_10(indicators.macd.signal),
            rsi=get_last_10(indicators.rsi.rsi),
            bb_upper=get_last_10(indicators.bollinger_bands.upper),
            bb_middle=get_last_10(indicators.bollinger_bands.middle),
            bb_lower=get_last_10(indicators.bollinger_bands.lower),
            atr=get_last_10(indicators.atr.atr),
        )

    def _calculate_risk_metrics(
        self, account_context: AccountContext, market_context: MarketContext
    ) -> RiskMetrics:
        """Calculate risk metrics for trading context.

        Args:
            account_context: Account context with positions and performance
            market_context: Market context with price and volatility data

        Returns:
            RiskMetrics with calculated values
        """
        # Calculate total exposure from open positions
        total_exposure = sum(pos.size * pos.current_price for pos in account_context.open_positions)

        # Calculate Value at Risk (95%) - simplified calculation
        # VaR = Position Value * Volatility * Z-score (1.65 for 95%)
        var_95 = total_exposure * market_context.volatility * 1.65 if total_exposure > 0 else 0.0

        # Get max drawdown from performance metrics
        max_drawdown = abs(account_context.recent_performance.max_drawdown)

        # Calculate correlation risk (simplified - based on number of positions in same direction)
        correlation_risk = 0.0
        if len(account_context.open_positions) > 1:
            long_positions = sum(1 for pos in account_context.open_positions if pos.side == "long")
            short_positions = len(account_context.open_positions) - long_positions
            # Higher correlation risk if all positions are in the same direction
            correlation_risk = (
                max(long_positions, short_positions) / len(account_context.open_positions) * 100
            )

        # Calculate concentration risk (largest position as % of total)
        concentration_risk = 0.0
        if account_context.open_positions and total_exposure > 0:
            largest_position = max(
                pos.size * pos.current_price for pos in account_context.open_positions
            )
            concentration_risk = (largest_position / total_exposure) * 100

        return RiskMetrics(
            var_95=var_95,
            max_drawdown=max_drawdown,
            correlation_risk=correlation_risk,
            concentration_risk=concentration_risk,
        )

    def _validate_context(
        self, market_context: MarketContext, account_context: AccountContext
    ) -> dict:
        """Validate the built context for completeness and freshness.

        Args:
            market_context: Market context to validate
            account_context: Account context to validate

        Returns:
            Dict with validation status (is_valid, missing_data, stale_data, warnings, data_age_seconds)
        """
        missing_data = []
        stale_data = []
        warnings = []

        # Check market context
        if market_context is None:
            missing_data.append("Market context is None")
        else:
            if market_context.current_price <= 0:
                missing_data.append("Invalid current price")
            if market_context.technical_indicators is None:
                warnings.append("No technical indicators available")

            # Check data freshness using the market context's method
            if not market_context.validate_data_freshness(
                max_age_minutes=self.MAX_DATA_AGE_MINUTES
            ):
                # Calculate age from price history
                if market_context.price_history:
                    latest_data = max(market_context.price_history, key=lambda x: x.timestamp)
                    # Handle both timezone-aware and timezone-naive datetimes
                    latest_timestamp = latest_data.timestamp
                    if latest_timestamp.tzinfo is None:
                        latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
                    data_age = (datetime.now(timezone.utc) - latest_timestamp).total_seconds()
                    stale_data.append(f"Market data is {data_age / 60:.1f} minutes old")

        # Check account context
        if account_context is None:
            missing_data.append("Account context is None")
        else:
            if account_context.balance_usd < 0:
                missing_data.append("Invalid account balance")
            if account_context.available_balance < 0:
                missing_data.append("Invalid available balance")

        # Calculate data age
        data_age_seconds = 0.0
        if market_context and market_context.price_history:
            latest_data = max(market_context.price_history, key=lambda x: x.timestamp)
            # Handle both timezone-aware and timezone-naive datetimes
            latest_timestamp = latest_data.timestamp
            if latest_timestamp.tzinfo is None:
                latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
            data_age_seconds = (datetime.now(timezone.utc) - latest_timestamp).total_seconds()

        is_valid = len(missing_data) == 0 and len(stale_data) == 0

        return {
            "is_valid": is_valid,
            "missing_data": missing_data,
            "stale_data": stale_data,
            "warnings": warnings,
            "data_age_seconds": data_age_seconds,
        }

    async def build_trading_context(
        self,
        symbol: str,
        account_id: int,
        timeframes: List[str],
        force_refresh: bool = False,
    ) -> TradingContext:
        """Build complete trading context for decision making.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            account_id: Account ID
            timeframes: List of two timeframes to analyze (e.g., ["5m", "1h"])
            force_refresh: Force refresh of cached data

        Returns:
            TradingContext object with all necessary data

        Raises:
            ContextBuilderError: If context building fails
            InsufficientMarketDataError: If insufficient market data
            StaleDataError: If data is too stale
        """
        if len(timeframes) != 2:
            raise ValueError("build_trading_context requires exactly two timeframes.")

        logger.info(
            f"Building trading context for {symbol}, account {account_id} with timeframes {timeframes}"
        )

        try:
            # Clean up expired cache entries
            self.cleanup_expired_cache()

            # Pre-validate data availability if not forcing refresh
            if not force_refresh:
                availability_check = await self.validate_context_data_availability(
                    symbol, account_id
                )
                # availability_check is now a dict instead of ContextValidationResult object
                if not availability_check["is_valid"]:
                    # Try graceful degradation
                    degraded_context = self.handle_data_unavailability(
                        symbol, account_id, availability_check
                    )
                    if degraded_context:
                        logger.info(f"Using degraded context for {symbol}")
                        return degraded_context
                    else:
                        raise InsufficientMarketDataError(
                            f"Data unavailable: {availability_check['missing_data']}"
                        )

            # Build context components concurrently
            market_context_task = self.get_market_context(symbol, timeframes, force_refresh)
            account_context_task = self.get_account_context(account_id, force_refresh)
            recent_trades_task = self.get_recent_trades(account_id, symbol)

            market_context, account_context, recent_trades = await asyncio.gather(
                market_context_task,
                account_context_task,
                recent_trades_task,
                return_exceptions=True,
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
            if not validation_result["is_valid"]:
                logger.warning(f"Context validation warnings: {validation_result['warnings']}")
                if validation_result["missing_data"]:
                    raise InsufficientMarketDataError(
                        f"Missing data: {validation_result['missing_data']}"
                    )
                if validation_result["stale_data"]:
                    raise StaleDataError(f"Stale data: {validation_result['stale_data']}")

            # Calculate risk metrics
            risk_metrics = self._calculate_risk_metrics(account_context, market_context)

            context = TradingContext(
                symbol=symbol,
                account_id=account_id,
                market_data=market_context,
                account_state=account_context,
                recent_trades=recent_trades,
                risk_metrics=risk_metrics,
                timestamp=datetime.now(timezone.utc),
            )

            logger.info(
                f"Successfully built trading context for {symbol} (data age: {validation_result['data_age_seconds'] / 60:.1f}min)"
            )
            return context

        except Exception as e:
            logger.error(f"Failed to build trading context for {symbol}: {e}")
            raise ContextBuilderError(f"Context building failed: {str(e)}") from e

    async def get_market_context(
        self,
        symbol: str,
        timeframes: List[str],
        force_refresh: bool = False,
        db_session: AsyncSession = None,
    ) -> MarketContext:
        """Build market context with price data and technical indicators for multiple timeframes."""
        if len(timeframes) != 2:
            raise ValueError("get_market_context expects exactly two timeframes.")

        cache_key = f"market_context_{symbol}_{'-'.join(timeframes)}"
        if not force_refresh and cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cached_time).total_seconds() < self._cache_ttl_seconds:
                logger.debug(f"Using cached market context for {symbol}")
                return cached_data

        db = db_session or self._db_session
        if db is None:
            raise ContextBuilderError("No database session provided.")

        # Primary timeframe (for price, volume, etc.) is the shorter one
        primary_timeframe, long_timeframe = timeframes

        async def _get_indicator_set(timeframe: str) -> TechnicalIndicatorsSet:
            market_data = await self.market_data_service.get_latest_market_data(
                db, symbol, timeframe, self.DEFAULT_PRICE_HISTORY_LIMIT
            )
            if not market_data or len(market_data) < self.MIN_CANDLES_FOR_INDICATORS:
                logger.warning(
                    f"Insufficient data for TA on {symbol} ({timeframe}): {len(market_data) if market_data else 0} candles"
                )
                return self._create_partial_indicators(market_data or [])
            try:
                market_data.sort(key=lambda x: x.time)
                ta_indicators = self.technical_analysis_service.calculate_all_indicators(market_data)
                return self._convert_technical_indicators(ta_indicators)
            except TAInsufficientDataError as e:
                logger.warning(f"TA InsufficientDataError for {symbol} ({timeframe}): {e}")
                return self._create_partial_indicators(market_data)
            except Exception as e:
                logger.error(f"Failed to calculate indicators for {symbol} ({timeframe}): {e}")
                return TechnicalIndicatorsSet()

        # Fetch indicators for both timeframes concurrently
        interval_indicators, long_interval_indicators = await asyncio.gather(
            _get_indicator_set(primary_timeframe),
            _get_indicator_set(long_timeframe),
        )

        technical_indicators = TechnicalIndicators(
            interval=interval_indicators,
            long_interval=long_interval_indicators,
        )

        # Get primary market data for main context fields
        primary_market_data = await self.market_data_service.get_latest_market_data(
            db, symbol, primary_timeframe, self.DEFAULT_PRICE_HISTORY_LIMIT
        )
        if not primary_market_data or len(primary_market_data) < 10:
            raise InsufficientMarketDataError(f"Insufficient primary market data for {symbol}")

        primary_market_data.sort(key=lambda x: x.time)
        latest_candle = primary_market_data[-1]
        current_price = latest_candle.close
        price_24h_ago = (
            primary_market_data[-24].close if len(primary_market_data) >= 24 else primary_market_data[0].close
        )
        price_change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
        volume_24h = (
            sum(c.volume for c in primary_market_data[-24:]) if len(primary_market_data) >= 24 else latest_candle.volume
        )

        # Calculate volatility
        volatility = 0.0
        if len(primary_market_data) >= 20:
            returns = [
                (primary_market_data[-i].close - primary_market_data[-i-1].close) / primary_market_data[-i-1].close
                for i in range(1, min(21, len(primary_market_data)))
            ]
            if len(returns) > 1:
                volatility = stdev(returns) * 100

        price_history = [
            PricePoint(timestamp=c.time, price=c.close, volume=c.volume) for c in primary_market_data[-50:]
        ]

        funding_rate = next(
            (
                float(c.funding_rate)
                for c in reversed(primary_market_data)
                if hasattr(c, "funding_rate") and c.funding_rate is not None
            ),
            None,
        )

        market_context = MarketContext(
            current_price=current_price,
            price_change_24h=price_change_24h,
            volume_24h=volume_24h,
            funding_rate=funding_rate,
            open_interest=None, # TODO
            price_history=price_history,
            volatility=volatility,
            technical_indicators=technical_indicators,
        )

        self._cache[cache_key] = (datetime.now(timezone.utc), market_context)
        return market_context

    async def get_account_context(
        self, account_id: int, force_refresh: bool = False, db_session: AsyncSession = None
    ) -> AccountContext:
        """
        Build account context with balance, positions, and performance metrics.

        Args:
            account_id: Account ID
            force_refresh: Force refresh of cached data
            db_session: Optional database session to use

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

        db = db_session or self._db_session
        if db is None:
            raise ContextBuilderError("No database session provided.")
        should_close = False

        try:
            # Get account details
            account_result = await db.execute(select(Account).where(Account.id == account_id))
            account = account_result.scalar_one_or_none()

            if not account:
                raise ContextBuilderError(f"Account {account_id} not found")

            # Get open positions
            positions_result = await db.execute(
                select(Position)
                .where(Position.account_id == account_id, Position.status == "open")
                .order_by(desc(Position.created_at))
            )
            positions = positions_result.scalars().all()

            # Convert positions to summaries (new schema uses 'size' instead of 'quantity')
            position_summaries = []
            for pos in positions:
                position_summary = PositionSummary(
                    symbol=pos.symbol,
                    side=pos.side,
                    size=pos.quantity,  # Map quantity to size
                    entry_price=pos.entry_price,
                    current_price=pos.current_price,
                    unrealized_pnl=pos.unrealized_pnl,
                    percentage_pnl=pos.unrealized_pnl_percent,  # Map unrealized_pnl_percent to percentage_pnl
                )
                position_summaries.append(position_summary)

            # Calculate total unrealized PnL
            total_pnl = sum(pos.unrealized_pnl for pos in positions)

            # Get recent performance metrics
            performance_metrics = await self._calculate_performance_metrics(db, account_id)

            # Calculate balance
            balance_usd = float(account.balance_usd)
            used_margin = sum(pos.entry_value / pos.leverage for pos in positions)
            available_balance = balance_usd - used_margin

            # Calculate risk exposure as percentage
            total_exposure = sum(pos.entry_value for pos in positions)
            risk_exposure = (total_exposure / balance_usd * 100) if balance_usd > 0 else 0.0

            # Get or create default trading strategy
            active_strategy = self._get_default_strategy()

            account_context = AccountContext(
                account_id=account_id,
                balance_usd=balance_usd,
                available_balance=max(0, available_balance),  # Ensure non-negative
                total_pnl=total_pnl,
                open_positions=position_summaries,
                recent_performance=performance_metrics,
                risk_exposure=min(100.0, risk_exposure),  # Cap at 100%
                max_position_size=account.max_position_size_usd,
                active_strategy=active_strategy,
            )

            # Cache the result
            self._cache[cache_key] = (datetime.now(timezone.utc), account_context)

            logger.debug(
                f"Built account context: balance=${balance_usd:.2f}, positions={len(positions)}, pnl=${total_pnl:.2f}"
            )
            return account_context

        finally:
            if should_close:
                await db.close()

    def _get_default_strategy(self) -> TradingStrategy:
        """Get default trading strategy.

        Returns:
            Default TradingStrategy object
        """
        from ...schemas.trading_decision import StrategyRiskParameters

        return TradingStrategy(
            strategy_id="default",
            strategy_name="Default Strategy",
            strategy_type="conservative",
            prompt_template="Analyze market conditions and provide conservative trading recommendations.",
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=2.0,
                max_daily_loss=5.0,
                stop_loss_percentage=2.0,
                take_profit_ratio=2.0,
                max_leverage=2.0,
                cooldown_period=300,
            ),
            timeframe_preference=["5m", "1h"],
            max_positions=3,
            position_sizing="percentage",
            is_active=True,
        )

    async def get_recent_trades(
        self, account_id: int, symbol: Optional[str] = None, db_session: AsyncSession = None
    ) -> List[TradeHistory]:
        """
        Get recent trade history for the account.

        Args:
            account_id: Account ID
            symbol: Optional symbol filter
            db_session: Optional database session to use

        Returns:
           List of TradeHistory objects
        """
        db = db_session or self._db_session
        if db is None:
            raise ContextBuilderError("No database session provided.")
        should_close = False

        try:
            # Build the base query
            query = select(Trade).where(Trade.account_id == account_id)

            # Add symbol filter if provided
            if symbol:
                query = query.where(Trade.symbol == symbol)

            # Order by most recent first and limit results
            query = query.order_by(desc(Trade.created_at)).limit(self.RECENT_TRADES_LIMIT)

            # Execute the query
            result = await db.execute(query)
            trades = result.scalars().all()

            # Convert to TradeHistory objects (new schema uses 'size' instead of 'quantity')
            trade_history = [
                TradeHistory(
                    symbol=trade.symbol,
                    side=trade.side,
                    size=trade.quantity,  # Map quantity to size
                    price=trade.price,
                    timestamp=trade.created_at,
                    pnl=trade.pnl,
                )
                for trade in trades
            ]

            return trade_history
        finally:
            if should_close:
                await db.close()

    async def _calculate_performance_metrics(
        self, db: AsyncSession, account_id: int
    ) -> PerformanceMetrics:
        """Calculate performance metrics for the account."""
        # Get trades from the last 30 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.PERFORMANCE_LOOKBACK_DAYS)

        result = await db.execute(
            select(Trade).where(
                Trade.account_id == account_id,
                Trade.created_at >= cutoff_date,
                Trade.pnl.isnot(None),
            )
        )
        trades = result.scalars().all()

        if not trades:
            return PerformanceMetrics(
                total_pnl=0.0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                max_drawdown=0.0,
                sharpe_ratio=None,
            )

        # Calculate metrics
        total_pnl = sum(trade.pnl for trade in trades if trade.pnl)
        winning_trades = [trade for trade in trades if trade.pnl and trade.pnl > 0]
        losing_trades = [trade for trade in trades if trade.pnl and trade.pnl < 0]

        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        avg_win = (
            sum(trade.pnl for trade in winning_trades) / len(winning_trades)
            if winning_trades
            else 0
        )
        avg_loss = (
            sum(trade.pnl for trade in losing_trades) / len(losing_trades) if losing_trades else 0
        )

        # Calculate max drawdown (simplified)
        running_pnl = 0
        peak = 0
        max_drawdown = 0
        for trade in trades:
            if trade.pnl:
                running_pnl += trade.pnl
                if running_pnl > peak:
                    peak = running_pnl
                drawdown = peak - running_pnl
                max_drawdown = min(max_drawdown, -drawdown)  # Negative value

        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = None
        if len(trades) > 1:
            returns = [trade.pnl for trade in trades if trade.pnl]
            if returns:
                avg_return = sum(returns) / len(returns)
                std_return = stdev(returns) if len(returns) > 1 else 0
                sharpe_ratio = (avg_return / std_return) if std_return > 0 else None

        return PerformanceMetrics(
            total_pnl=total_pnl,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
        )

    def _create_partial_indicators(
        self, market_data: List[MarketData]
    ) -> TechnicalIndicatorsSet:
        """Create partial technical indicators with available data, returning a set."""
        try:
            if len(market_data) < 20:
                return TechnicalIndicatorsSet()

            close_prices = [candle.close for candle in market_data]

            # Calculate SMA as a fallback for EMA
            ema_20 = None
            if len(close_prices) >= 20:
                ema_20 = [sum(close_prices[i-20:i]) / 20 for i in range(20, len(close_prices) + 1)]
                ema_20 = ema_20[-10:] # Last 10 points

            rsi = None
            if len(close_prices) >= 15:
                # Simplified RSI calculation for the last 10 points
                rsi_values = []
                for i in range(len(close_prices) - 14, len(close_prices)):
                    period_prices = close_prices[i-14:i+1]
                    gains = sum(c2 - c1 for c1, c2 in zip(period_prices, period_prices[1:]) if c2 > c1)
                    losses = sum(abs(c2 - c1) for c1, c2 in zip(period_prices, period_prices[1:]) if c2 < c1)
                    avg_gain = gains / 14
                    avg_loss = losses / 14 if losses > 0 else 1
                    rs = avg_gain / avg_loss if avg_loss > 0 else 0
                    rsi_val = 100 - (100 / (1 + rs))
                    rsi_values.append(rsi_val)
                rsi = rsi_values[-10:]

            return TechnicalIndicatorsSet(
                ema_20=ema_20,
                rsi=rsi,
            )
        except Exception as e:
            logger.error(f"Failed to create partial indicators: {e}")
            return TechnicalIndicatorsSet()

    async def validate_context_data_availability(self, symbol: str, account_id: int) -> dict:
        """
        Validate data availability before building context.

        Args:
            symbol: Trading pair symbol
            account_id: Account ID

        Returns:
            Dict with availability status (is_valid, missing_data, stale_data, warnings, data_age_seconds)
        """
        missing_data = []
        warnings = []
        db = self._db_session

        if db is None:
            return {
                "is_valid": False,
                "missing_data": ["Database session not available"],
                "stale_data": [],
                "warnings": [],
                "data_age_seconds": 0,
            }

        try:
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
            data_age_seconds = 0
            if market_data:
                latest_candle = max(market_data, key=lambda x: x.timestamp)
                is_fresh, age_minutes = self.validate_data_freshness(latest_candle.timestamp)
                data_age_seconds = age_minutes * 60

                if not is_fresh:
                    warnings.append(f"Market data for {symbol} is {age_minutes:.1f} minutes old")

            is_valid = len(missing_data) == 0

            return {
                "is_valid": is_valid,
                "missing_data": missing_data,
                "stale_data": [],
                "warnings": warnings,
                "data_age_seconds": data_age_seconds,
            }

        except Exception as e:
            logger.error(f"Failed to validate data availability: {e}")
            return {
                "is_valid": False,
                "missing_data": [f"Data validation failed: {str(e)}"],
                "stale_data": [],
                "warnings": [],
                "data_age_seconds": 0,
            }

    def handle_data_unavailability(
        self, symbol: str, account_id: int, validation_result: dict
    ) -> Optional[TradingContext]:
        """
        Handle data unavailability with graceful degradation.

        Args:
            symbol: Trading pair symbol
            account_id: Account ID
            validation_result: Validation result dict with issues

        Returns:
            Degraded TradingContext or None if critical data missing
        """
        if not validation_result["is_valid"]:
            logger.warning(
                f"Cannot create context for {symbol}: {validation_result['missing_data']}"
            )
            return None

        # If we have warnings but data is valid, we can create a degraded context
        if validation_result["warnings"]:
            logger.warning(
                f"Creating degraded context for {symbol}: {validation_result['warnings']}"
            )

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


def get_context_builder_service(
    db_session: Optional[AsyncSession] = None,
) -> "ContextBuilderService":
    """Get or create the context builder service instance.

    Args:
        db_session: Optional database session. If not provided, the service will create its own.
    """
    global _context_builder_service
    if _context_builder_service is None:
        _context_builder_service = ContextBuilderService(db_session=db_session)
    elif db_session is not None and _context_builder_service._db_session is None:
        # Update the existing instance with the new session if needed
        _context_builder_service._db_session = db_session
    return _context_builder_service
