"""`aima init` and `aima status` — first-run wizard and key probe."""

from __future__ import annotations

import typer

from .. import config as cfg
from ..client import AimaClient
from ..context import get_state, reload_state
from ..errors import AimaError
from ..output import emit_json, info, render_keyvalue, success, warn


def init(ctx: typer.Context) -> None:
    """Interactive first-run wizard: prompt, validate, write config (0600)."""
    state = get_state(ctx)
    conf = state.config
    path = cfg.config_path()

    if path.exists() and not state.json_mode:
        warn(f"Config already exists at {path}.")
        if not typer.confirm("Overwrite it?", default=False):
            raise typer.Exit(code=0)

    if state.json_mode:
        # Non-interactive: rely on env / existing values; just validate.
        api_key = conf.api_key
        base_url = conf.base_url
        if not api_key:
            raise AimaError(
                "init in --json mode needs AIMA_API_KEY set (no prompts available).",
                exit_code=3,
            )
    else:
        info("Setting up AIMA Labs CLI. Get your API key from the dashboard.")
        default_key = conf.api_key or None
        api_key = typer.prompt(
            "API key (api_...)",
            default=default_key,
            hide_input=False,
            show_default=bool(default_key),
        ).strip()
        base_url = typer.prompt(
            "Base URL", default=conf.base_url or cfg.DEFAULT_BASE_URL
        ).strip()

    # Validate by hitting GET /voices before persisting.
    probe_conf = cfg.Config(base_url=base_url.rstrip("/"), api_key=api_key, source_path=path)
    info("Validating key against the API…")
    with AimaClient(probe_conf) as client:
        client.list_voices()

    written = cfg.save_config(base_url=base_url, api_key=api_key)
    reload_state(ctx)
    if state.json_mode:
        emit_json(
            {"configured": True, "config_path": str(written), "base_url": base_url.rstrip("/")}
        )
    else:
        success(f"Validated and saved config to {written} (mode 0600).")
        info("Try: aima voices list")


def status(ctx: typer.Context) -> None:
    """Show config and probe that the API key still works."""
    state = get_state(ctx)
    conf = state.config

    base = {
        "base_url": conf.base_url,
        "api_key": conf.masked_api_key(),
        "config_path": str(conf.source_path),
    }

    probe_ok = False
    probe_error = None
    if conf.has_api_key:
        try:
            with state.client() as client:
                client.list_voices()
            probe_ok = True
        except AimaError as exc:
            probe_error = exc.message
    else:
        probe_error = "no api_key configured"

    payload = {**base, "api_ok": probe_ok, "api_error": probe_error}
    if state.json_mode:
        emit_json(payload)
    else:
        render_keyvalue(base, title="aima status")
        if probe_ok:
            success("API: ok")
        else:
            warn(f"API: {probe_error}")

    if not probe_ok:
        raise typer.Exit(code=1)
