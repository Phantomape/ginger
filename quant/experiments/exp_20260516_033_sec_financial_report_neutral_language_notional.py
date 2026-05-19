"""exp-20260516-033: SEC financial-report neutral-language notional.

Alpha search on one causal variable: a paper-notional multiplier for covered
SEC financial-report T+1 paper-sleeve candidates whose archived filing text is
classified as ``neutral_or_mixed_language``. The accepted queue, T+1 excess
floor, hold days, max positions, base notional, periodic-report scalar, 10-Q
scalar, and live orders stay fixed.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260516-033"
STEM = "exp_20260516_033_sec_financial_report_neutral_language_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exp_20260511_112_sec_financial_report_t1_sleeve_capacity import (  # noqa: E402
    SOURCE_EXP100_JSON,
    WINDOWS,
    _aggregate,
    _combine_curves,
    _core_metrics,
    _delta,
    _equity_metrics,
    _load_exp100,
    _load_snapshot_prices,
    _normalise_core_curve,
    _rebuild_sleeve_state,
    _round,
    _rows_by_t1_date,
    _run_core_backtest,
    _safe,
    _write_json,
)
from exp_20260512_002_sec_financial_report_hold_days import (  # noqa: E402
    _filter_current_queue,
)
from sec_event_queue import (  # noqa: E402
    FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
    language_features,
)
from sec_financial_report_event_sleeve import (  # noqa: E402
    DEFAULT_EVENT_NOTIONAL_USD,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_financial_report_neutral_language_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
TEXT_ARCHIVE_JSONL = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_filing_text_20241002_20260421.jsonl"
)

# The reused SEC sleeve helpers predate the current docs/backtesting.md snapshot
# directory. Keep the canonical dates and point only at the current fixed files.
WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

ACCEPTED_10Q_PERIODIC_REPORT_SCALAR = 2.0
BASELINE_NEUTRAL_LANGUAGE_SCALAR = 1.0
NEUTRAL_LANGUAGE_SCALAR_VARIANTS = (0.75, 1.0, 1.10, 1.25, 1.50, 2.0)
MIN_PROMOTION_CLOSED_TRADES = 40
MIN_NEUTRAL_LANGUAGE_CLOSED_TRADES = 20
MAX_DRAWDOWN_WORSENING = 0.005


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _candidate_counts(exp100: dict[str, Any]) -> dict[str, int]:
    return {
        label: len(window.get("candidate_rows") or [])
        for label, window in exp100.get("windows", {}).items()
    }


def _accession(row: dict[str, Any]) -> str:
    return str(row.get("accession_number") or row.get("accession") or "").strip()


def _load_text_rows() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    rows_by_accession: dict[str, dict[str, Any]] = {}
    load_stats: list[dict[str, Any]] = []
    paths = [TEXT_ARCHIVE_JSONL]
    if not TEXT_ARCHIVE_JSONL.exists():
        paths = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_text_*.jsonl"))

    for path in paths:
        if not path.exists() or path.stat().st_size <= 0:
            continue
        loaded = 0
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            accession = _accession(row)
            if not accession:
                continue
            rows_by_accession[accession] = row
            loaded += 1
        load_stats.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "bytes": path.stat().st_size,
                "rows_loaded": loaded,
            }
        )
        if path == TEXT_ARCHIVE_JSONL:
            break
    return rows_by_accession, load_stats


def _annotate_language_fields(
    exp100: dict[str, Any],
    text_rows_by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    annotated = json.loads(json.dumps(exp100))
    for window in annotated.get("windows", {}).values():
        for row in window.get("candidate_rows") or []:
            accession = _accession(row)
            text_row = text_rows_by_accession.get(accession)
            if not text_row:
                row["sec_text_coverage_status"] = "missing_text_archive"
                row["language_bucket"] = None
                row["text_event_type"] = None
                continue
            features = language_features(text_row)
            row["sec_text_coverage_status"] = "covered"
            row["sec_text_pit_caveat"] = text_row.get("pit_caveat")
            row["text_event_type"] = features.get("text_event_type")
            row["language_bucket"] = features.get("language_bucket")
            row["language_score"] = features.get("language_score")
            row["positive_phrase_hits"] = features.get("positive_phrase_hits")
            row["negative_phrase_hits"] = features.get("negative_phrase_hits")
            row["guidance_raise_hits"] = features.get("guidance_raise_hits")
            row["guidance_cut_hits"] = features.get("guidance_cut_hits")
    return annotated


def _text_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    aggregate_status = Counter()
    aggregate_bucket = Counter()
    total = 0
    for label, window in exp100.get("windows", {}).items():
        rows = window.get("candidate_rows") or []
        status = Counter(str(row.get("sec_text_coverage_status") or "unknown") for row in rows)
        bucket = Counter(str(row.get("language_bucket") or "uncovered") for row in rows)
        total += len(rows)
        aggregate_status.update(status)
        aggregate_bucket.update(bucket)
        by_window[label] = {
            "candidate_count": len(rows),
            "coverage_status": dict(sorted(status.items())),
            "language_bucket": dict(sorted(bucket.items())),
        }
    covered = int(aggregate_status.get("covered") or 0)
    return {
        "aggregate": {
            "candidate_count": total,
            "covered_candidate_count": covered,
            "coverage_rate": _round(covered / total, 4) if total else None,
            "coverage_status": dict(sorted(aggregate_status.items())),
            "language_bucket": dict(sorted(aggregate_bucket.items())),
        },
        "by_window": by_window,
    }


def _gate2_open_position_field_check() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "path": str(OPEN_POSITIONS_JSON.relative_to(REPO_ROOT)),
            "exists": False,
            "checked_position_count": 0,
            "missing_entry_date_count": 0,
            "missing_target_price_count": 0,
            "passed": False,
        }
    raw = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        positions = raw
    elif isinstance(raw, dict):
        positions = raw.get("positions") or raw.get("open_positions") or []
    else:
        positions = []
    missing_entry = [
        str(item.get("ticker") or index)
        for index, item in enumerate(positions)
        if isinstance(item, dict) and not item.get("entry_date")
    ]
    missing_target = [
        str(item.get("ticker") or index)
        for index, item in enumerate(positions)
        if isinstance(item, dict) and item.get("target_price") in (None, "")
    ]
    return {
        "path": str(OPEN_POSITIONS_JSON.relative_to(REPO_ROOT)),
        "exists": True,
        "checked_position_count": len(positions),
        "missing_entry_date_count": len(missing_entry),
        "missing_target_price_count": len(missing_target),
        "sample_missing_entry_date": missing_entry[:10],
        "sample_missing_target_price": missing_target[:10],
        "passed": not missing_entry and not missing_target,
    }


def _source_candidate(position: dict[str, Any]) -> dict[str, Any]:
    candidate = position.get("source_candidate") or {}
    return candidate if isinstance(candidate, dict) else {}


def _event_family(position: dict[str, Any]) -> str:
    return str(_source_candidate(position).get("event_family") or "")


def _form_base(position: dict[str, Any]) -> str:
    candidate = _source_candidate(position)
    raw = (
        candidate.get("form_base")
        or candidate.get("form_type")
        or candidate.get("form")
        or candidate.get("sec_form")
        or ""
    )
    return str(raw).upper().strip() or "UNKNOWN"


def _is_10q(position: dict[str, Any]) -> bool:
    return _form_base(position).startswith("10-Q")


def _language_bucket(position: dict[str, Any]) -> str:
    return str(_source_candidate(position).get("language_bucket") or "uncovered")


def _coverage_status(position: dict[str, Any]) -> str:
    return str(_source_candidate(position).get("sec_text_coverage_status") or "unknown")


def _is_neutral_language_position(position: dict[str, Any]) -> bool:
    return (
        _coverage_status(position) == "covered"
        and _language_bucket(position) == "neutral_or_mixed_language"
    )


def _base_notional_for_position(position: dict[str, Any]) -> tuple[float, float, str]:
    base = float(DEFAULT_EVENT_NOTIONAL_USD)
    if _event_family(position) == "periodic_report":
        if _is_10q(position):
            scalar = float(ACCEPTED_10Q_PERIODIC_REPORT_SCALAR)
            return base * scalar, scalar, "periodic_report_10q_scalar"
        scalar = float(DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR)
        return base * scalar, scalar, "periodic_report_default_scalar"
    return base, 1.0, "base"


def _notional_for_position(
    position: dict[str, Any],
    *,
    neutral_language_scalar: float,
) -> tuple[float, float, str]:
    notional, scalar, rule = _base_notional_for_position(position)
    if not _is_neutral_language_position(position):
        return notional, scalar, rule
    combined_scalar = scalar * float(neutral_language_scalar)
    return (
        float(DEFAULT_EVENT_NOTIONAL_USD) * combined_scalar,
        combined_scalar,
        f"{rule}+neutral_mixed_language_scalar",
    )


def _pnl_for_position(
    position: dict[str, Any],
    *,
    neutral_language_scalar: float,
    closed: bool,
) -> float:
    adjusted_notional, _, _ = _notional_for_position(
        position,
        neutral_language_scalar=neutral_language_scalar,
    )
    if closed:
        try:
            net_return = float(position.get("net_return_pct") or 0.0) / 100.0
        except (TypeError, ValueError):
            net_return = 0.0
        return adjusted_notional * net_return

    try:
        source_notional = float(position.get("notional") or 0.0)
        source_pnl = float(position.get("net_pnl_if_closed_now") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if source_notional <= 0:
        return 0.0
    return adjusted_notional * (source_pnl / source_notional)


def _adjust_closed_position(
    position: dict[str, Any],
    *,
    neutral_language_scalar: float,
) -> dict[str, Any]:
    adjusted = dict(position)
    notional, scalar, rule = _notional_for_position(
        position,
        neutral_language_scalar=neutral_language_scalar,
    )
    adjusted["base_notional"] = float(DEFAULT_EVENT_NOTIONAL_USD)
    adjusted["notional"] = round(notional, 2)
    adjusted["event_notional_scalar"] = scalar
    adjusted["event_notional_rule"] = rule
    adjusted["form_base"] = _form_base(position)
    adjusted["event_family"] = _event_family(position)
    adjusted["sec_text_coverage_status"] = _coverage_status(position)
    adjusted["language_bucket"] = _language_bucket(position)
    adjusted["neutral_language_bucket"] = _is_neutral_language_position(position)
    adjusted["neutral_language_notional_scalar"] = neutral_language_scalar
    adjusted["pnl"] = round(
        _pnl_for_position(
            position,
            neutral_language_scalar=neutral_language_scalar,
            closed=True,
        ),
        2,
    )
    return adjusted


def _closed_position_breakdown(closed_positions: list[dict[str, Any]]) -> dict[str, Any]:
    count_by_rule = Counter(
        str(item.get("event_notional_rule") or "UNKNOWN") for item in closed_positions
    )
    count_by_bucket = Counter(
        str(item.get("language_bucket") or "uncovered") for item in closed_positions
    )
    count_by_coverage = Counter(
        str(item.get("sec_text_coverage_status") or "unknown") for item in closed_positions
    )
    pnl_by_rule: dict[str, float] = {}
    pnl_by_bucket: dict[str, float] = {}
    neutral_count = 0
    neutral_pnl = 0.0
    for item in closed_positions:
        rule = str(item.get("event_notional_rule") or "UNKNOWN")
        bucket = str(item.get("language_bucket") or "uncovered")
        pnl = float(item.get("pnl") or 0.0)
        pnl_by_rule[rule] = pnl_by_rule.get(rule, 0.0) + pnl
        pnl_by_bucket[bucket] = pnl_by_bucket.get(bucket, 0.0) + pnl
        if item.get("neutral_language_bucket") is True:
            neutral_count += 1
            neutral_pnl += pnl
    return {
        "closed_trade_count_by_rule": dict(sorted(count_by_rule.items())),
        "closed_pnl_by_rule": {
            key: _round(value, 2) for key, value in sorted(pnl_by_rule.items())
        },
        "closed_trade_count_by_language_bucket": dict(sorted(count_by_bucket.items())),
        "closed_pnl_by_language_bucket": {
            key: _round(value, 2) for key, value in sorted(pnl_by_bucket.items())
        },
        "closed_trade_count_by_text_coverage": dict(sorted(count_by_coverage.items())),
        "neutral_language_closed_trade_count": neutral_count,
        "neutral_language_total_pnl": _round(neutral_pnl, 2),
    }


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    neutral_language_scalar: float,
) -> dict[str, Any]:
    prices_by_date = _load_snapshot_prices(window["snapshot"])
    candidates_by_t1 = _rows_by_t1_date(window_payload)
    state = empty_sec_financial_report_event_sleeve_state()
    skipped_entries: list[dict[str, Any]] = []
    pnl_by_date: OrderedDict[str, float] = OrderedDict()
    max_open_positions = 0
    max_gross_notional = 0.0
    enqueued_candidates = 0

    for as_of, prices in prices_by_date.items():
        candidates = candidates_by_t1.get(as_of, [])
        enqueued_candidates += len(candidates)
        queue = {
            "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
            "rule_version": f"{EXPERIMENT_ID}-replay",
            "enabled": False,
            "asof_date": as_of,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "data_source": {
                "status": "replay",
                "source_experiment": "exp-20260511-100",
                "window": window_label,
            },
        }
        snapshot = build_sec_financial_report_event_sleeve_snapshot(
            sec_financial_report_t1_queue=queue,
            as_of=as_of,
            open_prices=prices["open"],
            current_prices=prices["close"],
            state=state,
            config={
                "max_positions": DEFAULT_MAX_POSITIONS,
                "event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
                "periodic_report_notional_scalar": DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
                "tenq_periodic_report_notional_scalar": ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            },
            persist=False,
        )
        skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
        state = _rebuild_sleeve_state(snapshot, skipped_entries)

        realized = sum(
            _pnl_for_position(
                item,
                neutral_language_scalar=neutral_language_scalar,
                closed=True,
            )
            for item in state.get("closed_positions") or []
        )
        unrealized = sum(
            _pnl_for_position(
                item,
                neutral_language_scalar=neutral_language_scalar,
                closed=False,
            )
            for item in state.get("open_positions") or []
        )
        pnl_by_date[as_of] = realized + unrealized
        open_positions = state.get("open_positions") or []
        max_open_positions = max(max_open_positions, len(open_positions))
        max_gross_notional = max(
            max_gross_notional,
            sum(
                _notional_for_position(
                    item,
                    neutral_language_scalar=neutral_language_scalar,
                )[0]
                for item in open_positions
            ),
        )

    closed_positions = [
        _adjust_closed_position(
            item,
            neutral_language_scalar=neutral_language_scalar,
        )
        for item in state.get("closed_positions") or []
    ]
    wins = sum(1 for item in closed_positions if float(item.get("pnl") or 0.0) > 0)
    sleeve_curve = [
        (date_value, 100_000.0 + pnl) for date_value, pnl in pnl_by_date.items()
    ]
    standalone_metrics = _equity_metrics(
        sleeve_curve,
        trade_count=len(closed_positions),
        win_rate=(wins / len(closed_positions) if closed_positions else None),
    )
    standalone_metrics.update(
        {
            "candidate_count": enqueued_candidates,
            "closed_trade_count": len(closed_positions),
            "open_position_count_end": len(state.get("open_positions") or []),
            "skipped_capacity_count": len(skipped_entries),
            "max_open_positions": max_open_positions,
            "max_gross_notional": _round(max_gross_notional, 2),
        }
    )
    standalone_metrics.update(_closed_position_breakdown(closed_positions))
    return {
        "daily_pnl": list(pnl_by_date.items()),
        "metrics": standalone_metrics,
        "sample_closed_positions": closed_positions[:10],
    }


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    neutral_language_scalar: float,
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            neutral_language_scalar=neutral_language_scalar,
        )
        core_curve = core_results[label]["equity_curve"]
        combined_curve = _combine_curves(core_curve, sleeve["daily_pnl"])
        core_metrics = core_results[label]["metrics"]
        combined_metrics = _equity_metrics(
            combined_curve,
            trade_count=int(core_metrics.get("trade_count") or 0)
            + int(sleeve["metrics"].get("closed_trade_count") or 0),
            win_rate=None,
            signals_generated=core_metrics.get("signals_generated"),
            signals_survived=core_metrics.get("signals_survived"),
        )
        by_window[label] = {
            "combined_metrics": combined_metrics,
            "core_metrics": core_metrics,
            "sleeve_metrics": sleeve["metrics"],
            "sample_closed_positions": sleeve["sample_closed_positions"],
        }
    return {"by_window": by_window, "aggregate": _aggregate(by_window)}


def _neutral_closed_trade_count(row: dict[str, Any]) -> int:
    return sum(
        int(window["sleeve_metrics"].get("neutral_language_closed_trade_count", 0))
        for window in row["by_window"].values()
    )


def _window_checks(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label in WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        after_sleeve = after["by_window"][label]["sleeve_metrics"]
        before_sleeve = before["by_window"][label]["sleeve_metrics"]
        checks[label] = {
            "ev_delta": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "pnl_delta": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "max_drawdown_delta": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "neutral_language_closed_trade_count": int(
                after_sleeve.get("neutral_language_closed_trade_count") or 0
            ),
            "neutral_language_pnl_delta": _round(
                float(after_sleeve.get("neutral_language_total_pnl") or 0.0)
                - float(before_sleeve.get("neutral_language_total_pnl") or 0.0),
                2,
            ),
        }
    return checks


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _delta(after["aggregate"], before["aggregate"])
    checks = _window_checks(after, before)
    ev_positive_windows = sum(1 for row in checks.values() if row["ev_delta"] > 0)
    ev_regressed_windows = sum(1 for row in checks.values() if row["ev_delta"] < 0)
    pnl_positive_windows = sum(1 for row in checks.values() if row["pnl_delta"] > 0)
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in checks.values())
    sleeve_trades_after = int(after["aggregate"].get("sleeve_closed_trade_count_sum") or 0)
    neutral_closed_trades_after = _neutral_closed_trade_count(after)
    passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("sleeve_total_pnl_sum_delta") or 0.0) > 0.0
        and ev_positive_windows == 3
        and ev_regressed_windows == 0
        and pnl_positive_windows == 3
        and max_drawdown_delta_max <= MAX_DRAWDOWN_WORSENING
        and sleeve_trades_after >= MIN_PROMOTION_CLOSED_TRADES
        and neutral_closed_trades_after >= MIN_NEUTRAL_LANGUAGE_CLOSED_TRADES
    )
    return {
        "aggregate_delta": aggregate_delta,
        "neutral_language_closed_trade_count_after": neutral_closed_trades_after,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "passed": passed,
        "pnl_positive_windows": pnl_positive_windows,
        "rule": (
            "Pass if aggregate EV and sleeve PnL improve, EV and PnL improve "
            "in all three windows, max drawdown worsens by no more than 0.5 "
            "percentage points in any window, sleeve closed trades >= 40, and "
            "neutral-language closed trades >= 20."
        ),
        "sleeve_closed_trade_count_after": sleeve_trades_after,
        "window_checks": checks,
    }


def _best_candidate(variants: OrderedDict[str, dict[str, Any]]) -> str:
    baseline = variants[f"neutral_language_scalar_{BASELINE_NEUTRAL_LANGUAGE_SCALAR:.2f}"]
    candidates = [
        (name, row, _gate(row, baseline))
        for name, row in variants.items()
        if row["neutral_language_notional_scalar"] != BASELINE_NEUTRAL_LANGUAGE_SCALAR
    ]
    passed = [(name, row, gate) for name, row, gate in candidates if gate["passed"]]
    if passed:
        return max(
            passed,
            key=lambda item: (
                item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or 0.0,
                item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or 0.0,
            ),
        )[0]
    return max(
        candidates,
        key=lambda item: (
            item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or -999.0,
            item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or -999999.0,
        ),
    )[0]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    coverage = payload["text_coverage_summary"]["aggregate"]
    lines = [
        f"# {payload['experiment_id']} SEC neutral-language notional",
        "",
        f"- decision: `{payload['decision']}`",
        f"- changed_variable: `{payload['changed_variable']}`",
        f"- best_variant: `{payload['best_variant']}`",
        f"- expected_value_score_delta: `{payload['expected_value_score_delta']}`",
        f"- total_pnl_delta: `{gate['aggregate_delta'].get('total_pnl_sum_delta')}`",
        f"- sleeve_pnl_delta: `{gate['aggregate_delta'].get('sleeve_total_pnl_sum_delta')}`",
        f"- gate_passed: `{gate['passed']}`",
        f"- text_coverage_rate: `{coverage.get('coverage_rate')}`",
        "",
        "## Window Deltas",
        "",
        "| window | EV delta | PnL delta | Max DD delta | Neutral trades | Neutral PnL delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in gate["window_checks"].items():
        lines.append(
            "| {label} | {ev} | {pnl} | {dd} | {count} | {neutral_pnl} |".format(
                label=label,
                ev=row["ev_delta"],
                pnl=row["pnl_delta"],
                dd=row["max_drawdown_delta"],
                count=row["neutral_language_closed_trade_count"],
                neutral_pnl=row["neutral_language_pnl_delta"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["next_evidence_needed"],
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    timestamp = _utc_now()
    raw_exp100 = _load_exp100()
    current_queue = _filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = _load_text_rows()
    exp100 = _annotate_language_fields(current_queue, text_rows_by_accession)
    text_coverage = _text_coverage_summary(exp100)
    gate2_fields = _gate2_open_position_field_check()

    core_results = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        core_results[label] = {
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for scalar in NEUTRAL_LANGUAGE_SCALAR_VARIANTS:
        name = f"neutral_language_scalar_{scalar:.2f}"
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=scalar,
        )
        row["neutral_language_notional_scalar"] = scalar
        variants[name] = row

    baseline_key = f"neutral_language_scalar_{BASELINE_NEUTRAL_LANGUAGE_SCALAR:.2f}"
    baseline = variants[baseline_key]
    best_key = _best_candidate(variants)
    best = variants[best_key]
    gate = _gate(best, baseline)
    production_field_blocked = True
    metric_gate_passed = bool(gate["passed"])
    status = "observed_only" if metric_gate_passed else "rejected"
    decision = (
        "observed_only_neutral_language_notional_positive_field_blocked"
        if metric_gate_passed
        else "rejected_neutral_language_notional_scalar"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, covered "
            "filings with neutral_or_mixed_language may be better underreaction "
            "candidates after positive T+1 confirmation than explicitly positive "
            "or negative filing prose, so they may deserve a separate paper-notional "
            "multiplier."
        ),
        "change_summary": (
            "Replay-only paper-notional multiplier for covered "
            "neutral_or_mixed_language SEC financial-report T+1 sleeve rows."
        ),
        "change_type": "alpha_search_semantic_risk_allocation",
        "component": "quant/experiments",
        "changed_variable": "sec_financial_report_neutral_language_notional_scalar",
        "parameters": {
            "baseline_neutral_language_notional_scalar": BASELINE_NEUTRAL_LANGUAGE_SCALAR,
            "neutral_language_definition": (
                "sec_text_coverage_status == covered and language_bucket == "
                "neutral_or_mixed_language"
            ),
            "neutral_language_scalar_variants": list(NEUTRAL_LANGUAGE_SCALAR_VARIANTS),
            "base_event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": DEFAULT_MAX_POSITIONS,
            "min_t1_excess_return_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
            "source_candidate_artifact": str(SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
            "text_archive": str(TEXT_ARCHIVE_JSONL.relative_to(REPO_ROOT)),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production paper-sleeve replay over the same OHLCV snapshots. "
            "Core replay uses REPLAY_PARTIAL_REDUCES and REGIME_AWARE_EXIT."
        ),
        "date_range": {
            "primary": {
                "start": WINDOWS["late_strong"]["start"],
                "end": WINDOWS["late_strong"]["end"],
            },
            "secondary": [
                {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
                {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
            ],
        },
        "candidate_counts_after_current_queue_filter": _candidate_counts(exp100),
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
        "gate2_required_fields": gate2_fields,
        "before_metrics": baseline["aggregate"],
        "after_metrics": best["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "best_variant": best_key,
        "gate": gate,
        "decision": decision,
        "rejection_reason": (
            None
            if metric_gate_passed
            else "No neutral-language scalar cleared the three-window semantic allocation gate."
        ),
        "next_evidence_needed": (
            "Metric gate passed on replay, but do not promote until SEC financial-report "
            "production candidates carry language_bucket/text coverage fields and parity "
            "tests prove the same field is visible in run.py and backtester paths."
            if metric_gate_passed
            else "Do not retry neutral-language notional scalars on this frozen sample; "
            "future SEC text work needs production-visible language fields, fuller text "
            "coverage, or forward replacement-value evidence."
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
            "production_field_blocked": production_field_blocked,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "risk allocation: use a new replayable SEC filing-text language "
                "bucket to scale paper notional only for neutral/mixed-language "
                "financial-report T+1 candidates."
            ),
            "2_history_check": (
                "Recent SEC financial-report experiments accepted max-3 capacity, "
                "T+1 excess floor, 10-day hold, 10-Q 2.0x notional, and rejected "
                "10-Q-first priority, paired-filing dedupe, buybacks, and auxiliary "
                "earnings 8-K notional. No logged experiment isolated the "
                "neutral_or_mixed_language bucket on the accepted 10-Q stack."
            ),
            "3_single_causal_variable": "neutral/mixed language paper-notional scalar only",
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "variants": variants,
        "why_not_other_changes": (
            "Space nearby LUNR/RKLB target and risk-scalar retries are exhausted "
            "without new forward evidence, core ATR/volume/RS threshold retunes are "
            "anti-repeat logged, and LLM soft-ranking is still too sparse. This tests "
            "a different deterministic SEC semantic field instead of adding noisy tickers."
        ),
        "related_files": [
            f"quant/experiments/{STEM}.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG_JSONL.relative_to(REPO_ROOT)),
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": status,
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["changed_variable"],
            "acceptance_rule": gate["rule"],
            "result": {
                "decision": decision,
                "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
                "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
                "production_field_blocked": production_field_blocked,
            },
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision} best={best_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
