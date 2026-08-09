"""Shared SEC N-PORT ownership-breadth fresh-entry gate.

The fixed policy uses the point-in-time report pairing in
``sec_nport_share_accumulation`` but changes the response surface: it counts
independent fund series that bought a ticker from zero or sold it to zero.
With at least twenty matched series, negative breadth excludes only a fresh
candidate.  Zero or missing breadth fails open.

``BacktestEngine`` asks an entry-universe resolver about a signal date and
fills on the following trading session.  The resolver therefore evaluates
N-PORT filings at the strictly next caller-supplied session.  The calendar is
copied and hash-bound at construction, so later caller mutation cannot change
the action clock.  Daily snapshots expose the same decisions as a
non-trading observer; this module has no order, ranking, sizing, add-on, exit,
or cost adapter.
"""

from __future__ import annotations

import json
import threading
import weakref
from bisect import bisect_right
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Iterable, Mapping

try:  # Package and quant/ script-style imports are both used in this repo.
    from .entry_universe_ledger import canonical_hash, membership_hash
    from .sec_nport_share_accumulation import (
        MIN_MATCHED_SERIES as _UPSTREAM_MIN_MATCHED_SERIES,
        RULE_VERSION as SHARE_ACCUMULATION_RULE_VERSION,
        NPortDataset,
        compute_share_accumulation,
    )
except ImportError:  # pragma: no cover - exercised by experiment runners.
    from entry_universe_ledger import canonical_hash, membership_hash
    from sec_nport_share_accumulation import (
        MIN_MATCHED_SERIES as _UPSTREAM_MIN_MATCHED_SERIES,
        RULE_VERSION as SHARE_ACCUMULATION_RULE_VERSION,
        NPortDataset,
        compute_share_accumulation,
    )


SOURCE = "sec_form_nport_public_holdings"
RULE_VERSION = "sec_nport_ownership_breadth_negative_fresh_entry_gate_v1"
MIN_MATCHED_SERIES = 20
TRADE_ENABLED = False

if _UPSTREAM_MIN_MATCHED_SERIES != MIN_MATCHED_SERIES:  # pragma: no cover
    raise RuntimeError(
        "N-PORT ownership breadth and share-accumulation coverage floors drifted"
    )

_POLICY = {
    "min_matched_series": MIN_MATCHED_SERIES,
    "minimum_matched_series": MIN_MATCHED_SERIES,
    "breadth_formula": (
        "(bought_from_zero_series_count-sold_to_zero_series_count)"
        "/matched_series_count"
    ),
    "negative_response": "fresh_candidate_ineligible",
    "zero_response": "fail_open_fresh_candidate_eligible",
    "missing_response": "fail_open_fresh_candidate_eligible",
    "action_clock": "strictly_next_caller_supplied_trading_session",
    "filing_clock": "filing_date_strictly_before_action_date",
    "scope": "fresh_core_entries_only",
}

# Building the semantic identity requires sorting the compact N-PORT records.
# NPortDataset owns immutable tuples of frozen dataclasses, so cache by the
# dataset object while also checking tuple identity/counts in case a caller
# replaces those public attributes.  Weak keys avoid extending dataset life.
_DATASET_IDENTITY_CACHE: weakref.WeakKeyDictionary[
    NPortDataset, tuple[tuple[int, int, int, int], dict[str, Any]]
] = weakref.WeakKeyDictionary()
_DATASET_IDENTITY_CACHE_LOCK = threading.RLock()


class NPortOwnershipBreadthGateError(ValueError):
    """The breadth gate received an invalid calendar or source identity."""


def _default_off_flags() -> dict[str, bool]:
    return {
        "trade_enabled": False,
        "can_place_orders": False,
        "strategy_behavior_changed": False,
        "alters_live_orders": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_existing_positions": False,
        "alters_addons": False,
        "alters_candidate_ranking": False,
        "alters_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_costs": False,
    }


def _normalise_date(value: Any, *, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) and hasattr(value, "date"):
        try:
            candidate = value.date()
        except Exception as exc:  # pragma: no cover - defensive custom object.
            raise NPortOwnershipBreadthGateError(
                f"{field} must be an ISO calendar date"
            ) from exc
        if isinstance(candidate, date):
            return candidate.isoformat()
    text = str(value or "").strip()
    if not text:
        raise NPortOwnershipBreadthGateError(f"{field} is required")
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise NPortOwnershipBreadthGateError(
            f"{field} must be an ISO calendar date, got {value!r}"
        ) from exc


