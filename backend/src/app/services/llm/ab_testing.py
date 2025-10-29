"""
A/B testing functionality for LLM model comparison.

Provides capabilities to compare different models and track performance.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ...core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ABTestResult:
    """Result of an A/B test comparison."""
    model_a: str
    model_b: str
    model_a_performance: Dict
    model_b_performance: Dict
    winner: Optional[str] = None
    confidence_level: float = 0.0
    test_duration_hours: float = 0.0
    total_decisions: int = 0


@dataclass
class ModelPerformance:
    """Performance metrics for a model in A/B testing."""
    model_name: str
    total_decisions: int = 0
    successful_decisions: int = 0
    avg_confidence: float = 0.0
    avg_response_time_ms: float = 0.0
    total_cost: float = 0.0
    decision_accuracy: float = 0.0  # Based on actual trading outcomes
    last_updated: datetime = field(default_factory=datetime.utcnow)


class ABTestManager:
    """Manages A/B testing for LLM models."""

    def __init__(self):
        """Initialize A/B test manager."""
        self.active_tests: Dict[str, Dict] = {}
        self.model_performance: Dict[str, ModelPerformance] = {}
        self.test_results: List[ABTestResult] = []

    def start_ab_test(
        self,
        test_name: str,
        model_a: str,
        model_b: str,
        traffic_split: float = 0.5,
        duration_hours: int = 24,
    ) -> bool:
        """
        Start an A/B test between two models.

        Args:
            test_name: Unique name for the test
            model_a: First model to test
            model_b: Second model to test
            traffic_split: Percentage of traffic for model_a (0.0-1.0)
            duration_hours: Test duration in hours

        Returns:
            True if test started successfully
        """
        if test_name in self.active_tests:
            logger.warning(f"A/B test '{test_name}' already exists")
            return False

        self.active_tests[test_name] = {
            "model_a": model_a,
            "model_b": model_b,
            "traffic_split": traffic_split,
            "start_time": datetime.utcnow(),
            "end_time": datetime.utcnow() + timedelta(hours=duration_hours),
            "decisions_a": 0,
            "decisions_b": 0,
        }

        # Initialize performance tracking
        if model_a not in self.model_performance:
            self.model_performance[model_a] = ModelPerformance(model_name=model_a)
        if model_b not in self.model_performance:
            self.model_performance[model_b] = ModelPerformance(model_name=model_b)

        logger.info(f"Started A/B test '{test_name}': {model_a} vs {model_b}")
        return True

    def get_model_for_decision(self, test_name: str, account_id: int) -> Optional[str]:
        """
        Get model to use for decision based on A/B test configuration.

        Args:
            test_name: Name of the A/B test
            account_id: Account ID for consistent assignment

        Returns:
            Model name to use or None if test not active
        """
        if test_name not in self.active_tests:
            return None

        test = self.active_tests[test_name]

        # Check if test is still active
        if datetime.utcnow() > test["end_time"]:
            logger.info(f"A/B test '{test_name}' has ended")
            return None

        # Use account ID for consistent assignment
        # This ensures the same account always gets the same model
        random.seed(account_id)

        if random.random() < test["traffic_split"]:
            test["decisions_a"] += 1
            return test["model_a"]
        else:
            test["decisions_b"] += 1
            return test["model_b"]

    def record_decision_performance(
        self,
        model_name: str,
        confidence: float,
        response_time_ms: float,
        cost: Optional[float] = None,
        success: bool = True,
    ):
        """
        Record performance metrics for a model decision.

        Args:
            model_name: Name of the model
            confidence: Decision confidence score
            response_time_ms: Response time in milliseconds
            cost: API cost for the decision
            success: Whether the decision was successful
        """
        if model_name not in self.model_performance:
            self.model_performance[model_name] = ModelPerformance(model_name=model_name)

        perf = self.model_performance[model_name]
        perf.total_decisions += 1

        if success:
            perf.successful_decisions += 1

        # Update running averages
        total = perf.total_decisions
        perf.avg_confidence = ((perf.avg_confidence * (total - 1)) + confidence) / total
        perf.avg_response_time_ms = ((perf.avg_response_time_ms * (total - 1)) + response_time_ms) / total

        if cost:
            perf.total_cost += cost

        perf.last_updated = datetime.utcnow()

    def record_decision_outcome(
        self,
        model_name: str,
        was_profitable: bool,
        actual_return: float,
    ):
        """
        Record actual trading outcome for decision accuracy calculation.

        Args:
            model_name: Name of the model
            was_profitable: Whether the trade was profitable
            actual_return: Actual return percentage
        """
        if model_name not in self.model_performance:
            return

        perf = self.model_performance[model_name]

        # Simple accuracy calculation based on profitability
        # This could be enhanced with more sophisticated metrics
        if perf.total_decisions > 0:
            current_accuracy = perf.decision_accuracy * (perf.total_decisions - 1)
            new_accuracy = current_accuracy + (1.0 if was_profitable else 0.0)
            perf.decision_accuracy = new_accuracy / perf.total_decisions

    def end_ab_test(self, test_name: str) -> Optional[ABTestResult]:
        """
        End an A/B test and calculate results.

        Args:
            test_name: Name of the test to end

        Returns:
            ABTestResult with comparison results
        """
        if test_name not in self.active_tests:
            logger.warning(f"A/B test '{test_name}' not found")
            return None

        test = self.active_tests[test_name]
        model_a = test["model_a"]
        model_b = test["model_b"]

        # Get performance data
        perf_a = self.model_performance.get(model_a)
        perf_b = self.model_performance.get(model_b)

        if not perf_a or not perf_b:
            logger.error(f"Performance data missing for A/B test '{test_name}'")
            return None

        # Calculate test duration
        duration = datetime.utcnow() - test["start_time"]
        duration_hours = duration.total_seconds() / 3600

        # Create performance dictionaries
        model_a_performance = {
            "total_decisions": perf_a.total_decisions,
            "success_rate": (perf_a.successful_decisions / perf_a.total_decisions) * 100 if perf_a.total_decisions > 0 else 0,
            "avg_confidence": perf_a.avg_confidence,
            "avg_response_time_ms": perf_a.avg_response_time_ms,
            "total_cost": perf_a.total_cost,
            "decision_accuracy": perf_a.decision_accuracy * 100,
        }

        model_b_performance = {
            "total_decisions": perf_b.total_decisions,
            "success_rate": (perf_b.successful_decisions / perf_b.total_decisions) * 100 if perf_b.total_decisions > 0 else 0,
            "avg_confidence": perf_b.avg_confidence,
            "avg_response_time_ms": perf_b.avg_response_time_ms,
            "total_cost": perf_b.total_cost,
            "decision_accuracy": perf_b.decision_accuracy * 100,
        }

        # Determine winner based on multiple criteria
        winner = self._determine_winner(model_a_performance, model_b_performance)
        confidence_level = self._calculate_confidence(model_a_performance, model_b_performance)

        result = ABTestResult(
            model_a=model_a,
            model_b=model_b,
            model_a_performance=model_a_performance,
            model_b_performance=model_b_performance,
            winner=winner,
            confidence_level=confidence_level,
            test_duration_hours=duration_hours,
            total_decisions=test["decisions_a"] + test["decisions_b"],
        )

        # Store result and clean up
        self.test_results.append(result)
        del self.active_tests[test_name]

        logger.info(f"A/B test '{test_name}' completed. Winner: {winner} (confidence: {confidence_level:.2f}%)")
        return result

    def get_active_tests(self) -> Dict[str, Dict]:
        """
        Get all active A/B tests.

        Returns:
            Dictionary of active tests
        """
        # Clean up expired tests
        current_time = datetime.utcnow()
        expired_tests = [
            name for name, test in self.active_tests.items()
            if current_time > test["end_time"]
        ]

        for test_name in expired_tests:
            self.end_ab_test(test_name)

        return self.active_tests.copy()

    def get_model_performance(self, model_name: str) -> Optional[ModelPerformance]:
        """
        Get performance metrics for a specific model.

        Args:
            model_name: Name of the model

        Returns:
            ModelPerformance or None if not found
        """
        return self.model_performance.get(model_name)

    def get_test_results(self, limit: int = 10) -> List[ABTestResult]:
        """
        Get recent A/B test results.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of recent test results
        """
        return self.test_results[-limit:]

    def _determine_winner(self, perf_a: Dict, perf_b: Dict) -> Optional[str]:
        """
        Determine winner based on multiple performance criteria.

        Args:
            perf_a: Performance metrics for model A
            perf_b: Performance metrics for model B

        Returns:
            Winner model name or None if tie
        """
        # Weighted scoring system
        weights = {
            "decision_accuracy": 0.4,
            "success_rate": 0.3,
            "avg_confidence": 0.2,
            "cost_efficiency": 0.1,  # Lower cost is better
        }

        # Calculate cost efficiency (decisions per dollar)
        cost_eff_a = perf_a["total_decisions"] / max(perf_a["total_cost"], 0.01)
        cost_eff_b = perf_b["total_decisions"] / max(perf_b["total_cost"], 0.01)

        # Normalize metrics to 0-100 scale
        score_a = (
            perf_a["decision_accuracy"] * weights["decision_accuracy"] +
            perf_a["success_rate"] * weights["success_rate"] +
            perf_a["avg_confidence"] * weights["avg_confidence"] +
            (cost_eff_a / max(cost_eff_a, cost_eff_b)) * 100 * weights["cost_efficiency"]
        )

        score_b = (
            perf_b["decision_accuracy"] * weights["decision_accuracy"] +
            perf_b["success_rate"] * weights["success_rate"] +
            perf_b["avg_confidence"] * weights["avg_confidence"] +
            (cost_eff_b / max(cost_eff_a, cost_eff_b)) * 100 * weights["cost_efficiency"]
        )

        # Require at least 5% difference to declare winner
        if abs(score_a - score_b) < 5:
            return None

        return "model_a" if score_a > score_b else "model_b"

    def _calculate_confidence(self, perf_a: Dict, perf_b: Dict) -> float:
        """
        Calculate statistical confidence in the test results.

        Args:
            perf_a: Performance metrics for model A
            perf_b: Performance metrics for model B

        Returns:
            Confidence level as percentage
        """
        # Simple confidence calculation based on sample size and difference
        total_decisions = perf_a["total_decisions"] + perf_b["total_decisions"]

        if total_decisions < 10:
            return 0.0

        # Calculate difference in key metrics
        accuracy_diff = abs(perf_a["decision_accuracy"] - perf_b["decision_accuracy"])
        success_diff = abs(perf_a["success_rate"] - perf_b["success_rate"])

        # Simple confidence calculation
        # This could be enhanced with proper statistical tests
        base_confidence = min(total_decisions / 100 * 100, 95)  # Max 95%
        metric_confidence = (accuracy_diff + success_diff) / 2

        return min(base_confidence * (metric_confidence / 50), 95)


# Global A/B test manager instance
_ab_test_manager: Optional[ABTestManager] = None


def get_ab_test_manager() -> ABTestManager:
    """Get or create the A/B test manager instance."""
    global _ab_test_manager
    if _ab_test_manager is None:
        _ab_test_manager = ABTestManager()
    return _ab_test_manager