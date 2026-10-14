"""Shared fixtures: the spec file and the test data folder."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime_internals_lab.spec import Spec, load_spec

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def spec() -> Spec:
    """The shared spec/workload.json, validated."""
    return load_spec(REPO / "spec" / "workload.json")


@pytest.fixture(scope="session")
def repo() -> Path:
    """The repository root."""
    return REPO


@pytest.fixture(scope="session")
def fixtures() -> Path:
    """The folder with recorded test inputs."""
    return FIXTURES
