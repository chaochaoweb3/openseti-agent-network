"""Small local coordinator API for volunteer tasks."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .repository import Repository
from .validator import validate_result

MAX_REQUEST_BYTES = 1_000_000


def json_bytes(payload: Any, status: int = 200) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


class CoordinatorHandler(BaseHTTPRequestHandler):
    repo: Repository

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json_bytes(payload, status)
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> Any:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0:
            raise ValueError("missing request body")
        if length > MAX_REQUEST_BYTES:
            raise ValueError(f"request body exceeds {MAX_REQUEST_BYTES} bytes")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.removeprefix("/v1")
        if path == "/health":
            self.send_json({"ok": True})
            return

        if path == "/tasks/next":
            task = self.repo.next_task()
            if task is None:
                self.send_json({"error": "no tasks available"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(task)
            return

        if path.startswith("/tasks/"):
            task_id = unquote(path.removeprefix("/tasks/"))
            task = self.repo.get_task(task_id)
            if task is None:
                self.send_json({"error": "task not found", "task_id": task_id}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(task)
            return

        if path == "/leaderboard":
            self.send_json(self.repo.leaderboard())
            return

        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.removeprefix("/v1")
        if path != "/results":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self.read_json()
            if not isinstance(payload, dict):
                raise ValueError("top-level payload must be an object")
            validate_result(payload)
            if self.repo.get_task(payload["task_id"]) is None:
                raise ValueError(f"unknown task_id: {payload['task_id']}")
            path = self.repo.save_result(payload)
        except Exception as exc:  # noqa: BLE001 - API returns readable client errors.
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json({"ok": True, "path": str(path.relative_to(self.repo.root))}, HTTPStatus.CREATED)


def build_server(root: Path, host: str, port: int) -> ThreadingHTTPServer:
    repo = Repository(root)

    class Handler(CoordinatorHandler):
        pass

    Handler.repo = repo
    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the OSAN local coordinator.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    server = build_server(args.root.resolve(), args.host, args.port)
    print(f"OSAN coordinator listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
