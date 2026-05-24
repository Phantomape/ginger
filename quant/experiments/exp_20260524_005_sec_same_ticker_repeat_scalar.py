"""exp-20260524-005: SEC same-ticker repeat notional scalar.

Alpha search on one production-visible state field in the default-off SEC
financial-report paper sleeve.  The accepted SEC stack has a concentration
blocker, so this experiment tests whether repeated same-ticker SEC paper
entries within a fixed 60-calendar-day lookback deserve a notional scalar.

Core entries, exits, queue eligibility, hold days, live orders, LLM authority,
and candidate ranking are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import date, datetime, timezone
import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260524-005"
STEM = "exp_20260524_005_sec_same_ticker_repeat_scalar"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import sec_financial_report_event_sleeve as sleeve  # noqa: E402
import exp_20260519_008_sec_earnings_release_spy_context_notional as base  # noqa: E402


parent = base.prev.parent
BASE_NOTIONAL_FOR_POSITION = base._notional_for_position

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_same_ticker_repeat_scalar.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR = 1.10
REPEAT_LOOKBACK_DAYS = 60
BASELINE_REPEAT_SCALAR = 1.0
TARGET_SCALAR_VARIANTS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("repeat_scalar_0_00", 0.00),
        ("repeat_scalar_0_25", 0.25),
        ("repeat_scalar_0_50", 0.50),
        ("repeat_scalar_0_75", 0.75),
        ("repeat_scalar_1_00", 1.00),
        ("repeat_scalar_1_10", 1.10),
        ("repeat_scalar_1_25", 1.25),
        ("repeat_scalar_1_50", 1.50),
        ("repeat_scalar_2_00", 2.00),
    ]
)
SCALAR_FIELD = "sec_same_ticker_repeat_60d_notional_scalar"
TRIAL_FAMILY = "sec_repeat_ticker_state_allocation"
MIN_ADJUSTED_TRADES = 6
MIN_ADJUSTED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_EV_REGRESSED_WINDOWS = 0
MIN_EV_IMPROVED_WINDOWS = 2
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
MAX_TOP5_CONTRIBUTION = 0.60
MAX_HHI_CONCENTRATION = 0.35
_ACTIVE_REPEAT_SCALAR = BASELINE_REPEAT_SCALAR


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    return base._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return base._round(value, ndigits)


def _float(value: Any) -> float | None:
    return base._float(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _parse_date(value: Any) -> date | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _source_candidate(position: dict[str, Any]) -> dict[str, Any]:
    return base._source_candidate(position)


def _ticker_from_item(item: dict[str, Any]) -> str:
    candidate = item.get("candidate") or item.get("source_candidate") or {}
    return str(item.get("ticker") or candidate.get("ticker") or "").upper()


def _item_reference_date(item: dict[str, Any]) -> date | None:
    candidate = item.get("candidate") or item.get("source_candidate") or {}
    for field in (
        "entry_date",
        "created_asof",
        "source_event_date",
        "usable_trade_date",
        "t1_date",
        "accepted_at",
    ):
        parsed = _parse_date(item.get(field)) or _parse_date(candidate.get(field))
        if parsed is not None:
            return parsed
    return None


def _same_ticker_repeat_metadata(
    state: dict[str, Any],
    candidate: dict[str, Any],
    as_of: str,
) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    ref = (
        _parse_date(as_of)
        or _parse_date(candidate.get("t1_date"))
        or _parse_date(candidate.get("usable_trade_date"))
    )
    best: dict[str, Any] | None = None
    for bucket in ("pending_entries", "open_positions", "closed_positions"):
        for item in state.get(bucket, []) or []:
            if _ticker_from_item(item) != ticker:
                continue
            prior = _item_reference_date(item)
            if prior is None or ref is None or prior > ref:
                continue
            age = (ref - prior).days
            if age <= REPEAT_LOOKBACK_DAYS and (
                best is None or age < int(best["prior_age_days"])
            ):
                best = {
                    "prior_bucket": bucket,
                    "prior_entry_date": prior.isoformat(),
                    "prior_age_days": age,
                }
    if best is None:
        return {
            "sec_same_ticker_repeat_state": "first_or_outside_lookback",
            "sec_same_ticker_repeat_lookback_days": REPEAT_LOOKBACK_DAYS,
            "sec_same_ticker_repeat_prior_entry_date": None,
            "sec_same_ticker_repeat_prior_age_days": None,
            "sec_same_ticker_repeat_prior_bucket": None,
        }
    return {
        "sec_same_ticker_repeat_state": "repeat_within_60d",
        "sec_same_ticker_repeat_lookback_days": REPEAT_LOOKBACK_DAYS,
        "sec_same_ticker_repeat_prior_entry_date": best["prior_entry_date"],
        "sec_same_ticker_repeat_prior_age_days": best["prior_age_days"],
        "sec_same_ticker_repeat_prior_bucket": best["prior_bucket"],
    }


def _patched_add_queue_candidates(
    state: dict[str, Any],
    queue: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    enriched = deepcopy(queue)
    candidates = []
    for candidate in enriched.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        row = deepcopy(candidate)
        row.update(_same_ticker_repeat_metadata(state, row, as_of))
        candidates.append(row)
    enriched["candidates"] = candidates
    return _ORIGINAL_ADD_QUEUE_CANDIDATES(
        state,
        enriched,
        as_of=as_of,
        config=config,
    )


_ORIGINAL_ADD_QUEUE_CANDIDATES = sleeve._add_queue_candidates


def _is_repeat_candidate(candidate: dict[str, Any]) -> bool:
    return str(candidate.get("sec_same_ticker_repeat_state") or "") == "repeat_within_60d"


def _is_repeat_position(position: dict[str, Any]) -> bool:
    return _is_repeat_candidate(_source_candidate(position))


def _notional_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float,
) -> tuple[float, float, str]:
    notional, scalar, rule = BASE_NOTIONAL_FOR_POSITION(
        position,
        target_scalar=target_scalar,
    )
    if not _is_repeat_position(position):
        return notional, scalar, rule
    scalar *= float(_ACTIVE_REPEAT_SCALAR)
    rule_parts = [part for part in str(rule).split("+") if part]
    rule_parts.append("same_ticker_repeat_60d_scalar")
    return (
        float(parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        "+".join(rule_parts),
    )


def _notional_for_repeat_scalar(
    position: dict[str, Any],
    *,
    repeat_scalar: float,
) -> tuple[float, float, str]:
    global _ACTIVE_REPEAT_SCALAR
    original_scalar = _ACTIVE_REPEAT_SCALAR
    _ACTIVE_REPEAT_SCALAR = float(repeat_scalar)
    try:
        return _notional_for_position(
            position,
            target_scalar=ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
        )
    finally:
        _ACTIVE_REPEAT_SCALAR = original_scalar


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    repeat_scalar: float,
) -> dict[str, Any]:
    global _ACTIVE_REPEAT_SCALAR
    original_scalar = _ACTIVE_REPEAT_SCALAR
    original_add = sleeve._add_queue_candidates
    original_notional = base._notional_for_position
    _ACTIVE_REPEAT_SCALAR = float(repeat_scalar)
    sleeve._add_queue_candidates = _patched_add_queue_candidates
    base._notional_for_position = _notional_for_position
    try:
        row = base._run_variant(
            core_results=core_results,
            exp100=exp100,
            target_scalar=ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
        )
    finally:
        sleeve._add_queue_candidates = original_add
        base._notional_for_position = original_notional
        _ACTIVE_REPEAT_SCALAR = original_scalar
    row[SCALAR_FIELD] = repeat_scalar
    return row


def _pnl_for_position(
    position: dict[str, Any],
    *,
    repeat_scalar: float,
    closed: bool,
) -> float:
    adjusted_notional, _, _ = _notional_for_repeat_scalar(
        position,
        repeat_scalar=repeat_scalar,
    )
    if closed:
        net_return = _float(position.get("net_return_pct")) or 0.0
        return adjusted_notional * (net_return / 100.0)
    source_notional = _float(position.get("notional"))
    source_pnl = _float(position.get("net_pnl_if_closed_now")) or 0.0
    if not source_notional or source_notional <= 0:
        return 0.0
    return adjusted_notional * (source_pnl / source_notional)


def _closed_repeat_positions_for_scalar(
    exp100: dict[str, Any],
    *,
    repeat_scalar: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    original_add = sleeve._add_queue_candidates
    sleeve._add_queue_candidates = _patched_add_queue_candidates
    try:
        for label, window in parent.WINDOWS.items():
            prices_by_date = parent._load_snapshot_prices(window["snapshot"])
            candidates_by_t1 = parent._rows_by_t1_date(exp100["windows"][label])
            state = parent.empty_sec_financial_report_event_sleeve_state()
            skipped_entries: list[dict[str, Any]] = []
            for as_of, prices in prices_by_date.items():
                candidates = candidates_by_t1.get(as_of, [])
                queue = {
                    "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
                    "rule_version": f"{EXPERIMENT_ID}-replay",
                    "enabled": False,
                    "asof_date": as_of,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                    "data_source": {"status": "replay", "window": label},
                }
                snapshot = parent.build_sec_financial_report_event_sleeve_snapshot(
                    sec_financial_report_t1_queue=queue,
                    as_of=as_of,
                    open_prices=prices["open"],
                    current_prices=prices["close"],
                    state=state,
                    config={
                        "max_positions": parent.DEFAULT_MAX_POSITIONS,
                        "event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
                        "periodic_report_notional_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
                        "tenq_periodic_report_notional_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
                        "neutral_underreaction_notional_enabled": False,
                    },
                    persist=False,
                )
                skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
                state = parent._rebuild_sleeve_state(snapshot, skipped_entries)

            for position in state.get("closed_positions") or []:
                if not _is_repeat_position(position):
                    continue
                candidate = _source_candidate(position)
                baseline_pnl = _pnl_for_position(
                    position,
                    repeat_scalar=BASELINE_REPEAT_SCALAR,
                    closed=True,
                )
                adjusted_pnl = _pnl_for_position(
                    position,
                    repeat_scalar=repeat_scalar,
                    closed=True,
                )
                notional, scalar, rule = _notional_for_repeat_scalar(
                    position,
                    repeat_scalar=repeat_scalar,
                )
                rows.append(
                    {
                        "window": label,
                        "ticker": position.get("ticker"),
                        "entry_date": position.get("entry_date"),
                        "exit_date": position.get("exit_date"),
                        "event_family": candidate.get("event_family"),
                        "form_base": candidate.get("form_base") or candidate.get("form_type"),
                        "language_bucket": candidate.get("language_bucket"),
                        "text_event_type": candidate.get("text_event_type"),
                        "t1_excess_return_vs_spy": candidate.get("t1_excess_return_vs_spy"),
                        "t1_return": candidate.get("t1_return"),
                        "spy_t1_return": candidate.get("spy_t1_return"),
                        "repeat_state": candidate.get("sec_same_ticker_repeat_state"),
                        "repeat_prior_entry_date": candidate.get(
                            "sec_same_ticker_repeat_prior_entry_date"
                        ),
                        "repeat_prior_age_days": candidate.get(
                            "sec_same_ticker_repeat_prior_age_days"
                        ),
                        "repeat_prior_bucket": candidate.get(
                            "sec_same_ticker_repeat_prior_bucket"
                        ),
                        "event_notional_rule": rule,
                        "event_notional_scalar": scalar,
                        "notional": _round(notional, 2),
                        "baseline_pnl": _round(baseline_pnl, 2),
                        "adjusted_pnl": _round(adjusted_pnl, 2),
                        "incremental_pnl": _round(adjusted_pnl - baseline_pnl, 2),
                    }
                )
    finally:
        sleeve._add_queue_candidates = original_add
    return rows


def _target_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    original_add = sleeve._add_queue_candidates
    sleeve._add_queue_candidates = _patched_add_queue_candidates
    aggregate = {"enqueued": 0, "repeat_candidates": 0}
    by_window: dict[str, Any] = {}
    try:
        for label, window in parent.WINDOWS.items():
            prices_by_date = parent._load_snapshot_prices(window["snapshot"])
            candidates_by_t1 = parent._rows_by_t1_date(exp100["windows"][label])
            state = parent.empty_sec_financial_report_event_sleeve_state()
            skipped_entries: list[dict[str, Any]] = []
            counts = Counter()
            repeat_tickers = Counter()
            for as_of, prices in prices_by_date.items():
                candidates = candidates_by_t1.get(as_of, [])
                queue = {
                    "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
                    "rule_version": f"{EXPERIMENT_ID}-coverage",
                    "enabled": False,
                    "asof_date": as_of,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                    "data_source": {"status": "replay", "window": label},
                }
                snapshot = parent.build_sec_financial_report_event_sleeve_snapshot(
                    sec_financial_report_t1_queue=queue,
                    as_of=as_of,
                    open_prices=prices["open"],
                    current_prices=prices["close"],
                    state=state,
                    config={
                        "max_positions": parent.DEFAULT_MAX_POSITIONS,
                        "event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
                        "periodic_report_notional_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
                        "tenq_periodic_report_notional_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
                        "neutral_underreaction_notional_enabled": False,
                    },
                    persist=False,
                )
                for entry in snapshot.get("new_pending_entries") or []:
                    candidate = entry.get("candidate") or {}
                    counts[str(candidate.get("sec_same_ticker_repeat_state"))] += 1
                    if _is_repeat_candidate(candidate):
                        repeat_tickers.update([str(entry.get("ticker") or "").upper()])
                skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
                state = parent._rebuild_sleeve_state(snapshot, skipped_entries)
            enqueued = sum(counts.values())
            repeats = counts.get("repeat_within_60d", 0)
            aggregate["enqueued"] += enqueued
            aggregate["repeat_candidates"] += repeats
            by_window[label] = {
                "enqueued": enqueued,
                "repeat_candidates": repeats,
                "state_counts": dict(sorted(counts.items())),
                "repeat_tickers": dict(sorted(repeat_tickers.items())),
            }
    finally:
        sleeve._add_queue_candidates = original_add
    aggregate["repeat_share"] = (
        aggregate["repeat_candidates"] / aggregate["enqueued"]
        if aggregate["enqueued"]
        else 0.0
    )
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "target_definition": {
            "field": "sec_same_ticker_repeat_state",
            "target": "repeat_within_60d",
            "lookback_days": REPEAT_LOOKBACK_DAYS,
            "prior_buckets": ["pending_entries", "open_positions", "closed_positions"],
        },
    }


def _window_deltas(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for label in parent.WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        checks[label] = {
            "expected_value_score": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "total_pnl": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "max_drawdown_pct": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "sharpe_daily": _round(
                float(after_m["sharpe_daily"]) - float(before_m["sharpe_daily"]),
                6,
            ),
        }
    return checks


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = parent._delta(row["aggregate"], baseline["aggregate"])
    by_window = _window_deltas(row, baseline)
    return {
        SCALAR_FIELD: row[SCALAR_FIELD],
        "aggregate_delta": aggregate_delta,
        "by_window": by_window,
        "ev_positive_windows": sum(
            1 for item in by_window.values() if (item["expected_value_score"] or 0.0) > 0
        ),
        "ev_regressed_windows": sum(
            1 for item in by_window.values() if (item["expected_value_score"] or 0.0) < 0
        ),
        "pnl_positive_windows": sum(
            1 for item in by_window.values() if (item["total_pnl"] or 0.0) > 0
        ),
        "pnl_regressed_windows": sum(
            1 for item in by_window.values() if (item["total_pnl"] or 0.0) < 0
        ),
        "max_drawdown_delta_max": max(
            float(item["max_drawdown_pct"] or 0.0) for item in by_window.values()
        ),
    }


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(str(row["window"]) for row in rows)
    by_ticker = Counter(str(row["ticker"]) for row in rows)
    pnl_by_window: dict[str, float] = {}
    pnl_by_ticker: dict[str, float] = {}
    positive_by_ticker: dict[str, float] = {}
    for row in rows:
        pnl = float(row.get("incremental_pnl") or 0.0)
        ticker = str(row["ticker"])
        window = str(row["window"])
        pnl_by_window[window] = pnl_by_window.get(window, 0.0) + pnl
        pnl_by_ticker[ticker] = pnl_by_ticker.get(ticker, 0.0) + pnl
        if pnl > 0:
            positive_by_ticker[ticker] = positive_by_ticker.get(ticker, 0.0) + pnl

    positive_values = sorted(positive_by_ticker.values(), reverse=True)
    positive_total = sum(positive_values)
    max_positive = positive_values[0] if positive_values else 0.0
    top5 = sum(positive_values[:5])
    hhi = (
        sum((value / positive_total) ** 2 for value in positive_values)
        if positive_total > 0
        else None
    )
    return {
        "adjusted_trade_count": len(rows),
        "windows_present": len(by_window),
        "by_window_count": dict(sorted(by_window.items())),
        "by_window_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_window.items())
        },
        "by_ticker_count": dict(sorted(by_ticker.items())),
        "by_ticker_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_ticker.items())
        },
        "positive_by_ticker_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(positive_by_ticker.items())
        },
        "positive_incremental_pnl": _round(positive_total, 2),
        "max_single_positive_incremental_pnl": _round(max_positive, 2),
        "max_single_positive_pnl_share": (
            _round(max_positive / positive_total, 4) if positive_total > 0 else None
        ),
        "pnl_top_5_contribution_pct": (
            _round(top5 / positive_total, 4) if positive_total > 0 else None
        ),
        "pnl_hhi_concentration": _round(hhi, 4) if hhi is not None else None,
        "sample_rows": rows[:20],
    }


def _gate(summary: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    aggregate = summary["aggregate_delta"]
    max_single = selection["max_single_positive_pnl_share"]
    top5 = selection["pnl_top_5_contribution_pct"]
    hhi = selection["pnl_hhi_concentration"]
    checks = {
        "positive_aggregate_ev": (aggregate.get("expected_value_score_sum_delta") or 0.0) > 0,
        "positive_aggregate_pnl": (aggregate.get("total_pnl_sum_delta") or 0.0) > 0,
        "ev_improved_window_coverage": summary["ev_positive_windows"] >= MIN_EV_IMPROVED_WINDOWS,
        "no_ev_regressed_windows": summary["ev_regressed_windows"] <= MAX_EV_REGRESSED_WINDOWS,
        "drawdown_worse_guard": summary["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE,
        "adjusted_trade_sample": selection["adjusted_trade_count"] >= MIN_ADJUSTED_TRADES,
        "adjusted_window_coverage": selection["windows_present"] >= MIN_ADJUSTED_WINDOWS,
        "single_ticker_positive_share_cap": (
            max_single is None or max_single <= MAX_SINGLE_TICKER_POSITIVE_SHARE
        ),
        "top5_contribution_cap": top5 is None or top5 <= MAX_TOP5_CONTRIBUTION,
        "hhi_concentration_cap": hhi is None or hhi <= MAX_HHI_CONCENTRATION,
    }
    return {
        "aggregate_delta": aggregate,
        "by_window": summary["by_window"],
        "checks": checks,
        "passed": all(checks.values()),
        "metrics": {
            "adjusted_trade_count": selection["adjusted_trade_count"],
            "adjusted_windows": sorted(selection["by_window_count"].keys()),
            "windows_ev_improved": summary["ev_positive_windows"],
            "windows_ev_regressed": summary["ev_regressed_windows"],
            "max_drawdown_worse": _round(summary["max_drawdown_delta_max"], 6),
            "max_single_positive_pnl_share": max_single,
            "pnl_top_5_contribution_pct": top5,
            "pnl_hhi_concentration": hhi,
        },
        "rules": {
            "metric_gate": (
                "aggregate EV/PnL positive, at least two EV-improved windows, "
                "zero EV-regressed windows, and max drawdown worsening <= 0.5pp"
            ),
            "sample_guard": {
                "min_adjusted_trades": MIN_ADJUSTED_TRADES,
                "min_adjusted_windows": MIN_ADJUSTED_WINDOWS,
            },
            "tail_guard": {
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
                "max_top5_contribution": MAX_TOP5_CONTRIBUTION,
                "max_hhi_concentration": MAX_HHI_CONCENTRATION,
            },
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    aggregate = gate["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Same-Ticker Repeat Scalar",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Best Variant",
        "",
        f"- best_variant: `{payload['best_variant']}`",
        f"- target_scalar: `{payload['parameters']['best_target_scalar']}`",
        f"- EV delta: `{aggregate.get('expected_value_score_sum_delta')}`",
        f"- PnL delta: `${aggregate.get('total_pnl_sum_delta')}`",
        f"- gate_passed: `{gate['passed']}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|",
    ]
    for label, row in gate["by_window"].items():
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {dd:+.4f} |".format(
                label=label,
                ev=row.get("expected_value_score", 0.0),
                pnl=row.get("total_pnl", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(_safe(gate), indent=2, sort_keys=True),
            "```",
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(_safe(payload["selection"]), indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    raw_exp100 = parent._load_exp100()
    current_queue = parent._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = parent._load_text_rows()
    exp100 = parent._annotate_language_fields(current_queue, text_rows_by_accession)
    text_coverage = parent._text_coverage_summary(exp100)
    target_coverage = _target_coverage_summary(exp100)
    gate2_fields = parent._gate2_open_position_field_check()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in parent.WINDOWS.items():
        result = parent._run_core_backtest(window)
        core_results[label] = {
            "metrics": parent._core_metrics(result),
            "equity_curve": parent._normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for key, scalar in TARGET_SCALAR_VARIANTS.items():
        variants[key] = _run_variant(
            core_results=core_results,
            exp100=exp100,
            repeat_scalar=scalar,
        )

    baseline_key = "repeat_scalar_1_00"
    baseline = variants[baseline_key]
    for key, row in variants.items():
        summaries[key] = _variant_summary(row, baseline)

    selections: dict[str, dict[str, Any]] = {}
    gates: dict[str, dict[str, Any]] = {}
    non_baseline = [key for key in variants if key != baseline_key]
    for key in non_baseline:
        scalar = TARGET_SCALAR_VARIANTS[key]
        selections[key] = _selection_summary(
            _closed_repeat_positions_for_scalar(exp100, repeat_scalar=scalar)
        )
        gates[key] = _gate(summaries[key], selections[key])

    passed = [key for key in non_baseline if gates[key]["passed"]]
    if passed:
        best_key = max(
            passed,
            key=lambda key: (
                summaries[key]["aggregate_delta"].get("expected_value_score_sum_delta")
                or -999.0,
                summaries[key]["aggregate_delta"].get("total_pnl_sum_delta") or -999999.0,
            ),
        )
    else:
        best_key = max(
            non_baseline,
            key=lambda key: (
                summaries[key]["aggregate_delta"].get("expected_value_score_sum_delta")
                or -999.0,
                summaries[key]["aggregate_delta"].get("total_pnl_sum_delta") or -999999.0,
            ),
        )

    best_scalar = TARGET_SCALAR_VARIANTS[best_key]
    selection = selections[best_key]
    gate = gates[best_key]
    status = "accepted_candidate" if gate["passed"] else "rejected"
    decision = (
        "promising_sec_same_ticker_repeat_scalar"
        if gate["passed"]
        else "rejected_sec_same_ticker_repeat_scalar"
    )
    interpretation = (
        "A same-ticker repeat scalar cleared the default-off SEC paper-sleeve "
        "Gate 4. It remains offline until shared policy wiring and parity tests "
        "are added."
        if gate["passed"]
        else "No same-ticker repeat scalar cleared the three-window, tail-aware "
        "SEC paper-sleeve gate on top of the accepted stack."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Within the default-off SEC financial-report paper sleeve, repeated "
            "same-ticker entries inside a 60-calendar-day lookback may represent "
            "a distinct replacement-value state. A bounded paper-notional scalar "
            "can test whether that state should be faded for concentration control "
            "or expanded for continuation value without changing eligibility, "
            "ranking, exits, LLM authority, or live orders."
        ),
        "change_summary": (
            "Sweep one paper-notional scalar for candidates whose ticker already "
            "appears in pending, open, or closed SEC paper-sleeve state within "
            "60 calendar days."
        ),
        "change_type": "alpha_search_sec_state_allocation",
        "component": "offline_sec_financial_report_paper_sleeve_replay",
        "changed_variable": SCALAR_FIELD,
        "single_causal_variable": SCALAR_FIELD,
        "trial_family": TRIAL_FAMILY,
        "trial_accounting": {
            "trial_family": TRIAL_FAMILY,
            "changed_variable": SCALAR_FIELD,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260519-008",
                "exp-20260522-011",
                "exp-20260524-004",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "stateful same-ticker repeat exposure derived from production-visible "
                "SEC paper sleeve state"
            ),
        },
        "parameters": {
            "baseline_target_scalar": BASELINE_REPEAT_SCALAR,
            "target_scalar_variants": dict(TARGET_SCALAR_VARIANTS),
            "best_target_scalar": best_scalar,
            "repeat_lookback_days": REPEAT_LOOKBACK_DAYS,
            "accepted_earnings_release_spy_context_scalar": (
                ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR
            ),
            "base_event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": parent.DEFAULT_MAX_POSITIONS,
            "anti_js": "No JavaScript was used.",
        },
        "target_definition": {
            "field": "sec_same_ticker_repeat_state",
            "target": "repeat_within_60d",
            "lookback_days": REPEAT_LOOKBACK_DAYS,
            "prior_state_buckets": ["pending_entries", "open_positions", "closed_positions"],
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production SEC financial-report paper-sleeve replay over the "
            "same snapshots."
        ),
        "windows": parent.WINDOWS,
        "candidate_counts_after_current_queue_filter": parent._candidate_counts(exp100),
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
        "target_coverage_summary": target_coverage,
        "gate2_required_fields": gate2_fields,
        "before_metrics": baseline["aggregate"],
        "after_metrics": variants[best_key]["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["by_window"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
        "best_variant": best_key,
        "variant_summaries": summaries,
        "selection": selection,
        "gate": gate,
        "interpretation": interpretation,
        "rejection_reason": None if gate["passed"] else interpretation,
        "next_evidence_needed": (
            "If pursued, promote only through shared default-off SEC paper-sleeve "
            "state metadata and parity tests; live orders remain disabled pending "
            "forward replacement-value evidence."
            if gate["passed"]
            else "Do not retry same-ticker repeat notional scalars on the frozen "
            "SEC sample without a new state variable or forward concentration evidence."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "live_default_orders_changed": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital/risk allocation: repeated same-ticker SEC paper entries "
                "inside 60 calendar days may deserve one notional scalar."
            ),
            "2_history_check": (
                "exp-20260519-008 improved the accepted SEC paper stack but left "
                "a concentration blocker; exp-20260522-011 rejected a semantic "
                "haircut due window/concentration failures; exp-20260524-004 "
                "added language provenance only."
            ),
            "3_single_causal_variable": SCALAR_FIELD,
            "4_acceptance_standard": gate["rules"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "The run uses deterministic SEC paper state; no new LLM authority "
                "or prompt dependency is introduced."
            ),
        },
        "why_not_other_changes": (
            "Skipped core state-surface and risk-scalar retunes because recent "
            "logs show low materiality and higher multiple-testing risk. This "
            "run uses one production-visible SEC state variable tied to the "
            "current concentration blocker."
        ),
        "related_files": [
            f"quant/experiments/{STEM}.py",
            _repo_rel(OUT_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            _repo_rel(EXPERIMENT_LOG_JSONL),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload.get("gate", {}) or {}
    selected = payload.get("best_variant")
    selected_summary = (payload.get("variant_summaries", {}) or {}).get(
        str(selected),
        {},
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload.get("timestamp"),
        "hypothesis": payload.get("hypothesis"),
        "change_type": "alpha_search",
        "changed_variable": SCALAR_FIELD,
        "trial_accounting": payload.get("trial_accounting"),
        "parameters": payload.get("parameters"),
        "backtest_protocol": payload.get("backtest_protocol"),
        "before_metrics": payload.get("before_metrics"),
        "after_metrics": selected_summary,
        "expected_value_score_delta": payload.get("expected_value_score_delta"),
        "decision": payload.get("decision"),
        "rejection_reason": payload.get("rejection_reason"),
        "next_evidence_needed": payload.get("next_evidence_needed"),
        "production_impact": payload.get("production_impact"),
        "gate": gate,
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": payload["single_causal_variable"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(DOC_LOG),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "aggregate_ev_delta": payload["expected_value_score_delta"],
                    "aggregate_pnl_delta": payload["total_pnl_delta"],
                    "gate_passed": payload["gate"]["passed"],
                    "window_checks": payload["gate"]["by_window"],
                    "selection": payload["selection"],
                    "target_coverage": payload["target_coverage_summary"],
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
