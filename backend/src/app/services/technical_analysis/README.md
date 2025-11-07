# Technical Analysis Service

A comprehensive technical analysis service for calculating financial indicators from market data.

## Overview

The Technical Analysis Service provides calculations for 5 key technical indicators, returning a series of the last 10 values for each.

1. **EMA (Exponential Moving Average)** - Trend following indicator with 12-period default
2. **MACD (Moving Average Convergence Divergence)** - Momentum indicator with MACD line, signal line, and histogram
3. **RSI (Relative Strength Index)** - Momentum oscillator (0-100) with 14-period default
4. **Bollinger Bands** - Volatility indicator with upper, middle, and lower bands
5. **ATR (Average True Range)** - Volatility indicator with 14-period default

## Features

- **Pure Functions**: Stateless indicator calculations using TA-Lib
- **Type Safety**: Pydantic models for all inputs and outputs
- **Error Handling**: Custom exceptions for different error scenarios
- **Validation**: Comprehensive candle data validation
- **Singleton Pattern**: Global service instance via factory function
- **Logging**: Structured logging for debugging and monitoring

## Installation

The service is part of the trading application. Dependencies are already included in `pyproject.toml`:

```bash
cd backend
uv sync
```

## Usage

### Basic Usage

```python
from app.services import get_technical_analysis_service
from app.models.market_data import MarketData

# Get the service instance
ta_service = get_technical_analysis_service()

# Prepare market data (requires at least 50 candles)
candles = [...]  # List of MarketData objects

# Calculate all indicators
indicators = ta_service.calculate_all_indicators(candles)

# Access individual indicators (last value in the series)
print(f"Last EMA: {indicators.ema.ema[-1]}")
print(f"Last RSI: {indicators.rsi.rsi[-1]}")
print(f"Last MACD: {indicators.macd.macd[-1]}")
print(f"Last Bollinger Bands Upper: {indicators.bollinger_bands.upper[-1]}")
print(f"Last ATR: {indicators.atr.atr[-1]}")
```

### Error Handling

```python
from app.services.technical_analysis.exceptions import (
    InsufficientDataError,
    InvalidCandleDataError,
    CalculationError,
)

try:
    indicators = ta_service.calculate_all_indicators(candles)
except InsufficientDataError as e:
    print(f"Not enough data: {e}")
except InvalidCandleDataError as e:
    print(f"Invalid candle data: {e}")
except CalculationError as e:
    print(f"Calculation failed: {e}")
```

### Output Format

The service returns a `TechnicalIndicators` object containing a series of the last 10 values for each indicator.

```python
{
    "ema": {
        "ema": [44998.1, 44999.5, 45000.5, 45001.2, 45002.8, 45003.4, 45004.1, 45005.0, 45005.3, 45005.5],
        "period": 12
    },
    "macd": {
        "macd": [98.1, 99.2, 100.5, 101.1, 101.5, 101.0, 100.8, 100.9, 100.7, 100.6],
        "signal": [94.1, 94.5, 95.2, 96.0, 96.8, 97.5, 98.1, 98.6, 99.0, 99.3],
        "histogram": [4.0, 4.7, 5.3, 5.1, 4.7, 3.5, 2.7, 2.3, 1.7, 1.3]
    },
    "rsi": {
        "rsi": [64.1, 64.5, 65.5, 66.2, 66.8, 65.9, 65.2, 64.8, 64.5, 64.2],
        "period": 14
    },
    "bollinger_bands": {
        "upper": [45900.0, 45950.0, 46000.0, 46050.0, 46100.0, 46150.0, 46200.0, 46250.0, 46300.0, 46350.0],
        "middle": [44900.0, 44950.0, 45000.0, 45050.0, 45100.0, 45150.0, 45200.0, 45250.0, 45300.0, 45350.0],
        "lower": [43900.0, 43950.0, 44000.0, 44050.0, 44100.0, 44150.0, 44200.0, 44250.0, 44300.0, 44350.0],
        "period": 20,
        "std_dev": 2.0
    },
    "atr": {
        "atr": [490.0, 492.1, 500.0, 501.2, 503.4, 505.1, 504.8, 506.3, 507.0, 508.1],
        "period": 14
    },
    "timestamp": "2024-01-01T12:00:00",
    "candle_count": 100,
    "series_length": 10
}
```

## Module Structure

