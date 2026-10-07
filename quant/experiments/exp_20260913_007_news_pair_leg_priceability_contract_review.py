"""exp-20260913-007: outcome-blind identity projection for the news-propagation
pair sleeve leg-priceability contract review.

Reads ONLY identity fields (readiness records, ledger decision ids/dates/
tickers, bar EXISTENCE on given sessions).  Settled outcome objects, if any,
are discarded unread; no PnL, return or spread is read or written.

``--phase before`` runs on the pre-amendment module (admission ignores bars),
``--phase after`` on the amended module (admission receives bars).  Both
phases additionally compute the same hypothetical check in the runner so the
two artifacts are directly comparable.

Usage:
    python -m quant.experiments.exp_20260913_007_news_pair_leg_priceability_contract_review --phase before
    python -m quant.experiments.exp_20260913_007_news_pair_leg_priceability_contract_review --phase after
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))

import news_propagation_pair_paper_sleeve as sleeve  # noqa: E402

EXPERIMENT_ID = "exp-20260913-007"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
LEDGER = sleeve.DEFAULT_DIR / "ledger.jsonl"
LOOKBACK = 5
GRACE = 5


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_bar(bars, ticker: str, session: str) -> bool:
    row = (bars.get(ticker) or {}).get(session) or {}
    return bool(row.get("open")) and bool(row.get("close"))


def _pre_entry_sessions(first_seen_at: str, calendar: list[str]) -> list[str] | None:
    observed = sleeve._aware_datetime(first_seen_at)
    local_date = observed.astimezone(sleeve.NEW_YORK).date().isoformat()
    prior = [s for s in calendar if s <= local_date]
    return prior[-LOOKBACK:] if len(prior) >= LOOKBACK else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    args = parser.parse_args()

    records = [
        r
        for r in sleeve.load_readiness_records()
        if r.get("status") == "measurement_ready"
        and r.get("schema_version") == sleeve.READINESS_SCHEMA_VERSION
    ]
    ledger = sleeve._load_ledger(LEDGER)
    frozen = [r for r in ledger if r.get("record_type") == "basket_decision"]
    tickers = {
        t
        for r in records
        for side in ("long_side", "short_side")
        for t in ((r.get(side) or {}).get("ticker_row_counts") or {})
    } | {
        t
        for d in frozen
        for leg in ("long_leg", "short_leg")
        for t in (d.get(leg) or {}).get("weights") or {}
    }
    bars = sleeve.load_pair_bars(tickers)
    calendar = sorted((bars.get(sleeve.SESSION_ANCHOR_TICKER) or {}).keys())

    # Module admission (before: bars ignored / after: bars applied).
    try:
        module_decisions = sleeve.build_news_propagation_pair_baskets(records, bars=bars)
        admission_receives_bars = True
    except TypeError:
        module_decisions = sleeve.build_news_propagation_pair_baskets(records)
        admission_receives_bars = False
    module_by_id = {d["basket_id"]: d for d in module_decisions}

    baskets = []
    totals = {
        "ready_records": len(records),
        "frozen_ledger_decisions": len(frozen),
        "module_admitted_hypothetical": len(module_decisions),
        "module_admission_receives_bars": admission_receives_bars,
        "module_decisions_with_exclusion_field": 0,
        "hypothetical_baskets_fully_priceable_on_known_sessions": 0,
        "hypothetical_baskets_with_empty_side": 0,
        "frozen_unsettleable_today": 0,
    }
    for record in sorted(records, key=lambda r: str(r.get("first_seen_at"))):
        batch_id = str(record.get("first_seen_batch_id"))
        pre = _pre_entry_sessions(str(record.get("first_seen_at")), calendar)
        sides = {}
        empty_side = False
        for side, leg in (("long_side", "long_leg"), ("short_side", "short_leg")):
            counts = (record.get(side) or {}).get("ticker_row_counts") or {}
            if pre is None:
                keep, drop = [], sorted(counts)
            else:
                keep = sorted(t for t in counts if all(_has_bar(bars, t, s) for s in pre))
                drop = sorted(t for t in counts if t not in keep)
            if not keep:
                empty_side = True
            sides[leg] = {"kept": len(keep), "excluded_unpriceable": drop}
        # Would the kept legs be priceable at entry/exit where those sessions exist?
        sessions = sleeve._entry_exit_sessions(
            str(record.get("first_seen_at")), calendar, sleeve.HOLD_SESSIONS
        )
        known = []
        if pre is not None:
            local_date = pre[-1]
            entry = next((s for s in calendar if s > local_date), None)
            if entry:
                known.append(entry)
            if sessions:
                known.append(sessions[1])
        kept_all = [
            t
            for side, leg in (("long_side", "long_leg"), ("short_side", "short_leg"))
            for t in ((record.get(side) or {}).get("ticker_row_counts") or {})
            if t not in sides[leg]["excluded_unpriceable"]
        ]
        fully = bool(kept_all) and not empty_side and all(
            _has_bar(bars, t, s) for t in kept_all for s in known
        )
        if fully:
            totals["hypothetical_baskets_fully_priceable_on_known_sessions"] += 1
        if empty_side:
            totals["hypothetical_baskets_with_empty_side"] += 1
        module_decision = module_by_id.get(batch_id)
        module_excl = None
        if module_decision is not None:
            module_excl = {
                leg: sorted((module_decision.get(leg) or {}).get("excluded_unpriceable") or [])
                for leg in ("long_leg", "short_leg")
                if "excluded_unpriceable" in (module_decision.get(leg) or {})
            }
            if module_excl:
                totals["module_decisions_with_exclusion_field"] += 1
        # Frozen ledger decision: unsettleable status today (identity only).
        frozen_row = next((d for d in frozen if d["basket_id"] == batch_id), None)
        frozen_status = None
        grace_end = None
        if frozen_row is not None:
            outcome, blocker = sleeve.settle_pair_basket(frozen_row, bars)
            frozen_status = (
                str((outcome or {}).get("outcome_status"))
                if outcome is not None
                else str(blocker).split(":", 1)[0]
            )
            del outcome  # never read beyond its status label
            if frozen_status == "unsettleable":
                totals["frozen_unsettleable_today"] += 1
            if sessions:
                idx = calendar.index(sessions[1])
                grace_end = (
                    calendar[idx + GRACE] if idx + GRACE < len(calendar) else f">{calendar[-1]}"
                )
        baskets.append(
            {
                "basket_id": batch_id,
                "first_seen_at": record.get("first_seen_at"),
                "pre_entry_sessions": pre,
                "known_entry_exit_sessions_checked": known,
                "hypothetical_sides": sides,
                "hypothetical_fully_priceable_on_known_sessions": fully,
                "module_excluded_unpriceable": module_excl,
                "frozen_status_today": frozen_status,
                "frozen_grace_end_session": grace_end,
            }
        )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "phase": args.phase,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "outcome_blind": True,
        "fields_read": "identity only: readiness ticker_row_counts, first_seen_at, ledger decision ids/tickers, bar existence per session; outcome objects discarded unread",
        "rule_under_review": {
            "admission": f"ticker admitted only if a bar exists on every one of the {LOOKBACK} sessions at or before the first_seen New York date (strictly before entry)",
            "terminal": f"window-complete basket with a still-missing leg becomes unsettleable after {GRACE} further anchor sessions",
        },
        "sleeve_module_sha256": _sha256(Path(sleeve.__file__)),
        "ledger_sha256": _sha256(LEDGER),
        "anchor_last_session": calendar[-1] if calendar else None,
        "totals": totals,
        "baskets": baskets,
        "trade_enabled": False,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"news_pair_leg_priceability_{args.phase}.json"
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"phase": args.phase, "totals": totals}, indent=2))
    for b in baskets:
        print(
            b["basket_id"][:34],
            "pre",
            b["pre_entry_sessions"][-1] if b["pre_entry_sessions"] else None,
            {k: (v["kept"], len(v["excluded_unpriceable"])) for k, v in b["hypothetical_sides"].items()},
            "fully_priceable",
            b["hypothetical_fully_priceable_on_known_sessions"],
            "frozen",
            b["frozen_status_today"],
            "grace_end",
            b["frozen_grace_end_session"],
        )
    print("wrote", out)


if __name__ == "__main__":
    main()
