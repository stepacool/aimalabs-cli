import pytest

from aima.errors import UserError
from aima.parsing import parse_field_spec, parse_lead_spec, parse_map_spec


def test_field_basic():
    f = parse_field_spec("budget:string:Ask their monthly budget.", order=1)
    assert f == {
        "title": "budget",
        "type": "string",
        "description": "Ask their monthly budget.",
        "order": 1,
    }


def test_field_description_with_colons():
    f = parse_field_spec("note:string:format is a:b:c", order=2)
    assert f["description"] == "format is a:b:c"


def test_field_enum_values():
    f = parse_field_spec("tier:enum:Which tier?:values=bronze,silver,gold", order=1)
    assert f["meta"] == {"values": ["bronze", "silver", "gold"]}
    assert f["description"] == "Which tier?"


def test_field_enum_requires_values():
    with pytest.raises(UserError):
        parse_field_spec("tier:enum:Which tier?", order=1)


def test_field_calendar_sets_use_calendar():
    f = parse_field_spec("slot:calendar_appointment:Book a demo.", order=1)
    assert f["use_calendar"] is True


def test_field_bad_type():
    with pytest.raises(UserError):
        parse_field_spec("x:notatype:desc", order=1)


def test_field_missing_parts():
    with pytest.raises(UserError):
        parse_field_spec("only:two", order=1)


def test_lead_basic():
    assert parse_lead_spec("Jane Doe:+15551234567") == {
        "name": "Jane Doe",
        "phone_number": "+15551234567",
    }


def test_lead_name_with_no_colon():
    with pytest.raises(UserError):
        parse_lead_spec("no phone here")


def test_map_basic():
    assert parse_map_spec("budget=Monthly Budget") == ("budget", "Monthly Budget")


def test_map_bad():
    with pytest.raises(UserError):
        parse_map_spec("noequals")
