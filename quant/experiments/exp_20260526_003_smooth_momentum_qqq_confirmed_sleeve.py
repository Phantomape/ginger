"""exp-20260526-003: smooth momentum path with QQQ confirmation.

This alpha search keeps the rejected exp-20260526-002 smooth daily-return
path source fixed and changes one variable: require QQQ's 20-day close-to-close
return to exceed SPY's 20-day close-to-close return before the top ranked
smooth-path candidate can enter the default-off paper sleeve.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260526_002_smooth_momentum_path_sleeve as smooth_source  # noqa: E402
import exp_20260426_041_opening_range_continuation_shadow as ohlcv_shadow  # noqa: E402


EXPERIMENT_ID = "exp-20260526-003"
STEM = "smooth_momentum_qqq_confirmed_sleeve"
TRIAL_FAMILY = "smooth_momentum_path_qqq_confirmed_default_off_paper_sleeve"
CHANGED_VARIABLE = (
    "smooth_momentum_path_daily_top1_qqq_gt_spy20_next_open_10d_fixed_notional_sleeve_v1"
)
RULE_VERSION = "smooth_momentum_path_qqq_confirmed_v1"
SOURCE_EXP002_REL = (
    "data/experiments/exp-20260526-002/smooth_momentum_path_sleeve.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MARKET_LOOKBACK_DAYS = 20
MIN_QQQ_MINUS_SPY_RET20 = 0.0
MARKET_GATE_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _configure_modules() -> None:
    smooth_source.EXPERIMENT_ID = EXPERIMENT_ID
    smooth_source.STEM = STEM
    smooth_source.TRIAL_FAMILY = TRIAL_FAMILY
    smooth_source.CHANGED_VARIABLE = CHANGED_VARIABLE
    smooth_source.RULE_VERSION = RULE_VERSION
    smooth_source.OUT_DIR = OUT_DIR
    smooth_source.OUT_JSON = OUT_JSON
    smooth_source.LOG_JSON = LOG_JSON
    smooth_source.TICKET_JSON = TICKET_JSON
    smooth_source.ARTIFACT_MD = ARTIFACT_MD
    smooth_source.EXPERIMENT_LOG = EXPERIMENT_LOG
    smooth_source.PATH_AUDIT = OrderedDict()
    smooth_source._configure_base_module()
    base._candidate_rows_for_window = _candidate_rows_for_window


def _load_source_exp002() -> dict[str, Any]:
    try:
        raw = subprocess.run(
            ["git", "show", f"HEAD:{SOURCE_EXP002_REL}"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return {
            "source": "git_HEAD",
            "path": SOURCE_EXP002_REL,
            "payload": json.loads(raw),
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        path = REPO_ROOT / SOURCE_EXP002_REL
        return {
            "source": "working_tree_fallback",
            "path": SOURCE_EXP002_REL,
            "payload": json.loads(path.read_text(encoding="utf-8")),
        }


def _close_return_to_date(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date: str,
    lookback_days: int,
) -> float | None:
    rows = ohlcv_shadow._series(snapshot, ticker)
    idx = ohlcv_shadow._row_index(rows).get(date)
    if idx is None or idx - lookback_days < 0:
        return None
    return smooth_source._close_return(rows, idx - lookback_days, idx)


def _window_label(cfg: dict[str, str]) -> str:
    return next(
        (
            label
            for label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start") or "unknown"),
    )


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_candidates = smooth_source._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    missing_market_context = 0
    market_rejected = 0
    candidates: list[dict[str, Any]] = []
    for row in raw_candidates:
        date = str(row.get("date") or "")
        qqq_ret20 = _close_return_to_date(snapshot, "QQQ", date, MARKET_LOOKBACK_DAYS)
        spy_ret20 = _close_return_to_date(snapshot, "SPY", date, MARKET_LOOKBACK_DAYS)
        if qqq_ret20 is None or spy_ret20 is None:
            missing_market_context += 1
            continue
        qqq_minus_spy = qqq_ret20 - spy_ret20
        if qqq_minus_spy <= MIN_QQQ_MINUS_SPY_RET20:
            market_rejected += 1
            continue
        candidates.append(
            {
                **row,
                "qqq_ret20": base._round(qqq_ret20, 6),
                "spy_ret20": base._round(spy_ret20, 6),
                "qqq_minus_spy_ret20": base._round(qqq_minus_spy, 6),
                "market_confirmation": "qqq_ret20_gt_spy_ret20",
                "smooth_momentum_rule_version": RULE_VERSION,
                "known_at": "signal-date close before next-open paper entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    label = _window_label(cfg)
    MARKET_GATE_AUDIT[label] = {
        "raw_smooth_momentum_candidates": len(raw_candidates),
        "missing_market_context": missing_market_context,
        "qqq_not_stronger_than_spy_rejected": market_rejected,
        "qqq_confirmed_candidates": len(candidates),
        "candidate_days_after_confirmation": len(
            {str(row.get("date") or "") for row in candidates}
        ),
        "market_rule": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
    }
    return candidates


def _source_exp002_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    source = _load_source_exp002()
    source_payload = source["payload"]
    source_by_window = source_payload["delta_metrics"]["by_window"]
    source_aggregate = source_payload["delta_metrics"]["aggregate"]
    aggregate = payload["delta_metrics"]["aggregate"]
    by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    windows_ev_regressed: list[str] = []
    windows_pnl_regressed: list[str] = []
    for label in base.WINDOWS:
        variant_delta = payload["delta_metrics"]["by_window"][label]
        source_delta = source_by_window[label]
        ev_delta_vs_source = (
            float(variant_delta["expected_value_score"])
            - float(source_delta["expected_value_score"])
        )
        pnl_delta_vs_source = (
            float(variant_delta["total_pnl"]) - float(source_delta["total_pnl"])
        )
        if ev_delta_vs_source < 0:
            windows_ev_regressed.append(label)
        if pnl_delta_vs_source < 0:
            windows_pnl_regressed.append(label)
        by_window[label] = {
            "variant_ev_delta": base._round(variant_delta["expected_value_score"], 6),
            "exp002_ev_delta": base._round(source_delta["expected_value_score"], 6),
            "ev_delta_vs_exp002": base._round(ev_delta_vs_source, 6),
            "variant_pnl_delta": base._round(variant_delta["total_pnl"], 2),
            "exp002_pnl_delta": base._round(source_delta["total_pnl"], 2),
            "pnl_delta_vs_exp002": base._round(pnl_delta_vs_source, 2),
        }

    variant_ev = float(aggregate["expected_value_score_delta_sum"])
    source_ev = float(source_aggregate["expected_value_score_delta_sum"])
    variant_pnl = float(aggregate["total_pnl_delta_sum"])
    source_pnl = float(source_aggregate["total_pnl_delta_sum"])
    return {
        "source": source["source"],
        "comparison_artifact": source["path"],
        "source_exp002_overlay_ev_delta_sum": base._round(source_ev, 6),
        "source_exp002_overlay_pnl_delta_sum": base._round(source_pnl, 2),
        "variant_overlay_ev_delta_sum": base._round(variant_ev, 6),
        "variant_overlay_pnl_delta_sum": base._round(variant_pnl, 2),
        "overlay_ev_delta_vs_exp002_sum": base._round(variant_ev - source_ev, 6),
        "overlay_pnl_delta_vs_exp002_sum": base._round(variant_pnl - source_pnl, 2),
        "windows_ev_regressed_vs_exp002": windows_ev_regressed,
        "windows_pnl_regressed_vs_exp002": windows_pnl_regressed,
        "by_window": by_window,
    }


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = smooth_source._update_payload(payload)
    decision = (
        "promising_replay_only_smooth_momentum_qqq_confirmed_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_smooth_momentum_qqq_confirmed_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "The rejected exp-20260526-002 smooth daily-return path source may be "
        "too exposed to weak growth-tape regimes. Requiring QQQ 20-day "
        "close-to-close return to exceed SPY 20-day return should retain the "
        "source's broad mid/old-window participation while removing the "
        "late_strong and drawdown failure mode."
    )
    payload["change_type"] = "smooth_momentum_path_qqq_confirmed_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 1
    payload["mechanism_family"] = "daily_return_path_free_ohlcv_candidate_pool"
    payload["trial_variant_id"] = "smooth_momentum_path_top1_qqq_confirmed_v1"
    payload["nearby_prior_experiments"] = [
        "exp-20260526-002",
        "exp-20260526-001",
        "exp-20260525-037",
        "exp-20260525-022",
        "exp-20260525-020",
        "exp-20260525-011",
        "exp-20260525-026",
    ]
    payload["multiple_testing_risk_bucket"] = "medium_high"
    payload["new_evidence_type"] = (
        "orthogonal_production_visible_qqq_vs_spy_market_confirmation_on_"
        "fixed_smooth_momentum_path_source"
    )
    payload["parameters"]["market_confirmation"] = {
        "source": "free daily OHLCV",
        "lookback_trading_days": MARKET_LOOKBACK_DAYS,
        "rule": "QQQ close-to-close return > SPY close-to-close return",
        "min_qqq_minus_spy_ret20": MIN_QQQ_MINUS_SPY_RET20,
        "known_at": "signal-date close",
        "entry_timing": "next available open",
    }
    payload["parameters"]["locked_variables"].extend(
        [
            "smooth path source thresholds from exp-20260526-002",
            "daily top-1 selection",
        ]
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool: fixed smooth daily-return-path leaders may "
            "be alpha only in a QQQ-led growth tape. This stays in the playbook's "
            "free-data daily-return pattern direction and avoids LLM soft-ranking."
        ),
        "2_history_check": {
            "exp-20260526-002": (
                "Smooth path top-1 was rejected: aggregate EV +0.2807 but "
                "late_strong regressed -0.9813 EV / -$10,944.08 and max drawdown "
                "drift was +10.25pp."
            ),
            "exp-20260526-001": (
                "Gap-and-hold with the same QQQ>SPY market conditioner was rejected, "
                "so the conditioner is not assumed universal."
            ),
            "exp-20260525-022/037": (
                "VCP+QQQ and top-2 depth were accepted as default-off paper, but "
                "playbook/memory block further VCP threshold/top-N retunes."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=20 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_003_smooth_momentum_qqq_confirmed_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for signal-date relative strength",
        "QQQ and SPY 20-day close-to-close returns known at signal-date close",
        "derived smooth-path OHLCV fields from exp-20260526-002",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["market_gate_audit"] = MARKET_GATE_AUDIT
    payload["source_exp002_comparison"] = _source_exp002_comparison(payload)
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-residual leaders because recent "
        "logs show sparse usable data. Skipped VCP, state-surface, broad-market "
        "scalar, opening-range, sector-leadership, inside-day, gap-and-hold, "
        "Space, AI-infra, and smooth-path threshold retunes due fresh rejections "
        "or anti-repeat rules. This changes only the market confirmation field "
        "on the fixed smooth-path source."
    )
    payload["interpretation"] = (
        "The smooth momentum QQQ-confirmed sleeve cleared Gate 4 as a replay-only "
        "lead, but no production/shared policy was promoted."
        if payload["gate4"]["passed"]
        else (
            "The smooth momentum QQQ-confirmed sleeve did not clear Gate 4. Do "
            "not promote it or retry nearby smooth-path / QQQ-SPY lookback "
            "thresholds on these frozen windows without forward paper rows or "
            "a materially different production-visible source field."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else payload.get("rejection_reason")
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result would still require a shared default-off paper adapter, "
        "daily report exposure, forward replacement-value ledger, and parity tests "
        "before any live/default behavior changes."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | QQQ-confirmed | Raw smooth |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["market_gate_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {confirmed} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                confirmed=audit.get("qqq_confirmed_candidates"),
                raw=audit.get("raw_smooth_momentum_candidates"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Smooth Momentum QQQ-Confirmed Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: keep exp-20260526-002 smooth-path candidate "
                "definition fixed, but admit paper candidates only when QQQ's "
                "20-day return is above SPY's 20-day return."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Market Gate Audit",
            "",
            "```json",
            json.dumps(payload["market_gate_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Comparison To exp-20260526-002",
            "",
            "```json",
            json.dumps(payload["source_exp002_comparison"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Smooth momentum QQQ-confirmed sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_modules()
    payload = _update_payload(base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "market_gate_audit": payload["market_gate_audit"],
                    "source_exp002_comparison": payload["source_exp002_comparison"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
