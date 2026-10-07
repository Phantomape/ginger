"""Dollar-neutral news-propagation pair paper sleeve (default-off).

Experiment: exp-20260827-001 (consumes the exp-20260824-001 single-use
pair-build qualification through the d-0003 conversion gate).

Every ``measurement_ready`` first-seen batch produced by
``news_propagation_pair_forward_observer`` is mechanically admitted exactly
once as ONE dollar-neutral paper basket:

- long leg: the batch's negative-polarity exposure tickers, equal row weight;
- short leg: the batch's positive-polarity exposure tickers, equal row weight;
- $1,000 paper notional per leg, synchronous entry at the first regular
  session open strictly after the batch ``first_seen_at``;
- exit at the close of the 10th held session (entry session inclusive);
- frozen 45bp per-leg round-trip cost (90bp per basket);
- fail-closed missing-leg handling: a basket settles only when BOTH legs are
  fully priceable for every ticker; it never partially settles and never
  enters one-sided.

Blocked batches are never admitted. iBorrowDesk coverage checked at admission
time by the readiness observer is indicative research evidence, NOT a broker
locate, so this sleeve is capped at default-off paper: ``trade_enabled`` stays
false and no signal, OrderIntent, or order is ever created.

The sleeve is judged ONLY by its own pre-registered forward acceptance
contract (``ACCEPTANCE_CONTRACT``); no interim read may relax those bars.

Ledger (append-only, dedup by record_id):
  data/paper_sleeves/news_propagation_pair/ledger.jsonl
  data/paper_sleeves/news_propagation_pair/state.json
  data/paper_sleeves/news_propagation_pair/latest_summary.json
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, time
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

try:
    from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text
except ModuleNotFoundError:  # package-style test/import
    from quant.data_paths import DATA_ROOT, atomic_write_json, atomic_write_text

RULE_VERSION = "news_propagation_pair_dollar_neutral_v1"
READINESS_SCHEMA_VERSION = "news_propagation_pair_forward_readiness_v1"
LONG_POLARITY = "negative"
SHORT_POLARITY = "positive"
LEG_NOTIONAL_USD = 1_000.0
HOLD_SESSIONS = 10
ROUND_TRIP_COST_RATE_PER_LEG = 0.0045
SESSION_ANCHOR_TICKER = "SPY"
COMPARATOR_TICKERS = ("SPY", "QQQ")
NEW_YORK = ZoneInfo("America/New_York")

# Frozen at build time (exp-20260827-001).  The sleeve is accepted or rejected
# ONLY against these bars once the sample exists; they must not be retuned.
ACCEPTANCE_CONTRACT = {
    "min_closed_baskets": 20,
    "min_decision_dates": 10,
    "net_total_pnl_after_costs_positive": True,
    "both_chronological_halves_positive": True,
    "max_single_ticker_abs_gross_contribution": 0.40,
}

DEFAULT_DIR = DATA_ROOT / "paper_sleeves" / "news_propagation_pair"
DEFAULT_READINESS_DIR = (
    DATA_ROOT / "non_ohlcv" / "news_propagation_pair_forward_readiness"
)
MASSIVE_DB = DATA_ROOT / "warehouse" / "massive_history.sqlite"


def _aware_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _production_impact() -> dict[str, Any]:
    return {
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "signals": [],
        "order_intents": [],
        "orders": [],
    }


# ---------------------------------------------------------------------------
# Admission (shared by replay and daily; outcome-blind by construction)
# ---------------------------------------------------------------------------


def _side_weights(side: Mapping[str, Any]) -> dict[str, float]:
    counts = dict(side.get("ticker_row_counts") or {})
    total = sum(counts.values())
    if total <= 0:
        return {}
    return {ticker: counts[ticker] / total for ticker in sorted(counts)}


def build_pair_basket_decision(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """One immutable basket decision from one measurement_ready record.

    Uses ONLY admission-time fields; settled outcomes never appear in the
    readiness schema, so admission cannot condition on results.
    """
    if record.get("schema_version") != READINESS_SCHEMA_VERSION:
        return None
    if record.get("status") != "measurement_ready":
        return None
    batch_id = str(record.get("first_seen_batch_id") or "")
    first_seen = _aware_datetime(record.get("first_seen_at"))
    if not batch_id or first_seen is None:
        return None
    long_weights = _side_weights(record.get("long_side") or {})
    short_weights = _side_weights(record.get("short_side") or {})
    if not long_weights or not short_weights:
        return None
    borrow = record.get("borrow_coverage") or {}
    decision = {
        "record_type": "basket_decision",
        "record_id": f"decision:{batch_id}",
        "schema_version": RULE_VERSION,
        "rule_version": RULE_VERSION,
        "basket_id": batch_id,
        "readiness_record_id": record.get("record_id"),
        "first_seen_at": str(record.get("first_seen_at")),
        "decision_date": first_seen.astimezone(NEW_YORK).date().isoformat(),
        "entry_rule": "first_regular_session_open_strictly_after_first_seen_at",
        "exit_rule": f"close_of_session_{HOLD_SESSIONS}_including_entry_session",
        "hold_sessions": HOLD_SESSIONS,
        "leg_notional_usd": LEG_NOTIONAL_USD,
        "round_trip_cost_rate_per_leg": ROUND_TRIP_COST_RATE_PER_LEG,
        "long_leg": {
            "polarity": LONG_POLARITY,
            "weights": long_weights,
        },
        "short_leg": {
            "polarity": SHORT_POLARITY,
            "weights": short_weights,
        },
        "borrow_evidence": {
            "required_tickers": borrow.get("required_tickers"),
            "covered_tickers": borrow.get("covered_tickers"),
            "is_broker_locate": False,
            "source": "iborrowdesk_indicative_not_broker_locate",
        },
        "outcome_status": "pending",
        **_production_impact(),
    }
    return decision


def build_news_propagation_pair_baskets(
    readiness_records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Deterministic basket decisions for every measurement_ready record."""
    decisions = []
    seen: set[str] = set()
    for record in readiness_records:
        decision = build_pair_basket_decision(record)
        if decision is None or decision["basket_id"] in seen:
            continue
        seen.add(decision["basket_id"])
        decisions.append(decision)
    return sorted(decisions, key=lambda row: (row["first_seen_at"], row["basket_id"]))


