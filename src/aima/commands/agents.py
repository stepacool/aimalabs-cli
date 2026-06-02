"""`aima agents ...`"""

from __future__ import annotations

import typer

from ..context import get_state
from ..errors import UserError
from ..output import emit_json, render_keyvalue, render_table
from ..parsing import read_string_or_at_path

app = typer.Typer(help="List, create, and update agents.", no_args_is_help=True)

LIST_COLUMNS = [
    ("agent_id", "ID"),
    ("name", "Name"),
    ("company_name", "Company"),
    ("language", "Lang"),
    ("selected_voice_id", "Voice"),
    ("created_at", "Created"),
]


@app.command("list")
def list_agents(
    ctx: typer.Context,
    limit: int = typer.Option(None, "--limit", "-n", min=1, max=200, help="Max rows (1..200)."),
) -> None:
    """List agents, newest first."""
    state = get_state(ctx)
    with state.client() as client:
        agents = client.list_agents(limit=limit)
    if state.json_mode:
        emit_json(agents)
    else:
        render_table(agents, LIST_COLUMNS, title=f"Agents ({len(agents)})")


@app.command("get")
def get_agent(
    ctx: typer.Context,
    agent_id: int = typer.Argument(..., help="Agent ID (from `agents list`)."),
) -> None:
    """Show a single agent, including its system prompt."""
    state = get_state(ctx)
    with state.client() as client:
        agent = client.get_agent(agent_id)
    if state.json_mode:
        emit_json(agent)
    else:
        render_keyvalue(agent, title=f"Agent {agent_id}")


@app.command("create")
def create_agent(
    ctx: typer.Context,
    name: str = typer.Option(None, "--name", help="Agent display name (required)."),
    company_name: str = typer.Option(None, "--company-name", help="Company name (required)."),
    language: str = typer.Option(None, "--language", "-l", help="ISO-639-1 code (default: en)."),
    system_prompt: str = typer.Option(
        None, "--system-prompt", help="Literal string or @path/to/file."
    ),
    voice_id: int = typer.Option(None, "--voice-id", help="selected_voice_id from `voices list`."),
) -> None:
    """Create a reusable agent that campaigns can be bound to."""
    state = get_state(ctx)

    if not name:
        raise UserError("--name is required.")
    if not company_name:
        raise UserError("--company-name is required.")

    body: dict = {"name": name, "company_name": company_name}
    if language is not None:
        body["language"] = language
    if system_prompt is not None:
        body["system_prompt"] = read_string_or_at_path(system_prompt)
    if voice_id is not None:
        body["selected_voice_id"] = voice_id

    with state.client() as client:
        result = client.create_agent(body)

    if state.json_mode:
        emit_json(result)
    else:
        render_keyvalue(result, title="Agent created")


@app.command("update")
def update_agent(
    ctx: typer.Context,
    agent_id: int = typer.Argument(..., help="Agent ID (from `agents list`)."),
    name: str = typer.Option(None, "--name", help="New display name."),
    company_name: str = typer.Option(None, "--company-name", help="New company name."),
    language: str = typer.Option(None, "--language", "-l", help="New ISO-639-1 code."),
    system_prompt: str = typer.Option(
        None, "--system-prompt", help="Literal string or @path/to/file."
    ),
    voice_id: int = typer.Option(None, "--voice-id", help="New selected_voice_id."),
) -> None:
    """Update an agent. Only the flags you pass are changed."""
    state = get_state(ctx)

    body: dict = {}
    if name is not None:
        body["name"] = name
    if company_name is not None:
        body["company_name"] = company_name
    if language is not None:
        body["language"] = language
    if system_prompt is not None:
        body["system_prompt"] = read_string_or_at_path(system_prompt)
    if voice_id is not None:
        body["selected_voice_id"] = voice_id

    if not body:
        raise UserError(
            "Nothing to update. Pass at least one of "
            "--name, --company-name, --language, --system-prompt, --voice-id."
        )

    with state.client() as client:
        result = client.update_agent(agent_id, body)

    if state.json_mode:
        emit_json(result)
    else:
        render_keyvalue(result, title=f"Agent {agent_id} updated")
