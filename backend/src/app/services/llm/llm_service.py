"""
LLM Service for market analysis and trading insights.

Integrates with OpenRouter API for LLM-powered analysis.
Enhanced with structured decision generation, multi-model support,
and comprehensive error handling.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError as PydanticValidationError

from ...core.config import config
from ...core.logging import get_logger
from ...schemas.trading_decision import DecisionResult, TradingContext, TradingDecision
from .ab_testing import get_ab_test_manager
from .circuit_breaker import CircuitBreaker
from .llm_exceptions import (
    InsufficientDataError,
    LLMAPIError,
    ModelSwitchError,
    ValidationError,
)
from .llm_metrics import HealthStatus, UsageMetrics, get_metrics_tracker

logger = get_logger(__name__)


class LLMService:
    """Service for LLM-powered market analysis and trading decisions."""

    def __init__(self):
        """Initialize the LLM Service."""
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL
        self.model = config.LLM_MODEL
        self.referer = config.OPENROUTER_REFERER
        self.app_title = config.OPENROUTER_APP_TITLE

        # Initialize OpenRouter client (lazy loaded)
        self._client = None

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
        self, symbol: str, market_data: Dict[str, Any], additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze market data and provide trading insights.

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
        """
        Get trading signal based on market analysis.

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
        self, market_data_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Summarize overall market conditions.

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
        self, symbol: str, market_data: Dict[str, Any], additional_context: Optional[str] = None
    ) -> str:
        """Build market analysis prompt."""
        prompt = f"""
Analyze the following market data for {symbol}:

Current Price: ${market_data.get('close', 0):.2f}
24h High: ${market_data.get('high', 0):.2f}
24h Low: ${market_data.get('low', 0):.2f}
Volume: {market_data.get('volume', 0):.2f}
Open: ${market_data.get('open', 0):.2f}

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

Price: ${market_data.get('close', 0):.2f}
24h Change: {market_data.get('change_percent', 0):.2f}%
Volume: {market_data.get('volume', 0):.2f}
RSI: {market_data.get('rsi', 50):.2f}
MACD: {market_data.get('macd', 0):.4f}

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
        symbol: str,
        context: TradingContext,
        strategy_override: Optional[str] = None,
        ab_test_name: Optional[str] = None,
    ) -> DecisionResult:
        """
        Generate structured trading decision using LLM analysis.

        Args:
            symbol: Trading pair symbol
            context: Complete trading context
            strategy_override: Optional strategy to override account strategy
            ab_test_name: Optional A/B test name for model selection

        Returns:
            DecisionResult with structured decision and validation status

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

            # Build decision prompt
            prompt = self._build_decision_prompt(symbol, context, strategy_override)

            # Generate decision with circuit breaker protection
            decision_data = await self.circuit_breaker.call(self._call_llm_for_decision, prompt)

            # Parse and validate decision
            decision = self._parse_decision_response(decision_data, symbol)

            processing_time_ms = (time.time() - start_time) * 1000

            # Record A/B testing metrics if applicable
            if ab_test_name and self.model != original_model:
                self.ab_test_manager.record_decision_performance(
                    model_name=self.model,
                    confidence=decision.confidence,
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

            logger.info(f"Trading decision generated for {symbol}: {decision.action}")
            return result

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Error generating trading decision for {symbol}: {e}")

            # Record A/B testing failure if applicable
            if ab_test_name and self.model != original_model:
                self.ab_test_manager.record_decision_performance(
                    model_name=self.model,
                    confidence=0,
                    response_time_ms=processing_time_ms,
                    success=False,
                )

            # Return fallback decision
            fallback_decision = self._create_fallback_decision(symbol)
            
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
        """
        Switch to a different LLM model.

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
            raise ModelSwitchError(f"Model switch failed: {e}")

    async def validate_api_health(self) -> HealthStatus:
        """
        Validate API health and connectivity.

        Returns:
            HealthStatus with current service health
        """
        try:
            health_status = self.metrics_tracker.get_health_status()
            health_status.circuit_breaker_open = self.circuit_breaker.is_open

            # Test connectivity if needed
            if health_status.consecutive_failures > 3:
                test_successful = await self._test_model_connection()
                if not test_successful:
                    health_status.is_healthy = False

            return health_status

        except Exception as e:
            logger.error(f"Error validating API health: {e}")
            return HealthStatus(
                is_healthy=False,
                consecutive_failures=999,
                circuit_breaker_open=self.circuit_breaker.is_open,
            )

    def get_usage_metrics(self, timeframe_hours: int = 24) -> UsageMetrics:
        """
        Get usage metrics for specified timeframe.

        Args:
            timeframe_hours: Hours to look back for metrics

        Returns:
            UsageMetrics summary
        """
        return self.metrics_tracker.get_usage_metrics(timeframe_hours)

    def start_ab_test(
        self,
        test_name: str,
        model_a: str,
        model_b: str,
        traffic_split: float = 0.5,
        duration_hours: int = 24,
    ) -> bool:
        """
        Start A/B test between two models.

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
        """
        Get model to use based on A/B test configuration.

        Args:
            test_name: Name of the A/B test
            account_id: Account ID for consistent assignment

        Returns:
            Model name to use or None if no active test
        """
        return self.ab_test_manager.get_model_for_decision(test_name, account_id)

    def end_ab_test(self, test_name: str):
        """
        End an A/B test and get results.

        Args:
            test_name: Name of the test to end

        Returns:
            ABTestResult with comparison results
        """
        return self.ab_test_manager.end_ab_test(test_name)

    def get_active_ab_tests(self) -> Dict:
        """
        Get all active A/B tests.

        Returns:
            Dictionary of active tests
        """
        return self.ab_test_manager.get_active_tests()

    async def _call_llm_for_decision(self, prompt: str) -> Dict[str, Any]:
        """
        Make LLM API call for decision generation with retry logic.

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
                    max_tokens=1000,
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
        """
        Validate that context has sufficient data for decision generation.

        Args:
            context: Trading context to validate

        Returns:
            True if context is sufficient
        """
        required_fields = [
            context.market_data.current_price,
            context.account_state.balance_usd,
            context.account_state.available_balance,
        ]

        return all(field is not None and field > 0 for field in required_fields)

    def _build_decision_prompt(
        self,
        symbol: str,
        context: TradingContext,
        strategy_override: Optional[str] = None,
    ) -> str:
        """
        Build comprehensive prompt for trading decision generation.

        Args:
            symbol: Trading pair symbol
            context: Trading context
            strategy_override: Optional strategy override

        Returns:
            Formatted prompt string
        """
        strategy = context.account_state.active_strategy
        if strategy_override:
            # Use strategy override template if provided
            prompt_template = self._get_strategy_template(strategy_override)
        else:
            prompt_template = strategy.prompt_template

        market_data = context.market_data
        account_state = context.account_state

        # Format technical indicators
        indicators = market_data.technical_indicators
        ema_20 = indicators.ema_20 if indicators.ema_20 is not None else 'N/A'
        ema_50 = indicators.ema_50 if indicators.ema_50 is not None else 'N/A'
        macd = indicators.macd if indicators.macd is not None else 'N/A'
        macd_signal = indicators.macd_signal if indicators.macd_signal is not None else 'N/A'
        rsi = indicators.rsi if indicators.rsi is not None else 'N/A'
        bb_upper = indicators.bb_upper if indicators.bb_upper is not None else 'N/A'
        bb_middle = indicators.bb_middle if indicators.bb_middle is not None else 'N/A'
        bb_lower = indicators.bb_lower if indicators.bb_lower is not None else 'N/A'
        atr = indicators.atr if indicators.atr is not None else 'N/A'
        
        # Format price history
        price_history_text = "\n".join(
            [f"- {ph.timestamp}: ${ph.price:.2f} (Vol: {ph.volume:.2f})" 
             for ph in market_data.price_history[-10:]]  # Last 10 price points
        )
        
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
Correlation Risk: {context.risk_metrics.correlation_risk*100:.1f}%
Concentration Risk: {context.risk_metrics.concentration_risk*100:.1f}%
"""

        # Format indicators
        indicators_text = f"""
=== TECHNICAL INDICATORS ===
EMA: 20-period: {ema_20}, 50-period: {ema_50}
MACD: {macd} (Signal: {macd_signal})
RSI: {rsi}
Bollinger Bands: Upper {bb_upper}, Middle {bb_middle}, Lower {bb_lower}
ATR: {atr}
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
"""

        # Build the complete prompt
        prompt = f"""
=== MARKET DATA ===
Symbol: {symbol}
Current Price: ${market_data.current_price:.2f}
24h Change: {market_data.price_change_24h:.2f}%
24h Volume: ${market_data.volume_24h:,.2f}
Volatility: {market_data.volatility:.2f}%

=== ACCOUNT INFO ===
Balance: ${account_state.balance_usd:,.2f}
Available: ${account_state.available_balance:,.2f}
Risk Exposure: {account_state.risk_exposure:.1f}%

{performance_text}
{price_history_text}
{indicators_text}
{strategy_params}

=== OPEN POSITIONS ===
{positions_text}

=== RISK METRICS ===
{risk_metrics}

=== INSTRUCTIONS ===
{strategy.prompt_template}
"""

        return prompt.strip()

    def _get_decision_system_prompt(self) -> str:
        """Get system prompt for decision generation."""
        return """You are an expert cryptocurrency trading advisor. Generate structured trading decisions in JSON format.

Your response must be valid JSON with the following structure:
{
  "asset": "BTCUSDT",
  "action": "buy|sell|hold|adjust_position|close_position|adjust_orders",
  "allocation_usd": 100.0,
  "tp_price": 50000.0,
  "sl_price": 45000.0,
  "exit_plan": "Take profit at resistance, stop loss below support",
  "rationale": "Detailed reasoning for the decision",
  "confidence": 85,
  "risk_level": "low|medium|high"
}

Rules:
- allocation_usd must be positive number
- tp_price and sl_price are optional but must be positive if provided
- confidence must be 0-100
- rationale must explain your reasoning clearly
- Consider risk management and position sizing
- Only recommend actions you can justify with the provided data"""

    def _parse_decision_response(
        self, response_data: Dict[str, Any], symbol: str
    ) -> TradingDecision:
        """
        Parse and validate LLM response into TradingDecision.

        Args:
            response_data: LLM response data
            symbol: Trading symbol

        Returns:
            Validated TradingDecision

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

            # Validate required fields
            if "asset" not in decision_dict:
                decision_dict["asset"] = symbol

            # Create TradingDecision with validation
            decision = TradingDecision(**decision_dict)

            logger.debug(f"Successfully parsed decision: {decision.action} for {decision.asset}")
            return decision

        except (PydanticValidationError, KeyError, TypeError) as e:
            logger.error(f"Decision validation failed: {e}")
            raise ValidationError(f"Invalid decision format: {e}")

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from text response.

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

    def _create_fallback_decision(self, symbol: str) -> TradingDecision:
        """
        Create conservative fallback decision when LLM fails.

        Args:
            symbol: Trading symbol

        Returns:
            Conservative TradingDecision
        """
        return TradingDecision(
            asset=symbol,
            action="hold",
            allocation_usd=0.0,
            position_adjustment=None,
            order_adjustment=None,
            tp_price=None,
            sl_price=None,
            exit_plan="Hold position due to analysis failure. Will reassess when conditions improve.",
            rationale="LLM analysis failed, defaulting to conservative hold position. "
                    "This is a safety measure to prevent unintended trades when the analysis service is unavailable.",
            confidence=0,
            risk_level="low",
        )

    def _get_strategy_template(self, strategy_type: str) -> str:
        """
        Get prompt template for strategy type.

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
        """
        Test connection to current model.

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


# Global service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
