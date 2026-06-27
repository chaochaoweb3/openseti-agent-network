import json
from pathlib import Path

from osan.validator import validate_result
from osan.worker import run_task


ROOT = Path(__file__).resolve().parents[1]


def test_dry_run_worker_generates_valid_result():
    task = json.loads((ROOT / "tasks" / "openseti-demo-001.json").read_text())

    payload = run_task(
        task=task,
        provider="dry-run",
        model="dry-run-reviewer-v1",
        worker_id="pytest-worker",
        max_cost_usd=0,
    )

    validate_result(payload)
    assert payload["task_id"] == "openseti-demo-001"
    assert payload["mode"] == "api-worker"
    assert "api_key" not in json.dumps(payload).lower()