def _normalise_sessions(values: Iterable[Any]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise NPortOwnershipBreadthGateError(
            "trading_sessions must be a collection, not one string"
        )
    try:
        sessions = {
            _normalise_date(value, field="trading session") for value in values
        }
    except TypeError as exc:
        raise NPortOwnershipBreadthGateError(
            "trading_sessions must be an iterable collection"
        ) from exc
    return sorted(sessions)


def _normalise_tickers(values: Iterable[str], *, field: str) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise NPortOwnershipBreadthGateError(
            f"{field} must be a collection, not one string"
        )
    try:
        iterator = iter(values)
    except TypeError as exc:
        raise NPortOwnershipBreadthGateError(
            f"{field} must be an iterable collection"
        ) from exc
    output: set[str] = set()
    for raw in iterator:
        ticker = str(raw or "").strip().upper()
        if not ticker:
            raise NPortOwnershipBreadthGateError(
                f"{field} contains a blank ticker"
            )
        output.add(ticker)
    return sorted(output)


def _json_copy(value: Any, *, field: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise NPortOwnershipBreadthGateError(
            f"{field} must be deterministic JSON: {exc}"
        ) from exc


def _dataset_identity(dataset: NPortDataset) -> dict[str, Any]:
    stamp = (
        id(dataset.holdings),
        len(dataset.holdings),
        id(dataset.reports),
        len(dataset.reports),
    )
    cacheable = True
    try:
        with _DATASET_IDENTITY_CACHE_LOCK:
            cached = _DATASET_IDENTITY_CACHE.get(dataset)
    except TypeError:  # Defensive support for an unhashable/slot-only subclass.
        cacheable = False
        cached = None
    if cached is not None and cached[0] == stamp:
        return deepcopy(cached[1])

    holding_records = dataset.holdings
    report_records = dataset.reports
    holdings = sorted(
        (
            {
                "accession": row.accession,
                "series_id": row.series_id,
                "ticker": row.ticker,
                "report_date": row.report_date.isoformat(),
                "filing_date": row.filing_date.isoformat(),
                "balance": row.balance,
                "currency_value": row.currency_value,
            }
            for row in holding_records
        ),
        key=lambda row: (
            row["series_id"],
            row["report_date"],
            row["filing_date"],
            row["accession"],
            row["ticker"],
            row["balance"],
            -1.0 if row["currency_value"] is None else row["currency_value"],
        ),
    )
    reports = sorted(
        (
            {
                "accession": row.accession,
                "series_id": row.series_id,
                "report_date": row.report_date.isoformat(),
                "filing_date": row.filing_date.isoformat(),
            }
            for row in report_records
        ),
        key=lambda row: (
            row["series_id"],
            row["report_date"],
            row["filing_date"],
            row["accession"],
        ),
    )
    identity = {
        "schema": "sec_nport_dataset_identity_v1",
        "holding_count": len(holdings),
        "report_count": len(reports),
        "holdings_hash": canonical_hash(holdings),
        "reports_hash": canonical_hash(reports),
    }
    current_stamp = (
        id(dataset.holdings),
        len(dataset.holdings),
        id(dataset.reports),
        len(dataset.reports),
    )
    if cacheable and current_stamp == stamp:
        try:
            with _DATASET_IDENTITY_CACHE_LOCK:
                _DATASET_IDENTITY_CACHE[dataset] = (stamp, deepcopy(identity))
        except TypeError:  # pragma: no cover - defensive subclass race.
            pass
    return deepcopy(identity)


def _source_identity_copy(
    source_identity: Mapping[str, Any] | str | None,
    dataset_identity: Mapping[str, Any],
) -> dict[str, Any]:
    if source_identity is None:
        return deepcopy(dict(dataset_identity))
    if isinstance(source_identity, str):
        text = source_identity.strip()
        if not text:
            raise NPortOwnershipBreadthGateError("source_identity cannot be blank")
        return {"identity": text}
    if not isinstance(source_identity, Mapping):
        raise NPortOwnershipBreadthGateError(
            "source_identity must be a mapping or non-empty string"
        )
    copied = _json_copy(dict(source_identity), field="source_identity")
    if not copied:
        raise NPortOwnershipBreadthGateError("source_identity cannot be empty")
    return copied


def _compact_decision(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: decision.get(key)
        for key in (
            "ticker",
            "action_date",
            "status",
            "reason",
            "fresh_entry_eligible",
            "breadth_score",
            "matched_series_count",
            "bought_from_zero_series_count",
            "sold_to_zero_series_count",
            "continuous_holder_series_count",
            "decision_hash",
        )
    }


def compute_ownership_breadth_decision(
    dataset: NPortDataset,
    action_date: Any,
    ticker: str,
    raw_prices: Mapping[Any, Any] | Any | None = None,
) -> dict[str, Any]:
    """Compute the fixed PIT ownership-breadth decision for one candidate.

    ``action_date`` is the session at which a fresh entry could execute.  The
    upstream helper enforces ``filing_date < action_date``.  ``raw_prices`` is
    accepted for caller compatibility but is deliberately not read: neither
    split factors nor aggregate share changes enter this breadth policy.
    """

    if not isinstance(dataset, NPortDataset):
        raise NPortOwnershipBreadthGateError("dataset must be an NPortDataset")
    action = _normalise_date(action_date, field="action_date")
    symbol = str(ticker or "").strip().upper()
    if not symbol:
        raise NPortOwnershipBreadthGateError("ticker is required")
    del raw_prices

    accumulation = compute_share_accumulation(
        dataset,
        action_date=action,
        ticker=symbol,
        # An explicit inert mapping prevents the upstream helper from falling
        # back to a mutable/effectful dataset price lookup.  Breadth depends
        # only on holder-presence zero crossings.
        raw_prices={},
        min_matched_series=MIN_MATCHED_SERIES,
    )
    matched = int(accumulation.get("matched_series_count") or 0)
    bought = int(accumulation.get("bought_from_zero_series_count") or 0)
    sold = int(accumulation.get("sold_to_zero_series_count") or 0)
    continuous = int(accumulation.get("continuous_holder_series_count") or 0)
    if min(matched, bought, sold, continuous) < 0 or bought + sold > matched:
        raise NPortOwnershipBreadthGateError(
            "upstream N-PORT helper emitted inconsistent breadth counts"
        )

    has_coverage = matched >= MIN_MATCHED_SERIES
    breadth_score = (bought - sold) / matched if has_coverage else None
    if breadth_score is None:
        status = "missing"
        reason = "fail_open_insufficient_matched_series"
    elif breadth_score < 0.0:
        status = "negative"
        reason = "exclude_fresh_candidate_negative_ownership_breadth"
    elif breadth_score > 0.0:
        status = "positive"
        reason = "eligible_positive_ownership_breadth"
    else:
        status = "neutral"
        reason = "fail_open_zero_ownership_breadth"
    fresh_entry_eligible = breadth_score is None or breadth_score >= 0.0

    payload: dict[str, Any] = {
        "schema": "sec_nport_ownership_breadth_decision_v1",
        "source": SOURCE,
        "rule_version": RULE_VERSION,
        "share_accumulation_rule_version": SHARE_ACCUMULATION_RULE_VERSION,
        "ticker": symbol,
        "action_date": action,
        "status": status,
        "breadth_bucket": "zero" if breadth_score == 0.0 else status,
        "reason": reason,
        "fresh_entry_eligible": fresh_entry_eligible,
        "candidate_eligible": fresh_entry_eligible,
        "eligible": fresh_entry_eligible,
        "has_minimum_coverage": has_coverage,
        "breadth_score": breadth_score,
        "score": breadth_score,
        "matched_series_count": matched,
        "bought_from_zero_series_count": bought,
        "sold_to_zero_series_count": sold,
        "continuous_holder_series_count": continuous,
        "report_pair_count": int(accumulation.get("report_pair_count") or 0),
        "previous_report_date_range": accumulation.get(
            "previous_report_date_range"
        ),
        "current_report_date_range": accumulation.get(
            "current_report_date_range"
        ),
        # Aggregate-share sign and split-price diagnostics are deliberately
        # outside this policy.  Once count coverage passes, normalise the
        # upstream reason so raw-price inputs cannot change breadth identity.
        "upstream_coverage_reason": (
            "minimum_matched_series_satisfied"
            if has_coverage
            else accumulation.get("reason")
        ),
        "filing_date_rule": "filing_date_strictly_before_action_date",
        "policy": deepcopy(_POLICY),
        **_default_off_flags(),
    }
    payload["decision_hash"] = canonical_hash(payload)
    return payload


def _calendar_fail_open_decision(ticker: str, signal_date: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "sec_nport_ownership_breadth_decision_v1",
        "source": SOURCE,
        "rule_version": RULE_VERSION,
        "share_accumulation_rule_version": SHARE_ACCUMULATION_RULE_VERSION,
        "ticker": ticker,
        "action_date": None,
        "signal_date": signal_date,
        "status": "missing",
        "breadth_bucket": "missing",
        "reason": "fail_open_no_next_trading_session",
        "fresh_entry_eligible": True,
        "candidate_eligible": True,
        "eligible": True,
        "has_minimum_coverage": False,
        "breadth_score": None,
        "score": None,
        "matched_series_count": 0,
        "bought_from_zero_series_count": 0,
        "sold_to_zero_series_count": 0,
        "continuous_holder_series_count": 0,
        "report_pair_count": 0,
        "previous_report_date_range": None,
        "current_report_date_range": None,
        "upstream_coverage_reason": "no_next_trading_session",
        "filing_date_rule": "filing_date_strictly_before_action_date",
        "policy": deepcopy(_POLICY),
        **_default_off_flags(),
    }
    payload["decision_hash"] = canonical_hash(payload)
    return payload


class NPortOwnershipBreadthEntryResolver:
    """BacktestEngine-compatible next-session fresh-entry resolver."""

    def __init__(
        self,
        base_tickers: Iterable[str],
        dataset: NPortDataset,
        trading_sessions: Iterable[Any],
        source_identity: Mapping[str, Any] | str | None,
    ) -> None:
        if not isinstance(dataset, NPortDataset):
            raise NPortOwnershipBreadthGateError("dataset must be an NPortDataset")
        self._base = frozenset(
            _normalise_tickers(base_tickers, field="base_tickers")
        )
        self._dataset = dataset
        # Tuple-copy plus a hash in metadata binds the caller's action clock.
        self._sessions = tuple(_normalise_sessions(trading_sessions))
        self._dataset_identity = _dataset_identity(dataset)
        self._source_identity = _source_identity_copy(
            source_identity, self._dataset_identity
        )
        self._source_identity_hash = canonical_hash(self._source_identity)
        self._source_hash = canonical_hash(
            {
                "source_identity": self._source_identity,
                "dataset_identity": self._dataset_identity,
            }
        )
        self._resolution_cache: dict[str, dict[str, Any]] = {}
        self._metadata = {
            "schema": "sec_nport_ownership_breadth_resolver_metadata_v1",
            "source": SOURCE,
            "source_hash": self._source_hash,
            "source_identity": deepcopy(self._source_identity),
            "source_identity_hash": self._source_identity_hash,
            "dataset_identity": deepcopy(self._dataset_identity),
            "rule_version": RULE_VERSION,
            "share_accumulation_rule_version": SHARE_ACCUMULATION_RULE_VERSION,
            "policy": deepcopy(_POLICY),
            "base_ticker_count": len(self._base),
            "base_membership_hash": membership_hash(self._base),
            "calendar_source": "immutable_caller_supplied_trading_sessions",
            "trading_sessions": list(self._sessions),
            "trading_session_count": len(self._sessions),
            "trading_sessions_hash": canonical_hash(list(self._sessions)),
            "trading_session_min": self._sessions[0] if self._sessions else None,
            "trading_session_max": self._sessions[-1] if self._sessions else None,
            "fill_semantics": (
                "resolve(signal_day) evaluates N-PORT filings strictly before "
                "the next caller-supplied trading-session fill"
            ),
            "unknown_coverage_policy": (
                "zero_or_missing_breadth_fails_open_to_base_universe"
            ),
            **_default_off_flags(),
        }

    @property
    def data_tickers(self) -> frozenset[str]:
        return self._base

    @property
    def metadata(self) -> dict[str, Any]:
        return deepcopy(self._metadata)

    def resolve(self, as_of: Any) -> dict[str, Any]:
        day = _normalise_date(as_of, field="as_of")
        cached = self._resolution_cache.get(day)
        if cached is not None:
            return deepcopy(cached)

        position = bisect_right(self._sessions, day)
        entry_session = (
            self._sessions[position] if position < len(self._sessions) else None
        )
        if entry_session is None:
            decisions = {
                ticker: _calendar_fail_open_decision(ticker, day)
                for ticker in sorted(self._base)
            }
        else:
            decisions = {
                ticker: compute_ownership_breadth_decision(
                    self._dataset,
                    entry_session,
                    ticker,
                )
                for ticker in sorted(self._base)
            }
        compact = {
            ticker: _compact_decision(decision)
            for ticker, decision in decisions.items()
        }
        excluded = sorted(
            ticker
            for ticker, decision in decisions.items()
            if not decision["fresh_entry_eligible"]
        )
        missing = sorted(
            ticker
            for ticker, decision in decisions.items()
            if decision["breadth_score"] is None
        )
        zero = sorted(
            ticker
            for ticker, decision in decisions.items()
            if decision["breadth_score"] == 0.0
        )
        covered = sorted(self._base - set(missing))
        eligible = sorted(self._base - set(excluded))
        if entry_session is None:
            coverage_status = "unknown_no_next_trading_session"
        elif not missing:
            coverage_status = "covered"
        elif covered:
            coverage_status = "partial"
        else:
            coverage_status = "uncovered"

        semantic = {
            "as_of": day,
            "entry_session": entry_session,
            "eligible": eligible,
            "excluded": excluded,
            "covered": covered,
            "missing": missing,
            "zero": zero,
            "ticker_decisions": compact,
            "coverage_status": coverage_status,
            "source_hash": self._source_hash,
            "source_identity_hash": self._source_identity_hash,
            "dataset_identity_hash": canonical_hash(self._dataset_identity),
            "trading_sessions_hash": self._metadata["trading_sessions_hash"],
            "rule_version": RULE_VERSION,
        }
        snapshot_hash = canonical_hash(
            {"record_type": "sec_nport_ownership_breadth_membership", **semantic}
        )
        record_hash = canonical_hash(
            {"record_type": "sec_nport_ownership_breadth_resolution", **semantic}
        )
        provenance = {
            "rule_version": RULE_VERSION,
            "share_accumulation_rule_version": SHARE_ACCUMULATION_RULE_VERSION,
            "source_identity": deepcopy(self._source_identity),
            "source_identity_hash": self._source_identity_hash,
            "dataset_identity": deepcopy(self._dataset_identity),
            "trading_sessions_hash": self._metadata["trading_sessions_hash"],
            "signal_date": day,
            "action_date": entry_session,
            "entry_session": entry_session,
            "excluded_tickers": excluded,
            "covered_tickers": covered,
            "missing_tickers": missing,
            "zero_breadth_tickers": zero,
            "coverage_status": coverage_status,
            "source_coverage_complete": entry_session is not None and not missing,
            "ticker_decisions": compact,
            "fill_semantics": self._metadata["fill_semantics"],
            "unknown_coverage_policy": self._metadata[
                "unknown_coverage_policy"
            ],
            **_default_off_flags(),
        }
        if excluded:
            reason = "next_session_negative_ownership_breadth_entry_exclusion"
        elif missing or entry_session is None:
            reason = f"fail_open_{coverage_status}"
        elif zero:
            reason = "fail_open_zero_breadth_no_exclusion"
        else:
            reason = "no_negative_ownership_breadth_exclusion"
        resolved = {
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
        self._resolution_cache[day] = deepcopy(resolved)
        return deepcopy(resolved)

    def __call__(self, as_of: Any) -> set[str]:
        return set(self.resolve(as_of)["tickers"])


def build_daily_ownership_breadth_snapshot(
    dataset: NPortDataset,
    as_of: Any,
    trading_sessions: Iterable[Any],
    candidate_tickers: Iterable[str],
    base_tickers: Iterable[str] | None = None,
    *,
    source_identity: Mapping[str, Any] | str | None = None,
    raw_prices: Mapping[Any, Any] | Any | None = None,
) -> dict[str, Any]:
    """Annotate daily fresh candidates with the shared default-off policy.

    ``raw_prices`` is accepted for caller symmetry.  Ownership breadth uses
    only zero-crossing counts, so it cannot affect eligibility or hashes.
    """

    del raw_prices  # Explicitly non-causal for the fixed breadth policy.
    candidates = _normalise_tickers(
        candidate_tickers, field="candidate_tickers"
    )
    base = _normalise_tickers(
        base_tickers if base_tickers is not None else candidates,
        field="base_tickers",
    )
    # Candidate annotations must remain visible even when a diagnostic caller
    # supplies a narrower base list; unioning here does not create an order.
    resolution_base = sorted(set(base) | set(candidates))
    resolver = NPortOwnershipBreadthEntryResolver(
        resolution_base,
        dataset,
        trading_sessions,
        source_identity,
    )
    resolved = resolver.resolve(as_of)
    provenance = resolved["provenance"]
    decisions = provenance["ticker_decisions"]
    candidate_rows = []
    for ticker in candidates:
        decision = deepcopy(decisions[ticker])
        eligible = bool(decision["fresh_entry_eligible"])
        candidate_rows.append(
            {
                **decision,
                "signal_date": resolved["as_of"],
                "entry_session": provenance["entry_session"],
                "decision": (
                    "observe_fresh_entry_eligible_default_off"
                    if eligible
                    else "observe_fresh_entry_exclusion_default_off"
                ),
                **_default_off_flags(),
            }
        )
    excluded_candidates = sorted(
        row["ticker"]
        for row in candidate_rows
        if not row["fresh_entry_eligible"]
    )
    fail_open_candidates = sorted(
        row["ticker"]
        for row in candidate_rows
        if row["breadth_score"] is None or row["breadth_score"] == 0.0
    )
    base_eligible = sorted(set(base) & set(resolved["tickers"]))
    base_excluded = sorted(set(base) - set(base_eligible))
    snapshot: dict[str, Any] = {
        "schema": "sec_nport_ownership_breadth_daily_snapshot_v1",
        "record_id": f"sec_nport_ownership_breadth:{resolved['as_of']}",
        "source": SOURCE,
        "source_hash": resolved["source_hash"],
        "source_identity": deepcopy(resolver.metadata["source_identity"]),
        "source_identity_hash": resolver.metadata["source_identity_hash"],
        "dataset_identity": deepcopy(resolver.metadata["dataset_identity"]),
        "rule_version": RULE_VERSION,
        "share_accumulation_rule_version": SHARE_ACCUMULATION_RULE_VERSION,
        "policy": deepcopy(_POLICY),
        "as_of": resolved["as_of"],
        "signal_date": resolved["as_of"],
        "action_date": provenance["entry_session"],
        "next_trading_session": provenance["entry_session"],
        "status": (
            "ok" if provenance["entry_session"] else "calendar_uncovered"
        ),
        "decision": "observe_fresh_entry_eligibility_default_off",
        "base_tickers": base,
        "base_ticker_count": len(base),
        "eligible_tickers": base_eligible,
        "eligible_ticker_count": len(base_eligible),
        "excluded_tickers_for_next_session": base_excluded,
        "excluded_tickers": base_excluded,
        "candidate_count": len(candidate_rows),
        "candidate_tickers": candidates,
        "excluded_candidate_tickers": excluded_candidates,
        "fail_open_candidate_tickers": fail_open_candidates,
        "candidates": candidate_rows,
        "coverage_status": provenance["coverage_status"],
        "covered_tickers": deepcopy(provenance["covered_tickers"]),
        "missing_tickers": deepcopy(provenance["missing_tickers"]),
        "zero_breadth_tickers": deepcopy(
            provenance["zero_breadth_tickers"]
        ),
        "trading_sessions_hash": provenance["trading_sessions_hash"],
        "resolver_snapshot_hash": resolved["snapshot_sha256"],
        "resolver_record_hash": resolved["record_hash"],
        "membership_hash": membership_hash(base_eligible),
        "order_intents": [],
        "orders": [],
        **_default_off_flags(),
    }
    snapshot["snapshot_hash"] = canonical_hash(snapshot)
    return snapshot


__all__ = [
    "MIN_MATCHED_SERIES",
    "NPortOwnershipBreadthEntryResolver",
    "NPortOwnershipBreadthGateError",
    "RULE_VERSION",
    "SOURCE",
    "TRADE_ENABLED",
    "build_daily_ownership_breadth_snapshot",
    "compute_ownership_breadth_decision",
]
