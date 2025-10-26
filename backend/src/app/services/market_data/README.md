# Market Data Service Module

A modular, well-structured service for fetching, storing, and scheduling market data from Aster DEX.

## 📁 Module Structure

```
market_data/
├── __init__.py          # Public API exports
├── events.py            # Event system (80 lines)
├── utils.py             # Time/interval utilities (50 lines)
├── client.py            # Aster DEX API client (100 lines)
├── repository.py        # Database operations (180 lines)
├── scheduler.py         # Candle-close scheduler (170 lines)
└── service.py           # Main service orchestration (350 lines)
```

**Total:** ~930 lines across 7 focused modules (previously 713 lines in 1 file)

## 🎯 Design Principles

### Single Responsibility Principle
Each module has one clear purpose:
- **events.py** → Event system only
- **scheduler.py** → Scheduling logic only
- **client.py** → API communication only
- **repository.py** → Database operations only
- **utils.py** → Helper functions only
- **service.py** → Orchestration only

### Separation of Concerns
- **Business logic** (service.py) is separate from **infrastructure** (client, repository)
- **Scheduling** is independent of **data fetching**
- **Events** can be used by any component

### Dependency Injection
The service composes its dependencies:
```python
self.client = AsterClient(...)
self.repository = MarketDataRepository()
self.event_manager = EventManager()
self.scheduler = CandleScheduler(...)
```

## 📚 Module Documentation

### `events.py`
**Purpose:** Event system for market data notifications

**Key Classes:**
- `BaseEvent` - Base class for all events
- `CandleCloseEvent` - Event triggered when a candle closes
- `EventType` - Enum of event types
- `EventManager` - Manages event handlers and dispatching

**Usage:**
```python
from .events import EventManager, EventType, CandleCloseEvent

manager = EventManager()
manager.register_handler(EventType.CANDLE_CLOSE, my_handler)
await manager.trigger_event(event, EventType.CANDLE_CLOSE, interval="1h")
```

---

### `utils.py`
**Purpose:** Time and interval utility functions

**Key Functions:**
- `get_interval_seconds(interval)` - Convert interval string to seconds
- `calculate_next_candle_close(interval, current_time)` - Calculate next candle close time
- `calculate_previous_candle_close(interval, current_time)` - Calculate previous candle close time
- `format_symbol(asset, quote_currency)` - Format asset to trading pair symbol
- `validate_interval(interval)` - Validate if interval is supported

**Usage:**
```python
from .utils import format_symbol, get_interval_seconds

symbol = format_symbol("BTC")  # Returns "BTCUSDT"
seconds = get_interval_seconds("1h")  # Returns 3600
```

---

### `client.py`
**Purpose:** Aster DEX API client wrapper

**Key Classes:**
- `AsterClient` - Wrapper for Aster DEX REST API

**Features:**
- Thread-safe client creation (new instance per request)
- Async wrapper for blocking I/O operations
- Automatic error handling and logging

**Usage:**
```python
from .client import AsterClient

client = AsterClient(api_key, api_secret, base_url)
candles = await client.fetch_klines("BTCUSDT", "1h", limit=100)
```

---

### `repository.py`
**Purpose:** Database operations for market data

**Key Classes:**
- `MarketDataRepository` - Repository for market data CRUD operations

**Methods:**
- `store_candles(db, symbol, interval, data)` - Store candles with upsert logic
- `get_latest(db, symbol, interval, limit)` - Get latest market data
- `get_range(db, symbol, interval, start_time, end_time)` - Get data in time range

**Usage:**
```python
from .repository import MarketDataRepository

repo = MarketDataRepository()
count = await repo.store_candles(db, "BTCUSDT", "1h", candles)
data = await repo.get_latest(db, "BTCUSDT", "1h", limit=100)
```

---

### `scheduler.py`
**Purpose:** Candle-close based scheduling

**Key Classes:**
- `CandleScheduler` - Manages candle-close based scheduling

**Features:**
- Multi-interval support (e.g., 1h and 4h simultaneously)
- Graceful shutdown handling
- Automatic retry with exponential backoff
- Status reporting

**Usage:**
```python
from .scheduler import CandleScheduler

scheduler = CandleScheduler(
    intervals=["1h", "4h"],
    event_manager=event_manager,
    fetch_callback=my_fetch_function
)
await scheduler.start()
status = await scheduler.get_status()
await scheduler.stop()
```

---

### `service.py`
**Purpose:** Main service orchestrating all components

**Key Classes:**
- `MarketDataService` - Main service class
- `get_market_data_service()` - Singleton factory function

