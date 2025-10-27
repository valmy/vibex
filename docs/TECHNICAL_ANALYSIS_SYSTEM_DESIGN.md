# Technical Analysis Service: System Design & Implementation Plan

## Executive Summary

This document provides a comprehensive system design and implementation plan for the Technical Analysis Service based on the design document at `docs/TECHNICAL_ANALYSIS_DESIGN.md`. The service will calculate technical indicators (EMA, MACD, RSI, Bollinger Bands, ATR) from OHLCV market data using TA-Lib and NumPy.

**Key Characteristics:**
- **Modular Architecture**: Follows existing service patterns (market_data, llm_service)
- **Dependency Injection**: Decoupled from database, receives data as arguments
- **Singleton Pattern**: Global service instance via factory function
- **Async-Ready**: Compatible with FastAPI async operations
- **Well-Tested**: Unit, service-level, and integration tests

---

## 1. System Design Overview

### 1.1 Architecture & Component Structure

```
backend/src/app/services/technical_analysis/
├── __init__.py              # Public API exports & singleton factory
├── service.py               # TechnicalAnalysisService (orchestration)
├── indicators.py            # Indicator calculation functions
├── schemas.py               # Pydantic data models
├── exceptions.py            # Custom exceptions
└── README.md                # Module documentation
```

**Component Responsibilities:**

| Component | Purpose | Dependencies |
|-----------|---------|--------------|
| `service.py` | Orchestrates calculations, validates input | indicators, schemas, logging |
| `indicators.py` | Pure calculation functions | numpy, talib, schemas |
| `schemas.py` | Data contracts (Pydantic models) | pydantic |
| `exceptions.py` | Custom exceptions for error handling | None |
| `__init__.py` | Public API, singleton factory | service, schemas |

### 1.2 Data Flow

```
MarketData (List[MarketData])
    ↓
TechnicalAnalysisService.calculate_all_indicators()
    ↓
Extract OHLCV arrays (numpy)
    ↓
indicators.calculate_*() functions
    ↓
Individual indicator schemas (EMAOutput, MACDOutput, etc.)
    ↓
TechnicalIndicators (aggregated result)
```

### 1.3 Integration Points

**Consumers:**
- `LLMService`: Fetch indicators for prompt building
- `TradingService` (future): Decision making based on indicators
- `API Routes`: Direct indicator queries via HTTP

**Data Sources:**
- `MarketDataService`: Provides candle data
- `MarketDataRepository`: Database queries

**Dependencies:**
- `numpy`: Array operations
- `talib`: Indicator calculations
- `pydantic`: Data validation
- `logging`: Structured logging

### 1.4 API Interfaces & Contracts

**Public Service Interface:**
```python
class TechnicalAnalysisService:
    def calculate_all_indicators(
        self, 
        candles: List[MarketData]
    ) -> TechnicalIndicators
```

**Input Contract:**
- Minimum 50 candles required
- Candles ordered oldest to newest
- All OHLCV fields populated

**Output Contract:**
- Returns `TechnicalIndicators` object
- All indicator values are Optional[float]
- Includes metadata (period, timestamp)

### 1.5 Error Handling & Logging Strategy

**Error Hierarchy:**
```
TechnicalAnalysisException (base)
├── InsufficientDataError (< 50 candles)
├── InvalidCandleDataError (missing/invalid OHLCV)
└── CalculationError (talib/numpy errors)
```

**Logging Levels:**
- `DEBUG`: Calculation details, array shapes
- `INFO`: Service initialization, calculation completion
- `WARNING`: Data quality issues, edge cases
- `ERROR`: Exceptions, failed calculations

---

## 2. Implementation Plan

### Phase 1: Foundation (Days 1-2)

**Tasks:**
1. Create module structure and `__init__.py`
2. Define Pydantic schemas in `schemas.py`
3. Create custom exceptions in `exceptions.py`
4. Set up logging configuration

**Deliverables:**
- Module directory structure
- All schema definitions
- Exception classes
- Logging setup

**Dependencies:** None (can start immediately)

### Phase 2: Core Calculations (Days 2-3)

**Tasks:**
1. Implement `indicators.py` with all 5 indicator functions
2. Add input validation and error handling
3. Test each function with known values
4. Document calculation parameters

**Deliverables:**
- All indicator functions implemented
- Unit tests for each indicator
- Documentation of parameters and outputs

**Dependencies:** Phase 1 complete

