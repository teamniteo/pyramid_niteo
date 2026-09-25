.PHONY: check test lint build
check: lint test build

lint:
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .

test:
	uv run --frozen pytest

build:
	rm -f dist/pyramid_niteo-*.whl dist/pyramid_niteo-*.tar.gz
	uv build --no-sources
	uv run --frozen twine check dist/*
	uv run --no-project --isolated --with dist/pyramid_niteo-*.whl python scripts/smoke_wheel.py
