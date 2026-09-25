"""An optional recruitment message for people inspecting HTTP responses."""

from pyramid.config import Configurator
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import EXCVIEW

from ._ordering import CLIENT, MALFORMED, OPENAPI, TRANSACTION, XDEV
from ._types import Handler

MESSAGE = (
    "Hey there, we see you're interacting with our code, hope it works as expected! "
    "If you're looking for work, head to niteo.co/careers, "
    "and mention this message in your application."
)


def includeme(config: Configurator) -> None:
    config.add_tween(XDEV, over=(MALFORMED, CLIENT, OPENAPI, TRANSACTION, EXCVIEW))


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    def xdev(request: Request) -> Response:
        response = handler(request)
        response.headers["X-Dev"] = MESSAGE
        return response

    return xdev
