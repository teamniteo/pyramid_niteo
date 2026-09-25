"""Run the actual release gate without publishing anything."""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "tag", [None, "v999.0", "0.1.0", "v0.1.0; echo unexpected", "matching"]
)
def test_release_tag_must_match_package_version(tag):
    version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    env = {**os.environ}
    env.pop("RELEASE_TAG", None)
    if tag is not None:
        env["RELEASE_TAG"] = f"v{version}" if tag == "matching" else tag
    result = subprocess.run(
        [sys.executable, "scripts/check_release.py"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if tag == "matching":
        assert result.returncode == 0
        assert f"Publishing pyramid-niteo {version}" in result.stdout
    else:
        assert result.returncode != 0
        assert "Release tag must be" in result.stderr
