# Technical Analysis Service: Architecture & Design Diagrams

## 1. System Architecture

### High-Level System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │   API Routes     │  │   LLM Service    │  │ Trading Svc  │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘ │
│           │                     │                   │          │
│           └─────────────────────┼───────────────────┘          │
│                                 │                              │
│                    ┌────────────▼──────────────┐               │
│                    │ Technical Analysis Svc    │               │
│                    │ (NEW)                     │               │
│                    └────────────┬──────────────┘               │
│                                 │                              │
│           ┌─────────────────────┼─────────────────────┐        │
│           │                     │                     │        │
│  ┌────────▼────────┐  ┌────────▼────────┐  ┌────────▼──────┐ │
│  │ Market Data Svc │  │  Indicators     │  │   Schemas     │ │
│  │                 │  │  (EMA, MACD,    │  │   (Pydantic)  │ │
│  │                 │  │   RSI, BB, ATR) │  │               │ │
│  └────────┬────────┘  └────────┬────────┘  └───────────────┘ │
│           │                    │                              │
│           └────────────────────┼──────────────────────────────┤
│                                │                              │
│                    ┌───────────▼──────────┐                   │
│                    │  Market Data Table   │                   │
│                    │  (TimescaleDB)       │                   │
│                    └──────────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Module Structure

### Directory Layout

```
backend/src/app/services/technical_analysis/
│
├── __init__.py
│   ├── Exports: TechnicalAnalysisService, TechnicalIndicators
│   ├── Factory: get_technical_analysis_service()
│   └── Singleton: _ta_service
│
├── service.py
│   ├── Class: TechnicalAnalysisService
│   ├── Method: calculate_all_indicators()
│   ├── Method: _validate_candles()
│   └── Method: _prepare_arrays()
│
├── indicators.py
│   ├── Function: calculate_ema()
│   ├── Function: calculate_macd()
│   ├── Function: calculate_rsi()
│   ├── Function: calculate_bollinger_bands()
│   ├── Function: calculate_atr()
│   ├── Helper: _validate_array_length()
│   └── Helper: _handle_calculation_error()
│
├── schemas.py
│   ├── Schema: EMAOutput
│   ├── Schema: MACDOutput
│   ├── Schema: RSIOutput
│   ├── Schema: BollingerBandsOutput
│   ├── Schema: ATROutput
│   └── Schema: TechnicalIndicators (aggregated)
│
├── exceptions.py
│   ├── Exception: TechnicalAnalysisException
│   ├── Exception: InsufficientDataError
│   ├── Exception: InvalidCandleDataError
│   └── Exception: CalculationError
│
└── README.md
    ├── Module overview
    ├── Usage examples
    ├── API reference
    └── Troubleshooting
```

---

## 3. Data Flow Diagram

### Calculation Flow

```
Input: List[MarketData]
       (50+ candles, oldest to newest)
       │
       ▼
┌──────────────────────────────────┐
│ TechnicalAnalysisService         │
│ .calculate_all_indicators()      │
└──────────────────────────────────┘
       │
       ├─► _validate_candles()
       │   ├─ Check count >= 50
       │   ├─ Check OHLC present
       │   └─ Check High >= Low
       │
       ├─► _prepare_arrays()
       │   ├─ Extract close prices
       │   ├─ Extract high prices
       │   ├─ Extract low prices
       │   └─ Convert to numpy arrays
       │
       ├─► indicators.calculate_ema()
       │   └─ Return EMAOutput
       │
       ├─► indicators.calculate_macd()
       │   └─ Return MACDOutput
       │
       ├─► indicators.calculate_rsi()
       │   └─ Return RSIOutput
       │
       ├─► indicators.calculate_bollinger_bands()
       │   └─ Return BollingerBandsOutput
       │
       ├─► indicators.calculate_atr()
       │   └─ Return ATROutput
       │
       ▼
┌──────────────────────────────────┐
│ TechnicalIndicators              │
│ (aggregated result)              │
│ - ema: EMAOutput                 │
│ - macd: MACDOutput               │
│ - rsi: RSIOutput                 │
│ - bollinger_bands: BBOutput      │
│ - atr: ATROutput                 │
│ - timestamp: datetime            │
│ - candle_count: int              │
└──────────────────────────────────┘
       │
       ▼
Output: TechnicalIndicators
```

---

## 4. Component Interaction Diagram

### Service Integration

