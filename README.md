# pyramid_niteo

[![CI](https://github.com/teamniteo/pyramid_niteo/actions/workflows/ci.yml/badge.svg)](https://github.com/teamniteo/pyramid_niteo/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyramid-niteo.svg)](https://pypi.org/project/pyramid-niteo/)
[![100% test coverage](https://img.shields.io/badge/test%20coverage-100%25-brightgreen)](https://github.com/teamniteo/pyramid_niteo/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Opt-in Pyramid tweens for [@teamniteo](https://github.com/teamniteo)'s apps on Fly.io, proxied by Cloudflare. Requires Python 3.14 or newer. Runtime dependencies are [Pyramid](https://trypyramid.com) and `expandvars`. There are no startup network calls.

## Installation and configuration

Install from PyPI:

```sh
uv add pyramid-niteo
```

Every tween is optional. Include each module you want. There is deliberately no package-wide `includeme()` and no module silently includes another:

```python
from pyramid.config import Configurator
from pyramid_niteo.settings import expandvars_dict


def main(global_config, **settings):
    config = Configurator(settings=expandvars_dict(settings))
    config.include("pyramid_niteo.security_headers")
    config.include("pyramid_niteo.release_version")
    config.include("pyramid_niteo.malformed_request")
    config.include("pyramid_niteo.client_addr")
    config.include("pyramid_niteo.flydev_access")
    # Optional: config.include("pyramid_niteo.xdev")
    # Optional: config.include("pyramid_niteo.uniform_response_time")
    # Register application routes and views here.
    return config.make_wsgi_app()
```

You can also list those modules under `pyramid.includes` in a PasteDeploy INI. `settings.expandvars_dict()` is a helper called before creating the configurator, not an includable tween.

## Modules

### `client_addr`

Resolves the visitor address for the two supported request paths:

- Direct to Fly: use `Fly-Client-IP`.
- Cloudflare → Fly: when `Fly-Client-IP` belongs to a published Cloudflare range, use the validated `CF-Connecting-IP` instead.

Ignores untrusted `CF-Connecting-IP` on direct traffic, removes `X-Forwarded-For`, and sets `request.remote_addr`. Consequently both `request.remote_addr` and `request.client_addr` expose the same normalized IP to access checks, metrics, and logging. There is no configurable header name or arbitrary proxy chain.

Invalid IP headers return 400. When `Fly-Client-IP` is missing, the original WSGI peer address is preserved for health checks and downstream consumers. The module never replaces it with `None`. In that case, `request.client_addr` falls back to the peer address, not a verified visitor address. `flydev_access` explicitly denies IP-based access without a Fly header, even if the peer is allowlisted. Other visitor-IP access checks must make the same distinction. Cloudflare requests with missing/invalid `CF-Connecting-IP` return 400. Only include this in the Fly deployment configuration, or supply realistic Fly headers in functional tests. Omit it for ordinary local development.

This relies on requests arriving through Fly Proxy. Do not expose the WSGI server directly to untrusted peers: they could forge Fly's headers. Cloudflare Workers in your zone are also trusted infrastructure. Disable Cloudflare's Pseudo IPv4 “Overwrite Headers” mode to retain the actual visitor address.

Cloudflare ranges are bundled in `_cloudflare.py`, with source URLs and a verification date. The ranges file is updated weekly.

### `flydev_access`

Restricts `fly.dev` and its subdomains to an IP allowlist. Domain labels are matched case-insensitively, with ports and a terminal DNS dot handled correctly. Custom domains are unaffected. This is review-app access control, not origin authentication or proof that a request passed through Cloudflare.

```ini
niteo.flydev_allowlist =
    198.51.100.20
    2001:db8::20
```

An empty allowlist denies everyone on those domains. Entries are individual IPv4 or IPv6 addresses, not CIDRs. Invalid entries fail at application startup.

Requires explicitly including `pyramid_niteo.client_addr`. Missing it raises a configuration error. CI runners on cione/citwo use the same IP allowlist as other callers: add their outbound addresses in each application's settings. There is no token or header-based bypass.

### `security_headers`

Sets CSP, HSTS (one year including subdomains), `nosniff`, `SAMEORIGIN`, `strict-origin-when-cross-origin`, and a restrictive Permissions Policy. Generates a fresh `request.csp_nonce` before rendering and includes that nonce in `script-src`.

```ini
niteo.csp_policy =
    default-src 'self'
    script-src 'self' https://scripts.example.com
    frame-ancestors 'self'
    connect-src 'self'
    report-uri https://your-report-endpoint.example/csp
niteo.csp_connect_origins = https://cdn.example.com
```

CSP accepts semicolon-separated or one-directive-per-line input. Duplicate directives fail at startup. Standalone `'none'` is supported for blocking all sources in a directive. It fails at startup if combined with other sources, added connection origins, or the automatic `script-src` nonce. The default is `default-src 'self'; script-src 'self'; frame-ancestors 'self'`. A missing `script-src` inherits `default-src` (or `'self'`). An empty `script-src` allows only nonced scripts. An optional list of HTTP(S)/WS(S) origins extends `connect-src`, inheriting `default-src` when necessary. Add any origins used by browser fetch requests to `niteo.csp_connect_origins`. Configure CSP reporting in `niteo.csp_policy`. Deprecated `Expect-CT` and `X-XSS-Protection` headers are not emitted.

Use the nonce on your rendered script tags, and keep nonce-bearing HTML out of shared CDN caches. The response's CSP nonce must match its HTML. This module sets headers on responses returned by inner tweens, including access denials and Pyramid exception views. It does not catch unhandled Python exceptions or add headers to responses generated by Fly/Cloudflare outside Pyramid.

### `release_version`

Sets `X-Release-Version` from the `GIT_COMMIT` environment variable. It must be a full 40-character hexadecimal Git SHA. Missing or invalid values fail at startup. CI must supply that revision during deploy, as it is not a built-in Fly environment variable.

### `malformed_request`

Returns 404 for URLs that cannot be decoded as UTF-8, before URL-consuming inner tweens or views run. It does not intercept unrelated application errors.

### `uniform_response_time`

Pads configured POST endpoints to a minimum total duration. Configure the paths and floor per application. The defaults are empty paths and zero milliseconds.

```ini
niteo.response_padding_ms = 1000
niteo.padded_paths =
    /api/v1/login/forgot
    /api/v1/login/link
    /api/v1/register
    /api/v1/login/password
```

Padding applies to every response, including successful logins. Matching is exact, ignores query strings, and only applies to POST. Durations already above the floor are not delayed. Negative or non-integer floors and paths without a leading slash fail at startup.

The minimum response time is a non-negative integer in milliseconds. Uses a monotonic clock and includes transaction completion in the elapsed time. Sleeping occupies a worker: keep authentication rate limiting in place. A timing floor reduces one enumeration signal. It cannot hide differences above the floor or replace consistent authentication behavior.

### `xdev`

Adds the Niteo recruitment message in `X-Dev`. No settings required.

### `settings.expandvars_dict`

Expands environment variables with two substitution passes, `${VAR:-default}`, `${VAR:?required}`, and Python literal conversion (including lowercase `true`/`false`, numbers, lists and dictionaries). The input dictionary is not modified. Non-string inputs raise `ValueError`. Literal-looking strings are converted too. Quote them if they must remain strings.

## Ordering

Each `includeme()` declares only the relationships its behavior needs:

- Client IP resolution precedes `flydev_access`.
- Malformed URL handling precedes timing, OpenAPI, transactions, and routing.
- Response headers wrap early denials and OpenAPI/transaction/exception responses.
- Timing wraps OpenAPI, transactions, and the exception view so commits count.

There is no fixed order among security, release, and recruitment headers, nor between independent IP and URL handling. Apps can place their own tweens between these modules. OpenAPI and transaction addons remain optional app dependencies and retain their own relative ordering.

Release instructions are in [RELEASING.md](RELEASING.md).

Development instructions are in [DEVELOPMENT.md](DEVELOPMENT.md).
