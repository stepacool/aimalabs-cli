import json

from aima.cli import app


def test_usage_view_json(configured, runner, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/usage",
        json={
            "voice_minutes": {"used": 17.3, "total": 59.8},
            "whatsapp_leads": {"used": 12.0, "total": 250.0},
        },
    )
    result = runner.invoke(app, ["--json", "usage", "view"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["voice_minutes"] == {"used": 17.3, "total": 59.8}
    assert data["whatsapp_leads"] == {"used": 12.0, "total": 250.0}


def test_usage_view_human_omits_zero_whatsapp(configured, runner, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/usage",
        json={
            "voice_minutes": {"used": 10.0, "total": 100.0},
            "whatsapp_leads": {"used": 0.0, "total": 0.0},
        },
    )
    result = runner.invoke(app, ["--no-json", "usage", "view"])
    assert result.exit_code == 0
    assert "Voice minutes: 10 / 100" in result.stderr
    assert "WhatsApp" not in result.stderr


def test_usage_view_without_key(tmp_config, cli):
    result = cli(["usage", "view"])
    assert result.aima_exit == 3
