"""Audit overlapping-entry cohort loss concentration.

Observed-only loss attribution for exp-20260504-016. This script reads the
current accepted three-window trade artifact and measures whether bad trades
cluster when entries occur into already-crowded portfolio days. It does not
change entries, exits, sizing, ranking, or production behavior.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

EXP_ID = "exp-20260504-016"
SOURCE_TRADES = DATA_DIR / "experiments" / "current_accepted_trades_20260502_alpha_search.json"
OUT_JSON = (
    DATA_DIR
    / "experiments"
    / EXP_ID
    / "exp_20260504_016_overlapping_entry_cohort_loss_concentration.json"
)

WINDOW_ORDER = ("late_strong", "mid_weak", "old_thin")
FAMILY_BUCKET = "overlap_pressure_3_plus"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _date(value: Any) -> str:
    return str(value or "")[:10]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _flatten_trades(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in WINDOW_ORDER:
        window_payload = payload.get(window, {})
        for trade in window_payload.get("trades") or []:
            if isinstance(trade, dict):
                rows.append({**trade, "window": window})
    return sorted(rows, key=lambda row: (row.get("window") or "", _date(row.get("entry_date")), row.get("ticker") or ""))


def _same_day_entries(window_trades: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    return [trade for trade in window_trades if _date(trade.get("entry_date")) == entry_date]


def _active_before_entry(window_trades: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for trade in window_trades:
        trade_entry = _date(trade.get("entry_date"))
        trade_exit = _date(trade.get("exit_date"))
        if trade_entry and trade_exit and trade_entry < entry_date <= trade_exit:
            active.append(trade)
    return active


def _bucket_for(overlap_pressure_count: int) -> str:
    if overlap_pressure_count >= 3:
        return FAMILY_BUCKET
    return f"overlap_pressure_{overlap_pressure_count}"


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    pnl = sum(_float(row.get("pnl")) for row in rows)
    winners = [row for row in rows if _float(row.get("pnl")) > 0]
    losers = [row for row in rows if _float(row.get("pnl")) < 0]
    loss_dollars = sum(_float(row.get("pnl")) for row in losers)
    winner_pnl = sum(_float(row.get("pnl")) for row in winners)
    return {
        "trade_count": count,
        "winner_count": len(winners),
        "loser_count": len(losers),
        "win_rate": round(len(winners) / count, 4) if count else None,
        "net_pnl": round(pnl, 2),
        "loss_dollars": round(loss_dollars, 2),
        "winner_collateral_pnl": round(winner_pnl, 2),
        "avg_pnl": round(pnl / count, 2) if count else None,
        "avg_loser_pnl": round(loss_dollars / len(losers), 2) if losers else None,
        "avg_winner_pnl": round(winner_pnl / len(winners), 2) if winners else None,
    }


def build_audit() -> dict[str, Any]:
    source = _load_json(SOURCE_TRADES)
    trades = _flatten_trades(source)
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_window[trade["window"]].append(trade)

    annotated: list[dict[str, Any]] = []
    for window in WINDOW_ORDER:
        window_trades = by_window[window]
        for trade in window_trades:
            entry_date = _date(trade.get("entry_date"))
            same_day = _same_day_entries(window_trades, entry_date)
            active_before = _active_before_entry(window_trades, entry_date)
            overlap_pressure_count = len(active_before) + len(same_day)
            bucket = _bucket_for(overlap_pressure_count)
            annotated.append(
                {
                    "window": window,
                    "ticker": trade.get("ticker"),
                    "strategy": trade.get("strategy"),
                    "sector": trade.get("sector"),
                    "entry_date": entry_date,
                    "exit_date": _date(trade.get("exit_date")),
                    "pnl": round(_float(trade.get("pnl")), 2),
                    "pnl_pct_net": round(_float(trade.get("pnl_pct_net")), 6),
                    "exit_reason": trade.get("exit_reason"),
                    "active_positions_before_entry": len(active_before),
                    "same_day_entry_count": len(same_day),
                    "overlap_pressure_count": overlap_pressure_count,
                    "overlap_bucket": bucket,
                    "active_before_tickers": sorted(str(row.get("ticker")) for row in active_before),
                    "same_day_tickers": sorted(str(row.get("ticker")) for row in same_day),
                    "is_family_member": bucket == FAMILY_BUCKET,
                    "is_loser": _float(trade.get("pnl")) < 0,
                }
            )

    overall = _summarize(annotated)
    family_rows = [row for row in annotated if row["is_family_member"]]
    non_family_rows = [row for row in annotated if not row["is_family_member"]]
    family_summary = _summarize(family_rows)
    non_family_summary = _summarize(non_family_rows)

    bucket_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    window_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in annotated:
        bucket_rows[row["overlap_bucket"]].append(row)
        window_rows[row["window"]].append(row)

    bucket_summary = {bucket: _summarize(rows) for bucket, rows in sorted(bucket_rows.items())}
    window_summary: dict[str, Any] = {}
    for window, rows in sorted(window_rows.items()):
        window_family = [row for row in rows if row["is_family_member"]]
        window_summary[window] = {
            "all": _summarize(rows),
            "family": _summarize(window_family),
            "family_loss_share_of_window_losses": _loss_share(window_family, rows),
        }

    family_losers = [row for row in family_rows if row["is_loser"]]
    family_winners = [row for row in family_rows if not row["is_loser"]]
    loss_share = _loss_share(family_rows, annotated)
    winner_collateral_ratio = (
        abs(family_summary["winner_collateral_pnl"] / family_summary["loss_dollars"])
        if family_summary["loss_dollars"]
        else None
    )

    candidate = _candidate_from(family_summary, loss_share, winner_collateral_ratio)

    return {
        "experiment_id": EXP_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "overlapping entry cohort loss concentration",
        "source_trades": str(SOURCE_TRADES.relative_to(REPO_ROOT)).replace("\\", "/"),
        "production_change_made": False,
        "strategy_logic_changed": False,
        "definition": {
            "overlap_pressure_count": "active positions already open before the entry date plus same-day accepted entries in the same canonical window",
            "family_bucket": FAMILY_BUCKET,
            "family_rule": "overlap_pressure_count >= 3",
            "reason_not_a_filter": "This is an observed-only taxonomy; no entry, exit, sizing, or ranking rule is changed.",
        },
        "history_guardrails": {
            "not_generic_hold_quality": True,
            "not_wide_stop": True,
            "not_low_mfe": True,
            "not_overnight_gap": True,
            "not_near_target_giveback": True,
            "not_sector_breakdown": True,
            "not_entry_extension": True,
            "not_risk_amplified_stopout": True,
        },
        "overall": overall,
        "family_summary": family_summary,
        "non_family_summary": non_family_summary,
        "bucket_summary": bucket_summary,
        "window_summary": window_summary,
        "family_loss_share_of_all_losses": loss_share,
        "winner_collateral_to_family_loss_abs_ratio": (
            round(winner_collateral_ratio, 4) if winner_collateral_ratio is not None else None
        ),
        "family_losers": sorted(family_losers, key=lambda row: row["pnl"])[:20],
        "family_winners_collateral": sorted(family_winners, key=lambda row: row["pnl"], reverse=True)[:20],
        "entry_date_pressure_counts": _entry_date_pressure_counts(annotated),
        "future_alpha_or_fix_candidate": candidate,
        "decision": "observed_only",
    }


def _loss_share(subset: list[dict[str, Any]], universe: list[dict[str, Any]]) -> float | None:
    subset_losses = sum(_float(row.get("pnl")) for row in subset if _float(row.get("pnl")) < 0)
    total_losses = sum(_float(row.get("pnl")) for row in universe if _float(row.get("pnl")) < 0)
    if not total_losses:
        return None
    return round(abs(subset_losses / total_losses), 4)


def _entry_date_pressure_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["window"], row["entry_date"])].append(row)
    out = []
    for (window, entry_date), group in grouped.items():
        out.append(
            {
                "window": window,
                "entry_date": entry_date,
                "trade_count": len(group),
                "max_overlap_pressure_count": max(row["overlap_pressure_count"] for row in group),
                "net_pnl": round(sum(_float(row.get("pnl")) for row in group), 2),
                "tickers": sorted(str(row.get("ticker")) for row in group),
            }
        )
    return sorted(out, key=lambda row: (row["window"], row["entry_date"]))


def _candidate_from(
    family_summary: dict[str, Any],
    loss_share: float | None,
    winner_collateral_ratio: float | None,
) -> dict[str, Any]:
    if not family_summary["trade_count"]:
        return {
            "candidate": "No overlapping-entry loss family was found.",
            "priority": "none",
            "rationale": "The audited pressure bucket has zero trades.",
        }
    if (
        loss_share is not None
        and loss_share >= 0.35
        and winner_collateral_ratio is not None
        and winner_collateral_ratio <= 0.75
    ):
        return {
            "candidate": "Test a default-off scarce-slot ranking audit that penalizes new entries only when overlap pressure is high and same-day alternatives exist.",
            "priority": "candidate_for_future_alpha_discovery",
            "rationale": "Family losses are material and winner collateral appears bounded, but this audit alone cannot justify a filter.",
            "required_next_evidence": [
                "same-day skipped-candidate replacement value",
                "multi-window before/after replay",
                "proof that winners in the same pressure bucket are not truncated",
            ],
        }
    return {
        "candidate": "Do not add an overlap-pressure rule from this audit alone.",
        "priority": "low",
        "rationale": "Either loss concentration is not high enough or winner collateral risk is too large.",
        "required_next_evidence": [
            "new discriminator such as event/news context or same-day candidate quality",
            "capacity-aware replacement value rather than a broad pressure filter",
        ],
    }


def main() -> None:
    payload = build_audit()
    _write_json(OUT_JSON, payload)
    print(json.dumps({
        "experiment_id": EXP_ID,
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "family_summary": payload["family_summary"],
        "family_loss_share_of_all_losses": payload["family_loss_share_of_all_losses"],
        "winner_collateral_to_family_loss_abs_ratio": payload["winner_collateral_to_family_loss_abs_ratio"],
        "decision": payload["decision"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
