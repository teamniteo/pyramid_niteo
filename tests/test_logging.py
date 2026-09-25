"""Standard logging preserves structured fields without configuring handlers."""

import logging

import pytest


@pytest.mark.parametrize(
    ("modules", "headers", "environ", "status", "message", "fields"),
    [
        (
            ["client_addr", "flydev_access"],
            {"Host": "app.fly.dev", "Fly-Client-IP": "192.0.2.1"},
            {},
            403,
            "Fly app access denied",
            {"host": "app.fly.dev", "client_ip": "192.0.2.1"},
        ),
        (
            ["client_addr", "flydev_access"],
            {"Host": "app.fly.dev"},
            {"REMOTE_ADDR": "192.0.2.1"},
            403,
            "Fly app access denied",
            {"host": "app.fly.dev", "client_ip": "192.0.2.1"},
        ),
        (
            ["client_addr"],
            {"Fly-Client-IP": "bad"},
            {},
            400,
            "Invalid client IP headers",
            {"fly_client_ip": "bad", "cf_connecting_ip": None},
        ),
        (
            ["client_addr"],
            {"Fly-Client-IP": "173.245.48.1", "CF-Connecting-IP": "bad"},
            {},
            400,
            "Invalid client IP headers",
            {"fly_client_ip": "173.245.48.1", "cf_connecting_ip": "bad"},
        ),
        (
            ["client_addr"],
            {"Fly-Client-IP": "173.245.48.1"},
            {},
            400,
            "Invalid client IP headers",
            {"fly_client_ip": "173.245.48.1", "cf_connecting_ip": None},
        ),
        (
            ["malformed_request"],
            {},
            {"PATH_INFO": "/\xff"},
            404,
            "Malformed request URL",
            {"url": "/\xff"},
        ),
    ],
)
def test_rejection_logs_once(
    make_app, caplog, modules, headers, environ, status, message, fields
):
    root_handlers = list(logging.getLogger().handlers)
    app = make_app(modules)
    app.get(
        "/?token=do-not-log",
        headers={"Authorization": "Bearer do-not-log", **headers},
        extra_environ=environ,
        status=status,
    )
    assert logging.getLogger().handlers == root_handlers
    (record,) = caplog.records
    assert record.name.startswith("pyramid_niteo.")
    assert record.levelno == logging.WARNING
    assert record.getMessage() == message
    assert not hasattr(record, "status_code")
    for key, value in fields.items():
        assert getattr(record, key) == value
    assert "do-not-log" not in repr(record.__dict__)


def test_allowed_request_is_quiet(make_app, caplog):
    make_app(
        ["client_addr", "flydev_access", "malformed_request"],
        settings={"niteo.flydev_allowlist": "192.0.2.1"},
    ).get("/", headers={"Host": "app.fly.dev", "Fly-Client-IP": "192.0.2.1"})
    assert not caplog.records
