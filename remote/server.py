from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from flask import Flask, Response, jsonify, request, stream_with_context
from werkzeug.serving import WSGIRequestHandler


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent

SECRET = os.environ.get("REMOTE_CODEX_TOKEN", "ying")
PROMPT_FILE = Path(os.environ.get("REMOTE_CODEX_PROMPT", APP_ROOT / "prompt.md")).resolve()
CODEX_SANDBOX = os.environ.get("REMOTE_CODEX_SANDBOX", "workspace-write")
CODEX_APPROVAL = os.environ.get("REMOTE_CODEX_APPROVAL", "never")
CODEX_MODEL = os.environ.get("REMOTE_CODEX_MODEL")
HOST = os.environ.get("REMOTE_CODEX_HOST", "0.0.0.0")
PORT = int(os.environ.get("REMOTE_CODEX_PORT", "5000"))
MAX_LOG_LINES = int(os.environ.get("REMOTE_CODEX_MAX_LOG_LINES", "5000"))
SSE_BATCH_LINES = max(1, int(os.environ.get("REMOTE_CODEX_SSE_BATCH_LINES", "100")))
CONSOLE_LOGS = os.environ.get("REMOTE_CODEX_CONSOLE_LOGS", "1").lower() not in {"0", "false", "no", "off"}
FIX_MOJIBAKE = os.environ.get("REMOTE_CODEX_FIX_MOJIBAKE", "1").lower() not in {"0", "false", "no", "off"}
LOG_DIR = Path(os.environ.get("REMOTE_CODEX_LOG_DIR", APP_ROOT / "logs")).resolve()

app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

job_lock = threading.Lock()
console_lock = threading.Lock()
jobs: dict[str, "CodexJob"] = {}
current_job_id: str | None = None

MOJIBAKE_MARKERS = (
    "Ã",
    "Â",
    "â",
    "€",
    "鏂",
    "囨",
    "鍒",
    "鍏",
    "鍥",
    "涓",
    "浠",
    "杩",
    "璇",
    "鎴",
    "瀛",
    "绋",
    "銆",
    "锛",
    "妯",
    "绛",
    "搴",
    "瑙",
    "閫",
    "闃",
    "熀",
    "姝",
    "鍊",
    "浼",
    "蹇",
    "楂",
    "粏",
    "鍚",
    "彂",
    "獙",
)


class QuietRequestHandler(WSGIRequestHandler):
    def log_request(self, code: str | int = "-", size: str | int = "-") -> None:
        return

    def log_error(self, format: str, *args: Any) -> None:
        return


def resolve_codex_bin() -> str:
    configured = os.environ.get("REMOTE_CODEX_BIN")
    if configured:
        return configured

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin" / "codex.exe",
        Path(os.environ.get("APPDATA", "")) / "npm" / "codex.cmd",
        Path.home() / "AppData" / "Local" / "OpenAI" / "Codex" / "bin" / "codex.exe",
        Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which("codex")
    if found:
        return found

    return "codex"


CODEX_BIN = resolve_codex_bin()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def console_log(line: str) -> None:
    if not CONSOLE_LOGS:
        return
    with console_lock:
        try:
            print(line, flush=True)
        except Exception:
            return


def mojibake_score(text: str) -> int:
    marker_score = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    private_use_score = sum(1 for char in text if "\ue000" <= char <= "\uf8ff")
    return marker_score + private_use_score


def repair_mojibake(text: str) -> str:
    if not FIX_MOJIBAKE:
        return text

    original_score = mojibake_score(text)
    if original_score == 0:
        return text

    best_text = text
    best_score = original_score
    for encoding in ("gb18030", "gbk", "cp936"):
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        candidate_score = mojibake_score(candidate)
        if candidate_score < best_score:
            best_text = candidate
            best_score = candidate_score
    return best_text


def client_addr() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


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


