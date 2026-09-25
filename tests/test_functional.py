"""Exercise installed tweens together, including real transaction completion."""

from itertools import combinations
from unittest.mock import Mock

import pytest
from pyramid.config import Configurator
from pyramid.interfaces import ITweens
from pyramid.response import Response
from pyramid.tweens import EXCVIEW
from webtest import TestApp

from pyramid_niteo._ordering import (
    ACCESS,
    CLIENT,
    MALFORMED,
    OPENAPI,
    RELEASE,
    SECURITY,
    TIMING,
    TRANSACTION,
    XDEV,
)

MODULES = [
    "security_headers",
    "release_version",
    "xdev",
    "malformed_request",
    "client_addr",
    "flydev_access",
    "uniform_response_time",
]
NAMES = [SECURITY, RELEASE, XDEV, MALFORMED, CLIENT, ACCESS, TIMING]
SUBSETS = [
    subset
    for size in range(len(MODULES) + 1)
    for subset in combinations(MODULES, size)
    if "flydev_access" not in subset or "client_addr" in subset
]


@pytest.mark.parametrize("modules", SUBSETS)
@pytest.mark.parametrize("reverse", [False, True])
def test_optional_combinations_respect_dependencies(make_app, modules, reverse):
    app = make_app(list(reversed(modules)) if reverse else modules)
    names = [name for name, _ in app.app.registry.getUtility(ITweens).implicit()]
    assert set(names) == {
        name for module, name in zip(MODULES, NAMES, strict=True) if module in modules
    } | {EXCVIEW}
    assert_required_order(names)
    response = app.get("/")
    assert ("Content-Security-Policy" in response.headers) == (
        "security_headers" in modules
    )
    assert ("X-Release-Version" in response.headers) == ("release_version" in modules)
    assert ("X-Dev" in response.headers) == ("xdev" in modules)
    assert (response.json["nonce"] is not None) == ("security_headers" in modules)


@pytest.mark.parametrize(
    ("path", "headers", "environ", "status"),
    [
        ("/unauthorized", {}, {}, 401),
        ("/", {"Host": "app.fly.dev"}, {}, 403),
        ("/", {"Fly-Client-IP": "bad"}, {}, 400),
        ("/", {}, {"PATH_INFO": "/\xff"}, 404),
    ],
)
def test_headers_on_early_and_exception_responses(
    make_app, path, headers, environ, status
):
    response = make_app(reversed(MODULES)).get(
        path,
        headers=headers,
        extra_environ=environ,
        status=status,
    )
    assert (
        response.headers["X-Release-Version"]
        == "0123456789abcdef0123456789abcdef01234567"
    )
    assert "nonce-" in response.headers["Content-Security-Policy"]
    assert "niteo.co/careers" in response.headers["X-Dev"]


def test_malformed_request_never_calls_view(make_app):
    view = Mock(side_effect=AssertionError("view must not run"))
    make_app(["malformed_request"], view=view).get(
        "/",
        extra_environ={"PATH_INFO": "/\xff"},
        status=404,
    )
    view.assert_not_called()


def test_timing_includes_real_transaction_commit(monkeypatch):
    events = []
    now = [0.0]
    monkeypatch.setattr(
        "pyramid_niteo.uniform_response_time.time.monotonic", lambda: now[0]
    )
    monkeypatch.setattr(
        "pyramid_niteo.uniform_response_time.time.sleep",
        lambda seconds: events.append(("sleep", seconds)),
    )
    config = Configurator(
        settings={
            "niteo.response_padding_ms": 1000,
            "niteo.padded_paths": "/forgot",
            "tm.manager_hook": "pyramid_tm.explicit_manager",
        }
    )
    config.include("pyramid_niteo.uniform_response_time")
    config.include("pyramid_tm")

    def view(request):
        def committed(success):
            events.append(("commit", success))
            now[0] = 0.4

        request.tm.get().addAfterCommitHook(committed)
        return Response("OK")

    config.add_route("forgot", "/forgot")
    config.add_view(view, route_name="forgot")
    TestApp(config.make_wsgi_app()).post("/forgot")
    assert events == [("commit", True), ("sleep", 0.6)]


def test_real_openapi_and_transaction_order():
    config = Configurator()
    config.include("pyramid_tm")
    config.include("pyramid_openapi3")
    for module in reversed(MODULES):
        config.include(f"pyramid_niteo.{module}")
    app = config.make_wsgi_app()
    names = [name for name, _ in app.registry.getUtility(ITweens).implicit()]
    assert_required_order(names)


def assert_required_order(names):
    relationships = [(CLIENT, ACCESS), (MALFORMED, TIMING)]
    for outer in [SECURITY, RELEASE, XDEV]:
        relationships.extend((outer, inner) for inner in [MALFORMED, CLIENT, ACCESS])
    for outer in [SECURITY, RELEASE, XDEV, MALFORMED, TIMING]:
        relationships.extend(
            (outer, inner) for inner in [OPENAPI, TRANSACTION, EXCVIEW]
        )
    for outer, inner in relationships:
        if outer in names and inner in names:
            assert names.index(outer) < names.index(inner)


def test_application_can_order_independent_headers():
    config = Configurator()
    for module in MODULES:
        config.include(f"pyramid_niteo.{module}")
    # No package constraint requires security headers outside release headers.
    config.add_tween(f"{__name__}.passthrough", under=RELEASE, over=SECURITY)
    names = [
        name
        for name, _ in config.make_wsgi_app().registry.getUtility(ITweens).implicit()
    ]
    assert names.index(RELEASE) < names.index(SECURITY)
    assert_required_order(names)


def passthrough(handler, registry):
    return handler
