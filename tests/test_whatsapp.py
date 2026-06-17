import json
import threading
import time
import urllib.request
import pytest
from aima.cli import app


def test_whatsapp_connect_success(configured, runner, httpx_mock, monkeypatch):
    """Test standard whatsapp connection flow with a successful callback."""
    # 1. Mock the config endpoint
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp/config",
        json={"facebook_app_id": "12345", "whatsapp_config_id": "67890"},
    )

    # 2. Mock the register endpoint
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/register",
        json={
            "whatsapp_credentials": [
                {
                    "id": 1,
                    "display_phone_number": "+15550199",
                    "title": "My WA",
                    "waba_id": "waba123",
                    "status": "created",
                }
            ],
            "summary": {"created": 1, "updated": 0},
        },
    )

    browser_opened_url = []

    def mock_webbrowser_open(url):
        browser_opened_url.append(url)

        # Send callback request asynchronously using built-in urllib
        def send_callback():
            time.sleep(0.3)
            try:
                urllib.request.urlopen("http://localhost:8089/callback?code=testcode_abc")
            except Exception as e:
                print(f"Test callback failed: {e}")

        threading.Thread(target=send_callback, daemon=True).start()
        return True

    monkeypatch.setattr("webbrowser.open", mock_webbrowser_open)

    result = runner.invoke(
        app,
        ["--json", "whatsapp", "connect", "embedded", "--port", "8089"],
    )

    assert result.exit_code == 0

    # Assert correct parameters were in the login URL
    assert len(browser_opened_url) == 1
    opened_url = browser_opened_url[0]
    assert opened_url.startswith("https://www.facebook.com/v24.0/dialog/oauth")
    assert "client_id=12345" in opened_url
    assert "config_id=67890" in opened_url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8089%2Fcallback" in opened_url

    # Check request payload sent to the backend (mapped from embedded -> embedded_signup)
    register_request = next(
        r for r in httpx_mock.get_requests() if r.url.path == "/api/cli/whatsapp/register"
    )
    sent_payload = json.loads(register_request.content)
    assert sent_payload == {
        "code": "testcode_abc",
        "create_system_user": True,
        "source": "embedded_signup",
    }

    # Verify output data
    output_data = json.loads(result.stdout)
    assert len(output_data["whatsapp_credentials"]) == 1
    assert output_data["whatsapp_credentials"][0]["display_phone_number"] == "+15550199"


