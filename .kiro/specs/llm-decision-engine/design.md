# LLM Decision Engine Integration - Design Document

## Overview

The LLM Decision Engine Integration enhances the existing AI Trading Agent by implementing a sophisticated decision-making system that leverages Large Language Models for intelligent trading decisions. This system builds upon the existing `LLMService` foundation and integrates with the technical analysis service, market data service, and account management to provide comprehensive trading intelligence.

The design focuses on creating a robust, scalable, and maintainable system that can handle real-time trading decisions while ensuring data integrity, error handling, and performance optimization.

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

**File**: `backend/src/app/services/llm_service.py` (Enhanced)

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
    symbol: str,
    context: TradingContext
) -> TradingDecision

async def validate_api_health(self) -> HealthStatus

async def get_usage_metrics(self) -> UsageMetrics

async def switch_model(self, model_name: str) -> bool
```

### 2. Context Builder Service

**File**: `backend/src/app/services/context_builder.py` (New)

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
    symbol: str,
    account_id: int
) -> TradingContext

async def get_market_context(
    self,
    symbol: str,
    timeframes: List[str]
) -> MarketContext

async def get_account_context(self, account_id: int) -> AccountContext
```

### 3. Decision Validator Service

**File**: `backend/src/app/services/decision_validator.py` (New)

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

**File**: `backend/src/app/services/strategy_manager.py` (New)

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

**File**: `backend/src/app/services/decision_engine.py` (New)

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
    symbol: str,
    account_id: int,
    strategy_override: Optional[str] = None
) -> DecisionResult

async def batch_decisions(
    self,
    symbols: List[str],
    account_id: int
) -> List[DecisionResult]

async def get_decision_history(
    self,
    account_id: int,
    limit: int = 100
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
class TradingDecision(BaseModel):
    """Structured trading decision from LLM."""

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
    """Complete context for trading decisions."""

    symbol: str
    account_id: int
    market_data: MarketContext
    account_state: AccountContext
    recent_trades: List[TradeHistory]
    risk_metrics: RiskMetrics
    timestamp: datetime
```

### Market Context Schema

```python
class MarketContext(BaseModel):
    """Market data context for decisions."""

    current_price: float
    price_change_24h: float
    volume_24h: float
    funding_rate: Optional[float]
    open_interest: Optional[float]
    price_history: List[PricePoint]
    volatility: float
    technical_indicators: TechnicalIndicators
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
  "symbol": "BTC/USDT",
  "account_id": 1,
  "force_refresh": false
}
```

### Decision History

```
GET /api/v1/decisions/history?account_id=1&limit=50&symbol=BTC/USDT
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