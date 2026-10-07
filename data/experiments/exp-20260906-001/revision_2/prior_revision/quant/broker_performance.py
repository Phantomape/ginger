"""Read-only, fee-covered cash trading PnL from committed broker facts.

This measures a covered subset of closed lifecycles, not strategy performance or
total account return. No ledger, state, order, or network operation is performed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import math
from pathlib import Path
import re
from typing import Any

try:
    import broker_execution_ledger as ledger
except ImportError:  # pragma: no cover - package-style imports
    from quant import broker_execution_ledger as ledger


DEFAULT_LEDGER_DIR = ledger.DEFAULT_LEDGER_DIR
RULE_VERSION = "broker_closed_lifecycle_performance_v1"
_COMMITTED = "all_surface_ledgers_committed_before_manifest"
_STOCK_CODE = re.compile(r"US\.[A-Z]{1,6}(?:[.-][A-Z]{1,2})?\Z")
_BUY = {"BUY", "BUY_BACK", "BUYBACK"}
_SELL = {"SELL", "SELL_SHORT", "SHORT_SELL"}


def unavailable_broker_performance(reason: str) -> dict[str, Any]:
    """Stable empty shape also usable by the daily reporting error boundary."""
    return {
        "status": "unavailable",
        "rule_version": RULE_VERSION,
        "lifecycle_rule_version": ledger.LIFECYCLE_RULE_VERSION,
        "source_hashes": {name: None for name in ledger.LEDGER_FILENAMES.values()},
        "source_as_of": None,
        "counts": {name: 0 for name in (
            "committed_collection_count", "effective_fill_count", "cancelled_fill_count",
            "unknown_status_fill_count", "uncommitted_row_count", "closed_lifecycle_count",
            "evaluated_lifecycle_count", "excluded_lifecycle_count", "open_lifecycle_count",
            "unlinked_fill_count",
        )},
        "pnl_by_currency": {"USD": {
            "gross_trading_pnl_before_order_fees": None,
            "order_fee_total": None,
            "net_trading_pnl_after_order_fees": None,
            "evaluated_lifecycle_count": 0,
        }},
        "coverage_reasons": {reason: 1} if reason else {},
        "strategy_attribution_status": "unavailable_no_decision_order_lineage",
        "limitations": [
            "Only validated, fully closed US cash stock/ETF lifecycles with complete order fees are summed.",
            "Gross and net values cover the same evaluated subset; excluded trades are not zero profit.",
            "Excludes open-position mark-to-market, financing, borrow costs, dividends, FX and cash transfers.",
            "Not total account return, strategy attribution, TWR, Sharpe or replacement value.",
            "Broker event timestamps have unspecified timezone; no UTC trade-time claim is made.",
            "History before the broker query window and corporate-action adjustments are not reconstructed.",
        ],
        "trade_enabled": False,
    }


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and math.isfinite(float(number)) else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _order_key(fact: dict) -> tuple:
    return fact.get("account_key"), fact.get("order_id")


def _link_key(fact: dict) -> tuple:
    return fact.get("account_key"), fact.get("deal_id")


def _load_committed(root: Path, result: dict) -> dict[str, list[dict]]:
    raw_bytes = {}
    rows_by_name = {}
    # Check the exact bytes again after the multi-file read. A concurrent append
    # yields unavailable rather than a mixture of two collection snapshots.
    for name, filename in ledger.LEDGER_FILENAMES.items():
        path = root / filename
        raw_bytes[name] = path.read_bytes() if path.exists() else None
        result["source_hashes"][filename] = (
            hashlib.sha256(raw_bytes[name]).hexdigest() if raw_bytes[name] is not None else None
        )
    for name, filename in ledger.LEDGER_FILENAMES.items():
        _, rows_by_name[name] = ledger._strict_read_chain(root / filename)
    for name, filename in ledger.LEDGER_FILENAMES.items():
        path = root / filename
        if (path.read_bytes() if path.exists() else None) != raw_bytes[name]:
            raise ledger.BrokerLedgerCorruptionError("source_changed_during_read")
    if any(not isinstance(row.get("fact"), dict) for rows in rows_by_name.values() for row in rows):
        raise ledger.BrokerLedgerCorruptionError("invalid_fact_shape")
    manifests = [row for row in rows_by_name["collections"]
                 if row["fact"].get("commit_status") == _COMMITTED
                 and row.get("collection_id")
                 and row["fact"].get("collection_id") == row["collection_id"]]
    committed = {(row["fact"].get("account_key"), row["collection_id"]) for row in manifests}
    visible = {}
    for name, rows in rows_by_name.items():
        visible[name] = [row for row in rows
                         if (row["fact"].get("account_key"), row.get("collection_id")) in committed]
        if name != "collections":
            result["counts"]["uncommitted_row_count"] += len(rows) - len(visible[name])
    if len({account for account, _ in committed}) > 1:
        raise ledger.BrokerLedgerCorruptionError("mixed_account_scope")
    result["counts"]["committed_collection_count"] = len(committed)
    if manifests:
        result["source_as_of"] = manifests[-1]["fact"].get("collection_completed_at_utc")
    return visible


def _fill_errors(row: dict, link: dict | None, prefix: list[str]) -> set[str]:
    fact = row["fact"]
    errors = set()
    qty, price = _decimal(fact.get("qty")), _decimal(fact.get("price"))
    if not fact.get("deal_id") or not fact.get("order_id"):
        errors.add("missing_fill_identity")
    if not _STOCK_CODE.fullmatch(str(fact.get("code") or "")) or fact.get("deal_market") != "US":
        errors.add("unsupported_instrument")
    if fact.get("currency") != "USD":
        errors.add("unsupported_or_unknown_fill_currency")
    if qty is None or qty <= 0 or price is None or price <= 0 or fact.get("trd_side") not in _BUY | _SELL:
        errors.add("invalid_fill_quantity_price_or_side")
    else:
        cash = qty * price * (-1 if fact["trd_side"] in _BUY else 1)
        if _decimal(fact.get("effective_gross_trade_cash_flow_before_order_fee")) != cash:
            errors.add("fill_cash_flow_mismatch")
    if link is None:
        return errors | {"missing_lifecycle_link"}
    if link.get("rule_version") != ledger.LIFECYCLE_RULE_VERSION:
        errors.add("unsupported_lifecycle_rule")
    if (link.get("fill_identity_key") != row["identity_key"]
            or any(link.get(key) != fact.get(key) for key in ("account_key", "deal_id", "order_id", "code"))):
        errors.add("latest_link_fill_mismatch")
    if link.get("link_status") != "linked":
        errors.add(str(link.get("link_status") or "unlinked"))
    if link.get("anchor_status") != "current_broker_qty_anchored" or _decimal(link.get("history_window_initial_qty")) != 0:
        errors.add("unknown_position_baseline")
    if link.get("mapping_input_prefix_hash") != ledger._sha256_json(["initial_qty:0", *prefix]):
        errors.add("lifecycle_input_prefix_mismatch")
    return errors


def _lifecycle_errors(items: list[tuple[dict, dict]], fill_errors: dict) -> set[str]:
    errors = set().union(*(fill_errors[row["identity_key"]] for row, _ in items))
    first, last = items[0][1], items[-1][1]
    if (first.get("event_role") != "open" or _decimal(first.get("running_qty_before")) != 0
            or last.get("event_role") != "close" or _decimal(last.get("running_qty_after")) != 0):
        errors.add("incomplete_lifecycle")
    running = Decimal("0")
    for index, (row, link) in enumerate(items):
        qty = _decimal(row["fact"].get("qty"))
        if qty is None or row["fact"].get("trd_side") not in _BUY | _SELL:
            errors.add("invalid_lifecycle_quantity")
            continue
        delta = qty if row["fact"]["trd_side"] in _BUY else -qty
        after = running + delta
        if (_decimal(link.get("running_qty_before")) != running
                or _decimal(link.get("running_qty_after")) != after
                or running * after < 0 or (after == 0 and index != len(items) - 1)):
            errors.add("invalid_lifecycle_quantity_path")
        running = after
    return errors


def compute_broker_performance(ledger_dir: str | Path = DEFAULT_LEDGER_DIR) -> dict[str, Any]:
    """Return deterministic JSON-safe performance over strictly covered lifecycles.

    Missing/corrupt sources return null PnL plus coverage reasons. Version order
    is append order within each validated chain, after collection visibility.
    """
    result = unavailable_broker_performance("")
    try:
        visible = _load_committed(Path(ledger_dir), result)
    except (ledger.BrokerLedgerError, OSError, UnicodeError) as exc:
        reason = "source_changed_during_read" if str(exc) == "source_changed_during_read" else "ledger_corrupt_or_unreadable"
        result["coverage_reasons"] = {reason: 1}
        return result
    counts = result["counts"]
    reasons = Counter()
    if counts["uncommitted_row_count"]:
        reasons["uncommitted_rows"] = counts["uncommitted_row_count"]
    if not counts["committed_collection_count"]:
        reasons["no_committed_collections"] += 1
        result["coverage_reasons"] = dict(reasons)
        return result

    latest = {ledger._deal_key(row["fact"]): row for row in visible["fills"]}
    effective = []
    for row in latest.values():
        status = row["fact"].get("deal_status") or row["fact"].get("status")
        if status in {"OK", "CHANGED"}:
            effective.append(row)
        elif status == "CANCELLED":
            counts["cancelled_fill_count"] += 1
        else:
            counts["unknown_status_fill_count"] += 1
    counts["effective_fill_count"] = len(effective)
    if counts["unknown_status_fill_count"]:
        reasons["unknown_status_fills"] = counts["unknown_status_fill_count"]
    effective.sort(key=lambda row: ledger._fill_sort_key(row["fact"]))
    links = {_link_key(row["fact"]): row["fact"] for row in visible["lifecycle_links"]}
    orders = {_order_key(row["fact"]): row["fact"] for row in visible["orders"]}
    fees = {_order_key(row["fact"]): row["fact"] for row in visible["order_fees"]}
    groups, order_fills, prefixes = defaultdict(list), defaultdict(list), defaultdict(list)
    fill_errors = {}
    fill_lifecycles = {}
    for row in effective:
        fact = row["fact"]
        prefix = prefixes[(fact.get("account_key"), fact.get("code"))]
        prefix.append(row["identity_key"])
        link = links.get(_link_key(fact))
        errors = _fill_errors(row, link, prefix)
        fill_errors[row["identity_key"]] = errors
        lifecycle_id = (link or {}).get("lifecycle_id")
        fill_lifecycles[row["identity_key"]] = lifecycle_id
        order_fills[_order_key(fact)].append(row)
        if lifecycle_id:
            groups[lifecycle_id].append((row, link))
        else:
            counts["unlinked_fill_count"] += 1
            for reason in errors or {"missing_lifecycle_id"}:
                reasons[reason + "_fills"] += 1

    gross_total, fee_total = Decimal("0"), Decimal("0")
    for lifecycle_id, items in groups.items():
        if not any(link.get("event_role") == "close" for _, link in items):
            counts["open_lifecycle_count"] += 1
            reasons["open_or_unclosed_lifecycles"] += 1
            for reason in set().union(*(fill_errors[row["identity_key"]] for row, _ in items)):
                reasons[reason + "_lifecycles"] += 1
            continue
        counts["closed_lifecycle_count"] += 1
        errors = _lifecycle_errors(items, fill_errors)
        lifecycle_fees = Decimal("0")
        for order_key in {_order_key(row["fact"]) for row, _ in items}:
            fills = order_fills[order_key]
            order, fee = orders.get(order_key), fees.get(order_key)
            if any(fill_lifecycles[row["identity_key"]] != lifecycle_id or fill_errors[row["identity_key"]] for row in fills):
                errors.add("order_spans_untrusted_or_other_lifecycle")
            quantities = [_decimal(row["fact"].get("qty")) for row in fills]
            if order is None:
                errors.add("missing_order_snapshot")
            elif (any(qty is None for qty in quantities)
                  or _decimal(order.get("dealt_qty")) != sum((qty for qty in quantities if qty is not None), Decimal("0"))):
                errors.add("order_quantity_mismatch")
            if order and order.get("currency") != "USD":
                errors.add("unsupported_or_unknown_order_currency")
            if fee is None or fee.get("fee_status") != "reported" or _decimal(fee.get("fee_amount")) is None:
                errors.add("missing_order_fee")
            elif fee.get("currency") != "USD":
                errors.add("unsupported_or_unknown_fee_currency")
            else:
                lifecycle_fees += _decimal(fee["fee_amount"])
        if errors:
            counts["excluded_lifecycle_count"] += 1
            for reason in errors:
                reasons[reason + "_lifecycles"] += 1
            continue
        counts["evaluated_lifecycle_count"] += 1
        gross_total += sum((
            _decimal(row["fact"]["effective_gross_trade_cash_flow_before_order_fee"])
            for row, _ in items
        ), Decimal("0"))
        fee_total += lifecycle_fees

    evaluated = counts["evaluated_lifecycle_count"]
    if evaluated:
        result["pnl_by_currency"]["USD"] = {
            "gross_trading_pnl_before_order_fees": round(float(gross_total), 8),
            "order_fee_total": round(float(fee_total), 8),
            "net_trading_pnl_after_order_fees": round(float(gross_total - fee_total), 8),
            "evaluated_lifecycle_count": evaluated,
        }
        result["status"] = "partial" if reasons else "ok"
    else:
        reasons["no_evaluable_closed_lifecycles"] += 1
    result["coverage_reasons"] = dict(sorted(reasons.items()))
    return result
