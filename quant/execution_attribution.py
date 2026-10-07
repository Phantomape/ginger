"""Prospective machine-advice identities; never an order submission adapter.

Only a broker's exact remark can associate an order with a frozen decision.
The clock proves local observation order, not the broker's execution timezone.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import uuid

try:
    import broker_execution_ledger as ledger
except ImportError:
    from quant import broker_execution_ledger as ledger


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ledger.DATA_ROOT / "live_pilot" / "execution_attribution"
RULE_VERSION = "prospective_machine_decision_attribution_v1"
TOKEN = re.compile(r"GNG-[0-9a-f]{28}\Z")


def _number(value):
    try:
        value = Decimal(str(value))
        return value if value.is_finite() and value > 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _time(value):
    value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("observation clock must have a timezone")
    return value.astimezone(timezone.utc)


def _validate_decision(payload):
    if not isinstance(payload, dict):
        raise ValueError("decision payload must be an object")
    if not isinstance(payload.get("as_of"), str) or date.fromisoformat(payload["as_of"]).isoformat() != payload["as_of"]:
        raise ValueError("as_of must be an ISO date")
    hashes = payload.get("policy_hashes")
    kind = payload.get("action_kind")
    if (not isinstance(payload.get("source_ref"), str) or not payload["source_ref"].strip()
            or not isinstance(hashes, dict) or not hashes
            or any(not isinstance(k, str) or not k or not isinstance(v, str)
                   or not re.fullmatch(r"[0-9a-f]{64}", v) for k, v in hashes.items())
            or not isinstance(payload.get("source_payload"), dict) or not payload["source_payload"]
            or kind not in {"entry", "add_on", "bracket"}
            or payload.get("side") != ("SELL" if kind == "bracket" else "BUY")
            or not isinstance(payload.get("account_key"), str) or not payload["account_key"]
            or not isinstance(payload.get("strategy_id"), str) or not payload["strategy_id"]
            or not re.fullmatch(r"US\.[A-Z]{1,6}(?:[.-][A-Z]{1,2})?", str(payload.get("code", "")))
            or not _number(payload.get("quantity"))
            or payload.get("stage") != "machine_advice_not_order_authorization"
            or payload.get("trade_enabled") is not False):
        raise ValueError("incomplete or invalid decision contract")


def _read(directory):
    path = Path(directory) / "decisions.jsonl"
    before = path.read_bytes() if path.exists() else None
    _, rows = ledger._strict_read_chain(path)
    if (path.read_bytes() if path.exists() else None) != before:
        raise ledger.BrokerLedgerCorruptionError("decision_source_changed_during_read")
    tokens = set()
    for row in rows:
        fact = row["fact"]
        payload = fact.get("decision")
        try:
            _validate_decision(payload)
        except (ValueError, TypeError) as exc:
            raise ledger.BrokerLedgerCorruptionError("invalid_decision_contract") from exc
        token = fact.get("broker_remark", "")
        if (row.get("record_type") != "machine_execution_decision"
                or row.get("observed_at_utc") != fact.get("recorded_at")
                or fact.get("rule_version") != RULE_VERSION or not isinstance(payload, dict)
                or fact.get("decision_id") != ledger._sha256_json(payload)
                or row["identity_key"] != fact["decision_id"]
                or not TOKEN.fullmatch(token) or token in tokens
                or payload.get("stage") != "machine_advice_not_order_authorization"
                or payload.get("trade_enabled") is not False
                or not payload.get("account_key") or not payload.get("strategy_id")
                or payload.get("side") not in {"BUY", "SELL"}
                or not _number(payload.get("quantity"))):
            raise ledger.BrokerLedgerCorruptionError("invalid_decision_fact")
        _time(fact["recorded_at"])
        tokens.add(token)
    return rows


def record_decisions(plans, *, as_of, account_key, source_ref, policy_hashes,
                     directory=DEFAULT_DIR, recorded_at=None):
    """Freeze complete advice payloads. Identical repeats retain the first clock/token."""
    if not account_key or not source_ref or not policy_hashes:
        raise ValueError("account, source identity and policy hashes are required")
    stamp = recorded_at or ledger.utc_now_iso()
    _time(stamp)
    path = Path(directory) / "decisions.jsonl"
    with ledger._exclusive_ledger_lock(Path(directory) / ".writer.lock"):
        existing = {r["identity_key"]: r for r in _read(directory)}
        candidates, selected = [], []
        for plan in plans:
            if (not plan.get("strategy_id") or plan.get("side") not in {"BUY", "SELL"}
                    or not re.fullmatch(r"US\.[A-Z]{1,6}(?:[.-][A-Z]{1,2})?", str(plan.get("code", "")))
                    or not _number(plan.get("quantity"))):
                raise ValueError("incomplete machine advice")
            payload = json.loads(ledger._canonical_json({
                **plan, "as_of": as_of, "account_key": account_key,
                "source_ref": source_ref, "policy_hashes": policy_hashes,
                "stage": "machine_advice_not_order_authorization", "trade_enabled": False,
            }))
            _validate_decision(payload)
            identity = ledger._sha256_json(payload)
            if identity in existing:
                fact = existing[identity]["fact"]
            else:
                fact = {"rule_version": RULE_VERSION, "decision_id": identity,
                        "decision": payload, "recorded_at": stamp,
                        "broker_remark": "GNG-" + uuid.uuid4().hex[:28]}
                candidate = ledger._candidate(record_type="machine_execution_decision",
                    identity_key=identity, conflict_key=identity, fact=fact,
                    observed_at=stamp, collection_id=identity)
                candidates.append(candidate)
                existing[identity] = candidate
            selected.append(fact)
        plan = ledger._plan_append(path, candidates)
        ledger._write_plan(plan)
    return {"status": "ok", "rule_version": RULE_VERSION, "trade_enabled": False,
            "stage": "machine_advice_not_order_authorization", "as_of": as_of,
            "rows_appended": len(plan.new_rows), "decisions": selected}


def resolve_order_bindings(visible, *, directory=DEFAULT_DIR):
    """Read only. Require exact identity on every committed version of the order."""
    rows = _read(directory)
    decisions = {r["fact"]["broker_remark"]: r["fact"] for r in rows}
    orders = defaultdict(list)
    for row in visible["orders"]:
        f = row["fact"]
        orders[(f.get("account_key"), f.get("order_id"))].append(row)
    token_orders = defaultdict(set)
    for key, versions in orders.items():
        for row in versions:
            token = row["fact"].get("remark")
            if token in decisions:
                token_orders[token].add(key)
    missing_tokens = {r["fact"].get("remark") for versions in orders.values() for r in versions
                      if TOKEN.fullmatch(str(r["fact"].get("remark") or ""))
                      and r["fact"].get("remark") not in decisions}
    if missing_tokens:
        raise ledger.BrokerLedgerCorruptionError("broker_remark_references_missing_decision")
    anchored_collections = {r["collection_id"] for r in visible["collections"]
                           if r["fact"].get("surface_commit_anchors")}
    bindings, blockers = {}, Counter()
    for key, versions in orders.items():
        token = versions[-1]["fact"].get("remark")
        snapshot = decisions.get(token)
        if snapshot is None:
            blockers["missing_or_unknown_decision_remark"] += 1
            continue
        decision = snapshot["decision"]
        if len(token_orders[token]) != 1:
            blockers["remark_reused_for_multiple_orders"] += 1
            continue
        errors = set()
        for row in versions:
            fact = row["fact"]
            if row.get("collection_id") not in anchored_collections:
                errors.add("order_version_without_commit_anchor")
            if fact.get("remark") != token:
                errors.add("remark_not_present_on_all_order_versions")
            if (key[0] != decision["account_key"] or fact.get("code") != decision["code"]
                    or fact.get("trd_side") != decision["side"]):
                errors.add("order_identity_mismatch")
            if _number(fact.get("qty")) != _number(decision["quantity"]):
                errors.add("order_quantity_changed")
            try:
                if _time(row["observed_at_utc"]) <= _time(snapshot["recorded_at"]):
                    errors.add("order_observed_before_decision")
            except (ValueError, KeyError, TypeError):
                errors.add("missing_observation_clock")
        if errors:
            blockers.update(errors)
        else:
            bindings[key] = snapshot
    return bindings, {"status": "ok" if rows else "no_recorded_decisions",
        "decision_count": len(rows), "broker_order_count": len(orders),
        "bound_order_count": len(bindings), "unbound_order_count": len(orders) - len(bindings),
        "blockers": dict(sorted(blockers.items())),
        "binding_basis": "exact_broker_remark_and_prior_local_decision_observation",
        "broker_event_timezone_verified": False,
        "decision_ledger_sha256": hashlib.sha256((Path(directory) / "decisions.jsonl").read_bytes()).hexdigest() if rows else None}


def _open_owners(visible, bindings):
    """Carry entry ownership only through a fully linked, explicitly bound open path."""
    latest_fills = {ledger._deal_key(r["fact"]): r for r in visible["fills"]}
    links = {(r["fact"].get("account_key"), r["fact"].get("deal_id")): r["fact"]
             for r in visible["lifecycle_links"]}
    paths = defaultdict(list)
    for row in latest_fills.values():
        f = row["fact"]
        if f.get("deal_status") not in {"OK", "CHANGED"}:
            continue
        link = links.get((f.get("account_key"), f.get("deal_id")), {})
        paths[(f.get("account_key"), f.get("code"))].append((row, link))
    owners = {}
    position_rows = visible["positions"][-1]["fact"].get("positions", []) if visible["positions"] else []
    positions = {p.get("code"): _number(p.get("qty")) for p in position_rows}
    try:
        from broker_performance import _fill_errors
    except ImportError:
        from quant.broker_performance import _fill_errors
    for key, path in paths.items():
        path.sort(key=lambda item: ledger._fill_sort_key(item[0]["fact"]))
        latest_id = path[-1][1].get("lifecycle_id")
        active = [(r, l) for r, l in path if l.get("lifecycle_id") == latest_id]
        if (not latest_id or active[0][1].get("event_role") != "open"
                or active[-1][1].get("event_role") == "close"):
            continue
        snapshots, prefix, running = [], [], Decimal("0")
        failed = False
        for row, link in path:
            prefix.append(row["identity_key"])
            if link.get("lifecycle_id") != latest_id:
                continue
            f = row["fact"]
            snap = bindings.get((f.get("account_key"), f.get("order_id")))
            quantity = _number(f.get("qty"))
            if (snap is None or _fill_errors(row, link, prefix) or quantity is None
                    or snap["decision"]["code"] != f.get("code")
                    or snap["decision"]["side"] != f.get("trd_side")):
                failed = True
                break
            after = running + quantity * (1 if f["trd_side"] == "BUY" else -1)
            if (Decimal(str(link.get("running_qty_before"))) != running
                    or Decimal(str(link.get("running_qty_after"))) != after or after <= 0):
                failed = True
                break
            running = after
            snapshots.append(snap)
        if not failed and snapshots:
            strategies = {s["decision"]["strategy_id"] for s in snapshots}
            if len(strategies) == 1 and positions.get(key[1]) == running:
                owners[key[1]] = (next(iter(strategies)), sorted({s["decision_id"] for s in snapshots}), running)
    return owners


def build_daily_attribution_decisions(*, as_of, signals, pilot_signals, addon_actions,
                                     bracket_orders, broker_dir=ledger.DEFAULT_LEDGER_DIR,
                                     directory=DEFAULT_DIR, refresh_status=None,
                                     capture_not_before=None):
    """Called after machine advice is assembled; does not mutate any input or trade."""
    try:
        from broker_performance import _load_committed, unavailable_broker_performance
    except ImportError:
        from quant.broker_performance import _load_committed, unavailable_broker_performance
    summary = unavailable_broker_performance("")
    if refresh_status != "refreshed" or not capture_not_before:
        raise ValueError("successful broker refresh from this run required")
    visible = _load_committed(Path(broker_dir), summary)
    age = _time(ledger.utc_now_iso()) - _time(summary["source_as_of"])
    if age < timedelta(0) or age > timedelta(hours=24):
        raise ValueError("broker capture is stale or from the future")
    if _time(summary["source_as_of"]) < _time(capture_not_before):
        raise ValueError("economic queries predate this run's broker refresh")
    latest_manifest = visible["collections"][-1]["fact"] if visible["collections"] else {}
    if (not latest_manifest.get("surface_commit_anchors")
            or (latest_manifest.get("query_manifest", {}).get("positions") or {}).get("status") != "ok"):
        raise ValueError("current committed positions and surface anchors required")
    fill_ids = {r["identity_key"] for r in visible["fills"]}
    if any(r["fact"].get("fill_identity_key") not in fill_ids for r in visible["lifecycle_links"]):
        raise ValueError("broker capture is missing referenced fills")
    accounts = {r["fact"].get("account_key") for r in visible["collections"]}
    if len(accounts) != 1 or not all(v["latest_status"] == "ok" for v in summary["query_coverage"].values()):
        raise ValueError("fresh committed broker identity required for decision attribution")
    bindings, _ = resolve_order_bindings(visible, directory=directory)
    owners = _open_owners(visible, bindings)
    plans, unassigned = [], 0
    for sleeve, rows in (("core", signals or []), ("pilot", pilot_signals or [])):
        for row in rows:
            qty = (row.get("sizing") or {}).get("shares_to_buy")
            strategy = row.get("strategy")
            if not _number(qty) or not strategy:
                unassigned += 1
                continue
            plans.append({"strategy_id": sleeve + ":" + strategy,
                "code": "US." + row["ticker"].upper(), "side": "BUY", "quantity": qty,
                "action_kind": "entry", "source_payload": row})
    for kind, rows in (("add_on", addon_actions or []), ("bracket", (bracket_orders or {}).get("orders", []))):
        for row in rows:
            code = "US." + str(row.get("ticker") or "").upper()
            qty = row.get("shares_to_buy") if kind == "add_on" else row.get("quantity")
            owner = owners.get(code)
            if (not owner or not _number(qty)
                    or (kind == "bracket" and ((bracket_orders or {}).get("positions_stale") or _number(qty) > owner[2]))):
                unassigned += 1
                continue
            plans.append({"strategy_id": owner[0], "code": code,
                "side": "BUY" if kind == "add_on" else "SELL", "quantity": qty,
                "action_kind": kind, "source_payload": row, "parent_decision_ids": owner[1]})
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT / "quant").glob("*.py")) if not p.name.startswith("test_")}
    result = record_decisions(plans, as_of=as_of, account_key=next(iter(accounts)),
        source_ref="quant.run.step7.machine_advice", policy_hashes=hashes, directory=directory)
    result["unassigned_advice_count"] = unassigned
    return result
