"""
Integration tests for Technical Analysis Service.

Tests integration with other services and components.
"""

from datetime import datetime, timezone

import pytest

from app.models.market_data import MarketData
from app.services import get_technical_analysis_service


@pytest.fixture
def market_data_candles():
    """Create realistic market data candles."""
    candles = []
    base_price = 45000.0
    for i in range(100):
        # Create realistic OHLC data
        open_price = base_price + i
        close_price = base_price + i + 50
        high_price = max(open_price, close_price) + 100
        low_price = min(open_price, close_price) - 50

        candles.append(
            MarketData(
                time=datetime.now(timezone.utc),
                symbol="BTCUSDT",
                interval="1h",
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1000.0 + i * 10,
            )
        )
    return candles


class TestTechnicalAnalysisIntegration:
    """Integration tests for Technical Analysis Service."""

    def test_service_singleton_across_imports(self):
        """Test that singleton service is consistent across imports."""
        service1 = get_technical_analysis_service()
        service2 = get_technical_analysis_service()
        assert service1 is service2

    def test_calculate_indicators_with_realistic_data(self, market_data_candles):
        """Test indicator calculation with realistic market data."""
        service = get_technical_analysis_service()
        result = service.calculate_all_indicators(market_data_candles)

        # Verify all indicators are calculated
        assert isinstance(result.ema.ema, list)
        assert isinstance(result.macd.macd, list)
        assert isinstance(result.rsi.rsi, list)
        assert isinstance(result.bollinger_bands.upper, list)
        assert isinstance(result.atr.atr, list)

        # Verify metadata
        assert result.candle_count == 100
        assert result.series_length == 10
        assert result.timestamp is not None

    def test_multiple_calculations_with_different_data(self):
        """Test multiple calculations with different data sets."""
        service = get_technical_analysis_service()

        # First calculation - uptrend
        candles1 = []
        for i in range(100):
            candles1.append(
                MarketData(
                    time=datetime.now(timezone.utc),
                    symbol="BTCUSDT",
                    interval="1h",
                    open=45000.0 + i * 10,
                    high=45100.0 + i * 10,
                    low=44900.0 + i * 10,
                    close=45050.0 + i * 10,
                    volume=1000.0 + i,
                )
            )

        result1 = service.calculate_all_indicators(candles1)

        # Second calculation - downtrend
        candles2 = []
        for i in range(100):
            candles2.append(
                MarketData(
                    time=datetime.now(timezone.utc),
                    symbol="ETHUSDT",
                    interval="1h",
                    open=2500.0 - i * 5,
                    high=2600.0 - i * 5,
                    low=2400.0 - i * 5,
                    close=2550.0 - i * 5,
                    volume=5000.0 + i,
                )
            )

        result2 = service.calculate_all_indicators(candles2)

        # Results should be different
        assert result1.ema.ema[-1] != result2.ema.ema[-1]
        # RSI should be different (uptrend vs downtrend)
        if result1.rsi.rsi[-1] is not None and result2.rsi.rsi[-1] is not None:
            assert result1.rsi.rsi[-1] > result2.rsi.rsi[-1]

    def test_service_handles_edge_case_prices(self):
        """Test service with edge case price values."""
        service = get_technical_analysis_service()

        # Create candles with very small price differences
        candles = []
        base_price = 0.0001
        for i in range(100):
            candles.append(
                MarketData(
                    time=datetime.now(timezone.utc),
                    symbol="SHIBUSDT",
                    interval="1h",
                    open=base_price + i * 0.00001,
                    high=base_price + i * 0.00001 + 0.000001,
                    low=base_price + i * 0.00001 - 0.000001,
                    close=base_price + i * 0.00001 + 0.0000005,
                    volume=1000000.0 + i * 1000,
                )
            )

        result = service.calculate_all_indicators(candles)
        assert isinstance(result.ema.ema, list)
        assert isinstance(result.rsi.rsi, list)

    def test_service_with_volatile_market_data(self):
        """Test service with highly volatile market data."""
        service = get_technical_analysis_service()

        # Create candles with high volatility
        candles = []
        base_price = 45000.0
        for i in range(100):
            # Simulate high volatility
            volatility = 500 * (i % 3)
            candles.append(
                MarketData(
                    time=datetime.now(timezone.utc),
                    symbol="BTCUSDT",
                    interval="1h",
                    open=base_price + volatility,
                    high=base_price + volatility + 1000,
                    low=base_price + volatility - 1000,
                    close=base_price + volatility + 500,
                    volume=1000.0 + i,
                )
            )

        result = service.calculate_all_indicators(candles)

        # Verify ATR is higher due to volatility
        assert isinstance(result.atr.atr, list)
        if result.atr.atr[-1] is not None:
            assert result.atr.atr[-1] > 100  # Should be significant

    def test_service_with_trending_market(self):
        """Test service with strong uptrend."""
        service = get_technical_analysis_service()

        # Create candles with strong uptrend
        candles = []
        base_price = 45000.0
        for i in range(100):
            trend = i * 100  # Strong uptrend
            candles.append(
                MarketData(
                    time=datetime.now(timezone.utc),
                    symbol="BTCUSDT",
                    interval="1h",
                    open=base_price + trend,
                    high=base_price + trend + 100,
                    low=base_price + trend - 50,
                    close=base_price + trend + 75,
                    volume=1000.0 + i,
                )
            )

        result = service.calculate_all_indicators(candles)

        # In uptrend, RSI should be elevated
        if result.rsi.rsi[-1] is not None:
            assert result.rsi.rsi[-1] > 50

    def test_service_with_downtrend_market(self):
        """Test service with strong downtrend."""
        service = get_technical_analysis_service()

        # Create candles with strong downtrend
        candles = []
        base_price = 50000.0
        for i in range(100):
            trend = i * 100  # Strong downtrend
            candles.append(
                MarketData(
                    time=datetime.now(timezone.utc),
                    symbol="BTCUSDT",
                    interval="1h",
                    open=base_price - trend,
                    high=base_price - trend + 50,
                    low=base_price - trend - 100,
                    close=base_price - trend - 75,
                    volume=1000.0 + i,
                )
            )

        result = service.calculate_all_indicators(candles)

        # In downtrend, RSI should be depressed
        if result.rsi.rsi[-1] is not None:
            assert result.rsi.rsi[-1] < 50

    def test_service_output_serialization(self, market_data_candles):
        """Test that service output can be serialized to JSON."""
        service = get_technical_analysis_service()
        result = service.calculate_all_indicators(market_data_candles)

        # Should be able to convert to dict
        result_dict = result.model_dump()
        assert isinstance(result_dict, dict)
        assert "ema" in result_dict
        assert "macd" in result_dict
        assert "rsi" in result_dict
        assert "bollinger_bands" in result_dict
        assert "atr" in result_dict
        assert result_dict["series_length"] == 10

        # Should be able to convert to JSON
        result_json = result.model_dump_json()
        assert isinstance(result_json, str)
        assert "series_length" in result_json

    def test_service_performance_with_large_dataset(self):
        """Test service performance with large dataset."""
        service = get_technical_analysis_service()

        # Create 500 candles
        candles = []
        base_price = 45000.0
        for i in range(500):
            candles.append(
                MarketData(
                    time=datetime.now(timezone.utc),
                    symbol="BTCUSDT",
                    interval="1h",
                    open=base_price + i,
                    high=base_price + i + 100,
                    low=base_price + i - 50,
                    close=base_price + i + 50,
                    volume=1000.0 + i,
                )
            )

        # Should complete without error
        result = service.calculate_all_indicators(candles)
        assert result.candle_count == 500
        assert isinstance(result.ema.ema, list)
        assert len(result.ema.ema) == 10
