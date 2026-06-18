"""`aima whatsapp connect/list/validate/delete ...` — manage WhatsApp credentials."""

from __future__ import annotations

import typer

from ..context import get_state
from ..output import emit_json, render_keyvalue, render_table, success, warn
from .whatsapp_connect import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    WhatsAppMode,
    run_connect_flow,
)

app = typer.Typer(
    help="Register and manage WhatsApp Business credentials.", no_args_is_help=True
)

WHATSAPP_CREDENTIALS_COLUMNS = [
    ("id", "ID"),
    ("display_phone_number", "Phone Number"),
    ("title", "Title"),
    ("whatsapp_business_account_id", "WABA ID"),
    ("source", "Source"),
]

TEMPLATE_COLUMNS = [
    ("name", "Name"),
    ("language", "Language"),
    ("status", "Status"),
    ("category", "Category"),
]

TEMPLATE_PICK_COLUMNS = [
    ("#", "#"),
    *TEMPLATE_COLUMNS,
]


@app.command("connect")
def connect(
    ctx: typer.Context,
    mode: WhatsAppMode = typer.Argument(
        ...,
        help=(
            "Connection mode: 'coexistence' (keep business app on phone) "
            "or 'embedded' (dedicated API number)."
        ),
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not attempt to open the browser automatically."
    ),
    timeout: int = typer.Option(
        DEFAULT_CONNECT_TIMEOUT_SECONDS,
        "--timeout",
        help="Seconds to wait for browser connect to complete.",
    ),
) -> None:
    """Connect WhatsApp via a browser link (Meta embedded signup / coexistence)."""
    state = get_state(ctx)

    with state.client() as client:
        result = run_connect_flow(
            client,
            mode,
            open_browser=not no_browser,
            timeout=timeout,
            json_mode=state.json_mode,
        )

    credentials = (result.get("result") or {}).get("whatsapp_credentials") or []

    if state.json_mode:
        emit_json(result)
        return

    success("WhatsApp connected successfully!")
    if credentials:
        render_table(
            credentials,
            WHATSAPP_CREDENTIALS_COLUMNS,
            title="Connected WhatsApp Accounts",
        )
    else:
        render_keyvalue(
            {
                "session_id": result.get("session_id"),
                "status": result.get("status"),
            },
            title="Connect Session",
        )


@app.command("list")
def list_accounts(ctx: typer.Context) -> None:
    """List all WhatsApp credentials registered to your account."""
    state = get_state(ctx)
    with state.client() as client:
        accounts = client.list_whatsapp()

    for account in accounts:
        if "source" not in account:
            account["source"] = account.get("status", "embedded_signup")

    if state.json_mode:
        emit_json(accounts)
    else:
        render_table(
            accounts,
            WHATSAPP_CREDENTIALS_COLUMNS,
            title=f"WhatsApp Credentials ({len(accounts)})",
        )


@app.command("templates")
def templates(
    ctx: typer.Context,
    credentials_id: int = typer.Argument(..., help="WhatsApp credentials ID."),
) -> None:
    """List APPROVED message templates for WhatsApp credentials."""
    state = get_state(ctx)
    with state.client() as client:
        items = client.list_whatsapp_templates(credentials_id)

    if state.json_mode:
        emit_json(items)
    else:
        render_table(
            items,
            TEMPLATE_COLUMNS,
            title=f"Templates ({len(items)})",
        )


@app.command("validate")
def validate(
    ctx: typer.Context,
    credentials_id: int = typer.Argument(..., help="WhatsApp credentials ID to validate."),
) -> None:
    """Validate WhatsApp Business API credentials by testing actual API calls."""
    state = get_state(ctx)
    with state.client() as client:
        result = client.validate_whatsapp(credentials_id)

    if state.json_mode:
        emit_json(result)
    else:
        base = {
            "valid": result.get("valid"),
            "account_status": result.get("account_status"),
            "phone_number_status": result.get("phone_number_status"),
            "templates_count": result.get("templates_count"),
            "message": result.get("message"),
        }
        render_keyvalue(base, title=f"Validation Result (ID: {credentials_id})")
        if result.get("valid"):
            success("Credentials are valid and working.")
        else:
            warn("Credentials validation failed.")


@app.command("delete")
def delete(
    ctx: typer.Context,
    credentials_id: int = typer.Argument(..., help="WhatsApp credentials ID to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a WhatsApp credentials entry by ID."""
    state = get_state(ctx)

    if not yes and not state.json_mode:
        prompt = f"Delete WhatsApp credentials ID {credentials_id}?"
        if not typer.confirm(prompt):
            raise typer.Exit(code=0)

    with state.client() as client:
        result = client.delete_whatsapp(credentials_id)

    if state.json_mode:
        emit_json(result)
    else:
        success(f"WhatsApp credentials ID {credentials_id} deleted successfully.")
