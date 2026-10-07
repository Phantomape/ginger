"""Reserved read-only broker collection proof, followed by guarded ledger append.

Never calls generate/refresh_open_positions, order methods, or account unlock.
Raw captures, SDK logs and the isolated ledger stay in a gitignored directory.
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "quant"))
import broker_execution_ledger as ledger
from broker_performance import compute_broker_performance
import moomoo_open_positions as broker

EXPERIMENT_ID = "exp-20260906-008"
OUTPUT = ROOT / "data/experiments" / EXPERIMENT_ID
PRIVATE = ROOT / "data/runtime/broker_history_date_range_paging" / EXPERIMENT_ID
CANONICAL = ledger.DEFAULT_LEDGER_DIR


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                               allow_nan=False) + "\n", encoding="utf-8")


def raw_bytes(root):
    return {name: (root / name).read_bytes() if (root / name).is_file() else b""
            for name in ledger.LEDGER_FILENAMES.values()}


def raw_hashes(snapshot):
    return {name: hashlib.sha256(value).hexdigest() for name, value in snapshot.items()}


def capture_fact_comparison(capture, root):
    orders = [ledger.normalize_order(row, capture) for row in capture["orders"]]
    currencies = {str(row["order_id"]): str(row["currency"]) for row in orders
                  if row.get("order_id") and row.get("currency")}
    fills = [ledger.normalize_fill(row, capture, order_currency=currencies.get(str(row.get("order_id"))))
             for row in capture["deals"]]
    fees = [ledger.normalize_order_fee(row, capture, order_currency=currencies.get(str(row.get("order_id"))))
            for row in capture["order_fees"]]
    result = {}
    for name, facts in (("fills", fills), ("orders", orders), ("order_fees", fees)):
        key = ledger._deal_key if name == "fills" else lambda fact: (fact.get("account_key"), fact.get("order_id"))
        desired = {key(fact): ledger._sha256_json(fact) for fact in facts}
        _, rows = ledger._strict_read_chain(root / ledger.LEDGER_FILENAMES[name])
        actual = {key(row["fact"]): row["fact_hash"] for row in rows}
        result[name] = {"desired_distinct_count": len(desired),
                        "mismatch_count": sum(actual.get(identity) != value for identity, value in desired.items())}
    return result


def verify_existing_capture():
    output = OUTPUT / "version_projection_revision"
    contract = json.loads((output / "source_contract.json").read_text(encoding="utf-8"))
    if any(sha(ROOT / relative) != expected for relative, expected in contract["code_sha256"].items()):
        raise SystemExit("Frozen revision code changed.")
    before = raw_bytes(CANONICAL)
    if raw_hashes(before) != contract["canonical_raw_sha256"]:
        raise SystemExit("Frozen revision source changed.")
    capture = json.loads((PRIVATE / "capture.json").read_text(encoding="utf-8"))
    replay = ledger.persist_broker_execution_capture(capture, ledger_dir=CANONICAL)
    comparison = {name: capture_fact_comparison(capture, root) for name, root in
                  (("isolated", PRIVATE / "isolated_ledger"), ("canonical", CANONICAL))}
    first = compute_broker_performance(CANONICAL)
    checks = {
        "actual_capture_final_facts_match": all(row["mismatch_count"] == 0 for group in comparison.values() for row in group.values()),
        "committed_capture_replay_appended_zero_rows": all(row["rows_appended"] == 0 for row in replay["ledgers"].values()),
        "raw_bytes_unchanged": raw_bytes(CANONICAL) == before,
        "two_performance_calls_identical": first == compute_broker_performance(CANONICAL),
    }
    write(output / "verification_after.json", {
        "experiment_id": EXPERIMENT_ID, "completed_at": datetime.now(timezone.utc).isoformat(),
        "source_contract_sha256": sha(output / "source_contract.json"),
        "capture_fact_comparison": comparison, "checks": checks,
        "canonical_broker_performance": first, "all_passed": all(checks.values()),
        "new_broker_calls": False, "alpha_changed": False, "trade_enabled": False,
    })
    if not all(checks.values()):
        raise SystemExit(2)


def main():
    contract = json.loads((OUTPUT / "source_contract.json").read_text(encoding="utf-8"))
    if any(sha(ROOT / relative) != expected for relative, expected in contract["code_sha256"].items()):
        raise SystemExit("Frozen code changed; refuse proof.")
    private_capture = PRIVATE / "capture.json"
    ignored = subprocess.run(["git", "check-ignore", "--quiet", str(private_capture)], cwd=ROOT).returncode == 0
    if not ignored:
        raise SystemExit("Raw capture destination is not gitignored.")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    before = raw_bytes(CANONICAL)
    if raw_hashes(before) != contract["canonical_raw_sha256"]:
        raise SystemExit("Frozen canonical source changed; refuse append proof.")
    protected = {relative: sha(ROOT / relative) for relative in contract["protected_files"]}
    result = {
        "experiment_id": EXPERIMENT_ID,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "code_sha256": contract["code_sha256"],
        "canonical_raw_hashes_before": raw_hashes(before),
        "source_contract_sha256": sha(OUTPUT / "source_contract.json"),
        "read_only_broker_calls": True,
        "raw_capture_gitignored": ignored,
        "canonical_append_performed": False,
        "economic_progress": False,
        "alpha_changed": False,
        "trade_enabled": False,
        "backtest_metrics": "not_applicable_measurement_repair",
    }
    try:
        existing_valid = ledger.validate_broker_execution_ledger(CANONICAL)["status"] == "valid"
    except ledger.BrokerLedgerError:
        existing_valid = False
    result["canonical_chain_valid_before"] = existing_valid
    os.environ["GINGER_MOOMOO_SDK_APPDATA"] = str(PRIVATE / "sdk_appdata")
    runtime_log = (PRIVATE / "collection_runtime.log").open("w", encoding="utf-8")
    with redirect_stdout(runtime_log), redirect_stderr(runtime_log):
        state = broker.fetch_moomoo_state()
    runtime_log.flush()  # SDK background disconnect logging still owns this stream.
    if state is None:
        text = (PRIVATE / "collection_runtime.log").read_text(encoding="utf-8")
        result["live_status"] = ("opend_unreachable" if "OpenD not reachable" in text else
                                 "sdk_unavailable" if "SDK unavailable" in text else "broker_context_unavailable")
    else:
        capture = state["broker_execution"]
        write(private_capture, capture)
        queries = capture["queries"]
        result["query_summary"] = {name: {key: row.get(key) for key in ("status", "row_count", "observed_at_utc")}
                                   for name, row in queries.items()}
        result["history_window"] = {"start": capture["history_start"], "end": capture["history_end"]}
        result["captured_counts"] = {name: len(capture[name]) for name in
                                     ("deals", "orders", "order_fees", "cashflows", "accounts", "positions")}
        history_ok = all(queries[name]["status"] == "ok" for name in ("history_deals", "history_orders"))
        isolated = PRIVATE / "isolated_ledger"
        ledger.persist_broker_execution_capture(capture, ledger_dir=isolated)
        isolated_valid = ledger.validate_broker_execution_ledger(isolated)["status"] == "valid"
        result["isolated_chain_valid"] = isolated_valid
        result["isolated_broker_performance"] = compute_broker_performance(isolated)
        result["isolated_capture_fact_comparison"] = capture_fact_comparison(capture, isolated)
        isolated_facts_match = all(row["mismatch_count"] == 0 for row in result["isolated_capture_fact_comparison"].values())
        unchanged = raw_bytes(CANONICAL) == before
        if history_ok and existing_valid and isolated_valid and isolated_facts_match and unchanged:
            persisted = ledger.persist_broker_execution_capture(capture, ledger_dir=CANONICAL)
            result["canonical_append_performed"] = True
            result["canonical_rows_appended"] = {name: row["rows_appended"]
                                                  for name, row in persisted["ledgers"].items()}
            result["live_status"] = "history_restored_and_appended"
        else:
            result["live_status"] = "capture_retained_private_no_canonical_append"
            result["append_preconditions"] = {"all_history_segments_ok": history_ok,
                                               "existing_chain_valid": existing_valid,
                                               "isolated_valid": isolated_valid, "source_unchanged": unchanged}
    after = raw_bytes(CANONICAL)
    result["canonical_raw_hashes_after"] = raw_hashes(after)
    result["old_raw_prefixes_unchanged"] = {name: after[name].startswith(value) for name, value in before.items()}
    result["protected_files_unchanged"] = protected == {relative: sha(ROOT / relative) for relative in protected}
    first = compute_broker_performance(CANONICAL)
    second = compute_broker_performance(CANONICAL)
    result["canonical_broker_performance"] = first
    result["two_performance_calls_identical"] = first == second
    result["performance_read_did_not_write_raw"] = after == raw_bytes(CANONICAL)
    result["completed_at"] = datetime.now(timezone.utc).isoformat()
    result["engineering_checks_passed"] = (
        all(result["old_raw_prefixes_unchanged"].values()) and result["protected_files_unchanged"]
        and result["two_performance_calls_identical"] and result["performance_read_did_not_write_raw"]
    )
    write(OUTPUT / "after.json", result)
    if not result["engineering_checks_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    verify_existing_capture() if "--verify-existing-capture" in sys.argv else main()