# ---------------------------------------------------------------------------
# Pricing (warehouse first, massive_history split-normalized fallback)
# ---------------------------------------------------------------------------


def load_pair_bars(
    tickers: Iterable[str],
    *,
    massive_db: Path | str | None = None,
) -> dict[str, dict[str, dict[str, float]]]:
    """{ticker: {date_iso: {open, close}}} from warehouse cold+hot, then
    massive_history for tickers absent from the warehouse.  Massive bars are
    raw; split normalization for them happens at settlement via the returned
    ``__splits__`` entry ({ticker: [(execution_date, factor), ...]}).
    """
    wanted = sorted(
        {str(t).upper() for t in tickers if t} | set(COMPARATOR_TICKERS)
    )
    bars: dict[str, Any] = {}
    try:
        from news_event_exposure_observer import load_frames
    except ModuleNotFoundError:  # package-style import
        from quant.news_event_exposure_observer import load_frames
    frames = load_frames(set(wanted))
    for ticker, frame in frames.items():
        rows = {}
        for index, row in frame.iterrows():
            rows[str(index.date())] = {
                "open": float(row["Open"]),
                "close": float(row["Close"]),
            }
        if rows:
            bars[ticker] = rows
    missing = [t for t in wanted if t not in bars]
    splits: dict[str, list[tuple[str, float]]] = {}
    db_path = Path(massive_db) if massive_db else MASSIVE_DB
    if missing and db_path.exists():
        with sqlite3.connect(str(db_path)) as conn:
            for ticker in missing:
                rows = {
                    str(r[0]): {"open": float(r[1]), "close": float(r[2])}
                    for r in conn.execute(
                        "SELECT trade_date, open, close FROM daily_bars "
                        "WHERE ticker=? AND open IS NOT NULL AND close IS NOT NULL",
                        (ticker,),
                    )
                    if r[1] and r[2]
                }
                if rows:
                    bars[ticker] = rows
                    split_rows = []
                    for execution_date, split_from, split_to in conn.execute(
                        "SELECT execution_date, split_from, split_to "
                        "FROM stock_splits WHERE ticker=?",
                        (ticker,),
                    ):
                        try:
                            split_rows.append(
                                (str(execution_date), float(split_to) / float(split_from))
                            )
                        except (TypeError, ValueError, ZeroDivisionError):
                            continue
                    if split_rows:
                        splits[ticker] = split_rows
    bars["__splits__"] = splits
    return bars


