import json
from pathlib import Path

import pytest

from osan.validator import ValidationError, validate_result


ROOT = Path(__file__).resolve().parents[1]


def load_example():
    return json.loads((ROOT / "examples" / "agent-client-result.json").read_text())


def test_valid_example_result():
    validate_result(load_example())


def test_missing_required_field_is_rejected():
    payload = load_example()
    del payload["worker_id"]

    with pytest.raises(ValidationError):
        validate_result(payload)


def test_unknown_extra_field_is_rejected():
    payload = load_example()
    payload["authorization"] = "Bearer abcdefghijklmnopqrstuvwxyz"

    with pytest.raises(ValueError):
        validate_result(payload)


def test_invalid_confidence_is_rejected():
    payload = load_example()
    payload["confidence"] = 2

    with pytest.raises(ValidationError):
        validate_result(payload)


def test_overlong_analysis_is_rejected():
    payload = load_example()
    payload["result"]["analysis"] = "x" * 10001

    with pytest.raises(ValidationError):
        validate_result(payload)


def test_absurd_cost_is_rejected():
    payload = load_example()
    payload["cost_estimate_usd"] = 1001

    with pytest.raises(ValidationError):
        validate_result(payload)
