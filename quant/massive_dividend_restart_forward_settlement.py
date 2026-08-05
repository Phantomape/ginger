"""Massive dividend-restart forward settlement contract (exp-20260803-002).

Observer first-build ID 2 of 2 (AGENTS.md section 2.4 observer first-build
budget): the settlement layer for the exp-20260802-003 forward observer. It
turns eligible ``restart_after_observed_gap`` candidate rows into settled
forward H10 decisions so the exp-20260801-004 reopen contract (>= 30 settled
restart decisions) accrues machine-checkably.

Frozen policy (ports exp-20260801-004 replay semantics; do not retune here):
- entry: first regular session whose 09:30 America/New_York open is strictly
  after ``first_seen_at``, resolved against the SPY session calendar inside
  the massive warehouse (data calendar, never the process wall clock);
- selection: within one declaration date, eligible restart rows that pass the
  policy-level PIT membership gate (active common stock in the massive
  instrument master) are ordered by (median 20-bar pre-declaration dollar
  volume descending, ticker ascending) and at most the top 2 become
  decisions; selection only activates once every same-declaration-date
  candidate has a final gate evaluation, and candidates discovered after
  their declaration date has resolved are excluded append-only forever;
- comparator: outcome-blind core-or-cash bound at decision resolution. The
  first ordinal may consume the first not-yet-consumed, non-same-ticker live
  core-bucket fill whose entry date equals the decision entry session (from
  the position-control ledger); every other case is zero-return cash. A core
  slot is consumed at most once globally. The binding uses entry-session
  facts only and is persisted before any exit bar is read;
- settlement: split-normalized entry-session open to close of the 9th
  following session (a 10-session hold counting the entry session, matching
  the frozen replay map delta), $4,000 notional, 0.35% round-trip cost,
  0.70% double-cost stress, SPY and QQQ same-interval secondary legs on the
  identical massive warehouse reader. Missing entry or exit bars void the
  decision with a reason; voided rows never count as settled.

Event sourcing: this module never mutates the observer ledger. It appends to
its own ``settlement_ledger.jsonl`` — ``date_resolution`` (one per resolved
declaration date, freezing the selected decision set), ``decision`` (one per
selected row, carrying the comparator binding), ``settlement`` (one per
decision once bars cover the exit session, settled or voided), and
``late_discovery_excluded`` rows. Reruns are idempotent: state is derived
from the two ledgers, so a rerun with no new inputs emits nothing.

Every emitted row is observer-only with ``trade_enabled`` false. Nothing
here alters orders, ranking, sizing or exits.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

try:
    from data_paths import atomic_write_json
except ImportError:  # pragma: no cover - package-style imports for tooling
    from quant.data_paths import atomic_write_json

try:
    from us_market_calendar import (
        is_us_equity_session,
        latest_completed_us_equity_session,
    )
except ImportError:  # pragma: no cover - package-style imports for tooling
    from quant.us_market_calendar import (
        is_us_equity_session,
        latest_completed_us_equity_session,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OBSERVER_DIR = (
    REPO_ROOT / "data" / "non_ohlcv" / "massive_dividend_restart_forward"
)
DEFAULT_BARS_DATABASE = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
DEFAULT_POSITION_CONTROL_LEDGER = (
    REPO_ROOT / "data" / "live_pilot" / "position_control" / "ledger.jsonl"
)

SCHEMA_VERSION = 1
SOURCE_EXPERIMENT = "exp-20260803-002"
SESSION_TICKER = "SPY"
SECONDARY_TICKERS = ("SPY", "QQQ")
ENTRY_OPEN_LOCAL = dt.time(9, 30)
ENTRY_TZ = ZoneInfo("America/New_York")
HOLD_SESSIONS_AFTER_ENTRY = 9  # exit close = 10th held session incl. entry
TOP_PER_DECLARATION_DATE = 2
NOTIONAL = 4000.0
COST = 0.0035
DOUBLE_COST = 0.0070
TARGET_GAP_VARIANT = "restart_after_observed_gap"
REOPEN_REQUIRED_SETTLED_DECISIONS = 30
COMPARATOR_RULE = (
    "first_ordinal_may_consume_one_same_entry_session_live_core_bucket_slot_"
    "once_globally_same_ticker_collision_and_all_other_cases_zero_return_cash"
)
MEMBERSHIP_RULE = "active_common_stock_in_massive_instrument_master"

# exp-20260805-004: bars lagging the latest completed US-equity session by at
# least this many sessions is a fail-closed input-staleness condition. One
# session of lag is normal intraday (today's bars land after the close); two
# means the daily catch-up has actually missed a completed session.
STALE_BARS_ALERT_MIN_SESSIONS = 2


def count_stale_sessions(
    bars_max_trade_date: Any, latest_completed_session: dt.date
) -> int | None:
    """US-equity sessions in (bars_max_trade_date, latest_completed_session].

    Data-calendar arithmetic only; holidays and weekends never count, so the
    staleness alert cannot flap across quiet calendar days. Returns None when
    ``bars_max_trade_date`` is missing or unparseable (caller fails closed).
    """

    text = str(bars_max_trade_date or "").strip()[:10]
    try:
        cursor = dt.date.fromisoformat(text)
    except ValueError:
        return None
    stale = 0
    while cursor < latest_completed_session:
        cursor += dt.timedelta(days=1)
        if is_us_equity_session(cursor):
            stale += 1
    return stale


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


class SettlementContractError(Exception):
    """Raised on a settlement input-contract violation (fail closed)."""


def _parse_first_seen(value: Any) -> dt.datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise SettlementContractError(
            f"forward candidate first_seen_at is not ISO-8601: {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise SettlementContractError(
            f"forward candidate first_seen_at lacks a timezone: {value!r}"
        )
    return parsed


def entry_anchor_date(first_seen_at: Any) -> str:
    """Earliest calendar date whose regular 09:30 ET open is after first_seen.

    Pure data arithmetic on the candidate's own frozen vintage: no process
    clock is consulted. The anchor is then snapped forward to the first real
    session in the warehouse session calendar.
    """

    local = _parse_first_seen(first_seen_at).astimezone(ENTRY_TZ)
    anchor = local.date()
    if local.time() >= ENTRY_OPEN_LOCAL:
        anchor = anchor + dt.timedelta(days=1)
    return anchor.isoformat()


def _load_jsonl(path: Path, *, label: str) -> tuple[list[dict[str, Any]], bool]:
    """Load a JSONL ledger; tolerate only a torn FINAL line (crash recovery)."""

    if not path.is_file():
        return [], False
    rows: list[dict[str, Any]] = []
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    torn_final_line = False
    last_index = len(raw_lines) - 1
    for index, line in enumerate(raw_lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            if index == last_index:
                torn_final_line = True
                continue
            raise SettlementContractError(
                f"{label} ledger line {index + 1} is corrupt mid-file"
            ) from exc
    return rows, torn_final_line


def _append_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _observer_views(
    observer_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    """First occurrence wins per decision_key (observer emits each key once)."""

    candidates: dict[str, Mapping[str, Any]] = {}
    evaluations: dict[str, Mapping[str, Any]] = {}
    for row in observer_rows:
        record_type = row.get("record_type")
        key = str(row.get("decision_key") or "")
        if not key:
            continue
        if record_type == "forward_candidate" and key not in candidates:
            candidates[key] = row
        elif record_type == "gate_evaluation" and key not in evaluations:
            evaluations[key] = row
    return candidates, evaluations


def _settlement_views(
    settlement_rows: list[Mapping[str, Any]],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    """Dedup by (record_type, key); first occurrence wins (idempotent reads)."""

    views: dict[str, dict[str, Mapping[str, Any]]] = {
        "date_resolution": {},
        "decision": {},
        "settlement": {},
        "late_discovery_excluded": {},
    }
    for row in settlement_rows:
        record_type = str(row.get("record_type") or "")
        if record_type == "date_resolution":
            key = str(row.get("declaration_date") or "")
        else:
            key = str(row.get("decision_key") or "")
        if not key or record_type not in views:
            continue
        views[record_type].setdefault(key, row)
    return views


def _session_calendar(conn: sqlite3.Connection) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT trade_date FROM daily_bars WHERE ticker=? ORDER BY 1",
            (SESSION_TICKER,),
        )
    ]


def _bar(conn: sqlite3.Connection, ticker: str, date: str):
    return conn.execute(
        "SELECT open, close FROM daily_bars WHERE ticker=? AND trade_date=?",
        (ticker, date),
    ).fetchone()


def _split_factor(
    conn: sqlite3.Connection, ticker: str, entry_session: str, exit_session: str
) -> float:
    factor = 1.0
    for execution_date, split_from, split_to in conn.execute(
        "SELECT execution_date, split_from, split_to FROM stock_splits "
        "WHERE ticker=?",
        (ticker,),
    ):
        if entry_session < execution_date <= exit_session:
            try:
                factor *= float(split_to) / float(split_from)
            except (TypeError, ValueError, ZeroDivisionError) as exc:
                raise SettlementContractError(
                    f"corrupt split row for {ticker} on {execution_date}"
                ) from exc
    return factor


def _leg_return(
    conn: sqlite3.Connection, ticker: str, entry_session: str, exit_session: str
) -> float | None:
    """Split-normalized gross return, entry open to exit close (replay parity)."""

    entry_bar = _bar(conn, ticker, entry_session)
    exit_bar = _bar(conn, ticker, exit_session)
    if (
        entry_bar is None
        or entry_bar[0] in (None, 0)
        or exit_bar is None
        or exit_bar[1] in (None, 0)
    ):
        return None
    factor = _split_factor(conn, ticker, entry_session, exit_session)
    return (float(exit_bar[1]) * factor) / float(entry_bar[0]) - 1.0


def _membership_active_common_stock(conn: sqlite3.Connection, ticker: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM instrument_master "
        "WHERE ticker=? AND instrument_type='CS' AND active=1 LIMIT 1",
        (ticker,),
    ).fetchone()
    return row is not None


def _core_slots_by_session(
    position_control_ledger: Path,
) -> dict[str, list[str]]:
    """Distinct live core-bucket fills keyed by entry date (comparator surface).

    Missing or unreadable surface degrades to cash comparators (recorded on
    the decision rows) rather than blocking settlement.
    """

    if not position_control_ledger.is_file():
        return {}
    slots: dict[str, set[str]] = {}
    try:
        with position_control_ledger.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("strategy_bucket") != "core":
                    continue
                ticker = str(row.get("ticker") or "").strip().upper()
                entry_date = str(row.get("entry_date") or "").strip()[:10]
                if ticker and len(entry_date) == 10:
                    slots.setdefault(entry_date, set()).add(ticker)
    except OSError:
        return {}
    return {date: sorted(tickers) for date, tickers in slots.items()}


def persist_massive_dividend_restart_forward_settlement(
    today: Any = None,
    *,
    observer_dir: Path | str = DEFAULT_OBSERVER_DIR,
    bars_database: Path | str = DEFAULT_BARS_DATABASE,
    position_control_ledger: Path | str = DEFAULT_POSITION_CONTROL_LEDGER,
    now_fn: Callable[[], dt.datetime] = _utc_now,
) -> dict[str, Any]:
    """Run one settlement cycle: resolve dates, bind decisions, settle H10.

    ``today`` is a caller-provided run label recorded on the summary; it never
    enters session resolution, selection, comparator binding or settlement.
    The function never raises: failures persist a non-ok fail-closed status.
    """

    observer_root = Path(observer_dir)
    observer_ledger_path = observer_root / "ledger.jsonl"
    settlement_ledger_path = observer_root / "settlement_ledger.jsonl"
    summary_path = observer_root / "latest_settlement_summary.json"
    run_started_at = _iso(now_fn())

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "default_off_massive_dividend_restart_forward_settlement",
        "source_experiment": SOURCE_EXPERIMENT,
        "run_label": None if today is None else str(today),
        "run_started_at": run_started_at,
        "target_gap_variant": TARGET_GAP_VARIANT,
        "hold_sessions_after_entry": HOLD_SESSIONS_AFTER_ENTRY,
        "top_per_declaration_date": TOP_PER_DECLARATION_DATE,
        "comparator_rule": COMPARATOR_RULE,
        "membership_rule": MEMBERSHIP_RULE,
        "notional": NOTIONAL,
        "cost_pct": COST,
        "double_cost_pct": DOUBLE_COST,
        "reopen_required_settled_decisions": REOPEN_REQUIRED_SETTLED_DECISIONS,
        "observer_only": True,
        "trade_enabled": False,
    }

    def _fail(status: str, reason: str, error: str | None = None) -> dict[str, Any]:
        summary.update(
            {"status": status, "reason": reason, "alert": True, "error": error}
        )
        atomic_write_json(summary, summary_path)
        return summary

    database = Path(bars_database)
    if not database.is_file():
        return _fail("blocked_missing_bars_database", "bars_database_not_found")

    try:
        observer_rows, observer_torn = _load_jsonl(
            observer_ledger_path, label="observer"
        )
        settlement_rows, settlement_torn = _load_jsonl(
            settlement_ledger_path, label="settlement"
        )
    except SettlementContractError as exc:
        return _fail("error", "corrupt_ledger", str(exc))
    if observer_torn:
        # The observer ledger is another producer's output: a torn final line
        # there means that producer crashed mid-append. Fail closed instead of
        # silently consuming a half-written surface.
        return _fail("error", "observer_ledger_torn_final_line")

    candidates_by_key, evaluations_by_key = _observer_views(observer_rows)
    views = _settlement_views(settlement_rows)
    resolved_dates = views["date_resolution"]
    decisions_by_key = dict(views["decision"])
    settlements_by_key = views["settlement"]
    late_excluded = views["late_discovery_excluded"]

    consumed_core_slots: set[str] = {
        str(row.get("core_slot_id"))
        for row in decisions_by_key.values()
        if row.get("core_slot_id")
    }

    new_events: list[dict[str, Any]] = []
    recorded_at = _iso(now_fn())

    try:
        with sqlite3.connect(
            f"file:{database.as_posix()}?mode=ro", uri=True
        ) as conn:
            calendar = _session_calendar(conn)
            calendar_index = {date: i for i, date in enumerate(calendar)}
            warehouse_max = calendar[-1] if calendar else None
            max_row = conn.execute(
                "SELECT MAX(trade_date) FROM daily_bars"
            ).fetchone()
            bars_max = max_row[0] if max_row else None
            core_slots = _core_slots_by_session(Path(position_control_ledger))

            # ── Phase 1: late-discovery exclusions ────────────────────────
            for key, candidate in sorted(candidates_by_key.items()):
                declaration_date = str(candidate["declaration_date"])
                if (
                    declaration_date in resolved_dates
                    and key
                    not in set(
                        resolved_dates[declaration_date].get(
                            "considered_decision_keys"
                        )
                        or []
                    )
                    and key not in late_excluded
                ):
                    event = {
                        "schema_version": SCHEMA_VERSION,
                        "record_type": "late_discovery_excluded",
                        "decision_key": key,
                        "declaration_date": declaration_date,
                        "reason": "candidate_discovered_after_date_resolution",
                        "recorded_at": recorded_at,
                        "observer_only": True,
                        "trade_enabled": False,
                    }
                    new_events.append(event)
                    late_excluded[key] = event

            # ── Phase 2: resolve declaration dates (ascending) ────────────
            by_date: dict[str, list[Mapping[str, Any]]] = {}
            for key, candidate in candidates_by_key.items():
                if key in late_excluded:
                    continue
                by_date.setdefault(str(candidate["declaration_date"]), []).append(
                    candidate
                )
            for declaration_date in sorted(by_date):
                if declaration_date in resolved_dates:
                    continue
                members = by_date[declaration_date]
                if any(
                    str(row["decision_key"]) not in evaluations_by_key
                    for row in members
                ):
                    continue  # gates not final for every same-date candidate
                pool = []
                membership_failures = []
                for row in members:
                    if row.get("gap_variant") != TARGET_GAP_VARIANT:
                        continue
                    evaluation = evaluations_by_key[str(row["decision_key"])]
                    if evaluation.get("eligible") is not True:
                        continue
                    if not _membership_active_common_stock(
                        conn, str(row["ticker"])
                    ):
                        membership_failures.append(str(row["decision_key"]))
                        continue
                    pool.append((row, evaluation))
                entries: list[tuple[Mapping[str, Any], Mapping[str, Any], str]] = []
                resolvable = True
                for row, evaluation in pool:
                    anchor = entry_anchor_date(row["first_seen_at"])
                    if warehouse_max is None or warehouse_max < anchor:
                        resolvable = False
                        break
                    entry_session = next(
                        (date for date in calendar if date >= anchor), None
                    )
                    if entry_session is None:
                        resolvable = False
                        break
                    entries.append((row, evaluation, entry_session))
                if not resolvable:
                    continue  # calendar has not reached this date's entries yet
                entries.sort(
                    key=lambda item: (
                        -float(item[1].get("median_dollar_volume_20") or 0.0),
                        str(item[0]["ticker"]),
                    )
                )
                selected = entries[:TOP_PER_DECLARATION_DATE]
                selected_keys = []
                for ordinal, (row, evaluation, entry_session) in enumerate(
                    selected, start=1
                ):
                    key = str(row["decision_key"])
                    selected_keys.append(key)
                    comparator = "cash"
                    core_slot_id = None
                    comparator_reason = "additional_slot_cash"
                    if ordinal == 1:
                        comparator_reason = "no_core_slot_same_entry_session"
                        for core_ticker in core_slots.get(entry_session, []):
                            slot_id = f"{core_ticker}:{entry_session}"
                            if slot_id in consumed_core_slots:
                                continue
                            if core_ticker == str(row["ticker"]):
                                comparator_reason = "same_ticker_collision_cash"
                                continue
                            comparator = "core_slot"
                            core_slot_id = slot_id
                            comparator_reason = "matched_first_available_core_slot"
                            consumed_core_slots.add(slot_id)
                            break
                    decision = {
                        "schema_version": SCHEMA_VERSION,
                        "record_type": "decision",
                        "decision_key": key,
                        "ticker": str(row["ticker"]),
                        "declaration_date": declaration_date,
                        "gap_variant": row.get("gap_variant"),
                        "first_seen_at": row.get("first_seen_at"),
                        "entry_anchor_date": entry_anchor_date(
                            row["first_seen_at"]
                        ),
                        "entry_session": entry_session,
                        "entry_rule": row.get("entry_rule"),
                        "liquidity_rank_on_declaration_date": ordinal,
                        "ordinal_within_declaration_date": ordinal,
                        "median_dollar_volume_20": evaluation.get(
                            "median_dollar_volume_20"
                        ),
                        "comparator": comparator,
                        "core_slot_id": core_slot_id,
                        "comparator_reason": comparator_reason,
                        "comparator_rule": COMPARATOR_RULE,
                        "core_slots_available_that_session": len(
                            core_slots.get(entry_session, [])
                        ),
                        "membership_rule": MEMBERSHIP_RULE,
                        "recorded_at": recorded_at,
                        "observer_only": True,
                        "trade_enabled": False,
                    }
                    new_events.append(decision)
                    decisions_by_key[key] = decision
                resolution = {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "date_resolution",
                    "declaration_date": declaration_date,
                    "considered_decision_keys": sorted(
                        str(row["decision_key"]) for row in members
                    ),
                    "selected_decision_keys": selected_keys,
                    "membership_gate_failed_keys": sorted(membership_failures),
                    "eligible_pool_size": len(pool),
                    "warehouse_max_trade_date": warehouse_max,
                    "recorded_at": recorded_at,
                    "observer_only": True,
                    "trade_enabled": False,
                }
                new_events.append(resolution)
                resolved_dates[declaration_date] = resolution

            # ── Phase 3: settle decisions whose exit session has bars ─────
            for key in sorted(decisions_by_key):
                if key in settlements_by_key:
                    continue
                decision = decisions_by_key[key]
                entry_session = str(decision["entry_session"])
                entry_index = calendar_index.get(entry_session)
                if entry_index is None:
                    continue  # calendar rebuilt shorter than before: stay pending
                exit_index = entry_index + HOLD_SESSIONS_AFTER_ENTRY
                if exit_index >= len(calendar):
                    continue  # exit session not yet in the data calendar
                exit_session = calendar[exit_index]
                ticker = str(decision["ticker"])
                gross = _leg_return(conn, ticker, entry_session, exit_session)
                settlement: dict[str, Any] = {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "settlement",
                    "decision_key": key,
                    "ticker": ticker,
                    "declaration_date": decision["declaration_date"],
                    "gap_variant": decision.get("gap_variant"),
                    "entry_session": entry_session,
                    "h10_exit_session": exit_session,
                    "comparator": decision.get("comparator"),
                    "core_slot_id": decision.get("core_slot_id"),
                    "notional": NOTIONAL,
                    "cost_pct": COST,
                    "double_cost_pct": DOUBLE_COST,
                    "warehouse_max_trade_date": warehouse_max,
                    "recorded_at": recorded_at,
                    "observer_only": True,
                    "trade_enabled": False,
                }
                if gross is None:
                    settlement.update(
                        {"settled": False, "void_reason": "missing_entry_or_exit_bar"}
                    )
                else:
                    treatment_value = NOTIONAL * (gross - COST)
                    if decision.get("comparator") == "core_slot":
                        core_ticker = str(decision["core_slot_id"]).split(":")[0]
                        core_ret = _leg_return(
                            conn, core_ticker, entry_session, exit_session
                        )
                        baseline_value = (
                            NOTIONAL * (core_ret - COST)
                            if core_ret is not None
                            else 0.0
                        )
                        baseline_double = (
                            NOTIONAL * (core_ret - DOUBLE_COST)
                            if core_ret is not None
                            else 0.0
                        )
                    else:
                        core_ret = None
                        baseline_value = 0.0
                        baseline_double = 0.0
                    spy = _leg_return(conn, "SPY", entry_session, exit_session)
                    qqq = _leg_return(conn, "QQQ", entry_session, exit_session)
                    settlement.update(
                        {
                            "settled": True,
                            "gross_return": round(gross, 6),
                            "treatment_value": round(treatment_value, 2),
                            "core_comparator_return": None
                            if core_ret is None
                            else round(core_ret, 6),
                            "baseline_value": round(baseline_value, 2),
                            "replacement_value": round(
                                treatment_value - baseline_value, 2
                            ),
                            "replacement_value_double_cost": round(
                                NOTIONAL * (gross - DOUBLE_COST) - baseline_double,
                                2,
                            ),
                            "spy_value": None
                            if spy is None
                            else round(NOTIONAL * (spy - COST), 2),
                            "qqq_value": None
                            if qqq is None
                            else round(NOTIONAL * (qqq - COST), 2),
                        }
                    )
                new_events.append(settlement)
                settlements_by_key[key] = settlement
    except (sqlite3.Error, SettlementContractError) as exc:
        return _fail("error", "settlement_cycle_failed", str(exc))

    _append_jsonl(settlement_ledger_path, new_events)

    settled_restart = [
        row
        for row in settlements_by_key.values()
        if row.get("settled") is True
        and row.get("gap_variant") == TARGET_GAP_VARIANT
    ]
    voided = [
        row for row in settlements_by_key.values() if row.get("settled") is False
    ]
    latest_completed = latest_completed_us_equity_session(now_fn())
    stale_sessions = count_stale_sessions(bars_max, latest_completed)
    bars_stale = (
        stale_sessions is None or stale_sessions >= STALE_BARS_ALERT_MIN_SESSIONS
    )
    summary.update(
        {
            "status": "stale_bars_input" if bars_stale else "ok",
            "alert": bars_stale,
            "reason": (
                "bars_max_trade_date "
                f"{bars_max} lags latest completed session "
                f"{latest_completed.isoformat()} by "
                f"{'unknown' if stale_sessions is None else stale_sessions} "
                "sessions"
                if bars_stale
                else None
            ),
            "latest_completed_session": latest_completed.isoformat(),
            "bars_stale_sessions": stale_sessions,
            "stale_bars_alert_min_sessions": STALE_BARS_ALERT_MIN_SESSIONS,
            "recovered_torn_settlement_final_line": settlement_torn,
            "warehouse_max_trade_date": warehouse_max,
            "bars_max_trade_date": bars_max,
            "calendar_session_count": len(calendar),
            "candidate_count_total": len(candidates_by_key),
            "resolved_declaration_date_count": len(resolved_dates),
            "pending_declaration_date_count": len(
                {
                    str(row["declaration_date"])
                    for key, row in candidates_by_key.items()
                    if key not in late_excluded
                }
                - set(resolved_dates)
            ),
            "decision_count_total": len(decisions_by_key),
            "settled_decision_count": sum(
                1
                for row in settlements_by_key.values()
                if row.get("settled") is True
            ),
            "settled_restart_decision_count": len(settled_restart),
            "voided_decision_count": len(voided),
            "pending_settlement_count": len(decisions_by_key)
            - len(settlements_by_key),
            "late_discovery_excluded_count": len(late_excluded),
            "new_event_count": len(new_events),
            "aggregate_settled_replacement_value": round(
                sum(float(row.get("replacement_value") or 0.0) for row in settled_restart),
                2,
            ),
            "reopen_progress": {
                "required": REOPEN_REQUIRED_SETTLED_DECISIONS,
                "settled_restart_decisions": len(settled_restart),
            },
        }
    )
    atomic_write_json(summary, summary_path)
    return summary