def _entry_exit_sessions(
    first_seen_at: str, calendar: list[str], hold_sessions: int
) -> tuple[str, str] | None:
    observed = _aware_datetime(first_seen_at)
    if observed is None:
        return None
    observed_local = observed.astimezone(NEW_YORK)
    entry_index = None
    for index, session in enumerate(calendar):
        session_open = datetime.combine(
            datetime.strptime(session, "%Y-%m-%d").date(), time(9, 30), tzinfo=NEW_YORK
        )
        if session_open > observed_local:
            entry_index = index
            break
    if entry_index is None:
        return None
    exit_index = entry_index + hold_sessions - 1
    if exit_index >= len(calendar):
        return None
    return calendar[entry_index], calendar[exit_index]


def _split_factor(
    splits: Mapping[str, list[tuple[str, float]]],
    ticker: str,
    entry_session: str,
    exit_session: str,
) -> float:
    factor = 1.0
    for execution_date, ratio in splits.get(ticker, []):
        if entry_session < execution_date <= exit_session:
            factor *= ratio
    return factor


def _leg_return(
    bars: Mapping[str, Any], ticker: str, entry_session: str, exit_session: str
) -> float | None:
    rows = bars.get(ticker) or {}
    entry_bar = rows.get(entry_session)
    exit_bar = rows.get(exit_session)
    if not entry_bar or not exit_bar:
        return None
    entry_open = float(entry_bar.get("open") or 0.0)
    exit_close = float(exit_bar.get("close") or 0.0)
    if entry_open <= 0 or exit_close <= 0:
        return None
    factor = _split_factor(bars.get("__splits__") or {}, ticker, entry_session, exit_session)
    return (exit_close * factor) / entry_open - 1.0


# ---------------------------------------------------------------------------
# Settlement (fail-closed: both legs fully priced or nothing)
# ---------------------------------------------------------------------------


