# System Design: Technical Analysis Service

## 1. Introduction & Purpose

This document outlines the design for a new `TechnicalAnalysisService` within the `vibex` backend. The primary purpose of this service is to calculate a suite of technical analysis (TA) indicators from OHLCV market data.

This service will encapsulate all logic related to TA calculations, providing a clean, reusable, and testable component that can be consumed by other services, such as the `LLMService` or a future `TradingService`. It will use the `TA-Lib` and `numpy` libraries for efficient and accurate calculations, as specified in the project requirements.

The design adheres to the existing architectural principles of the application, including modularity, single responsibility, and dependency injection.

## 2. Location and Module Structure

The new service will reside in `backend/src/app/services/technical_analysis/`. It will follow the established modular pattern:

```
backend/src/app/services/
├── ...
└── technical_analysis/
    ├── __init__.py          # Exports public interface (service & schemas)
    ├── service.py           # Main service class for orchestration
    ├── indicators.py        # Core calculation logic using TA-Lib/Numpy
    ├── schemas.py           # Pydantic models for indicator data structures
    └── README.md            # Documentation for this module
```

- **`service.py`**: Contains the `TechnicalAnalysisService` class, which orchestrates data preparation and calculation.
- **`indicators.py`**: Provides functions that perform the actual TA calculations. This isolates the mathematical logic.
- **`schemas.py`**: Defines the data contracts (inputs and outputs) for the service, ensuring type safety and clear structure.
- **`README.md`**: Contains documentation specific to this service.

## 3. Core Components & Design

### 3.1. `TechnicalAnalysisService` (`service.py`)

This is the main entry point for the service.

**Key Responsibilities:**
- Provide a single public method: `calculate_all_indicators(candles: List[MarketData])`.
- Accept a list of at least 50 `MarketData` objects (or a similar data structure) to ensure sufficient data for calculations.
- Coordinate the calculation of all required TA indicators by calling the appropriate functions in `indicators.py`.
- Return a single, structured `TechnicalIndicators` object containing the results.

**Dependencies:**
- It will receive candle data as an argument, decoupling it from the `MarketDataRepository`. This makes the service more flexible and easier to test.

```python
# backend/src/app/services/technical_analysis/service.py (Conceptual)

from typing import List
import numpy as np
from ...models.market_data import MarketData
from . import indicators
from .schemas import TechnicalIndicators

class TechnicalAnalysisService:
    """Service for calculating technical analysis indicators."""

    def calculate_all_indicators(self, candles: List[MarketData]) -> TechnicalIndicators:
        """
        Calculate all required TA indicators from a list of candles.

        Args:
            candles: A list of MarketData objects, ordered from oldest to newest.
                     Requires at least 50 candles for accurate calculations.

        Returns:
            A TechnicalIndicators object containing all calculated data.
        """
        if len(candles) < 50:
            raise ValueError("Not enough candle data provided for TA calculation (min 50).")

        # Prepare numpy arrays from candle data
        close_prices = np.array([c.close for c in candles])
        high_prices = np.array([c.high for c in candles])
        low_prices = np.array([c.low for c in candles])
        volume = np.array([c.volume for c in candles])

        # Calculate all indicators
        ema = indicators.calculate_ema(close_prices)
        macd = indicators.calculate_macd(close_prices)
        rsi = indicators.calculate_rsi(close_prices)
        bollinger_bands = indicators.calculate_bollinger_bands(close_prices)
        atr = indicators.calculate_atr(high_prices, low_prices, close_prices)

        # Assemble and return structured response
        return TechnicalIndicators(
            ema=ema,
            macd=macd,
            rsi=rsi,
            bollinger_bands=bollinger_bands,
            atr=atr,
        )
```

### 3.2. Indicator Calculation Logic (`indicators.py`)

This module contains the pure calculation functions.

**Key Responsibilities:**
- Implement functions for each required indicator: `calculate_ema`, `calculate_macd`, `calculate_rsi`, `calculate_bollinger_bands`, `calculate_atr`.
- Use `numpy` for data manipulation and `talib` for the core indicator calculations.
- Each function will accept one or more `numpy.ndarray` arguments (e.g., close prices, high prices) and return a Pydantic schema object with the results.