### Phase 3: Service Layer (Days 3-4)

**Tasks:**
1. Implement `TechnicalAnalysisService` class
2. Add data preparation logic (numpy arrays)
3. Implement orchestration logic
4. Add comprehensive error handling

**Deliverables:**
- Service class with full functionality
- Service-level tests
- Error handling tests

**Dependencies:** Phase 2 complete

### Phase 4: Integration & Registration (Days 4-5)

**Tasks:**
1. Update `backend/src/app/services/__init__.py`
2. Create singleton factory function
3. Integrate with LLMService (optional enhancement)
4. Create integration tests

**Deliverables:**
- Service registered in services module
- Integration tests with LLMService
- Documentation

**Dependencies:** Phase 3 complete

### Phase 5: Testing & Documentation (Days 5-6)

**Tasks:**
1. Write comprehensive unit tests
2. Write integration tests
3. Create module README.md
4. Add docstrings and type hints

**Deliverables:**
- >90% code coverage
- All tests passing
- Complete documentation

**Dependencies:** All phases complete

---

## 3. Technical Decisions & Justifications

### 3.1 Design Pattern Choices

**Decision: Singleton Factory Pattern**
- **Rationale**: Matches existing `get_market_data_service()` and `get_llm_service()` patterns
- **Benefit**: Single instance, lazy initialization, easy testing with mocks
- **Implementation**: Global `_ta_service` variable with factory function

**Decision: Dependency Injection (Data as Arguments)**
- **Rationale**: Decouples service from database, improves testability
- **Benefit**: Can test with mock data, reusable across different data sources
- **Trade-off**: Caller must fetch data first (acceptable, follows market_data pattern)

**Decision: Pure Functions for Indicators**
- **Rationale**: Separates calculation logic from orchestration
- **Benefit**: Easy to test, reusable, clear responsibilities
- **Implementation**: Each function takes numpy arrays, returns schema object

### 3.2 Data Structure Choices

**Decision: Pydantic Models for All Outputs**
- **Rationale**: Type safety, validation, serialization to JSON
- **Benefit**: Works seamlessly with FastAPI, clear contracts
- **Implementation**: Individual schemas per indicator + aggregated `TechnicalIndicators`

**Decision: Optional[float] for Indicator Values**
- **Rationale**: Some indicators may be None during warmup period
- **Benefit**: Handles edge cases gracefully, clear intent
- **Implementation**: All indicator fields are Optional

### 3.3 Error Handling Approach

**Decision: Custom Exception Hierarchy**
- **Rationale**: Specific error types for different failure modes
- **Benefit**: Callers can handle specific errors appropriately
- **Implementation**: Base `TechnicalAnalysisException` with specific subclasses

**Decision: Validation at Service Entry Point**
- **Rationale**: Fail fast with clear error messages
- **Benefit**: Prevents invalid data from reaching calculations
- **Implementation**: Check candle count, data completeness in `calculate_all_indicators()`

### 3.4 Library Choices

**TA-Lib vs Alternatives:**
- **Rationale**: Already in pyproject.toml, industry standard, C-based performance
- **Benefit**: Fast, accurate, well-documented
- **Trade-off**: Requires system library installation (already done in Docker)

**NumPy for Array Operations:**
- **Rationale**: Already in pyproject.toml, required by TA-Lib
- **Benefit**: Efficient array operations, standard in data science
- **Implementation**: Convert MarketData list to numpy arrays

---

## 4. Code Structure & Organization

### 4.1 File Organization

**`schemas.py` Structure:**
```
Individual Indicator Schemas:
- EMAOutput(BaseModel)
- MACDOutput(BaseModel)
- RSIOutput(BaseModel)
- BollingerBandsOutput(BaseModel)
- ATROutput(BaseModel)

Aggregated Schema:
- TechnicalIndicators(BaseModel)
```

**`indicators.py` Structure:**
```
Helper Functions:
- _validate_array_length()
- _handle_calculation_error()

Indicator Functions:
- calculate_ema()
- calculate_macd()
- calculate_rsi()
- calculate_bollinger_bands()
- calculate_atr()
```

**`service.py` Structure:**
```
TechnicalAnalysisService:
- __init__()
- calculate_all_indicators()
- _prepare_arrays()
- _validate_candles()
```

### 4.2 Class Hierarchies & Interfaces

**No inheritance required** - service is standalone, schemas inherit from Pydantic BaseModel

