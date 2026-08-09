"""SEC same-issuer dual-class convergence paper sleeve (exp-20260718-007).

This module is a production-shareable, default-off paper helper.  Historical
replay and the daily adapter deliberately use the same state transition
function.  The official SEC ticker snapshot supplies only issuer identity; it
does not select securities.  All six preregistered identities are audited,
while price-provenance admission restricts economic decisions to the five-pair
``FROZEN_PAIRS`` set.  Identity, economic, and provenance-policy surfaces each
have a checked canonical hash.

The SEC ticker file is a current snapshot rather than effective-dated history.
Historical replay therefore remains conditional evidence, and the daily path
requires an exact ``sec_as_of == as_of`` observation.  No function in this
module emits an executable order.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

try:
    from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text
except ModuleNotFoundError:  # package-style import in focused tests
    from quant.data_paths import DATA_ROOT, atomic_write_json, atomic_write_text


RULE_VERSION = "sec_same_issuer_dual_class_robust_spread_v1"

FROZEN_IDENTITY_PAIRS: tuple[dict[str, Any], ...] = (
    {
        "pair_id": "GOOG/GOOGL",
        "left_ticker": "GOOG",
        "right_ticker": "GOOGL",
        "cik": 1652044,
        "data_provenance_admitted": False,
        "data_provenance_status": "excluded_mixed_provider_adjustment_vintage",
        "data_provenance_caveat": (
            "The two historical legs are not one provider/adjustment vintage; "
            "later hot data revised the GOOG leg by about 6bp."
        ),
        "reopen_condition": (
            "Both legs must be reacquired in one batch/vintage and the exp-local "
            "panel must be hash-bound."
        ),
    },
    {
        "pair_id": "FOX/FOXA", "left_ticker": "FOX", "right_ticker": "FOXA",
        "cik": 1754301, "data_provenance_admitted": True,
        "data_provenance_status": "admitted", "data_provenance_caveat": None,
        "reopen_condition": None,
    },
    {
        "pair_id": "NWS/NWSA", "left_ticker": "NWS", "right_ticker": "NWSA",
        "cik": 1564708, "data_provenance_admitted": True,
        "data_provenance_status": "admitted", "data_provenance_caveat": None,
        "reopen_condition": None,
    },
    {
        "pair_id": "HEI/HEI-A", "left_ticker": "HEI", "right_ticker": "HEI-A",
        "cik": 46619, "data_provenance_admitted": True,
        "data_provenance_status": "admitted", "data_provenance_caveat": None,
        "reopen_condition": None,
    },
    {
        "pair_id": "Z/ZG", "left_ticker": "Z", "right_ticker": "ZG",
        "cik": 1617640, "data_provenance_admitted": True,
        "data_provenance_status": "admitted_hash_bound_cold_panel",
        "data_provenance_caveat": (
            "Economic admission is conditional on the hash-bound exp-local cold panel."
        ),
        "reopen_condition": None,
    },
    {
        "pair_id": "UA/UAA", "left_ticker": "UA", "right_ticker": "UAA",
        "cik": 1336917, "data_provenance_admitted": True,
        "data_provenance_status": "admitted", "data_provenance_caveat": None,
        "reopen_condition": None,
    },
)
FROZEN_PAIRS: tuple[dict[str, Any], ...] = tuple(
    row for row in FROZEN_IDENTITY_PAIRS if row["data_provenance_admitted"]
)
FROZEN_IDENTITY_WHITELIST_SHA256 = (
    "b723fdf0124e79ebe8f4c8c1013bffd0390c35ee675164f1cbbb22e41f95ee95"
)
FROZEN_ECONOMIC_WHITELIST_SHA256 = (
    "e300580c3b6546eb9808d5f81ee5fbacc05c832ac0859676a97f9dc92f14ba56"
)
FROZEN_PROVENANCE_POLICY_SHA256 = (
    "411762b1c831d1ad3bd8b4bc320d0acb0cf311d650fe282240a689135c31e8a2"
)
# Backwards-compatible name now binds the economically eligible five-pair set.
FROZEN_WHITELIST_SHA256 = FROZEN_ECONOMIC_WHITELIST_SHA256
PAIR_BY_ID = {row["pair_id"]: row for row in FROZEN_IDENTITY_PAIRS}
FROZEN_TICKERS = tuple(
    ticker
    for row in FROZEN_PAIRS
    for ticker in (row["left_ticker"], row["right_ticker"])
)
FROZEN_IDENTITY_TICKERS = tuple(
    ticker
    for row in FROZEN_IDENTITY_PAIRS
    for ticker in (row["left_ticker"], row["right_ticker"])
)

ROBUST_LOOKBACK_SESSIONS = 120
MAD_SCALE = 1.4826
ENTRY_ROBUST_Z = 2.5
ENTRY_MIN_ABS_LOG_DEVIATION = math.log(1.01)
CONVERGENCE_ABS_LOG_DEVIATION = math.log(1.0025)
ADVERSE_LOG_SPREAD_STOP = math.log(1.03)
MAX_HOLD_SESSIONS = 10
SAME_PAIR_COOLDOWN_SESSIONS = 10
MAX_CONCURRENT_PAIRS = 1

INITIAL_CASH_USD = 10_000.0
LEG_NOTIONAL_CAP_USD = 5_000.0
MAX_ENTRY_DOLLAR_IMBALANCE = 0.05
ROUND_TRIP_COST_RATE_PER_LEG = 0.0045
HALF_TRADE_COST_RATE = ROUND_TRIP_COST_RATE_PER_LEG / 2.0
SHORT_CARRY_ANNUAL_RATE = 0.05

DEFAULT_DIR = DATA_ROOT / "paper_sleeves" / "sec_same_issuer_dual_class_spread"
DEFAULT_STATE_PATH = DEFAULT_DIR / "state.json"
DEFAULT_SNAPSHOT_LEDGER_PATH = DEFAULT_DIR / "daily_snapshots.jsonl"
DEFAULT_PAIR_LEDGER_PATH = DEFAULT_DIR / "pair_lifecycle.jsonl"


class FrozenIdentityError(ValueError):
    """Raised when the SEC payload does not prove every frozen identity."""


def _identity_projection(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "pair_id": row["pair_id"],
            "left_ticker": row["left_ticker"],
            "right_ticker": row["right_ticker"],
            "cik": int(row["cik"]),
        }
        for row in rows
    ]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _assert_whitelist_hash() -> None:
    checks = {
        "identity": (
            _identity_projection(FROZEN_IDENTITY_PAIRS),
            FROZEN_IDENTITY_WHITELIST_SHA256,
        ),
        "economic": (
            _identity_projection(FROZEN_PAIRS),
            FROZEN_ECONOMIC_WHITELIST_SHA256,
        ),
        "provenance_policy": (list(FROZEN_IDENTITY_PAIRS), FROZEN_PROVENANCE_POLICY_SHA256),
    }
    for label, (value, expected) in checks.items():
        actual = hashlib.sha256(_canonical_bytes(value)).hexdigest()
        if actual != expected:
            raise RuntimeError(
                f"frozen dual-class {label} hash mismatch: expected {expected}, got {actual}"
            )


_assert_whitelist_hash()


def production_impact() -> dict[str, Any]:
    """Fail-closed production boundary shared by every returned snapshot."""
    return {
        "trade_enabled": False,
        "enabled": False,
        "adapter_status": "shared_default_off_paper_helper",
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_core": False,
        "live_ready": False,
        "effective_dated_sec_identity_verified": False,
        "broker_locate_verified": False,
        "broker_size_verified": False,
    }


def execution_sizing_contract() -> dict[str, Any]:
    """Declare why the measured paper size is not an executable notional."""
    return {
        "rule_version": RULE_VERSION,
        "paper_notional_is_evidence_only": True,
        "paper_account_cash_usd": INITIAL_CASH_USD,
        "paper_leg_notional_cap_usd": LEG_NOTIONAL_CAP_USD,
        "maximum_entry_dollar_imbalance": MAX_ENTRY_DOLLAR_IMBALANCE,
        "experiment_notional_usd": None,
        "whole_shares_required": True,
        "short_proceeds_reusable": False,
        "entry_marked_gross_limit_usd": INITIAL_CASH_USD,
        "cash_must_remain_nonnegative": True,
        "maximum_open_or_pending_pairs": MAX_CONCURRENT_PAIRS,
        "live_ready": False,
        "trade_enabled": False,
        "fail_closed": True,
        "missing_live_requirements": [
            "effective_dated_sec_identity",
            "broker_locate",
            "broker_size",
        ],
    }


def selection_contract() -> dict[str, Any]:
    return {
        "maximum_open_or_pending_pairs": MAX_CONCURRENT_PAIRS,
        "free_close_ranking": ["descending_abs_robust_z", "ascending_pair_id"],
        "pairs_scheduled_per_free_close": 1,
        "occupied_signal_action": "discard_without_queue",
        "entry_timing": "strict_next_common_session_open",
    }


def cooldown_contract() -> dict[str, Any]:
    return {
        "scope": "same_pair",
        "anchor": "exit_common_session",
        "complete_common_sessions_blocked_after_exit": SAME_PAIR_COOLDOWN_SESSIONS,
        "eligible_session_offset_after_exit": SAME_PAIR_COOLDOWN_SESSIONS + 1,
    }


def price_provenance_contract() -> dict[str, Any]:
    """Serialize the outcome-blind six-identity/five-economic admission audit."""
    excluded = [
        dict(row) for row in FROZEN_IDENTITY_PAIRS
        if not row["data_provenance_admitted"]
    ]
    return {
        "identity_candidate_count": len(FROZEN_IDENTITY_PAIRS),
        "economic_admitted_pair_count": len(FROZEN_PAIRS),
        "identity_candidate_pair_ids": [row["pair_id"] for row in FROZEN_IDENTITY_PAIRS],
        "economic_admitted_pair_ids": [row["pair_id"] for row in FROZEN_PAIRS],
        "identity_whitelist_sha256": FROZEN_IDENTITY_WHITELIST_SHA256,
        "economic_whitelist_sha256": FROZEN_ECONOMIC_WHITELIST_SHA256,
        "provenance_policy_sha256": FROZEN_PROVENANCE_POLICY_SHA256,
        "excluded_identity_candidates": excluded,
        "excluded_pair_ids": [row["pair_id"] for row in excluded],
        "hot_data_substitution_allowed": False,
        "z_zg_cold_panel_caveat": {
            "pair_id": "Z/ZG",
            "data_provenance_admitted": True,
            "panel_requirement": "hash_bound_exp_local_cold_panel",
            "hot_data_substitution_allowed": False,
        },
    }


def _date10(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _mapping_value(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        result = _finite_number(row.get(key))
        if result is not None:
            return result
    return None


def _sec_payload(payload: Any) -> tuple[Any, bytes]:
    if isinstance(payload, Path):
        raw = payload.read_bytes()
        return json.loads(raw.decode("utf-8-sig")), raw
    if isinstance(payload, bytes):
        return json.loads(payload.decode("utf-8-sig")), payload
    if isinstance(payload, str):
        stripped = payload.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            raw = payload.encode("utf-8")
            return json.loads(payload), raw
        path = Path(payload)
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8-sig")), raw
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return payload, raw


def _sec_rows(obj: Any) -> list[Mapping[str, Any]]:
    if isinstance(obj, list):
        return [row for row in obj if isinstance(row, Mapping)]
    if not isinstance(obj, Mapping):
        return []
    # SEC's alternate exchange file is {"fields": [...], "data": [[...], ...]}.
    fields = obj.get("fields")
    data = obj.get("data")
    if isinstance(fields, list) and isinstance(data, list):
        return [
            dict(zip((str(field) for field in fields), row))
            for row in data
            if isinstance(row, list)
        ]
    if isinstance(obj.get("rows"), list):
        return [row for row in obj["rows"] if isinstance(row, Mapping)]
    if "ticker" in obj and ("cik_str" in obj or "cik" in obj):
        return [obj]
    # The canonical company_tickers.json is an object keyed by row number.
    return [row for row in obj.values() if isinstance(row, Mapping)]


def parse_sec_company_tickers(payload: Any) -> dict[str, Any]:
    """Parse raw SEC ticker JSON into explicit one-CIK-to-many mappings.

    The source hash records the exact bytes for a path/bytes/string input and a
    canonical JSON representation for an already-decoded object.
    """
    obj, raw = _sec_payload(payload)
    rows = _sec_rows(obj)
    cik_to_tickers: dict[int, set[str]] = {}
    ticker_to_cik: dict[str, int] = {}
    duplicate_rows = 0
    rejected_rows = 0
    for row in rows:
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        raw_cik = row.get("cik_str", row.get("cik"))
        try:
            cik = int(str(raw_cik).lstrip("0") or "0")
        except (TypeError, ValueError):
            rejected_rows += 1
            continue
        if not ticker or cik <= 0:
            rejected_rows += 1
            continue
        previous = ticker_to_cik.get(ticker)
        if previous is not None and previous != cik:
            raise FrozenIdentityError(
                f"SEC ticker {ticker} maps to multiple CIKs: {previous}, {cik}"
            )
        if previous == cik:
            duplicate_rows += 1
        ticker_to_cik[ticker] = cik
        cik_to_tickers.setdefault(cik, set()).add(ticker)
    return {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_row_count": len(rows),
        "parsed_ticker_count": len(ticker_to_cik),
        "parsed_cik_count": len(cik_to_tickers),
        "duplicate_rows": duplicate_rows,
        "rejected_rows": rejected_rows,
        "ticker_to_cik": dict(sorted(ticker_to_cik.items())),
        "cik_to_tickers": {
            str(cik): sorted(tickers) for cik, tickers in sorted(cik_to_tickers.items())
        },
    }


def assert_frozen_sec_identities(payload: Any) -> dict[str, Any]:
    """Assert all preregistered ticker/CIK identities without auto-admission."""
    _assert_whitelist_hash()
    parsed = parse_sec_company_tickers(payload)
    ticker_to_cik = parsed["ticker_to_cik"]
    missing: list[str] = []
    mismatched: list[dict[str, Any]] = []
    ignored_same_cik: dict[str, list[str]] = {}
    identity_tickers = set(FROZEN_IDENTITY_TICKERS)
    for pair in FROZEN_IDENTITY_PAIRS:
        cik = int(pair["cik"])
        for ticker in (pair["left_ticker"], pair["right_ticker"]):
            actual = ticker_to_cik.get(ticker)
            if actual is None:
                missing.append(ticker)
            elif actual != cik:
                mismatched.append(
                    {"ticker": ticker, "expected_cik": cik, "actual_cik": actual}
                )
        extras = [
            ticker
            for ticker in parsed["cik_to_tickers"].get(str(cik), [])
            if ticker not in identity_tickers
        ]
        if extras:
            ignored_same_cik[pair["pair_id"]] = extras
    if missing or mismatched:
        raise FrozenIdentityError(
            "frozen SEC dual-class identities failed: "
            f"missing={sorted(missing)}, mismatched={mismatched}"
        )
    return {
        "status": "verified",
        "source_sha256": parsed["source_sha256"],
        "whitelist_sha256": FROZEN_ECONOMIC_WHITELIST_SHA256,
        "identity_whitelist_sha256": FROZEN_IDENTITY_WHITELIST_SHA256,
        "economic_whitelist_sha256": FROZEN_ECONOMIC_WHITELIST_SHA256,
        "provenance_policy_sha256": FROZEN_PROVENANCE_POLICY_SHA256,
        "identity_candidates": [dict(row) for row in FROZEN_IDENTITY_PAIRS],
        "identity_candidate_count": len(FROZEN_IDENTITY_PAIRS),
        "admitted_pairs": [dict(row) for row in FROZEN_PAIRS],
        "admitted_pair_count": len(FROZEN_PAIRS),
        "excluded_identity_candidates": [
            dict(row) for row in FROZEN_IDENTITY_PAIRS
            if not row["data_provenance_admitted"]
        ],
        "ignored_same_cik_tickers": ignored_same_cik,
        "auto_admission_enabled": False,
        "parsed_cik_count": parsed["parsed_cik_count"],
        "parsed_ticker_count": parsed["parsed_ticker_count"],
    }


def _normalise_prices(payloads: Mapping[str, Any]) -> dict[str, dict[str, dict[str, float]]]:
    result: dict[str, dict[str, dict[str, float]]] = {}
    for ticker in FROZEN_IDENTITY_TICKERS:
        payload = (payloads or {}).get(ticker)
        if payload is None:
            # Be forgiving about caller key case, but never ticker identity.
            payload = next(
                (value for key, value in (payloads or {}).items() if str(key).upper() == ticker),
                None,
            )
        if hasattr(payload, "iterrows"):
            candidates = list(payload.iterrows())
        elif isinstance(payload, Mapping):
            candidates = (
                [(None, row) for row in payload["rows"]]
                if isinstance(payload.get("rows"), list)
                else list(payload.items())
            )
        elif isinstance(payload, list):
            candidates = [(None, row) for row in payload]
        else:
            candidates = []
        bars: dict[str, dict[str, float]] = {}
        for fallback, raw in candidates:
            if not isinstance(raw, Mapping) and hasattr(raw, "to_dict"):
                raw = raw.to_dict()
            if isinstance(raw, Mapping):
                day = next(
                    (
                        _date10(raw.get(key))
                        for key in ("date", "Date", "datetime", "Datetime", "timestamp")
                        if _date10(raw.get(key))
                    ),
                    _date10(fallback),
                )
                open_price = _mapping_value(raw, "open", "Open", "price", "close", "Close")
                close_price = _mapping_value(raw, "close", "Close", "price", "open", "Open")
            else:
                day = _date10(fallback)
                open_price = close_price = _finite_number(raw)
            if day and open_price and close_price and open_price > 0 and close_price > 0:
                bars[day] = {"open": float(open_price), "close": float(close_price)}
        result[ticker] = bars
    return result


def _pair_common_dates(
    pair: Mapping[str, Any],
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> list[str]:
    return sorted(
        set(prices.get(str(pair["left_ticker"]), {}))
        & set(prices.get(str(pair["right_ticker"]), {}))
    )


def _account_sessions(
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> list[str]:
    sessions: set[str] = set()
    for pair in FROZEN_PAIRS:
        sessions.update(_pair_common_dates(pair, prices))
    return sorted(sessions)


def _pair_signal(
    pair: Mapping[str, Any],
    as_of: str,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any]:
    pair_id = str(pair["pair_id"])
    left = str(pair["left_ticker"])
    right = str(pair["right_ticker"])
    common = _pair_common_dates(pair, prices)
    base = {
        "pair_id": pair_id,
        "cik": int(pair["cik"]),
        "left_ticker": left,
        "right_ticker": right,
        "signal_date": as_of,
        "rule_version": RULE_VERSION,
        "prior_observation_count": 0,
        "data_provenance_admitted": bool(pair["data_provenance_admitted"]),
        "data_provenance_status": pair["data_provenance_status"],
        "data_provenance_caveat": pair["data_provenance_caveat"],
        "data_provenance_reopen_condition": pair["reopen_condition"],
        "statistical_entry_threshold_pass": False,
        "eligible": False,
        "trade_enabled": False,
    }
    if as_of not in common:
        return {**base, "reason": "missing_exact_common_close"}
    prior_dates = [day for day in common if day < as_of]
    if len(prior_dates) < ROBUST_LOOKBACK_SESSIONS:
        return {
            **base,
            "reason": "insufficient_strictly_prior_common_sessions",
            "prior_observation_count": len(prior_dates),
        }
    prior_dates = prior_dates[-ROBUST_LOOKBACK_SESSIONS:]
    prior_spreads = [
        math.log(prices[left][day]["close"] / prices[right][day]["close"])
        for day in prior_dates
    ]
    anchor = median(prior_spreads)
    mad = median([abs(value - anchor) for value in prior_spreads])
    scaled_mad = MAD_SCALE * mad
    current = math.log(prices[left][as_of]["close"] / prices[right][as_of]["close"])
    deviation = current - anchor
    robust_z = deviation / scaled_mad if scaled_mad > 1e-12 else None
    threshold_pass = (
        robust_z is not None
        and abs(robust_z) >= ENTRY_ROBUST_Z
        and abs(deviation) >= ENTRY_MIN_ABS_LOG_DEVIATION
    )
    if deviation > 0:
        long_ticker, short_ticker, direction = right, left, 1
    else:
        long_ticker, short_ticker, direction = left, right, -1
    return {
        **base,
        "reason": (
            "data_provenance_not_admitted"
            if not pair["data_provenance_admitted"]
            else None if threshold_pass
            else "robust_spread_entry_threshold_not_met"
        ),
        "statistical_entry_threshold_pass": threshold_pass,
        "eligible": bool(threshold_pass and pair["data_provenance_admitted"]),
        "prior_observation_count": len(prior_dates),
        "prior_first_date": prior_dates[0],
        "prior_last_date": prior_dates[-1],
        "frozen_anchor_log_ratio": anchor,
        "frozen_raw_mad": mad,
        "frozen_scaled_mad": scaled_mad,
        "signal_log_ratio": current,
        "signal_log_deviation": deviation,
        "signal_abs_premium_deviation": math.exp(abs(deviation)) - 1.0,
        "signal_robust_z": robust_z,
        "signal_direction": direction,
        "long_ticker": long_ticker,
        "short_ticker": short_ticker,
    }


def compute_strict_prior_pair_signal(
    pair_id: str,
    as_of: Any,
    ohlcv_by_ticker: Mapping[str, Any],
) -> dict[str, Any]:
    """Public no-lookahead signal diagnostic for one frozen pair."""
    pair = PAIR_BY_ID.get(str(pair_id).upper())
    if pair is None:
        raise KeyError(f"pair is not in the frozen whitelist: {pair_id}")
    day = _date10(as_of)
    if not day:
        raise ValueError(f"invalid as_of: {as_of!r}")
    return _pair_signal(pair, day, _normalise_prices(ohlcv_by_ticker))


def _imbalance(long_notional: float, short_notional: float) -> float:
    denominator = max(long_notional, short_notional)
    return abs(long_notional - short_notional) / denominator if denominator > 0 else 1.0


def size_whole_share_pair_entry(
    *,
    long_open: float,
    short_open: float,
    available_cash_usd: float,
) -> dict[str, Any]:
    """Maximise balanced whole-share exposure under the frozen cash envelope."""
    long_px = _finite_number(long_open)
    short_px = _finite_number(short_open)
    cash = _finite_number(available_cash_usd)
    if not long_px or not short_px or not cash or min(long_px, short_px, cash) <= 0:
        return {"status": "rejected", "reason": "invalid_entry_price_or_cash"}
    max_long = int(LEG_NOTIONAL_CAP_USD // long_px)
    max_short = int(LEG_NOTIONAL_CAP_USD // short_px)
    if max_long < 1 or max_short < 1:
        return {"status": "rejected", "reason": "one_share_exceeds_leg_cap"}

    # For each long quantity only the short quantities nearest equal dollars,
    # the cap, or the cash boundary can be optimal.  This is deterministic and
    # avoids a quadratic search for low-priced shares.
    best: tuple[tuple[float, float, float, int, int], dict[str, Any]] | None = None
    gross_cash_capacity = cash / (1.0 + HALF_TRADE_COST_RATE)
    for long_shares in range(1, max_long + 1):
        long_notional = long_shares * long_px
        max_short_cash = int(max(0.0, gross_cash_capacity - long_notional) // short_px)
        max_feasible_short = min(max_short, max_short_cash)
        if max_feasible_short < 1:
            continue
        target = long_notional / short_px
        short_candidates = {
            1,
            max_feasible_short,
            min(max_feasible_short, max(1, int(math.floor(target)))),
            min(max_feasible_short, max(1, int(math.ceil(target)))),
        }
        for short_shares in short_candidates:
            short_notional = short_shares * short_px
            entry_cost = HALF_TRADE_COST_RATE * (long_notional + short_notional)
            required = long_notional + short_notional + entry_cost
            imbalance = _imbalance(long_notional, short_notional)
            if required > cash + 1e-9 or imbalance > MAX_ENTRY_DOLLAR_IMBALANCE + 1e-12:
                continue
            values = {
                "status": "fundable",
                "reason": None,
                "long_shares": long_shares,
                "short_shares": short_shares,
                "long_entry_notional_usd": long_notional,
                "short_entry_notional_usd": short_notional,
                "short_collateral_usd": short_notional,
                "entry_trade_cost_usd": entry_cost,
                "entry_required_cash_usd": required,
                "entry_dollar_imbalance": imbalance,
                "cash_remaining_after_entry_usd": cash - required,
                "short_proceeds_reused_usd": 0.0,
            }
            score = (
                min(long_notional, short_notional),
                long_notional + short_notional,
                -imbalance,
                long_shares,
                short_shares,
            )
            if best is None or score > best[0]:
                best = (score, values)
    if best is None:
        return {
            "status": "rejected",
            "reason": "whole_share_cash_or_imbalance_constraint",
            "max_entry_dollar_imbalance": MAX_ENTRY_DOLLAR_IMBALANCE,
        }
    return best[1]


def empty_sec_same_issuer_dual_class_spread_state() -> dict[str, Any]:
    return {
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "initial_cash_usd": INITIAL_CASH_USD,
        "cash_usd": INITIAL_CASH_USD,
        "pending_pair": None,
        "open_pair": None,
        "closed_pairs": [],
        "last_entry_date_by_pair": {},
        "last_exit_date_by_pair": {},
        "processed_dates": [],
        "last_processed_as_of": None,
        "equity_curve": [],
        "audit": {},
    }


def _copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _bump(state: dict[str, Any], key: str, amount: int = 1) -> None:
    audit = state.setdefault("audit", {})
    audit[key] = int(audit.get(key) or 0) + amount


def _cooldown_allows(
    pair: Mapping[str, Any],
    day: str,
    prior_exit_date: str | None,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> bool:
    if not prior_exit_date:
        return True
    common = _pair_common_dates(pair, prices)
    positions = {value: index for index, value in enumerate(common)}
    if prior_exit_date not in positions or day not in positions:
        return False
    # The ten sessions *after* the exit are complete cooldown sessions.  A pair
    # becomes eligible again only on the following (eleventh) common session.
    return positions[day] - positions[prior_exit_date] > SAME_PAIR_COOLDOWN_SESSIONS


def _entry_from_pending(
    pending: Mapping[str, Any],
    day: str,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
    cash: float,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    pair = PAIR_BY_ID[str(pending["pair_id"])]
    if not pair["data_provenance_admitted"]:
        return None, {
            "status": "skipped",
            "reason": "pending_pair_data_provenance_not_admitted",
        }
    common = _pair_common_dates(pair, prices)
    observed_after_signal = [
        value for value in common if str(pending["signal_date"]) < value <= day
    ]
    if not observed_after_signal:
        return None, {"status": "waiting"}
    expected = observed_after_signal[0]
    if expected != day:
        return None, {
            "status": "skipped",
            "reason": "missed_exact_next_common_session_open",
            "expected_entry_date": expected,
        }
    long_ticker = str(pending["long_ticker"])
    short_ticker = str(pending["short_ticker"])
    long_open = prices[long_ticker][day]["open"]
    short_open = prices[short_ticker][day]["open"]
    sizing = size_whole_share_pair_entry(
        long_open=long_open,
        short_open=short_open,
        available_cash_usd=cash,
    )
    if sizing["status"] != "fundable":
        return None, {"status": "skipped", **sizing}
    left = str(pair["left_ticker"])
    right = str(pair["right_ticker"])
    entry_log_ratio = math.log(prices[left][day]["open"] / prices[right][day]["open"])
    funded = {
        **dict(pending),
        **sizing,
        "entry_date": day,
        "long_entry_open": long_open,
        "short_entry_open": short_open,
        "entry_log_ratio": entry_log_ratio,
        "entry_log_deviation_from_frozen_anchor": (
            entry_log_ratio - float(pending["frozen_anchor_log_ratio"])
        ),
        "reserved_capital_usd": (
            float(sizing["long_entry_notional_usd"])
            + float(sizing["short_collateral_usd"])
        ),
        "entry_marked_gross_usd": (
            float(sizing["long_entry_notional_usd"])
            + float(sizing["short_entry_notional_usd"])
        ),
        "entry_marked_gross_lte_account_cap": (
            float(sizing["long_entry_notional_usd"])
            + float(sizing["short_entry_notional_usd"])
            <= INITIAL_CASH_USD + 1e-9
        ),
        "cash_nonnegative_after_entry": (
            float(sizing["cash_remaining_after_entry_usd"]) >= -1e-9
        ),
        "open_or_pending_count_after_entry": 1,
        "trade_enabled": False,
    }
    return funded, {"status": "entered"}


def _inclusive_carry(position: Mapping[str, Any], day: str) -> tuple[int, float]:
    calendar_days = (
        date.fromisoformat(day) - date.fromisoformat(str(position["entry_date"]))
    ).days + 1
    carry = (
        float(position["short_entry_notional_usd"])
        * SHORT_CARRY_ANNUAL_RATE
        * calendar_days
        / 365.0
    )
    return calendar_days, carry


def _mark_open_pair(
    state: Mapping[str, Any],
    day: str,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any]:
    cash = float(state.get("cash_usd") or 0.0)
    position = state.get("open_pair")
    if not isinstance(position, Mapping):
        return {
            "status": "ok",
            "as_of": day,
            "cash_usd": cash,
            "equity_usd": cash,
            "gross_exposure_usd": 0.0,
            "accrued_short_carry_usd": 0.0,
        }
    long_ticker = str(position["long_ticker"])
    short_ticker = str(position["short_ticker"])
    long_bar = prices.get(long_ticker, {}).get(day)
    short_bar = prices.get(short_ticker, {}).get(day)
    if not long_bar or not short_bar:
        return {
            "status": "missing_exact_open_pair_close",
            "as_of": day,
            "long_ticker": long_ticker,
            "short_ticker": short_ticker,
        }
    long_value = int(position["long_shares"]) * long_bar["close"]
    short_value = int(position["short_shares"]) * short_bar["close"]
    short_unrealized = float(position["short_entry_notional_usd"]) - short_value
    _, carry = _inclusive_carry(position, day)
    equity = (
        cash
        + long_value
        + float(position["short_collateral_usd"])
        + short_unrealized
        - carry
    )
    return {
        "status": "ok",
        "as_of": day,
        "cash_usd": cash,
        "long_market_value_usd": long_value,
        "short_market_value_usd": short_value,
        "short_unrealized_pnl_usd": short_unrealized,
        "accrued_short_carry_usd": carry,
        "equity_usd": equity,
        "gross_exposure_usd": long_value + short_value,
    }


def _exit_reason(
    position: Mapping[str, Any],
    day: str,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> tuple[str | None, dict[str, Any]]:
    pair = PAIR_BY_ID[str(position["pair_id"])]
    common = _pair_common_dates(pair, prices)
    if day not in common:
        return None, {"status": "not_common_session"}
    left = str(pair["left_ticker"])
    right = str(pair["right_ticker"])
    current = math.log(prices[left][day]["close"] / prices[right][day]["close"])
    anchor = float(position["frozen_anchor_log_ratio"])
    direction = int(position["signal_direction"])
    adverse_from_entry = direction * (current - float(position["entry_log_ratio"]))
    held_dates = [
        value for value in common if str(position["entry_date"]) <= value <= day
    ]
    held = len(held_dates)
    detail = {
        "exit_log_ratio": current,
        "exit_log_deviation_from_frozen_anchor": current - anchor,
        "adverse_log_spread_move_from_entry": adverse_from_entry,
        "held_sessions": held,
    }
    if abs(current - anchor) <= CONVERGENCE_ABS_LOG_DEVIATION:
        return "spread_converged", detail
    if adverse_from_entry >= ADVERSE_LOG_SPREAD_STOP:
        return "adverse_spread_stop", detail
    if held >= MAX_HOLD_SESSIONS:
        return "max_hold_timeout", detail
    return None, detail


def _close_pair(
    position: Mapping[str, Any],
    day: str,
    reason: str,
    exit_detail: Mapping[str, Any],
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any]:
    long_ticker = str(position["long_ticker"])
    short_ticker = str(position["short_ticker"])
    long_exit = prices[long_ticker][day]["close"]
    short_exit = prices[short_ticker][day]["close"]
    long_exit_value = int(position["long_shares"]) * long_exit
    short_exit_value = int(position["short_shares"]) * short_exit
    long_pnl = long_exit_value - float(position["long_entry_notional_usd"])
    short_pnl = float(position["short_entry_notional_usd"]) - short_exit_value
    gross_pnl = long_pnl + short_pnl
    exit_cost = HALF_TRADE_COST_RATE * (long_exit_value + short_exit_value)
    calendar_days, carry = _inclusive_carry(position, day)
    entry_cost = float(position["entry_trade_cost_usd"])
    net_pnl = gross_pnl - entry_cost - exit_cost - carry
    return {
        **dict(position),
        **dict(exit_detail),
        "exit_date": day,
        "exit_reason": reason,
        "long_exit_close": long_exit,
        "short_exit_close": short_exit,
        "long_exit_value_usd": long_exit_value,
        "short_exit_value_usd": short_exit_value,
        "long_gross_pnl_usd": long_pnl,
        "short_gross_pnl_usd": short_pnl,
        "gross_pnl_usd": gross_pnl,
        "exit_trade_cost_usd": exit_cost,
        "total_trade_cost_usd": entry_cost + exit_cost,
        "short_carry_calendar_days_inclusive": calendar_days,
        "short_carry_usd": carry,
        "net_pnl_usd": net_pnl,
        "return_on_reserved_capital": net_pnl / float(position["reserved_capital_usd"]),
        "trade_enabled": False,
    }


def _advance_day(
    state: dict[str, Any],
    day: str,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
    *,
    allow_new_signals: bool,
) -> dict[str, Any]:
    """Shared replay/daily state transition for one exact market date."""
    events: list[dict[str, Any]] = []
    cash = float(state.get("cash_usd") or 0.0)

    pending = state.get("pending_pair")
    if isinstance(pending, Mapping):
        funded, entry_status = _entry_from_pending(pending, day, prices, cash)
        if entry_status["status"] == "entered" and funded is not None:
            cash -= float(funded["entry_required_cash_usd"])
            if cash < -1e-7:
                raise RuntimeError("entry cash invariant violated")
            state["open_pair"] = funded
            state["pending_pair"] = None
            state.setdefault("last_entry_date_by_pair", {})[str(funded["pair_id"])] = day
            _bump(state, "entries_funded")
            state.setdefault("audit", {})["maximum_entry_marked_gross_usd"] = max(
                float((state.get("audit") or {}).get("maximum_entry_marked_gross_usd") or 0.0),
                float(funded["entry_marked_gross_usd"]),
            )
            events.append(
                {
                    **funded,
                    "event": "entered",
                    "event_id": f"{RULE_VERSION}:{funded['pair_id']}:{funded['signal_date']}:entry",
                }
            )
        elif entry_status["status"] == "skipped":
            state["pending_pair"] = None
            _bump(state, "entries_skipped")
            events.append(
                {
                    **dict(pending),
                    **entry_status,
                    "event": "entry_skipped",
                    "event_id": f"{RULE_VERSION}:{pending['pair_id']}:{pending['signal_date']}:entry_skip",
                    "trade_enabled": False,
                }
            )

    state["cash_usd"] = cash
    exited: dict[str, Any] | None = None
    position = state.get("open_pair")
    if isinstance(position, Mapping):
        reason, exit_detail = _exit_reason(position, day, prices)
        if reason:
            exited = _close_pair(position, day, reason, exit_detail, prices)
            cash += (
                float(position["reserved_capital_usd"])
                + float(exited["gross_pnl_usd"])
                - float(exited["exit_trade_cost_usd"])
                - float(exited["short_carry_usd"])
            )
            state["cash_usd"] = cash
            state["open_pair"] = None
            state.setdefault("closed_pairs", []).append(exited)
            state.setdefault("last_exit_date_by_pair", {})[str(position["pair_id"])] = day
            _bump(state, "pairs_closed")
            _bump(state, f"exit_{reason}")
            events.append(
                {
                    **exited,
                    "event": "exited",
                    "event_id": f"{RULE_VERSION}:{position['pair_id']}:{position['signal_date']}:exit",
                }
            )

    signal_rows: list[dict[str, Any]] = []
    qualifying: list[dict[str, Any]] = []
    free_at_signal_close = (
        state.get("open_pair") is None and state.get("pending_pair") is None
    )
    if allow_new_signals:
        for pair in FROZEN_IDENTITY_PAIRS:
            row = _pair_signal(pair, day, prices)
            if (
                row.get("statistical_entry_threshold_pass")
                and not row.get("data_provenance_admitted")
            ):
                _bump(state, "data_provenance_excluded_threshold_signals")
            if row.get("eligible"):
                _bump(state, "raw_threshold_signals")
                if not free_at_signal_close:
                    row["same_pair_cooldown_pass"] = None
                    row["disposition"] = "discarded_open_or_pending"
                    _bump(state, "signals_discarded_open_or_pending")
                else:
                    previous_exit = (state.get("last_exit_date_by_pair") or {}).get(
                        pair["pair_id"]
                    )
                    cooldown_ok = _cooldown_allows(pair, day, previous_exit, prices)
                    row["same_pair_cooldown_pass"] = cooldown_ok
                    if cooldown_ok:
                        row["disposition"] = "eligible_for_arbitration"
                        qualifying.append(row)
                        _bump(state, "signals_generated")
                    else:
                        row["disposition"] = "blocked_post_exit_cooldown"
                        _bump(state, "signals_blocked_cooldown")
            signal_rows.append(row)
        qualifying.sort(key=lambda row: (-abs(float(row["signal_robust_z"])), row["pair_id"]))
        if free_at_signal_close and qualifying:
            _bump(state, "free_close_arbitration_runs")
            _bump(state, "free_close_arbitration_candidates", len(qualifying))
            if len(qualifying) > 1:
                _bump(state, "multi_pair_arbitration_runs")

    selected: dict[str, Any] | None = None
    if (
        allow_new_signals
        and qualifying
        and state.get("open_pair") is None
        and state.get("pending_pair") is None
    ):
        selected = {
            **qualifying[0],
            "pending_entry_rule": "strict_next_common_session_open",
            "target_price": None,
            "target_price_role": "not_applicable_pair_spread_exit",
            "trade_enabled": False,
        }
        state["pending_pair"] = selected
        _bump(state, "signals_selected")
        _bump(state, "free_close_arbitration_selections")
        events.append(
            {
                **selected,
                "event": "signal",
                "event_id": f"{RULE_VERSION}:{selected['pair_id']}:{day}:signal",
            }
        )
    state["cash_usd"] = cash
    state["trade_enabled"] = False
    state["last_processed_as_of"] = day
    if day not in state.setdefault("processed_dates", []):
        state["processed_dates"].append(day)
    open_or_pending = int(isinstance(state.get("open_pair"), Mapping)) + int(
        isinstance(state.get("pending_pair"), Mapping)
    )
    if open_or_pending > MAX_CONCURRENT_PAIRS:
        raise RuntimeError("open+pending concurrency invariant violated")
    if cash < -1e-7:
        raise RuntimeError("cash nonnegative invariant violated")
    state.setdefault("audit", {})["maximum_open_or_pending_count"] = max(
        int((state.get("audit") or {}).get("maximum_open_or_pending_count") or 0),
        open_or_pending,
    )
    mark = _mark_open_pair(state, day, prices)
    if mark.get("status") == "ok":
        state.setdefault("equity_curve", []).append(dict(mark))
    elif isinstance(state.get("open_pair"), Mapping):
        _bump(state, "missing_exact_open_pair_marks")
    return {
        "events": events,
        "signal_rows": signal_rows,
        "qualifying_signals": qualifying,
        "selected_signal": selected,
        "entered_pair": next((row for row in events if row.get("event") == "entered"), None),
        "exited_pair": exited,
        "mark": mark,
        "open_or_pending_count": open_or_pending,
    }


def _max_drawdown(equity_curve: Sequence[Mapping[str, Any]]) -> float:
    peak = 0.0
    worst = 0.0
    for row in equity_curve:
        equity = float(row.get("equity_usd") or 0.0)
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, equity / peak - 1.0)
    return worst


def summarize_sec_same_issuer_dual_class_spread_state(
    state: Mapping[str, Any],
) -> dict[str, Any]:
    closed = [row for row in state.get("closed_pairs") or [] if isinstance(row, Mapping)]
    equity = [row for row in state.get("equity_curve") or [] if isinstance(row, Mapping)]
    audit = dict(state.get("audit") or {})
    generated = int(audit.get("signals_generated") or 0)
    funded = int(audit.get("entries_funded") or 0)
    pnls = [float(row.get("net_pnl_usd") or 0.0) for row in closed]
    pair_counts = Counter(str(row.get("pair_id") or "") for row in closed)
    pair_shares = {
        pair_id: count / len(closed)
        for pair_id, count in sorted(pair_counts.items())
        if pair_id
    }
    return {
        "signals_generated": generated,
        "signals_survived": funded,
        "survival_rate": funded / generated if generated else None,
        "funded_entry_count": funded,
        "closed_pair_count": len(closed),
        "open_pair_count": int(isinstance(state.get("open_pair"), Mapping)),
        "pending_pair_count": int(isinstance(state.get("pending_pair"), Mapping)),
        "total_net_pnl_usd": sum(pnls),
        "win_rate": sum(value > 0 for value in pnls) / len(pnls) if pnls else None,
        "ending_cash_usd": float(state.get("cash_usd") or 0.0),
        "ending_equity_usd": (
            float(equity[-1]["equity_usd"]) if equity else float(state.get("cash_usd") or 0.0)
        ),
        "minimum_free_cash_usd": min(
            (float(row.get("cash_usd") or 0.0) for row in equity),
            default=float(state.get("cash_usd") or 0.0),
        ),
        "maximum_marked_gross_usd": max(
            (float(row.get("gross_exposure_usd") or 0.0) for row in equity), default=0.0
        ),
        "max_drawdown": _max_drawdown(equity),
        "cash_nonnegative": all(float(row.get("cash_usd") or 0.0) >= -1e-7 for row in equity),
        "max_concurrent_pairs": MAX_CONCURRENT_PAIRS,
        "maximum_open_or_pending_count": int(audit.get("maximum_open_or_pending_count") or 0),
        "open_or_pending_invariant_passed": (
            int(audit.get("maximum_open_or_pending_count") or 0) <= MAX_CONCURRENT_PAIRS
        ),
        "maximum_entry_marked_gross_usd": float(
            audit.get("maximum_entry_marked_gross_usd") or 0.0
        ),
        "entry_marked_gross_limit_passed": (
            float(audit.get("maximum_entry_marked_gross_usd") or 0.0)
            <= INITIAL_CASH_USD + 1e-7
        ),
        "missing_exact_open_pair_mark_count": int(
            audit.get("missing_exact_open_pair_marks") or 0
        ),
        "exact_open_pair_marks_passed": not bool(
            audit.get("missing_exact_open_pair_marks")
        ),
        "closed_pair_counts": dict(sorted(pair_counts.items())),
        "closed_pair_shares": pair_shares,
        "maximum_closed_pair_share": max(pair_shares.values(), default=None),
        "closed_pair_hhi": sum(value * value for value in pair_shares.values()),
        "audit": audit,
    }


def _daily_returns(equity_curve: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    previous = INITIAL_CASH_USD
    for row in equity_curve:
        equity = float(row.get("equity_usd") or 0.0)
        result.append(
            {
                "as_of": row.get("as_of"),
                "equity_usd": equity,
                "daily_return": equity / previous - 1.0 if previous > 0 else None,
            }
        )
        previous = equity
    return result


def _settle_replay_window_boundary(
    state: dict[str, Any],
    final_day: str,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> list[dict[str, Any]]:
    """Measurement-only final-close settlement; never used by the daily path."""
    events: list[dict[str, Any]] = []
    pending = state.get("pending_pair")
    if isinstance(pending, Mapping):
        state["pending_pair"] = None
        _bump(state, "pending_cancelled_window_end")
        events.append(
            {
                **dict(pending),
                "event": "pending_cancelled_window_end",
                "event_id": (
                    f"{RULE_VERSION}:{pending['pair_id']}:"
                    f"{pending['signal_date']}:window_end_cancel"
                ),
                "cancel_date": final_day,
                "trade_enabled": False,
            }
        )
    position = state.get("open_pair")
    if isinstance(position, Mapping):
        pair = PAIR_BY_ID[str(position["pair_id"])]
        if final_day not in _pair_common_dates(pair, prices):
            raise RuntimeError("window boundary lacks an exact two-leg close")
        _, exit_detail = _exit_reason(position, final_day, prices)
        closed = _close_pair(
            position,
            final_day,
            "window_end_force_close",
            exit_detail,
            prices,
        )
        cash = (
            float(state.get("cash_usd") or 0.0)
            + float(position["reserved_capital_usd"])
            + float(closed["gross_pnl_usd"])
            - float(closed["exit_trade_cost_usd"])
            - float(closed["short_carry_usd"])
        )
        if cash < -1e-7:
            raise RuntimeError("cash nonnegative invariant violated at replay boundary")
        state["cash_usd"] = cash
        state["open_pair"] = None
        state.setdefault("closed_pairs", []).append(closed)
        state.setdefault("last_exit_date_by_pair", {})[str(position["pair_id"])] = final_day
        _bump(state, "pairs_closed")
        _bump(state, "exit_window_end_force_close")
        events.append(
            {
                **closed,
                "event": "exited",
                "event_id": (
                    f"{RULE_VERSION}:{position['pair_id']}:"
                    f"{position['signal_date']}:window_end_exit"
                ),
            }
        )
        curve = state.setdefault("equity_curve", [])
        if curve and curve[-1].get("as_of") == final_day:
            curve.pop()
        curve.append(
            {
                "status": "ok",
                "as_of": final_day,
                "cash_usd": cash,
                "equity_usd": cash,
                "gross_exposure_usd": 0.0,
                "accrued_short_carry_usd": 0.0,
                "window_boundary_settled": True,
            }
        )
    return events


def replay_sec_same_issuer_dual_class_spread_sleeve(
    sec_payload: Any,
    ohlcv_by_ticker: Mapping[str, Any],
    start: Any,
    end: Any,
) -> dict[str, Any]:
    """Replay the frozen policy over exact market dates in ``[start, end]``."""
    start_day = _date10(start)
    end_day = _date10(end)
    if not start_day or not end_day or start_day > end_day:
        raise ValueError(f"invalid replay window: {start!r}..{end!r}")
    identity = assert_frozen_sec_identities(sec_payload)
    prices = _normalise_prices(ohlcv_by_ticker)
    sessions = [day for day in _account_sessions(prices) if start_day <= day <= end_day]
    state = empty_sec_same_issuer_dual_class_spread_state()
    events: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    for day in sessions:
        transition = _advance_day(state, day, prices, allow_new_signals=True)
        events.extend(transition["events"])
        daily.append(
            {
                "as_of": day,
                "signal_rows": transition["signal_rows"],
                "qualifying_signals": transition["qualifying_signals"],
                "selected_signal": transition["selected_signal"],
                "entered_pair": transition["entered_pair"],
                "exited_pair": transition["exited_pair"],
                "mark": transition["mark"],
            }
        )
    boundary_events: list[dict[str, Any]] = []
    if sessions:
        boundary_events = _settle_replay_window_boundary(state, sessions[-1], prices)
        events.extend(boundary_events)
        if daily:
            daily[-1]["window_boundary_events"] = boundary_events
            forced_exit = next(
                (row for row in boundary_events if row.get("event") == "exited"), None
            )
            if forced_exit is not None:
                daily[-1]["exited_pair"] = forced_exit
                daily[-1]["mark"] = state["equity_curve"][-1]
    return {
        "rule_version": RULE_VERSION,
        "start": start_day,
        "end": end_day,
        "session_count": len(sessions),
        "identity_contract": identity,
        "price_provenance_contract": price_provenance_contract(),
        "identity_pit_caveat": (
            "SEC company_tickers is a current snapshot, not effective-dated history; "
            "historical evidence is conditional on the frozen whitelist."
        ),
        "events": events,
        "window_boundary_contract": {
            "pending_action": "cancel_without_fill",
            "open_action": "force_close_at_final_exact_close",
            "open_exit_reason": "window_end_force_close",
            "normal_exit_cost_and_inclusive_carry_charged": True,
            "daily_policy_affected": False,
        },
        "selection_contract": selection_contract(),
        "cooldown_contract": cooldown_contract(),
        "daily_snapshots": daily,
        "trades": list(state["closed_pairs"]),
        "daily_equity": list(state["equity_curve"]),
        "daily_returns": _daily_returns(state["equity_curve"]),
        "state": state,
        "summary": summarize_sec_same_issuer_dual_class_spread_state(state),
        "execution_sizing_contract": execution_sizing_contract(),
        "trade_enabled": False,
        "production_impact": production_impact(),
    }


def _state_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    equity = state.get("equity_curve") or []
    latest = equity[-1] if equity else None
    return {
        "cash_usd": float(state.get("cash_usd") or 0.0),
        "pending_pair_count": int(isinstance(state.get("pending_pair"), Mapping)),
        "open_pair_count": int(isinstance(state.get("open_pair"), Mapping)),
        "closed_pair_count": len(state.get("closed_pairs") or []),
        "last_processed_as_of": state.get("last_processed_as_of"),
        "equity_usd": latest.get("equity_usd") if isinstance(latest, Mapping) else None,
        "gross_exposure_usd": (
            latest.get("gross_exposure_usd") if isinstance(latest, Mapping) else None
        ),
        "accrued_short_carry_usd": (
            latest.get("accrued_short_carry_usd") if isinstance(latest, Mapping) else None
        ),
    }


def empty_sec_same_issuer_dual_class_spread_paper_snapshot(
    as_of: Any,
    reason: str,
    *,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    day = _date10(as_of) or str(as_of or "")
    work = _copy_json(state or empty_sec_same_issuer_dual_class_spread_state())
    return {
        "record_id": f"{RULE_VERSION}:snapshot:{day}",
        "rule_version": RULE_VERSION,
        "as_of": day,
        "status": "refused",
        "reason": reason,
        "state": work,
        "state_summary": _state_summary(work),
        "events": [],
        "price_provenance_contract": price_provenance_contract(),
        "selection_contract": selection_contract(),
        "cooldown_contract": cooldown_contract(),
        "execution_sizing_contract": execution_sizing_contract(),
        "trade_enabled": False,
        "production_impact": production_impact(),
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return value if isinstance(value, dict) else None


def _append_jsonl_idempotent(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    key_field: str,
) -> dict[str, int]:
    existing: list[dict[str, Any]] = []
    if path.exists():
        existing = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    keys = {str(row.get(key_field) or "") for row in existing}
    appended: list[dict[str, Any]] = []
    duplicates = 0
    for raw in rows:
        row = dict(raw)
        key = str(row.get(key_field) or "")
        if not key:
            raise ValueError(f"missing {key_field}")
        if key in keys:
            duplicates += 1
            continue
        keys.add(key)
        appended.append(row)
    if appended:
        atomic_write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in existing + appended) + "\n",
            path,
        )
    return {
        "appended": len(appended),
        "duplicates": duplicates,
        "total": len(existing) + len(appended),
    }


def build_sec_same_issuer_dual_class_spread_paper_snapshot(
    *,
    as_of: Any,
    sec_payload: Any,
    sec_as_of: Any,
    ohlcv_by_ticker: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    state_path: str | Path | None = None,
    snapshot_ledger_path: str | Path | None = None,
    pair_ledger_path: str | Path | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Advance one exact-date default-off snapshot, refusing stale inputs."""
    day = _date10(as_of)
    if not day:
        return empty_sec_same_issuer_dual_class_spread_paper_snapshot(as_of, "invalid_as_of")
    sec_day = _date10(sec_as_of)
    if sec_day != day:
        return empty_sec_same_issuer_dual_class_spread_paper_snapshot(
            day, "stale_sec_identity_as_of", state=state
        )
    try:
        identity = assert_frozen_sec_identities(sec_payload)
    except (FrozenIdentityError, OSError, json.JSONDecodeError) as exc:
        snapshot = empty_sec_same_issuer_dual_class_spread_paper_snapshot(
            day, "sec_identity_validation_failed", state=state
        )
        snapshot["identity_error"] = str(exc)
        return snapshot

    state_target = Path(state_path) if state_path is not None else DEFAULT_STATE_PATH
    snapshot_target = (
        Path(snapshot_ledger_path)
        if snapshot_ledger_path is not None
        else DEFAULT_SNAPSHOT_LEDGER_PATH
    )
    pair_target = Path(pair_ledger_path) if pair_ledger_path is not None else DEFAULT_PAIR_LEDGER_PATH
    loaded = _load_json(state_target) if persist and state is None else None
    work = _copy_json(state or loaded or empty_sec_same_issuer_dual_class_spread_state())
    if work.get("rule_version") != RULE_VERSION:
        return empty_sec_same_issuer_dual_class_spread_paper_snapshot(
            day, "state_rule_version_mismatch", state=work
        )
    for state_key in ("pending_pair", "open_pair"):
        state_pair = work.get(state_key)
        if not isinstance(state_pair, Mapping):
            continue
        identity_pair = PAIR_BY_ID.get(str(state_pair.get("pair_id") or ""))
        if identity_pair is None or not identity_pair["data_provenance_admitted"]:
            snapshot = empty_sec_same_issuer_dual_class_spread_paper_snapshot(
                day, "state_contains_data_provenance_ineligible_pair", state=work
            )
            snapshot["state_pair_field"] = state_key
            snapshot["state_pair_id"] = state_pair.get("pair_id")
            snapshot["identity_contract"] = identity
            return snapshot

    prices = _normalise_prices(ohlcv_by_ticker)
    sessions = _account_sessions(prices)
    if day not in sessions:
        return empty_sec_same_issuer_dual_class_spread_paper_snapshot(
            day, "as_of_not_exact_common_session", state=work
        )
    if day in set(work.get("processed_dates") or []):
        snapshot = empty_sec_same_issuer_dual_class_spread_paper_snapshot(
            day, "already_processed_idempotent", state=work
        )
        snapshot["status"] = "idempotent"
        snapshot["identity_contract"] = identity
        return snapshot
    last_day = _date10(work.get("last_processed_as_of"))
    if last_day:
        try:
            day_pos = sessions.index(day)
        except ValueError:  # covered above; keeps the guard explicit
            day_pos = -1
        expected_previous = sessions[day_pos - 1] if day_pos > 0 else None
        if expected_previous != last_day:
            snapshot = empty_sec_same_issuer_dual_class_spread_paper_snapshot(
                day, "stale_as_of_refused", state=work
            )
            snapshot["expected_previous_session"] = expected_previous
            snapshot["state_last_processed_as_of"] = last_day
            snapshot["identity_contract"] = identity
            return snapshot
    existing_open = work.get("open_pair")
    if isinstance(existing_open, Mapping):
        if (
            day not in prices.get(str(existing_open["long_ticker"]), {})
            or day not in prices.get(str(existing_open["short_ticker"]), {})
        ):
            snapshot = empty_sec_same_issuer_dual_class_spread_paper_snapshot(
                day, "open_pair_missing_exact_as_of_mark", state=work
            )
            snapshot["identity_contract"] = identity
            return snapshot

    transition = _advance_day(work, day, prices, allow_new_signals=True)
    snapshot = {
        "record_id": f"{RULE_VERSION}:snapshot:{day}",
        "rule_version": RULE_VERSION,
        "as_of": day,
        "status": "ready",
        "reason": None,
        "identity_contract": identity,
        "price_provenance_contract": price_provenance_contract(),
        "signal_rows": transition["signal_rows"],
        "qualifying_signals": transition["qualifying_signals"],
        "selected_signal": transition["selected_signal"],
        "entered_pair": transition["entered_pair"],
        "exited_pair": transition["exited_pair"],
        "events": transition["events"],
        "selection_contract": selection_contract(),
        "cooldown_contract": cooldown_contract(),
        "daily_mark": transition["mark"],
        "state": work,
        "state_summary": _state_summary(work),
        "execution_sizing_contract": execution_sizing_contract(),
        "trade_enabled": False,
        "production_impact": production_impact(),
    }
    if persist:
        atomic_write_json(work, state_target, indent=2, ensure_ascii=True)
        snapshot_for_ledger = {key: value for key, value in snapshot.items() if key != "state"}
        snapshot["snapshot_ledger_merge"] = _append_jsonl_idempotent(
            snapshot_target, [snapshot_for_ledger], key_field="record_id"
        )
        snapshot["pair_ledger_merge"] = _append_jsonl_idempotent(
            pair_target, transition["events"], key_field="event_id"
        )
    return snapshot


