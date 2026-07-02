import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from osan.server import build_server
from osan.worker import run_task


ROOT = Path(__file__).resolve().parents[1]


def read_json(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_server_task_result_leaderboard_flow(tmp_path):
    root = tmp_path
    (root / "tasks").mkdir()
    (root / "data").mkdir()
    task = json.loads((ROOT / "tasks" / "openseti-demo-001.json").read_text())
    (root / "tasks" / "openseti-demo-001.json").write_text(json.dumps(task), encoding="utf-8")

    server = build_server(root, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    try:
        next_task = read_json(f"{base_url}/v1/tasks/next")
        assert next_task["task_id"] == "openseti-demo-001"

        catalog = read_json(f"{base_url}/v1/tasks")
        assert catalog["tasks"][0]["task_id"] == "openseti-demo-001"
        assert catalog["tasks"][0]["result_count"] == 0
        assert catalog["tasks"][0]["needs_more_reviews"] is True

        payload = run_task(next_task, "dry-run", "dry-run-reviewer-v1", "server-test-worker", 0)
        status, response = post_json(f"{base_url}/v1/results", payload)
        assert status == 201
        assert response["ok"] is True

        leaderboard = read_json(f"{base_url}/v1/leaderboard")
        assert leaderboard["workers"][0]["worker_id"] == "server-test-worker"
        assert leaderboard["tasks"]["openseti-demo-001"]["result_count"] == 1
    finally:
        server.shutdown()
        server.server_close()


def test_server_task_summary_reports_consensus_and_disagreement(tmp_path):
    root = tmp_path
    (root / "tasks").mkdir()
    (root / "data").mkdir()
    task = json.loads((ROOT / "tasks" / "openseti-demo-001.json").read_text())
    (root / "tasks" / "openseti-demo-001.json").write_text(json.dumps(task), encoding="utf-8")

    server = build_server(root, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    try:
        next_task = read_json(f"{base_url}/v1/tasks/next")
        for worker_id in ("summary-worker-a", "summary-worker-b"):
            payload = run_task(next_task, "dry-run", "dry-run-reviewer-v1", worker_id, 0)
            status, response = post_json(f"{base_url}/v1/results", payload)
            assert status == 201
            assert response["ok"] is True

        dissenting = run_task(next_task, "dry-run", "dry-run-reviewer-v1", "summary-worker-c", 0)
        dissenting["recommendation"] = "needs_follow_up_observation"
        dissenting["result"]["classification"] = "interesting_but_unconfirmed"
        dissenting["confidence"] = 0.31
        status, response = post_json(f"{base_url}/v1/results", dissenting)
        assert status == 201
        assert response["ok"] is True

        summary = read_json(f"{base_url}/v1/tasks/openseti-demo-001/summary")
        assert summary["result_count"] == 3
        assert summary["unique_worker_count"] == 3
        assert summary["needs_more_reviews"] is False
        assert summary["has_disagreement"] is True
        assert summary["recommendations"] == {
            "needs_follow_up_observation": 1,
            "needs_human_review": 2,
        }
        assert summary["classifications"] == {
            "interesting_but_unconfirmed": 1,
            "likely_rfi_or_instrumental": 2,
        }
        assert summary["consensus_recommendation"] == "needs_human_review"
        assert summary["consensus_classification"] == "likely_rfi_or_instrumental"
        assert summary["mean_confidence"] == 0.557

        catalog = read_json(f"{base_url}/v1/tasks")
        assert catalog["tasks"][0]["result_count"] == 3
        assert catalog["tasks"][0]["has_disagreement"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_server_rejects_large_post_body(tmp_path):
    (tmp_path / "tasks").mkdir()
    server = build_server(tmp_path, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    request = urllib.request.Request(
        f"http://{host}:{port}/v1/results",
        data=b"x" * 1_000_001,
        headers={"content-type": "application/json"},
        method="POST",
    )

    try:
        try:
            urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            body = json.loads(exc.read().decode("utf-8"))
            assert "exceeds" in body["error"]
        except urllib.error.URLError as exc:
            reason = str(exc.reason)
            assert "Connection reset" in reason or "Broken pipe" in reason
        else:
            raise AssertionError("large body should be rejected")
    finally:
        server.shutdown()
        server.server_close()
