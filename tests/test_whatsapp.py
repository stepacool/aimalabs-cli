import json

from aima.cli import app


def test_whatsapp_connect_session_flow(configured, runner, httpx_mock, monkeypatch):
    """Test browser-link connect flow with Redis session polling."""
    create_response = {
        "session_id": "sess-abc",
        "connect_url": "https://app.test/connect/whatsapp/sess-abc",
        "source": "embedded_signup",
        "status": "pending",
        "expires_in_seconds": 1800,
    }
    pending_response = {
        "session_id": "sess-abc",
        "source": "embedded_signup",
        "status": "pending",
        "error": None,
        "result": None,
    }
    completed_response = {
        "session_id": "sess-abc",
        "source": "embedded_signup",
        "status": "completed",
        "error": None,
        "result": {
            "whatsapp_credentials": [
                {
                    "id": 1,
                    "display_phone_number": "+15550199",
                    "title": "My WA",
                    "waba_id": "waba123",
                    "status": "created",
                }
            ]
        },
    }

    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/connect-sessions",
        json=create_response,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp/connect-sessions/sess-abc",
        json=pending_response,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp/connect-sessions/sess-abc",
        json=completed_response,
    )

    opened_urls = []

    def mock_webbrowser_open(url):
        opened_urls.append(url)
        return True

    monkeypatch.setattr("webbrowser.open", mock_webbrowser_open)
    monkeypatch.setattr("aima.commands.whatsapp_connect.time.sleep", lambda _seconds: None)

    result = runner.invoke(app, ["--json", "whatsapp", "connect", "embedded"])

    assert result.exit_code == 0
    assert opened_urls == ["https://app.test/connect/whatsapp/sess-abc"]
    output_data = json.loads(result.stdout)
    assert output_data["status"] == "completed"


def test_whatsapp_connect_coexistence_source(configured, runner, httpx_mock, monkeypatch):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/connect-sessions",
        json={
            "session_id": "sess-coex",
            "connect_url": "https://app.test/connect/whatsapp/sess-coex",
            "source": "coexistence",
            "status": "pending",
            "expires_in_seconds": 1800,
        },
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp/connect-sessions/sess-coex",
        json={
            "session_id": "sess-coex",
            "source": "coexistence",
            "status": "completed",
            "error": None,
            "result": {"whatsapp_credentials": []},
        },
    )

    monkeypatch.setattr("webbrowser.open", lambda _url: True)
    monkeypatch.setattr("aima.commands.whatsapp_connect.time.sleep", lambda _seconds: None)

    result = runner.invoke(app, ["--json", "whatsapp", "connect", "coexistence"])

    assert result.exit_code == 0
    create_request = next(
        r
        for r in httpx_mock.get_requests()
        if r.url.path == "/api/cli/whatsapp/connect-sessions" and r.method == "POST"
    )
    assert json.loads(create_request.content) == {"source": "coexistence"}


def test_whatsapp_connect_invalid_mode(configured, runner):
    result = runner.invoke(app, ["whatsapp", "connect", "invalid-mode"])
    assert result.exit_code != 0
    assert "embedded" in (result.stdout + result.stderr).lower()


def test_whatsapp_list_json(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp",
        json=[
            {
                "id": 1,
                "display_phone_number": "+15550199",
                "title": "My WA",
                "whatsapp_business_account_id": "waba123",
                "source": "embedded_signup",
            }
        ],
    )
    result = runner.invoke(app, ["--json", "whatsapp", "list"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed[0]["source"] == "embedded_signup"


def test_whatsapp_list_text(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp",
        json=[
            {
                "id": 1,
                "display_phone_number": "+15550199",
                "title": "My WA",
                "whatsapp_business_account_id": "waba123",
                "source": "embedded_signup",
            }
        ],
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "list"])
    assert result.exit_code == 0
    assert "+15550199" in result.stdout


def test_whatsapp_validate_success_json(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/1/validate",
        json={
            "valid": True,
            "account_status": "APPROVED",
            "phone_number_status": "VERIFIED",
            "templates_count": 5,
            "message": "All credentials are valid and working",
        },
    )
    result = runner.invoke(app, ["--json", "whatsapp", "validate", "1"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["valid"] is True


def test_whatsapp_validate_success_text(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/1/validate",
        json={
            "valid": True,
            "account_status": "APPROVED",
            "phone_number_status": "VERIFIED",
            "templates_count": 5,
            "message": "All credentials are valid and working",
        },
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "validate", "1"])
    assert result.exit_code == 0
    assert "valid" in result.stdout.lower()


def test_whatsapp_validate_failed(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/1/validate",
        json={
            "valid": False,
            "account_status": "REJECTED",
            "phone_number_status": "UNVERIFIED",
            "templates_count": 0,
            "message": "Credentials validation failed",
        },
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "validate", "1"])
    assert result.exit_code == 0
    assert "failed" in result.stdout.lower()


def test_whatsapp_delete_yes(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="DELETE",
        url="https://api.test/api/cli/whatsapp/1",
        json={"ok": True},
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "delete", "1", "--yes"])
    assert result.exit_code == 0
    assert "deleted" in (result.stdout + result.stderr).lower()


def test_whatsapp_delete_confirm_no(configured, runner, httpx_mock):
    result = runner.invoke(app, ["--no-json", "whatsapp", "delete", "1"], input="n\n")
    assert result.exit_code == 0


def test_whatsapp_delete_confirm_yes(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="DELETE",
        url="https://api.test/api/cli/whatsapp/1",
        json={"ok": True},
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "delete", "1"], input="y\n")
    assert result.exit_code == 0
    assert "deleted" in (result.stdout + result.stderr).lower()


def test_whatsapp_templates_json(configured, runner, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/whatsapp/4/templates",
        json=[{"name": "hi", "language": "en", "status": "APPROVED", "category": "UTILITY"}],
    )
    result = runner.invoke(app, ["--json", "whatsapp", "templates", "4"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["name"] == "hi"
