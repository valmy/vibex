"""
Usage metrics tracking for LLM service.

Tracks API usage, costs, performance, and decision accuracy.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ...core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class APICall:
    """Individual API call record."""

    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time_ms: float
    cost: Optional[float] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class UsageMetrics:
    """Usage metrics summary."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time_ms: float = 0.0
    calls_per_model: Dict[str, int] = field(default_factory=dict)
    error_rate: float = 0.0


@dataclass
class HealthStatus:
    """Health status of LLM service."""

    is_healthy: bool
    last_successful_call: Optional[datetime] = None
    consecutive_failures: int = 0
    circuit_breaker_open: bool = False
    avg_response_time_ms: float = 0.0
    error_rate_1h: float = 0.0


class LLMMetricsTracker:
    """Tracks LLM service metrics and performance."""

    def __init__(self, max_history: int = 10000):
        """
        Initialize metrics tracker.

        Args:
            max_history: Maximum number of API calls to keep in history
        """
        self.max_history = max_history
        self.api_calls: deque[APICall] = deque(maxlen=max_history)
        self.model_costs = {
            "openai/gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
            "openai/gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
            "anthropic/claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "x-ai/grok-beta": {"input": 0.005, "output": 0.015},
            "deepseek/deepseek-r1": {"input": 0.0014, "output": 0.0028},
        }

    def record_api_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        response_time_ms: float,
        success: bool = True,
        error: Optional[str] = None,
    ) -> APICall:
        """
        Record an API call.

        Args:
            model: Model used for the call
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            response_time_ms: Response time in milliseconds
            success: Whether the call was successful
            error: Error message if call failed

        Returns:
            APICall record
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        call = APICall(
            timestamp=datetime.now(timezone.utc),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_time_ms=response_time_ms,
            cost=cost,
            success=success,
            error=error,
        )

        self.api_calls.append(call)

        if success:
            logger.debug(
                f"API call recorded: {model}, {total_tokens} tokens, {response_time_ms:.2f}ms"
            )
        else:
            logger.warning(f"Failed API call recorded: {model}, error: {error}")

        return call

    def get_usage_metrics(self, timeframe_hours: int = 24) -> UsageMetrics:
        """
        Get usage metrics for specified timeframe.

        Args:
            timeframe_hours: Hours to look back for metrics

        Returns:
            UsageMetrics summary
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=timeframe_hours)
        recent_calls = [call for call in self.api_calls if call.timestamp >= cutoff_time]

        if not recent_calls:
            return UsageMetrics()

        total_calls = len(recent_calls)
        successful_calls = sum(1 for call in recent_calls if call.success)
        failed_calls = total_calls - successful_calls
        total_tokens = sum(call.total_tokens for call in recent_calls)
        total_cost = sum(call.cost or 0 for call in recent_calls)
        avg_response_time = sum(call.response_time_ms for call in recent_calls) / total_calls

        calls_per_model: Dict[str, int] = defaultdict(int)
        for call in recent_calls:
            calls_per_model[call.model] += 1

        error_rate = (failed_calls / total_calls) * 100 if total_calls > 0 else 0

        return UsageMetrics(
            total_calls=total_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            total_tokens=total_tokens,
            total_cost=total_cost,
            avg_response_time_ms=avg_response_time,
            calls_per_model=dict(calls_per_model),
            error_rate=error_rate,
        )

    def get_health_status(self) -> HealthStatus:
        """
        Get current health status of LLM service.

        Returns:
            HealthStatus summary
        """
        if not self.api_calls:
            return HealthStatus(is_healthy=False)

        recent_calls = list(self.api_calls)[-100:]  # Last 100 calls
        successful_calls = [call for call in recent_calls if call.success]

        last_successful_call = None
        if successful_calls:
            last_successful_call = max(successful_calls, key=lambda x: x.timestamp).timestamp

        # Count consecutive failures from the end
        consecutive_failures = 0
        for call in reversed(recent_calls):
            if call.success:
                break
            consecutive_failures += 1

        # Calculate error rate for last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_hour_calls = [call for call in recent_calls if call.timestamp >= one_hour_ago]
        error_rate_1h = 0.0
        if recent_hour_calls:
            failed_in_hour = sum(1 for call in recent_hour_calls if not call.success)
            error_rate_1h = (failed_in_hour / len(recent_hour_calls)) * 100

        avg_response_time = 0.0
        if recent_calls:
            avg_response_time = sum(call.response_time_ms for call in recent_calls) / len(
                recent_calls
            )

        is_healthy = (
            consecutive_failures < 5
            and error_rate_1h < 50
            and avg_response_time < 30000  # 30 seconds
        )

        return HealthStatus(
            is_healthy=is_healthy,
            last_successful_call=last_successful_call,
            consecutive_failures=consecutive_failures,
            circuit_breaker_open=False,  # Will be updated by circuit breaker
            avg_response_time_ms=avg_response_time,
            error_rate_1h=error_rate_1h,
        )

    def _calculate_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> Optional[float]:
        """
        Calculate cost for API call.

        Args:
            model: Model used
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Cost in USD or None if model not found
        """
        if model not in self.model_costs:
            return None

        costs = self.model_costs[model]
        input_cost = (prompt_tokens / 1000) * costs["input"]
        output_cost = (completion_tokens / 1000) * costs["output"]

        return input_cost + output_cost

    def get_model_performance(self, model: str, timeframe_hours: int = 24) -> Dict[str, Any]:
        """
        Get performance metrics for specific model.

        Args:
            model: Model to analyze
            timeframe_hours: Hours to look back

        Returns:
            Performance metrics dictionary
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=timeframe_hours)
        model_calls = [
            call for call in self.api_calls if call.model == model and call.timestamp >= cutoff_time
        ]

        if not model_calls:
            return {"error": "No calls found for model"}

        successful_calls = [call for call in model_calls if call.success]

        return {
            "total_calls": len(model_calls),
            "successful_calls": len(successful_calls),
            "success_rate": (len(successful_calls) / len(model_calls)) * 100,
            "avg_response_time_ms": sum(call.response_time_ms for call in model_calls)
            / len(model_calls),
            "total_tokens": sum(call.total_tokens for call in model_calls),
            "total_cost": sum(call.cost or 0 for call in model_calls),
        }

    def clear_old_records(self, days: int = 7) -> None:
        """
        Clear records older than specified days.

        Args:
            days: Number of days to keep
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        original_count = len(self.api_calls)

        # Convert to list, filter, and convert back to deque
        filtered_calls = [call for call in self.api_calls if call.timestamp >= cutoff_time]
        self.api_calls.clear()
        self.api_calls.extend(filtered_calls)

        removed_count = original_count - len(self.api_calls)
        if removed_count > 0:
            logger.info(f"Cleared {removed_count} old API call records")


# Global metrics tracker instance
_metrics_tracker: Optional[LLMMetricsTracker] = None


def get_metrics_tracker() -> LLMMetricsTracker:
    """Get or create the metrics tracker instance."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = LLMMetricsTracker()
    return _metrics_tracker
