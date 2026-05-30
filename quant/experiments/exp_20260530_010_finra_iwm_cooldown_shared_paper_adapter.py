"""exp-20260530-010: shared FINRA IWM cooldown paper adapter.

This closeout promotes the accepted exp-20260530-007 replay lead into a shared
default-off paper adapter. It does not change live/core orders. The three-window
Gate 4 evidence remains the canonical exp-20260530-007 before/after replay, and
this run records the production/backtest parity boundary plus focused tests for
the shared helper.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from quant.finra_iwm_paper_sleeve import (
        COOLDOWN_RULE_VERSION,
        MARKET_CONFIRMATION_RULE_VERSION,
        RULE_VERSION,
        SLEEVE_NAME,
        SOURCE_RULE_VERSION,
    )
except ImportError:  # pragma: no cover - direct script execution
    import sys

    REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORT))
    from quant.finra_iwm_paper_sleeve import (
        COOLDOWN_RULE_VERSION,
        MARKET_CONFIRMATION_RULE_VERSION,
        RULE_VERSION,
        SLEEVE_NAME,
        SOURCE_RULE_VERSION,
    )


EXPERIMENT_ID = "exp-20260530-010"
STEM = "finra_iwm_cooldown_shared_paper_adapter"
REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_010_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
PRIOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260530-007"
    / "exp_20260530_007_finra_iwm_same_ticker_cooldown_candidate_pool.json"
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _window_table(prior: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    before_metrics = prior.get("before_metrics") or {}
    after_metrics = prior.get("after_metrics") or {}
    deltas = (prior.get("delta_metrics") or {}).get("by_window") or {}
    for label in ("late_strong", "mid_weak", "old_thin"):
        before = before_metrics.get(label) or {}
        after = after_metrics.get(label) or {}
        delta = deltas.get(label) or {}
        rows.append(
            {
                "window": label,
                "before_ev": before.get("expected_value_score"),
                "after_ev": after.get("expected_value_score"),
                "delta_ev": delta.get("expected_value_score"),
                "before_pnl": before.get("total_pnl"),
                "after_pnl": after.get("total_pnl"),
                "delta_pnl": delta.get("total_pnl"),
                "before_survival_rate": before.get("survival_rate"),
                "after_survival_rate": after.get("survival_rate"),
                "target_trades": len((prior.get("target_trades_by_window") or {}).get(label) or []),
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    prior = _load_json(PRIOR_JSON)
    aggregate = (prior.get("delta_metrics") or {}).get("aggregate") or {}
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": "accepted_default_off_finra_iwm_shared_adapter",
        "decision": "accepted_default_off_finra_iwm_shared_adapter",
        "hypothesis": (
            "The accepted FINRA short-pressure IWM-confirmed seven-day same-ticker "
            "cooldown candidate pool should become a shared default-off paper "
            "adapter so production can collect forward replacement-value evidence "
            "without changing live orders."
        ),
        "change_type": "default_off_paper_adapter",
        "changed_variable": "finra_iwm_cooldown_shared_default_off_adapter_v1",
        "single_causal_variable": "shared FINRA IWM cooldown default-off paper adapter boundary",
        "trial_family": "finra_iwm_same_ticker_cooldown_candidate_pool",
        "trial_variant_id": "finra_iwm_cooldown_shared_default_off_adapter_v1",
        "nearby_prior_experiments": [
            "exp-20260530-007",
            "exp-20260530-005",
            "exp-20260529-017",
            "exp-20260529-018",
        ],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / entry: preserve the accepted FINRA+IWM+cooldown "
                "paper source and move it into production-visible default-off "
                "forward collection."
            ),
            "2_history_check": {
                "exp-20260530-007": (
                    "Accepted replay candidate: aggregate EV +0.3308 / +4.19%, "
                    "PnL +$8,298.40 / +3.53%, 3/3 windows improved, 38 target "
                    "trades, concentration passed."
                ),
                "exp-20260530-005": (
                    "IWM-confirmed source improved all windows but failed the "
                    "single-ticker positive-share guard before cooldown."
                ),
                "exp-20260529-018": (
                    "FINRA score monotonicity failed, so this run does not retune "
                    "the score or threshold."
                ),
            },
            "3_single_causal_variable": "shared FINRA IWM cooldown default-off paper adapter boundary",
            "4_acceptance_standard": (
                "Use docs/backtesting.md three windows from exp-20260530-007 for "
                "paper alpha evidence; adapter acceptance additionally requires "
                "production-visible shared code, no live/core order impact, and "
                "focused parity/ledger tests."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260530_010_finra_iwm_cooldown_shared_paper_adapter.py"
            ),
        },
        "three_window_evidence_source": _repo_rel(PRIOR_JSON),
        "three_window_result": {
            "windows": _window_table(prior),
            "aggregate": aggregate,
            "gate4": prior.get("gate4"),
            "target_trade_summary": prior.get("target_trade_summary"),
        },
        "adapter_validation": {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "market_confirmation_rule_version": MARKET_CONFIRMATION_RULE_VERSION,
            "same_ticker_cooldown_rule_version": COOLDOWN_RULE_VERSION,
            "shared_files": [
                "quant/finra_iwm_paper_sleeve.py",
                "quant/run.py",
                "quant/default_off_alpha_attribution.py",
                "quant/report_generator.py",
                "quant/data_paths.py",
                "quant/test_finra_iwm_paper_sleeve.py",
            ],
            "focused_tests": [
                "py_compile finra_iwm/run/report/default_off modules",
                "pytest quant/test_finra_iwm_paper_sleeve.py quant/test_default_off_alpha_attribution.py -q",
            ],
        },
        "production_impact": {
            "shared_policy_changed": True,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "replay_only": False,
            "default_off_paper_only": True,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "parity_test_added": True,
        },
        "acceptance_basis": (
            "Accepted as a default-off production-visible adapter, not as live "
            "capital. It preserves the accepted three-window paper lead and starts "
            "forward evidence collection without changing core/live behavior."
        ),
        "next_evidence_needed": (
            "Closed forward replacement-value rows, cash/core displacement "
            "comparison, concentration and kill-gate monitoring before any live "
            "activation review."
        ),
        "related_files": [
            "quant/finra_iwm_paper_sleeve.py",
            "quant/test_finra_iwm_paper_sleeve.py",
            "quant/run.py",
            "quant/default_off_alpha_attribution.py",
            "quant/report_generator.py",
            "quant/data_paths.py",
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(PRIOR_JSON),
        ],
    }
    return payload


def build_artifact(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260530-010 FINRA IWM Cooldown Shared Paper Adapter",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single variable: move the accepted FINRA+IWM seven-day same-ticker cooldown paper source into a shared default-off production adapter.",
        "",
        "## Three-Window Evidence",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["three_window_result"]["windows"]:
        lines.append(
            "| {window} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | ${before_pnl:,.2f} | ${after_pnl:,.2f} | ${delta_pnl:+,.2f} | {target_trades} |".format(
                **row
            )
        )
    aggregate = payload["three_window_result"]["aggregate"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate.get('expected_value_score_delta_sum')}` (`{aggregate.get('expected_value_score_delta_pct')}`)",
            f"- PnL delta: `${aggregate.get('total_pnl_delta_sum')}` (`{aggregate.get('total_pnl_delta_pct')}`)",
            "- Gate 4 from `exp-20260530-007` passed: 3/3 EV/PnL windows improved, 38 target trades, max drawdown drift +0.03pp, survival unchanged, concentration passed.",
            "",
            "## Production Parity",
            "",
            "The adapter is shared production code and is default-off paper only. `trade_enabled=false`; it does not change core signals, rankings, sizing, exits, watchlists, or orders.",
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(build_artifact(payload), encoding="utf-8")
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": payload["decision"], "artifact": _repo_rel(OUT_JSON)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
