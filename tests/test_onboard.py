import json

from aima.cli import app


def test_onboard_rejects_json_mode(configured, cli):
    result = cli(["--json", "onboard"])
    assert result.aima_exit == 1
    assert "interactive" in result.aima_stderr.lower()


def test_onboard_whatsapp_outbound_happy_path(configured, runner, httpx_mock, monkeypatch):
    monkeypatch.setattr("aima.commands.whatsapp_connect.time.sleep", lambda _seconds: None)

    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp",
        json=[
            {
                "id": 5,
                "display_phone_number": "+15550199",
                "title": "WA",
                "whatsapp_business_account_id": "waba",
                "source": "embedded_signup",
            }
        ],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/5/validate",
        json={"valid": True, "message": "ok"},
    )
    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp/5/templates",
        json=[{"name": "hello", "language": "en", "status": "APPROVED", "category": "MARKETING"}],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/campaigns",
        json={
            "campaign_id": 9,
            "agent_id": 1,
            "title": "T",
            "campaign_type": "whatsapp",
            "desired_field_ids": [],
        },
    )
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

    result = runner.invoke(
        app,
        ["--no-json", "onboard"],
        input="\n".join(
            [
                "whatsapp",
                "y",
                "5",
                "1",
                "Camp",
                "Co",
                "",
                "n",
                "Jane",
                "+15551234567",
                "y",
            ]
        )
        + "\n",
    )
    assert result.exit_code == 0, result.stdout + result.stderr

    campaign_requests = [
        r
        for r in httpx_mock.get_requests()
        if r.url.path == "/api/cli/campaigns" and r.method == "POST"
    ]
    assert len(campaign_requests) == 1
    body = json.loads(campaign_requests[0].content)
    assert body["campaign_type"] == "whatsapp"
    assert body["whatsapp_credentials_id"] == 5
    assert body["template_name"] == "hello"
    assert body["only_respond_to_initiated_conversations"] is False


def test_onboard_whatsapp_inbound_when_templates_exist(configured, runner, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp",
        json=[
            {
                "id": 5,
                "display_phone_number": "+15550199",
                "title": "WA",
                "source": "embedded_signup",
            }
        ],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/5/validate",
        json={"valid": True},
    )
    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp/5/templates",
        json=[{"name": "hello", "language": "en", "status": "APPROVED", "category": "MARKETING"}],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/campaigns",
        json={
            "campaign_id": 12,
            "agent_id": 1,
            "title": "In",
            "campaign_type": "whatsapp",
            "desired_field_ids": [],
        },
    )

    result = runner.invoke(
        app,
        ["--no-json", "onboard"],
        input="\n".join(["whatsapp", "y", "5", "0", "Inbound Camp", "Co", "", "n"]) + "\n",
    )
    assert result.exit_code == 0, result.stdout + result.stderr

    body = json.loads(
        next(
            r.content
            for r in httpx_mock.get_requests()
            if r.url.path == "/api/cli/campaigns" and r.method == "POST"
        )
    )
    assert body["only_respond_to_initiated_conversations"] is True
    assert "template_name" not in body


def test_onboard_whatsapp_inbound_when_no_templates(configured, runner, httpx_mock):
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
                "whatsapp_credentials": [
                    {
                        "id": 3,
                        "display_phone_number": "+1999",
                        "title": "WA",
                        "waba_id": "w",
                        "status": "created",
                    }
                ]
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
        json={
            "campaign_id": 11,
            "agent_id": 1,
            "title": "In",
            "campaign_type": "whatsapp",
            "desired_field_ids": [],
        },
    )

    result = runner.invoke(
        app,
        ["--no-json", "onboard"],
        input="\n".join(
            [
                "whatsapp",
                "embedded",
                "y",
                "Inbound Camp",
                "Co",
                "",
                "n",
            ]
        )
        + "\n",
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "inbound" in result.stdout.lower() or "message" in result.stdout.lower()

    initiate_calls = [r for r in httpx_mock.get_requests() if r.url.path.endswith("/initiate")]
    assert initiate_calls == []


def test_onboard_whatsapp_decline_inbound_offers_exit(configured, runner, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp",
        json=[{"id": 2, "display_phone_number": "+1", "title": "WA", "source": "embedded_signup"}],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/2/validate",
        json={"valid": True},
    )
    httpx_mock.add_response(url="https://api.test/api/cli/whatsapp/2/templates", json=[])

    result = runner.invoke(
        app,
        ["--no-json", "onboard"],
        input="\n".join(["whatsapp", "y", "2", "n"]) + "\n",
    )
    assert result.exit_code != 0 or "Meta Business Manager" in result.stdout + result.stderr

    campaign_calls = [r for r in httpx_mock.get_requests() if r.url.path == "/api/cli/campaigns"]
    assert campaign_calls == []


def test_whatsapp_templates_json(configured, runner, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp/4/templates",
        json=[{"name": "hi", "language": "en", "status": "APPROVED", "category": "UTILITY"}],
    )
    result = runner.invoke(app, ["--json", "whatsapp", "templates", "4"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["name"] == "hi"
