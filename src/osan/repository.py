"""Filesystem-backed task and result repository."""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .validator import validate_result, validate_task


MIN_INDEPENDENT_REVIEWS = 3


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
            validate_result(result)
            result["_path"] = str(path.relative_to(self.root))
            results.append(result)
        return results

    def task_catalog(self) -> list[dict[str, Any]]:
        summaries = {summary["task_id"]: summary for summary in self.task_summaries()}
        catalog = []
        for task in self.list_tasks():
            summary = summaries.get(task["task_id"], self._summarize_results(task["task_id"], []))
            catalog.append(
                {
                    "task_id": task["task_id"],
                    "domain": task["domain"],
                    "task_type": task["task_type"],
                    "title": task["title"],
                    "dataset_source": task["dataset_source"],
                    "source_license": task["source_license"],
                    "path": task["_path"],
                    "result_count": summary["result_count"],
                    "unique_worker_count": summary["unique_worker_count"],
                    "needs_more_reviews": summary["needs_more_reviews"],
                    "has_disagreement": summary["has_disagreement"],
                }
            )
        return catalog

    def task_summaries(self) -> list[dict[str, Any]]:
        results_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for result in self.list_results():
            results_by_task[result["task_id"]].append(result)

        task_ids = {task["task_id"] for task in self.list_tasks()} | set(results_by_task)
        return [
            self._summarize_results(task_id, results_by_task.get(task_id, []))
            for task_id in sorted(task_ids)
        ]

    def task_summary(self, task_id: str) -> dict[str, Any] | None:
        if self.get_task(task_id) is None:
            return None
        results = [result for result in self.list_results() if result["task_id"] == task_id]
        return self._summarize_results(task_id, results)

    def _summarize_results(self, task_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
        recommendation_counts = Counter(result["recommendation"] for result in results)
        classification_counts = Counter(result["result"]["classification"] for result in results)
        workers = sorted({result["worker_id"] for result in results})
        confidences = [float(result["confidence"]) for result in results]
        result_count = len(results)

        return {
            "task_id": task_id,
            "result_count": result_count,
            "unique_worker_count": len(workers),
            "independent_review_target": MIN_INDEPENDENT_REVIEWS,
            "needs_more_reviews": len(workers) < MIN_INDEPENDENT_REVIEWS,
            "has_disagreement": len(recommendation_counts) > 1 or len(classification_counts) > 1,
            "recommendations": dict(sorted(recommendation_counts.items())),
            "classifications": dict(sorted(classification_counts.items())),
            "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
            "consensus_recommendation": self._majority_value(recommendation_counts, result_count),
            "consensus_classification": self._majority_value(classification_counts, result_count),
            "workers": workers,
            "latest_created_at": max((result["created_at"] for result in results), default=None),
        }

    def _majority_value(self, counter: Counter[str], result_count: int) -> str | None:
        if result_count < MIN_INDEPENDENT_REVIEWS or not counter:
            return None

        [(value, count), *rest] = counter.most_common()
        if count <= result_count / 2:
            return None
        if rest and rest[0][1] == count:
            return None
        return value

    def leaderboard(self) -> dict[str, Any]:
        by_worker: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"worker_id": "", "valid_results": 0, "tasks": set(), "modes": set()}
        )

        for result in self.list_results():
            worker_id = result.get("worker_id", "unknown")
            task_id = result.get("task_id", "unknown")
            row = by_worker[worker_id]
            row["worker_id"] = worker_id
            row["valid_results"] += 1
            row["tasks"].add(task_id)
            row["modes"].add(result.get("mode", "unknown"))

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
            "tasks": {summary["task_id"]: summary for summary in self.task_summaries() if summary["result_count"]},
        }
