"""Resolve the visitor IP for direct Fly and Cloudflare → Fly traffic."""

import logging
from ipaddress import ip_address

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import INGRESS

from ._cloudflare import NETWORKS
from ._ordering import CLIENT
from ._types import Handler

logger = logging.getLogger(__name__)


def includeme(config: Configurator) -> None:
    config.add_tween(CLIENT, under=INGRESS)


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    def client_addr(request: Request) -> Response:
        # Missing Fly headers (e.g. internal health checks) must never let
        # attacker-controlled X-Forwarded-For become an authorization input.
        raw = request.headers.get("Fly-Client-IP")
        request.headers.pop("X-Forwarded-For", None)
        if raw is None:
            # Preserve the WSGI peer address for health checks and downstream
            # consumers. It is not a verified visitor address without Fly.
            return handler(request)
        try:
            addr = ip_address(raw)
            if any(addr in network for network in NETWORKS):
                addr = ip_address(request.headers.get("CF-Connecting-IP", ""))
        except ValueError:
            logger.warning(
                "Invalid client IP headers",
                extra={
                    "fly_client_ip": raw,
                    "cf_connecting_ip": request.headers.get("CF-Connecting-IP"),
                },
            )
            return HTTPBadRequest("Invalid client IP headers.")
        request.remote_addr = str(addr)
        return handler(request)

    return client_addr
