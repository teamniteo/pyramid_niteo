"""Expand PasteDeploy settings before creating the Pyramid configurator."""

from ast import literal_eval
from collections.abc import Mapping
from typing import Any

from expandvars import expandvars


def safe_eval(text: str) -> Any:
    """Preserve pyramid-heroku's literal conversion, including true/false."""
    if not isinstance(text, str):
        raise ValueError(f"Expected a string, got {type(text)} instead.")
    if not text:
        return text
    try:
        return literal_eval(text[0].upper() + text[1:])
    except ValueError, SyntaxError:
        return text


def expandvars_dict(settings: Mapping[str, str]) -> dict[str, Any]:
    """Expand required/default/nested variables and convert Python literals.

    Two passes allow one level of nested substitution.
    Missing ${VAR:?} values raise expandvars.ExpandvarsException.
    """
    return {
        key: safe_eval(expandvars(expandvars(value))) for key, value in settings.items()
    }
