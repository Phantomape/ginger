#!/usr/bin/env python3
"""
Manual-import helper for LLM trading advice.

Current workflow: user runs run.py → gets data/llm_prompt_<date>.txt → pastes it
into ChatGPT / Claude web → copies the JSON response back. Without this helper,
the response is thrown away and forward_tester has nothing to grade.

This script takes the pasted response (which may include markdown fences,
leading commentary, or partial JSON) and writes it into TWO files:

1. ``data/investment_advice_<date>.json`` — wrapper format that forward_tester
   expects (``{advice_raw, advice_parsed, token_usage, timestamp}``).

2. ``data/llm_prompt_resp_<date>.json`` — same content, consumed by the
   backtester's ``--replay-llm`` path (llm_replay.py) to close the
   production/backtest parity gap for the LLM new-trade gate.

Usage:
    # From a saved file
    python quant/import_advice.py --date 2026-04-10 --input response.txt

    # From stdin (pipe or redirect)
    python quant/import_advice.py --date 2026-04-10 --stdin < response.txt

    # From the system clipboard (requires pyperclip)
    python quant/import_advice.py --date 2026-04-10 --clipboard

The --date argument accepts either YYYY-MM-DD or YYYYMMDD.  If omitted, today
is used.  The helper validates that ``new_trade`` and ``position_actions`` keys
are present; if either is missing, it logs a warning but still writes the file
so partial captures are not lost.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime

# Reuse existing parsing + writing helpers — do not duplicate.
# parse_json_advice handles markdown-fenced, leading-commentary, and clean JSON.
# save_advice writes the {advice_raw, advice_parsed, token_usage, timestamp} wrapper
# that forward_tester.evaluate_file() expects.
from llm_advisor import _build_archive_context, parse_json_advice, save_advice

logger = logging.getLogger(__name__)

DATA_DIR = "data"


def _parse_date_arg(raw: str | None) -> str:
    """Return YYYYMMDD. Accept YYYY-MM-DD, YYYYMMDD, or None (→ today)."""
    if raw is None or raw == "":
        return datetime.now().strftime("%Y%m%d")
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    raise SystemExit(f"Invalid --date {raw!r}; expected YYYY-MM-DD or YYYYMMDD")


def _read_source(args: argparse.Namespace) -> str:
    """Load raw response text from --input, --stdin, or --clipboard."""
    chosen = [flag for flag in ("input", "stdin", "clipboard") if getattr(args, flag)]
    if len(chosen) != 1:
        raise SystemExit("Specify exactly one of --input, --stdin, --clipboard")

    if args.input:
        if not os.path.exists(args.input):
            raise SystemExit(f"Input file not found: {args.input}")
        with open(args.input, "r", encoding="utf-8") as f:
            return f.read()

    if args.stdin:
        data = sys.stdin.read()
        if not data.strip():
            raise SystemExit("stdin was empty")
        return data

    # --clipboard
    try:
        import pyperclip  # type: ignore
    except ImportError:
        raise SystemExit(
            "pyperclip is not installed; install with `pip install pyperclip` "
            "or use --input / --stdin instead"
        )
    data = pyperclip.paste()
    if not data or not data.strip():
        raise SystemExit("Clipboard was empty")
    return data


def _extract_date_from_filename(path: str) -> str | None:
    """Extract YYYYMMDD from llm_output/investment_advice style filenames."""
    name = os.path.basename(path)
    match = re.search(r"_(\d{8})\.json$", name)
    if not match:
        return None
    return match.group(1)


def _load_json_file(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _load_text_file(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _is_real_saved_advice(payload) -> bool:
    """True only when the saved wrapper already contains a real new_trade decision."""
    if not isinstance(payload, dict):
        return False
    parsed = payload.get("advice_parsed")
    return isinstance(parsed, dict) and "new_trade" in parsed


def _normalize_replay_payload(raw_text: str, date_str: str, output_dir: str) -> dict:
    """Build a canonical replay wrapper with prompt-time archive context."""
    parsed_direct = None
    advice_raw = raw_text
    try:
        existing = json.loads(raw_text)
    except Exception:
        existing = None

    if isinstance(existing, dict) and "advice_parsed" in existing:
        parsed_direct = existing.get("advice_parsed")
        advice_raw = existing.get("advice_raw") or raw_text

    payload = {
        "timestamp": datetime.now().isoformat(),
        "advice_raw": advice_raw,
        "advice_parsed": (
            parsed_direct if isinstance(parsed_direct, dict) else parse_json_advice(advice_raw)
        ),
        "token_usage": None,
    }
    archive_context = _build_archive_context(date_str, output_dir)
    if archive_context:
        payload["archive_context"] = archive_context
    return payload


def normalize_replay_archive(
    date_str: str,
    *,
    output_dir: str = DATA_DIR,
    raw_text: str | None = None,
) -> dict:
    """
    Rewrite llm_prompt_resp_YYYYMMDD.json into canonical wrapper form.
    """
    replay_path = os.path.join(output_dir, f"llm_prompt_resp_{date_str}.json")
    existing_text = raw_text if raw_text is not None else _load_text_file(replay_path)
    if not existing_text or not existing_text.strip():
        return {
            "date_str": date_str,
            "status": "missing_replay_text",
            "replay_path": replay_path,
        }

    payload = _normalize_replay_payload(existing_text, date_str, output_dir)
    parsed = payload.get("advice_parsed")
    if not (isinstance(parsed, dict) and "new_trade" in parsed):
        return {
            "date_str": date_str,
            "status": "skipped_non_response",
            "replay_path": replay_path,
        }

    with open(replay_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return {
        "date_str": date_str,
        "status": "normalized",
        "replay_path": replay_path,
        "has_archive_context": "archive_context" in payload,
        "signals_presented_count": (
            (payload.get("archive_context") or {}).get("signals_presented_count")
        ),
        "ranking_eligible": (payload.get("archive_context") or {}).get("ranking_eligible"),
    }


def _validate_structure(parsed: dict | None, raw_text: str) -> dict:
    """
    Ensure parsed response is a dict with new_trade + position_actions.
    Warn on missing keys; do not raise — partial captures are still useful.
    """
    if parsed is None:
        logger.error(
            "Could not extract JSON from response. Saving raw text only so you "
            "can inspect the file and retry."
        )
        # Still return an empty dict so save_advice writes the raw envelope.
        return {}

    if not isinstance(parsed, dict):
        logger.warning(
            "Parsed response is %s, not a JSON object — saving as-is but "
            "forward_tester will likely skip it",
            type(parsed).__name__,
        )
        return {} if not isinstance(parsed, dict) else parsed

    if "new_trade" not in parsed:
        logger.warning(
            "Response is missing 'new_trade' key — forward_tester will skip "
            "new-trade grading for this file"
        )
    if "position_actions" not in parsed:
        logger.warning(
            "Response is missing 'position_actions' key — forward_tester will "
            "skip position grading for this file"
        )
    return parsed


def import_advice(
    date_str: str,
    raw_text: str,
    output_dir: str = DATA_DIR,
) -> str:
    """
    Parse raw LLM response text and write it to two files:
      - ``<output_dir>/investment_advice_<YYYYMMDD>.json``  (forward_tester)
      - ``<output_dir>/llm_prompt_resp_<YYYYMMDD>.json``    (backtester --replay-llm)

    Args:
        date_str:   YYYYMMDD (produced by _parse_date_arg)
        raw_text:   The pasted LLM response (may contain fences / commentary)
        output_dir: Directory to write into (default: data/)

    Returns:
        The absolute path to the primary output file (investment_advice_*.json).
    """
    parsed = parse_json_advice(raw_text)
    _validate_structure(parsed, raw_text)

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"investment_advice_{date_str}.json")

    # save_advice rebuilds the wrapper (advice_raw / advice_parsed / token_usage
    # / timestamp) that forward_tester.evaluate_file expects.  Pass token_usage=None
    # because we don't know usage from a pasted response.
    ok = save_advice(raw_text, out_path, token_usage=None)
    if not ok:
        raise SystemExit(f"Failed to write {out_path}")

    # Also write llm_prompt_resp_YYYYMMDD.json for the backtester's --replay-llm path.
    # llm_replay.py handles the same wrapper format (advice_parsed key present → unwrap).
    # This closes the production/backtest parity gap for the LLM new-trade gate (P-LLM).
    # Guard: only write if this is a real LLM response (has parseable new_trade or
    # explicit NO NEW TRADE), not a "Prompt saved to..." acknowledgment message.
    _is_real_response = (isinstance(parsed, dict) and "new_trade" in parsed)
    replay_path = os.path.join(output_dir, f"llm_prompt_resp_{date_str}.json")
    if _is_real_response and not os.path.exists(replay_path):
        try:
            import shutil
            shutil.copy2(out_path, replay_path)
            logger.info("LLM replay log written → %s", replay_path)
        except Exception as e:
            logger.warning("Could not write LLM replay log %s: %s", replay_path, e)
    elif not _is_real_response:
        logger.warning(
            "Skipping LLM replay log: response does not contain 'new_trade' key "
            "(likely a save-prompt acknowledgment, not a real LLM response)"
        )
    else:
        logger.info("LLM replay log already exists; preserving existing file: %s", replay_path)

    # Log a one-line summary so the user can see what landed in the file.
    if isinstance(parsed, dict):
        nt = parsed.get("new_trade")
        if isinstance(nt, dict):
            nt_desc = f"new_trade={nt.get('ticker', '?')} ({nt.get('signal_source', '?')})"
        elif isinstance(nt, str):
            nt_desc = f"new_trade={nt}"
        else:
            nt_desc = "new_trade=<missing>"
        pa = parsed.get("position_actions")
        pa_desc = f"position_actions={len(pa)}" if isinstance(pa, list) else "position_actions=<missing>"
        logger.info("Imported %s, %s → %s", nt_desc, pa_desc, out_path)
    else:
        logger.info("Imported raw text (no parsed JSON) → %s", out_path)

    return out_path


def recover_advice_from_raw_output(
    raw_output_path: str,
    *,
    date_str: str | None = None,
    output_dir: str = DATA_DIR,
) -> dict:
    """
    Recover a replayable advice archive from an existing llm_output_YYYYMMDD.json file.

    This is for legacy/raw captures that were saved outside the normal import flow.
    It only overwrites investment_advice_YYYYMMDD.json when the existing file is a
    placeholder/non-response shell; real parsed advice files are preserved.
    """
    if not os.path.exists(raw_output_path):
        raise SystemExit(f"Raw output file not found: {raw_output_path}")

    resolved_date = date_str or _extract_date_from_filename(raw_output_path)
    if not resolved_date:
        raise SystemExit(
            f"Could not infer date from {raw_output_path!r}; pass date_str explicitly"
        )
    resolved_date = _parse_date_arg(resolved_date)

    with open(raw_output_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    os.makedirs(output_dir, exist_ok=True)
    advice_path = os.path.join(output_dir, f"investment_advice_{resolved_date}.json")
    replay_path = os.path.join(output_dir, f"llm_prompt_resp_{resolved_date}.json")

    existing = _load_json_file(advice_path)
    if _is_real_saved_advice(existing):
        return {
            "date_str": resolved_date,
            "status": "skipped_existing_real_advice",
            "advice_path": advice_path,
            "replay_path": replay_path,
        }

    out_path = import_advice(resolved_date, raw_text, output_dir=output_dir)
    return {
        "date_str": resolved_date,
        "status": "recovered",
        "advice_path": out_path,
        "replay_path": replay_path,
    }


def normalize_replay_file(
    replay_path: str,
    *,
    date_str: str | None = None,
    output_dir: str = DATA_DIR,
) -> dict:
    """Normalize an existing llm_prompt_resp_YYYYMMDD.json file in place."""
    if not os.path.exists(replay_path):
        raise SystemExit(f"Replay file not found: {replay_path}")

    resolved_date = date_str or _extract_date_from_filename(replay_path)
    if not resolved_date:
        raise SystemExit(
            f"Could not infer date from {replay_path!r}; pass date_str explicitly"
        )
    resolved_date = _parse_date_arg(resolved_date)
    raw_text = _load_text_file(replay_path)
    return normalize_replay_archive(
        resolved_date,
        output_dir=output_dir,
        raw_text=raw_text,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Import a pasted LLM advice response into data/investment_advice_<date>.json",
    )
    parser.add_argument("--date", type=str, default=None,
                        help="Recommendation date (YYYY-MM-DD or YYYYMMDD). Default: today.")
    src = parser.add_argument_group("input source (choose exactly one)")
    src.add_argument("--input",     type=str, default=None, help="Path to a file containing the response")
    src.add_argument("--stdin",     action="store_true",    help="Read response from stdin")
    src.add_argument("--clipboard", action="store_true",    help="Read response from the system clipboard (requires pyperclip)")
    parser.add_argument("--output-dir", type=str, default=DATA_DIR,
                        help=f"Directory to write into (default: {DATA_DIR})")
    args = parser.parse_args()

    date_str = _parse_date_arg(args.date)
    raw_text = _read_source(args)
    import_advice(date_str, raw_text, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
