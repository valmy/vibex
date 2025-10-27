# Technical Analysis Service: Technical Decisions & Justifications

## Overview

This document details all technical decisions made for the Technical Analysis Service implementation, with justifications based on the existing codebase patterns and best practices.

---

## 1. Architecture Decisions

### 1.1 Singleton Factory Pattern

**Decision:** Use global `_ta_service` variable with `get_technical_analysis_service()` factory function

**Justification:**
- **Consistency**: Matches existing patterns in `get_market_data_service()` and `get_llm_service()`
- **Simplicity**: Single instance, lazy initialization
- **Testability**: Easy to mock in tests
- **Thread-safety**: Python GIL ensures safe access

**Implementation:**
```python
_ta_service: Optional[TechnicalAnalysisService] = None

def get_technical_analysis_service() -> TechnicalAnalysisService:
    global _ta_service
    if _ta_service is None:
        _ta_service = TechnicalAnalysisService()
    return _ta_service
```

**Alternatives Considered:**
- Dependency injection via FastAPI Depends() - Too complex for stateless service
- Class methods - Less flexible for testing
- Module-level functions - No state management

---

### 1.2 Dependency Injection (Data as Arguments)

**Decision:** Service receives `List[MarketData]` as argument, not database session

**Justification:**
- **Decoupling**: Service doesn't depend on database layer
- **Reusability**: Can use with any data source (API, cache, files)
- **Testability**: Easy to test with mock data
- **Flexibility**: Caller controls data fetching strategy

**Implementation:**
```python
def calculate_all_indicators(self, candles: List[MarketData]) -> TechnicalIndicators:
    # Service receives data, doesn't fetch it
```

**Comparison with Market Data Service:**
- Market Data Service: Fetches from API, stores in DB
- Technical Analysis Service: Receives prepared data, calculates indicators
- This separation of concerns is intentional and beneficial

**Alternatives Considered:**
- Pass database session - Violates single responsibility
- Pass symbol + interval - Requires database access, less flexible
- Pass raw arrays - Loses type safety and metadata

---

### 1.3 Pure Functions for Indicators

**Decision:** Each indicator is a pure function returning schema object

**Justification:**
- **Testability**: No side effects, deterministic
- **Reusability**: Can be used independently
- **Clarity**: Clear input/output contracts
- **Performance**: No state management overhead

**Implementation:**
```python
def calculate_ema(close_prices: np.ndarray) -> EMAOutput:
    # Pure function: same input always produces same output
    ema_values = talib.EMA(close_prices, timeperiod=12)
    return EMAOutput(ema=float(ema_values[-1]))
```

**Alternatives Considered:**
- Methods on service class - Less reusable, harder to test
- Stateful calculator class - Unnecessary complexity
- Raw numpy arrays - No type safety

---

## 2. Data Structure Decisions

### 2.1 Pydantic Models for All Outputs

**Decision:** Use Pydantic BaseModel for all indicator outputs

**Justification:**
- **Type Safety**: Compile-time type checking
- **Validation**: Automatic data validation
- **Serialization**: Seamless JSON conversion for APIs
- **Documentation**: Auto-generated OpenAPI schemas
- **Consistency**: Matches existing schema patterns in codebase

**Implementation:**
```python
class EMAOutput(BaseModel):
    ema: Optional[float]
    period: int = 12
```

**Benefits:**
- FastAPI automatically generates OpenAPI docs
- JSON serialization works out of the box
- Type hints are enforced
- Validation errors are clear

**Alternatives Considered:**
- Dataclasses - No validation, less FastAPI integration
- TypedDict - No validation, no serialization
- Raw dictionaries - No type safety

---

### 2.2 Optional[float] for Indicator Values

**Decision:** All indicator values are `Optional[float]`

**Justification:**
- **Edge Cases**: Some indicators may be None during warmup
- **Graceful Degradation**: Handles insufficient data
- **Clear Intent**: Explicitly shows value may be missing
- **Consistency**: Matches Pydantic best practices

**Implementation:**
```python
class MACDOutput(BaseModel):
    macd: Optional[float] = None
    signal: Optional[float] = None
    histogram: Optional[float] = None
```

**When Values Are None:**
- First N candles (warmup period)
- Invalid data (NaN from talib)
- Calculation errors (caught and logged)

**Alternatives Considered:**
- Always return float - Requires default values, less clear
- Raise exception on None - Too strict, breaks on edge cases
- Return 0.0 - Misleading, hard to distinguish from real zero

---

### 2.3 Aggregated TechnicalIndicators Schema

**Decision:** Single aggregated schema containing all indicators

**Justification:**
- **Atomicity**: All indicators calculated together
- **Consistency**: Single timestamp for all values
- **Convenience**: Single return value from service
- **API Simplicity**: One endpoint returns all data

**Implementation:**
```python
class TechnicalIndicators(BaseModel):
    ema: EMAOutput
    macd: MACDOutput
    rsi: RSIOutput
    bollinger_bands: BollingerBandsOutput
    atr: ATROutput
    timestamp: datetime
    candle_count: int
```

