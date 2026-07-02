"""Filesystem-backed task and result repository."""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .validator import validate_task


class Repository:
    def __init__(self, root: Path):
        self.root = root
        self.tasks_dir = root / "tasks"
        self.results_dir = root / "data" / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def list_tasks(self) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        for path in sorted(self.tasks_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                task = json.load(handle)
            validate_task(task)
            task["_path"] = str(path.relative_to(self.root))
            tasks.append(task)
        return tasks

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        for task in self.list_tasks():
            if task.get("task_id") == task_id:
                return task
        return None

    def next_task(self) -> dict[str, Any] | None:
        tasks = self.list_tasks()
        if not tasks:
            return None

        counts = Counter(result.get("task_id") for result in self.list_results())
        return min(tasks, key=lambda task: (counts[task.get("task_id")], task.get("task_id", "")))

    def result_path(self, task_id: str, worker_id: str) -> Path:
        safe_task = "".join(char for char in task_id if char.isalnum() or char in "._-")
        safe_worker = "".join(char for char in worker_id if char.isalnum() or char in "._-")
        return self.results_dir / f"{safe_task}--{safe_worker}.json"

    def save_result(self, payload: dict[str, Any]) -> Path:
        path = self.result_path(payload["task_id"], payload["worker_id"])
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            tmp_name = handle.name
        os.replace(tmp_name, path)
        return path

    def list_results(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for path in sorted(self.results_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                result = json.load(handle)
            result["_path"] = str(path.relative_to(self.root))
            results.append(result)
        return results

    def leaderboard(self) -> dict[str, Any]:
        by_worker: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"worker_id": "", "valid_results": 0, "tasks": set(), "modes": set()}
        )
        by_task: dict[str, Counter[str]] = defaultdict(Counter)

        for result in self.list_results():
            worker_id = result.get("worker_id", "unknown")
            task_id = result.get("task_id", "unknown")
            row = by_worker[worker_id]
            row["worker_id"] = worker_id
            row["valid_results"] += 1
            row["tasks"].add(task_id)
            row["modes"].add(result.get("mode", "unknown"))
            by_task[task_id][result.get("recommendation", "unknown")] += 1

        workers = []
        for row in by_worker.values():
            workers.append(
                {
                    "worker_id": row["worker_id"],
                    "valid_results": row["valid_results"],
                    "unique_tasks": len(row["tasks"]),
                    "modes": sorted(row["modes"]),
                }
            )

        workers.sort(key=lambda item: (-item["valid_results"], item["worker_id"]))

        return {
            "workers": workers,
            "tasks": {
                task_id: {
                    "result_count": sum(counter.values()),
                    "recommendations": dict(counter),
                    "has_disagreement": len(counter) > 1,
                }
                for task_id, counter in sorted(by_task.items())
            },
        }
