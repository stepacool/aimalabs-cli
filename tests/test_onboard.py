import json
from collections import deque

import pytest

from aima.cli import app
from aima.prompts import INBOUND_TEMPLATE

_ACCOUNT = {
    "id": 5,
    "display_phone_number": "+15550199",
    "title": "WA",
    "source": "embedded_signup",
}
_TEMPLATE = {"name": "hello", "language": "en", "status": "APPROVED", "category": "MARKETING"}
_CAMPAIGN = {
    "campaign_id": 9,
    "agent_id": 1,
    "title": "T",
    "campaign_type": "whatsapp",
    "desired_field_ids": [],
}


def _mock_whatsapp_onboard(httpx_mock, *, templates=None, cred_id=5):
    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp",
        json=[{**_ACCOUNT, "id": cred_id}],
    )
    httpx_mock.add_response(
        method="POST",
        url=f"https://api.test/api/cli/whatsapp/{cred_id}/validate",
        json={"valid": True},
    )
    httpx_mock.add_response(
        url=f"https://api.test/api/cli/whatsapp/{cred_id}/templates",
        json=[] if templates is None else templates,
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/campaigns",
        json={**_CAMPAIGN, "campaign_id": 9 if templates is not None else 11},
    )


def _patch_onboard_prompts(monkeypatch, *, selects=(), confirms=(), texts=(), rows=()):
    """Queue return values for Questionary wrappers used by onboard flows."""
    select_q = deque(selects)
    confirm_q = deque(confirms)
    text_q = deque(texts)
    row_q = deque(rows)

    def fake_select(_message, _choices, *, default=None):
        return select_q.popleft()

    def fake_confirm(_message, *, default=False):
        return confirm_q.popleft()

    def fake_text(_message, *, default="", validate=None):
        return text_q.popleft()

    def fake_row(_message, _rows, *, label, value_key, extra_choices=()):
        return row_q.popleft()

    for module in ("aima.commands.onboard", "aima.commands.onboard_whatsapp"):
        monkeypatch.setattr(f"{module}.ask_select", fake_select)
        monkeypatch.setattr(f"{module}.ask_confirm", fake_confirm)
        monkeypatch.setattr(f"{module}.ask_text", fake_text)
        monkeypatch.setattr(f"{module}.ask_row", fake_row)


def test_onboard_rejects_json_mode(configured, cli):
    result = cli(["--json", "onboard"])
    assert result.aima_exit == 1
    assert "interactive" in result.aima_stderr.lower()


def test_onboard_whatsapp_outbound_happy_path(configured, runner, httpx_mock, monkeypatch):
    monkeypatch.setattr("aima.commands.whatsapp_connect.time.sleep", lambda _seconds: None)
    _mock_whatsapp_onboard(httpx_mock, templates=[_TEMPLATE])
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/campaigns/9/test-leads",
        json=[{"lead_id": 42, "name": "Jane", "phone_number": "+15551234567"}],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/leads/42/initiate",
        json={
            "lead_id": 42,
            "conversation_id": 7,
            "message_status": "sent",
            "conversation_status": "no_response",
        },
    )
    httpx_mock.add_response(
        url="https://api.test/api/cli/leads/42/status",
        json={
            "lead_id": 42,
            "name": "Jane",
            "phone_number": "+15551234567",
            "values": None,
            "latest_call": None,
            "latest_conversation": {
                "conversation_id": 7,
                "status": "no_response",
                "latest_message_status": "sent",
                "latest_message_at": "2026-01-01T00:00:00",
            },
        },
    )

    _patch_onboard_prompts(
        monkeypatch,
        selects=["whatsapp", ("hello", "en")],
        confirms=[True, False, True],
        rows=[5],
        texts=["Camp", "Co", "", "Jane", "+15551234567"],
    )

    result = runner.invoke(app, ["--no-json", "onboard"])
    assert result.exit_code == 0, result.stdout + result.stderr
    body = json.loads(
        next(
            r.content
            for r in httpx_mock.get_requests()
            if r.url.path == "/api/cli/campaigns" and r.method == "POST"
        )
    )
    assert body["template_name"] == "hello"
    assert body["only_respond_to_initiated_conversations"] is False


@pytest.mark.parametrize(
    ("flow", "expect_inbound"),
    [
        ("template_inbound", True),
        ("connect_no_templates", True),
    ],
)
def test_onboard_whatsapp_inbound(
    configured, runner, httpx_mock, monkeypatch, flow, expect_inbound
):
    if flow == "connect_no_templates":
        monkeypatch.setattr("aima.commands.whatsapp_connect.time.sleep", lambda _seconds: None)
        httpx_mock.add_response(url="https://api.test/api/cli/whatsapp", json=[])
        httpx_mock.add_response(
            method="POST",
            url="https://api.test/api/cli/whatsapp/connect-sessions",
            json={
                "session_id": "sess-1",
                "connect_url": "https://app.test/connect/whatsapp/sess-1",
                "source": "embedded_signup",
                "status": "pending",
                "expires_in_seconds": 1800,
            },
        )
        httpx_mock.add_response(
            url="https://api.test/api/cli/whatsapp/connect-sessions/sess-1",
            json={
                "session_id": "sess-1",
                "status": "completed",
                "result": {
                    "whatsapp_credentials": [{**_ACCOUNT, "id": 3, "display_phone_number": "+1999"}]
                },
            },
        )
        httpx_mock.add_response(
            method="POST",
            url="https://api.test/api/cli/whatsapp/3/validate",
            json={"valid": True},
        )
        httpx_mock.add_response(url="https://api.test/api/cli/whatsapp/3/templates", json=[])
        httpx_mock.add_response(
            method="POST",
            url="https://api.test/api/cli/campaigns",
            json={**_CAMPAIGN, "campaign_id": 11},
        )
        _patch_onboard_prompts(
            monkeypatch,
            selects=["whatsapp", "embedded"],
            confirms=[True, False],
            texts=["Inbound Camp", "Co", ""],
        )
    else:
        _mock_whatsapp_onboard(httpx_mock, templates=[_TEMPLATE])
        _patch_onboard_prompts(
            monkeypatch,
            selects=["whatsapp", INBOUND_TEMPLATE],
            confirms=[True, False],
            rows=[5],
            texts=["Inbound Camp", "Co", ""],
        )

    result = runner.invoke(app, ["--no-json", "onboard"])
    assert result.exit_code == 0, result.stdout + result.stderr

    body = json.loads(
        next(
            r.content
            for r in httpx_mock.get_requests()
            if r.url.path == "/api/cli/campaigns" and r.method == "POST"
        )
    )
    assert body["only_respond_to_initiated_conversations"] is expect_inbound
    assert "template_name" not in body
    assert not [r for r in httpx_mock.get_requests() if r.url.path.endswith("/initiate")]


def test_onboard_whatsapp_decline_inbound_offers_exit(configured, runner, httpx_mock, monkeypatch):
    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp",
        json=[{**_ACCOUNT, "id": 2, "display_phone_number": "+1"}],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/2/validate",
        json={"valid": True},
    )
    httpx_mock.add_response(url="https://api.test/api/cli/whatsapp/2/templates", json=[])

    _patch_onboard_prompts(
        monkeypatch,
        selects=["whatsapp"],
        confirms=[True, False],
        rows=[2],
    )

    result = runner.invoke(app, ["--no-json", "onboard"])
    assert result.exit_code != 0 or "Meta Business Manager" in result.stdout + result.stderr
    assert not [r for r in httpx_mock.get_requests() if r.url.path == "/api/cli/campaigns"]
