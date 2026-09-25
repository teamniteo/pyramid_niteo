"""CSP nonces and browser security headers for Fly-hosted applications."""

import secrets
from urllib.parse import urlsplit

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import EXCVIEW

from ._ordering import CLIENT, MALFORMED, OPENAPI, SECURITY, TRANSACTION
from ._types import Handler

DEFAULT_POLICY = "default-src 'self'; script-src 'self'; frame-ancestors 'self'"
HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "camera=(), microphone=(), midi=(), accelerometer=(), gyroscope=(), "
        "magnetometer=(), usb=()"
    ),
}


def includeme(config: Configurator) -> None:
    config.add_tween(SECURITY, over=(MALFORMED, CLIENT, OPENAPI, TRANSACTION, EXCVIEW))


def _policy(settings: dict) -> dict[str, list[str]]:
    policy = {}
    for directive in (
        settings.get("niteo.csp_policy", DEFAULT_POLICY).replace("\n", ";").split(";")
    ):
        tokens = directive.split()
        if tokens:
            name, *values = tokens
            if name in policy:
                raise ConfigurationError(f"Duplicate CSP directive: {name}")
            policy[name] = values
    for origin in settings.get("niteo.csp_connect_origins", "").split():
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https", "ws", "wss"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ConfigurationError(
                "niteo.csp_connect_origins must contain URL origins"
            )
        sources = policy.setdefault(
            "connect-src", list(policy.get("default-src", ["'self'"]))
        )
        normalized = f"{parsed.scheme}://{parsed.netloc}"
        if normalized not in sources:
            sources.append(normalized)
    policy.setdefault("script-src", list(policy.get("default-src", ["'self'"])))
    for name, sources in policy.items():
        if "'none'" in (source.lower() for source in sources) and (
            len(sources) > 1 or name == "script-src"
        ):
            raise ConfigurationError(
                f"CSP {name}: 'none' conflicts with configured sources or additions"
            )
    return policy


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    policy = _policy(registry.settings)

    def security_headers(request: Request) -> Response:
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce
        directives = {name: list(values) for name, values in policy.items()}
        directives["script-src"].append(f"'nonce-{nonce}'")
        response = handler(request)
        response.headers.update(HEADERS)
        response.headers["Content-Security-Policy"] = (
            "; ".join(" ".join([name, *values]) for name, values in directives.items())
            + ";"
        )
        return response

    return security_headers