def test_whatsapp_connect_coexistence(configured, runner, httpx_mock, monkeypatch):
    """Test coexistence whatsapp connection flow."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp/config",
        json={"facebook_app_id": "12345", "whatsapp_config_id": "67890"},
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/register",
        json={
            "whatsapp_credentials": [
                {
                    "id": 2,
                    "display_phone_number": "+15550200",
                    "title": "Coexistence WA",
                    "waba_id": "waba456",
                    "status": "updated",
                }
            ],
            "summary": {"created": 0, "updated": 1},
        },
    )

    def mock_webbrowser_open(url):
        # Trigger callback immediately using built-in urllib
        def send_callback():
            time.sleep(0.3)
            try:
                urllib.request.urlopen("http://localhost:8090/callback?code=coexistence_code")
            except Exception as e:
                print(f"Test callback failed: {e}")

        threading.Thread(target=send_callback, daemon=True).start()
        return True

    monkeypatch.setattr("webbrowser.open", mock_webbrowser_open)

    result = runner.invoke(
        app,
        [
            "--json",
            "whatsapp",
            "connect",
            "coexistence",
            "--port",
            "8090",
            "--no-system-user",
        ],
    )

    assert result.exit_code == 0

    # Check request payload sent to the backend
    register_request = next(
        r for r in httpx_mock.get_requests() if r.url.path == "/api/cli/whatsapp/register"
    )
    sent_payload = json.loads(register_request.content)
    assert sent_payload == {
        "code": "coexistence_code",
        "create_system_user": False,
        "source": "coexistence",
    }


def test_whatsapp_connect_invalid_mode(configured, cli):
    """Test connect fails with invalid mode."""
    result = cli(
        ["whatsapp", "connect", "invalid-mode"],
    )
    assert result.aima_exit != 0
    assert "coexistence" in result.aima_stderr
    assert "embedded" in result.aima_stderr


def test_whatsapp_list_json(configured, runner, httpx_mock):
    """Test list command in JSON mode."""
    accounts = [
        {
            "id": 1,
            "display_phone_number": "+15550199",
            "title": "My WA",
            "waba_id": "waba123",
            "source": "embedded_signup",
        }
    ]
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp",
        json=accounts,
    )
    result = runner.invoke(app, ["--json", "whatsapp", "list"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert len(parsed) == 1
    assert parsed[0]["id"] == 1
    assert parsed[0]["source"] == "embedded_signup"


def test_whatsapp_list_text(configured, runner, httpx_mock):
    """Test list command in text mode."""
    accounts = [
        {
            "id": 1,
            "display_phone_number": "+15550199",
            "title": "My WA",
            "waba_id": "waba123",
            "source": "embedded_signup",
        }
    ]
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/whatsapp",
        json=accounts,
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "list"])
    assert result.exit_code == 0
    assert "WhatsApp Credentials (1)" in result.stdout
    assert "My WA" in result.stdout
    assert "+15550199" in result.stdout


def test_whatsapp_validate_success_json(configured, runner, httpx_mock):
    """Test validate command in JSON mode when credentials are valid."""
    validation_response = {
        "valid": True,
        "account_status": "APPROVED",
        "phone_number_status": "VERIFIED",
        "templates_count": 5,
        "message": "All good",
    }
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/1/validate",
        json=validation_response,
    )
    result = runner.invoke(app, ["--json", "whatsapp", "validate", "1"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["valid"] is True
    assert parsed["account_status"] == "APPROVED"


def test_whatsapp_validate_success_text(configured, runner, httpx_mock):
    """Test validate command in text mode when credentials are valid."""
    validation_response = {
        "valid": True,
        "account_status": "APPROVED",
        "phone_number_status": "VERIFIED",
        "templates_count": 5,
        "message": "All good",
    }
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/1/validate",
        json=validation_response,
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "validate", "1"])
    assert result.exit_code == 0
    assert "Validation Result (ID: 1)" in result.stdout
    assert "Credentials are valid and working." in result.stderr


def test_whatsapp_validate_failed(configured, runner, httpx_mock):
    """Test validate command when credentials are invalid."""
    validation_response = {
        "valid": False,
        "account_status": "SUSPENDED",
        "phone_number_status": "UNVERIFIED",
        "templates_count": 0,
        "message": "Token expired",
    }
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/whatsapp/1/validate",
        json=validation_response,
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "validate", "1"])
    assert result.exit_code == 0
    assert "Credentials validation failed." in result.stderr
    assert "Token expired" in result.stdout


def test_whatsapp_delete_yes(configured, runner, httpx_mock):
    """Test delete command with confirmation skipped (--yes)."""
    httpx_mock.add_response(
        method="DELETE",
        url="https://api.test/api/cli/whatsapp/1",
        json={"ok": True},
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "delete", "1", "--yes"])
    assert result.exit_code == 0
    assert "WhatsApp credentials ID 1 deleted successfully." in result.stderr


def test_whatsapp_delete_confirm_no(configured, runner, httpx_mock):
    """Test delete command when user confirms NO."""
    result = runner.invoke(app, ["--no-json", "whatsapp", "delete", "1"], input="n\n")
    assert result.exit_code == 0
    # No request should have been made to delete
    delete_reqs = [r for r in httpx_mock.get_requests() if r.method == "DELETE"]
    assert len(delete_reqs) == 0


def test_whatsapp_delete_confirm_yes(configured, runner, httpx_mock):
    """Test delete command when user confirms YES."""
    httpx_mock.add_response(
        method="DELETE",
        url="https://api.test/api/cli/whatsapp/1",
        json={"ok": True},
    )
    result = runner.invoke(app, ["--no-json", "whatsapp", "delete", "1"], input="y\n")
    assert result.exit_code == 0
    assert "WhatsApp credentials ID 1 deleted successfully." in result.stderr
    delete_reqs = [r for r in httpx_mock.get_requests() if r.method == "DELETE"]
    assert len(delete_reqs) == 1
