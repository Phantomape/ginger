"""exp-20260512-777 low-deployment ETF overlay candidate-pool sweep.

Alpha search, default-off paper/replay. The accepted paper adapter from
exp-20260510-008 already exposes the low-deployment ETF overlay in production
without changing orders. This experiment tests one causal variable on top of
that surface: whether the tiny ETF candidate pool should stay at v1 or use a
broader but still liquid macro ETF set.

No core signal generation, ranking, sizing, exits, add-ons, LLM/news replay,
stock universe membership, or live/default order path is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from exp_20260510_007_low_deployment_dynamic_etf_overlay import (  # noqa: E402
    INITIAL_CAPITAL,
    MAX_ACTIVE_CORE_POSITIONS,
    OVERLAY_NOTIONAL_FRACTION,
    STATE_MOMENTUM_DAYS,
    STATE_SMA_DAYS,
    _aggregate,
    _delta,
    _field_audit,
    _metrics,
    _metrics_with_overlay,
    _overlay_path,
    _repo_rel,
    _safe,
    _single_ticker_positive_share,
)


EXPERIMENT_ID = "exp-20260512-777"
STEM = "low_deployment_etf_candidate_pool"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_POOL = ("QQQ", "SPY", "IWM", "GLD", "SLV")
CANDIDATE_POOLS: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
    [
        ("v1_current", BASELINE_POOL),
        ("no_slv", ("QQQ", "SPY", "IWM", "GLD")),
        ("metals_only", ("GLD", "SLV")),
        ("gold_only", ("GLD",)),
        ("equity_only", ("QQQ", "SPY", "IWM")),
        ("add_bonds", ("QQQ", "SPY", "IWM", "GLD", "SLV", "TLT", "IEF")),
        ("add_energy", ("QQQ", "SPY", "IWM", "GLD", "SLV", "USO", "XLE")),
        (
            "cross_asset_plus",
            ("QQQ", "SPY", "IWM", "GLD", "SLV", "TLT", "IEF", "USO", "XLE"),
        ),
        ("defensive_plus", ("GLD", "SLV", "TLT", "IEF", "UUP")),
    ]
)

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = (
        path.read_text(encoding="utf-8", errors="replace").splitlines()
        if path.exists()
        else []
    )
    kept = [line for line in lines if compact not in line and pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _load_snapshot_rows(
    snapshot_path: str,
    candidate_pool: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads((REPO_ROOT / snapshot_path).read_text(encoding="utf-8"))
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker in candidate_pool:
        rows = []
        for row in (payload.get("ohlcv") or {}).get(ticker, []):
            rows.append(
                {
                    "date": row["Date"],
                    "open": float(row["Open"]),
                    "close": float(row["Close"]),
                }
            )
        if rows:
            out[ticker] = sorted(rows, key=lambda row: row["date"])
    return out


def _window_row(
    result: dict[str, Any],
    window: dict[str, str],
    candidate_pool: tuple[str, ...],
) -> dict[str, Any]:
    overlay = _overlay_path(result, _load_snapshot_rows(window["snapshot"], candidate_pool))
    before = _metrics(result)
    after = _metrics_with_overlay(result, overlay)
    return {
        "before": before,
        "after": after,
        "delta": _delta(after, before),
        "overlay_total_pnl": overlay["overlay_total_pnl"],
        "overlay_day_count": overlay["overlay_day_count"],
        "low_deployment_day_count": overlay["low_deployment_day_count"],
        "ticker_day_counts": overlay["ticker_day_counts"],
        "overlay_days": overlay["overlay_days"],
        "overlay_days_sample": overlay["overlay_days"][:20],
    }


def _variant_delta_vs_baseline(
    variant_windows: dict[str, dict[str, Any]],
    baseline_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict()
    for label, row in variant_windows.items():
        base = baseline_windows[label]
        by_window[label] = _delta(row["after"], base["after"])
        by_window[label]["overlay_total_pnl"] = round(
            row["overlay_total_pnl"] - base["overlay_total_pnl"],
            2,
        )
        by_window[label]["overlay_day_count"] = (
            row["overlay_day_count"] - base["overlay_day_count"]
        )
    ev_before = sum(
        row["after"]["expected_value_score"] for row in baseline_windows.values()
    )
    ev_delta = sum(row["expected_value_score"] for row in by_window.values())
    pnl_before = sum(row["after"]["total_pnl"] for row in baseline_windows.values())
    pnl_delta = sum(row["total_pnl"] for row in by_window.values())
    aggregate = {
        "baseline_overlay_expected_value_score_sum": _round(ev_before, 6),
        "candidate_overlay_expected_value_score_delta_sum": _round(ev_delta, 6),
        "candidate_overlay_expected_value_score_delta_pct": (
            _round(ev_delta / ev_before, 6) if ev_before else None
        ),
        "baseline_overlay_total_pnl_sum": _round(pnl_before, 2),
        "candidate_overlay_total_pnl_delta_sum": _round(pnl_delta, 2),
        "candidate_overlay_total_pnl_delta_pct": (
            _round(pnl_delta / pnl_before, 6) if pnl_before else None
        ),
        "windows_ev_improved": sum(
            1 for row in by_window.values() if row.get("expected_value_score", 0) > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in by_window.values() if row.get("expected_value_score", 0) < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in by_window.values() if row.get("total_pnl", 0) > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in by_window.values() if row.get("total_pnl", 0) < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row.get("max_drawdown_pct", 0.0) for row in by_window.values()),
            6,
        ),
    }
    return {"by_window": by_window, "aggregate": aggregate}


def _gate4(
    variant_delta: dict[str, Any],
    variant_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    aggregate = variant_delta["aggregate"]
    concentration = _single_ticker_positive_share(variant_windows)
    concentration_ok = concentration is None or concentration <= 0.75
    directional = bool(
        aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and aggregate["candidate_overlay_expected_value_score_delta_sum"] > 0
        and aggregate["candidate_overlay_total_pnl_delta_sum"] > 0
        and aggregate["max_drawdown_delta_max"] <= 0.01
        and concentration_ok
    )
    material = bool(
        (aggregate["candidate_overlay_expected_value_score_delta_pct"] or 0.0) >= 0.02
        or (aggregate["candidate_overlay_total_pnl_delta_pct"] or 0.0) >= 0.02
    )
    return {
        "passed": bool(directional and material),
        "passed_directionally": directional,
        "strong_materiality_passed": material,
        "concentration_ok": concentration_ok,
        "single_ticker_positive_share": concentration,
        "basis": "Three canonical backtesting.md windows, candidate-pool delta measured against accepted v1 ETF overlay.",
        "rule": (
            "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive "
            "aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive "
            "contribution share <= 75%, and at least 2% aggregate EV or PnL uplift "
            "versus the accepted overlay baseline."
        ),
    }


def _choose_best(variants: dict[str, dict[str, Any]]) -> str:
    candidates = [
        (name, row)
        for name, row in variants.items()
        if name != "v1_current"
        and row["gate4"]["passed_directionally"]
        and row["delta_vs_v1"]["aggregate"][
            "candidate_overlay_expected_value_score_delta_sum"
        ]
        > 0
    ]
    if not candidates:
        return "v1_current"
    return max(
        candidates,
        key=lambda item: (
            item[1]["gate4"]["passed"],
            item[1]["delta_vs_v1"]["aggregate"][
                "candidate_overlay_expected_value_score_delta_sum"
            ],
            item[1]["delta_vs_v1"]["aggregate"][
                "candidate_overlay_total_pnl_delta_sum"
            ],
        ),
    )[0]


def _build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    baseline_results = OrderedDict()
    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe=get_universe(),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        baseline_results[label] = result

    variants: dict[str, dict[str, Any]] = OrderedDict()
    for name, pool in CANDIDATE_POOLS.items():
        windows = OrderedDict(
            (
                label,
                _window_row(baseline_results[label], WINDOWS[label], pool),
            )
            for label in WINDOWS
        )
        core_delta = _aggregate(windows)
        variants[name] = {
            "candidate_pool": list(pool),
            "windows": windows,
            "delta_vs_core": {"aggregate": core_delta},
        }

    v1_windows = variants["v1_current"]["windows"]
    for name, row in variants.items():
        row["delta_vs_v1"] = _variant_delta_vs_baseline(row["windows"], v1_windows)
        row["gate4"] = _gate4(row["delta_vs_v1"], row["windows"])

    best_variant = _choose_best(variants)
    accepted = best_variant != "v1_current" and variants[best_variant]["gate4"]["passed"]
    if accepted:
        decision = "accepted_default_off_low_deployment_etf_candidate_pool"
        rejection_reason = None
        decision_rationale = (
            f"{best_variant} improved the accepted v1 low-deployment ETF overlay "
            "across all three canonical windows without changing core trading "
            "behavior. Promote only the default-off paper candidate pool; live "
            "orders remain blocked by forward outcomes and cash semantics."
        )
    elif best_variant != "v1_current":
        decision = "directionally_positive_underpowered"
        rejection_reason = None
        decision_rationale = (
            f"{best_variant} was directionally positive versus v1, but did not "
            "clear the materiality gate. Keep v1 as the shared default-off paper "
            "pool and require forward evidence before retrying adjacent ETF pools."
        )
    else:
        decision = "rejected_keep_v1_candidate_pool"
        rejection_reason = (
            "No tested ETF candidate-pool variant beat the accepted v1 pool across "
            "the three-window EV/PnL/drawdown/concentration gate."
        )
        decision_rationale = rejection_reason

    before_metrics = {
        label: row["after"] for label, row in variants["v1_current"]["windows"].items()
    }
    after_metrics = {
        label: row["after"] for label, row in variants[best_variant]["windows"].items()
    }
    delta_metrics = variants[best_variant]["delta_vs_v1"]
    best_aggregate = delta_metrics["aggregate"]

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "low_deployment_dynamic_etf_overlay_allocation",
        "hypothesis": (
            "The accepted low-deployment ETF overlay may improve replacement "
            "value if its candidate pool includes only the most useful liquid "
            "macro ETF surfaces, rather than blindly keeping the original v1 set."
        ),
        "change_type": "alpha_search_candidate_pool",
        "changed_variable": "low_deployment_etf_overlay_candidate_tickers",
        "single_causal_variable": (
            "ETF candidate pool used by the default-off low-deployment dynamic "
            "ETF overlay selector; selector, low-deployment trigger, notional, "
            "core strategy behavior, and live order path stay locked."
        ),
        "parameters": {
            "baseline_pool": list(BASELINE_POOL),
            "tested_candidate_pools": {
                name: list(pool) for name, pool in CANDIDATE_POOLS.items()
            },
            "best_variant": best_variant,
            "best_candidate_pool": variants[best_variant]["candidate_pool"],
            "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
            "overlay_notional_fraction": OVERLAY_NOTIONAL_FRACTION,
            "state_sma_days": STATE_SMA_DAYS,
            "state_momentum_days": STATE_MOMENTUM_DAYS,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "position caps",
                "portfolio heat",
                "exits",
                "follow-through add-ons",
                "LLM/news replay",
                "live/default orders",
            ],
        },
        "alpha_hypothesis": {
            "category": "capital_allocation/candidate_pool_quality",
            "playbook_alignment": (
                "Uses the current research queue's capital-allocation direction, "
                "avoids blocked LLM soft-ranking and SEC filing-shock data, and "
                "improves a production-visible default-off paper surface rather "
                "than adding noisy stock tickers."
            ),
        },
        "historical_experiment_check": {
            "exp-20260510-007": (
                "Original low-deployment dynamic ETF overlay was positive in "
                "3/3 windows and is the before baseline for this candidate-pool test."
            ),
            "exp-20260510-008": (
                "Default-off production paper adapter exists; any positive "
                "candidate-pool change must update that shared paper surface only."
            ),
            "broad ETF expansion guardrail": (
                "The experiment does not add ETFs to the core stock universe, "
                "does not consume A/B slots, and remains default-off paper-only."
            ),
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "gate2_field_audit": _field_audit(),
        "gate3": {
            "new_filter_added": False,
            "note": (
                "No core entry filter or candidate filter was added; survival "
                "rates are inherited from the accepted core replay."
            ),
            "survival_rates": {
                label: row["before"]["survival_rate"]
                for label, row in variants["v1_current"]["windows"].items()
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "expected_value_score_delta": best_aggregate[
            "candidate_overlay_expected_value_score_delta_sum"
        ],
        "gate4": variants[best_variant]["gate4"],
        "variant_summary": {
            name: {
                "candidate_pool": row["candidate_pool"],
                "aggregate_delta_vs_v1": row["delta_vs_v1"]["aggregate"],
                "gate4": row["gate4"],
                "ticker_day_counts": {
                    label: window["ticker_day_counts"]
                    for label, window in row["windows"].items()
                },
                "overlay_total_pnl": {
                    label: window["overlay_total_pnl"]
                    for label, window in row["windows"].items()
                },
            }
            for name, row in variants.items()
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this deterministic "
                "candidate-pool test does not depend on LLM replay."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "parity_test_added": accepted,
            "replay_only": False if accepted else True,
            "default_off_paper_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_orders_changed": False,
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_action": (
            "If accepted, update the shared low-deployment ETF paper config and "
            "focused tests while keeping live orders disabled. If rejected, keep "
            "the v1 candidate pool and do not retry adjacent ETF pool variants "
            "without forward paper replacement-value evidence."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }
    return {**log_record, "variants": variants}


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["parameters"]["best_variant"]
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Low-deployment ETF Candidate Pool",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Best Variant Versus Accepted V1",
        "",
        f"- best_variant: `{best}`",
        f"- candidate_pool: `{payload['parameters']['best_candidate_pool']}`",
        f"- EV delta vs v1: `{aggregate['candidate_overlay_expected_value_score_delta_sum']}`",
        f"- PnL delta vs v1: `${aggregate['candidate_overlay_total_pnl_delta_sum']}`",
        f"- EV windows improved/regressed: `{aggregate['windows_ev_improved']}` / `{aggregate['windows_ev_regressed']}`",
        f"- PnL windows improved/regressed: `{aggregate['windows_pnl_improved']}` / `{aggregate['windows_pnl_regressed']}`",
        f"- max DD delta max: `{aggregate['max_drawdown_delta_max']}`",
        "",
        "## Three-window Deltas Vs V1",
        "",
        "| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["delta_metrics"]["by_window"].items():
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {ret:+.4f} | {sharpe:+.2f} | {dd:+.4f} | {days:+d} |".format(
                label=label,
                ev=row.get("expected_value_score", 0.0),
                pnl=row.get("total_pnl", 0.0),
                ret=row.get("strategy_total_return_pct", 0.0),
                sharpe=row.get("sharpe_daily", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
                days=int(row.get("overlay_day_count", 0)),
            )
        )
    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | Pool | EV delta vs v1 | PnL delta vs v1 | EV +/- windows | Gate 4 |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for name, row in payload["variant_summary"].items():
        agg = row["aggregate_delta_vs_v1"]
        lines.append(
            "| {name} | {pool} | {ev:+.4f} | ${pnl:+,.2f} | {imp}/{reg} | {gate} |".format(
                name=name,
                pool=", ".join(row["candidate_pool"]),
                ev=agg["candidate_overlay_expected_value_score_delta_sum"],
                pnl=agg["candidate_overlay_total_pnl_delta_sum"],
                imp=agg["windows_ev_improved"],
                reg=agg["windows_ev_regressed"],
                gate=row["gate4"]["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"  replay_only: {payload['production_impact']['replay_only']}",
            f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
            f"  default_off_paper_only: {payload['production_impact']['default_off_paper_only']}",
            f"  alters_orders: {payload['production_impact']['alters_orders']}",
            "```",
            "",
            "Live/default orders remain disabled.",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "best_variant": payload["parameters"]["best_variant"],
        "best_candidate_pool": payload["parameters"]["best_candidate_pool"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "decision": payload["decision"],
        "artifact": _repo_rel(ARTIFACT_MD),
    }
    _write_json(TICKET_JSON, ticket)


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_artifact(payload)
    log_payload = dict(payload)
    log_payload.pop("variants", None)
    _append_jsonl_dedup(EXPERIMENT_LOG, log_payload)
    print(json.dumps(_safe({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "best_variant": payload["parameters"]["best_variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["delta_metrics"]["aggregate"][
            "candidate_overlay_total_pnl_delta_sum"
        ],
        "artifact": _repo_rel(ARTIFACT_MD),
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
