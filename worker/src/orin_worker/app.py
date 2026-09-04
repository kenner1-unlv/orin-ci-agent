from __future__ import annotations

import json
import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from orin_worker import __version__
from orin_worker.editor import EditorSettings, JobRejected, JobRunner

LOG = logging.getLogger("orin_worker")


def settings() -> tuple[str, int, EditorSettings]:
    host = os.environ.get("WORKER_HOST", "127.0.0.1")
    port = int(os.environ.get("WORKER_PORT", "8765"))
    state_dir = Path(
        os.environ.get(
            "WORKER_STATE_DIR",
            str(Path.home() / ".local" / "state" / "persistent-worker"),
        )
    )
    editor = EditorSettings(
        worktree_root=Path(os.environ.get("WORKER_WORKTREE_ROOT", "/data/persistent-worker/worktrees")),
        state_dir=state_dir,
        artifact_dir=Path(os.environ.get("WORKER_ARTIFACT_DIR", str(state_dir / "artifacts"))),
        model_url=os.environ.get("WORKER_MODEL_URL", "http://127.0.0.1:11434"),
        model=os.environ.get("WORKER_MODEL", "qwen3-coder:30b-a3b-q4_K_M"),
        max_iterations=int(os.environ.get("WORKER_MAX_ITERATIONS", "30")),
        timeout_seconds=int(os.environ.get("WORKER_JOB_TIMEOUT", "300")),
        think=os.environ.get("WORKER_MODEL_THINK", "false").lower() == "true",
        context_tokens=int(os.environ.get("WORKER_MODEL_CONTEXT", "32768")),
    )
    return host, port, editor


class WorkerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], config: EditorSettings, model_client: Any | None = None):
        self.state_dir = config.state_dir
        self.jobs = JobRunner(config, model_client)
        super().__init__(address, WorkerHandler)


class WorkerHandler(BaseHTTPRequestHandler):
    server: WorkerServer

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", "version": __version__})
            return
        if self.path == "/ready":
            try:
                self.server.state_dir.mkdir(parents=True, exist_ok=True)
                probe = self.server.state_dir / ".ready"
                probe.touch(exist_ok=True)
            except OSError as exc:
                LOG.exception("Readiness probe failed")
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"status": "not_ready", "reason": type(exc).__name__},
                )
                return
            self._json(HTTPStatus.OK, {"status": "ready"})
            return
        if self.path.startswith("/v1/jobs/"):
            job = self.server.jobs.load(self.path.removeprefix("/v1/jobs/"))
            if job is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            else:
                self._json(HTTPStatus.OK, job)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/v1/jobs":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 16_384:
                    raise JobRejected("request body must contain 1 to 16384 bytes")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise JobRejected("request body must be a JSON object")
                result = self.server.jobs.run(payload)
            except (JobRejected, json.JSONDecodeError, KeyError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "job_rejected", "message": str(exc)})
                return
            self._json(HTTPStatus.CREATED, result)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, message: str, *args: object) -> None:
        LOG.info("%s - %s", self.client_address[0], message % args)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("WORKER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    host, port, editor = settings()
    server = WorkerServer((host, port), editor)
    LOG.info("Worker %s listening on http://%s:%s", __version__, host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Shutdown requested")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
