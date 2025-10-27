# Technical Analysis Service: Implementation Guide

## Overview

This guide provides detailed implementation specifications for each component of the Technical Analysis Service. Follow this guide sequentially to implement the service correctly.

---

## 1. Schemas Implementation (`schemas.py`)

### 1.1 Individual Indicator Schemas

Each indicator has its own output schema with relevant fields:

```python
# EMA (Exponential Moving Average)
class EMAOutput(BaseModel):
    """EMA indicator output."""
    ema: Optional[float] = Field(None, description="EMA value")
    period: int = Field(default=12, description="EMA period")

# MACD (Moving Average Convergence Divergence)
class MACDOutput(BaseModel):
    """MACD indicator output."""
    macd: Optional[float] = Field(None, description="MACD line")
    signal: Optional[float] = Field(None, description="Signal line")
    histogram: Optional[float] = Field(None, description="MACD histogram")

# RSI (Relative Strength Index)
class RSIOutput(BaseModel):
    """RSI indicator output."""
    rsi: Optional[float] = Field(None, description="RSI value (0-100)")
    period: int = Field(default=14, description="RSI period")

# Bollinger Bands
class BollingerBandsOutput(BaseModel):
    """Bollinger Bands indicator output."""
    upper: Optional[float] = Field(None, description="Upper band")
    middle: Optional[float] = Field(None, description="Middle band (SMA)")
    lower: Optional[float] = Field(None, description="Lower band")
    period: int = Field(default=20, description="Period")
    std_dev: float = Field(default=2.0, description="Standard deviations")

# ATR (Average True Range)
class ATROutput(BaseModel):
    """ATR indicator output."""
    atr: Optional[float] = Field(None, description="ATR value")
    period: int = Field(default=14, description="ATR period")
```

### 1.2 Aggregated Schema

```python
class TechnicalIndicators(BaseModel):
    """Container for all calculated technical indicators."""
    
    ema: EMAOutput
    macd: MACDOutput
    rsi: RSIOutput
    bollinger_bands: BollingerBandsOutput
    atr: ATROutput
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    candle_count: int = Field(description="Number of candles used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ema": {"ema": 45000.5, "period": 12},
                "macd": {"macd": 100.5, "signal": 95.2, "histogram": 5.3},
                "rsi": {"rsi": 65.5, "period": 14},
                "bollinger_bands": {
                    "upper": 46000.0,
                    "middle": 45000.0,
                    "lower": 44000.0,
                    "period": 20,
                    "std_dev": 2.0
                },
                "atr": {"atr": 500.0, "period": 14},
                "timestamp": "2024-01-01T12:00:00",
                "candle_count": 100
            }
        }
```

---

## 2. Exceptions Implementation (`exceptions.py`)

```python
class TechnicalAnalysisException(Exception):
    """Base exception for technical analysis service."""
    pass

class InsufficientDataError(TechnicalAnalysisException):
    """Raised when insufficient candle data provided."""
    def __init__(self, provided: int, required: int = 50):
        self.provided = provided
        self.required = required
        super().__init__(
            f"Insufficient candle data: {provided} provided, {required} required"
        )

class InvalidCandleDataError(TechnicalAnalysisException):
    """Raised when candle data is invalid or incomplete."""
    def __init__(self, message: str, candle_index: int = None):
        self.candle_index = candle_index
        super().__init__(f"Invalid candle data at index {candle_index}: {message}")

class CalculationError(TechnicalAnalysisException):
    """Raised when indicator calculation fails."""
    def __init__(self, indicator_name: str, original_error: Exception):
        self.indicator_name = indicator_name
        self.original_error = original_error
        super().__init__(
            f"Failed to calculate {indicator_name}: {str(original_error)}"
        )
```

---

## 3. Indicators Implementation (`indicators.py`)

### 3.1 Helper Functions

```python
def _validate_array_length(arr: np.ndarray, min_length: int = 50) -> None:
    """Validate array has minimum length."""
    if len(arr) < min_length:
        raise InsufficientDataError(len(arr), min_length)

def _handle_calculation_error(
    indicator_name: str, 
    error: Exception
) -> CalculationError:
    """Convert calculation errors to service exceptions."""
    return CalculationError(indicator_name, error)
```

### 3.2 Indicator Functions

**Key Implementation Details:**

1. **EMA (12-period default)**
   - Use talib.EMA()
   - Return last value
   - Handle NaN values

2. **MACD (12, 26, 9 defaults)**
   - Use talib.MACD()
   - Returns (macd, signal, histogram)
   - Return last values

3. **RSI (14-period default)**
   - Use talib.RSI()
   - Returns values 0-100
   - Return last value

4. **Bollinger Bands (20-period, 2 std dev)**
   - Use talib.BBANDS()
   - Returns (upper, middle, lower)
   - Return last values

5. **ATR (14-period default)**
   - Use talib.ATR()
   - Requires high, low, close
   - Return last value

### 3.3 Error Handling Pattern

```python
def calculate_ema(close_prices: np.ndarray) -> EMAOutput:
    """Calculate EMA indicator."""
    try:
        _validate_array_length(close_prices)
        ema_values = talib.EMA(close_prices, timeperiod=12)
        ema = float(ema_values[-1]) if not np.isnan(ema_values[-1]) else None
        return EMAOutput(ema=ema, period=12)
    except Exception as e:
        logger.error(f"EMA calculation failed: {e}")
        raise _handle_calculation_error("EMA", e)
```

---

## 4. Service Implementation (`service.py`)

### 4.1 Class Structure

