"""Types shared by the tween factories."""

from collections.abc import Callable

from pyramid.request import Request
from pyramid.response import Response

Handler = Callable[[Request], Response]
