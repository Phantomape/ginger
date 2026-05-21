"""exp-20260521-003: event source-capacity scout.

Alpha search, replay-only. Tests one candidate-pool variable on top of the
accepted default-off event overlay: whether each event source should be allowed
more than one active paper event at a time.

No JavaScript is used. No shared policy, production adapter, core behavior,
LLM/news behavior, or live/default orders are changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260521_001_event_broad_breadth_adapter as current


EXPERIMENT_ID = "exp-20260521-003"
EXPERIMENT_SLUG = "event_source_capacity"

REPO_ROOT = current.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from experiments import exp_20260504_034_form4_satellite_overlay as form4_base  # noqa: E402
from experiments import exp_20260504_039_sec_governance_procedural_overlay as gov_base  # noqa: E402
from experiments import exp_20260504_049_default_off_event_overlay_bundle as base  # noqa: E402


OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "source_cap_1"
CAPACITY_VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted event overlay source capacity: at most one active paper position per source.",
                "per_source_active_capacity": 1,
            },
        ),
        (
            "source_cap_2",
            {
                "description": "Allow up to two active paper positions per source.",
                "per_source_active_capacity": 2,
            },
        ),
        (
            "source_cap_3",
            {
                "description": "Allow up to three active paper positions per source.",
                "per_source_active_capacity": 3,
            },
        ),
    ]
)


def _parent():
    return current._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _configure_modules() -> None:
    current._configure_modules()


def _load_source_inputs() -> dict[str, Any]:
    prices = base._load_price_map()

    form4_events, form4_path = base._load_form4_events(prices)
    form4_candidates = []
    for event in form4_events:
        trade = base.form4_candidate_trade(event, prices)
        if trade.get("status") == "price_ready":
            trade["source"] = "form4_meaningful_purchase"
            form4_candidates.append(trade)

    sec_negative_candidates, sec_negative_prices = base.build_sec_negative_candidates()
    for ticker, rows in sec_negative_prices.items():
        prices.setdefault(ticker, rows)
    sec_negative_trades = [
        trade
        for trade in (base._sec_negative_trade(row, prices) for row in sec_negative_candidates)
        if trade.get("status") == "price_ready"
    ]

    governance_candidates, governance_prices, governance_coverage = (
        base.build_sec_governance_candidates()
    )
    for ticker, rows in governance_prices.items():
        prices.setdefault(ticker, rows)

    return {
        "prices": prices,
        "form4_path": str(form4_path) if form4_path else None,
        "form4_candidates": form4_candidates,
        "sec_negative_trades": sec_negative_trades,
        "governance_candidates": governance_candidates,
        "governance_coverage": governance_coverage,
        "raw_counts": {
            "form4_price_ready_candidates": len(form4_candidates),
            "sec_negative_price_ready_candidates": len(sec_negative_trades),
            "sec_governance_deduped_candidates": len(governance_candidates),
        },
    }


def _select_form4_with_capacity(
    candidates: list[dict[str, Any]],
    *,
    start: str,
    end: str,
    max_active: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        row
        for row in candidates
        if start <= str(row.get("usable_trade_date") or "")[:10] <= end
    ]
    ready = [row for row in scoped if row.get("status") == "price_ready"]
    ready.sort(
        key=lambda row: (
            row["entry_date"],
            -float(row.get("total_purchase_value") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for row in ready:
        entry_date = row["entry_date"]
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if len(active) >= max_active:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "usable_trade_date": row.get("usable_trade_date"),
                    "entry_date": entry_date,
                    "window": row.get("window"),
                    "reason": "event_sleeve_capacity_full",
                    "source": "form4_meaningful_purchase",
                    "active_tickers": [trade.get("ticker") for trade in active],
                }
            )
            continue
        selected.append({**row, "source": "form4_meaningful_purchase"})
        active.append(row)
    return selected, skipped


def _select_sec_negative_with_capacity(
    candidates: list[dict[str, Any]],
    *,
    start: str,
    end: str,
    max_active: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        row
        for row in candidates
        if row.get("status") == "price_ready"
        and start <= str(row.get("entry_date") or "")[:10] <= end
    ]
    scoped.sort(
        key=lambda row: (
            row["entry_date"],
            float(row.get("reaction_excess_return") or 0.0),
            row["ticker"],
        )
    )
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for row in scoped:
        entry_date = str(row["entry_date"])[:10]
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if len(active) >= max_active:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "entry_date": entry_date,
                    "reason": "source_slot_full",
                    "source": "sec_negative_reaction",
                }
            )
            continue
        selected.append({**row, "source": "sec_negative_reaction"})
        active.append(row)
    return selected, skipped


def _select_governance_with_capacity(
    candidates: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    start: str,
    end: str,
    max_active: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [
        row
        for row in candidates
        if start <= str(row.get("entry_date") or "")[:10] <= end
    ]
    rows.sort(
        key=lambda item: (
            item["entry_date"],
            item["target_cell"],
            item["reaction_excess_return"],
            item["ticker"],
        )
    )
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    active_exits: list[str] = []
    for row in rows:
        entry_date = str(row["entry_date"])[:10]
        active_exits = [exit_date for exit_date in active_exits if exit_date >= entry_date]
        if len(active_exits) >= max_active:
            skipped.append(
                {
                    "ticker": row["ticker"],
                    "entry_date": entry_date,
                    "target_cell": row["target_cell"],
                    "reason": "slot_full",
                    "source": "sec_governance_procedural",
                }
            )
            continue
        horizon = row["horizons"][f"{base.HOLD_DAYS}d"]
        exit_date = str(horizon["end_date"])[:10]
        entry_row = gov_base._row_on(prices, row["ticker"], entry_date)
        exit_row = gov_base._row_on(prices, row["ticker"], exit_date)
        if not entry_row or not exit_row or not entry_row.get("open") or not exit_row.get("close"):
            skipped.append(
                {
                    "ticker": row["ticker"],
                    "entry_date": entry_date,
                    "target_cell": row["target_cell"],
                    "reason": "missing_price",
                    "source": "sec_governance_procedural",
                }
            )
            continue
        entry_open = float(entry_row["open"])
        exit_close = float(exit_row["close"])
        shares = base.EVENT_NOTIONAL / entry_open
        pnl = (
            shares * exit_close
            - base.EVENT_NOTIONAL
            - base.EVENT_NOTIONAL * base.ROUND_TRIP_COST_PCT
        )
        selected.append(
            {
                "ticker": row["ticker"],
                "window": row["window"],
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_open": round(entry_open, 4),
                "exit_close": round(exit_close, 4),
                "shares": shares,
                "notional": base.EVENT_NOTIONAL,
                "pnl": round(pnl, 2),
                "net_return_pct": round(pnl / base.EVENT_NOTIONAL, 6),
                "reaction_excess_return": row.get("reaction_excess_return"),
                "reaction_bucket": row.get("reaction_bucket"),
                "semantic_subcategory": row.get("semantic_subcategory"),
                "target_cell": row.get("target_cell"),
                "filing_count": row.get("filing_count"),
                "form_bases": row.get("form_bases"),
                "eight_k_item_codes": row.get("eight_k_item_codes"),
                "accession_numbers": row.get("accession_numbers"),
                "source": "sec_governance_procedural",
            }
        )
        active_exits.append(exit_date)
    return selected, skipped


def _select_event_trades_for_capacity(
    inputs: dict[str, Any],
    capacity: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    source_skips: dict[str, list[dict[str, Any]]] = {
        "form4_meaningful_purchase": [],
        "sec_negative_reaction": [],
        "sec_governance_procedural": [],
    }
    selected_counts: dict[str, Counter[str]] = OrderedDict()
    for label, window in base.WINDOWS.items():
        form4_selected, form4_skipped = _select_form4_with_capacity(
            inputs["form4_candidates"],
            start=window["start"],
            end=window["end"],
            max_active=capacity,
        )
        negative_selected, negative_skipped = _select_sec_negative_with_capacity(
            inputs["sec_negative_trades"],
            start=window["start"],
            end=window["end"],
            max_active=capacity,
        )
        governance_selected, governance_skipped = _select_governance_with_capacity(
            inputs["governance_candidates"],
            inputs["prices"],
            start=window["start"],
            end=window["end"],
            max_active=capacity,
        )
        source_skips["form4_meaningful_purchase"].extend(form4_skipped)
        source_skips["sec_negative_reaction"].extend(negative_skipped)
        source_skips["sec_governance_procedural"].extend(governance_skipped)

        rows = [*governance_selected, *negative_selected, *form4_selected]
        rows.sort(
            key=lambda row: (
                row["entry_date"],
                base.SOURCE_ORDER.get(row.get("source"), 99),
                row.get("ticker", ""),
            )
        )
        by_window[label] = rows
        selected_counts[label] = Counter(str(row.get("source") or "unknown") for row in rows)

    coverage = {
        "form4_source_path": inputs["form4_path"],
        **inputs["raw_counts"],
        "sec_governance_coverage": inputs["governance_coverage"],
        "selected_counts_by_window": {
            label: dict(counter) for label, counter in selected_counts.items()
        },
        "source_skipped_counts": {
            source: len(rows) for source, rows in source_skips.items()
        },
        "source_skipped_reason_counts": {
            source: dict(
                Counter(str(row.get("reason") or row.get("status") or "unknown") for row in rows)
            )
            for source, rows in source_skips.items()
        },
    }
    return by_window, coverage


def _accepted_event_scalar(trade: dict[str, Any]) -> float:
    scalar = current._accepted_event_scalar(trade)
    if current._is_broad_breadth_event(trade):
        scalar *= 1.25
    return scalar


def _scaled_trade(trade: dict[str, Any], variant_name: str, capacity: int) -> dict[str, Any]:
    scalar = _accepted_event_scalar(trade)
    base_notional = float(trade.get("notional") or base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "per_source_active_capacity": capacity,
        "accepted_event_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _trade_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("source") or ""),
        str(row.get("ticker") or "").upper(),
        str(row.get("entry_date") or "")[:10],
        str(row.get("exit_date") or "")[:10],
    )


def _max_positive_share(rows: list[dict[str, Any]]) -> float | None:
    positive = [float(row.get("pnl") or 0.0) for row in rows if float(row.get("pnl") or 0.0) > 0]
    total = sum(positive)
    if total <= 0:
        return None
    return round(max(positive) / total, 4)


def _incremental_summary(
    baseline_rows: dict[str, list[dict[str, Any]]],
    variant_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    baseline_keys = {
        label: {_trade_key(row) for row in rows} for label, rows in baseline_rows.items()
    }
    all_added: list[dict[str, Any]] = []
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    for label, rows in variant_rows.items():
        added = [row for row in rows if _trade_key(row) not in baseline_keys[label]]
        all_added.extend(added)
        by_window[label] = {
            "added_trade_count": len(added),
            "added_wins": sum(1 for row in added if float(row.get("pnl") or 0.0) > 0),
            "added_total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in added), 2),
            "added_tickers": sorted({str(row.get("ticker") or "") for row in added}),
            "added_by_source": dict(Counter(str(row.get("source") or "") for row in added)),
            "added_trades": [
                {
                    "source": row.get("source"),
                    "ticker": row.get("ticker"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get("exit_date"),
                    "pnl": row.get("pnl"),
                    "accepted_event_scalar": row.get("accepted_event_scalar"),
                    "state_surface": row.get("state_surface"),
                    "breadth_bucket": row.get("breadth_bucket"),
                    "dispersion_bucket": row.get("dispersion_bucket"),
                }
                for row in added
            ],
        }
    return {
        "added_trade_count": len(all_added),
        "added_windows_present": sum(1 for row in by_window.values() if row["added_trade_count"] > 0),
        "added_tickers": sorted({str(row.get("ticker") or "") for row in all_added}),
        "added_by_source": dict(Counter(str(row.get("source") or "") for row in all_added)),
        "added_wins": sum(1 for row in all_added if float(row.get("pnl") or 0.0) > 0),
        "added_win_rate": round(
            sum(1 for row in all_added if float(row.get("pnl") or 0.0) > 0) / len(all_added),
            4,
        )
        if all_added
        else None,
        "added_total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in all_added), 2),
        "added_max_single_positive_pnl_share": _max_positive_share(all_added),
        "by_window": by_window,
    }


def _gate_vs_baseline(
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    incremental: dict[str, Any],
) -> dict[str, Any]:
    gate = _parent().base._gate_summary(baseline_metrics, after_metrics)
    sample_ok = (
        (incremental.get("added_trade_count") or 0) >= 6
        and (incremental.get("added_windows_present") or 0) >= 2
        and len(incremental.get("added_tickers") or []) >= 4
        and (
            incremental.get("added_max_single_positive_pnl_share") is None
            or incremental["added_max_single_positive_pnl_share"] <= 0.50
        )
    )
    return {
        **gate,
        "sample_guard_passed": bool(sample_ok),
        "passed": bool(gate["passed"] and sample_ok),
        "sample_guard": {
            "min_added_trades": 6,
            "min_added_windows": 2,
            "min_added_tickers": 4,
            "max_added_single_positive_pnl_share": 0.50,
            "actual_added_trades": incremental.get("added_trade_count"),
            "actual_added_windows": incremental.get("added_windows_present"),
            "actual_added_tickers": incremental.get("added_tickers"),
            "actual_added_max_single_positive_pnl_share": incremental.get(
                "added_max_single_positive_pnl_share"
            ),
        },
    }


def _choose_best(gates: dict[str, dict[str, Any]]) -> str:
    names = [name for name in CAPACITY_VARIANTS if name != BASELINE_VARIANT]
    passed = [name for name in names if gates[name]["passed"]]
    candidates = passed if passed else names
    return max(
        candidates,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
            -CAPACITY_VARIANTS[name]["per_source_active_capacity"],
        ),
    )


def build_payload() -> dict[str, Any]:
    _configure_modules()
    parent = _parent()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inputs = _load_source_inputs()

    core_results = {
        label: parent.base._load_core_result(window)
        for label, window in parent.base.WINDOWS.items()
    }
    core_metrics = OrderedDict(
        (label, parent.base._core_metrics(result))
        for label, result in core_results.items()
    )

    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in CAPACITY_VARIANTS
    )
    variant_events: dict[str, dict[str, list[dict[str, Any]]]] = OrderedDict(
        (name, OrderedDict()) for name in CAPACITY_VARIANTS
    )
    coverage_by_variant: dict[str, dict[str, Any]] = OrderedDict()

    for name, variant in CAPACITY_VARIANTS.items():
        capacity = int(variant["per_source_active_capacity"])
        raw_by_window, coverage = _select_event_trades_for_capacity(inputs, capacity)
        enriched_by_window = parent.base._enrich_event_trades(raw_by_window)
        coverage_by_variant[name] = coverage
        for label, window in parent.base.WINDOWS.items():
            scaled = [
                _scaled_trade(trade, name, capacity)
                for trade in enriched_by_window[label]
            ]
            curve = parent.base._event_equity_curve(
                scaled,
                prices=inputs["prices"],
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = parent.base._combined_metrics(
                core_results[label],
                curve,
                scaled,
            )
            variant_events[name][label] = scaled

    baseline_metrics = variant_metrics[BASELINE_VARIANT]
    incremental_by_variant = OrderedDict(
        (
            name,
            _incremental_summary(
                variant_events[BASELINE_VARIANT],
                variant_events[name],
            ),
        )
        for name in CAPACITY_VARIANTS
    )
    gates_vs_baseline = OrderedDict(
        (
            name,
            _gate_vs_baseline(
                baseline_metrics,
                variant_metrics[name],
                incremental_by_variant[name],
            ),
        )
        for name in CAPACITY_VARIANTS
        if name != BASELINE_VARIANT
    )
    best_variant = _choose_best(gates_vs_baseline)
    best_gate = gates_vs_baseline[best_variant]
    passed = bool(best_gate["passed"])
    decision = (
        "promising_replay_only_event_source_capacity"
        if passed
        else "rejected_event_source_capacity"
    )
    rejection_reason = None
    if not passed:
        rejection_reason = (
            f"Best variant `{best_variant}` did not clear Gate 4: aggregate EV "
            f"delta {best_gate['delta']['aggregate_ev_delta']}, PnL delta "
            f"{best_gate['delta']['aggregate_pnl_delta']}, EV improved/regressed "
            f"{best_gate['delta']['windows_ev_improved']}/"
            f"{best_gate['delta']['windows_ev_regressed']}, "
            f"sample_guard_passed={best_gate['sample_guard_passed']}."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_candidate_pool_capacity_replay",
        "mechanism_family": "external_event_satellite_overlay_candidate_pool",
        "trial_family": "event_source_capacity_maturation",
        "trial_variant_id": "per_source_active_capacity",
        "changed_variable": "event_overlay_per_source_active_capacity",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260504-049",
            "exp-20260507-026",
            "exp-20260517-010",
            "exp-20260520-042",
            "exp-20260520-043",
            "exp-20260520-044",
            "exp-20260521-001",
            "exp-20260521-002",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_replacement_value_cohort",
        "hypothesis": (
            "The accepted default-off event overlay may be capacity constrained "
            "by one active paper position per source. Allowing a second or third "
            "active candidate per source could capture additional event "
            "replacement value without changing core trades or event semantics."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool / capital allocation",
            "entry_exit_ranking_or_allocation": "candidate_pool",
            "playbook_alignment": (
                "Uses a governed default-off event sleeve and replacement-value "
                "maturation path instead of LLM soft-ranking, state-surface "
                "scalar mining, or broad core universe expansion."
            ),
        },
        "single_causal_variable": (
            "per-source active paper event capacity; event definitions, ranking "
            "within each source, accepted front-rank/broad-breadth notional "
            "scalars, hold period, and core strategy stay fixed."
        ),
        "parameters": {
            "variants": CAPACITY_VARIANTS,
            "acceptance_baseline": BASELINE_VARIANT,
            "baseline_experiment": "exp-20260521-001",
            "base_event_notional_usd": base.EVENT_NOTIONAL,
            "hold_days": base.HOLD_DAYS,
            "round_trip_cost_pct": base.ROUND_TRIP_COST_PCT,
            "selected_capacity": CAPACITY_VARIANTS[best_variant]["per_source_active_capacity"],
            "sample_guard": {
                "min_added_trades": 6,
                "min_added_windows": 2,
                "min_added_tickers": 4,
                "max_added_single_positive_pnl_share": 0.50,
            },
            "anti_js": "No JavaScript was used.",
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "event source definitions",
                "event source thresholds",
                "event holding period",
                "front-rank rotation event scalar",
                "broad-breadth event scalar",
                "rotation event scalar",
                "non-rotation event scalar",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in parent.base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in parent.base.WINDOWS.items()
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Event source capacity may be suppressing replacement value; "
                "this is candidate-pool/capital allocation and follows the "
                "event-rotation maturation lane."
            ),
            "2_history_check": (
                "The all-source event overlay and front-rank/broad-breadth "
                "fields passed in exp049/026/017-010/020-044/021-001. "
                "High-dispersion context failed in exp-20260521-002. This tests "
                "source capacity, not another context notional scalar."
            ),
            "3_single_causal_variable": (
                "Only per-source active event paper capacity changes from 1 to "
                "2 or 3; all source definitions and accepted notional scalars "
                "stay locked."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "accepted exp-20260521-001 baseline, require aggregate EV/PnL "
                "improvement, no EV-regressed window, incremental sample guard "
                "pass, and no production/backtest divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260521_003_event_source_capacity.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260504-049": "Established the all-source default-off event overlay at capacity 1.",
            "exp-20260507-026": "Added non-generic positive state-surface event notional evidence.",
            "exp-20260517-010": "Revalidated event rotation after the latest accepted core stack.",
            "exp-20260520-044": "Promoted front-rank event rotation into the shared default-off adapter.",
            "exp-20260521-001": "Accepted broad-breadth event context in the shared default-off adapter.",
            "exp-20260521-002": "Rejected high-dispersion context due old_thin EV/PnL regression.",
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window replay "
                "plus default-off event paper overlay accounting"
            ),
            "windows": parent.base.WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "event_overlay": "default_off_paper_replay",
            },
        },
        "gate1": {
            "baseline_name": BASELINE_VARIANT,
            "baseline_metrics": baseline_metrics,
            "baseline_artifact": "data/experiments/exp-20260521-001/event_broad_breadth_adapter.json",
        },
        "gate2": {
            "required_fields": [
                "source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                "state_feature_available",
                "state_score_positive",
                "state_surface",
                "breadth_bucket",
                "dispersion_bucket",
            ],
            "baseline_selected_counts": coverage_by_variant[BASELINE_VARIANT][
                "selected_counts_by_window"
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_changed": True,
            "survival_impact": (
                "not applicable to default-off event paper overlay; core signals "
                "and survival are unchanged"
            ),
            "passed": True,
        },
        "gate4": {
            **best_gate,
            "basis": (
                "Three canonical docs/backtesting.md windows, primary comparison "
                "against the accepted exp-20260521-001 event broad-breadth baseline."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            BASELINE_VARIANT: baseline_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {"variant_vs_source_cap_1": gates_vs_baseline},
        "best_variant": best_variant,
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "incremental_selection": incremental_by_variant,
        "coverage": coverage_by_variant,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_orders_enabled": False,
            "promotion_blocker_if_positive": (
                "A positive source-capacity result still needs shared source "
                "queue capacity wiring, adapter parity tests, and closed forward "
                "replacement-value evidence before any live/default capital."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains attribution/sample-limited; this uses "
                "deterministic PIT event queues and state-surface fields only."
            ),
        },
        "decision_rationale": (
            "Promising replay-only: source capacity improved the accepted event "
            "overlay baseline without an EV-regressed window and passed the "
            "incremental sample guard. It is not a production promotion."
            if passed
            else "Rejected: source capacity did not clear the three-window EV-first gate."
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Do not promote source capacity without shared queue wiring and "
            "closed forward replacement-value evidence; avoid nearby capacity "
            "retries on the frozen sample if Gate 4 failed."
            if not passed
            else "Use this only as scout evidence; next valid step is shared default-off queue capacity parity plus forward replacement-value tracking."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking and SEC/buyback semantic fields due sample "
            "and provenance limits; skipped state-surface/broad-market nearby "
            "retunes due anti-repeat rules; skipped high-dispersion event context "
            "because exp-20260521-002 just failed old_thin."
        ),
        "risk_of_change": (
            "Replay-only scout. Increasing event source capacity can add "
            "correlated event exposure and may overstate robustness before "
            "forward replacement-value evidence matures."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["gate4"]
    baseline = payload["before_metrics"][BASELINE_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event Source-Capacity Scout",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Tests whether the accepted default-off "
            "event overlay is capacity constrained by one active paper position "
            "per source."
        ),
        "",
        "## Gate 4 Result",
        "",
        "| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _parent().base.WINDOWS:
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=baseline[label]["expected_value_score"],
                aev=after[label]["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=baseline[label]["total_pnl"],
                apnl=after[label]["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Sweep",
            "",
            "| Variant | Passed | dEV | dPnL | Improved | Regressed | Added trades | Added windows | Added PnL | Max positive share |",
            "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, row in payload["delta_metrics"]["variant_vs_source_cap_1"].items():
        selection = payload["incremental_selection"][name]
        lines.append(
            "| {name} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {trades} | {windows} | ${added_pnl:+,.2f} | {share} |".format(
                name=name,
                passed="yes" if row["passed"] else "no",
                dev=row["delta"]["aggregate_ev_delta"],
                dpnl=row["delta"]["aggregate_pnl_delta"],
                improved=row["delta"]["windows_ev_improved"],
                regressed=row["delta"]["windows_ev_regressed"],
                trades=selection["added_trade_count"],
                windows=selection["added_windows_present"],
                added_pnl=selection["added_total_pnl"],
                share=selection["added_max_single_positive_pnl_share"],
            )
        )
    lines.extend(
        [
            "",
            "## Incremental Selection",
            "",
            "```json",
            json.dumps(payload["incremental_selection"][best], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay only. No shared policy, production adapter, production "
                "report, core behavior, or live/default order path changed."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "lane",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "hypothesis",
        "alpha_hypothesis",
        "single_causal_variable",
        "parameters",
        "date_range",
        "market_regime_summary",
        "gate_questions",
        "historical_experiment_check",
        "backtest_protocol",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "best_variant",
        "expected_value_score_delta",
        "total_pnl_delta",
        "incremental_selection",
        "production_impact",
        "llm_metrics",
        "decision_rationale",
        "rejection_reason",
        "next_action",
        "why_not_other_attractive_points",
        "risk_of_change",
        "related_files",
        "anti_js",
    ]
    return {key: payload.get(key) for key in keys}


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    compact = _compact_log(payload)
    _write_json(LOG_JSON, compact)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event source-capacity scout",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(_safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    best = payload["best_variant"]
    gate = payload["gate4"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_variant": best,
                    "ev_delta_vs_source_cap_1": gate["delta"]["aggregate_ev_delta"],
                    "pnl_delta_vs_source_cap_1": gate["delta"]["aggregate_pnl_delta"],
                    "windows_ev_improved": gate["delta"]["windows_ev_improved"],
                    "windows_ev_regressed": gate["delta"]["windows_ev_regressed"],
                    "sample_guard_passed": gate["sample_guard_passed"],
                    "incremental_selection": payload["incremental_selection"][best],
                    "out_json": str(OUT_JSON),
                    "anti_js": "No JavaScript was used.",
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
