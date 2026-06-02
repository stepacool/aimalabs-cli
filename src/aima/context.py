"""Per-invocation state carried on the Typer context (ctx.obj)."""

from __future__ import annotations

import sys
from dataclasses import dataclass

import typer

from .client import AimaClient
from .config import Config, load_config


@dataclass
class AppState:
    """Resolved once in the root callback, read by every command."""

    json_mode: bool
    config: Config

    def client(self) -> AimaClient:
        """Build an API client, raising ConfigError (exit 3) if no key."""
        return AimaClient(self.config)


def get_state(ctx: typer.Context) -> AppState:
    state = ctx.obj
    assert isinstance(state, AppState), "AppState not initialized"
    return state


def reload_state(ctx: typer.Context) -> AppState:
    """Re-read config from disk and refresh the state (after a config write)."""
    state = get_state(ctx)
    state.config = load_config()
    return state


def stdout_is_tty() -> bool:
    try:
        return sys.stdout.isatty()
    except Exception:
        return False
