"""`aima whatsapp connect/list/validate/delete ...` — manage WhatsApp credentials."""

from __future__ import annotations

import time
import webbrowser
from enum import StrEnum

import typer

from ..context import get_state
from ..errors import UserError
from ..output import emit_json, info, render_keyvalue, render_table, success, warn

app = typer.Typer(
    help="Register and manage WhatsApp Business credentials.", no_args_is_help=True
)


class WhatsAppMode(StrEnum):
    coexistence = "coexistence"
    embedded = "embedded"


WHATSAPP_CREDENTIALS_COLUMNS = [
    ("id", "ID"),
    ("display_phone_number", "Phone Number"),
    ("title", "Title"),
    ("whatsapp_business_account_id", "WABA ID"),
    ("source", "Source"),
]

POLL_INTERVAL_SECONDS = 3
DEFAULT_CONNECT_TIMEOUT_SECONDS = 30 * 60


def _mode_to_source(mode: WhatsAppMode) -> str:
    return "coexistence" if mode == WhatsAppMode.coexistence else "embedded_signup"


def _poll_connect_session(
    client,
    session_id: str,
    timeout_seconds: int,
) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = client.get_whatsapp_connect_session(session_id)
        state = status.get("status")
        if state == "completed":
            return status
        if state == "failed":
            error = status.get("error") or "WhatsApp connect failed"
            raise UserError(error)
        time.sleep(POLL_INTERVAL_SECONDS)
    raise UserError(
        "Timed out waiting for WhatsApp connect. "
        "Open the URL again with `aima whatsapp connect` if the session expired."
    )


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
    source = _mode_to_source(mode)

    with state.client() as client:
        session = client.create_whatsapp_connect_session(source)

    connect_url = session["connect_url"]
    session_id = session["session_id"]

    info("Open this URL in your browser to connect WhatsApp:")
    info(f"\n{connect_url}\n")
    info(f"Session expires in {session.get('expires_in_seconds', 1800)} seconds.")

    if not no_browser:
        webbrowser.open(connect_url)

    if state.json_mode:
        info("Waiting for connect to complete...")
    else:
        info("Waiting for connect to complete (Ctrl+C to stop polling)...")

    try:
        with state.client() as client:
            result = _poll_connect_session(client, session_id, timeout)
    except KeyboardInterrupt:
        info("\nStopped polling. The connect URL may still work until it expires.")
        raise typer.Exit(code=130) from None

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
                "session_id": session_id,
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

    # Backwards compatibility of headers for WHATSAPP_CREDENTIALS_COLUMNS
    for account in accounts:
        # backend returns display_phone_number and source, map source if not present
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
