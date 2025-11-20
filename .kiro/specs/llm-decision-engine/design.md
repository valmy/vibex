# LLM Decision Engine Integration - Design Document

## Overview

The LLM Decision Engine Integration enhances the existing AI Trading Agent by implementing a sophisticated decision-making system that leverages Large Language Models for intelligent trading decisions. This system builds upon the existing `LLMService` foundation and integrates with the technical analysis service, market data service, and account management to provide comprehensive trading intelligence.

The design focuses on creating a robust, scalable, and maintainable system that can handle real-time trading decisions while ensuring data integrity, error handling, and performance optimization.

## Schema Unification (2025-11-02)

**IMPORTANT**: The codebase previously had two different `TradingContext` schemas:

1. `app.schemas.context.TradingContext` (used by ContextBuilderService) - **DEPRECATED**
2. `app.schemas.trading_decision.TradingContext` (used by LLMService) - **CANONICAL**

These schemas have been unified to use `app.schemas.trading_decision.TradingContext` as the single canonical schema throughout the codebase.

### Key Changes

- **Deleted**: `backend/src/app/schemas/context.py` (entire file removed)
- **Updated**: `ContextBuilderService` now uses schemas from `app.schemas.trading_decision`
- **TechnicalIndicators**: Changed from nested structure (EMAOutput, MACDOutput, etc.) to flat structure (ema_20, ema_50, macd, macd_signal, rsi, bb_upper, bb_middle, bb_lower, atr)
- **RiskMetrics**: Now uses var_95, max_drawdown, correlation_risk, concentration_risk fields
- **PerformanceMetrics**: Simplified to total_pnl, win_rate, avg_win, avg_loss, max_drawdown, sharpe_ratio
- **AccountContext**: active_strategy is now required (not Optional)
- **MarketContext**: No longer has symbol field (symbol is in TradingContext)
- **PositionSummary**: Uses 'size' instead of 'quantity', 'percentage_pnl' instead of 'unrealized_pnl_percent'
- **TradeHistory**: Uses 'size' instead of 'quantity'

### Migration Impact

- All services now use the same schema definitions
- Tests updated to use canonical schemas
- Adapter methods added to convert between nested and flat TechnicalIndicators structures
- Validation methods now return dict instead of ContextValidationResult object

## LLM Services Package Organization

All LLM Decision Engine components are organized in the `services/llm/` package for better maintainability and clear separation of concerns:

```
backend/src/app/services/llm/
├── __init__.py              # Package interface with clean exports
├── decision_engine.py       # Main orchestrator and entry point
├── llm_service.py          # LLM API integration and model management
├── decision_validator.py    # Decision validation and business rules
├── strategy_manager.py      # Trading strategy management
├── context_builder.py       # Trading context assembly
├── ab_testing.py           # A/B testing framework for models
├── circuit_breaker.py      # Fault tolerance and error handling
├── llm_metrics.py          # Performance and usage metrics
└── llm_exceptions.py       # Structured exception hierarchy
```

This organization provides:

- **Clear Separation**: LLM components are isolated from other services
- **Easy Maintenance**: Related functionality is grouped together
- **Clean Imports**: Package interface provides clean access to services
- **Scalability**: Easy to add new LLM-related components

## Multi-Asset Decision Making for Perpetual Futures

The LLM Decision Engine is designed to analyze and make perpetual futures trading decisions across multiple assets simultaneously, as defined by the `$ASSETS` environment variable (e.g., BTC, ETH, SOL). This approach provides several advantages for active futures trading:

### Benefits of Multi-Asset Analysis

1. **Opportunity Identification**: The LLM can identify the best trading opportunities across multiple assets simultaneously
2. **Capital Efficiency**: The system can optimize capital allocation across multiple active positions
3. **Market Context Awareness**: Cross-asset analysis provides better understanding of overall market conditions and trends
4. **Risk Management**: Decisions account for concentration risk across the entire portfolio of active positions
5. **Comparative Analysis**: The LLM can compare relative strength and momentum across assets to prioritize trades

### Decision Structure

Each trading decision contains:

- **Individual Asset Decisions**: Specific actions (buy/sell/hold/adjust) for each perpetual futures contract
- **Portfolio Rationale**: Overall strategy explaining the multi-asset trading approach
- **Total Allocation**: Aggregate capital allocation across all active positions
- **Portfolio Risk Level**: Overall risk assessment considering all positions and leverage

