"""Close out exp-20260602-014 post-earnings continuation risk support scout.

The intended alpha was a bounded risk scalar for already-selected core trades
with PIT-safe post-earnings continuation confirmation. The current accepted
artifacts do not preserve the per-trade continuation field or the PIT-DTE
before-trade list, so the risk scalar cannot be audited as a production-ready
before/after policy without adding trace instrumentation first.

No strategy, production, or backtester behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260602-014"
STEM = "post_earnings_continuation_risk_support"
DECISION = "rejected_trace_granularity_blocks_continuation_risk_scalar"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _repo_root()
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_014_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _after_trade_field_audit() -> dict[str, Any]:
    after_dir = REPO_ROOT / "data" / "experiments" / "exp-20260602-003"
    required = [
        "post_earnings_continuation_confirmed",
        "post_earnings_event_date",
        "days_since_last_earnings",
    ]
    by_window: dict[str, Any] = {}
    total = 0
    with_any_required = 0
    for path in sorted(after_dir.glob("*_after.json")):
        data = _load_json(path)
        trades = data.get("trades", [])
        window_total = len(trades)
        window_with_any = 0
        coverage = {}
        for field in required:
            present = sum(1 for trade in trades if trade.get(field) not in (None, ""))
            coverage[field] = {
                "present": present,
                "missing": window_total - present,
                "coverage_ratio": round(present / window_total, 6)
                if window_total
                else None,
            }
            if present:
                window_with_any += present
        total += window_total
        with_any_required += sum(
            1
            for trade in trades
            if any(trade.get(field) not in (None, "") for field in required)
        )
        by_window[path.stem.replace("_after", "")] = {
            "trade_count": window_total,
            "trades_with_any_required_field": window_with_any,
            "coverage": coverage,
        }
    return {
        "source": "data/experiments/exp-20260602-003/*_after.json",
        "required_fields": required,
        "total_trades": total,
        "trades_with_any_required_field": with_any_required,
        "passed": with_any_required > 0,
        "by_window": by_window,
    }


def _build_payload(now: str) -> dict[str, Any]:
    exp003_path = (
        REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260602-003"
        / "exp_20260602_003_post_earnings_explicit_continuation.json"
    )
    exp003 = _load_json(exp003_path)
    baseline_path = REPO_ROOT / exp003["baseline_result_file"]
    pit_dte = _load_json(baseline_path)
    after_trade_audit = _after_trade_field_audit()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "lane": "alpha_search",
        "status": "rejected",
        "decision": DECISION,
        "hypothesis": (
            "Already-selected core trend/breakout trades with PIT-safe "
            "post-earnings continuation confirmation may deserve a bounded "
            "risk-budget support scalar."
        ),
        "change_type": "risk_allocation",
        "mechanism_family": "risk_allocation",
        "trial_family": "post_earnings_continuation_risk_support",
        "changed_variable": "post_earnings_continuation_confirmed_risk_scalar_v1",
        "single_causal_variable": "post_earnings_continuation_confirmed_risk_scalar_v1",
        "nearby_prior_experiments": [
            "exp-20260602-003",
            "exp-20260602-004",
            "exp-20260602-006",
            "exp-20260602-011",
            "exp-20260602-012",
        ],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: bounded support for core trades that are "
                "explicitly confirmed as post-earnings continuation."
            ),
            "2_history_check": {
                "exp-20260602-003": (
                    "Accepted explicit continuation semantics with aggregate "
                    "EV +1.5345 and PnL +$42,312.38, but did not retain "
                    "per-trade continuation tags in closed-trade artifacts."
                ),
                "exp-20260602-004_006_011_012": (
                    "Generic post-earnings pools and peer/reaction transfer "
                    "families were not stable enough for promotion."
                ),
            },
            "3_single_causal_variable": (
                "post_earnings_continuation_confirmed_risk_scalar_v1 only"
            ),
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows; require credible "
                "before/after EV/PnL, drawdown, survival, trade count, and "
                "concentration evidence before any production/shared scalar."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260602_014_post_earnings_continuation_risk_support.py"
            ),
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md canonical three windows",
            "current_accepted_stack": exp003["aggregate"]["after"],
            "exp003_before": exp003["aggregate"]["before"],
            "exp003_after": exp003["aggregate"]["after"],
            "passed": True,
        },
        "gate2": {
            "open_position_contract": (
                "No new open-position dependency introduced; entry_date and "
                "target_price requirements remain unchanged."
            ),
            "pit_dte_control_has_trade_trace": bool(pit_dte.get("trades")),
            "exp003_after_trade_field_audit": after_trade_audit,
            "passed": False,
            "blocker": (
                "The accepted continuation artifacts preserve only window-level "
                "before metrics plus after closed trades without continuation "
                "tags. A risk scalar cannot be attributed to a target trade set "
                "or validated for production/backtest parity from these files."
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_core_survival_rate": exp003["aggregate"]["after"][
                "min_survival_rate"
            ],
            "passed": True,
        },
        "gate4": {
            "passed": False,
            "failed_reasons": [
                "target_trade_trace_missing",
                "risk_scalar_after_not_credible_without_per_trade_field",
            ],
            "evaluated_before_after_windows": exp003["by_window"],
            "note": (
                "No after scalar was retained or promoted. Window-level exp003 "
                "increment is not enough to prove a bounded risk-allocation rule."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_orders_changed": False,
            "default_off_paper_only": False,
            "parity_note": (
                "A positive retry must first add shared, production-visible "
                "trace fields to closed trades/candidate events and then run "
                "the same scalar in production/backtest shared sizing code."
            ),
        },
        "why_switched_alpha": (
            "The alpha idea is blocked by trace granularity rather than by a "
            "parameter choice. Per the user instruction, the run switches to a "
            "separate free-OHLCV candidate-pool alpha instead of retuning this."
        ),
        "next_alpha_direction": (
            "OHLCV-only volatility contraction plus relative-strength breakout "
            "candidate pool with strict liquidity and concentration guardrails."
        ),
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    gate2 = payload["gate2"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            'status: "rejected"',
            'lane: "alpha_search"',
            'change_type: "risk_allocation"',
            'mechanism_family: "risk_allocation"',
            'trial_family: "post_earnings_continuation_risk_support"',
            'changed_variable: "post_earnings_continuation_confirmed_risk_scalar_v1"',
            f'completed_at: "{payload["timestamp"]}"',
            f'artifact: "{_repo_rel(OUT_JSON)}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            "Rejected before strategy implementation. The accepted continuation "
            "artifacts do not preserve enough per-trade trace to validate a "
            "risk scalar without risking backtest/production inconsistency.",
            "",
            "## Gate 2 Blocker",
            "",
            f"- PIT-DTE control has trade trace: `{gate2['pit_dte_control_has_trade_trace']}`",
            f"- exp003 after trades with continuation fields: `{gate2['exp003_after_trade_field_audit']['trades_with_any_required_field']}`",
            "",
            "## Decision",
            "",
            f"`{DECISION}`. Do not promote or retry this scalar until the shared "
            "closed-trade/candidate-event trace carries the continuation field.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "rejected",
            "completed_at": payload["timestamp"],
            "result": {
                "decision": DECISION,
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "summary": payload["gate2"]["blocker"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _write_manifest(now: str) -> None:
    files = {
        "runner": _repo_rel(Path(__file__)),
        "result": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "card": _repo_rel(CARD_MD),
        "manifest": _repo_rel(MANIFEST_JSON),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": now,
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def main() -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = _build_payload(now)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _update_ticket(payload)
    _write_manifest(now)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": DECISION,
                "gate2_passed": payload["gate2"]["passed"],
                "blocker": payload["gate2"]["blocker"],
                "artifact": _repo_rel(OUT_JSON),
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