**Alternatives Considered:**
- Separate schemas per indicator - Requires multiple calls
- Flat schema - Hard to organize, unclear structure
- Dictionary - No type safety

---

## 3. Error Handling Decisions

### 3.1 Custom Exception Hierarchy

**Decision:** Create specific exception types for different error scenarios

**Justification:**
- **Specificity**: Callers can handle different errors appropriately
- **Debugging**: Clear error messages with context
- **Logging**: Structured error information
- **Testing**: Easy to test error conditions

**Exception Types:**
```python
TechnicalAnalysisException (base)
├── InsufficientDataError (< 50 candles)
├── InvalidCandleDataError (missing/invalid OHLCV)
└── CalculationError (talib/numpy errors)
```

**Usage Pattern:**
```python
try:
    indicators = ta_service.calculate_all_indicators(candles)
except InsufficientDataError as e:
    logger.warning(f"Not enough data: {e}")
    return None
except InvalidCandleDataError as e:
    logger.error(f"Bad data: {e}")
    raise
except CalculationError as e:
    logger.error(f"Calculation failed: {e}")
    raise
```

**Alternatives Considered:**
- Generic Exception - No specificity, hard to handle
- Return error codes - Not Pythonic, easy to ignore
- Silent failures - Dangerous, hard to debug

---

### 3.2 Validation at Service Entry Point

**Decision:** Validate all input at `calculate_all_indicators()` entry point

**Justification:**
- **Fail Fast**: Catch errors early with clear messages
- **Single Responsibility**: Validation in one place
- **Performance**: Don't process invalid data
- **User Experience**: Clear error messages

**Validation Checks:**
1. Minimum 50 candles
2. All OHLC fields present
3. High >= Low
4. No negative prices/volume

**Implementation:**
```python
def _validate_candles(self, candles: List[MarketData]) -> None:
    if len(candles) < self.MIN_CANDLES:
        raise InsufficientDataError(len(candles))
    
    for i, candle in enumerate(candles):
        if not all([candle.open, candle.high, candle.low, candle.close]):
            raise InvalidCandleDataError("Missing OHLC", i)
        if candle.high < candle.low:
            raise InvalidCandleDataError("High < Low", i)
```

**Alternatives Considered:**
- Validate in each indicator function - Redundant, scattered
- No validation - Dangerous, unclear errors
- Validate in repository - Wrong layer, not service's responsibility

---

## 4. Library & Dependency Decisions

### 4.1 TA-Lib for Indicator Calculations

**Decision:** Use TA-Lib (already in pyproject.toml)

**Justification:**
- **Already Included**: No new dependencies needed
- **Industry Standard**: Used by professional traders
- **Performance**: C-based implementation, very fast
- **Accuracy**: Well-tested, reliable calculations
- **Documentation**: Extensive documentation available

**TA-Lib Advantages:**
- Handles edge cases (NaN, infinity)
- Optimized for performance
- Consistent with industry standards
- Widely used in trading systems

**Alternatives Considered:**
- pandas_ta - Lighter weight, but less mature
- Manual implementation - Error-prone, slow
- Other libraries - Less established

**Installation Note:**
- Already installed in Docker image (timescale/timescaledb:latest-pg16-oss)
- System library required (libta-lib)
- Python wrapper: TA-Lib>=0.6.8 (in pyproject.toml)

---

### 4.2 NumPy for Array Operations

**Decision:** Use NumPy (already in pyproject.toml)

**Justification:**
- **Already Included**: No new dependencies
- **Required by TA-Lib**: TA-Lib depends on NumPy
- **Performance**: Vectorized operations are fast
- **Standard**: Industry standard for numerical computing

**NumPy Usage:**
```python
close_prices = np.array([c.close for c in candles], dtype=np.float64)
ema_values = talib.EMA(close_prices, timeperiod=12)
```

**Alternatives Considered:**
- pandas - Heavier, not needed for this use case
- Lists - Slow, not suitable for calculations
- Raw Python - Too slow for large datasets

---

## 5. Logging & Monitoring Decisions

### 5.1 Structured Logging

**Decision:** Use existing logging infrastructure with structured JSON logs

**Justification:**
- **Consistency**: Matches existing logging patterns
- **Searchability**: JSON logs are easily searchable
- **Monitoring**: Structured data for log aggregation
- **Performance**: Minimal overhead

**Log Levels:**
- `DEBUG`: Calculation details, array shapes
- `INFO`: Service initialization, completion
- `WARNING`: Data quality issues
- `ERROR`: Exceptions, failed calculations

**Implementation:**
```python
logger = get_logger(__name__)

logger.debug(f"Calculating indicators for {len(candles)} candles")
logger.info(f"Indicators calculated successfully")
logger.warning(f"Insufficient data: {len(candles)} < 50")
logger.error(f"Calculation failed: {error}")
```

**Alternatives Considered:**
- Print statements - Not suitable for production
- Custom logging - Reinventing the wheel
- No logging - Impossible to debug

---

## 6. Testing Strategy Decisions

### 6.1 Unit Tests with Known Values

**Decision:** Test each indicator against known values