**Type Hints:**
- All functions have complete type hints
- Return types are explicit (schemas or None)
- Input types are explicit (List[MarketData], np.ndarray)

### 4.3 Database Schema Changes

**No database schema changes required** - service reads from existing `market_data` table

**Potential Future Enhancement:**
- Store calculated indicators in new `technical_indicators` table
- Create hypertable for time-series optimization
- Add indexes on symbol, time, interval

### 4.4 Configuration Requirements

**No new configuration variables required** - service is stateless

**Optional Future Configuration:**
- Indicator periods (EMA, RSI, etc.)
- Bollinger Bands standard deviations
- ATR period

---

## 5. Testing Strategy

### 5.1 Unit Tests (`tests/unit/test_technical_analysis.py`)

**Test Coverage:**
- Each indicator function with known values
- Edge cases (NaN, infinity, zero volume)
- Array shape validation
- Error handling

**Test Data:**
- Use real historical data with known indicator values
- Create synthetic data for edge cases
- Mock numpy/talib if needed

### 5.2 Service-Level Tests (`tests/unit/test_ta_service.py`)

**Test Coverage:**
- Service initialization
- Full calculation workflow
- Input validation (< 50 candles)
- Error propagation
- Output structure validation

### 5.3 Integration Tests (`tests/integration/test_ta_integration.py`)

**Test Coverage:**
- Integration with MarketDataService
- Integration with LLMService
- End-to-end workflow
- Database query → calculation → result

### 5.4 Test Execution

```bash
# Run all TA tests
uv run pytest tests/unit/test_technical_analysis.py -v

# Run with coverage
uv run pytest tests/unit/test_technical_analysis.py --cov=src/app/services/technical_analysis

# Run integration tests
uv run pytest tests/integration/test_ta_integration.py -v
```

---

## 6. Implementation Checklist

### Phase 1: Foundation
- [ ] Create `backend/src/app/services/technical_analysis/` directory
- [ ] Create `__init__.py` with exports
- [ ] Create `schemas.py` with all Pydantic models
- [ ] Create `exceptions.py` with custom exceptions
- [ ] Create `README.md` with module documentation

### Phase 2: Core Calculations
- [ ] Implement `indicators.py` with all 5 functions
- [ ] Add input validation to each function
- [ ] Write unit tests for each indicator
- [ ] Verify against known values

### Phase 3: Service Layer
- [ ] Implement `TechnicalAnalysisService` class
- [ ] Add `calculate_all_indicators()` method
- [ ] Add data preparation logic
- [ ] Write service-level tests

### Phase 4: Integration
- [ ] Update `backend/src/app/services/__init__.py`
- [ ] Create singleton factory function
- [ ] Write integration tests
- [ ] Test with LLMService

### Phase 5: Polish
- [ ] Achieve >90% code coverage
- [ ] Add comprehensive docstrings
- [ ] Add type hints to all functions
- [ ] Update module README.md

---

## 7. Success Criteria

- ✅ All 5 indicators implemented and tested
- ✅ Service follows existing patterns (singleton, DI)
- ✅ >90% code coverage
- ✅ All tests passing
- ✅ Comprehensive documentation
- ✅ Integration with LLMService working
- ✅ No breaking changes to existing code
- ✅ Async-compatible for FastAPI

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| TA-Lib installation issues | Already in Docker image, documented in README |
| Insufficient data handling | Validate minimum 50 candles, clear error messages |
| Calculation accuracy | Test against known values, use industry-standard library |
| Performance issues | Use numpy arrays, profile if needed |
| Integration complexity | Follow existing patterns, write integration tests |

---

## 9. Future Enhancements

1. **Persistent Storage**: Store calculated indicators in database
2. **Caching**: Cache calculations for recent candles
3. **Configurable Periods**: Allow customization of indicator periods
4. **Additional Indicators**: Add more indicators (Stochastic, CCI, etc.)
5. **Real-time Updates**: Calculate on each candle close event
6. **Performance Metrics**: Track calculation time, accuracy

---

## 10. References

- Design Document: `docs/TECHNICAL_ANALYSIS_DESIGN.md`
- Market Data Service: `backend/src/app/services/market_data/`
- LLM Service: `backend/src/app/services/llm_service.py`
- Existing Tests: `backend/tests/unit/`, `backend/tests/integration/`
- TA-Lib Documentation: https://github.com/mrjbq7/ta-lib
- NumPy Documentation: https://numpy.org/doc/

