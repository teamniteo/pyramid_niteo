# Development

Use the pinned Nix development shell, the same way CI does:

```sh
nix-shell
uv sync --frozen
make check
```

Or run `nix-shell --run 'make check'`. `make check` runs Ruff lint/format checks, unit and WSGI functional tests with 100% statement/branch coverage, builds the wheel and sdist, validates metadata, and smoke-tests the installed wheel in an isolated environment. CI runs this on Python 3.14.

The shell provides Python 3.14 and pins nixpkgs. `uv.lock` pins Python development dependencies. To update dependencies, use `uv lock --upgrade` in the shell and rerun checks.
