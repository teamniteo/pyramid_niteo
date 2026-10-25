"""Every request leaves one access line, whatever answered it."""

import logging

import pytest


@pytest.fixture
def records(caplog):
    caplog.set_level(logging.INFO, logger="pyramid_niteo.request_log")

    def request_records():
        return [r for r in caplog.records if r.name == "pyramid_niteo.request_log"]

    return request_records


def test_request_logs_once(make_app, records, monkeypatch):
    clock = iter([10.0, 10.25])
    monkeypatch.setattr("pyramid_niteo.request_log.time.monotonic", lambda: next(clock))
    response = make_app(["client_addr", "request_log"]).post(
        "/vendors?token=do-not-log",
        b"payload",
        headers={
            "Authorization": "Bearer do-not-log",
            "Host": "app.example.com",
            "Fly-Client-IP": "192.0.2.1",
            "Fly-Request-Id": "01JABCDEF",
            "CF-Ray": "8f1c2d3e4a5b6c7d-AMS",
            "User-Agent": "python-requests/2.32.3",
        },
    )
    (record,) = records()
    assert record.levelno == logging.INFO
    assert record.getMessage() == "Request"
    assert {
        key: getattr(record, key)
        for key in [
            "method",
            "path",
            "host",
            "request_bytes",
            "status",
            "response_bytes",
            "duration_ms",
            "client_ip",
            "user_agent",
            "request_id",
            "cf_ray",
        ]
    } == {
        "method": "POST",
        "path": "/vendors",
        "host": "app.example.com",
        "request_bytes": len(b"payload"),
        "status": 200,
        "response_bytes": len(response.body),
        "duration_ms": 250,
        "client_ip": "192.0.2.1",
        "user_agent": "python-requests/2.32.3",
        "request_id": "01JABCDEF",
        "cf_ray": "8f1c2d3e4a5b6c7d-AMS",
    }
    assert "do-not-log" not in repr(record.__dict__)


def test_request_logs_cloudflare_visitor(make_app, records):
    make_app(["client_addr", "request_log"]).get(
        "/",
        headers={
            "Fly-Client-IP": "173.245.48.1",
            "CF-Connecting-IP": "198.51.100.7",
            "X-Forwarded-For": "203.0.113.66",
        },
    )
    (record,) = records()
    assert record.client_ip == "198.51.100.7"


@pytest.mark.parametrize(
    ("modules", "method", "path", "headers", "body", "status"),
    [
        (["request_log"], "GET", "/unauthorized", {}, b"", 401),
        (
            ["client_addr", "flydev_access", "request_log"],
            "GET",
            "/",
            {"Host": "app.fly.dev"},
            b"",
            403,
        ),
        (["max_body_size", "request_log"], "POST", "/", {}, b"x" * 1025, 413),
    ],
)
def test_request_logs_inner_responses(
    make_app, records, modules, method, path, headers, body, status
):
    make_app(modules).request(
        path, method=method, headers=headers, body=body, status=status
    )
    (record,) = records()
    assert record.status == status


def test_escaped_exception_logs_500(make_app, records):
    def view(request):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        make_app(["request_log"], view=view).get("/")
    (record,) = records()
    assert (record.status, record.response_bytes) == (500, None)


def test_undecodable_url_logs_raw_path(make_app, records):
    with pytest.raises(UnicodeDecodeError):
        make_app(["request_log"]).get("/", extra_environ={"PATH_INFO": "/\xff"})
    (record,) = records()
    assert (record.path, record.status) == ("/\xff", 500)


def test_rejected_url_is_not_logged_as_request(make_app, records):
    make_app(["malformed_request", "request_log"]).get(
        "/", extra_environ={"PATH_INFO": "/\xff"}, status=404
    )
    assert records() == []
