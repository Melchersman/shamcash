"""Public exports, matching clients, and runnable documentation syntax."""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import shamcash
from shamcash import LinkSession, ShamCashAPI, ShamCashAPISync
from shamcash.exceptions import ERROR_MAP
from lifecycle_payloads import CREATED

ROOT = Path(__file__).resolve().parents[1]
METHODS = [
    "create_link_session",
    "get_link_session",
    "get_link_qr",
    "wait_for_link",
    "list_plans",
    "subscribe",
    "set_auto_renew",
    "start_trial",
    "delete_account",
]


def test_public_exports_and_error_classes_are_available():
    assert len(shamcash.__all__) == len(set(shamcash.__all__))
    for name in shamcash.__all__:
        assert getattr(shamcash, name) is not None
    for cls in ERROR_MAP.values():
        assert cls.__name__ in shamcash.__all__


def test_client_methods_have_matching_arguments():
    for name in METHODS:
        sync = getattr(ShamCashAPISync, name)
        asynchronous = getattr(ShamCashAPI, name)
        assert (
            inspect.signature(sync).parameters
            == inspect.signature(asynchronous).parameters
        )
        assert not inspect.iscoroutinefunction(sync)
        assert inspect.iscoroutinefunction(asynchronous)


def test_source_version_matches_distribution_metadata():
    project = (ROOT / "pyproject.toml").read_text()
    assert (
        re.search(r'^version = "([^"]+)"', project, re.MULTILINE).group(1)
        == shamcash.__version__
    )


def test_readme_python_examples_are_valid_syntax():
    examples = re.findall(
        r"```python\n(.*?)```", (ROOT / "README.md").read_text(), flags=re.DOTALL
    )
    assert len(examples) >= 6
    for example in examples:
        ast.parse(example)


def test_session_representation_does_not_include_login_credentials():
    session = LinkSession.from_dict(CREATED)
    representation = repr(session)
    assert session.link_session_id in representation
    assert "provider-id" not in representation
    assert "public-key" not in representation
    assert "data:image" not in representation
