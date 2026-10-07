"""exp-20260913-006: outcome-blind identity projection of the pending
news-propagation pair baskets' settlement blockers, before and after the
load_pair_bars stale-warehouse-frame fallthrough repair.

Reads ONLY identity/status fields: basket ids, decision dates, entry/exit
sessions, blocker kinds and the missing-ticker classification.  If a basket
becomes fully priceable the outcome object is discarded unread; only the
boolean ``settleable`` is recorded.  No PnL, return or spread is read or
written.

Usage:
    python -m quant.experiments.exp_20260913_006_news_pair_bar_source_fallback_repair --phase before
    python -m quant.experiments.exp_20260913_006_news_pair_bar_source_fallback_repair --phase after
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))

import news_propagation_pair_paper_sleeve as sleeve  # noqa: E402
from news_event_exposure_observer import load_frames  # noqa: E402

EXPERIMENT_ID = "exp-20260913-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
LEDGER = sleeve.DEFAULT_DIR / "ledger.jsonl"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _classify_missing(
    tickers: list[str],
    exit_session: str,
    warehouse_last: dict[str, str],
    massive: sqlite3.Connection,
) -> dict[str, list[str]]:
    out = {
        "massive_covers_exit_session": [],
        "present_somewhere_but_not_at_exit_session": [],
        "absent_from_every_source": [],
    }
    for ticker in tickers:
        row = massive.execute(
            "SELECT COUNT(*), MAX(trade_date) FROM daily_bars WHERE ticker=?",
            (ticker,),
        ).fetchone()
        massive_count, massive_last = int(row[0] or 0), row[1]
        has_exit = bool(
            massive.execute(
                "SELECT 1 FROM daily_bars WHERE ticker=? AND trade_date=? "
                "AND open IS NOT NULL AND close IS NOT NULL",
                (ticker, exit_session),
            ).fetchone()
        )
        if has_exit:
            out["massive_covers_exit_session"].append(ticker)
        elif massive_count or ticker in warehouse_last:
            out["present_somewhere_but_not_at_exit_session"].append(ticker)
        else:
            out["absent_from_every_source"].append(ticker)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    args = parser.parse_args()

    ledger = sleeve._load_ledger(LEDGER)
    decisions = [r for r in ledger if r.get("record_type") == "basket_decision"]
    settled_ids = {
        str(r.get("basket_id")) for r in ledger if r.get("record_type") == "basket_outcome"
    }
    pending = [d for d in decisions if d["basket_id"] not in settled_ids]
    tickers = {
        t
        for d in pending
        for leg in ("long_leg", "short_leg")
        for t in (d.get(leg) or {}).get("weights") or {}
    }
    bars = sleeve.load_pair_bars(tickers)
    calendar = sorted((bars.get(sleeve.SESSION_ANCHOR_TICKER) or {}).keys())
    frames = load_frames(set(tickers) | set(sleeve.COMPARATOR_TICKERS))
    warehouse_last = {
        t: str(f.index.max().date()) for t, f in frames.items() if len(f)
    }

    baskets = []
    totals = {
        "pending_baskets": len(pending),
        "settleable_baskets": 0,
        "missing_leg_bars_baskets": 0,
        "holding_window_not_complete_baskets": 0,
        "missing_tickers_total": 0,
        "massive_covers_exit_session": 0,
        "present_somewhere_but_not_at_exit_session": 0,
        "absent_from_every_source": 0,
        "baskets_with_any_absent_from_every_source": 0,
    }
    with sqlite3.connect(f"file:{sleeve.MASSIVE_DB}?mode=ro", uri=True) as massive:
        for decision in pending:
            outcome, blocker = sleeve.settle_pair_basket(decision, bars)
            sessions = sleeve._entry_exit_sessions(
                str(decision.get("first_seen_at")), calendar, int(decision["hold_sessions"])
            )
            row = {
                "basket_id": decision["basket_id"],
                "decision_date": decision.get("decision_date"),
                "entry_session": sessions[0] if sessions else None,
                "exit_session": sessions[1] if sessions else None,
                "leg_ticker_count": sum(
                    len((decision.get(leg) or {}).get("weights") or {})
                    for leg in ("long_leg", "short_leg")
                ),
                "settleable": outcome is not None,
                "blocker_kind": None if outcome is not None else str(blocker).split(":", 1)[0],
            }
            del outcome  # never read
            if row["settleable"]:
                totals["settleable_baskets"] += 1
            elif row["blocker_kind"] == "missing_leg_bars":
                totals["missing_leg_bars_baskets"] += 1
                missing = sorted(str(blocker).split(":", 1)[1].split(","))
                classes = _classify_missing(missing, row["exit_session"], warehouse_last, massive)
                row["missing_ticker_count"] = len(missing)
                row["missing_ticker_classes"] = classes
                totals["missing_tickers_total"] += len(missing)
                for key, values in classes.items():
                    totals[key] += len(values)
                if classes["absent_from_every_source"]:
                    totals["baskets_with_any_absent_from_every_source"] += 1
            elif row["blocker_kind"] == "holding_window_not_complete":
                totals["holding_window_not_complete_baskets"] += 1
            baskets.append(row)

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "phase": args.phase,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "outcome_blind": True,
        "fields_read": "identity/status only: basket_id, decision_date, first_seen_at, hold_sessions, leg tickers, blocker string, bar existence; settled outcome objects discarded unread",
        "sleeve_module_sha256": _sha256(Path(sleeve.__file__)),
        "ledger_sha256": _sha256(LEDGER),
        "warehouse_anchor_last_session": calendar[-1] if calendar else None,
        "totals": totals,
        "baskets": baskets,
        "trade_enabled": False,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"news_pair_bar_source_fallback_{args.phase}.json"
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"phase": args.phase, "totals": totals}, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
