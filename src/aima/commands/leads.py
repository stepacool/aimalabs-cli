"""`aima leads ...`"""

from __future__ import annotations

import csv
import io

import typer

from ..context import get_state
from ..errors import UserError
from ..output import emit_json, info, render_keyvalue, render_table
from ..parsing import parse_lead_spec, parse_map_spec, read_file_or_stdin

app = typer.Typer(help="Add test leads or bulk-upload from CSV.", no_args_is_help=True)

LEAD_COLUMNS = [
    ("lead_id", "Lead ID"),
    ("name", "Name"),
    ("phone_number", "Phone"),
]


@app.command("add-test")
def add_test(
    ctx: typer.Context,
    campaign_id: int = typer.Option(..., "--campaign-id", help="Target campaign id."),
    lead: list[str] = typer.Option(
        ..., "--lead", help="Repeatable: 'Name:+E164', e.g. 'Jane Doe:+15551234567'."
    ),
) -> None:
    """Add one or more test leads to a campaign (does not dispatch)."""
    state = get_state(ctx)
    leads = [parse_lead_spec(tok) for tok in lead]
    with state.client() as client:
        created = client.add_test_leads(campaign_id, leads)
    if state.json_mode:
        emit_json(created)
    else:
        render_table(created, LEAD_COLUMNS, title=f"Test leads added ({len(created)})")


@app.command("upload-csv")
def upload_csv(
    ctx: typer.Context,
    campaign_id: int = typer.Option(..., "--campaign-id", help="Target campaign id."),
    file: str = typer.Option(..., "--file", help="CSV path, or '-' for stdin."),
    name_col: str = typer.Option(..., "--name-col", help="CSV column holding the name."),
    phone_col: str = typer.Option(..., "--phone-col", help="CSV column holding the phone."),
    map_: list[str] = typer.Option(
        None, "--map", help="Repeatable: 'desired_field=csv_column'."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the >50-row confirmation."),
) -> None:
    """Bulk-create leads from a CSV file (read locally, posted inline)."""
    state = get_state(ctx)
    content = read_file_or_stdin(file)

    values_map = dict(parse_map_spec(tok) for tok in (map_ or []))
    mapping = {
        "name": name_col,
        "phone_number": phone_col,
        "values": values_map,
    }

    # Count data rows for the confirmation gate (header excluded).
    row_count = _count_data_rows(content)
    if row_count > 50 and not yes:
        if state.json_mode:
            raise UserError(
                f"Refusing to upload {row_count} leads non-interactively. "
                "Pass --yes to confirm."
            )
        if not typer.confirm(f"Upload {row_count} leads to campaign {campaign_id}?"):
            raise typer.Exit(code=0)

    with state.client() as client:
        result = client.upload_csv(campaign_id, content, mapping)

    if state.json_mode:
        emit_json(result)
    else:
        created = result.get("created")
        total = result.get("total_rows")
        info(f"Uploaded CSV to campaign {campaign_id}.")
        from ..output import success

        success(f"Created {created} of {total} rows.")


@app.command("initiate")
def initiate(
    ctx: typer.Context,
    lead_id: int = typer.Argument(..., help="Lead id to send the campaign template to."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Send the campaign's WhatsApp template to a lead (outbound WhatsApp campaigns only)."""
    state = get_state(ctx)
    if not yes:
        if state.json_mode:
            raise UserError(
                f"Refusing to initiate lead {lead_id} non-interactively. Pass --yes to confirm."
            )
        if not typer.confirm(f"Send WhatsApp template to lead {lead_id}?", default=False):
            raise typer.Exit(code=0)

    with state.client() as client:
        result = client.initiate_lead(lead_id)

    if state.json_mode:
        emit_json(result)
    else:
        render_keyvalue(result, title="Initiated")
        info(f"Watch status with: aima calls status {lead_id} --poll")


def _count_data_rows(content: str) -> int:
    try:
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
    except (csv.Error, ValueError):
        return 0
    # Drop header + any trailing blank lines.
    data = [r for r in rows[1:] if any(cell.strip() for cell in r)]
    return len(data)
