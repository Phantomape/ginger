"""Shared default-off ORTEX borrow-stress entry-admission policy.

The policy preserves the fixed thresholds from ``exp-20260712-013`` while
adapting them to the authenticated ORTEX ``costToBorrowNew`` sidecar.  ORTEX
does not provide loan availability on this surface, so the alternate
fee-delta/availability branch is deliberately unavailable and can never be
inferred from the fee series alone.

The frozen transition state starts non-stressed and resets to non-stressed
whenever a caller-supplied trading session has no row.  Eligible transitions
schedule exactly one exclusion on the row's strictly next session.  The
resolver is compatible with ``BacktestEngine``: resolving a signal day
evaluates the next fill session.  Missing source coverage fails open to the
caller's base universe, with coverage and missing-field state retained in
immutable provenance.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Iterable, Mapping

try:  # Support both package imports and quant/ script-style imports.
    from .entry_universe_ledger import canonical_hash, membership_hash
except ImportError:  # pragma: no cover - exercised by script runners.
    from entry_universe_ledger import canonical_hash, membership_hash


SOURCE = "ortex_api_cost_to_borrow_new"
RULE_VERSION = "ortex_exp20260712_013_borrow_stress_next_open_entry_gate_v1"
TRADE_ENABLED = False

# Fixed observed-only constants from exp-20260712-013.  Do not retune here.
FEE_LEVEL_STRESS = 1.0
FEE_DELTA5_STRESS = 0.25
AVAIL_RATIO5_STRESS = 0.70
LOOKBACK_SESSIONS = 5
COOLDOWN_SESSIONS = 10
EXCLUSION_SESSIONS = 1

AVAILABILITY_FIELD = "availability"
_POLICY = {
    "fee_level_stress_pct": FEE_LEVEL_STRESS,
    "fee_delta5_stress_pp": FEE_DELTA5_STRESS,
    "availability_ratio5_stress": AVAIL_RATIO5_STRESS,
    "lookback_trading_sessions": LOOKBACK_SESSIONS,
    "lookback_semantics": "exact_caller_trading_session_t_minus_5",
    "initial_stress_state": "non_stressed",
    "missing_trading_session_state": "reset_non_stressed",
    "cooldown_trading_sessions": COOLDOWN_SESSIONS,
    "exclusion_sessions_per_transition": EXCLUSION_SESSIONS,
    "alternate_delta_availability_branch_available": False,
    "alternate_branch_missing_fields": [AVAILABILITY_FIELD],
}


class OrtexBorrowEntryGateError(ValueError):
    """The ORTEX entry-gate source or hash contract is invalid."""


def _normalise_date(value: Any, *, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) and hasattr(value, "date"):
        try:
            candidate = value.date()
        except Exception as exc:  # pragma: no cover - defensive custom object.
            raise OrtexBorrowEntryGateError(
                f"{field} must be an ISO calendar date"
            ) from exc
        if isinstance(candidate, date):
            return candidate.isoformat()
    text = str(value or "").strip()
    if len(text) > 10:
        text = text[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except (TypeError, ValueError) as exc:
        raise OrtexBorrowEntryGateError(
            f"{field} must be an ISO calendar date, got {value!r}"
        ) from exc


def _try_date(value: Any) -> str | None:
    try:
        return _normalise_date(value, field="source date")
    except OrtexBorrowEntryGateError:
        return None


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalise_sessions(values: Iterable[Any]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise OrtexBorrowEntryGateError(
            "trading_sessions must be an iterable, not one string"
        )
    return sorted(
        {
            _normalise_date(value, field="trading session")
            for value in values
        }
    )


def _normalise_tickers(values: Iterable[str]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise OrtexBorrowEntryGateError(
            "base_tickers must be an iterable, not one string"
        )
    return sorted(
        {
            str(value).strip().upper()
            for value in values
            if str(value).strip()
        }
    )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_source_hash(value: str | None) -> str | None:
    if value is None:
        return None
    if not _is_sha256(value):
        raise OrtexBorrowEntryGateError(
            "source_rows_sha256 must be a lowercase SHA-256 hex digest"
        )
    return value


def _strict_next_session(
    sessions: list[str], provider_date: str
) -> tuple[str | None, int | None]:
    position = bisect_right(sessions, provider_date)
    if position >= len(sessions):
        return None, None
    return sessions[position], position


def _source_identity(raw_rows: Iterable[Any]) -> list[dict[str, Any]]:
    """Return a JSON-safe, order-independent identity for caller rows."""
    identities: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            identities.append({"invalid_row_type": type(raw).__name__})
            continue
        identities.append(
            {
                "ticker": str(raw.get("ticker") or "").strip().upper() or None,
                "provider_date": _try_date(raw.get("provider_date")),
                "usable_trade_date": _try_date(raw.get("usable_trade_date")),
                "cost_to_borrow_new_pct": _finite_number(
                    raw.get("cost_to_borrow_new_pct")
                ),
                "historical_block": (
                    str(raw.get("historical_block")).strip()
                    if raw.get("historical_block") is not None
                    and str(raw.get("historical_block")).strip()
                    else None
                ),
            }
        )
    return sorted(identities, key=lambda row: canonical_hash(row))


def _normalise_source_rows(
    raw_rows: list[Any], sessions: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for row_number, raw in enumerate(raw_rows, start=1):
        if not isinstance(raw, Mapping):
            invalid.append(
                {
                    "row_number": row_number,
                    "ticker": None,
                    "provider_date": None,
                    "usable_trade_date": None,
                    "missing_fields": [
                        "ticker",
                        "provider_date",
                        "usable_trade_date",
                        "cost_to_borrow_new_pct",
                    ],
                    "reasons": ["source_row_not_mapping"],
                }
            )
            continue

        ticker = str(raw.get("ticker") or "").strip().upper()
        provider_date = _try_date(raw.get("provider_date"))
        usable_trade_date = _try_date(raw.get("usable_trade_date"))
        fee = _finite_number(raw.get("cost_to_borrow_new_pct"))
        missing_fields: list[str] = []
        if not ticker:
            missing_fields.append("ticker")
        if provider_date is None:
            missing_fields.append("provider_date")
        if usable_trade_date is None:
            missing_fields.append("usable_trade_date")
        if fee is None:
            missing_fields.append("cost_to_borrow_new_pct")

        reasons: list[str] = []
        expected_usable: str | None = None
        usable_position: int | None = None
        if provider_date is not None:
            expected_usable, usable_position = _strict_next_session(
                sessions, provider_date
            )
            if expected_usable is None:
                reasons.append("no_strictly_next_caller_supplied_trading_session")
            elif usable_trade_date != expected_usable:
                reasons.append("usable_trade_date_not_strict_next_session")

        if missing_fields or reasons:
            invalid.append(
                {
                    "row_number": row_number,
                    "ticker": ticker or None,
                    "provider_date": provider_date,
                    "usable_trade_date": usable_trade_date,
                    "expected_usable_trade_date": expected_usable,
                    "missing_fields": missing_fields,
                    "reasons": reasons,
                }
            )
            continue

        historical_block = raw.get("historical_block")
        valid.append(
            {
                "ticker": ticker,
                "provider_date": provider_date,
                "usable_trade_date": usable_trade_date,
                "usable_session_position": usable_position,
                "cost_to_borrow_new_pct": fee,
                "historical_block": (
                    str(historical_block).strip()
                    if historical_block is not None
                    and str(historical_block).strip()
                    else None
                ),
                "source_row_number": row_number,
            }
        )

    # Conflicting same-ticker/provider-date rows are not safe to choose between.
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in valid:
        by_key[(row["ticker"], row["provider_date"])].append(row)
    deduplicated: list[dict[str, Any]] = []
    for key, candidates in sorted(by_key.items()):
        semantic = {
            canonical_hash(
                {
                    field: row[field]
                    for field in (
                        "ticker",
                        "provider_date",
                        "usable_trade_date",
                        "cost_to_borrow_new_pct",
                        "historical_block",
                    )
                }
            )
            for row in candidates
        }
        if len(semantic) > 1:
            invalid.append(
                {
                    "row_number": min(row["source_row_number"] for row in candidates),
                    "ticker": key[0],
                    "provider_date": key[1],
                    "usable_trade_date": None,
                    "missing_fields": [],
                    "reasons": ["conflicting_duplicate_source_rows"],
                }
            )
            continue
        deduplicated.append(min(candidates, key=lambda row: row["source_row_number"]))
    deduplicated.sort(
        key=lambda row: (
            row["ticker"],
            row["provider_date"],
            row["usable_trade_date"],
        )
    )
    invalid.sort(
        key=lambda row: (
            int(row.get("row_number") or 0),
            str(row.get("ticker") or ""),
        )
    )
    return deduplicated, invalid


def build_ortex_borrow_stress_exclusion_index(
    rows: Iterable[Mapping[str, Any]],
    trading_sessions: Iterable[Any],
    source_rows_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a hash-bound one-fill-session exclusion index.

    A row is usable only when its ``usable_trade_date`` exactly matches the
    first supplied session strictly after ``provider_date``.  Transition state
    starts non-stressed and any missing caller trading session resets it to
    non-stressed, exactly matching exp-20260712-013.  Fee delta uses the row on
    the exact caller session at t-5, never the fifth prior source row.  Missing
    availability permanently disables that alternate branch, so a large fee
    delta alone never marks an ORTEX row stressed.
    """
    raw_rows = list(rows)
    sessions = _normalise_sessions(trading_sessions)
    supplied_source_hash = _validate_source_hash(source_rows_sha256)
    source_rows_canonical_hash = canonical_hash(
        {"source": SOURCE, "rows": _source_identity(raw_rows)}
    )
    if (
        supplied_source_hash is not None
        and supplied_source_hash != source_rows_canonical_hash
    ):
        raise OrtexBorrowEntryGateError(
            "source_rows_sha256 does not match the canonical input rows"
        )
    # The resolver identity is always derived from the supplied rows.  Callers
    # may pass the same precomputed canonical digest as an assertion, but they
    # cannot substitute an unrelated, merely well-formed SHA-256 value.
    bound_source_hash = source_rows_canonical_hash
    normalised, invalid = _normalise_source_rows(raw_rows, sessions)

    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalised:
        by_ticker[row["ticker"]].append(row)

    by_session: dict[str, set[str]] = defaultdict(set)
    coverage_by_session: dict[str, set[str]] = defaultdict(set)
    observations: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    suppressed_transition_count = 0

    session_positions = {session: position for position, session in enumerate(sessions)}
    for ticker, ticker_rows in sorted(by_ticker.items()):
        last_exclusion_signal_position: int | None = None
        stressed_prev = False
        prior_observation: dict[str, Any] | None = None
        reset_reason = "initial_non_stressed_state"
        rows_by_provider_date = {
            row["provider_date"]: row for row in ticker_rows
        }
        timeline = sorted(set(sessions) | set(rows_by_provider_date))

        for provider_day in timeline:
            row = rows_by_provider_date.get(provider_day)
            if row is None:
                # exp-20260712-013 iterated the trading-session spine and
                # explicitly reset stressed_prev=False on a missing row.
                if provider_day in session_positions:
                    stressed_prev = False
                    prior_observation = None
                    reset_reason = "missing_trading_session_reset"
                continue

            block = row["historical_block"]
            provider_position = session_positions.get(provider_day)
            lookback_day = (
                sessions[provider_position - LOOKBACK_SESSIONS]
                if provider_position is not None
                and provider_position >= LOOKBACK_SESSIONS
                else None
            )
            lookback = (
                rows_by_provider_date.get(lookback_day)
                if lookback_day is not None
                else None
            )
            fee_delta5 = (
                row["cost_to_borrow_new_pct"]
                - lookback["cost_to_borrow_new_pct"]
                if lookback is not None
                else None
            )
            fee_level_stressed = (
                row["cost_to_borrow_new_pct"] >= FEE_LEVEL_STRESS
            )
            alternate_branch_available = False
            alternate_branch_stressed = False
            stressed = bool(fee_level_stressed or alternate_branch_stressed)
            prior_observed = prior_observation is not None
            prior_non_stressed = bool(
                prior_observation is not None and not prior_observation["stressed"]
            )
            stress_transition = bool(stressed and not stressed_prev)
            usable_position = int(row["usable_session_position"])
            signal_position = usable_position - 1
            cooldown_eligible = bool(
                last_exclusion_signal_position is None
                or signal_position
                > last_exclusion_signal_position + COOLDOWN_SESSIONS
            )
            eligible_transition = bool(stress_transition and cooldown_eligible)

            coverage_by_session[row["usable_trade_date"]].add(ticker)
            observation = {
                "ticker": ticker,
                "provider_date": row["provider_date"],
                "usable_trade_date": row["usable_trade_date"],
                "historical_block": block,
                "cost_to_borrow_new_pct": row["cost_to_borrow_new_pct"],
                "lookback_provider_date": lookback_day,
                "fee_delta5_pp": fee_delta5,
                "availability_ratio5": None,
                "fee_level_branch_stressed": fee_level_stressed,
                "alternate_delta_availability_branch_available": (
                    alternate_branch_available
                ),
                "alternate_delta_availability_branch_stressed": (
                    alternate_branch_stressed
                ),
                "alternate_branch_missing_fields": [AVAILABILITY_FIELD],
                "stressed": stressed,
                "prior_observed": prior_observed,
                "prior_provider_date": (
                    prior_observation["provider_date"]
                    if prior_observation is not None
                    else None
                ),
                "prior_non_stressed": prior_non_stressed,
                "transition_state_before": (
                    "stressed" if stressed_prev else "non_stressed"
                ),
                "transition_state_basis": (
                    "prior_observed_row" if prior_observed else reset_reason
                ),
                "stress_transition": stress_transition,
                "cooldown_eligible": cooldown_eligible,
                "eligible_transition": eligible_transition,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_live_orders": False,
            }
            observations.append(observation)
            if eligible_transition:
                last_exclusion_signal_position = signal_position
                by_session[row["usable_trade_date"]].add(ticker)
                transitions.append(
                    {
                        **observation,
                        "exclusion_session": row["usable_trade_date"],
                        "exclusion_session_count": EXCLUSION_SESSIONS,
                        "decision": "observe_fresh_entry_exclusion_default_off",
                    }
                )
            elif stress_transition:
                suppressed_transition_count += 1

            stressed_prev = stressed
            prior_observation = {
                "provider_date": row["provider_date"],
                "stressed": stressed,
            }
            reset_reason = "prior_observed_row"

    observations.sort(key=lambda row: (row["provider_date"], row["ticker"]))
    transitions.sort(key=lambda row: (row["provider_date"], row["ticker"]))
    payload: dict[str, Any] = {
        "schema": "ortex_borrow_stress_entry_exclusion_index_v1",
        "source": SOURCE,
        "rule_version": RULE_VERSION,
        "policy": deepcopy(_POLICY),
        "activation_semantics": (
            "one_exclusion_on_strict_usable_trade_date_when_stressed_and_"
            "previous_state_non_stressed_initially_or_after_missing_session"
        ),
        "resolver_semantics": (
            "resolve_signal_day_tests_next_caller_supplied_fill_session"
        ),
        "unknown_coverage_policy": "fail_open_to_base_universe_with_provenance",
        "source_rows_sha256": bound_source_hash,
        "source_rows_sha256_supplied": supplied_source_hash is not None,
        "source_rows_canonical_hash": source_rows_canonical_hash,
        "trading_sessions": sessions,
        "trading_sessions_hash": canonical_hash(sessions),
        "input_row_count": len(raw_rows),
        "valid_row_count": len(normalised),
        "invalid_row_count": len(invalid),
        "invalid_rows": invalid,
        "observations": observations,
        "transition_count": len(transitions),
        "suppressed_transition_count": suppressed_transition_count,
        "transitions": transitions,
        "by_session": {
            session: sorted(tickers)
            for session, tickers in sorted(by_session.items())
        },
        "coverage_by_session": {
            session: sorted(tickers)
            for session, tickers in sorted(coverage_by_session.items())
        },
        "policy_field_coverage": {
            "cost_to_borrow_new_pct": True,
            AVAILABILITY_FIELD: False,
            "alternate_delta_availability_branch_available": False,
            "missing_policy_fields": [AVAILABILITY_FIELD],
        },
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_live_orders": False,
    }
    payload["index_hash"] = canonical_hash(payload)
    return payload


