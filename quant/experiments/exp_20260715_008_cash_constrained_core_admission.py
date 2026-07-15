"""exp-20260715-008: execution-date cash-constrained core order admission.

Measurement repair. The canonical core backtester books entry and add-on
fills with no execution-date cash constraint; the exp-20260715-005 dated
ledger reconstruction found 18-20 negative-cash events per canonical window
(max overdraft about -23,234 USD on 100,000 USD initial capital), i.e. the
published champion books physically unexecutable fills.

This runner replays the three canonical windows twice under the
exp-20260712-015 frozen behavior inputs:

- before: CASH_LEDGER_ENFORCED=False (must reproduce the published post-MTM
  baseline identity exactly, proving the audit-only ledger changes nothing);
- after:  CASH_LEDGER_ENFORCED=True (unaffordable core entries/add-ons are
  deterministically scaled down or skipped; exits release cash).

Acceptance (see ticket): before-pass Gate-1 identity holds; after-pass has
zero negative-cash events, logged admission events, and exact cash
conservation; the unenforced audit independently reproduces the overdraft
phenomenon; EV/PnL/drawdown/trade deltas are reported as the honest
re-measurement with no improvement requirement. DEFAULT_CONFIG stays False;
the canonical default flip / re-baseline is an explicit follow-up decision.
"""

from __future__ import annotations

import json
import sys
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

import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402

EXPERIMENT_ID = "exp-20260715-008"
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT = EXP_DIR / "exp_20260715_008_cash_constrained_core_admission.json"
BEFORE_FILE = EXP_DIR / "before.json"
AFTER_FILE = EXP_DIR / "after.json"

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


