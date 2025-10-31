# End-to-End Tests

This directory contains end-to-end tests that validate the complete LLM Decision Engine workflow with real data and technical analysis.

## Test Categories

### `test_llm_decision_engine_e2e.py`
- **Complete Decision Workflow**: Tests the full decision generation pipeline with real market data
- **Technical Analysis Integration**: Validates technical indicator calculations with actual OHLCV data
- **Decision Consistency**: Tests decision consistency over multiple calls
- **Performance Metrics**: Validates decision engine performance tracking
- **Market Pattern Validation**: Tests decision quality with different market scenarios

### `test_decision_accuracy_regression.py`
- **Pattern Recognition**: Tests decision accuracy against known market patterns
- **Uptrend/Downtrend Analysis**: Validates decisions for strong directional moves
- **Consolidation Detection**: Tests decision quality during sideways markets
- **Breakout Recognition**: Validates decisions during breakout patterns
- **Cross-Pattern Consistency**: Ensures reasonable decisions across different market conditions

## Key Features

- **Real Market Data**: Uses 100 hours of realistic OHLCV data with trends, volatility, and noise
- **Technical Indicators**: Integrates with actual technical analysis service for RSI, EMA, MACD, Bollinger Bands, ATR
- **Decision Validation**: Tests complete decision pipeline from context building to final decision
- **Performance Testing**: Validates response times, success rates, and consistency
- **Pattern Testing**: Tests against known market patterns for regression validation

## Running E2E Tests

```bash
# Run all e2e tests
uv run pytest tests/e2e/ -v

# Run specific test file
uv run pytest tests/e2e/test_llm_decision_engine_e2e.py -v

# Run with detailed logging to see technical indicators and decision analysis
uv run pytest tests/e2e/ -v -s --log-cli-level=INFO

# Run specific test with full logging output
uv run pytest tests/e2e/test_llm_decision_engine_e2e.py::TestLLMDecisionEngineE2E::test_technical_analysis_with_real_data -v -s --log-cli-level=INFO

# Run pattern recognition tests with detailed analysis
uv run pytest tests/e2e/test_decision_accuracy_regression.py -v -s --log-cli-level=INFO
```

## Test Data

The tests create realistic market data patterns:
- **Uptrend**: Consistent price increases with volume confirmation
- **Downtrend**: Consistent price decreases with volume confirmation
- **Consolidation**: Tight price ranges with minimal movement
- **Breakout**: Consolidation followed by strong directional move
- **Volatile**: High volatility with large price swings

## Validation Criteria

- Decision structure validation (action, confidence, risk level, rationale)
- Technical indicator accuracy (values within expected ranges)
- Processing time validation (< 30 seconds)
- Consistency checks across multiple calls
- Pattern-appropriate decision validation