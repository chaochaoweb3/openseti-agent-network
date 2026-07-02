import json
from pathlib import Path

import pytest

from osan.validator import ValidationError, validate_task


ROOT = Path(__file__).resolve().parents[1]


def load_demo_task():
    return json.loads((ROOT / "tasks" / "openseti-demo-001.json").read_text())


def test_all_task_files_validate():
    for path in (ROOT / "tasks").glob("*.json"):
        validate_task(json.loads(path.read_text()))


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
