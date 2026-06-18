"""Shared WhatsApp browser connect flow for CLI commands and onboard."""

from __future__ import annotations

import time
import webbrowser
from enum import StrEnum
from typing import Any

import typer

from ..errors import UserError
from ..output import info

POLL_INTERVAL_SECONDS = 3
DEFAULT_CONNECT_TIMEOUT_SECONDS = 30 * 60


class WhatsAppMode(StrEnum):
    coexistence = "coexistence"
    embedded = "embedded"


def mode_to_source(mode: WhatsAppMode) -> str:
    return "coexistence" if mode == WhatsAppMode.coexistence else "embedded_signup"


def poll_connect_session(client, session_id: str, timeout_seconds: int) -> dict:
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


def run_connect_flow(
    client,
    mode: WhatsAppMode,
    *,
    open_browser: bool = True,
    timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    json_mode: bool = False,
) -> dict[str, Any]:
    """Create session, optionally open browser, poll until complete.

    Returns the completed session status dict (includes result.whatsapp_credentials).
    """
    source = mode_to_source(mode)
    session = client.create_whatsapp_connect_session(source)
    connect_url = session["connect_url"]
    session_id = session["session_id"]

    info("Open this URL in your browser to connect WhatsApp:")
    info(f"\n{connect_url}\n")
    info(f"Session expires in {session.get('expires_in_seconds', 1800)} seconds.")

    if open_browser:
        webbrowser.open(connect_url)

    if json_mode:
        info("Waiting for connect to complete...")
    else:
        info("Waiting for connect to complete (Ctrl+C to stop polling)...")

    try:
        return poll_connect_session(client, session_id, timeout)
    except KeyboardInterrupt:
        info("\nStopped polling. The connect URL may still work until it expires.")
        raise typer.Exit(code=130) from None
