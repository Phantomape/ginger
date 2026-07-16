"""exp-20260716-010: leave-one-policy-family-out ablation of the accepted
default-on sizing/cap/add-on stack under CASH_LEDGER_ENFORCED.

Every boost, cap-raise, haircut, and add-on policy in the current champion was
accepted while the backtester booked fills with no execution-date cash
constraint (peak reconstructed overdraft -$188k on $100k initial capital,
exp-20260715-008). Under the enforced ledger (exp-20260715-010 anchor,
aggregate EV 6.2057 / PnL $130,992.36 / 49 trades), the marginal contribution
of each family may have changed sign: extra basis now displaces other entries
instead of being financed by free leverage.

Design: single batch. One `baseline_verify` pass (no patches; must reproduce
the published cash-feasible anchor identity exactly — Gate 1) plus 11 ablation
arms. Each arm neutralizes ONE policy family (multipliers -> 1.0, cap raises ->
MAX_POSITION_PCT, add-on family -> ADDON_ENABLED False) via monkeypatched
module constants (exp-20260428-025 pattern) and replays the three canonical
windows under the exp-20260712-015 frozen behavior inputs. Everything else,
including cash-admission semantics, is locked.

Predeclared verdict per arm (fixed before any ablation run):
  - removal_candidate_nominated: ablated aggregate EV > anchor EV * 1.10 AND
    ablated aggregate PnL > anchor PnL AND worst-window max drawdown not worse
    than anchor + 1.0pp AND per-window EV improved in >= 2 of 3 windows.
    Because 11 arms are compared, a nomination is NOT accepted removal in this
    ticket; it requires a dedicated follow-up confirmation ticket with its own
    predeclared Gate 4 (multiple-comparison guard).
  - pays_its_way: ablated aggregate EV strictly below anchor EV (the policy
    still adds value under cash enforcement).
  - simplification_candidate: |aggregate EV delta| <= 2% of anchor EV while the
    family touched >= 1 signal (dead weight; removal ~free).
  - mixed_inconclusive: everything else.
Ticket-level decision: rejected (no removal promoted) unless a follow-up
confirmation is explicitly nominated; the marginal-contribution table itself is
the deliverable.

Reproduce:
    .\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260716_010_cash_feasible_policy_stack_ablation.py
Optional: pass arm names as argv to run a subset (baseline_verify always runs).
"""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backtester import BacktestEngine  # noqa: E402
import portfolio_engine  # noqa: E402
import production_parity  # noqa: E402

import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402

EXPERIMENT_ID = "exp-20260716-010"
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT = EXP_DIR / "exp_20260716_010_cash_feasible_policy_stack_ablation.json"
ANCHOR_SUMMARY = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)

PE = "portfolio_engine"
PP = "production_parity"
_MODULES = {PE: portfolio_engine, PP: production_parity}

BASE_CAP = portfolio_engine.MAX_POSITION_PCT  # 0.40 neutral value for cap raises

