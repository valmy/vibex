"""
Technical Analysis Service module.

Provides technical indicator calculations for market data.
"""

import logging
from typing import Optional

from .schemas import TATechnicalIndicators
from .service import TechnicalAnalysisService

logger = logging.getLogger(__name__)

# Singleton instance
_ta_service: Optional[TechnicalAnalysisService] = None


def get_technical_analysis_service() -> TechnicalAnalysisService:
    """
    Get or create the singleton TechnicalAnalysisService instance.

    Returns:
        TechnicalAnalysisService: The singleton service instance

    Example:
        >>> ta_service = get_technical_analysis_service()
        >>> indicators = ta_service.calculate_all_indicators(candles)
    """
    global _ta_service
    if _ta_service is None:
        logger.info("Creating TechnicalAnalysisService singleton instance")
        _ta_service = TechnicalAnalysisService()
    return _ta_service


__all__ = [
    "TechnicalAnalysisService",
    "TATechnicalIndicators",
    "get_technical_analysis_service",
]
