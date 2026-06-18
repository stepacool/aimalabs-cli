"""Entry point: assemble the `aima <noun> <verb>` command tree."""

from __future__ import annotations

import os

import typer

from . import __version__
from .commands import agents, calls, campaigns, config_cmd, leads, onboard, setup, usage, voices, whatsapp
from .config import load_config
from .context import AppState, stdout_is_tty
from .errors import AimaError
from .output import error, resolve_json_mode

app = typer.Typer(
    name="aima",
    help=(
        "AIMA Labs CLI — drive voice/WhatsApp campaigns.\n\n"
        "Run 'aima init' to get started, or 'aima onboard' for a guided walkthrough."
    ),
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
    # Don't dump rich tracebacks at end users; AimaError.show() handles display.
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aima {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    ctx: typer.Context,
    json_mode: bool = typer.Option(
        None,
        "--json/--no-json",
        help="Force machine-readable JSON (or force human output). "
        "Defaults to JSON when stdout is not a TTY.",
    ),
    _version: bool = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Resolve global state once and stash it on the context."""
    env_json = os.environ.get("AIMA_OUTPUT", "").lower() == "json"
    resolved = resolve_json_mode(
        json_flag=json_mode, env_json=env_json, is_tty=stdout_is_tty()
    )
    ctx.obj = AppState(json_mode=resolved, config=load_config())


# -- top-level composite / setup commands ---------------------------------

app.command("init", help="Interactive first-run setup wizard.")(setup.init)
app.command("status", help="Show config and probe that the API key works.")(setup.status)
app.command("onboard", help="Guided end-to-end walkthrough (voice → campaign → call).")(
    onboard.onboard
)

# -- noun sub-apps ---------------------------------------------------------

app.add_typer(config_cmd.app, name="config")
app.add_typer(voices.app, name="voices")
app.add_typer(agents.app, name="agents")
app.add_typer(campaigns.app, name="campaigns")
app.add_typer(leads.app, name="leads")
app.add_typer(calls.app, name="calls")
app.add_typer(usage.app, name="usage")
app.add_typer(whatsapp.app, name="whatsapp")


def main() -> None:
    """Console-script entry point: map AimaError → stderr line + exit code.

    (AimaError is a ClickException, but this typer version's vendored core does
    not run Click's standalone exception handling, so we do it explicitly here.)
    """
    try:
        app(standalone_mode=True)
    except AimaError as exc:
        error(exc.message)
        raise SystemExit(exc.exit_code) from None
    except KeyboardInterrupt:
        error("Aborted.")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
