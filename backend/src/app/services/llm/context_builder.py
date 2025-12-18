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
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...models.account import Account
from ...models.market_data import MarketData
from ...models.position import Position
from ...models.trade import Trade
from ...schemas.trading_decision import (
    AccountContext,
    AssetMarketData,
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
from ...services.llm.strategy_manager import StrategyManager
from ...services.market_data.service import get_market_data_service
from ...services.technical_analysis.exceptions import (
    InsufficientDataError as TAInsufficientDataError,
)
from ...services.technical_analysis.schemas import TATechnicalIndicators
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

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        """Initialize the Context Builder Service.

        Args:
            session_factory: Optional database session factory.
        """
        self.market_data_service = get_market_data_service()
        self.technical_analysis_service = TechnicalAnalysisService()
        self._cache: Dict[str, Tuple[datetime, Any]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes cache TTL
        self._session_factory = session_factory
        self.strategy_manager = StrategyManager(session_factory=session_factory)

        logger.info("ContextBuilderService initialized")

    def cleanup_expired_cache(self) -> None:
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
            ema_20=get_last_10(indicators.ema_20),
            ema_50=get_last_10(indicators.ema_50),
            macd=get_last_10(indicators.macd),
            macd_signal=get_last_10(indicators.macd_signal),
            rsi=get_last_10(indicators.rsi),
            bb_upper=get_last_10(indicators.bb_upper),
            bb_middle=get_last_10(indicators.bb_middle),
            bb_lower=get_last_10(indicators.bb_lower),
            atr=get_last_10(indicators.atr),
        )

    def _calculate_market_sentiment(self, assets: Dict[str, AssetMarketData]) -> str:
        """Calculate overall market sentiment based on asset price changes.

        Args:
            assets: Dictionary of asset market data

        Returns:
            Market sentiment string: "bullish", "bearish", or "neutral"
        """
        if not assets:
            return "neutral"

        # Calculate average price change
        avg_price_change = sum(asset_data.price_change_24h for asset_data in assets.values()) / len(
            assets
        )

        # Count bullish vs bearish assets
        bullish_count = sum(1 for asset_data in assets.values() if asset_data.price_change_24h > 0)
        bearish_count = len(assets) - bullish_count

        # Determine sentiment
        if avg_price_change > 2.0 and bullish_count > bearish_count:
            return "bullish"
        elif avg_price_change < -2.0 and bearish_count > bullish_count:
            return "bearish"
        else:
            return "neutral"

    def _calculate_portfolio_risk_metrics(
        self, account_context: AccountContext, market_context: MarketContext
    ) -> RiskMetrics:
        """Calculate portfolio-wide risk metrics for multi-asset trading context.

        Args:
            account_context: Account context with positions and performance
            market_context: Multi-asset market context with price and volatility data

        Returns:
            RiskMetrics with calculated values across all assets
        """
        # Calculate total exposure from open positions
        total_exposure = sum(pos.size * pos.current_price for pos in account_context.open_positions)

        # Calculate portfolio-weighted volatility
        portfolio_volatility = 0.0
        if market_context.assets and total_exposure > 0:
            # Weight volatility by position size
            weighted_volatility = 0.0
            for pos in account_context.open_positions:
                asset_data = market_context.assets.get(pos.symbol)
                if asset_data:
                    position_value = pos.size * pos.current_price
                    weight = position_value / total_exposure
                    weighted_volatility += asset_data.volatility * weight
            portfolio_volatility = weighted_volatility
        elif market_context.assets:
            # If no positions, use average volatility
            portfolio_volatility = sum(
                asset_data.volatility for asset_data in market_context.assets.values()
            ) / len(market_context.assets)

        # Calculate Value at Risk (95%) - simplified calculation
        # VaR = Position Value * Volatility * Z-score (1.65 for 95%)
        var_95 = total_exposure * portfolio_volatility * 1.65 if total_exposure > 0 else 0.0

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

        # Calculate concentration risk across assets
        concentration_risk = 0.0
        if account_context.open_positions and total_exposure > 0:
            # Group positions by asset
            asset_exposures: Dict[str, float] = {}
            for pos in account_context.open_positions:
                position_value = pos.size * pos.current_price
                asset_exposures[pos.symbol] = asset_exposures.get(pos.symbol, 0) + position_value

            # Find largest asset exposure
            if asset_exposures:
                largest_asset_exposure = max(asset_exposures.values())
                concentration_risk = (largest_asset_exposure / total_exposure) * 100

        return RiskMetrics(
            var_95=var_95,
            max_drawdown=max_drawdown,
            correlation_risk=correlation_risk,
            concentration_risk=concentration_risk,
        )

    async def build_trading_context(
        self,
        symbols: List[str],
        account_id: int,
        timeframes: List[str],
        force_refresh: bool = False,
    ) -> TradingContext:
        """Build complete multi-asset trading context for decision making.

        Args:
            symbols: List of trading pair symbols (e.g., ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            account_id: Account ID
            timeframes: List of two timeframes to analyze (e.g., ["5m", "1h"])
            force_refresh: Force refresh of cached data

        Returns:
            TradingContext object with all necessary data for all assets

        Raises:
            ContextBuilderError: If context building fails
            InsufficientMarketDataError: If insufficient market data
            StaleDataError: If data is too stale
        """
        if len(timeframes) != 2:
            raise ValueError("build_trading_context requires exactly two timeframes.")

        logger.info(
            f"Building multi-asset trading context for {symbols}, account {account_id} with timeframes {timeframes}"
        )

        self.cleanup_expired_cache()
        all_errors: List[str] = []

        market_context_task = self.get_market_context(symbols, timeframes, force_refresh)
        account_context_task = self.get_account_context(account_id, force_refresh)
        recent_trades_tasks = [self.get_recent_trades(account_id, symbol) for symbol in symbols]

        results = await asyncio.gather(
            market_context_task,
            account_context_task,
            *recent_trades_tasks,
            return_exceptions=True,
        )

        market_context, account_context, recent_trades_by_symbol = self._process_context_results(
            results, symbols, all_errors
        )

        self._validate_full_context(market_context, account_context)

        risk_metrics = self._calculate_portfolio_risk_metrics(account_context, market_context)

        successful_symbols = list(market_context.assets.keys())
        context = TradingContext(
            symbols=successful_symbols,
            account_id=account_id,
            timeframes=timeframes,
            market_data=market_context,
            account_state=account_context,
            recent_trades=recent_trades_by_symbol,
            risk_metrics=risk_metrics,
            timestamp=datetime.now(timezone.utc),
            errors=all_errors,
        )

        logger.info(
            f"Successfully built multi-asset trading context for {len(successful_symbols)} assets"
        )
        return context

    def _process_context_results(
        self, results: List[Any], symbols: List[str], all_errors: List[str]
    ) -> Tuple[MarketContext, AccountContext, Dict[str, List[TradeHistory]]]:
        market_context_result, account_context, *recent_trades_results = results

        if isinstance(market_context_result, Exception):
            raise market_context_result
        market_context, market_errors = market_context_result
        all_errors.extend(market_errors)

        if isinstance(account_context, Exception):
            raise account_context

        recent_trades_by_symbol: Dict[str, List[TradeHistory]] = {}
        for i, symbol in enumerate(symbols):
            if isinstance(recent_trades_results[i], Exception):
                logger.warning(
                    f"Failed to get recent trades for {symbol}: {recent_trades_results[i]}"
                )
                recent_trades_by_symbol[symbol] = []
            else:
                recent_trades_by_symbol[symbol] = recent_trades_results[i]

        return market_context, account_context, recent_trades_by_symbol

    def _validate_full_context(
        self, market_context: MarketContext, account_context: AccountContext
    ) -> None:
        """Validate that we have sufficient context data."""
        if not market_context.assets:
            raise InsufficientMarketDataError("No market data available for any assets")

        if account_context.balance_usd <= 0:
            raise ContextBuilderError("Invalid account balance")

        if account_context.available_balance < 0:
            raise ContextBuilderError("Invalid available balance")

    async def get_market_context(
        self,
        symbols: List[str],
        timeframes: List[str],
        force_refresh: bool = False,
    ) -> Tuple[MarketContext, List[str]]:
        """Build multi-asset market context with price data and technical indicators for multiple timeframes.

        Handles partial failures by returning a context with successful assets and a list of errors.

        Args:
            symbols: List of trading pair symbols
            timeframes: List of two timeframes to analyze
            force_refresh: Force refresh of cached data

        Returns:
            Tuple of (MarketContext with successful assets, list of error messages for failed assets)
        """
        if len(timeframes) != 2:
            raise ValueError("get_market_context expects exactly two timeframes.")

        if self._session_factory is None:
            raise ContextBuilderError("No database session factory provided.")

        # Primary timeframe (for price, volume, etc.) is the shorter one
        primary_timeframe, long_timeframe = timeframes

        async def _get_asset_market_data(symbol: str) -> AssetMarketData:
            cache_key = f"market_context_{symbol}_{'-'.join(timeframes)}"
            if not force_refresh and (cached_data := self._get_cached_data(cache_key)):
                return cached_data

            if self._session_factory is None:
                raise ContextBuilderError("No database session factory provided.")
            async with self._session_factory() as db:
                interval_indicators, long_interval_indicators = await self._fetch_indicators(
                    symbol, primary_timeframe, long_timeframe, db
                )
                technical_indicators = TechnicalIndicators(
                    interval=interval_indicators, long_interval=long_interval_indicators
                )
                primary_market_data = await self._fetch_primary_market_data(
                    symbol, primary_timeframe, db
                )

                asset_market_data = self._build_asset_market_data(
                    symbol, primary_market_data, technical_indicators
                )
                self._cache[cache_key] = (datetime.now(timezone.utc), asset_market_data)
                return asset_market_data

        asset_data_results = await asyncio.gather(
            *[_get_asset_market_data(symbol) for symbol in symbols], return_exceptions=True
        )
        assets, errors = self._process_asset_data_results(asset_data_results, symbols)
        market_sentiment = self._calculate_market_sentiment(assets)

        market_context = MarketContext(
            assets=assets,
            market_sentiment=market_sentiment,
            timestamp=datetime.now(timezone.utc),
        )
        if not assets:
            raise InsufficientMarketDataError(
                f"Failed to get market data for all symbols: {symbols}. Errors: {errors}"
            )
        if errors:
            logger.warning(f"Partial market data failure. Errors: {errors}")

        return market_context, errors

    def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cached_time).total_seconds() < self._cache_ttl_seconds:
                logger.debug(f"Using cached market context for {cache_key}")
                return cached_data
        return None

    async def _fetch_indicators(
        self, symbol: str, primary_timeframe: str, long_timeframe: str, db: AsyncSession
    ) -> Tuple[TechnicalIndicatorsSet, TechnicalIndicatorsSet]:
        interval_indicators = await self._get_indicator_set(symbol, primary_timeframe, db)
        long_interval_indicators = await self._get_indicator_set(symbol, long_timeframe, db)
        return interval_indicators, long_interval_indicators

    async def _get_indicator_set(
        self, symbol: str, timeframe: str, db: AsyncSession
    ) -> TechnicalIndicatorsSet:
        market_data = await self.market_data_service.get_latest_market_data(
            db, symbol, timeframe, self.DEFAULT_PRICE_HISTORY_LIMIT
        )
        if not market_data or len(market_data) < self.MIN_CANDLES_FOR_INDICATORS:
            try:
                await self.market_data_service.sync_market_data(db, symbol, timeframe)
                market_data = await self.market_data_service.get_latest_market_data(
                    db, symbol, timeframe, self.DEFAULT_PRICE_HISTORY_LIMIT
                )
            except Exception as e:
                logger.warning(f"Failed to sync market data for {symbol} ({timeframe}): {e}")
            if not market_data or len(market_data) < self.MIN_CANDLES_FOR_INDICATORS:
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

    def _create_partial_indicators(self, market_data: List[MarketData]) -> TechnicalIndicatorsSet:
        """Create a partial indicators set when full indicators can't be calculated."""
        return TechnicalIndicatorsSet()

    async def _fetch_primary_market_data(
        self, symbol: str, timeframe: str, db: AsyncSession
    ) -> List[MarketData]:
        primary_market_data = await self.market_data_service.get_latest_market_data(
            db, symbol, timeframe, self.DEFAULT_PRICE_HISTORY_LIMIT
        )
        if not primary_market_data or len(primary_market_data) < 10:
            raise InsufficientMarketDataError(f"Insufficient primary market data for {symbol}")
        primary_market_data.sort(key=lambda x: x.time)
        return primary_market_data

    def _build_asset_market_data(
        self,
        symbol: str,
        primary_market_data: List[MarketData],
        technical_indicators: TechnicalIndicators,
    ) -> AssetMarketData:
        latest_candle = primary_market_data[-1]
        current_price = latest_candle.close
        price_24h_ago = (
            primary_market_data[-24].close
            if len(primary_market_data) >= 24
            else primary_market_data[0].close
        )
        price_change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
        volume_24h = (
            sum(c.volume for c in primary_market_data[-24:])
            if len(primary_market_data) >= 24
            else latest_candle.volume
        )
        volatility = self._calculate_volatility(primary_market_data)
        price_history = [
            PricePoint(timestamp=c.time, price=c.close, volume=c.volume)
            for c in primary_market_data[-50:]
        ]
        funding_rate = next(
            (
                float(c.funding_rate)
                for c in reversed(primary_market_data)
                if hasattr(c, "funding_rate") and c.funding_rate is not None
            ),
            None,
        )
        return AssetMarketData(
            symbol=symbol,
            current_price=current_price,
            price_change_24h=price_change_24h,
            volume_24h=volume_24h,
            funding_rate=funding_rate,
            open_interest=None,
            price_history=price_history,
            volatility=volatility,
            technical_indicators=technical_indicators,
        )

    def _calculate_volatility(self, market_data: List[MarketData]) -> float:
        if len(market_data) < 20:
            return 0.0
        returns = [
            (market_data[-i].close - market_data[-i - 1].close) / market_data[-i - 1].close
            for i in range(1, min(21, len(market_data)))
        ]
        return stdev(returns) * 100 if len(returns) > 1 else 0.0

    def _process_asset_data_results(
        self, asset_data_results: List[Any], symbols: List[str]
    ) -> Tuple[Dict[str, AssetMarketData], List[str]]:
        assets, errors = {}, []
        for i, symbol in enumerate(symbols):
            result = asset_data_results[i]
            if isinstance(result, Exception):
                error_message = f"Failed to get market data for {symbol}: {result}"
                logger.error(error_message)
                errors.append(error_message)
            else:
                assets[symbol] = result
        return assets, errors

    async def get_account_context(
        self, account_id: int, force_refresh: bool = False
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

        if self._session_factory is None:
            raise ContextBuilderError("No database session factory provided.")

        async with self._session_factory() as db:
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
                    # Validate the side is one of the expected values
                    if pos.side not in ["long", "short"]:
                        raise ContextBuilderError(f"Invalid position side: {pos.side}")
                    # Cast to Literal type to satisfy mypy
                    side_literal: Literal["long", "short"] = pos.side  # type: ignore
                    position_summary = PositionSummary(
                        symbol=pos.symbol,
                        side=side_literal,
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

                # Get active trading strategy
                active_strategy = await self.strategy_manager.get_account_strategy(account_id)
                if not active_strategy:
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
                    maker_fee_bps=account.maker_fee_bps,
                    taker_fee_bps=account.taker_fee_bps,
                    active_strategy=active_strategy,
                )

                # Cache the result
                self._cache[cache_key] = (datetime.now(timezone.utc), account_context)

                logger.debug(
                    f"Built account context: balance=${balance_usd:.2f}, positions={len(positions)}, pnl=${total_pnl:.2f}"
                )
                return account_context

            except Exception as e:
                logger.error(f"Failed to get account context: {e}")
                raise ContextBuilderError(f"Failed to get account context: {e}") from e

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
        self, account_id: int, symbol: Optional[str] = None
    ) -> List[TradeHistory]:
        """
        Get recent trade history for the account.

        Args:
            account_id: Account ID
            symbol: Optional symbol filter

        Returns:
           List of TradeHistory objects
        """
        if self._session_factory is None:
            raise ContextBuilderError("No database session factory provided.")

        async with self._session_factory() as db:
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
                trade_history = []
                for trade in trades:
                    # Validate the side is one of the expected values
                    if trade.side not in ["buy", "sell"]:
                        raise ContextBuilderError(f"Invalid trade side: {trade.side}")

                    # Ensure the timestamp is not None
                    if trade.created_at is None:
                        raise ContextBuilderError(f"Trade {trade.id} has no timestamp")

                    # Cast to Literal type to satisfy mypy
                    side_literal: Literal["buy", "sell"] = trade.side  # type: ignore

                    trade_history.append(
                        TradeHistory(
                            symbol=trade.symbol,
                            side=side_literal,
                            size=trade.quantity,  # Map quantity to size
                            price=trade.price,
                            timestamp=trade.created_at,
                            pnl=trade.pnl,
                        )
                    )

                return trade_history
            except Exception as e:
                logger.error(f"Failed to get recent trades: {e}")
                raise ContextBuilderError(f"Failed to get recent trades: {e}") from e

    async def _calculate_performance_metrics(
        self, db: AsyncSession, account_id: int
    ) -> PerformanceMetrics:
        """Calculate performance metrics for the account."""
        # Get trades from the last 30 days
        # Note: created_at in DB is naive timestamp (UTC), so we need naive datetime for comparison
        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=self.PERFORMANCE_LOOKBACK_DAYS
        )

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
            sum(trade.pnl for trade in winning_trades if trade.pnl is not None)
            / len(winning_trades)
            if winning_trades
            else 0
        )
        avg_loss = (
            sum(trade.pnl for trade in losing_trades if trade.pnl is not None) / len(losing_trades)
            if losing_trades
            else 0
        )

        # Calculate max drawdown (simplified)
        running_pnl = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for trade in trades:
            if trade.pnl is not None:
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

    def clear_cache(self, pattern: Optional[str] = None) -> None:
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
    session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
) -> "ContextBuilderService":
    """Get or create the context builder service instance.

    Args:
        session_factory: Optional database session factory. If not provided, the service will create its own.
    """
    global _context_builder_service
    if _context_builder_service is None:
        _context_builder_service = ContextBuilderService(session_factory=session_factory)
    elif session_factory is not None and _context_builder_service._session_factory is None:
        # Update the existing instance with the new session factory if needed
        _context_builder_service._session_factory = session_factory
    return _context_builder_service
