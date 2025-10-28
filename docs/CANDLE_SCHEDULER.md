# Candle-Close Based Scheduling

This document describes the candle-close based scheduling system implemented in the MarketDataService.

## Overview

The candle-close based scheduling system replaces the previous WebSocket-based approach with a more reliable and efficient method for fetching and processing market data at candle close times. This system ensures that we get complete and accurate candle data without the complexity and potential issues of maintaining persistent WebSocket connections.

## Key Features

- **Accurate Candle Timing**: Precisely schedules data fetches at candle close times
- **Multiple Intervals**: Supports both short and long candle intervals (configurable)
- **Event-Driven Architecture**: Uses an event system to notify components of candle closes
- **Automatic Retries**: Implements exponential backoff for failed requests
- **Graceful Shutdown**: Properly cleans up resources on shutdown

## Configuration

The system is configured using the following environment variables:

- `INTERVAL`: The primary candle interval (e.g., '1h', '4h')
- `LONG_INTERVAL`: The longer candle interval (e.g., '4h', '1d')
- `ASSETS`: Comma-separated list of trading pairs to monitor

## Usage

### Starting the Scheduler

```python
from app.services.market_data_service import get_market_data_service

# Get the market data service instance
market_data_service = get_market_data_service()

# Start the scheduler
await market_data_service.start_scheduler()
```

### Handling Candle Close Events

You can register event handlers to be called when a candle closes:

```python
from app.services.market_data_service import EventType, CandleCloseEvent

async def handle_candle_close(event: CandleCloseEvent):
    print(f"Candle closed: {event.symbol} {event.interval} at {event.close_time}")
    print(f"Candle data: {event.candle}")

# Register the handler for a specific interval
market_data_service.register_event_handler(
    EventType.CANDLE_CLOSE,
    handle_candle_close,
    interval="1h"  # or None for all intervals
)
```

### Checking Scheduler Status

```python
status = await market_data_service.get_scheduler_status()
print(f"Scheduler status: {status}")
```

### Stopping the Scheduler

```python
await market_data_service.stop_scheduler()
```

## Implementation Details

### Candle Close Calculation

The system calculates candle close times based on the interval:

- For minute intervals (e.g., '1m', '5m'), candles close at the top of each minute
- For hour intervals (e.g., '1h', '4h'), candles close at the top of the hour
- For day intervals (e.g., '1d'), candles close at midnight UTC

### Error Handling

- Failed API calls are automatically retried with exponential backoff
- The scheduler continues running even if processing a candle fails
- Errors are logged for monitoring and debugging

### Performance Considerations

- The scheduler uses asyncio for efficient concurrency
- Database operations are batched where possible
- The system is designed to handle multiple symbols and intervals efficiently

## Testing

A test script is available at `src/tests/test_candle_scheduler.py` that demonstrates how to use the scheduler and handle candle close events.

## Monitoring

Monitor the following log events:
- `Candle closed`: A candle has closed and been processed
- `Failed to fetch`: A candle fetch failed after retries
- `Scheduler status`: Periodic status updates

## Troubleshooting

### Common Issues

1. **Missed Candles**: If candles are being missed, check the logs for errors during fetch operations
2. **Incorrect Timing**: Verify that the system time is synchronized using NTP
3. **API Rate Limits**: If you hit rate limits, consider reducing the number of symbols or increasing the interval

### Logging

Enable debug logging for more detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Improvements

- Add support for backfilling missed candles
- Implement more sophisticated error recovery
- Add metrics and monitoring integration
- Support for custom candle intervals
