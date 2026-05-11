from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, stream_with_context


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent

SECRET = os.environ.get("REMOTE_CODEX_TOKEN", "ying")
PROMPT_FILE = Path(os.environ.get("REMOTE_CODEX_PROMPT", APP_ROOT / "prompt.md")).resolve()
CODEX_BIN = os.environ.get("REMOTE_CODEX_BIN", "codex")
CODEX_SANDBOX = os.environ.get("REMOTE_CODEX_SANDBOX", "workspace-write")
CODEX_APPROVAL = os.environ.get("REMOTE_CODEX_APPROVAL", "never")
CODEX_MODEL = os.environ.get("REMOTE_CODEX_MODEL")
HOST = os.environ.get("REMOTE_CODEX_HOST", "0.0.0.0")
PORT = int(os.environ.get("REMOTE_CODEX_PORT", "5000"))
MAX_LOG_LINES = int(os.environ.get("REMOTE_CODEX_MAX_LOG_LINES", "5000"))
LOG_DIR = Path(os.environ.get("REMOTE_CODEX_LOG_DIR", APP_ROOT / "logs")).resolve()

app = Flask(__name__)

job_lock = threading.Lock()
jobs: dict[str, "CodexJob"] = {}
current_job_id: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_token() -> bool:
    token = request.args.get("token") or request.form.get("token")
    header_token = request.headers.get("X-Remote-Token")
    auth_header = request.headers.get("Authorization", "")
    bearer_token = ""
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:].strip()
    return SECRET in {token, header_token, bearer_token}


def require_token() -> tuple[bool, Any]:
    if check_token():
        return True, None
    return False, (jsonify({"error": "unauthorized"}), 403)


class CodexJob:
    def __init__(self, prompt_file: Path) -> None:
        self.id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.prompt_file = prompt_file
        self.status = "queued"
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.returncode: int | None = None
        self.error: str | None = None
        self.command: list[str] = []
        self.lines: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self.process: subprocess.Popen[str] | None = None
        self.log_file = LOG_DIR / f"{self.id}.log"
        self._thread = threading.Thread(target=self._run, name=f"codex-job-{self.id}", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "returncode": self.returncode,
            "error": self.error,
            "prompt_file": str(self.prompt_file),
            "log_file": str(self.log_file),
            "command": redact_command(self.command),
            "line_count": len(self.lines),
        }

    def append(self, line: str) -> None:
        clean_line = line.rstrip("\r\n")
        self.lines.append(clean_line)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(clean_line + "\n")

    def stop(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return
        self.append("[server] stop requested")
        try:
            if os.name == "nt":
                process.terminate()
            else:
                process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)
        except Exception:
            process.kill()

    def _run(self) -> None:
        global current_job_id

        self.status = "running"
        self.started_at = utc_now()
        self.append(f"[server] job {self.id} started at {self.started_at}")
        self.append(f"[server] prompt file: {self.prompt_file}")

        try:
            prompt = self.prompt_file.read_text(encoding="utf-8")
        except Exception as exc:
            self.status = "failed"
            self.error = f"failed to read prompt file: {exc}"
            self.ended_at = utc_now()
            self.append(f"[server] {self.error}")
            self.append(f"[server] job ended at {self.ended_at}")
            return

        if not prompt.strip():
            self.status = "failed"
            self.error = "prompt file is empty"
            self.ended_at = utc_now()
            self.append("[server] prompt file is empty")
            self.append(f"[server] job ended at {self.ended_at}")
            return

        cmd = [
            CODEX_BIN,
            "exec",
            "--cd",
            str(REPO_ROOT),
            "--sandbox",
            CODEX_SANDBOX,
            "--ask-for-approval",
            CODEX_APPROVAL,
            "--color",
            "never",
        ]
        if CODEX_MODEL:
            cmd.extend(["--model", CODEX_MODEL])
        cmd.append("-")
        self.command = cmd
        self.append("[server] command: " + " ".join(redact_command(cmd)))

        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=REPO_ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=creationflags,
            )
            assert self.process.stdin is not None
            assert self.process.stdout is not None
            self.process.stdin.write(prompt)
            self.process.stdin.close()

            for line in self.process.stdout:
                self.append(line)

            self.returncode = self.process.wait()
            self.status = "succeeded" if self.returncode == 0 else "failed"
            self.append(f"[server] codex exited with code {self.returncode}")
        except Exception as exc:
            self.status = "failed"
            self.error = str(exc)
            self.append(f"[server] failed to run codex: {exc}")
        finally:
            self.ended_at = utc_now()
            self.append(f"[server] job ended at {self.ended_at}")
            with job_lock:
                if current_job_id == self.id:
                    current_job_id = None


