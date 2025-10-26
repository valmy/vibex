"""Aster DEX API client for market data fetching."""

import asyncio
import logging
from typing import Any, Dict, List

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
    def _client(self):
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
            def _fetch_in_thread():
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

