"""
API routes for market analysis powered by LLM.

Provides endpoints for market analysis, trading signals, and market summaries.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import config
from ...core.logging import get_logger
from ...db.session import get_db
from ...services import get_llm_service, get_market_data_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.post("/market/{symbol}")
async def analyze_market(
    symbol: str,
    context: Optional[str] = Query(None, description="Additional context for analysis"),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze market data for a symbol using LLM.

    Args:
        symbol: Trading pair symbol (e.g., BTCUSDT)
        context: Optional additional context for analysis

    Returns:
        Market analysis with insights and recommendations
    """
    try:
        llm_service = get_llm_service()
        market_service = get_market_data_service()

        logger.info(f"Analyzing market for {symbol}")

        # Get latest market data
        latest_data = await market_service.get_latest_market_data(
            db, symbol, interval="1h", limit=1
        )

        if not latest_data:
            raise HTTPException(status_code=404, detail=f"No market data found for {symbol}")

        # Convert to dictionary for LLM
        market_data = {
            "symbol": latest_data[0].symbol,
            "close": latest_data[0].close,
            "high": latest_data[0].high,
            "low": latest_data[0].low,
            "open": latest_data[0].open,
            "volume": latest_data[0].volume,
            "time": latest_data[0].time.isoformat(),
        }

        # Get analysis from LLM
        analysis = await llm_service.analyze_market(symbol, market_data, context)

        return {"status": "success", "data": analysis}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing market for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze market: {str(e)}")


@router.post("/signal/{symbol}")
async def get_trading_signal(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Get trading signal for a symbol using LLM analysis.

    Args:
        symbol: Trading pair symbol

    Returns:
        Trading signal with recommendation and confidence
    """
    try:
        llm_service = get_llm_service()
        market_service = get_market_data_service()

        logger.info(f"Generating trading signal for {symbol}")

        # Get latest market data
        latest_data = await market_service.get_latest_market_data(
            db, symbol, interval="1h", limit=1
        )

        if not latest_data:
            raise HTTPException(status_code=404, detail=f"No market data found for {symbol}")

        # Convert to dictionary for LLM
        market_data = {
            "symbol": latest_data[0].symbol,
            "close": latest_data[0].close,
            "high": latest_data[0].high,
            "low": latest_data[0].low,
            "open": latest_data[0].open,
            "volume": latest_data[0].volume,
            "change_percent": (
                (latest_data[0].close - latest_data[0].open) / latest_data[0].open * 100
            ),
            "rsi": 50,  # Placeholder - would calculate from data
            "macd": 0,  # Placeholder - would calculate from data
        }

        # Get signal from LLM
        signal = await llm_service.get_trading_signal(symbol, market_data)

        return {"status": "success", "data": signal}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating trading signal for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate trading signal: {str(e)}")


@router.post("/summary")
async def get_market_summary(db: AsyncSession = Depends(get_db)):
    """
    Get overall market summary for all configured assets.

    Returns:
        Market summary with sentiment and opportunities
    """
    try:
        llm_service = get_llm_service()
        market_service = get_market_data_service()

        logger.info("Generating market summary")

        # Get latest data for all assets
        assets = [asset.strip() for asset in config.ASSETS.split(",")]
        market_data_list = []

        for symbol in assets:
            try:
                latest_data = await market_service.get_latest_market_data(
                    db, symbol, interval="1h", limit=1
                )

                if latest_data:
                    data = latest_data[0]
                    market_data_list.append(
                        {
                            "symbol": data.symbol,
                            "close": data.close,
                            "high": data.high,
                            "low": data.low,
                            "open": data.open,
                            "volume": data.volume,
                            "change_percent": ((data.close - data.open) / data.open * 100),
                        }
                    )
            except Exception as e:
                logger.warning(f"Could not get data for {symbol}: {e}")

        if not market_data_list:
            raise HTTPException(status_code=404, detail="No market data available for summary")

        # Get summary from LLM
        summary = await llm_service.summarize_market_conditions(market_data_list)

        return {"status": "success", "data": summary}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating market summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate market summary: {str(e)}")


@router.get("/health")
async def analysis_health():
    """Check health of analysis services."""
    try:
        llm_service = get_llm_service()
        market_service = get_market_data_service()

        return {
            "status": "healthy",
            "services": {"llm": "ready", "market_data": "ready"},
            "model": config.LLM_MODEL,
            "assets": config.ASSETS,
        }
    except Exception as e:
        logger.error(f"Analysis health check failed: {e}")
        raise HTTPException(status_code=503, detail="Analysis services unavailable")
