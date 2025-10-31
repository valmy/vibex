"""
Strategy Manager Service for LLM Decision Engine.

Provides comprehensive strategy management including configuration loading,
strategy assignment, switching, and performance tracking.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...core.exceptions import ConfigurationError, ValidationError
from ...schemas.trading_decision import (
    StrategyAlert,
    StrategyAssignment,
    StrategyComparison,
    StrategyMetrics,
    StrategyPerformance,
    StrategyRiskParameters,
    TradingStrategy,
)

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages trading strategies for the LLM Decision Engine.

    Handles strategy configuration, assignment, switching, and performance tracking.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the Strategy Manager.

        Args:
            config_path: Path to strategy configuration files directory
        """
        self.config_path = config_path or Path("config/strategies")
        self._strategies: Dict[str, TradingStrategy] = {}
        self._strategy_assignments: Dict[int, str] = {}  # account_id -> strategy_id
        self._performance_cache: Dict[str, StrategyPerformance] = {}
        self._metrics_cache: Dict[
            Tuple[str, int], StrategyMetrics
        ] = {}  # (strategy_id, account_id)
        self._alerts: List[StrategyAlert] = []

        # Initialize predefined strategies
        self._initialize_predefined_strategies()

    def _initialize_predefined_strategies(self) -> None:
        """Initialize predefined trading strategies."""

        # Conservative Strategy
        conservative_strategy = TradingStrategy(
            strategy_id="conservative",
            strategy_name="Conservative Trading",
            strategy_type="conservative",
            prompt_template=self._get_conservative_prompt_template(),
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=2.0,
                max_daily_loss=5.0,
                stop_loss_percentage=3.0,
                take_profit_ratio=2.0,
                max_leverage=2.0,
                cooldown_period=600,  # 10 minutes
            ),
            timeframe_preference=["4h", "1d"],
            max_positions=2,
            position_sizing="percentage",
            is_active=True,
        )

        # Aggressive Strategy
        aggressive_strategy = TradingStrategy(
            strategy_id="aggressive",
            strategy_name="Aggressive Trading",
            strategy_type="aggressive",
            prompt_template=self._get_aggressive_prompt_template(),
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=5.0,
                max_daily_loss=15.0,
                stop_loss_percentage=5.0,
                take_profit_ratio=3.0,
                max_leverage=5.0,
                cooldown_period=300,  # 5 minutes
            ),
            timeframe_preference=["1h", "4h"],
            max_positions=5,
            position_sizing="volatility_adjusted",
            is_active=True,
        )

        # Scalping Strategy
        scalping_strategy = TradingStrategy(
            strategy_id="scalping",
            strategy_name="Scalping Strategy",
            strategy_type="scalping",
            prompt_template=self._get_scalping_prompt_template(),
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=1.0,
                max_daily_loss=8.0,
                stop_loss_percentage=1.5,
                take_profit_ratio=1.5,
                max_leverage=3.0,
                cooldown_period=60,  # 1 minute
            ),
            timeframe_preference=["1m", "5m", "15m"],
            max_positions=3,
            position_sizing="fixed",
            is_active=True,
        )

        # Swing Strategy
        swing_strategy = TradingStrategy(
            strategy_id="swing",
            strategy_name="Swing Trading",
            strategy_type="swing",
            prompt_template=self._get_swing_prompt_template(),
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=3.0,
                max_daily_loss=10.0,
                stop_loss_percentage=4.0,
                take_profit_ratio=2.5,
                max_leverage=3.0,
                cooldown_period=1800,  # 30 minutes
            ),
            timeframe_preference=["4h", "1d", "3d"],
            max_positions=3,
            position_sizing="kelly",
            is_active=True,
        )

        # DCA Strategy
        dca_strategy = TradingStrategy(
            strategy_id="dca",
            strategy_name="Dollar Cost Averaging",
            strategy_type="dca",
            prompt_template=self._get_dca_prompt_template(),
            risk_parameters=StrategyRiskParameters(
                max_risk_per_trade=1.5,
                max_daily_loss=3.0,
                stop_loss_percentage=10.0,  # Wider stops for DCA
                take_profit_ratio=1.8,
                max_leverage=1.5,
                cooldown_period=3600,  # 1 hour
            ),
            timeframe_preference=["1d", "3d", "1w"],
            max_positions=2,
            position_sizing="fixed",
            is_active=True,
        )

        # Store predefined strategies
        self._strategies = {
            "conservative": conservative_strategy,
            "aggressive": aggressive_strategy,
            "scalping": scalping_strategy,
            "swing": swing_strategy,
            "dca": dca_strategy,
        }

        logger.info(f"Initialized {len(self._strategies)} predefined strategies")

    def _get_conservative_prompt_template(self) -> str:
        """Get prompt template for conservative strategy."""
        return """
You are a conservative cryptocurrency trading advisor. Your primary goal is capital preservation with steady, low-risk returns.

STRATEGY GUIDELINES:
- Focus on strong support/resistance levels and well-established trends
- Prioritize risk management over profit maximization
- Only enter trades with high probability setups (>70% confidence)
- Use tight stop-losses and reasonable take-profits (2:1 ratio minimum)
- Avoid trading during high volatility periods or major news events
- Prefer longer timeframes (4h, 1d) for more stable signals

RISK MANAGEMENT:
- Maximum 2% risk per trade
- Maximum 5% daily loss limit
- Use 3% stop-loss as default
- Take profits at 2x risk (6% target)
- Maximum 2 concurrent positions

MARKET CONDITIONS TO AVOID:
- High volatility (ATR > 5% of price)
- Major news events or announcements
- Low volume periods
- Unclear market structure

Analyze the provided market data and account context. If conditions are favorable, provide a conservative trading recommendation. If not, recommend holding or reducing exposure.
"""

    def _get_aggressive_prompt_template(self) -> str:
        """Get prompt template for aggressive strategy."""
        return """
You are an aggressive cryptocurrency trading advisor focused on maximizing returns through high-probability momentum trades.

STRATEGY GUIDELINES:
- Look for strong momentum and breakout opportunities
- Accept higher risk for potentially greater returns
- Enter trades with strong technical confirmation
- Use wider stops but maintain favorable risk/reward ratios (3:1 minimum)
- Take advantage of volatility and market inefficiencies
- Focus on shorter to medium timeframes (1h, 4h)

RISK MANAGEMENT:
- Maximum 5% risk per trade
- Maximum 15% daily loss limit
- Use 5% stop-loss as default
- Take profits at 3x risk (15% target)
- Maximum 5 concurrent positions

FAVORABLE CONDITIONS:
- Strong momentum with volume confirmation
- Clear breakouts above/below key levels
- High volatility with directional bias
- Strong technical indicator alignment

ENTRY CRITERIA:
- Multiple timeframe confirmation
- Volume above average
- Clear risk/reward setup
- Strong momentum indicators (MACD, RSI divergence)

Analyze the market data aggressively. Look for high-probability setups that offer significant profit potential while maintaining proper risk management.
"""

    def _get_scalping_prompt_template(self) -> str:
        """Get prompt template for scalping strategy."""
        return """
You are a scalping trading advisor focused on quick, small profits from short-term price movements.

STRATEGY GUIDELINES:
- Focus on very short timeframes (1m, 5m, 15m)
- Look for quick profit opportunities with tight spreads
- Enter and exit trades rapidly (minutes to hours)
- Use small position sizes with tight stops
- Focus on high-frequency, low-risk trades
- Target small but consistent profits

RISK MANAGEMENT:
- Maximum 1% risk per trade
- Maximum 8% daily loss limit
- Use 1.5% stop-loss as default
- Take profits at 1.5x risk (2.25% target)
- Maximum 3 concurrent positions
- Very short cooldown periods (1 minute)

IDEAL CONDITIONS:
- High liquidity and tight spreads
- Clear short-term support/resistance levels
- Stable market conditions without major news
- Good technical indicator signals on short timeframes

ENTRY SIGNALS:
- Price bouncing off support/resistance
- Short-term momentum shifts
- RSI oversold/overbought reversals
- Quick breakouts with volume

Focus on quick, precise entries and exits. Avoid holding positions during uncertain periods. Cut losses quickly and take profits at predetermined levels.
"""

    def _get_swing_prompt_template(self) -> str:
        """Get prompt template for swing strategy."""
        return """
You are a swing trading advisor focused on capturing medium-term price movements over days to weeks.

STRATEGY GUIDELINES:
- Analyze medium to long-term trends (4h, 1d, 3d timeframes)
- Look for swing highs and lows for entry/exit points
- Hold positions for several days to weeks
- Focus on major support/resistance levels and trend changes
- Use fundamental analysis alongside technical analysis
- Be patient and wait for high-quality setups

RISK MANAGEMENT:
- Maximum 3% risk per trade
- Maximum 10% daily loss limit
- Use 4% stop-loss as default
- Take profits at 2.5x risk (10% target)
- Maximum 3 concurrent positions
- Longer cooldown periods (30 minutes)

IDEAL SETUPS:
- Clear trend reversals at major levels
- Breakouts from consolidation patterns
- Divergences between price and indicators
- Strong fundamental catalysts supporting technical setup

ANALYSIS FOCUS:
- Major support/resistance levels
- Trend line breaks and retests
- Chart patterns (triangles, flags, head & shoulders)
- Volume confirmation on breakouts
- Multi-timeframe trend alignment

Take time to analyze the bigger picture. Look for high-quality swing opportunities that align with the overall market trend and have strong technical confirmation.
"""

    def _get_dca_prompt_template(self) -> str:
        """Get prompt template for DCA strategy."""
        return """
You are a Dollar Cost Averaging (DCA) trading advisor focused on systematic accumulation during favorable market conditions.

STRATEGY GUIDELINES:
- Focus on systematic buying during market downturns
- Use longer timeframes (1d, 3d, 1w) for trend analysis
- Accumulate positions gradually rather than all at once
- Focus on strong assets during temporary weakness
- Use wider stops to avoid being shaken out of positions
- Be patient and focus on long-term value accumulation

RISK MANAGEMENT:
- Maximum 1.5% risk per trade
- Maximum 3% daily loss limit
- Use 10% stop-loss (wider for DCA approach)
- Take profits at 1.8x risk (2.7% target) or hold for longer term
- Maximum 2 concurrent DCA positions
- Longer cooldown periods (1 hour)

DCA CONDITIONS:
- Market in downtrend or consolidation
- Asset showing relative strength
- Good long-term fundamentals
- Oversold conditions on longer timeframes

ACCUMULATION STRATEGY:
- Buy on dips and weakness
- Average down on strong assets
- Focus on quality over quantity
- Use market volatility as opportunity
- Maintain long-term perspective

Analyze market conditions for DCA opportunities. Focus on high-quality assets that are temporarily undervalued. Be patient and systematic in your approach.
"""

    async def load_strategy_from_file(self, file_path: Path) -> TradingStrategy:
        """
        Load a strategy configuration from a JSON file.

        Args:
            file_path: Path to the strategy configuration file

        Returns:
            TradingStrategy: Loaded strategy configuration

        Raises:
            ConfigurationError: If file cannot be loaded or parsed
            ValidationError: If strategy configuration is invalid
        """
        try:
            with open(file_path, "r") as f:
                strategy_data = json.load(f)

            # Validate and create strategy
            strategy = TradingStrategy(**strategy_data)

            # Validate strategy constraints
            validation_errors = strategy.validate_strategy_constraints()
            if validation_errors:
                raise ValidationError(f"Strategy validation failed: {', '.join(validation_errors)}")

            logger.info(f"Loaded strategy '{strategy.strategy_id}' from {file_path}")
            return strategy

        except FileNotFoundError:
            raise ConfigurationError(f"Strategy file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in strategy file {file_path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading strategy from {file_path}: {e}")

    async def save_strategy_to_file(self, strategy: TradingStrategy, file_path: Path) -> None:
        """
        Save a strategy configuration to a JSON file.

        Args:
            strategy: Strategy to save
            file_path: Path where to save the strategy

        Raises:
            ConfigurationError: If file cannot be saved
        """
        try:
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert strategy to dict and save
            strategy_data = strategy.model_dump()
            with open(file_path, "w") as f:
                json.dump(strategy_data, f, indent=2, default=str)

            logger.info(f"Saved strategy '{strategy.strategy_id}' to {file_path}")

        except Exception as e:
            raise ConfigurationError(f"Error saving strategy to {file_path}: {e}")

    async def create_custom_strategy(
        self,
        strategy_id: str,
        strategy_name: str,
        prompt_template: str,
        risk_parameters: StrategyRiskParameters,
        timeframe_preference: List[str] = None,
        max_positions: int = 3,
        position_sizing: str = "percentage",
    ) -> TradingStrategy:
        """
        Create a custom trading strategy.

        Args:
            strategy_id: Unique identifier for the strategy
            strategy_name: Human-readable name
            prompt_template: LLM prompt template
            risk_parameters: Risk management parameters
            timeframe_preference: Preferred timeframes
            max_positions: Maximum concurrent positions
            position_sizing: Position sizing method

        Returns:
            TradingStrategy: Created custom strategy

        Raises:
            ValidationError: If strategy configuration is invalid
        """
        if strategy_id in self._strategies:
            raise ValidationError(f"Strategy '{strategy_id}' already exists")

        if timeframe_preference is None:
            timeframe_preference = ["1h", "4h"]

        custom_strategy = TradingStrategy(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            strategy_type="custom",
            prompt_template=prompt_template,
            risk_parameters=risk_parameters,
            timeframe_preference=timeframe_preference,
            max_positions=max_positions,
            position_sizing=position_sizing,
            is_active=True,
        )

        # Validate strategy constraints
        validation_errors = custom_strategy.validate_strategy_constraints()
        if validation_errors:
            raise ValidationError(
                f"Custom strategy validation failed: {', '.join(validation_errors)}"
            )

        # Store the strategy
        self._strategies[strategy_id] = custom_strategy

        # Save to file if config path exists
        if self.config_path.exists():
            file_path = self.config_path / f"{strategy_id}.json"
            await self.save_strategy_to_file(custom_strategy, file_path)

        logger.info(f"Created custom strategy '{strategy_id}'")
        return custom_strategy

    async def get_available_strategies(self) -> List[TradingStrategy]:
        """
        Get all available trading strategies.

        Returns:
            List[TradingStrategy]: List of all available strategies
        """
        return list(self._strategies.values())

    async def get_strategy(self, strategy_id: str) -> Optional[TradingStrategy]:
        """
        Get a specific strategy by ID.

        Args:
            strategy_id: Strategy identifier

        Returns:
            Optional[TradingStrategy]: Strategy if found, None otherwise
        """
        return self._strategies.get(strategy_id)

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

        Raises:
            ValidationError: If strategy doesn't exist or assignment is invalid
        """
        if strategy_id not in self._strategies:
            raise ValidationError(f"Strategy '{strategy_id}' not found")

        strategy = self._strategies[strategy_id]
        if not strategy.is_active:
            raise ValidationError(f"Strategy '{strategy_id}' is not active")

        # Get previous strategy if any
        previous_strategy_id = self._strategy_assignments.get(account_id)

        # Create assignment record
        assignment = StrategyAssignment(
            account_id=account_id,
            strategy_id=strategy_id,
            assigned_by=assigned_by,
            previous_strategy_id=previous_strategy_id,
            switch_reason=switch_reason,
        )

        # Update assignment mapping
        self._strategy_assignments[account_id] = strategy_id

        logger.info(
            f"Assigned strategy '{strategy_id}' to account {account_id}"
            f"{f' (switched from {previous_strategy_id})' if previous_strategy_id else ''}"
        )

        return assignment

    async def get_account_strategy(self, account_id: int) -> Optional[TradingStrategy]:
        """
        Get the currently assigned strategy for an account.

        Args:
            account_id: Account identifier

        Returns:
            Optional[TradingStrategy]: Assigned strategy or None if no assignment
        """
        strategy_id = self._strategy_assignments.get(account_id)
        if strategy_id:
            return self._strategies.get(strategy_id)
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

        Raises:
            ValidationError: If switch is invalid
        """
        current_strategy_id = self._strategy_assignments.get(account_id)

        if current_strategy_id == new_strategy_id:
            raise ValidationError(
                f"Account {account_id} is already using strategy '{new_strategy_id}'"
            )

        # Validate the switch (could add business rules here)
        await self._validate_strategy_switch(account_id, current_strategy_id, new_strategy_id)

        # Perform the assignment
        assignment = await self.assign_strategy_to_account(
            account_id=account_id,
            strategy_id=new_strategy_id,
            assigned_by=switched_by,
            switch_reason=switch_reason,
        )

        logger.info(
            f"Switched account {account_id} from '{current_strategy_id}' to '{new_strategy_id}': {switch_reason}"
        )

        return assignment

    async def _validate_strategy_switch(
        self, account_id: int, current_strategy_id: Optional[str], new_strategy_id: str
    ) -> None:
        """
        Validate a strategy switch operation.

        Args:
            account_id: Account identifier
            current_strategy_id: Current strategy (if any)
            new_strategy_id: New strategy to switch to

        Raises:
            ValidationError: If switch is not allowed
        """
        # Check if new strategy exists and is active
        new_strategy = self._strategies.get(new_strategy_id)
        if not new_strategy:
            raise ValidationError(f"Strategy '{new_strategy_id}' not found")

        if not new_strategy.is_active:
            raise ValidationError(f"Strategy '{new_strategy_id}' is not active")

        # Add business rules for strategy switching
        # For example, prevent switching from conservative to aggressive without approval
        if current_strategy_id == "conservative" and new_strategy_id == "aggressive":
            logger.warning(
                f"Switching account {account_id} from conservative to aggressive strategy"
            )

        # Could add more validation rules here:
        # - Check account balance requirements
        # - Check if account has open positions that conflict with new strategy
        # - Check cooldown periods between switches
        # - etc.

    async def deactivate_strategy(self, strategy_id: str) -> bool:
        """
        Deactivate a strategy (prevent new assignments).

        Args:
            strategy_id: Strategy to deactivate

        Returns:
            bool: True if deactivated, False if not found
        """
        strategy = self._strategies.get(strategy_id)
        if strategy:
            strategy.is_active = False
            logger.info(f"Deactivated strategy '{strategy_id}'")
            return True
        return False

    async def activate_strategy(self, strategy_id: str) -> bool:
        """
        Activate a strategy (allow new assignments).

        Args:
            strategy_id: Strategy to activate

        Returns:
            bool: True if activated, False if not found
        """
        strategy = self._strategies.get(strategy_id)
        if strategy:
            strategy.is_active = True
            logger.info(f"Activated strategy '{strategy_id}'")
            return True
        return False

    async def get_strategy_assignments(self) -> Dict[int, str]:
        """
        Get all current strategy assignments.

        Returns:
            Dict[int, str]: Mapping of account_id to strategy_id
        """
        return self._strategy_assignments.copy()

    async def get_accounts_using_strategy(self, strategy_id: str) -> List[int]:
        """
        Get all accounts currently using a specific strategy.

        Args:
            strategy_id: Strategy identifier

        Returns:
            List[int]: List of account IDs using the strategy
        """
        return [
            account_id
            for account_id, assigned_strategy_id in self._strategy_assignments.items()
            if assigned_strategy_id == strategy_id
        ]

    async def resolve_strategy_conflicts(self, account_id: int) -> List[str]:
        """
        Check for and resolve strategy conflicts for an account.

        Args:
            account_id: Account to check

        Returns:
            List[str]: List of conflicts found and resolved
        """
        conflicts = []
        strategy_id = self._strategy_assignments.get(account_id)

        if not strategy_id:
            conflicts.append("No strategy assigned to account")
            # Auto-assign default strategy
            await self.assign_strategy_to_account(
                account_id=account_id,
                strategy_id="conservative",
                switch_reason="Auto-assigned due to missing strategy",
            )
            conflicts.append("Auto-assigned conservative strategy")
            return conflicts

        strategy = self._strategies.get(strategy_id)
        if not strategy:
            conflicts.append(f"Assigned strategy '{strategy_id}' not found")
            # Auto-assign default strategy
            await self.assign_strategy_to_account(
                account_id=account_id,
                strategy_id="conservative",
                switch_reason="Auto-assigned due to missing strategy",
            )
            conflicts.append("Auto-assigned conservative strategy")

        elif not strategy.is_active:
            conflicts.append(f"Assigned strategy '{strategy_id}' is inactive")
            # Switch to default active strategy
            await self.switch_account_strategy(
                account_id=account_id,
                new_strategy_id="conservative",
                switch_reason="Switched due to inactive strategy",
            )
            conflicts.append("Switched to conservative strategy")

        return conflicts

    async def update_strategy_metrics(
        self,
        strategy_id: str,
        account_id: int,
        current_positions: int,
        total_allocated: float,
        unrealized_pnl: float,
        realized_pnl_today: float,
        trades_today: int,
        last_trade_time: Optional[datetime] = None,
    ) -> StrategyMetrics:
        """
        Update real-time metrics for a strategy.

        Args:
            strategy_id: Strategy identifier
            account_id: Account identifier
            current_positions: Number of current positions
            total_allocated: Total allocated capital
            unrealized_pnl: Unrealized P&L
            realized_pnl_today: Realized P&L for today
            trades_today: Number of trades today
            last_trade_time: Time of last trade

        Returns:
            StrategyMetrics: Updated metrics
        """
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            raise ValidationError(f"Strategy '{strategy_id}' not found")

        # Calculate risk utilization
        max_risk = strategy.risk_parameters.max_daily_loss
        risk_utilization = (
            min(100.0, abs(realized_pnl_today) / max_risk * 100) if max_risk > 0 else 0.0
        )

        # Calculate cooldown remaining
        cooldown_remaining = 0
        if last_trade_time:
            time_since_trade = (datetime.now(timezone.utc) - last_trade_time).total_seconds()
            cooldown_remaining = max(
                0, strategy.risk_parameters.cooldown_period - int(time_since_trade)
            )

        metrics = StrategyMetrics(
            strategy_id=strategy_id,
            account_id=account_id,
            current_positions=current_positions,
            total_allocated=total_allocated,
            unrealized_pnl=unrealized_pnl,
            realized_pnl_today=realized_pnl_today,
            trades_today=trades_today,
            last_trade_time=last_trade_time,
            risk_utilization=risk_utilization,
            cooldown_remaining=cooldown_remaining,
        )

        # Cache the metrics
        self._metrics_cache[(strategy_id, account_id)] = metrics

        # Check for alerts
        await self._check_strategy_alerts(metrics)

        return metrics

    async def get_strategy_metrics(
        self, strategy_id: str, account_id: int
    ) -> Optional[StrategyMetrics]:
        """
        Get current metrics for a strategy.

        Args:
            strategy_id: Strategy identifier
            account_id: Account identifier

        Returns:
            Optional[StrategyMetrics]: Current metrics or None if not found
        """
        return self._metrics_cache.get((strategy_id, account_id))

    async def calculate_strategy_performance(
        self,
        strategy_id: str,
        start_date: datetime,
        end_date: datetime,
        trades_data: List[dict],  # Trade data from database
    ) -> StrategyPerformance:
        """
        Calculate comprehensive performance metrics for a strategy.

        Args:
            strategy_id: Strategy identifier
            start_date: Performance calculation start date
            end_date: Performance calculation end date
            trades_data: List of trade data dictionaries

        Returns:
            StrategyPerformance: Calculated performance metrics
        """
        if not trades_data:
            # Return empty performance if no trades
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
                profit_factor=1.0,
                avg_trade_duration_hours=0.0,
                total_volume_traded=0.0,
                start_date=start_date,
                end_date=end_date,
                period_days=(end_date - start_date).days,
            )

        # Calculate basic metrics
        total_trades = len(trades_data)
        winning_trades = sum(1 for trade in trades_data if trade.get("pnl", 0) > 0)
        losing_trades = sum(1 for trade in trades_data if trade.get("pnl", 0) < 0)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # P&L calculations
        pnls = [trade.get("pnl", 0) for trade in trades_data]
        total_pnl = sum(pnls)

        winning_pnls = [pnl for pnl in pnls if pnl > 0]
        losing_pnls = [pnl for pnl in pnls if pnl < 0]

        avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0.0
        avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0.0
        max_win = max(pnls) if pnls else 0.0
        max_loss = min(pnls) if pnls else 0.0

        # Calculate profit factor
        gross_profit = sum(winning_pnls) if winning_pnls else 0.0
        gross_loss = abs(sum(losing_pnls)) if losing_pnls else 0.0
        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else (gross_profit if gross_profit > 0 else 1.0)
        )

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(pnls)

        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = None
        if len(pnls) > 1:
            import statistics

            avg_return = statistics.mean(pnls)
            std_return = statistics.stdev(pnls)
            sharpe_ratio = avg_return / std_return if std_return > 0 else 0.0

        # Calculate Sortino ratio (downside deviation)
        sortino_ratio = None
        if losing_pnls:
            import statistics

            avg_return = sum(pnls) / len(pnls)
            downside_deviation = statistics.stdev(losing_pnls)
            sortino_ratio = avg_return / downside_deviation if downside_deviation > 0 else 0.0

        # Calculate average trade duration
        durations = []
        for trade in trades_data:
            if "entry_time" in trade and "exit_time" in trade:
                entry_time = trade["entry_time"]
                exit_time = trade["exit_time"]
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                if isinstance(exit_time, str):
                    exit_time = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
                duration = (exit_time - entry_time).total_seconds() / 3600  # hours
                durations.append(duration)

        avg_trade_duration_hours = sum(durations) / len(durations) if durations else 0.0

        # Calculate total volume
        total_volume_traded = sum(trade.get("volume", 0) for trade in trades_data)

        performance = StrategyPerformance(
            strategy_id=strategy_id,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_win=max_win,
            max_loss=max_loss,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            profit_factor=profit_factor,
            avg_trade_duration_hours=avg_trade_duration_hours,
            total_volume_traded=total_volume_traded,
            start_date=start_date,
            end_date=end_date,
            period_days=(end_date - start_date).days,
        )

        # Cache the performance
        self._performance_cache[strategy_id] = performance

        return performance

    def _calculate_max_drawdown(self, pnls: List[float]) -> float:
        """Calculate maximum drawdown from P&L series."""
        if not pnls:
            return 0.0

        cumulative_pnl = 0.0
        peak = 0.0
        max_drawdown = 0.0

        for pnl in pnls:
            cumulative_pnl += pnl
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            drawdown = peak - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown

    async def get_strategy_performance(
        self, strategy_id: str, timeframe: str = "7d"
    ) -> Optional[StrategyPerformance]:
        """
        Get cached performance metrics for a strategy.

        Args:
            strategy_id: Strategy identifier
            timeframe: Timeframe for performance (not used in cache lookup)

        Returns:
            Optional[StrategyPerformance]: Cached performance or None
        """
        return self._performance_cache.get(strategy_id)

    async def compare_strategies(
        self,
        strategy_ids: List[str],
        comparison_period_days: int = 30,
        ranking_criteria: str = "sharpe_ratio",
    ) -> StrategyComparison:
        """
        Compare performance of multiple strategies.

        Args:
            strategy_ids: List of strategy IDs to compare
            comparison_period_days: Period for comparison
            ranking_criteria: Criteria for ranking strategies

        Returns:
            StrategyComparison: Comparison results
        """
        strategies_performance = []

        for strategy_id in strategy_ids:
            performance = self._performance_cache.get(strategy_id)
            if performance:
                strategies_performance.append(performance)

        if not strategies_performance:
            raise ValidationError("No performance data available for comparison")

        # Rank strategies based on criteria
        if ranking_criteria == "total_pnl":
            best_strategy = max(strategies_performance, key=lambda x: x.total_pnl)
        elif ranking_criteria == "win_rate":
            best_strategy = max(strategies_performance, key=lambda x: x.win_rate)
        elif ranking_criteria == "profit_factor":
            best_strategy = max(strategies_performance, key=lambda x: x.profit_factor)
        else:  # sharpe_ratio
            best_strategy = max(
                strategies_performance,
                key=lambda x: x.sharpe_ratio if x.sharpe_ratio is not None else -999,
            )

        return StrategyComparison(
            strategies=strategies_performance,
            comparison_period_days=comparison_period_days,
            best_performing_strategy=best_strategy.strategy_id,
            ranking_criteria=ranking_criteria,
        )

    async def get_strategy_recommendations(self, account_id: int) -> List[str]:
        """
        Get strategy recommendations based on performance.

        Args:
            account_id: Account identifier

        Returns:
            List[str]: List of recommendations
        """
        recommendations = []
        current_strategy_id = self._strategy_assignments.get(account_id)

        if not current_strategy_id:
            recommendations.append(
                "No strategy assigned. Consider starting with 'conservative' strategy."
            )
            return recommendations

        current_performance = self._performance_cache.get(current_strategy_id)
        if not current_performance:
            recommendations.append("Insufficient performance data for recommendations.")
            return recommendations

        # Check if current strategy needs attention
        if current_performance.needs_attention():
            recommendations.append(
                f"Current strategy '{current_strategy_id}' shows concerning performance patterns."
            )

            # Suggest alternative strategies
            if current_performance.win_rate < 30:
                recommendations.append(
                    "Consider switching to 'conservative' strategy for better win rate."
                )

            if current_performance.max_drawdown < -1000:
                recommendations.append(
                    "Consider reducing position sizes or switching to lower-risk strategy."
                )

        # Performance-based recommendations
        grade = current_performance.get_performance_grade()
        if grade in ["A+", "A"]:
            recommendations.append(
                f"Excellent performance (Grade: {grade}). Continue with current strategy."
            )
        elif grade in ["B+", "B"]:
            recommendations.append(
                f"Good performance (Grade: {grade}). Consider minor optimizations."
            )
        elif grade in ["C+", "C"]:
            recommendations.append(
                f"Average performance (Grade: {grade}). Review strategy parameters."
            )
        else:
            recommendations.append(f"Poor performance (Grade: {grade}). Consider strategy change.")

        return recommendations

    async def _check_strategy_alerts(self, metrics: StrategyMetrics) -> None:
        """
        Check for strategy performance alerts.

        Args:
            metrics: Current strategy metrics
        """
        strategy = self._strategies.get(metrics.strategy_id)
        if not strategy:
            return

        alerts = []

        # Check daily loss limit
        daily_loss_limit = strategy.risk_parameters.max_daily_loss
        if abs(metrics.realized_pnl_today) >= daily_loss_limit:
            alerts.append(
                StrategyAlert(
                    strategy_id=metrics.strategy_id,
                    account_id=metrics.account_id,
                    alert_type="risk_limit_exceeded",
                    severity="critical",
                    message=f"Daily loss limit exceeded: {metrics.realized_pnl_today:.2f} >= {daily_loss_limit:.2f}",
                    threshold_value=daily_loss_limit,
                    current_value=abs(metrics.realized_pnl_today),
                )
            )

        # Check risk utilization
        if metrics.risk_utilization >= 90:
            alerts.append(
                StrategyAlert(
                    strategy_id=metrics.strategy_id,
                    account_id=metrics.account_id,
                    alert_type="risk_limit_exceeded",
                    severity="high",
                    message=f"High risk utilization: {metrics.risk_utilization:.1f}%",
                    threshold_value=90.0,
                    current_value=metrics.risk_utilization,
                )
            )

        # Check for consecutive losses (simplified - would need trade history)
        if metrics.realized_pnl_today < -500 and metrics.trades_today >= 3:
            alerts.append(
                StrategyAlert(
                    strategy_id=metrics.strategy_id,
                    account_id=metrics.account_id,
                    alert_type="consecutive_losses",
                    severity="medium",
                    message=f"Multiple losing trades today: {metrics.trades_today} trades, PnL: {metrics.realized_pnl_today:.2f}",
                    current_value=metrics.realized_pnl_today,
                )
            )

        # Add alerts to the list
        self._alerts.extend(alerts)

        # Log critical alerts
        for alert in alerts:
            if alert.severity == "critical":
                logger.error(f"CRITICAL ALERT: {alert.message}")
            elif alert.severity == "high":
                logger.warning(f"HIGH ALERT: {alert.message}")

    async def get_strategy_alerts(
        self,
        strategy_id: Optional[str] = None,
        account_id: Optional[int] = None,
        severity: Optional[str] = None,
    ) -> List[StrategyAlert]:
        """
        Get strategy alerts with optional filtering.

        Args:
            strategy_id: Filter by strategy ID
            account_id: Filter by account ID
            severity: Filter by severity level

        Returns:
            List[StrategyAlert]: Filtered list of alerts
        """
        alerts = self._alerts.copy()

        if strategy_id:
            alerts = [a for a in alerts if a.strategy_id == strategy_id]

        if account_id:
            alerts = [a for a in alerts if a.account_id == account_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    async def acknowledge_alert(self, alert_index: int, acknowledged_by: str) -> bool:
        """
        Acknowledge a strategy alert.

        Args:
            alert_index: Index of alert to acknowledge
            acknowledged_by: User acknowledging the alert

        Returns:
            bool: True if acknowledged, False if not found
        """
        if 0 <= alert_index < len(self._alerts):
            alert = self._alerts[alert_index]
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now(timezone.utc)
            logger.info(f"Alert acknowledged by {acknowledged_by}: {alert.message}")
            return True
        return False

    async def clear_old_alerts(self, max_age_hours: int = 24) -> int:
        """
        Clear old alerts to prevent memory buildup.

        Args:
            max_age_hours: Maximum age of alerts to keep

        Returns:
            int: Number of alerts cleared
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        initial_count = len(self._alerts)

        self._alerts = [
            alert
            for alert in self._alerts
            if alert.created_at > cutoff_time or not alert.acknowledged
        ]

        cleared_count = initial_count - len(self._alerts)
        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} old alerts")

        return cleared_count