### Context Building

The Context Builder aggregates data for all configured assets:

- Market data (price, volume, funding rate) for each perpetual futures contract
- Technical indicators for each asset across multiple timeframes
- Overall market sentiment analysis
- Per-asset trade history and performance
- Current open positions and their P&L

### LLM Prompt Strategy

The LLM receives comprehensive multi-asset context and is prompted to:

1. Analyze each asset individually based on technical indicators and market conditions
2. Identify the strongest trading opportunities across all assets
3. Optimize capital allocation across opportunities based on conviction and risk
4. Provide specific actions for each asset with rationale
5. Explain the overall trading strategy across all assets

## Architecture

### High-Level System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Market Data   │    │ Technical Analysis│    │ Account State   │
│   Service       │───▶│    Service        │───▶│   Service       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Context Builder                              │
│  • Market indicators (EMA, MACD, RSI, Bollinger, ATR)         │
│  • Account performance & positions                             │
│  • Recent trading history                                      │
│  • Risk metrics and constraints                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Decision Engine                              │
│  • Enhanced LLM Service                                        │
│  • Structured Output Generation                                │
│  • Multi-model Support (GPT-5, Grok-4, DeepSeek R1)          │
│  • Decision Validation & Sanitization                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Decision Validator                           │
│  • Schema Validation                                           │
│  • Business Rule Validation                                    │
│  • Risk Management Checks                                      │
│  • Fallback Mechanisms                                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Trading Execution Layer                      │
│  • Order Placement                                             │
│  • Position Management                                         │
│  • Trade Logging                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Enhanced LLM Service

**File**: `backend/src/app/services/llm/llm_service.py` (Enhanced)

**Responsibilities**:

- Manage OpenRouter API connections with multiple model support
- Generate structured trading decisions using advanced prompts
- Handle API failures with exponential backoff and circuit breaker patterns
- Maintain comprehensive logging of all LLM interactions
- Support A/B testing between different models

**Key Methods**:

```python
async def generate_trading_decision(
    self,
    symbols: List[str],
    context: TradingContext
) -> TradingDecision

async def validate_api_health(self) -> HealthStatus

async def get_usage_metrics(self) -> UsageMetrics

async def switch_model(self, model_name: str) -> bool
```

### 2. Context Builder Service

**File**: `backend/src/app/services/llm/context_builder.py` (New)

**Responsibilities**:

- Aggregate market data from multiple timeframes
- Integrate technical analysis indicators
- Include account state and position information
- Build comprehensive context for LLM prompts
- Handle data freshness validation

**Key Methods**:

```python
async def build_trading_context(
    self,
    symbols: List[str],
    account_id: int
) -> TradingContext

async def get_market_context(
    self,
    symbols: List[str],
    timeframes: List[str]
) -> MarketContext

async def get_account_context(self, account_id: int) -> AccountContext
```

### 3. Decision Validator Service

**File**: `backend/src/app/services/llm/decision_validator.py` (New)

**Responsibilities**:

- Validate trading decisions against JSON schema
- Apply business rule validation
- Enforce risk management constraints
- Implement fallback mechanisms for invalid decisions
- Track validation metrics and errors

**Key Methods**:

```python
async def validate_decision(
    self,
    decision: TradingDecision,
    context: TradingContext
) -> ValidationResult

async def apply_risk_checks(
    self,
    decision: TradingDecision,
    account_context: AccountContext
) -> RiskValidationResult

async def get_validation_metrics(self) -> ValidationMetrics
```

### 4. Strategy Manager Service

**File**: `backend/src/app/services/llm/strategy_manager.py` (New)

**Responsibilities**:

- Manage trading strategies for each account
- Load and validate strategy configurations
- Handle strategy switching and updates
- Provide strategy-specific prompt templates
- Track strategy performance metrics

**Key Methods**:

```python
async def get_account_strategy(self, account_id: int) -> TradingStrategy

async def update_account_strategy(
    self,
    account_id: int,
    strategy_id: str
) -> bool

async def create_custom_strategy(
    self,
    strategy: TradingStrategy
) -> str

async def get_available_strategies(self) -> List[TradingStrategy]

async def get_strategy_performance(
    self,
    strategy_id: str,
    timeframe: str = "7d"
) -> StrategyPerformance
```

