"""`aima phones list/available/rent/release ...` — manage rented PSTN numbers."""

from __future__ import annotations

import typer

from ..context import get_state
from ..output import emit_json, render_keyvalue, render_table, success
from ..prompts import ask_confirm

app = typer.Typer(help="Rent and manage outbound phone numbers.", no_args_is_help=True)

RENTED_COLUMNS = [
    ("id", "ID"),
    ("phone_e164", "Phone"),
    ("country_code", "Country"),
    ("status", "Status"),
    ("assignment_id", "Assignment ID"),
]

AVAILABLE_COLUMNS = [
    ("id", "ID"),
    ("phone_e164", "Phone"),
    ("country_code", "Country"),
    ("status", "Status"),
]


@app.command("list")
def list_rented(
    ctx: typer.Context,
    limit: int | None = typer.Option(None, "--limit", help="Max rows to return."),
) -> None:
    """List phone numbers rented by your account."""
    state = get_state(ctx)
    params: dict[str, int] = {}
    if limit is not None:
        params["limit"] = limit

    with state.client() as client:
        phones = client.list_phones(**params)

    if state.json_mode:
        emit_json(phones)
    else:
        render_table(
            phones,
            RENTED_COLUMNS,
            title=f"Rented Phone Numbers ({len(phones)})",
        )


@app.command("available")
def list_available(
    ctx: typer.Context,
    limit: int | None = typer.Option(None, "--limit", help="Max rows to return."),
) -> None:
    """List phone numbers available to rent."""
    state = get_state(ctx)
    params: dict[str, int] = {}
    if limit is not None:
        params["limit"] = limit

    with state.client() as client:
        phones = client.list_available_phones(**params)

    if state.json_mode:
        emit_json(phones)
    else:
        render_table(
            phones,
            AVAILABLE_COLUMNS,
            title=f"Available Phone Numbers ({len(phones)})",
        )


@app.command("rent")
def rent(
    ctx: typer.Context,
    phone_number_id: int = typer.Argument(..., help="Phone number ID from `phones available`."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Rent an available phone number."""
    state = get_state(ctx)

    if not yes and not state.json_mode:
        prompt = f"Rent phone number ID {phone_number_id}?"
        if not ask_confirm(prompt):
            raise typer.Exit(code=0)

    with state.client() as client:
        result = client.rent_phone(phone_number_id)

    if state.json_mode:
        emit_json(result)
    else:
        render_keyvalue(
            {
                "assignment_id": result.get("assignment_id"),
                "phone_e164": result.get("phone_e164"),
                "status": result.get("status"),
                "monthly_price_cents": result.get("monthly_price_cents"),
            },
            title="Rented Phone Number",
        )
        success(f"Rented {result.get('phone_e164')} (assignment {result.get('assignment_id')}).")


@app.command("release")
def release(
    ctx: typer.Context,
    assignment_id: int = typer.Argument(..., help="Assignment ID from `phones list`."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Release a rented phone number."""
    state = get_state(ctx)

    if not yes and not state.json_mode:
        prompt = f"Release phone assignment ID {assignment_id}?"
        if not ask_confirm(prompt):
            raise typer.Exit(code=0)

    with state.client() as client:
        result = client.release_phone(assignment_id)

    if state.json_mode:
        emit_json(result)
    else:
        render_keyvalue(
            {
                "assignment_id": result.get("assignment_id"),
                "phone_e164": result.get("phone_e164"),
                "status": result.get("status"),
            },
            title="Released Phone Number",
        )
        success(f"Released {result.get('phone_e164')}.")
