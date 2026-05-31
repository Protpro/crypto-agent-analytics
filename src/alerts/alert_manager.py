"""
Alert Manager — routes alerts to Telegram, Discord, and webhook endpoints.
"""

import asyncio
import json
import time
from typing import Optional

import httpx

from src.utils.logger import get_logger

logger = get_logger("alerts")


class AlertManager:
    """Routes alerts to multiple notification channels."""

    def __init__(self, config: dict):
        self.config = config.get("alerts", {})
        self.telegram_token = self.config.get("telegram_bot_token")
        self.telegram_chat_id = self.config.get("telegram_chat_id")
        self.discord_webhook = self.config.get("discord_webhook")
        self.rate_limit: dict[str, float] = {}
        self.min_interval = self.config.get("min_interval_seconds", 30)

    async def send(self, alert: dict):
        """Send alert to all configured channels."""
        alert_type = alert.get("type", "unknown")

        # Rate limit per alert type
        now = time.time()
        if alert_type in self.rate_limit:
            if now - self.rate_limit[alert_type] < self.min_interval:
                return
        self.rate_limit[alert_type] = now

        message = self._format_alert(alert)

        tasks = []
        if self.telegram_token and self.telegram_chat_id:
            tasks.append(self._send_telegram(message))
        if self.discord_webhook:
            tasks.append(self._send_discord(message, alert))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _format_alert(self, alert: dict) -> str:
        """Format alert into readable message."""
        alert_type = alert.get("type", "unknown")

        emoji_map = {
            "whale_behavior_change": "🐋",
            "mev_sandwich": "🥪",
            "mev_frontrun": "🏃",
            "liquidation": "💥",
            "large_bridge_transfer": "🌉",
            "sentiment_spike": "📡",
            "exchange_flow": "💰",
        }

        emoji = emoji_map.get(alert_type, "⚠️")
        lines = [f"{emoji} **{alert_type.replace('_', ' ').title()}**
"]

        for key, value in alert.items():
            if key != "type":
                if isinstance(value, float):
                    lines.append(f"• {key}: {value:,.2f}")
                else:
                    lines.append(f"• {key}: {value}")

        return "
".join(lines)

    async def _send_telegram(self, message: str):
        """Send alert via Telegram bot."""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": message[:4096],
                    "parse_mode": "Markdown",
                })
                resp.raise_for_status()
            except Exception as e:
                logger.error(f"Telegram alert failed: {e}")

    async def _send_discord(self, message: str, alert: dict):
        """Send alert via Discord webhook."""
        async with httpx.AsyncClient() as client:
            try:
                embed = {
                    "title": alert.get("type", "Alert").replace("_", " ").title(),
                    "description": message[:4096],
                    "color": 0xFF6B35,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                resp = await client.post(self.discord_webhook, json={
                    "embeds": [embed]
                })
                resp.raise_for_status()
            except Exception as e:
                logger.error(f"Discord alert failed: {e}")
