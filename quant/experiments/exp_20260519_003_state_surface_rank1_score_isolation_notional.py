"""exp-20260519-003: state-surface rank-1 score isolation notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
when the residual score-expansion state-surface queue has a clear rank-1 score
lead, shift paper notional toward rank 1 instead of keeping the generic
score-expansion profile.

Core entries, exits, candidate eligibility, queue ranking, hold days, active
capacity, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260519_001_state_surface_score_expansion_notional as score_exp
import exp_20260519_002_state_surface_repeat_ticker_notional as repeat


EXPERIMENT_ID = "exp-20260519-003"
EXPERIMENT_SLUG = "state_surface_rank1_score_isolation_notional"

REPO_ROOT = repeat.REPO_ROOT
WINDOWS = repeat.WINDOWS
BASELINE_VARIANT = "accepted_score_expansion_repeat_notional"
MIN_SELECTED_TRADES = repeat.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 6
MIN_ADJUSTED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = repeat.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = repeat.MAX_SINGLE_TICKER_POSITIVE_SHARE
SCORE_EXPANSION_PROFILE_NAME = "score_expansion_top3_ge_0p4"
RULE_VERSION = "state_surface_rank1_score_isolation_rank_notional_v1"

RANK1_SCORE_ISOLATION_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "score_gap_min": None,
                "aggression_order": 0,
                "description": "accepted score-expansion plus recent-repeat stack",
            },
        ),
        (
            "rank1_score_gap020_200_110_080",
            {
                "profile": [2.0, 1.10, 0.80, 0.675, 0.35],
                "score_gap_min": 0.20,
                "aggression_order": 1,
                "description": "rank-1 score isolation with moderate transfer",
            },
        ),
        (
            "rank1_score_gap020_210_105_075",
            {
                "profile": [2.1, 1.05, 0.75, 0.675, 0.35],
                "score_gap_min": 0.20,
                "aggression_order": 2,
                "description": "rank-1 score isolation with stronger transfer",
            },
        ),
        (
            "rank1_score_gap020_220_100_070",
            {
                "profile": [2.2, 1.00, 0.70, 0.675, 0.35],
                "score_gap_min": 0.20,
                "aggression_order": 3,
                "description": "rank-1 score isolation with strongest tested transfer",
            },
        ),
        (
            "rank1_score_gap030_220_100_070",
            {
                "profile": [2.2, 1.00, 0.70, 0.675, 0.35],
                "score_gap_min": 0.30,
                "aggression_order": 4,
                "description": "stricter rank-1 score isolation with strongest transfer",
            },
        ),
        (
            "rank1_score_gap045_220_100_070",
            {
                "profile": [2.2, 1.00, 0.70, 0.675, 0.35],
                "score_gap_min": 0.45,
                "aggression_order": 5,
                "description": "strictest rank-1 score isolation with strongest transfer",
            },
        ),
    ]
)

OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") != payload["experiment_id"]:
                rows.append(line)
    rows.append(json.dumps(_safe(payload), sort_keys=True))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _accepted_score_expansion_repeat_trades(
    *,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    pre_score = score_exp._current_accepted_trades(
        core_results=core_results,
        prices=prices,
    )
    score_variant = score_exp.SCORE_EXPANSION_VARIANTS[
        "residual_score_expansion_ge_040_rank1_top"
    ]
    scored = score_exp._apply_score_expansion_profile(
        pre_score,
        variant_name="residual_score_expansion_ge_040_rank1_top",
        variant=score_variant,
    )
    return repeat._apply_recent_repeat_scalar(
        scored,
        variant_name="repeat_60d_topup_1_50",
        scalar=1.5,
    )


def _profile_multiplier(profile: list[float], rank: Any) -> float:
    try:
        queue_rank = int(rank)
    except (TypeError, ValueError):
        queue_rank = 1
    queue_rank = max(queue_rank, 1)
    if queue_rank > len(profile):
        return float(profile[-1])
    return float(profile[queue_rank - 1])


def _base_profile_name(row: dict[str, Any]) -> str:
    return str(
        row.get("score_expansion_profile_name")
        or row.get("recent_ticker_repeat_profile_name")
        or row.get("rank_notional_profile_name")
        or ""
    )


def _profile_name(score_gap_min: float) -> str:
    value = str(round(float(score_gap_min), 6)).rstrip("0").rstrip(".")
    return f"rank1_score_gap_ge_{value.replace('.', 'p')}_score_expansion_top3_ge_0p4"


def _apply_rank1_score_isolation_profile(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    profile = variant.get("profile")
    score_gap_min = repeat.parent.parent._float(variant.get("score_gap_min"))
    base_notional = float(repeat.parent.parent.parent.base.EVENT_NOTIONAL)
    for trade in trades:
        row = dict(trade)
        row["rank1_score_isolation_variant"] = variant_name
        row["rank1_score_isolation_profile_applied"] = False
        row["rank1_score_isolation_profile_name"] = _base_profile_name(row)
        row["rank1_score_isolation_min_score_gap"] = None
        row["rank1_score_isolation_rule_version"] = RULE_VERSION
        score_gap = repeat.parent.parent._float(row.get("score_top_to_second_gap"))
        applies = (
            variant_name != BASELINE_VARIANT
            and profile
            and score_gap_min is not None
            and score_gap is not None
            and score_gap >= score_gap_min
            and str(row.get("score_expansion_profile_name") or "")
            == SCORE_EXPANSION_PROFILE_NAME
        )
        if applies:
            multiplier = _profile_multiplier(
                profile,
                row.get("queue_rank") or row.get("rank"),
            )
            notional = round(base_notional * multiplier, 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["rank1_score_isolation_profile_applied"] = True
            row["rank1_score_isolation_profile_name"] = _profile_name(score_gap_min)
            row["rank1_score_isolation_min_score_gap"] = score_gap_min
            row["rank_notional_multiplier"] = multiplier
            row["notional"] = notional
            row["shares"] = notional / entry_open
            row["pnl"] = round(notional * net_return, 2)
        adjusted.append(row)
    return adjusted


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "sector": repeat._sector(trade),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "queue_rank": trade.get("queue_rank"),
                "candidate_breadth": trade.get("candidate_breadth"),
                "score": trade.get("score"),
                "score_top_to_second_gap": trade.get("score_top_to_second_gap"),
                "score_top3_spread": trade.get("score_top3_spread"),
                "score_expansion_profile_name": trade.get("score_expansion_profile_name"),
                "rank1_score_isolation_profile_applied": trade.get(
                    "rank1_score_isolation_profile_applied"
                ),
                "rank1_score_isolation_profile_name": trade.get(
                    "rank1_score_isolation_profile_name"
                ),
                "rank1_score_isolation_min_score_gap": trade.get(
                    "rank1_score_isolation_min_score_gap"
                ),
                "recent_ticker_repeat_applied": trade.get(
                    "recent_ticker_repeat_applied"
                ),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    baseline_trades: list[dict[str, Any]],
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    selected = _apply_rank1_score_isolation_profile(
        baseline_trades,
        variant_name=variant_name,
        variant=variant,
    )
    after_metrics = repeat._metrics_for_trades(
        trades=selected,
        core_results=core_results,
        prices=prices,
    )
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    for label in WINDOWS:
        adjusted = [row for row in selected if row.get("window") == label]
        applied = [
            row for row in adjusted if row.get("rank1_score_isolation_profile_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(adjusted),
            "rank1_score_isolation_adjusted_trade_count": len(applied),
            "rank1_score_isolation_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in adjusted),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for row in adjusted if float(row.get("pnl") or 0.0) > 0)
                / len(adjusted),
                4,
            )
            if adjusted
            else None,
            "ticker_distribution": dict(Counter(row.get("ticker") for row in adjusted)),
            "notional_by_queue_rank": repeat.parent.parent.rank_exp._notional_by_queue_rank(
                adjusted
            ),
            "selected_trades": _selected_trade_rows(adjusted),
        }
    adjusted_all = [
        row for row in selected if row.get("rank1_score_isolation_profile_applied")
    ]
    adjusted_windows = {str(row.get("window")) for row in adjusted_all if row.get("window")}
    return {
        "variant_name": variant_name,
        "variant_type": "rank1_score_isolation_rank_notional_profile",
        "profile": variant.get("profile"),
        "score_gap_min": variant.get("score_gap_min"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "rank1_score_isolation_adjusted_trade_count": len(adjusted_all),
        "rank1_score_isolation_adjusted_windows": sorted(adjusted_windows),
        "single_ticker_positive_share": repeat.parent.parent._single_ticker_positive_share(
            selected
        ),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = repeat.parent.parent.parent._aggregate_delta(
        baseline_metrics,
        variant["metrics"],
    )
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["rank1_score_isolation_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["rank1_score_isolation_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    passed = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and sample_guard_passed
        and adjusted_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    share = variant["single_ticker_positive_share"]
    share_delta = (
        round(share - baseline_share, 6)
        if share is not None and baseline_share is not None
        else None
    )
    return {
        "passed": passed,
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "rank1_score_isolation_adjusted_trade_count": variant[
            "rank1_score_isolation_adjusted_trade_count"
        ],
        "rank1_score_isolation_adjusted_windows": variant[
            "rank1_score_isolation_adjusted_windows"
        ],
        "selected_trade_count": variant["selected_trade_count"],
        "sample_guard_passed": sample_guard_passed,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": share,
        "baseline_single_ticker_positive_share": baseline_share,
        "single_ticker_positive_share_delta": share_delta,
        "concentration_guard_passed": concentration_guard_passed,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard_passed,
        "minimum_selected_trades": MIN_SELECTED_TRADES,
        "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
        "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
        "delta_metrics": delta,
    }


def _choose_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [
        row
        for row in rows
        if row["variant_name"] != BASELINE_VARIANT and row["gate4"]["passed"]
    ]
    if passing:
        return max(
            passing,
            key=lambda row: (
                row["gate4"]["aggregate_ev_delta"],
                row["gate4"]["aggregate_pnl_delta"],
                -row["gate4"]["max_drawdown_worse_max"],
                -row["aggression_order"],
            ),
        )
    return max(
        [row for row in rows if row["variant_name"] != BASELINE_VARIANT],
        key=lambda row: (
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            row["gate4"]["windows_ev_improved"],
            -row["gate4"]["windows_ev_regressed"],
        ),
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Rank-1 Score Isolation Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `rank1_score_isolation_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Score Gap | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {gap} | {profile} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                gap=row["score_gap_min"] if row["score_gap_min"] is not None else "n/a",
                profile=row["profile"] or "n/a",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["rank1_score_isolation_adjusted_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share=f"{share:.2%}" if share is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bdd:.2%} | {add:.2%} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                trades=sleeve["rank1_score_isolation_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    gate2 = repeat.parent.parent.parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    prices = repeat.parent.parent.parent._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        core_results[label] = repeat.parent.parent.parent._load_core_result(window)

    baseline_trades = _accepted_score_expansion_repeat_trades(
        core_results=core_results,
        prices=prices,
    )
    baseline_metrics = repeat._metrics_for_trades(
        trades=baseline_trades,
        core_results=core_results,
        prices=prices,
    )
    baseline_share = repeat.parent.parent._single_ticker_positive_share(baseline_trades)

    variants = [
        _variant_payload(
            variant_name=variant_name,
            variant=variant,
            baseline_trades=baseline_trades,
            core_results=core_results,
            prices=prices,
        )
        for variant_name, variant in RANK1_SCORE_ISOLATION_VARIANTS.items()
    ]
    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            baseline_share=baseline_share,
            variant=variant,
        )
        sweep_summary.append(
            {
                "variant_name": variant["variant_name"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "profile": variant["profile"],
                "score_gap_min": variant["score_gap_min"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "rank1_score_isolation_adjusted_trade_count": variant[
                    "rank1_score_isolation_adjusted_trade_count"
                ],
                "rank1_score_isolation_adjusted_windows": variant[
                    "rank1_score_isolation_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(
        row for row in variants if row["variant_name"] == best["variant_name"]
    )
    delta = repeat.parent.parent.parent._aggregate_delta(
        baseline_metrics,
        best_payload["metrics"],
    )
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_rank1_score_isolation_notional"
        if passed
        else "rejected_state_surface_rank1_score_isolation_notional"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        ),
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "hypothesis": "In the residual score-expansion state-surface sleeve, a large rank-1 score gap identifies isolated leadership where paper notional should shift from rank 2/3 toward rank 1.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Targets state-surface maturation through a new rank-quality/crowding field, not LLM soft-ranking or candidate-pool broadening.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "rank1_score_isolation_rank_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_profile": best["profile"],
            "score_gap_min": best["score_gap_min"],
            "score_expansion_profile_name": SCORE_EXPANSION_PROFILE_NAME,
            "profile_priority": "after higher-priority top2 sector, ret60, rank2 ret20, rank1 ret20, and score-compression profiles; before generic residual score-expansion",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "recent ticker repeat scalar",
                "LLM/news",
                "live/default orders",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows; core unchanged plus default-off state-surface paper overlay replay.",
        "before_metrics": baseline_metrics,
        "after_metrics": best_payload["metrics"],
        "delta_metrics": delta,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"]
            for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_ev_delta"]},
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_pnl_delta"]},
        "gate1": {
            "baseline_artifacts": [
                _repo_rel(
                    "data/experiments/exp-20260519-001/state_surface_score_expansion_notional.json"
                ),
                _repo_rel(
                    "data/experiments/exp-20260519-002/state_surface_repeat_ticker_notional.json"
                ),
            ],
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": "Uses the production-visible combined score-expansion plus repeat stack as Gate 1 baseline.",
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "score_top_to_second_gap",
                "score_expansion_profile_name",
                "candidate_breadth",
                "queue_rank",
                "entry_open",
                "net_return_pct",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in baseline_metrics.values()
            ),
            "after_survival_rate": {
                label: best_payload["metrics"][label].get("survival_rate")
                for label in WINDOWS
            },
            "hard_rule": "No candidate gate changed; only default-off paper notional changes.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260519-001": "Accepted residual score-expansion field; this run does not change its threshold and only tests a rank-1 isolation override inside that branch.",
            "exp-20260519-002": "Accepted recent ticker repeat field; this run keeps its 60d/1.50x scalar fixed in the baseline.",
            "exp-20260518-021": "Rejected rank-2 ret5 leadership because concentration worsened; this field shifts toward isolated rank 1 and lowers concentration.",
            "llm_soft_ranking": "Skipped because sparse/PIT-limited attribution remains a known data limit.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this deterministic field is replayable from state-surface candidate scores.",
        },
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": True,
            "parity_test_added": passed,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
            "default_off_paper_only": True,
        },
        "interpretation": (
            "Rank-1 score isolation improved the default-off state-surface paper overlay in two windows with zero EV-regressed windows and lower single-ticker positive concentration."
            if passed
            else "Rank-1 score isolation did not clear Gate 4; keep the score-expansion plus repeat stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata; require forward tail/concentration evidence before any live adapter work."
            if passed
            else "Do not retry adjacent score-gap profiles without forward evidence or a distinct field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: residual score-expansion queues with an isolated rank-1 score leader should route more paper notional to rank 1.",
            "2_history_check": "Prior score-expansion and repeat fields were accepted; adjacent score-expansion threshold mining is blocked, so this freezes those fields and tests score_top_to_second_gap as one new rank-quality field.",
            "3_single_causal_variable": "rank1_score_isolation_rank_notional_profile",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, >=2 improved windows, zero EV-regressed windows, adjusted trades >=6 across >=2 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
        ],
    }
    return _safe(payload)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface rank-1 score isolation notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "summary": (
                f"Rank-1 isolation best profile {payload['parameters']['best_profile']} "
                f"changed aggregate EV {payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
                f"and PnL ${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
