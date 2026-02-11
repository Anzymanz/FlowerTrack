from __future__ import annotations

import os
import sys
from typing import Iterable

MODE_STANDALONE = "standalone"
MODE_HOST = "host"
MODE_CLIENT = "client"

HOST_FLAGS = {"-host", "--host"}
CLIENT_FLAGS = {"-client", "--client"}

ENV_KEY = "FLOWERTRACK_NETWORK_MODE"


def consume_mode_flags(argv: list[str] | None = None) -> str:
    """Parse and remove network mode flags from argv, then cache mode in env."""
    args = sys.argv if argv is None else argv
    mode = MODE_STANDALONE
    # Last matching flag wins if both appear.
    for arg in args:
        if arg in HOST_FLAGS:
            mode = MODE_HOST
        elif arg in CLIENT_FLAGS:
            mode = MODE_CLIENT

    args[:] = [arg for arg in args if arg not in HOST_FLAGS and arg not in CLIENT_FLAGS]
    os.environ[ENV_KEY] = mode
    return mode


def get_mode() -> str:
    mode = str(os.getenv(ENV_KEY, MODE_STANDALONE)).strip().lower()
    if mode not in {MODE_STANDALONE, MODE_HOST, MODE_CLIENT}:
        return MODE_STANDALONE
    return mode


def is_networked(mode: str | None = None) -> bool:
    value = (mode or get_mode()).strip().lower()
    return value in {MODE_HOST, MODE_CLIENT}


def is_host(mode: str | None = None) -> bool:
    value = (mode or get_mode()).strip().lower()
    return value == MODE_HOST


def is_client(mode: str | None = None) -> bool:
    value = (mode or get_mode()).strip().lower()
    return value == MODE_CLIENT

