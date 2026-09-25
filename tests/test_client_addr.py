import pytest


@pytest.mark.parametrize("ip", ["198.51.100.20", "2001:db8::20"])
def test_direct_fly_ignores_spoofed_headers(make_app, ip):
    app = make_app(["client_addr"])
    response = app.get(
        "/",
        headers={
            "Fly-Client-IP": ip,
            "CF-Connecting-IP": "192.0.2.1",
            "X-Forwarded-For": "192.0.2.2, 192.0.2.3",
        },
    )
    assert response.json["ip"] == ip


@pytest.mark.parametrize("edge", ["173.245.48.1", "2606:4700::1"])
@pytest.mark.parametrize("visitor", ["198.51.100.20", "2001:db8::20"])
def test_cloudflare_through_fly(make_app, edge, visitor):
    app = make_app(["client_addr"])
    assert (
        app.get(
            "/",
            headers={
                "Fly-Client-IP": edge,
                "CF-Connecting-IP": visitor,
                "X-Forwarded-For": "192.0.2.2",
            },
        ).json["ip"]
        == visitor
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"Fly-Client-IP": "garbage"},
        {"Fly-Client-IP": ""},
        {"Fly-Client-IP": "198.51.100.20, 192.0.2.1"},
        {"Fly-Client-IP": "173.245.48.1"},
        {"Fly-Client-IP": "173.245.48.1", "CF-Connecting-IP": "garbage"},
        {"Fly-Client-IP": "173.245.48.1", "CF-Connecting-IP": "1.2.3.4, 2.3.4.5"},
    ],
)
def test_invalid_ip_fails_closed(make_app, headers):
    make_app(["client_addr"]).get("/", headers=headers, status=400)


@pytest.mark.parametrize("peer", ["127.0.0.1", "10.0.0.10", "::1"])
def test_internal_healthcheck_preserves_peer_address(make_app, peer):
    from pyramid.response import Response

    def view(request):
        # Exercise a downstream consumer that expects a string, not None.
        return Response(
            json_body={
                "remote": request.remote_addr.strip(),
                "client": request.client_addr,
                "forwarded": request.headers.get("X-Forwarded-For"),
            }
        )

    response = make_app(["client_addr"], view=view).get(
        "/",
        headers={"X-Forwarded-For": "192.0.2.1", "CF-Connecting-IP": "192.0.2.2"},
        extra_environ={"REMOTE_ADDR": peer},
    )
    assert response.json == {"remote": peer, "client": peer, "forwarded": None}