def redact_command(cmd: list[str]) -> list[str]:
    return ["<token>" if part == SECRET else part for part in cmd]


def current_job() -> CodexJob | None:
    with job_lock:
        if current_job_id:
            return jobs.get(current_job_id)
        if not jobs:
            return None
        return jobs[next(reversed(jobs))]


def start_job() -> tuple[CodexJob | None, str | None]:
    global current_job_id
    with job_lock:
        if current_job_id:
            active = jobs[current_job_id]
            return None, f"job already running: {active.id}"
        job = CodexJob(PROMPT_FILE)
        jobs[job.id] = job
        current_job_id = job.id
    job.start()
    return job, None


def sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.route("/")
def index() -> str:
    return INDEX_HTML


@app.route("/run", methods=["GET", "POST"])
def run_codex() -> Any:
    ok, response = require_token()
    if not ok:
        return response

    job, error = start_job()
    if error:
        return jsonify({"error": error, "job": current_job().snapshot() if current_job() else None}), 409
    assert job is not None
    return jsonify({"status": "started", "job": job.snapshot()})


@app.route("/stop", methods=["POST"])
def stop_codex() -> Any:
    ok, response = require_token()
    if not ok:
        return response

    job = current_job()
    if job is None:
        return jsonify({"status": "idle"})
    job.stop()
    return jsonify({"status": "stopping", "job": job.snapshot()})


@app.route("/status")
def status() -> Any:
    ok, response = require_token()
    if not ok:
        return response

    job = current_job()
    return jsonify(
        {
            "server_time": utc_now(),
            "prompt_file": str(PROMPT_FILE),
            "repo_root": str(REPO_ROOT),
            "current_job": job.snapshot() if job else None,
        }
    )


@app.route("/log")
def log() -> Any:
    ok, response = require_token()
    if not ok:
        return response

    job = current_job()
    if job is None:
        return jsonify({"lines": []})
    return jsonify({"job": job.snapshot(), "lines": list(job.lines)})


