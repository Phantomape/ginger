"""Read-only broker query, isolated validation, then append a committed-head capture.

Never invokes order APIs, generate(), or operator position-file updates.
Raw account data stays in the ignored runtime directory; proof output is redacted.
"""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "quant"))
import broker_execution_ledger as L
import broker_performance as P
import execution_attribution as A
import moomoo_open_positions as M

ID = "exp-20260909-002"
OUT = ROOT / "data/experiments" / ID
PRIVATE = ROOT / "data/runtime/broker_decision_order_attribution" / ID


def raw(root):
    return {name: (root / name).read_bytes() if (root / name).exists() else b""
            for name in L.LEDGER_FILENAMES.values()}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    protected = [ROOT / "operator_inputs/open_positions.json", ROOT / "quant/constants.py",
                 ROOT / "quant/backtester.py"]
    protected_before = {p.as_posix(): digest(p) for p in protected}
    before = raw(L.DEFAULT_LEDGER_DIR)
    before_summary = P.compute_broker_performance()
    started = L.utc_now_iso()
    capture_path = PRIVATE / "capture.json"
    if "--replay-existing" in sys.argv:
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
        started = capture["collection_started_at_utc"]
    else:
        if capture_path.exists():
            raise SystemExit("Existing frozen capture: use --replay-existing.")
        # SDK background disconnect callbacks retain their logging stream.
        # Keep an in-memory stream alive instead of closing its file underneath.
        log = io.StringIO()
        with redirect_stdout(log), redirect_stderr(log):
            state = M.fetch_moomoo_state()
        (PRIVATE / "sdk.log").write_text(log.getvalue(), encoding="utf-8")
        if not state or not state.get("broker_execution"):
            raise SystemExit("Read-only broker capture unavailable; canonical bytes unchanged.")
        capture = state["broker_execution"]
        capture_path.write_text(json.dumps(capture, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    required = ["positions", "history_deals", "history_orders", "order_fees"]
    if any((capture.get("queries", {}).get(k) or {}).get("status") != "ok" for k in required):
        raise SystemExit("A required query failed; canonical bytes unchanged.")
    isolated = PRIVATE / "isolated_ledger"
    L.persist_broker_execution_capture(capture, ledger_dir=isolated)
    L.validate_broker_execution_ledger(isolated)
    # Append only after the isolated capture and existing canonical chains pass.
    L.validate_broker_execution_ledger(L.DEFAULT_LEDGER_DIR)
    appended = L.persist_broker_execution_capture(capture)
    after = raw(L.DEFAULT_LEDGER_DIR)
    if not all(after[k].startswith(value) for k, value in before.items()):
        raise RuntimeError("old raw prefix changed")
    summary = P.compute_broker_performance()
    replay = L.persist_broker_execution_capture(capture)
    # Current inputs contain no explicitly tagged entry. Validate the real daily
    # adapter with zero new advice; never retrospectively mint historical orders.
    advice = A.build_daily_attribution_decisions(as_of=datetime.now(timezone.utc).date().isoformat(),
        signals=[], pilot_signals=[], addon_actions=[], bracket_orders={"orders": []},
        refresh_status="refreshed", capture_not_before=started)
    checks = {
        "old_eight_raw_prefixes_preserved": all(after[k].startswith(v) for k, v in before.items()),
        "replay_zero_append": all(v["rows_appended"] == 0 for v in replay["ledgers"].values()),
        "replay_raw_bytes_unchanged": raw(L.DEFAULT_LEDGER_DIR) == after,
        "protected_strategy_and_position_files_unchanged": protected_before == {p.as_posix(): digest(p) for p in protected},
        "economic_query_coverage_ok": all(v["latest_status"] == "ok" for v in summary["query_coverage"].values()),
        "anchored_collection_present": summary["collection_commit_integrity"]["anchored_collection_count"] >= 1,
        "no_historical_strategy_ownership_invented": summary["strategy_attribution"]["attributed_lifecycle_count"] == 0,
        "unknown_strategy_profit_is_null": summary["strategy_attribution"]["net_trading_pnl_after_order_fees"] is None,
        "real_daily_zero_advice_adapter_ok": advice["status"] == "ok" and not advice["decisions"],
    }
    proof = {"experiment_id": ID, "recorded_at": L.utc_now_iso(), "checks": checks,
        "all_passed": all(checks.values()), "source_as_of": summary["source_as_of"],
        "collection_commit_integrity": summary["collection_commit_integrity"],
        "captured_counts": {k: len(capture.get(k) or []) for k in ["deals", "orders", "order_fees", "positions"]},
        "canonical_rows_appended": {k: v["rows_appended"] for k, v in appended["ledgers"].items()},
        "binding_coverage": summary["strategy_attribution"]["binding_coverage"],
        "evaluated_lifecycle_count": summary["counts"]["evaluated_lifecycle_count"],
        "old_raw_hashes": {k: hashlib.sha256(v).hexdigest() for k, v in before.items()},
        "new_raw_hashes": {k: hashlib.sha256(v).hexdigest() for k, v in after.items()},
        "capture_sha256": digest(capture_path), "economic_progress": False, "trade_enabled": False,
        "orders_submitted": False, "old_account_sample_pnl_unchanged": before_summary["pnl_by_currency"] == summary["pnl_by_currency"]}
    destination = OUT / ("live_verification_replay.json" if "--replay-existing" in sys.argv else "live_verification.json")
    if destination.exists():
        raise SystemExit("Proof path already exists; preserve previous verification.")
    destination.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"proof": str(destination), "checks": checks, "source_as_of": summary["source_as_of"]}))
    if not proof["all_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