```python
class TechnicalAnalysisService:
    """Service for calculating technical analysis indicators."""
    
    MIN_CANDLES = 50
    
    def __init__(self):
        """Initialize the service."""
        logger.info("TechnicalAnalysisService initialized")
    
    def calculate_all_indicators(
        self, 
        candles: List[MarketData]
    ) -> TechnicalIndicators:
        """
        Calculate all technical indicators.
        
        Args:
            candles: List of MarketData objects (oldest to newest)
        
        Returns:
            TechnicalIndicators with all calculated values
        
        Raises:
            InsufficientDataError: If < 50 candles
            InvalidCandleDataError: If candle data invalid
            CalculationError: If calculation fails
        """
        # Validate input
        self._validate_candles(candles)
        
        # Prepare arrays
        close_prices, high_prices, low_prices, volume = self._prepare_arrays(candles)
        
        # Calculate indicators
        ema = indicators.calculate_ema(close_prices)
        macd = indicators.calculate_macd(close_prices)
        rsi = indicators.calculate_rsi(close_prices)
        bollinger_bands = indicators.calculate_bollinger_bands(close_prices)
        atr = indicators.calculate_atr(high_prices, low_prices, close_prices)
        
        # Assemble result
        return TechnicalIndicators(
            ema=ema,
            macd=macd,
            rsi=rsi,
            bollinger_bands=bollinger_bands,
            atr=atr,
            candle_count=len(candles)
        )
    
    def _validate_candles(self, candles: List[MarketData]) -> None:
        """Validate candle data."""
        if len(candles) < self.MIN_CANDLES:
            raise InsufficientDataError(len(candles), self.MIN_CANDLES)
        
        for i, candle in enumerate(candles):
            if not all([candle.open, candle.high, candle.low, candle.close]):
                raise InvalidCandleDataError(
                    "Missing OHLC data",
                    candle_index=i
                )
            if candle.high < candle.low:
                raise InvalidCandleDataError(
                    "High < Low",
                    candle_index=i
                )
    
    def _prepare_arrays(
        self, 
        candles: List[MarketData]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Convert candles to numpy arrays."""
        close_prices = np.array([c.close for c in candles], dtype=np.float64)
        high_prices = np.array([c.high for c in candles], dtype=np.float64)
        low_prices = np.array([c.low for c in candles], dtype=np.float64)
        volume = np.array([c.volume for c in candles], dtype=np.float64)
        
        return close_prices, high_prices, low_prices, volume
```

---

## 5. Module Initialization (`__init__.py`)

```python
"""Technical Analysis Service module."""

from typing import Optional

from .service import TechnicalAnalysisService
from .schemas import TechnicalIndicators

__all__ = [
    "TechnicalAnalysisService",
    "TechnicalIndicators",
    "get_technical_analysis_service",
]

# Global service instance
_ta_service: Optional[TechnicalAnalysisService] = None

def get_technical_analysis_service() -> TechnicalAnalysisService:
    """Get or create the technical analysis service instance."""
    global _ta_service
    if _ta_service is None:
        _ta_service = TechnicalAnalysisService()
    return _ta_service
```

---

## 6. Services Module Update

Update `backend/src/app/services/__init__.py`:

```python
from .llm_service import LLMService, get_llm_service
from .market_data import MarketDataService, get_market_data_service
from .technical_analysis import (
    TechnicalAnalysisService,
    TechnicalIndicators,
    get_technical_analysis_service,
)

__all__ = [
    "MarketDataService",
    "get_market_data_service",
    "LLMService",
    "get_llm_service",
    "TechnicalAnalysisService",
    "TechnicalIndicators",
    "get_technical_analysis_service",
]
```

---

## 7. Integration with LLMService

Update `backend/src/app/services/llm_service.py`:

```python
async def get_trading_signal(self, symbol: str, ...):
    """Get trading signal with technical indicators."""
    from . import get_market_data_service, get_technical_analysis_service
    
    # Fetch market data
    market_data_service = get_market_data_service()
    async with get_db() as db:
        candles = await market_data_service.get_latest_market_data(
            db, symbol, "1h", limit=100
        )
    
    # Calculate indicators
    ta_service = get_technical_analysis_service()
    indicators = ta_service.calculate_all_indicators(candles)
    
    # Build prompt with indicators
    prompt = self._build_signal_prompt(
        symbol,
        market_data={"close": candles[-1].close},
        indicators=indicators.model_dump()
    )
    
    # ... rest of implementation
```

---

## 8. Testing Structure

### Unit Tests Location
`backend/tests/unit/test_technical_analysis.py`

### Integration Tests Location
`backend/tests/integration/test_ta_integration.py`

### Test Fixtures
- Mock MarketData objects
- Known indicator values for validation
- Edge case data (NaN, zero volume, etc.)

---

## 9. Implementation Order

1. Create directory structure
2. Implement `schemas.py`
3. Implement `exceptions.py`
4. Implement `indicators.py` (with tests)
5. Implement `service.py` (with tests)
6. Create `__init__.py`
7. Update `services/__init__.py`
8. Write integration tests
9. Update LLMService (optional)
10. Create README.md

---

## 10. Validation Checklist

- [ ] All 5 indicators implemented
- [ ] All schemas defined with proper types
- [ ] All exceptions defined
- [ ] Service validates input (50+ candles)
- [ ] Service handles errors gracefully
- [ ] All functions have type hints
- [ ] All functions have docstrings
- [ ] Unit tests for each indicator
- [ ] Service-level tests
- [ ] Integration tests
- [ ] >90% code coverage
- [ ] No breaking changes to existing code