```python
# backend/src/app/services/technical_analysis/indicators.py (Conceptual)

import numpy as np
import talib
from .schemas import MACDOutput, RSIOutput, BollingerBandsOutput, EMAOutput, ATROutput

def calculate_macd(close_prices: np.ndarray) -> MACDOutput:
    macd, signal, hist = talib.MACD(close_prices)
    return MACDOutput(macd=macd[-1], signal=signal[-1], hist=hist[-1])

def calculate_rsi(close_prices: np.ndarray, period: int = 14) -> RSIOutput:
    rsi = talib.RSI(close_prices, timeperiod=period)
    return RSIOutput(rsi=rsi[-1], period=period)

# ... other indicator functions ...
```

### 3.3. Data Schemas (`schemas.py`)

This module defines the data structures for the service's output using Pydantic.

**Key Responsibilities:**
- Define specific schemas for each indicator's output (e.g., `MACDOutput`, `RSIOutput`).
- Define a comprehensive `TechnicalIndicators` schema that aggregates all the individual indicator schemas into a single object.

```python
# backend/src/app/services/technical_analysis/schemas.py (Conceptual)

from pydantic import BaseModel
from typing import Optional

class MACDOutput(BaseModel):
    macd: Optional[float]
    signal: Optional[float]
    hist: Optional[float]

class RSIOutput(BaseModel):
    rsi: Optional[float]
    period: int

class BollingerBandsOutput(BaseModel):
    upper: Optional[float]
    middle: Optional[float]
    lower: Optional[float]

# ... other schemas ...

class TechnicalIndicators(BaseModel):
    """Container for all calculated technical indicators."""
    ema: EMAOutput
    macd: MACDOutput
    rsi: RSIOutput
    bollinger_bands: BollingerBandsOutput
    atr: ATROutput
```

## 4. Integration and Usage

### 4.1. Service Registration

A singleton factory function will be created and exposed in `backend/src/app/services/__init__.py`.

```python
# backend/src/app/services/technical_analysis/__init__.py
from .service import TechnicalAnalysisService
from .schemas import TechnicalIndicators

_ta_service: Optional[TechnicalAnalysisService] = None

def get_technical_analysis_service() -> TechnicalAnalysisService:
    global _ta_service
    if _ta_service is None:
        _ta_service = TechnicalAnalysisService()
    return _ta_service

__all__ = ["get_technical_analysis_service", "TechnicalAnalysisService", "TechnicalIndicators"]
```

```python
# backend/src/app/services/__init__.py (Modification)
# ... existing imports
from .technical_analysis import TechnicalAnalysisService, get_technical_analysis_service

__all__ = [
    # ... existing exports
    "TechnicalAnalysisService",
    "get_technical_analysis_service",
]
```

### 4.2. Usage Example (within `LLMService`)

The `LLMService` can be updated to use this new service to get real-time indicator data for its prompts, replacing hardcoded or missing values.

```python
# backend/src/app/services/llm_service.py (Conceptual Change)

from ..services import get_market_data_service, get_technical_analysis_service

class LLMService:
    # ...

    async def get_trading_signal(self, symbol: str, ...):
        # 1. Fetch market data
        market_data_service = get_market_data_service()
        async with get_db() as db:
            candles = await market_data_service.get_latest_market_data(db, symbol, "1h", limit=100)

        # 2. Calculate indicators
        ta_service = get_technical_analysis_service()
        indicators = ta_service.calculate_all_indicators(candles)

        # 3. Build prompt with accurate data
        prompt = self._build_signal_prompt(
            symbol,
            market_data={"close": candles[-1].close, ...},
            indicators=indicators
        )
        # ...
```

## 5. Dependencies

The following Python libraries will be added to the `pyproject.toml`:

- `numpy`: For numerical operations and preparing data for TA-Lib.
- `TA-Lib`: The core library for performing the calculations. This requires the underlying TA-Lib C library to be installed on the system.

## 6. Testing Strategy

- **Unit Tests**: Each function in `indicators.py` will be tested in isolation with pre-defined `numpy` arrays to verify the correctness of the calculations against known values.
- **Service-Level Tests**: The `TechnicalAnalysisService` will be tested by mocking the input candle data and asserting that the final `TechnicalIndicators` object is structured correctly.
- **Integration Tests**: An integration test will verify that the `LLMService` (or another consumer) can successfully retrieve data from the `MarketDataService`, pass it to the `TechnicalAnalysisService`, and receive the calculated indicators.
