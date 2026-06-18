"""Tests for aima.prompts Questionary wrappers."""

from __future__ import annotations

import pytest
import typer

from aima import prompts


class _FakeQuestion:
    def __init__(self, result, *, raises: BaseException | None = None):
        self._result = result
        self._raises = raises

    def unsafe_ask(self, patch_stdout=False):
        if self._raises is not None:
            raise self._raises
        return self._result


def test_ask_text_returns_stripped(monkeypatch):
    monkeypatch.setattr(
        prompts.questionary,
        "text",
        lambda message, default="", validate=None: _FakeQuestion("  hello  "),
    )
    assert prompts.ask_text("Name") == "hello"


def test_ask_text_abort_exits(monkeypatch):
    monkeypatch.setattr(
        prompts.questionary,
        "text",
        lambda message, default="", validate=None: _FakeQuestion(None),
    )
    with pytest.raises(typer.Exit) as exc:
        prompts.ask_text("Name")
    assert exc.value.exit_code == 0


def test_ask_confirm_returns_bool(monkeypatch):
    monkeypatch.setattr(
        prompts.questionary,
        "confirm",
        lambda message, default=True, auto_enter=True: _FakeQuestion(True),
    )
    assert prompts.ask_confirm("Go?") is True


def test_ask_confirm_abort_returns_false(monkeypatch):
    monkeypatch.setattr(
        prompts.questionary,
        "confirm",
        lambda message, default=True, auto_enter=True: _FakeQuestion(None),
    )
    assert prompts.ask_confirm("Go?") is False


def test_ask_select_returns_value(monkeypatch):
    monkeypatch.setattr(
        prompts.questionary,
        "select",
        lambda message, choices, default=None: _FakeQuestion("voice"),
    )
    assert prompts.ask_select("Channel", ["voice", "whatsapp"]) == "voice"


def test_ask_select_abort_exits(monkeypatch):
    monkeypatch.setattr(
        prompts.questionary,
        "select",
        lambda message, choices, default=None: _FakeQuestion(None),
    )
    with pytest.raises(typer.Exit) as exc:
        prompts.ask_select("Channel", ["voice"])
    assert exc.value.exit_code == 0


def test_keyboard_interrupt_exits_130(monkeypatch):
    monkeypatch.setattr(
        prompts.questionary,
        "text",
        lambda message, default="", validate=None: _FakeQuestion(
            None, raises=KeyboardInterrupt()
        ),
    )
    with pytest.raises(typer.Exit) as exc:
        prompts.ask_text("Name")
    assert exc.value.exit_code == 130


def test_ask_row_builds_choices(monkeypatch):
    captured: dict = {}

    def fake_select(message, choices, *, default=None):
        captured["message"] = message
        captured["choices"] = choices
        return _FakeQuestion(42)

    monkeypatch.setattr(prompts, "ask_select", lambda message, choices, *, default=None: 42)
    rows = [{"id": 42, "title": "Main"}]
    value = prompts.ask_row("Pick", rows, label=lambda r: str(r["id"]), value_key="id")
    assert value == 42
