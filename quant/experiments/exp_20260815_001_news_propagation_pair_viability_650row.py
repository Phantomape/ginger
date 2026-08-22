"""exp-20260815-001: contract-mandated 650-row attribution re-read of the
news_propagation_negative_side lane (pair-sleeve viability decision).

Frozen contract (predeclared outcome-blind in the ticket and in
data/alpha_search/news_propagation_forward_readiness_20260815.json):

- Cohort: closed rows of data/non_ohlcv/news_event_exposure_observations/rows.jsonl
  with event_date >= 2026-07-01 (strictly out-of-replay) and event_polarity in
  {negative, positive}. Frozen at 655 negative / 812 positive rows.
- Settlement: the observer-materialized excess_10d (exposure-ticker
  next-open-to-10-session-close return minus SPY same-window return). Nothing
  is recomputed here.
- Viability bars (BOTH must pass for the pair sleeve to qualify for its own
  shared-paper-first build; frozen at the 2026-08-08 re-park):
  V1 event-level separation (mean of per-event mean excess_10d, negative
     minus positive) > 100bp.
  V2 row-level pooled mean separation > 45bp.
- Confirmation bars (exp-20260807-001 contract, re-verified for direction
  stability; a fail here kills the separation claim itself):
  F1 floors: negative closed rows >= 200, events >= 20, event dates >= 10,
     positive control rows >= 200.
  F2 event-level: negative > positive.
  F3 row-level: pooled mean AND median negative > positive.
  F4 halves: event-level separation > 0 in both chronological halves.
  F5 concentration: no single negative event > 40% of the negative side's
     summed positive per-event excess; no single ticker > 40% of the negative
     side's row-level positive excess mass.
- Result ceiling observed_only either way; a viability pass promotes nothing
  by itself. Any V-bar fail re-parks the lane at >= 983 closed negative rows
  (builder synced AFTER close in the same ticket).

Repro:
    .\\.venv\\Scripts\\python.exe -B -m quant.experiments.exp_20260815_001_news_propagation_pair_viability_650row
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT_ID = "exp-20260815-001"
LEDGER = Path("data/non_ohlcv/news_event_exposure_observations/rows.jsonl")
READINESS = Path("data/alpha_search/news_propagation_forward_readiness_20260815.json")
OUT = Path(
    "data/experiments/exp-20260815-001/"
    "exp_20260815_001_news_propagation_pair_viability_650row.json"
)
FORWARD_START = "2026-07-01"
CONCENTRATION_CAP = 0.40
V1_EVENT_LEVEL_BP = 100.0
V2_ROW_MEAN_BP = 45.0


def _load_cohort() -> tuple[dict, list[dict]]:
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    ledger_bytes = LEDGER.read_bytes()
    ledger_sha = hashlib.sha256(ledger_bytes).hexdigest()
    if ledger_sha != readiness["ledger_sha256"]:
        raise SystemExit(
            "ledger_sha256 mismatch versus the frozen outcome-blind snapshot; "
            "re-freeze before reading outcomes"
        )
    rows = []
    for line in ledger_bytes.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if str(r.get("event_date", "")) < FORWARD_START:
            continue
        if r.get("outcome_status") != "closed":
            continue
        if r.get("event_polarity") not in ("negative", "positive"):
            continue
        if r.get("excess_10d") is None:
            continue
        rows.append(r)
    return readiness, rows


def _event_means(rows: list[dict]) -> dict[str, dict]:
    by_event: dict[str, dict] = {}
    grouped: dict[str, list[float]] = defaultdict(list)
    dates: dict[str, str] = {}
    for r in rows:
        grouped[r["event_id"]].append(float(r["excess_10d"]))
        dates[r["event_id"]] = str(r["event_date"])
    for event_id, values in grouped.items():
        by_event[event_id] = {
            "event_date": dates[event_id],
            "leg_count": len(values),
            "mean_excess_10d": statistics.fmean(values),
        }
    return by_event


def _median_lower(sorted_values: list[str]) -> str:
    return sorted_values[(len(sorted_values) - 1) // 2]


def _side_stats(rows: list[dict]) -> dict:
    events = _event_means(rows)
    row_values = [float(r["excess_10d"]) for r in rows]
    event_values = [e["mean_excess_10d"] for e in events.values()]
    unique_dates = sorted({e["event_date"] for e in events.values()})
    median_date = _median_lower(unique_dates)
    half1 = [e["mean_excess_10d"] for e in events.values() if e["event_date"] <= median_date]
    half2 = [e["mean_excess_10d"] for e in events.values() if e["event_date"] > median_date]
    return {
        "rows": len(rows),
        "events": len(events),
        "event_dates": len(unique_dates),
        "median_event_date": median_date,
        "row_mean": statistics.fmean(row_values),
        "row_median": statistics.median(row_values),
        "event_mean": statistics.fmean(event_values),
        "event_median": statistics.median(event_values),
        "half1_event_mean": statistics.fmean(half1) if half1 else None,
        "half2_event_mean": statistics.fmean(half2) if half2 else None,
        "half1_events": len(half1),
        "half2_events": len(half2),
        "_events": events,
    }


def main() -> None:
    readiness, rows = _load_cohort()
    neg_rows = [r for r in rows if r["event_polarity"] == "negative"]
    pos_rows = [r for r in rows if r["event_polarity"] == "positive"]
    neg = _side_stats(neg_rows)
    pos = _side_stats(pos_rows)

    frozen = readiness["cohort"]
    if neg["rows"] != frozen["negative"]["closed_rows"] or pos["rows"] != frozen["positive"]["closed_rows"]:
        raise SystemExit("cohort count drift versus the frozen snapshot")

    # F5a: single-event share of the negative side's summed positive per-event excess.
    positive_event_means = [
        (eid, e["mean_excess_10d"])
        for eid, e in neg["_events"].items()
        if e["mean_excess_10d"] > 0
    ]
    pos_mass_events = sum(v for _, v in positive_event_means)
    max_event_share = (
        max(v for _, v in positive_event_means) / pos_mass_events
        if pos_mass_events > 0
        else None
    )
    max_event_id = (
        max(positive_event_means, key=lambda item: item[1])[0]
        if positive_event_means
        else None
    )

    # F5b: single-ticker share of the negative side's row-level positive excess mass.
    ticker_pos_mass: dict[str, float] = defaultdict(float)
    for r in neg_rows:
        v = float(r["excess_10d"])
        if v > 0:
            ticker_pos_mass[r["exposure_ticker"]] += v
    total_ticker_mass = sum(ticker_pos_mass.values())
    max_ticker, max_ticker_mass = (
        max(ticker_pos_mass.items(), key=lambda item: item[1])
        if ticker_pos_mass
        else (None, 0.0)
    )
    max_ticker_share = (
        max_ticker_mass / total_ticker_mass if total_ticker_mass > 0 else None
    )

    event_level_bp = (neg["event_mean"] - pos["event_mean"]) * 1e4
    row_mean_bp = (neg["row_mean"] - pos["row_mean"]) * 1e4

    confirmation = {
        "F1_floors": (
            neg["rows"] >= 200
            and neg["events"] >= 20
            and neg["event_dates"] >= 10
            and pos["rows"] >= 200
        ),
        "F2_event_level_negative_gt_positive": neg["event_mean"] > pos["event_mean"],
        "F3_row_level_mean_and_median_negative_gt_positive": (
            neg["row_mean"] > pos["row_mean"] and neg["row_median"] > pos["row_median"]
        ),
        "F4_separation_positive_both_halves": (
            neg["half1_event_mean"] is not None
            and pos["half1_event_mean"] is not None
            and neg["half2_event_mean"] is not None
            and pos["half2_event_mean"] is not None
            and (neg["half1_event_mean"] - pos["half1_event_mean"]) > 0
            and (neg["half2_event_mean"] - pos["half2_event_mean"]) > 0
        ),
        "F5_concentration_caps": (
            max_event_share is not None
            and max_event_share <= CONCENTRATION_CAP
            and max_ticker_share is not None
            and max_ticker_share <= CONCENTRATION_CAP
        ),
    }
    viability = {
        "V1_event_level_separation_gt_100bp": event_level_bp > V1_EVENT_LEVEL_BP,
        "V2_row_level_mean_separation_gt_45bp": row_mean_bp > V2_ROW_MEAN_BP,
    }
    confirmation_pass = all(confirmation.values())
    viability_pass = all(viability.values())
    failed = sorted(
        [k for k, v in confirmation.items() if not v]
        + [k for k, v in viability.items() if not v]
    )

    if viability_pass and confirmation_pass:
        decision = "observed_only_pair_sleeve_viability_qualified"
    elif confirmation_pass:
        decision = "rejected_pair_viability_below_cost_bar_separation_still_confirmed"
    else:
        decision = "rejected_forward_polarity_separation_direction_unstable"

    def _side_public(side: dict) -> dict:
        return {k: v for k, v in side.items() if not k.startswith("_")}

    artifact = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ledger_sha256": readiness["ledger_sha256"],
        "readiness_snapshot": str(READINESS),
        "forward_predicate": readiness["forward_predicate"],
        "concentration_cap": CONCENTRATION_CAP,
        "viability_bars": {
            "event_level_bp_required_gt": V1_EVENT_LEVEL_BP,
            "row_level_mean_bp_required_gt": V2_ROW_MEAN_BP,
            "source": "2026-08-08 re-park contract (two-leg round trip ~90bp + buffer)",
        },
        "negative": _side_public(neg),
        "positive": _side_public(pos),
        "separation": {
            "event_level_bp": event_level_bp,
            "row_level_mean_bp": row_mean_bp,
            "row_level_median_bp": (neg["row_median"] - pos["row_median"]) * 1e4,
            "half1_event_level_bp": (
                (neg["half1_event_mean"] - pos["half1_event_mean"]) * 1e4
                if neg["half1_event_mean"] is not None
                and pos["half1_event_mean"] is not None
                else None
            ),
            "half2_event_level_bp": (
                (neg["half2_event_mean"] - pos["half2_event_mean"]) * 1e4
                if neg["half2_event_mean"] is not None
                and pos["half2_event_mean"] is not None
                else None
            ),
        },
        "concentration": {
            "max_single_negative_event_positive_excess_share": max_event_share,
            "max_single_negative_event_id": max_event_id,
            "max_single_ticker_positive_excess_share": max_ticker_share,
            "max_single_ticker": max_ticker,
        },
        "confirmation_checks": confirmation,
        "viability_checks": viability,
        "failed_checks": failed,
        "decision": decision,
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "notes": (
            "Descriptive only; excess_10d is the observer-materialized SPY-excess. "
            "The tilt shape was not re-read: it stays dead outcome-blind at 1/0/0 "
            "executed-entry touches versus the >=5-per-window bar (structurally "
            "uncovered windows; observer starts 2026-01). A viability fail re-parks "
            "the lane at >= 983 closed negative-side rows."
        ),
        "descriptive": {
            "negative_row_mean_bp_vs_zero": neg["row_mean"] * 1e4,
            "negative_row_median_bp_vs_zero": neg["row_median"] * 1e4,
            "positive_row_mean_bp_vs_zero": pos["row_mean"] * 1e4,
            "positive_row_median_bp_vs_zero": pos["row_median"] * 1e4,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: artifact[k] for k in (
        "decision", "failed_checks", "separation", "concentration", "descriptive"
    )}, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
