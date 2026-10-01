"""Reject oversized POST, PUT, and PATCH bodies before any inner tween reads them."""

import logging

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.httpexceptions import HTTPLengthRequired, HTTPRequestEntityTooLarge
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import EXCVIEW

from ._ordering import BODY, OPENAPI, TIMING, TRANSACTION
from ._types import Handler

logger = logging.getLogger(__name__)

CHECKED_METHODS = {"PATCH", "POST", "PUT"}


def includeme(config: Configurator) -> None:
    config.add_tween(BODY, over=(TIMING, OPENAPI, TRANSACTION, EXCVIEW))


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    try:
        # int() truncates a float, int(str()) refuses it.
        limit = int(str(registry.settings["niteo.max_body_size"]))
    except (KeyError, ValueError) as exc:
        raise ConfigurationError(
            "niteo.max_body_size must be set to an integer"
        ) from exc
    if limit < 0:
        raise ConfigurationError("niteo.max_body_size must be >= 0")

    def max_body_size(request: Request) -> Response:
        if request.method not in CHECKED_METHODS:
            return handler(request)
        content_length = request.content_length
        path = request.environ.get("PATH_INFO")
        # Capping a body of undeclared length would mean reading it.
        if content_length is None:
            logger.warning("Request body length missing", extra={"path": path})
            return HTTPLengthRequired()
        if content_length > limit:
            logger.warning(
                "Request body too large",
                extra={"path": path, "content_length": content_length},
            )
            return HTTPRequestEntityTooLarge()
        return handler(request)

    return max_body_size
