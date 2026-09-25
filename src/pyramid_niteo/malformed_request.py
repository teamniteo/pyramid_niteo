"""Reject undecodable URLs before any inner tween consumes them."""

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPNotFound
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import EXCVIEW

from ._ordering import MALFORMED, OPENAPI, TIMING, TRANSACTION
from ._types import Handler


def includeme(config: Configurator) -> None:
    config.add_tween(MALFORMED, over=(TIMING, OPENAPI, TRANSACTION, EXCVIEW))


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    def malformed_request(request: Request) -> Response:
        try:
            _ = request.url
        except UnicodeDecodeError:
            return HTTPNotFound()
        return handler(request)

    return malformed_request