### 5. Decision Engine Orchestrator

**File**: `backend/src/app/services/llm/decision_engine.py` (New)

**Responsibilities**:

- Orchestrate the complete decision-making workflow
- Coordinate between context building, LLM analysis, and validation
- Manage decision caching and rate limiting
- Handle multi-account decision processing with strategy-aware decisions
- Provide unified interface for trading decisions

**Key Methods**:

```python
async def make_trading_decision(
    self,
    symbols: List[str],
    account_id: int,
    strategy_override: Optional[str] = None
) -> DecisionResult

async def get_decision_history(
    self,
    account_id: int,
    limit: int = 100,
    symbol: Optional[str] = None
) -> List[DecisionResult]

async def switch_strategy(
    self,
    account_id: int,
    strategy_id: str
) -> bool
```

## Data Models

### Trading Decision Schema

```python
class AssetDecision(BaseModel):
    """Trading decision for a single asset."""

    asset: str = Field(..., description="Trading pair symbol")
    action: Literal["buy", "sell", "hold", "adjust_position", "close_position", "adjust_orders"] = Field(
        ..., description="Trading action"
    )
    allocation_usd: float = Field(..., ge=0, description="Allocation amount in USD")
    position_adjustment: Optional[PositionAdjustment] = Field(
        None, description="Position adjustment details (for adjust_position action)"
    )
    order_adjustment: Optional[OrderAdjustment] = Field(
        None, description="Order adjustment details (for adjust_orders action)"
    )
    tp_price: Optional[float] = Field(None, gt=0, description="Take-profit price")
    sl_price: Optional[float] = Field(None, gt=0, description="Stop-loss price")
    exit_plan: str = Field(..., description="Exit strategy description")
    rationale: str = Field(..., description="Decision reasoning")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score")
    risk_level: Literal["low", "medium", "high"] = Field(..., description="Risk assessment")

class TradingDecision(BaseModel):
    """Multi-asset structured trading decision from LLM for perpetual futures."""

    decisions: List[AssetDecision] = Field(
        ..., description="Trading decisions for each asset"
    )
    portfolio_rationale: str = Field(
        ..., description="Overall trading strategy and reasoning across assets"
    )
    total_allocation_usd: float = Field(
        ..., ge=0, description="Total allocation across all assets"
    )
    portfolio_risk_level: Literal["low", "medium", "high"] = Field(
        ..., description="Overall portfolio risk assessment"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PositionAdjustment(BaseModel):
    """Position adjustment details."""

    adjustment_type: Literal["increase", "decrease"] = Field(
        ..., description="Type of position adjustment"
    )
    adjustment_amount_usd: float = Field(
        ..., gt=0, description="Amount to adjust position by (in USD)"
    )
    adjustment_percentage: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage of current position to adjust"
    )
    new_tp_price: Optional[float] = Field(
        None, gt=0, description="New take-profit price after adjustment"
    )
    new_sl_price: Optional[float] = Field(
        None, gt=0, description="New stop-loss price after adjustment"
    )

class OrderAdjustment(BaseModel):
    """Order adjustment details for TP/SL modifications."""

    adjust_tp: bool = Field(default=False, description="Whether to adjust take-profit")
    adjust_sl: bool = Field(default=False, description="Whether to adjust stop-loss")
    new_tp_price: Optional[float] = Field(
        None, gt=0, description="New take-profit price"
    )
    new_sl_price: Optional[float] = Field(
        None, gt=0, description="New stop-loss price"
    )
    cancel_tp: bool = Field(default=False, description="Cancel existing take-profit order")
    cancel_sl: bool = Field(default=False, description="Cancel existing stop-loss order")
```

### Trading Context Schema

```python
class TradingContext(BaseModel):
    """Complete multi-asset context for trading decisions."""

    symbols: List[str] = Field(..., description="List of asset symbols to analyze")
    account_id: int
    market_data: MarketContext = Field(..., description="Multi-asset market data")
    account_state: AccountContext
    recent_trades: Dict[str, List[TradeHistory]] = Field(
        ..., description="Recent trades grouped by asset symbol"
    )
    risk_metrics: RiskMetrics
    timestamp: datetime
    errors: List[str] = Field([], description="Errors encountered during context building")
```

