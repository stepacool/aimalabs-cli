"""`aima calls ...` — dispatch real calls and watch their status."""

from __future__ import annotations

import time
from collections.abc import Callable

import typer

from ..context import get_state
from ..errors import UserError
from ..output import emit_json, info, render_keyvalue, success, warn
from ..prompts import ask_confirm

app = typer.Typer(help="Dispatch outbound calls and check status.", no_args_is_help=True)

_WHATSAPP_DONE_STATUSES = frozenset({"sent", "delivered"})
_WHATSAPP_PRE_SEND_STATUSES = frozenset({"not_started", "failed_to_start"})


@app.command("dispatch")
def dispatch(
    ctx: typer.Context,
    lead_id: int = typer.Argument(..., help="Lead id to call."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Place a REAL outbound call to a lead. Not idempotent — every run dials."""
    state = get_state(ctx)
    if not yes:
        if state.json_mode:
            # No TTY to confirm on — fail closed rather than auto-dial.
            raise UserError(
                f"Refusing to dispatch lead {lead_id} non-interactively. "
                "Pass --yes to place the call."
            )
        warn(f"This places a REAL phone call to lead {lead_id}.")
        if not ask_confirm("Dispatch now?", default=False):
            raise typer.Exit(code=0)
    with state.client() as client:
        result = client.dispatch(lead_id)
    if state.json_mode:
        emit_json(result)
    else:
        render_keyvalue(result, title="Dispatched")
        info(f"Watch it with: aima calls status {lead_id} --poll")


@app.command("status")
def status(
    ctx: typer.Context,
    lead_id: int = typer.Argument(..., help="Lead id to inspect."),
    poll: bool = typer.Option(False, "--poll", help="Refetch until the call ends."),
    poll_interval: int = typer.Option(20, "--poll-interval", min=1, help="Seconds between polls."),
    poll_timeout: int = typer.Option(300, "--poll-timeout", min=1, help="Max seconds to poll."),
) -> None:
    """Fetch a lead's latest call status and extracted values."""
    state = get_state(ctx)
    with state.client() as client:
        if not poll:
            result = client.lead_status(lead_id)
        else:
            result = poll_lead_status(
                client,
                lead_id,
                interval=poll_interval,
                timeout=poll_timeout,
                is_done=call_poll_done,
                progress=call_poll_progress,
                json_mode=state.json_mode,
            )

    if state.json_mode:
        emit_json(result)
    else:
        render_lead_status(result)


def poll_lead_status(
    client,
    lead_id: int,
    *,
    interval: int,
    timeout: int,
    is_done: Callable[[dict], bool],
    progress: Callable[[dict], str],
    json_mode: bool,
) -> dict:
    deadline = time.monotonic() + timeout
    result = client.lead_status(lead_id)
    while not is_done(result):
        if time.monotonic() >= deadline:
            if not json_mode:
                warn(f"Poll timed out after {timeout}s.")
            return result
        if not json_mode:
            info(progress(result))
        remaining = deadline - time.monotonic()
        time.sleep(min(interval, max(0.0, remaining)))
        result = client.lead_status(lead_id)
    return result


def call_poll_done(result: dict) -> bool:
    return bool((result.get("latest_call") or {}).get("ended_at"))


def call_poll_progress(result: dict) -> str:
    status = (result.get("latest_call") or {}).get("status") or "pending"
    return f"… {status}; re-checking"


def whatsapp_poll_done(result: dict) -> bool:
    conv = result.get("latest_conversation") or {}
    if conv.get("latest_message_status") in _WHATSAPP_DONE_STATUSES:
        return True
    status = conv.get("status")
    return bool(status and status not in _WHATSAPP_PRE_SEND_STATUSES)


def whatsapp_poll_progress(result: dict) -> str:
    conv = result.get("latest_conversation") or {}
    return (
        f"… conversation={conv.get('status') or 'pending'} "
        f"message={conv.get('latest_message_status') or 'pending'}; re-checking"
    )


def render_lead_status(result: dict) -> None:
    head = {k: result.get(k) for k in ("lead_id", "name", "phone_number")}
    render_keyvalue(head, title="Lead")

    values = result.get("values")
    if values:
        from ..output import render_table

        render_table(values, [("key", "Field"), ("value", "Value")], title="Extracted values")

    conv = result.get("latest_conversation")
    if conv:
        render_keyvalue(conv, title="Latest conversation")
        if conv.get("latest_message_status") in _WHATSAPP_DONE_STATUSES:
            success(f"Message {conv.get('latest_message_status')}.")

    call = result.get("latest_call")
    if not call:
        if not conv:
            info("No call placed yet.")
        return
    render_keyvalue(call, title="Latest call")
    if call.get("ended_at"):
        success(f"Call ended ({call.get('status')}).")
