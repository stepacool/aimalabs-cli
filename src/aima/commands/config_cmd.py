"""`aima config ...` — local config management (no API calls)."""

from __future__ import annotations

import typer

from .. import config as cfg
from ..context import get_state, reload_state
from ..output import emit_json, info, render_keyvalue, success
from ..prompts import ask_confirm

app = typer.Typer(help="Inspect and edit local CLI configuration.", no_args_is_help=True)


@app.command("show")
def show(ctx: typer.Context) -> None:
    """Print the effective configuration with the API key masked."""
    state = get_state(ctx)
    conf = state.config
    payload = {
        "base_url": conf.base_url,
        "api_key": conf.masked_api_key(),
        "config_path": str(conf.source_path),
        "config_exists": conf.source_path.exists(),
    }
    if state.json_mode:
        emit_json(payload)
    else:
        render_keyvalue(payload, title="aima config")


@app.command("set")
def set_value(ctx: typer.Context, key: str, value: str) -> None:
    """Set a config key. One of: base_url, api_key."""
    state = get_state(ctx)
    path = cfg.set_key(key, value)
    reload_state(ctx)
    if state.json_mode:
        emit_json({"set": key, "config_path": str(path)})
    else:
        success(f"Set {key} in {path}")


@app.command("clear")
def clear(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Delete the local config file."""
    state = get_state(ctx)
    path = cfg.config_path()
    if not path.exists():
        info(f"No config file at {path}; nothing to clear.")
        if state.json_mode:
            emit_json({"cleared": False, "config_path": str(path)})
        return
    if not yes and not state.json_mode:
        if not ask_confirm(f"Delete {path}?"):
            raise typer.Exit(code=0)
    cfg.clear_config()
    if state.json_mode:
        emit_json({"cleared": True, "config_path": str(path)})
    else:
        success(f"Removed {path}")
