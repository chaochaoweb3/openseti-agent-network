import pytest

from osan.security import assert_no_secrets, find_secret_paths


def test_rejects_secret_key_names():
    payload = {"task_id": "x", "api_key": "not-even-real"}

    with pytest.raises(ValueError):
        assert_no_secrets(payload)


def test_rejects_secret_value_patterns():
    payload = {"result": {"analysis": "leaked sk-abcdefghijklmnopqrstuvwxyz"}}

    assert "result.analysis" in find_secret_paths(payload)


def test_allows_scientific_token_word_without_secret_shape():
    payload = {"result": {"analysis": "Token budgets are a project design topic."}}

    assert_no_secrets(payload)
