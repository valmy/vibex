from datetime import datetime, timezone
from src.app.models.market_data import MarketData
from src.app.schemas.market_data import MarketDataRead

def test_market_data_schema_mapping():
    """Test that MarketData model correctly maps to MarketDataRead schema."""
    now = datetime(2023, 10, 27, 10, 0, 0, tzinfo=timezone.utc)

    md = MarketData(
        time=now,
        id=1,
        symbol="BTCUSDT",
        interval="1h",
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=1000.0
    )

    schema = MarketDataRead.model_validate(md)

    assert schema.time == now
    assert schema.symbol == "BTCUSDT"
    assert schema.open_price == 100.0

    # Check serialization
    json_output = schema.model_dump_json()
    # Pydantic v2 might serialize UTC as 'Z'
    assert "2023-10-27T10:00:00Z" in json_output or "2023-10-27T10:00:00+00:00" in json_output
    assert "time" in json_output
    # Check that timestamp is NOT in json output (it was renamed)
    assert "\"timestamp\"" not in json_output