def build_codex_command() -> list[str]:
    cmd = [CODEX_BIN]
    if CODEX_APPROVAL:
        cmd.extend(["--ask-for-approval", CODEX_APPROVAL])
    cmd.extend(
        [
            "exec",
            "--cd",
            str(REPO_ROOT),
            "--sandbox",
            CODEX_SANDBOX,
            "--color",
            "never",
        ]
    )
    if CODEX_MODEL:
        cmd.extend(["--model", CODEX_MODEL])
    cmd.append("-")
    return cmd


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
        self.lines: deque[tuple[int, str]] = deque(maxlen=MAX_LOG_LINES)
        self.next_seq = 0
        self.process: subprocess.Popen[str] | None = None
        self.log_file = LOG_DIR / f"{self.id}.log"
        self._condition = threading.Condition()
        self._log_handle: TextIO | None = None
        self._log_file_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name=f"codex-job-{self.id}", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            line_count = self.next_seq
            retained_lines = len(self.lines)
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
            "line_count": line_count,
            "retained_lines": retained_lines,
        }

    def append(self, line: str) -> None:
        clean_line = repair_mojibake(line.rstrip("\r\n"))
        with self._condition:
            seq = self.next_seq
            self.next_seq += 1
            self.lines.append((seq, clean_line))
            self._condition.notify_all()
        console_log(clean_line)
        self._write_log_line(clean_line)

    def _write_log_line(self, line: str) -> None:
        with self._log_file_lock:
            if self._log_handle is not None:
                self._log_handle.write(line + "\n")
                self._log_handle.flush()
                return
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with self.log_file.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(line + "\n")

    def log_lines(self) -> list[str]:
        with self._condition:
            return [line for _, line in self.lines]

    def log_entries_after(self, after_seq: int) -> tuple[list[tuple[int, str]], int]:
        with self._condition:
            if not self.lines:
                return [], 0
            oldest_seq = self.lines[0][0]
            dropped = max(0, oldest_seq - after_seq - 1)
            return [(seq, line) for seq, line in self.lines if seq > after_seq], dropped

    def wait_for_log_change(self, timeout: float) -> None:
        with self._condition:
            self._condition.wait(timeout=timeout)

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
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with self.log_file.open("a", encoding="utf-8", errors="replace") as fh:
                with self._log_file_lock:
                    self._log_handle = fh
                try:
                    self.append(f"[server] job {self.id} started at {self.started_at}")
                    self.append(f"[server] prompt file: {self.prompt_file}")

                    try:
                        prompt = self.prompt_file.read_text(encoding="utf-8")
                    except Exception as exc:
                        self.status = "failed"
                        self.error = f"failed to read prompt file: {exc}"
                        self.append(f"[server] {self.error}")
                        return

                    if not prompt.strip():
                        self.status = "failed"
                        self.error = "prompt file is empty"
                        self.append("[server] prompt file is empty")
                        return

                    cmd = build_codex_command()
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
                    with self._log_file_lock:
                        self._log_handle = None
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


@app.route("/favicon.ico")
def favicon() -> Response:
    return Response(status=204)


@app.route("/run", methods=["GET", "POST"])
def run_codex() -> Any:
    ok, response = require_token()
    if not ok:
        console_log(f"[server] unauthorized run request from {client_addr()}")
        return response

    console_log(f"[server] run requested from {client_addr()}")
    job, error = start_job()
    if error:
        console_log(f"[server] run rejected: {error}")
        return jsonify({"error": error, "job": current_job().snapshot() if current_job() else None}), 409
    assert job is not None
    return jsonify({"status": "started", "job": job.snapshot()})


@app.route("/stop", methods=["POST"])
def stop_codex() -> Any:
    ok, response = require_token()
    if not ok:
        console_log(f"[server] unauthorized stop request from {client_addr()}")
        return response

    console_log(f"[server] stop requested from {client_addr()}")
    job = current_job()
    if job is None:
        console_log("[server] stop ignored: no current job")
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
            "command_template": redact_command(build_codex_command()),
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
    return jsonify({"job": job.snapshot(), "lines": job.log_lines()})


