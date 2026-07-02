"""Task fixture manifest generation and validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .validator import ValidationError, load_json, validate_task


MANIFEST_VERSION = 1
DEFAULT_MANIFEST = Path("tasks.manifest.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def task_entry(root: Path, path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValidationError(f"{path} must contain a JSON object")
    validate_task(payload)
    return {
        "path": path.relative_to(root).as_posix(),
        "task_id": payload["task_id"],
        "domain": payload["domain"],
        "task_type": payload["task_type"],
        "source_license": payload["source_license"],
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def build_task_manifest(root: Path) -> dict[str, Any]:
    tasks_dir = root / "tasks"
    task_paths = sorted(path for path in tasks_dir.glob("*.json") if path.is_file())
    return {
        "manifest_version": MANIFEST_VERSION,
        "tasks": [task_entry(root, path) for path in task_paths],
    }


def validate_manifest_shape(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValidationError("manifest must be a JSON object")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValidationError(f"manifest_version must be {MANIFEST_VERSION}")

    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValidationError("tasks must be a non-empty array")

    seen_paths: set[str] = set()
    seen_task_ids: set[str] = set()
    required = {"path", "task_id", "domain", "task_type", "source_license", "sha256", "bytes"}
    for index, entry in enumerate(tasks):
        if not isinstance(entry, dict):
            raise ValidationError(f"tasks[{index}] must be an object")
        missing = required - set(entry)
        if missing:
            raise ValidationError(f"tasks[{index}] missing fields: {', '.join(sorted(missing))}")
        extra = set(entry) - required
        if extra:
            raise ValidationError(f"tasks[{index}] has unknown fields: {', '.join(sorted(extra))}")

        for field in ("path", "task_id", "domain", "task_type", "source_license", "sha256"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValidationError(f"tasks[{index}].{field} must be a non-empty string")
        if not isinstance(entry["bytes"], int) or entry["bytes"] <= 0:
            raise ValidationError(f"tasks[{index}].bytes must be a positive integer")
        if len(entry["sha256"]) != 64 or any(char not in "0123456789abcdef" for char in entry["sha256"]):
            raise ValidationError(f"tasks[{index}].sha256 must be a lowercase SHA-256 hex digest")

        path = entry["path"]
        task_id = entry["task_id"]
        if path in seen_paths:
            raise ValidationError(f"duplicate manifest path: {path}")
        if task_id in seen_task_ids:
            raise ValidationError(f"duplicate manifest task_id: {task_id}")
        seen_paths.add(path)
        seen_task_ids.add(task_id)

    return manifest


def validate_task_manifest(root: Path, manifest_path: Path = DEFAULT_MANIFEST) -> None:
    expected = build_task_manifest(root)
    actual_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    actual = validate_manifest_shape(load_json(actual_path))
    if actual != expected:
        raise ValidationError(
            "task manifest is stale; run scripts/validate-task-manifest --write "
            "after reviewing task fixture changes"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or generate the OSAN task manifest.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--write", action="store_true", help="Rewrite the manifest file from tasks/*.json.")
    parser.add_argument("--print", action="store_true", help="Print the generated manifest to stdout.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest

    try:
        generated = build_task_manifest(root)
        if args.print:
            sys.stdout.write(canonical_json(generated))
            return 0
        if args.write:
            manifest_path.write_text(canonical_json(generated), encoding="utf-8")
            print(f"wrote: {manifest_path.relative_to(root)}")
            return 0
        validate_task_manifest(root, manifest_path)
    except Exception as exc:  # noqa: BLE001 - CLI should return readable validation failures.
        print(f"invalid: {exc}", file=sys.stderr)
        return 1

    print(f"valid: {manifest_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
