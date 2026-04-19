"""
LLM decision replay for backtester.

Reads data/llm_prompt_resp_YYYYMMDD.json and returns the LLM's approved tickers
for new entries on that date. Used by backtester's --replay-llm path to close
the §6.1 parity gap between production (LLM gates new trades) and backtest
(historically accepted all code-surviving signals).

Files are written by import_advice.py (which copies investment_advice_YYYYMMDD.json
to llm_prompt_resp_YYYYMMDD.json) or manually. Both bare JSON and the
{advice_raw, advice_parsed, ...} wrapper format are accepted.

Only `new_trade` is replayed. `position_actions` are ignored because exits in
the backtester are already code-deterministic (same rule engine as production's
forced_rule path); mixing the LLM's position_actions would cross LLM and
forced_rule bookkeeping without adding signal.
"""
import json
import os
from datetime import datetime


def _response_path(date_str, data_dir):
    return os.path.join(data_dir, f"llm_prompt_resp_{date_str}.json")


def _extract_advice_body(raw):
    """Accept both save_advice-wrapped and bare advice JSON."""
    if not isinstance(raw, dict):
        return None
    if "advice_parsed" in raw:
        return raw.get("advice_parsed") or {}
    return raw


def _approved_tickers_from_advice(advice):
    """
    new_trade shapes observed in the wild:
      - dict with {"ticker": "AMZN", ...}  → approved = ["AMZN"]
      - str "NO NEW TRADE" / None / missing → approved = []
      - dict with ticker=None / ""          → approved = []
    """
    if not isinstance(advice, dict):
        return []
    new_trade = advice.get("new_trade")
    if isinstance(new_trade, dict):
        ticker = new_trade.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            return [ticker.strip().upper()]
    return []


def get_llm_decision_for_date(date_obj, data_dir="data"):
    """
    Args:
        date_obj: datetime.date / datetime.datetime / pandas Timestamp / str
        data_dir: directory holding llm_prompt_resp_YYYYMMDD.json files

    Returns:
        {
          "file_present":       bool,
          "date_str":           "YYYYMMDD",
          "approved_tickers":   list[str],   # [] when file missing OR LLM said no new trade
        }
    """
    if hasattr(date_obj, "strftime"):
        date_str = date_obj.strftime("%Y%m%d")
    else:
        date_str = str(date_obj).replace("-", "")[:8]

    path = _response_path(date_str, data_dir)
    if not os.path.exists(path):
        return {
            "file_present":     False,
            "date_str":         date_str,
            "approved_tickers": [],
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {
            "file_present":     False,
            "date_str":         date_str,
            "approved_tickers": [],
        }

    advice = _extract_advice_body(raw)
    approved = _approved_tickers_from_advice(advice)
    return {
        "file_present":     True,
        "date_str":         date_str,
        "approved_tickers": approved,
    }


def apply_llm_gate(signals, decision):
    """
    Apply LLM approval decision to a list of sized signals.

    Args:
        signals: list of signal dicts, each with "ticker" key
        decision: return value of get_llm_decision_for_date

    Returns:
        (filtered_signals, presented_n, vetoed_n)

        presented_n = len(signals) at entry
        vetoed_n    = presented_n - len(filtered_signals)
                      (0 if file_present is False — replay missing => no veto)
    """
    presented_n = len(signals)
    if not decision["file_present"]:
        return list(signals), presented_n, 0
    approved = {t.upper() for t in decision["approved_tickers"]}
    kept = [s for s in signals if (s.get("ticker") or "").upper() in approved]
    return kept, presented_n, presented_n - len(kept)