# Each family: list of (module_key, constant_name, neutral_value) patches and
# optional BacktestEngine config overrides. Multipliers neutralize to 1.0;
# cap raises neutralize to the base MAX_POSITION_PCT.
FAMILIES: dict[str, dict[str, Any]] = {
    "riskon_leader_boosts_off": {
        "accepted_by": "exp-20260501-024 lineage (risk-on regime boosts + SPY-relative leader 2.0x/0.50 cap)",
        "patches": [
            (PE, "RISK_ON_UNMODIFIED_RISK_MULTIPLIER", 1.0),
            (PE, "RISK_ON_UNMODIFIED_LOW_SCORE_RISK_MULTIPLIER", 1.0),
            (PE, "RISK_ON_UNMODIFIED_MID_SCORE_RISK_MULTIPLIER", 1.0),
            (PE, "RISK_ON_SPY_RELATIVE_LEADER_RISK_MULTIPLIER", 1.0),
            (PE, "RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT", BASE_CAP),
        ],
    },
    "clean_spy_leader_family_off": {
        "accepted_by": "exp-20260513-036 lineage (clean SPY leader signal-day 1.10x + 0.525/0.60/0.70 caps)",
        "patches": [
            (PE, "CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER", 1.0),
            (PE, "CLEAN_SPY_LEADER_SIGNAL_DAY_MAX_POSITION_PCT", BASE_CAP),
            (PE, "CLEAN_SPY_CAP_ONLY_LEADER_MAX_POSITION_PCT", BASE_CAP),
            (PE, "CLEAN_SPY_CAP_ONLY_RS20_LEADER_MAX_POSITION_PCT", BASE_CAP),
        ],
    },
    "rs_topups_off": {
        "accepted_by": "rs20 entry-state 1.10x + rs60 top-quintile 1.15x lineages",
        "patches": [
            (PE, "RS20_ENTRY_STATE_RISK_MULTIPLIER", 1.0),
            (PE, "RS60_TOP_QUINTILE_RISK_MULTIPLIER", 1.0),
        ],
    },
    "signal_day_green_off": {
        "accepted_by": "exp-20260513-007 (signal-day ticker green candle 1.05x)",
        "patches": [(PE, "SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER", 1.0)],
    },
    "mid_sector_dispersion_off": {
        "accepted_by": "exp-20260506-032 (trend mid-sector-dispersion 1.25x)",
        "patches": [(PE, "TREND_MID_SECTOR_DISPERSION_RISK_MULTIPLIER", 1.0)],
    },
    "financials_boosts_off": {
        "accepted_by": "exp-20260501-006 lineage (financials 1.5x / sector-leader 2.5x + 0.50/0.55 caps)",
        "patches": [
            (PE, "TREND_FINANCIALS_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_FINANCIALS_SECTOR_LEADER_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_FINANCIALS_SECTOR_LEADER_MAX_POSITION_PCT", BASE_CAP),
            (PE, "TREND_FINANCIALS_MID_DISPERSION_LEADER_MAX_POSITION_PCT", BASE_CAP),
        ],
    },
    "commodities_gold_boosts_off": {
        "accepted_by": "commodities/gold near-high boost + cap lineages",
        "patches": [
            (PE, "TREND_COMMODITIES_NEAR_HIGH_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_COMMODITIES_NEAR_HIGH_MAX_POSITION_PCT", BASE_CAP),
            (PE, "TREND_GOLD_NEAR_HIGH_MAX_POSITION_PCT", BASE_CAP),
            (PE, "BREAKOUT_COMMODITIES_MAX_POSITION_PCT", BASE_CAP),
        ],
    },
    "quality_slot_topups_off": {
        "accepted_by": "exp-20260517-004/-009 + quality top-up lineages (1.075/1.025/1.075/1.05)",
        "patches": [
            (PE, "CORE_CONFIRMED_QUALITY_RISK_MULTIPLIER", 1.0),
            (PE, "GREEN_DECEL_QUALITY_NONCONSUMER_RISK_MULTIPLIER", 1.0),
            (PP, "SCARCE_SLOT_RANK1_RISK_MULTIPLIER", 1.0),
            (PP, "AMPLE_SLOT_STOCK_RANK1_RISK_MULTIPLIER", 1.0),
        ],
    },
    "ma200_extension_topups_off": {
        "accepted_by": "price-vs-200MA extension top-ups (1.025x / trend 1.125x)",
        "patches": [
            (PE, "PRICE_VS_200MA_EXTENSION_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_PRICE_VS_200MA_EXTENSION_RISK_MULTIPLIER", 1.0),
        ],
    },
    "defensive_haircuts_off": {
        "accepted_by": "accepted defensive haircut stack (TQS, sector/strategy DTE/gap zero-or-quarter, TSM/ISRG 0.25x)",
        "patches": [
            (PE, "LOW_TQS_RISK_MULTIPLIER", 1.0),
            (PE, "LOW_TQS_BREAKOUT_NON_EXEMPT_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_INDUSTRIALS_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_TECH_GAP_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_TECH_TIGHT_GAP_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_TECH_NEAR_HIGH_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_TECH_DTE_RISK_MULTIPLIER", 1.0),
            (PE, "BREAKOUT_INDUSTRIALS_GAP_RISK_MULTIPLIER", 1.0),
            (PE, "BREAKOUT_COMMS_NEAR_HIGH_RISK_MULTIPLIER", 1.0),
            (PE, "BREAKOUT_COMMS_GAP_RISK_MULTIPLIER", 1.0),
            (PE, "BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER", 1.0),
            (PE, "BREAKOUT_TECH_DTE_RISK_MULTIPLIER", 1.0),
            (PE, "BREAKOUT_HEALTHCARE_DTE_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_HEALTHCARE_DTE_RISK_MULTIPLIER", 1.0),
            (PE, "TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER", 1.0),
            (PE, "TSM_CORE_RISK_MULTIPLIER", 1.0),
            (PE, "ISRG_CORE_RISK_MULTIPLIER", 1.0),
        ],
    },
    "addon_stack_off": {
        "accepted_by": "exp-20260428-005 lineage (add-on fraction 0.50 + follow-through caps)",
        "patches": [],
        "config": {"ADDON_ENABLED": False},
    },
}

