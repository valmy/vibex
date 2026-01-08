"""Aster DEX API client for market data fetching."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AsterClient:
    """Wrapper for Aster DEX REST API client."""

    def __init__(self, api_key: str, api_secret: str, base_url: str):
        """
        Initialize the Aster client.

        Args:
            api_key: API key for authentication
            api_secret: API secret for authentication
            base_url: Base URL for the Aster DEX API
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url

    @property
    def _client(self) -> Any:  # Assuming 'Client' is untyped, use Any for now
        """
        Create and return a new Aster REST API client on each access.

        This approach avoids issues with thread-safety and stale connections
        by ensuring each operation gets a fresh, isolated client instance.

        Returns:
            Client: A new Aster REST API client instance

        Raises:
            Exception: If client initialization fails
        """
        try:
            from aster.rest_api import Client

            # Create a new client instance for each call.
            client = Client(key=self.api_key, secret=self.api_secret, base_url=self.base_url)
            logger.debug("New Aster REST API client instance created.")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize Aster client: {e}", exc_info=True)
            raise

    async def fetch_klines(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch kline/candlestick data from Aster DEX.

        This method uses the _client property and fetches data within a separate
        thread to avoid blocking the async event loop with synchronous I/O.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Candle interval (e.g., "1m", "1h", "4h")
            limit: Number of candles to fetch

        Returns:
            List of candle data dictionaries

        Raises:
            Exception: If the API call fails
        """
        try:
            # The actual fetching is done in a separate thread to handle blocking I/O.
            def _fetch_in_thread() -> List[Dict[str, Any]]:
                try:
                    # Use the _client property to get a fresh client instance
                    client = self._client

                    # Call klines with positional arguments for symbol and interval
                    result = client.klines(symbol, interval, limit=limit)
                    return result

                except Exception as e:
                    logger.error(f"Error fetching market data in thread: {e}", exc_info=True)
                    raise

            # Run the blocking I/O in a thread pool
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, _fetch_in_thread)

            logger.debug(f"Successfully fetched {len(data)} candles for {symbol} ({interval})")
            return data
        except Exception as e:
            # This will catch errors from the thread and log them.
            logger.error(f"Error in fetch_klines task: {e}", exc_info=True)
            raise

    async def fetch_funding_rate(
        self,
        symbol: Optional[str] = None,
        startTime: Optional[int] = None,
        endTime: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch funding rate history from Aster DEX.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT"). If None, fetches for all symbols.
            startTime: Start time in milliseconds
            endTime: End time in milliseconds
            limit: Number of funding rate records to fetch (default 100, max 1000)

        Returns:
            List of funding rate data dictionaries

        Raises:
            Exception: If the API call fails
        """
        try:

            def _fetch_in_thread() -> List[Dict[str, Any]]:
                try:
                    client = self._client
                    # Build kwargs dynamically to handle None values
                    kwargs: Dict[str, Any] = {"limit": limit}
                    if symbol is not None:
                        kwargs["symbol"] = symbol
                    if startTime is not None:
                        kwargs["startTime"] = int(startTime)
                    if endTime is not None:
                        kwargs["endTime"] = int(endTime)

                    result = client.funding_rate(**kwargs)
                    return result
                except Exception as e:
                    logger.error(f"Error fetching funding rate in thread: {e}", exc_info=True)
                    raise

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, _fetch_in_thread)

            logger.debug(f"Successfully fetched {len(data)} funding rate records")
            return data
        except Exception as e:
            logger.error(f"Error in fetch_funding_rate task: {e}", exc_info=True)
            raise

    async def fetch_balance(self) -> float:
        """
        Fetch account balance from Aster DEX.

        Returns:
            Account balance in USD

        Raises:
            Exception: If the API call fails (401 for invalid credentials, 502 for other errors)
        """
        try:

            def _fetch_in_thread() -> float:
                try:
                    client = self._client
                    # Fetch account information which includes balance
                    result = client.account()
                    # Extract balance from the response
                    if isinstance(result, dict):
                        balance = (
                            result.get("totalWalletBalance")
                            or result.get("balance")
                            or result.get("availableBalance")
                            or result.get("totalMarginBalance")
                            or 0.0
                        )
                        return float(balance)
                    else:
                        logger.error(f"Unexpected account response format: {result}")
                        raise ValueError("Unexpected account response format")
                except Exception as e:
                    logger.error(f"Error fetching balance in thread: {e}", exc_info=True)
                    raise

            loop = asyncio.get_event_loop()
            balance = await loop.run_in_executor(None, _fetch_in_thread)

            logger.debug(f"Successfully fetched account balance: {balance}")
            return balance
        except Exception as e:
            logger.error(f"Error in fetch_balance task: {e}", exc_info=True)
            raise

    async def place_order(
        self,
        symbol: str,
        side: str,
        type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a new order on Aster DEX.

        Args:
            symbol: Trading pair symbol
            side: 'BUY' or 'SELL'
            type: 'MARKET', 'LIMIT', 'STOP_MARKET', 'TAKE_PROFIT', etc.
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            stop_price: Trigger price (required for STOP/TAKE_PROFIT orders)
            reduce_only: Whether the order is reduce-only

        Returns:
            Order response dictionary
        """
        try:
            def _place_in_thread() -> Dict[str, Any]:
                try:
                    client = self._client
                    kwargs: Dict[str, Any] = {
                        "symbol": symbol,
                        "side": side.upper(),
                        "type": type.upper(),
                        "quantity": quantity
                    }
                    if price is not None:
                        kwargs["price"] = price
                    if stop_price is not None:
                        kwargs["stopPrice"] = stop_price
                    if reduce_only:
                        kwargs["reduceOnly"] = "true"

                    if hasattr(client, "new_order"):
                        return client.new_order(**kwargs)
                    elif hasattr(client, "order"):
                        return client.order(**kwargs)
                    else:
                        return client.new_order(**kwargs)
                        
                except Exception as e:
                    logger.error(f"Error placing order in thread: {e}", exc_info=True)
                    raise

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, _place_in_thread)
            
            logger.info(f"Order placed successfully: {symbol} {side} {quantity}")
            return response
            
        except Exception as e:
            logger.error(f"Error in place_order task: {e}", exc_info=True)
            raise

    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch open positions from Aster DEX.

        Returns:
            List of position dictionaries
        """
        try:
            def _fetch_in_thread() -> List[Dict[str, Any]]:
                try:
                    client = self._client
                    # library method is likely client.account_position() or similar
                    if hasattr(client, "account_position"):
                        return client.account_position()
                    elif hasattr(client, "positions"):
                        return client.positions()
                    else:
                        # Default guess for Hyperliquid/Aster fork
                        return client.account_position()
                except Exception as e:
                    logger.error(f"Error fetching positions in thread: {e}", exc_info=True)
                    raise

            loop = asyncio.get_event_loop()
            positions = await loop.run_in_executor(None, _fetch_in_thread)
            return positions
        except Exception as e:
            logger.error(f"Error in fetch_positions task: {e}", exc_info=True)
            raise