@app.route("/events")
def events() -> Any:
    ok, response = require_token()
    if not ok:
        return response

    @stream_with_context
    def generate() -> Any:
        request_job_id = request.args.get("job") or ""
        try:
            last_seq = int(request.args.get("after", "-1"))
        except ValueError:
            last_seq = -1
        active_job_id = request_job_id
        last_status_key = None
        next_heartbeat = 0.0
        while True:
            job = current_job()
            if job is None:
                yield sse_event("status", {"status": "idle", "server_time": utc_now()})
                time.sleep(2)
                continue

            if job.id != active_job_id:
                active_job_id = job.id
                last_seq = -1
                last_status_key = None

            snapshot = job.snapshot()
            status_key = (
                snapshot["id"],
                snapshot["status"],
                snapshot["started_at"],
                snapshot["ended_at"],
                snapshot["returncode"],
                snapshot["error"],
            )
            now = time.monotonic()
            if status_key != last_status_key or now >= next_heartbeat:
                yield sse_event("status", snapshot)
                last_status_key = status_key
                next_heartbeat = now + 5

            entries, dropped = job.log_entries_after(last_seq)
            if dropped:
                yield sse_event(
                    "log",
                    {
                        "job_id": job.id,
                        "seq": last_seq + dropped,
                        "index": last_seq + dropped,
                        "text": f"[server] skipped {dropped} old retained log lines during reconnect",
                    },
                )
                last_seq += dropped
            for offset in range(0, len(entries), SSE_BATCH_LINES):
                chunk = entries[offset : offset + SSE_BATCH_LINES]
                if len(chunk) == 1:
                    seq, line = chunk[0]
                    yield sse_event("log", {"job_id": job.id, "seq": seq, "index": seq, "text": line})
                else:
                    yield sse_event(
                        "log_batch",
                        {
                            "job_id": job.id,
                            "entries": [
                                {"seq": seq, "index": seq, "text": line}
                                for seq, line in chunk
                            ],
                        },
                    )
                last_seq = chunk[-1][0]

            if job.status in {"succeeded", "failed"} and not entries:
                yield sse_event("done", job.snapshot())
                break

            job.wait_for_log_change(timeout=0.5)

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
    #log { min-height: 65vh; max-height: 72vh; overflow: auto; white-space: pre-wrap; border: 1px solid #2b313d; border-radius: 6px; padding: 12px; background: #0b0d10; line-height: 1.45; overflow-anchor: none; contain: content; }
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
        <button id="copy">Copy Log</button>
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
    const MAX_RENDERED_LINES = 1200;
    let source = null;
    let reconnectTimer = null;
    let activeJobId = null;
    let lastSeq = -1;
    let logLines = [];
    let pendingLogLines = [];
    let flushTimer = 0;

    const urlToken = new URLSearchParams(location.search).get("token");
    if (urlToken) tokenInput.value = urlToken;

    function buildUrl(path, extra = {}) {
      const params = new URLSearchParams();
      const token = tokenInput.value.trim();
      if (token) params.set("token", token);
      for (const [key, value] of Object.entries(extra)) {
        if (value !== undefined && value !== null && value !== "") {
          params.set(key, String(value));
        }
      }
      const query = params.toString();
      return query ? `${path}?${query}` : path;
    }

    function appendLog(text) {
      pendingLogLines.push(text);
      if (!flushTimer) flushTimer = window.setTimeout(flushLog, 80);
    }

    function flushLog() {
      if (flushTimer) {
        window.clearTimeout(flushTimer);
        flushTimer = 0;
      }
      if (!pendingLogLines.length) return;

      const shouldStick = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 24;
      const batch = pendingLogLines;
      pendingLogLines = [];
      logLines.push(...batch);

      if (logLines.length > MAX_RENDERED_LINES) {
        logLines = logLines.slice(-MAX_RENDERED_LINES);
        logEl.textContent = logLines.join("\\n") + "\\n";
      } else {
        logEl.appendChild(document.createTextNode(batch.join("\\n") + "\\n"));
      }

      if (shouldStick) logEl.scrollTop = logEl.scrollHeight;
    }

    function resetLogState() {
      if (flushTimer) {
        window.clearTimeout(flushTimer);
        flushTimer = 0;
      }
      logLines = [];
      pendingLogLines = [];
      lastSeq = -1;
      logEl.textContent = "";
    }

    async function copyLog() {
      flushLog();
      const button = document.getElementById("copy");
      const original = button.textContent;
      try {
        let text = logLines.join("\\n");
        try {
          const data = await api("/log");
          if (Array.isArray(data.lines)) text = data.lines.join("\\n");
        } catch (_) {
          text = logEl.textContent;
        }
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
        } else {
          const textarea = document.createElement("textarea");
          textarea.value = text;
          textarea.setAttribute("readonly", "");
          textarea.style.position = "fixed";
          textarea.style.left = "-9999px";
          document.body.appendChild(textarea);
          textarea.focus();
          textarea.select();
          textarea.setSelectionRange(0, textarea.value.length);
          document.execCommand("copy");
          document.body.removeChild(textarea);
        }
        button.textContent = "Copied";
      } catch (err) {
        button.textContent = "Copy failed";
        appendLog(`[browser] ${err.message}`);
      } finally {
        setTimeout(() => { button.textContent = original; }, 1200);
      }
    }

    async function api(path, method = "GET") {
      const response = await fetch(buildUrl(path), { method });
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
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      const cursor = activeJobId ? { job: activeJobId, after: lastSeq } : {};
      source = new EventSource(buildUrl("/events", cursor));
      const handleLogEntry = data => {
        if (data.job_id && data.job_id !== activeJobId) {
          activeJobId = data.job_id;
          resetLogState();
        }
        const seq = Number(data.seq ?? data.index ?? -1);
        if (seq <= lastSeq) return;
        lastSeq = seq;
        appendLog(data.text);
      };
      source.addEventListener("status", event => {
        const data = JSON.parse(event.data);
        statusEl.textContent = data.id ? `${data.status} ${data.id}` : data.status;
        if (data.id && data.id !== activeJobId) {
          activeJobId = data.id;
          resetLogState();
        }
        if (data.prompt_file) promptEl.textContent = data.prompt_file;
        if (data.log_file) logfileEl.textContent = data.log_file;
      });
      source.addEventListener("log", event => {
        handleLogEntry(JSON.parse(event.data));
      });
      source.addEventListener("log_batch", event => {
        const data = JSON.parse(event.data);
        const jobId = data.job_id || activeJobId;
        for (const entry of data.entries || []) {
          handleLogEntry({ ...entry, job_id: jobId });
        }
      });
      source.addEventListener("done", event => {
        flushLog();
        const data = JSON.parse(event.data);
        statusEl.textContent = `${data.status} ${data.id}`;
        if (source) {
          source.close();
          source = null;
        }
      });
      source.onerror = () => {
        statusEl.textContent = "disconnected";
        if (source) {
          source.close();
          source = null;
        }
        if (!reconnectTimer) reconnectTimer = window.setTimeout(connect, 1200);
      };
    }

    document.getElementById("run").addEventListener("click", async () => {
      if (source) {
        source.close();
        source = null;
      }
      resetLogState();
      try {
        const data = await api("/run", "POST");
        statusEl.textContent = `${data.job.status} ${data.job.id}`;
        activeJobId = data.job.id;
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
    document.getElementById("copy").addEventListener("click", copyLog);
    refreshStatus();
    if (tokenInput.value) connect();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    console_log(f"[server] remote runner starting at {utc_now()}")
    console_log(f"[server] listen: http://{HOST}:{PORT}")
    console_log(f"[server] repo root: {REPO_ROOT}")
    console_log(f"[server] prompt file: {PROMPT_FILE}")
    console_log(f"[server] codex bin: {CODEX_BIN}")
    console_log(f"[server] console logs: {'enabled' if CONSOLE_LOGS else 'disabled'}")
    console_log(f"[server] mojibake repair: {'enabled' if FIX_MOJIBAKE else 'disabled'}")
    app.run(host=HOST, port=PORT, threaded=True, request_handler=QuietRequestHandler)
