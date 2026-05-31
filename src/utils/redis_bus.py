"""
Redis Streams event bus for inter-agent communication.
"""

import json
import asyncio
from typing import AsyncGenerator

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class RedisBus:
    """Async Redis Streams publisher/subscriber."""

    def __init__(self, config: dict):
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 6379)
        self.db = config.get("db", 0)
        self._redis = None
        self._group = "agent_group"

    async def _connect(self):
        if self._redis is None:
            self._redis = aioredis.Redis(
                host=self.host, port=self.port, db=self.db,
                decode_responses=True
            )
        return self._redis

    async def publish(self, stream: str, event: dict):
        """Publish a single event to a stream."""
        r = await self._connect()
        await r.xadd(stream, {"data": json.dumps(event)})

    async def publish_many(self, stream: str, events: list):
        """Publish multiple events in a pipeline."""
        r = await self._connect()
        pipe = r.pipeline()
        for event in events:
            pipe.xadd(stream, {"data": json.dumps(event)})
        await pipe.execute()

    async def subscribe(self, stream: str) -> AsyncGenerator[dict, None]:
        """Subscribe to a stream and yield events."""
        r = await self._connect()

        # Create consumer group if not exists
        try:
            await r.xgroup_create(stream, self._group, id="0", mkstream=True)
        except Exception:
            pass  # Group already exists

        consumer = f"agent_{id(self)}"

        while True:
            try:
                results = await r.xreadgroup(
                    self._group, consumer, {stream: ">"}, count=10, block=5000
                )
                if results:
                    for stream_name, messages in results:
                        for msg_id, data in messages:
                            yield json.loads(data["data"])
                            await r.xack(stream, self._group, msg_id)
            except Exception as e:
                await asyncio.sleep(1)
