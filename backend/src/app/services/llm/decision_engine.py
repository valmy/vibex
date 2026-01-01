"""
Decision Engine Orchestrator for LLM-powered trading decisions.

Coordinates all components to provide a unified interface for trading decision generation.
Handles context building, LLM analysis, validation, caching, and multi-account support.

SCHEMA UNIFICATION (2025-11-02):
This service uses the CANONICAL schemas from app.schemas.trading_decision:
- TradingContext: Complete trading context for decision making
- TradingDecision: Structured trading decision from LLM
- DecisionResult: Result of decision generation with context and decision
- HealthStatus: Health status of the decision engine
- UsageMetrics: Usage metrics for monitoring

CACHE INVALIDATION:
- _invalidate_account_caches(): Clears caches for a specific account using clear_cache()
- invalidate_symbol_caches(): Clears caches for a specific symbol using clear_cache()

These methods use the new clear_cache(pattern) API from ContextBuilderService.
Previously, they called invalidate_cache_for_account() and invalidate_cache_for_symbol()
which have been removed during schema unification.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.session import get_session_factory
from ...schemas.trading_decision import (
    AccountContext,
    DecisionResult,
    HealthStatus,
    MarketContext,
    PerformanceMetrics,
    RiskMetrics,
    StrategyRiskParameters,
    TradingContext,
    TradingStrategy,
    UsageMetrics,
)
from .context_builder import get_context_builder_service
from .decision_repository import DecisionRepository
from .decision_validator import get_decision_validator
from .llm_service import get_llm_service
from .strategy_manager import StrategyManager

logger = logging.getLogger(__name__)

# Constants for minimal context creation
# These values satisfy Pydantic schema constraints for historical decision contexts
# where full context data is not available
_MINIMAL_VALID_MAX_POSITION_SIZE = 1.0  # Must be > 0 per AccountContext constraint


class DecisionEngineError(Exception):
    """Base exception for decision engine errors."""

    pass


class RateLimitExceededError(DecisionEngineError):
    """Raised when rate limit is exceeded."""

    pass


class CacheEntry:
    """Cache entry with TTL and metadata."""

    def __init__(self, data: Any, ttl_seconds: int = 300):
        self.data = data
        self.created_at = datetime.now(timezone.utc)
        self.ttl_seconds = ttl_seconds
        self.access_count = 0
        self.last_accessed = self.created_at

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def access(self) -> Any:
        """Access cached data and update metrics."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
        return self.data


class RateLimiter:
    """Rate limiter for decision requests."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[datetime]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed under rate limit."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Clean old requests
        self.requests[key] = [req_time for req_time in self.requests[key] if req_time > cutoff]

        # Check if under limit
        return len(self.requests[key]) < self.max_requests

    def record_request(self, key: str) -> None:
        """Record a new request."""
        self.requests[key].append(datetime.now(timezone.utc))

    def get_remaining_requests(self, key: str) -> int:
        """Get remaining requests for key."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Clean old requests
        self.requests[key] = [req_time for req_time in self.requests[key] if req_time > cutoff]

        return max(0, self.max_requests - len(self.requests[key]))

    def get_reset_time(self, key: str) -> Optional[datetime]:
        """Get when rate limit resets for key."""
        if not self.requests[key]:
            return None

        oldest_request = min(self.requests[key])
        return oldest_request + timedelta(seconds=self.window_seconds)


