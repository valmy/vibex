"""
Decision Validator Service for LLM-generated trading decisions.

Provides comprehensive validation including schema validation, business rules,
risk management checks, and fallback mechanisms.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from ..core.exceptions import ValidationError as CustomValidationError
from ..schemas.trading_decision import (
    AccountContext,
    DecisionResult,
    RiskValidationResult,
    TradingContext,
    TradingDecision,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class DecisionValidationError(CustomValidationError):
    """Exception raised when decision validation fails."""
    pass


class DecisionValidator:
    """
    Comprehensive validation service for trading decisions.

    Handles schema validation, business rule validation, risk management checks,
    and provides fallback mechanisms for invalid decisions.
    """

    def __init__(self):
        """Initialize the decision validator."""
        self.validation_metrics = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "avg_validation_time_ms": 0.0,
            "validation_errors": {},
            "last_reset": datetime.utcnow()
        }

        # Define validation rules
        self.business_rules = self._initialize_business_rules()
        self.risk_rules = self._initialize_risk_rules()

    def _initialize_business_rules(self) -> Dict[str, callable]:
        """Initialize business rule validation functions."""
        return {
            "allocation_validation": self._validate_allocation_amount,
            "price_logic_validation": self._validate_price_logic,
            "position_size_validation": self._validate_position_size,
            "leverage_validation": self._validate_leverage_constraints,
            "action_requirements_validation": self._validate_action_requirements,
            "strategy_specific_validation": self._validate_strategy_specific_rules
        }

    def _initialize_risk_rules(self) -> Dict[str, callable]:
        """Initialize risk management validation functions."""
        return {
            "risk_exposure_validation": self._validate_risk_exposure,
            "position_limit_validation": self._validate_position_limits,
            "daily_loss_validation": self._validate_daily_loss_limits,
            "correlation_validation": self._validate_correlation_risk,
            "concentration_validation": self._validate_concentration_risk
        }

    async def validate_decision(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> ValidationResult:
        """
        Validate a trading decision against all validation rules.

        Args:
            decision: The trading decision to validate
            context: The trading context for validation

        Returns:
            ValidationResult with validation status and details
        """
        start_time = time.time()
        errors = []
        warnings = []
        rules_checked = []

        try:
            # Update metrics
            self.validation_metrics["total_validations"] += 1

            # 1. Schema validation
            schema_errors = await self._validate_schema(decision)
            if schema_errors:
                errors.extend(schema_errors)
            rules_checked.append("schema_validation")

            # 2. Business rule validation
            business_errors, business_warnings = await self._validate_business_rules(decision, context)
            errors.extend(business_errors)
            warnings.extend(business_warnings)
            rules_checked.extend(self.business_rules.keys())

            # 3. Risk management validation
            risk_errors, risk_warnings = await self._validate_risk_rules(decision, context)
            errors.extend(risk_errors)
            warnings.extend(risk_warnings)
            rules_checked.extend(self.risk_rules.keys())

            # Calculate validation time
            validation_time_ms = (time.time() - start_time) * 1000

            # Update metrics
            if errors:
                self.validation_metrics["failed_validations"] += 1
                for error in errors:
                    error_type = error.split(":")[0] if ":" in error else "unknown"
                    self.validation_metrics["validation_errors"][error_type] = (
                        self.validation_metrics["validation_errors"].get(error_type, 0) + 1
                    )
            else:
                self.validation_metrics["successful_validations"] += 1

            # Update average validation time
            total_validations = self.validation_metrics["total_validations"]
            current_avg = self.validation_metrics["avg_validation_time_ms"]
            self.validation_metrics["avg_validation_time_ms"] = (
                (current_avg * (total_validations - 1) + validation_time_ms) / total_validations
            )

            result = ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                validation_time_ms=validation_time_ms,
                rules_checked=rules_checked
            )

            logger.info(
                f"Decision validation completed",
                extra={
                    "symbol": decision.asset,
                    "action": decision.action,
                    "is_valid": result.is_valid,
                    "error_count": len(errors),
                    "warning_count": len(warnings),
                    "validation_time_ms": validation_time_ms
                }
            )

            return result

        except Exception as e:
            logger.error(f"Unexpected error during validation: {str(e)}", exc_info=True)
            self.validation_metrics["failed_validations"] += 1

            return ValidationResult(
                is_valid=False,
                errors=[f"validation_error: Unexpected validation error: {str(e)}"],
                warnings=[],
                validation_time_ms=(time.time() - start_time) * 1000,
                rules_checked=rules_checked
            )

    async def _validate_schema(self, decision: TradingDecision) -> List[str]:
        """
        Validate decision against JSON schema and Pydantic model constraints.

        Args:
            decision: The trading decision to validate

        Returns:
            List of schema validation errors
        """
        errors = []

        try:
            # Pydantic validation is already done during model creation
            # Additional custom schema validations

            # Validate action-specific requirements
            action_errors = decision.validate_action_requirements()
            errors.extend([f"schema_error: {error}" for error in action_errors])

            # Validate field constraints
            if decision.confidence < 0 or decision.confidence > 100:
                errors.append("schema_error: Confidence must be between 0 and 100")

            if decision.allocation_usd < 0:
                errors.append("schema_error: Allocation amount cannot be negative")

            # Validate required fields based on action
            if decision.action in ["buy", "sell"] and not decision.rationale.strip():
                errors.append("schema_error: Rationale is required for buy/sell actions")

            if decision.action in ["buy", "sell"] and not decision.exit_plan.strip():
                errors.append("schema_error: Exit plan is required for buy/sell actions")

            # Validate position adjustment details
            if decision.position_adjustment:
                if decision.position_adjustment.adjustment_amount_usd <= 0:
                    errors.append("schema_error: Position adjustment amount must be positive")

            # Validate order adjustment details
            if decision.order_adjustment:
                if not (decision.order_adjustment.adjust_tp or decision.order_adjustment.adjust_sl or
                       decision.order_adjustment.cancel_tp or decision.order_adjustment.cancel_sl):
                    errors.append("schema_error: Order adjustment must specify at least one action")

        except ValidationError as e:
            errors.append(f"schema_error: Pydantic validation failed: {str(e)}")
        except Exception as e:
            errors.append(f"schema_error: Unexpected schema validation error: {str(e)}")

        return errors

    async def _validate_business_rules(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """
        Validate decision against business rules.

        Args:
            decision: The trading decision to validate
            context: The trading context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        for rule_name, rule_func in self.business_rules.items():
            try:
                rule_errors, rule_warnings = await rule_func(decision, context)
                errors.extend([f"business_rule: {error}" for error in rule_errors])
                warnings.extend([f"business_rule: {warning}" for warning in rule_warnings])
            except Exception as e:
                logger.error(f"Error in business rule {rule_name}: {str(e)}", exc_info=True)
                errors.append(f"business_rule: Error validating {rule_name}: {str(e)}")

        return errors, warnings

    async def _validate_risk_rules(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """
        Validate decision against risk management rules.

        Args:
            decision: The trading decision to validate
            context: The trading context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        for rule_name, rule_func in self.risk_rules.items():
            try:
                rule_errors, rule_warnings = await rule_func(decision, context)
                errors.extend([f"risk_rule: {error}" for error in rule_errors])
                warnings.extend([f"risk_rule: {warning}" for warning in rule_warnings])
            except Exception as e:
                logger.error(f"Error in risk rule {rule_name}: {str(e)}", exc_info=True)
                errors.append(f"risk_rule: Error validating {rule_name}: {str(e)}")

        return errors, warnings

    # Business Rule Validation Methods
    async def _validate_allocation_amount(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate allocation amount against available capital."""
        errors = []
        warnings = []

        if decision.action in ["buy", "sell"]:
            available_balance = context.account_state.available_balance

            if decision.allocation_usd > available_balance:
                errors.append(f"Allocation amount ${decision.allocation_usd:.2f} exceeds available balance ${available_balance:.2f}")

            # Warning for large allocations
            if decision.allocation_usd > available_balance * 0.5:
                warnings.append(f"Large allocation: ${decision.allocation_usd:.2f} is more than 50% of available balance")

        return errors, warnings

    async def _validate_price_logic(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate take-profit and stop-loss price logic."""
        errors = []
        warnings = []

        current_price = context.market_data.current_price
        price_errors = decision.validate_price_logic(current_price)
        errors.extend(price_errors)

        # Additional price logic checks
        if decision.tp_price and decision.sl_price:
            if decision.action == "buy":
                risk_reward_ratio = (decision.tp_price - current_price) / (current_price - decision.sl_price)
            elif decision.action == "sell":
                risk_reward_ratio = (current_price - decision.tp_price) / (decision.sl_price - current_price)
            else:
                risk_reward_ratio = None

            if risk_reward_ratio and risk_reward_ratio < 1.0:
                warnings.append(f"Risk/reward ratio {risk_reward_ratio:.2f} is less than 1:1")

        return errors, warnings

    async def _validate_position_size(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate position size constraints."""
        errors = []
        warnings = []

        max_position_size = context.account_state.max_position_size

        if decision.action in ["buy", "sell"] and decision.allocation_usd > max_position_size:
            errors.append(f"Position size ${decision.allocation_usd:.2f} exceeds maximum allowed ${max_position_size:.2f}")

        return errors, warnings

    async def _validate_leverage_constraints(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate leverage constraints."""
        errors = []
        warnings = []

        strategy = context.account_state.active_strategy
        max_leverage = strategy.risk_parameters.max_leverage

        # For now, we assume leverage is embedded in allocation calculation
        # This could be extended to include explicit leverage validation

        return errors, warnings

    async def _validate_action_requirements(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate action-specific requirements."""
        errors = []
        warnings = []

        # Check if trying to adjust/close non-existent position
        existing_position = context.account_state.get_position_for_symbol(decision.asset)

        if decision.action in ["adjust_position", "close_position", "adjust_orders"] and not existing_position:
            errors.append(f"Cannot {decision.action} - no existing position for {decision.asset}")

        # Check position count limits for new positions
        if decision.action in ["buy", "sell"] and not existing_position:
            max_positions = context.account_state.active_strategy.max_positions
            current_positions = len(context.account_state.open_positions)

            if current_positions >= max_positions:
                errors.append(f"Cannot open new position - maximum positions ({max_positions}) reached")

        return errors, warnings

    async def _validate_strategy_specific_rules(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate strategy-specific rules."""
        errors = []
        warnings = []

        strategy = context.account_state.active_strategy

        # Validate against strategy risk parameters
        if decision.action in ["buy", "sell"]:
            max_risk_per_trade = strategy.risk_parameters.max_risk_per_trade
            balance = context.account_state.balance_usd
            max_risk_amount = balance * (max_risk_per_trade / 100)

            if decision.allocation_usd > max_risk_amount:
                errors.append(f"Trade risk ${decision.allocation_usd:.2f} exceeds strategy limit ${max_risk_amount:.2f}")

        return errors, warnings

    # Risk Management Validation Methods
    async def _validate_risk_exposure(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate risk exposure limits."""
        errors = []
        warnings = []

        if decision.action in ["buy", "sell"]:
            additional_allocation = decision.allocation_usd if decision.action in ["buy", "sell"] else 0
            current_exposure = context.account_state.risk_exposure

            if not context.account_state.is_within_risk_limits(additional_allocation):
                errors.append("Trade would exceed account risk limits")

            # Add warnings for high risk exposure
            if current_exposure > 80.0:
                warnings.append(f"High risk exposure: {current_exposure:.1f}% of account")
            elif current_exposure > 60.0:
                warnings.append(f"Elevated risk exposure: {current_exposure:.1f}% of account")

            # Add warnings for high-risk decisions
            if decision.risk_level == "high":
                warnings.append("Decision marked as high risk level")

        return errors, warnings

    async def _validate_position_limits(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate position limits."""
        errors = []
        warnings = []

        if decision.action in ["buy", "sell"]:
            if not context.account_state.can_open_new_position(decision.allocation_usd):
                errors.append("Cannot open new position due to account limits")

        return errors, warnings

    async def _validate_daily_loss_limits(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate daily loss limits."""
        errors = []
        warnings = []

        strategy = context.account_state.active_strategy
        max_daily_loss_pct = strategy.risk_parameters.max_daily_loss
        balance = context.account_state.balance_usd
        max_daily_loss = balance * (max_daily_loss_pct / 100)

        # Check current daily PnL (this would need to be calculated from recent trades)
        # For now, we'll use a simplified check
        current_unrealized_pnl = sum(pos.unrealized_pnl for pos in context.account_state.open_positions)

        if current_unrealized_pnl < -max_daily_loss:
            warnings.append(f"Current unrealized loss ${abs(current_unrealized_pnl):.2f} approaches daily limit ${max_daily_loss:.2f}")

        return errors, warnings

    async def _validate_correlation_risk(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate correlation risk."""
        errors = []
        warnings = []

        # Check if adding similar positions (simplified correlation check)
        if decision.action in ["buy", "sell"]:
            similar_positions = [
                pos for pos in context.account_state.open_positions
                if pos.symbol.split('/')[0] == decision.asset.split('/')[0]  # Same base currency
            ]

            if len(similar_positions) >= 2:
                warnings.append(f"High correlation risk: multiple positions in {decision.asset.split('/')[0]} assets")

        return errors, warnings

    async def _validate_concentration_risk(
        self,
        decision: TradingDecision,
        context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate concentration risk."""
        errors = []
        warnings = []

        if decision.action in ["buy", "sell"]:
            total_exposure = context.account_state.calculate_total_exposure()
            new_exposure = total_exposure + decision.allocation_usd
            balance = context.account_state.balance_usd

            concentration_pct = (new_exposure / balance) * 100

            if concentration_pct > 80:
                errors.append(f"Concentration risk too high: {concentration_pct:.1f}% of balance")
            elif concentration_pct > 60:
                warnings.append(f"High concentration risk: {concentration_pct:.1f}% of balance")

        return errors, warnings

    async def apply_risk_checks(
        self,
        decision: TradingDecision,
        account_context: AccountContext
    ) -> RiskValidationResult:
        """
        Apply comprehensive risk checks to a trading decision.

        Args:
            decision: The trading decision to check
            account_context: The account context for risk assessment

        Returns:
            RiskValidationResult with detailed risk assessment
        """
        risk_factors = []
        risk_score = 0.0

        # Position size risk
        max_position_exceeded = decision.allocation_usd > account_context.max_position_size
        if max_position_exceeded:
            risk_factors.append("Position size exceeds maximum allowed")
            risk_score += 25

        # Daily loss limit risk
        strategy = account_context.active_strategy
        max_daily_loss_pct = strategy.risk_parameters.max_daily_loss
        balance = account_context.balance_usd
        max_daily_loss = balance * (max_daily_loss_pct / 100)

        current_unrealized_pnl = sum(pos.unrealized_pnl for pos in account_context.open_positions)
        daily_loss_limit_exceeded = current_unrealized_pnl < -max_daily_loss

        if daily_loss_limit_exceeded:
            risk_factors.append("Daily loss limit exceeded")
            risk_score += 30

        # Correlation risk (simplified)
        correlation_risk_high = False
        if decision.action in ["buy", "sell"]:
            similar_positions = [
                pos for pos in account_context.open_positions
                if pos.symbol.split('/')[0] == decision.asset.split('/')[0]
            ]
            correlation_risk_high = len(similar_positions) >= 2

            if correlation_risk_high:
                risk_factors.append("High correlation with existing positions")
                risk_score += 20

        # Leverage risk
        max_leverage = strategy.risk_parameters.max_leverage
        leverage_exceeded = False  # This would need actual leverage calculation

        # Risk level assessment
        if decision.risk_level == "high":
            risk_score += 15
            risk_factors.append("Decision marked as high risk")
        elif decision.risk_level == "medium":
            risk_score += 10

        # Confidence factor
        if decision.confidence < 50:
            risk_score += 10
            risk_factors.append("Low confidence decision")

        return RiskValidationResult(
            passed=risk_score < 50,  # Fail if risk score is too high
            risk_score=min(risk_score, 100),  # Cap at 100
            risk_factors=risk_factors,
            max_position_exceeded=max_position_exceeded,
            daily_loss_limit_exceeded=daily_loss_limit_exceeded,
            correlation_risk_high=correlation_risk_high,
            leverage_exceeded=leverage_exceeded
        )

    async def create_fallback_decision(
        self,
        original_decision: TradingDecision,
        context: TradingContext,
        validation_errors: List[str]
    ) -> TradingDecision:
        """
        Create a conservative fallback decision when validation fails.

        Args:
            original_decision: The original invalid decision
            context: The trading context
            validation_errors: List of validation errors

        Returns:
            Conservative fallback trading decision
        """
        logger.warning(
            f"Creating fallback decision for {original_decision.asset}",
            extra={
                "original_action": original_decision.action,
                "validation_errors": validation_errors
            }
        )

        # Create conservative fallback decision
        fallback_decision = TradingDecision(
            asset=original_decision.asset,
            action="hold",  # Conservative default
            allocation_usd=0.0,  # No allocation for hold
            tp_price=None,
            sl_price=None,
            exit_plan="Conservative hold due to validation failures. Monitor market conditions.",
            rationale=f"Fallback decision created due to validation errors: {'; '.join(validation_errors[:3])}",
            confidence=25.0,  # Low confidence for fallback
            risk_level="low",  # Conservative risk level
            timestamp=datetime.utcnow()
        )

        return fallback_decision

    async def get_validation_metrics(self) -> Dict:
        """
        Get validation performance metrics.

        Returns:
            Dictionary containing validation metrics
        """
        total_validations = self.validation_metrics["total_validations"]
        success_rate = 0.0

        if total_validations > 0:
            success_rate = (self.validation_metrics["successful_validations"] / total_validations) * 100

        return {
            "total_validations": total_validations,
            "successful_validations": self.validation_metrics["successful_validations"],
            "failed_validations": self.validation_metrics["failed_validations"],
            "success_rate": success_rate,
            "avg_validation_time_ms": self.validation_metrics["avg_validation_time_ms"],
            "validation_errors": dict(self.validation_metrics["validation_errors"]),
            "last_reset": self.validation_metrics["last_reset"],
            "uptime_hours": (datetime.utcnow() - self.validation_metrics["last_reset"]).total_seconds() / 3600
        }

    async def reset_metrics(self):
        """Reset validation metrics."""
        self.validation_metrics = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "avg_validation_time_ms": 0.0,
            "validation_errors": {},
            "last_reset": datetime.utcnow()
        }

        logger.info("Validation metrics reset")


# Global validator instance
_validator_instance: Optional[DecisionValidator] = None


def get_decision_validator() -> DecisionValidator:
    """Get the global decision validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = DecisionValidator()
    return _validator_instance