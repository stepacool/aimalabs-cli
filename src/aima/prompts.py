"""Interactive CLI prompts via Questionary.

Single import surface for commands. Maps user abort (None) and Ctrl+C to
typer.Exit so callers keep the same control flow as the old typer.prompt/confirm.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

import questionary
import typer
from questionary import Choice

T = TypeVar("T")

INBOUND_TEMPLATE = "__inbound__"


def _ask(question: questionary.Question) -> Any:
    try:
        return question.unsafe_ask(patch_stdout=True)
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None


def ask_text(
    message: str,
    *,
    default: str = "",
    validate: Callable[[str], bool | str] | None = None,
) -> str:
    """Free-text input; returns stripped string (empty allowed)."""
    result = _ask(
        questionary.text(
            message,
            default=default,
            validate=validate,
        )
    )
    if result is None:
        raise typer.Exit(code=0)
    return str(result).strip()


def ask_confirm(message: str, *, default: bool = False) -> bool:
    """Yes/no confirmation. Returns False when the user aborts."""
    result = _ask(questionary.confirm(message, default=default, auto_enter=True))
    if result is None:
        return False
    return bool(result)


def ask_select(
    message: str,
    choices: Sequence[Choice | str],
    *,
    default: Any | None = None,
) -> Any:
    """Pick one item from a list. Raises typer.Exit(0) on abort."""
    result = _ask(questionary.select(message, choices=list(choices), default=default))
    if result is None:
        raise typer.Exit(code=0)
    return result


def ask_row(
    message: str,
    rows: list[dict],
    *,
    label: Callable[[dict], str],
    value_key: str,
    extra_choices: Sequence[Choice] = (),
) -> Any:
    """Select one row by human label; returns row[value_key]."""
    if not rows and not extra_choices:
        raise ValueError("ask_row requires at least one row or extra choice")

    choices: list[Choice] = list(extra_choices)
    for row in rows:
        choices.append(Choice(title=label(row), value=row[value_key]))
    return ask_select(message, choices)
