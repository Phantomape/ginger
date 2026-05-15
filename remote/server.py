from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from copy import deepcopy
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
OPEN_POSITIONS_FILE = Path(
    os.environ.get("REMOTE_CODEX_OPEN_POSITIONS", REPO_ROOT / "operator_inputs" / "open_positions.json")
).resolve()
OPEN_POSITIONS_SECTIONS = ("observations", "positions")
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,15}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

job_lock = threading.Lock()
console_lock = threading.Lock()
open_positions_lock = threading.Lock()
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


def json_error(message: str, status: int = 400, **extra: Any) -> tuple[Any, int]:
    payload: dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def open_positions_audit_path() -> Path:
    return LOG_DIR / "open_positions_edits.jsonl"


def open_positions_backup_dir() -> Path:
    return LOG_DIR / "open_positions_backups"


def load_open_positions_payload() -> dict[str, Any]:
    with OPEN_POSITIONS_FILE.open("r", encoding="utf-8-sig") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("open_positions payload must be a JSON object")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{uuid.uuid4().hex}")
    text = json.dumps(payload, ensure_ascii=False, indent=4, allow_nan=False) + "\n"
    try:
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def backup_open_positions() -> str | None:
    if not OPEN_POSITIONS_FILE.exists():
        return None
    backup_dir = open_positions_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    backup_path = backup_dir / f"open_positions_{suffix}.json"
    shutil.copy2(OPEN_POSITIONS_FILE, backup_path)
    return str(backup_path)


def normalize_ticker(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    ticker = value.strip().upper()
    if not TICKER_RE.match(ticker):
        return None
    return ticker


def coerce_number(
    row: dict[str, Any],
    field: str,
    path: str,
    errors: list[str],
    *,
    required: bool,
    positive: bool = False,
    allow_null: bool = False,
) -> None:
    if field not in row or row.get(field) == "":
        if required:
            errors.append(f"{path}.{field} is required")
        return
    value = row.get(field)
    if value is None:
        if allow_null:
            return
        errors.append(f"{path}.{field} cannot be null")
        return
    if isinstance(value, bool):
        errors.append(f"{path}.{field} must be numeric")
        return
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        errors.append(f"{path}.{field} must be numeric")
        return
    if not numeric == numeric or numeric in {float("inf"), float("-inf")}:
        errors.append(f"{path}.{field} must be finite")
        return
    if positive and numeric <= 0:
        errors.append(f"{path}.{field} must be > 0")
        return
    row[field] = int(numeric) if numeric.is_integer() else numeric


def validate_date_field(row: dict[str, Any], field: str, path: str, errors: list[str]) -> None:
    value = row.get(field)
    if not isinstance(value, str) or not DATE_RE.match(value.strip()):
        errors.append(f"{path}.{field} must be YYYY-MM-DD")
        return
    row[field] = value.strip()


def validate_position_row(raw: Any, section: str, index: int, seen: set[str], errors: list[str]) -> dict[str, Any]:
    path = f"{section}[{index}]"
    if not isinstance(raw, dict):
        errors.append(f"{path} must be an object")
        return {}

    row = deepcopy(raw)
    ticker = normalize_ticker(row.get("ticker"))
    if ticker is None:
        errors.append(f"{path}.ticker must be an uppercase ticker-like string")
    elif ticker in seen:
        errors.append(f"{path}.ticker duplicates another {section} row")
    else:
        seen.add(ticker)
        row["ticker"] = ticker

    direction = row.get("direction")
    if not isinstance(direction, str) or direction.strip().lower() not in {"long", "short"}:
        errors.append(f"{path}.direction must be long or short")
    else:
        row["direction"] = direction.strip().lower()

    coerce_number(row, "shares", path, errors, required=True, positive=True)
    coerce_number(row, "original_shares", path, errors, required=False, positive=True)
    coerce_number(row, "avg_cost", path, errors, required=True, positive=True)
    coerce_number(row, "target_price", path, errors, required=True, positive=True)
    coerce_number(row, "stop_price", path, errors, required=True, positive=True)
    validate_date_field(row, "entry_date", path, errors)

    strategy = row.get("opened_by_strategy")
    if strategy is None:
        row["opened_by_strategy"] = "manual"
    elif not isinstance(strategy, str):
        errors.append(f"{path}.opened_by_strategy must be a string")
    else:
        row["opened_by_strategy"] = strategy.strip() or "manual"

    notes = row.get("risk_notes")
    if notes is None:
        row["risk_notes"] = ""
    elif not isinstance(notes, str):
        errors.append(f"{path}.risk_notes must be a string")

    return row


def validate_open_positions_payload(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(raw, dict):
        return None, ["payload must be a JSON object"]

    payload = deepcopy(raw)
    as_of = payload.get("as_of")
    if as_of is not None:
        if not isinstance(as_of, str) or not DATE_RE.match(as_of.strip()):
            errors.append("as_of must be YYYY-MM-DD when present")
        else:
            payload["as_of"] = as_of.strip()

    account = payload.get("account")
    if account is not None and not isinstance(account, str):
        errors.append("account must be a string when present")

    coerce_number(payload, "portfolio_value_usd", "root", errors, required=False, positive=True)
    coerce_number(payload, "cash_usd", "root", errors, required=False, allow_null=True)

    if "positions" not in payload:
        errors.append("positions list is required")

    for section in OPEN_POSITIONS_SECTIONS:
        rows = payload.get(section, [])
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            errors.append(f"{section} must be a list")
            continue
        seen: set[str] = set()
        payload[section] = [
            validate_position_row(item, section, index, seen, errors)
            for index, item in enumerate(rows)
        ]

    return (None if errors else payload), errors


def open_positions_field_audit(payload: dict[str, Any]) -> dict[str, Any]:
    missing: dict[str, list[str]] = {"positions": [], "observations": []}
    counts: dict[str, int] = {}
    required_fields = ("entry_date", "target_price", "stop_price")
    for section in OPEN_POSITIONS_SECTIONS:
        rows = payload.get(section) or []
        counts[section] = len(rows) if isinstance(rows, list) else 0
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "?")
            missing_fields = [field for field in required_fields if row.get(field) in {None, ""}]
            if missing_fields:
                missing[section].append(f"{ticker}: {', '.join(missing_fields)}")
    return {
        "counts": counts,
        "required_fields": list(required_fields),
        "missing": missing,
        "passed": not any(missing.values()),
    }


def open_positions_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {
        "as_of": payload.get("as_of"),
        "portfolio_value_usd": payload.get("portfolio_value_usd"),
        "cash_usd": payload.get("cash_usd"),
        "positions": [row.get("ticker") for row in payload.get("positions", []) if isinstance(row, dict)],
        "observations": [row.get("ticker") for row in payload.get("observations", []) if isinstance(row, dict)],
    }


def record_open_positions_audit(
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    detail: dict[str, Any] | None = None,
) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": utc_now(),
        "client": client_addr(),
        "action": action,
        "path": str(OPEN_POSITIONS_FILE),
        "detail": detail or {},
        "before": open_positions_summary(before),
        "after": open_positions_summary(after),
    }
    with open_positions_audit_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


