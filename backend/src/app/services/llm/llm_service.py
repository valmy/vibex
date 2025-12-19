"""
LLM Service for market analysis and trading insights.

Integrates with OpenRouter API for LLM-powered analysis.
Enhanced with structured decision generation, multi-model support,
and comprehensive error handling.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError as PydanticValidationError

from ...core.config import config
from ...core.logging import get_logger
from ...schemas.trading_decision import (
    DecisionResult,
    HealthStatus,
    TradingContext,
    TradingDecision,
    UsageMetrics,
)
from .ab_testing import get_ab_test_manager
from .circuit_breaker import CircuitBreaker
from .llm_exceptions import (
    AuthenticationError,
    InsufficientDataError,
    LLMAPIError,
    ModelSwitchError,
    ValidationError,
)
from .llm_metrics import get_metrics_tracker

logger = get_logger(__name__)


class LLMService:
    """Service for LLM-powered market analysis and trading decisions."""

    def __init__(self) -> None:
        """Initialize the LLM Service."""
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL
        self.model = config.LLM_MODEL
        self.referer = config.OPENROUTER_REFERER
        self.app_title = config.OPENROUTER_APP_TITLE

        # Initialize OpenRouter client (lazy loaded)
        self._client: Optional[Any] = None

        # Enhanced features
        self.metrics_tracker = get_metrics_tracker()
        self.ab_test_manager = get_ab_test_manager()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60, expected_exception=LLMAPIError
        )

        # Supported models
        self.supported_models = {
            "gpt-4": "openai/gpt-4",
            "gpt-3.5-turbo": "openai/gpt-3.5-turbo",
            "claude-3-sonnet": "anthropic/claude-3-sonnet",
            "grok-beta": "x-ai/grok-beta",
            "deepseek-r1": "deepseek/deepseek-r1",
        }

        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay for exponential backoff

    @property
    def client(self):
        # type: () -> Any  # Return type depends on imported client
        """Lazy load OpenRouter client."""
        if self._client is None:
            try:
                import openai

                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    default_headers={
                        "HTTP-Referer": self.referer,
                        "X-Title": self.app_title,
                    },
                )
                logger.info(f"OpenRouter client initialized with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter client: {e}")
                raise
        return self._client

    async def analyze_market(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze market data and provide trading insights.

        Args:
            symbol: Trading pair symbol
            market_data: Market data dictionary with OHLCV data
            additional_context: Additional context for analysis

        Returns:
            Analysis result with insights and recommendations
        """
        try:
            prompt = self._build_analysis_prompt(symbol, market_data, additional_context)

            logger.info(f"Analyzing market for {symbol}")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert cryptocurrency trading analyst. Provide concise, actionable market analysis.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            analysis_text = response.choices[0].message.content

            # Parse the response
            result = {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "analysis": analysis_text,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }

            logger.info(f"Market analysis completed for {symbol}")
            return result
        except Exception as e:
            logger.error(f"Error analyzing market for {symbol}: {e}")
            raise

    async def get_trading_signal(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        account_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get trading signal based on market analysis.

        Args:
            symbol: Trading pair symbol
            market_data: Market data dictionary
            account_info: Optional account information

        Returns:
            Trading signal with recommendation
        """
        try:
            prompt = self._build_signal_prompt(symbol, market_data, account_info)

            logger.info(f"Generating trading signal for {symbol}")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional trading advisor. Provide trading signals in JSON format with: signal (BUY/SELL/HOLD), confidence (0-100), reason.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=300,
            )

            signal_text = response.choices[0].message.content

            # Try to parse JSON response
            try:
                signal_data = json.loads(signal_text)
            except json.JSONDecodeError:
                # If not JSON, extract signal from text
                signal_data = {"signal": "HOLD", "confidence": 50, "reason": signal_text}

            result = {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal": signal_data.get("signal", "HOLD"),
                "confidence": signal_data.get("confidence", 50),
                "reason": signal_data.get("reason", ""),
                "model": self.model,
            }

            logger.info(f"Trading signal generated for {symbol}: {result['signal']}")
            return result
        except Exception as e:
            logger.error(f"Error generating trading signal for {symbol}: {e}")
            raise

    async def summarize_market_conditions(
        self,
        market_data_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Summarize overall market conditions.

        Args:
            market_data_list: List of market data for multiple symbols

        Returns:
            Market summary
        """
        try:
            prompt = self._build_summary_prompt(market_data_list)

            logger.info("Generating market summary")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a market analyst. Provide a concise summary of market conditions.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=400,
            )

            summary_text = response.choices[0].message.content

            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": summary_text,
                "symbols_analyzed": len(market_data_list),
                "model": self.model,
            }

            logger.info("Market summary generated")
            return result
        except Exception as e:
            logger.error(f"Error generating market summary: {e}")
            raise

    def _build_analysis_prompt(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        additional_context: Optional[str] = None,
    ) -> str:
        """Build market analysis prompt."""
        prompt = f"""
Analyze the following market data for {symbol}:

Current Price: ${market_data.get("close", 0):.2f}
24h High: ${market_data.get("high", 0):.2f}
24h Low: ${market_data.get("low", 0):.2f}
Volume: {market_data.get("volume", 0):.2f}
Open: ${market_data.get("open", 0):.2f}

{f"Additional Context: {additional_context}" if additional_context else ""}

Provide:
1. Current trend analysis
2. Key support/resistance levels
3. Volume analysis
4. Potential price targets
5. Risk assessment
"""
        return prompt.strip()

    def _build_signal_prompt(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        account_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build trading signal prompt."""
        prompt = f"""
Generate a trading signal for {symbol} based on:

Price: ${market_data.get("close", 0):.2f}
24h Change: {market_data.get("change_percent", 0):.2f}%
Volume: {market_data.get("volume", 0):.2f}
RSI: {market_data.get("rsi", 50):.2f}
MACD: {market_data.get("macd", 0):.4f}

{f"Account Balance: ${account_info.get('balance', 0):.2f}" if account_info else ""}

Respond in JSON format:
{{"signal": "BUY|SELL|HOLD", "confidence": 0-100, "reason": "brief reason"}}
"""
        return prompt.strip()

    def _build_summary_prompt(self, market_data_list: List[Dict[str, Any]]) -> str:
        """Build market summary prompt."""
        symbols_summary = "\n".join(
            [
                f"- {data.get('symbol', 'N/A')}: ${data.get('close', 0):.2f} ({data.get('change_percent', 0):.2f}%)"
                for data in market_data_list
            ]
        )

        prompt = f"""
Summarize the current market conditions for these assets:

{symbols_summary}

Provide:
1. Overall market sentiment
2. Key trends
3. Risk factors
4. Opportunities
"""
        return prompt.strip()

    async def generate_trading_decision(
        self,
        symbols: List[str],
        context: TradingContext,
        strategy_override: Optional[str] = None,
        ab_test_name: Optional[str] = None,
    ) -> DecisionResult:
        """Generate structured multi-asset trading decision using LLM analysis.

        Args:
            symbols: List of trading pair symbols to analyze
            context: Complete multi-asset trading context
            strategy_override: Optional strategy to override account strategy
            ab_test_name: Optional A/B test name for model selection

        Returns:
            DecisionResult with structured multi-asset decision and validation status

        Raises:
            LLMAPIError: When API call fails
            ValidationError: When decision validation fails
            InsufficientDataError: When context is insufficient
        """
        start_time = time.time()
        original_model = self.model

        try:
            # Check for A/B test model override
            if ab_test_name:
                test_model = self.get_ab_test_model(ab_test_name, context.account_id)
                if test_model:
                    self.model = test_model
                    logger.debug(f"Using A/B test model: {test_model}")

            # Validate context
            if not self._validate_context(context):
                raise InsufficientDataError("Insufficient context for decision generation")

            # Build multi-asset decision prompt
            prompt = self._build_multi_asset_decision_prompt(symbols, context, strategy_override)

            # Generate decision with circuit breaker protection
            decision_data = await self.circuit_breaker.call(self._call_llm_for_decision, prompt)

            # Parse and validate multi-asset decision
            decision = self._parse_multi_asset_decision_response(decision_data, symbols)

            processing_time_ms = (time.time() - start_time) * 1000

            # Record A/B testing metrics if applicable
            if ab_test_name and self.model != original_model:
                # Calculate average confidence across all asset decisions
                avg_confidence = (
                    sum(d.confidence for d in decision.decisions) / len(decision.decisions)
                    if decision.decisions
                    else 0
                )
                self.ab_test_manager.record_decision_performance(
                    model_name=self.model,
                    confidence=avg_confidence,
                    response_time_ms=processing_time_ms,
                    cost=decision_data.get("cost"),
                    success=True,
                )

            # Create result
            result = DecisionResult(
                decision=decision,
                context=context,
                validation_passed=True,
                validation_errors=[],
                processing_time_ms=processing_time_ms,
                model_used=self.model,
                api_cost=decision_data.get("cost"),
            )

            logger.info(f"Multi-asset trading decision generated for {len(symbols)} assets")
            return result

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Error generating multi-asset trading decision: {e}")

            # Record A/B testing failure if applicable
            if ab_test_name and self.model != original_model:
                self.ab_test_manager.record_decision_performance(
                    model_name=self.model,
                    confidence=0,
                    response_time_ms=processing_time_ms,
                    success=False,
                )

            # Return fallback decision
            fallback_decision = self._create_multi_asset_fallback_decision(symbols)

            # For the error case, we'll use the original context directly
            # as it's already a TradingContext object
            return DecisionResult(
                decision=fallback_decision,
                context=context,  # Use the original context directly
                validation_passed=False,
                validation_errors=[str(e)],
                processing_time_ms=processing_time_ms,
                model_used=self.model,
            )
        finally:
            # Restore original model if it was changed for A/B testing
            if ab_test_name and self.model != original_model:
                self.model = original_model

    async def switch_model(self, model_name: str) -> bool:
        """Switch to a different LLM model.

        Args:
            model_name: Name of the model to switch to

        Returns:
            True if switch was successful

        Raises:
            ModelSwitchError: When model switch fails
        """
        try:
            if model_name not in self.supported_models:
                available_models = ", ".join(self.supported_models.keys())
                raise ModelSwitchError(
                    f"Model '{model_name}' not supported. Available: {available_models}"
                )

            old_model = self.model
            self.model = self.supported_models[model_name]

            # Test the new model with a simple call
            test_successful = await self._test_model_connection()

            if test_successful:
                logger.info(f"Successfully switched from {old_model} to {self.model}")
                return True
            else:
                # Revert to old model
                self.model = old_model
                raise ModelSwitchError(f"Failed to connect to model {model_name}")

        except Exception as e:
            logger.error(f"Error switching to model {model_name}: {e}")
            raise ModelSwitchError(f"Model switch failed: {e}") from e

    async def validate_api_health(self) -> HealthStatus:
        """Validate API health and connectivity.

        Returns:
            HealthStatus with current service health
        """
        try:
            tracker_status = self.metrics_tracker.get_health_status()
            circuit_open = self.circuit_breaker.is_open

            # Test connectivity if needed
            if tracker_status.consecutive_failures > 3:
                test_successful = await self._test_model_connection()
                if not test_successful:
                    tracker_status.is_healthy = False

            return HealthStatus(
                is_healthy=tracker_status.is_healthy and not circuit_open,
                response_time_ms=tracker_status.avg_response_time_ms,
                last_successful_request=tracker_status.last_successful_call,
                consecutive_failures=tracker_status.consecutive_failures,
                circuit_breaker_open=circuit_open,
                available_models=list(self.supported_models.keys()),
                current_model=self.model,
                error_message=None if tracker_status.is_healthy else "Health check failed",
            )

        except Exception as e:
            logger.error(f"Error validating API health: {e}")
            return HealthStatus(
                is_healthy=False,
                consecutive_failures=999,
                circuit_breaker_open=self.circuit_breaker.is_open,
                available_models=list(self.supported_models.keys()),
                current_model=self.model,
                error_message=str(e),
            )

    def get_usage_metrics(self, timeframe_hours: int = 24) -> UsageMetrics:
        """Get usage metrics for specified timeframe.

        Args:
            timeframe_hours: Hours to look back for metrics

        Returns:
            UsageMetrics summary
        """
        tracker_metrics = self.metrics_tracker.get_usage_metrics(timeframe_hours)

        requests_per_hour = (
            tracker_metrics.total_calls / timeframe_hours if timeframe_hours > 0 else 0
        )
        cost_per_req = (
            tracker_metrics.total_cost / tracker_metrics.total_calls
            if tracker_metrics.total_calls > 0
            else 0.0
        )

        return UsageMetrics(
            total_requests=tracker_metrics.total_calls,
            successful_requests=tracker_metrics.successful_calls,
            failed_requests=tracker_metrics.failed_calls,
            avg_response_time_ms=tracker_metrics.avg_response_time_ms,
            total_cost_usd=tracker_metrics.total_cost,
            cost_per_request=cost_per_req,
            requests_per_hour=requests_per_hour,
            error_rate=tracker_metrics.error_rate,
            uptime_percentage=100.0 - tracker_metrics.error_rate,
            period_start=datetime.now(timezone.utc) - timedelta(hours=timeframe_hours),
            period_end=datetime.now(timezone.utc),
        )

    def start_ab_test(
        self,
        test_name: str,
        model_a: str,
        model_b: str,
        traffic_split: float = 0.5,
        duration_hours: int = 24,
    ) -> bool:
        """Start A/B test between two models.

        Args:
            test_name: Unique name for the test
            model_a: First model to test
            model_b: Second model to test
            traffic_split: Percentage of traffic for model_a (0.0-1.0)
            duration_hours: Test duration in hours

        Returns:
            True if test started successfully
        """
        return self.ab_test_manager.start_ab_test(
            test_name, model_a, model_b, traffic_split, duration_hours
        )

    def get_ab_test_model(self, test_name: str, account_id: int) -> Optional[str]:
        """Get model to use based on A/B test configuration.

        Args:
            test_name: Name of the A/B test
            account_id: Account ID for consistent assignment

        Returns:
            Model name to use or None if no active test
        """
        return self.ab_test_manager.get_model_for_decision(test_name, account_id)

    def end_ab_test(
        self, test_name: str
    ) -> Any:  # Return type should match what ab_test_manager.end_ab_test returns
        """End an A/B test and get results.

        Args:
            test_name: Name of the test to end

        Returns:
            ABTestResult with comparison results
        """
        return self.ab_test_manager.end_ab_test(test_name)

    def get_active_ab_tests(self) -> Dict[str, Any]:
        """Get all active A/B tests.

        Returns:
            Dictionary of active tests
        """
        return self.ab_test_manager.get_active_tests()

    async def _call_llm_for_decision(self, prompt: str) -> Dict[str, Any]:
        """Make LLM API call for decision generation with retry logic.

        Args:
            prompt: Decision generation prompt

        Returns:
            LLM response data

        Raises:
            LLMAPIError: When API call fails after retries
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self._get_decision_system_prompt(),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,  # Lower temperature for more consistent decisions
                    max_tokens=2000,  # Increased for multi-asset decisions with more detailed analysis
                )

                response_time_ms = (time.time() - start_time) * 1000

                # Record successful API call
                self.metrics_tracker.record_api_call(
                    model=self.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    response_time_ms=response_time_ms,
                    success=True,
                )

                # log debug response
                logger.debug(f"LLM response: {response.choices[0].message.content}")

                return {
                    "content": response.choices[0].message.content,
                    "usage": response.usage,
                    "cost": self.metrics_tracker._calculate_cost(
                        self.model,
                        response.usage.prompt_tokens,
                        response.usage.completion_tokens,
                    ),
                }

            except Exception as e:
                last_exception = e
                response_time_ms = (
                    (time.time() - start_time) * 1000 if "start_time" in locals() else 0
                )

                # Record failed API call
                self.metrics_tracker.record_api_call(
                    model=self.model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    response_time_ms=response_time_ms,
                    success=False,
                    error=str(e),
                )

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.base_delay * (2**attempt)
                    logger.warning(
                        f"API call failed (attempt {attempt + 1}), retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"API call failed after {self.max_retries} attempts: {e}")

        raise LLMAPIError(f"API call failed after {self.max_retries} attempts: {last_exception}")

    def _validate_context(self, context: TradingContext) -> bool:
        """Validate that context has sufficient data for multi-asset decision generation.

        Args:
            context: Trading context to validate

        Returns:
            True if context is sufficient
        """
        # Validate account state
        if not context.account_state.balance_usd or context.account_state.balance_usd <= 0:
            logger.warning("Invalid account balance")
            return False

        if (
            not context.account_state.available_balance
            or context.account_state.available_balance <= 0
        ):
            logger.warning("Invalid available balance")
            return False

        # Validate multi-asset market data
        if not context.market_data.assets or len(context.market_data.assets) == 0:
            logger.warning("No asset data in context")
            return False

        # Validate each asset has minimum required data
        for symbol, asset_data in context.market_data.assets.items():
            if not asset_data.current_price or asset_data.current_price <= 0:
                logger.warning(f"Invalid price for {symbol}")
                return False

            if not asset_data.technical_indicators:
                logger.warning(f"Missing technical indicators for {symbol}")
                return False

        return True

    def _build_multi_asset_decision_prompt(
        self,
        symbols: List[str],
        context: TradingContext,
        strategy_override: Optional[str] = None,
    ) -> str:
        """Build comprehensive prompt for multi-asset trading decision generation.

        Args:
            symbols: List of trading pair symbols
            context: Multi-asset trading context
            strategy_override: Optional strategy override

        Returns:
            Formatted prompt string for multi-asset analysis
        """
        strategy = context.account_state.active_strategy
        if strategy_override:
            prompt_template = self._get_strategy_template(strategy_override)
        else:
            prompt_template = strategy.prompt_template

        account_state = context.account_state

        # Build market data section for all assets
        assets_data = []
        for symbol in symbols:
            asset_data = context.market_data.get_asset_data(symbol)
            if asset_data:
                # Format technical indicators for this asset
                indicators = asset_data.technical_indicators
                indicators_text = f"""
  Primary Interval ({context.timeframes[0]}):
    EMA-20: {", ".join([f"{v:.2f}" for v in indicators.interval.ema_20[-10:]]) if indicators.interval.ema_20 else "N/A"}
    EMA-50: {", ".join([f"{v:.2f}" for v in indicators.interval.ema_50[-10:]]) if indicators.interval.ema_50 else "N/A"}
    RSI: {", ".join([f"{v:.2f}" for v in indicators.interval.rsi[-10:]]) if indicators.interval.rsi else "N/A"}
    MACD: {", ".join([f"{v:.4f}" for v in indicators.interval.macd[-10:]]) if indicators.interval.macd else "N/A"}
    Bollinger Bands Upper: {", ".join([f"{v:.2f}" for v in indicators.interval.bb_upper[-10:]]) if indicators.interval.bb_upper else "N/A"}
    Bollinger Bands Middle: {", ".join([f"{v:.2f}" for v in indicators.interval.bb_middle[-10:]]) if indicators.interval.bb_middle else "N/A"}
    Bollinger Bands Lower: {", ".join([f"{v:.2f}" for v in indicators.interval.bb_lower[-10:]]) if indicators.interval.bb_lower else "N/A"}
  Long-Term Interval ({context.timeframes[1]}):
    EMA-20: {", ".join([f"{v:.2f}" for v in indicators.long_interval.ema_20[-10:]]) if indicators.long_interval.ema_20 else "N/A"}
    EMA-50: {", ".join([f"{v:.2f}" for v in indicators.long_interval.ema_50[-10:]]) if indicators.long_interval.ema_50 else "N/A"}
    RSI: {", ".join([f"{v:.2f}" for v in indicators.long_interval.rsi[-10:]]) if indicators.long_interval.rsi else "N/A"}
    Bollinger Bands Upper: {", ".join([f"{v:.2f}" for v in indicators.long_interval.bb_upper[-10:]]) if indicators.long_interval.bb_upper else "N/A"}
    Bollinger Bands Middle: {", ".join([f"{v:.2f}" for v in indicators.long_interval.bb_middle[-10:]]) if indicators.long_interval.bb_middle else "N/A"}
    Bollinger Bands Lower: {", ".join([f"{v:.2f}" for v in indicators.long_interval.bb_lower[-10:]]) if indicators.long_interval.bb_lower else "N/A"}
"""

                # Format funding rate if available
                funding_rate_text = ""
                if asset_data.funding_rate is not None:
                    funding_rate_text = f"Funding Rate: {asset_data.funding_rate * 100:.4f}%\n"

                asset_text = f"""
--- {symbol} ---
Current Price: ${asset_data.current_price:.2f}
24h Change: {asset_data.price_change_24h:.2f}%
24h Volume: ${asset_data.volume_24h:,.2f}
Volatility: {asset_data.volatility:.2f}%
{funding_rate_text}Trend: {asset_data.get_price_trend()}
{indicators_text}
"""
                assets_data.append(asset_text)

        # Format account performance
        perf = account_state.recent_performance
        performance_text = f"""
Total PnL: ${perf.total_pnl:.2f} ({perf.win_rate:.1f}% win rate)
Average Win: ${perf.avg_win:.2f}, Average Loss: ${abs(perf.avg_loss):.2f}
Max Drawdown: {perf.max_drawdown:.1f}%
"""

        # Format risk metrics
        risk_metrics = f"""
Value at Risk (95%): ${context.risk_metrics.var_95:.2f}
Max Drawdown: ${context.risk_metrics.max_drawdown:.2f}
Correlation Risk: {context.risk_metrics.correlation_risk:.1f}%
Concentration Risk: {context.risk_metrics.concentration_risk:.1f}%
"""

        # Format positions
        positions_text = ""
        if account_state.open_positions:
            positions_text = "\n".join(
                [
                    f"- {pos.symbol}: {pos.side} {pos.size} @ ${pos.entry_price:.2f} (PnL: {pos.percentage_pnl:.2f}%)"
                    for pos in account_state.open_positions
                ]
            )
        else:
            positions_text = "No open positions"

        # Format strategy parameters
        strategy_params = f"""
=== STRATEGY PARAMETERS ===
Max Risk per Trade: {strategy.risk_parameters.max_risk_per_trade}%
Max Daily Loss: {strategy.risk_parameters.max_daily_loss}%
Stop Loss: {strategy.risk_parameters.stop_loss_percentage}%
Take Profit Ratio: {strategy.risk_parameters.take_profit_ratio}
Max Leverage: {strategy.risk_parameters.max_leverage}x
Max Positions: {strategy.max_positions}
"""

        # Build the complete prompt
        prompt = f"""
=== MULTI-ASSET PORTFOLIO ANALYSIS ===
Analyze the following {len(symbols)} perpetual futures assets and provide a comprehensive portfolio-level trading strategy.

=== MARKET DATA FOR ALL ASSETS ===
{"".join(assets_data)}

Market Sentiment: {context.market_data.market_sentiment or "neutral"}

=== ACCOUNT INFO ===
Balance: ${account_state.balance_usd:,.2f}
Available: ${account_state.available_balance:,.2f}
Risk Exposure: {account_state.risk_exposure:.1f}%

{performance_text}

=== OPEN POSITIONS ===
{positions_text}

=== RISK METRICS ===
{risk_metrics}

{strategy_params}

=== INSTRUCTIONS ===
{prompt_template}

IMPORTANT: Analyze ALL assets and provide decisions for each. Consider:
1. Which assets show the strongest technical signals?
2. How should capital be allocated across opportunities?
3. What is the overall portfolio risk level?
4. How do the assets correlate with each other?
5. Which positions should be prioritized based on conviction and risk?

Provide a portfolio-level rationale explaining your overall trading strategy across all assets.
"""

        return prompt.strip()

    def _get_decision_system_prompt(self) -> str:
        """Get system prompt for multi-asset decision generation."""
        return """You are an expert cryptocurrency trading advisor specializing in multi-asset portfolio management for perpetual futures. Generate structured trading decisions in JSON format.

Your response must be valid JSON with the following structure for MULTI-ASSET decisions:
{
  "decisions": [
    {
      "asset": "BTCUSDT",
      "action": "buy|sell|hold|adjust_position|close_position|adjust_orders",
      "allocation_usd": 100.0,
      "tp_price": 50000.0,
      "sl_price": 45000.0,
      "exit_plan": "Take profit at resistance, stop loss below support",
      "rationale": "Detailed reasoning for this asset's decision",
      "confidence": 85,
      "risk_level": "low|medium|high"
    },
    {
      "asset": "ETHUSDT",
      "action": "hold",
      "allocation_usd": 0.0,
      "tp_price": null,
      "sl_price": null,
      "exit_plan": "Wait for better entry",
      "rationale": "Detailed reasoning for this asset's decision",
      "confidence": 60,
      "risk_level": "low"
    }
  ],
  "portfolio_rationale": "Overall strategy explaining how these decisions work together as a portfolio",
  "total_allocation_usd": 100.0,
  "portfolio_risk_level": "medium"
}

Rules:
- Provide decisions for ALL assets in the analysis
- allocation_usd must be positive number for buy/sell actions, 0 for hold
- total_allocation_usd must equal the sum of individual allocations
- tp_price and sl_price are optional but must be positive if provided
- confidence must be 0-100 for each asset
- rationale must explain reasoning for each asset
- portfolio_rationale must explain overall strategy across all assets
- Consider portfolio-level risk management and capital allocation
- Prioritize opportunities based on technical strength and conviction
- Only recommend actions you can justify with the provided data"""

    def _parse_multi_asset_decision_response(
        self,
        response_data: Dict[str, Any],
        symbols: List[str],
    ) -> TradingDecision:
        """Parse and validate LLM response into multi-asset TradingDecision.

        Args:
            response_data: LLM response data
            symbols: List of trading symbols

        Returns:
            Validated multi-asset TradingDecision

        Raises:
            ValidationError: When response cannot be parsed or validated
        """
        try:
            content = response_data["content"]

            # Try to parse JSON response
            try:
                decision_dict = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                # Try to extract JSON from text
                decision_dict = self._extract_json_from_text(content)

            # Validate multi-asset structure
            if "decisions" not in decision_dict:
                raise ValidationError("Response missing 'decisions' field for multi-asset decision")

            # Ensure all symbols have decisions
            decision_symbols = {d.get("asset") for d in decision_dict.get("decisions", [])}
            missing_symbols = set(symbols) - decision_symbols
            if missing_symbols:
                logger.warning(f"LLM did not provide decisions for: {missing_symbols}")
                # Add hold decisions for missing symbols
                for symbol in missing_symbols:
                    decision_dict["decisions"].append(
                        {
                            "asset": symbol,
                            "action": "hold",
                            "allocation_usd": 0.0,
                            "exit_plan": "No decision provided by LLM",
                            "rationale": "LLM did not analyze this asset",
                            "confidence": 0,
                            "risk_level": "low",
                        }
                    )

            # Create TradingDecision with validation
            decision = TradingDecision(**decision_dict)

            logger.debug(
                f"Successfully parsed multi-asset decision with {len(decision.decisions)} asset decisions"
            )
            return decision

        except (PydanticValidationError, KeyError, TypeError) as e:
            logger.error(f"Multi-asset decision validation failed: {e}")
            raise ValidationError(f"Invalid multi-asset decision format: {e}") from e

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text response.

        Args:
            text: Text containing JSON

        Returns:
            Parsed JSON dictionary

        Raises:
            ValidationError: When JSON cannot be extracted
        """
        # Try to find JSON in the text
        import re

        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        raise ValidationError("No valid JSON found in response")

    def _create_multi_asset_fallback_decision(self, symbols: List[str]) -> TradingDecision:
        """Create conservative multi-asset fallback decision when LLM fails.

        Args:
            symbols: List of trading symbols

        Returns:
            Conservative multi-asset TradingDecision
        """
        from ...schemas.trading_decision import AssetDecision

        # Create hold decisions for all symbols
        asset_decisions = []
        for symbol in symbols:
            asset_decisions.append(
                AssetDecision(
                    asset=symbol,
                    action="hold",
                    allocation_usd=0.0,
                    tp_price=None,
                    sl_price=None,
                    exit_plan="Hold position due to analysis failure. Will reassess when conditions improve.",
                    rationale="LLM analysis failed, defaulting to conservative hold position for this asset.",
                    confidence=0,
                    risk_level="low",
                )
            )

        return TradingDecision(
            decisions=asset_decisions,
            portfolio_rationale="LLM analysis failed, defaulting to conservative hold positions across all assets. "
            "This is a safety measure to prevent unintended trades when the analysis service is unavailable.",
            total_allocation_usd=0.0,
            portfolio_risk_level="low",
        )

    def _get_strategy_template(self, strategy_type: str) -> str:
        """Get prompt template for strategy type.

        Args:
            strategy_type: Strategy type

        Returns:
            Prompt template string
        """
        templates = {
            "conservative": """
Analyze {symbol} for conservative trading:

Market Data:
- Current Price: ${current_price:.2f}
- 24h Change: {price_change_24h:.2f}%
- Volume: {volume_24h:.2f}
- Volatility: {volatility:.2f}%

Technical Indicators:
{technical_indicators}

Account Status:
- Balance: ${balance_usd:.2f}
- Available: ${available_balance:.2f}
- Risk Exposure: {risk_exposure:.2f}%

Open Positions:
{open_positions}

Conservative Strategy Rules:
- Max risk per trade: {max_risk_per_trade}%
- Stop loss: {stop_loss_percentage}%
- Take profit ratio: {take_profit_ratio}:1
- Focus on capital preservation
- Only high-confidence setups

Generate a conservative trading decision.
""",
            "aggressive": """
Analyze {symbol} for aggressive trading:

Market Data:
- Current Price: ${current_price:.2f}
- 24h Change: {price_change_24h:.2f}%
- Volume: {volume_24h:.2f}
- Volatility: {volatility:.2f}%

Technical Indicators:
{technical_indicators}

Account Status:
- Balance: ${balance_usd:.2f}
- Available: ${available_balance:.2f}
- Risk Exposure: {risk_exposure:.2f}%

Open Positions:
{open_positions}

Aggressive Strategy Rules:
- Max risk per trade: {max_risk_per_trade}%
- Stop loss: {stop_loss_percentage}%
- Take profit ratio: {take_profit_ratio}:1
- Capitalize on momentum
- Accept higher risk for higher returns

Generate an aggressive trading decision.
""",
        }

        return templates.get(strategy_type, templates["conservative"])

    async def _test_model_connection(self) -> bool:
        """Test connection to current model.

        Returns:
            True if connection successful
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test connection. Respond with 'OK'."}],
                max_tokens=10,
                temperature=0,
            )

            return response.choices[0].message.content.strip().upper() == "OK"

        except Exception as e:
            logger.error(f"Model connection test failed: {e}")
            return False

    async def validate_authentication(self) -> bool:
        """Validate authentication with LLM server.

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: When authentication fails with detailed error information
        """
        try:
            # Check if API key is configured
            if not self.api_key or self.api_key.strip() == "":
                error_msg = (
                    f"Authentication failed: No API key configured. "
                    f"Expected OPENROUTER_API_KEY in environment, got empty string. "
                    f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
                )
                logger.error(error_msg)
                raise AuthenticationError(error_msg)

            # Test authentication with a simple API call
            test_prompt = "Authentication test - respond with 'AUTH_OK' if authenticated."

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": test_prompt}],
                max_tokens=10,
                temperature=0,
            )

            # Check if authentication was successful
            response_content = response.choices[0].message.content.strip()
            if "AUTH_OK" in response_content.upper():
                logger.info("LLM server authentication successful")
                return True
            else:
                # Authentication failed - provide comprehensive error details
                error_msg = (
                    f"Authentication failed: LLM server rejected credentials. "
                    f"Server response: '{response_content}'. "
                    f"Expected: 'AUTH_OK', Actual: '{response_content}'. "
                    f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
                )
                logger.error(error_msg)
                raise AuthenticationError(error_msg)

        except Exception as e:
            # Provide comprehensive authentication failure details
            error_msg = (
                f"Authentication failed: {str(e)}. "
                f"Server: {self.base_url}, "
                f"Model: {self.model}. "
                f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
            )
            logger.error(error_msg)
            raise AuthenticationError(error_msg) from e


# Global service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
