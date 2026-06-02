"""Output rendering: human (rich tables / key-value) vs machine (--json).

Output mode is resolved once per invocation (see resolve_json_mode) and carried
on the AppState. Every command renders through the helpers here so that --json
always wins and secrets are masked in human mode.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.table import Table

from .config import mask_api_key

# stderr console so machine-readable stdout (--json) is never polluted.
_err = Console(stderr=True)
_out = Console()


def resolve_json_mode(
    *, json_flag: bool | None, env_json: bool, is_tty: bool
) -> bool:
    """Decide whether to emit machine-readable JSON.

    Precedence: explicit --json / --no-json flag, then AIMA_OUTPUT=json env,
    then auto-detect (non-TTY stdout → json).
    """
    if json_flag is not None:
        return json_flag
    if env_json:
        return True
    return not is_tty


def emit_json(data: Any) -> None:
    """Print a raw JSON body to stdout and nothing else."""
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def info(message: str) -> None:
    """Human-facing status line — goes to stderr to keep stdout clean."""
    _err.print(message)


def warn(message: str) -> None:
    _err.print(f"[yellow]{message}[/yellow]")


def error(message: str) -> None:
    _err.print(f"[red]{message}[/red]")


def success(message: str) -> None:
    _err.print(f"[green]{message}[/green]")


def _fmt(value: Any) -> str:
    if value is None:
        return "[dim]—[/dim]"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "[dim]—[/dim]"
    return str(value)


def render_table(
    rows: list[dict], columns: list[tuple[str, str]], *, title: str | None = None
) -> None:
    """Render a list of dicts as a rich table.

    `columns` is a list of (key, header) tuples controlling order and labels.
    """
    table = Table(title=title, show_lines=False, header_style="bold cyan")
    for _key, header in columns:
        table.add_column(header)
    for row in rows:
        table.add_row(*[_fmt(row.get(key)) for key, _h in columns])
    if not rows:
        _out.print("[dim]No results.[/dim]")
        return
    _out.print(table)


def render_keyvalue(
    data: dict, *, title: str | None = None, mask_keys: tuple[str, ...] = ()
) -> None:
    """Render a single resource as an aligned key/value block."""
    table = Table(
        show_header=False, box=None, title=title, title_justify="left", pad_edge=False
    )
    table.add_column("key", style="bold cyan", no_wrap=True)
    table.add_column("value", overflow="fold")
    for key, value in data.items():
        if key in mask_keys:
            value = mask_api_key(value)
        table.add_row(str(key), _fmt(value))
    _out.print(table)
