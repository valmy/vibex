# Aster Connector Python Library - API Documentation

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [REST API Client](#rest-api-client)
- [Market Data Endpoints](#market-data-endpoints)
- [Account & Trading Endpoints](#account--trading-endpoints)
- [User Data Streams](#user-data-streams)
- [WebSocket Client](#websocket-client)
- [Error Handling](#error-handling)
- [Configuration Options](#configuration-options)

## Overview

The Aster Connector Python Library is a lightweight connector to the Aster Finance public API. It provides both REST and WebSocket API access for trading and market data operations.

## Installation

Install the library using pip:

```bash
pip install aster-connector-python
```

## Quick Start

### REST API Client

```python
from aster.rest_api import Client

# Public API calls (no authentication required)
client = Client()
print(client.time())  # Get server time
print(client.ping())  # Test connectivity

# Authenticated API calls
client = Client(key='<api_key>', secret='<api_secret>')

# Get account information
print(client.account())

# Place a new order
params = {
    'symbol': 'BTCUSDT',
    'side': 'SELL',
    'type': 'LIMIT',
    'timeInForce': 'GTC',
    'quantity': 0.002,
    'price': 59808
}

response = client.new_order(**params)
print(response)
```

### WebSocket Client

```python
from aster.websocket.client.stream import WebsocketClient as Client

def message_handler(message):
    print(message)

ws_client = Client()
ws_client.start()

# Subscribe to mini ticker for a specific symbol
ws_client.mini_ticker(
    symbol='bnbusdt',
    id=1,
    callback=message_handler,
)

# Combine selected streams
ws_client.instant_subscribe(
    stream=['bnbusdt@bookTicker', 'ethusdt@bookTicker'],
    callback=message_handler,
)

ws_client.stop()
```

## Authentication

The library supports API key and secret authentication for private endpoints:

```python
from aster.rest_api import Client

# Initialize client with API credentials
client = Client(
    key='<your-api-key>',
    secret='<your-api-secret>'
)
```

## REST API Client

The `Client` class extends the `API` class and provides methods for all available endpoints.

### Initialization Options

```python
from aster.rest_api import Client

client = Client(
    key=None,                    # API key (optional for public endpoints)
    secret=None,                 # API secret (optional for public endpoints)
    base_url='https://fapi.asterdex.com',  # Base API URL (default)
    timeout=None,                # Request timeout in seconds
    proxies=None,                # Proxy configuration (e.g., {'https': 'http://1.2.3.4:8080'})
    show_limit_usage=False,      # Show rate limit usage in response
    show_header=False            # Show full response headers
)
```

## Market Data Endpoints

### Connectivity

#### ping()
Test connectivity to the API.

```python
client.ping()
```

#### time()
Get the current server time.

```python
server_time = client.time()
```

### Market Information

#### exchange_info()
Get current exchange trading rules and symbol information.

```python
info = client.exchange_info()
```

#### depth(symbol, **kwargs)
Get order book depth.

```python
depth = client.depth('BTCUSDT', limit=100)
```

#### trades(symbol, **kwargs)
Get recent market trades.

```python
trades = client.trades('BTCUSDT', limit=50)
```

#### historical_trades(symbol, **kwargs)
Get older market historical trades (requires API key).

```python
historical = client.historical_trades('BTCUSDT', limit=100)
```

#### agg_trades(symbol, **kwargs)
Get compressed/aggregate market trades.

```python
agg_trades = client.agg_trades('BTCUSDT', limit=100)
```

### Kline/Candlestick Data

#### klines(symbol, interval, **kwargs)
Get kline/candlestick data.

```python
klines = client.klines(
    'BTCUSDT',
    '1h',  # interval options: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, etc.
    limit=100,
    startTime=1609459200000,
    endTime=1609545600000
)
```

#### index_price_klines(pair, interval, **kwargs)
Get index price kline data.

```python
index_klines = client.index_price_klines('BTCUSD', '1h')
```

#### mark_price_klines(symbol, interval, **kwargs)
Get mark price kline data.

```python
mark_klines = client.mark_price_klines('BTCUSDT', '1h')
```

### Price and Ticker Data

#### mark_price(symbol=None)
Get mark price and funding rate for a symbol or all symbols.

```python
# For specific symbol
mark = client.mark_price('BTCUSDT')

# For all symbols
mark = client.mark_price()
```

#### funding_rate(symbol=None, **kwargs)
Get funding rate history.

```python
funding_rate = client.funding_rate('BTCUSDT', limit=100)
```

#### ticker_24hr_price_change(symbol=None)
Get 24hr ticker price change statistics.

```python
# For specific symbol
stats = client.ticker_24hr_price_change('BTCUSDT')

# For all symbols
stats = client.ticker_24hr_price_change()
```

#### ticker_price(symbol=None)
Get latest price for a symbol or all symbols.

```python
# For specific symbol
price = client.ticker_price('BTCUSDT')

# For all symbols
prices = client.ticker_price()
```

#### book_ticker(symbol=None)
Get best price/qty on the order book for a symbol or all symbols.

```python
# For specific symbol
book = client.book_ticker('BTCUSDT')

# For all symbols
books = client.book_ticker()
```

## Account & Trading Endpoints

**Note**: These endpoints require API authentication.

### Account Information

#### account(**kwargs)
Get current account information.

```python
account_info = client.account()
```

#### balance(**kwargs)
Get futures account balance.

```python
balances = client.balance()
```

#### get_position_risk(**kwargs)
Get current position information.

```python
positions = client.get_position_risk()
```

### Position Management

#### get_position_mode(**kwargs)
Get current position mode (Hedge Mode or One-way Mode).

```python
mode = client.get_position_mode()
```

#### change_position_mode(dualSidePosition, **kwargs)
Change user's position mode on every symbol.

```python
# Enable Hedge Mode: "true", Disable Hedge Mode: "false"
result = client.change_position_mode("true")
```

#### get_multi_asset_mode(**kwargs)
Get current multi-assets mode.

```python
multi_asset_mode = client.get_multi_asset_mode()
```

#### change_multi_asset_mode(multiAssetsMargin, **kwargs)
Change user's multi-assets mode.

```python
# Enable Multi-Assets Mode: "true", Disable: "false"
result = client.change_multi_asset_mode("true")
```

### Order Management

#### new_order(symbol, side, type, **kwargs)
Place a new order.

```python
order = client.new_order(
    symbol='BTCUSDT',
    side='BUY',
    type='LIMIT',
    quantity=0.001,
    price=50000,
    timeInForce='GTC'
)
```

#### new_batch_order(batchOrders)
Place multiple orders.

```python
batch_orders = [
    {
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'type': 'LIMIT',
        'quantity': 0.001,
        'price': 50000,
        'timeInForce': 'GTC'
    }
]
result = client.new_batch_order(batchOrders=batch_orders)
```

#### query_order(symbol, orderId=None, origClientOrderId=None, **kwargs)
Query order status.

```python
order = client.query_order('BTCUSDT', orderId=123456)
# or
order = client.query_order('BTCUSDT', origClientOrderId='myId123')
```

#### cancel_order(symbol, orderId=None, origClientOrderId=None, **kwargs)
Cancel an order.

```python
result = client.cancel_order('BTCUSDT', orderId=123456)
```

#### cancel_open_orders(symbol, **kwargs)
Cancel all open orders for a symbol.

```python
result = client.cancel_open_orders('BTCUSDT')
```

#### get_open_orders(symbol, **kwargs)
Query current open orders.

```python
orders = client.get_open_orders('BTCUSDT')
```

#### get_orders(symbol, **kwargs)
Get all current open orders (across all symbols if symbol not specified).

```python
orders = client.get_orders()  # All open orders
# or
orders = client.get_orders(symbol='BTCUSDT')
```

#### get_all_orders(symbol, **kwargs)
Get all account orders (active, canceled, or filled).

```python
orders = client.get_all_orders('BTCUSDT', limit=500)
```

### Trade Management

#### get_account_trades(symbol, **kwargs)
Get account trade list.

```python
trades = client.get_account_trades('BTCUSDT', limit=100)
```

#### get_income_history(**kwargs)
Get income history.

```python
income = client.get_income_history(
    symbol='BTCUSDT',
    incomeType='REALIZED_PNL',
    startTime=1609459200000,
    endTime=1609545600000,
    limit=100
)
```

### Risk Management

#### change_leverage(symbol, leverage, **kwargs)
Change initial leverage.

```python
result = client.change_leverage('BTCUSDT', leverage=10)
```

#### change_margin_type(symbol, marginType, **kwargs)
Change margin type (ISOLATED or CROSSED).

```python
result = client.change_margin_type('BTCUSDT', 'ISOLATED')
```

#### modify_isolated_position_margin(symbol, amount, type, **kwargs)
Modify isolated position margin.

```python
# Add margin: type=1, Reduce margin: type=2
result = client.modify_isolated_position_margin('BTCUSDT', 100, 1)
```

#### get_position_margin_history(symbol, **kwargs)
Get position margin change history.

```python
history = client.get_position_margin_history('BTCUSDT')
```

## User Data Streams

### Create Listen Key

#### new_listen_key()
Create a user data stream listen key.

```python
listen_key_data = client.new_listen_key()
listen_key = listen_key_data['listenKey']
```

### Keep Alive Listen Key

#### renew_listen_key(listenKey)
Ping/keep-alive a listen key.

```python
client.renew_listen_key(listen_key)
```

### Close Listen Key

#### close_listen_key(listenKey)
Close a listen key.

```python
client.close_listen_key(listen_key)
```

## WebSocket Client

The WebSocket client provides real-time market data feeds.

### Initialization

```python
from aster.websocket.client.stream import WebsocketClient as Client

ws_client = Client(stream_url="wss://fstream.asterdex.com")
ws_client.start()
```

### WebSocket Endpoints

#### agg_trade(symbol, id, callback, **kwargs)
Subscribe to aggregate trade stream.

```python
def agg_trade_handler(message):
    print(f"Aggregate trade: {message}")

ws_client.agg_trade('BTCUSDT', id=1, callback=agg_trade_handler)
```

#### mark_price(symbol, id, callback, speed=None, **kwargs)
Subscribe to mark price stream (pushed every 3 seconds or 1 second).

```python
def mark_price_handler(message):
    print(f"Mark price: {message}")

# Every 3 seconds
ws_client.mark_price('BTCUSDT', id=1, callback=mark_price_handler)

# Every 1 second
ws_client.mark_price('BTCUSDT', id=1, callback=mark_price_handler, speed=1)
```

#### kline(symbol, id, interval, callback, **kwargs)
Subscribe to kline/candlestick stream.

```python
def kline_handler(message):
    print(f"Kline data: {message}")

ws_client.kline('BTCUSDT', id=1, interval='1m', callback=kline_handler)
```

#### mini_ticker(id, callback, symbol=None, **kwargs)
Subscribe to mini ticker stream for individual symbol or all market.

```python
def mini_ticker_handler(message):
    print(f"Mini ticker: {message}")

# For all market
ws_client.mini_ticker(id=1, callback=mini_ticker_handler)

# For specific symbol
ws_client.mini_ticker(id=1, callback=mini_ticker_handler, symbol='BTCUSDT')
```

#### ticker(id, callback, symbol=None, **kwargs)
Subscribe to 24hr ticker stream for individual symbol or all market.

```python
def ticker_handler(message):
    print(f"Ticker: {message}")

# For all market
ws_client.ticker(id=1, callback=ticker_handler)

# For specific symbol
ws_client.ticker(id=1, callback=ticker_handler, symbol='BTCUSDT')
```

#### book_ticker(id, callback, symbol=None, **kwargs)
Subscribe to book ticker stream for individual symbol or all market.

```python
def book_ticker_handler(message):
    print(f"Book ticker: {message}")

# For all market
ws_client.book_ticker(id=1, callback=book_ticker_handler)

# For specific symbol
ws_client.book_ticker(id=1, callback=book_ticker_handler, symbol='BTCUSDT')
```

#### liquidation_order(id, callback, symbol=None, **kwargs)
Subscribe to liquidation order stream for specific symbol or all market.

```python
def liquidation_handler(message):
    print(f"Liquidation: {message}")

# For all market
ws_client.liquidation_order(id=1, callback=liquidation_handler)

# For specific symbol
ws_client.liquidation_order(id=1, callback=liquidation_handler, symbol='BTCUSDT')
```

#### partial_book_depth(symbol, id, level, speed, callback, **kwargs)
Subscribe to partial book depth stream.

```python
def depth_handler(message):
    print(f"Partial depth: {message}")

# level: 5, 10, or 20
# speed: 100, 250, or 500 (milliseconds)
ws_client.partial_book_depth('BTCUSDT', id=1, level=20, speed=100, callback=depth_handler)
```

#### diff_book_depth(symbol, id, speed, callback, **kwargs)
Subscribe to diff. book depth stream.

```python
def diff_depth_handler(message):
    print(f"Diff depth: {message}")

# speed: 100, 250, or 500 (milliseconds)
ws_client.diff_book_depth('BTCUSDT', id=1, speed=250, callback=diff_depth_handler)
```

#### user_data(listen_key, id, callback, **kwargs)
Subscribe to user data stream using a listen key.

```python
def user_data_handler(message):
    print(f"User data: {message}")

ws_client.user_data(listen_key, id=1, callback=user_data_handler)
```

### Managing WebSocket Connections

```python
# Start the connection
ws_client.start()

# Stop the connection
ws_client.stop()

# Subscribe to multiple streams at once
ws_client.instant_subscribe(
    stream=['bnbusdt@bookTicker', 'ethusdt@bookTicker'],
    callback=message_handler,
)
```

## Error Handling

The library provides custom exception classes for error handling:

### ClientError
Thrown when the server returns a 4xx status code (client-side error).

Properties:
- `status_code`: HTTP status code
- `error_code`: Server's error code (e.g., -1102)
- `error_message`: Server's error message (e.g., "Unknown order sent.")
- `header`: Full response header

```python
from aster.error import ClientError

try:
    result = client.new_order(symbol='BTCUSDT', side='BUY', type='LIMIT', quantity=0.001, price=50000)
except ClientError as e:
    print(f"Client error: {e.error_code} - {e.error_message}")
```

### ServerError
Thrown when the server returns a 5xx status code (server-side error).

Properties:
- `status_code`: HTTP status code
- `message`: Error message

```python
from aster.error import ServerError

try:
    result = client.time()
except ServerError as e:
    print(f"Server error: {e.status_code} - {e.message}")
```

### Parameter Errors
Various parameter validation errors may also be raised:
- `ParameterRequiredError`: Required parameter is missing
- `ParameterValueError`: Invalid enum value
- `ParameterTypeError`: Incorrect data type

## Configuration Options

### Response Metadata
Display rate limit usage or full response headers:

```python
# Show rate limit usage
client = Client(show_limit_usage=True)

# Show full response headers
client = Client(show_header=True)
```

### Request Timeout
Set request timeout in seconds:

```python
client = Client(timeout=10)  # 10 seconds timeout
```

### Proxy Configuration
Use proxy for API requests:

```python
proxies = {'https': 'http://1.2.3.4:8080'}
client = Client(proxies=proxies)
```

### RecvWindow Parameter
For authenticated endpoints, set the recvWindow parameter:

```python
# Must be ≤ 60000ms (60 seconds)
order = client.new_order(
    symbol='BTCUSDT',
    side='BUY',
    type='LIMIT',
    quantity=0.001,
    price=50000,
    recvWindow=10000  # 10 seconds window
)
```

### Logging
Enable debug logging to see request details:

```python
import logging

# Set log level to DEBUG to see requests
logging.basicConfig(level=logging.DEBUG)
```

## Additional Notes

1. **Base URL**: The default base URL is `https://fapi.asterdex.com`. This can be changed during initialization.

2. **Parameter Naming**: Use exact parameter names as specified in the official API documentation, even if they don't follow Python naming conventions.

3. **WebSocket Heartbeat**: The library handles WebSocket ping/pong automatically. The server sends ping frames every 3 minutes and requires a response within 10 minutes.

4. **Rate Limits**: Check the response headers for rate limit information, especially when `show_limit_usage=True` is set.

5. **Listen Key Expiration**: Listen keys expire after 60 minutes without a keep-alive request. Use `renew_listen_key` to extend the expiration.

## Examples

For complete working examples, please check the `examples/` directory in the repository:
- REST API examples in `examples/rest_api/`
- WebSocket examples in `examples/websocket/`