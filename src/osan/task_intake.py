"""Task intake scoring based on the public rubric."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .security import find_secret_paths
from .validator import (
    TASK_OVERCLAIM_PHRASES,
    TASK_REJECTED_LICENSES,
    ValidationError,
    load_json,
    validate_task,
)


MIN_ACCEPTED_SCORE = 10
MAX_SCORE = 12
PUBLIC_LICENSE_MARKERS = {
    "apache",
    "cc-",
    "cc0",
    "creative commons",
    "mit",
    "public domain",
    "public-domain",
}
PRIVATE_PATH_MARKERS = ("/users/", "/home/", "/private/", "\\users\\")
SOURCE_WEAK_MARKERS = {"", "unknown", "tbd", "private", "proprietary", "internal"}
REQUIRED_OUTPUTS = {"short_summary", "classification", "confidence", "recommendation", "evidence_refs", "limitations"}
CAUTION_MARKERS = {
    "caveat",
    "claim",
    "conservative",
    "demo",
    "fixture",
    "incomplete",
    "limitation",
    "metadata-only",
    "missing",
    "not",
    "preliminary",
    "synthetic",
    "workflow",
}


def _has_any(text: str, markers: set[str] | tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _score(source: int, reason: str) -> dict[str, Any]:
    return {"score": source, "reason": reason}


def _task_text(task: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "dataset_source", "source_license", "input_uri", "input_sha256", "objective"):
        parts.append(str(task.get(key, "")))
    for key in ("caveats", "review_questions", "expected_outputs"):
        value = task.get(key, [])
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    return " ".join(parts).lower()


def score_source(task: dict[str, Any]) -> dict[str, Any]:
    source = str(task.get("dataset_source", "")).strip()
    source_url = str(task.get("source_url", "")).strip()
    source_citation = str(task.get("source_citation", "")).strip()
    input_uri = str(task.get("input_uri", "")).strip()
    source_lower = source.lower()

    if source_lower in SOURCE_WEAK_MARKERS:
        return _score(0, "source is missing, private, or unclear")
    if "synthetic-demo" in source_lower:
        return _score(2, "source is clearly marked as a synthetic demo")
    if source_url.startswith(("http://", "https://")) and source_citation:
        return _score(2, "public source URL and citation are present")
    if input_uri.startswith(("http://", "https://")) and source:
        return _score(2, "public input URI and source name are present")
    return _score(1, "source is named but attribution is limited")


def score_license(task: dict[str, Any]) -> dict[str, Any]:
    license_name = str(task.get("source_license", "")).strip().lower()
    if license_name in TASK_REJECTED_LICENSES:
        return _score(0, "license is missing or non-redistributable")
    if _has_any(license_name, PUBLIC_LICENSE_MARKERS):
        return _score(2, "license is explicit and redistributable")
    return _score(1, "license is explicit but not recognized by the checker")


def score_reproducibility(task: dict[str, Any]) -> dict[str, Any]:
    input_uri = str(task.get("input_uri", "")).strip()
    input_sha256 = str(task.get("input_sha256", "")).strip().lower()
    task_input = task.get("input")

    if not isinstance(task_input, dict) or not task_input:
        return _score(0, "input object is missing or empty")
    if input_sha256 in {"self-contained-demo", "metadata-only-public-fixture"}:
        return _score(2, "fixture is self-contained or explicitly metadata-only")
    if input_uri.startswith(("http://", "https://")):
        return _score(2, "input is clearly linked to a public URI")
    if input_uri.startswith("tasks/"):
        return _score(2, "input is a repository-local task fixture")
    if input_uri:
        return _score(1, "input URI is present but not clearly reproducible")
    return _score(0, "input URI is missing")


def score_review_value(task: dict[str, Any]) -> dict[str, Any]:
    questions = task.get("review_questions", [])
    expected_outputs = set(task.get("expected_outputs", []))
    objective = str(task.get("objective", "")).strip()

    if len(objective) < 24 or not questions:
        return _score(0, "objective or review questions are too vague")
    if REQUIRED_OUTPUTS <= expected_outputs and len(questions) >= 3:
        return _score(2, "review questions and expected outputs support auditable review")
    return _score(1, "review shape is usable but narrow or incomplete")


def score_caveats(task: dict[str, Any]) -> dict[str, Any]:
    caveats = task.get("caveats", [])
    if not isinstance(caveats, list) or not caveats:
        return _score(0, "caveats are missing")
    caveat_text = " ".join(str(item) for item in caveats)
    if len(caveats) >= 2 and _has_any(caveat_text, CAUTION_MARKERS):
        return _score(2, "conservative caveats are explicit")
    return _score(1, "caveats exist but are thin")


def score_privacy(task: dict[str, Any]) -> dict[str, Any]:
    findings = find_secret_paths(task)
    if findings:
        return _score(0, f"secret-like fields or values found: {', '.join(findings)}")

    input_uri = str(task.get("input_uri", ""))
    if _has_any(input_uri, PRIVATE_PATH_MARKERS):
        return _score(0, "input_uri appears to reference a private local path")
    return _score(2, "no credentials, private paths, or secret-like fields found")


def hard_rejections(task: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    try:
        validate_task(task)
    except Exception as exc:  # noqa: BLE001 - report validation failure as a hard rejection reason.
        reasons.append(str(exc))

    text = _task_text(task)
    if any(phrase in text for phrase in TASK_OVERCLAIM_PHRASES):
        reasons.append("task text invites unsupported extraterrestrial discovery claims")

    if str(task.get("source_license", "")).strip().lower() in TASK_REJECTED_LICENSES:
        reasons.append("source license is not explicitly redistributable")

    input_uri = str(task.get("input_uri", ""))
    if _has_any(input_uri, PRIVATE_PATH_MARKERS):
        reasons.append("task references a private local input path")

    if find_secret_paths(task):
        reasons.append("task contains secret-like fields or values")

    return sorted(set(reasons))


def score_task(task: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    categories = {
        "source": score_source(task),
        "license": score_license(task),
        "reproducibility": score_reproducibility(task),
        "review_value": score_review_value(task),
        "caveats": score_caveats(task),
        "privacy": score_privacy(task),
    }
    total = sum(category["score"] for category in categories.values())
    rejections = hard_rejections(task)
    status = "pass" if total >= MIN_ACCEPTED_SCORE and not rejections else "fail"
    return {
        "path": str(path) if path else None,
        "task_id": task.get("task_id"),
        "status": status,
        "score": total,
        "max_score": MAX_SCORE,
        "minimum_score": MIN_ACCEPTED_SCORE,
        "categories": categories,
        "hard_rejections": rejections,
    }


def task_paths(root: Path, requested: list[Path]) -> list[Path]:
    if requested:
        return [path if path.is_absolute() else root / path for path in requested]
    return sorted((root / "tasks").glob("*.json"))


def check_tasks(root: Path, requested: list[Path]) -> list[dict[str, Any]]:
    reports = []
    for path in task_paths(root, requested):
        path = path.resolve()
        payload = load_json(path)
        if not isinstance(payload, dict):
            raise ValidationError(f"{path} must contain a JSON object")
        reports.append(score_task(payload, path.relative_to(root) if path.is_relative_to(root) else path))
    if not reports:
        raise ValidationError("no task files found")
    return reports


def print_human_report(reports: list[dict[str, Any]]) -> None:
    for report in reports:
        print(
            f"{report['status'].upper()} {report['path']} "
            f"{report['score']}/{report['max_score']} task_id={report['task_id']}"
        )
        for name, category in report["categories"].items():
            print(f"  {name}: {category['score']}/2 - {category['reason']}")
        for reason in report["hard_rejections"]:
            print(f"  hard_rejection: {reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score OSAN tasks against the public intake rubric.")
    parser.add_argument("tasks", nargs="*", type=Path, help="Task JSON files. Defaults to tasks/*.json.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON report.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        reports = check_tasks(root, args.tasks)
    except Exception as exc:  # noqa: BLE001 - CLI should return readable validation failures.
        print(f"invalid: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"tasks": reports}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human_report(reports)

    if any(report["status"] != "pass" for report in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
