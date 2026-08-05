"""Massive dividend-restart forward observer (exp-20260802-003).

Default-off, observer-only forward producer for the dividend-restart lane.
exp-20260801-004 closed the historical replay as an observed-only descriptive
lead and froze its reopen contract on settled forward evidence: this module
accumulates the calendar-bound forward candidate rows that contract requires.

Daily contract:
- freeze the complete ``/stocks/v1/dividends`` page chain from the authorized
  Massive API host (the endpoint exposes no declaration-date filter, so the
  full ticker-ascending cursor chain is the only complete discovery surface);
- bind a content identity to the canonical decision-safe row multiset so
  volatile response metadata, pagination order and page partition cannot make
  frozen decision content masquerade as fresh input; retain the ordered raw
  page-chain provenance under a separate audit identity;
- detect new first-positive-USD-cash declarations whose same-ticker positive
  declaration gap is at least ``GAP_DAYS`` days, using only ticker,
  declaration_date, cash_amount and currency (distribution_type, frequency,
  split_adjusted_cash_amount and historical_adjustment_factor stay forbidden
  decision inputs per exp-20260728-008);
- append event-sourced rows to an append-only JSONL ledger: one ``coverage``
  receipt per run, one ``forward_candidate`` row per new ticker:declaration
  decision, and one ``gate_evaluation`` row when the strictly pre-declaration
  liquidity/price gates become computable from warehouse bars.

Clock contract: no wall-clock date enters request parameters or row
attribution. Candidate vintage is ``first_seen_at`` (UTC retrieval time) and
the entry rule is frozen as the first regular session whose 09:30 America/
New_York open is strictly after ``first_seen_at``; session resolution is
deferred to the settlement contract (observer first-build ID 2). The recency
window for gap scanning is anchored to the fetched chain's own maximum
declaration date, never to the process clock.

Every emitted row is observer-only with ``trade_enabled`` false. Nothing here
alters orders, ranking, sizing or exits.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from massive_ohlcv_backfill import (
        API_ORIGIN,
        MassiveClient,
        MassiveError,
        load_api_key,
        _canonical_decimal_text,
        _decode_decimal_json,
        _sanitize_api_url,
    )
    from data_paths import atomic_write_json
    from us_market_calendar import latest_completed_us_equity_session
except ImportError:  # pragma: no cover - package-style imports for tooling
    from quant.massive_ohlcv_backfill import (
        API_ORIGIN,
        MassiveClient,
        MassiveError,
        load_api_key,
        _canonical_decimal_text,
        _decode_decimal_json,
        _sanitize_api_url,
    )
    from quant.data_paths import atomic_write_json
    from quant.us_market_calendar import latest_completed_us_equity_session

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "massive_dividend_restart_forward"
DEFAULT_BARS_DATABASE = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"

SCHEMA_VERSION = 1
GAP_DAYS = 1095
RECENT_WINDOW_DAYS = 30
DEFAULT_MAX_PAGES = 400
STALE_UNCHANGED_RUNS = 3
CONTENT_IDENTITY_KIND = "decision_safe_dividend_row_multiset_v2"
RETRIEVAL_PROVENANCE_IDENTITY_KIND = "ordered_sanitized_page_raw_sha256_v1"
PRE_DECLARATION_BARS = 20
MIN_MEDIAN_DOLLAR_VOLUME = 1_000_000.0
MIN_LAST_CLOSE = 3.0
ENTRY_RULE = (
    "first_regular_session_0930_america_new_york_open_strictly_after_first_seen_at"
)
EXPECTED_CADENCE = "at_least_one_coverage_row_per_trading_day_zero_candidates_normal"


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_date(value: Any) -> str | None:
    text = str(value or "").strip()[:10]
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def fetch_dividend_page_chain(
    client: MassiveClient,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    """Freeze the complete dividends cursor chain into a minimal projection.

    Returns positive-USD rows only (the sole decision-safe filter this lane is
    allowed) plus a chain-level content identity. Raises ``MassiveError`` on
    any contract violation so the caller fails closed.
    """

    page_bound = int(max_pages)
    if page_bound < 1:
        raise MassiveError("Dividend forward page bound must be positive")
    url: str | None = f"{API_ORIGIN}/stocks/v1/dividends?limit=5000"
    seen_urls: set[str] = set()
    retrieval_provenance: list[dict[str, Any]] = []
    rows_by_provider: dict[str, dict[str, Any]] = {}
    anonymous_rows: list[dict[str, Any]] = []
    total_rows = 0
    skipped_rows = 0
    page_number = 0
    while url:
        page_number += 1
        if page_number > page_bound:
            raise MassiveError("Dividend forward pagination exceeded its page bound")
        safe_url = _sanitize_api_url(url)
        if not safe_url.split("?", 1)[0].endswith("/stocks/v1/dividends"):
            raise MassiveError("Dividend forward pagination left the dividends path")
        if safe_url in seen_urls:
            raise MassiveError("Dividend forward pagination cursor repeated")
        seen_urls.add(safe_url)
        fetched = client.get_json(safe_url)
        payload = _decode_decimal_json(fetched.raw_bytes, label="Dividend forward")
        if payload.get("status") not in {"OK", "DELAYED"}:
            raise MassiveError("Dividend forward response status was not usable")
        raw_rows = payload.get("results")
        if not isinstance(raw_rows, list):
            raise MassiveError("Dividend forward results must be a list")
        raw_sha256 = hashlib.sha256(fetched.raw_bytes).hexdigest()
        if fetched.sha256 != raw_sha256:
            raise MassiveError("Dividend forward raw response digest mismatched")
        retrieval_provenance.append(
            {
                "page_number": page_number,
                "sanitized_url": safe_url,
                "raw_sha256": raw_sha256,
            }
        )
        for raw in raw_rows:
            if not isinstance(raw, Mapping):
                skipped_rows += 1
                continue
            total_rows += 1
            ticker = str(raw.get("ticker") or "").strip().upper()
            declaration_date = _valid_date(raw.get("declaration_date"))
            currency = str(raw.get("currency") or "").strip().lower()
            if not ticker or declaration_date is None or currency != "usd":
                skipped_rows += 1
                continue
            try:
                cash_amount = _canonical_decimal_text(
                    raw.get("cash_amount"), "cash_amount"
                )
            except MassiveError:
                skipped_rows += 1
                continue
            if not cash_amount or cash_amount.startswith("-") or cash_amount == "0":
                skipped_rows += 1
                continue
            provider_value = raw.get("id")
            provider_text = (
                str(provider_value).strip() if provider_value is not None else ""
            )
            provider_id = provider_text or None
            row = {
                "provider_id": provider_id,
                "ticker": ticker,
                "declaration_date": declaration_date,
                "cash_amount": cash_amount,
            }
            if provider_id is None:
                anonymous_rows.append(row)
            else:
                previous = rows_by_provider.get(provider_id)
                if previous is None:
                    rows_by_provider[provider_id] = row
                elif previous != row:
                    raise MassiveError(
                        "Dividend forward provider_id has conflicting decision fields"
                    )
        next_url_value = payload.get("next_url")
        url = str(next_url_value) if next_url_value else None

    rows = sorted(
        [*rows_by_provider.values(), *anonymous_rows],
        key=lambda row: (
            str(row["provider_id"] or ""),
            row["ticker"],
            row["declaration_date"],
            row["cash_amount"],
        ),
    )
    declaration_dates = [row["declaration_date"] for row in rows]
    max_declaration_date = max(declaration_dates) if declaration_dates else None
    min_declaration_date = min(declaration_dates) if declaration_dates else None
    identity_material = json.dumps(
        {
            "content_identity_kind": CONTENT_IDENTITY_KIND,
            "rows": rows,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    retrieval_provenance_material = json.dumps(
        {
            "retrieval_provenance_identity_kind": (
                RETRIEVAL_PROVENANCE_IDENTITY_KIND
            ),
            "pages": retrieval_provenance,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "rows": rows,
        "page_count": len(retrieval_provenance),
        "provider_row_count": total_rows,
        "positive_usd_row_count": len(rows),
        "skipped_row_count": skipped_rows,
        "max_declaration_date": max_declaration_date,
        "min_declaration_date": min_declaration_date,
        "content_identity_kind": CONTENT_IDENTITY_KIND,
        "content_identity": hashlib.sha256(identity_material).hexdigest(),
        "retrieval_provenance_identity_kind": (
            RETRIEVAL_PROVENANCE_IDENTITY_KIND
        ),
        "retrieval_provenance_identity": hashlib.sha256(
            retrieval_provenance_material
        ).hexdigest(),
        "retrieval_provenance": retrieval_provenance,
    }


def detect_new_candidates(
    chain: Mapping[str, Any],
    known_decision_keys: set[str],
    *,
    gap_days: int = GAP_DAYS,
    recent_window_days: int = RECENT_WINDOW_DAYS,
    first_seen_at: str,
) -> list[dict[str, Any]]:
    """Detect first-positive-USD declarations after a >=gap_days gap.

    The recency cutoff anchors to the chain's own max declaration date (data
    calendar), never the process clock. A ticker with no prior positive USD
    declaration anywhere in the provider chain only qualifies when the chain's
    global minimum declaration date proves at least ``gap_days`` days of
    lookback coverage before the candidate declaration.
    """

    max_decl = chain.get("max_declaration_date")
    min_decl = chain.get("min_declaration_date")
    if not max_decl or not min_decl:
        return []
    anchor = dt.date.fromisoformat(max_decl)
    coverage_floor = dt.date.fromisoformat(min_decl)
    cutoff = (anchor - dt.timedelta(days=int(recent_window_days))).isoformat()

    by_ticker: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in chain.get("rows", []):
        by_ticker[row["ticker"]][row["declaration_date"]].append(row)

    candidates: list[dict[str, Any]] = []
    for ticker, per_date in by_ticker.items():
        dates = sorted(per_date)
        for index, declaration_date in enumerate(dates):
            if declaration_date < cutoff:
                continue
            decision_key = f"{ticker}:{declaration_date}"
            if decision_key in known_decision_keys:
                continue
            decl = dt.date.fromisoformat(declaration_date)
            prior = dates[index - 1] if index > 0 else None
            if prior is not None:
                gap = (decl - dt.date.fromisoformat(prior)).days
                if gap < int(gap_days):
                    continue
                gap_variant = "restart_after_observed_gap"
            else:
                gap = None
                if (decl - coverage_floor).days < int(gap_days):
                    # Cannot prove the gap: provider history is too shallow
                    # before this declaration. Skip rather than emit unprovable
                    # rows.
                    continue
                gap_variant = "no_prior_positive_in_provider_history"
            same_date_rows = per_date[declaration_date]
            candidates.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "forward_candidate",
                    "decision_key": decision_key,
                    "ticker": ticker,
                    "declaration_date": declaration_date,
                    "prior_positive_declaration_date": prior,
                    "gap_days": gap,
                    "gap_variant": gap_variant,
                    "cash_amounts": sorted(
                        {row["cash_amount"] for row in same_date_rows}
                    ),
                    "provider_ids": sorted(
                        {
                            row["provider_id"]
                            for row in same_date_rows
                            if row["provider_id"]
                        }
                    ),
                    "first_seen_at": first_seen_at,
                    "entry_rule": ENTRY_RULE,
                    "content_identity_kind": chain.get("content_identity_kind"),
                    "content_identity": chain.get("content_identity"),
                    "observer_only": True,
                    "trade_enabled": False,
                }
            )
    candidates.sort(key=lambda row: row["decision_key"])
    return candidates


def evaluate_pending_gates(
    pending_candidates: list[Mapping[str, Any]],
    *,
    bars_database: Path | str = DEFAULT_BARS_DATABASE,
    evaluated_at: str,
) -> list[dict[str, Any]]:
    """Evaluate strictly pre-declaration liquidity/price gates when possible.

    Gate inputs are immutable pre-declaration facts, so late evaluation is not
    look-ahead. A candidate stays pending (no row emitted) until warehouse
    coverage reaches its declaration date; insufficient pre-declaration bars
    are a final ineligible verdict.
    """

    if not pending_candidates:
        return []
    database = Path(bars_database)
    if not database.is_file():
        return []
    evaluations: list[dict[str, Any]] = []
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as conn:
        max_row = conn.execute("SELECT MAX(trade_date) FROM daily_bars").fetchone()
        warehouse_max = max_row[0] if max_row else None
        if not warehouse_max:
            return []
        for candidate in pending_candidates:
            declaration_date = str(candidate["declaration_date"])
            if warehouse_max < declaration_date:
                continue  # bars not yet available; retry on a later run
            bars = conn.execute(
                "SELECT trade_date, close, volume FROM daily_bars "
                "WHERE ticker=? AND trade_date<? ORDER BY trade_date DESC LIMIT ?",
                (
                    str(candidate["ticker"]),
                    declaration_date,
                    PRE_DECLARATION_BARS,
                ),
            ).fetchall()
            evaluation: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "record_type": "gate_evaluation",
                "decision_key": str(candidate["decision_key"]),
                "evaluated_at": evaluated_at,
                "warehouse_max_trade_date": warehouse_max,
                "pre_declaration_bar_count": len(bars),
                "observer_only": True,
                "trade_enabled": False,
            }
            if len(bars) < PRE_DECLARATION_BARS:
                evaluation.update(
                    {
                        "eligible": False,
                        "reason": "insufficient_pre_declaration_bars",
                    }
                )
            else:
                dollar_volumes = [
                    float(close) * float(volume)
                    for _, close, volume in bars
                    if close is not None and volume is not None
                ]
                last_close = bars[0][1]
                if len(dollar_volumes) < PRE_DECLARATION_BARS or last_close is None:
                    evaluation.update(
                        {
                            "eligible": False,
                            "reason": "missing_close_or_volume_fields",
                        }
                    )
                else:
                    median_dollar_volume = statistics.median(dollar_volumes)
                    evaluation.update(
                        {
                            "median_dollar_volume_20": round(median_dollar_volume, 2),
                            "last_pre_declaration_close": float(last_close),
                            "eligible": (
                                median_dollar_volume >= MIN_MEDIAN_DOLLAR_VOLUME
                                and float(last_close) >= MIN_LAST_CLOSE
                            ),
                            "reason": "gates_computed",
                        }
                    )
            evaluations.append(evaluation)
    evaluations.sort(key=lambda row: row["decision_key"])
    return evaluations


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _append_ledger(path: Path, rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _ledger_views(
    ledger_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    candidates: dict[str, Mapping[str, Any]] = {}
    evaluations: dict[str, Mapping[str, Any]] = {}
    for row in ledger_rows:
        record_type = row.get("record_type")
        key = str(row.get("decision_key") or "")
        if not key:
            continue
        if record_type == "forward_candidate" and key not in candidates:
            candidates[key] = row
        elif record_type == "gate_evaluation":
            evaluations[key] = row
    return candidates, evaluations


def persist_massive_dividend_restart_forward_observer(
    today: Any = None,
    *,
    client: MassiveClient | None = None,
    out_dir: Path | str = DEFAULT_OUT_DIR,
    bars_database: Path | str = DEFAULT_BARS_DATABASE,
    max_pages: int = DEFAULT_MAX_PAGES,
    stale_unchanged_runs: int = STALE_UNCHANGED_RUNS,
    now_fn: Callable[[], dt.datetime] = _utc_now,
) -> dict[str, Any]:
    """Run one observer cycle and persist ledger, state and summary.

    ``today`` is a caller-provided run label recorded on the coverage receipt;
    it never enters request parameters or row attribution. The function never
    raises: any failure is persisted as a non-ok fail-closed status.
    """

    output_root = Path(out_dir)
    state_path = output_root / "state.json"
    ledger_path = output_root / "ledger.jsonl"
    summary_path = output_root / "latest_summary.json"
    run_started_at = _iso(now_fn())
    state: dict[str, Any] = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "default_off_massive_dividend_restart_forward_observer",
        "source_experiment": "exp-20260802-003",
        "run_label": None if today is None else str(today),
        "run_started_at": run_started_at,
        "expected_cadence": EXPECTED_CADENCE,
        "entry_rule": ENTRY_RULE,
        "gap_days": GAP_DAYS,
        "observer_only": True,
        "trade_enabled": False,
    }

    try:
        if client is None:
            client = MassiveClient(load_api_key())
        chain = fetch_dividend_page_chain(client, max_pages=max_pages)
    except MassiveError as exc:
        summary.update(
            {
                "status": "error",
                "reason": "fetch_failed_or_credential_missing",
                "error": str(exc),
                "alert": True,
            }
        )
        _append_ledger(
            ledger_path,
            [
                {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "coverage",
                    "run_label": summary["run_label"],
                    "run_started_at": run_started_at,
                    "status": "error",
                    "error": str(exc),
                }
            ],
        )
        atomic_write_json(summary, summary_path)
        return summary

    fetched_clock = now_fn()
    fetched_at = _iso(fetched_clock)
    completed_session = latest_completed_us_equity_session(fetched_clock).isoformat()
    previous_identity = str(state.get("last_content_identity") or "")
    previous_kind = str(state.get("content_identity_kind") or "")
    previous_session = _valid_date(state.get("last_completed_us_equity_session"))
    session_anchor = max(
        value for value in (previous_session, completed_session) if value is not None
    )
    prior_unchanged_sessions = int(
        state.get(
            "consecutive_unchanged_content_sessions",
            state.get("consecutive_unchanged_content_runs") or 0,
        )
    )
    legacy_state_migrated = bool(
        previous_identity and previous_kind != CONTENT_IDENTITY_KIND
    )
    if legacy_state_migrated or chain["content_identity"] != previous_identity:
        unchanged_sessions = 0
    elif previous_session is None:
        # Establish a completed-session anchor without interpreting an
        # unanchored persisted count as fresh evidence.
        unchanged_sessions = 0
    elif completed_session > previous_session:
        unchanged_sessions = prior_unchanged_sessions + 1
    else:
        # Same-session, weekend, cross-UTC-midnight and clock-regression reruns
        # cannot advance the freshness counter.
        unchanged_sessions = prior_unchanged_sessions
    stale = unchanged_sessions >= max(1, int(stale_unchanged_runs))

    ledger_rows = _load_ledger(ledger_path)
    candidates_by_key, evaluations_by_key = _ledger_views(ledger_rows)
    new_candidates = detect_new_candidates(
        chain,
        set(candidates_by_key),
        first_seen_at=fetched_at,
    )
    for row in new_candidates:
        candidates_by_key[row["decision_key"]] = row

    pending = [
        row
        for key, row in candidates_by_key.items()
        if key not in evaluations_by_key
    ]
    new_evaluations = evaluate_pending_gates(
        pending,
        bars_database=bars_database,
        evaluated_at=fetched_at,
    )
    for row in new_evaluations:
        evaluations_by_key[row["decision_key"]] = row

    eligible_count = sum(
        1 for row in evaluations_by_key.values() if row.get("eligible") is True
    )
    status = "stale_input" if stale else "ok"
    coverage_row = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "coverage",
        "run_label": summary["run_label"],
        "run_started_at": run_started_at,
        "fetched_at": fetched_at,
        "status": status,
        "completed_us_equity_session": completed_session,
        "content_identity_kind": chain["content_identity_kind"],
        "content_identity": chain["content_identity"],
        "retrieval_provenance_identity_kind": chain[
            "retrieval_provenance_identity_kind"
        ],
        "retrieval_provenance_identity": chain["retrieval_provenance_identity"],
        "retrieval_provenance": chain["retrieval_provenance"],
        "page_count": chain["page_count"],
        "provider_row_count": chain["provider_row_count"],
        "positive_usd_row_count": chain["positive_usd_row_count"],
        "max_declaration_date": chain["max_declaration_date"],
        "new_candidate_count": len(new_candidates),
        "new_gate_evaluation_count": len(new_evaluations),
        "pending_gate_count": len(candidates_by_key) - len(evaluations_by_key),
        "consecutive_unchanged_content_sessions": unchanged_sessions,
        # Compatibility alias consumed by the existing daily coverage wiring.
        "consecutive_unchanged_content_runs": unchanged_sessions,
        "legacy_state_migrated": legacy_state_migrated,
    }
    _append_ledger(ledger_path, [*new_candidates, *new_evaluations, coverage_row])

    state_payload = {
        "schema_version": SCHEMA_VERSION,
        "last_run_started_at": run_started_at,
        "last_fetched_at": fetched_at,
        "last_status": status,
        "content_identity_kind": chain["content_identity_kind"],
        "last_content_identity": chain["content_identity"],
        "last_retrieval_provenance_identity_kind": chain[
            "retrieval_provenance_identity_kind"
        ],
        "last_retrieval_provenance_identity": chain[
            "retrieval_provenance_identity"
        ],
        "last_retrieval_provenance": chain["retrieval_provenance"],
        # Monotonic max prevents a regressed clock followed by recovery from
        # counting the same already-observed completed session twice.
        "last_completed_us_equity_session": session_anchor,
        "last_max_declaration_date": chain["max_declaration_date"],
        "last_page_count": chain["page_count"],
        "consecutive_unchanged_content_sessions": unchanged_sessions,
        "consecutive_unchanged_content_runs": unchanged_sessions,
        "candidate_count_total": len(candidates_by_key),
        "gate_evaluated_count_total": len(evaluations_by_key),
    }
    atomic_write_json(state_payload, state_path)

    summary.update(
        {
            "status": status,
            "alert": stale,
            "reason": (
                "content_identity_unchanged_for_completed_sessions"
                if stale
                else None
            ),
            "fetched_at": fetched_at,
            "completed_us_equity_session": completed_session,
            "content_identity_kind": chain["content_identity_kind"],
            "content_identity": chain["content_identity"],
            "retrieval_provenance_identity_kind": chain[
                "retrieval_provenance_identity_kind"
            ],
            "retrieval_provenance_identity": chain[
                "retrieval_provenance_identity"
            ],
            "retrieval_provenance": chain["retrieval_provenance"],
            "page_count": chain["page_count"],
            "provider_row_count": chain["provider_row_count"],
            "positive_usd_row_count": chain["positive_usd_row_count"],
            "max_declaration_date": chain["max_declaration_date"],
            "min_declaration_date": chain["min_declaration_date"],
            "new_candidate_count": len(new_candidates),
            "candidate_count_total": len(candidates_by_key),
            "new_gate_evaluation_count": len(new_evaluations),
            "gate_evaluated_count_total": len(evaluations_by_key),
            "eligible_candidate_count": eligible_count,
            "pending_gate_count": len(candidates_by_key) - len(evaluations_by_key),
            "consecutive_unchanged_content_sessions": unchanged_sessions,
            "consecutive_unchanged_content_runs": unchanged_sessions,
            "legacy_state_migrated": legacy_state_migrated,
        }
    )
    atomic_write_json(summary, summary_path)
    return summary
