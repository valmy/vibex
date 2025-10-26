"""
LLM Service for market analysis and trading insights.

Integrates with OpenRouter API for LLM-powered analysis.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.config import config
from ..core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Service for LLM-powered market analysis."""

    def __init__(self):
        """Initialize the LLM Service."""
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL
        self.model = config.LLM_MODEL
        self.referer = config.OPENROUTER_REFERER
        self.app_title = config.OPENROUTER_APP_TITLE

        # Initialize OpenRouter client (lazy loaded)
        self._client = None

    @property
    def client(self):
        """Lazy load OpenRouter client."""
        if self._client is None:
            try:
                import openai

                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    default_headers={
                        "HTTP-Referer": self.referer,
                        "X-Title": self.app_title,
                    },
                )
                logger.info(f"OpenRouter client initialized with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter client: {e}")
                raise
        return self._client

    async def analyze_market(
        self, symbol: str, market_data: Dict[str, Any], additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze market data and provide trading insights.

        Args:
            symbol: Trading pair symbol
            market_data: Market data dictionary with OHLCV data
            additional_context: Additional context for analysis

        Returns:
            Analysis result with insights and recommendations
        """
        try:
            prompt = self._build_analysis_prompt(symbol, market_data, additional_context)

            logger.info(f"Analyzing market for {symbol}")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert cryptocurrency trading analyst. Provide concise, actionable market analysis.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            analysis_text = response.choices[0].message.content

            # Parse the response
            result = {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "analysis": analysis_text,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }

            logger.info(f"Market analysis completed for {symbol}")
            return result
        except Exception as e:
            logger.error(f"Error analyzing market for {symbol}: {e}")
            raise

    async def get_trading_signal(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        account_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get trading signal based on market analysis.

        Args:
            symbol: Trading pair symbol
            market_data: Market data dictionary
            account_info: Optional account information

        Returns:
            Trading signal with recommendation
        """
        try:
            prompt = self._build_signal_prompt(symbol, market_data, account_info)

            logger.info(f"Generating trading signal for {symbol}")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional trading advisor. Provide trading signals in JSON format with: signal (BUY/SELL/HOLD), confidence (0-100), reason.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=300,
            )

            signal_text = response.choices[0].message.content

            # Try to parse JSON response
            try:
                signal_data = json.loads(signal_text)
            except json.JSONDecodeError:
                # If not JSON, extract signal from text
                signal_data = {"signal": "HOLD", "confidence": 50, "reason": signal_text}

            result = {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "signal": signal_data.get("signal", "HOLD"),
                "confidence": signal_data.get("confidence", 50),
                "reason": signal_data.get("reason", ""),
                "model": self.model,
            }

            logger.info(f"Trading signal generated for {symbol}: {result['signal']}")
            return result
        except Exception as e:
            logger.error(f"Error generating trading signal for {symbol}: {e}")
            raise

    async def summarize_market_conditions(
        self, market_data_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Summarize overall market conditions.

        Args:
            market_data_list: List of market data for multiple symbols

        Returns:
            Market summary
        """
        try:
            prompt = self._build_summary_prompt(market_data_list)

            logger.info("Generating market summary")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a market analyst. Provide a concise summary of market conditions.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=400,
            )

            summary_text = response.choices[0].message.content

            result = {
                "timestamp": datetime.utcnow().isoformat(),
                "summary": summary_text,
                "symbols_analyzed": len(market_data_list),
                "model": self.model,
            }

            logger.info("Market summary generated")
            return result
        except Exception as e:
            logger.error(f"Error generating market summary: {e}")
            raise

    def _build_analysis_prompt(
        self, symbol: str, market_data: Dict[str, Any], additional_context: Optional[str] = None
    ) -> str:
        """Build market analysis prompt."""
        prompt = f"""
Analyze the following market data for {symbol}:

Current Price: ${market_data.get('close', 0):.2f}
24h High: ${market_data.get('high', 0):.2f}
24h Low: ${market_data.get('low', 0):.2f}
Volume: {market_data.get('volume', 0):.2f}
Open: ${market_data.get('open', 0):.2f}

{f"Additional Context: {additional_context}" if additional_context else ""}

Provide:
1. Current trend analysis
2. Key support/resistance levels
3. Volume analysis
4. Potential price targets
5. Risk assessment
"""
        return prompt.strip()

    def _build_signal_prompt(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        account_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build trading signal prompt."""
        prompt = f"""
Generate a trading signal for {symbol} based on:

Price: ${market_data.get('close', 0):.2f}
24h Change: {market_data.get('change_percent', 0):.2f}%
Volume: {market_data.get('volume', 0):.2f}
RSI: {market_data.get('rsi', 50):.2f}
MACD: {market_data.get('macd', 0):.4f}

{f"Account Balance: ${account_info.get('balance', 0):.2f}" if account_info else ""}

Respond in JSON format:
{{"signal": "BUY|SELL|HOLD", "confidence": 0-100, "reason": "brief reason"}}
"""
        return prompt.strip()

    def _build_summary_prompt(self, market_data_list: List[Dict[str, Any]]) -> str:
        """Build market summary prompt."""
        symbols_summary = "\n".join(
            [
                f"- {data.get('symbol', 'N/A')}: ${data.get('close', 0):.2f} ({data.get('change_percent', 0):.2f}%)"
                for data in market_data_list
            ]
        )

        prompt = f"""
Summarize the current market conditions for these assets:

{symbols_summary}

Provide:
1. Overall market sentiment
2. Key trends
3. Risk factors
4. Opportunities
"""
        return prompt.strip()


# Global service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