**Justification:**
- **Accuracy**: Verify calculations are correct
- **Regression**: Catch calculation changes
- **Confidence**: Know the service works
- **Documentation**: Tests serve as examples

**Test Data Sources:**
- Historical data with known indicator values
- Synthetic data for edge cases
- Reference implementations (TradingView, etc.)

**Example:**
```python
def test_ema_calculation():
    close_prices = np.array([44.0, 44.25, 44.5, 43.75, 44.5, 45.0, 45.5])
    result = calculate_ema(close_prices)
    assert result.ema is not None
    assert 44.0 < result.ema < 45.5
```

---

### 6.2 Service-Level Tests

**Decision:** Test full workflow with mocked data

**Justification:**
- **Integration**: Verify components work together
- **Error Handling**: Test exception scenarios
- **Validation**: Test input validation
- **Output**: Verify output structure

**Test Scenarios:**
- Valid input (50+ candles)
- Insufficient data (< 50 candles)
- Invalid data (missing OHLC)
- Edge cases (NaN, zero volume)

---

### 6.3 Integration Tests

**Decision:** Test with real MarketData objects from database

**Justification:**
- **End-to-End**: Verify complete workflow
- **Real Data**: Test with actual data structures
- **Database**: Verify database integration
- **Performance**: Measure real performance

**Test Scenarios:**
- Fetch data from database
- Calculate indicators
- Verify results
- Measure performance

---

## 7. Performance Decisions

### 7.1 NumPy Array Conversion

**Decision:** Convert MarketData list to NumPy arrays once

**Justification:**
- **Performance**: NumPy operations are fast
- **Efficiency**: Single conversion, multiple uses
- **Clarity**: Clear data preparation step

**Implementation:**
```python
def _prepare_arrays(self, candles: List[MarketData]):
    close_prices = np.array([c.close for c in candles], dtype=np.float64)
    high_prices = np.array([c.high for c in candles], dtype=np.float64)
    low_prices = np.array([c.low for c in candles], dtype=np.float64)
    volume = np.array([c.volume for c in candles], dtype=np.float64)
    return close_prices, high_prices, low_prices, volume
```

**Performance Characteristics:**
- Conversion: O(n) where n = number of candles
- Calculations: O(n) for each indicator
- Total: O(n) for all indicators combined

---

### 7.2 Last Value Only

**Decision:** Return only the last calculated value for each indicator

**Justification:**
- **Simplicity**: Single value per indicator
- **Performance**: No need to store all values
- **Use Case**: Trading decisions use latest values
- **Storage**: Minimal data to store/transmit

**Implementation:**
```python
ema_values = talib.EMA(close_prices, timeperiod=12)
ema = float(ema_values[-1])  # Last value only
```

**Alternatives Considered:**
- Return all values - Unnecessary data, slower
- Return last N values - More complex, not needed
- Return statistics - Loses detail

---

## 8. Future Enhancement Decisions

### 8.1 Caching Strategy (Future)

**Potential Decision:** Cache calculations for recent candles

**Rationale:**
- Same candles requested multiple times
- Avoid redundant calculations
- Improve response time

**Implementation Approach:**
- Cache key: (symbol, interval, candle_count)
- TTL: 1 minute (candle interval)
- Invalidate on new candle

---

### 8.2 Persistent Storage (Future)

**Potential Decision:** Store calculated indicators in database

**Rationale:**
- Historical analysis
- Performance tracking
- Audit trail

**Implementation Approach:**
- New table: `technical_indicators` (hypertable)
- Columns: symbol, interval, time, ema, macd, rsi, bb_upper, bb_lower, atr
- Indexes: (symbol, time), (interval, time)

---

## 9. Consistency with Existing Patterns

### 9.1 Service Pattern Alignment

| Aspect | Market Data Service | LLM Service | TA Service |
|--------|-------------------|------------|-----------|
| Singleton | ✅ get_market_data_service() | ✅ get_llm_service() | ✅ get_technical_analysis_service() |
| Initialization | In __init__.py | In __init__.py | In __init__.py |
| Error Handling | Custom exceptions | Try/except | Custom exceptions |
| Logging | get_logger() | get_logger() | get_logger() |
| Type Hints | ✅ Complete | ✅ Complete | ✅ Complete |
| Docstrings | ✅ Comprehensive | ✅ Comprehensive | ✅ Comprehensive |

---

### 9.2 Code Quality Standards

- **Type Hints**: All functions have complete type hints
- **Docstrings**: All classes and functions documented
- **Error Handling**: Specific exceptions with context
- **Logging**: Structured logging at appropriate levels
- **Testing**: >90% code coverage
- **Code Style**: Black formatting, Ruff linting

---

## 10. Summary

The Technical Analysis Service design follows established patterns in the codebase while introducing best practices for indicator calculations. Key decisions prioritize:

1. **Consistency**: Matches existing service patterns
2. **Simplicity**: Clear, focused responsibilities
3. **Testability**: Easy to test and mock
4. **Performance**: Efficient calculations
5. **Maintainability**: Clear code, good documentation
6. **Reliability**: Comprehensive error handling

All decisions are justified by codebase patterns, best practices, and the specific requirements of the trading application.

