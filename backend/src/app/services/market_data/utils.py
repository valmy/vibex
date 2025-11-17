"""Utility functions for time and interval calculations."""

from datetime import datetime, timezone


def get_interval_seconds(interval: str) -> int:
    """
    Convert interval string to seconds.

    Args:
        interval: Candle interval (e.g., '1m', '5m', '1h', '4h', '1d')

    Returns:
        int: Interval duration in seconds

    Raises:
        ValueError: If the interval format is invalid
    """
    if not interval:
        raise ValueError("Interval cannot be empty")

    if interval.endswith("m"):
        return int(interval[:-1]) * 60
    elif interval.endswith("h"):
        return int(interval[:-1]) * 3600
    elif interval.endswith("d"):
        return int(interval[:-1]) * 86400
    else:
        raise ValueError(f"Invalid interval format: {interval}")


def calculate_next_candle_close(interval: str, current_time: datetime) -> datetime:
    """
    Calculate the next candle close time for a given interval.

    Args:
        interval: Candle interval (e.g., '1h', '4h')
        current_time: Current UTC time

    Returns:
        datetime: Next candle close time in UTC
    """
    interval_seconds = get_interval_seconds(interval)
    current_timestamp = int(current_time.timestamp())

    # Calculate the next close time
    next_close_timestamp = (
        current_timestamp - (current_timestamp % interval_seconds) + interval_seconds
    )
    return datetime.fromtimestamp(next_close_timestamp, timezone.utc)


def calculate_previous_candle_close(interval: str, current_time: datetime) -> datetime:
    """
    Calculate the most recent candle close time for a given interval.

    Args:
        interval: Candle interval (e.g., '1h', '4h')
        current_time: Current UTC time

    Returns:
        datetime: Previous candle close time in UTC
    """
    interval_seconds = get_interval_seconds(interval)
    current_timestamp = int(current_time.timestamp())

    # Calculate the previous close time
    prev_close_timestamp = current_timestamp - (current_timestamp % interval_seconds)
    return datetime.fromtimestamp(prev_close_timestamp, timezone.utc)


def format_symbol(asset: str, quote_currency: str = "USDT") -> str:
    """
    Format asset to trading pair symbol.

    Args:
        asset: Base asset (e.g., 'BTC', 'ETH')
        quote_currency: Quote currency (default: 'USDT')

    Returns:
        str: Formatted symbol (e.g., 'BTCUSDT')

    Examples:
        >>> format_symbol('BTC')
        'BTCUSDT'
        >>> format_symbol('BTCUSDT')
        'BTCUSDT'
        >>> format_symbol('ETH', 'USDC')
        'ETHUSDC'
    """
    return f"{asset}{quote_currency}" if quote_currency not in asset.upper() else asset


def validate_interval(interval: str) -> bool:
    """
    Validate if interval is supported.

    Args:
        interval: Interval string to validate

    Returns:
        bool: True if interval is valid, False otherwise
    """
    return interval in ["1m", "3m", "5m", "1h", "4h", "1d"]
