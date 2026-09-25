from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pyramid.exceptions import ConfigurationError
from pyramid.request import Request
from pyramid.response import Response

from pyramid_niteo.uniform_response_time import tween_factory

SETTINGS = {
    "niteo.response_padding_ms": 1000,
    "niteo.padded_paths": "/forgot /register /password",
}


@pytest.mark.parametrize(
    ("method", "path", "status", "elapsed", "expected"),
    [
        ("POST", "/forgot", 200, 0.2, 0.8),
        ("POST", "/forgot", 401, 0.2, 0.8),
        ("POST", "/register", 200, 1.5, None),
        ("POST", "/password", 401, 0.25, 0.75),
        ("POST", "/password", 200, 0.2, 0.8),
        ("GET", "/forgot", 200, 0.2, None),
        ("POST", "/other", 200, 0.2, None),
    ],
)
@pytest.mark.parametrize("floor_ms", [1000, "1000"])
def test_padding(monkeypatch, method, path, status, elapsed, expected, floor_ms):
    sleep = Mock()
    monkeypatch.setattr("pyramid_niteo.uniform_response_time.time.sleep", sleep)
    monotonic = Mock(side_effect=[10, 10 + elapsed])
    monkeypatch.setattr("pyramid_niteo.uniform_response_time.time.monotonic", monotonic)
    response = Response(status=status)
    handler = Mock(return_value=response)
    tween = tween_factory(
        handler,
        SimpleNamespace(settings={**SETTINGS, "niteo.response_padding_ms": floor_ms}),
    )
    request = Request.blank(path, method=method)
    assert tween(request) is response
    handler.assert_called_once_with(request)
    if expected is None:
        sleep.assert_not_called()
    else:
        assert sleep.call_args.args[0] == pytest.approx(expected)
        sleep.assert_called_once()


def test_disabled_by_default(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr("pyramid_niteo.uniform_response_time.time.sleep", sleep)
    tween_factory(lambda request: Response(), SimpleNamespace(settings={}))(
        Request.blank("/forgot", method="POST")
    )
    sleep.assert_not_called()


@pytest.mark.parametrize("floor", [-1, "nan", "inf", "invalid", None, 1.5, "1.5", True])
def test_bad_floor(make_app, floor):
    with pytest.raises(ConfigurationError, match="niteo.response_padding_ms"):
        make_app(["uniform_response_time"], {"niteo.response_padding_ms": floor})


def test_bad_path(make_app):
    with pytest.raises(ConfigurationError, match="must start with"):
        make_app(["uniform_response_time"], {"niteo.padded_paths": "forgot"})
