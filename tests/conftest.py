"""Real Pyramid applications exercised through their WSGI entrypoint."""

import pytest
from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPUnauthorized
from pyramid.response import Response
from webtest import TestApp


@pytest.fixture(autouse=True)
def release_environment(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "0123456789abcdef0123456789abcdef01234567")


@pytest.fixture
def make_app():
    def make(modules=(), settings=None, view=None):
        config = Configurator(settings=settings or {})
        for module in modules:
            config.include(f"pyramid_niteo.{module}")
        config.add_route("root", "/*path")

        def default_view(request):
            if request.path == "/unauthorized":
                raise HTTPUnauthorized()
            return Response(
                json_body={
                    "ip": request.client_addr,
                    "nonce": getattr(request, "csp_nonce", None),
                }
            )

        config.add_view(view or default_view, route_name="root")
        return TestApp(config.make_wsgi_app())

    return make