### Market Context Schema

```python
class AssetMarketData(BaseModel):
    """Market data for a single asset."""

    symbol: str
    current_price: float
    price_change_24h: float
    volume_24h: float
    funding_rate: Optional[float]
    open_interest: Optional[float]
    price_history: List[PricePoint]
    volatility: float
    technical_indicators: TechnicalIndicators

class MarketContext(BaseModel):
    """Multi-asset market data context for perpetual futures trading decisions."""

    assets: Dict[str, AssetMarketData] = Field(
        ..., description="Market data for each asset symbol"
    )
    market_sentiment: Optional[str] = Field(
        None, description="Overall market sentiment (bullish/bearish/neutral)"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TechnicalIndicatorsSet(BaseModel):
    """Set of technical indicators for a specific timeframe."""
    ema_20: Optional[List[float]]
    ema_50: Optional[List[float]]
    macd: Optional[List[float]]
    macd_signal: Optional[List[float]]
    rsi: Optional[List[float]]
    bb_upper: Optional[List[float]]
    bb_middle: Optional[List[float]]
    bb_lower: Optional[List[float]]
    atr: Optional[List[float]]

class TechnicalIndicators(BaseModel):
    """Technical indicators for market analysis."""
    interval: TechnicalIndicatorsSet
    long_interval: TechnicalIndicatorsSet
```

### Account Context Schema

```python
class AccountContext(BaseModel):
    """Account state context for decisions."""

    account_id: int
    balance_usd: float
    available_balance: float
    total_pnl: float
    open_positions: List[PositionSummary]
    recent_performance: PerformanceMetrics
    risk_exposure: float
    max_position_size: float
    active_strategy: TradingStrategy
    maker_fee_bps: float
    taker_fee_bps: float

class TradingStrategy(BaseModel):
    """Trading strategy configuration."""

    strategy_id: str = Field(..., description="Unique strategy identifier")
    strategy_name: str = Field(..., description="Human-readable strategy name")
    strategy_type: Literal["conservative", "aggressive", "scalping", "swing", "dca", "custom"] = Field(
        ..., description="Strategy type classification"
    )
    prompt_template: str = Field(..., description="LLM prompt template for this strategy")
    risk_parameters: StrategyRiskParameters = Field(..., description="Risk management parameters")
    timeframe_preference: List[str] = Field(
        default=["1h", "4h"], description="Preferred timeframes for analysis"
    )
    max_positions: int = Field(default=3, ge=1, description="Maximum concurrent positions")
    position_sizing: Literal["fixed", "percentage", "kelly", "volatility_adjusted"] = Field(
        default="percentage", description="Position sizing method"
    )
    is_active: bool = Field(default=True, description="Whether strategy is active")

class StrategyRiskParameters(BaseModel):
    """Risk management parameters for trading strategies."""

    max_risk_per_trade: float = Field(..., ge=0, le=100, description="Max risk per trade (%)")
    max_daily_loss: float = Field(..., ge=0, le=100, description="Max daily loss (%)")
    stop_loss_percentage: float = Field(..., ge=0, le=50, description="Default stop loss (%)")
    take_profit_ratio: float = Field(default=2.0, ge=1.0, description="Risk/reward ratio")
    max_leverage: float = Field(default=2.0, ge=1.0, le=10.0, description="Maximum leverage")
    cooldown_period: int = Field(default=300, ge=0, description="Cooldown between trades (seconds)")
```

## Error Handling

### Exception Hierarchy

```python
class DecisionEngineError(Exception):
    """Base exception for decision engine errors."""
    pass

class LLMAPIError(DecisionEngineError):
    """LLM API communication errors."""
    pass

class ValidationError(DecisionEngineError):
    """Decision validation errors."""
    pass

class ContextBuildingError(DecisionEngineError):
    """Context building errors."""
    pass

class InsufficientDataError(DecisionEngineError):
    """Insufficient data for decision making."""
    pass
```

### Error Handling Strategy

1. **API Failures**: Exponential backoff with circuit breaker
2. **Validation Failures**: Detailed error logging and fallback to conservative decisions
3. **Data Unavailability**: Graceful degradation with reduced context
4. **Rate Limiting**: Queue management and request throttling
5. **Model Failures**: Automatic fallback to alternative models

## Testing Strategy

### Unit Tests

