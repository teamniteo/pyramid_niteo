import pytest
from pyramid.exceptions import ConfigurationError

MODULES = ["flydev_access", "client_addr"]  # Deliberately reverse ingress order.
SETTINGS = {"niteo.flydev_allowlist": "198.51.100.20\n2001:db8::20"}


@pytest.mark.parametrize(
    "host", ["app.fly.dev", "app.fly.dev:443", "APP.FLY.DEV", "app.fly.dev.", "fly.dev"]
)
def test_denied_by_default(make_app, host):
    make_app(MODULES).get(
        "/", headers={"Host": host, "Fly-Client-IP": "198.51.100.20"}, status=403
    )


@pytest.mark.parametrize("ip", ["198.51.100.20", "2001:db8:0:0:0:0:0:20"])
def test_allowlisted(make_app, ip):
    make_app(MODULES, SETTINGS).get(
        "/", headers={"Host": "app.fly.dev", "Fly-Client-IP": ip}
    )


def test_cloudflare_visitor_allowlisted(make_app):
    make_app(MODULES, SETTINGS).get(
        "/",
        headers={
            "Host": "app.fly.dev",
            "Fly-Client-IP": "173.245.48.1",
            "CF-Connecting-IP": "198.51.100.20",
        },
    )


@pytest.mark.parametrize(
    "host", ["app.example.com", "fly.dev.attacker.example", "notfly.dev", "localhost"]
)
def test_other_hosts_are_outside_gate(make_app, host):
    make_app(MODULES).get("/", headers={"Host": host})


def test_missing_fly_header_cannot_use_forwarded_allowlist(make_app):
    make_app(MODULES, SETTINGS).get(
        "/",
        headers={
            "Host": "app.fly.dev",
            "X-Forwarded-For": "198.51.100.20",
        },
        status=403,
    )


def test_dependency_not_implicitly_enabled(make_app):
    with pytest.raises(ConfigurationError, match="requires include"):
        make_app(["flydev_access"])


def test_invalid_allowlist(make_app):
    with pytest.raises(ConfigurationError, match="IP addresses"):
        make_app(MODULES, {"niteo.flydev_allowlist": "not-an-ip"})


def test_headers_cannot_bypass_ip_allowlist(make_app):
    make_app(MODULES).get(
        "/",
        headers={
            "Host": "app.fly.dev",
            "Fly-Client-IP": "198.51.100.20",
            "X-Niteo-Flydev-Token": "secret",
            "User-Agent": "secret",
        },
        status=403,
    )


@pytest.mark.parametrize("peer", ["198.51.100.20", "2001:db8::20"])
def test_peer_in_allowlist_cannot_grant_access_without_fly_header(make_app, peer):
    make_app(MODULES, SETTINGS).get(
        "/",
        headers={"Host": "app.fly.dev"},
        extra_environ={"REMOTE_ADDR": peer},
        status=403,
    )
