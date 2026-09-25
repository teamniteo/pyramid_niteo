"""Pad selected POST responses, including transaction completion."""

import time

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import EXCVIEW

from ._ordering import OPENAPI, TIMING, TRANSACTION
from ._types import Handler


def includeme(config: Configurator) -> None:
    config.add_tween(TIMING, over=(OPENAPI, TRANSACTION, EXCVIEW))


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    try:
        floor_ms = int(str(registry.settings.get("niteo.response_padding_ms", 0)))
    except ValueError as exc:
        raise ConfigurationError(
            "niteo.response_padding_ms must be an integer"
        ) from exc
    if floor_ms < 0:
        raise ConfigurationError("niteo.response_padding_ms must be >= 0")
    floor = floor_ms / 1000
    paths = set(registry.settings.get("niteo.padded_paths", "").split())
    if any(not path.startswith("/") for path in paths):
        raise ConfigurationError("Padded paths must start with /")

    def uniform_response_time(request: Request) -> Response:
        if not floor or request.method != "POST":
            return handler(request)
        if request.path not in paths:
            return handler(request)
        start = time.monotonic()
        response = handler(request)
        remaining = floor - (time.monotonic() - start)
        if remaining > 0:
            time.sleep(remaining)
        return response

    return uniform_response_time