def find_position_index(payload: dict[str, Any], section: str, ticker: str) -> int | None:
    rows = payload.get(section) or []
    for index, row in enumerate(rows):
        if isinstance(row, dict) and normalize_ticker(row.get("ticker")) == ticker:
            return index
    return None


def save_open_positions_payload(
    payload: dict[str, Any],
    *,
    action: str,
    detail: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[str], str | None]:
    normalized, errors = validate_open_positions_payload(payload)
    if errors or normalized is None:
        return None, errors, None

    with open_positions_lock:
        before = load_open_positions_payload() if OPEN_POSITIONS_FILE.exists() else None
        backup_path = backup_open_positions()
        write_json_atomic(OPEN_POSITIONS_FILE, normalized)
        record_open_positions_audit(action, before, normalized, detail)
    return normalized, [], backup_path


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


@app.route("/open-positions", methods=["GET", "PUT"])
def open_positions() -> Any:
    ok, response = require_token()
    if not ok:
        console_log(f"[server] unauthorized open-positions request from {client_addr()}")
        return response

    if request.method == "GET":
        try:
            payload = load_open_positions_payload()
        except Exception as exc:
            return json_error(f"failed to read open_positions.json: {exc}", 500)
        return jsonify(
            {
                "path": str(OPEN_POSITIONS_FILE),
                "updated_at": utc_now(),
                "payload": payload,
                "field_audit": open_positions_field_audit(payload),
            }
        )

    incoming = request.get_json(silent=True)
    normalized, errors, backup_path = save_open_positions_payload(
        incoming,
        action="replace_payload",
        detail={"source": "open_positions_editor"},
    )
    if errors or normalized is None:
        return json_error("open_positions validation failed", 400, errors=errors)
    console_log(f"[server] open_positions saved from {client_addr()}")
    return jsonify(
        {
            "status": "saved",
            "path": str(OPEN_POSITIONS_FILE),
            "backup_path": backup_path,
            "payload": normalized,
            "field_audit": open_positions_field_audit(normalized),
        }
    )