__all__ = [
    "RULE_VERSION",
    "FROZEN_IDENTITY_PAIRS",
    "FROZEN_PAIRS",
    "FROZEN_IDENTITY_TICKERS",
    "FROZEN_TICKERS",
    "FROZEN_IDENTITY_WHITELIST_SHA256",
    "FROZEN_ECONOMIC_WHITELIST_SHA256",
    "FROZEN_PROVENANCE_POLICY_SHA256",
    "FROZEN_WHITELIST_SHA256",
    "ROBUST_LOOKBACK_SESSIONS",
    "MAD_SCALE",
    "ENTRY_ROBUST_Z",
    "ENTRY_MIN_ABS_LOG_DEVIATION",
    "CONVERGENCE_ABS_LOG_DEVIATION",
    "ADVERSE_LOG_SPREAD_STOP",
    "MAX_HOLD_SESSIONS",
    "SAME_PAIR_COOLDOWN_SESSIONS",
    "INITIAL_CASH_USD",
    "LEG_NOTIONAL_CAP_USD",
    "MAX_ENTRY_DOLLAR_IMBALANCE",
    "ROUND_TRIP_COST_RATE_PER_LEG",
    "HALF_TRADE_COST_RATE",
    "SHORT_CARRY_ANNUAL_RATE",
    "DEFAULT_STATE_PATH",
    "DEFAULT_SNAPSHOT_LEDGER_PATH",
    "DEFAULT_PAIR_LEDGER_PATH",
    "FrozenIdentityError",
    "parse_sec_company_tickers",
    "assert_frozen_sec_identities",
    "compute_strict_prior_pair_signal",
    "size_whole_share_pair_entry",
    "empty_sec_same_issuer_dual_class_spread_state",
    "empty_sec_same_issuer_dual_class_spread_paper_snapshot",
    "summarize_sec_same_issuer_dual_class_spread_state",
    "replay_sec_same_issuer_dual_class_spread_sleeve",
    "build_sec_same_issuer_dual_class_spread_paper_snapshot",
    "execution_sizing_contract",
    "selection_contract",
    "cooldown_contract",
    "price_provenance_contract",
    "production_impact",
]
