"""exp-20260827-001: shared-paper-first dollar-neutral news-propagation pair
sleeve BUILD, consuming the exp-20260824-001 single-use qualification through
the d-0003 conversion gate.

Trigger artifact (machine, outcome-blind): the 2026-08-27 pair forward
readiness snapshot reported measurement_ready_batches=1 for the first time
(batch news-first-seen-845025fae409b81adeb3, 29/29 PIT indicative borrow
coverage, no cross-side overlap, concentration within 40%), frozen at
data/alpha_search/news_pair_build_readiness_20260827.json.

Frozen build contract (inherited unchanged from exp-20260824-001 closeout):

- one basket per measurement_ready first-seen batch, admitted exactly once;
- long leg = negative-polarity rows, short leg = positive-polarity rows,
  equal row weight within side, $1,000 paper notional per leg;
- synchronous entry at the first regular-session open strictly after batch
  first_seen_at; fail-closed missing-leg handling (never partial, never
  one-sided); exit at the close of the 10th held session;
- frozen 45bp/leg round-trip costs; iBorrowDesk coverage is indicative only,
  NOT a broker locate, so the sleeve is capped at default-off paper;
- forward acceptance contract pre-registered at build time and frozen:
  >= 20 closed baskets over >= 10 decision dates, net total PnL after costs
  positive, both chronological halves positive, single-ticker absolute gross
  contribution <= 40%.

This runner verifies the build (replay/daily parity, mechanical admission of
the ready batch, idempotency, default-off boundary) and writes the closeout
artifact. It reads no settled basket outcome (none exists; the first entry
open follows the batch freeze).

Repro:
    .\\.venv\\Scripts\\python.exe -B -m quant.experiments.exp_20260827_001_news_propagation_pair_paper_sleeve_build
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT_ID = "exp-20260827-001"
READINESS_ANCHOR = Path("data/alpha_search/news_pair_build_readiness_20260827.json")
READY_BATCH_ID = "news-first-seen-845025fae409b81adeb3"
OUT = Path(
    "data/experiments/exp-20260827-001/"
    "exp_20260827_001_news_propagation_pair_paper_sleeve_build.json"
)


def main() -> int:
    import sys

    sys.path.insert(0, str(Path("quant").resolve()))
    import news_propagation_pair_paper_sleeve as sleeve

    anchor_sha = hashlib.sha256(READINESS_ANCHOR.read_bytes()).hexdigest()
    records = sleeve.load_readiness_records()
    ready = [r for r in records if r.get("status") == "measurement_ready"]

    # Replay path (shared helper, no bars needed for admission parity).
    replay_decisions = sleeve.build_news_propagation_pair_baskets(records)

    # Daily path already ran in production; re-run for idempotency evidence.
    daily_first = sleeve.run()
    daily_second = sleeve.run()
    ledger = sleeve._load_ledger(Path(daily_first["ledger_path"]))
    ledger_decisions = [
        r for r in ledger if r.get("record_type") == "basket_decision"
    ]

    parity = (
        len(replay_decisions) == len(ledger_decisions)
        and all(
            replay == daily
            for replay, daily in zip(replay_decisions, ledger_decisions)
        )
    )
    admitted = next(
        (r for r in ledger_decisions if r["basket_id"] == READY_BATCH_ID), None
    )

    checks = {
        "trigger_batch_measurement_ready": any(
            r.get("first_seen_batch_id") == READY_BATCH_ID for r in ready
        ),
        "ready_batch_admitted_exactly_once": sum(
            1 for r in ledger_decisions if r["basket_id"] == READY_BATCH_ID
        )
        == 1,
        "blocked_batches_never_admitted": all(
            r["basket_id"]
            in {x.get("first_seen_batch_id") for x in ready}
            for r in ledger_decisions
        ),
        "replay_daily_decision_parity": parity,
        "daily_rerun_idempotent": daily_second["appended_this_run"] == 0,
        "dollar_neutral_weights": (
            admitted is not None
            and abs(sum(admitted["long_leg"]["weights"].values()) - 1.0) < 1e-9
            and abs(sum(admitted["short_leg"]["weights"].values()) - 1.0) < 1e-9
        ),
        "default_off_boundary": (
            admitted is not None
            and admitted["trade_enabled"] is False
            and admitted["signals"] == []
            and admitted["order_intents"] == []
            and admitted["orders"] == []
            and daily_second["trade_enabled"] is False
        ),
        "no_settled_outcome_read": daily_second["settled_baskets"] == 0,
    }

    artifact = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trigger_artifact": str(READINESS_ANCHOR),
        "trigger_artifact_sha256": anchor_sha,
        "conversion_gate": "d-0003",
        "consumed_qualification": "exp-20260824-001 single-use pair-build qualification",
        "rule_version": sleeve.RULE_VERSION,
        "frozen_contract": {
            "leg_notional_usd": sleeve.LEG_NOTIONAL_USD,
            "hold_sessions": sleeve.HOLD_SESSIONS,
            "round_trip_cost_rate_per_leg": sleeve.ROUND_TRIP_COST_RATE_PER_LEG,
            "entry_rule": "first_regular_session_open_strictly_after_first_seen_at",
            "fail_closed_missing_leg": True,
            "acceptance_contract": dict(sleeve.ACCEPTANCE_CONTRACT),
        },
        "ready_batch_id": READY_BATCH_ID,
        "admitted_decision_record_id": admitted["record_id"] if admitted else None,
        "admitted_long_tickers": len(admitted["long_leg"]["weights"]) if admitted else 0,
        "admitted_short_tickers": (
            len(admitted["short_leg"]["weights"]) if admitted else 0
        ),
        "settlement_blockers": daily_second["settlement_blockers"],
        "acceptance_progress": daily_second["acceptance_progress"],
        "checks": checks,
        "build_verified": all(checks.values()),
        "iborrowdesk_is_broker_locate": False,
        "pnl_measured": False,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({"build_verified": artifact["build_verified"], **checks}, indent=1))
    return 0 if artifact["build_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