@app.route("/open-positions/<section>", methods=["POST"])
def create_open_position(section: str) -> Any:
    ok, response = require_token()
    if not ok:
        return response
    if section not in OPEN_POSITIONS_SECTIONS:
        return json_error(f"section must be one of {', '.join(OPEN_POSITIONS_SECTIONS)}", 404)

    row = request.get_json(silent=True)
    if not isinstance(row, dict):
        return json_error("request body must be a position object")
    ticker = normalize_ticker(row.get("ticker"))
    if ticker is None:
        return json_error("position.ticker must be a ticker-like string")

    try:
        payload = load_open_positions_payload()
    except Exception as exc:
        return json_error(f"failed to read open_positions.json: {exc}", 500)
    if find_position_index(payload, section, ticker) is not None:
        return json_error(f"{ticker} already exists in {section}", 409)

    payload.setdefault(section, [])
    payload[section].append(row)
    normalized, errors, backup_path = save_open_positions_payload(
        payload,
        action="create_position",
        detail={"section": section, "ticker": ticker},
    )
    if errors or normalized is None:
        return json_error("open_positions validation failed", 400, errors=errors)
    index = find_position_index(normalized, section, ticker)
    return jsonify(
        {
            "status": "created",
            "backup_path": backup_path,
            "position": normalized[section][index] if index is not None else None,
            "field_audit": open_positions_field_audit(normalized),
        }
    )


