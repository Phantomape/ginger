"""exp-20260504-005 SEC results 8-K filing-text language shadow replay.

Shadow-only alpha search. It tests whether newly backfilled SEC filing text
adds information beyond raw Item 2.02 filing presence, Companyfacts checklists,
or first price reaction. No production/backtest entry, ranking, sizing, or
exit logic is changed.
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
EXPERIMENT_ID = "exp-20260504-007"
TEXT_PATH = DATA_DIR / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
TEXT_SUMMARY_PATH = DATA_DIR / "non_ohlcv" / "sec_filing_text_backfill_summary_20241002_20260421.json"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_filing_text_language_shadow.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = REPO_ROOT / "docs" / "non_ohlcv_data_audit" / "sec_filing_text_language_shadow_20260504.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
BASELINE_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / "exp-20260503-051.json"

SNAPSHOT_FILES = {
    "old_thin": DATA_DIR / "ohlcv_snapshot_20241002_20250422.json",
    "mid_weak": DATA_DIR / "ohlcv_snapshot_20250423_20251022.json",
    "late_strong": DATA_DIR / "ohlcv_snapshot_20251023_20260421.json",
}
WINDOWS = OrderedDict([
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
])

HORIZONS = (5, 10, 20)
MIN_VALID_10D = 10

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


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        out = float(value)
        if math.isfinite(out):
            return out
    return None


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _pct_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1.0


def _safe_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _safe_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe_payload(value) for value in payload]
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    return payload


def load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path, {})
    raw = payload.get("ohlcv") if isinstance(payload, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw or {}).items():
        converted = []
        for row in rows or []:
            date_value = str(row.get("Date") or row.get("date") or "")[:10]
            if not date_value:
                continue
            converted.append({
                "date": date_value,
                "open": _as_float(row.get("Open") if "Open" in row else row.get("open")),
                "close": _as_float(row.get("Close") if "Close" in row else row.get("close")),
                "volume": _as_float(row.get("Volume") if "Volume" in row else row.get("volume")),
            })
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
        text for name, text in _document_sections(combined)
        if _is_semantic_doc_name(name, str(primary) if primary else None)
    ]
    if not parts:
        return combined[:120000]
    return " ".join(parts)[:120000]


def _phrase_count(text: str, phrases: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(lowered.count(phrase) for phrase in phrases)


def _pattern_count(text: str, patterns: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(len(re.findall(pattern, lowered, flags=re.I | re.S)) for pattern in patterns)


def extract_snippets(text: str, phrases: tuple[str, ...], *, max_snippets: int = 4, radius: int = 120) -> list[str]:
    lowered = text.lower()
    snippets: list[str] = []
    for phrase in phrases:
        start = lowered.find(phrase)
        if start == -1:
            continue
        lo = max(0, start - radius)
        hi = min(len(text), start + len(phrase) + radius)
        snippet = re.sub(r"\s+", " ", text[lo:hi]).strip()
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= max_snippets:
            break
    return snippets


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
    elif earnings_hits or ("revenue" in lowered and ("net income" in lowered or "earnings per share" in lowered or "eps" in lowered)):
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

    matched_phrases = []
    for phrase in POSITIVE_PHRASES:
        if phrase in lowered:
            matched_phrases.append(f"positive:{phrase}")
    for phrase in NEGATIVE_PHRASES:
        if phrase in lowered:
            matched_phrases.append(f"negative:{phrase}")
    if guidance_raise_hits:
        matched_phrases.append("positive:guidance_raise_pattern")
    if guidance_cut_hits:
        matched_phrases.append("negative:guidance_cut_pattern")
    if deferred_hits:
        matched_phrases.append("event:deferred_results")

    return {
        "semantic_text_char_count": len(text),
        "text_event_type": event_type,
        "language_score": score,
        "language_bucket": bucket,
        "positive_phrase_hits": positive_hits,
        "negative_phrase_hits": negative_hits,
        "guidance_raise_hits": guidance_raise_hits,
        "guidance_cut_hits": guidance_cut_hits,
        "deferred_results_hits": deferred_hits,
        "production_update_hits": production_hits,
        "earnings_release_hits": earnings_hits,
        "matched_phrases": matched_phrases[:20],
        "audit_snippets": extract_snippets(
            text,
            POSITIVE_PHRASES + NEGATIVE_PHRASES + DEFERRED_RESULTS_PHRASES,
            max_snippets=4,
        ),
    }


def evaluate_price(event: dict[str, Any], snapshot: dict[str, list[dict[str, Any]]], window: str) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
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
    qqq_entry_idx = _idx_after(qqq_rows, reaction_date) if qqq_rows else None
    if entry_idx is None or spy_entry_idx is None:
        out["price_status"] = "missing_entry_date"
        out["horizons"] = {}
        return out

    reaction_return = _pct_change(reaction.get("open"), reaction.get("close"))
    spy_reaction_return = _pct_change(spy_reaction.get("open"), spy_reaction.get("close"))
    out.update({
        "price_status": "covered",
        "reaction_date": reaction_date,
        "entry_date": rows[entry_idx]["date"],
        "reaction_return": _round(reaction_return),
        "reaction_excess_return": _round(
            reaction_return - spy_reaction_return
            if reaction_return is not None and spy_reaction_return is not None
            else None
        ),
    })

    horizons: dict[str, dict[str, Any]] = {}
    entry_open = rows[entry_idx].get("open")
    spy_entry_open = spy_rows[spy_entry_idx].get("open")
    qqq_entry_open = qqq_rows[qqq_entry_idx].get("open") if qqq_rows and qqq_entry_idx is not None else None
    for horizon in HORIZONS:
        end_idx = entry_idx + horizon - 1
        spy_end_idx = spy_entry_idx + horizon - 1
        qqq_end_idx = qqq_entry_idx + horizon - 1 if qqq_entry_idx is not None else None
        if end_idx >= len(rows) or spy_end_idx >= len(spy_rows):
            horizons[f"{horizon}d"] = {"status": "insufficient_forward_days"}
            continue
        ret = _pct_change(entry_open, rows[end_idx].get("close"))
        spy_ret = _pct_change(spy_entry_open, spy_rows[spy_end_idx].get("close"))
        qqq_ret = None
        if qqq_rows and qqq_end_idx is not None and qqq_end_idx < len(qqq_rows):
            qqq_ret = _pct_change(qqq_entry_open, qqq_rows[qqq_end_idx].get("close"))
        horizons[f"{horizon}d"] = {
            "status": "valid" if ret is not None and spy_ret is not None else "missing_price",
            "return": _round(ret),
            "spy_return": _round(spy_ret),
            "excess_return": _round(ret - spy_ret if ret is not None and spy_ret is not None else None),
            "qqq_return": _round(qqq_ret),
            "excess_vs_qqq": _round(ret - qqq_ret if ret is not None and qqq_ret is not None else None),
            "end_date": rows[end_idx]["date"],
        }
    out["horizons"] = horizons
    return out


def _distribution(values: list[float]) -> dict[str, Any]:
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
        for metric in ("return", "excess_return", "excess_vs_qqq"):
            values = []
            for row in rows:
                data = (row.get("horizons") or {}).get(key) or {}
                value = data.get(metric)
                if isinstance(value, (int, float)) and math.isfinite(value):
                    values.append(float(value))
            out[key][metric] = _distribution(values)
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


def _compact_event(row: dict[str, Any]) -> dict[str, Any]:
    horizons = row.get("horizons") or {}
    return {
        "ticker": row.get("ticker"),
        "window": row.get("window"),
        "usable_trade_date": row.get("usable_trade_date"),
        "entry_date": row.get("entry_date"),
        "accession_number": row.get("accession_number"),
        "text_event_type": row.get("text_event_type"),
        "language_bucket": row.get("language_bucket"),
        "language_score": row.get("language_score"),
        "matched_phrases": row.get("matched_phrases"),
        "reaction_excess_return": row.get("reaction_excess_return"),
        "horizons": {
            horizon: horizons.get(horizon)
            for horizon in ("5d", "10d", "20d")
            if horizon in horizons
        },
        "audit_snippets": row.get("audit_snippets"),
    }


def _load_baseline_metrics() -> dict[str, Any]:
    payload = _load_json(BASELINE_LOG, {})
    if isinstance(payload, dict):
        if isinstance(payload.get("baseline_metrics"), dict):
            return payload["baseline_metrics"]
        if isinstance(payload.get("before_metrics"), dict):
            return payload["before_metrics"]
    return {}


def build_payload() -> dict[str, Any]:
    text_summary = _load_json(TEXT_SUMMARY_PATH, {})
    text_rows = _load_jsonl(TEXT_PATH)
    snapshots = {label: load_snapshot(path) for label, path in SNAPSHOT_FILES.items()}

    evaluated: list[dict[str, Any]] = []
    for row in text_rows:
        usable = str(row.get("usable_trade_date") or "")
        window = window_for_date(usable)
        if not window:
            continue
        features = language_features(row)
        event = {
            **{key: row.get(key) for key in (
                "ticker",
                "cik",
                "accession_number",
                "form_type",
                "form_base",
                "filing_date",
                "usable_trade_date",
                "accepted_at",
                "eight_k_item_codes",
                "primary_document",
                "documents_fetched",
                "text_char_count",
                "text_word_count",
            )},
            **features,
        }
        evaluated.append(evaluate_price(event, snapshots[window], window))

    covered = [row for row in evaluated if row.get("price_status") == "covered"]
    positive_language = [row for row in covered if row.get("language_bucket") == "positive_language"]
    negative_language = [row for row in covered if row.get("language_bucket") == "negative_language"]
    earnings_positive = [
        row for row in positive_language
        if row.get("text_event_type") == "earnings_release_text"
    ]
    deferred_or_operational = [
        row for row in covered
        if row.get("language_bucket") == "deferred_or_operational"
        or row.get("text_event_type") in {"deferred_results_or_operational_update", "operational_update"}
    ]

    primary_10d = [
        ((row.get("horizons") or {}).get("10d") or {}).get("excess_return")
        for row in earnings_positive
    ]
    primary_10d = [float(value) for value in primary_10d if isinstance(value, (int, float)) and math.isfinite(value)]
    primary_avg = mean(primary_10d) if primary_10d else None
    primary_win = sum(1 for value in primary_10d if value > 0) / len(primary_10d) if primary_10d else None
    primary_by_window = summarize_group(earnings_positive, "window")
    positive_window_count = 0
    for data in primary_by_window.values():
        d10 = (((data.get("forward_distribution") or {}).get("10d") or {}).get("excess_return") or {})
        if isinstance(d10.get("avg"), (int, float)) and d10["avg"] > 0:
            positive_window_count += 1

    if len(primary_10d) >= MIN_VALID_10D and primary_avg is not None and primary_avg > 0.02 and primary_win and primary_win >= 0.55 and positive_window_count >= 2:
        decision = "observed_promising_not_promoted"
        status = "observed_promising_not_promoted"
        decision_rationale = (
            "The fixed filing-text language proxy is promising enough for a proper LLM grading retry, "
            "but it is not promoted because it is a keyword proxy and no shared production/backtest policy changed."
        )
        next_action = (
            "Freeze this text packet schema and run an LLM filing-text grading replay on the same events, "
            "then test whether LLM grades beat the keyword proxy and raw price reaction."
        )
    else:
        decision = "observed_only_not_promoted"
        status = "observed_only_not_promoted"
        decision_rationale = (
            "The fixed filing-text language proxy did not clear a promotion-quality bar. "
            "Use the text layer as structured LLM input, not as a standalone keyword strategy."
        )
        next_action = (
            "Do not tune nearby keyword lists. A valid retry should use LLM filing-text grading on the frozen packets "
            "or join analyst revisions to these same SEC results events."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "SEC results 8-K filing text may identify true earnings-release catalysts, deferred operational updates, "
            "guidance changes, and demand/margin language that improve C-strategy event grading beyond raw Item 2.02, "
            "Companyfacts checklists, or first price reaction."
        ),
        "alpha_hypothesis": {
            "category": "event_grading / entry_candidate_ranking",
            "text": "Filing-text language in results 8-Ks can rank earnings/event shocks better than raw SEC form context.",
            "why_this_is_not_repeat": (
                "Prior runs tested price reaction and Companyfacts point scoring. This run adds the actual SEC filing/exhibit text."
            ),
        },
        "change_type": "non_ohlcv_shadow_alpha",
        "single_causal_variable": "SEC Item 2.02 filing-text language features",
        "component": (
            "quant/sec_filing_text_backfill.py; "
            "quant/experiments/exp_20260504_005_sec_filing_text_language_shadow.py"
        ),
        "historical_experiment_check": {
            "prior_same_family": {
                "exp-20260504-002": "results 8-K + positive first reaction failed.",
                "exp-20260504-004": "Companyfacts financial-quality checklist was not monotonic.",
            },
            "mechanism_insight_check": (
                "docs/alpha-optimization-playbook.md says valid retry needs LLM filing-text grading, analyst revisions, "
                "or cleaner earnings-release XBRL; this run supplies and tests the filing-text layer."
            ),
            "mechanism_exclusion_check": [
                "No nearby price-reaction threshold sweep.",
                "No Companyfacts point-weight sweep.",
                "No production promotion from shadow evidence.",
            ],
        },
        "parameters": {
            "forms": ["8-K"],
            "item_codes": ["2.02"],
            "language_proxy_version": "fixed_keyword_proxy_v0",
            "entry_timing": "next trading-day open after SEC public-PIT usable trade date reaction close",
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
        "before_metrics": _load_baseline_metrics(),
        "after_metrics": _load_baseline_metrics(),
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
            "basis": "No promoted strategy change; fixed-window baseline metrics are unchanged by design.",
        },
        "coverage": {
            "text_backfill": text_summary,
            "evaluated_event_count": len(evaluated),
            "price_covered_count": len(covered),
            "price_coverage_rate": round(len(covered) / len(evaluated), 4) if evaluated else None,
            "positive_language_event_count": len(positive_language),
            "earnings_positive_event_count": len(earnings_positive),
            "earnings_positive_valid_10d_count": len(primary_10d),
            "earnings_positive_positive_10d_window_count": positive_window_count,
            "negative_language_event_count": len(negative_language),
            "deferred_or_operational_event_count": len(deferred_or_operational),
            "by_price_status": dict(Counter(row.get("price_status") for row in evaluated)),
            "by_window": dict(Counter(row.get("window") for row in covered)),
            "by_text_event_type": dict(Counter(row.get("text_event_type") for row in covered)),
            "by_language_bucket": dict(Counter(row.get("language_bucket") for row in covered)),
        },
        "shadow_metrics": {
            "all_text_events": {
                "forward_distribution": summarize_forward(covered),
                "by_window": summarize_group(covered, "window"),
                "by_text_event_type": summarize_group(covered, "text_event_type"),
                "by_language_bucket": summarize_group(covered, "language_bucket"),
            },
            "earnings_positive_language": {
                "event_count": len(earnings_positive),
                "forward_distribution": summarize_forward(earnings_positive),
                "by_window": primary_by_window,
                "sample_events": [_compact_event(row) for row in earnings_positive[:60]],
            },
            "negative_language": {
                "event_count": len(negative_language),
                "forward_distribution": summarize_forward(negative_language),
                "by_window": summarize_group(negative_language, "window"),
            },
            "deferred_or_operational": {
                "event_count": len(deferred_or_operational),
                "forward_distribution": summarize_forward(deferred_or_operational),
                "by_window": summarize_group(deferred_or_operational, "window"),
            },
            "top_10d_excess": [
                _compact_event(row)
                for row in sorted(
                    [
                        row for row in covered
                        if isinstance(((row.get("horizons") or {}).get("10d") or {}).get("excess_return"), (int, float))
                    ],
                    key=lambda item: ((item.get("horizons") or {}).get("10d") or {}).get("excess_return"),
                    reverse=True,
                )[:25]
            ],
            "bottom_10d_excess": [
                _compact_event(row)
                for row in sorted(
                    [
                        row for row in covered
                        if isinstance(((row.get("horizons") or {}).get("10d") or {}).get("excess_return"), (int, float))
                    ],
                    key=lambda item: ((item.get("horizons") or {}).get("10d") or {}).get("excess_return"),
                )[:25]
            ],
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "filing_text_feature_packet_pre_llm",
            "llm_attribution_metric": "forward returns by frozen text-language packet bucket",
            "llm_ready_packet_count": len(covered),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if decision != "observed_only_not_promoted" else decision_rationale,
        "next_retry_requires": [
            "Do not tune nearby keyword phrases without new information.",
            "Run LLM filing-text grading on the same frozen packet schema, or join analyst revisions.",
            "Any production use must be implemented in a shared production/backtest feature module.",
        ],
        "next_action": next_action,
        "related_files": [
            "data/non_ohlcv/sec_filing_text_20241002_20260421.jsonl",
            "data/non_ohlcv/sec_filing_text_backfill_summary_20241002_20260421.json",
            "quant/sec_filing_text_backfill.py",
            "quant/experiments/exp_20260504_005_sec_filing_text_language_shadow.py",
            "data/experiments/exp-20260504-005/sec_filing_text_language_shadow.json",
            "docs/experiments/logs/exp-20260504-005.json",
            "docs/non_ohlcv_data_audit/sec_filing_text_language_shadow_20260504.md",
        ],
    }
    return _safe_payload(payload)


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _cohort_row(label: str, data: dict[str, Any]) -> str:
    forward = data.get("forward_distribution") or {}
    d10 = ((forward.get("10d") or {}).get("excess_return") or {})
    d20 = ((forward.get("20d") or {}).get("excess_return") or {})
    return (
        f"| {label} | {data.get('event_count')} | "
        f"{_format_pct(d10.get('avg'))} | {_format_pct(d10.get('win_rate'))} | "
        f"{_format_pct(d20.get('avg'))} | {_format_pct(d20.get('win_rate'))} |"
    )


def _table(title: str, rows: dict[str, Any]) -> list[str]:
    lines = [f"## {title}", "", "| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |", "|---|---:|---:|---:|---:|---:|"]
    for key, data in rows.items():
        lines.append(_cohort_row(key, data))
    lines.append("")
    return lines


def build_report(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    primary = payload["shadow_metrics"]["earnings_positive_language"]
    lines = [
        "# SEC filing-text language shadow replay",
        "",
        f"- Experiment: `{EXPERIMENT_ID}`",
        f"- Status: `{payload['status']}`",
        "- Production impact: shadow-only; no strategy logic changed.",
        "",
        "## Headline",
        "",
        payload["decision_rationale"],
        "",
        "## Coverage",
        "",
        f"- Text rows: `{(coverage['text_backfill'] or {}).get('rows_written')}`",
        f"- Text status counts: `{(coverage['text_backfill'] or {}).get('status_counts')}`",
        f"- Evaluated events: `{coverage['evaluated_event_count']}`",
        f"- Price-covered events: `{coverage['price_covered_count']}`",
        f"- Earnings positive-language events: `{coverage['earnings_positive_event_count']}`",
        f"- Earnings positive valid 10d outcomes: `{coverage['earnings_positive_valid_10d_count']}`",
        "",
        "## Primary Cohort",
        "",
        "| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |",
        "|---|---:|---:|---:|---:|---:|",
        _cohort_row("earnings_positive_language", primary),
        "",
    ]
    lines.extend(_table("By Language Bucket", payload["shadow_metrics"]["all_text_events"]["by_language_bucket"]))
    lines.extend(_table("By Text Event Type", payload["shadow_metrics"]["all_text_events"]["by_text_event_type"]))
    lines.extend(_table("By Window", payload["shadow_metrics"]["all_text_events"]["by_window"]))
    lines.extend([
        "## Gate / Caveat",
        "",
        "- Gate 4 is intentionally not passed because this is not a promoted strategy change.",
        "- SEC archive text is public-PIT keyed by accepted_at/usable_trade_date, but the fetch happened after the fact.",
        "- This is a fixed keyword proxy, not an LLM grade; use it as a baseline and packet schema.",
        "",
        "## Next Action",
        "",
        payload["next_action"],
        "",
    ])
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "SEC filing text language shadow",
        "summary": payload["decision_rationale"],
        "best_variant": "earnings_positive_language",
        "best_variant_gate4": False,
        "delta_metrics": {
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "coverage": payload["coverage"],
            "earnings_positive_language": payload["shadow_metrics"]["earnings_positive_language"]["forward_distribution"],
        },
        "production_impact": payload["production_impact"],
        "next_action": payload["next_action"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_text(REPORT_MD, build_report(payload))

    compact = dict(payload)
    compact.pop("shadow_metrics", None)
    compact["shadow_metrics_summary"] = {
        "earnings_positive_language": payload["shadow_metrics"]["earnings_positive_language"],
        "negative_language": payload["shadow_metrics"]["negative_language"],
        "deferred_or_operational": payload["shadow_metrics"]["deferred_or_operational"],
        "by_language_bucket": payload["shadow_metrics"]["all_text_events"]["by_language_bucket"],
    }
    existing_lines = (
        EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if EXPERIMENT_LOG.exists()
        else []
    )
    kept_lines = [
        line for line in existing_lines
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
        and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
    ]
    kept_lines.append(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "coverage": payload["coverage"],
        "earnings_positive_10d_excess": (
            payload["shadow_metrics"]["earnings_positive_language"]["forward_distribution"]["10d"]["excess_return"]
        ),
        "by_language_bucket": payload["shadow_metrics"]["all_text_events"]["by_language_bucket"],
        "by_text_event_type": payload["shadow_metrics"]["all_text_events"]["by_text_event_type"],
    }, indent=2, ensure_ascii=False))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
