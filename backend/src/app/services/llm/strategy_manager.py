"""
Strategy Manager Service for LLM Decision Engine.

Provides comprehensive strategy management including configuration loading,
strategy assignment, switching, and performance tracking.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...core.exceptions import ConfigurationError, ValidationError
from ...models.strategy import Strategy as StrategyModel
from ...models.strategy import StrategyAssignment as StrategyAssignmentModel
from ...schemas.trading_decision import (
    StrategyAlert,
    StrategyAssignment,
    StrategyMetrics,
    StrategyPerformance,
    StrategyRiskParameters,
    TradingStrategy,
)

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages trading strategies for the LLM Decision Engine.

    Handles strategy configuration, assignment, switching, and performance tracking
    using database persistence.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    ):
        """
        Initialize the Strategy Manager.

        Args:
            config_path: Path to strategy configuration files directory (legacy/backup)
            session_factory: Database session factory
        """
        self.config_path = config_path or Path("config/strategies")
        self.session_factory = session_factory
        self._performance_cache: Dict[str, StrategyPerformance] = {}
        self._metrics_cache: Dict[Tuple[str, int], StrategyMetrics] = {}
        self._alerts: List[StrategyAlert] = []

        # Initialize predefined strategies if session factory is available
        # We can't await here in __init__, so this must be called explicitly or lazily
        # For now, we'll rely on the application startup to call this or handle it lazily
        pass

    async def initialize(self) -> None:
        """Initialize the service and seed strategies."""
        if self.session_factory:
            await self._initialize_predefined_strategies()

    async def _initialize_predefined_strategies(self) -> None:
        """Initialize predefined trading strategies in the database."""
        if not self.session_factory:
            logger.warning("No session factory available, skipping strategy initialization")
            return

        conservative_prompt = self._get_conservative_prompt_template()
        aggressive_prompt = self._get_aggressive_prompt_template()
        scalping_prompt = self._get_scalping_prompt_template()
        swing_prompt = self._get_swing_prompt_template()
        dca_prompt = self._get_dca_prompt_template()

        strategies_data = [
            {
                "strategy_id": "conservative_perps",
                "strategy_name": "Conservative Perps",
                "strategy_type": "conservative",
                "prompt_template": conservative_prompt,
                "risk_parameters": {
                    "max_risk_per_trade": 0.5,
                    "max_daily_loss": 2.0,
                    "stop_loss_percentage": 1.5,
                    "take_profit_ratio": 3.0,
                    "max_leverage": 3.0,
                    "cooldown_period": 600,
                    "max_funding_rate_bps": 5.0,
                    "liquidation_buffer": 0.15,  # Default for perps
                },
                "timeframe_preference": ["5m", "15m", "4h"],
                "max_positions": 2,
                "position_sizing": "volatility_adjusted",
                "order_preference": "maker_only",
                "funding_rate_threshold": 0.05,
                "is_active": True,
            },
            {
                "strategy_id": "aggressive_perps",
                "strategy_name": "Aggressive Perps",
                "strategy_type": "aggressive",
                "prompt_template": aggressive_prompt,
                "risk_parameters": {
                    "max_risk_per_trade": 2.0,
                    "max_daily_loss": 8.0,
                    "stop_loss_percentage": 2.0,
                    "take_profit_ratio": 2.0,
                    "max_leverage": 15.0,
                    "cooldown_period": 120,
                    "max_funding_rate_bps": 15.0,
                    "liquidation_buffer": 0.15,  # Default for perps
                },
                "timeframe_preference": ["5m", "15m", "1h"],
                "max_positions": 4,
                "position_sizing": "percentage",
                "order_preference": "taker_accepted",
                "funding_rate_threshold": 0.15,
                "is_active": True,
            },
            {
                "strategy_id": "scalping_perps",
                "strategy_name": "Perps Scalping",
                "strategy_type": "scalping",
                "prompt_template": scalping_prompt,
                "risk_parameters": {
                    "max_risk_per_trade": 0.25,
                    "max_daily_loss": 1.5,
                    "stop_loss_percentage": 0.15,
                    "take_profit_ratio": 1.3,
                    "max_leverage": 10.0,
                    "cooldown_period": 30,
                    "max_funding_rate_bps": 3.0,
                    "liquidation_buffer": 0.15,  # Default for perps
                },
                "timeframe_preference": ["1m", "5m"],
                "max_positions": 3,
                "position_sizing": "fixed",
                "order_preference": "maker_only",
                "funding_rate_threshold": 0.03,
                "is_active": True,
            },
            {
                "strategy_id": "swing_perps",
                "strategy_name": "Swing Perps",
                "strategy_type": "swing",
                "prompt_template": swing_prompt,
                "risk_parameters": {
                    "max_risk_per_trade": 1.5,
                    "max_daily_loss": 5.0,
                    "stop_loss_percentage": 2.5,
                    "take_profit_ratio": 2.5,
                    "max_leverage": 5.0,
                    "cooldown_period": 300,
                    "max_funding_rate_bps": 8.0,
                    "liquidation_buffer": 0.15,  # Default for perps
                },
                "timeframe_preference": ["5m", "15m", "4h"],
                "max_positions": 3,
                "position_sizing": "volatility_adjusted",
                "order_preference": "maker_preferred",
                "funding_rate_threshold": 0.08,
                "is_active": True,
            },
            {
                "strategy_id": "dca_hedge",
                "strategy_name": "Perps DCA Hedge",
                "strategy_type": "dca",
                "prompt_template": dca_prompt,
                "risk_parameters": {
                    "max_risk_per_trade": 1.0,
                    "max_daily_loss": 3.0,
                    "stop_loss_percentage": 0,
                    "take_profit_ratio": 3.0,
                    "max_leverage": 1.0,
                    "cooldown_period": 900,
                    "max_funding_rate_bps": 10.0,
                    "liquidation_buffer": 0.15,  # Default for perps
                },
                "timeframe_preference": ["15m", "1h"],
                "max_positions": 1,
                "position_sizing": "fixed",
                "order_preference": "maker_only",
                "funding_rate_threshold": 0.10,
                "is_active": True,
            },
        ]

        async with self.session_factory() as session:
            try:
                for strategy_data in strategies_data:
                    # Check if strategy already exists
                    stmt = select(StrategyModel).where(
                        StrategyModel.strategy_id == strategy_data["strategy_id"]
                    )
                    result = await session.execute(stmt)
                    existing_strategy = result.scalar_one_or_none()

                    if not existing_strategy:
                        # Create new strategy
                        db_strategy = StrategyModel(
                            strategy_id=strategy_data["strategy_id"],
                            strategy_name=strategy_data["strategy_name"],
                            strategy_type=strategy_data["strategy_type"],
                            prompt_template=strategy_data["prompt_template"],
                            risk_parameters=strategy_data["risk_parameters"],
                            timeframe_preference=strategy_data["timeframe_preference"],
                            max_positions=strategy_data["max_positions"],
                            position_sizing=strategy_data["position_sizing"],
                            order_preference=strategy_data["order_preference"],
                            funding_rate_threshold=strategy_data["funding_rate_threshold"],
                            is_active=strategy_data["is_active"],
                            created_by="system",
                            version="1.0",
                            description=f"Predefined {strategy_data['strategy_type']} strategy for perpetual futures trading",
                        )
                        session.add(db_strategy)
                        logger.info(f"Added predefined strategy: {strategy_data['strategy_name']}")

                await session.commit()
                logger.info(
                    f"Initialized {len([s for s in strategies_data if s])} predefined strategies"
                )
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to initialize predefined strategies: {e}")
                raise ConfigurationError(f"Failed to initialize predefined strategies: {e}") from e

    def _get_conservative_prompt_template(self) -> str:
        """Get prompt template for conservative strategy."""
        return """