class OrtexBorrowEntryUniverseResolver:
    """BacktestEngine-compatible next-fill entry-universe resolver."""

    def __init__(
        self,
        base_tickers: Iterable[str],
        exclusion_index: Mapping[str, Any],
        trading_sessions: Iterable[Any] | None = None,
        source_rows_sha256: str | None = None,
    ) -> None:
        self._base = frozenset(_normalise_tickers(base_tickers))
        self._index = deepcopy(dict(exclusion_index))
        stored_hash = self._index.pop("index_hash", None)
        if stored_hash != canonical_hash(self._index):
            raise OrtexBorrowEntryGateError(
                "ORTEX borrow exclusion index hash mismatch"
            )
        if (
            self._index.get("schema")
            != "ortex_borrow_stress_entry_exclusion_index_v1"
            or self._index.get("source") != SOURCE
            or self._index.get("rule_version") != RULE_VERSION
            or self._index.get("policy") != _POLICY
        ):
            raise OrtexBorrowEntryGateError(
                "ORTEX borrow exclusion index identity mismatch"
            )
        self._index["index_hash"] = stored_hash

        indexed_sessions = _normalise_sessions(
            self._index.get("trading_sessions") or []
        )
        supplied_sessions = (
            _normalise_sessions(trading_sessions)
            if trading_sessions is not None
            else indexed_sessions
        )
        if supplied_sessions != indexed_sessions:
            raise OrtexBorrowEntryGateError(
                "resolver trading_sessions differ from the hash-bound index"
            )
        expected_source_hash = _validate_source_hash(source_rows_sha256)
        indexed_source_hash = self._index.get("source_rows_sha256")
        if not _is_sha256(indexed_source_hash):
            raise OrtexBorrowEntryGateError(
                "hash-bound index has an invalid source_rows_sha256"
            )
        if (
            expected_source_hash is not None
            and expected_source_hash != indexed_source_hash
        ):
            raise OrtexBorrowEntryGateError(
                "resolver source_rows_sha256 differs from the hash-bound index"
            )

        self._sessions = tuple(indexed_sessions)
        self._source_hash = str(indexed_source_hash)
        self._by_session = {
            str(session): frozenset(str(ticker).upper() for ticker in tickers)
            for session, tickers in (self._index.get("by_session") or {}).items()
        }
        self._coverage_by_session = {
            str(session): frozenset(str(ticker).upper() for ticker in tickers)
            for session, tickers in (
                self._index.get("coverage_by_session") or {}
            ).items()
        }
        self._metadata = {
            "schema": "ortex_borrow_entry_universe_resolver_metadata_v1",
            "source": SOURCE,
            "source_hash": self._source_hash,
            "rule_version": RULE_VERSION,
            "index_hash": stored_hash,
            "trading_sessions_hash": self._index["trading_sessions_hash"],
            "base_ticker_count": len(self._base),
            "base_membership_hash": membership_hash(self._base),
            "transition_count": self._index["transition_count"],
            "fill_semantics": (
                "resolve(signal_day) applies one exclusion when the next_"
                "trading_session fill has an eligible borrow-stress transition"
            ),
            "unknown_coverage_policy": (
                "fail_open_to_base_universe_with_provenance"
            ),
            "policy_field_coverage": deepcopy(
                self._index["policy_field_coverage"]
            ),
            "trade_enabled": False,
            "strategy_behavior_changed": False,
            "alters_live_orders": False,
        }

    @property
    def data_tickers(self) -> frozenset[str]:
        return self._base

    @property
    def metadata(self) -> dict[str, Any]:
        return deepcopy(self._metadata)

    def resolve(self, as_of: Any) -> dict[str, Any]:
        day = _normalise_date(as_of, field="as_of")
        next_position = bisect_right(self._sessions, day)
        entry_session = (
            self._sessions[next_position]
            if next_position < len(self._sessions)
            else None
        )
        covered = (
            self._coverage_by_session.get(entry_session, frozenset())
            if entry_session is not None
            else frozenset()
        )
        excluded = (
            self._by_session.get(entry_session, frozenset())
            if entry_session is not None
            else frozenset()
        )
        covered_base = sorted(self._base & covered)
        missing_base = sorted(self._base - covered)
        excluded_base = sorted(self._base & excluded)
        eligible = sorted(self._base - excluded)

        if entry_session is None:
            coverage_status = "unknown_no_next_trading_session"
        elif not missing_base:
            coverage_status = "covered"
        elif covered_base:
            coverage_status = "partial"
        else:
            coverage_status = "uncovered"
        missing_source_fields_by_ticker = {
            ticker: ["cost_to_borrow_new_pct"] for ticker in missing_base
        }
        missing_fields = [AVAILABILITY_FIELD]
        if missing_base:
            missing_fields.append("cost_to_borrow_new_pct")

        semantic = {
            "as_of": day,
            "entry_session": entry_session,
            "eligible": eligible,
            "excluded": excluded_base,
            "covered": covered_base,
            "missing": missing_base,
            "coverage_status": coverage_status,
            "missing_fields": missing_fields,
            "source_hash": self._source_hash,
            "index_hash": self._index["index_hash"],
            "rule_version": RULE_VERSION,
        }
        snapshot_hash = canonical_hash(
            {"record_type": "ortex_borrow_entry_membership", **semantic}
        )
        record_hash = canonical_hash(
            {"record_type": "ortex_borrow_entry_resolution", **semantic}
        )
        provenance = {
            "rule_version": RULE_VERSION,
            "index_hash": self._index["index_hash"],
            "source_rows_sha256": self._source_hash,
            "entry_session": entry_session,
            "excluded_tickers": excluded_base,
            "coverage_status": coverage_status,
            "source_coverage_complete": not missing_base,
            "covered_tickers": covered_base,
            "missing_tickers": missing_base,
            "missing_fields": missing_fields,
            "missing_source_fields_by_ticker": missing_source_fields_by_ticker,
            "missing_policy_fields": [AVAILABILITY_FIELD],
            "alternate_delta_availability_branch_available": False,
            "fill_semantics": self._metadata["fill_semantics"],
            "unknown_coverage_policy": self._metadata[
                "unknown_coverage_policy"
            ],
            "trade_enabled": False,
            "strategy_behavior_changed": False,
            "alters_live_orders": False,
        }
        if excluded_base:
            reason = "next_session_borrow_stress_entry_exclusion"
        elif coverage_status in {"covered", "partial"}:
            reason = "no_active_next_session_exclusion"
        else:
            reason = f"fail_open_{coverage_status}"
        return {
            "status": "resolved",
            "as_of": day,
            "snapshot_as_of": day,
            "effective_as_of": day,
            "snapshot_sha256": snapshot_hash,
            "snapshot_hash": snapshot_hash,
            "record_hash": record_hash,
            "tickers": eligible,
            "ticker_count": len(eligible),
            "membership_hash": membership_hash(eligible),
            "source": SOURCE,
            "source_hash": self._source_hash,
            "rule_version": RULE_VERSION,
            "clean_cutoff": day,
            "reason": reason,
            "provenance": provenance,
        }

    def __call__(self, as_of: Any) -> set[str]:
        return set(self.resolve(as_of)["tickers"])


