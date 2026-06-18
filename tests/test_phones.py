import json

from aima.cli import app


def test_phones_list_json(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/phones",
        json=[
            {
                "id": 42,
                "phone_e164": "+15551234001",
                "country_code": "1",
                "status": "assigned",
                "assignment_id": 7,
            }
        ],
    )

    result = runner.invoke(app, ["--json", "phones", "list"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["assignment_id"] == 7
    assert data[0]["phone_e164"] == "+15551234001"


def test_phones_available_human(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.test/api/cli/phones/available",
        json=[
            {
                "id": 99,
                "phone_e164": "+15559876543",
                "country_code": "1",
                "status": "available",
            }
        ],
    )

    result = runner.invoke(app, ["--no-json", "phones", "available"])

    assert result.exit_code == 0
    assert "+15559876543" in result.stdout
    assert "Available Phone Numbers" in result.stdout


def test_phones_rent_with_yes(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.test/api/cli/phones/rent",
        json={
            "assignment_id": 7,
            "phone_number_id": 42,
            "phone_e164": "+15551234001",
            "status": "assigned",
            "assignment_type": "rent",
            "monthly_price_cents": 1000,
        },
    )

    result = runner.invoke(app, ["--json", "phones", "rent", "42", "--yes"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["assignment_id"] == 7
    assert data["monthly_price_cents"] == 1000


def test_phones_release_with_yes(configured, runner, httpx_mock):
    httpx_mock.add_response(
        method="DELETE",
        url="https://api.test/api/cli/phones/7",
        json={
            "assignment_id": 7,
            "phone_e164": "+15551234001",
            "status": "ended",
        },
    )

    result = runner.invoke(app, ["--json", "phones", "release", "7", "--yes"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "ended"
    assert data["phone_e164"] == "+15551234001"