```
technical_analysis/
├── __init__.py           # Public API and singleton factory
├── service.py            # Main service class
├── indicators.py         # Indicator calculation functions
├── schemas.py            # Pydantic data models
├── exceptions.py         # Custom exception classes
└── README.md             # This file
```

## API Reference

### TechnicalAnalysisService

#### `calculate_all_indicators(candles: List[MarketData]) -> TechnicalIndicators`

Calculate all technical indicators from a list of market data candles.

**Parameters:**
- `candles`: List of MarketData objects ordered from oldest to newest. Requires at least 50 candles.

**Returns:**
- `TechnicalIndicators`: Object containing a series of the last 10 values for each calculated indicator.

**Raises:**
- `InsufficientDataError`: If fewer than 50 candles provided
- `InvalidCandleDataError`: If candle data is invalid or incomplete
- `CalculationError`: If indicator calculation fails

### Indicator Functions

All indicator functions are in `indicators.py`:

- `calculate_ema(close_prices: np.ndarray) -> EMAOutput`
- `calculate_macd(close_prices: np.ndarray) -> MACDOutput`
- `calculate_rsi(close_prices: np.ndarray) -> RSIOutput`
- `calculate_bollinger_bands(close_prices: np.ndarray) -> BollingerBandsOutput`
- `calculate_atr(high_prices: np.ndarray, low_prices: np.ndarray, close_prices: np.ndarray) -> ATROutput`

## Data Requirements

### Minimum Candles
- **50 candles minimum** required for accurate calculations
- Candles should be ordered from oldest to newest

### Candle Data Validation
The service validates:
- All OHLC fields are present (open, high, low, close)
- High >= Low
- No negative prices
- No negative volume

## Testing

### Unit Tests
```bash
cd backend
uv run pytest tests/unit/test_technical_analysis.py -v
```

### Integration Tests
```bash
cd backend
uv run pytest tests/integration/test_technical_analysis_integration.py -v
```

### All Tests
```bash
cd backend
uv run pytest tests/unit/test_technical_analysis.py tests/integration/test_technical_analysis_integration.py -v
```

## Performance

- **Calculation Time**: ~10-50ms for 100 candles (depends on system)
- **Memory Usage**: Minimal (arrays are temporary)
- **Scalability**: Handles 500+ candles efficiently

## Dependencies

- **TA-Lib** (>=0.6.8): Technical analysis library
- **NumPy** (>=2.3.4): Array operations
- **Pydantic** (>=2.0): Data validation

## Integration Points

### With LLMService
The Technical Analysis Service integrates with LLMService to provide market indicators for AI-powered trading signals:

```python
from app.services import get_llm_service, get_technical_analysis_service

llm_service = get_llm_service()
ta_service = get_technical_analysis_service()

# Get market data
candles = ...

# Calculate indicators
indicators = ta_service.calculate_all_indicators(candles)

# Use in LLM prompt
signal = llm_service.get_trading_signal(symbol, indicators)
```

### With MarketDataService
The service receives market data from MarketDataService:

```python
from app.services import get_market_data_service, get_technical_analysis_service

market_service = get_market_data_service()
ta_service = get_technical_analysis_service()

# Get latest market data
candles = market_service.get_latest_market_data(symbol, "1h", limit=100)

# Calculate indicators
indicators = ta_service.calculate_all_indicators(candles)
```

## Logging

The service uses structured logging. Enable debug logging to see detailed calculation information:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.services.technical_analysis")
```

## Troubleshooting

### InsufficientDataError
**Problem**: "Insufficient candle data: X provided, 50 required"
**Solution**: Provide at least 50 candles for calculation

### InvalidCandleDataError
**Problem**: "Invalid candle data at index X: ..."
**Solution**: Check that all candles have valid OHLCV data and High >= Low

### CalculationError
**Problem**: "Failed to calculate EMA: ..."
**Solution**: Check that input data is valid and not corrupted

## Future Enhancements

- Additional indicators (Stochastic, CCI, ADX, etc.)
- Configurable indicator periods
- Caching for repeated calculations
- Async calculation support
- Performance optimizations

## Contributing

When adding new indicators:

1. Add calculation function to `indicators.py`
2. Add output schema to `schemas.py`
3. Add to `TechnicalIndicators` schema
4. Add to `calculate_all_indicators()` method
5. Add unit tests
6. Update documentation

## License

Part of the Vibex trading application.

