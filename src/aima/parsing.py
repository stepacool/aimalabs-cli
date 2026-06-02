"""Pure parsing helpers for CLI inputs — no I/O side effects beyond reading
files explicitly requested by the user (@path and CSV/stdin)."""

from __future__ import annotations

import sys
from pathlib import Path

from .errors import UserError

FIELD_TYPES = {
    "string", "integer", "float", "boolean", "date", "datetime",
    "calendar_appointment", "json", "array", "enum", "file",
}


def read_string_or_at_path(value: str | None) -> str | None:
    """Resolve a value that may be a literal string or an @path/to/file.

    A leading '@' means: read the file contents. '@-' reads stdin.
    """
    if value is None:
        return None
    if value.startswith("@"):
        ref = value[1:]
        if ref == "-":
            return sys.stdin.read()
        path = Path(ref).expanduser()
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise UserError(f"Cannot read {path}: {exc}") from exc
    return value


def read_file_or_stdin(path_str: str) -> str:
    """Read a file path, or stdin when path is '-'."""
    if path_str == "-":
        return sys.stdin.read()
    path = Path(path_str).expanduser()
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UserError(f"Cannot read {path}: {exc}") from exc


def parse_field_spec(token: str, order: int) -> dict:
    """Parse a --field token into a DesiredFieldInput dict.

    Format: `title:type:description`, with optional trailing `:values=a,b,c`
    for enum fields. `description` may itself contain colons.
    """
    values: list[str] | None = None
    work = token

    # Peel off an optional `:values=...` enum suffix first.
    marker = ":values="
    idx = work.find(marker)
    if idx != -1:
        values_raw = work[idx + len(marker):]
        work = work[:idx]
        values = [v.strip() for v in values_raw.split(",") if v.strip()]

    parts = work.split(":", 2)
    if len(parts) < 3:
        raise UserError(
            f"Bad --field '{token}'. Expected 'title:type:description' "
            "(append ':values=a,b,c' for enum)."
        )
    title, ftype, description = parts[0].strip(), parts[1].strip(), parts[2].strip()

    if not title:
        raise UserError(f"Bad --field '{token}': empty title.")
    if ftype not in FIELD_TYPES:
        raise UserError(
            f"Bad --field '{token}': unknown type '{ftype}'. "
            f"Valid types: {', '.join(sorted(FIELD_TYPES))}."
        )
    if not description:
        raise UserError(f"Bad --field '{token}': empty description.")

    field: dict = {
        "title": title,
        "type": ftype,
        "description": description,
        "order": order,
    }
    if ftype == "enum":
        if not values:
            raise UserError(
                f"Bad --field '{token}': enum requires ':values=a,b,c'."
            )
        field["meta"] = {"values": values}
    if ftype == "calendar_appointment":
        field["use_calendar"] = True
    return field


def parse_lead_spec(token: str) -> dict:
    """Parse a --lead token `Name:E164` into {name, phone_number}.

    The name may contain spaces but not a colon; the phone is the last
    colon-separated segment.
    """
    if ":" not in token:
        raise UserError(
            f"Bad --lead '{token}'. Expected 'Name:+E164', e.g. 'Jane Doe:+15551234567'."
        )
    name, _, phone = token.rpartition(":")
    name = name.strip()
    phone = phone.strip()
    if not name or not phone:
        raise UserError(f"Bad --lead '{token}': both name and phone are required.")
    return {"name": name, "phone_number": phone}


def parse_map_spec(token: str) -> tuple[str, str]:
    """Parse a --map token `FIELD=COL` into (field, column)."""
    if "=" not in token:
        raise UserError(f"Bad --map '{token}'. Expected 'field=column'.")
    field, _, col = token.partition("=")
    field = field.strip()
    col = col.strip()
    if not field or not col:
        raise UserError(f"Bad --map '{token}': both field and column are required.")
    return field, col
