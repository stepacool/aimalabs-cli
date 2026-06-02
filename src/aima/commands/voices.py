"""`aima voices ...`"""

from __future__ import annotations

import typer

from ..context import get_state
from ..output import emit_json, render_table

app = typer.Typer(help="List voices available to your account.", no_args_is_help=True)

VOICE_COLUMNS = [
    ("id", "ID"),
    ("title", "Title"),
    ("provider", "Provider"),
    ("voice_type", "Type"),
    ("languages", "Languages"),
    ("is_system", "System"),
    ("description", "Description"),
]


@app.command("list")
def list_voices(
    ctx: typer.Context,
    language: str = typer.Option(None, "--language", "-l", help="ISO-639-1 code, e.g. en, es."),
    provider: str = typer.Option(None, "--provider", "-p", help="Voice provider enum value."),
    voice_type: str = typer.Option(None, "--voice-type", "-t", help="per_customer or generic."),
    no_active: bool = typer.Option(
        False, "--no-active", help="List inactive voices (sends is_active=false)."
    ),
) -> None:
    """List voices. Default shows active only; --no-active shows inactive."""
    state = get_state(ctx)
    # Default: send is_active=true. --no-active sends is_active=false.
    is_active = False if no_active else True
    with state.client() as client:
        voices = client.list_voices(
            language=language, provider=provider, voice_type=voice_type, is_active=is_active
        )
    if state.json_mode:
        emit_json(voices)
    else:
        render_table(voices, VOICE_COLUMNS, title=f"Voices ({len(voices)})")