```
┌─────────────────────────────────────────────────────────────┐
│                    Caller (LLMService, API)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ 1. get_technical_analysis_service()
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              TechnicalAnalysisService                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ calculate_all_indicators(candles)                   │   │
│  │                                                     │   │
│  │ 1. Validate input                                   │   │
│  │ 2. Prepare numpy arrays                             │   │
│  │ 3. Call indicator functions                         │   │
│  │ 4. Aggregate results                                │   │
│  │ 5. Return TechnicalIndicators                       │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌─────────┐      ┌─────────┐      ┌─────────┐
   │ Schemas │      │Exceptions│     │Indicators│
   │         │      │          │     │          │
   │ Pydantic│      │ Custom   │     │ Pure     │
   │ Models  │      │ Errors   │     │ Functions│
   └─────────┘      └─────────┘     └─────────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
                  ┌─────────────────┐
                  │ NumPy / TA-Lib  │
                  │ (Calculations)  │
                  └─────────────────┘
```

---

## 5. Error Handling Flow

### Exception Hierarchy

```
Exception
    │
    └─► TechnicalAnalysisException (base)
        │
        ├─► InsufficientDataError
        │   └─ Raised when: len(candles) < 50
        │   └─ Message: "Insufficient candle data: X provided, 50 required"
        │
        ├─► InvalidCandleDataError
        │   └─ Raised when: Missing OHLC or High < Low
        │   └─ Message: "Invalid candle data at index X: ..."
        │
        └─► CalculationError
            └─ Raised when: talib/numpy error
            └─ Message: "Failed to calculate EMA: ..."
```

### Error Handling Pattern

```
try:
    indicators = ta_service.calculate_all_indicators(candles)
    
except InsufficientDataError as e:
    # Handle: Not enough data
    logger.warning(f"Insufficient data: {e}")
    return None
    
except InvalidCandleDataError as e:
    # Handle: Bad data
    logger.error(f"Invalid data: {e}")
    raise HTTPException(status_code=400, detail=str(e))
    
except CalculationError as e:
    # Handle: Calculation failed
    logger.error(f"Calculation failed: {e}")
    raise HTTPException(status_code=500, detail="Calculation failed")
    
except Exception as e:
    # Unexpected error
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

---

## 6. Data Structure Diagram

### TechnicalIndicators Schema

```
TechnicalIndicators
├── ema: EMAOutput
│   ├── ema: Optional[float]
│   └── period: int = 12
│
├── macd: MACDOutput
│   ├── macd: Optional[float]
│   ├── signal: Optional[float]
│   └── histogram: Optional[float]
│
├── rsi: RSIOutput
│   ├── rsi: Optional[float]
│   └── period: int = 14
│
├── bollinger_bands: BollingerBandsOutput
│   ├── upper: Optional[float]
│   ├── middle: Optional[float]
│   ├── lower: Optional[float]
│   ├── period: int = 20
│   └── std_dev: float = 2.0
│
├── atr: ATROutput
│   ├── atr: Optional[float]
│   └── period: int = 14
│
├── timestamp: datetime
└── candle_count: int
```

---

## 7. Dependency Graph

### Module Dependencies

```
__init__.py
    ├─► service.py
    │   ├─► indicators.py
    │   │   ├─► schemas.py
    │   │   ├─► exceptions.py
    │   │   ├─► numpy
    │   │   └─► talib
    │   ├─► schemas.py
    │   ├─► exceptions.py
    │   ├─► logging
    │   └─► models.market_data
    ├─► schemas.py
    │   └─► pydantic
    └─► exceptions.py

External Dependencies:
    ├─► numpy (array operations)
    ├─► talib (indicator calculations)
    ├─► pydantic (data validation)
    └─► logging (structured logging)
```

---

## 8. Integration Points

### With Existing Services

```
┌──────────────────────────────────────────────────────────┐
│                  LLMService                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │ get_trading_signal(symbol)                         │ │
│  │ 1. Fetch market data (MarketDataService)           │ │
│  │ 2. Calculate indicators (TechnicalAnalysisService) │ │
│  │ 3. Build prompt with indicators                    │ │
│  │ 4. Call LLM API                                    │ │
│  │ 5. Return signal                                   │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌──────────────────────┐      ┌──────────────────────────┐
│ MarketDataService    │      │ TechnicalAnalysisService │
│                      │      │                          │
│ get_latest_market_   │      │ calculate_all_indicators │
│ data(symbol, "1h")   │      │ (candles)                │
└──────────────────────┘      └──────────────────────────┘
         │                              │
         ▼                              ▼
