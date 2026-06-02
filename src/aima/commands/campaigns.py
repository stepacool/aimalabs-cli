"""`aima campaigns ...`"""

from __future__ import annotations

import typer
import yaml

from ..context import get_state
from ..errors import UserError
from ..output import emit_json, render_keyvalue, render_table
from ..parsing import parse_field_spec, read_string_or_at_path

app = typer.Typer(help="List and create campaigns.", no_args_is_help=True)

CAMPAIGN_TYPES = {"voice", "whatsapp", "hybrid"}

LIST_COLUMNS = [
    ("campaign_id", "ID"),
    ("title", "Title"),
    ("campaign_type", "Type"),
    ("language", "Lang"),
    ("is_active", "Active"),
    ("company_name", "Company"),
    ("agent_name", "Agent"),
    ("selected_voice_id", "Voice"),
    ("created_at", "Created"),
]


@app.command("list")
def list_campaigns(
    ctx: typer.Context,
    active: bool = typer.Option(False, "--active", help="Only active campaigns."),
    inactive: bool = typer.Option(False, "--inactive", help="Only inactive campaigns."),
    limit: int = typer.Option(None, "--limit", "-n", min=1, max=200, help="Max rows (1..200)."),
) -> None:
    """List campaigns, newest first."""
    state = get_state(ctx)
    if active and inactive:
        raise UserError("--active and --inactive are mutually exclusive.")
    is_active = True if active else (False if inactive else None)
    with state.client() as client:
        campaigns = client.list_campaigns(is_active=is_active, limit=limit)
    if state.json_mode:
        emit_json(campaigns)
    else:
        render_table(campaigns, LIST_COLUMNS, title=f"Campaigns ({len(campaigns)})")


@app.command("create")
def create_campaign(
    ctx: typer.Context,
    title: str = typer.Option(None, "--title", help="Campaign name (required)."),
    company_name: str = typer.Option(None, "--company-name", help="Company name (required)."),
    voice_id: int = typer.Option(None, "--voice-id", help="selected_voice_id from `voices list`."),
    agent_name: str = typer.Option(None, "--agent-name", help="Agent display name."),
    language: str = typer.Option(None, "--language", "-l", help="ISO-639-1 code."),
    system_prompt: str = typer.Option(
        None, "--system-prompt", help="Literal string or @path/to/file."
    ),
    extra_context: str = typer.Option(
        None, "--extra-context", help="Literal string or @path/to/file."
    ),
    campaign_type: str = typer.Option(
        None, "--campaign-type", help="voice | whatsapp | hybrid."
    ),
    inactive: bool = typer.Option(False, "--inactive", help="Create as inactive."),
    field: list[str] = typer.Option(
        None, "--field", help="Repeatable: 'title:type:description' (':values=a,b' for enum)."
    ),
    from_yaml: str = typer.Option(
        None, "--from-yaml", help="YAML file with the full request body."
    ),
) -> None:
    """Create a campaign, its agent, and its extraction fields atomically."""
    state = get_state(ctx)

    body: dict = {}

    if from_yaml:
        loaded = read_string_or_at_path("@" + from_yaml)
        parsed = yaml.safe_load(loaded)
        if not isinstance(parsed, dict):
            raise UserError(f"--from-yaml {from_yaml} must contain a YAML mapping.")
        body.update(parsed)

    # Explicit flags overlay the YAML body (title always wins, per spec).
    if title is not None:
        body["title"] = title
    if company_name is not None:
        body["company_name"] = company_name
    if voice_id is not None:
        body["selected_voice_id"] = voice_id
    if agent_name is not None:
        body["agent_name"] = agent_name
    if language is not None:
        body["language"] = language
    if system_prompt is not None:
        body["system_prompt"] = read_string_or_at_path(system_prompt)
    if extra_context is not None:
        body["extra_context"] = read_string_or_at_path(extra_context)
    if campaign_type is not None:
        if campaign_type not in CAMPAIGN_TYPES:
            raise UserError(
                f"--campaign-type must be one of {', '.join(sorted(CAMPAIGN_TYPES))}."
            )
        body["campaign_type"] = campaign_type
    if inactive:
        body["is_active"] = False

    if field:
        body["desired_fields"] = [
            parse_field_spec(tok, order=i + 1) for i, tok in enumerate(field)
        ]

    # Validate required fields after merge.
    if not body.get("title"):
        raise UserError("--title is required (or provide it via --from-yaml).")
    if not body.get("company_name"):
        raise UserError("--company-name is required (or provide it via --from-yaml).")

    with state.client() as client:
        result = client.create_campaign(body)

    if state.json_mode:
        emit_json(result)
    else:
        render_keyvalue(result, title="Campaign created")


@app.command("update")
def update_campaign(
    ctx: typer.Context,
    campaign_id: int = typer.Argument(..., help="Campaign ID (from `campaigns list`)."),
    title: str = typer.Option(None, "--title", help="New campaign name."),
    agent_id: int = typer.Option(
        None, "--agent-id", help="Assign a different agent (from `agents list`)."
    ),
    extra_context: str = typer.Option(
        None, "--extra-context", help="Per-campaign prompt. Literal string or @path/to/file."
    ),
    active: bool = typer.Option(False, "--active", help="Activate the campaign."),
    inactive: bool = typer.Option(False, "--inactive", help="Pause the campaign."),
) -> None:
    """Update a campaign: retitle, reassign its agent, or edit its prompt."""
    state = get_state(ctx)

    if active and inactive:
        raise UserError("--active and --inactive are mutually exclusive.")

    body: dict = {}
    if title is not None:
        body["title"] = title
    if agent_id is not None:
        body["agent_id"] = agent_id
    if extra_context is not None:
        body["extra_context"] = read_string_or_at_path(extra_context)
    if active:
        body["is_active"] = True
    elif inactive:
        body["is_active"] = False

    if not body:
        raise UserError(
            "Nothing to update. Pass at least one of "
            "--title, --agent-id, --extra-context, --active/--inactive."
        )

    with state.client() as client:
        result = client.update_campaign(campaign_id, body)

    if state.json_mode:
        emit_json(result)
    else:
        render_keyvalue(result, title=f"Campaign {campaign_id} updated")