Analyze {symbol} perpetual futures conservatively. Use 5m timeframe for precise entries but confirm bias on 4h trend. Focus on strong support/resistance, funding rate direction, and liquidation cluster avoidance. Prioritize limit orders (maker) for fee efficiency. Current funding rate: {funding_rate}%. Target 3:1+ reward/risk to offset holding costs. Maximum 2 concurrent positions.
"""

    def _get_aggressive_prompt_template(self) -> str:
        """Get prompt template for aggressive strategy."""
        return """
Analyze {symbol} for aggressive perpetual futures trading on 5m timeframe. Hunt for momentum breakouts, funding rate squeezes, and liquidation hunts. Accept taker fees for immediate entries on confirmed breaks. Monitor open interest changes and funding rate: {funding_rate}%. Use 15x max leverage with 2% stop loss. Target 2:1 risk/reward, exit within 4-6 hours to limit funding. Obey daily loss limits strictly.
"""

    def _get_scalping_prompt_template(self) -> str:
        """Get prompt template for scalping strategy."""
        return """
Scalp {symbol} perpetuals on 1m/5m timeframes. Focus on order book imbalances, micro-divergences, and funding rate arbitrage. USE LIMIT ORDERS ONLY (maker fee 0.005%). Target 0.2% profit with 0.15% stop. Avoid trading 5 minutes before/after funding. Current funding: {funding_rate}bps. Max hold time: 30 minutes. Check liquidation heatmap for cluster avoidance.
"""

    def _get_swing_prompt_template(self) -> str:
        """Get prompt template for swing strategy."""
        return """
