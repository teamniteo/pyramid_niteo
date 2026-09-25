"""Restrict *.fly.dev requests to an explicit IP allowlist."""

from ipaddress import ip_address

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.httpexceptions import HTTPForbidden
from pyramid.interfaces import ITweens
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import INGRESS

from ._ordering import ACCESS, CLIENT
from ._types import Handler


def includeme(config: Configurator) -> None:
    config.add_tween(ACCESS, under=(CLIENT, INGRESS))


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    tweens = registry.getUtility(ITweens)
    enabled = {name for name, _ in (tweens.explicit or tweens.implicit())}
    if CLIENT not in enabled:
        raise ConfigurationError(
            "flydev_access requires include('pyramid_niteo.client_addr')"
        )
    try:
        allowed = {
            str(ip_address(ip))
            for ip in registry.settings.get("niteo.flydev_allowlist", "").split()
        }
    except ValueError as exc:
        raise ConfigurationError(
            "niteo.flydev_allowlist must contain IP addresses"
        ) from exc

    def flydev_access(request: Request) -> Response:
        host = request.host.split(":", 1)[0].lower().rstrip(".")
        if (host == "fly.dev" or host.endswith(".fly.dev")) and (
            not request.headers.get("Fly-Client-IP")
            or request.client_addr not in allowed
        ):
            return HTTPForbidden("Access to this Fly app is restricted.")
        return handler(request)

    return flydev_access
