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
