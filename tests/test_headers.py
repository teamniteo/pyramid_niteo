import pytest
from pyramid.exceptions import ConfigurationError
from pyramid.response import Response


def test_nonce_matches_html_and_changes_per_request(make_app):
    def view(request):
        return Response(f'<script nonce="{request.csp_nonce}">hello()</script>')

    app = make_app(["security_headers"], view=view)
    first, second = app.get("/"), app.get("/")
    nonce = first.text.split('"')[1]
    assert f"'nonce-{nonce}'" in first.headers["Content-Security-Policy"]
    assert (
        first.headers["Content-Security-Policy"]
        != second.headers["Content-Security-Policy"]
    )
    assert (
        first.headers["Strict-Transport-Security"]
        == "max-age=31536000; includeSubDomains"
    )
    assert first.headers["X-Content-Type-Options"] == "nosniff"
    assert first.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert first.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in first.headers["Permissions-Policy"]
    assert "Expect-CT" not in first.headers
    assert "X-XSS-Protection" not in first.headers


def test_policy_multiline_and_connect_origins(make_app):
    app = make_app(
        ["security_headers"],
        {
            "niteo.csp_policy": ("default-src 'self'\nscript-src;\nconnect-src"),
            "niteo.csp_connect_origins": (
                "https://cdn.example.com/ "
                "https://cdn.example.com wss://socket.example.com"
            ),
        },
    )
    response = app.get("/")
    csp = response.headers["Content-Security-Policy"]
    assert csp.count("https://cdn.example.com") == 1
    assert "connect-src https://cdn.example.com wss://socket.example.com;" in csp
    assert "script-src 'nonce-" in csp
    assert "default-src 'self';" in csp


@pytest.mark.parametrize(
    ("policy", "origins", "directive"),
    [
        ("img-src 'none' https://example.com", "", "img-src"),
        ("img-src 'NONE' 'self'", "", "img-src"),
        ("script-src 'none'", "", "script-src"),
        ("script-src 'NONE'", "", "script-src"),
        ("default-src 'none'", "", "script-src"),
        ("connect-src 'none'", "https://example.com", "connect-src"),
        ("default-src 'none'; script-src", "https://example.com", "connect-src"),
    ],
)
def test_conflicting_none_rejected_at_startup(make_app, policy, origins, directive):
    with pytest.raises(ConfigurationError, match=f"CSP {directive}: 'none' conflicts"):
        make_app(
            ["security_headers"],
            {"niteo.csp_policy": policy, "niteo.csp_connect_origins": origins},
        )


def test_standalone_none_preserved(make_app):
    app = make_app(
        ["security_headers"],
        {
            "niteo.csp_policy": (
                "default-src 'none'; script-src; object-src 'none'; "
                "frame-ancestors 'none'; connect-src 'none'; img-src 'NONE'"
            ),
        },
    )
    csp = app.get("/").headers["Content-Security-Policy"]
    for directive in ("default-src", "object-src", "frame-ancestors", "connect-src"):
        assert f"{directive} 'none';" in csp
    assert "img-src 'NONE';" in csp
    assert "script-src 'nonce-" in csp


def test_inherits_default_sources(make_app):
    app = make_app(
        ["security_headers"],
        {
            "niteo.csp_policy": "default-src https://assets.example.com",
            "niteo.csp_connect_origins": "https://cdn.example.com",
        },
    )
    csp = app.get("/").headers["Content-Security-Policy"]
    assert "script-src https://assets.example.com 'nonce-" in csp
    assert "connect-src https://assets.example.com https://cdn.example.com;" in csp


def test_empty_policy(make_app):
    app = make_app(
        ["security_headers"],
        {
            "niteo.csp_policy": "",
            "niteo.csp_connect_origins": "https://cdn.example.com",
        },
    )
    csp = app.get("/").headers["Content-Security-Policy"]
    assert "script-src 'self' 'nonce-" in csp
    assert "connect-src 'self' https://cdn.example.com;" in csp


@pytest.mark.parametrize(
    "origin",
    [
        "garbage",
        "ftp://cdn.example.com",
        "https://cdn.example.com/path",
        "https://user@cdn.example.com",
        "https://user:pass@cdn.example.com",
        "https://cdn.example.com?q=x",
        "https://cdn.example.com#fragment",
    ],
)
def test_invalid_origins(make_app, origin):
    with pytest.raises(ConfigurationError, match="URL origins"):
        make_app(["security_headers"], {"niteo.csp_connect_origins": origin})


def test_duplicate_csp_directive_rejected(make_app):
    with pytest.raises(ConfigurationError, match="Duplicate CSP directive"):
        make_app(
            ["security_headers"],
            {"niteo.csp_policy": "script-src 'self'; script-src https://example.com"},
        )


@pytest.mark.parametrize(
    "version",
    [
        None,
        "",
        "abc123",
        "a" * 39,
        "a" * 41,
        "g" * 40,
        "a" * 39 + "\n",
        "a" * 39 + "\r",
        "a" * 39 + "\t",
        "a" * 40 + "\n",
    ],
)
def test_invalid_release_config(make_app, monkeypatch, version):
    if version is None:
        monkeypatch.delenv("GIT_COMMIT", raising=False)
    else:
        monkeypatch.setenv("GIT_COMMIT", version)
    with pytest.raises(ConfigurationError, match="40-character Git SHA"):
        make_app(["release_version"])


@pytest.mark.parametrize(
    "version", ["0123456789abcdef" * 2 + "01234567", "ABCDEF01" * 5]
)
def test_release_from_environment(make_app, monkeypatch, version):
    monkeypatch.setenv("GIT_COMMIT", version)
    response = make_app(["release_version"]).get("/")
    assert response.headers["X-Release-Version"] == version


def test_recruitment_opt_in(make_app):
    assert "X-Dev" not in make_app().get("/").headers
    assert "niteo.co/careers" in make_app(["xdev"]).get("/").headers["X-Dev"]
