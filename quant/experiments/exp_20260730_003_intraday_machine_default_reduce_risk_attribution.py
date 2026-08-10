"""exp-20260730-003: machine-default intraday REDUCE_RISK vs no adjustment.

Observed-only settled-forward attribution under the frozen exp-20260714-010 /
exp-20260725-001/002/003 contract.  The treatment population is exactly the
settled active machine_default_action=REDUCE_RISK strict effective next-close
economic cohorts in the hash-bound 20260729 outcome ledger.  The result bars
were frozen in the predeclared 2026-07-24 candidate (amendment child
cand-ea93e2c4d56f8f8b731a) before any outcome field was read at the current
maturity.  Result ceiling: observed_only (admission class
settled_forward_attribution); no strategy, order, sizing, exit, or ledger
behavior changes.
"""
from __future__ import annotations

import hashlib
import io
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260730-003"
LEDGER = (
    "data/daily/intraday/backtests/outcome_ledgers/"
    "intraday_triage_outcomes_20260729.jsonl"
)
EXPECTED_LEDGER_SHA256 = (
    "168155b45eaf492b8ac7e50172a9ef77a99798c04563df1d4978d4fafc52bcda"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ACTIVE_ACTION = "REDUCE_RISK"

# Frozen result bars (2026-07-24 candidate falsifier, parent-verbatim).
MIN_ACTIVE = 20
MIN_PER_HALF = 5
MAX_TICKER_ACTION_COUNT_SHARE = 0.35
MAX_TICKER_POSITIVE_VALUE_SHARE = 0.40


def _read_ledger() -> list[dict]:
    path = REPO_ROOT / LEDGER
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_LEDGER_SHA256:
        raise SystemExit(
            f"ledger hash mismatch: expected {EXPECTED_LEDGER_SHA256}, got {digest}"
        )
    rows = [
        json.loads(line)
        for line in payload.decode("utf-8").splitlines()
        if line.strip()
    ]
    versions = {row.get("outcome_rule_version") for row in rows}
    if versions != {"intraday_triage_counterfactual_outcome_v2"}:
        raise SystemExit(f"unexpected outcome rule versions: {sorted(versions)}")
    return rows


def _select_effective(raw_rows: list[dict]) -> list[dict]:
    """Mirror scripts/build_reopen_readiness.py canonical cohort selection."""
    buckets: dict[tuple, list[tuple[int, dict]]] = {}
    for index, row in enumerate(raw_rows):
        execution_time = str(row.get("execution_time") or "").strip()
        horizon = str(row.get("horizon") or "").strip()
        ticker = str(row.get("ticker") or "").upper().strip()
        if execution_time and ticker:
            key = ("execution", ticker, execution_time, horizon)
        else:
            observation_id = str(row.get("observation_id") or f"row-{index}")
            key = ("observation", observation_id, horizon, str(index))
        buckets.setdefault(key, []).append((index, row))
    selected = []
    for group in buckets.values():
        selected.append(max(
            group,
            key=lambda item: (
                str(item[1].get("decision_timestamp") or ""),
                str(item[1].get("observation_id") or ""),
                item[0],
            ),
        ))
    selected.sort(key=lambda item: item[0])
    return [row for _, row in selected]


def _completed_close(row: dict) -> bool:
    text = str(row.get("horizon_time") or "").strip()
    if not text:
        return False
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return False
    return (stamp.hour, stamp.minute, stamp.second) == (15, 55, 0)


def _chronological(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (
        str(row.get("decision_timestamp") or ""),
        str(row.get("execution_time") or ""),
        str(row.get("ticker") or "").upper(),
        str(row.get("observation_id") or ""),
    ))


def _active_row_value(row: dict) -> dict:
    """Fail closed unless every required active-row field is present."""
    for field in ("decision_timestamp", "execution_time", "ticker"):
        if not str(row.get(field) or "").strip():
            raise SystemExit(f"active row missing {field}: {row.get('observation_id')}")
    decision = datetime.fromisoformat(str(row["decision_timestamp"]))
    execution = datetime.fromisoformat(str(row["execution_time"]))
    if not execution > decision:
        raise SystemExit(
            f"execution not after decision: {row.get('observation_id')}"
        )
    result = row.get("machine_default_result")
    if not isinstance(result, dict) or result.get("action") != ACTIVE_ACTION:
        raise SystemExit(
            f"machine_default_result malformed: {row.get('observation_id')}"
        )
    required = (
        "cost_bps", "gross_return_bps", "net_return_bps",
        "paper_notional_usd", "paper_pnl_usd", "fraction_existing_position",
    )
    for field in required:
        if not isinstance(result.get(field), (int, float)):
            raise SystemExit(
                f"machine_default_result missing {field}: {row.get('observation_id')}"
            )
    notional = float(result["paper_notional_usd"])
    cost_bps = float(result["cost_bps"])
    gross_bps = float(result["gross_return_bps"])
    net_bps = float(result["net_return_bps"])
    value_usd = float(result["paper_pnl_usd"])
    double_cost_value_usd = (gross_bps - 2.0 * cost_bps) / 10000.0 * notional
    return {
        "observation_id": row.get("observation_id"),
        "ticker": str(row.get("ticker")).upper(),
        "decision_timestamp": row.get("decision_timestamp"),
        "execution_time": row.get("execution_time"),
        "cost_bps": cost_bps,
        "gross_return_bps": gross_bps,
        "net_return_bps": net_bps,
        "paper_notional_usd": notional,
        "value_vs_no_adjustment_usd": value_usd,
        "double_cost_value_usd": double_cost_value_usd,
        "final_matches_machine_default": (
            str(row.get("final_action") or "").upper() == ACTIVE_ACTION
        ),
    }


def main() -> None:
    rows = _read_ledger()
    raw = [
        row for row in rows
        if row.get("primary_ticker_day_decision") and row.get("horizon") == "next_close"
    ]
    effective = _select_effective(raw)
    strict = [
        row for row in effective
        if row.get("status") == "closed" and _completed_close(row)
    ]
    ordered = _chronological(strict)
    split = len(ordered) // 2
    first_half_ids = {
        id(row) for row in ordered[:split]
    }

    active_rows = [
        row for row in ordered
        if str(row.get("machine_default_action") or "").upper() == ACTIVE_ACTION
    ]
    active = [_active_row_value(row) for row in active_rows]
    active_first = [
        value for row, value in zip(active_rows, active)
        if id(row) in first_half_ids
    ]
    active_second = [
        value for row, value in zip(active_rows, active)
        if id(row) not in first_half_ids
    ]

    values = [item["value_vs_no_adjustment_usd"] for item in active]
    total_value = sum(values)
    ticker_counts: dict[str, int] = {}
    ticker_values: dict[str, float] = {}
    for item in active:
        ticker_counts[item["ticker"]] = ticker_counts.get(item["ticker"], 0) + 1
        ticker_values[item["ticker"]] = (
            ticker_values.get(item["ticker"], 0.0)
            + item["value_vs_no_adjustment_usd"]
        )
    positive_total = sum(v for v in values if v > 0)
    positive_by_ticker = {
        ticker: sum(
            item["value_vs_no_adjustment_usd"]
            for item in active
            if item["ticker"] == ticker and item["value_vs_no_adjustment_usd"] > 0
        )
        for ticker in ticker_counts
    }
    loto_totals = {
        ticker: total_value - ticker_values[ticker] for ticker in ticker_counts
    }
    double_cost_total = sum(item["double_cost_value_usd"] for item in active)

    bars = {
        "active_count_at_least_20": len(active) >= MIN_ACTIVE,
        "first_half_count_at_least_5": len(active_first) >= MIN_PER_HALF,
        "second_half_count_at_least_5": len(active_second) >= MIN_PER_HALF,
        "costed_active_mean_positive": (
            len(active) > 0 and statistics.mean(values) > 0
        ),
        "costed_active_median_positive": (
            len(active) > 0 and statistics.median(values) > 0
        ),
        "first_half_mean_positive": (
            len(active_first) > 0
            and statistics.mean(
                item["value_vs_no_adjustment_usd"] for item in active_first
            ) > 0
        ),
        "second_half_mean_positive": (
            len(active_second) > 0
            and statistics.mean(
                item["value_vs_no_adjustment_usd"] for item in active_second
            ) > 0
        ),
        "max_ticker_action_count_share_at_most_35pct": (
            len(active) > 0
            and max(ticker_counts.values()) / len(active)
            <= MAX_TICKER_ACTION_COUNT_SHARE
        ),
        "max_ticker_positive_value_share_at_most_40pct": (
            positive_total <= 0
            or max(positive_by_ticker.values()) / positive_total
            <= MAX_TICKER_POSITIVE_VALUE_SHARE
        ),
        "every_leave_one_ticker_out_total_positive": (
            len(loto_totals) > 0 and all(v > 0 for v in loto_totals.values())
        ),
        "double_cost_total_positive": double_cost_total > 0,
    }
    all_pass = all(bars.values())
    decision = (
        "observed_only" if all_pass
        else "observed_only_rejected_machine_default_vs_no_adjustment_not_robust"
    )

    summary = {
        "schema": "intraday_machine_default_reduce_risk_attribution_v2",
        "experiment_id": EXPERIMENT_ID,
        "ledger": LEDGER,
        "ledger_sha256": EXPECTED_LEDGER_SHA256,
        "outcome_rule_version": "intraday_triage_counterfactual_outcome_v2",
        "strict_effective_next_close_settlements": len(strict),
        "active_machine_default_count": len(active),
        "active_first_half_count": len(active_first),
        "active_second_half_count": len(active_second),
        "final_matches_machine_default_all": all(
            item["final_matches_machine_default"] for item in active
        ),
        "total_value_vs_no_adjustment_usd": round(total_value, 4),
        "mean_value_usd": round(statistics.mean(values), 4) if values else None,
        "median_value_usd": round(statistics.median(values), 4) if values else None,
        "first_half_mean_usd": (
            round(statistics.mean(
                item["value_vs_no_adjustment_usd"] for item in active_first
            ), 4) if active_first else None
        ),
        "second_half_mean_usd": (
            round(statistics.mean(
                item["value_vs_no_adjustment_usd"] for item in active_second
            ), 4) if active_second else None
        ),
        "double_cost_total_usd": round(double_cost_total, 4),
        "ticker_action_counts": dict(sorted(
            ticker_counts.items(), key=lambda kv: -kv[1]
        )),
        "ticker_value_usd": {
            ticker: round(value, 4)
            for ticker, value in sorted(
                ticker_values.items(), key=lambda kv: kv[1]
            )
        },
        "positive_value_total_usd": round(positive_total, 4),
        "positive_value_share_by_ticker": {
            ticker: round(value / positive_total, 4)
            for ticker, value in sorted(
                positive_by_ticker.items(), key=lambda kv: -kv[1]
            )
            if positive_total > 0
        },
        "leave_one_ticker_out_totals_usd": {
            ticker: round(value, 4)
            for ticker, value in sorted(loto_totals.items(), key=lambda kv: kv[1])
        },
        "frozen_bars": bars,
        "all_bars_passed": all_pass,
        "decision": decision,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "result_ceiling": "observed_only",
        "active_rows": active,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "machine_default_reduce_risk_attribution.json"
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    compact = {
        key: value for key, value in summary.items() if key != "active_rows"
    }
    print(json.dumps(compact, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
