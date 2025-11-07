"""
Unit tests for Technical Analysis Service.

Tests indicator calculations, validation, and error handling.
"""

from datetime import datetime, timezone

import pytest

from app.models.market_data import MarketData
from app.services.technical_analysis import TechnicalAnalysisService, get_technical_analysis_service
from app.services.technical_analysis.exceptions import InsufficientDataError, InvalidCandleDataError


@pytest.fixture
def ta_service():
    """Create a TechnicalAnalysisService instance."""
    return TechnicalAnalysisService()


@pytest.fixture
def valid_candles():
    """Create a list of valid candles for testing."""
    candles = []
    base_price = 45000.0
    for i in range(100):
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
    return candles


@pytest.fixture
def insufficient_candles():
    """Create a list with insufficient candles."""
    candles = []
    base_price = 45000.0
    for i in range(30):  # Less than 50 required
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
    return candles


class TestTechnicalAnalysisService:
    """Tests for TechnicalAnalysisService."""

    def test_service_initialization(self, ta_service):
        """Test service initializes correctly."""
        assert ta_service is not None
        assert ta_service.MIN_CANDLES == 50
        assert ta_service.SERIES_LENGTH == 10

    def test_singleton_factory(self):
        """Test singleton factory returns same instance."""
        service1 = get_technical_analysis_service()
        service2 = get_technical_analysis_service()
        assert service1 is service2

    def test_calculate_all_indicators_success(self, ta_service, valid_candles):
        """Test successful calculation of all indicators."""
        result = ta_service.calculate_all_indicators(valid_candles)

        assert result is not None
        assert result.series_length == 10

        assert isinstance(result.ema.ema, list)
        assert len(result.ema.ema) == 10
        assert result.ema.period == 12

        assert isinstance(result.macd.macd, list)
        assert isinstance(result.macd.signal, list)
        assert isinstance(result.macd.histogram, list)
        assert len(result.macd.macd) == 10

        assert isinstance(result.rsi.rsi, list)
        assert len(result.rsi.rsi) == 10
        assert result.rsi.period == 14

        assert isinstance(result.bollinger_bands.upper, list)
        assert isinstance(result.bollinger_bands.middle, list)
        assert isinstance(result.bollinger_bands.lower, list)
        assert len(result.bollinger_bands.upper) == 10
        assert result.bollinger_bands.period == 20

        assert isinstance(result.atr.atr, list)
        assert len(result.atr.atr) == 10
        assert result.atr.period == 14

        assert result.candle_count == 100
        assert result.timestamp is not None

    def test_insufficient_data_error(self, ta_service, insufficient_candles):
        """Test InsufficientDataError is raised with < 50 candles."""
        with pytest.raises(InsufficientDataError) as exc_info:
            ta_service.calculate_all_indicators(insufficient_candles)

        assert exc_info.value.provided == 30
        assert exc_info.value.required == 50

    def test_invalid_candle_missing_ohlc(self, ta_service, valid_candles):
        """Test InvalidCandleDataError when OHLC is missing."""
        # Set close to None
        valid_candles[10].close = None

        with pytest.raises(InvalidCandleDataError) as exc_info:
            ta_service.calculate_all_indicators(valid_candles)

        assert "Missing OHLC data" in str(exc_info.value)
        assert exc_info.value.candle_index == 10

    def test_invalid_candle_high_less_than_low(self, ta_service, valid_candles):
        """Test InvalidCandleDataError when high < low."""
        valid_candles[10].high = 100
        valid_candles[10].low = 200

        with pytest.raises(InvalidCandleDataError) as exc_info:
            ta_service.calculate_all_indicators(valid_candles)

        assert "High" in str(exc_info.value) and "Low" in str(exc_info.value)
        assert exc_info.value.candle_index == 10

    def test_invalid_candle_negative_price(self, ta_service, valid_candles):
        """Test InvalidCandleDataError when price is negative."""
        valid_candles[10].close = -100

        with pytest.raises(InvalidCandleDataError) as exc_info:
            ta_service.calculate_all_indicators(valid_candles)

        assert "Negative price" in str(exc_info.value)
        assert exc_info.value.candle_index == 10

    def test_invalid_candle_negative_volume(self, ta_service, valid_candles):
        """Test InvalidCandleDataError when volume is negative."""
        valid_candles[10].volume = -100

        with pytest.raises(InvalidCandleDataError) as exc_info:
            ta_service.calculate_all_indicators(valid_candles)

        assert "Negative volume" in str(exc_info.value)
        assert exc_info.value.candle_index == 10

    def test_validate_candles_with_exactly_50_candles(self, ta_service):
        """Test validation passes with exactly 50 candles."""
        candles = []
        base_price = 45000.0
        for i in range(50):
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

        # Should not raise
        result = ta_service.calculate_all_indicators(candles)
        assert result.candle_count == 50

    def test_rsi_value_range(self, ta_service, valid_candles):
        """Test RSI value is in valid range (0-100)."""
        result = ta_service.calculate_all_indicators(valid_candles)
        for rsi_value in result.rsi.rsi:
            if rsi_value is not None:
                assert 0 <= rsi_value <= 100

    def test_ema_value_reasonable(self, ta_service, valid_candles):
        """Test EMA value is reasonable (close to price range)."""
        result = ta_service.calculate_all_indicators(valid_candles)
        last_ema = result.ema.ema[-1]
        if last_ema is not None:
            # EMA should be within reasonable range of prices
            prices = [c.close for c in valid_candles]
            min_price = min(prices)
            max_price = max(prices)
            assert min_price <= last_ema <= max_price * 1.1

    def test_bollinger_bands_order(self, ta_service, valid_candles):
        """Test Bollinger Bands upper > middle > lower."""
        result = ta_service.calculate_all_indicators(valid_candles)
        bb = result.bollinger_bands
        for upper, middle, lower in zip(bb.upper, bb.middle, bb.lower):
            if all([upper, middle, lower]):
                assert upper >= middle >= lower

    def test_atr_positive(self, ta_service, valid_candles):
        """Test ATR is positive."""
        result = ta_service.calculate_all_indicators(valid_candles)
        for atr_value in result.atr.atr:
            if atr_value is not None:
                assert atr_value > 0

    def test_macd_histogram_calculation(self, ta_service, valid_candles):
        """Test MACD histogram = MACD - Signal."""
        result = ta_service.calculate_all_indicators(valid_candles)
        macd = result.macd
        for m, s, h in zip(macd.macd, macd.signal, macd.histogram):
            if all([m, s, h]):
                # Histogram should be approximately MACD - Signal
                expected_histogram = m - s
                assert abs(h - expected_histogram) < 0.01