@app.route("/events")
def events() -> Any:
    ok, response = require_token()
    if not ok:
        return response

    @stream_with_context
    def generate() -> Any:
        index = 0
        last_status = None
        while True:
            job = current_job()
            if job is None:
                yield sse_event("status", {"status": "idle", "server_time": utc_now()})
                time.sleep(2)
                continue

            snapshot = job.snapshot()
            if snapshot != last_status:
                yield sse_event("status", snapshot)
                last_status = snapshot

            lines = list(job.lines)
            while index < len(lines):
                yield sse_event("log", {"index": index, "text": lines[index]})
                index += 1

            if job.status in {"succeeded", "failed"} and index >= len(lines):
                yield sse_event("done", job.snapshot())
                break

            time.sleep(0.5)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return Response(generate(), mimetype="text/event-stream", headers=headers)


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Remote Runner</title>
  <style>
    :root { color-scheme: dark; font-family: Consolas, ui-monospace, SFMono-Regular, Menlo, monospace; }
    body { margin: 0; background: #111317; color: #e8edf2; }
    main { max-width: 1100px; margin: 0 auto; padding: 20px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
    h1 { font-size: 22px; margin: 0; font-weight: 700; }
    .controls { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    input { width: 180px; max-width: 45vw; border: 1px solid #3a4150; border-radius: 6px; padding: 9px 10px; background: #191d24; color: #e8edf2; }
    button { border: 1px solid #3a4150; border-radius: 6px; padding: 9px 12px; background: #242a34; color: #e8edf2; cursor: pointer; }
    button:hover { background: #2d3542; }
    button.primary { background: #2f6fed; border-color: #2f6fed; }
    button.danger { background: #74333a; border-color: #91434b; }
    .meta { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin: 16px 0; }
    .box { border: 1px solid #2b313d; border-radius: 6px; padding: 10px; background: #171b22; min-height: 42px; overflow-wrap: anywhere; }
    .label { color: #9aa7b7; font-size: 12px; margin-bottom: 5px; }
    #log { min-height: 65vh; max-height: 72vh; overflow: auto; white-space: pre-wrap; border: 1px solid #2b313d; border-radius: 6px; padding: 12px; background: #0b0d10; line-height: 1.45; }
    .muted { color: #9aa7b7; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Codex Remote Runner</h1>
      <div class="controls">
        <input id="token" type="password" placeholder="token" autocomplete="current-password">
        <button class="primary" id="run">Run</button>
        <button class="danger" id="stop">Stop</button>
        <button id="reconnect">Reconnect</button>
      </div>
    </header>
    <section class="meta">
      <div class="box"><div class="label">status</div><div id="status" class="muted">idle</div></div>
      <div class="box"><div class="label">prompt</div><div id="prompt" class="muted">loading</div></div>
      <div class="box"><div class="label">log file</div><div id="logfile" class="muted">none</div></div>
    </section>
    <pre id="log"></pre>
  </main>
  <script>
    const tokenInput = document.getElementById("token");
    const logEl = document.getElementById("log");
    const statusEl = document.getElementById("status");
    const promptEl = document.getElementById("prompt");
    const logfileEl = document.getElementById("logfile");
    let source = null;

    const urlToken = new URLSearchParams(location.search).get("token");
    if (urlToken) tokenInput.value = urlToken;

    function tokenParam() {
      return encodeURIComponent(tokenInput.value.trim());
    }

    function appendLog(text) {
      logEl.textContent += text + "\\n";
      logEl.scrollTop = logEl.scrollHeight;
    }

    async function api(path, method = "GET") {
      const response = await fetch(`${path}?token=${tokenParam()}`, { method });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || response.statusText);
      return data;
    }

    async function refreshStatus() {
      try {
        const data = await api("/status");
        promptEl.textContent = data.prompt_file || "";
        if (data.current_job) {
          statusEl.textContent = `${data.current_job.status} ${data.current_job.id}`;
          logfileEl.textContent = data.current_job.log_file || "";
        } else {
          statusEl.textContent = "idle";
          logfileEl.textContent = "none";
        }
      } catch (err) {
        statusEl.textContent = err.message;
      }
    }

    function connect() {
      if (source) source.close();
      source = new EventSource(`/events?token=${tokenParam()}`);
      source.addEventListener("status", event => {
        const data = JSON.parse(event.data);
        statusEl.textContent = data.id ? `${data.status} ${data.id}` : data.status;
        if (data.prompt_file) promptEl.textContent = data.prompt_file;
        if (data.log_file) logfileEl.textContent = data.log_file;
      });
      source.addEventListener("log", event => {
        appendLog(JSON.parse(event.data).text);
      });
      source.addEventListener("done", event => {
        const data = JSON.parse(event.data);
        statusEl.textContent = `${data.status} ${data.id}`;
      });
      source.onerror = () => {
        statusEl.textContent = "disconnected";
      };
    }

    document.getElementById("run").addEventListener("click", async () => {
      logEl.textContent = "";
      try {
        const data = await api("/run", "POST");
        statusEl.textContent = `${data.job.status} ${data.job.id}`;
        connect();
      } catch (err) {
        appendLog(`[browser] ${err.message}`);
      }
    });

    document.getElementById("stop").addEventListener("click", async () => {
      try {
        const data = await api("/stop", "POST");
        if (data.job) statusEl.textContent = `${data.job.status} ${data.job.id}`;
      } catch (err) {
        appendLog(`[browser] ${err.message}`);
      }
    });

    document.getElementById("reconnect").addEventListener("click", connect);
    refreshStatus();
    if (tokenInput.value) connect();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, threaded=True)
