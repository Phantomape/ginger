"""exp-20260717-006: clean_spy_leader family removal — predeclared holdout confirmation.

exp-20260716-010's leave-one-family-out ablation measured the clean_spy_leader
sizing family (signal-day 1.10x risk multiplier + 0.525/0.60/0.70 position-cap
raises, exp-20260513-036 lineage) as a near-zero simplification candidate under
CASH_LEDGER_ENFORCED (+0.61% aggregate EV when removed; raised caps rarely bind
once cash admission scales fills). Its post_run_reflection predeclared exactly
one legal follow-up: a confirmation ticket for this bundle with its own fresh
Gate 4 on an unseen or extended window set. The three canonical windows are
deterministic re-verification only; the deciding out-of-sample evidence is a
newly frozen holdout window 2026-04-22..2026-07-16 extracted from the live
overlay warehouse into an experiment-owned sqlite (hash-bound, no hot sibling,
so the overlay view is a pass-through and later live writes cannot mutate it).

Fixed bundle (no partial bundles, no gold-cap arm, no retuning):
    CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER  -> 1.0
    CLEAN_SPY_LEADER_SIGNAL_DAY_MAX_POSITION_PCT -> MAX_POSITION_PCT (0.40)
    CLEAN_SPY_CAP_ONLY_LEADER_MAX_POSITION_PCT   -> MAX_POSITION_PCT (0.40)
    CLEAN_SPY_CAP_ONLY_RS20_LEADER_MAX_POSITION_PCT -> MAX_POSITION_PCT (0.40)

Predeclared acceptance (from the ticket, fixed before any after-run):
  1. canonical 3-window after run reproduces the exp-20260716-010
     clean_spy_leader_family_off arm exactly (per-window EV/PnL/trade counts),
     worst DD not worse than anchor +1pp, zero negative-cash events;
  2. holdout baseline (current stack) vs bundle-removed after:
     EV delta >= -2% of holdout baseline EV,
     PnL delta >= -2% of abs(holdout baseline PnL),
     max drawdown not worse than baseline +1pp,
     trade count within +/-20%, survival not degraded by more than 5pp,
     zero negative-cash events (byte-identical trades count as pass);
  3. Gate 2 sentinel fields (entry_date, stop_price, target_mult_used) present
     on all trades in every run.
Accept => retained simplification (apply family removal to shared
portfolio_engine policy in this ticket). Any bar fails => rejected, stack
unchanged.

Reproduce:
    .\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260717_006_clean_spy_leader_family_removal_holdout_confirmation.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backtester import BacktestEngine  # noqa: E402
import portfolio_engine  # noqa: E402
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    connect_overlay_reader,
    overlay_reader_status,
)

import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402

EXPERIMENT_ID = "exp-20260717-006"
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT = EXP_DIR / "exp_20260717_006_clean_spy_leader_family_removal_holdout_confirmation.json"
HOLDOUT_DB = EXP_DIR / "holdout_warehouse.sqlite"
HOLDOUT_MANIFEST = EXP_DIR / "holdout_warehouse_manifest.json"
ANCHOR_SUMMARY = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
ABLATION_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260716-010"
    / "exp_20260716_010_cash_feasible_policy_stack_ablation.json"
)

HOLDOUT_LABEL = "holdout_recent"
HOLDOUT_START = "2026-04-22"
HOLDOUT_END = "2026-07-16"
# Engine lookback is 400 calendar days before window start; extract with margin.
EXTRACT_START = "2025-03-01"

BASE_CAP = portfolio_engine.MAX_POSITION_PCT
BUNDLE_PATCHES: list[tuple[str, Any]] = [
    ("CLEAN_SPY_LEADER_SIGNAL_DAY_RISK_MULTIPLIER", 1.0),
    ("CLEAN_SPY_LEADER_SIGNAL_DAY_MAX_POSITION_PCT", BASE_CAP),
    ("CLEAN_SPY_CAP_ONLY_LEADER_MAX_POSITION_PCT", BASE_CAP),
    ("CLEAN_SPY_CAP_ONLY_RS20_LEADER_MAX_POSITION_PCT", BASE_CAP),
]

HEADLINE_KEYS = (
    "expected_value_score",
    "total_pnl",
    "sharpe_daily",
    "max_drawdown_pct",
    "win_rate",
    "signals_generated",
    "signals_survived",
    "survival_rate",
)


def _freeze_holdout_warehouse(universe: list[str]) -> dict[str, Any]:
    """Extract the holdout rowset from the live overlay warehouse into an
    experiment-owned sqlite. Idempotent: an existing frozen file is verified
    against its recorded manifest hash, never re-extracted."""
    tickers = sorted({str(t).upper() for t in universe})
    if HOLDOUT_DB.exists() and HOLDOUT_MANIFEST.exists():
        manifest = json.loads(HOLDOUT_MANIFEST.read_text(encoding="utf-8"))
        digest = _holdout_rowset_sha256(HOLDOUT_DB)
        if digest != manifest.get("rowset_sha256"):
            raise RuntimeError(
                "frozen holdout warehouse hash mismatch: "
                f"{digest} != {manifest.get('rowset_sha256')}"
            )
        return manifest

    EXP_DIR.mkdir(parents=True, exist_ok=True)
    src = connect_overlay_reader(DEFAULT_WAREHOUSE_PATH)
    status = overlay_reader_status(src)
    if status["hot_exists"] and not status["hot_attached"]:
        raise RuntimeError(f"hot tier exists but not attached: {status}")
    qs = ",".join("?" for _ in tickers)
    rows = src.execute(
        f"SELECT ticker, date, open, high, low, close, volume FROM ohlcv_overlay "
        f"WHERE ticker IN ({qs}) AND date >= ? AND date <= ? ORDER BY ticker, date",
        [*tickers, EXTRACT_START, HOLDOUT_END],
    ).fetchall()
    src.close()
    if not rows:
        raise RuntimeError("holdout extraction returned zero rows")

    tmp = HOLDOUT_DB.with_suffix(".sqlite.tmp")
    if tmp.exists():
        tmp.unlink()
    dst = sqlite3.connect(tmp)
    dst.execute(
        "CREATE TABLE ohlcv (ticker TEXT NOT NULL, date TEXT NOT NULL, "
        "open REAL, high REAL, low REAL, close REAL, volume REAL, source TEXT, "
        "updated_at TEXT NOT NULL, "
        "PRIMARY KEY (ticker, date))"
    )
    frozen_at = datetime.now(timezone.utc).isoformat()
    dst.executemany(
        "INSERT INTO ohlcv (ticker, date, open, high, low, close, volume, "
        "source, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'exp-20260717-006 frozen overlay extract', "
        f"'{frozen_at}')",
        rows,
    )
    dst.commit()
    dst.close()
    tmp.replace(HOLDOUT_DB)

    per_ticker: dict[str, dict[str, Any]] = {}
    for ticker, day, *_ in rows:
        info = per_ticker.setdefault(
            ticker, {"rows": 0, "min_date": day, "max_date": day}
        )
        info["rows"] += 1
        info["min_date"] = min(info["min_date"], day)
        info["max_date"] = max(info["max_date"], day)
    missing = sorted(set(tickers) - set(per_ticker))
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "source_warehouse": str(DEFAULT_WAREHOUSE_PATH),
        "overlay_status": status,
        "extract_start": EXTRACT_START,
        "holdout_start": HOLDOUT_START,
        "holdout_end": HOLDOUT_END,
        "tickers_requested": len(tickers),
        "tickers_with_rows": len(per_ticker),
        "tickers_missing": missing,
        "total_rows": len(rows),
        "rowset_sha256": _holdout_rowset_sha256(HOLDOUT_DB),
        "per_ticker": per_ticker,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    HOLDOUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _holdout_rowset_sha256(db_path: Path) -> str:
    conn = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        hasher = hashlib.sha256()
        for row in conn.execute(
            "SELECT ticker, date, open, high, low, close, volume FROM ohlcv "
            "ORDER BY ticker, date"
        ):
            hasher.update(repr(row).encode("utf-8"))
        return hasher.hexdigest()
    finally:
        conn.close()


def _run_window(label: str, start: str, end: str, frozen: dict[str, Any],
                warehouse: Path, snapshot: str | None,
                patches: list[tuple[str, Any]]) -> dict[str, Any]:
    behavior = frozen["behavior"]
    calendar = gate1._calendar_dates(frozen)
    config = dict(gate1.RUN_CONFIG)
    config["CASH_LEDGER_ENFORCED"] = True
    saved: list[tuple[str, Any]] = []
    try:
        for name, value in patches:
            saved.append((name, getattr(portfolio_engine, name)))
            setattr(portfolio_engine, name, value)
        engine = BacktestEngine(
            list(behavior["universe"]),
            start=start,
            end=end,
            config=config,
            ohlcv_warehouse_path=str(warehouse),
            ohlcv_warehouse_snapshot_source=snapshot,
            replay_llm=False,
            replay_news=False,
            include_pilot_sleeve=False,
            require_non_ohlcv=False,
            include_oracle_diagnostics=False,
        )
        engine._earnings_snapshots = behavior["earnings_snapshots"]
        engine._download_earnings_calendar = lambda: {
            ticker: list(values) for ticker, values in calendar.items()
        }
        result = engine.run()
    finally:
        for name, value in saved:
            setattr(portfolio_engine, name, value)
    if result.get("error"):
        raise RuntimeError(f"{label}: {result['error']}")
    return result


def _finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _headline(result: dict[str, Any]) -> dict[str, Any]:
    metrics = {key: _finite(result.get(key)) for key in HEADLINE_KEYS}
    for key in ("expected_value_score", "total_pnl"):
        if metrics[key] is None:
            raise RuntimeError(f"non-finite {key}")
    metrics["trade_count"] = result.get("total_trades")
    ledger = result.get("cash_ledger") or {}
    metrics["negative_cash_event_count"] = ledger.get(
        "negative_cash_event_count",
        len(ledger.get("negative_cash_events") or []),
    )
    metrics["min_cash"] = ledger.get("min_cash")
    metrics["trade_rows_sha256"] = gate1._stable_hash(result.get("trades") or [])
    return metrics


def _gate2_fields(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades") or []
    missing_entry = [t.get("trade_key") for t in trades if not t.get("entry_date")]
    missing_stop = [t.get("trade_key") for t in trades if t.get("stop_price") in (None, 0)]
    return {
        "trade_count": len(trades),
        "entry_date_missing": missing_entry,
        "stop_price_missing": missing_stop,
        "target_mult_present": all("target_mult_used" in t for t in trades),
        "passed": not missing_entry and not missing_stop,
    }


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    anchor = json.loads(ANCHOR_SUMMARY.read_text(encoding="utf-8"))
    anchor_windows = {w["label"]: w for w in anchor["windows"]}
    anchor_agg_ev = sum(w["expected_value_score"] for w in anchor["windows"])
    anchor_worst_dd = max(w["max_drawdown_pct"] for w in anchor["windows"])

    ablation = json.loads(ABLATION_ARTIFACT.read_text(encoding="utf-8"))
    arm_ref = ablation["arms"]["clean_spy_leader_family_off"]

    frozen = gate1._load_or_capture_frozen_inputs(refresh=False)
    manifest = _freeze_holdout_warehouse(list(frozen["behavior"]["universe"]))
    print(
        f"[holdout] frozen warehouse rows={manifest['total_rows']} "
        f"tickers={manifest['tickers_with_rows']}/{manifest['tickers_requested']} "
        f"sha256={manifest['rowset_sha256'][:16]}...",
        flush=True,
    )

    runs: dict[str, dict[str, dict[str, Any]]] = {"baseline": {}, "after": {}}
    gate2: dict[str, dict[str, Any]] = {"baseline": {}, "after": {}}
    survival: dict[str, dict[str, Any]] = {"baseline": {}, "after": {}}

    window_specs = [
        {**spec, "warehouse": gate1.WAREHOUSE} for spec in gate1.WINDOWS
    ] + [
        {
            "label": HOLDOUT_LABEL,
            "start": HOLDOUT_START,
            "end": HOLDOUT_END,
            "snapshot": None,
            "warehouse": HOLDOUT_DB,
        }
    ]

    for pass_name, patches in (("baseline", []), ("after", BUNDLE_PATCHES)):
        for spec in window_specs:
            label = spec["label"]
            t0 = time.time()
            result = _run_window(
                label,
                spec["start"],
                spec["end"],
                frozen,
                spec["warehouse"],
                spec.get("snapshot"),
                patches,
            )
            head = _headline(result)
            runs[pass_name][label] = head
            gate2[pass_name][label] = _gate2_fields(result)
            survival[pass_name][label] = {
                "signals_generated": result.get("signals_generated"),
                "signals_survived": result.get("signals_survived"),
                "survival_rate": result.get("survival_rate"),
            }
            if pass_name == "baseline" and label != HOLDOUT_LABEL:
                # keep the full identity for the Gate-1 anchor check
                head["daily_return_series_sha256"] = gate1._result_identity(result)[
                    "daily_return_series_sha256"
                ]
            print(
                f"[{pass_name}] {label}: EV={head['expected_value_score']}"
                f" pnl={head['total_pnl']} trades={head['trade_count']}"
                f" dd={head['max_drawdown_pct']}"
                f" ({time.time() - t0:.1f}s)",
                flush=True,
            )

    # ---- Gate 1: canonical baseline must reproduce the anchor identity.
    gate1_checks: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        head = runs["baseline"][label]
        ref = anchor_windows[label]
        entry = {
            "trade_rows_sha256_match": head["trade_rows_sha256"] == ref["trade_rows_sha256"],
            "daily_return_series_sha256_match": (
                head["daily_return_series_sha256"] == ref["daily_return_series_sha256"]
            ),
            "expected_value_score_match": (
                head["expected_value_score"] == ref["expected_value_score"]
            ),
            "total_pnl_match": head["total_pnl"] == ref["total_pnl"],
            "trade_count_match": head["trade_count"] == ref["trade_count"],
        }
        entry["all_match"] = all(entry.values())
        gate1_checks[label] = entry
    gate1_checks["all_windows_match"] = all(
        e["all_match"] for e in gate1_checks.values() if isinstance(e, dict)
    )

    # ---- Condition 1: canonical after must reproduce the exp-20260716-010 arm.
    canon_after = {
        label: runs["after"][label] for label in (s["label"] for s in gate1.WINDOWS)
    }
    canon_after_agg_ev = sum(r["expected_value_score"] for r in canon_after.values())
    canon_after_worst_dd = max(r["max_drawdown_pct"] for r in canon_after.values())
    arm_match = {
        label: {
            "ev_match": canon_after[label]["expected_value_score"]
            == arm_ref["windows"][label]["expected_value_score"],
            "pnl_match": canon_after[label]["total_pnl"]
            == arm_ref["windows"][label]["total_pnl"],
            "trade_count_match": canon_after[label]["trade_count"]
            == arm_ref["windows"][label]["trade_count"],
        }
        for label in canon_after
    }
    for entry in arm_match.values():
        entry["all_match"] = all(entry.values())
    cond1 = {
        "arm_reproduced_exactly": all(e["all_match"] for e in arm_match.values()),
        "aggregate_ev_delta_vs_anchor": canon_after_agg_ev - anchor_agg_ev,
        "worst_dd_within_1pp": canon_after_worst_dd <= anchor_worst_dd + 1.0,
        "zero_negative_cash_events": all(
            (r["negative_cash_event_count"] or 0) == 0 for r in canon_after.values()
        ),
        "per_window_match": arm_match,
    }
    cond1["passed"] = (
        cond1["arm_reproduced_exactly"]
        and cond1["worst_dd_within_1pp"]
        and cond1["zero_negative_cash_events"]
    )

    # ---- Condition 2: holdout decision.
    hb = runs["baseline"][HOLDOUT_LABEL]
    ha = runs["after"][HOLDOUT_LABEL]
    byte_identical = hb["trade_rows_sha256"] == ha["trade_rows_sha256"]
    ev_delta = ha["expected_value_score"] - hb["expected_value_score"]
    pnl_delta = ha["total_pnl"] - hb["total_pnl"]
    ev_floor = -0.02 * abs(hb["expected_value_score"])
    pnl_floor = -0.02 * abs(hb["total_pnl"])
    trade_ratio = (
        ha["trade_count"] / hb["trade_count"] if hb["trade_count"] else 1.0
    )
    surv_b = survival["baseline"][HOLDOUT_LABEL]["survival_rate"] or 0.0
    surv_a = survival["after"][HOLDOUT_LABEL]["survival_rate"] or 0.0
    cond2 = {
        "byte_identical_trades": byte_identical,
        "ev_delta": ev_delta,
        "ev_floor": ev_floor,
        "ev_ok": byte_identical or ev_delta >= ev_floor,
        "pnl_delta": pnl_delta,
        "pnl_floor": pnl_floor,
        "pnl_ok": byte_identical or pnl_delta >= pnl_floor,
        "dd_ok": ha["max_drawdown_pct"] <= hb["max_drawdown_pct"] + 1.0,
        "trade_count_ratio": trade_ratio,
        "trade_count_ok": 0.8 <= trade_ratio <= 1.2,
        "survival_ok": surv_a >= surv_b - 5.0,
        "zero_negative_cash_events": (
            (hb["negative_cash_event_count"] or 0) == 0
            and (ha["negative_cash_event_count"] or 0) == 0
        ),
    }
    cond2["passed"] = all(
        cond2[k]
        for k in (
            "ev_ok",
            "pnl_ok",
            "dd_ok",
            "trade_count_ok",
            "survival_ok",
            "zero_negative_cash_events",
        )
    )

    # ---- Condition 3: Gate 2 sentinel fields everywhere.
    cond3 = {
        "passed": all(
            entry["passed"] and entry["target_mult_present"]
            for side in gate2.values()
            for entry in side.values()
        )
    }

    accepted = (
        gate1_checks["all_windows_match"]
        and cond1["passed"]
        and cond2["passed"]
        and cond3["passed"]
    )

    payload = {
        "schema": "clean_spy_leader_family_removal_holdout_confirmation_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started,
        "anchor_summary": str(ANCHOR_SUMMARY.relative_to(ROOT)),
        "ablation_artifact": str(ABLATION_ARTIFACT.relative_to(ROOT)),
        "ablation_arm": "clean_spy_leader_family_off",
        "bundle_patches": [[n, v] for n, v in BUNDLE_PATCHES],
        "holdout_manifest": str(HOLDOUT_MANIFEST.relative_to(ROOT)),
        "holdout_rowset_sha256": manifest["rowset_sha256"],
        "holdout_window": {"start": HOLDOUT_START, "end": HOLDOUT_END},
        "gate1": gate1_checks,
        "gate2": gate2,
        "gate3_survival": survival,
        "runs": runs,
        "condition_1_canonical_arm_reproduction": cond1,
        "condition_2_holdout_decision": cond2,
        "condition_3_gate2_sentinels": cond3,
        "decision": "accepted_retained_simplification" if accepted else "rejected",
        "production_impact": (
            "on acceptance the clean_spy_leader family constants/branches are "
            "removed from shared portfolio_engine policy (default-on sizing "
            "simplification applied by this ticket); on rejection nothing changes"
        ),
    }
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[done] artifact -> {ARTIFACT}", flush=True)
    print(
        f"[done] gate1={gate1_checks['all_windows_match']}"
        f" cond1={cond1['passed']} cond2={cond2['passed']} cond3={cond3['passed']}"
        f" decision={payload['decision']}",
        flush=True,
    )
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
