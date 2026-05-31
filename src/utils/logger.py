"""
Structured logging with Rich formatting.
"""

import logging
from rich.logging import RichHandler


def get_logger(name: str) -> logging.Logger:
    """Get a Rich-formatted logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
