"""Broker-authoritative, append-only execution facts.

The Moomoo refresh already talks to OpenD once per daily run.  This module
turns that ephemeral response into durable facts without changing any order,
strategy, ranking, sizing, or exit behavior.

Raw broker facts and derived interpretations are deliberately separate:

* deal rows are versioned because the broker can mark a fill CHANGED/CANCELLED;
* orders and order-level fees are versioned snapshots because they can change;
* cash flows are versioned snapshots projected by latest ``cashflow_id`` state;
* account/position snapshots describe collection-time state, never historical
  post-fill state;
* fill-to-lifecycle links are derived sidecar rows and may be rebuilt.

Every JSONL file is a strict hash chain.  Broker corrections append versions;
a corrupt chain, fixed-snapshot conflict, or mixed account root fails closed
before any canonical ledger file is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text
except ImportError:  # pragma: no cover - package-style imports
    from quant.data_paths import DATA_ROOT, atomic_write_json, atomic_write_text


SCHEMA_VERSION = 1
RULE_VERSION = "broker_execution_fact_ledger_v1"
LIFECYCLE_RULE_VERSION = "broker_fill_lifecycle_replay_v3_strict_baseline"
DEFAULT_LEDGER_DIR = DATA_ROOT / "live_pilot" / "broker_execution"

LEDGER_FILENAMES = {
    "fills": "fills.jsonl",
    "orders": "order_snapshots.jsonl",
    "order_fees": "order_fee_snapshots.jsonl",
    "cashflows": "cash_flows.jsonl",
    "accounts": "account_snapshots.jsonl",
    "positions": "position_snapshots.jsonl",
    "lifecycle_links": "fill_lifecycle_links.jsonl",
    "collections": "collection_manifests.jsonl",
}

_ID_FIELDS = {
    "acc_id",
    "cashflow_id",
    "combo_id",
    "counter_broker_id",
    "deal_id",
    "order_id",
    "position_id",
}
_DECIMAL_FIELDS = {
    "amount",
    "aud_assets",
    "aud_net_cash_power",
    "au_cash",
    "au_avl_withdrawal_cash",
    "available_funds",
    "average_cost",
    "avl_withdrawal_cash",
    "beginning_dtbp",
    "bond_assets",
    "cad_assets",
    "cad_net_cash_power",
    "ca_cash",
    "ca_avl_withdrawal_cash",
    "can_sell_qty",
    "cash",
    "cashflow_amount",
    "cnh_assets",
    "cnh_net_cash_power",
    "cn_cash",
    "cn_avl_withdrawal_cash",
    "cost_price",
    "crypto_mv",
    "dealt_avg_price",
    "dealt_qty",
    "diluted_cost",
    "dt_call_amount",
    "exposure_level",
    "exposure_limit",
    "fee_amount",
    "frozen_cash",
    "fund_assets",
    "hkd_assets",
    "hkd_net_cash_power",
    "hk_cash",
    "hk_avl_withdrawal_cash",
    "initial_margin",
    "interest_charged_amount",
    "jpy_assets",
    "jpy_net_cash_power",
    "jp_cash",
    "jp_avl_withdrawal_cash",
    "long_mv",
    "maintenance_margin",
    "margin_call_margin",
    "market_val",
    "max_power_short",
    "max_withdrawal",
    "myr_assets",
    "myr_net_cash_power",
    "my_cash",
    "my_avl_withdrawal_cash",
    "net_cash_power",
    "nominal_price",
    "pending_asset",
    "pl_ratio",
    "pl_ratio_avg_cost",
    "pl_val",
    "power",
    "price",
    "qty",
    "realized_pl",
    "remaining_dtbp",
    "remaining_limit",
    "securities_assets",
    "sgd_assets",
    "sgd_net_cash_power",
    "sg_cash",
    "sg_avl_withdrawal_cash",
    "short_mv",
    "today_buy_qty",
    "today_buy_val",
    "today_pl_val",
    "today_sell_qty",
    "today_sell_val",
    "today_trd_val",
    "total_assets",
    "trail_spread",
    "trail_value",
    "unrealized_pl",
    "usd_assets",
    "usd_net_cash_power",
    "us_cash",
    "us_avl_withdrawal_cash",
    "used_limit",
}
_UNKNOWN_TEXT = {"", "N/A", "NA", "NONE", "NAN", "NULL", "--"}


class BrokerLedgerError(RuntimeError):
    """Base class for canonical broker-ledger failures."""


class BrokerLedgerCorruptionError(BrokerLedgerError):
    """Raised when an existing JSONL ledger is not a valid hash chain."""


class BrokerLedgerConflictError(BrokerLedgerError):
    """Raised for a fixed snapshot identity conflict or mixed-account root."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def account_key(*, security_firm: str, trade_environment: str, acc_id: Any) -> str:
    """Stable account scope without persisting the raw broker account number."""
    firm = str(security_firm or "unknown").strip().lower()
    env = str(trade_environment or "unknown").strip().lower()
    digest = hashlib.sha256(
        f"{firm}|{env}|{str(acc_id).strip()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"moomoo:{firm}:{env}:{digest}"


def _is_unknown(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().upper() in _UNKNOWN_TEXT:
        return True
    if isinstance(value, float) and not math.isfinite(value):
        return True
    return False


def _decimal_text(value: Any) -> str | None:
    if _is_unknown(value):
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not dec.is_finite():
        return None
    text = format(dec, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def _as_decimal(value: Any) -> Decimal | None:
    text = _decimal_text(value)
    return Decimal(text) if text is not None else None


def _id_text(value: Any) -> str | None:
    if _is_unknown(value):
        return None
    # Pandas may surface integral IDs as floats; avoid the trailing '.0'.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy/enum-shaped SDK values to strict JSON primitives."""
    if _is_unknown(value):
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return json_safe(item())
        except (TypeError, ValueError):
            pass
    return str(value)


def _clean_record(raw: Mapping[str, Any], *, omit_account_id: bool = True) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for raw_key, value in raw.items():
        key = str(raw_key)
        if omit_account_id and key == "acc_id":
            continue
        if key in _ID_FIELDS:
            clean[key] = _id_text(value)
        elif key in _DECIMAL_FIELDS:
            clean[key] = _decimal_text(value)
        elif key == "fee_details":
            details = []
            for item in value or []:
                if isinstance(item, Mapping):
                    title = item.get("title") or item.get("name")
                    amount = item.get("amount") or item.get("value")
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    title, amount = item[0], item[1]
                else:
                    title, amount = str(item), None
                details.append(
                    {"title": str(title or ""), "amount": _decimal_text(amount)}
                )
            clean[key] = details
        else:
            clean[key] = json_safe(value)
    return clean


def _base_context(capture: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": "moomoo_opend",
        "security_firm": str(capture.get("security_firm") or "unknown"),
        "trade_environment": str(capture.get("trade_environment") or "REAL"),
        "account_key": str(capture.get("account_key") or "unknown"),
    }


def normalize_fill(
    raw: Mapping[str, Any],
    capture: Mapping[str, Any],
    *,
    order_currency: str | None = None,
) -> dict[str, Any]:
    fact = {**_base_context(capture), **_clean_record(raw)}
    code = str(fact.get("code") or "").strip()
    fact["ticker"] = code.split(".", 1)[-1].upper() if code else None
    fact["trd_side"] = str(fact.get("trd_side") or "").upper() or None
    deal_status = str(fact.get("status") or "").upper() or None
    fact["deal_status"] = deal_status
    if deal_status in {"OK", "CHANGED"}:
        economic_status = "effective"
    elif deal_status == "CANCELLED":
        economic_status = "cancelled"
    else:
        economic_status = "unknown_quarantined"
    fact["economic_effect_status"] = economic_status
    fact["event_time_raw"] = str(fact.get("create_time") or "") or None
    fact["event_time_timezone_status"] = "broker_local_unspecified"
    fact["event_time_utc"] = None
    fact["currency"] = order_currency
    fact["currency_provenance"] = (
        "joined_from_order_snapshot" if order_currency else "unavailable"
    )

    qty = _as_decimal(fact.get("qty"))
    price = _as_decimal(fact.get("price"))
    gross = abs(qty * price) if qty is not None and price is not None else None
    fact["gross_notional"] = _decimal_text(gross)
    fact["effective_gross_notional"] = (
        _decimal_text(gross) if economic_status == "effective" else None
    )
    side = fact.get("trd_side")
    if gross is None:
        cash_flow = None
    elif side in {"BUY", "BUY_BACK", "BUYBACK"}:
        cash_flow = -gross
    elif side in {"SELL", "SELL_SHORT", "SHORT_SELL"}:
        cash_flow = gross
    else:
        cash_flow = None
    fact["gross_trade_cash_flow_before_order_fee"] = _decimal_text(cash_flow)
    fact["effective_gross_trade_cash_flow_before_order_fee"] = (
        _decimal_text(cash_flow) if economic_status == "effective" else None
    )
    fact["fee_scope"] = "order_level_not_fill_level"
    return fact


def normalize_order(raw: Mapping[str, Any], capture: Mapping[str, Any]) -> dict[str, Any]:
    fact = {**_base_context(capture), **_clean_record(raw)}
    code = str(fact.get("code") or "").strip()
    fact["ticker"] = code.split(".", 1)[-1].upper() if code else None
    fact["trd_side"] = str(fact.get("trd_side") or "").upper() or None
    fact["create_time_raw"] = str(fact.get("create_time") or "") or None
    fact["updated_time_raw"] = str(fact.get("updated_time") or "") or None
    fact["event_time_timezone_status"] = "broker_local_unspecified"
    return fact


def normalize_order_fee(
    raw: Mapping[str, Any],
    capture: Mapping[str, Any],
    *,
    order_currency: str | None,
) -> dict[str, Any]:
    fact = {**_base_context(capture), **_clean_record(raw)}
    fact["currency"] = order_currency
    fact["currency_provenance"] = (
        "joined_from_order_snapshot" if order_currency else "unavailable"
    )
    fact["fee_status"] = "reported" if fact.get("fee_amount") is not None else "pending_or_unavailable"
    fact["fee_scope"] = "broker_reported_order_level"
    return fact


def normalize_cashflow(raw: Mapping[str, Any], capture: Mapping[str, Any]) -> dict[str, Any]:
    fact = {**_base_context(capture), **_clean_record(raw)}
    fact["create_time_raw"] = str(fact.get("create_time") or "") or None
    fact["event_time_timezone_status"] = "broker_local_unspecified"
    fact["accounting_scope"] = "cash_reconciliation_do_not_double_count_as_order_fee"
    return fact


def _deal_key(fact: Mapping[str, Any]) -> str:
    account = str(fact.get("account_key") or "unknown")
    market = str(fact.get("deal_market") or "unknown")
    deal_id = _id_text(fact.get("deal_id"))
    if deal_id:
        return f"{account}|{market}|{deal_id}"
    return f"{account}|{market}|missing|{_sha256_json(fact)}"


def _fill_identity(fact: Mapping[str, Any]) -> str:
    """Version identity: broker deal status can be OK/CHANGED/CANCELLED."""
    return f"deal_snapshot|{_deal_key(fact)}|{_sha256_json(fact)}"


def _cashflow_key(fact: Mapping[str, Any]) -> str:
    account = str(fact.get("account_key") or "unknown")
    currency = str(fact.get("currency") or "unknown")
    clearing = str(fact.get("clearing_date") or "unknown")
    cashflow_id = _id_text(fact.get("cashflow_id"))
    if cashflow_id:
        return f"{account}|{currency}|{clearing}|{cashflow_id}"
    return f"{account}|{currency}|{clearing}|missing|{_sha256_json(fact)}"


def _cashflow_identity(fact: Mapping[str, Any]) -> str:
    return f"cashflow_snapshot|{_cashflow_key(fact)}|{_sha256_json(fact)}"


def _versioned_identity(record_type: str, fact: Mapping[str, Any], entity_id: Any) -> str:
    account = str(fact.get("account_key") or "unknown")
    entity = _id_text(entity_id) or "missing"
    return f"{record_type}|{account}|{entity}|{_sha256_json(fact)}"


def _snapshot_identity(record_type: str, capture: Mapping[str, Any]) -> str:
    return (
        f"{record_type}|{capture.get('account_key') or 'unknown'}|"
        f"{capture.get('collection_id') or 'unknown'}"
    )


def _candidate(
    *,
    record_type: str,
    identity_key: str,
    fact: Mapping[str, Any],
    observed_at: str,
    collection_id: str,
    conflict_key: str | None = None,
) -> dict[str, Any]:
    fact_dict = dict(fact)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "identity_key": identity_key,
        "conflict_key": conflict_key,
        "fact_hash": _sha256_json(fact_dict),
        "observed_at_utc": observed_at,
        "collection_id": collection_id,
        "fact": fact_dict,
    }


@dataclass
class _AppendPlan:
    path: Path
    existing_text: str
    existing_rows: list[dict[str, Any]]
    new_rows: list[dict[str, Any]]

    @property
    def final_rows(self) -> list[dict[str, Any]]:
        return self.existing_rows + self.new_rows


def _strict_read_chain(path: Path) -> tuple[str, list[dict[str, Any]]]:
    if not path.exists():
        return "", []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BrokerLedgerCorruptionError(f"cannot read {path}: {exc}") from exc
    if text and not text.endswith("\n"):
        raise BrokerLedgerCorruptionError(f"{path} lacks a trailing newline")

    rows: list[dict[str, Any]] = []
    expected_prev: str | None = None
    identities: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise BrokerLedgerCorruptionError(f"blank line in {path}:{line_number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BrokerLedgerCorruptionError(
                f"invalid JSON in {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise BrokerLedgerCorruptionError(f"non-object row in {path}:{line_number}")
        expected_sequence = len(rows) + 1
        if row.get("ledger_sequence") != expected_sequence:
            raise BrokerLedgerCorruptionError(
                f"sequence mismatch in {path}:{line_number}"
            )
        if row.get("prev_record_hash") != expected_prev:
            raise BrokerLedgerCorruptionError(
                f"previous-hash mismatch in {path}:{line_number}"
            )
        supplied_hash = row.get("record_hash")
        payload = {k: v for k, v in row.items() if k != "record_hash"}
        if supplied_hash != _sha256_json(payload):
            raise BrokerLedgerCorruptionError(f"record-hash mismatch in {path}:{line_number}")
        if row.get("fact_hash") != _sha256_json(row.get("fact")):
            raise BrokerLedgerCorruptionError(f"fact-hash mismatch in {path}:{line_number}")
        identity = str(row.get("identity_key") or "")
        if not identity or identity in identities:
            raise BrokerLedgerCorruptionError(
                f"missing/duplicate identity in {path}:{line_number}"
            )
        identities.add(identity)
        expected_prev = str(supplied_hash)
        rows.append(row)
    return text, rows


def _plan_append(path: Path, candidates: Iterable[dict[str, Any]]) -> _AppendPlan:
    existing_text, existing = _strict_read_chain(path)
    identities = {str(row["identity_key"]): row for row in existing}
    conflicts = {
        str(row["conflict_key"]): str(row["fact_hash"])
        for row in existing
        if row.get("conflict_key")
    }
    new_rows: list[dict[str, Any]] = []
    prev_hash = str(existing[-1]["record_hash"]) if existing else None

    for raw_candidate in candidates:
        candidate = dict(raw_candidate)
        identity = str(candidate.get("identity_key") or "")
        if not identity:
            raise BrokerLedgerError(f"candidate for {path} has no identity_key")
        prior = identities.get(identity)
        if prior is not None:
            if prior.get("fact_hash") != candidate.get("fact_hash"):
                raise BrokerLedgerConflictError(
                    f"identity {identity!r} changed content in {path}"
                )
            continue
        conflict_key = candidate.get("conflict_key")
        if conflict_key:
            prior_hash = conflicts.get(str(conflict_key))
            if prior_hash is not None and prior_hash != candidate.get("fact_hash"):
                raise BrokerLedgerConflictError(
                    f"fixed ledger identity {conflict_key!r} changed content in {path}"
                )
            conflicts[str(conflict_key)] = str(candidate.get("fact_hash"))

        candidate["ledger_sequence"] = len(existing) + len(new_rows) + 1
        candidate["prev_record_hash"] = prev_hash
        candidate["record_hash"] = _sha256_json(candidate)
        prev_hash = str(candidate["record_hash"])
        identities[identity] = candidate
        new_rows.append(candidate)
    return _AppendPlan(path, existing_text, existing, new_rows)


def _write_plan(plan: _AppendPlan) -> None:
    if not plan.new_rows:
        return
    suffix = "".join(_canonical_json(row) + "\n" for row in plan.new_rows)
    # Preserve the validated prefix byte-for-byte; only append canonical rows.
    atomic_write_text(plan.existing_text + suffix, plan.path)


@contextmanager
def _exclusive_ledger_lock(lock_path: Path, timeout_seconds: float = 15.0):
    """Small cross-platform advisory lock for CLI writers outside run.py."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - CI may exercise on POSIX
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise BrokerLedgerError(f"timed out waiting for {lock_path}")
                time.sleep(0.05)
        yield
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


def _query_status(capture: Mapping[str, Any], name: str) -> str:
    query = (capture.get("queries") or {}).get(name) or {}
    return str(query.get("status") or "missing")


def _query_ok(capture: Mapping[str, Any], name: str) -> bool:
    return _query_status(capture, name) in {"ok", "partial"}


def _account_snapshot_fact(capture: Mapping[str, Any]) -> dict[str, Any]:
    accounts = [_clean_record(row) for row in capture.get("accounts") or []]
    positions_available = _query_ok(capture, "positions")
    positions = (
        [_clean_record(row) for row in capture.get("positions") or []]
        if positions_available
        else []
    )
    account = accounts[0] if accounts else {}

    total_assets = _as_decimal(account.get("total_assets"))
    long_mv = _as_decimal(account.get("long_mv"))
    short_mv = _as_decimal(account.get("short_mv"))
    reported_market_val = _as_decimal(account.get("market_val"))
    cash = _as_decimal(account.get("cash"))
    long_mv = long_mv if long_mv is not None else Decimal("0")
    short_mv = short_mv if short_mv is not None else Decimal("0")
    gross = abs(long_mv) + abs(short_mv)
    net = long_mv + short_mv if short_mv <= 0 else long_mv - short_mv

    reporting_currency = str(account.get("currency") or "") or None
    position_by_currency: dict[str, dict[str, Decimal]] = {}
    for row in positions:
        market_val = _as_decimal(row.get("market_val")) or Decimal("0")
        side = str(row.get("position_side") or "LONG").upper()
        currency = str(row.get("currency") or "unknown")
        bucket = position_by_currency.setdefault(
            currency, {"long": Decimal("0"), "short": Decimal("0")}
        )
        if side.startswith("SHORT"):
            bucket["short"] += abs(market_val)
        else:
            bucket["long"] += abs(market_val)
    position_currency_summary = {
        currency: {
            "long_market_value": _decimal_text(values["long"]),
            "short_market_value": _decimal_text(values["short"]),
            "gross_market_value": _decimal_text(values["long"] + values["short"]),
            "net_market_value": _decimal_text(values["long"] - values["short"]),
        }
        for currency, values in sorted(position_by_currency.items())
    }
    same_reporting_currency = bool(
        positions_available
        and (
            not positions
            or (
                reporting_currency is not None
                and set(position_by_currency) == {reporting_currency}
            )
        )
    )
    if same_reporting_currency:
        values = position_by_currency.get(
            reporting_currency or "", {"long": Decimal("0"), "short": Decimal("0")}
        )
        position_gross = values["long"] + values["short"]
        position_net = values["long"] - values["short"]
    else:
        position_gross = None
        position_net = None

    def ratio(numerator: Decimal, denominator: Decimal | None) -> str | None:
        if denominator is None or denominator == 0:
            return None
        return _decimal_text(numerator / denominator)

    return {
        **_base_context(capture),
        "collection_id": capture.get("collection_id"),
        "collection_started_at_utc": capture.get("collection_started_at_utc"),
        "collection_completed_at_utc": capture.get("collection_completed_at_utc"),
        "reporting_currency": reporting_currency,
        "account_info": accounts,
        "account_row_count": len(accounts),
        "exposure": {
            "cash_reported": _decimal_text(cash),
            "total_assets_reported": _decimal_text(total_assets),
            "market_value_reported": _decimal_text(reported_market_val),
            "long_market_value_reported": _decimal_text(long_mv),
            "short_market_value_reported": _decimal_text(short_mv),
            "gross_exposure_reported": _decimal_text(gross),
            "net_exposure_reported": _decimal_text(net),
            "gross_leverage_reported": ratio(gross, total_assets),
            "net_leverage_reported": ratio(net, total_assets),
            "position_gross_market_value": _decimal_text(position_gross),
            "position_net_market_value": _decimal_text(position_net),
            "position_gross_leverage": (
                ratio(position_gross, total_assets)
                if position_gross is not None
                else None
            ),
            "position_net_leverage": (
                ratio(position_net, total_assets)
                if position_net is not None
                else None
            ),
            "position_vs_account_market_value_delta": _decimal_text(
                position_net - reported_market_val
                if position_net is not None and reported_market_val is not None
                else None
            ),
            "cash_plus_position_net_vs_total_assets_delta": _decimal_text(
                cash + position_net - total_assets
                if cash is not None
                and position_net is not None
                and total_assets is not None
                else None
            ),
            "negative_cash_preserved": bool(cash is not None and cash < 0),
            "position_market_value_by_currency": position_currency_summary,
            "position_exposure_status": (
                "reported_same_currency"
                if same_reporting_currency
                else (
                    "suppressed_cross_currency_no_fx"
                    if positions_available
                    else "unavailable_position_query_failed"
                )
            ),
        },
        "temporal_scope": "collection_time_not_historical_post_fill",
    }


def _position_snapshot_fact(capture: Mapping[str, Any]) -> dict[str, Any]:
    positions = [_clean_record(row) for row in capture.get("positions") or []]
    return {
        **_base_context(capture),
        "collection_id": capture.get("collection_id"),
        "collection_started_at_utc": capture.get("collection_started_at_utc"),
        "collection_completed_at_utc": capture.get("collection_completed_at_utc"),
        "position_count": len(positions),
        "positions": positions,
        "flat_account_observed": len(positions) == 0,
        "temporal_scope": "collection_time",
    }


def _economic_effect_status(fact: Mapping[str, Any]) -> str:
    explicit = str(fact.get("economic_effect_status") or "").lower()
    if explicit in {"effective", "cancelled", "unknown_quarantined"}:
        return explicit
    status = str(fact.get("deal_status") or fact.get("status") or "").upper()
    if status in {"OK", "CHANGED"}:
        return "effective"
    if status == "CANCELLED":
        return "cancelled"
    return "unknown_quarantined"


def _economic_fill_projection(
    deal_snapshot_rows: Iterable[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], dict[str, Any]]:
    """Select the latest broker version per deal and keep economic fills only."""
    latest_by_deal: dict[str, Mapping[str, Any]] = {}
    snapshot_count = 0
    for row in deal_snapshot_rows:
        snapshot_count += 1
        fact = row.get("fact") or {}
        latest_by_deal[_deal_key(fact)] = row

    status_counts: dict[str, int] = {}
    effective: list[Mapping[str, Any]] = []
    excluded: list[Mapping[str, Any]] = []
    for row in latest_by_deal.values():
        fact = row.get("fact") or {}
        status = _economic_effect_status(fact)
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "effective":
            effective.append(row)
        else:
            excluded.append(row)
    effective.sort(key=lambda row: _fill_sort_key(row.get("fact") or {}))
    excluded.sort(key=lambda row: _fill_sort_key(row.get("fact") or {}))
    return effective, excluded, {
        "deal_snapshot_count": snapshot_count,
        "distinct_deal_count": len(latest_by_deal),
        "effective_deal_count": len(effective),
        "cancelled_deal_count": status_counts.get("cancelled", 0),
        "unknown_quarantined_deal_count": status_counts.get(
            "unknown_quarantined", 0
        ),
        "latest_status_counts": status_counts,
        "projection_rule": "latest_deal_version_OK_or_CHANGED_effective_v1",
    }


def _build_void_lifecycle_links(
    excluded_deal_rows: Iterable[Mapping[str, Any]],
    *,
    observed_at: str,
    collection_id: str,
) -> list[dict[str, Any]]:
    candidates = []
    for row in excluded_deal_rows:
        fact = row.get("fact") or {}
        effect = _economic_effect_status(fact)
        link_fact = {
            "source": "derived_from_broker_fills",
            "rule_version": LIFECYCLE_RULE_VERSION,
            "fill_identity_key": row.get("identity_key"),
            "account_key": fact.get("account_key"),
            "code": fact.get("code"),
            "ticker": fact.get("ticker"),
            "deal_id": fact.get("deal_id"),
            "order_id": fact.get("order_id"),
            "event_time_raw": fact.get("event_time_raw"),
            "lifecycle_id": None,
            "lifecycle_start_deal_id": None,
            "lifecycle_direction": None,
            "event_role": "void_non_effective_deal",
            "link_status": f"void_{effect}",
            "running_qty_before": None,
            "running_qty_after": None,
            "ordering_method": "not_applicable_non_effective_deal",
        }
        candidates.append(
            _candidate(
                record_type="fill_lifecycle_link",
                identity_key=(
                    f"lifecycle_link|{row.get('identity_key')}|"
                    f"{LIFECYCLE_RULE_VERSION}|void"
                ),
                fact=link_fact,
                observed_at=observed_at,
                collection_id=collection_id,
            )
        )
    return candidates


def _cashflow_projection(
    cashflow_snapshot_rows: Iterable[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    snapshot_count = 0
    for row in cashflow_snapshot_rows:
        snapshot_count += 1
        latest[_cashflow_key(row.get("fact") or {})] = row
    rows = list(latest.values())
    return rows, {
        "cashflow_snapshot_count": snapshot_count,
        "distinct_cashflow_count": len(rows),
        "projection_rule": "latest_version_per_cashflow_key_v1",
        "raw_rows_must_not_be_summed_across_versions": True,
    }


def _signed_fill_qty(fact: Mapping[str, Any]) -> Decimal | None:
    if _economic_effect_status(fact) != "effective":
        return None
    qty = _as_decimal(fact.get("qty"))
    if qty is None:
        return None
    qty = abs(qty)
    side = str(fact.get("trd_side") or "").upper()
    if side in {"BUY", "BUY_BACK", "BUYBACK"}:
        return qty
    if side in {"SELL", "SELL_SHORT", "SHORT_SELL"}:
        return -qty
    return None


def _fill_sort_key(fact: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(fact.get("event_time_raw") or fact.get("create_time") or ""),
        str(fact.get("deal_id") or ""),
        str(fact.get("order_id") or ""),
    )


def _build_lifecycle_links(
    fill_records: Iterable[Mapping[str, Any]],
    *,
    observed_at: str,
    collection_id: str,
    current_positions: Iterable[Mapping[str, Any]],
    position_query_ok: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = list(fill_records)
    facts = [dict(row.get("fact") or {}) for row in rows]
    coverage_hash = _sha256_json(
        sorted(str(row.get("identity_key") or "") for row in rows)
    )
    grouped: dict[str, list[tuple[Mapping[str, Any], dict[str, Any]]]] = {}
    for row, fact in zip(rows, facts):
        code = str(fact.get("code") or fact.get("ticker") or "unknown")
        grouped.setdefault(code, []).append((row, fact))

    broker_qty: dict[str, Decimal] = {}
    if position_query_ok:
        for raw in current_positions:
            code = str(raw.get("code") or "")
            qty = _as_decimal(raw.get("qty")) or Decimal("0")
            side = str(raw.get("position_side") or "LONG").upper()
            broker_qty[code] = -abs(qty) if side.startswith("SHORT") else qty

    candidates: list[dict[str, Any]] = []
    closed_ids: set[str] = set()
    current: dict[str, dict[str, Any]] = {}
    ambiguous = 0
    unlinked = 0
    baseline_unknown_securities = 0
    for code, items in sorted(grouped.items()):
        items.sort(key=lambda pair: _fill_sort_key(pair[1]))
        net_delta = sum(
            (_signed_fill_qty(fact) or Decimal("0") for _, fact in items),
            Decimal("0"),
        )
        initial_qty = (
            broker_qty.get(code, Decimal("0")) - net_delta
            if position_query_ok
            else None
        )
        running = initial_qty if initial_qty is not None else Decimal("0")
        trusted = initial_qty == 0 if initial_qty is not None else False
        quarantine_reason = None if trusted else "baseline_unknown"
        if not trusted:
            baseline_unknown_securities += 1
        lifecycle_id: str | None = None
        lifecycle_start_deal_id: str | None = None
        direction: str | None = None
        prefix_identities: list[str] = [
            f"initial_qty:{_decimal_text(initial_qty) if initial_qty is not None else 'unknown'}"
        ]
        for row, fact in items:
            prefix_identities.append(str(row.get("identity_key") or ""))
            prefix_hash = _sha256_json(prefix_identities)
            delta = _signed_fill_qty(fact)
            before = running
            status = "linked"
            if delta is None or delta == 0:
                role = "unlinked_unknown_side_or_qty"
                status = "unlinked"
                unlinked += 1
                after = before
            else:
                after = before + delta
                same_direction_add = before != 0 and (before > 0) == (delta > 0)
                if not trusted:
                    status = (
                        "ambiguous_until_flat"
                        if quarantine_reason == "cross_zero"
                        else "unlinked_baseline_unknown"
                    )
                    role = (
                        "quarantined_add"
                        if same_direction_add
                        else (
                            "quarantined_flat_boundary"
                            if after == 0
                            else "quarantined_reduce_or_cross"
                        )
                    )
                    unlinked += 1
                    lifecycle_id = None
                    lifecycle_start_deal_id = None
                    direction = None
                    if (
                        after == 0
                        and position_query_ok
                        and quarantine_reason == "cross_zero"
                    ):
                        # A broker-observed flat boundary makes only subsequent
                        # fills safe to link; this boundary itself belongs to an
                        # unknown pre-window/ambiguous lifecycle.
                        trusted = True
                        quarantine_reason = None
                elif before == 0:
                    start = str(fact.get("deal_id") or row.get("identity_key"))
                    lifecycle_start_deal_id = str(fact.get("deal_id") or "") or None
                    lifecycle_id = "lifecycle|" + hashlib.sha256(
                        f"{fact.get('account_key')}|{code}|{start}".encode("utf-8")
                    ).hexdigest()[:24]
                    direction = "long" if delta > 0 else "short"
                    role = "open"
                elif same_direction_add:
                    role = "add"
                elif after == 0:
                    role = "close"
                    if lifecycle_id:
                        closed_ids.add(lifecycle_id)
                elif (before > 0 and after > 0) or (before < 0 and after < 0):
                    role = "reduce"
                else:
                    role = "crosses_zero"
                    status = "ambiguous_cross_zero"
                    ambiguous += 1
                    unlinked += 1
                    trusted = False
                    quarantine_reason = "cross_zero"

            link_fact = {
                "source": "derived_from_broker_fills",
                "rule_version": LIFECYCLE_RULE_VERSION,
                # Prefix-scoped input identity means a future fill appends only
                # its own link.  If an older fill is later backfilled, only that
                # security's affected suffix receives new link versions.
                "mapping_input_prefix_hash": prefix_hash,
                "fill_identity_key": row.get("identity_key"),
                "account_key": fact.get("account_key"),
                "code": fact.get("code"),
                "ticker": fact.get("ticker"),
                "deal_id": fact.get("deal_id"),
                "order_id": fact.get("order_id"),
                "event_time_raw": fact.get("event_time_raw"),
                "lifecycle_id": lifecycle_id,
                "lifecycle_start_deal_id": lifecycle_start_deal_id,
                "lifecycle_direction": direction,
                "event_role": role,
                "link_status": status,
                "running_qty_before": _decimal_text(before),
                "running_qty_after": _decimal_text(after),
                "history_window_initial_qty": _decimal_text(initial_qty),
                "anchor_status": (
                    "current_broker_qty_anchored"
                    if position_query_ok
                    else "position_query_unavailable"
                ),
                "ordering_method": "broker_time_raw_then_deal_id_then_order_id",
            }
            identity = (
                f"lifecycle_link|{row.get('identity_key')}|"
                f"{LIFECYCLE_RULE_VERSION}|{prefix_hash}"
            )
            candidates.append(
                _candidate(
                    record_type="fill_lifecycle_link",
                    identity_key=identity,
                    fact=link_fact,
                    observed_at=observed_at,
                    collection_id=collection_id,
                )
            )
            running = after
            if role == "close":
                lifecycle_id = None
                lifecycle_start_deal_id = None
                direction = None
            elif role == "crosses_zero":
                # A single crossing fill requires quantity splitting that the raw
                # deal does not provide.  Preserve the raw fact and quarantine the
                # derived identity rather than inventing a synthetic fill.
                lifecycle_id = None
                lifecycle_start_deal_id = None
                direction = None
        current[code] = {
            "running_qty": _decimal_text(running),
            "lifecycle_id": lifecycle_id,
            "lifecycle_start_deal_id": lifecycle_start_deal_id,
            "direction": direction,
            "link_status": (
                "linked" if trusted and lifecycle_id else (
                    "flat" if trusted and running == 0 else "unlinked_or_ambiguous"
                )
            ),
            "history_window_initial_qty": _decimal_text(initial_qty),
        }
    return candidates, {
        "rule_version": LIFECYCLE_RULE_VERSION,
        "mapping_input_hash": coverage_hash,
        "active_mapping_link_count": len(rows),
        "closed_lifecycle_count": len(closed_ids),
        "trusted_closed_lifecycle_count": len(closed_ids),
        "current_lifecycles": current,
        "ambiguous_cross_zero_count": ambiguous,
        "unlinked_count": unlinked,
        "baseline_unknown_security_count": baseline_unknown_securities,
        "position_anchor_status": (
            "current_broker_positions_used"
            if position_query_ok
            else "position_query_unavailable"
        ),
    }


def _position_qty_reconciliation(
    fill_rows: Iterable[Mapping[str, Any]],
    current_positions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    replay: dict[str, Decimal] = {}
    for row in fill_rows:
        fact = row.get("fact") or {}
        code = str(fact.get("code") or "")
        delta = _signed_fill_qty(fact)
        if code and delta is not None:
            replay[code] = replay.get(code, Decimal("0")) + delta

    broker: dict[str, Decimal] = {}
    for raw in current_positions:
        code = str(raw.get("code") or "")
        qty = _as_decimal(raw.get("qty")) or Decimal("0")
        side = str(raw.get("position_side") or "LONG").upper()
        broker[code] = -abs(qty) if side.startswith("SHORT") else qty

    mismatches = []
    for code in sorted(set(replay) | set(broker)):
        replay_qty = replay.get(code, Decimal("0"))
        broker_qty = broker.get(code, Decimal("0"))
        delta = replay_qty - broker_qty
        if delta != 0:
            mismatches.append(
                {
                    "code": code,
                    "replayed_qty": _decimal_text(replay_qty),
                    "broker_qty": _decimal_text(broker_qty),
                    "delta": _decimal_text(delta),
                    "explanation_status": (
                        "history_window_or_corporate_action_or_transfer_unexplained"
                    ),
                }
            )
    return {
        "status": "matched" if not mismatches else "mismatch_not_synthetic_fill",
        "matched_security_count": len(set(replay) | set(broker)) - len(mismatches),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "history_complete": False,
        "note": (
            "Replay excludes transfers, splits and fills before the requested history window; "
            "mismatches are surfaced and never repaired with synthetic fills."
        ),
    }


def _fill_order_reconciliation(
    effective_fill_rows: Iterable[Mapping[str, Any]],
    order_snapshot_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    fill_qty_by_order: dict[str, Decimal] = {}
    for row in effective_fill_rows:
        fact = row.get("fact") or {}
        order_id = _id_text(fact.get("order_id"))
        qty = _as_decimal(fact.get("qty"))
        if order_id and qty is not None:
            fill_qty_by_order[order_id] = fill_qty_by_order.get(
                order_id, Decimal("0")
            ) + abs(qty)

    latest_orders: dict[str, Mapping[str, Any]] = {}
    for row in order_snapshot_rows:
        fact = row.get("fact") or {}
        order_id = _id_text(fact.get("order_id"))
        if order_id:
            latest_orders[order_id] = fact
    dealt_qty_by_order = {
        order_id: abs(_as_decimal(fact.get("dealt_qty")) or Decimal("0"))
        for order_id, fact in latest_orders.items()
    }
    relevant = set(fill_qty_by_order) | {
        order_id for order_id, qty in dealt_qty_by_order.items() if qty != 0
    }
    mismatches = []
    for order_id in sorted(relevant):
        fill_qty = fill_qty_by_order.get(order_id, Decimal("0"))
        dealt_qty = dealt_qty_by_order.get(order_id, Decimal("0"))
        if fill_qty != dealt_qty:
            mismatches.append(
                {
                    "order_id": order_id,
                    "effective_fill_qty": _decimal_text(fill_qty),
                    "latest_order_dealt_qty": _decimal_text(dealt_qty),
                    "delta": _decimal_text(fill_qty - dealt_qty),
                }
            )
    return {
        "status": "matched" if not mismatches else "mismatch",
        "compared_order_count": len(relevant),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "rule": "latest_order_snapshot_vs_latest_effective_deal_versions",
    }


def _safe_query_manifest(capture: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, raw in (capture.get("queries") or {}).items():
        if not isinstance(raw, Mapping):
            continue
        out[str(name)] = {
            "status": str(raw.get("status") or "unknown"),
            "row_count": int(raw.get("row_count") or 0),
            "observed_at_utc": raw.get("observed_at_utc"),
            "error": str(raw.get("error"))[:500] if raw.get("error") else None,
        }
    return out


def _collection_manifest_fact(capture: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_base_context(capture),
        "collection_id": capture.get("collection_id"),
        "collection_started_at_utc": capture.get("collection_started_at_utc"),
        "collection_completed_at_utc": capture.get("collection_completed_at_utc"),
        "sdk_version": str(capture.get("sdk_version") or "unknown"),
        "history_start": capture.get("history_start"),
        "history_end": capture.get("history_end"),
        "cashflow_lookback_days": capture.get("cashflow_lookback_days"),
        "query_manifest": _safe_query_manifest(capture),
        "captured_row_counts": {
            "deals": len(capture.get("deals") or []),
            "orders": len(capture.get("orders") or []),
            "order_fees": len(capture.get("order_fees") or []),
            "cashflows": len(capture.get("cashflows") or []),
            "accounts": len(capture.get("accounts") or []),
            "positions": len(capture.get("positions") or []),
        },
        "commit_status": "all_surface_ledgers_committed_before_manifest",
    }


def persist_broker_execution_capture(
    capture: Mapping[str, Any],
    *,
    ledger_dir: str | Path = DEFAULT_LEDGER_DIR,
    lock_timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Validate, append and summarize one broker collection.

    The caller must provide a stable ``collection_id``.  Replaying the exact
    same capture is therefore fully idempotent, including account and flat
    position snapshots.
    """
    root = Path(ledger_dir)
    root.mkdir(parents=True, exist_ok=True)
    observed_at = str(
        capture.get("collection_completed_at_utc")
        or capture.get("collection_started_at_utc")
        or utc_now_iso()
    )
    collection_id = str(capture.get("collection_id") or "")
    if not collection_id:
        raise BrokerLedgerError("capture.collection_id is required")
    if not capture.get("account_key"):
        raise BrokerLedgerError("capture.account_key is required")

    orders = [normalize_order(row, capture) for row in capture.get("orders") or []]
    currency_by_order = {
        str(order.get("order_id")): str(order.get("currency"))
        for order in orders
        if order.get("order_id") and order.get("currency")
    }
    fills = [
        normalize_fill(
            row,
            capture,
            order_currency=currency_by_order.get(str(_id_text(row.get("order_id")))),
        )
        for row in capture.get("deals") or []
    ]
    fees = [
        normalize_order_fee(
            row,
            capture,
            order_currency=currency_by_order.get(str(_id_text(row.get("order_id")))),
        )
        for row in capture.get("order_fees") or []
    ]
    cashflows = [
        normalize_cashflow(row, capture) for row in capture.get("cashflows") or []
    ]

    fill_candidates = []
    for fact in fills:
        fill_candidates.append(
            _candidate(
                record_type="broker_deal_snapshot",
                identity_key=_fill_identity(fact),
                fact=fact,
                observed_at=observed_at,
                collection_id=collection_id,
            )
        )
    order_candidates = [
        _candidate(
            record_type="broker_order_snapshot",
            identity_key=_versioned_identity("order", fact, fact.get("order_id")),
            fact=fact,
            observed_at=observed_at,
            collection_id=collection_id,
        )
        for fact in orders
    ]
    fee_candidates = [
        _candidate(
            record_type="broker_order_fee_snapshot",
            identity_key=_versioned_identity("order_fee", fact, fact.get("order_id")),
            fact=fact,
            observed_at=observed_at,
            collection_id=collection_id,
        )
        for fact in fees
    ]
    cash_candidates = []
    for fact in cashflows:
        cash_candidates.append(
            _candidate(
                record_type="broker_cashflow_snapshot",
                identity_key=_cashflow_identity(fact),
                fact=fact,
                observed_at=observed_at,
                collection_id=collection_id,
            )
        )

    account_candidates = []
    if _query_ok(capture, "account") and bool(capture.get("accounts")):
        fact = _account_snapshot_fact(capture)
        account_candidates.append(
            _candidate(
                record_type="broker_account_snapshot",
                identity_key=_snapshot_identity("account_snapshot", capture),
                fact=fact,
                observed_at=observed_at,
                collection_id=collection_id,
            )
        )
    position_candidates = []
    if _query_ok(capture, "positions"):
        fact = _position_snapshot_fact(capture)
        position_candidates.append(
            _candidate(
                record_type="broker_position_snapshot",
                identity_key=_snapshot_identity("position_snapshot", capture),
                fact=fact,
                observed_at=observed_at,
                collection_id=collection_id,
            )
        )
    collection_fact = _collection_manifest_fact(capture)
    collection_candidates = [
        _candidate(
            record_type="broker_collection_manifest",
            identity_key=(
                f"collection|{capture.get('account_key')}|{collection_id}"
            ),
            fact=collection_fact,
            observed_at=observed_at,
            collection_id=collection_id,
        )
    ]

    paths = {name: root / filename for name, filename in LEDGER_FILENAMES.items()}
    with _exclusive_ledger_lock(root / ".ledger.lock", lock_timeout_seconds):
        # Plan every raw surface first.  A corruption/conflict therefore aborts
        # before any canonical ledger bytes are changed.
        plans = {
            "fills": _plan_append(paths["fills"], fill_candidates),
            "orders": _plan_append(paths["orders"], order_candidates),
            "order_fees": _plan_append(paths["order_fees"], fee_candidates),
            "cashflows": _plan_append(paths["cashflows"], cash_candidates),
            "accounts": _plan_append(paths["accounts"], account_candidates),
            "positions": _plan_append(paths["positions"], position_candidates),
            "collections": _plan_append(paths["collections"], collection_candidates),
        }
        established_account_keys = {
            str((row.get("fact") or {}).get("account_key"))
            for plan in plans.values()
            for row in plan.existing_rows
            if (row.get("fact") or {}).get("account_key")
        }
        capture_account_key = str(capture.get("account_key"))
        if established_account_keys and established_account_keys != {
            capture_account_key
        }:
            raise BrokerLedgerConflictError(
                "broker ledger directory is account-scoped; established="
                f"{sorted(established_account_keys)!r}, capture={capture_account_key!r}"
            )
        effective_fill_rows, excluded_deal_rows, deal_projection = _economic_fill_projection(
            plans["fills"].final_rows
        )
        _, cashflow_projection = _cashflow_projection(
            plans["cashflows"].final_rows
        )
        lifecycle_candidates, lifecycle_summary = _build_lifecycle_links(
            effective_fill_rows,
            observed_at=observed_at,
            collection_id=collection_id,
            current_positions=(capture.get("positions") or []),
            position_query_ok=_query_ok(capture, "positions"),
        )
        lifecycle_candidates.extend(
            _build_void_lifecycle_links(
                excluded_deal_rows,
                observed_at=observed_at,
                collection_id=collection_id,
            )
        )
        lifecycle_summary["void_latest_deal_link_count"] = len(
            excluded_deal_rows
        )
        lifecycle_summary["deal_projection"] = deal_projection
        plans["lifecycle_links"] = _plan_append(
            paths["lifecycle_links"], lifecycle_candidates
        )

        # All validation passed.  Cross-file atomicity is intentionally obtained
        # through idempotent recovery: if a later file write fails, the next run
        # skips already committed identities and completes the remainder.
        for name in LEDGER_FILENAMES:
            _write_plan(plans[name])

        query_manifest = _safe_query_manifest(capture)
        query_failures = sorted(
            name
            for name, row in query_manifest.items()
            if row.get("status") not in {"ok", "partial", "skipped"}
        )
        query_partials = sorted(
            name
            for name, row in query_manifest.items()
            if row.get("status") == "partial"
        )
        snapshot_gaps = []
        if not (_query_ok(capture, "account") and bool(capture.get("accounts"))):
            snapshot_gaps.append("current_account_snapshot_unavailable")
        if not _query_ok(capture, "positions"):
            snapshot_gaps.append("current_position_snapshot_unavailable")
        fill_rows = effective_fill_rows
        fee_rows = plans["order_fees"].final_rows
        latest_fee_by_order: dict[str, Mapping[str, Any]] = {}
        for row in fee_rows:
            fact = row.get("fact") or {}
            if fact.get("order_id"):
                latest_fee_by_order[str(fact.get("order_id"))] = fact
        fee_order_ids = {
            order_id
            for order_id, fact in latest_fee_by_order.items()
            if fact.get("fee_amount") is not None
        }
        fill_order_ids = {
            str((row.get("fact") or {}).get("order_id"))
            for row in fill_rows
            if (row.get("fact") or {}).get("order_id")
        }
        fill_times = sorted(
            str((row.get("fact") or {}).get("event_time_raw"))
            for row in fill_rows
            if (row.get("fact") or {}).get("event_time_raw")
        )
        if _query_ok(capture, "positions"):
            qty_reconciliation = _position_qty_reconciliation(
                fill_rows,
                capture.get("positions") or [],
            )
        else:
            qty_reconciliation = {
                "status": "unavailable_position_query_failed",
                "matched_security_count": 0,
                "mismatch_count": 0,
                "mismatches": [],
                "history_complete": False,
                "note": "No quantity comparison was attempted because the broker position query failed.",
            }
        fill_order_reconciliation = _fill_order_reconciliation(
            fill_rows,
            plans["orders"].final_rows,
        )
        counts = {
            name: {
                "rows_before": len(plan.existing_rows),
                "rows_appended": len(plan.new_rows),
                "rows_total": len(plan.final_rows),
                "head_record_hash": (
                    plan.final_rows[-1].get("record_hash") if plan.final_rows else None
                ),
            }
            for name, plan in plans.items()
        }
        latest_account = (
            plans["accounts"].final_rows[-1].get("fact")
            if plans["accounts"].final_rows
            else None
        )
        latest_positions = (
            plans["positions"].final_rows[-1].get("fact")
            if plans["positions"].final_rows
            else None
        )
        latest_account_is_current = bool(
            latest_account and latest_account.get("collection_id") == collection_id
        )
        latest_positions_is_current = bool(
            latest_positions and latest_positions.get("collection_id") == collection_id
        )
        state = {
            "schema_version": SCHEMA_VERSION,
            "rule_version": RULE_VERSION,
            "generated_at_utc": utc_now_iso(),
            "latest_collection_id": collection_id,
            "latest_collection_started_at_utc": capture.get(
                "collection_started_at_utc"
            ),
            "latest_collection_completed_at_utc": capture.get(
                "collection_completed_at_utc"
            ),
            "account_key": capture.get("account_key"),
            "security_firm": capture.get("security_firm"),
            "trade_environment": capture.get("trade_environment"),
            "sdk_version": capture.get("sdk_version"),
            "status": (
                "partial_collection"
                if query_failures or query_partials or snapshot_gaps
                else (
                    "ok_with_reconciliation_gaps"
                    if qty_reconciliation["mismatch_count"]
                    or fill_order_reconciliation["mismatch_count"]
                    else "ok"
                )
            ),
            "query_manifest": query_manifest,
            "query_failures": query_failures,
            "query_partials": query_partials,
            "snapshot_gaps": snapshot_gaps,
            "ledgers": counts,
            "coverage": {
                "requested_history_start": capture.get("history_start"),
                "requested_history_end": capture.get("history_end"),
                "first_fill_time_raw": fill_times[0] if fill_times else None,
                "last_fill_time_raw": fill_times[-1] if fill_times else None,
                "history_complete": False,
                "historical_post_fill_account_state": "unavailable",
                "account_snapshot_coverage_begins": (
                    (plans["accounts"].final_rows[0].get("fact") or {}).get(
                        "collection_completed_at_utc"
                    )
                    if plans["accounts"].final_rows
                    else None
                ),
            },
            "fee_coverage": {
                "fill_order_count": len(fill_order_ids),
                "orders_with_reported_fee": len(fill_order_ids & fee_order_ids),
                "orders_without_reported_fee": sorted(fill_order_ids - fee_order_ids),
                "fee_scope": "order_level",
                "fill_fee_allocation": "not_performed",
            },
            "deal_projection": deal_projection,
            "cashflow_projection": cashflow_projection,
            "lifecycle_replay": lifecycle_summary,
            "position_qty_reconciliation": qty_reconciliation,
            "fill_order_reconciliation": fill_order_reconciliation,
            "latest_account_snapshot": latest_account,
            "latest_account_snapshot_is_current_collection": latest_account_is_current,
            "latest_position_snapshot": latest_positions,
            "latest_position_snapshot_is_current_collection": latest_positions_is_current,
            "production_impact": (
                "measurement_only_no_orders_no_strategy_no_ranking_no_sizing"
            ),
        }
        atomic_write_json(state, root / "state.json", indent=2, ensure_ascii=True)
        write_broker_ledger_health(
            capture,
            ledger_dir=root,
            status="healthy",
        )

    return {
        "status": state["status"],
        "ledger_dir": str(root),
        "state_path": str(root / "state.json"),
        "collection_id": collection_id,
        "ledgers": counts,
        "state": state,
    }


def validate_broker_execution_ledger(
    ledger_dir: str | Path = DEFAULT_LEDGER_DIR,
) -> dict[str, Any]:
    """Strictly validate every canonical JSONL chain without writing."""
    root = Path(ledger_dir)
    result = {}
    for name, filename in LEDGER_FILENAMES.items():
        _, rows = _strict_read_chain(root / filename)
        result[name] = {
            "rows": len(rows),
            "head_record_hash": rows[-1].get("record_hash") if rows else None,
        }
    non_manifest_rows = sum(
        row["rows"] for name, row in result.items() if name != "collections"
    )
    if non_manifest_rows and result["collections"]["rows"] == 0:
        raise BrokerLedgerCorruptionError(
            "non-empty broker ledgers have no committed collection manifest"
        )
    return {"status": "valid", "ledgers": result}


def write_broker_ledger_health(
    capture: Mapping[str, Any],
    *,
    ledger_dir: str | Path = DEFAULT_LEDGER_DIR,
    status: str,
    error: BaseException | None = None,
) -> dict[str, Any]:
    """Write current collector health outside the canonical hash chains.

    This remains writable even when a canonical JSONL chain is damaged, so a
    holdings refresh can proceed without silently hiding the audit failure.
    """
    root = Path(ledger_dir)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "generated_at_utc": utc_now_iso(),
        "status": str(status),
        "collection_id": capture.get("collection_id"),
        "account_key": capture.get("account_key"),
        "query_manifest": _safe_query_manifest(capture),
        "error_type": type(error).__name__ if error else None,
        "error": str(error)[:1000] if error else None,
        "holdings_refresh_policy": "continue_with_current_broker_positions_and_surface_alert",
        "production_impact": "measurement_failure_visible_no_strategy_or_order_change",
    }
    atomic_write_json(payload, root / "health.json", indent=2, ensure_ascii=True)
    return payload
