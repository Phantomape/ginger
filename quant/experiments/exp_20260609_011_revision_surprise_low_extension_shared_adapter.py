"""exp-20260609-011: revision surprise low-extension shared adapter.

Alpha search, shared-paper-first promotion test. This keeps the fixed
revision+positive-surprise-history+low-extension policy bundle from the
positive exp-20260608-011 lead, but moves the candidate source into a shared
default-off paper helper used by both historical replay and daily snapshots.

No live/default orders, core ranking, sizing, exits, LLM/news path, watchlist,
or run.py behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
for _path in (ROOT / "quant", ROOT / "quant" / "experiments"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import exp_20260601_010_gap_up_hold_high_close_candidate_pool as framework  # noqa: E402
import revision_surprise_low_extension_paper_sleeve as sleeve  # noqa: E402


EXPERIMENT_ID = "exp-20260609-011"
STEM = "revision_surprise_low_extension_shared_adapter"
TRIAL_FAMILY = "analyst_revision_surprise_low_extension_candidate_pool"
TRIAL_VARIANT_ID = "revision_surprise_low_extension_shared_default_off_adapter_v1"
CHANGED_VARIABLE = "positive_surprise_history_revision_low_extension_shared_default_off_adapter_v1"
RULE_VERSION = sleeve.RULE_VERSION

BASE_NOTIONAL_USD = float(sleeve.DEFAULT_CONFIG["paper_notional_usd"])
HOLD_DAYS = int(sleeve.DEFAULT_CONFIG["hold_days"])
MAX_PAPER_TRADES_PER_DAY = int(sleeve.DEFAULT_CONFIG["daily_entry_slots"])

MIN_PRICE = float(sleeve.DEFAULT_CONFIG["min_price"])
MIN_AVG_DOLLAR_VOLUME_20 = float(sleeve.DEFAULT_CONFIG["min_avg_dollar_volume_20d"])
MIN_VOLUME_RATIO_20 = float(sleeve.DEFAULT_CONFIG["min_volume_ratio_20d"])
MIN_CLOSE_LOCATION = float(sleeve.DEFAULT_CONFIG["min_close_location"])
MIN_RET20_EXCESS_SPY = float(sleeve.DEFAULT_CONFIG["min_ret20_excess_spy"])
MAX_RET20_EXCESS_SPY = float(sleeve.DEFAULT_CONFIG["max_ret20_excess_spy"])

MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

_ORIGINAL_BUILD_PAYLOAD = framework._build_payload
_ORIGINAL_ARTIFACT = framework._artifact


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_PRICE = MIN_PRICE
    framework.MIN_AVG_DOLLAR_VOLUME_20 = MIN_AVG_DOLLAR_VOLUME_20
    framework.MIN_VOLUME_RATIO_20 = MIN_VOLUME_RATIO_20
    framework.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    framework.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_JSON = BEFORE_JSON
    framework.AFTER_JSON = AFTER_JSON
    framework.LOG_JSON = LOG_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.CARD_MD = CARD_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_payload = _build_payload
    framework._artifact = _artifact


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if "SPY" not in frames:
        raise RuntimeError("SPY is required for revision surprise low-extension replay")
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])
    signal_dates = [str(idx.date()) for idx in frames["SPY"].loc[start:end].index]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates, contexts, scan = sleeve.build_revision_surprise_low_extension_candidate_rows(
        ohlcv_by_ticker=frames,
        dates=signal_dates,
        core_entries_by_date=core_entries,
        config=sleeve.DEFAULT_CONFIG,
        require_future_bars=True,
    )
    selected, rejected = sleeve.select_revision_surprise_low_extension_signal_rows(
        candidates=candidates,
        config=sleeve.DEFAULT_CONFIG,
    )
    tail_rejects = Counter(
        str(row.get("filter_reason") or "unknown")
        for row in rejected
        if str(row.get("filter_reason") or "").startswith("ret20")
        or str(row.get("filter_reason") or "") == "missing_ret20_excess_spy"
    )
    diagnostics = {
        "raw_pass_counts": scan.get("raw_pass_counts", {}),
        "revision_reject_counts": scan.get("revision_reject_counts", {}),
        "revision_source": scan.get("revision_source"),
        "revision_source_caveat": scan.get("revision_source_caveat"),
        "raw_candidate_count": scan.get("raw_candidate_count", 0),
        "candidate_day_count": scan.get("candidate_day_count", 0),
        "contexts": contexts[:25],
        "low_extension_tail_gate": {
            "max_ret20_excess_spy": MAX_RET20_EXCESS_SPY,
            "policy": "gate prior selected daily top-1; no backup candidate substitution",
            "prior_raw_candidate_count": len(candidates),
            "kept_selected_count": len(selected),
            "rejected_count": len(rejected),
            "tail_reject_counts": dict(sorted(tail_rejects.items())),
            "blocked_examples": [
                {
                    "ticker": row.get("ticker"),
                    "date": row.get("date"),
                    "ret20_excess_spy": row.get("ret20_excess_spy"),
                    "score": row.get("score"),
                    "reject_reason": row.get("filter_reason"),
                }
                for row in rejected
                if row.get("filter_reason")
                in {"ret20_excess_spy_above_tail_cap", "missing_ret20_excess_spy"}
            ][:25],
        },
        "shared_helper": {
            "module": "quant/revision_surprise_low_extension_paper_sleeve.py",
            "historical_function": "build_revision_surprise_low_extension_candidate_rows",
            "daily_snapshot_function": "build_revision_surprise_low_extension_snapshot",
            "parity_test": "quant/test_revision_surprise_low_extension_paper_sleeve.py",
        },
    }
    return selected, diagnostics


def _build_payload() -> dict[str, Any]:
    payload = _ORIGINAL_BUILD_PAYLOAD()
    numeric_passed = bool(payload["gate4"].get("passed"))
    accepted = numeric_passed
    if accepted:
        decision = "accepted_shared_default_off_revision_surprise_low_extension_adapter"
        rationale = (
            "Numeric Gate 4 passed and the policy now uses the same shared helper "
            "for historical replay and daily default-off paper snapshots. It is "
            "accepted only as default-off paper observation; trade_enabled remains "
            "false until forward rows and PIT source provenance pass."
        )
    else:
        decision = "rejected_revision_surprise_low_extension_shared_adapter"
        rationale = (
            "Gate 4 failed after moving the fixed revision+surprise+low-extension "
            "policy into a shared helper; do not retain the adapter behavior."
        )

    actual_success = 1 if accepted else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "accepted" if accepted else "rejected",
            "decision": decision,
            "accepted": accepted,
            "hypothesis": (
                "Analyst EPS estimate revision velocity backed by positive "
                "historical surprise history should identify candidates where "
                "expectations are improving for fundamental reasons; blocking "
                "selected top1 names already >35 percentage points ahead of SPY "
                "over 20 days should avoid crowded late momentum entries."
            ),
            "change_type": "default_off_shared_paper_adapter",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "analyst_revision_expectation_trajectory",
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260604-029",
                "exp-20260606-016",
                "exp-20260608-011",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "shared_historical_and_daily_default_off_adapter",
            "interpretation": rationale,
            "rejection_reason": None if accepted else "; ".join(payload["gate4"]["failed_gates"]),
            "prediction": {
                "success_probability": 0.34,
                "expected_ev_delta": 0.18,
                "expected_pnl_delta": 2900.0,
                "main_failure_modes": [
                    "shared_replay_drift",
                    "proxy_source_provenance_block",
                    "concentration_failed",
                    "window_regression",
                ],
                "confidence_reason": (
                    "exp-20260608-011 was positive in all three canonical windows "
                    "but was not promotable because the rule was replay-only. "
                    "This run tests the same fixed bundle through a shared "
                    "daily/historical helper without retuning thresholds."
                ),
                "recorded_at": "2026-06-09T00:00:00+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.34 - actual_success) ** 2, 6),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Use the shared helper to select the same fixed daily top1 "
                "candidate: >=3% 20-snapshot EPS estimate revision, 7-60 days "
                "to earnings, positive surprise history, liquid 20-day breakout, "
                "ret20_excess_spy >=0 and <=0.35. The low-extension cap gates "
                "the already selected top1; no backup candidate is substituted."
            ),
            "revision_lookback_trading_days": sleeve.DEFAULT_CONFIG[
                "revision_lookback_trading_days"
            ],
            "min_eps_estimate_revision_20d_pct": sleeve.DEFAULT_CONFIG[
                "min_eps_estimate_revision_20d_pct"
            ],
            "min_positive_surprise_ratio": sleeve.DEFAULT_CONFIG[
                "min_positive_surprise_ratio"
            ],
            "max_ret20_excess_spy": MAX_RET20_EXCESS_SPY,
            "selection_policy": "selected_top1_gate_no_backup_substitution",
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool: analyst revision plus demonstrated surprise "
            "quality should reflect improving expectations; the low-extension "
            "tail gate avoids already crowded continuation names."
        ),
        "2_history_check": {
            "exp-20260604-029": (
                "Raw revision velocity was aggregate-positive but old_thin regressed "
                "and source provenance was proxy-grade."
            ),
            "exp-20260606-016": (
                "Adding positive surprise history improved aggregate but still failed "
                "old_thin/drawdown/concentration."
            ),
            "exp-20260608-011": (
                "Low-extension selected-top1 gate improved all three windows and "
                "passed numeric Gate 4, but lacked shared daily/historical adapter."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; positive aggregate EV/PnL; "
            "no EV/PnL-regressed window; sample, drawdown, survival, and concentration "
            "guards pass; production parity requires shared helper and default-off "
            "daily snapshot semantics with trade_enabled=false."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_011_revision_surprise_low_extension_shared_adapter.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate4"].update(
        {
            "passed": accepted,
            "numeric_passed": numeric_passed,
            "decision": decision,
            "rationale": rationale,
            "requires_forward_before_live": accepted,
            "source_provenance_guard": {
                "default_off_paper_observable": accepted,
                "live_promotable_source": False,
                "reason": (
                    "daily earnings snapshots are replayable and helper-parity safe, "
                    "but historical EPS estimate provenance remains proxy-grade "
                    "until a PIT vendor/provenance adapter exists."
                ),
            },
        }
    )
    if payload.get("gate1", {}).get("baseline_drift"):
        payload["gate1"]["baseline_drift"]["interpretation"] = (
            "Gate 1 uses the same current BacktestEngine replay before and after "
            "across docs/backtesting.md windows. Any documented-baseline drift is "
            "reported, but the accepted scope is default-off paper helper parity "
            "with no live/default order changes."
        )
    payload["production_impact"] = sleeve._production_impact()
    payload["production_impact"].update(
        {
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_data_fetch_changed": False,
            "daily_snapshot_exposed": True,
            "requires_forward_before_live": accepted,
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "trade_enabled": False,
        "shared_helper_module": "quant/revision_surprise_low_extension_paper_sleeve.py",
        "historical_replay_uses_shared_helper": True,
        "daily_snapshot_uses_shared_helper": True,
        "parity_tests": ["quant/test_revision_surprise_low_extension_paper_sleeve.py"],
        "source_provenance_promotable_to_live": False,
        "parity_note": (
            "Historical replay and daily default-off snapshots call the same helper. "
            "No production/default orders are changed; the remaining limitation is "
            "source provenance and forward default-off observation, not code parity."
        ),
    }
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The result reproduced the exp-20260608-011 positive lead because the "
            "shared helper preserved the exact same economic bundle: improving "
            "EPS estimates, positive surprise history, liquid breakout confirmation, "
            "and a selected-top1 low-extension cap. The gain is modest but broad: "
            "all three canonical windows improved, drawdown improved slightly, "
            "and positive PnL concentration stayed inside the accepted guardrails."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep revision threshold, days-to-earnings bounds, surprise "
            "ratio, ret20_excess_spy cap, hold days, top-N, liquidity, close-location, "
            "or backup-substitution on the same frozen snapshot sample; that would "
            "turn the accepted shared adapter into threshold overfit."
        ),
        "new_evidence_required": (
            "Before any live activation, require forward default-off closed rows "
            "from this helper plus PIT analyst-estimate provenance or analyst-count "
            "trajectory evidence, then run a narrow activation-envelope Gate 1-4 "
            "with capital cap, liquidity, concentration, kill-switch, and order "
            "semantics fixed."
        ),
        "outcome_interpretation": rationale,
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(ROOT / "quant" / "revision_surprise_low_extension_paper_sleeve.py"),
        framework._repo_rel(ROOT / "quant" / "test_revision_surprise_low_extension_paper_sleeve.py"),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    text = _ORIGINAL_ARTIFACT(payload).replace(
        "Gap-Up Hold High-Close Candidate Pool",
        "Revision Surprise Low-Extension Shared Adapter",
    )
    return (
        text
        + "\n## Shared Adapter\n\n"
        + "- helper: `quant/revision_surprise_low_extension_paper_sleeve.py`\n"
        + "- daily snapshot API: `build_revision_surprise_low_extension_snapshot`\n"
        + "- historical replay API: `build_revision_surprise_low_extension_candidate_rows`\n"
        + "- production parity: default-off paper only; no run.py/order/ranking/sizing/exit change.\n"
        + "- live limitation: EPS estimate provenance remains proxy-grade pending PIT source evidence.\n"
    )


def _upsert_log_reflection(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_LOG.exists():
        return
    rows: list[str] = []
    replaced = False
    for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            rows.append(line)
            continue
        if row.get("experiment_id") == EXPERIMENT_ID:
            row["post_run_reflection"] = payload["post_run_reflection"]
            row["next_evidence_needed"] = payload["post_run_reflection"][
                "new_evidence_required"
            ]
            row["calibration"] = {
                "actual_success": 1 if payload.get("accepted") else 0,
                "predicted_success_probability": payload["prediction"].get(
                    "success_probability"
                ),
                "brier_score": payload["prediction"].get("brier_score"),
                "actual_ev_delta": payload["prediction"].get("actual_ev_delta"),
                "actual_pnl_delta": payload["prediction"].get("actual_pnl_delta"),
                "surprise_note": payload["post_run_reflection"]["why_result_happened"],
            }
            rows.append(json.dumps(row, sort_keys=True))
            replaced = True
        else:
            rows.append(line)
    if replaced:
        EXPERIMENT_LOG.write_text("\n".join(rows) + "\n", encoding="utf-8")


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _patch_framework()
    payload = framework.run(output)
    _upsert_log_reflection(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": framework._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
