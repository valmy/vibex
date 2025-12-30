"""
LLM Service for market analysis and trading insights.

Integrates with OpenRouter API for LLM-powered analysis.
Enhanced with structured decision generation, multi-model support,
and comprehensive error handling.
"""

import asyncio
import json
import re
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

        # Initialize messages history
        messages = [
            {
                "role": "system",
                "content": self._get_decision_system_prompt(),
            },
            {"role": "user", "content": prompt},
        ]

        # Max loop for tool calls to prevent infinite loops
        max_tool_loops = 20

        for attempt in range(self.max_retries):
            attempt_start_time = time.time()
            try:
                # Reset conversation state for each retry attempt
                current_messages = list(messages)
                tool_loop_count = 0

                while tool_loop_count < max_tool_loops:
                    (
                        result,
                        updated_messages,
                        should_continue,
                    ) = await self._execute_decision_loop_step(current_messages)

                    if not should_continue:
                        return result

                    current_messages = updated_messages
                    tool_loop_count += 1

                # End of while loop
                logger.error("Max tool loops reached without final content")
                raise LLMAPIError("Max tool loops reached without final content")

            except Exception as e:
                last_exception = e
                response_time_ms = (time.time() - attempt_start_time) * 1000

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

    async def _execute_decision_loop_step(
        self, current_messages: List[Dict[str, Any]]
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
        """Execute a single step of the decision loop.

        Returns:
            Tuple of (result, updated_messages, should_continue)
        """
        start_time = time.time()

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=current_messages,
            temperature=0.3,
            max_tokens=10000,
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

        message = response.choices[0].message

        # debug logging
        logger.debug(f"LLM response type: {type(message)}")
        logger.debug(f"Tool calls present: {bool(message.tool_calls)}")

        # Handle Tool Calls (DeepSeek R1 Thinking via Tool)
        if message.tool_calls:
            return await self._handle_tool_calls(message, current_messages)

        # Handle Content and Native Reasoning
        return await self._handle_content_response(message, current_messages, response)

    async def _handle_tool_calls(
        self, message: Any, current_messages: List[Dict[str, Any]]
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
        """Process tool calls from the LLM."""
        # Append the assistant's message with tool calls
        current_messages.append(message)

        for tool_call in message.tool_calls:
            if tool_call.function.name == "deepseek_reasoner":
                args_str = tool_call.function.arguments
                try:
                    args = json.loads(args_str)
                    reasoning = args.get("reasoning", "")
                    is_final = args.get("final", False)

                    if reasoning:
                        logger.debug(f"DeepSeek R1 Tool Reasoning: {reasoning[:200]}...")

                    if is_final:
                        logger.debug("DeepSeek R1 thinking finished (final=True)")

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse deepseek_reasoner arguments: {args_str}")

            # Append tool response (required by OpenAI API)
            current_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "continue",
                }
            )

        return {}, current_messages, True

    async def _handle_content_response(
        self, message: Any, current_messages: List[Dict[str, Any]], response: Any
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
        """Process content response from the LLM."""
        content = getattr(message, "content", None) or ""
        reasoning_content = (
            getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None) or ""
        )

        if reasoning_content:
            logger.debug(f"DeepSeek R1 Native Reasoning found (length: {len(reasoning_content)})")

        # Check if we have final content
        if content:
            logger.debug(f"Content received (length: {len(content)} chars)")

            # Validate if it looks like the final JSON response
            if '"decisions"' in content or "'decisions'" in content:
                logger.debug("Content contains 'decisions' key, accepting as final response")
                return (
                    {
                        "content": content,
                        "usage": response.usage,
                        "cost": self.metrics_tracker._calculate_cost(
                            self.model,
                            response.usage.prompt_tokens,
                            response.usage.completion_tokens,
                        ),
                    },
                    current_messages,
                    False,
                )
            else:
                # Content present but missing 'decisions'. It's likely intermediate reasoning text.
                logger.debug("Content missing 'decisions' key. Treating as intermediate reasoning.")
                current_messages.append({"role": "assistant", "content": content})
                # Force the model to output JSON
                current_messages.append(
                    {
                        "role": "user",
                        "content": "Please now provide the final decision in valid JSON format with the 'decisions' key.",
                    }
                )
                return {}, current_messages, True

        # If content is empty but we have reasoning_content, it's an intermediate thinking step
        if not content and reasoning_content:
            logger.debug("Received native reasoning content but no final content. Continuing loop.")
            # Append reasoning as assistant message so model knows what it thought and continues
            current_messages.append({"role": "assistant", "content": reasoning_content})
            return {}, current_messages, True

        # If we got here: no tool calls, no content, and no reasoning content.
        logger.warning("Received empty response from LLM (no content, no tool calls, no reasoning)")
        # break loop to trigger retry
        raise LLMAPIError("Received empty response from LLM")

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
        return """You are an expert cryptocurrency trading advisor specializing in multi-asset portfolio management for perpetual futures.

CRITICAL: You must respond with ONLY valid JSON. No explanations, no thinking, no text before or after the JSON.

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
- Respond with ONLY JSON - no text before, no text after
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

            # Log raw response for debugging reasoning model outputs
            logger.debug(f"Raw LLM response (first 500 chars): {content[:500]}")
            logger.debug(f"Raw LLM response length: {len(content)} chars")

            # Try to parse JSON directly first (works if response is pure JSON or JSON in code blocks)
            try:
                decision_dict = json.loads(content)
                logger.debug("Successfully parsed JSON directly from response")
            except json.JSONDecodeError:
                # Try to extract JSON from text (handles code blocks, thinking content, etc.)
                logger.debug("Direct JSON parse failed, trying extraction methods...")
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

    def _remove_thinking_content(self, text: str) -> str:
        """Remove thinking/reasoning content from LLM responses.

        Reasoning models like deepseek-r1 often include thinking content before
        the actual JSON response. This method strips that content.

        Args:
            text: Raw LLM response text

        Returns:
            Text with thinking content removed
        """

        original_length = len(text)
        logger.debug(
            f"Processing response for thinking removal (original length: {original_length})"
        )

        patterns = [
            (r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
            (r"\\boxed\{[^}]*\}", 0),
            (r"(?:Reasoning|Thinking)[:\s]+.*?(?=\{|```json|$)", re.IGNORECASE | re.DOTALL),
            (r"<\|reserved_\d+\|>.*?<\|reserved_\d+\|>", re.DOTALL | re.IGNORECASE),
            (r"<\|im_start\|>thinking.*?<\|im_end\|>", re.DOTALL | re.IGNORECASE),
            (r"Answer[:\s]+.*?(?=\{|```json|$)", re.IGNORECASE | re.DOTALL),
            (
                r"^(?:We are|Let me|Based on|Considering|After|I will|I can|First|Seeing that|For this|In this|As we|The |To )[^\n{]*(?=\n(?:```json|\{))",
                re.IGNORECASE | re.MULTILINE,
            ),
            (r"### Thinking.*?###", re.DOTALL | re.IGNORECASE),
            (r"\*\*Thinking:.*?\*\*", re.DOTALL | re.IGNORECASE),
            (r"Thinking Process:.*?(?=\{|```)", re.DOTALL | re.IGNORECASE),
            (
                r"\n\s*(?:Let me|Here's|Now|Based on|After|First|Seeing that|In summary)[^.]*\n(?=```)",
                re.IGNORECASE,
            ),
        ]

        for pattern, flags in patterns:
            text = re.sub(pattern, "", text, flags=flags)

        # Clean up extra whitespace and newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        removed_length = original_length - len(text)
        logger.debug(f"Removed {removed_length} characters of thinking content")

        return text

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text response."""
        logger.debug(f"Extracting JSON from text (length: {len(text)} chars)")

        # 0. Clean thinking content first to avoid false positives
        text = self._remove_thinking_content(text)

        # 1. Try to extract JSON from code blocks (most reliable)
        code_block_json = self._extract_json_from_code_blocks(text)
        if code_block_json:
            return code_block_json

        # 2. Comprehensive search for JSON objects
        scanned_json = self._scan_for_json_objects(text)
        if scanned_json:
            return scanned_json

        # 3. Fall back to regex for small/nested structures if the above failed
        regex_json = self._extract_json_via_regex(text)
        if regex_json:
            return regex_json

        raise ValidationError("No valid JSON found in response")

    def _extract_json_from_code_blocks(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract JSON from markdown code blocks."""

        code_block_patterns = [
            r"```(?:json)?\s*(\{[\s\S]*?\})\s*```",  # Code block with JSON
            r"```(?:json)?\s*(\[.*?\]\n)\s*```",  # Code block with JSON array
        ]

        for pattern in code_block_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    logger.debug("Successfully parsed JSON from code block")
                    return parsed
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse JSON from code block: {e}")
                    continue
        return None

    def _extract_json_via_regex(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON using regex as a last resort."""

        logger.debug("Falling back to regex extraction")
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and "decisions" in parsed:
                    logger.debug("Found JSON with 'decisions' key via regex")
                    return parsed
            except json.JSONDecodeError:
                continue

        # Return any valid JSON from regex if no 'decisions' found
        for match in matches:
            try:
                parsed = json.loads(match)
                logger.debug(f"Found JSON keys: {list(parsed.keys())} via regex")
                return parsed
            except json.JSONDecodeError:
                continue
        return None

    def _scan_for_json_objects(self, text: str) -> Optional[Dict[str, Any]]:
        """Scan text for valid JSON objects by finding braces."""

        valid_objects = []
        start_indices = [m.start() for m in re.finditer(r"\{", text)]

        if len(start_indices) > 50:
            logger.debug(f"Found {len(start_indices)} start positions, checking all")

        for start_idx in start_indices:
            obj = self._parse_json_at_start_index(text, start_idx)
            if obj:
                valid_objects.append(obj)
                if obj["has_decisions"]:
                    break

        if valid_objects:
            valid_objects.sort(key=lambda x: x["score"], reverse=True)
            best_match = valid_objects[0]
            logger.debug(
                f"Found {len(valid_objects)} valid JSON objects. Best match score: {best_match['score']}"
            )
            return best_match["parsed"]

        return None

    def _parse_json_at_start_index(self, text: str, start_idx: int) -> Optional[Dict[str, Any]]:
        """Try to parse a JSON object starting at a specific index."""
        end_idx = text.rfind("}")
        if end_idx == -1 or end_idx <= start_idx or (end_idx - start_idx < 10):
            return None

        current_end = end_idx
        max_shrink_attempts = 20
        attempts = 0

        while current_end > start_idx and attempts < max_shrink_attempts:
            potential_json = text[start_idx : current_end + 1]
            try:
                parsed = json.loads(potential_json)
                score = 0
                has_decisions = False
                if isinstance(parsed, dict):
                    if "decisions" in parsed:
                        score += 1000
                        has_decisions = True
                    score += len(potential_json)

                return {
                    "parsed": parsed,
                    "score": score,
                    "has_decisions": has_decisions,
                    "length": len(potential_json),
                }
            except json.JSONDecodeError:
                current_end = text.rfind("}", start_idx, current_end)
                attempts += 1
        return None

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
        import openai

        timestamp = datetime.now(timezone.utc).isoformat()

        if not self.api_key or self.api_key.strip() == "":
            error_msg = (
                f"Authentication failed: No API key configured. "
                f"Expected OPENROUTER_API_KEY in environment, got empty string. "
                f"Timestamp: {timestamp}"
            )
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

        try:
            # Use a lightweight API call to check authentication.
            # A successful call to `models.list()` confirms the API key is valid.
            await self.client.models.list()
            logger.info("LLM server authentication successful")
            return True
        except openai.AuthenticationError as e:
            error_msg = (
                f"Authentication failed: LLM server rejected credentials. "
                f"Error: {str(e)}. Server: {self.base_url}. "
                f"Timestamp: {timestamp}"
            )
            logger.error(error_msg)
            raise AuthenticationError(error_msg) from e
        except openai.APIConnectionError as e:
            error_msg = (
                f"Authentication failed: Could not connect to LLM server. "
                f"Error: {str(e)}. Server: {self.base_url}. "
                f"Timestamp: {timestamp}"
            )
            logger.error(error_msg)
            raise AuthenticationError(error_msg) from e
        except Exception as e:
            # Catch other unexpected exceptions during authentication validation.
            error_msg = (
                f"Authentication validation failed with an unexpected error: {str(e)}. "
                f"Server: {self.base_url}, Model: {self.model}. "
                f"Timestamp: {timestamp}"
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
