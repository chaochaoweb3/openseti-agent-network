"""Release smoke test for the local coordinator and dry-run worker path."""

from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .server import build_server
from .worker import get_json, run_task, submit_result


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_release_smoke(
    root: Path,
    task_id: str,
    repeat: int,
    worker_prefix: str,
    host: str = "127.0.0.1",
    port: int = 0,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run repeated dry-run submissions through the local HTTP coordinator."""
    if repeat <= 0:
        raise ValueError("repeat must be > 0")

    root = root.resolve()
    run_id = run_id or _run_id()
    server = build_server(root, host, port, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bound_host, bound_port = server.server_address
    base_url = f"http://{bound_host}:{bound_port}"

    try:
        health = get_json(f"{base_url}/v1/health")
        if health.get("ok") is not True:
            raise RuntimeError(f"coordinator health check failed: {health}")

        task = get_json(f"{base_url}/v1/tasks/{task_id}")
        baseline_summary = get_json(f"{base_url}/v1/tasks/{task_id}/summary")
        baseline_count = int(baseline_summary.get("result_count") or 0)
        submitted_workers: list[str] = []

        for index in range(1, repeat + 1):
            worker_id = f"{worker_prefix}-{run_id}-{index:06d}"
            payload = run_task(
                task=task,
                provider="dry-run",
                model="dry-run-reviewer-v1",
                worker_id=worker_id,
                max_cost_usd=0,
            )
            response = submit_result(base_url, payload)
            if response.get("ok") is not True:
                raise RuntimeError(f"coordinator rejected result: {response}")
            submitted_workers.append(worker_id)

        leaderboard = get_json(f"{base_url}/v1/leaderboard")
        final_summary = get_json(f"{base_url}/v1/tasks/{task_id}/summary")
        final_count = int(final_summary.get("result_count") or 0)
        added_count = final_count - baseline_count
        if added_count < repeat:
            raise RuntimeError(
                f"expected at least {repeat} new result(s), got {added_count} "
                f"(baseline={baseline_count}, final={final_count})"
            )

        missing_workers = [worker for worker in submitted_workers if worker not in final_summary["workers"]]
        if missing_workers:
            raise RuntimeError(f"submitted workers missing from task summary: {missing_workers}")

        return {
            "ok": True,
            "base_url": base_url,
            "task_id": task_id,
            "run_id": run_id,
            "submitted": repeat,
            "baseline_result_count": baseline_count,
            "final_result_count": final_count,
            "added_result_count": added_count,
            "workers": submitted_workers,
            "leaderboard": leaderboard,
            "summary": final_summary,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the OSAN local release smoke test.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--task-id", default="openseti-demo-001")
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--worker-prefix", default="release-smoke")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)

    result = run_release_smoke(
        root=args.root,
        task_id=args.task_id,
        repeat=args.repeat,
        worker_prefix=args.worker_prefix,
        host=args.host,
        port=args.port,
        run_id=args.run_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
