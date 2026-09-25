"""Reject releases whose tag does not match the package version."""

import os
import tomllib
from pathlib import Path


def main() -> None:
    with Path("pyproject.toml").open("rb") as source:
        version = tomllib.load(source)["project"]["version"]
    expected = f"v{version}"
    actual = os.environ.get("RELEASE_TAG")
    if actual != expected:
        raise SystemExit(f"Release tag must be {expected!r}, got {actual!r}")
    print(f"Publishing pyramid-niteo {version} from {actual}")


if __name__ == "__main__":
    main()
