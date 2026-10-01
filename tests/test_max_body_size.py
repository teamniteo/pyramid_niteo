from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pyramid.exceptions import ConfigurationError
from pyramid.request import Request
from pyramid.response import Response

from pyramid_niteo.max_body_size import tween_factory

LIMIT = 100


class UnreadableBody:
    def read(self, *args):
        raise AssertionError("body must not be read")

    readline = readlines = __iter__ = read


def call(method, content_length, limit=LIMIT):
    view = Mock(return_value=Response())
    tween = tween_factory(
        view, SimpleNamespace(settings={"niteo.max_body_size": limit})
    )
    request = Request.blank("/", method=method)
    request.body_file_raw = UnreadableBody()
    request.content_length = content_length
    return tween(request), view


@pytest.mark.parametrize("method", ["PATCH", "POST", "PUT"])
@pytest.mark.parametrize("content_length", [0, LIMIT])
def test_body_within_limit_passes(method, content_length):
    response, view = call(method, content_length)
    assert response.status_code == 200
    view.assert_called_once()


@pytest.mark.parametrize("method", ["PATCH", "POST", "PUT"])
@pytest.mark.parametrize(
    ("content_length", "status"), [(LIMIT + 1, 413), (10**12, 413), (None, 411)]
)
def test_rejected_body_is_never_read(method, content_length, status):
    response, view = call(method, content_length)
    assert response.status_code == status
    view.assert_not_called()


@pytest.mark.parametrize("method", ["DELETE", "GET", "HEAD", "OPTIONS"])
@pytest.mark.parametrize("content_length", [None, LIMIT + 1])
def test_methods_without_body_pass(method, content_length):
    response, view = call(method, content_length)
    assert response.status_code == 200
    view.assert_called_once()


@pytest.mark.parametrize("limit", [100, "100"])
def test_limit_accepts_expanded_and_raw_settings(limit):
    assert call("POST", 100, limit)[0].status_code == 200
    assert call("POST", 101, limit)[0].status_code == 413


def test_zero_limit_allows_only_empty_bodies():
    assert call("POST", 0, 0)[0].status_code == 200
    assert call("POST", 1, 0)[0].status_code == 413


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({}, "must be set to an integer"),
        ({"niteo.max_body_size": "11 MB"}, "must be set to an integer"),
        ({"niteo.max_body_size": 1.5}, "must be set to an integer"),
        ({"niteo.max_body_size": "1.5"}, "must be set to an integer"),
        ({"niteo.max_body_size": True}, "must be set to an integer"),
        ({"niteo.max_body_size": None}, "must be set to an integer"),
        ({"niteo.max_body_size": -1}, "must be >= 0"),
    ],
)
def test_invalid_limit_fails_at_startup(settings, message):
    with pytest.raises(ConfigurationError, match=message):
        tween_factory(Mock(), SimpleNamespace(settings=settings))