- **LLM Service Tests**: Mock OpenRouter API responses
- **Context Builder Tests**: Test data aggregation logic
- **Decision Validator Tests**: Test validation rules and edge cases
- **Decision Engine Tests**: Test orchestration workflow

### Integration Tests

- **End-to-End Decision Flow**: Test complete decision-making pipeline
- **Database Integration**: Test data persistence and retrieval
- **API Integration**: Test with real OpenRouter API (in test environment)
- **Multi-Account Testing**: Test account isolation and concurrent processing

### Performance Tests

- **Load Testing**: Test decision generation under high load
- **Latency Testing**: Measure decision generation time
- **Memory Usage**: Monitor memory consumption during batch processing
- **API Rate Limiting**: Test rate limit handling

## Implementation Phases

### Phase 1: Enhanced LLM Service (Week 1)

- Extend existing LLMService with structured decision generation
- Implement multi-model support and model switching
- Add comprehensive error handling and retry logic
- Create usage metrics and monitoring

### Phase 2: Context Builder Service (Week 1)

- Create context aggregation service
- Integrate with technical analysis service
- Implement account state integration
- Add data freshness validation

### Phase 3: Decision Validator Service (Week 2)

- Implement schema validation
- Add business rule validation
- Create risk management checks
- Implement fallback mechanisms

### Phase 4: Strategy Manager Service (Week 2)

- Create strategy management service
- Implement predefined trading strategies
- Add strategy switching capabilities
- Create strategy performance tracking

### Phase 5: Decision Engine Orchestrator (Week 2)

- Create orchestration service
- Implement decision caching
- Add multi-account support with strategy awareness
- Create unified API interface

### Phase 6: Integration and Testing (Week 3)

- Integrate with existing trading pipeline
- Implement comprehensive testing
- Add monitoring and alerting
- Performance optimization

## API Endpoints

### Decision Generation

```
POST /api/v1/decisions/generate
{
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],  // Optional, defaults to $ASSETS env variable
  "account_id": 1,
  "force_refresh": false
}
```

### Decision History

```
GET /api/v1/decisions/history?account_id=1&limit=50&symbol=BTCUSDT  // symbol filter is optional
```

### Decision Validation

```
POST /api/v1/decisions/validate
{
  "decision": {...},
  "context": {...}
}
```

### Model Management

```
POST /api/v1/decisions/models/switch
{
  "model": "x-ai/grok-4",
  "account_id": 1
}
```

### Performance Metrics

```
GET /api/v1/decisions/metrics?account_id=1&timeframe=24h
```

### Strategy Management

```
GET /api/v1/strategies/available
GET /api/v1/strategies/account/{account_id}
POST /api/v1/strategies/account/{account_id}/switch
{
  "strategy_id": "conservative_swing"
}
POST /api/v1/strategies/custom
{
  "strategy": {...}
}
GET /api/v1/strategies/{strategy_id}/performance?timeframe=7d
```

## Security Considerations

1. **API Key Management**: Secure storage and rotation of OpenRouter API keys
2. **Input Validation**: Comprehensive validation of all inputs
3. **Rate Limiting**: Protection against API abuse
4. **Audit Logging**: Complete audit trail of all decisions
5. **Access Control**: Account-based access control for decisions

## Performance Optimization

1. **Caching**: Cache frequently accessed market data and technical indicators
2. **Async Processing**: Non-blocking decision generation
3. **Batch Processing**: Efficient batch decision generation for multiple symbols
4. **Connection Pooling**: Efficient HTTP connection management
5. **Memory Management**: Optimized memory usage for large datasets

## Monitoring and Observability

1. **Decision Metrics**: Track decision accuracy, latency, and success rates
2. **API Metrics**: Monitor OpenRouter API usage and costs
3. **Error Tracking**: Comprehensive error logging and alerting
4. **Performance Monitoring**: Track system performance and resource usage
5. **Business Metrics**: Monitor trading performance and ROI

## Future Enhancements

1. **Machine Learning Integration**: Incorporate ML models for decision enhancement
2. **Advanced Risk Management**: Implement sophisticated risk models
3. **Multi-Exchange Support**: Extend to support multiple exchanges
4. **Real-time Streaming**: Implement real-time decision updates
5. **Advanced Analytics**: Enhanced performance analytics and reporting
