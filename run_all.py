#!/usr/bin/env python3
"""
Supervisor: launch all agents concurrently.
"""

import asyncio
import argparse
import signal
import sys
import yaml

from src.agents.chain_agent import ChainAgent
from src.agents.whale_agent import WhaleAgent
from src.agents.sentiment_agent import SentimentAgent


async def main(config_path: str):
    with open(config_path) as f:
        config = yaml.safe_load(f)

    agents = [
        ChainAgent(config),
        WhaleAgent(config),
        SentimentAgent(config),
    ]

    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    def shutdown():
        print("\n🛑 Shutting down agents...")
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    tasks = [asyncio.create_task(agent.run(stop)) for agent in agents]

    print(f"🚀 Launched {len(agents)} agents")
    print("   Press Ctrl+C to stop\n")

    await stop.wait()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    print("✅ All agents stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/settings.yaml")
    args = parser.parse_args()
    asyncio.run(main(args.config))
