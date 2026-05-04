"""exp-20260503-051 SEC filing reaction drift shadow replay.

This is an alpha-search experiment, not a production strategy change. It tests
whether the first EOD price reaction after a PIT-safe SEC filing identifies
post-reaction drift. No entry, sizing, exit, ranking, or universe policy is
changed by this script.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260503-051"
SEC_EVENTS_PATH = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_filing_reaction_drift.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

HORIZONS = (5, 10, 20)
POSITIVE_REACTION_EXCESS_MIN = 0.02
NEGATIVE_REACTION_EXCESS_MAX = -0.02
MIN_PROMISING_VALID_10D = 20


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    raw = payload.get("ohlcv") or payload
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in raw.items():
        converted = []
        for row in rows or []:
            date = str(row.get("Date") or row.get("date") or "")[:10]
            if not date:
                continue
            converted.append({
                "date": date,
                "open": _as_float(row.get("Open") if "Open" in row else row.get("open")),
                "close": _as_float(row.get("Close") if "Close" in row else row.get("close")),
                "volume": _as_float(row.get("Volume") if "Volume" in row else row.get("volume")),
            })
        if converted:
            out[str(ticker).upper()] = sorted(converted, key=lambda item: item["date"])
    return out


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
        if math.isfinite(result):
            return result
    return None


def _idx_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


def _idx_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] > date_value:
            return idx
    return None


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    values = []
    for row in rows[max(0, idx - lookback):idx]:
        close = row.get("close")
        volume = row.get("volume")
        if isinstance(close, (int, float)) and isinstance(volume, (int, float)):
            values.append(close * volume)
    return mean(values) if values else None


def _pct_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1.0


def _summary(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if isinstance(value, (int, float)) and math.isfinite(float(value))]
    if not clean:
        return {"count": 0, "avg": None, "median": None, "p25": None, "p75": None, "win_rate": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "p25": round(ordered[int((len(ordered) - 1) * 0.25)], 6),
        "p75": round(ordered[int((len(ordered) - 1) * 0.75)], 6),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "converged": (result.get("convergence") or {}).get("converged"),
    }


def filing_category(group: dict[str, Any]) -> str:
    forms = set(group["form_bases"])
    items = set(group["eight_k_item_codes"])
    if "8-K" in forms and "2.02" in items:
        return "8k_2_02_results"
    if forms & {"10-Q", "10-K"}:
        return "periodic_10q_10k"
    if items & {"1.01", "1.02", "2.03"}:
        return "agreement_or_debt"
    if "5.02" in items:
        return "leadership_change"
    if items & {"7.01", "8.01"}:
        return "fd_or_other_event"
    return "other_sec_filing"


def reaction_bucket(excess_return: float | None) -> str:
    if excess_return is None:
        return "reaction_unknown"
    if excess_return >= POSITIVE_REACTION_EXCESS_MIN:
        return "positive_excess_ge_2pct"
    if excess_return >= 0:
        return "positive_excess_0_to_2pct"
    if excess_return <= NEGATIVE_REACTION_EXCESS_MAX:
        return "negative_excess_le_minus_2pct"
    return "negative_excess_0_to_minus_2pct"


def load_event_groups(path: Path) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _load_jsonl(path):
        ticker = str(row.get("ticker") or "").upper()
        usable_trade_date = str(row.get("usable_trade_date") or "")[:10]
        if not ticker or not usable_trade_date:
            continue
        key = (ticker, usable_trade_date)
        group = grouped.setdefault(key, {
            "ticker": ticker,
            "usable_trade_date": usable_trade_date,
            "accepted_at_min": None,
            "filing_dates": set(),
            "form_types": set(),
            "form_bases": set(),
            "eight_k_item_codes": set(),
            "accession_numbers": set(),
            "pit_safe_count": 0,
            "filing_count": 0,
            "max_size": None,
            "sample_archive_urls": [],
        })
        group["filing_count"] += 1
        if row.get("pit_safe_flag"):
            group["pit_safe_count"] += 1
        accepted_at = row.get("accepted_at")
        if accepted_at and (group["accepted_at_min"] is None or str(accepted_at) < group["accepted_at_min"]):
            group["accepted_at_min"] = str(accepted_at)
        for field, target in [
            ("filing_date", "filing_dates"),
            ("form_type", "form_types"),
            ("form_base", "form_bases"),
            ("accession_number", "accession_numbers"),
        ]:
            value = row.get(field)
            if value:
                group[target].add(str(value))
        for code in row.get("eight_k_item_codes") or []:
            group["eight_k_item_codes"].add(str(code))
        size = _as_float(row.get("size"))
        if size is not None:
            group["max_size"] = max(group["max_size"] or 0, size)
        if row.get("archive_url") and len(group["sample_archive_urls"]) < 3:
            group["sample_archive_urls"].append(row["archive_url"])

    events = []
    for group in grouped.values():
        normalized = dict(group)
        for key in ("filing_dates", "form_types", "form_bases", "eight_k_item_codes", "accession_numbers"):
            normalized[key] = sorted(group[key])
        normalized["filing_category"] = filing_category(normalized)
        events.append(normalized)
    return sorted(events, key=lambda item: (item["usable_trade_date"], item["ticker"]))


def evaluate_group(
    group: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
    window_label: str,
) -> dict[str, Any]:
    row = dict(group)
    row["window"] = window_label
    ticker_rows = snapshot.get(group["ticker"])
    if not ticker_rows:
        row["price_status"] = "no_ticker_price"
        return row
    reaction_idx = _idx_on_or_after(ticker_rows, group["usable_trade_date"])
    spy_reaction_idx = _idx_on_or_after(spy_rows, group["usable_trade_date"])
    if reaction_idx is None or spy_reaction_idx is None:
        row["price_status"] = "no_reaction_day"
        return row
    if reaction_idx == 0 or spy_reaction_idx == 0:
        row["price_status"] = "no_previous_close"
        return row
    entry_idx = _idx_after(ticker_rows, ticker_rows[reaction_idx]["date"])
    spy_entry_idx = _idx_after(spy_rows, spy_rows[spy_reaction_idx]["date"])
    if entry_idx is None or spy_entry_idx is None:
        row["price_status"] = "no_entry_day"
        return row

    reaction_ret = _pct_change(ticker_rows[reaction_idx - 1]["close"], ticker_rows[reaction_idx]["close"])
    spy_reaction_ret = _pct_change(spy_rows[spy_reaction_idx - 1]["close"], spy_rows[spy_reaction_idx]["close"])
    reaction_excess = reaction_ret - spy_reaction_ret if reaction_ret is not None and spy_reaction_ret is not None else None

    row["price_status"] = "covered"
    row["reaction_date"] = ticker_rows[reaction_idx]["date"]
    row["entry_date"] = ticker_rows[entry_idx]["date"]
    row["reaction_return"] = round(reaction_ret, 6) if reaction_ret is not None else None
    row["spy_reaction_return"] = round(spy_reaction_ret, 6) if spy_reaction_ret is not None else None
    row["reaction_excess_return"] = round(reaction_excess, 6) if reaction_excess is not None else None
    row["reaction_bucket"] = reaction_bucket(reaction_excess)
    avg_dv = _avg_dollar_volume(ticker_rows, reaction_idx)
    row["avg_dollar_volume_20d"] = round(avg_dv, 2) if avg_dv is not None else None
    row["horizons"] = {}

    entry_open = ticker_rows[entry_idx]["open"]
    spy_entry_open = spy_rows[spy_entry_idx]["open"]
    for horizon in HORIZONS:
        end_idx = entry_idx + horizon
        spy_end_idx = spy_entry_idx + horizon
        key = f"{horizon}d"
        if end_idx >= len(ticker_rows) or spy_end_idx >= len(spy_rows):
            row["horizons"][key] = {"status": "pending"}
            continue
        ticker_ret = _pct_change(entry_open, ticker_rows[end_idx]["close"])
        spy_ret = _pct_change(spy_entry_open, spy_rows[spy_end_idx]["close"])
        if ticker_ret is None or spy_ret is None:
            row["horizons"][key] = {"status": "bad_price"}
            continue
        row["horizons"][key] = {
            "status": "valid",
            "return": round(ticker_ret, 6),
            "spy_return": round(spy_ret, 6),
            "excess_return": round(ticker_ret - spy_ret, 6),
            "end_date": ticker_rows[end_idx]["date"],
        }
    return row


def _valid_values(rows: list[dict[str, Any]], horizon_key: str, field: str = "excess_return") -> list[float]:
    values = []
    for row in rows:
        data = (row.get("horizons") or {}).get(horizon_key) or {}
        value = data.get(field)
        if data.get("status") == "valid" and isinstance(value, (int, float)):
            values.append(float(value))
    return values


def summarize_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"{horizon}d": {
            "return": _summary(_valid_values(rows, f"{horizon}d", "return")),
            "excess_return": _summary(_valid_values(rows, f"{horizon}d", "excess_return")),
        }
        for horizon in HORIZONS
    }


def summarize_group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return {
        group_key: {
            "event_count": len(group_rows),
            "forward_distribution": summarize_forward(group_rows),
        }
        for group_key, group_rows in sorted(grouped.items())
    }


def _horizon_excess(
    ticker: str,
    entry_date: str,
    snapshot: dict[str, list[dict[str, Any]]],
    horizon: int = 10,
) -> float | None:
    rows = snapshot.get(ticker)
    spy_rows = snapshot.get("SPY")
    if not rows or not spy_rows:
        return None
    entry_idx = _idx_on_or_after(rows, entry_date)
    spy_entry_idx = _idx_on_or_after(spy_rows, entry_date)
    if entry_idx is None or spy_entry_idx is None:
        return None
    end_idx = entry_idx + horizon
    spy_end_idx = spy_entry_idx + horizon
    if end_idx >= len(rows) or spy_end_idx >= len(spy_rows):
        return None
    ticker_ret = _pct_change(rows[entry_idx]["open"], rows[end_idx]["close"])
    spy_ret = _pct_change(spy_rows[spy_entry_idx]["open"], spy_rows[spy_end_idx]["close"])
    if ticker_ret is None or spy_ret is None:
        return None
    return ticker_ret - spy_ret


def attach_slot_conflicts(
    rows: list[dict[str, Any]],
    baseline_trades: dict[str, list[dict[str, Any]]],
    snapshots: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    core_by_window_day: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for label, trades in baseline_trades.items():
        snapshot = snapshots[label]
        for trade in trades:
            entry_date = str(trade.get("entry_date") or "")[:10]
            ticker = str(trade.get("ticker") or "").upper()
            if not entry_date or not ticker:
                continue
            core_by_window_day[(label, entry_date)].append({
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "pnl": trade.get("pnl"),
                "pnl_pct_net": trade.get("pnl_pct_net"),
                "core_10d_excess_return": _horizon_excess(ticker, entry_date, snapshot, horizon=10),
            })

    enriched = []
    replacements = []
    conflict_count = 0
    valid_conflict_count = 0
    positive_replacement_count = 0
    for row in rows:
        candidate = dict(row)
        same_day = core_by_window_day.get((row["window"], row.get("entry_date")), [])
        candidate["same_day_core_trade_count"] = len(same_day)
        candidate["same_day_core_trades"] = same_day[:5]
        candidate["slot_conflict_proxy"] = bool(same_day)
        if same_day:
            conflict_count += 1
        core_values = [
            float(item["core_10d_excess_return"])
            for item in same_day
            if isinstance(item.get("core_10d_excess_return"), (int, float))
        ]
        candidate_10d = ((candidate.get("horizons") or {}).get("10d") or {}).get("excess_return")
        if core_values and isinstance(candidate_10d, (int, float)):
            core_avg = mean(core_values)
            replacement = float(candidate_10d) - core_avg
            candidate["same_day_core_avg_10d_excess_return"] = round(core_avg, 6)
            candidate["replacement_value_10d_excess_proxy"] = round(replacement, 6)
            replacements.append(replacement)
            valid_conflict_count += 1
            if replacement > 0:
                positive_replacement_count += 1
        else:
            candidate["same_day_core_avg_10d_excess_return"] = None
            candidate["replacement_value_10d_excess_proxy"] = None
        enriched.append(candidate)

    return enriched, {
        "same_day_core_conflict_count": conflict_count,
        "same_day_core_conflict_rate": round(conflict_count / len(rows), 4) if rows else None,
        "valid_replacement_proxy_count": valid_conflict_count,
        "positive_replacement_proxy_count": positive_replacement_count,
        "positive_replacement_proxy_rate": (
            round(positive_replacement_count / valid_conflict_count, 4)
            if valid_conflict_count else None
        ),
        "replacement_value_10d_excess_proxy": _summary([float(value) for value in replacements]),
    }


def run_baseline_windows(universe: list[str]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    baseline_metrics = {}
    baseline_trades = {}
    for label, cfg in WINDOWS.items():
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        ).run()
        if "error" in result:
            raise RuntimeError(f"baseline {label} failed: {result['error']}")
        baseline_metrics[label] = _metrics(result)
        baseline_trades[label] = result.get("trades", [])
    return baseline_metrics, baseline_trades


def _compact_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "window": row.get("window"),
        "usable_trade_date": row.get("usable_trade_date"),
        "reaction_date": row.get("reaction_date"),
        "entry_date": row.get("entry_date"),
        "filing_category": row.get("filing_category"),
        "form_bases": row.get("form_bases"),
        "eight_k_item_codes": row.get("eight_k_item_codes"),
        "filing_count": row.get("filing_count"),
        "reaction_excess_return": row.get("reaction_excess_return"),
        "reaction_bucket": row.get("reaction_bucket"),
        "avg_dollar_volume_20d": row.get("avg_dollar_volume_20d"),
        "horizons": row.get("horizons"),
        "slot_conflict_proxy": row.get("slot_conflict_proxy"),
        "same_day_core_trade_count": row.get("same_day_core_trade_count"),
        "replacement_value_10d_excess_proxy": row.get("replacement_value_10d_excess_proxy"),
    }


def _positive_reaction_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("reaction_bucket") == "positive_excess_ge_2pct"]


def _positive_window_count(rows: list[dict[str, Any]]) -> int:
    count = 0
    for label in WINDOWS:
        values = _valid_values([row for row in rows if row.get("window") == label], "10d")
        if values and mean(values) > 0:
            count += 1
    return count


def _safe_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _safe_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe_payload(value) for value in payload]
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    return payload


def build_payload() -> dict[str, Any]:
    universe = sorted(get_universe())
    event_groups = load_event_groups(SEC_EVENTS_PATH)
    snapshots = {
        label: _load_snapshot(REPO_ROOT / cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }
    baseline_metrics, baseline_trades = run_baseline_windows(universe)

    evaluated: list[dict[str, Any]] = []
    for label, cfg in WINDOWS.items():
        snapshot = snapshots[label]
        spy_rows = snapshot.get("SPY") or []
        for event in event_groups:
            usable_date = event["usable_trade_date"]
            if cfg["start"] <= usable_date <= cfg["end"]:
                evaluated.append(evaluate_group(event, snapshot, spy_rows, label))

    covered = [row for row in evaluated if row.get("price_status") == "covered"]
    covered, slot_summary = attach_slot_conflicts(covered, baseline_trades, snapshots)
    positive_rows = _positive_reaction_rows(covered)
    positive_valid_10d = _valid_values(positive_rows, "10d")
    positive_windows = _positive_window_count(positive_rows)

    if len(positive_valid_10d) >= MIN_PROMISING_VALID_10D and positive_windows >= 2 and mean(positive_valid_10d) > 0:
        status = "shadow_promising_not_promoted"
        decision = "shadow_promising_not_promoted"
        decision_rationale = (
            "The positive SEC filing reaction cohort has enough valid 10d samples and positive "
            "average 10d excess return in at least two windows, but it remains shadow-only because "
            "no shared production/backtest policy consumes SEC filing reaction features yet."
        )
        next_action = (
            "Build a default-off shared SEC event-reaction feature and production reporting path, "
            "then retest only as an existing-candidate ranking/confirmation overlay."
        )
    else:
        status = "rejected"
        decision = "rejected"
        decision_rationale = (
            "The fixed +2% SEC filing reaction discriminator did not show enough stable "
            "multi-window post-reaction drift to justify a production ranking or entry change."
        )
        next_action = (
            "Do not retry nearby raw SEC reaction thresholds. A valid retry needs richer filing "
            "semantics such as 8-K item text, XBRL surprise fields, or forward production SEC archives."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "sec_filing_event_reaction_alpha",
        "change_type": "shadow_reaction_drift_replay",
        "hypothesis": (
            "PIT-safe SEC filing event-days with a first EOD excess reaction of at least +2% "
            "may identify post-reaction drift that can later confirm or rank existing A/B candidates."
        ),
        "alpha_hypothesis_category": "entry_ranking_event_confirmation",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin; this uses the new SEC public "
            "PIT filing backbone and local OHLCV snapshots instead."
        ),
        "history_check": {
            "mechanism_insight_guardrail": (
                "This is not a broad static universe scout, not a low-liquidity filing promotion, "
                "and not a nearby SPY-leader threshold. It follows exp-20260503-050's next action "
                "by joining SEC filing events to price reaction."
            ),
            "similar_experiments": {
                "exp-20260503-002": "Round-1 earnings/SEC schema was coverage-blocked before the SEC filing backfill existed.",
                "exp-20260503-006": "Broad SEC filing universe scout found broad filings weak but 10-K/high-ADV pockets interesting.",
                "exp-20260503-011": "Liquidity-gated 10-K scout was shadow-only and blocked from production universe promotion.",
                "exp-20260503-047": "SPY-relative leader reaction/quality gates were rejected; this test is SEC-event scoped.",
            },
            "why_not_simple_repeat": (
                "The new input is the accession-level SEC filing backfill with usable_trade_date, "
                "and the tested discriminator is post-filing EOD reaction rather than form type alone."
            ),
        },
        "parameters": {
            "single_causal_variable": "SEC filing first EOD excess reaction >= +2%",
            "event_unit": "ticker + usable_trade_date, with same-day filings grouped",
            "entry_timing": "next trading-day open after the reaction close, to avoid using same-day close before it exists",
            "reaction_excess_threshold": POSITIVE_REACTION_EXCESS_MIN,
            "negative_reaction_threshold": NEGATIVE_REACTION_EXCESS_MAX,
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
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
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
            "sec_event_group_count": len(event_groups),
            "evaluated_window_event_count": len(evaluated),
            "price_covered_count": len(covered),
            "price_coverage_rate": round(len(covered) / len(evaluated), 4) if evaluated else None,
            "positive_reaction_event_count": len(positive_rows),
            "positive_reaction_valid_10d_count": len(positive_valid_10d),
            "positive_reaction_windows_with_positive_10d_avg": positive_windows,
            "by_price_status": dict(Counter(row.get("price_status") for row in evaluated)),
        },
        "shadow_metrics": {
            "all_sec_events": {
                "forward_distribution": summarize_forward(covered),
                "by_window": summarize_group(covered, "window"),
                "by_filing_category": summarize_group(covered, "filing_category"),
                "by_reaction_bucket": summarize_group(covered, "reaction_bucket"),
            },
            "positive_reaction_ge_2pct": {
                "event_count": len(positive_rows),
                "forward_distribution": summarize_forward(positive_rows),
                "by_window": summarize_group(positive_rows, "window"),
                "by_filing_category": summarize_group(positive_rows, "filing_category"),
            },
            "slot_conflict": slot_summary,
            "sample_events": [_compact_event(row) for row in covered[:80]],
            "top_positive_10d_excess": [
                _compact_event(row)
                for row in sorted(
                    [
                        row for row in covered
                        if isinstance(((row.get("horizons") or {}).get("10d") or {}).get("excess_return"), (int, float))
                    ],
                    key=lambda item: ((item.get("horizons") or {}).get("10d") or {}).get("excess_return"),
                    reverse=True,
                )[:20]
            ],
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if decision != "rejected" else decision_rationale,
        "next_retry_requires": [
            "Do not retry nearby raw reaction thresholds without richer filing semantics.",
            "If promoted later, implement SEC filing-reaction features in a shared production/backtest module.",
            "Use forward production SEC archives to verify the backfilled public-PIT proxy.",
        ],
        "next_action": next_action,
        "related_files": [
            "data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl",
            "quant/experiments/exp_20260503_051_sec_filing_reaction_drift.py",
            "data/experiments/exp-20260503-051/sec_filing_reaction_drift.json",
            "docs/experiments/logs/exp-20260503-051.json",
            "docs/experiments/tickets/exp-20260503-051.json",
        ],
    }
    return _safe_payload(payload)


def persist(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "SEC filing reaction drift",
        "summary": payload["decision_rationale"],
        "best_variant": "positive_excess_ge_2pct",
        "best_variant_gate4": False,
        "delta_metrics": {
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "positive_reaction_ge_2pct": payload["shadow_metrics"]["positive_reaction_ge_2pct"]["forward_distribution"],
            "coverage": payload["coverage"],
        },
        "production_impact": payload["production_impact"],
        "next_action": payload["next_action"],
    }
    _write_json(TICKET_JSON, ticket)

    compact = dict(payload)
    compact.pop("shadow_metrics", None)
    compact["shadow_metrics_summary"] = {
        "positive_reaction_ge_2pct": payload["shadow_metrics"]["positive_reaction_ge_2pct"],
        "slot_conflict": payload["shadow_metrics"]["slot_conflict"],
    }
    existing_lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines() if EXPERIMENT_LOG.exists() else []
    kept_lines = [
        line for line in existing_lines
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
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
        "positive_reaction_10d_excess": payload["shadow_metrics"]["positive_reaction_ge_2pct"]["forward_distribution"]["10d"]["excess_return"],
        "positive_reaction_by_window": payload["shadow_metrics"]["positive_reaction_ge_2pct"]["by_window"],
        "slot_conflict": payload["shadow_metrics"]["slot_conflict"],
    }, indent=2, ensure_ascii=False))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
