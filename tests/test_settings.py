import pytest
from expandvars import ExpandvarsException

from pyramid_niteo.settings import expandvars_dict, safe_eval


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("false", False),
        ("true", True),
        ("None", None),
        ("0", 0),
        ("1.2", 1.2),
        ("['a']", ["a"]),
        ("{'a': 1}", {"a": 1}),
        ("(1, 2)", (1, 2)),
        ("hello", "hello"),
        ("__import__('os').system('false')", "__import__('os').system('false')"),
    ],
)
def test_literal_compatibility(value, expected):
    assert safe_eval(value) == expected


def test_non_string_rejected():
    with pytest.raises(ValueError, match="Expected a string"):
        safe_eval(False)


def test_expansion(monkeypatch):
    monkeypatch.delenv("MISSING_NITEO", raising=False)
    monkeypatch.setenv("NESTED_NITEO", "prefix_${VALUE_NITEO}")
    monkeypatch.setenv("VALUE_NITEO", "value")
    original = {
        "default": "${MISSING_NITEO:-false}",
        "nested": "${NESTED_NITEO}",
        "required": "${VALUE_NITEO:?}",
        "integer": "${MISSING_NITEO:-5}",
    }
    assert expandvars_dict(original) == {
        "default": False,
        "nested": "prefix_value",
        "required": "value",
        "integer": 5,
    }
    assert original["integer"] == "${MISSING_NITEO:-5}"


def test_missing_required(monkeypatch):
    monkeypatch.delenv("MISSING_NITEO", raising=False)
    monkeypatch.delenv("EXPANDVARS_RECOVER_NULL", raising=False)
    with pytest.raises(ExpandvarsException):
        expandvars_dict({"secret": "${MISSING_NITEO:?required}"})