**Public API:**
```python
# Scheduler control
await service.start_scheduler()
await service.stop_scheduler()
status = await service.get_scheduler_status()

# Event handling
service.register_event_handler(EventType.CANDLE_CLOSE, handler)

# Data operations
candles = await service.fetch_market_data("BTCUSDT", "1h", limit=100)
count = await service.store_market_data(db, "BTCUSDT", "1h", candles)
data = await service.get_latest_market_data(db, "BTCUSDT", "1h", limit=100)
data = await service.get_market_data_range(db, "BTCUSDT", "1h", start, end)
results = await service.sync_market_data(db, symbol="BTCUSDT")
```

---

## 🚀 Usage Examples

### Basic Usage
```python
from src.app.services import get_market_data_service

# Get the singleton service instance
service = get_market_data_service()

# Start the scheduler
await service.start_scheduler()

# Fetch market data
candles = await service.fetch_market_data("BTCUSDT", "1h", limit=100)

# Store in database
async with get_db() as db:
    count = await service.store_market_data(db, "BTCUSDT", "1h", candles)
```

### Custom Event Handler
```python
from src.app.services import get_market_data_service
from src.app.services.market_data import EventType, CandleCloseEvent

async def my_candle_handler(event: CandleCloseEvent):
    print(f"Candle closed: {event.symbol} {event.interval} at {event.close_time}")
    # Your custom logic here

service = get_market_data_service()
service.register_event_handler(EventType.CANDLE_CLOSE, my_candle_handler, interval="1h")
```

### Direct Component Usage
```python
from src.app.services.market_data.client import AsterClient
from src.app.services.market_data.repository import MarketDataRepository
from src.app.core.config import config

# Use client directly
client = AsterClient(
    api_key=config.ASTERDEX_API_KEY,
    api_secret=config.ASTERDEX_API_SECRET,
    base_url=config.ASTERDEX_BASE_URL
)
candles = await client.fetch_klines("BTCUSDT", "1h", limit=100)

# Use repository directly
repo = MarketDataRepository()
async with get_db() as db:
    count = await repo.store_candles(db, "BTCUSDT", "1h", candles)
```

## 🧪 Testing

Each module can be tested independently:

```python
# Test client
from src.app.services.market_data.client import AsterClient

async def test_client():
    client = AsterClient(api_key, api_secret, base_url)
    candles = await client.fetch_klines("BTCUSDT", "1h", limit=10)
    assert len(candles) == 10

# Test repository
from src.app.services.market_data.repository import MarketDataRepository

async def test_repository():
    repo = MarketDataRepository()
    count = await repo.store_candles(db, "BTCUSDT", "1h", test_data)
    assert count == len(test_data)

# Test utils
from src.app.services.market_data.utils import format_symbol, get_interval_seconds

def test_utils():
    assert format_symbol("BTC") == "BTCUSDT"
    assert get_interval_seconds("1h") == 3600
```

## 📊 Benefits of This Structure

### 1. **Maintainability**
- Easy to find code (know which file to look in)
- Modify one concern without affecting others
- Clear module boundaries

### 2. **Testability**
- Test each component in isolation
- Mock dependencies easily
- Smaller, focused test files

### 3. **Reusability**
- `AsterClient` can be used by other services
- `EventManager` can handle other event types
- `CandleScheduler` can be reused for different scheduling needs

### 4. **Scalability**
- Easy to add new features (e.g., WebSocket streaming)
- Can split further if modules grow too large
- Clear extension points

### 5. **Onboarding**
- New developers can understand one module at a time
- Clear documentation per module
- Obvious where to add new features

## 🔄 Migration Notes

### Backward Compatibility
The public API remains unchanged:
```python
from src.app.services import get_market_data_service

service = get_market_data_service()
# All existing code continues to work!
```

### What Changed
- **Before:** 1 file with 713 lines
- **After:** 7 files with ~930 lines total (includes better documentation)

### Import Changes
Only direct imports of internal classes need updates:
```python
# Old (no longer works)
from src.app.services.market_data_service import CandleCloseEvent

# New
from src.app.services.market_data import CandleCloseEvent
```

## 📝 Future Enhancements

Potential additions to this module:
- **WebSocket streaming** (add `websocket.py`)
- **Caching layer** (add `cache.py`)
- **Data validation** (add `validators.py`)
- **Metrics/monitoring** (add `metrics.py`)
- **More event types** (extend `events.py`)

Each can be added as a new focused module without disrupting existing code.

