"""
Chain Agent — streams blocks from EVM RPC nodes.

Decodes transactions, extracts calldata, and publishes
structured events to Redis Streams for downstream agents.
"""

import asyncio
import json
import time
from typing import Optional
from web3 import Web3
from web3.exceptions import BlockNotFound

from src.utils.redis_bus import RedisBus
from src.utils.logger import get_logger

logger = get_logger("chain_agent")

# Known DEX routers
DEX_ROUTERS = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3",
    "0x10ed43c718714eb63d5aa57b78b54704e256024e": "PancakeSwap",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch V5",
}

# Known CEX deposit addresses
CEX_HOT_WALLETS = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
    "0xa090e606e30bd747d4e6245a1517ebe430f0057e": "Coinbase",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2": "FTX (defunct)',
}

# Transfer event signature
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class ChainAgent:
    """Streams EVM blocks and decodes transactions."""

    def __init__(self, config: dict):
        self.chains = config.get("chains", {})
        self.bus = RedisBus(config.get("redis", {}))
        self.min_value_usd = config.get("whale", {}).get("min_value_usd", 100000)
        self._running = False

    async def run(self, stop: asyncio.Event):
        """Main loop — stream blocks from all configured chains."""
        self._running = True
        tasks = []
        for chain_name, chain_cfg in self.chains.items():
            tasks.append(asyncio.create_task(
                self._stream_chain(chain_name, chain_cfg, stop)
            ))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _stream_chain(self, name: str, cfg: dict, stop: asyncio.Event):
        """Stream blocks from a single chain."""
        w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
        logger.info(f"[{name}] Connected to {cfg['rpc']}")

        last_block = w3.eth.block_number

        while not stop.is_set():
            try:
                current = w3.eth.block_number
                if current <= last_block:
                    await asyncio.sleep(2)
                    continue

                for block_num in range(last_block + 1, current + 1):
                    if stop.is_set():
                        break
                    await self._process_block(w3, name, block_num)
                    last_block = block_num

            except Exception as e:
                logger.error(f"[{name}] Error: {e}")
                await asyncio.sleep(5)

    async def _process_block(self, w3: Web3, chain: str, block_num: int):
        """Process a single block — extract relevant transactions."""
        try:
            block = w3.eth.get_block(block_num, full_transactions=True)
        except BlockNotFound:
            return

        events = []
        for tx in block.transactions:
            if tx["value"] == 0 and not tx.get("to"):
                continue

            event = {
                "chain": chain,
                "block": block_num,
                "hash": tx["hash"].hex(),
                "from": tx["from"].lower() if tx["from"] else None,
                "to": tx["to"].lower() if tx["to"] else None,
                "value_eth": float(w3.from_wei(tx["value"], "ether")),
                "gas_price_gwei": float(w3.from_wei(tx["gasPrice"], "gwei")),
                "timestamp": block.timestamp,
                "method_id": tx["input"][:10].hex() if len(tx["input"]) >= 10 else "0x",
            }

            # Classify transaction
            event["tags"] = self._classify_tx(event)

            # Only emit if relevant
            if event["tags"] or event["value_eth"] > 10:
                events.append(event)

        if events:
            await self.bus.publish_many("chain:transactions", events)
            logger.info(f"[{chain}] Block {block_num}: {len(events)} relevant txs")

    def _classify_tx(self, tx: dict) -> list:
        """Classify transaction tags."""
        tags = []

        # DEX swap
        if tx["to"] and tx["to"] in DEX_ROUTERS:
            tags.append(f"dex:{DEX_ROUTERS[tx['to']]}")

        # CEX deposit
        if tx["to"] and tx["to"] in CEX_HOT_WALLETS:
            tags.append(f"cex_deposit:{CEX_HOT_WALLETS[tx['to']]}")

        # Large transfer
        if tx["value_eth"] > 100:
            tags.append("large_transfer")

        # Contract creation
        if tx["to"] is None:
            tags.append("contract_creation")

        return tags
