"""Expose the deployed Git revision in response headers."""

import os
import re

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response
from pyramid.tweens import EXCVIEW

from ._ordering import CLIENT, MALFORMED, OPENAPI, RELEASE, TRANSACTION
from ._types import Handler


def includeme(config: Configurator) -> None:
    config.add_tween(RELEASE, over=(MALFORMED, CLIENT, OPENAPI, TRANSACTION, EXCVIEW))


def tween_factory(handler: Handler, registry: Registry) -> Handler:
    version = os.environ.get("GIT_COMMIT", "")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", version):
        raise ConfigurationError("Set GIT_COMMIT to a full 40-character Git SHA")

    def release_version(request: Request) -> Response:
        response = handler(request)
        response.headers["X-Release-Version"] = version
        return response

    return release_version