Swing trade {symbol} perps: use 5m for precision entry, 4h for trend direction. Hold 6-18 hours max. Monitor funding rate trend: {funding_rate}bps. Target 2.5:1 R:R. Use 3-5x leverage. Place limit orders at premium/discount to avoid taker fees. Calculate liquidation price before entry: must be >15% away. Exit if funding flips against position for 2 consecutive periods.
"""

    def _get_dca_prompt_template(self) -> str:
        """Get prompt template for DCA strategy."""
        return """
Execute DCA for {symbol} perps: place limit orders every 15m at 0.5% increments. Use 1x leverage ONLY. Current funding {funding_rate}bps - avoid if >10bps. Hedge spot exposure or build gradual directional position. Max 5 entry orders, then take profit at +3% from average entry. No stop loss - manual intervention only. Maker orders essential.
"""

    async def create_custom_strategy(
        self,
        name: str,
        prompt_template: str,
        risk_parameters: StrategyRiskParameters,
        timeframe_preference: Optional[List[str]] = None,
        max_positions: Optional[int] = None,
        position_sizing: Optional[
            Literal["fixed", "percentage", "kelly", "volatility_adjusted"]
        ] = None,
        order_preference: Optional[
            Literal["maker_only", "taker_accepted", "maker_preferred", "any"]
        ] = None,
        funding_rate_threshold: Optional[float] = None,
        created_by: Optional[str] = None,
    ) -> TradingStrategy:
        """Create a custom trading strategy.

        Args:
            name: Human-readable strategy name.
            prompt_template: LLM prompt template.
            risk_parameters: Risk management parameters.
            timeframe_preference: Preferred timeframes.
            max_positions: Maximum concurrent positions.
            position_sizing: Position sizing method.
            order_preference: Preference for order types.
            funding_rate_threshold: Funding rate threshold.
            created_by: Identifier of the user creating the strategy.
        """
        if not self.session_factory:
            raise ConfigurationError("Database session not available")

        # Generate a simple identifier from the name.
        strategy_id = name.lower().replace(" ", "_")
        if timeframe_preference is None:
            timeframe_preference = ["1h", "4h"]

        # Create Pydantic model for validation
        custom_strategy = TradingStrategy(
            strategy_id=strategy_id,
            strategy_name=name,
            strategy_type="custom",
            prompt_template=prompt_template,
            risk_parameters=risk_parameters,
            timeframe_preference=timeframe_preference,
            max_positions=max_positions if max_positions is not None else 3,
            position_sizing=position_sizing if position_sizing is not None else "percentage",
            order_preference=order_preference if order_preference is not None else "any",
            funding_rate_threshold=funding_rate_threshold
            if funding_rate_threshold is not None
            else 0.0,
            is_active=True,
        )

        # Validate strategy constraints
        validation_errors = custom_strategy.validate_strategy_constraints()
        if validation_errors:
            raise ValidationError(
                f"Custom strategy validation failed: {', '.join(validation_errors)}"
            )

        async with self.session_factory() as session:
            try:
                # Ensure strategy does not already exist
                stmt = select(StrategyModel).where(StrategyModel.strategy_id == strategy_id)
                result = await session.execute(stmt)
                if result.scalar_one_or_none():
                    raise ValidationError(f"Strategy '{strategy_id}' already exists")

                # Persist to DB
                db_strategy = StrategyModel(
                    strategy_id=strategy_id,
                    strategy_name=name,
                    strategy_type="custom",
                    prompt_template=prompt_template,
                    risk_parameters=risk_parameters.model_dump(),
                    timeframe_preference=timeframe_preference,
                    max_positions=custom_strategy.max_positions,
                    position_sizing=custom_strategy.position_sizing,
                    order_preference=custom_strategy.order_preference,
                    funding_rate_threshold=custom_strategy.funding_rate_threshold,
                    is_active=True,
                    created_by=created_by,
                )
                session.add(db_strategy)
                await session.commit()
                logger.info(f"Created custom strategy '{strategy_id}' in database")
                return custom_strategy
            except ValidationError:
                raise
            except Exception as e:
                await session.rollback()
                raise ConfigurationError(f"Failed to create strategy: {e}") from e

    async def get_available_strategies(self) -> List[TradingStrategy]:
        """
        Get all available active trading strategies.

        Returns:
            List[TradingStrategy]: List of all available strategies
        """
        if not self.session_factory:
            return []

        async with self.session_factory() as session:
            try:
                stmt = select(StrategyModel).where(StrategyModel.is_active == True)  # noqa: E712
                result = await session.execute(stmt)
                db_strategies = result.scalars().all()

                return [self._map_db_to_pydantic(s) for s in db_strategies]
            except Exception as e:
                logger.error(f"Failed to get available strategies: {e}")
                return []

    async def get_strategy(self, strategy_id: str) -> Optional[TradingStrategy]:
        """
        Get a specific strategy by ID.

        Args:
            strategy_id: Strategy identifier

        Returns:
            Optional[TradingStrategy]: Strategy if found, None otherwise
        """
        if not self.session_factory:
            return None

        async with self.session_factory() as session:
            try:
                stmt = select(StrategyModel).where(StrategyModel.strategy_id == strategy_id)
                result = await session.execute(stmt)
                db_strategy = result.scalar_one_or_none()

                if db_strategy:
                    return self._map_db_to_pydantic(db_strategy)
                return None
            except Exception as e:
                logger.error(f"Failed to get strategy {strategy_id}: {e}")
                return None

    async def validate_strategy(self, strategy: TradingStrategy) -> List[str]:
        """
        Validate a strategy configuration.

        Args:
            strategy: Strategy to validate

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        return strategy.validate_strategy_constraints()

    async def assign_strategy_to_account(
        self,
        account_id: int,
        strategy_id: str,
        assigned_by: Optional[str] = None,
        switch_reason: Optional[str] = None,
    ) -> StrategyAssignment:
        """
        Assign a strategy to an account.

        Args:
            account_id: Account identifier
            strategy_id: Strategy to assign
            assigned_by: User who assigned the strategy
            switch_reason: Reason for strategy assignment/switch

        Returns:
            StrategyAssignment: Assignment record
        """
        if not self.session_factory:
            raise ConfigurationError("Database session not available")

        async with self.session_factory() as session:
            try:
                # 1. Get the strategy to assign
                stmt = select(StrategyModel).where(StrategyModel.strategy_id == strategy_id)
                result = await session.execute(stmt)
                strategy = result.scalar_one_or_none()

                if not strategy:
                    raise ValidationError(f"Strategy '{strategy_id}' not found")
                if not strategy.is_active:
                    raise ValidationError(f"Strategy '{strategy_id}' is not active")

                # 2. Get current active assignment
                stmt = select(StrategyAssignmentModel).where(
                    and_(
                        StrategyAssignmentModel.account_id == account_id,
                        StrategyAssignmentModel.is_active == True,  # noqa: E712
                    )
                )
                result = await session.execute(stmt)
                current_assignment = result.scalar_one_or_none()

                previous_strategy_id = None
                if current_assignment:
                    # Deactivate current assignment
                    current_assignment.is_active = False
                    current_assignment.deactivated_at = datetime.utcnow()
                    current_assignment.deactivated_by = assigned_by
                    current_assignment.deactivation_reason = switch_reason
                    previous_strategy_id = current_assignment.strategy_id

                # 3. Create new assignment
                new_assignment = StrategyAssignmentModel(
                    account_id=account_id,
                    strategy_id=strategy.id,  # Use DB ID
                    assigned_by=assigned_by,
                    previous_strategy_id=previous_strategy_id,
                    switch_reason=switch_reason,
                    is_active=True,
                    assigned_at=datetime.utcnow(),
                )
                session.add(new_assignment)
                await session.commit()
                await session.refresh(new_assignment)

                logger.info(f"Assigned strategy '{strategy_id}' to account {account_id}")

                return StrategyAssignment(
                    account_id=account_id,
                    strategy_id=strategy_id,
                    assigned_by=assigned_by,
                    previous_strategy_id=str(previous_strategy_id)
                    if previous_strategy_id
                    else None,
                    switch_reason=switch_reason,
                    assigned_at=new_assignment.assigned_at,
                )

            except ValidationError:
                raise
            except Exception as e:
                await session.rollback()
                raise ConfigurationError(f"Failed to assign strategy: {e}") from e

    async def get_account_strategy(self, account_id: int) -> Optional[TradingStrategy]:
        """
        Get the currently assigned strategy for an account.

        Args:
            account_id: Account identifier

        Returns:
            Optional[TradingStrategy]: Assigned strategy or None if no assignment
        """
        if not self.session_factory:
            return None

        async with self.session_factory() as session:
            try:
                # Join StrategyAssignment with Strategy to get details
                stmt = (
                    select(StrategyModel)
                    .join(
                        StrategyAssignmentModel,
                        StrategyModel.id == StrategyAssignmentModel.strategy_id,
                    )
                    .where(
                        and_(
                            StrategyAssignmentModel.account_id == account_id,
                            StrategyAssignmentModel.is_active == True,  # noqa: E712
                        )
                    )
                )
                result = await session.execute(stmt)
                db_strategy = result.scalar_one_or_none()

                if db_strategy:
                    return self._map_db_to_pydantic(db_strategy)
                return None

            except Exception as e:
                logger.error(f"Failed to get account strategy: {e}")
                return None

    async def switch_account_strategy(
        self,
        account_id: int,
        new_strategy_id: str,
        switch_reason: str,
        switched_by: Optional[str] = None,
    ) -> StrategyAssignment:
        """
        Switch an account's strategy.

        Args:
            account_id: Account identifier
            new_strategy_id: New strategy to assign
            switch_reason: Reason for the switch
            switched_by: User who initiated the switch

        Returns:
            StrategyAssignment: New assignment record
        """
        current_strategy = await self.get_account_strategy(account_id)
        current_strategy_id = current_strategy.strategy_id if current_strategy else None

        if current_strategy_id == new_strategy_id:
            raise ValidationError(
                f"Account {account_id} is already using strategy '{new_strategy_id}'"
            )

        # Validate the switch
        await self._validate_strategy_switch(account_id, current_strategy_id, new_strategy_id)

        # Perform the assignment
        return await self.assign_strategy_to_account(
            account_id=account_id,
            strategy_id=new_strategy_id,
            assigned_by=switched_by,
            switch_reason=switch_reason,
        )

    async def _validate_strategy_switch(
        self, account_id: int, current_strategy_id: Optional[str], new_strategy_id: str
    ) -> None:
        """
        Validate a strategy switch operation.

        Args:
            account_id: Account identifier
            current_strategy_id: Current strategy (if any)
            new_strategy_id: New strategy to switch to
        """
        strategy = await self.get_strategy(new_strategy_id)
        if not strategy:
            raise ValidationError(f"Strategy '{new_strategy_id}' not found")

        if not strategy.is_active:
            raise ValidationError(f"Strategy '{new_strategy_id}' is not active")

        if current_strategy_id == "conservative" and new_strategy_id == "aggressive":
            logger.warning(
                f"Switching account {account_id} from conservative to aggressive strategy"
            )

    async def deactivate_strategy(self, strategy_id: str) -> bool:
        """
        Deactivate a strategy (prevent new assignments).

        Args:
            strategy_id: Strategy to deactivate

        Returns:
            bool: True if deactivated, False if not found
        """
        if not self.session_factory:
            return False

        async with self.session_factory() as session:
            try:
                stmt = select(StrategyModel).where(StrategyModel.strategy_id == strategy_id)
                result = await session.execute(stmt)
                strategy = result.scalar_one_or_none()

                if strategy:
                    strategy.is_active = False
                    await session.commit()
                    logger.info(f"Deactivated strategy '{strategy_id}'")
                    return True
                return False
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to deactivate strategy: {e}")
                return False

    async def activate_strategy(self, strategy_id: str) -> bool:
        """
        Activate a strategy (allow new assignments).

        Args:
            strategy_id: Strategy to activate

        Returns:
            bool: True if activated, False if not found
        """
        if not self.session_factory:
            return False

        async with self.session_factory() as session:
            try:
                stmt = select(StrategyModel).where(StrategyModel.strategy_id == strategy_id)
                result = await session.execute(stmt)
                strategy = result.scalar_one_or_none()

                if strategy:
                    strategy.is_active = True
                    await session.commit()
                    logger.info(f"Activated strategy '{strategy_id}'")
                    return True
                return False
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to activate strategy: {e}")
                return False

    async def get_strategy_assignments(self) -> Dict[int, str]:
        """
        Get all current strategy assignments.

        Returns:
            Dict[int, str]: Mapping of account_id to strategy_id
        """
        if not self.session_factory:
            return {}

        async with self.session_factory() as session:
            try:
                stmt = (
                    select(StrategyAssignmentModel, StrategyModel.strategy_id)
                    .join(StrategyModel, StrategyAssignmentModel.strategy_id == StrategyModel.id)
                    .where(StrategyAssignmentModel.is_active == True)  # noqa: E712
                )
                result = await session.execute(stmt)
                assignments = result.all()

                return {
                    assignment[0].account_id: strategy_id for assignment, strategy_id in assignments
                }
            except Exception as e:
                logger.error(f"Failed to get strategy assignments: {e}")
                return {}

    async def get_accounts_using_strategy(self, strategy_id: str) -> List[int]:
        """
        Get all accounts currently using a specific strategy.

        Args:
            strategy_id: Strategy identifier

        Returns:
            List[int]: List of account IDs using the strategy
        """
        if not self.session_factory:
            return []

        async with self.session_factory() as session:
            try:
                stmt = (
                    select(StrategyAssignmentModel.account_id)
                    .join(StrategyModel, StrategyAssignmentModel.strategy_id == StrategyModel.id)
                    .where(
                        and_(
                            StrategyModel.strategy_id == strategy_id,
                            StrategyAssignmentModel.is_active == True,  # noqa: E712
                        )
                    )
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
            except Exception as e:
                logger.error(f"Failed to get accounts using strategy: {e}")
                return []

    async def resolve_strategy_conflicts(self, account_id: int) -> List[str]:
        """
        Check for and resolve strategy conflicts for an account.

        Args:
            account_id: Account to check

        Returns:
            List[str]: List of conflicts found and resolved
        """
        conflicts = []
        strategy = await self.get_account_strategy(account_id)

        if not strategy:
            conflicts.append("No strategy assigned to account")
            # Auto-assign default strategy
            try:
                await self.assign_strategy_to_account(
                    account_id=account_id,
                    strategy_id="conservative",
                    switch_reason="Auto-assigned due to missing strategy",
                )
                conflicts.append("Auto-assigned conservative strategy")
            except Exception as e:
                conflicts.append(f"Failed to auto-assign strategy: {e}")
            return conflicts

        if not strategy.is_active:
            conflicts.append(f"Assigned strategy '{strategy.strategy_id}' is inactive")
            # Switch to default active strategy
            try:
                await self.switch_account_strategy(
                    account_id=account_id,
                    new_strategy_id="conservative",
                    switch_reason="Switched due to inactive strategy",
                )
                conflicts.append("Switched to conservative strategy")
            except Exception as e:
                conflicts.append(f"Failed to switch strategy: {e}")

        return conflicts

    async def switch_by_funding_regime(
        self, account_id: int, market_context: Dict
    ) -> Optional[StrategyAssignment]:
        """
        Switch strategy based on funding rate regime.

        Args:
            account_id: Account identifier
            market_context: Market context containing funding rates

        Returns:
            Optional[StrategyAssignment]: New assignment if switched, None otherwise
        """
        # Calculate average funding rate
        funding_rates = []
        if "assets" in market_context:
            for asset_data in market_context["assets"].values():
                if hasattr(asset_data, "funding_rate") and asset_data.funding_rate is not None:
                    funding_rates.append(asset_data.funding_rate)

        if not funding_rates:
            return None

        avg_funding = sum(funding_rates) / len(funding_rates)
        current_strategy = await self.get_account_strategy(account_id)
        current_strategy_id = current_strategy.strategy_id if current_strategy else None

        # Define thresholds (0.05% = 5 bps)
        HIGH_FUNDING_THRESHOLD = 0.0005
        NEGATIVE_FUNDING_THRESHOLD = -0.0005

        target_strategy = None
        reason = ""

        if avg_funding > HIGH_FUNDING_THRESHOLD:
            if current_strategy_id in ["aggressive", "swing"]:
                target_strategy = "scalping"
                reason = f"High positive funding rate ({avg_funding:.4%}). Switching to Scalping to reduce holding costs."

        elif avg_funding < NEGATIVE_FUNDING_THRESHOLD:
            if current_strategy_id == "scalping":
                target_strategy = "dca"
                reason = f"High negative funding rate ({avg_funding:.4%}). Switching to DCA to capture funding."

        if target_strategy and target_strategy != current_strategy_id:
            logger.info(f"Funding regime switch triggered: {reason}")
            return await self.switch_account_strategy(
                account_id=account_id,
                new_strategy_id=target_strategy,
                switch_reason=reason,
                switched_by="system_funding_monitor",
            )

        return None

    def calculate_strategy_performance(
        self,
        strategy_id: str,
        trades: List[Dict],
        period_start: datetime,
        period_end: datetime,
    ) -> StrategyPerformance:
        """
        Calculate performance metrics for a strategy.
        """
        total_trades = len(trades)
        period_days = max(1, (period_end - period_start).days)

        if total_trades == 0:
            return StrategyPerformance(
                strategy_id=strategy_id,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                max_win=0.0,
                max_loss=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                profit_factor=1.0,  # Default to 1.0 for no trades
                avg_trade_duration_hours=0.0,
                total_volume_traded=0.0,
                total_fees_paid=0.0,
                total_funding_paid=0.0,
                total_liquidations=0,
                start_date=period_start,
                end_date=period_end,
                period_days=period_days,
            )

        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) <= 0]

        total_pnl = sum(t.get("pnl", 0) for t in trades)
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0.0

        gross_profit = sum(t.get("pnl", 0) for t in winning_trades)
        gross_loss = abs(sum(t.get("pnl", 0) for t in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
        if profit_factor == float("inf"):
            profit_factor = 100.0  # Cap at reasonable value

        # Calculate averages
        avg_win = (gross_profit / len(winning_trades)) if winning_trades else 0.0
        avg_loss = (-gross_loss / len(losing_trades)) if losing_trades else 0.0

        # Max win/loss
        max_win = max([t.get("pnl", 0) for t in trades], default=0.0)
        max_loss = min([t.get("pnl", 0) for t in trades], default=0.0)

        # Volume
        total_volume = sum(t.get("volume", 0) for t in trades)

        # Fees and Funding
        total_fees = sum(t.get("fee", 0) for t in trades)
        total_funding = sum(t.get("funding", 0) for t in trades)
        total_liquidations = sum(1 for t in trades if t.get("is_liquidation"))

        # Duration (mock calculation if entry/exit times not available)
        total_duration_hours = 0.0
        for t in trades:
            if "entry_time" in t and "exit_time" in t:
                duration = (t["exit_time"] - t["entry_time"]).total_seconds() / 3600
                total_duration_hours += duration

        avg_duration = (total_duration_hours / total_trades) if total_trades > 0 else 0.0

        return StrategyPerformance(
            strategy_id=strategy_id,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_win=max_win,
            max_loss=max_loss,
            max_drawdown=0.0,  # Placeholder, requires equity curve
            sharpe_ratio=0.0,  # Placeholder
            sortino_ratio=0.0,  # Placeholder
            profit_factor=profit_factor,
            avg_trade_duration_hours=avg_duration,
            total_volume_traded=total_volume,
            total_fees_paid=total_fees,
            total_funding_paid=total_funding,
            total_liquidations=total_liquidations,
            start_date=period_start,
            end_date=period_end,
            period_days=period_days,
        )

    def _map_db_to_pydantic(self, db_strategy: StrategyModel) -> TradingStrategy:
        """Map database model to Pydantic model."""
        return TradingStrategy(
            strategy_id=db_strategy.strategy_id,
            strategy_name=db_strategy.strategy_name,
            strategy_type=db_strategy.strategy_type,
            prompt_template=db_strategy.prompt_template,
            risk_parameters=StrategyRiskParameters(**db_strategy.risk_parameters),
            timeframe_preference=db_strategy.timeframe_preference,
            max_positions=db_strategy.max_positions,
            position_sizing=db_strategy.position_sizing,
            order_preference=db_strategy.order_preference,
            funding_rate_threshold=db_strategy.funding_rate_threshold,
            is_active=db_strategy.is_active,
        )
