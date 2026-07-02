import json
import shutil
from pathlib import Path

import pytest

from osan.task_manifest import build_task_manifest, validate_task_manifest
from osan.validator import ValidationError, validate_task


ROOT = Path(__file__).resolve().parents[1]


def load_demo_task():
    return json.loads((ROOT / "tasks" / "openseti-demo-001.json").read_text())


def test_all_task_files_validate():
    for path in (ROOT / "tasks").glob("*.json"):
        validate_task(json.loads(path.read_text()))


def test_task_manifest_matches_current_task_files():
    validate_task_manifest(ROOT)


def test_task_manifest_contains_expected_task_ids():
    manifest = build_task_manifest(ROOT)
    task_ids = sorted(
        json.loads(path.read_text())["task_id"]
        for path in (ROOT / "tasks").glob("*.json")
    )

    assert [entry["task_id"] for entry in manifest["tasks"]] == task_ids


def test_task_manifest_rejects_stale_hash(tmp_path):
    shutil.copytree(ROOT / "tasks", tmp_path / "tasks")
    shutil.copy(ROOT / "tasks.manifest.json", tmp_path / "tasks.manifest.json")

    task_path = tmp_path / "tasks" / "openseti-demo-001.json"
    task = json.loads(task_path.read_text())
    task["caveats"].append("Temporary local edit that should change the file hash.")
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="manifest is stale"):
        validate_task_manifest(tmp_path)


def test_task_requires_source_license():
    task = load_demo_task()
    del task["source_license"]

    with pytest.raises(ValidationError, match="source_license"):
        validate_task(task)


def test_task_requires_caveats():
    task = load_demo_task()
    task["caveats"] = []

    with pytest.raises(ValidationError, match="caveats"):
        validate_task(task)


def test_task_rejects_private_license():
    task = load_demo_task()
    task["source_license"] = "private"

    with pytest.raises(ValidationError, match="source_license"):
        validate_task(task)


def test_task_rejects_discovery_overclaim():
    task = load_demo_task()
    task["title"] = "Confirmed extraterrestrial discovery from demo data"

    with pytest.raises(ValidationError, match="confirmed extraterrestrial"):
        validate_task(task)


def test_task_rejects_secret_fields():
    task = load_demo_task()
    task["input"]["api_key"] = "not-real"

    with pytest.raises(ValueError):
        validate_task(task)
