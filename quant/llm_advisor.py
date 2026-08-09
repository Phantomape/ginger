"""
LLM-based investment advisor using local Codex.

Analyzes filtered trade news and current positions to provide investment recommendations.
"""

import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from data_paths import DATA_ROOT, daily_artifact_path, resolve_daily_artifact_path
from operator_input_paths import open_positions_path, repo_relative
from open_position_schema import (
    account_position_tickers,
    account_positions,
    core_slot_positions,
    has_account_positions,
    legacy_positions_payload,
)

logger = logging.getLogger(__name__)

# Kept as a module attribute for older tests and callers that monkeypatch the
# former API client path. The production path persists an auditable prompt and
# now prefers local Codex over remote API calls.
OpenAI = None

LOCAL_CODEX_DEFAULT_MODEL = "gpt-5.6-sol"
LOCAL_CODEX_DEFAULT_TIMEOUT_SECONDS = 900
LOCAL_CODEX_DEFAULT_SANDBOX = "read-only"


def _env_flag(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def _first_env_value(*names):
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _local_codex_enabled():
    return _env_flag("GINGER_LOCAL_CODEX_ENABLED", True) and _env_flag(
        "LOCAL_CODEX_ENABLED", True
    )


def _resolve_local_codex_model(requested_model=None):
    return (
        _first_env_value("GINGER_LOCAL_CODEX_MODEL", "LOCAL_CODEX_MODEL")
        or requested_model
        or LOCAL_CODEX_DEFAULT_MODEL
    )


def _local_codex_timeout_seconds():
    raw = _first_env_value("GINGER_LOCAL_CODEX_TIMEOUT_SECONDS", "LOCAL_CODEX_TIMEOUT_SECONDS")
    if raw is None:
        return LOCAL_CODEX_DEFAULT_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid local Codex timeout %r; using default", raw)
        return LOCAL_CODEX_DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        return LOCAL_CODEX_DEFAULT_TIMEOUT_SECONDS
    return value


def _local_codex_ephemeral_enabled():
    return _env_flag("GINGER_LOCAL_CODEX_EPHEMERAL", True) and _env_flag(
        "LOCAL_CODEX_EPHEMERAL", True
    )


def _local_codex_sandbox_mode():
    value = (
        _first_env_value("GINGER_LOCAL_CODEX_SANDBOX", "LOCAL_CODEX_SANDBOX")
        or LOCAL_CODEX_DEFAULT_SANDBOX
    )
    if value not in {"read-only", "workspace-write", "danger-full-access"}:
        logger.warning("Invalid local Codex sandbox %r; using read-only", value)
        return LOCAL_CODEX_DEFAULT_SANDBOX
    return value


def _candidate_codex_executables():
    candidates = []
    explicit = _first_env_value("GINGER_CODEX_EXE", "LOCAL_CODEX_EXE", "CODEX_EXE")
    if explicit:
        candidates.append(explicit)

    home = Path.home()
    candidates.extend(
        [
            str(home / ".codex" / ".sandbox-bin" / "codex.exe"),
            str(home / ".codex" / "plugins" / ".plugin-appserver" / "codex.exe"),
        ]
    )
    discovered = shutil.which("codex")
    if discovered:
        candidates.append(discovered)

    unique = []
    seen = set()
    for candidate in candidates:
        normalized = str(candidate)
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _probe_codex_executable(executable):
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as exc:
        logger.debug("Local Codex probe failed for %s: %s", executable, exc)
        return False
    if completed.returncode == 0:
        return True
    logger.debug(
        "Local Codex probe returned %s for %s: %s",
        completed.returncode,
        executable,
        (completed.stderr or completed.stdout or "").strip()[-500:],
    )
    return False


def _discover_codex_executable():
    for executable in _candidate_codex_executables():
        if _probe_codex_executable(executable):
            return executable
    return None


def _tail_text(text, limit=2000):
    text = text or ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    else:
        text = str(text)
    if len(text) <= limit:
        return text
    return text[-limit:]


def _path_status(path):
    path = Path(path)
    status = {"path": str(path), "exists": path.exists()}
    if status["exists"]:
        try:
            stat = path.stat()
            status["size_bytes"] = stat.st_size
            status["modified_at"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except OSError as exc:
            status["stat_error"] = str(exc)
    return status


def _local_codex_failure_artifact_path(date_str, data_dir):
    advice_path = daily_artifact_path("investment_advice", date_str, data_dir)
    return advice_path.parent / f"local_codex_failure_{date_str}.json"


def _record_local_codex_failure(date_str, data_dir, result, **context):
    payload = {
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "provider": "local_codex",
        **context,
        **result,
    }
    response_path = payload.get("response_path")
    if response_path:
        payload["response_path_status"] = _path_status(response_path)

    artifact_path = _local_codex_failure_artifact_path(date_str, data_dir)
    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        result["diagnostic_path"] = str(artifact_path)
    except Exception as exc:
        logger.warning("Failed to write local Codex diagnostic artifact: %s", exc)
        result["diagnostic_error"] = str(exc)
    return result


def _build_local_codex_prompt(prompt_file, system_message, user_message):
    return (
        "You are the local Codex JSON responder for Ginger's daily trading workflow.\n"
        "Do not inspect files, run commands, or modify the repository. The prompt below is self-contained.\n"
        "Return only one valid JSON object matching the requested schema. Do not include markdown fences.\n"
        "Code-owned risk, sizing, exits, and order boundaries are authoritative; only apply the prompt's LLM semantic checks.\n\n"
        f"Audit prompt file: {prompt_file}\n\n"
        "=== SYSTEM MESSAGE ===\n"
        f"{system_message}\n\n"
        "=== USER MESSAGE ===\n"
        f"{user_message}\n"
    )


def _call_local_codex(prompt_file, system_message, user_message, date_str, data_dir, model=None):
    model_id = _resolve_local_codex_model(model)
    executable = _discover_codex_executable()
    if not executable:
        return _record_local_codex_failure(
            date_str,
            data_dir,
            {
                "success": False,
                "error": "local_codex_executable_unavailable",
                "model": model_id,
                "provider": "local_codex",
            },
            candidate_count=len(_candidate_codex_executables()),
        )

    advice_path = daily_artifact_path("investment_advice", date_str, data_dir)
    output_path = advice_path.parent / f"local_codex_response_{date_str}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    codex_prompt = _build_local_codex_prompt(prompt_file, system_message, user_message)
    sandbox_mode = _local_codex_sandbox_mode()
    ephemeral_enabled = _local_codex_ephemeral_enabled()
    cmd = [
        executable,
        "exec",
        "--sandbox",
        sandbox_mode,
        "--model",
        model_id,
        "--cd",
        str(Path.cwd()),
        "--output-last-message",
        str(output_path),
        "-",
    ]
    if ephemeral_enabled:
        cmd.insert(2, "--ephemeral")

    started = time.time()
    try:
        completed = subprocess.run(
            cmd,
            input=codex_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_local_codex_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as exc:
        timeout_seconds = _local_codex_timeout_seconds()
        return _record_local_codex_failure(
            date_str,
            data_dir,
            {
                "success": False,
                "error": f"local_codex_timeout_after_{timeout_seconds}s",
                "stderr": _tail_text(getattr(exc, "stderr", "") or ""),
                "stdout": _tail_text(getattr(exc, "stdout", "") or ""),
                "model": model_id,
                "provider": "local_codex",
                "response_path": str(output_path),
                "codex_executable": executable,
                "codex_ephemeral": ephemeral_enabled,
                "codex_sandbox": sandbox_mode,
                "timeout_seconds": timeout_seconds,
                "duration_seconds": round(time.time() - started, 3),
            },
            command=cmd,
            prompt_file=str(prompt_file),
        )
    except Exception as exc:
        return _record_local_codex_failure(
            date_str,
            data_dir,
            {
                "success": False,
                "error": f"local_codex_launch_failed: {exc}",
                "model": model_id,
                "provider": "local_codex",
                "response_path": str(output_path),
                "codex_executable": executable,
                "codex_ephemeral": ephemeral_enabled,
                "codex_sandbox": sandbox_mode,
                "duration_seconds": round(time.time() - started, 3),
            },
            command=cmd,
            prompt_file=str(prompt_file),
        )

    duration_seconds = round(time.time() - started, 3)
    if completed.returncode != 0:
        return _record_local_codex_failure(
            date_str,
            data_dir,
            {
                "success": False,
                "error": f"local_codex_returncode_{completed.returncode}",
                "returncode": completed.returncode,
                "stderr": _tail_text(completed.stderr),
                "stdout": _tail_text(completed.stdout),
                "model": model_id,
                "provider": "local_codex",
                "response_path": str(output_path),
                "codex_executable": executable,
                "codex_ephemeral": ephemeral_enabled,
                "codex_sandbox": sandbox_mode,
                "duration_seconds": duration_seconds,
            },
            command=cmd,
            prompt_file=str(prompt_file),
        )

    raw_response = ""
    if output_path.exists():
        raw_response = output_path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw_response:
        raw_response = (completed.stdout or "").strip()

    parsed = parse_json_advice(raw_response)
    if not isinstance(parsed, dict) or "new_trade" not in parsed:
        return _record_local_codex_failure(
            date_str,
            data_dir,
            {
                "success": False,
                "error": "local_codex_response_missing_new_trade_json",
                "response_path": str(output_path),
                "stdout": _tail_text(completed.stdout),
                "stderr": _tail_text(completed.stderr),
                "model": model_id,
                "provider": "local_codex",
                "codex_executable": executable,
                "codex_ephemeral": ephemeral_enabled,
                "codex_sandbox": sandbox_mode,
                "duration_seconds": duration_seconds,
            },
            command=cmd,
            prompt_file=str(prompt_file),
        )

    token_usage = {
        "provider": "local_codex",
        "model": model_id,
        "codex_executable": executable,
        "codex_ephemeral": ephemeral_enabled,
        "codex_sandbox": sandbox_mode,
        "codex_response_path": str(output_path),
        "duration_seconds": duration_seconds,
    }
    advice_path.parent.mkdir(parents=True, exist_ok=True)
    if not save_advice(raw_response, str(advice_path), token_usage=token_usage):
        return _record_local_codex_failure(
            date_str,
            data_dir,
            {
                "success": False,
                "error": "local_codex_save_advice_failed",
                "response_path": str(output_path),
                "model": model_id,
                "provider": "local_codex",
                "codex_executable": executable,
                "codex_ephemeral": ephemeral_enabled,
                "codex_sandbox": sandbox_mode,
                "duration_seconds": duration_seconds,
            },
            command=cmd,
            prompt_file=str(prompt_file),
        )

    return {
        "success": True,
        "advice_path": str(advice_path),
        "replay_path": str(_replay_log_path_for_output(str(advice_path), date_str)),
        "response_path": str(output_path),
        "model": model_id,
        "provider": "local_codex",
        "token_usage": token_usage,
    }


def _load_json_if_exists(path):
    """Best-effort JSON loader for optional replay sidecar files."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load optional JSON sidecar {path}: {e}")
        return None


def _archive_root_for_output(filepath: str) -> str:
    """Use data root for organized daily files, else keep caller's directory."""
    path = Path(filepath).resolve()
    data_root = DATA_ROOT.resolve()
    try:
        path.relative_to(data_root / "daily")
        return str(data_root)
    except ValueError:
        return str(path.parent)


def _replay_log_path_for_output(filepath: str, date_str: str) -> str:
    path = Path(filepath).resolve()
    data_root = DATA_ROOT.resolve()
    try:
        path.relative_to(data_root / "daily")
        return str(daily_artifact_path("llm_prompt_resp", date_str))
    except ValueError:
        return str(path.parent / f"llm_prompt_resp_{date_str}.json")


def _build_archive_context(date_str, data_dir):
    """Attach prompt-time production context to dated advice / replay archives.

    The top alpha branch (`LLM soft ranking`) is blocked not just by missing
    replies, but by lacking prompt-time candidate context. This helper mirrors
    enough program-side state into the saved advice wrapper so replay readiness
    can later distinguish:
      - ranking-eligible candidate days
      - prompt days that were hard-locked by heat / regime rules
      - days with no prompt candidates at all
    """
    decision_log = _load_json_if_exists(
        resolve_daily_artifact_path("llm_decision_log", date_str, data_dir)
    )
    quant_signals = _load_json_if_exists(
        resolve_daily_artifact_path("quant_signals", date_str, data_dir)
    )

    signal_details = []
    if isinstance(decision_log, dict):
        signal_details = decision_log.get("signal_details") or []

    signal_tickers = []
    for item in signal_details:
        if not isinstance(item, dict):
            continue
        ticker = item.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            signal_tickers.append(ticker.strip().upper())

    source = None
    new_trade_locked = None
    account_state = None
    lock_reason = None
    if isinstance(decision_log, dict):
        source = "llm_decision_log"
        new_trade_locked = decision_log.get("new_trade_locked")
        account_state = decision_log.get("account_state")
        lock_reason = decision_log.get("lock_reason")
        if not signal_tickers:
            for ticker in decision_log.get("signals_presented", []) or []:
                if isinstance(ticker, str) and ticker.strip():
                    signal_tickers.append(ticker.strip().upper())
    elif isinstance(quant_signals, dict):
        source = "quant_signals"
        for item in quant_signals.get("signals", []) or []:
            if not isinstance(item, dict):
                continue
            ticker = item.get("ticker")
            if isinstance(ticker, str) and ticker.strip():
                signal_tickers.append(ticker.strip().upper())
        review = quant_signals.get("entry_candidate_review") or {}
        if isinstance(review, dict):
            for item in review.get("candidates", []) or []:
                if not isinstance(item, dict):
                    continue
                ticker = item.get("ticker")
                if isinstance(ticker, str) and ticker.strip():
                    signal_tickers.append(ticker.strip().upper())
            if source is None and review.get("candidate_count"):
                source = "quant_signals.entry_candidate_review"

    if source is None:
        return None

    signal_tickers = list(dict.fromkeys(signal_tickers))
    if new_trade_locked is True:
        ranking_eligible = False
    elif signal_tickers:
        ranking_eligible = True
    else:
        ranking_eligible = False

    context = {
        "source": source,
        "signals_presented": signal_tickers,
        "signals_presented_count": len(signal_tickers),
        "ranking_eligible": ranking_eligible,
    }
    if new_trade_locked is not None:
        context["new_trade_locked"] = bool(new_trade_locked)
    if account_state is not None:
        context["account_state"] = account_state
    if lock_reason:
        context["lock_reason"] = lock_reason
    if isinstance(quant_signals, dict):
        review = quant_signals.get("entry_candidate_review") or {}
        if isinstance(review, dict):
            context["entry_candidate_review_count"] = int(
                review.get("candidate_count") or 0
            )
            context["entry_candidate_operator_review_count"] = int(
                review.get("operator_review_count") or 0
            )
            context["entry_candidate_backtest_buy_count"] = int(
                review.get("backtest_accounting_buy_count") or 0
            )
    return context


def load_open_positions(filepath=None):
    """
    Load open positions from JSON file.

    Args:
        filepath (str): Path to open_positions.json

    Returns:
        dict: Open positions data or None if file not found
    """
    try:
        path = open_positions_path(filepath)
        if not path.exists():
            logger.warning(f"Open positions file not found: {repo_relative(path)}")
            return None

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load open positions: {e}")
        return None


def load_prompt_template(template_path="../instructions/prompts/trade_advice.txt"):
    """
    Load the prompt template file.

    Args:
        template_path (str): Path to trade_advice.txt

    Returns:
        str: Template content or None if file not found
    """
    try:
        # Try relative path first
        if not os.path.exists(template_path):
            # Try from project root
            template_path = "instructions/prompts/trade_advice.txt"

        if not os.path.exists(template_path):
            logger.warning(f"Prompt template file not found: {template_path}")
            return None

        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt template: {e}")
        return None


def build_prompt(trade_news, open_positions, trend_signals=None):
    """
    Build prompt from template by inserting positions, news, and trend signals.

    Args:
        trade_news (list): List of filtered trade news items
        open_positions (dict): Current portfolio positions
        trend_signals (dict): Optional trend signal data from trend_signals module

    Returns:
        tuple: (system_message, user_message) or (None, None) if failed
    """
    # Load template
    template = load_prompt_template()
    if not template:
        logger.error("Failed to load prompt template, using fallback")
        return None, None

    # Parse template to extract SYSTEM and USER sections
    lines = template.split('\n')
    system_lines = []
    user_lines = []
    current_section = None

    for line in lines:
        if line.strip() == "SYSTEM:":
            current_section = "system"
            continue
        elif line.strip() == "USER:":
            current_section = "user"
            continue

        if current_section == "system":
            system_lines.append(line)
        elif current_section == "user":
            user_lines.append(line)

    system_message = '\n'.join(system_lines).strip()
    account_position_rows = account_positions(open_positions) if open_positions else []
    account_tickers = account_position_tickers(open_positions, positive_only=True)

    # Build user message with dynamic data. The template text is mojibake in
    # this repository, so use stable section boundaries instead of brittle
    # regexes over corrupted labels.
    today = datetime.now().strftime("%b. %d, %Y, %I:%M %p EST")
    user_message = '\n'.join(user_lines)
    user_message = user_message.replace("Jan. 15th, 2026, 4:30 PM EST", today, 1)

    # Replace positions JSON (remove 'as_of' field since the prompt has its own date line).
    if open_positions:
        positions_copy = legacy_positions_payload(open_positions)
        positions_copy.pop('as_of', None)
        positions_copy.pop("core_positions", None)
        positions_copy.pop("observations", None)
        positions_json = json.dumps(positions_copy, indent=4)
    else:
        positions_json = "{}"

    pos_start = user_message.find("1)")
    news_start = user_message.find("\n2)", pos_start)
    if pos_start != -1 and news_start != -1:
        pos_header_end = user_message.find("\n", pos_start)
        pos_header = user_message[pos_start:pos_header_end]
        if "{" in pos_header:
            pos_header = pos_header.split("{", 1)[0].rstrip()
        positions_section = f"{pos_header}\n{positions_json}\n"
        user_message = user_message[:pos_start] + positions_section + user_message[news_start:]

    # Replace news JSON using section boundaries instead of mojibake regex text.
    news_json = json.dumps(trade_news, indent=2)
    # Compute news quality summary so LLM does not need to scan all items to know if
    # actionable news exists. T3-only days are extremely common; the summary prevents
    # T3 content from subtly influencing decisions even when rules say "ignore T3".
    _tier_counts = {"T1": 0, "T2": 0, "T3": 0}
    for _item in trade_news:
        _tier_counts[_item.get("tier", "T3")] += 1
    _has_actionable = _tier_counts["T1"] > 0 or _tier_counts["T2"] > 0
    news_quality_summary = json.dumps({
        "T1": _tier_counts["T1"],
        "T2": _tier_counts["T2"],
        "T3": _tier_counts["T3"],
        "has_actionable_news": _has_actionable,
        "note": "T3-only news is context noise; ignore it unless paired with T1/T2 actionable news." if not _has_actionable else "",
    })
    news_start = user_message.find("2)")
    separator_start = user_message.find("\n--------------------------------------------------------------------------------", news_start)
    if news_start != -1 and separator_start != -1:
        news_header_end = user_message.find("\n", news_start)
        news_header = user_message[news_start:news_header_end]
        news_section = (
            f"{news_header}\n{news_json}\n\n"
            f"news_quality_summary: {news_quality_summary}\n"
        )
        user_message = user_message[:news_start] + news_section + user_message[separator_start:]

    # Build sections 3a (quant signals) + 3b (technical context for held positions).
    # Only include tickers relevant to the decision - not the full 30-ticker universe.
    sections_3 = ""

    # --- 3a: Pre-computed quant signals (new trade candidates) ---
    quant_signals = trend_signals.get("quant_signals", []) if trend_signals else []
    addon_actions = trend_signals.get("addon_actions", []) if trend_signals else []
    entry_candidate_review = (
        trend_signals.get("entry_candidate_review") if trend_signals else None
    )
    if quant_signals:
        sections_3 += (
            f"\n\n3a) 量化信号 QUANT SIGNALS（预计算完成，直接使用）：\n"
            f"每条信号已含 strategy / entry_price / stop_price / target_price / "
            f"risk_reward_ratio / trade_quality_score / confidence_score。\n"
            f"{json.dumps(quant_signals, indent=2)}\n"
        )
    else:
        sections_3 += "\n\n3a) 量化信号 QUANT SIGNALS：今日无满足条件的量化信号。\n"

    if addon_actions:
        sections_3 += (
            f"\n\n3a-add) ADD-ON ACTIONS (code-decided, not new-entry candidates):\n"
            f"These actions come from the shared day-N follow-through rule; if no T1 disaster news exists, pass them through to add_on_trades.\n"
            f"{json.dumps(addon_actions, indent=2)}\n"
        )

    if (
        isinstance(entry_candidate_review, dict)
        and entry_candidate_review.get("candidate_count")
    ):
        review_payload = {
            "diagnostic_only": True,
            "orders_changed": False,
            "slot_accounting": entry_candidate_review.get("slot_accounting"),
            "operator_review_count": entry_candidate_review.get("operator_review_count"),
            "candidates": (entry_candidate_review.get("candidates") or [])[:10],
        }
        sections_3 += (
            "\n\n3a-review) ENTRY CANDIDATE REVIEW "
            "(operator-only; do not treat deferred rows as automatic orders):\n"
            "Use this to flag news/LLM risk for candidates that live slot "
            "accounting deferred but backtest-accounting would buy.\n"
            f"{json.dumps(review_payload, indent=2)}\n"
        )

    # --- 3b: Technical context - only tickers with open positions that have triggered exits ---
    raw_signals = trend_signals.get('signals', {}) if trend_signals else {}
    attention_tickers = set()
    for t, s in raw_signals.items():
        pos_ctx = s.get('position', {})
        if pos_ctx.get('exit_signals', {}).get('any_triggered'):
            attention_tickers.add(t)
    # Also include tickers that have quant signals
    signal_tickers = {s["ticker"] for s in quant_signals}
    addon_tickers = {
        a["ticker"] for a in addon_actions
        if isinstance(a, dict) and a.get("ticker")
    }
    review_tickers = set()
    if isinstance(entry_candidate_review, dict):
        review_tickers = {
            row["ticker"]
            for row in entry_candidate_review.get("candidates") or []
            if isinstance(row, dict) and row.get("ticker")
        }
    relevant_tickers = attention_tickers | signal_tickers | addon_tickers | review_tickers

    if relevant_tickers:
        filtered = {t: raw_signals[t] for t in relevant_tickers if t in raw_signals}
        if filtered:
            sections_3 += (
                f"\n\n3b) 技术背景 TECHNICAL CONTEXT（仅含有信号或需关注的标的）：\n"
                f"{json.dumps(filtered, indent=2)}\n"
            )

    if sections_3:
        task_a_pos = user_message.find("任务 A")
        if task_a_pos != -1:
            user_message = user_message[:task_a_pos] + sections_3 + "\n" + user_message[task_a_pos:]
        else:
            user_message += sections_3

    # Add position management section (insert before TASK A, after trend signals)
    # Use portfolio_engine: it applies effective stops (ATR/trailing) not just hard stops,
    # giving a more accurate heat reading for positions with large unrealised gains.
    from portfolio_engine import compute_portfolio_heat
    from portfolio_accounting import resolve_portfolio_accounting

    stored_pv = open_positions.get('portfolio_value_usd') if open_positions else None

    # Extract current prices + effective-stop inputs from trend signals first.
    # these are needed for the live portfolio value calculation below.
    current_prices   = {}
    features_for_heat = {}
    if trend_signals and trend_signals.get('signals'):
        for t, s in trend_signals['signals'].items():
            if s.get('close') is not None:
                current_prices[t] = s['close']
            # portfolio_engine needs atr + high_20d to compute effective stop
            features_for_heat[t] = {
                "atr":     s.get("atr"),
                "high_20d": s.get("20d_high"),
            }

    # Resolve account value once so heat, sector weights, and prompt context use
    # the same cash policy as the production runner.
    portfolio_value = stored_pv
    account_summary = None
    accounting_warnings = []
    if has_account_positions(open_positions, positive_only=True) and current_prices:
        account_summary = resolve_portfolio_accounting(
            open_positions,
            current_prices,
            stored_portfolio_value=stored_pv,
            logger=logger,
        )
        accounting_warnings = account_summary.get("warnings") or []
        if account_summary.get("portfolio_value_usd"):
            portfolio_value = account_summary["portfolio_value_usd"]


    # Portfolio heat (using effective stops: ATR/trailing, not just avg_cost stop)
    heat = None
    if portfolio_value and open_positions:
        try:
            heat = compute_portfolio_heat(
                open_positions, current_prices, portfolio_value,
                features_dict=features_for_heat,
            )
        except Exception as e:
            logger.warning(f"Failed to compute portfolio heat: {e}")

    # Market regime from trend signals
    regime = trend_signals.get('market_regime', {}) if trend_signals else {}

    # Sector concentration: compute per-sector market value and weight.
    # The LLM prompt requires ">40% sector weight -> block new positions in that sector"
    # but previously had NO sector data; rule was enforced blindly from LLM training.
    # Now we inject pre-computed weights so the rule can actually be enforced.
    sector_weights = {}
    if open_positions and portfolio_value and portfolio_value > 0:
        try:
            from risk_engine import SECTOR_MAP
            sector_mv: dict = {}
            total_mv = 0.0
            for pos in account_position_rows:
                t_  = pos.get("ticker", "")
                sh_ = pos.get("shares", 0)
                px_ = current_prices.get(t_) or pos.get("avg_cost", 0)
                mv_ = sh_ * px_
                sec = SECTOR_MAP.get(t_, "Unknown")
                sector_mv[sec] = sector_mv.get(sec, 0.0) + mv_
                total_mv += mv_
            if total_mv > 0:
                # Use portfolio_value (total account incl. cash) as denominator,
                # NOT total_mv (invested portion only).  When significant cash is
                # held, total_mv << portfolio_value and sector weights are overstated
                # by the ratio total_mv/portfolio_value, falsely triggering the
                # >40% sector block and preventing valid new trades.
                # portfolio_value > 0 is guaranteed by the outer if-guard on line 242.
                sector_denom = portfolio_value
                sector_weights = {
                    sec: round(mv / sector_denom, 3)
                    for sec, mv in sorted(sector_mv.items(), key=lambda x: -x[1])
                }
        except Exception as e:
            logger.warning(f"Sector concentration calc failed: {e}")

    # Data quality check: detect positions missing fields required for exit rules.
    # entry_date required by TIME_STOP (45-day stagnation rule)
    # target_price required by SIGNAL_TARGET (3.5x ATR partial-exit rule)
    # Without these, two exit rules silently never fire.
    _data_warnings = []
    if open_positions:
        _missing_entry_date  = [p["ticker"] for p in account_position_rows
                                 if p.get("ticker") and not p.get("entry_date")]
        _missing_target_price = [p["ticker"] for p in account_position_rows
                                  if p.get("ticker") and not p.get("target_price")]
        if _missing_entry_date:
            _data_warnings.append(
                f"TIME_STOP disabled for {_missing_entry_date}: add 'entry_date': 'YYYY-MM-DD' "
                "to each position in open_positions.json (45-day stagnation rule cannot fire)"
            )
        if _missing_target_price:
            _data_warnings.append(
                f"SIGNAL_TARGET disabled for {_missing_target_price}: add 'target_price' "
                "from the original entry signal to each position in open_positions.json "
                "(3.5x ATR partial-exit rule cannot fire, +7% to +20% zone has no exit guidance)"
            )

    # Preflight: compute machine states before data reaches LLM.
    # This converts raw flags (BEAR? heat%? CRITICAL exists?) into a single
    # account_state verdict + per-position decision_state.  The LLM reads the
    # verdict, not the raw flags, reducing the chance of conflicting rule
    # interpretations and "优先HOLD"/"必须EXIT" contradictions.
    from preflight_validator import enrich_positions_with_breach_status, compute_account_state
    from pending_actions import get_open_pending_actions
    from position_intent import audit_position_intent_coverage
    if trend_signals:
        enrich_positions_with_breach_status(trend_signals)
    core_fire_tickers = {
        str(row.get("ticker") or "").upper().strip()
        for row in core_slot_positions(open_positions, positive_only=True)
        if row.get("ticker")
    } if open_positions else set()
    preflight = compute_account_state(
        trend_signals = trend_signals,
        heat_data     = heat,
        regime_data   = regime,
        core_fire_tickers = core_fire_tickers,
    )
    if isinstance(trend_signals, dict):
        # Persist the machine-state summary alongside the day payload so later
        # decision logs / replay archives can recover prompt-time gating state.
        trend_signals["preflight"] = preflight
    # Merge preflight data_warnings with account and field-missing warnings
    combined_warnings = (
        (preflight.get("data_warnings") or [])
        + (accounting_warnings or [])
        + (_data_warnings or [])
    )
    entry_intent_audit = audit_position_intent_coverage(open_positions)
    missing_intent = entry_intent_audit.get("missing_intended_share_tickers") or []
    if missing_intent:
        fields = ", ".join(entry_intent_audit["accepted_intended_share_fields"])
        combined_warnings.append(
            f"ENTRY_TOP_UP blind for {missing_intent}: add one intended-share field "
            f"({fields}) to open_positions.json so conservative initial buys can be "
            "audited against the original signal size."
        )
    underfilled = entry_intent_audit.get("underfilled_positions") or []
    if underfilled:
        combined_warnings.append(
            "ENTRY_TOP_UP underfilled positions detected: "
            f"{underfilled}. This is audit context only; hard add-on rules still "
            "control whether an ADD is allowed."
        )
    pending_actions = get_open_pending_actions(open_positions, data_dir="data")

    pos_mgmt_data = {
        # Machine state summary (LLM reads this first).
        "account_state":    preflight["account_state"],
        "new_trade_locked": preflight["new_trade_locked"],
        "lock_reason":      preflight["lock_reason"],
        "position_states":      preflight["position_states"],   # {ticker: CRITICAL_EXIT | ATR_EXIT | TARGET_EXIT | HIGH_REDUCE | HOLD}
        "pending_unexecuted_actions": pending_actions,
        "entry_intent_audit": entry_intent_audit,
        # Pre-computed reduce % for HIGH_REDUCE positions; LLM reads directly.
        "suggested_reduce_pct": preflight["suggested_reduce_pct"],  # {ticker: int}
        # Pre-computed BEAR emergency stops; LLM uses directly if regime=BEAR.
        "bear_emergency_stops": preflight["bear_emergency_stops"],  # {ticker: float} empty if not BEAR
        # Current prices for ALL held tickers, required by BEAR stop-tightening rule
        # ("收紧至 current_price x 0.95") which applies to HOLD positions not in section 3b.
        # Without this, BEAR tightening silently fails for AMD/GOOG/MCD/NFLX etc.
        "current_prices":       {t: p for t, p in current_prices.items()
                                 if t.upper() in account_tickers},
        "accounting": account_summary if account_summary else {
            "portfolio_value_usd": portfolio_value,
            "cash_source": "stored_or_unavailable",
            "cash_is_inferred": False,
        },
        # Market context.
        "market_regime": {
            "regime":  regime.get("regime", "UNKNOWN"),
            "note":    regime.get("note", ""),
            "indices": regime.get("indices", {}),
        },
        "portfolio_heat": heat if heat else {
            "note": "Set portfolio_value_usd in open_positions.json to enable heat tracking"
        },
        "sector_concentration": sector_weights if sector_weights else {
            "note": "Sector weights unavailable (missing portfolio_value_usd or current prices)"
        },
        "sizing_note": (
            "shares = floor(portfolio_value_usd * 0.01 / (entry_price - stop_price))"
            if portfolio_value
            else "Set portfolio_value_usd in open_positions.json to enable position sizing"
        ),
        "data_warnings": combined_warnings,
        "positions_requiring_attention": [],
    }

    # Collect positions with triggered exit signals from trend signals.
    # MEDIUM+ urgency is always surfaced.  LOW urgency rules are skipped unless the
    # rule requires an action (REDUCE 33%) rather than monitoring (HOLD).
    #
    # SIGNAL_TARGET (LOW urgency) requires REDUCE 33%; always surface even when it
    # is the only triggered rule. Without this, winners reaching the +7% to +20% dead
    # zone get no explicit LLM attention in section 4 and the REDUCE is missed.
    #
    # PROFIT_LADDER_30 (LOW urgency, action=HOLD) is still excluded; including it
    # would flood section 4 with every +30% winner and dilute critical signals.
    _urgency_rank = {"CRITICAL": 4, "HIGH": 3, "WARNING": 2, "MEDIUM": 1, "LOW": 0}
    _min_surface_rank = 1   # MEDIUM and above always surfaced
    _action_required_low_rules = {"SIGNAL_TARGET"}   # target full exit visibility
    _review_surface_rules = {"LEGACY_TARGET_REVIEW"}  # visible, but not executable
    if trend_signals and trend_signals.get('signals'):
        for ticker, sig in trend_signals['signals'].items():
            pos_ctx   = sig.get('position', {})
            exit_sigs = pos_ctx.get('exit_signals', {})
            rules     = exit_sigs.get('triggered_rules', [])
            if not (exit_sigs.get('any_triggered') and rules):
                continue
            max_urgency = max(rules, key=lambda r: _urgency_rank.get(r['urgency'], 0))['urgency']
            # Include if MEDIUM+ urgency, if an action-required LOW rule fired,
            # or if a non-executable review rule needs operator visibility.
            has_action_required_low = any(
                r["rule"] in _action_required_low_rules for r in rules
            )
            has_review_surface_rule = any(
                r["rule"] in _review_surface_rules for r in rules
            )
            if (
                _urgency_rank.get(max_urgency, 0) < _min_surface_rank
                and not has_action_required_low
                and not has_review_surface_rule
            ):
                continue
            entry = {
                "ticker":                      ticker,
                "current_price":               sig['close'],
                "daily_high":                  pos_ctx.get('daily_high') or sig.get('daily_high'),
                "urgency":                     max_urgency,
                "triggered_rules":             rules,
                # Pre-computed position data; LLM prompt says "直接使用" these fields
                "shares":                      pos_ctx.get('shares'),
                "avg_cost":                    pos_ctx.get('avg_cost'),
                "unrealized_pnl_pct":          pos_ctx.get('unrealized_pnl_pct'),
                "legacy_basis":                pos_ctx.get('legacy_basis'),
                "exit_levels":                 pos_ctx.get('exit_levels'),
                "trailing_stop_from_20d_high": pos_ctx.get('trailing_stop_from_20d_high'),
                "drawdown_from_20d_high_pct":  pos_ctx.get('drawdown_from_20d_high_pct'),
                # Daily price change, required for post-earnings gap rules:
                # "daily_return_pct > +8% -> REDUCE 50%" and "< -5% -> EXIT"
                # Without this field the LLM cannot distinguish a single-day gap
                # event from cumulative unrealised P&L since entry.
                "daily_return_pct":            pos_ctx.get('daily_return_pct'),
                "prev_close":                  pos_ctx.get('prev_close'),
            }
            # Include days_to_earnings so LLM can apply the "dte <= 2 -> reduce 50%"
            # earnings pre-exit rule. Sourced from qp_features injected by run_pipeline.py
            # (trend_signals.generate_trend_signals() doesn't fetch earnings data).
            _dte = pos_ctx.get('days_to_earnings') or sig.get('days_to_earnings')
            if _dte is not None:
                entry["days_to_earnings"] = _dte
            pos_mgmt_data['positions_requiring_attention'].append(entry)

    pos_mgmt_json = json.dumps(pos_mgmt_data, indent=2)
    pos_mgmt_section = (
        f"\n\n4) POSITION MANAGEMENT (pre-computed - use these directly):\n"
        f"{pos_mgmt_json}\n"
    )

    task_a_pos = user_message.find("任务 A")
    if task_a_pos != -1:
        user_message = user_message[:task_a_pos] + pos_mgmt_section + "\n" + user_message[task_a_pos:]
    else:
        user_message += pos_mgmt_section

    return system_message, user_message


def _cwd_is_inside_repo():
    try:
        Path.cwd().resolve().relative_to(DATA_ROOT.parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _prompt_data_dir_for_current_context():
    return None if _cwd_is_inside_repo() else Path("data")


def _save_decision_log(date_str, trade_news, trend_signals, data_dir=None):
    """
    Save a structured log of what the code pre-decided before handing off to LLM.

    This enables future analysis: compare LLM veto/pass decisions against
    actual price outcomes to quantify the LLM's net contribution.
    """
    try:
        quant_signals = trend_signals.get("quant_signals", []) if trend_signals else []
        signals_presented = [s["ticker"] for s in quant_signals]
        entry_candidate_review = (
            trend_signals.get("entry_candidate_review")
            if isinstance(trend_signals, dict)
            else None
        )

        # Extract machine-state context from the preflight data embedded in
        # trend_signals (injected by build_prompt -> preflight_validator).
        position_states = {}
        suggested_reduce = {}
        new_trade_locked = None
        account_state = None
        lock_reason = None
        if isinstance(trend_signals, dict):
            preflight = trend_signals.get("preflight") or {}
            if isinstance(preflight, dict):
                position_states = preflight.get("position_states") or {}
                suggested_reduce = preflight.get("suggested_reduce_pct") or {}
                new_trade_locked = preflight.get("new_trade_locked")
                account_state = preflight.get("account_state")
                lock_reason = preflight.get("lock_reason")

        # Count news tiers
        tier_counts = {"T1": 0, "T2": 0, "T3": 0}
        for item in (trade_news or []):
            tier_counts[item.get("tier", "T3")] += 1

        log_entry = {
            "date": date_str,
            "signals_presented": signals_presented,
            "signal_details": [
                {
                    "ticker": s.get("ticker"),
                    "strategy": s.get("strategy"),
                    "entry_price": s.get("entry_price"),
                    "stop_price": s.get("stop_price"),
                    "target_price": s.get("target_price"),
                    "trade_quality_score": s.get("trade_quality_score"),
                    "risk_reward_ratio": s.get("risk_reward_ratio"),
                }
                for s in quant_signals
            ],
            "entry_candidate_review": entry_candidate_review,
            "news_summary": tier_counts,
            "has_actionable_news": tier_counts["T1"] > 0,
            "new_trade_locked": new_trade_locked,
            "account_state": account_state,
            "lock_reason": lock_reason,
            "position_states": position_states,
            "suggested_reduce_pct": suggested_reduce,
        }

        log_file = str(daily_artifact_path("llm_decision_log", date_str, data_dir))
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)
        logger.info(f"Decision log saved to {log_file}")

    except Exception as e:
        logger.warning(f"Failed to save decision log: {e}")


def _write_prompt_body(path, system_message, user_message):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("SYSTEM MESSAGE\n")
        f.write("=" * 80 + "\n\n")
        f.write(system_message)
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("USER MESSAGE\n")
        f.write("=" * 80 + "\n\n")
        f.write(user_message)
        f.write("\n")


def _save_prompt_file(date_str, system_message, user_message, trade_news, trend_signals):
    """Persist the rendered prompt for auditability, regardless of API usage."""
    data_dir = _prompt_data_dir_for_current_context()
    prompt_file = daily_artifact_path("llm_prompt", date_str, data_dir)

    _write_prompt_body(prompt_file, system_message, user_message)
    logger.info(f"Prompt saved to {prompt_file}")

    # Save decision log: what signals/positions the code pre-decided,
    # so we can later compare LLM veto/pass against actual outcomes.
    _save_decision_log(date_str, trade_news, trend_signals, data_dir=data_dir)
    return str(prompt_file)


def get_investment_advice(
    trade_news,
    open_positions=None,
    trend_signals=None,
    model=LOCAL_CODEX_DEFAULT_MODEL,
    max_tokens=4000,
    save_prompt_only=False,
):
    """
    Build the daily LLM prompt, then prefer local Codex for the JSON response.

    The prompt and decision log are always persisted first. By default, this
    then calls local Codex with gpt-5.6-sol and saves the structured response
    through the same advice/replay archive path used by import_advice.py. If
    local Codex is disabled, unavailable, or returns invalid JSON, the function
    keeps the prompt-only fallback so the operator can still import manually.

    Args:
        trade_news (list): List of filtered trade news items
        open_positions (dict): Optional open positions data
        trend_signals (dict): Optional trend signal data
        model (str): Local Codex model id. Default is gpt-5.6-sol.
        max_tokens (int): Kept for legacy caller compatibility.
        save_prompt_only (bool): True skips local Codex and only saves prompt.

    Returns:
        dict: {
            "success": bool,
            "advice": str or None,
            "error": str or None,
            "token_usage": None
        }
    """
    del max_tokens  # Legacy API compatibility; local Codex is not token-capped here.

    # Load open positions if not provided
    if open_positions is None:
        open_positions = load_open_positions()

    # Build prompt
    try:
        system_message, user_message = build_prompt(trade_news, open_positions, trend_signals)
        if not system_message or not user_message:
            raise Exception("Failed to build prompt from template")
        logger.info(f"Built prompt with {len(trade_news)} news items")
    except Exception as e:
        logger.error(f"Failed to build prompt: {e}")
        return {
            "success": False,
            "advice": None,
            "error": f"Failed to build prompt: {e}",
            "token_usage": None
        }

    today = datetime.now().strftime("%Y%m%d")
    try:
        prompt_file = _save_prompt_file(
            today,
            system_message,
            user_message,
            trade_news,
            trend_signals,
        )
    except Exception as e:
        logger.error(f"Failed to save prompt: {e}")
        return {
            "success": False,
            "advice": None,
            "error": f"Failed to save prompt: {e}",
            "token_usage": None
        }

    data_dir = _prompt_data_dir_for_current_context()
    if not save_prompt_only and _local_codex_enabled():
        codex_result = _call_local_codex(
            prompt_file,
            system_message,
            user_message,
            today,
            data_dir,
            model=model,
        )
        if codex_result.get("success"):
            return {
                "success": True,
                "advice": (
                    f"Prompt saved to {prompt_file}\n"
                    f"Local Codex ({codex_result['model']}) advice saved to "
                    f"{codex_result['advice_path']}\n"
                    f"Replay artifact ready at {codex_result['replay_path']}"
                ),
                "error": None,
                "token_usage": codex_result.get("token_usage"),
            }

        diagnostic_path = codex_result.get("diagnostic_path")
        diagnostic_suffix = f" diagnostic={diagnostic_path}" if diagnostic_path else ""
        stderr_tail = _tail_text(codex_result.get("stderr"), limit=500).strip()
        logger.warning(
            "Local Codex auto-call failed: %s%s",
            codex_result.get("error"),
            diagnostic_suffix,
        )
        if stderr_tail:
            logger.warning("Local Codex stderr tail: %s", stderr_tail)
        fallback_lines = [
            f"Prompt saved to {prompt_file}",
            f"Local Codex auto-call failed: {codex_result.get('error')}",
        ]
        if diagnostic_path:
            fallback_lines.append(f"Diagnostic artifact: {diagnostic_path}")
        fallback_lines.extend(
            [
                "",
                "Manual fallback: import the structured JSON response via import_advice.py",
            ]
        )
        return {
            "success": True,
            "advice": "\n".join(fallback_lines),
            "error": None,
            "token_usage": {
                "provider": "local_codex",
                "model": codex_result.get("model") or _resolve_local_codex_model(model),
                "error": codex_result.get("error"),
                "diagnostic_path": diagnostic_path,
                "stderr_tail": stderr_tail or None,
            },
        }

    return {
        "success": True,
        "advice": (
            f"Prompt saved to {prompt_file}\n\n"
            "Local Codex auto-call is disabled for this run. "
            "Import the structured JSON response via import_advice.py."
        ),
        "error": None,
        "token_usage": None,
    }


def parse_json_advice(advice_text):
    """
    Try to parse JSON from the advice text.

    Args:
        advice_text (str): The raw advice text from LLM

    Returns:
        dict: Parsed JSON or None if parsing failed
    """
    try:
        # Try to find JSON block in the response
        import re
        json_match = re.search(r'\{[\s\S]*\}', advice_text)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        return None
    except Exception as e:
        logger.warning(f"Failed to parse JSON from advice: {e}")
        return None


def save_advice(advice, filepath, token_usage=None):
    """
    Save investment advice to a file.

    Args:
        advice (str): The investment advice text
        filepath (str): Path to save the advice
        token_usage (dict): Optional token usage statistics

    Returns:
        bool: True if successful
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Try to parse structured JSON from advice
        parsed_advice = parse_json_advice(advice)
        basename = os.path.basename(filepath)
        data_dir = _archive_root_for_output(filepath)
        advice_date = _dated_advice_basename_date(basename)

        pending_overrides = []
        if isinstance(parsed_advice, dict):
            try:
                from pending_actions import (
                    apply_pending_action_overrides,
                    load_pending_actions,
                    register_pending_actions_from_advice,
                    save_pending_actions,
                )

                open_positions = load_open_positions()
                parsed_advice, pending_overrides = apply_pending_action_overrides(
                    parsed_advice,
                    open_positions,
                    data_dir=data_dir,
                    as_of_date=advice_date,
                )
                pending_records = register_pending_actions_from_advice(
                    parsed_advice,
                    open_positions,
                    existing_actions=load_pending_actions(data_dir),
                    as_of_date=advice_date,
                    source_file=basename,
                )
                save_pending_actions(pending_records, data_dir)
            except Exception as e:
                logger.warning("Pending-action reconciliation skipped: %s", e)

        output = {
            "timestamp": datetime.now().isoformat(),
            "advice_raw": advice,
            "advice_parsed": parsed_advice,
            "token_usage": token_usage
        }
        if pending_overrides:
            output["pending_action_overrides"] = [
                {
                    "ticker": item.get("ticker"),
                    "action": item.get("action"),
                    "shares_to_buy": item.get("shares_to_buy"),
                    "first_advice_date": item.get("first_advice_date"),
                    "exit_rule_triggered": item.get("exit_rule_triggered"),
                }
                for item in pending_overrides
            ]

        if advice_date:
            archive_context = _build_archive_context(advice_date, data_dir)
            if archive_context:
                output["archive_context"] = archive_context

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved investment advice to {filepath}")
        _maybe_write_replay_log(filepath, output)
        return True

    except Exception as e:
        logger.error(f"Failed to save advice: {e}")
        return False


def _dated_advice_basename_date(basename):
    """Extract YYYYMMDD from a dated advice/replay basename, else None.

    llm_prompt_resp_<date>.json is the canonical replay artifact; the
    investment_advice_<date>.json prefix is kept for legacy archives.
    """
    for prefix in ("llm_prompt_resp_", "investment_advice_"):
        if basename.startswith(prefix) and basename.endswith(".json"):
            date_str = basename[len(prefix):-len(".json")]
            if len(date_str) == 8 and date_str.isdigit():
                return date_str
    return None


def _maybe_write_replay_log(filepath, output):
    """Mirror legacy dated advice files to llm replay logs for backtest parity.

    Writes targeted directly at llm_prompt_resp_<date>.json ARE the replay
    log, so only the legacy investment_advice_ prefix needs mirroring.
    """
    basename = os.path.basename(filepath)
    if not basename.startswith("investment_advice_") or not basename.endswith(".json"):
        return

    date_str = basename[len("investment_advice_"):-len(".json")]
    if len(date_str) != 8 or not date_str.isdigit():
        return

    parsed_advice = output.get("advice_parsed")
    is_real_response = isinstance(parsed_advice, dict) and "new_trade" in parsed_advice
    if not is_real_response:
        logger.info(
            "Skipping LLM replay log for %s: parsed payload has no 'new_trade' key",
            basename,
        )
        return

    replay_path = _replay_log_path_for_output(filepath, date_str)
    if os.path.exists(replay_path):
        logger.info("LLM replay log already exists, skipping: %s", replay_path)
        return

    os.makedirs(os.path.dirname(replay_path), exist_ok=True)
    with open(replay_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info("Saved LLM replay log to %s", replay_path)
