"""`aima usage view` — show current-month voice minutes and WhatsApp leads."""

from __future__ import annotations

import typer

from ..context import get_state
from ..output import emit_json, info

app = typer.Typer(
    help="View billing allowance and current-month usage.",
    no_args_is_help=True,
)


def _format_metric(used: float, total: float) -> str:
    if float(used).is_integer():
        used_str = str(int(used))
    else:
        used_str = f"{used:.1f}"
    if float(total).is_integer():
        total_str = str(int(total))
    else:
        total_str = f"{total:.1f}"
    return f"{used_str} / {total_str}"


@app.command("view")
def view(ctx: typer.Context) -> None:
    """Show voice minutes and WhatsApp leads as used / total for this month."""
    state = get_state(ctx)
    with state.client() as client:
        result = client.get_usage()

    if state.json_mode:
        emit_json(result)
        return

    voice = result.get("voice_minutes") or {}
    info(f"Voice minutes: {_format_metric(voice.get('used', 0), voice.get('total', 0))}")

    whatsapp = result.get("whatsapp_leads") or {}
    whatsapp_total = float(whatsapp.get("total") or 0)
    if whatsapp_total > 0:
        info(
            f"WhatsApp leads: {_format_metric(whatsapp.get('used', 0), whatsapp_total)}"
        )