def _run_window(spec: dict[str, str], frozen: dict[str, Any],
                enforce_cash_ledger: bool) -> dict[str, Any]:
    behavior = frozen["behavior"]
    calendar = gate1._calendar_dates(frozen)
    config = dict(gate1.RUN_CONFIG)
    config["CASH_LEDGER_ENFORCED"] = bool(enforce_cash_ledger)
    engine = BacktestEngine(
        list(behavior["universe"]),
        start=spec["start"],
        end=spec["end"],
        config=config,
        ohlcv_warehouse_path=str(gate1.WAREHOUSE),
        ohlcv_warehouse_snapshot_source=spec["snapshot"],
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
    if result.get("error"):
        raise RuntimeError(f"{spec['label']}: {result['error']}")
    return result


def _headline(result: dict[str, Any]) -> dict[str, Any]:
    metrics = {key: result.get(key) for key in HEADLINE_KEYS}
    metrics["trade_count"] = result.get("total_trades")
    return metrics


def _cash_summary(result: dict[str, Any]) -> dict[str, Any]:
    audit = dict(result.get("cash_ledger") or {})
    # Keep artifacts small: event details capped in-engine already; drop the
    # bulky lists here and keep counts plus a small sample.
    audit["negative_cash_events_sample"] = (
        audit.pop("negative_cash_events", [])[:5]
    )
    audit["admission_events_sample"] = (
        audit.pop("admission_events", [])[:10]
    )
    return audit


def _gate1_identity_check(before_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    published = json.loads(gate1.BASELINE_SUMMARY.read_text(encoding="utf-8"))
    published_windows = {w["label"]: w for w in published["windows"]}
    checks = {}
    for label, result in before_results.items():
        identity = gate1._result_identity(result)
        ref = published_windows[label]
        checks[label] = {
            "trade_rows_sha256_match": (
                identity["trade_rows_sha256"] == ref["trade_rows_sha256"]
            ),
            "daily_return_series_sha256_match": (
                identity["daily_return_series_sha256"]
                == ref["daily_return_series_sha256"]
            ),
            "expected_value_score_match": (
                result.get("expected_value_score") == ref["expected_value_score"]
            ),
            "total_pnl_match": result.get("total_pnl") == ref["total_pnl"],
            "trade_count_match": result.get("total_trades") == ref["trade_count"],
        }
        checks[label]["all_match"] = all(checks[label].values())
    checks["all_windows_match"] = all(
        entry["all_match"] for entry in checks.values() if isinstance(entry, dict)
    )
    return checks


def main() -> int:
    frozen = gate1._load_or_capture_frozen_inputs(refresh=False)

    before_results: dict[str, dict[str, Any]] = {}
    after_results: dict[str, dict[str, Any]] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] before (ledger audit-only) ...", flush=True)
        before_results[label] = _run_window(spec, frozen, enforce_cash_ledger=False)
        print(f"[{label}] after (ledger enforced) ...", flush=True)
        after_results[label] = _run_window(spec, frozen, enforce_cash_ledger=True)

    gate1_checks = _gate1_identity_check(before_results)

    windows_payload = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        before = before_results[label]
        after = after_results[label]
        before_head = _headline(before)
        after_head = _headline(after)
        delta = {
            key: (
                round(after_head[key] - before_head[key], 6)
                if isinstance(before_head.get(key), (int, float))
                and isinstance(after_head.get(key), (int, float))
                else None
            )
            for key in before_head
        }
        windows_payload[label] = {
            "window": {k: spec[k] for k in ("label", "start", "end", "snapshot")},
            "before": before_head,
            "after": after_head,
            "delta": delta,
            "before_cash_audit": _cash_summary(before),
            "after_cash_audit": _cash_summary(after),
            "gate1_identity": gate1_checks[label],
        }

    after_audits = [windows_payload[s["label"]]["after_cash_audit"] for s in gate1.WINDOWS]
    before_audits = [windows_payload[s["label"]]["before_cash_audit"] for s in gate1.WINDOWS]

    acceptance = {
        "gate1_before_identity_all_windows": gate1_checks["all_windows_match"],
        "after_zero_negative_cash_events": all(
            a["negative_cash_event_count"] == 0 for a in after_audits
        ),
        "after_cash_conservation_passed": all(
            a["cash_conservation_passed"] for a in after_audits
        ),
        "before_cash_conservation_passed": all(
            a["cash_conservation_passed"] for a in before_audits
        ),
        "before_reproduces_overdraft_phenomenon": all(
            a["negative_cash_event_count"] > 0 for a in before_audits
        ),
        "after_admission_events_logged": all(
            (a["scaled_entry_count"] + a["skipped_entry_count"]
             + a["scaled_addon_count"] + a["skipped_addon_count"]) > 0
            for a in after_audits
        ),
    }
    acceptance["accepted_measurement_repair"] = all(acceptance.values())

    aggregate = {
        "before_ev_sum": round(sum(
            windows_payload[s["label"]]["before"]["expected_value_score"]
            for s in gate1.WINDOWS), 4),
        "after_ev_sum": round(sum(
            windows_payload[s["label"]]["after"]["expected_value_score"]
            for s in gate1.WINDOWS), 4),
        "before_pnl_sum": round(sum(
            windows_payload[s["label"]]["before"]["total_pnl"]
            for s in gate1.WINDOWS), 2),
        "after_pnl_sum": round(sum(
            windows_payload[s["label"]]["after"]["total_pnl"]
            for s in gate1.WINDOWS), 2),
    }
    aggregate["ev_delta"] = round(
        aggregate["after_ev_sum"] - aggregate["before_ev_sum"], 4)
    aggregate["pnl_delta"] = round(
        aggregate["after_pnl_sum"] - aggregate["before_pnl_sum"], 2)
    aggregate["ev_delta_pct"] = round(
        aggregate["ev_delta"] / aggregate["before_ev_sum"], 6
    ) if aggregate["before_ev_sum"] else None

    artifact = {
        "schema": "cash_constrained_core_admission_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Enforcing an execution-date cash ledger with deterministic "
            "scale-down or rejection of unaffordable core entries and add-ons "
            "repairs the negative-cash parity defect quantified by "
            "exp-20260715-005."
        ),
        "frozen_behavior_inputs": {
            "path": gate1._repo_rel(gate1.FROZEN_INPUTS),
            "behavior_sha256": frozen["behavior_sha256"],
        },
        "baseline_summary": gate1._repo_rel(gate1.BASELINE_SUMMARY),
        "default_config_flag": "CASH_LEDGER_ENFORCED stays False; canonical default flip and re-baseline are a follow-up decision.",
        "windows": windows_payload,
        "aggregate": aggregate,
        "acceptance": acceptance,
        "reproduction": {
            "command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260715_008_cash_constrained_core_admission.py"
            ),
        },
    }

    gate1._atomic_write_json(ARTIFACT, artifact)
    gate1._atomic_write_json(BEFORE_FILE, {
        "experiment_id": EXPERIMENT_ID,
        "role": "cash_ledger_audit_only_replay",
        "windows": {label: _headline(res) for label, res in before_results.items()},
        "cash_audits": {label: _cash_summary(res) for label, res in before_results.items()},
    })
    gate1._atomic_write_json(AFTER_FILE, {
        "experiment_id": EXPERIMENT_ID,
        "role": "cash_ledger_enforced_replay",
        "windows": {label: _headline(res) for label, res in after_results.items()},
        "cash_audits": {label: _cash_summary(res) for label, res in after_results.items()},
    })

    print(json.dumps({
        "acceptance": acceptance,
        "aggregate": aggregate,
    }, indent=2))
    return 0 if acceptance["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
