"""WhatsApp branch of `aima onboard`."""

from __future__ import annotations

import time
from typing import Literal

import typer

from ..errors import UserError
from ..output import info, render_keyvalue, render_table, success, warn
from .whatsapp import TEMPLATE_PICK_COLUMNS, WHATSAPP_CREDENTIALS_COLUMNS
from .whatsapp_connect import WhatsAppMode, run_connect_flow

_TERMINAL_MESSAGE_STATUSES = frozenset({"sent", "delivered"})
_PRE_SEND_CONVERSATION_STATUSES = frozenset({"not_started", "failed_to_start"})


def resolve_whatsapp_mode(
    client,
    credentials_id: int,
) -> tuple[Literal["outbound", "inbound"], tuple[str, str] | None]:
    """Pick outbound template by #, inbound-only via 0, or confirm when none exist."""
    info("Fetching approved templates…")
    templates = client.list_whatsapp_templates(credentials_id)
    if templates:
        indexed = [{**template, "#": index} for index, template in enumerate(templates, start=1)]
        render_table(indexed, TEMPLATE_PICK_COLUMNS, title=f"Templates ({len(templates)})")
        info(
            "Enter 0 for inbound-only "
            "(agent replies when contacts message you — no outbound template)."
        )
        pick = typer.prompt("Pick template #", type=int)
        if pick == 0:
            return "inbound", None
        if pick < 1 or pick > len(templates):
            raise UserError(
                f"Template # must be 0 (inbound-only) or between 1 and {len(templates)}."
            )
        selected = templates[pick - 1]
        return "outbound", (selected["name"], selected["language"])

    warn("No approved message templates found.")
    if typer.confirm(
        "Set up inbound-only campaign instead? "
        "(agent replies when contacts message you — no template needed)",
        default=True,
    ):
        return "inbound", None

    raise UserError(
        "No approved templates available. Create and approve a template in "
        "Meta Business Manager, then run `aima onboard` again."
    )


def _resolve_credentials_id(client, *, json_mode: bool) -> tuple[int, str | None]:
    accounts = client.list_whatsapp()
    for account in accounts:
        if "source" not in account:
            account["source"] = account.get("status", "embedded_signup")

    if accounts:
        render_table(
            accounts,
            WHATSAPP_CREDENTIALS_COLUMNS,
            title=f"WhatsApp Credentials ({len(accounts)})",
        )
        if typer.confirm("Use an existing WhatsApp account?", default=True):
            cred_id = typer.prompt("Credentials ID", type=int)
            phone = next(
                (a.get("display_phone_number") for a in accounts if a.get("id") == cred_id),
                None,
            )
            return cred_id, phone

    info("No WhatsApp account selected — starting browser connect.")
    mode_answer = (
        typer.prompt("Connect mode (embedded/coexistence)", default="embedded").strip().lower()
    )
    if mode_answer not in ("embedded", "coexistence"):
        raise UserError("Connect mode must be 'embedded' or 'coexistence'.")
    mode = WhatsAppMode.embedded if mode_answer == "embedded" else WhatsAppMode.coexistence

    result = run_connect_flow(client, mode, json_mode=json_mode)
    credentials = (result.get("result") or {}).get("whatsapp_credentials") or []
    if not credentials:
        raise UserError("Connect completed but no credentials were returned.")

    if len(credentials) == 1:
        cred = credentials[0]
        return cred["id"], cred.get("display_phone_number")

    render_table(credentials, WHATSAPP_CREDENTIALS_COLUMNS, title="Connected WhatsApp Accounts")
    cred_id = typer.prompt("Pick credentials ID", type=int)
    phone = next(
        (c.get("display_phone_number") for c in credentials if c.get("id") == cred_id),
        None,
    )
    return cred_id, phone


