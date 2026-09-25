"""Run outside the project environment to check the built distribution."""

import os
from pathlib import Path

from pyramid.config import Configurator
from pyramid.request import Request
from pyramid.response import Response

import pyramid_niteo

assert "/src/pyramid_niteo/" not in str(Path(pyramid_niteo.__file__).resolve())
os.environ["GIT_COMMIT"] = "0123456789abcdef0123456789abcdef01234567"
config = Configurator()
for module in [
    "security_headers",
    "release_version",
    "xdev",
    "malformed_request",
    "client_addr",
    "flydev_access",
    "uniform_response_time",
]:
    config.include(f"pyramid_niteo.{module}")
config.add_route("root", "/")
config.add_view(lambda request: Response(request.client_addr), route_name="root")
app = config.make_wsgi_app()
request = Request.blank(
    "https://app.example.com/", headers={"Fly-Client-IP": "192.0.2.1"}
)
response = request.get_response(app)
assert response.status_int == 200
assert response.text == "192.0.2.1"
assert (
    response.headers["X-Release-Version"] == "0123456789abcdef0123456789abcdef01234567"
)
assert "nonce-" in response.headers["Content-Security-Policy"]
print("Installed wheel smoke test passed.")
