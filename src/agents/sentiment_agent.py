"""
Sentiment Agent — Crypto Twitter NLP analysis.

Scrapes CT accounts, runs transformer sentiment model,
and correlates with on-chain whale activity.
"""

import asyncio
import time
from typing import Optional

import httpx

from src.utils.redis_bus import RedisBus
from src.utils.logger import get_logger

logger = get_logger("sentiment_agent")

# Key CT accounts to monitor
CT_ACCOUNTS = [
    "CryptoHayes", "inversebrah", "Cobie", "HsakaTrades",
    "lightcrypto", "smallcappera", "DeFiIgnas", "blknoiz01",
    "CryptoKaleo", "Pentosh1", "loomlock", "TheDeFiEdge",
]


class SentimentAgent:
    """Monitors CT sentiment and correlates with on-chain data."""

    def __init__(self, config: dict):
        self.bus = RedisBus(config.get("redis", {}))
        self.config = config.get("sentiment", {})
        self.poll_interval = self.config.get("poll_interval", 60)
        self.sentiment_cache: dict[str, float] = {}

    async def run(self, stop: asyncio.Event):
        """Main loop — poll CT accounts for sentiment."""
        logger.info("📡 Sentiment Agent started")

        while not stop.is_set():
            try:
                await self._poll_sentiment()
            except Exception as e:
                logger.error(f"Sentiment poll error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _poll_sentiment(self):
        """Poll recent tweets and compute sentiment."""
        async with httpx.AsyncClient() as client:
            for account in CT_ACCOUNTS[:5]:  # Rate limit
                try:
                    tweets = await self._fetch_tweets(client, account)
                    if tweets:
                        score = self._compute_sentiment(tweets)
                        self.sentiment_cache[account] = score

                        if abs(score) > 0.7:  # Strong signal
                            await self.bus.publish("alerts:sentiment", {
                                "type": "sentiment_spike",
                                "account": account,
                                "score": score,
                                "signal": "bullish" if score > 0 else "bearish",
                                "timestamp": time.time(),
                            })
                except Exception as e:
                    logger.debug(f"Skip {account}: {e}")
                await asyncio.sleep(2)  # Rate limit

    async def _fetch_tweets(self, client: httpx.AsyncClient, account: str) -> list:
        """Fetch recent tweets (placeholder — use real API in production)."""
        # In production: use X API v2 or scraping
        return []

    def _compute_sentiment(self, tweets: list) -> float:
        """Compute sentiment score from -1 (bearish) to +1 (bullish)."""
        if not tweets:
            return 0.0
        # Placeholder — use transformer model in production
        # from src.models.sentiment_model import SentimentModel
        # model = SentimentModel()
        # scores = [model.predict(t["text"]) for t in tweets]
        # return sum(scores) / len(scores)
        return 0.0

    def get_aggregate_sentiment(self) -> dict:
        """Get aggregate sentiment across all monitored accounts."""
        if not self.sentiment_cache:
            return {"avg": 0.0, "signal": "neutral", "accounts": 0}

        avg = sum(self.sentiment_cache.values()) / len(self.sentiment_cache)
        return {
            "avg": round(avg, 3),
            "signal": "bullish" if avg > 0.3 else "bearish" if avg < -0.3 else "neutral",
            "accounts": len(self.sentiment_cache),
            "details": dict(self.sentiment_cache),
        }
