# WebSocket Market Data Implementation

## Overview
This document describes the WebSocket implementation for real-time market data updates in the Vibex trading agent.

## Implementation Status: ✅ COMPLETED

### Components Implemented

#### 1. Database Schema (`init-db.sql`)
- ✅ Added all required columns to `market_data` table:
  - `id` (SERIAL)
  - `interval` (VARCHAR)
  - `quote_asset_volume` (DECIMAL)
  - `number_of_trades` (DECIMAL)
  - `taker_buy_base_asset_volume` (DECIMAL)
  - `taker_buy_quote_asset_volume` (DECIMAL)
- ✅ Updated primary key to support TimescaleDB hypertable
- ✅ Schema matches MarketData model and Aster API response

#### 2. Market Data Service (`market_data_service.py`)
- ✅ WebSocket client initialization with lazy loading
- ✅ Connection management with automatic reconnection
- ✅ Subscription handling for kline/candlestick streams
- ✅ Message processing and routing
- ✅ Error handling and logging
- ✅ Heartbeat mechanism to maintain connection
- ✅ Upsert logic for storing market data (prevents duplicates)
- ✅ Support for both short and long intervals

#### 3. WebSocket Features
- ✅ `initialize_websocket()`: Connects and subscribes to all configured assets
- ✅ `connect_websocket()`: Establishes WebSocket connection
- ✅ `subscribe_market_data()`: Subscribes to specific symbol/interval
- ✅ `_handle_market_data_update()`: Processes incoming kline updates
- ✅ `close_websocket()`: Graceful shutdown and cleanup
- ✅ `_reconnect_ws()`: Exponential backoff reconnection logic
- ✅ `_ws_heartbeat()`: Maintains connection with periodic pings

#### 4. Application Integration (`main.py`)
- ✅ WebSocket initialization on application startup
- ✅ Automatic subscription to all configured assets
- ✅ Subscriptions for both `INTERVAL` and `LONG_INTERVAL`
- ✅ Graceful shutdown and cleanup on application exit

## Configuration

### Environment Variables
- `ASSETS`: Comma-separated list of trading pairs (e.g., "BTC,ETH,SOL")
- `INTERVAL`: Short interval for market data (e.g., "1h")
- `LONG_INTERVAL`: Long interval for market data (e.g., "4h")
- `ASTERDEX_API_KEY`: API key for Aster DEX
- `ASTERDEX_API_SECRET`: API secret for Aster DEX
- `ASTERDEX_BASE_URL`: Base URL for Aster API

### WebSocket Constants
- `WEBSOCKET_PING_INTERVAL`: Interval for heartbeat pings (defined in `core/constants.py`)

## Usage

### Starting the Application
```bash
cd backend
podman-compose up
```

The WebSocket service will automatically:
1. Connect to Aster DEX WebSocket endpoint
2. Subscribe to all configured assets
3. Listen for real-time market data updates
4. Log incoming updates (debug level)

### Manual Sync
You can still manually sync historical data via the API:
```bash
curl -X POST http://localhost:3000/api/v1/market-data/sync-all
```

## Architecture

### WebSocket Flow
1. **Startup**: Application starts → `initialize_websocket()` called
2. **Connection**: Connects to `wss://fstream.asterdex.com/ws`
3. **Subscription**: Subscribes to streams like `btcusdt@kline_1h`, `ethusdt@kline_4h`
4. **Updates**: Receives real-time kline updates
5. **Processing**: `_handle_market_data_update()` processes each update
6. **Shutdown**: `close_websocket()` gracefully closes connections

### Error Handling
- Connection failures trigger automatic reconnection with exponential backoff
- Max 5 reconnection attempts with delays capped at 30 seconds
- Failed subscriptions are logged but don't block other subscriptions
- All errors are logged with appropriate context

## Future Enhancements

### Potential Improvements
- [ ] Store real-time updates directly to database (currently only logs)
- [ ] Implement in-memory cache for latest market data
- [ ] Add WebSocket health monitoring endpoint
- [ ] Implement rate limiting for database writes
- [ ] Add metrics collection for WebSocket performance
- [ ] Support for additional stream types (trades, depth, ticker)

## Testing

### Verify WebSocket Connection
1. Start the application
2. Check logs for: `"WebSocket market data subscriptions initialized"`
3. Monitor debug logs for: `"Market data update - {symbol} {interval}"`

### Check Database
```sql
SELECT symbol, interval, COUNT(*) as count, MAX(time) as latest
FROM trading.market_data
GROUP BY symbol, interval
ORDER BY symbol, interval;
```

## Notes
- WebSocket updates are logged at DEBUG level to avoid log spam
- The service uses a singleton pattern via `get_market_data_service()`
- All WebSocket operations are async and non-blocking
- The implementation follows Aster DEX WebSocket API specifications
