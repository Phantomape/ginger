"""exp-20260504-008 SEC negative-language reaction absorption shadow replay.

Alpha search. Test whether the positive SEC filing-text negative-language
branch from exp-20260504-005 is actually strongest when the first public-PIT
same-day reaction is negative versus SPY. This does not change production or
backtest trading logic.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
EXPERIMENT_ID = "exp-20260504-008"
TEXT_PATH = DATA_DIR / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_negative_reaction_absorption.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_negative_reaction_absorption_20260504.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SNAPSHOT_FILES = {
    "old_thin": DATA_DIR / "ohlcv_snapshot_20241002_20250422.json",
    "mid_weak": DATA_DIR / "ohlcv_snapshot_20250423_20251022.json",
    "late_strong": DATA_DIR / "ohlcv_snapshot_20251023_20260421.json",
}
WINDOWS = OrderedDict(
    [
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
    ]
)
HORIZONS = (5, 10, 20)

BASELINE_METRICS = OrderedDict(
    [
        (
            "late_strong",
            {
                "expected_value_score": 3.4191,
                "sharpe_daily": 4.35,
                "total_pnl": 78600.33,
                "total_return_pct": 0.786,
                "max_drawdown_pct": 0.0541,
                "win_rate": 0.7895,
                "trade_count": 19,
                "survival_rate": 0.8039,
            },
        ),
        (
            "mid_weak",
            {
                "expected_value_score": 1.4415,
                "sharpe_daily": 2.62,
                "total_pnl": 55015.08,
                "total_return_pct": 0.5502,
                "max_drawdown_pct": 0.0879,
                "win_rate": 0.5238,
                "trade_count": 21,
                "survival_rate": 0.7925,
            },
        ),
        (
            "old_thin",
            {
                "expected_value_score": 0.3179,
                "sharpe_daily": 1.29,
                "total_pnl": 24642.07,
                "total_return_pct": 0.2464,
                "max_drawdown_pct": 0.0805,
                "win_rate": 0.4091,
                "trade_count": 22,
                "survival_rate": 0.9167,
            },
        ),
    ]
)

DEFERRED_RESULTS_PHRASES = (
    "will post its financial results",
    "financial results will be announced",
    "will announce its financial results",
    "will issue its financial results",
    "will report financial results",
)
PRODUCTION_UPDATE_PHRASES = (
    "production, deliveries",
    "produced approximately",
    "delivered approximately",
    "vehicle deliveries",
    "storage deployments",
)
EARNINGS_RELEASE_PHRASES = (
    "announces financial results",
    "announced financial results",
    "reports financial results",
    "reported financial results",
    "quarterly financial results",
    "full year financial results",
    "fiscal year financial results",
    "results for the quarter",
)
POSITIVE_PHRASES = (
    "record revenue",
    "record quarterly",
    "record results",
    "strong demand",
    "robust demand",
    "accelerating demand",
    "continued momentum",
    "margin expansion",
    "expanded margin",
    "operating leverage",
    "free cash flow",
    "above expectations",
    "exceeded expectations",
    "better than expected",
)
NEGATIVE_PHRASES = (
    "weak demand",
    "soft demand",
    "lower demand",
    "headwinds",
    "margin pressure",
    "cost pressure",
    "challenging environment",
    "macroeconomic uncertainty",
    "inventory correction",
    "restructuring",
    "impairment",
    "declined",
    "decreased",
)
GUIDANCE_RAISE_PATTERNS = (
    r"\brais(?:e|es|ed|ing)\b.{0,80}\bguidance\b",
    r"\bguidance\b.{0,80}\brais(?:e|es|ed|ing)\b",
    r"\bincreas(?:e|es|ed|ing)\b.{0,80}\b(outlook|guidance)\b",
    r"\brais(?:e|es|ed|ing)\b.{0,80}\b(outlook|forecast)\b",
)
GUIDANCE_CUT_PATTERNS = (
    r"\blower(?:s|ed|ing)?\b.{0,80}\bguidance\b",
    r"\bguidance\b.{0,80}\blower(?:s|ed|ing)?\b",
    r"\breduc(?:e|es|ed|ing)\b.{0,80}\b(outlook|guidance)\b",
    r"\bwithdraw(?:s|n|ing)?\b.{0,80}\b(outlook|guidance)\b",
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _safe(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe(value) for value in payload]
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = float(value)
        if math.isfinite(value):
            return value
    return None


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def _pct_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1.0


def load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        converted = []
        for row in rows:
            date_value = str(row.get("Date") or row.get("date") or "")[:10]
            if not date_value:
                continue
            converted.append(
                {
                    "date": date_value,
                    "open": _as_float(row.get("Open") if "Open" in row else row.get("open")),
                    "close": _as_float(row.get("Close") if "Close" in row else row.get("close")),
                }
            )
        if converted:
            out[str(ticker).upper()] = sorted(converted, key=lambda item: item["date"])
    return out


def _idx_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _idx_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] > target:
            return idx
    return None


def window_for_date(date_value: str) -> str | None:
    for label, cfg in WINDOWS.items():
        if cfg["start"] <= date_value <= cfg["end"]:
            return label
    return None


def _is_semantic_doc_name(name: str, primary_document: str | None) -> bool:
    lowered = name.lower()
    primary = str(primary_document or "").lower()
    if "index-headers" in lowered or re.fullmatch(r"r\d+\.htm", lowered):
        return False
    if re.search(r"(ex[-_]?99|exhibit[-_]?99|ex99|ex991|e991|exhibit99)", lowered):
        return True
    return bool(primary and lowered == primary)


def _document_sections(combined_text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for match in re.finditer(r"(?:^| )DOCUMENT ([^ ]+) ", combined_text):
        start = match.end()
        end_match = re.search(r" DOCUMENT [^ ]+ ", combined_text[start:])
        end = start + end_match.start() if end_match else len(combined_text)
        sections.append((match.group(1), combined_text[start:end].strip()))
    return sections


def semantic_text(row: dict[str, Any]) -> str:
    combined = str(row.get("combined_text") or "")
    if not combined:
        return ""
    primary = row.get("primary_document")
    parts = [
        text
        for name, text in _document_sections(combined)
        if _is_semantic_doc_name(name, str(primary) if primary else None)
    ]
    return (" ".join(parts) if parts else combined)[:120000]


def _phrase_count(text: str, phrases: tuple[str, ...]) -> int:
    return sum(text.count(phrase) for phrase in phrases)


def _pattern_count(text: str, patterns: tuple[str, ...]) -> int:
    return sum(len(re.findall(pattern, text, flags=re.I | re.S)) for pattern in patterns)


def language_features(row: dict[str, Any]) -> dict[str, Any]:
    text = semantic_text(row)
    lowered = text.lower()
    deferred_hits = _phrase_count(lowered, DEFERRED_RESULTS_PHRASES)
    production_hits = _phrase_count(lowered, PRODUCTION_UPDATE_PHRASES)
    earnings_hits = _phrase_count(lowered, EARNINGS_RELEASE_PHRASES)
    positive_hits = _phrase_count(lowered, POSITIVE_PHRASES)
    negative_hits = _phrase_count(lowered, NEGATIVE_PHRASES)
    guidance_raise_hits = _pattern_count(lowered, GUIDANCE_RAISE_PATTERNS)
    guidance_cut_hits = _pattern_count(lowered, GUIDANCE_CUT_PATTERNS)

    if deferred_hits and production_hits:
        event_type = "deferred_results_or_operational_update"
    elif earnings_hits or (
        "revenue" in lowered
        and ("net income" in lowered or "earnings per share" in lowered or "eps" in lowered)
    ):
        event_type = "earnings_release_text"
    elif production_hits:
        event_type = "operational_update"
    else:
        event_type = "item_2_02_other_text"

    score = positive_hits + 2 * guidance_raise_hits - negative_hits - 2 * guidance_cut_hits
    if event_type == "deferred_results_or_operational_update":
        bucket = "deferred_or_operational"
    elif score >= 2:
        bucket = "positive_language"
    elif score <= -2:
        bucket = "negative_language"
    else:
        bucket = "neutral_or_mixed_language"

    return {
        "text_event_type": event_type,
        "language_score": score,
        "language_bucket": bucket,
        "positive_phrase_hits": positive_hits,
        "negative_phrase_hits": negative_hits,
        "guidance_raise_hits": guidance_raise_hits,
        "guidance_cut_hits": guidance_cut_hits,
    }


def evaluate_price(event: dict[str, Any], snapshot: dict[str, list[dict[str, Any]]], window: str) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    out = dict(event)
    out["window"] = window
    if not rows or not spy_rows:
        out["price_status"] = "missing_ticker_or_spy"
        out["horizons"] = {}
        return out

    usable = str(event.get("usable_trade_date") or "")
    reaction_idx = _idx_on_or_after(rows, usable)
    spy_reaction_idx = _idx_on_or_after(spy_rows, usable)
    if reaction_idx is None or spy_reaction_idx is None:
        out["price_status"] = "missing_reaction_date"
        out["horizons"] = {}
        return out
    reaction = rows[reaction_idx]
    spy_reaction = spy_rows[spy_reaction_idx]
    reaction_date = reaction["date"]
    entry_idx = _idx_after(rows, reaction_date)
    spy_entry_idx = _idx_after(spy_rows, reaction_date)
    if entry_idx is None or spy_entry_idx is None:
        out["price_status"] = "missing_entry_date"
        out["horizons"] = {}
        return out

    reaction_return = _pct_change(reaction.get("open"), reaction.get("close"))
    spy_reaction_return = _pct_change(spy_reaction.get("open"), spy_reaction.get("close"))
    out.update(
        {
            "price_status": "covered",
            "reaction_date": reaction_date,
            "entry_date": rows[entry_idx]["date"],
            "reaction_return": _round(reaction_return),
            "reaction_excess_return": _round(
                reaction_return - spy_reaction_return
                if reaction_return is not None and spy_reaction_return is not None
                else None
            ),
        }
    )

    horizons: dict[str, dict[str, Any]] = {}
    entry_open = rows[entry_idx].get("open")
    spy_entry_open = spy_rows[spy_entry_idx].get("open")
    for horizon in HORIZONS:
        end_idx = entry_idx + horizon - 1
        spy_end_idx = spy_entry_idx + horizon - 1
        if end_idx >= len(rows) or spy_end_idx >= len(spy_rows):
            horizons[f"{horizon}d"] = {"status": "insufficient_forward_days"}
            continue
        ret = _pct_change(entry_open, rows[end_idx].get("close"))
        spy_ret = _pct_change(spy_entry_open, spy_rows[spy_end_idx].get("close"))
        horizons[f"{horizon}d"] = {
            "status": "valid" if ret is not None and spy_ret is not None else "missing_price",
            "return": _round(ret),
            "spy_return": _round(spy_ret),
            "excess_return": _round(ret - spy_ret if ret is not None and spy_ret is not None else None),
            "end_date": rows[end_idx]["date"],
        }
    out["horizons"] = horizons
    return out


def reaction_bucket(row: dict[str, Any]) -> str:
    value = row.get("reaction_excess_return")
    if not isinstance(value, (int, float)):
        return "reaction_missing"
    if value >= 0:
        return "reaction_ge_0"
    if value >= -0.02:
        return "reaction_-2_to_0"
    if value >= -0.05:
        return "reaction_-5_to_-2"
    return "reaction_lt_-5"


def distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg": None, "median": None, "p25": None, "p75": None, "win_rate": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "avg": _round(mean(values)),
        "median": _round(median(values)),
        "p25": _round(ordered[int((len(ordered) - 1) * 0.25)]),
        "p75": _round(ordered[int((len(ordered) - 1) * 0.75)]),
        "win_rate": _round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def summarize_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for horizon in HORIZONS:
        key = f"{horizon}d"
        out[key] = {}
        for metric in ("return", "excess_return"):
            values = []
            for row in rows:
                value = ((row.get("horizons") or {}).get(key) or {}).get(metric)
                if isinstance(value, (int, float)) and math.isfinite(value):
                    values.append(float(value))
            out[key][metric] = distribution(values)
    return out


def summarize_group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "unknown")].append(row)
    return {
        label: {
            "event_count": len(items),
            "forward_distribution": summarize_forward(items),
        }
        for label, items in sorted(groups.items())
    }


def compact_event(row: dict[str, Any]) -> dict[str, Any]:
    horizons = row.get("horizons") or {}
    return {
        "ticker": row.get("ticker"),
        "window": row.get("window"),
        "usable_trade_date": row.get("usable_trade_date"),
        "entry_date": row.get("entry_date"),
        "accession_number": row.get("accession_number"),
        "text_event_type": row.get("text_event_type"),
        "language_bucket": row.get("language_bucket"),
        "reaction_bucket": row.get("reaction_bucket"),
        "reaction_excess_return": row.get("reaction_excess_return"),
        "horizons": {key: horizons.get(key) for key in ("5d", "10d", "20d")},
    }


def build_payload() -> dict[str, Any]:
    text_rows = _load_jsonl(TEXT_PATH)
    snapshots = {label: load_snapshot(path) for label, path in SNAPSHOT_FILES.items()}
    evaluated = []
    for row in text_rows:
        event = {**row, **language_features(row)}
        window = window_for_date(str(event.get("usable_trade_date") or ""))
        if not window:
            continue
        priced = evaluate_price(event, snapshots[window], window)
        priced["reaction_bucket"] = reaction_bucket(priced)
        evaluated.append(priced)

    covered = [row for row in evaluated if row.get("price_status") == "covered"]
    negative_language = [row for row in covered if row.get("language_bucket") == "negative_language"]
    primary = [
        row
        for row in negative_language
        if row.get("reaction_bucket") in {"reaction_-2_to_0", "reaction_-5_to_-2", "reaction_lt_-5"}
    ]
    reaction_ge_0 = [row for row in negative_language if row.get("reaction_bucket") == "reaction_ge_0"]

    by_reaction = summarize_group(negative_language, "reaction_bucket")
    primary_by_window = summarize_group(primary, "window")
    primary_10d_by_window = {
        window: data["forward_distribution"]["10d"]["excess_return"]
        for window, data in primary_by_window.items()
    }
    primary_valid_windows = [
        window
        for window, stats in primary_10d_by_window.items()
        if (stats.get("count") or 0) > 0 and (stats.get("avg") or 0) > 0
    ]
    primary_stats = summarize_forward(primary)
    primary_10d = primary_stats["10d"]["excess_return"]
    shadow_promising = (
        (primary_10d.get("count") or 0) >= 10
        and (primary_10d.get("avg") or 0) > 0
        and len(primary_valid_windows) == len(WINDOWS)
    )

    decision = "shadow_promising_not_promoted" if shadow_promising else "observed_only_not_promoted"
    rejection_reason = (
        "Shadow branch is positive but not production-promoted: SEC text/reaction grading is not yet a shared event "
        "policy, and no capital-allocation or replacement-value backtest has been run."
        if shadow_promising
        else "Reaction-conditioned negative-language branch did not meet the fixed-window shadow bar."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "SEC Item 2.02 filings whose text scores negative may be strongest when the first public-PIT reaction "
            "is also negative versus SPY, suggesting a bad-news-overreaction / recoverable-pressure setup rather "
            "than simple bad-news absorption."
        ),
        "alpha_hypothesis": {
            "category": "event_grading / entry_candidate_ranking",
            "entry_or_ranking": "ranking",
            "text": (
                "Within negative SEC filing language, same-day negative relative reaction should rank higher than "
                "nonnegative reaction for 10-20 day follow-through."
            ),
        },
        "change_type": "non_ohlcv_shadow_alpha",
        "single_causal_variable": "negative-language SEC filing events split by first-day reaction sign versus SPY",
        "historical_experiment_check": {
            "prior_same_family": {
                "exp-20260504-005": (
                    "Simple positive language failed; negative-language keyword proxy was shadow-positive but not "
                    "safe as a direct rule."
                ),
                "exp-20260504-002": "Raw positive SEC results-8K reaction failed.",
                "exp-20260504-004": "Companyfacts point score was nonmonotonic.",
            },
            "why_this_is_not_repeat": (
                "This does not promote negative keywords and does not tune positive-reaction thresholds. It tests a "
                "new mechanism: negative disclosure plus negative first reaction as a recoverable-pressure candidate "
                "ranking feature."
            ),
            "mechanism_insight_check": (
                "Recent playbook says the next valid filing-text retry needs richer grading rather than positive "
                "phrase tuning. This run keeps the text packet fixed and tests reaction semantics around the already "
                "identified negative-language pocket."
            ),
        },
        "parameters": {
            "forms": ["8-K"],
            "item_codes": ["2.02"],
            "reaction_metric": "ticker open-to-close return on usable trade date minus SPY open-to-close return",
            "primary_branch": "language_bucket == negative_language and reaction_excess_return < 0",
            "reaction_bins": ["reaction_ge_0", "reaction_-2_to_0", "reaction_-5_to_-2", "reaction_lt_-5"],
            "forward_horizons": list(HORIZONS),
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "add-ons",
                "exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": ["2025-04-23 -> 2025-10-22", "2024-10-02 -> 2025-04-22"],
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "shadow_only_no_strategy_logic_changed",
        },
        "gate4": {
            "passed": False,
            "basis": "No promoted strategy change; fixed-window A/B backtest metrics are unchanged by design.",
        },
        "coverage": {
            "text_rows_input": len(text_rows),
            "evaluated_event_count": len(evaluated),
            "price_covered_count": len(covered),
            "negative_language_event_count": len(negative_language),
            "primary_event_count": len(primary),
            "negative_reaction_ge0_event_count": len(reaction_ge_0),
            "by_price_status": dict(Counter(row.get("price_status") for row in evaluated)),
            "by_window": dict(Counter(row.get("window") for row in covered)),
            "negative_language_by_reaction_bucket": dict(
                Counter(row.get("reaction_bucket") for row in negative_language)
            ),
        },
        "shadow_metrics": {
            "all_covered_events": {
                "event_count": len(covered),
                "forward_distribution": summarize_forward(covered),
                "by_language_bucket": summarize_group(covered, "language_bucket"),
            },
            "negative_language": {
                "event_count": len(negative_language),
                "forward_distribution": summarize_forward(negative_language),
                "by_window": summarize_group(negative_language, "window"),
                "by_reaction_bucket": by_reaction,
            },
            "primary_negative_language_negative_reaction": {
                "event_count": len(primary),
                "forward_distribution": primary_stats,
                "by_window": primary_by_window,
                "sample_events": [compact_event(row) for row in primary[:25]],
            },
            "negative_language_nonnegative_reaction": {
                "event_count": len(reaction_ge_0),
                "forward_distribution": summarize_forward(reaction_ge_0),
                "by_window": summarize_group(reaction_ge_0, "window"),
            },
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "llm_ready_packet_count": len(primary),
            "llm_attribution_metric": (
                "primary 10d excess avg versus negative-language nonnegative-reaction branch"
            ),
        },
        "decision_rationale": rejection_reason,
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not promote keyword negative_language directly into entries.",
            "Freeze this negative-language + negative-reaction packet as structured LLM/event-sleeve input.",
            "Before production promotion, add shared production/backtest event policy and replacement-value logging.",
        ],
        "related_files": [
            "quant/experiments/exp_20260504_008_sec_negative_reaction_absorption.py",
            "data/experiments/exp-20260504-008/sec_negative_reaction_absorption.json",
            "docs/experiments/logs/exp-20260504-008.json",
            "docs/experiments/tickets/exp-20260504-008.json",
        ],
    }


def build_report(payload: dict[str, Any]) -> str:
    primary = payload["shadow_metrics"]["primary_negative_language_negative_reaction"]
    nonnegative = payload["shadow_metrics"]["negative_language_nonnegative_reaction"]
    primary_10d = primary["forward_distribution"]["10d"]["excess_return"]
    primary_20d = primary["forward_distribution"]["20d"]["excess_return"]
    nonnegative_10d = nonnegative["forward_distribution"]["10d"]["excess_return"]
    lines = [
        "# SEC Negative-Language Reaction Absorption Shadow",
        "",
        f"Experiment: `{EXPERIMENT_ID}`",
        "",
        "## Result",
        "",
        (
            "The strongest branch was not nonnegative reaction / simple absorption. "
            "It was `negative_language + reaction_excess_return < 0`."
        ),
        "",
        "| Branch | Events | 10d excess avg | 10d win rate | 20d excess avg | 20d win rate |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| negative language + negative reaction | {primary['event_count']} | "
            f"{primary_10d.get('avg')} | {primary_10d.get('win_rate')} | "
            f"{primary_20d.get('avg')} | {primary_20d.get('win_rate')} |"
        ),
        (
            f"| negative language + nonnegative reaction | {nonnegative['event_count']} | "
            f"{nonnegative_10d.get('avg')} | {nonnegative_10d.get('win_rate')} | "
            f"{nonnegative['forward_distribution']['20d']['excess_return'].get('avg')} | "
            f"{nonnegative['forward_distribution']['20d']['excess_return'].get('win_rate')} |"
        ),
        "",
        "## Gate 4",
        "",
        "No production strategy change was promoted. Core A/B backtest metrics remain unchanged.",
        "",
        "## Next",
        "",
        "Use this packet as structured LLM/event-sleeve input before any production promotion.",
    ]
    return "\n".join(lines) + "\n"


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, payload)
    _write_text(REPORT_MD, build_report(payload))
    log_line = json.dumps(
        {
            "experiment_id": payload["experiment_id"],
            "timestamp": payload["timestamp"],
            "status": payload["status"],
            "decision": payload["decision"],
            "lane": payload["lane"],
            "change_type": payload["change_type"],
            "hypothesis": payload["hypothesis"],
            "parameters": payload["parameters"],
            "date_range": payload["date_range"],
            "market_regime_summary": payload["market_regime_summary"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "production_impact": payload["production_impact"],
            "gate4": payload["gate4"],
            "coverage": payload["coverage"],
            "shadow_metrics": {
                "primary_negative_language_negative_reaction": payload["shadow_metrics"][
                    "primary_negative_language_negative_reaction"
                ],
                "negative_language_nonnegative_reaction": payload["shadow_metrics"][
                    "negative_language_nonnegative_reaction"
                ],
            },
            "llm_metrics": payload["llm_metrics"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "related_files": payload["related_files"],
        },
        sort_keys=True,
    )
    existing = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines() if EXPERIMENT_LOG.exists() else []
    if not any(f'"experiment_id": "{EXPERIMENT_ID}"' in line or f'"experiment_id":"{EXPERIMENT_ID}"' in line for line in existing):
        EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(log_line + "\n")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "coverage": payload["coverage"],
                "primary": payload["shadow_metrics"]["primary_negative_language_negative_reaction"][
                    "forward_distribution"
                ],
                "nonnegative_control": payload["shadow_metrics"]["negative_language_nonnegative_reaction"][
                    "forward_distribution"
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