def _poll_whatsapp(ctx, client, lead_id: int, *, interval: int = 20, timeout: int = 300) -> dict:
    from ..context import get_state

    state = get_state(ctx)
    deadline = time.monotonic() + timeout
    result = client.lead_status(lead_id)
    while True:
        conv = result.get("latest_conversation") or {}
        msg_status = conv.get("latest_message_status")
        conv_status = conv.get("status")
        if msg_status in _TERMINAL_MESSAGE_STATUSES:
            return result
        if conv_status and conv_status not in _PRE_SEND_CONVERSATION_STATUSES:
            return result
        if time.monotonic() >= deadline:
            if not state.json_mode:
                warn(f"Poll timed out after {timeout}s; message may still be in flight.")
            return result
        if not state.json_mode:
            info(
                f"… conversation={conv_status or 'pending'} "
                f"message={msg_status or 'pending'}; re-checking in {interval}s"
            )
        remaining = deadline - time.monotonic()
        time.sleep(min(interval, max(0.0, remaining)))
        result = client.lead_status(lead_id)


def _render_whatsapp_status(result: dict) -> None:
    head = {k: result.get(k) for k in ("lead_id", "name", "phone_number")}
    render_keyvalue(head, title="Lead")
    conv = result.get("latest_conversation")
    if conv:
        render_keyvalue(conv, title="Latest conversation")
        if conv.get("latest_message_status") in _TERMINAL_MESSAGE_STATUSES:
            success(f"Template message {conv.get('latest_message_status')}.")


def onboard_whatsapp(ctx: typer.Context, client) -> None:
    from .onboard import _collect_fields

    credentials_id, display_phone = _resolve_credentials_id(client, json_mode=False)

    info(f"Validating WhatsApp credentials {credentials_id}…")
    client.validate_whatsapp(credentials_id)

    mode, template = resolve_whatsapp_mode(client, credentials_id)

    title = typer.prompt("Campaign title")
    company = typer.prompt("Company name")
    sys_prompt = typer.prompt("System prompt (blank for default)", default="", show_default=False)
    fields = _collect_fields()

    body: dict = {
        "title": title,
        "company_name": company,
        "campaign_type": "whatsapp",
        "whatsapp_credentials_id": credentials_id,
    }
    if sys_prompt.strip():
        body["system_prompt"] = sys_prompt
    if fields:
        body["desired_fields"] = fields

    if mode == "outbound":
        assert template is not None
        template_name, template_language = template
        body["template_name"] = template_name
        body["template_language"] = template_language
        body["only_respond_to_initiated_conversations"] = False
    else:
        body["only_respond_to_initiated_conversations"] = True

    info("Creating campaign…")
    created = client.create_campaign(body)
    campaign_id = created.get("campaign_id")
    success(f"Campaign {campaign_id} created.")

    if mode == "inbound":
        phone = display_phone or "(see `aima whatsapp list`)"
        success(
            f"Inbound-only campaign ready. Message {phone} from WhatsApp to test — "
            "the agent will reply when you write first."
        )
        return

    assert template is not None
    template_name, template_language = template
    lead_name = typer.prompt("Test lead name")
    lead_phone = typer.prompt("Test lead phone (E.164, e.g. +15551234567)")
    info("Adding test lead…")
    leads = client.add_test_leads(campaign_id, [{"name": lead_name, "phone_number": lead_phone}])
    if not leads:
        raise UserError("No lead was created.")
    lead_id = leads[0]["lead_id"]
    success(f"Lead {lead_id} added.")

    warn(
        f"This will send template '{template_name}' ({template_language}) "
        f"to {lead_name} at {lead_phone}."
    )
    if not typer.confirm("Send template now?", default=False):
        info(f"Skipped. Send later with: aima leads initiate {lead_id}")
        return

    info("Sending template…")
    client.initiate_lead(lead_id)

    info("Polling for up to 5 minutes…")
    result = _poll_whatsapp(ctx, client, lead_id, interval=20, timeout=300)
    _render_whatsapp_status(result)
