"""Result validation without mandatory third-party dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .security import assert_no_secrets


RECOMMENDATIONS = {
    "reject_likely_rfi",
    "needs_human_review",
    "needs_follow_up_observation",
    "insufficient_data",
}

CLASSIFICATIONS = {
    "likely_rfi_or_instrumental",
    "ambiguous_candidate",
    "interesting_but_unconfirmed",
    "insufficient_data",
}

MODES = {"api-worker", "agent-client"}

REQUIRED_FIELDS = {
    "task_id",
    "worker_id",
    "mode",
    "model_provider",
    "model_name",
    "result",
    "confidence",
    "recommendation",
    "evidence_refs",
    "limitations",
    "runtime_seconds",
    "cost_estimate_usd",
    "created_at",
}

OPTIONAL_FIELDS = {"prompt_version", "input_sha256"}
MAX_SHORT_TEXT = 512
MAX_LONG_TEXT = 10_000
MAX_ARRAY_ITEMS = 64
MAX_RUNTIME_SECONDS = 86_400
MAX_COST_USD = 1_000


class ValidationError(ValueError):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_result(payload: dict[str, Any]) -> None:
    assert_no_secrets(payload)

    keys = set(payload)
    missing = REQUIRED_FIELDS - keys
    if missing:
        raise ValidationError(f"missing required fields: {', '.join(sorted(missing))}")

    extra = keys - REQUIRED_FIELDS - OPTIONAL_FIELDS
    if extra:
        raise ValidationError(f"unknown fields: {', '.join(sorted(extra))}")

    for field in ("task_id", "worker_id", "model_provider", "model_name", "created_at"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValidationError(f"{field} must be a non-empty string")
        if len(payload[field]) > MAX_SHORT_TEXT:
            raise ValidationError(f"{field} is too long")

    if payload["mode"] not in MODES:
        raise ValidationError(f"mode must be one of: {', '.join(sorted(MODES))}")

    confidence = payload["confidence"]
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValidationError("confidence must be a number between 0 and 1")

    if payload["recommendation"] not in RECOMMENDATIONS:
        raise ValidationError("recommendation has an invalid value")

    if not isinstance(payload["evidence_refs"], list) or not payload["evidence_refs"]:
        raise ValidationError("evidence_refs must be a non-empty array")
    if len(payload["evidence_refs"]) > MAX_ARRAY_ITEMS:
        raise ValidationError("evidence_refs has too many items")

    if not all(isinstance(item, str) and item.strip() for item in payload["evidence_refs"]):
        raise ValidationError("evidence_refs items must be non-empty strings")
    if any(len(item) > MAX_SHORT_TEXT for item in payload["evidence_refs"]):
        raise ValidationError("evidence_refs items must be shorter")

    if not isinstance(payload["limitations"], list):
        raise ValidationError("limitations must be an array")
    if len(payload["limitations"]) > MAX_ARRAY_ITEMS:
        raise ValidationError("limitations has too many items")

    if not all(isinstance(item, str) and item.strip() for item in payload["limitations"]):
        raise ValidationError("limitations items must be non-empty strings")
    if any(len(item) > MAX_SHORT_TEXT for item in payload["limitations"]):
        raise ValidationError("limitations items must be shorter")

    for field in ("runtime_seconds", "cost_estimate_usd"):
        if not isinstance(payload[field], (int, float)) or payload[field] < 0:
            raise ValidationError(f"{field} must be a non-negative number")
    if payload["runtime_seconds"] > MAX_RUNTIME_SECONDS:
        raise ValidationError("runtime_seconds is too large")
    if payload["cost_estimate_usd"] > MAX_COST_USD:
        raise ValidationError("cost_estimate_usd is too large")

    result = payload["result"]
    if not isinstance(result, dict):
        raise ValidationError("result must be an object")

    for field in ("short_summary", "classification", "analysis"):
        if field not in result:
            raise ValidationError(f"result.{field} is required")

    if not isinstance(result["short_summary"], str) or not result["short_summary"].strip():
        raise ValidationError("result.short_summary must be a non-empty string")
    if len(result["short_summary"]) > MAX_SHORT_TEXT:
        raise ValidationError("result.short_summary is too long")

    if result["classification"] not in CLASSIFICATIONS:
        raise ValidationError("result.classification has an invalid value")

    if not isinstance(result["analysis"], str) or not result["analysis"].strip():
        raise ValidationError("result.analysis must be a non-empty string")
    if len(result["analysis"]) > MAX_LONG_TEXT:
        raise ValidationError("result.analysis is too long")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an OSAN result JSON file.")
    parser.add_argument("result", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = load_json(args.result)
        if not isinstance(payload, dict):
            raise ValidationError("top-level payload must be an object")
        validate_result(payload)
    except Exception as exc:  # noqa: BLE001 - CLI should return readable validation failures.
        print(f"invalid: {exc}", file=sys.stderr)
        return 1

    print(f"valid: {args.result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
