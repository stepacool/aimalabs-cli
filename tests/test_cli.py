import json

from aima.cli import app


def test_exit_3_without_key(tmp_config, cli):
    result = cli(["voices", "list"])
    assert result.aima_exit == 3


def test_config_show_works_without_key(tmp_config, runner):
    result = runner.invoke(app, ["--json", "config", "show"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["api_key"] == "(not set)"


def test_voices_list_json(configured, runner, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/voices?is_active=true",
        json=[{"id": 42, "title": "Sarah", "provider": "eleven_labs",
               "voice_type": "generic", "languages": ["en"], "sample_url": None,
               "description": None, "is_system": True}],
    )
    result = runner.invoke(app, ["--json", "voices", "list"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["id"] == 42


def test_no_active_sends_false(configured, runner, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/voices?is_active=false", json=[]
    )
    result = runner.invoke(app, ["--json", "voices", "list", "--no-active"])
    assert result.exit_code == 0


def test_401_exit_1(configured, cli, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/voices?is_active=true",
        status_code=401,
        json={"detail": "nope"},
    )
    result = cli(["--json", "voices", "list"])
    assert result.aima_exit == 1
    assert "aima init" in result.aima_stderr


def test_422_flattened_exit_1(configured, cli, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/campaigns",
        status_code=422,
        json={"detail": [{"loc": ["body", "title"], "msg": "field required",
                          "type": "value_error.missing"}]},
    )
    result = cli(
        ["--json", "campaigns", "create", "--title", "T", "--company-name", "C"]
    )
    assert result.aima_exit == 1
    assert "title" in result.aima_stderr
    assert "field required" in result.aima_stderr


def test_5xx_exit_2(configured, cli, httpx_mock):
    httpx_mock.add_response(
        url="https://api.test/api/cli/voices?is_active=true",
        status_code=503,
        json={"detail": "down"},
    )
    result = cli(["--json", "voices", "list"])
    assert result.aima_exit == 2


def test_campaign_create_builds_body(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/campaigns",
        json={"campaign_id": 17, "agent_id": 9, "title": "T",
              "campaign_type": "voice", "desired_field_ids": [101]},
    )
    result = runner.invoke(app, [
        "--json", "campaigns", "create",
        "--title", "T", "--company-name", "Acme", "--voice-id", "42",
        "--field", "tier:enum:Which tier?:values=a,b",
    ])
    assert result.exit_code == 0
    sent = json.loads(httpx_mock.get_requests()[0].content)
    assert sent["title"] == "T"
    assert sent["company_name"] == "Acme"
    assert sent["selected_voice_id"] == 42
    assert sent["desired_fields"][0]["meta"] == {"values": ["a", "b"]}


def test_add_test_lead_strips_and_sends(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/campaigns/17/test-leads",
        json=[{"lead_id": 501, "name": "Jane Doe", "phone_number": "15551234567"}],
    )
    result = runner.invoke(app, [
        "--json", "leads", "add-test", "--campaign-id", "17",
        "--lead", "Jane Doe:+15551234567",
    ])
    assert result.exit_code == 0
    sent = json.loads(httpx_mock.get_requests()[0].content)
    assert sent["leads"][0] == {"name": "Jane Doe", "phone_number": "+15551234567"}


def test_dispatch_refuses_without_yes_noninteractive(configured, cli):
    # Non-interactive (--json) with no --yes must fail closed (no call placed).
    result = cli(["--json", "calls", "dispatch", "501"])
    assert result.aima_exit == 1
    assert "--yes" in result.aima_stderr


def test_dispatch_with_yes_calls_api(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/leads/501/dispatch",
        json={"call_id": 9001, "lead_id": 501, "status": "initiated"},
    )
    result = runner.invoke(app, ["--json", "calls", "dispatch", "501", "--yes"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["call_id"] == 9001


def test_version(runner):
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "aima" in result.stdout
