"""`aima whatsapp connect ...` — register WhatsApp credentials via Meta OAuth."""

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
from ..output import emit_json, info, render_table, success

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
    ("waba_id", "WABA ID"),
    ("status", "Status"),
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
