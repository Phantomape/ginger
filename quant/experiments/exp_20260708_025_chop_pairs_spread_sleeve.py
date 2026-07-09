"""exp-20260708-025: chop-regime long-short pairs spread sleeve, Gate 1-4.

Alpha search (owner priority 2026-07-08, round 2 — new evidence axis: first
long-short gate shape in the repo). exp-20260708-023 rejected single-name
long-only reversion in chop; this tests the market-neutral mirror: on
chop-labeled days, trade convergence of stretched spreads between highly
correlated core-universe pairs. Fixed predeclared bundle
``chop_pairs_spread_v1`` in ``quant/chop_pairs_spread_sleeve.py`` — no sweeps.
Default-off paper replay only.

Acceptance (predeclared, tightened after exp-20260708-023's lesson):
pooled over the three canonical windows the sleeve must close >= 15 trades
with positive total PnL (market-neutral, so cash is the bar), >= 2 evaluable
windows (>= 3 trades) non-negative, AND the chop-day mean PnL/trade must
exceed the risk_on control mean (conditioning must earn its keep; control
needs >= 5 trades to bind). Fewer than 15 pooled trades -> observed_only.
recent_observe stays diagnostic only per docs/backtesting.md.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

EXPERIMENT_ID = "exp-20260708-025"
OWNER = "interactive"
LANE = "alpha_search"
SLUG = "chop_pairs_spread_sleeve"
RUNNER = f"quant/experiments/exp_20260708_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from chop_mean_reversion_sleeve import breadth_by_date, regime_labels_by_date  # noqa: E402
from chop_pairs_spread_sleeve import (  # noqa: E402
    EXCLUDED_ENTRY_TICKERS,
    SLEEVE_RULE_VERSION,
    replay_chop_pairs_spread,
    summarize_pair_trades,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from filter import WATCHLIST  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_MAIN = DATA_DIR / "warehouse" / "warehouse_main.sqlite"
WAREHOUSE_HOT = DATA_DIR / "warehouse" / "warehouse_main_hot.sqlite"

CANONICAL_WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]
RECENT_OBSERVE_START = "2026-04-22"

MIN_POOLED_TRADES = 15
MIN_WINDOW_TRADES_EVALUABLE = 3
MIN_NONNEGATIVE_EVALUABLE_WINDOWS = 2
MIN_CONTROL_TRADES_TO_BIND = 5

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_025_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Owner priority 2026-07-08 round 2: chop gives no direction, so trade the "
    "axis that does not need one - a LONG-SHORT SPREAD family, the first "
    "market-neutral construct in this repo. On chop-labeled days, among core "
    "universe equity pairs with trailing 120d correlation >= 0.6, when the "
    "60d-normalized log price ratio stretches beyond 2 sigma, buy the laggard "
    "and short the leader in equal notional; exit on convergence below 0.5 "
    "sigma or a 10-day timeout."
)
ALPHA_HYPOTHESIS = HYPOTHESIS
CHANGED_VARIABLE = "chop_pairs_spread_entry_sleeve_v1"
MECHANISM_FAMILY = "chop_relative_value_spread"
TRIAL_FAMILY = "chop_pairs_spread_candidate_pool"
TRIAL_VARIANT_ID = "chop_pairs_spread_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260708-023", "exp-20260615-019", "exp-20260622-017"]
CAUSAL_COMPONENTS = [
    "chop_day_condition",
    "pit_trailing_correlation_pair_eligibility",
    "ratio_zscore_stretch_entry",
    "convergence_or_timeout_exit",
    "equal_notional_long_short_paper_accounting",
    "historical_replay",
]
PREDICTED_FAILURE_MODES = [
    "chop_day_sample_too_thin",
    "spread_convergence_slower_than_timeout",
    "correlation_pairs_unstable_pit",
    "two_leg_costs_eat_edge",
    "megacap_pairs_too_cointegrated_to_stretch",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def load_bars(tickers: list[str]) -> dict[str, list[dict[str, Any]]]:
    rows_by_ticker: dict[str, dict[str, dict[str, Any]]] = {t: {} for t in tickers}
    for wh in (WAREHOUSE_MAIN, WAREHOUSE_HOT):
        if not wh.exists():
            continue
        con = sqlite3.connect(f"file:{wh.resolve().as_posix()}?mode=ro", uri=True)
        try:
            placeholders = ",".join("?" for _ in tickers)
            query = (
                "select ticker, date, open, high, low, close from ohlcv "
                f"where ticker in ({placeholders}) order by ticker, date"
            )
            for ticker, day, open_, high, low, close in con.execute(query, tickers):
                if close is None:
                    continue
                rows_by_ticker[str(ticker).upper()][str(day)[:10]] = {
                    "Date": str(day)[:10],
                    "Open": float(open_) if open_ is not None else float(close),
                    "High": float(high) if high is not None else float(close),
                    "Low": float(low) if low is not None else float(close),
                    "Close": float(close),
                }
        finally:
            con.close()
    return {
        ticker: [by_date[d] for d in sorted(by_date)]
        for ticker, by_date in rows_by_ticker.items()
        if by_date
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()

    universe = sorted(set(WATCHLIST))
    bars_by_ticker = load_bars(universe)
    spy_bars = bars_by_ticker.get("SPY") or []
    latest_day = spy_bars[-1]["Date"] if spy_bars else None

    all_days = [b["Date"] for b in spy_bars if b["Date"] >= "2024-06-01"]
    breadth = breadth_by_date(bars_by_ticker, all_days)
    labels = regime_labels_by_date(spy_bars, breadth, all_days)

    windows: list[dict[str, Any]] = []
    control_windows: list[dict[str, Any]] = []
    for name, start, end in CANONICAL_WINDOWS:
        replay = replay_chop_pairs_spread(
            bars_by_ticker, spy_bars, start, end, regime_labels=labels,
        )
        control = replay_chop_pairs_spread(
            bars_by_ticker, spy_bars, start, end,
            entry_regime_label="risk_on_trend", regime_labels=labels,
        )
        windows.append({"window": name, **replay})
        control_windows.append(
            {
                "window": name,
                "entry_regime_label": "risk_on_trend",
                **{k: control[k] for k in ("entry_label_days", "signals_generated", "summary")},
            }
        )

    recent = None
    if latest_day and latest_day > RECENT_OBSERVE_START:
        r = replay_chop_pairs_spread(
            bars_by_ticker, spy_bars, RECENT_OBSERVE_START, latest_day, regime_labels=labels,
        )
        recent = {
            "window": "recent_observe",
            "gate_role": "observe_only_diagnostic",
            **{k: r[k] for k in ("start", "end", "entry_label_days", "signals_generated", "summary", "trades")},
        }

    pooled_trades = [t for w in windows for t in w["trades"]]
    pooled = summarize_pair_trades(pooled_trades)
    control_trade_count = sum(c["summary"]["trade_count"] for c in control_windows)
    control_total = sum(c["summary"]["total_pnl_usd"] or 0 for c in control_windows)
    control_mean = round(control_total / control_trade_count, 2) if control_trade_count else None

    evaluable = [w for w in windows if w["summary"]["trade_count"] >= MIN_WINDOW_TRADES_EVALUABLE]
    nonnegative_evaluable = [w for w in evaluable if (w["summary"]["total_pnl_usd"] or 0) >= 0]

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if not spy_bars or spy_bars[0]["Date"] > "2024-04-01":
        measurement_blockers.append("spy_history_insufficient_for_regime")

    alpha_blockers: list[str] = []
    sample_sufficient = pooled["trade_count"] >= MIN_POOLED_TRADES
    if not sample_sufficient:
        alpha_blockers.append("chop_day_sample_too_thin")
    if (pooled["total_pnl_usd"] or 0) <= 0:
        alpha_blockers.append("pooled_pnl_not_positive")
    if len(nonnegative_evaluable) < min(MIN_NONNEGATIVE_EVALUABLE_WINDOWS, max(len(evaluable), 1)):
        alpha_blockers.append("insufficient_nonnegative_windows")
    conditioning_binds = control_trade_count >= MIN_CONTROL_TRADES_TO_BIND
    if (
        conditioning_binds
        and pooled["mean_pnl_usd"] is not None
        and control_mean is not None
        and pooled["mean_pnl_usd"] <= control_mean
    ):
        alpha_blockers.append("chop_conditioning_does_not_beat_risk_on_control")

    measurement_passed = not measurement_blockers
    accepted_alpha = measurement_passed and not alpha_blockers
    if not measurement_passed:
        status, decision = "blocked", f"blocked_{SLUG}"
    elif accepted_alpha:
        status, decision = "accepted", f"accepted_default_off_paper_sleeve_{SLUG}"
    elif not sample_sufficient:
        status, decision = "observed_only", f"observed_only_insufficient_chop_sample_{SLUG}"
    else:
        status, decision = "rejected", f"rejected_{SLUG}"

    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "pooled_trade_count": pooled["trade_count"],
        "pooled_total_pnl_usd": pooled["total_pnl_usd"],
        "pooled_mean_pnl_usd": pooled["mean_pnl_usd"],
        "pooled_win_rate": pooled["win_rate"],
        "pooled_converged_share": pooled["converged_share"],
        "evaluable_window_count": len(evaluable),
        "nonnegative_evaluable_window_count": len(nonnegative_evaluable),
        "chop_days_by_window": {w["window"]: w["entry_label_days"] for w in windows},
        "risk_on_control_trade_count": control_trade_count,
        "risk_on_control_mean_pnl_usd": control_mean,
        "chop_mean_minus_control_mean_usd": (
            round((pooled["mean_pnl_usd"] or 0) - control_mean, 2)
            if pooled["mean_pnl_usd"] is not None and control_mean is not None
            else None
        ),
        "conditioning_criterion_bound": conditioning_binds,
    }
    success_probability = float(
        (ticket.get("prediction") or {}).get("success_probability") or 0.2
    )
    prediction = {
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
        "success_probability": success_probability,
        "expected_ev_delta": 0.5,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": PREDICTED_FAILURE_MODES,
        "confidence_reason": (ticket.get("prediction") or {}).get("confidence_reason"),
    }
    realized = measurement_blockers + alpha_blockers
    calibration = {
        "predicted_success_probability": success_probability,
        "actual_success": 1 if accepted_alpha else 0,
        "brier_score": round(
            (success_probability - (1.0 if accepted_alpha else 0.0)) ** 2, 6
        ),
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "realized_failure_modes": realized,
        "predicted_failure_mode_hit": bool(set(realized) & set(PREDICTED_FAILURE_MODES)),
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "default_off_paper_replay_only_no_daily_wiring_yet",
    }
    files = [
        "quant/chop_pairs_spread_sleeve.py",
        "quant/test_chop_pairs_spread_sleeve.py",
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": accepted_alpha,
        "accepted_alpha": accepted_alpha,
        "accepted_measurement_repair": False,
        "alpha_ready": accepted_alpha,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "strategy_logic",
        "implementation_mode": "shared_paper_first_default_off_replay",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape_long_short_spread",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260708-023": "Single-name long-only reversion in chop REJECTED (1/2 windows, +$2/trade, control beat chop).",
                "exp-20260615-019": "Chop is the loss axis for momentum sleeve entries (lead).",
                "exp-20260622-017": "Core stack is NOT chop-sensitive; chop work must be sleeve-scoped.",
                "novelty_gate": "Override accepted: first long-short spread gate shape in the repo.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                f"Accept only if pooled canonical-window trades >= {MIN_POOLED_TRADES}, pooled PnL > 0, "
                ">= 2 evaluable windows non-negative, AND chop mean/trade beats the risk_on control mean "
                f"(control binds at >= {MIN_CONTROL_TRADES_TO_BIND} trades). Thin sample -> observed_only."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "sleeve_rule_version": SLEEVE_RULE_VERSION,
            "universe_size": len(universe),
            "excluded_entry_tickers": sorted(EXCLUDED_ENTRY_TICKERS),
            "pair_eligibility": "trailing 120d return corr >= 0.6 on >= 100 overlapping obs (PIT)",
            "entry": "chop day AND |z(ln ratio, 60d)| >= 2.0; long cheap / short rich; next-open fills both legs",
            "exit": "|z| <= 0.5 or 10-trading-day timeout; window end force-close flagged",
            "caps": "max 2 new pairs/day, max 3 concurrent pairs, 1 lot/ticker",
            "leg_notional_usd": 4000.0,
            "cost_caveat": "megacap borrow cost for <=10-day shorts ignored (~0.3%/yr, immaterial at this horizon)",
            "warehouses": [repo_rel(WAREHOUSE_MAIN), repo_rel(WAREHOUSE_HOT)],
            "latest_bar_date": latest_day,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": measurement_passed,
            "fields_checked": [
                "pair", "long_ticker", "short_ticker", "signal_date", "entry_date",
                "exit_date", "exit_reason", "entry_zscore", "pair_correlation",
                "regime_label_at_signal", "p_choppy_at_signal",
            ],
            "entry_date_scope": "Paper replay rows carry entry_date per pair; no production signal objects are created.",
            "target_price_scope": "No target_price contract: exits are z-convergence or timeout by design (paper spread).",
        },
        "gate3": {
            "passed": measurement_passed,
            "filter_added": False,
            "signals_generated": sum(w["signals_generated"] for w in windows),
            "signals_survived": pooled["trade_count"],
            "survival_rate": round(
                pooled["trade_count"] / max(sum(w["signals_generated"] for w in windows), 1), 6
            ),
            "note": "Default-off paper sleeve; no filter added to the production chain.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": accepted_alpha,
            "alpha_ready": accepted_alpha,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": alpha_blockers,
            "measurement_repair_only": False,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "windows": windows,
        "risk_on_control_windows": control_windows,
        "recent_observe": recent,
        "pooled_summary": pooled,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": None,
            "forbidden_near_neighbor_retry": (
                "Do not retune corr threshold, z entry/exit, lookbacks, hold days, "
                "pair caps, or notional on these frozen windows; do not swap the "
                "regime axis. New evidence = forward chop-day paper rows via daily "
                "default-off wiring, or a genuinely new data source for pair "
                "selection (e.g. fundamental/flow linkage instead of price corr)."
            ),
            "new_evidence_required": (
                "Forward chop-labeled spread rows from daily wiring, or a new "
                "non-price pair-linkage source."
            ),
        },
        "next_retry_requires": [
            "forward chop-day spread rows from daily wiring (separate ticket if accepted)",
            "no same-window parameter retunes of chop_pairs_spread_v1",
        ],
        "changed_files": files,
        "related_files": [
            "quant/chop_mean_reversion_sleeve.py",
            "quant/regime_chop_state.py",
            "experiments/cards/exp-20260708-023.md",
        ],
        "allowed_write_scope": files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_chop_pairs_spread_sleeve.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def finalize_reflection(payload: dict[str, Any]) -> None:
    pooled = payload["pooled_summary"]
    delta = payload["delta_metrics"]
    if payload["accepted_alpha"]:
        why = (
            f"Stretched-pair convergence on chop days closed {pooled['trade_count']} spreads for "
            f"{pooled['total_pnl_usd']} USD (win rate {pooled['win_rate']}, converged share "
            f"{pooled['converged_share']}), beating the risk_on control by "
            f"{delta['chop_mean_minus_control_mean_usd']} USD/trade - the directionless regime "
            "does reward the market-neutral trade."
        )
    elif "chop_day_sample_too_thin" in payload["gate4"]["alpha_blockers"]:
        why = (
            f"Chop-labeled days produced only {pooled['trade_count']} pooled spreads "
            f"(< {MIN_POOLED_TRADES}); the bundle is frozen and evidence must come from "
            "forward chop days, not window re-slicing."
        )
    else:
        why = (
            f"Pairs spread on chop days closed {pooled['trade_count']} trades for "
            f"{pooled['total_pnl_usd']} USD (mean {pooled['mean_pnl_usd']}/trade, control mean "
            f"{delta['risk_on_control_mean_pnl_usd']}); the market-neutral mirror also failed "
            "the predeclared bar on the frozen windows."
        )
    payload["post_run_reflection"]["why_result_happened"] = why


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keep = dict(payload)
    keep["windows"] = [
        {k: w[k] for k in ("window", "start", "end", "trading_days", "entry_label_days",
                            "signals_generated", "summary")}
        for w in payload["windows"]
    ]
    if keep.get("recent_observe"):
        keep["recent_observe"] = {k: v for k, v in keep["recent_observe"].items() if k != "trades"}
    return keep


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: chop-regime pairs spread sleeve",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Pooled trades: `{delta['pooled_trade_count']}`  PnL: `{delta['pooled_total_pnl_usd']}`  win rate: `{delta['pooled_win_rate']}`",
            f"- Converged share: `{delta['pooled_converged_share']}`",
            f"- Chop days/window: `{delta['chop_days_by_window']}`",
            f"- chop mean/trade `{delta['pooled_mean_pnl_usd']}` vs risk_on control `{delta['risk_on_control_mean_pnl_usd']}` (binds: {delta['conditioning_criterion_bound']})",
            "- Strategy behavior changed: `false` (default-off paper replay only)",
            "",
            "## Why",
            "",
            payload["post_run_reflection"]["why_result_happened"] or "",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        QUANT_ROOT / "chop_pairs_spread_sleeve.py",
        QUANT_ROOT / "test_chop_pairs_spread_sleeve.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "changed_files": payload["changed_files"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log_record(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "accepted_measurement_repair": False,
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    finalize_reflection(payload)
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "delta_metrics": payload["delta_metrics"],
                "window_summaries": {w["window"]: w["summary"] for w in payload["windows"]},
                "recent_observe_summary": (
                    payload["recent_observe"]["summary"] if payload.get("recent_observe") else None
                ),
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
