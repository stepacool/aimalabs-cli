"""Error types and exit-code conventions.

Exit codes (per spec):
  0 — success
  1 — user error (4xx, bad flags, validation)
  2 — server / network error (5xx or transport failure)
  3 — missing or invalid config

The errors subclass click.ClickException so that Click's standalone mode (and
typer.testing.CliRunner) translate them into the right process exit code and
print `message` to stderr — no manual try/except needed at the call sites.
"""

from __future__ import annotations

import click

EXIT_OK = 0
EXIT_USER = 1
EXIT_SERVER = 2
EXIT_CONFIG = 3


class AimaError(click.ClickException):
    """Base CLI error carrying an exit code; prints `message` to stderr."""

    exit_code = EXIT_USER

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code

    def show(self, file=None) -> None:  # noqa: ARG002 — match Click signature
        # Import here to avoid a cycle (output imports config, not errors).
        from .output import error

        error(self.message)


class ConfigError(AimaError):
    """Missing or unreadable configuration (no api_key, bad file)."""

    exit_code = EXIT_CONFIG


class UserError(AimaError):
    """4xx response, bad flags, or local validation failure."""

    exit_code = EXIT_USER


class ServerError(AimaError):
    """5xx response or transport-level failure."""

    exit_code = EXIT_SERVER