class DecisionEngine:
    """
    Main orchestrator for LLM-powered trading decisions.

    Coordinates context building, LLM analysis, validation, and provides
    unified interface with caching and rate limiting.
    """

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        """Initialize the Decision Engine."""
        self.session_factory = session_factory
        self.llm_service = get_llm_service()
        self.context_builder = get_context_builder_service(session_factory=session_factory)
        self.decision_validator = get_decision_validator()
        self.strategy_manager = StrategyManager(session_factory=session_factory)
        self.decision_repository = DecisionRepository(session_factory) if session_factory else None

        # Caching system
        self._decision_cache: Dict[str, CacheEntry] = {}
        self._context_cache: Dict[str, CacheEntry] = {}
        self.cache_ttl_seconds = 300  # 5 minutes default

        # Rate limiting
        self.rate_limiter = RateLimiter(
            max_requests=60, window_seconds=60
        )  # 60 requests per minute

        # Performance metrics
        self.metrics: Dict[str, Any] = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "failed_decisions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_processing_time_ms": 0.0,
            "rate_limit_rejections": 0,
            "last_reset": datetime.now(timezone.utc),
        }

        # Concurrent processing limits
        self.max_concurrent_decisions = 10
        self._active_decisions: Dict[str, asyncio.Task[Any]] = {}

        logger.info("Decision Engine initialized")

    async def make_trading_decision(
        self,
        account_id: int,
        symbols: Optional[List[str]] = None,
        strategy_override: Optional[str] = None,
        force_refresh: bool = False,
        ab_test_name: Optional[str] = None,
    ) -> DecisionResult:
        """
        Generate a multi-asset trading decision for the given symbols and account.

        Args:
            symbols: List of trading pair symbols (e.g., ["BTCUSDT", "ETHUSDT"]).
                    If None, uses ASSETS environment variable.
            account_id: Account identifier
            strategy_override: Optional strategy to override account strategy
            force_refresh: Force refresh of cached data
            ab_test_name: Optional A/B test name for model selection

        Returns:
            DecisionResult with the multi-asset trading decision and metadata

        Raises:
            RateLimitExceededError: If rate limit is exceeded
            DecisionEngineError: If decision generation fails
        """
        # Default to ASSETS environment variable if symbols not provided or empty
        if not symbols:  # Handles both None and empty list
            from ...core.config import config

            # Get default assets from config, fallback to hardcoded list if empty or None
            assets_str = getattr(config, "ASSETS", None) or "BTC,ETH,SOL"
            symbols = [f"{asset.strip()}USDT" for asset in assets_str.split(",") if asset.strip()]

            # If still empty after parsing, use emergency defaults
            if not symbols:
                symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

            logger.info(f"Using default symbols: {symbols}")

        start_time = time.time()
        decision_key = f"{'_'.join(sorted(symbols))}_{account_id}_{strategy_override or 'default'}"

        try:
            # Check rate limits
            rate_limit_key = f"account_{account_id}"
            if not self.rate_limiter.is_allowed(rate_limit_key):
                self.metrics["rate_limit_rejections"] += 1
                remaining = self.rate_limiter.get_remaining_requests(rate_limit_key)
                reset_time = self.rate_limiter.get_reset_time(rate_limit_key)
                raise RateLimitExceededError(
                    f"Rate limit exceeded for account {account_id}. "
                    f"Remaining: {remaining}, Reset: {reset_time}"
                )

            # Record the request
            self.rate_limiter.record_request(rate_limit_key)

            # Check cache first (unless force refresh)
            if not force_refresh:
                cached_result = self._get_cached_decision(decision_key)
                if cached_result:
                    self.metrics["cache_hits"] += 1
                    logger.debug(f"Cache hit for decision {decision_key}")
                    return cached_result

            self.metrics["cache_misses"] += 1

            # Check concurrent processing limits
            if len(self._active_decisions) >= self.max_concurrent_decisions:
                raise DecisionEngineError(
                    "Maximum concurrent decisions reached. Please try again later."
                )

            # Create processing task
            task = asyncio.create_task(
                self._process_multi_asset_decision(
                    symbols, account_id, strategy_override, force_refresh, ab_test_name
                )
            )
            self._active_decisions[decision_key] = task

            try:
                result = await task

                # Cache the result
                self._cache_decision(decision_key, result)

                # Update metrics
                self.metrics["total_decisions"] += 1
                self.metrics["successful_decisions"] += 1

                processing_time_ms = (time.time() - start_time) * 1000
                self._update_avg_processing_time(processing_time_ms)

                logger.info(
                    "Multi-asset decision generated successfully",
                    extra={
                        "symbols": symbols,
                        "account_id": account_id,
                        "num_assets": len(symbols),
                        "processing_time_ms": processing_time_ms,
                        "cached": False,
                    },
                )

                return result

            finally:
                # Clean up active task
                self._active_decisions.pop(decision_key, None)

        except Exception as e:
            self.metrics["total_decisions"] += 1
            self.metrics["failed_decisions"] += 1

            logger.error(
                "Multi-asset decision generation failed",
                extra={
                    "symbols": symbols,
                    "account_id": account_id,
                    "error": str(e),
                    "processing_time_ms": (time.time() - start_time) * 1000,
                },
                exc_info=True,
            )

            raise DecisionEngineError(f"Decision generation failed: {str(e)}") from e

    async def _process_multi_asset_decision(
        self,
        symbols: List[str],
        account_id: int,
        strategy_override: Optional[str],
        force_refresh: bool,
        ab_test_name: Optional[str],
    ) -> DecisionResult:
        strategy = await self._get_strategy(account_id, strategy_override)
        timeframes = self._get_timeframes(strategy)
        context = await self._build_context(
            symbols, account_id, timeframes, force_refresh, strategy_override
        )
        decision_result = await self._generate_decision(
            symbols, context, strategy_override, ab_test_name
        )
        decision_result = await self._validate_and_handle_fallback(
            decision_result, context, symbols, account_id
        )
        await self._persist_decision_if_repository_exists(
            account_id, strategy.strategy_id, decision_result, context
        )
        return decision_result

    async def _get_strategy(self, account_id: int, strategy_override: Optional[str]) -> Any:
        if strategy_override:
            strategy = await self.strategy_manager.get_strategy(strategy_override)
            if not strategy:
                raise DecisionEngineError(f"Strategy '{strategy_override}' not found")
            return strategy
        return await self.strategy_manager.get_account_strategy(account_id)

    def _get_timeframes(self, strategy: Any) -> List[str]:
        timeframes = strategy.timeframe_preference or ["5m", "1h"]
        if len(timeframes) != 2:
            logger.warning(
                f"Strategy '{strategy.strategy_id}' has {len(timeframes)} timeframes, expected 2. Defaulting to ['5m', '1h']."
            )
            return ["5m", "1h"]
        return timeframes

    async def _build_context(
        self,
        symbols: Optional[List[str]],
        account_id: int,
        timeframes: List[str],
        force_refresh: bool,
        strategy_override: Optional[str],
    ) -> TradingContext:
        context = await self._build_multi_asset_context_with_recovery(
            symbols or [], account_id, timeframes, force_refresh
        )
        if strategy_override:
            strategy = await self.strategy_manager.get_strategy(strategy_override)
            if not strategy or not strategy.is_active:
                raise DecisionEngineError(
                    f"Strategy '{strategy_override}' is not active or not found"
                )
            context.account_state.active_strategy = strategy
        return context

    async def _generate_decision(
        self,
        symbols: List[str],
        context: TradingContext,
        strategy_override: Optional[str],
        ab_test_name: Optional[str],
    ) -> Any:
        return await self.llm_service.generate_trading_decision(
            symbols=symbols,
            context=context,
            strategy_override=strategy_override,
            ab_test_name=ab_test_name,
        )

    async def _validate_and_handle_fallback(
        self, decision_result: Any, context: TradingContext, symbols: List[str], account_id: int
    ) -> Any:
        if decision_result.validation_passed:
            validation_result = await self.decision_validator.validate_decision(
                decision_result.decision, context
            )
            decision_result.validation_passed = validation_result.is_valid
            decision_result.validation_errors = validation_result.errors

        if not decision_result.validation_passed:
            logger.warning(
                "Multi-asset decision validation failed, creating fallback",
                extra={
                    "symbols": symbols,
                    "account_id": account_id,
                    "errors": decision_result.validation_errors,
                },
            )
            fallback_decision = await self.decision_validator.create_fallback_decision(
                decision_result.decision, context, decision_result.validation_errors
            )
            decision_result.decision = fallback_decision
            decision_result.validation_passed = True
        return decision_result

    async def _persist_decision_if_repository_exists(
        self, account_id: int, strategy_id: str, decision_result: Any, context: TradingContext
    ) -> None:
        if self.decision_repository:
            try:
                await self._persist_decision(
                    account_id=account_id,
                    strategy_id=strategy_id,
                    decision_result=decision_result,
                    context=context,
                )
            except Exception as e:
                logger.error(f"Failed to persist decision to database: {e}", exc_info=True)

    async def _build_multi_asset_context_with_recovery(
        self, symbols: List[str], account_id: int, timeframes: List[str], force_refresh: bool
    ) -> TradingContext:
        """
        Build multi-asset trading context with error recovery mechanisms.

        Args:
            symbols: List of trading pair symbols
            account_id: Account identifier
            timeframes: List of timeframes for analysis
            force_refresh: Force refresh of cached data

        Returns:
            TradingContext with complete multi-asset context data

        Raises:
            DecisionEngineError: If context building fails completely
        """
        context_key = f"context_{'_'.join(sorted(symbols))}_{account_id}"

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_context = self._get_cached_context(context_key)
            if cached_context:
                logger.debug(f"Using cached multi-asset context for {context_key}")
                return cached_context

        try:
            # Build fresh multi-asset context
            context = await self.context_builder.build_trading_context(
                symbols=symbols,
                account_id=account_id,
                timeframes=timeframes,
                force_refresh=force_refresh,
            )

            # Cache the context
            self._cache_context(context_key, context)

            return context

        except Exception as e:
            logger.error(
                f"Multi-asset context building failed for {symbols}, account {account_id}: {e}"
            )

            # Try to resolve strategy conflicts and retry once
            try:
                conflicts = await self.strategy_manager.resolve_strategy_conflicts(account_id)
                if conflicts:
                    logger.info(
                        f"Resolved strategy conflicts for account {account_id}: {conflicts}"
                    )

                    # Retry context building
                    context = await self.context_builder.build_trading_context(
                        symbols=symbols,
                        account_id=account_id,
                        timeframes=timeframes,
                        force_refresh=True,  # Force refresh after conflict resolution
                    )

                    self._cache_context(context_key, context)
                    return context

            except Exception as retry_error:
                logger.error(f"Multi-asset context building retry failed: {retry_error}")

            raise DecisionEngineError(f"Failed to build multi-asset context: {str(e)}") from e

    def _get_cached_decision(self, key: str) -> Optional[DecisionResult]:
        """Get cached decision if available and not expired."""
        entry = self._decision_cache.get(key)
        if entry and not entry.is_expired():
            return entry.access()
        elif entry:
            # Remove expired entry
            del self._decision_cache[key]
        return None

    def _cache_decision(self, key: str, result: DecisionResult) -> None:
        """Cache a decision result."""
        # Determine TTL based on decision actions (multi-asset)
        ttl = self.cache_ttl_seconds

        # Check if all asset decisions are "hold"
        all_hold = all(d.action == "hold" for d in result.decision.decisions)
        # Check if any asset decision is buy/sell
        has_trading = any(d.action in ["buy", "sell"] for d in result.decision.decisions)

        if all_hold:
            ttl = 600  # Cache hold decisions longer (10 minutes)
        elif has_trading:
            ttl = 180  # Cache trading decisions shorter (3 minutes)

        self._decision_cache[key] = CacheEntry(result, ttl)

    def _get_cached_context(self, key: str) -> Optional[TradingContext]:
        """Get cached context if available and not expired."""
        entry = self._context_cache.get(key)
        if entry and not entry.is_expired():
            return entry.access()
        elif entry:
            # Remove expired entry
            del self._context_cache[key]
        return None

    def _cache_context(self, key: str, context: TradingContext) -> None:
        """Cache a trading context."""
        # Context cache TTL is shorter since market data changes frequently
        ttl = 120  # 2 minutes
        self._context_cache[key] = CacheEntry(context, ttl)

    def _update_avg_processing_time(self, processing_time_ms: float) -> None:
        """Update average processing time metric."""
        total_decisions = self.metrics["total_decisions"]
        current_avg = self.metrics["avg_processing_time_ms"]

        if total_decisions == 1:
            self.metrics["avg_processing_time_ms"] = processing_time_ms
        else:
            # Calculate running average
            self.metrics["avg_processing_time_ms"] = (
                current_avg * (total_decisions - 1) + processing_time_ms
            ) / total_decisions

    def _generate_cache_key(self, symbol: str, account_id: int, **kwargs: Any) -> str:
        """Generate a cache key for the given parameters."""
        key_data = {"symbol": symbol, "account_id": account_id, **kwargs}
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    async def _persist_decision(
        self,
        account_id: int,
        strategy_id: str,
        decision_result: DecisionResult,
        context: TradingContext,
    ) -> None:
        """
        Persist trading decision to database.

        Args:
            account_id: Account ID
            strategy_id: Strategy ID
            decision_result: Decision result to persist
            context: Trading context used for decision
        """
        try:
            # Extract market and account context for storage
            # Use mode='json' to ensure all values are JSON-serializable (e.g., datetime -> str)
            market_context_dict = (
                context.market_data.model_dump(mode="json") if context.market_data else {}
            )
            account_context_dict = (
                context.account_state.model_dump(mode="json") if context.account_state else {}
            )
            risk_metrics_dict = (
                context.risk_metrics.model_dump(mode="json") if context.risk_metrics else {}
            )

            # Save decision to database if repository is available
            if self.decision_repository:
                await self.decision_repository.save_decision(
                    account_id=account_id,
                    strategy_id=strategy_id,
                    trading_decision=decision_result.decision,
                    model_used=decision_result.model_used,
                    processing_time_ms=decision_result.processing_time_ms,
                    validation_passed=decision_result.validation_passed,
                    validation_errors=decision_result.validation_errors,
                    validation_warnings=None,  # Add if available in decision_result
                    market_context=market_context_dict,
                    account_context=account_context_dict,
                    risk_metrics=risk_metrics_dict,
                    api_cost=None,  # Add if available in decision_result
                )

            logger.info(
                f"Persisted multi-asset decision for account {account_id} with "
                f"{len(decision_result.decision.decisions)} asset decisions"
            )

        except Exception as e:
            logger.error(f"Failed to persist decision: {e}", exc_info=True)
            raise

    async def batch_decisions(
        self,
        symbols: List[str],
        account_id: int,
        strategy_override: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[DecisionResult]:
        """
        Generate trading decisions for multiple symbols concurrently.

        Args:
            symbols: List of trading pair symbols
            account_id: Account identifier
            strategy_override: Optional strategy to override account strategy
            force_refresh: Force refresh of cached data

        Returns:
            List of DecisionResult objects
        """
        logger.info(f"Generating batch decisions for {len(symbols)} symbols, account {account_id}")

        # For multi-asset support, we generate a single decision for all symbols
        # This allows the LLM to analyze all assets together and make portfolio-level decisions
        result = await self.make_trading_decision(
            symbols=symbols,
            account_id=account_id,
            strategy_override=strategy_override,
            force_refresh=force_refresh,
        )

        # Return as a list for backward compatibility
        return [result]

    async def get_decision_history(
        self,
        account_id: int,
        symbol: Optional[str] = None,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[DecisionResult]:
        """
        Get decision history for an account with optional symbol filtering.

        Args:
            account_id: Account identifier
            symbol: Optional symbol filter (filters asset decisions within multi-asset decisions)
            limit: Maximum number of decisions to return
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of historical DecisionResult objects

        Note: This is a placeholder implementation. In a real system,
        this would query a database for historical decisions.
        When symbol filter is provided, it filters the asset decisions within
        each multi-asset TradingDecision to show only decisions for that symbol.
        """
        logger.info(f"Getting decision history for account {account_id}, symbol filter: {symbol}")

        if not self.decision_repository:
            logger.warning("Decision repository not available, returning empty history")
            return []

        try:
            # Query decisions from database
            decisions = await self.decision_repository.get_decision_history(
                account_id=account_id,
                limit=limit,
                symbol=symbol,
            )

            # Convert Decision models to DecisionResult objects
            decision_results = []
            for decision in decisions:
                # Reconstruct TradingDecision from stored data
                if decision.is_multi_asset:
                    # Multi-asset decision
                    from ...schemas.trading_decision import AssetDecision, TradingDecision

                    asset_decisions = (
                        [AssetDecision(**ad) for ad in decision.asset_decisions]
                        if decision.asset_decisions
                        else []
                    )

                    # If symbol filter is provided, filter asset decisions
                    if symbol:
                        asset_decisions = [ad for ad in asset_decisions if ad.asset == symbol]

                    trading_decision = TradingDecision(
                        decisions=asset_decisions,
                        portfolio_rationale=decision.portfolio_rationale or "No rationale provided",
                        total_allocation_usd=decision.total_allocation_usd or 0.0,
                        portfolio_risk_level=decision.portfolio_risk_level or "medium",  # type: ignore[arg-type]
                        timestamp=decision.timestamp,
                    )
                else:
                    # Legacy single-asset decision - skip if symbol filter doesn't match
                    if symbol and decision.symbol != symbol:
                        continue

                    # Convert to multi-asset format for consistency
                    from ...schemas.trading_decision import AssetDecision, TradingDecision

                    asset_decision = AssetDecision(
                        asset=decision.symbol or "Unknown",
                        action=decision.action,  # type: ignore[arg-type]
                        allocation_usd=decision.allocation_usd or 0.0,
                        tp_price=decision.tp_price,
                        sl_price=decision.sl_price,
                        exit_plan=decision.exit_plan or "No exit plan",
                        rationale=decision.rationale or "No rationale",
                        confidence=decision.confidence or 0.0,
                        risk_level=decision.risk_level,  # type: ignore[arg-type]
                        position_adjustment=decision.position_adjustment,  # type: ignore[arg-type]
                        order_adjustment=decision.order_adjustment,  # type: ignore[arg-type]
                    )

                    trading_decision = TradingDecision(
                        decisions=[asset_decision],
                        portfolio_rationale=decision.rationale or "No rationale provided",
                        total_allocation_usd=decision.allocation_usd or 0.0,
                        portfolio_risk_level=decision.risk_level or "medium",  # type: ignore[arg-type]
                        timestamp=decision.timestamp,
                    )

                # Create DecisionResult
                # Note: We don't have the full context stored, so we create a minimal one
                default_context = self._create_minimal_context(
                    account_id=account_id, timestamp=decision.timestamp
                )

                decision_result = DecisionResult(
                    decision=trading_decision,
                    context=default_context,
                    validation_passed=decision.validation_passed,
                    validation_errors=decision.validation_errors or [],
                    processing_time_ms=decision.processing_time_ms,
                    model_used=decision.model_used,
                )

                decision_results.append(decision_result)

            logger.info(
                f"Retrieved {len(decision_results)} decisions for account {account_id}"
                + (f" with symbol filter {symbol}" if symbol else "")
            )

            return decision_results

        except Exception as e:
            logger.error(f"Failed to get decision history: {e}", exc_info=True)
            return []

    async def switch_strategy(
        self,
        account_id: int,
        strategy_id: str,
        switch_reason: str = "Manual switch",
        switched_by: Optional[str] = None,
    ) -> bool:
        """
        Switch the trading strategy for an account.

        Args:
            account_id: Account identifier
            strategy_id: New strategy to assign
            switch_reason: Reason for the switch
            switched_by: User who initiated the switch

        Returns:
            True if switch was successful

        Raises:
            DecisionEngineError: If switch fails
        """
        try:
            await self.strategy_manager.switch_account_strategy(
                account_id=account_id,
                new_strategy_id=strategy_id,
                switch_reason=switch_reason,
                switched_by=switched_by,
            )

            # Invalidate caches for this account
            self._invalidate_account_caches(account_id)

            logger.info(f"Strategy switched for account {account_id} to {strategy_id}")
            return True

        except Exception as e:
            logger.error(f"Strategy switch failed for account {account_id}: {e}")
            raise DecisionEngineError(f"Strategy switch failed: {str(e)}") from e

    def _invalidate_account_caches(self, account_id: int) -> None:
        """Invalidate all caches for a specific account."""
        # Invalidate decision caches
        keys_to_remove = [key for key in self._decision_cache.keys() if f"_{account_id}_" in key]
        for key in keys_to_remove:
            del self._decision_cache[key]

        # Invalidate context caches
        keys_to_remove = [key for key in self._context_cache.keys() if f"_{account_id}" in key]
        for key in keys_to_remove:
            del self._context_cache[key]

        # Invalidate context builder caches using the new clear_cache method
        self.context_builder.clear_cache(f"account_context_{account_id}")

        logger.debug(f"Invalidated caches for account {account_id}")

    def invalidate_symbol_caches(self, symbol: str) -> None:
        """Invalidate all caches for a specific symbol."""
        # Invalidate decision caches
        keys_to_remove = [
            key for key in self._decision_cache.keys() if key.startswith(f"{symbol}_")
        ]
        for key in keys_to_remove:
            del self._decision_cache[key]

        # Invalidate context caches
        keys_to_remove = [key for key in self._context_cache.keys() if f"_{symbol}_" in key]
        for key in keys_to_remove:
            del self._context_cache[key]

        # Invalidate context builder caches using the new clear_cache method
        self.context_builder.clear_cache(f"market_context_{symbol}")

        logger.debug(f"Invalidated caches for symbol {symbol}")

    def _create_minimal_performance_metrics(self) -> PerformanceMetrics:
        """Creates a minimal valid PerformanceMetrics object."""
        return PerformanceMetrics(
            total_pnl=0.0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            max_drawdown=0.0,
            sharpe_ratio=None,
        )

    def _create_minimal_strategy_risk_parameters(self) -> StrategyRiskParameters:
        """Creates minimal valid StrategyRiskParameters."""
        return StrategyRiskParameters(
            max_risk_per_trade=1.0,
            max_daily_loss=5.0,
            stop_loss_percentage=2.0,
            take_profit_ratio=2.0,
            max_leverage=2.0,
            cooldown_period=300,
            max_funding_rate_bps=0.0,
            liquidation_buffer=0.0,
        )

    def _create_minimal_trading_strategy(self) -> TradingStrategy:
        """Creates a minimal valid TradingStrategy object."""
        return TradingStrategy(
            strategy_id="unknown",
            strategy_name="Unknown Strategy",
            strategy_type="conservative",
            prompt_template="No template available",
            risk_parameters=self._create_minimal_strategy_risk_parameters(),
            timeframe_preference=["1h", "4h"],
            max_positions=3,
            position_sizing="percentage",
            order_preference="any",
            funding_rate_threshold=0.0,
            is_active=False,
        )

    def _create_minimal_account_context(self, account_id: int) -> AccountContext:
        """Creates a minimal valid AccountContext object."""
        return AccountContext(
            account_id=account_id,
            balance_usd=0.0,
            available_balance=0.0,
            total_pnl=0.0,
            open_positions=[],
            recent_performance=self._create_minimal_performance_metrics(),
            risk_exposure=0.0,
            max_position_size=_MINIMAL_VALID_MAX_POSITION_SIZE,
            maker_fee_bps=5.0,
            taker_fee_bps=20.0,
            leverage=2.0,
            active_strategy=self._create_minimal_trading_strategy(),
        )

    def _create_minimal_risk_metrics(self) -> RiskMetrics:
        """Creates a minimal valid RiskMetrics object."""
        return RiskMetrics(
            var_95=0.0,
            max_drawdown=0.0,
            correlation_risk=0.0,
            concentration_risk=0.0,
        )

    def _create_minimal_context(self, account_id: int, timestamp: datetime) -> TradingContext:
        """
        Create a minimal valid TradingContext for historical decisions.

        This is used when retrieving decision history where we don't have
        the full context stored in the database.

        Args:
            account_id: Account identifier
            timestamp: Timestamp for the context

        Returns:
            Minimal but valid TradingContext
        """
        # Create minimal MarketContext
        minimal_market_context = MarketContext(
            assets={},  # Empty assets dictionary
            market_sentiment=None,
            timestamp=timestamp,
        )

        return TradingContext(
            symbols=[],
            account_id=account_id,
            timeframes=[],
            market_data=minimal_market_context,
            account_state=self._create_minimal_account_context(account_id),
            recent_trades={},
            risk_metrics=self._create_minimal_risk_metrics(),
            timestamp=timestamp,
            errors=["Historical decision - full context not available"],
        )

    async def get_engine_health(self) -> HealthStatus:
        """
        Get the health status of the decision engine.

        Returns:
            HealthStatus with engine health information
        """
        try:
            # Check LLM service health
            llm_health = await self.llm_service.validate_api_health()

            # Check cache health
            cache_stats = self.get_cache_stats()

            # Determine overall health
            is_healthy = (
                llm_health.is_healthy
                and len(self._active_decisions) < self.max_concurrent_decisions
                and cache_stats["memory_usage_mb"] < 500  # Arbitrary threshold
            )

            return HealthStatus(
                is_healthy=is_healthy,
                response_time_ms=self.metrics["avg_processing_time_ms"],
                last_successful_request=None,  # TODO: Track this
                consecutive_failures=self.metrics["failed_decisions"],
                circuit_breaker_open=llm_health.circuit_breaker_open,
                available_models=getattr(llm_health, "available_models", []),
                current_model=getattr(llm_health, "current_model", None),
                error_message=(
                    getattr(llm_health, "error_message", None) if not is_healthy else None
                ),
            )

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                is_healthy=False,
                consecutive_failures=999,
                circuit_breaker_open=True,
                error_message=f"Health check failed: {str(e)}",
            )

    def get_usage_metrics(self, timeframe_hours: int = 24) -> UsageMetrics:
        """
        Get usage metrics for the decision engine.

        Args:
            timeframe_hours: Hours to look back for metrics

        Returns:
            UsageMetrics with engine usage statistics
        """
        total_requests = self.metrics["total_decisions"]
        successful_requests = self.metrics["successful_decisions"]
        failed_requests = self.metrics["failed_decisions"]

        error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0.0

        # Calculate uptime (simplified)
        uptime_hours = (
            datetime.now(timezone.utc) - self.metrics["last_reset"]
        ).total_seconds() / 3600
        uptime_percentage = (
            min(100.0, (uptime_hours / timeframe_hours) * 100) if timeframe_hours > 0 else 100.0
        )

        # Calculate requests per hour
        requests_per_hour = total_requests / max(1, uptime_hours)

        return UsageMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time_ms=self.metrics["avg_processing_time_ms"],
            total_cost_usd=0.0,  # TODO: Calculate actual costs
            cost_per_request=0.0,  # TODO: Calculate actual costs
            requests_per_hour=requests_per_hour,
            error_rate=error_rate,
            uptime_percentage=uptime_percentage,
            period_start=self.metrics["last_reset"],
            period_end=datetime.now(timezone.utc),
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        # Clean expired entries first
        self._cleanup_expired_cache()

        decision_cache_size = len(self._decision_cache)
        context_cache_size = len(self._context_cache)
        total_cache_size = decision_cache_size + context_cache_size

        # Calculate cache hit rate
        total_cache_requests = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        cache_hit_rate = (
            (self.metrics["cache_hits"] / total_cache_requests * 100)
            if total_cache_requests > 0
            else 0.0
        )

        # Estimate memory usage (rough calculation)
        memory_usage_mb = total_cache_size * 0.1  # Rough estimate: 100KB per entry

        return {
            "decision_cache_entries": decision_cache_size,
            "context_cache_entries": context_cache_size,
            "total_cache_entries": total_cache_size,
            "cache_hits": self.metrics["cache_hits"],
            "cache_misses": self.metrics["cache_misses"],
            "cache_hit_rate": cache_hit_rate,
            "memory_usage_mb": memory_usage_mb,
            "active_decisions": len(self._active_decisions),
            "max_concurrent_decisions": self.max_concurrent_decisions,
        }

    def _cleanup_expired_cache(self) -> None:
        """Clean up expired cache entries."""
        # Clean decision cache
        expired_decision_keys = [
            key for key, entry in self._decision_cache.items() if entry.is_expired()
        ]
        for key in expired_decision_keys:
            del self._decision_cache[key]

        # Clean context cache
        expired_context_keys = [
            key for key, entry in self._context_cache.items() if entry.is_expired()
        ]
        for key in expired_context_keys:
            del self._context_cache[key]

        if expired_decision_keys or expired_context_keys:
            logger.debug(
                f"Cleaned up {len(expired_decision_keys)} decision cache entries and {len(expired_context_keys)} context cache entries"
            )

    def clear_all_caches(self) -> None:
        """Clear all caches."""
        self._decision_cache.clear()
        self._context_cache.clear()
        self.context_builder.clear_cache()
        logger.info("All caches cleared")

    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.metrics = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "failed_decisions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_processing_time_ms": 0.0,
            "rate_limit_rejections": 0,
            "last_reset": datetime.now(timezone.utc),
        }
        logger.info("Decision engine metrics reset")

    async def shutdown(self) -> None:
        """Gracefully shutdown the decision engine."""
        logger.info("Shutting down decision engine...")

        # Cancel all active decisions
        for key, task in self._active_decisions.items():
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled active decision: {key}")

        # Wait for tasks to complete or timeout
        if self._active_decisions:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_decisions.values(), return_exceptions=True),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Some decisions did not complete within shutdown timeout")

        # Clear caches
        self.clear_all_caches()

        logger.info("Decision engine shutdown complete")


# Global service instance
_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine(session_factory: Optional[Any] = None) -> DecisionEngine:
    """Get or create the decision engine instance."""
    global _decision_engine
    if _decision_engine is None:
        if session_factory is None:
            try:
                session_factory = get_session_factory()
            except RuntimeError:
                # DB might not be initialized yet in tests or early startup
                logger.warning("Database not initialized when creating DecisionEngine")
                pass
        _decision_engine = DecisionEngine(session_factory=session_factory)
    return _decision_engine
