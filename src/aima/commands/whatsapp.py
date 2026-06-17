"""`aima whatsapp connect/list/validate/delete ...` — manage WhatsApp credentials."""

from __future__ import annotations

import json
import socket
import urllib.parse
import uuid
import webbrowser
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer

import typer

from ..context import get_state
from ..errors import UserError
from ..output import emit_json, info, render_keyvalue, render_table, success, warn

app = typer.Typer(
    help="Register and manage WhatsApp Business credentials.", no_args_is_help=True
)


class WhatsAppMode(str, Enum):
    coexistence = "coexistence"
    embedded = "embedded"


WHATSAPP_CREDENTIALS_COLUMNS = [
    ("id", "ID"),
    ("display_phone_number", "Phone Number"),
    ("title", "Title"),
    ("whatsapp_business_account_id", "WABA ID"),
    ("source", "Source"),
]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Local HTTP request handler to capture the authorization code callback."""

    def log_message(self, format: str, *args: tuple) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path in ("/", "/callback"):
            code = params.get("code")
            self.send_response(200 if code else 400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if code:
                self.server.oauth_code = code[0]
                self.wfile.write(
                    b"<h1>Success</h1><p>WhatsApp authenticated successfully! You can close this tab now.</p>"
                )
            else:
                self.wfile.write(b"<h1>Error</h1><p>Missing code parameter in redirect.</p>")
            self.server.should_stop = True
        else:
            self.send_response(404)
            self.end_headers()


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


@app.command("connect")
def connect(
    ctx: typer.Context,
    mode: WhatsAppMode = typer.Argument(
        ...,
        help="Connection mode: 'coexistence' (keep business app on phone) or 'embedded' (dedicated API number).",
    ),
    port: int = typer.Option(
        8085, "--port", "-p", help="Port to run the local OAuth callback server on."
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not attempt to open the browser automatically."
    ),
    no_system_user: bool = typer.Option(
        False, "--no-system-user", help="Do not create a permanent system user token."
    ),
) -> None:
    """Connect a WhatsApp account using Meta Embedded Signup / Coexistence OAuth flow."""
    state = get_state(ctx)

    if is_port_in_use(port):
        raise UserError(f"Port {port} is currently in use. Please choose another port with --port.")

    info("Fetching WhatsApp config from backend...")
    with state.client() as client:
        config = client.get_whatsapp_config()

    facebook_app_id = config.get("facebook_app_id")
    whatsapp_config_id = config.get("whatsapp_config_id")

    if not facebook_app_id:
        raise UserError("Facebook App ID is not configured on the backend.")

    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    server.oauth_code = None
    server.should_stop = False

    redirect_uri = f"http://localhost:{port}/callback"
    oauth_state = str(uuid.uuid4())
    extras = {"setup": {}, "sessionInfoVersion": 3}
    if mode == WhatsAppMode.coexistence:
        extras["featureType"] = "whatsapp_business_app_onboarding"

    params = {
        "client_id": facebook_app_id,
        "redirect_uri": redirect_uri,
        "state": oauth_state,
        "response_type": "code",
        "extras": json.dumps(extras),
    }

    if whatsapp_config_id:
        params["config_id"] = whatsapp_config_id

    oauth_url = f"https://www.facebook.com/v24.0/dialog/oauth?{urllib.parse.urlencode(params)}"

    info(f"Local callback server listening on {redirect_uri}...")
    info(f"Please open this URL in your browser to authenticate:\n\n{oauth_url}\n")

    if not no_browser:
        webbrowser.open(oauth_url)

    try:
        while not server.should_stop:
            server.handle_request()
    except KeyboardInterrupt:
        info("\nAborted.")
        raise typer.Exit(code=130)
    finally:
        server.server_close()

    if not server.oauth_code:
        raise UserError("Failed to receive authentication code from Facebook.")

    info("Authentication code received. Registering credentials with backend...")
    
    source = "coexistence" if mode == WhatsAppMode.coexistence else "embedded_signup"

    register_payload = {
        "code": server.oauth_code,
        "create_system_user": not no_system_user,
        "source": source,
    }

    with state.client() as client:
        result = client.register_whatsapp(register_payload)

    if state.json_mode:
        emit_json(result)
    else:
        success("WhatsApp credentials registered successfully!")
        render_table(
            result.get("whatsapp_credentials", []),
            WHATSAPP_CREDENTIALS_COLUMNS,
            title="Registered WhatsApp Accounts",
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
        if not typer.confirm(f"Are you sure you want to delete WhatsApp credentials ID {credentials_id}?"):
            raise typer.Exit(code=0)

    with state.client() as client:
        result = client.delete_whatsapp(credentials_id)

    if state.json_mode:
        emit_json(result)
    else:
        success(f"WhatsApp credentials ID {credentials_id} deleted successfully.")
