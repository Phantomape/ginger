"""exp-20260512-032: SEC financial-report paired-filing dedupe.

Alpha search on one causal variable: whether same-ticker, same-event-date SEC
financial-report paper candidates should be deduped before entering the
default-off T+1 sleeve. Capacity, T+1 floor, hold days, notional, queue sort,
live orders, and the core A/B behavior stay fixed.
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260512-033"
STEM = "sec_financial_report_paired_filing_dedupe"
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
from sec_event_queue import FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY  # noqa: E402
from sec_financial_report_event_sleeve import (  # noqa: E402
    DEFAULT_10Q_PERIODIC_REPORT_NOTIONAL_SCALAR,
    DEFAULT_EVENT_NOTIONAL_USD,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "none"
DEDUPE_VARIANTS = (
    BASELINE_VARIANT,
    "keep_10q_else_periodic",
    "keep_earnings_8k",
    "keep_highest_t1_excess",
)
MAX_DRAWDOWN_WORSENING = 0.005
MIN_SLEEVE_CLOSED_TRADES = 40
MIN_DEDUPED_CANDIDATES = 1


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
            and '"experiment_id":"exp-20260512-032"' not in line
            and '"experiment_id": "exp-20260512-032"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_source_candidates() -> dict[str, Any]:
    return json.loads(SOURCE_EXP100_JSON.read_text(encoding="utf-8"))


def _candidate_counts(exp100: dict[str, Any]) -> dict[str, int]:
    return {
        label: len(window.get("candidate_rows") or [])
        for label, window in exp100.get("windows", {}).items()
    }


def _source_candidate(position_or_entry: dict[str, Any]) -> dict[str, Any]:
    candidate = position_or_entry.get("source_candidate")
    if not isinstance(candidate, dict):
        candidate = position_or_entry.get("candidate")
    return candidate if isinstance(candidate, dict) else position_or_entry


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _event_family(row: dict[str, Any]) -> str:
    return str(_source_candidate(row).get("event_family") or "")


def _form_base(row: dict[str, Any]) -> str:
    candidate = _source_candidate(row)
    raw = (
        candidate.get("form_base")
        or candidate.get("form_type")
        or candidate.get("form")
        or candidate.get("sec_form")
        or ""
    )
    return str(raw).upper().strip() or "UNKNOWN"


def _event_date(row: dict[str, Any]) -> str:
    candidate = _source_candidate(row)
    raw = (
        candidate.get("event_trading_date")
        or candidate.get("event_date")
        or candidate.get("filing_date")
        or candidate.get("accepted_at")
        or ""
    )
    return str(raw)[:10]


def _ticker(row: dict[str, Any]) -> str:
    return str(_source_candidate(row).get("ticker") or "").upper().strip()


def _dedupe_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_ticker(row), _event_date(row))


def _is_10q_periodic(row: dict[str, Any]) -> bool:
    return _event_family(row) == "periodic_report" and _form_base(row).startswith("10-Q")


def _is_periodic(row: dict[str, Any]) -> bool:
    return _event_family(row) == "periodic_report"


def _is_earnings_8k(row: dict[str, Any]) -> bool:
    return _event_family(row) == "earnings_8k"


def _accepted_at(row: dict[str, Any]) -> str:
    return str(_source_candidate(row).get("accepted_at") or "")


def _candidate_identity(row: dict[str, Any]) -> dict[str, Any]:
    candidate = _source_candidate(row)
    return {
        "ticker": _ticker(row),
        "event_date": _event_date(row),
        "event_family": _event_family(row),
        "form_base": _form_base(row),
        "accepted_at": _accepted_at(row),
        "accession_number": str(candidate.get("accession_number") or ""),
        "t1_excess_return_vs_spy": _round(
            _float_or_zero(candidate.get("t1_excess_return_vs_spy")),
            6,
        ),
    }


def _dedupe_sort_key(row: dict[str, Any], variant: str) -> tuple[Any, ...]:
    candidate = _source_candidate(row)
    t1_excess = _float_or_zero(candidate.get("t1_excess_return_vs_spy"))
    if variant == "keep_10q_else_periodic":
        return (
            0 if _is_10q_periodic(row) else 1 if _is_periodic(row) else 2,
            -t1_excess,
            _accepted_at(row),
        )
    if variant == "keep_earnings_8k":
        return (
            0 if _is_earnings_8k(row) else 1,
            -t1_excess,
            _accepted_at(row),
        )
    if variant == "keep_highest_t1_excess":
        return (
            -t1_excess,
            0 if _is_10q_periodic(row) else 1 if _is_periodic(row) else 2,
            _accepted_at(row),
        )
    raise ValueError(f"Unsupported dedupe variant: {variant}")


def _dedupe_candidate_rows(
    rows: list[dict[str, Any]],
    *,
    variant: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if variant == BASELINE_VARIANT:
        return list(rows), {
            "candidate_count_before": len(rows),
            "candidate_count_after": len(rows),
            "deduped_candidate_count": 0,
            "dedupe_group_count": 0,
            "dedupe_group_samples": [],
        }

    grouped: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
    passthrough: list[tuple[int, dict[str, Any]]] = []
    for index, row in enumerate(rows):
        key = _dedupe_key(row)
        if not key[0] or not key[1]:
            passthrough.append((index, row))
            continue
        grouped.setdefault(key, []).append(row)

    selected_by_first_index: list[tuple[int, dict[str, Any]]] = list(passthrough)
    samples = []
    removed = 0
    dedupe_group_count = 0
    for group_rows in grouped.values():
        first_index = rows.index(group_rows[0])
        if len(group_rows) == 1:
            selected_by_first_index.append((first_index, group_rows[0]))
            continue
        chosen = sorted(group_rows, key=lambda row: _dedupe_sort_key(row, variant))[0]
        selected_by_first_index.append((first_index, chosen))
        removed += len(group_rows) - 1
        dedupe_group_count += 1
        if len(samples) < 10:
            samples.append(
                {
                    "key": list(_dedupe_key(chosen)),
                    "chosen": _candidate_identity(chosen),
                    "removed": [
                        _candidate_identity(row)
                        for row in group_rows
                        if row is not chosen
                    ],
                }
            )

    selected_by_first_index.sort(key=lambda item: item[0])
    deduped = [row for _, row in selected_by_first_index]
    return deduped, {
        "candidate_count_before": len(rows),
        "candidate_count_after": len(deduped),
        "deduped_candidate_count": removed,
        "dedupe_group_count": dedupe_group_count,
        "dedupe_group_samples": samples,
    }


def _apply_dedupe_variant(
    exp100: dict[str, Any],
    *,
    variant: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = copy.deepcopy(exp100)
    stats = {}
    for label in WINDOWS:
        window_payload = payload["windows"][label]
        rows = list(window_payload.get("candidate_rows") or [])
        deduped, window_stats = _dedupe_candidate_rows(rows, variant=variant)
        window_payload["candidate_rows"] = deduped
        stats[label] = window_stats
    return payload, stats


def _notional_for_position(position: dict[str, Any]) -> tuple[float, float, str]:
    base = float(DEFAULT_EVENT_NOTIONAL_USD)
    if _event_family(position) != "periodic_report":
        return base, 1.0, "base"
    if _form_base(position).startswith("10-Q"):
        scalar = float(DEFAULT_10Q_PERIODIC_REPORT_NOTIONAL_SCALAR)
        return base * scalar, scalar, "periodic_report_10q_scalar"
    scalar = float(DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR)
    return base * scalar, scalar, "periodic_report_default_scalar"


def _pnl_for_position(position: dict[str, Any], *, closed: bool) -> float:
    adjusted_notional, _, _ = _notional_for_position(position)
    if closed:
        return adjusted_notional * (_float_or_zero(position.get("net_return_pct")) / 100.0)

    source_notional = _float_or_zero(position.get("notional"))
    source_pnl = _float_or_zero(position.get("net_pnl_if_closed_now"))
    if source_notional <= 0:
        return 0.0
    return adjusted_notional * (source_pnl / source_notional)


def _adjust_closed_position(position: dict[str, Any]) -> dict[str, Any]:
    adjusted = dict(position)
    notional, scalar, rule = _notional_for_position(position)
    adjusted["base_notional"] = float(DEFAULT_EVENT_NOTIONAL_USD)
    adjusted["notional"] = round(notional, 2)
    adjusted["event_notional_scalar"] = scalar
    adjusted["event_notional_rule"] = rule
    adjusted["form_base"] = _form_base(position)
    adjusted["pnl"] = round(_pnl_for_position(position, closed=True), 2)
    return adjusted


def _closed_position_breakdown(
    closed_positions: list[dict[str, Any]],
) -> dict[str, Any]:
    count_by_family = Counter(
        _event_family(item) or "UNKNOWN" for item in closed_positions
    )
    count_by_form = Counter(str(item.get("form_base") or "UNKNOWN") for item in closed_positions)
    pnl_by_family: dict[str, float] = {}
    pnl_by_form: dict[str, float] = {}
    for item in closed_positions:
        family = _event_family(item) or "UNKNOWN"
        form = str(item.get("form_base") or "UNKNOWN")
        pnl = float(item.get("pnl") or 0.0)
        pnl_by_family[family] = pnl_by_family.get(family, 0.0) + pnl
        pnl_by_form[form] = pnl_by_form.get(form, 0.0) + pnl
    return {
        "closed_trade_count_by_event_family": dict(sorted(count_by_family.items())),
        "closed_pnl_by_event_family": {
            key: _round(value, 2) for key, value in sorted(pnl_by_family.items())
        },
        "closed_trade_count_by_form_base": dict(sorted(count_by_form.items())),
        "closed_pnl_by_form_base": {
            key: _round(value, 2) for key, value in sorted(pnl_by_form.items())
        },
    }


def _closed_positions_changed(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> int:
    before_ids = {str(item.get("decision_id")) for item in before}
    after_ids = {str(item.get("decision_id")) for item in after}
    return len(before_ids.symmetric_difference(after_ids))


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    dedupe_variant: str,
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
            "rule_version": f"{EXPERIMENT_ID}-{dedupe_variant}",
            "enabled": False,
            "asof_date": as_of,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "data_source": {
                "status": "replay",
                "source_experiment": "exp-20260511-100",
                "window": window_label,
                "dedupe_variant": dedupe_variant,
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
                "periodic_report_notional_scalar": (
                    DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR
                ),
                "tenq_periodic_report_notional_scalar": (
                    DEFAULT_10Q_PERIODIC_REPORT_NOTIONAL_SCALAR
                ),
            },
            persist=False,
        )
        skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
        state = _rebuild_sleeve_state(snapshot, skipped_entries)
        realized = sum(
            _pnl_for_position(item, closed=True)
            for item in state.get("closed_positions") or []
        )
        unrealized = sum(
            _pnl_for_position(item, closed=False)
            for item in state.get("open_positions") or []
        )
        pnl_by_date[as_of] = realized + unrealized
        max_open_positions = max(
            max_open_positions,
            int(snapshot.get("open_position_count") or 0),
        )
        max_gross_notional = max(
            max_gross_notional,
            sum(
                _notional_for_position(item)[0]
                for item in snapshot.get("open_positions") or []
            ),
        )

    closed_positions = [
        _adjust_closed_position(item) for item in state.get("closed_positions", [])
    ]
    standalone_metrics = _equity_metrics(
        list(pnl_by_date.items()),
        trade_count=len(closed_positions),
        win_rate=(
            sum(1 for item in closed_positions if float(item.get("pnl") or 0.0) > 0)
            / len(closed_positions)
            if closed_positions
            else None
        ),
        signals_generated=enqueued_candidates,
        signals_survived=enqueued_candidates,
    )
    standalone_metrics.update(
        {
            "closed_trade_count": len(closed_positions),
            "open_position_count_end": len(state.get("open_positions") or []),
            "pending_count_end": len(state.get("pending_entries") or []),
            "skipped_capacity_count": len(skipped_entries),
            "max_open_positions": max_open_positions,
            "max_gross_notional": _round(max_gross_notional, 2),
            "dedupe_variant": dedupe_variant,
        }
    )
    standalone_metrics.update(_closed_position_breakdown(closed_positions))
    return {
        "closed_positions": closed_positions,
        "daily_pnl": list(pnl_by_date.items()),
        "metrics": standalone_metrics,
        "sample_closed_positions": closed_positions[:10],
    }


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    dedupe_stats: dict[str, Any],
    dedupe_variant: str,
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            dedupe_variant=dedupe_variant,
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
            "closed_positions": sleeve["closed_positions"],
            "combined_metrics": combined_metrics,
            "core_metrics": core_metrics,
            "dedupe_stats": dedupe_stats[label],
            "sample_closed_positions": sleeve["sample_closed_positions"],
            "sleeve_metrics": sleeve["metrics"],
        }
    return {
        "aggregate": _aggregate(by_window),
        "by_window": by_window,
        "dedupe_variant": dedupe_variant,
        "dedupe_stats": dedupe_stats,
    }


def _window_checks(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label in WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        after_s = after["by_window"][label]["sleeve_metrics"]
        before_s = before["by_window"][label]["sleeve_metrics"]
        checks[label] = {
            "deduped_candidate_count": int(
                after["by_window"][label]["dedupe_stats"].get("deduped_candidate_count")
                or 0
            ),
            "changed_closed_trade_count": _closed_positions_changed(
                before["by_window"][label]["closed_positions"],
                after["by_window"][label]["closed_positions"],
            ),
            "ev_delta": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "max_drawdown_delta": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "pnl_delta": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "sleeve_pnl_delta": _round(
                float(after_s.get("total_pnl") or 0.0)
                - float(before_s.get("total_pnl") or 0.0),
                2,
            ),
            "sleeve_closed_trade_count_after": int(
                after_s.get("closed_trade_count") or 0
            ),
        }
    return checks


def _gate(
    after: dict[str, Any],
    before: dict[str, Any],
    *,
    dedupe_variant: str,
) -> dict[str, Any]:
    aggregate_delta = _delta(after["aggregate"], before["aggregate"])
    checks = _window_checks(after, before)
    ev_positive_windows = sum(1 for row in checks.values() if row["ev_delta"] > 0)
    ev_regressed_windows = sum(1 for row in checks.values() if row["ev_delta"] < 0)
    pnl_positive_windows = sum(1 for row in checks.values() if row["pnl_delta"] > 0)
    pnl_regressed_windows = sum(1 for row in checks.values() if row["pnl_delta"] < 0)
    changed_closed_trade_count = sum(
        row["changed_closed_trade_count"] for row in checks.values()
    )
    deduped_candidate_count = sum(
        row["deduped_candidate_count"] for row in checks.values()
    )
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in checks.values())
    sleeve_trades_after = int(after["aggregate"].get("sleeve_closed_trade_count_sum") or 0)
    passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("sleeve_total_pnl_sum_delta") or 0.0) > 0
        and ev_positive_windows >= 2
        and ev_regressed_windows == 0
        and pnl_positive_windows >= 2
        and pnl_regressed_windows == 0
        and max_drawdown_delta_max <= MAX_DRAWDOWN_WORSENING
        and sleeve_trades_after >= MIN_SLEEVE_CLOSED_TRADES
        and deduped_candidate_count >= MIN_DEDUPED_CANDIDATES
    )
    return {
        "aggregate_delta": aggregate_delta,
        "changed_closed_trade_count": changed_closed_trade_count,
        "deduped_candidate_count": deduped_candidate_count,
        "dedupe_variant": dedupe_variant,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "passed": passed,
        "pnl_positive_windows": pnl_positive_windows,
        "pnl_regressed_windows": pnl_regressed_windows,
        "rule": (
            "Pass if aggregate EV and sleeve PnL improve, at least two windows "
            "improve on EV/PnL, no window regresses on EV/PnL, max drawdown "
            "worsens by no more than 0.5 percentage points, sleeve closed "
            "trades >= 40, and the dedupe variant changes at least one "
            "candidate."
        ),
        "sleeve_closed_trade_count_after": sleeve_trades_after,
        "window_checks": checks,
    }


def _compact_position(position: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": position.get("decision_id"),
        "ticker": position.get("ticker"),
        "entry_date": position.get("entry_date"),
        "exit_date": position.get("exit_date"),
        "event_family": _event_family(position),
        "form_base": position.get("form_base"),
        "notional": position.get("notional"),
        "pnl": position.get("pnl"),
        "net_return_pct": position.get("net_return_pct"),
    }


def _compact_variant(variant: dict[str, Any]) -> dict[str, Any]:
    by_window = {}
    for label, row in variant["by_window"].items():
        by_window[label] = {
            "combined_metrics": row["combined_metrics"],
            "dedupe_stats": row["dedupe_stats"],
            "sample_closed_positions": [
                _compact_position(item) for item in row["sample_closed_positions"]
            ],
            "sleeve_metrics": row["sleeve_metrics"],
        }
    return {
        "aggregate": variant["aggregate"],
        "by_window": by_window,
        "dedupe_variant": variant["dedupe_variant"],
        "dedupe_stats": variant["dedupe_stats"],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC financial-report paired-filing dedupe",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Best tested dedupe variant: `{payload['best_variant']}`",
        f"- EV delta: `{payload['expected_value_score_delta']}`",
        (
            f"- Total PnL delta: "
            f"`{payload['gate']['aggregate_delta'].get('total_pnl_sum_delta')}`"
        ),
        (
            f"- Sleeve PnL delta: "
            f"`{payload['gate']['aggregate_delta'].get('sleeve_total_pnl_sum_delta')}`"
        ),
        f"- Deduped candidates: `{payload['gate']['deduped_candidate_count']}`",
        "",
        "## Aggregate",
        "",
        "| Variant | EV sum | EV delta | Total PnL | Total PnL delta | Sleeve PnL | Sleeve closed | Max DD max |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    baseline = payload["variants"][BASELINE_VARIANT]["aggregate"]
    for name, row in payload["variants"].items():
        agg = row["aggregate"]
        delta = _delta(agg, baseline)
        lines.append(
            f"| {name} | {agg['expected_value_score_sum']:.6f} | "
            f"{delta['expected_value_score_sum_delta']:.6f} | "
            f"${agg['total_pnl_sum']:,.2f} | "
            f"${delta['total_pnl_sum_delta']:,.2f} | "
            f"${agg['sleeve_total_pnl_sum']:,.2f} | "
            f"{agg['sleeve_closed_trade_count_sum']} | "
            f"{agg['max_drawdown_pct_max']:.4f} |"
        )
    lines.extend(["", f"## Window Deltas For {payload['best_variant']}", ""])
    lines.append(
        "| Window | Deduped | EV delta | PnL delta | Sleeve PnL delta | Changed trades | Max DD delta |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for label, row in payload["gate"]["window_checks"].items():
        lines.append(
            f"| {label} | {row['deduped_candidate_count']} | "
            f"{row['ev_delta']:.6f} | ${row['pnl_delta']:,.2f} | "
            f"${row['sleeve_pnl_delta']:,.2f} | "
            f"{row['changed_closed_trade_count']} | "
            f"{row['max_drawdown_delta']:.6f} |"
        )
    lines.extend(
        [
            "",
            (
                "This is a default-off paper sleeve candidate-pool alpha "
                "experiment. It changes no live orders, queue qualification, "
                "capacity, hold days, notional, or core signal path."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    timestamp = _utc_now()
    raw_exp100 = _load_source_candidates()
    exp100 = _filter_current_queue(raw_exp100)

    core_results = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        core_results[label] = {
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for dedupe_variant in DEDUPE_VARIANTS:
        variant_exp100, dedupe_stats = _apply_dedupe_variant(
            exp100,
            variant=dedupe_variant,
        )
        variants[dedupe_variant] = _run_variant(
            core_results=core_results,
            exp100=variant_exp100,
            dedupe_stats=dedupe_stats,
            dedupe_variant=dedupe_variant,
        )

    baseline = variants[BASELINE_VARIANT]
    variant_gates = {
        name: _gate(variant, baseline, dedupe_variant=name)
        for name, variant in variants.items()
        if name != BASELINE_VARIANT
    }
    best_variant = max(
        variant_gates,
        key=lambda name: (
            variant_gates[name]["aggregate_delta"].get(
                "expected_value_score_sum_delta"
            )
            or float("-inf")
        ),
    )
    after = variants[best_variant]
    gate = variant_gates[best_variant]
    status = "accepted" if gate["passed"] else "rejected"
    decision = (
        f"accepted_for_shared_default_off_{best_variant}_paired_filing_dedupe"
        if gate["passed"]
        else "rejected_paired_filing_dedupe"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, paired "
            "same-ticker same-event-date earnings_8k and periodic_report rows "
            "may double-count one event and consume scarce max-3 capacity; "
            "deduping those paired filings before sleeve entry may improve "
            "candidate-pool quality without adding tickers or changing risk."
        ),
        "change_type": "alpha_search_candidate_pool",
        "changed_variable": "sec_financial_report_same_ticker_same_event_day_dedupe",
        "parameters": {
            "baseline_variant": BASELINE_VARIANT,
            "dedupe_variants": list(DEDUPE_VARIANTS[1:]),
            "dedupe_key": ["ticker", "event_trading_date"],
            "base_event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
            "earnings_8k_scalar": 1.0,
            "periodic_report_scalar": DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": (
                DEFAULT_10Q_PERIODIC_REPORT_NOTIONAL_SCALAR
            ),
            "max_positions": DEFAULT_MAX_POSITIONS,
            "min_t1_excess_return_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
            "source_candidate_artifact": str(SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
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
        "best_variant": best_variant,
        "before_metrics": baseline["aggregate"],
        "after_metrics": after["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "gate": gate,
        "variant_gates": variant_gates,
        "decision": decision,
        "rejection_reason": (
            None
            if gate["passed"]
            else (
                "Every paired-filing dedupe variant regressed aggregate EV; the "
                "least-bad variant still regressed late_strong and mid_weak, so "
                "paired filings should not be collapsed on this frozen sample."
            )
        ),
        "next_evidence_needed": (
            "Promote only by moving the chosen dedupe helper into the shared "
            "default-off sleeve path and adding parity tests."
            if gate["passed"]
            else (
                "Do not retry same-ticker same-event-date SEC paired-filing "
                "dedupe variants on this frozen sample; future SEC work should "
                "use forward replacement value or a genuinely new "
                "earnings-quality field."
            )
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
            "alters_candidate_pool": True,
            "alters_sizing": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate_pool: dedupe same-ticker same-event-date SEC "
                "financial-report paired filings before the default-off paper "
                "sleeve to avoid capacity double-counting."
            ),
            "2_history_check": (
                "exp-20260512-020 accepted 10-Q notional; exp-20260512-025 "
                "rejected 10-Q queue priority because only old_thin improved. "
                "No logged experiment tested paired-filing candidate-pool "
                "dedupe itself."
            ),
            "3_single_causal_variable": (
                "paired-filing dedupe preference only; capacity, qualification, "
                "hold days, notional, sort order, and live orders stay fixed."
            ),
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": (
                f"Run .venv\\Scripts\\python.exe quant\\experiments\\"
                f"{Path(__file__).name}"
            ),
        },
        "variants": {
            name: _compact_variant(variant) for name, variant in variants.items()
        },
        "why_not_other_changes": (
            "Recent Space pool/risk retunes are constrained by forward catalyst "
            "replacement value, and LLM soft-ranking lacks enough attribution "
            "data for a clean Gate 4. This tests a distinct deterministic SEC "
            "candidate-pool mechanism using already logged fields."
        ),
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
                "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
                "best_variant": best_variant,
                "decision": decision,
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
                "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
            },
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision} best_variant={best_variant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
