from __future__ import annotations

import logging
import os
import sys

from github import Github


def _build_github_client() -> Github:
    """Build a Github client using the GITHUB_TOKEN env var when available.

    Falls back to unauthenticated access if no token is configured.
    """

    token = os.getenv("GITHUB_TOKEN")
    if token:
        return Github(token)
    else:
        with open("/home/afayolle/.github_token2") as f:
            token = f.read().strip()
        return Github(token)
    return Github()


def setup_logging(name: str = "github-repositories-tool") -> logging.Logger:
    """Configure and return a logger with stdout handler at INFO level.

    Parameters
    ----------
    name: str
        Name of the logger to configure.
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