def _default_off_flags() -> dict[str, bool]:
    return {
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_live_orders": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
    }


def build_daily_entry_admission_snapshot(
    rows: Iterable[Mapping[str, Any]],
    as_of: Any,
    trading_sessions: Iterable[Any],
    base_tickers: Iterable[str],
) -> dict[str, Any]:
    """Build the daily default-off admission snapshot with resolver parity."""
    row_values = list(rows)
    sessions = list(trading_sessions)
    base = _normalise_tickers(base_tickers)
    index = build_ortex_borrow_stress_exclusion_index(row_values, sessions)
    resolver = OrtexBorrowEntryUniverseResolver(
        base,
        index,
        trading_sessions=sessions,
        source_rows_sha256=index["source_rows_sha256"],
    )
    resolved = resolver.resolve(as_of)
    provenance = resolved["provenance"]
    excluded = list(provenance["excluded_tickers"])
    return {
        "schema": "ortex_borrow_entry_admission_daily_snapshot_v1",
        "record_id": f"ortex_borrow_entry_admission:{resolved['as_of']}",
        "source": SOURCE,
        "source_hash": resolved["source_hash"],
        "rule_version": RULE_VERSION,
        "policy": deepcopy(_POLICY),
        "as_of": resolved["as_of"],
        "next_trading_session": provenance["entry_session"],
        "status": "ok" if provenance["entry_session"] else "calendar_uncovered",
        "decision": "observe_entry_admission_default_off",
        "base_tickers": base,
        "base_ticker_count": len(base),
        "eligible_tickers": list(resolved["tickers"]),
        "eligible_ticker_count": resolved["ticker_count"],
        "excluded_tickers_for_next_session": excluded,
        "candidate_count": len(excluded),
        "candidates": [
            {
                "ticker": ticker,
                "signal_date": resolved["as_of"],
                "entry_session": provenance["entry_session"],
                "decision": "observe_fresh_entry_exclusion_default_off",
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_live_orders": False,
            }
            for ticker in excluded
        ],
        "coverage_status": provenance["coverage_status"],
        "source_coverage_complete": provenance["source_coverage_complete"],
        "covered_tickers": list(provenance["covered_tickers"]),
        "missing_tickers": list(provenance["missing_tickers"]),
        "missing_fields": list(provenance["missing_fields"]),
        "missing_source_fields_by_ticker": deepcopy(
            provenance["missing_source_fields_by_ticker"]
        ),
        "missing_policy_fields": list(provenance["missing_policy_fields"]),
        "alternate_delta_availability_branch_available": False,
        "source_row_count": index["input_row_count"],
        "valid_source_row_count": index["valid_row_count"],
        "invalid_source_row_count": index["invalid_row_count"],
        "transition_count": index["transition_count"],
        "exclusion_index_hash": index["index_hash"],
        "resolver_snapshot_hash": resolved["snapshot_sha256"],
        "resolver_record_hash": resolved["record_hash"],
        "membership_hash": resolved["membership_hash"],
        **_default_off_flags(),
    }


__all__ = [
    "AVAIL_RATIO5_STRESS",
    "COOLDOWN_SESSIONS",
    "EXCLUSION_SESSIONS",
    "FEE_DELTA5_STRESS",
    "FEE_LEVEL_STRESS",
    "LOOKBACK_SESSIONS",
    "OrtexBorrowEntryGateError",
    "OrtexBorrowEntryUniverseResolver",
    "RULE_VERSION",
    "SOURCE",
    "TRADE_ENABLED",
    "build_daily_entry_admission_snapshot",
    "build_ortex_borrow_stress_exclusion_index",
]
