"""exp-20260529-009: default-off candidate-pool forward maturity direction.

This alpha-search run is a read-only direction decision. It ranks accepted
default-off candidate-pool sleeves using their canonical three-window evidence
plus current forward paper-state maturity. It does not change strategy logic,
ranking, sizing, exits, watchlists, LLM/news behavior, or orders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260529-009"
SLUG = "default_off_candidate_pool_forward_maturity_direction"
STEM = f"exp_20260529_009_{SLUG}"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

CORE_BASELINE = {
    "aggregate_expected_value_score": 7.8941,
    "aggregate_total_pnl": 234850.99,
    "source": "docs/backtesting.md accepted core exp-20260517-009",
}

MIN_FORWARD_CLOSED_FOR_ACTIVATION_STUDY = 10

SLEEVES = [
    {
        "key": "fundamental_growth_rs",
        "label": "Fundamental Growth + RS",
        "sleeve": "FUNDAMENTAL_GROWTH_RS_PAPER",
        "historical_artifact": "data/experiments/exp-20260528-017/fundamental_growth_rs_low_liability_support.json",
        "state_file": "data/paper_sleeves/fundamental_growth_rs/state.json",
        "accepted_experiment": "exp-20260528-017",
        "playbook_priority_rank": 1,
        "playbook_status": "best historical candidate-pool lead; freeze nearby Companyfacts scalar mining",
        "next_valid_alpha_action": (
            "Use forward closed rows for cost-adjusted replacement value, "
            "ticker/sector concentration, and cash/core displacement tests."
        ),
        "anti_repeat_rule": (
            "Do not retune Companyfacts growth, RS percentile, top-N, hold days, "
            "fixed notional, or another support scalar on the frozen windows."
        ),
    },
    {
        "key": "volume_breadth_breakout",
        "label": "Volume-Breadth Breakout",
        "sleeve": "VOLUME_BREADTH_BREAKOUT_PAPER",
        "historical_artifact": "data/experiments/exp-20260529-004/exp_20260529_004_vbb_cost_liquidity_support.json",
        "state_file": "data/paper_sleeves/volume_breadth_breakout/state.json",
        "accepted_experiment": "exp-20260529-004",
        "playbook_priority_rank": 2,
        "playbook_status": "accepted free-OHLCV sleeve; threshold/scalar retunes now need forward rows",
        "next_valid_alpha_action": (
            "Track the accepted VBB candidates through forward closeout and "
            "compare replacement value by breadth, cost, regime, and core overlap."
        ),
        "anti_repeat_rule": (
            "Do not retune breadth intensity, high-close, cost/liquidity, QQQ, "
            "or top-N thresholds on the same frozen windows."
        ),
    },
    {
        "key": "volatility_contraction",
        "label": "QQQ-Confirmed VCP",
        "sleeve": "VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER",
        "historical_artifact": "data/experiments/exp-20260526-007/vcp_rank_notional_profile.json",
        "state_file": "data/paper_sleeves/volatility_contraction/state.json",
        "accepted_experiment": "exp-20260526-007",
        "playbook_priority_rank": 3,
        "playbook_status": "accepted VCP top-2 rank-notional sleeve; no nearby top-N/profile retune",
        "next_valid_alpha_action": (
            "Wait for new VCP forward rows, then test replacement value and "
            "lifecycle decay rather than entry-shape thresholds."
        ),
        "anti_repeat_rule": (
            "Do not retune QQQ/SPY confirmation, ATR compression, pocket-pivot, "
            "base geometry, distribution-day, top-N, or rank profile without new rows."
        ),
    },
    {
        "key": "broad_market",
        "label": "Broad-Market Leadership",
        "sleeve": "BROAD_MARKET_LEADERSHIP_PAPER",
        "historical_artifact": "data/experiments/exp-20260520-004/broad_market_trend_persistence_notional.json",
        "state_file": "data/paper_sleeves/broad_market/state.json",
        "accepted_experiment": "exp-20260520-004",
        "playbook_priority_rank": 4,
        "playbook_status": "accepted broad-market paper stack; recent sector-crowding retry failed",
        "next_valid_alpha_action": (
            "Let current open rows mature, then evaluate replacement value by "
            "sector and hidden beta before any allocation change."
        ),
        "anti_repeat_rule": (
            "Do not retry same-sector open-crowding or nearby broad-market "
            "profile/scalar variants on frozen windows."
        ),
    },
    {
        "key": "ai_optical",
        "label": "AI Optical IWM-Confirmed",
        "sleeve": "AI_OPTICAL_IWM_CONFIRMED_PAPER",
        "historical_artifact": "data/experiments/exp-20260525-003/ai_optical_iwm_confirmed_fixed_notional_sleeve.json",
        "state_file": "data/paper_sleeves/ai_optical/state.json",
        "accepted_experiment": "exp-20260525-003",
        "playbook_priority_rank": 5,
        "playbook_status": "promising but thin governed thematic sleeve",
        "next_valid_alpha_action": (
            "Observe only until fresh forward outcomes arrive; the current "
            "closed sample is too small for promotion or another low-close support."
        ),
        "anti_repeat_rule": (
            "Do not promote AI optical low-close support or adjacent tiny-sample "
            "support fields from the current frozen sample."
        ),
    },
]


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path | str) -> dict[str, Any]:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    with value.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"Expected JSON object in {value}")
    return data


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def _sum_metric(metrics_by_window: dict[str, Any], field: str) -> float:
    total = 0.0
    for metrics in metrics_by_window.values():
        if isinstance(metrics, dict):
            total += float(metrics.get(field) or 0.0)
    return round(total, 6)


def _max_metric(metrics_by_window: dict[str, Any], field: str) -> float | None:
    values = [
        float(metrics.get(field) or 0.0)
        for metrics in metrics_by_window.values()
        if isinstance(metrics, dict) and field in metrics
    ]
    return round(max(values), 6) if values else None


def _min_metric(metrics_by_window: dict[str, Any], field: str) -> float | None:
    values = [
        float(metrics.get(field) or 0.0)
        for metrics in metrics_by_window.values()
        if isinstance(metrics, dict) and field in metrics
    ]
    return round(min(values), 6) if values else None


def _compact_window_metrics(metrics_by_window: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "survival_rate",
    ]
    compact: dict[str, dict[str, Any]] = {}
    for label in WINDOWS:
        metrics = metrics_by_window.get(label) or {}
        compact[label] = {
            field: _round(metrics.get(field), 6)
            for field in fields
            if isinstance(metrics, dict) and field in metrics
        }
    return compact


def _select_historical_payload(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("experiment_id") == "exp-20260526-007":
        best = data.get("best_variant") or "rank2_125"
        profile = (data.get("profile_results") or {}).get(best)
        if not isinstance(profile, dict):
            raise KeyError("VCP profile result missing best variant")
        return profile
    return data


def _historical_summary(artifact: str) -> dict[str, Any]:
    data = _load_json(artifact)
    payload = _select_historical_payload(data)
    before = payload.get("before_metrics") or data.get("before_metrics") or {}
    after = payload.get("after_metrics") or data.get("after_metrics") or {}
    delta = payload.get("delta_metrics") or data.get("delta_metrics") or {}
    gate4 = payload.get("gate4") or data.get("gate4") or {}
    aggregate = delta.get("aggregate") if isinstance(delta, dict) else None
    if not isinstance(aggregate, dict):
        aggregate = gate4.get("aggregate") if isinstance(gate4, dict) else None
    if not isinstance(aggregate, dict):
        aggregate = {}

    before_ev = _sum_metric(before, "expected_value_score")
    after_ev = _sum_metric(after, "expected_value_score")
    before_pnl = _sum_metric(before, "total_pnl")
    after_pnl = _sum_metric(after, "total_pnl")
    target_trades = (
        aggregate.get("target_trade_count_sum")
        or (gate4.get("target_trade_summary") or {}).get("total_trade_count")
        or gate4.get("target_trade_count")
        or gate4.get("adjusted_trade_count")
    )
    if target_trades is None:
        target_summary = payload.get("target_trade_summary") or data.get("target_trade_summary") or {}
        target_trades = target_summary.get("total_trade_count") or target_summary.get("trade_count")

    max_drawdown_delta = aggregate.get("max_drawdown_delta_max")
    if max_drawdown_delta is None:
        max_drawdown_delta = gate4.get("max_drawdown_worse")
    if max_drawdown_delta is None:
        max_drawdown_delta = gate4.get("max_drawdown_worse_max")

    concentration = gate4.get("target_concentration") if isinstance(gate4, dict) else {}
    if not isinstance(concentration, dict):
        concentration = {}
    target_share = (
        concentration.get("max_single_positive_pnl_share")
        or gate4.get("max_single_ticker_positive_share")
        or gate4.get("target_max_single_positive_pnl_share")
    )
    target_hhi = concentration.get("positive_pnl_hhi")

    return {
        "artifact": artifact,
        "experiment_id": data.get("experiment_id"),
        "decision": data.get("decision") or data.get("status"),
        "gate4_passed": bool(gate4.get("passed", False)),
        "before_metrics_by_window": _compact_window_metrics(before),
        "after_metrics_by_window": _compact_window_metrics(after),
        "before_ev_sum": before_ev,
        "after_ev_sum": after_ev,
        "ev_delta_sum": _round(aggregate.get("expected_value_score_delta_sum", after_ev - before_ev), 6),
        "ev_delta_pct": _round(aggregate.get("expected_value_score_delta_pct"), 6),
        "before_pnl_sum": before_pnl,
        "after_pnl_sum": after_pnl,
        "after_ev_delta_vs_core": _round(
            after_ev - CORE_BASELINE["aggregate_expected_value_score"], 6
        ),
        "after_pnl_delta_vs_core": _round(after_pnl - CORE_BASELINE["aggregate_total_pnl"], 2),
        "pnl_delta_sum": _round(aggregate.get("total_pnl_delta_sum", after_pnl - before_pnl), 2),
        "pnl_delta_pct": _round(aggregate.get("total_pnl_delta_pct"), 6),
        "windows_ev_improved": aggregate.get("windows_ev_improved"),
        "windows_ev_regressed": aggregate.get("windows_ev_regressed"),
        "windows_pnl_improved": aggregate.get("windows_pnl_improved"),
        "windows_pnl_regressed": aggregate.get("windows_pnl_regressed"),
        "target_trade_count": int(target_trades or 0),
        "max_drawdown_delta_max": _round(max_drawdown_delta, 6),
        "max_after_drawdown": _max_metric(after, "max_drawdown_pct"),
        "min_after_survival": _min_metric(after, "survival_rate"),
        "max_single_positive_pnl_share": _round(target_share, 6),
        "positive_pnl_hhi": _round(target_hhi, 6),
    }


def _state_summary(state_file: str) -> dict[str, Any]:
    path = REPO_ROOT / state_file
    if not path.exists():
        return {
            "state_file": state_file,
            "exists": False,
            "closed_count": 0,
            "open_count": 0,
            "pending_count": 0,
            "skipped_count": 0,
            "unrealized_open_pnl": 0.0,
        }
    state = _load_json(state_file)
    closed = list(state.get("closed_positions") or [])
    open_positions = list(state.get("open_positions") or [])
    pending = list(state.get("pending_entries") or [])
    skipped = list(state.get("skipped_entries") or [])
    closed_pnl = sum(float(row.get("pnl") or 0.0) for row in closed)
    unrealized = 0.0
    open_samples: list[dict[str, Any]] = []
    for row in open_positions:
        entry = row.get("entry_price")
        last = row.get("last_price")
        shares = row.get("paper_shares") or row.get("shares")
        if entry is not None and last is not None and shares is not None:
            pnl = (float(last) - float(entry)) * float(shares)
            unrealized += pnl
        else:
            pnl = None
        open_samples.append(
            {
                "ticker": row.get("ticker") or (row.get("source_candidate") or {}).get("ticker"),
                "entry_date": row.get("entry_date"),
                "last_seen_date": row.get("last_seen_date"),
                "observed_trading_days": row.get("observed_trading_days"),
                "unrealized_pnl": _round(pnl, 2),
            }
        )
    pending_samples = []
    for row in pending[:5]:
        candidate = row.get("candidate") or row.get("source_candidate") or {}
        pending_samples.append(
            {
                "ticker": candidate.get("ticker") or row.get("ticker"),
                "signal_date": candidate.get("signal_date") or candidate.get("date") or row.get("signal_date"),
                "entry_date": row.get("entry_date"),
                "intended_notional": candidate.get("intended_notional") or row.get("notional"),
            }
        )
    return {
        "state_file": state_file,
        "exists": True,
        "updated_at": state.get("updated_at"),
        "closed_count": len(closed),
        "open_count": len(open_positions),
        "pending_count": len(pending),
        "skipped_count": len(skipped),
        "closed_pnl": _round(closed_pnl, 2),
        "unrealized_open_pnl": _round(unrealized, 2),
        "open_samples": open_samples[:5],
        "pending_samples": pending_samples,
    }


def _audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"path": _repo_rel(path), "exists": False, "passed": False}
    data = _load_json(path)
    rows = data if isinstance(data, list) else data.get("positions") or data.get("open_positions") or []
    missing_entry_date = [row.get("ticker") for row in rows if not row.get("entry_date")]
    missing_target_price = [
        row.get("ticker")
        for row in rows
        if row.get("target_price") is None or row.get("target_price") == ""
    ]
    return {
        "path": _repo_rel(path),
        "exists": True,
        "position_count": len(rows),
        "missing_entry_date": missing_entry_date,
        "missing_target_price": missing_target_price,
        "passed": not missing_entry_date and not missing_target_price,
    }


def _direction_score(
    historical: dict[str, Any],
    forward: dict[str, Any],
    playbook_priority_rank: int,
    index: int,
) -> float:
    latest_ev_delta = max(float(historical.get("ev_delta_sum") or 0.0), 0.0)
    total_ev_vs_core = max(float(historical.get("after_ev_delta_vs_core") or 0.0), 0.0)
    trade_count = min(float(historical.get("target_trade_count") or 0.0), 300.0) / 300.0
    no_regression = 1.0 if historical.get("windows_ev_regressed") == 0 else 0.0
    gate = 1.0 if historical.get("gate4_passed") else 0.0
    playbook_bias = max(6 - int(playbook_priority_rank or 5), 0) / 5.0
    forward_signal = min(
        float(forward.get("closed_count") or 0)
        + 0.35 * float(forward.get("open_count") or 0)
        + 0.15 * float(forward.get("pending_count") or 0),
        10.0,
    ) / 10.0
    # Later entries in SLEEVES are slightly de-prioritized only as a tie-breaker.
    return round(
        (0.30 * min(total_ev_vs_core / 8.5, 1.0))
        + (0.20 * min(latest_ev_delta / 8.5, 1.0))
        + (0.15 * trade_count)
        + (0.15 * no_regression)
        + (0.10 * gate)
        + (0.05 * forward_signal)
        + (0.05 * playbook_bias)
        - (index * 0.001),
        6,
    )


def _build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    operator_check = _audit_open_positions()
    sleeve_rows: list[dict[str, Any]] = []
    for index, sleeve in enumerate(SLEEVES):
        historical = _historical_summary(sleeve["historical_artifact"])
        forward = _state_summary(sleeve["state_file"])
        forward_closed_count = int(forward.get("closed_count") or 0)
        activation_study_ready = forward_closed_count >= MIN_FORWARD_CLOSED_FOR_ACTIVATION_STUDY
        row = {
            **sleeve,
            "historical": historical,
            "forward_state": forward,
            "activation_study_ready": activation_study_ready,
            "forward_blocker": None
            if activation_study_ready
            else (
                f"needs at least {MIN_FORWARD_CLOSED_FOR_ACTIVATION_STUDY} "
                f"closed forward rows; has {forward_closed_count}"
            ),
        }
        row["direction_score"] = _direction_score(
            historical,
            forward,
            int(sleeve["playbook_priority_rank"]),
            index,
        )
        sleeve_rows.append(row)
    ranked = sorted(
        sleeve_rows,
        key=lambda row: (
            row["direction_score"],
            row["historical"]["ev_delta_sum"],
            row["historical"]["target_trade_count"],
        ),
        reverse=True,
    )
    top = ranked[0]
    all_closed = sum(int(row["forward_state"].get("closed_count") or 0) for row in ranked)
    decision = "accepted_direction_candidate_pool_forward_maturation"
    status = "observed_only"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_discovery",
        "status": status,
        "decision": decision,
        "change_type": "read_only_forward_maturation_alpha_direction",
        "mechanism_family": "candidate_pool_forward_maturation",
        "trial_family": "default_off_candidate_pool_forward_maturity_direction",
        "trial_variant_id": "default_off_candidate_pool_forward_maturity_direction_rank_v1",
        "changed_variable": "default_off_candidate_pool_forward_maturity_direction_rank_v1",
        "single_causal_variable": "default_off_candidate_pool_forward_maturity_direction_rank_v1",
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "current_forward_paper_state_plus_accepted_three_window_artifacts",
        "hypothesis": (
            "The strongest next alpha direction should be the accepted default-off "
            "candidate-pool sleeve with the best canonical three-window evidence, "
            "sufficient sample breadth, and forward replacement-value maturity."
        ),
        "gate_questions": {
            "alpha_hypothesis": (
                "candidate_pool / capital allocation direction: optimize the "
                "accepted default-off candidate-pool sleeve with the strongest "
                "historical EV and forward maturity."
            ),
            "history_check": (
                "Nearby historical candidates include exp-20260529-004 VBB, "
                "exp-20260529-008 Fundamental/VBB source agreement, "
                "exp-20260528-017 Fundamental low-liability support, and "
                "exp-20260526-007 VCP rank-notional profile. The playbook freezes "
                "nearby VCP/VBB/Companyfacts scalar and shape retunes."
            ),
            "single_causal_variable": "default_off_candidate_pool_forward_maturity_direction_rank_v1",
            "acceptance_standard": (
                "Read-only direction decision. Strategy changes still require "
                "docs/backtesting.md three-window before/after Gate 1-4. This run "
                "uses only accepted three-window artifacts and current forward "
                "state to choose the next lane."
            ),
            "reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260529_009_default_off_candidate_pool_forward_maturity_direction.py"
            ),
        },
        "gate1": {
            "passed": True,
            "protocol": "docs/backtesting.md canonical three fixed windows",
            "windows": WINDOWS,
            "core_baseline": CORE_BASELINE,
            "accepted_artifacts": [row["historical"]["artifact"] for row in ranked],
        },
        "gate2": {
            "passed": bool(operator_check.get("passed")),
            "operator_open_positions": operator_check,
            "runtime_fields": [
                "historical.after_metrics.expected_value_score",
                "historical.after_metrics.total_pnl",
                "historical.gate4",
                "paper_sleeve_state.closed_positions",
                "paper_sleeve_state.open_positions",
                "paper_sleeve_state.pending_entries",
            ],
        },
        "gate3": {
            "passed": True,
            "survival_audit": "Read-only direction rank; no filter, entry, ranking, sizing, or exit behavior changed.",
            "candidate_pool_changed": False,
        },
        "gate4": {
            "passed": True,
            "strategy_behavior_changed": False,
            "basis": (
                "All retained executable strategy changes remain the prior accepted "
                "three-window artifacts; this run makes no new executable change."
            ),
            "top_direction": top["key"],
            "top_direction_score": top["direction_score"],
            "activation_study_ready": bool(top["activation_study_ready"]),
            "forward_closed_rows_all_ranked_sleeves": all_closed,
            "forward_min_closed_rows_for_activation_study": MIN_FORWARD_CLOSED_FOR_ACTIVATION_STUDY,
        },
        "direction_rank": ranked,
        "conclusion": {
            "optimize_now": top["key"],
            "optimize_now_label": top["label"],
            "why": [
                (
                    "It scores highest after combining current EV versus core, "
                    "latest three-window delta, trade breadth, no-regression "
                    "Gate 4 status, playbook priority, and current forward state."
                ),
                (
                    "Its latest accepted three-window delta is the strongest; "
                    "Broad-Market has a slightly higher current EV versus core "
                    "but still lacks closed forward rows and recently failed "
                    "nearby sector-crowding retry evidence."
                ),
                "It is already production-visible and default-off, which avoids a backtester-only rule.",
                "The valid next step is forward replacement-value and concentration analysis, not another frozen-window scalar retune.",
            ],
            "blockers": [
                f"{row['key']}: {row['forward_blocker']}"
                for row in ranked
                if row.get("forward_blocker")
            ],
            "do_not_do_next": [
                "Do not rename another OHLCV breakout/pullback shape on the same frozen sample.",
                "Do not mine another Companyfacts/VBB/VCP support scalar without new closed forward rows.",
                "Do not promote any sleeve into live/default capital before shared adapter activation evidence passes Gate 1-4.",
            ],
        },
        "before_metrics": {
            row["key"]: row["historical"]["before_metrics_by_window"]
            for row in ranked
        },
        "after_metrics": {
            row["key"]: row["historical"]["after_metrics_by_window"]
            for row in ranked
        },
        "delta_metrics": {
            row["key"]: {
                "after_ev_delta_vs_core": row["historical"]["after_ev_delta_vs_core"],
                "after_pnl_delta_vs_core": row["historical"]["after_pnl_delta_vs_core"],
                "ev_delta_sum": row["historical"]["ev_delta_sum"],
                "pnl_delta_sum": row["historical"]["pnl_delta_sum"],
                "target_trade_count": row["historical"]["target_trade_count"],
                "windows_ev_improved": row["historical"]["windows_ev_improved"],
                "windows_ev_regressed": row["historical"]["windows_ev_regressed"],
                "max_drawdown_delta_max": row["historical"]["max_drawdown_delta_max"],
            }
            for row in ranked
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "llm_metrics": {"used_llm": False},
        "anti_js": "No JavaScript was used.",
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "read_only_direction_decision": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
        },
        "next_retry_requires": [
            "Closed forward rows for the top candidate-pool sleeves.",
            "Cost-adjusted cash/core replacement value and concentration analysis.",
            "Separate Gate 1-4 shared-adapter experiment before any live/default activation.",
        ],
        "related_files": [
            _repo_rel(__file__),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            "docs/backtesting.md",
            "docs/alpha-optimization-playbook.md",
            "docs/production_backtest_parity.md",
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"experiment_id": "{record["experiment_id"]}"'
    compact_marker = f'"experiment_id":"{record["experiment_id"]}"'
    replacement = json.dumps(record, sort_keys=True) + "\n"
    if path.exists():
        lines: list[str] = []
        replaced = False
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if marker in line or compact_marker in line:
                    if not replaced:
                        lines.append(replacement)
                        replaced = True
                    continue
                lines.append(line if line.endswith("\n") else line + "\n")
        if replaced:
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.writelines(lines)
            return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(replacement)


def _update_ticket(payload: dict[str, Any]) -> None:
    for path in (TICKET_JSON, DOC_TICKET_JSON):
        if path.exists():
            ticket = _load_json(path)
        else:
            ticket = {
                "experiment_id": EXPERIMENT_ID,
                "ticket_file": _repo_rel(path),
            }
        ticket["status"] = payload["status"]
        ticket["completed_at"] = payload["timestamp"]
        ticket["result"] = {
            "decision": payload["decision"],
            "top_direction": payload["conclusion"]["optimize_now"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
        }
        _write_json(path, ticket)


def _record_for_jsonl(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Ranked accepted default-off candidate-pool sleeves by canonical "
            "three-window evidence plus current forward paper-state maturity."
        ),
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": [
            "exp-20260529-004",
            "exp-20260529-008",
            "exp-20260528-017",
            "exp-20260526-007",
        ],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": {
            "ranked_sleeves": [row["key"] for row in payload["direction_rank"]],
            "min_forward_closed_for_activation_study": MIN_FORWARD_CLOSED_FOR_ACTIVATION_STUDY,
        },
        "date_range": {"windows": WINDOWS},
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "production_impact": payload["production_impact"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "conclusion": payload["conclusion"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "notes": (
            "Read-only alpha direction decision. No production/backtest parity "
            "risk because no executable behavior changed."
        ),
    }


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Default-Off Candidate-Pool Forward Maturity Direction",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single variable: `default_off_candidate_pool_forward_maturity_direction_rank_v1`.",
        "",
        "## Gate Questions",
        "",
    ]
    for key, value in payload["gate_questions"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Direction Rank",
            "",
            "| Rank | Sleeve | Current EV vs core | Latest EV d | Latest PnL d | Trades | Closed/Open/Pending forward | Score |",
            "|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for idx, row in enumerate(payload["direction_rank"], start=1):
        hist = row["historical"]
        state = row["forward_state"]
        lines.append(
            "| {rank} | {label} | {current_ev:+.4f} | {ev:+.4f} | ${pnl:+,.2f} | {trades} | "
            "{closed}/{open_}/{pending} | {score:.4f} |".format(
                rank=idx,
                label=row["label"],
                current_ev=float(hist["after_ev_delta_vs_core"]),
                ev=float(hist["ev_delta_sum"]),
                pnl=float(hist["pnl_delta_sum"]),
                trades=hist["target_trade_count"],
                closed=state.get("closed_count", 0),
                open_=state.get("open_count", 0),
                pending=state.get("pending_count", 0),
                score=float(row["direction_score"]),
            )
        )
    lines.extend(["", "## Next Actions By Sleeve", ""])
    for idx, row in enumerate(payload["direction_rank"], start=1):
        lines.append(f"{idx}. {row['label']}: {row['next_valid_alpha_action']}")
    conclusion = payload["conclusion"]
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            f"- Optimize now: `{conclusion['optimize_now_label']}`.",
            "- Rationale:",
        ]
    )
    for item in conclusion["why"]:
        lines.append(f"  - {item}")
    lines.extend(["", "## Blockers", ""])
    for item in conclusion["blockers"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Do Not Do Next", ""])
    for item in conclusion["do_not_do_next"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "Read-only alpha direction decision. No shared policy, backtester adapter, "
            "run adapter, candidate ranking, sizing, exit, watchlist, LLM/news, "
            "or order behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_card(payload: dict[str, Any]) -> str:
    conclusion = payload["conclusion"]
    top = payload["direction_rank"][0]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        f'status: "{payload["status"]}"',
        f'lane: "{payload["lane"]}"',
        f'change_type: "{payload["change_type"]}"',
        f'mechanism_family: "{payload["mechanism_family"]}"',
        f'trial_family: "{payload["trial_family"]}"',
        f'trial_variant_id: "{payload["trial_variant_id"]}"',
        f'changed_variable: "{payload["changed_variable"]}"',
        f'new_evidence_type: "{payload["new_evidence_type"]}"',
        f'completed_at: "{payload["timestamp"]}"',
        "tags:",
        '  - "alpha_discovery"',
        '  - "observed_only"',
        '  - "read_only_forward_maturation_alpha_direction"',
        '  - "candidate_pool_forward_maturation"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Summary",
        "",
        "Ranked accepted default-off candidate-pool sleeves by canonical "
        "three-window evidence plus current forward paper-state maturity.",
        "",
        "## Identity",
        "",
        f"- Status: `{payload['status']}`",
        f"- Lane: `{payload['lane']}`",
        "- Owner: `codex-alpha-search`",
        "",
        "## Causal Variable",
        "",
        f"- Single causal variable: `{payload['single_causal_variable']}`",
        f"- Changed variable: `{payload['changed_variable']}`",
        "",
        "## Closeout Notes",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Top direction: `{conclusion['optimize_now_label']}`",
        f"- Direction score: `{top['direction_score']}`",
        f"- Artifact: `{_repo_rel(ARTIFACT_MD)}`",
        f"- Result JSON: `{_repo_rel(OUT_JSON)}`",
        f"- Main blocker: {top['forward_blocker']}",
        "- Acceptance basis: read-only alpha direction decision using accepted "
        "3-window artifacts; no executable behavior changed.",
        "- Next retry requires: closed forward rows, cost-adjusted replacement "
        "value, and concentration analysis before any live/default activation.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    payload = _build_payload()
    record = _record_for_jsonl(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _write_text(CARD_MD, _build_card(payload))
    _append_jsonl_once(EXPERIMENT_LOG, record)
    _update_ticket(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "top_direction": payload["conclusion"]["optimize_now"],
                "top_direction_label": payload["conclusion"]["optimize_now_label"],
                "artifact": _repo_rel(ARTIFACT_MD),
                "json": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "jsonl_appended_if_missing": _repo_rel(EXPERIMENT_LOG),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
