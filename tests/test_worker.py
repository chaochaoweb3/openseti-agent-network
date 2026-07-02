import json
from pathlib import Path

from osan.validator import validate_result
from osan.worker import get_json, main, run_task, submit_result


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


def test_dry_run_transit_task_generates_valid_result():
    task = json.loads((ROOT / "tasks" / "tess-spoc-transit-demo-001.json").read_text())

    payload = run_task(
        task=task,
        provider="dry-run",
        model="dry-run-reviewer-v1",
        worker_id="pytest-transit-worker",
        max_cost_usd=0,
    )

    validate_result(payload)
    assert payload["task_id"] == "tess-spoc-transit-demo-001"
    assert payload["result"]["classification"] == "ambiguous_candidate"
    assert payload["recommendation"] == "needs_human_review"
    assert "None MHz" not in payload["result"]["short_summary"]


def test_submit_result_posts_to_coordinator(tmp_path):
    from osan.server import build_server
    import threading

    (tmp_path / "tasks").mkdir()
    (tmp_path / "data").mkdir()
    task = json.loads((ROOT / "tasks" / "openseti-demo-001.json").read_text())
    (tmp_path / "tasks" / "openseti-demo-001.json").write_text(json.dumps(task), encoding="utf-8")

    server = build_server(tmp_path, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    try:
        fetched = get_json(f"{base_url}/v1/tasks/next")
        payload = run_task(fetched, "dry-run", "dry-run-reviewer-v1", "worker-submit-test", 0)
        response = submit_result(base_url, payload)
        assert response["ok"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_total_budget_stops_before_provider_call(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    task = ROOT / "tasks" / "openseti-demo-001.json"

    exit_code = main(
        [
            "--task",
            str(task),
            "--provider",
            "openai",
            "--repeat",
            "2",
            "--max-total-cost-usd",
            "0",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert not list(tmp_path.glob("*.json"))
