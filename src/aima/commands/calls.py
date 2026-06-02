"""`aima calls ...` — dispatch real calls and watch their status."""

from __future__ import annotations

import time

import typer

from ..context import get_state
from ..errors import UserError
from ..output import emit_json, info, render_keyvalue, success, warn

app = typer.Typer(help="Dispatch outbound calls and check status.", no_args_is_help=True)


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
        if not typer.confirm("Dispatch now?", default=False):
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
            result = _poll(ctx, client, lead_id, poll_interval, poll_timeout)

    if state.json_mode:
        emit_json(result)
    else:
        _render_status(result)


def _poll(ctx, client, lead_id: int, interval: int, timeout: int) -> dict:
    state = get_state(ctx)
    deadline = time.monotonic() + timeout
    result = client.lead_status(lead_id)
    while True:
        call = result.get("latest_call") or {}
        if call.get("ended_at"):
            return result
        if time.monotonic() >= deadline:
            if not state.json_mode:
                warn(f"Poll timed out after {timeout}s; call has not ended.")
            return result
        if not state.json_mode:
            status_str = (call.get("status") or "pending")
            info(f"… {status_str}; re-checking in {interval}s")
        remaining = deadline - time.monotonic()
        time.sleep(min(interval, max(0.0, remaining)))
        result = client.lead_status(lead_id)


def _render_status(result: dict) -> None:
    head = {k: result.get(k) for k in ("lead_id", "name", "phone_number")}
    render_keyvalue(head, title="Lead")

    values = result.get("values")
    if values:
        from ..output import render_table

        render_table(values, [("key", "Field"), ("value", "Value")], title="Extracted values")

    call = result.get("latest_call")
    if not call:
        info("No call placed yet.")
        return
    render_keyvalue(call, title="Latest call")
    if call.get("ended_at"):
        success(f"Call ended ({call.get('status')}).")