EV_REMOVAL_GAIN_MIN = 0.10  # AGENTS.md §5 capital-allocation retune bar
EV_DEADWEIGHT_BAND = 0.02
DRAWDOWN_TOLERANCE_PP = 1.0

HEADLINE_KEYS = (
    "expected_value_score",
    "total_pnl",
    "sharpe_daily",
    "max_drawdown_pct",
    "win_rate",
    "signals_generated",
    "signals_survived",
    "survival_rate",
)


def _run_window(spec: dict[str, str], frozen: dict[str, Any],
                patches: list[tuple[str, str, Any]],
                config_overrides: dict[str, Any]) -> dict[str, Any]:
    behavior = frozen["behavior"]
    calendar = gate1._calendar_dates(frozen)
    config = dict(gate1.RUN_CONFIG)
    config["CASH_LEDGER_ENFORCED"] = True
    config.update(config_overrides)
    saved: list[tuple[Any, str, Any]] = []
    try:
        for mod_key, name, value in patches:
            module = _MODULES[mod_key]
            saved.append((module, name, getattr(module, name)))
            setattr(module, name, value)
        engine = BacktestEngine(
            list(behavior["universe"]),
            start=spec["start"],
            end=spec["end"],
            config=config,
            ohlcv_warehouse_path=str(gate1.WAREHOUSE),
            ohlcv_warehouse_snapshot_source=spec["snapshot"],
            replay_llm=False,
            replay_news=False,
            include_pilot_sleeve=False,
            require_non_ohlcv=False,
            include_oracle_diagnostics=False,
        )
        engine._earnings_snapshots = behavior["earnings_snapshots"]
        engine._download_earnings_calendar = lambda: {
            ticker: list(values) for ticker, values in calendar.items()
        }
        result = engine.run()
    finally:
        for module, name, value in saved:
            setattr(module, name, value)
    if result.get("error"):
        raise RuntimeError(f"{spec['label']}: {result['error']}")
    return result


def _finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _headline(result: dict[str, Any]) -> dict[str, Any]:
    metrics = {key: _finite(result.get(key)) for key in HEADLINE_KEYS}
    for key in ("expected_value_score", "total_pnl"):
        if metrics[key] is None:
            raise RuntimeError(f"non-finite {key} in ablated run")
    metrics["trade_count"] = result.get("total_trades")
    ledger = result.get("cash_ledger") or {}
    metrics["negative_cash_event_count"] = ledger.get(
        "negative_cash_event_count",
        len(ledger.get("negative_cash_events") or []),
    )
    metrics["min_cash"] = ledger.get("min_cash")
    return metrics


