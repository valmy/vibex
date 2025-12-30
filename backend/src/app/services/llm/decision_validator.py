"""
Decision Validator Service for LLM-generated trading decisions.

Provides comprehensive validation including schema validation, business rules,
risk management checks, and fallback mechanisms.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import ValidationError

from ...core.exceptions import ValidationError as CustomValidationError
from ...schemas.trading_decision import (
    AccountContext,
    AssetDecision,
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

    def __init__(self) -> None:
        """Initialize the decision validator."""
        self.validation_metrics: Dict[str, Any] = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "avg_validation_time_ms": 0.0,
            "validation_errors": {},
            "last_reset": datetime.now(timezone.utc),
        }

        # Define validation rules
        self.business_rules = self._initialize_business_rules()
        self.risk_rules = self._initialize_risk_rules()

    def _initialize_business_rules(self) -> Dict[str, Callable[[Any, Any], Any]]:
        """Initialize business rule validation functions."""
        return {
            "allocation_validation": self._validate_allocation_amount,
            "price_logic_validation": self._validate_price_logic,
            "position_size_validation": self._validate_position_size,
            "leverage_validation": self._validate_leverage_constraints,
            "action_requirements_validation": self._validate_action_requirements,
            "strategy_specific_validation": self._validate_strategy_specific_rules,
        }

    def _initialize_risk_rules(self) -> Dict[str, Callable[[Any, Any], Any]]:
        """Initialize risk management validation functions."""
        return {
            "risk_exposure_validation": self._validate_risk_exposure,
            "position_limit_validation": self._validate_position_limits,
            "daily_loss_validation": self._validate_daily_loss_limits,
            "correlation_validation": self._validate_correlation_risk,
            "concentration_validation": self._validate_concentration_risk,
        }

    def _extract_base_currency(self, symbol: str) -> str:
        """
        Extract base currency from symbol.

        For symbols like 'BTCUSDT', 'ETHUSDT', 'SOLUSDT', etc.,
        this extracts the base currency (BTC, ETH, SOL).

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT', 'ETHUSDT')

        Returns:
            Base currency (e.g., 'BTC', 'ETH')
        """
        # Common quote currencies to remove from the end
        quote_currencies = ["USDT", "USDC", "USD", "BTC", "ETH", "EUR", "GBP"]

        symbol_upper = symbol.upper()

        # Try to find a matching quote currency at the end
        for quote in quote_currencies:
            if symbol_upper.endswith(quote):
                base = symbol_upper[: -len(quote)]
                if base:  # Make sure we have something left
                    return base

        # Fallback: if no quote currency found, assume first 3-4 characters
        # This handles cases like BTC, ETH, SOL, ADA, DOT, etc.
        if len(symbol) >= 6:
            return symbol[:3]  # Most common case
        else:
            return symbol  # Return as-is if too short

    def _calculate_stop_loss_percentage(
        self, asset_decision: AssetDecision, current_price: float
    ) -> Optional[float]:
        """
        Calculate stop loss percentage from sl_price.

        Args:
            asset_decision: The asset decision containing sl_price
            current_price: Current market price of the asset

        Returns:
            Stop loss percentage (e.g., 2.0 for 2%), or None if sl_price not available
        """
        if not asset_decision.sl_price:
            return None

        if current_price <= 0:
            return None

        if asset_decision.action == "buy":
            sl_pct = (current_price - asset_decision.sl_price) / current_price * 100
            return max(0, sl_pct)
        elif asset_decision.action == "sell":
            sl_pct = (asset_decision.sl_price - current_price) / current_price * 100
            return max(0, sl_pct)
        return None

    async def validate_decision(
        self, decision: TradingDecision, context: TradingContext
    ) -> ValidationResult:
        """
        Validate a multi-asset trading decision against all validation rules.

        Args:
            decision: The multi-asset trading decision to validate
            context: The multi-asset trading context for validation

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

            # 1. Schema validation for multi-asset decision
            schema_errors = await self._validate_multi_asset_schema(decision, context)
            if schema_errors:
                errors.extend(schema_errors)
            rules_checked.append("multi_asset_schema_validation")

            # 2. Portfolio allocation validation
            portfolio_errors = await self._validate_portfolio_allocation(decision, context)
            errors.extend(portfolio_errors)
            rules_checked.append("portfolio_allocation_validation")

            # 3. Business rule validation for each asset
            business_errors, business_warnings = await self._validate_multi_asset_business_rules(
                decision, context
            )
            errors.extend(business_errors)
            warnings.extend(business_warnings)
            rules_checked.extend(self.business_rules.keys())

            # 4. Risk management validation (portfolio-wide)
            risk_errors, risk_warnings = await self._validate_portfolio_risk_rules(
                decision, context
            )
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
                current_avg * (total_validations - 1) + validation_time_ms
            ) / total_validations

            result = ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                validation_time_ms=validation_time_ms,
                rules_checked=rules_checked,
            )

            logger.info(
                "Multi-asset decision validation completed",
                extra={
                    "num_assets": len(decision.decisions),
                    "is_valid": result.is_valid,
                    "error_count": len(errors),
                    "warning_count": len(warnings),
                    "validation_time_ms": validation_time_ms,
                },
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
                rules_checked=rules_checked,
            )

    async def _validate_multi_asset_schema(
        self, decision: TradingDecision, context: TradingContext
    ) -> List[str]:
        errors: List[str] = []
        try:
            self._validate_portfolio_level_fields(decision, errors)
            self._validate_asset_level_fields(decision, errors)
        except ValidationError as e:
            errors.append(f"schema_error: Pydantic validation failed: {str(e)}")
        except Exception as e:
            errors.append(f"schema_error: Unexpected schema validation error: {str(e)}")
        return errors

    def _validate_portfolio_level_fields(self, decision: Any, errors: List[str]) -> None:
        if not decision.decisions:
            errors.append("schema_error: No asset decisions provided")
        if not decision.portfolio_rationale or not decision.portfolio_rationale.strip():
            errors.append("schema_error: Portfolio rationale is required")
        if decision.total_allocation_usd < 0:
            errors.append("schema_error: Total allocation cannot be negative")

    def _validate_asset_level_fields(self, decision: Any, errors: List[str]) -> None:
        for asset_decision in decision.decisions:
            action_errors = asset_decision.validate_action_requirements()
            errors.extend(
                [f"schema_error ({asset_decision.asset}): {err}" for err in action_errors]
            )
            if not 0 <= asset_decision.confidence <= 100:
                errors.append(
                    f"schema_error ({asset_decision.asset}): Confidence must be between 0 and 100"
                )
            if asset_decision.allocation_usd < 0:
                errors.append(
                    f"schema_error ({asset_decision.asset}): Allocation amount cannot be negative"
                )
            if asset_decision.action in ["buy", "sell"] and not asset_decision.rationale.strip():
                errors.append(
                    f"schema_error ({asset_decision.asset}): Rationale is required for buy/sell actions"
                )
            if asset_decision.action in ["buy", "sell"] and not asset_decision.exit_plan.strip():
                errors.append(
                    f"schema_error ({asset_decision.asset}): Exit plan is required for buy/sell actions"
                )
            if (
                asset_decision.position_adjustment
                and asset_decision.position_adjustment.adjustment_amount_usd <= 0
            ):
                errors.append(
                    f"schema_error ({asset_decision.asset}): Position adjustment amount must be positive"
                )
            if asset_decision.order_adjustment and not any(
                [
                    asset_decision.order_adjustment.adjust_tp,
                    asset_decision.order_adjustment.adjust_sl,
                    asset_decision.order_adjustment.cancel_tp,
                    asset_decision.order_adjustment.cancel_sl,
                ]
            ):
                errors.append(
                    f"schema_error ({asset_decision.asset}): Order adjustment must specify at least one action"
                )

    async def _validate_portfolio_allocation(
        self, decision: TradingDecision, context: TradingContext
    ) -> List[str]:
        """
        Validate that portfolio allocation is consistent and within limits.

        Args:
            decision: The multi-asset trading decision
            context: The trading context

        Returns:
            List of allocation validation errors
        """
        errors = []

        # Validate total allocation matches sum of individual allocations
        allocation_errors = decision.validate_portfolio_allocation()
        errors.extend([f"portfolio_allocation: {error}" for error in allocation_errors])

        # Validate total allocation against available capital
        available_balance = context.account_state.available_balance
        if decision.total_allocation_usd > available_balance:
            errors.append(
                f"portfolio_allocation: Total allocation ${decision.total_allocation_usd:.2f} "
                f"exceeds available balance ${available_balance:.2f}"
            )

        return errors

    async def _validate_multi_asset_business_rules(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """
        Validate multi-asset decision by iterating through business rules.

        Args:
            decision: The multi-asset trading decision to validate
            context: The trading context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        for rule_func in self.business_rules.values():
            rule_errors, rule_warnings = await rule_func(decision, context)
            errors.extend(rule_errors)
            warnings.extend(rule_warnings)

        return errors, warnings

    async def _validate_portfolio_risk_rules(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """
        Validate multi-asset decision by iterating through portfolio risk rules.

        Args:
            decision: The multi-asset trading decision to validate
            context: The trading context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        for rule_func in self.risk_rules.values():
            rule_errors, rule_warnings = await rule_func(decision, context)
            errors.extend(rule_errors)
            warnings.extend(rule_warnings)

        return errors, warnings

    # Business Rule Validation Methods
    async def _validate_allocation_amount(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate allocation amount against available capital."""
        errors = []
        warnings = []

        for asset_decision in decision.decisions:
            if asset_decision.action in ["buy", "sell"]:
                available_balance = context.account_state.available_balance

                if asset_decision.allocation_usd > available_balance:
                    errors.append(
                        f"business_rule ({asset_decision.asset}): Allocation amount ${asset_decision.allocation_usd:.2f} "
                        f"exceeds available balance ${available_balance:.2f}"
                    )

                # Warning for large allocations
                if asset_decision.allocation_usd > available_balance * 0.5:
                    warnings.append(
                        f"business_rule ({asset_decision.asset}): Large allocation: ${asset_decision.allocation_usd:.2f} "
                        f"is more than 50% of available balance"
                    )

        return errors, warnings

    async def _validate_price_logic(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate take-profit and stop-loss price logic."""
        errors = []
        warnings = []

        for asset_decision in decision.decisions:
            asset_data = context.market_data.get_asset_data(asset_decision.asset)
            if not asset_data:
                errors.append(f"business_rule ({asset_decision.asset}): No market data available")
                continue

            current_price = asset_data.current_price
            price_errors = asset_decision.validate_price_logic(current_price)
            errors.extend(
                [f"business_rule ({asset_decision.asset}): {error}" for error in price_errors]
            )

            # Additional price logic checks
            if asset_decision.tp_price and asset_decision.sl_price:
                potential_reward: float = 0.0
                potential_risk: float = 0.0

                if asset_decision.action == "buy":
                    potential_reward = asset_decision.tp_price - current_price
                    potential_risk = current_price - asset_decision.sl_price
                elif asset_decision.action == "sell":
                    potential_reward = current_price - asset_decision.tp_price
                    potential_risk = asset_decision.sl_price - current_price

                if potential_risk > 0:
                    risk_reward_ratio: float = potential_reward / potential_risk
                    if risk_reward_ratio < 1.0:
                        warnings.append(
                            f"business_rule ({asset_decision.asset}): Risk/reward ratio {risk_reward_ratio:.2f} is less than 1:1"
                        )
                elif potential_reward > 0:
                    # Risk is zero or negative, reward is positive, so it's a good ratio
                    pass

        return errors, warnings

    async def _validate_position_size(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate position size constraints."""
        errors: List[str] = []
        warnings: List[str] = []

        max_position_size = context.account_state.max_position_size

        for asset_decision in decision.decisions:
            if (
                asset_decision.action in ["buy", "sell"]
                and asset_decision.allocation_usd > max_position_size
            ):
                errors.append(
                    f"business_rule ({asset_decision.asset}): Position size ${asset_decision.allocation_usd:.2f} "
                    f"exceeds maximum allowed ${max_position_size:.2f}"
                )

        return errors, warnings

    async def _validate_leverage_constraints(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate leverage constraints."""
        errors: List[str] = []
        warnings: List[str] = []

        # For now, we assume leverage is embedded in allocation calculation
        # This could be extended to include explicit leverage validation

        return errors, warnings

    async def _validate_action_requirements(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate action-specific requirements."""
        errors: List[str] = []
        warnings: List[str] = []

        # Check if trying to adjust/close non-existent position
        for asset_decision in decision.decisions:
            existing_position = context.account_state.get_position_for_symbol(asset_decision.asset)

            if (
                asset_decision.action in ["adjust_position", "close_position", "adjust_orders"]
                and not existing_position
            ):
                errors.append(
                    f"business_rule ({asset_decision.asset}): Cannot {asset_decision.action} - no existing position"
                )

        # Check position count limits for new positions
        new_positions_count = sum(
            1
            for d in decision.decisions
            if d.action in ["buy", "sell"]
            and not context.account_state.get_position_for_symbol(d.asset)
        )
        max_positions = context.account_state.active_strategy.max_positions
        current_positions = len(context.account_state.open_positions)

        if current_positions + new_positions_count > max_positions:
            errors.append(
                f"business_rule: Total positions ({current_positions + new_positions_count}) "
                f"would exceed maximum ({max_positions})"
            )

        return errors, warnings

    async def _validate_strategy_specific_rules(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate strategy-specific rules."""
        errors: List[str] = []
        warnings: List[str] = []

        strategy = context.account_state.active_strategy
        default_sl_pct = strategy.risk_parameters.stop_loss_percentage
        max_risk_per_trade = strategy.risk_parameters.max_risk_per_trade
        balance = context.account_state.balance_usd
        max_risk_amount = balance * (max_risk_per_trade / 100)

        for asset_decision in decision.decisions:
            if asset_decision.action not in ["buy", "sell"]:
                continue

            asset_data = context.market_data.get_asset_data(asset_decision.asset)
            if not asset_data:
                continue
            current_price = asset_data.current_price

            sl_pct = self._calculate_stop_loss_percentage(asset_decision, current_price)

            if sl_pct is None:
                sl_pct = default_sl_pct
            else:
                sl_pct = min(sl_pct, 100.0)

            if sl_pct <= 0:
                errors.append(
                    f"business_rule ({asset_decision.asset}): Stop loss percentage must be positive, "
                    f"got {sl_pct:.2f}%"
                )
                continue

            actual_risk = asset_decision.allocation_usd * (sl_pct / 100)

            if actual_risk > max_risk_amount:
                errors.append(
                    f"business_rule ({asset_decision.asset}): Actual risk ${actual_risk:.2f} "
                    f"(allocation ${asset_decision.allocation_usd:.2f} × {sl_pct:.2f}% SL) "
                    f"exceeds strategy limit ${max_risk_amount:.2f}"
                )

        return errors, warnings

    # Risk Management Validation Methods
    async def _validate_risk_exposure(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate risk exposure limits."""
        errors = []
        warnings = []

        # This is now a portfolio-level check
        additional_allocation = sum(
            d.allocation_usd for d in decision.decisions if d.action in ["buy", "sell"]
        )

        if additional_allocation > 0:
            if not context.account_state.is_within_risk_limits(additional_allocation):
                errors.append("risk_rule: Portfolio allocation would exceed account risk limits")

        current_exposure = context.account_state.risk_exposure
        if current_exposure > 80.0:
            warnings.append(f"risk_rule: High risk exposure: {current_exposure:.1f}% of account")
        elif current_exposure > 60.0:
            warnings.append(
                f"risk_rule: Elevated risk exposure: {current_exposure:.1f}% of account"
            )

        # Validate portfolio risk level consistency
        high_risk_count = sum(1 for d in decision.decisions if d.risk_level == "high")
        if len(decision.decisions) > 0 and high_risk_count > len(decision.decisions) / 2:
            warnings.append(
                f"risk_rule: More than half of decisions ({high_risk_count}/{len(decision.decisions)}) are high risk"
            )

        return errors, warnings

    async def _validate_position_limits(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate position limits."""
        errors: List[str] = []
        warnings: List[str] = []

        # This check is now handled by _validate_action_requirements (for count)
        # and _validate_position_size (for allocation).
        # We can leave this empty or remove it from the rules dict.
        # For now, let's just return empty.

        return errors, warnings

    async def _validate_daily_loss_limits(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate daily loss limits."""
        errors: List[str] = []
        warnings: List[str] = []

        strategy = context.account_state.active_strategy
        max_daily_loss_pct = strategy.risk_parameters.max_daily_loss
        balance = context.account_state.balance_usd
        max_daily_loss = balance * (max_daily_loss_pct / 100)

        # Check current daily PnL (this would need to be calculated from recent trades)
        # For now, we'll use a simplified check
        current_unrealized_pnl = sum(
            pos.unrealized_pnl for pos in context.account_state.open_positions
        )

        if current_unrealized_pnl < -max_daily_loss:
            warnings.append(
                f"risk_rule: Current unrealized loss ${abs(current_unrealized_pnl):.2f} "
                f"approaches daily limit ${max_daily_loss:.2f}"
            )

        return errors, warnings

    async def _validate_correlation_risk(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate correlation risk by checking for multiple positions in similar assets."""
        warnings = []

        # Combine existing positions with new proposed positions for a full view
        all_positions = {pos.symbol: pos for pos in context.account_state.open_positions}

        # Add new positions from the decision
        for asset_decision in decision.decisions:
            if asset_decision.action in ["buy", "sell"]:
                # Use a simple object to represent a potential new position
                # Using a dictionary instead of creating a new type
                all_positions[asset_decision.asset] = {"symbol": asset_decision.asset}  # type: ignore[assignment]

        # Group positions by base currency
        positions_by_base: Dict[str, List[str]] = {}
        for symbol in all_positions.keys():
            base = self._extract_base_currency(symbol)
            if base not in positions_by_base:
                positions_by_base[base] = []
            positions_by_base[base].append(symbol)

        # Check for correlation risk
        for base, symbols in positions_by_base.items():
            if len(symbols) > 1:
                warnings.append(
                    f"risk_rule: High correlation risk detected for base currency '{base}' with positions in: {', '.join(symbols)}"
                )

        return [], warnings

    async def _validate_concentration_risk(
        self, decision: TradingDecision, context: TradingContext
    ) -> Tuple[List[str], List[str]]:
        """Validate concentration risk."""
        errors = []
        warnings = []

        if decision.total_allocation_usd > 0:
            # Calculate concentration per asset
            asset_concentrations = {}
            for asset_decision in decision.decisions:
                if asset_decision.allocation_usd > 0:
                    concentration = (
                        asset_decision.allocation_usd / decision.total_allocation_usd
                    ) * 100
                    asset_concentrations[asset_decision.asset] = concentration

            # Check for over-concentration in single asset
            if asset_concentrations:
                max_concentration = max(asset_concentrations.values())
                if max_concentration > 60:
                    errors.append(
                        f"risk_rule: Single asset concentration ({max_concentration:.1f}%) exceeds safe limit (60%)"
                    )
                elif max_concentration > 50:
                    warnings.append(
                        f"risk_rule: High single asset concentration ({max_concentration:.1f}%)"
                    )

        return errors, warnings

    async def apply_risk_checks(
        self, decision: TradingDecision, account_context: AccountContext
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
        max_position_exceeded = decision.total_allocation_usd > account_context.max_position_size
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
        for asset_decision in decision.decisions:
            if asset_decision.action in ["buy", "sell"]:
                decision_base = self._extract_base_currency(asset_decision.asset)
                similar_positions = [
                    pos
                    for pos in account_context.open_positions
                    if self._extract_base_currency(pos.symbol) == decision_base
                ]
                correlation_risk_high = len(similar_positions) >= 2

                if correlation_risk_high:
                    risk_factors.append("High correlation with existing positions")
                    risk_score += 20
                    break  # Only need to find one instance of high correlation

        # Leverage risk
        leverage_exceeded = False  # This would need actual leverage calculation

        # Risk level assessment
        if decision.portfolio_risk_level == "high":
            risk_score += 15
            risk_factors.append("Decision marked as high risk")
        elif decision.portfolio_risk_level == "medium":
            risk_score += 10

        # Confidence factor
        avg_confidence = (
            sum(d.confidence for d in decision.decisions) / len(decision.decisions)
            if decision.decisions
            else 0
        )
        if avg_confidence < 50:
            risk_score += 10
            risk_factors.append("Low confidence decision")

        return RiskValidationResult(
            passed=risk_score < 50,  # Fail if risk score is too high
            risk_score=min(risk_score, 100),  # Cap at 100
            risk_factors=risk_factors,
            max_position_exceeded=max_position_exceeded,
            daily_loss_limit_exceeded=daily_loss_limit_exceeded,
            correlation_risk_high=correlation_risk_high,
            leverage_exceeded=leverage_exceeded,
        )

    async def create_fallback_decision(
        self,
        original_decision: TradingDecision,
        context: TradingContext,
        validation_errors: List[str],
    ) -> TradingDecision:
        """
        Create a conservative multi-asset fallback decision when validation fails.

        Args:
            original_decision: The original invalid multi-asset decision
            context: The trading context
            validation_errors: List of validation errors

        Returns:
            Conservative fallback multi-asset trading decision
        """
        from ...schemas.trading_decision import AssetDecision

        logger.warning(
            f"Creating multi-asset fallback decision for {len(original_decision.decisions)} assets",
            extra={
                "validation_errors": validation_errors,
            },
        )

        # Create conservative fallback decisions for all assets
        fallback_asset_decisions = []
        for asset_decision in original_decision.decisions:
            fallback_asset_decisions.append(
                AssetDecision(
                    asset=asset_decision.asset,
                    action="hold",  # Conservative default
                    allocation_usd=0.0,  # No allocation for hold
                    position_adjustment=None,
                    order_adjustment=None,
                    tp_price=None,
                    sl_price=None,
                    exit_plan="Conservative hold due to validation failures. Monitor market conditions.",
                    rationale=f"Fallback decision for {asset_decision.asset} due to validation errors",
                    confidence=25.0,  # Low confidence for fallback
                    risk_level="low",  # Conservative risk level
                )
            )

        # Create portfolio-level fallback decision
        fallback_decision = TradingDecision(
            decisions=fallback_asset_decisions,
            portfolio_rationale=f"Portfolio-wide fallback decision created due to validation errors: {'; '.join(validation_errors[:3])}. "
            "All positions set to hold for safety.",
            total_allocation_usd=0.0,
            portfolio_risk_level="low",
            timestamp=datetime.now(timezone.utc),
        )

        return fallback_decision

    async def get_validation_metrics(self) -> Dict[str, Any]:
        """
        Get validation performance metrics.

        Returns:
            Dictionary containing validation metrics
        """
        total_validations: int = self.validation_metrics["total_validations"]
        success_rate = 0.0

        if total_validations > 0:
            success_rate = (
                self.validation_metrics["successful_validations"] / total_validations
            ) * 100

        successful_validations: int = self.validation_metrics["successful_validations"]
        failed_validations: int = self.validation_metrics["failed_validations"]
        avg_validation_time: float = self.validation_metrics["avg_validation_time_ms"]
        validation_errors: Dict[str, Any] = self.validation_metrics["validation_errors"]
        last_reset: datetime = self.validation_metrics["last_reset"]

        return {
            "total_validations": total_validations,
            "successful_validations": successful_validations,
            "failed_validations": failed_validations,
            "success_rate": success_rate,
            "avg_validation_time_ms": avg_validation_time,
            "validation_errors": dict(validation_errors),
            "last_reset": last_reset,
            "uptime_hours": (datetime.now(timezone.utc) - last_reset).total_seconds() / 3600,
        }

    async def reset_metrics(self) -> None:
        """Reset validation metrics."""
        self.validation_metrics = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "avg_validation_time_ms": 0.0,
            "validation_errors": {},
            "last_reset": datetime.now(timezone.utc),
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