@app.route("/open-positions/<section>/<ticker>", methods=["PATCH", "DELETE"])
def edit_open_position(section: str, ticker: str) -> Any:
    ok, response = require_token()
    if not ok:
        return response
    if section not in OPEN_POSITIONS_SECTIONS:
        return json_error(f"section must be one of {', '.join(OPEN_POSITIONS_SECTIONS)}", 404)
    normalized_ticker = normalize_ticker(ticker)
    if normalized_ticker is None:
        return json_error("ticker must be ticker-like", 404)

    try:
        payload = load_open_positions_payload()
    except Exception as exc:
        return json_error(f"failed to read open_positions.json: {exc}", 500)

    index = find_position_index(payload, section, normalized_ticker)
    if index is None:
        return json_error(f"{normalized_ticker} not found in {section}", 404)

    if request.method == "DELETE":
        removed = payload[section].pop(index)
        normalized, errors, backup_path = save_open_positions_payload(
            payload,
            action="delete_position",
            detail={"section": section, "ticker": normalized_ticker, "removed": removed},
        )
        if errors or normalized is None:
            return json_error("open_positions validation failed", 400, errors=errors)
        return jsonify(
            {
                "status": "deleted",
                "backup_path": backup_path,
                "field_audit": open_positions_field_audit(normalized),
            }
        )

    updates = request.get_json(silent=True)
    if not isinstance(updates, dict):
        return json_error("request body must be an object")
    if "ticker" in updates and normalize_ticker(updates.get("ticker")) != normalized_ticker:
        return json_error("ticker cannot be changed through the patch endpoint")

    payload[section][index] = {**payload[section][index], **updates, "ticker": normalized_ticker}
    normalized, errors, backup_path = save_open_positions_payload(
        payload,
        action="patch_position",
        detail={"section": section, "ticker": normalized_ticker, "updated_fields": sorted(updates.keys())},
    )
    if errors or normalized is None:
        return json_error("open_positions validation failed", 400, errors=errors)
    new_index = find_position_index(normalized, section, normalized_ticker)
    return jsonify(
        {
            "status": "saved",
            "backup_path": backup_path,
            "position": normalized[section][new_index] if new_index is not None else None,
            "field_audit": open_positions_field_audit(normalized),
        }
    )


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
    h2 { font-size: 16px; margin: 0; }
    .panel { border: 1px solid #2b313d; border-radius: 6px; padding: 12px; background: #151922; margin: 16px 0; }
    .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
    .positions-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    #positionsJson { width: 100%; min-height: 220px; max-height: 44vh; box-sizing: border-box; resize: vertical; border: 1px solid #2b313d; border-radius: 6px; padding: 10px; background: #0b0d10; color: #e8edf2; font: inherit; line-height: 1.45; }
    #positionsStatus { margin-top: 8px; min-height: 18px; overflow-wrap: anywhere; }
    .ok { color: #7bd88f; }
    .warn { color: #ffd166; }
    .bad { color: #ff7b86; }
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
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Open Positions</h2>
          <div class="label" id="positionsPath">operator_inputs/open_positions.json</div>
        </div>
        <div class="positions-actions">
          <button id="loadPositions">Load</button>
          <button id="formatPositions">Format</button>
          <button class="primary" id="savePositions">Save</button>
        </div>
      </div>
      <textarea id="positionsJson" spellcheck="false" placeholder="Load open_positions.json to edit it here"></textarea>
      <div id="positionsStatus" class="muted">not loaded</div>
    </section>
    <pre id="log"></pre>
  </main>
  <script>
    const tokenInput = document.getElementById("token");
    const logEl = document.getElementById("log");
    const statusEl = document.getElementById("status");
    const promptEl = document.getElementById("prompt");
    const logfileEl = document.getElementById("logfile");
    const positionsPathEl = document.getElementById("positionsPath");
    const positionsJsonEl = document.getElementById("positionsJson");
    const positionsStatusEl = document.getElementById("positionsStatus");
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

    async function api(path, method = "GET", body = null) {
      const options = { method };
      if (body !== null) {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(body);
      }
      const response = await fetch(buildUrl(path), options);
      const data = await response.json();
      if (!response.ok) {
        const err = new Error(data.error || response.statusText);
        err.errors = data.errors || [];
        throw err;
      }
      return data;
    }

    function renderPositionsStatus(data, prefix = "loaded") {
      const audit = data.field_audit || {};
      const counts = audit.counts || {};
      const missing = audit.missing || {};
      const missingRows = [
        ...(missing.positions || []).map(text => `positions ${text}`),
        ...(missing.observations || []).map(text => `observations ${text}`)
      ];
      positionsPathEl.textContent = data.path || positionsPathEl.textContent;
      positionsStatusEl.className = audit.passed ? "ok" : "warn";
      positionsStatusEl.textContent = missingRows.length
        ? `${prefix}; ${counts.positions || 0} positions, ${counts.observations || 0} observations; missing ${missingRows.join("; ")}`
        : `${prefix}; ${counts.positions || 0} positions, ${counts.observations || 0} observations; required fields present`;
    }

    async function loadOpenPositions() {
      try {
        const data = await api("/open-positions");
        positionsJsonEl.value = JSON.stringify(data.payload, null, 4) + "\\n";
        renderPositionsStatus(data);
      } catch (err) {
        positionsStatusEl.className = "bad";
        positionsStatusEl.textContent = err.message;
      }
    }

    function parsePositionsEditor() {
      try {
        return JSON.parse(positionsJsonEl.value);
      } catch (err) {
        positionsStatusEl.className = "bad";
        positionsStatusEl.textContent = `JSON parse error: ${err.message}`;
        return null;
      }
    }

    async function saveOpenPositions() {
      const payload = parsePositionsEditor();
      if (payload === null) return;
      try {
        const data = await api("/open-positions", "PUT", payload);
        positionsJsonEl.value = JSON.stringify(data.payload, null, 4) + "\\n";
        renderPositionsStatus(data, "saved");
        if (data.backup_path) appendLog(`[server] open_positions backup: ${data.backup_path}`);
      } catch (err) {
        positionsStatusEl.className = "bad";
        positionsStatusEl.textContent = err.message;
        if (err.errors && err.errors.length) appendLog(`[browser] ${err.errors.join("; ")}`);
      }
    }

    function formatOpenPositions() {
      const payload = parsePositionsEditor();
      if (payload === null) return;
      positionsJsonEl.value = JSON.stringify(payload, null, 4) + "\\n";
      positionsStatusEl.className = "muted";
      positionsStatusEl.textContent = "formatted locally; not saved";
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
    document.getElementById("loadPositions").addEventListener("click", loadOpenPositions);
    document.getElementById("savePositions").addEventListener("click", saveOpenPositions);
    document.getElementById("formatPositions").addEventListener("click", formatOpenPositions);
    refreshStatus();
    if (tokenInput.value) {
      connect();
      loadOpenPositions();
    }
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
