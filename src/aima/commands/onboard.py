"""`aima onboard` — interactive end-to-end walkthrough.

Minimal-confirmation policy: only the real call (and large CSVs, n/a here) is
gated behind an explicit prompt. Every other step announces one line, then runs.
"""

from __future__ import annotations

import typer
from questionary import Choice

from .. import config as cfg
from ..context import get_state
from ..errors import UserError
from ..output import info, render_table, success, warn
from ..prompts import ask_confirm, ask_row, ask_select, ask_text
from .calls import call_poll_done, call_poll_progress, poll_lead_status, render_lead_status
from .onboard_whatsapp import onboard_whatsapp
from .setup import init as run_init
from .voices import VOICE_COLUMNS


def onboard(ctx: typer.Context) -> None:
    """Run setup → channel pick → voice or WhatsApp walkthrough."""
    state = get_state(ctx)
    if state.json_mode:
        raise UserError("onboard is interactive; it cannot run in --json mode.")

    if not cfg.config_path().exists() or not state.config.has_api_key:
        info("No config yet — running init first.")
        run_init(ctx)
        state = get_state(ctx)

    channel = ask_select(
        "Channel",
        [
            Choice("Voice", value="voice"),
            Choice("WhatsApp", value="whatsapp"),
        ],
        default="voice",
    )
    if channel == "whatsapp":
        client = state.client()
        try:
            onboard_whatsapp(ctx, client)
        finally:
            client.close()
        return

    if channel != "voice":
        raise UserError("Channel must be 'voice' or 'whatsapp'.")

    _onboard_voice(ctx, state)


def _voice_label(voice: dict) -> str:
    voice_id = voice.get("id")
    title = voice.get("title") or "Untitled"
    provider = voice.get("provider") or "unknown"
    return f"{voice_id} — {title} ({provider})"


def _onboard_voice(ctx: typer.Context, state) -> None:
    client = state.client()
    try:
        info("Fetching voices…")
        voices = client.list_voices(is_active=True)
        if not voices:
            raise UserError("No active voices available.")
        render_table(voices, VOICE_COLUMNS, title=f"Voices ({len(voices)})")
        voice_id = ask_row(
            "Pick a voice",
            voices,
            label=_voice_label,
            value_key="id",
        )

        title = ask_text("Campaign title")
        company = ask_text("Company name")
        sys_prompt = ask_text("System prompt (blank for default)", default="")
        fields = _collect_fields()

        body = {
            "title": title,
            "company_name": company,
            "selected_voice_id": voice_id,
            "campaign_type": "voice",
        }
        if sys_prompt.strip():
            body["system_prompt"] = sys_prompt
        if fields:
            body["desired_fields"] = fields

        info("Creating campaign…")
        created = client.create_campaign(body)
        campaign_id = created.get("campaign_id")
        success(f"Campaign {campaign_id} created.")

        lead_name = ask_text("Test lead name")
        lead_phone = ask_text("Test lead phone (E.164, e.g. +15551234567)")
        info("Adding test lead…")
        leads = client.add_test_leads(
            campaign_id, [{"name": lead_name, "phone_number": lead_phone}]
        )
        if not leads:
            raise UserError("No lead was created.")
        lead_id = leads[0]["lead_id"]
        success(f"Lead {lead_id} added.")

        warn(f"This will place a REAL call to {lead_name} at {lead_phone}.")
        if not ask_confirm("Dispatch now?", default=False):
            info(f"Skipped. Dispatch later with: aima calls dispatch {lead_id}")
            return
        info("Dispatching…")
        client.dispatch(lead_id)

        info("Polling for up to 5 minutes…")
        state = get_state(ctx)
        result = poll_lead_status(
            client,
            lead_id,
            interval=20,
            timeout=300,
            is_done=call_poll_done,
            progress=call_poll_progress,
            json_mode=state.json_mode,
        )
        render_lead_status(result)
    finally:
        client.close()


def _collect_fields() -> list[dict]:
    """Optionally collect extraction fields, one per prompt loop."""
    fields: list[dict] = []
    if not ask_confirm("Add extraction fields?", default=False):
        return fields
    order = 1
    while True:
        ftitle = ask_text("  field title (blank to stop)", default="")
        if not ftitle.strip():
            break
        desc = ask_text("  description")
        fields.append(
            {"title": ftitle.strip(), "description": desc, "type": "string", "order": order}
        )
        order += 1
    return fields