def _gate2_fields(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades") or []
    missing_entry = [t.get("trade_key") for t in trades if not t.get("entry_date")]
    missing_stop = [t.get("trade_key") for t in trades if t.get("stop_price") in (None, 0)]
    return {
        "trade_count": len(trades),
        "entry_date_missing": missing_entry,
        "stop_price_missing": missing_stop,
        "target_mult_present": all("target_mult_used" in t for t in trades),
        "passed": not missing_entry and not missing_stop,
    }


def _gate1_identity_check(baseline_results: dict[str, dict[str, Any]],
                          anchor_windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for label, result in baseline_results.items():
        identity = gate1._result_identity(result)
        ref = anchor_windows[label]
        entry = {
            "trade_rows_sha256_match": identity["trade_rows_sha256"] == ref["trade_rows_sha256"],
            "daily_return_series_sha256_match": (
                identity["daily_return_series_sha256"] == ref["daily_return_series_sha256"]
            ),
            "expected_value_score_match": (
                result.get("expected_value_score") == ref["expected_value_score"]
            ),
            "total_pnl_match": result.get("total_pnl") == ref["total_pnl"],
            "trade_count_match": result.get("total_trades") == ref["trade_count"],
        }
        entry["all_match"] = all(entry.values())
        checks[label] = entry
    checks["all_windows_match"] = all(
        entry["all_match"] for entry in checks.values() if isinstance(entry, dict)
    )
    return checks


def _sizing_families_touched(result: dict[str, Any],
                             patches: list[tuple[str, str, Any]]) -> int:
    """Count signals the ablated family actually touched in the BASELINE run.

    Attribution keys do not map 1:1 to constants, so this is a coarse
    signal-contact count used only for the simplification_candidate label.
    """
    attribution = result.get("sizing_rule_signal_attribution") or {}
    tokens = set()
    for _, name, _ in patches:
        stem = name.lower()
        for suffix in ("_risk_multiplier", "_max_position_pct"):
            stem = stem.replace(suffix, "")
        tokens.add(stem)
    touched = 0
    for key, value in attribution.items():
        key_l = key.lower()
        if any(token and token in key_l for token in tokens):
            if isinstance(value, dict):
                touched += int(value.get("signals_seen", 0))
    return touched


def _arm_verdict(anchor_agg: dict[str, float], arm: dict[str, Any],
                 baseline_touch_count: int) -> str:
    ev_delta = arm["aggregate_ev"] - anchor_agg["ev"]
    ev_gain = ev_delta / anchor_agg["ev"] if anchor_agg["ev"] else 0.0
    windows_improved = sum(
        1 for row in arm["windows"].values() if row["ev_delta"] > 0
    )
    dd_ok = arm["worst_max_drawdown_pct"] <= (
        anchor_agg["worst_max_drawdown_pct"] + DRAWDOWN_TOLERANCE_PP / 100.0
    )
    if (
        ev_gain > EV_REMOVAL_GAIN_MIN
        and arm["aggregate_pnl"] > anchor_agg["pnl"]
        and dd_ok
        and windows_improved >= 2
    ):
        return "removal_candidate_nominated"
    if abs(ev_gain) <= EV_DEADWEIGHT_BAND and baseline_touch_count > 0:
        return "simplification_candidate"
    if arm["aggregate_ev"] < anchor_agg["ev"]:
        return "pays_its_way"
    return "mixed_inconclusive"


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    requested = set(sys.argv[1:])
    arm_names = [n for n in FAMILIES if not requested or n in requested]

    anchor = json.loads(ANCHOR_SUMMARY.read_text(encoding="utf-8"))
    anchor_windows = {w["label"]: w for w in anchor["windows"]}
    anchor_agg = {
        "ev": sum(w["expected_value_score"] for w in anchor["windows"]),
        "pnl": sum(w["total_pnl"] for w in anchor["windows"]),
        "trades": sum(w["trade_count"] for w in anchor["windows"]),
        "worst_max_drawdown_pct": max(
            w["max_drawdown_pct"] for w in anchor["windows"]
        ),
    }

    frozen = gate1._load_or_capture_frozen_inputs(refresh=False)

    # Gate 1: unpatched pass must reproduce the anchor identity exactly.
    print("[gate1] baseline_verify pass", flush=True)
    baseline_results: dict[str, dict[str, Any]] = {}
    gate2: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        t0 = time.time()
        result = _run_window(spec, frozen, [], {})
        baseline_results[spec["label"]] = result
        gate2[spec["label"]] = _gate2_fields(result)
        print(
            f"[gate1] {spec['label']}: EV={result.get('expected_value_score')}"
            f" pnl={result.get('total_pnl')} trades={result.get('total_trades')}"
            f" ({time.time() - t0:.1f}s)",
            flush=True,
        )
    gate1_checks = _gate1_identity_check(baseline_results, anchor_windows)
    if not gate1_checks["all_windows_match"]:
        payload = {
            "schema": "cash_feasible_policy_stack_ablation_v1",
            "experiment_id": EXPERIMENT_ID,
            "status": "aborted_gate1_identity_mismatch",
            "gate1": gate1_checks,
        }
        EXP_DIR.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("[abort] Gate 1 identity mismatch", flush=True)
        return 1
    print("[gate1] anchor identity reproduced in all windows", flush=True)

    arms: dict[str, Any] = {}
    for arm_name in arm_names:
        family = FAMILIES[arm_name]
        patches = family.get("patches", [])
        config_overrides = family.get("config", {})
        arm_rows: dict[str, Any] = {}
        print(f"[arm] {arm_name}", flush=True)
        for spec in gate1.WINDOWS:
            label = spec["label"]
            t0 = time.time()
            result = _run_window(spec, frozen, patches, config_overrides)
            head = _headline(result)
            ref = anchor_windows[label]
            # Full _result_identity() hashes every RESULT_METRICS value with
            # allow_nan=False and ablated runs can carry non-finite side
            # metrics; only the trade-row hash is needed for change detection.
            trade_rows_sha256 = gate1._stable_hash(result.get("trades") or [])
            arm_rows[label] = {
                **head,
                "ev_delta": head["expected_value_score"] - ref["expected_value_score"],
                "pnl_delta": head["total_pnl"] - ref["total_pnl"],
                "trade_count_delta": head["trade_count"] - ref["trade_count"],
                "trade_rows_changed": trade_rows_sha256 != ref["trade_rows_sha256"],
            }
            print(
                f"[arm] {arm_name}/{label}: EV={head['expected_value_score']}"
                f" (d={arm_rows[label]['ev_delta']:+.4f})"
                f" pnl={head['total_pnl']}"
                f" (d={arm_rows[label]['pnl_delta']:+.2f})"
                f" trades={head['trade_count']}"
                f" ({time.time() - t0:.1f}s)",
                flush=True,
            )
        touch_count = sum(
            _sizing_families_touched(baseline_results[label], patches)
            for label in baseline_results
        )
        if arm_name == "addon_stack_off":
            touch_count = sum(
                1
                for label in baseline_results
                for t in (baseline_results[label].get("trades") or [])
                if t.get("addon_count")
            )
        arm_summary = {
            "accepted_by": family.get("accepted_by"),
            "patches": [(m, n, v) for m, n, v in family.get("patches", [])],
            "config_overrides": config_overrides,
            "windows": arm_rows,
            "aggregate_ev": sum(r["expected_value_score"] for r in arm_rows.values()),
            "aggregate_pnl": sum(r["total_pnl"] for r in arm_rows.values()),
            "aggregate_trades": sum(r["trade_count"] for r in arm_rows.values()),
            "worst_max_drawdown_pct": max(
                r["max_drawdown_pct"] for r in arm_rows.values()
            ),
            "negative_cash_events_total": sum(
                r["negative_cash_event_count"] or 0 for r in arm_rows.values()
            ),
            "baseline_family_signal_touch_count": touch_count,
        }
        arm_summary["aggregate_ev_delta"] = arm_summary["aggregate_ev"] - anchor_agg["ev"]
        arm_summary["aggregate_ev_gain_pct"] = (
            arm_summary["aggregate_ev_delta"] / anchor_agg["ev"]
        )
        arm_summary["aggregate_pnl_delta"] = (
            arm_summary["aggregate_pnl"] - anchor_agg["pnl"]
        )
        arm_summary["verdict"] = _arm_verdict(anchor_agg, arm_summary, touch_count)
        arms[arm_name] = arm_summary
        print(
            f"[arm] {arm_name}: aggEV={arm_summary['aggregate_ev']:.4f}"
            f" (d={arm_summary['aggregate_ev_delta']:+.4f},"
            f" {arm_summary['aggregate_ev_gain_pct']:+.2%})"
            f" aggPnL={arm_summary['aggregate_pnl']:.2f}"
            f" verdict={arm_summary['verdict']}",
            flush=True,
        )

    nominations = [n for n, a in arms.items() if a["verdict"] == "removal_candidate_nominated"]
    simplifications = [n for n, a in arms.items() if a["verdict"] == "simplification_candidate"]
    payload = {
        "schema": "cash_feasible_policy_stack_ablation_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started,
        "anchor_summary": str(ANCHOR_SUMMARY.relative_to(ROOT)),
        "anchor_aggregate": anchor_agg,
        "predeclared_rules": {
            "removal_gain_min": EV_REMOVAL_GAIN_MIN,
            "deadweight_band": EV_DEADWEIGHT_BAND,
            "drawdown_tolerance_pp": DRAWDOWN_TOLERANCE_PP,
            "windows_improved_min": 2,
            "note": (
                "removal_candidate_nominated requires a dedicated follow-up "
                "confirmation ticket; 11 simultaneous arms are a multiple-"
                "comparison surface and no removal is accepted inside this ID."
            ),
        },
        "gate1": gate1_checks,
        "gate2": gate2,
        "gate3_note": "no filters added; survival identical to anchor by construction of the baseline pass",
        "arms": arms,
        "removal_candidates_nominated": nominations,
        "simplification_candidates": simplifications,
        "production_impact": "none; no default, constant, order path, or ledger changed; all patches were reverted in-process",
    }
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[done] artifact -> {ARTIFACT}", flush=True)
    print(
        f"[done] nominations={nominations or 'NONE'}"
        f" simplification_candidates={simplifications or 'NONE'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
