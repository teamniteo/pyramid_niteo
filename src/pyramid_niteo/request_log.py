"""Log every request once, as Heroku's router did, since Fly Proxy does not."""

import logging
import time

from pyramid.config import Configurator
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import EXCVIEW, INGRESS

from ._ordering import (
    ACCESS,
    BODY,
    CLIENT,
    MALFORMED,
    OPENAPI,
    REQUEST_LOG,
    TIMING,
    TRANSACTION,
)
from ._types import Handler

logger = logging.getLogger(__name__)


def includeme(config: Configurator) -> None:
    config.add_tween(
        REQUEST_LOG,
        under=(CLIENT, MALFORMED, INGRESS),
        over=(ACCESS, BODY, TIMING, OPENAPI, TRANSACTION, EXCVIEW),
    )


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    def request_log(request: Request) -> Response:
        start = time.monotonic()
        response = None
        try:
            response = handler(request)
            return response
        finally:
            logger.info(
                "Request",
                extra={
                    "method": request.method,
                    # The raw WSGI path: decoding it could raise on a bad URL.
                    "path": request.environ.get("PATH_INFO"),
                    "host": request.host,
                    "request_bytes": request.content_length,
                    # Nothing caught an exception that escaped the exception view.
                    "status": 500 if response is None else response.status_code,
                    "response_bytes": (
                        None if response is None else response.content_length
                    ),
                    "duration_ms": round((time.monotonic() - start) * 1000),
                    "client_ip": request.client_addr,
                    "user_agent": request.user_agent,
                    "request_id": request.headers.get("Fly-Request-Id"),
                    "cf_ray": request.headers.get("CF-Ray"),
                },
            )

    return request_log