┌──────────────────────┐      ┌──────────────────────────┐
│ MarketDataRepository │      │ Indicators Module        │
│                      │      │                          │
│ get_latest()         │      │ calculate_ema()          │
│ get_range()          │      │ calculate_macd()         │
└──────────────────────┘      │ calculate_rsi()          │
         │                    │ calculate_bollinger_     │
         ▼                    │ bands()                  │
┌──────────────────────┐      │ calculate_atr()          │
│ Market Data Table    │      └──────────────────────────┘
│ (TimescaleDB)        │
└──────────────────────┘
```

---

## 9. Calculation Pipeline

### Indicator Calculation Sequence

```
Input: close_prices, high_prices, low_prices (numpy arrays)

┌─────────────────────────────────────────────────────────┐
│ EMA Calculation                                         │
│ talib.EMA(close_prices, timeperiod=12)                 │
│ Returns: array of EMA values                           │
│ Output: EMAOutput(ema=last_value, period=12)           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ MACD Calculation                                        │
│ talib.MACD(close_prices)                               │
│ Returns: (macd, signal, histogram) arrays              │
│ Output: MACDOutput(macd=..., signal=..., hist=...)     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ RSI Calculation                                         │
│ talib.RSI(close_prices, timeperiod=14)                 │
│ Returns: array of RSI values (0-100)                   │
│ Output: RSIOutput(rsi=last_value, period=14)           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Bollinger Bands Calculation                             │
│ talib.BBANDS(close_prices, timeperiod=20, nbdevup=2)   │
│ Returns: (upper, middle, lower) arrays                 │
│ Output: BollingerBandsOutput(upper=..., middle=...,    │
│         lower=..., period=20, std_dev=2.0)             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ ATR Calculation                                         │
│ talib.ATR(high_prices, low_prices, close_prices,       │
│           timeperiod=14)                               │
│ Returns: array of ATR values                           │
│ Output: ATROutput(atr=last_value, period=14)           │
└─────────────────────────────────────────────────────────┘

All outputs aggregated into:
TechnicalIndicators(
    ema=..., macd=..., rsi=...,
    bollinger_bands=..., atr=...,
    timestamp=now, candle_count=len(candles)
)
```

---

## 10. Testing Architecture

### Test Structure

```
tests/
├── unit/
│   ├── test_technical_analysis.py
│   │   ├── test_ema_calculation()
│   │   ├── test_macd_calculation()
│   │   ├── test_rsi_calculation()
│   │   ├── test_bollinger_bands_calculation()
│   │   ├── test_atr_calculation()
│   │   ├── test_service_initialization()
│   │   ├── test_calculate_all_indicators()
│   │   ├── test_insufficient_data_error()
│   │   ├── test_invalid_candle_data_error()
│   │   └── test_calculation_error()
│   │
│   └── test_ta_service.py
│       ├── test_service_singleton()
│       ├── test_service_with_valid_data()
│       ├── test_service_with_invalid_data()
│       └── test_service_error_handling()
│
└── integration/
    └── test_ta_integration.py
        ├── test_with_market_data_service()
        ├── test_with_llm_service()
        ├── test_end_to_end_workflow()
        └── test_performance()
```

---

## 11. Deployment Architecture

### Production Deployment

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Container                       │
│  ┌───────────────────────────────────────────────────┐ │
│  │  FastAPI Application                              │ │
│  │  ┌─────────────────────────────────────────────┐ │ │
│  │  │ Technical Analysis Service                  │ │ │
│  │  │ - Singleton instance                        │ │ │
│  │  │ - Stateless calculations                    │ │ │
│  │  │ - No persistent state                       │ │ │
│  │  └─────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │  Dependencies                                      │ │
│  │  - numpy (pre-installed)                          │ │
│  │  - talib (pre-installed)                          │ │
│  │  - pydantic (pre-installed)                       │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              TimescaleDB Container                      │
│  - Market data (hypertable)                            │
│  - Optimized for time-series queries                   │
└─────────────────────────────────────────────────────────┘
```

---

## Summary

This architecture provides:
- **Modularity**: Clear separation of concerns
- **Scalability**: Stateless service, easy to scale
- **Testability**: Pure functions, easy to mock
- **Maintainability**: Clear structure, good documentation
- **Performance**: Efficient numpy/talib operations
- **Reliability**: Comprehensive error handling

