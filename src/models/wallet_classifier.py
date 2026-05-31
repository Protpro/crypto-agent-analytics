"""
Wallet Classifier — ROCm-accelerated transformer model.

Classifies wallet behavior (whale, bot, MEV, retail, VC)
based on transaction embedding vectors.
"""

import numpy as np
from typing import Optional

try:
    import onnxruntime as ort
except ImportError:
    ort = None


WALLET_LABELS = [
    "retail",       # Regular user
    "whale",        # Large holder
    "bot",          # Automated trading
    "mev",          # MEV searcher/arbitrageur
    "vc",           # Venture capital
    "market_maker", # DEX/CEX market maker
    "smart_money",  # Consistently profitable
    "airdrop_hunter", # Multi-wallet sybil
]


class WalletClassifier:
    """Classify wallet type from transaction history embeddings."""

    def __init__(self, model_path: str = "models/wallet-embed-v1.onnx", device: str = "cpu"):
        self.model_path = model_path
        self.device = device
        self.session = None
        self._load_model()

    def _load_model(self):
        """Load ONNX model with ROCm or CPU execution."""
        if ort is None:
            return

        providers = ["CPUExecutionProvider"]
        if self.device == "rocm":
            providers = [
                ("ROCMExecutionProvider", {
                    "device_id": 0,
                    "arena_extend_strategy": "kNextPowerOfTwo",
                    "miopen_conv_exhaustive_search": False,
                }),
                "CPUExecutionProvider",
            ]

        try:
            self.session = ort.InferenceSession(
                self.model_path, providers=providers
            )
        except Exception:
            self.session = None

    def encode_transaction(self, tx: dict) -> np.ndarray:
        """Encode a transaction into a feature vector."""
        features = [
            tx.get("value_eth", 0),
            tx.get("gas_price_gwei", 0),
            len(tx.get("tags", [])),
            1 if tx.get("from") else 0,
            1 if tx.get("to") else 0,
            hash(tx.get("chain", "")) % 100,
        ]
        return np.array(features, dtype=np.float32)

    def classify(self, transactions: list[dict]) -> dict:
        """Classify a wallet based on its transactions."""
        if not transactions:
            return {"label": "unknown", "confidence": 0.0}

        # Encode transactions
        vectors = np.array([self.encode_transaction(tx) for tx in transactions])

        # Aggregate features
        mean_vec = vectors.mean(axis=0)
        std_vec = vectors.std(axis=0)
        features = np.concatenate([mean_vec, std_vec]).reshape(1, -1)

        if self.session:
            # Model inference
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: features})
            probs = outputs[0][0]
            label_idx = int(np.argmax(probs))
            return {
                "label": WALLET_LABELS[label_idx],
                "confidence": float(probs[label_idx]),
                "probs": {l: float(p) for l, p in zip(WALLET_LABELS, probs)},
            }

        # Fallback: heuristic classification
        return self._heuristic_classify(transactions)

    def _heuristic_classify(self, transactions: list[dict]) -> dict:
        """Simple heuristic classification when model not available."""
        total_value = sum(tx.get("value_eth", 0) for tx in transactions)
        tx_count = len(transactions)
        has_dex = any("dex" in str(tx.get("tags", [])) for tx in transactions)
        has_cex = any("cex" in str(tx.get("tags", [])) for tx in transactions)

        if total_value > 10000:
            return {"label": "whale", "confidence": 0.7}
        if has_dex and has_cex:
            return {"label": "market_maker", "confidence": 0.6}
        if tx_count > 100 and has_dex:
            return {"label": "bot", "confidence": 0.65}
        if has_dex and total_value > 100:
            return {"label": "smart_money", "confidence": 0.5}

        return {"label": "retail", "confidence": 0.4}