def settle_pair_basket(
    decision: Mapping[str, Any], bars: Mapping[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """(outcome_row, None) once fully priceable, else (None, blocker)."""
    calendar = sorted((bars.get(SESSION_ANCHOR_TICKER) or {}).keys())
    if not calendar:
        return None, "missing_session_anchor_bars"
    sessions = _entry_exit_sessions(
        str(decision.get("first_seen_at")), calendar, int(decision["hold_sessions"])
    )
    if sessions is None:
        return None, "holding_window_not_complete"
    entry_session, exit_session = sessions
    leg_results: dict[str, Any] = {}
    for leg_name, sign in (("long_leg", 1.0), ("short_leg", -1.0)):
        weights = (decision.get(leg_name) or {}).get("weights") or {}
        missing = []
        weighted_return = 0.0
        contributions = {}
        for ticker, weight in weights.items():
            leg_ret = _leg_return(bars, ticker, entry_session, exit_session)
            if leg_ret is None:
                missing.append(ticker)
                continue
            weighted_return += weight * leg_ret
            contributions[ticker] = round(
                sign * weight * leg_ret * float(decision["leg_notional_usd"]), 6
            )
        if missing:
            # Fail-closed missing-leg contract: never settle partially.
            return None, "missing_leg_bars:" + ",".join(sorted(missing))
        leg_results[leg_name] = {
            "weighted_return": weighted_return,
            "gross_pnl_usd": sign * weighted_return * float(decision["leg_notional_usd"]),
            "ticker_gross_contributions_usd": contributions,
        }
    notional = float(decision["leg_notional_usd"])
    cost_usd = 2.0 * float(decision["round_trip_cost_rate_per_leg"]) * notional
    gross_pnl = (
        leg_results["long_leg"]["gross_pnl_usd"]
        + leg_results["short_leg"]["gross_pnl_usd"]
    )
    net_pnl = gross_pnl - cost_usd
    comparators = {}
    for comparator in COMPARATOR_TICKERS:
        comp_return = _leg_return(bars, comparator, entry_session, exit_session)
        comparators[comparator] = (
            None
            if comp_return is None
            else round(2.0 * notional * comp_return, 6)
        )
    outcome = {
        "record_type": "basket_outcome",
        "record_id": f"outcome:{decision['basket_id']}:{decision['hold_sessions']}",
        "schema_version": RULE_VERSION,
        "rule_version": RULE_VERSION,
        "basket_id": decision["basket_id"],
        "decision_date": decision.get("decision_date"),
        "entry_session": entry_session,
        "exit_session": exit_session,
        "long_leg_return": round(leg_results["long_leg"]["weighted_return"], 6),
        "short_leg_return": round(leg_results["short_leg"]["weighted_return"], 6),
        "gross_pnl_usd": round(gross_pnl, 6),
        "cost_usd": round(cost_usd, 6),
        "net_pnl_usd": round(net_pnl, 6),
        "ticker_gross_contributions_usd": {
            **leg_results["long_leg"]["ticker_gross_contributions_usd"],
            **leg_results["short_leg"]["ticker_gross_contributions_usd"],
        },
        "replacement_value_vs_cash_usd": round(net_pnl, 6),
        "comparator_same_gross_capital_usd": comparators,
        "outcome_status": "settled",
        **_production_impact(),
    }
    return outcome, None


# ---------------------------------------------------------------------------
# Acceptance-contract progress (reporting only; never gates behavior)
# ---------------------------------------------------------------------------


def acceptance_progress(outcomes: list[Mapping[str, Any]]) -> dict[str, Any]:
    settled = sorted(
        (row for row in outcomes if row.get("outcome_status") == "settled"),
        key=lambda row: (str(row.get("decision_date")), str(row.get("basket_id"))),
    )
    decision_dates = sorted({str(row.get("decision_date")) for row in settled})
    total_net = sum(float(row.get("net_pnl_usd") or 0.0) for row in settled)
    half = len(settled) // 2
    first_half = sum(float(r.get("net_pnl_usd") or 0.0) for r in settled[:half])
    second_half = sum(float(r.get("net_pnl_usd") or 0.0) for r in settled[half:])
    contributions: dict[str, float] = {}
    for row in settled:
        for ticker, value in (row.get("ticker_gross_contributions_usd") or {}).items():
            contributions[ticker] = contributions.get(ticker, 0.0) + abs(float(value))
    total_abs = sum(contributions.values())
    max_share = (
        max(contributions.values()) / total_abs if total_abs > 0 else None
    )
    return {
        "contract": dict(ACCEPTANCE_CONTRACT),
        "closed_baskets": len(settled),
        "decision_dates": len(decision_dates),
        "net_total_pnl_usd": round(total_net, 6),
        "first_half_net_pnl_usd": round(first_half, 6),
        "second_half_net_pnl_usd": round(second_half, 6),
        "max_single_ticker_abs_gross_share": (
            round(max_share, 6) if max_share is not None else None
        ),
        "sample_sufficient": (
            len(settled) >= ACCEPTANCE_CONTRACT["min_closed_baskets"]
            and len(decision_dates) >= ACCEPTANCE_CONTRACT["min_decision_dates"]
        ),
    }


# ---------------------------------------------------------------------------
# Shared replay + daily persistence
# ---------------------------------------------------------------------------


def load_readiness_records(readiness_dir: Path | str | None = None) -> list[dict[str, Any]]:
    base = Path(readiness_dir) if readiness_dir else DEFAULT_READINESS_DIR
    path = base / "readiness_decisions.jsonl"
    records = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_news_propagation_pair_historical_trades(
    readiness_records: Iterable[Mapping[str, Any]],
    bars: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay path: same admission + settlement code as the daily path."""
    decisions = build_news_propagation_pair_baskets(readiness_records)
    outcomes = []
    blockers = {}
    for decision in decisions:
        outcome, blocker = settle_pair_basket(decision, bars)
        if outcome is not None:
            outcomes.append(outcome)
        else:
            blockers[decision["basket_id"]] = blocker
    return {
        "rule_version": RULE_VERSION,
        "decisions": decisions,
        "outcomes": outcomes,
        "settlement_blockers": blockers,
        "acceptance_progress": acceptance_progress(outcomes),
        **_production_impact(),
    }


def run(
    *,
    out_dir: Path | str | None = None,
    readiness_dir: Path | str | None = None,
    readiness_records: Iterable[Mapping[str, Any]] | None = None,
    bars: Mapping[str, Any] | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Daily default-off path: admit new measurement_ready batches exactly
    once, settle pending baskets fail-closed, append-only persist."""
    base = Path(out_dir) if out_dir else DEFAULT_DIR
    base.mkdir(parents=True, exist_ok=True)
    ledger_path = base / "ledger.jsonl"
    state_path = base / "state.json"

    records = (
        list(readiness_records)
        if readiness_records is not None
        else load_readiness_records(readiness_dir)
    )
    ledger = _load_ledger(ledger_path)
    existing_record_ids = {str(row.get("record_id")) for row in ledger}
    state = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    seen_baskets = set(state.get("seen_baskets") or []) | {
        str(row.get("basket_id"))
        for row in ledger
        if row.get("record_type") == "basket_decision"
    }

    appended: list[dict[str, Any]] = []
    for decision in build_news_propagation_pair_baskets(records):
        if (
            decision["basket_id"] in seen_baskets
            or decision["record_id"] in existing_record_ids
        ):
            continue
        seen_baskets.add(decision["basket_id"])
        existing_record_ids.add(decision["record_id"])
        ledger.append(decision)
        appended.append(decision)

    decisions = [r for r in ledger if r.get("record_type") == "basket_decision"]
    outcomes = [r for r in ledger if r.get("record_type") == "basket_outcome"]
    settled_ids = {str(r.get("basket_id")) for r in outcomes}
    pending = [d for d in decisions if d["basket_id"] not in settled_ids]

    settlement_blockers: dict[str, str] = {}
    if pending:
        if bars is None:
            tickers = {
                ticker
                for decision in pending
                for leg in ("long_leg", "short_leg")
                for ticker in (decision.get(leg) or {}).get("weights") or {}
            }
            bars = load_pair_bars(tickers)
        for decision in pending:
            outcome, blocker = settle_pair_basket(decision, bars)
            if outcome is None:
                settlement_blockers[decision["basket_id"]] = blocker or "unknown"
                continue
            if outcome["record_id"] in existing_record_ids:
                continue
            existing_record_ids.add(outcome["record_id"])
            ledger.append(outcome)
            outcomes.append(outcome)
            appended.append(outcome)

    if appended:
        body = "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) for row in ledger
        )
        atomic_write_text(body + "\n", ledger_path)

    summary = {
        "schema_version": RULE_VERSION,
        "rule_version": RULE_VERSION,
        "as_of": now_utc or datetime.now(tz=NEW_YORK).astimezone().isoformat(),
        "decisions": len(decisions),
        "settled_baskets": len(outcomes),
        "pending_baskets": len(decisions) - len(outcomes),
        "appended_this_run": len(appended),
        "settlement_blockers": settlement_blockers,
        "acceptance_progress": acceptance_progress(outcomes),
        "iborrowdesk_is_broker_locate": False,
        **_production_impact(),
    }
    atomic_write_json(
        {
            "schema_version": RULE_VERSION,
            "updated_at": summary["as_of"],
            "seen_baskets": sorted(seen_baskets),
            "trade_enabled": False,
        },
        state_path,
    )
    atomic_write_json(summary, base / "latest_summary.json")
    summary["ledger_path"] = str(ledger_path)
    return summary
