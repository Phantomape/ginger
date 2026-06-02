"""exp-20260602-021: sector peer moderate-shock ticker cooldown.

This alpha search keeps the exp-20260602-020 moderate same-sector peer-shock
candidate source fixed, then changes one governance variable: a selected
ticker cannot be admitted again for 30 calendar days. The goal is to test
whether the all-window EV lift survives without repeated ticker concentration.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260602_020_sector_peer_moderate_shock_candidate_pool as prior


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-021"
STEM = "sector_peer_moderate_shock_ticker_cooldown"
TRIAL_FAMILY = "sector_peer_moderate_shock_candidate_pool"
CHANGED_VARIABLE = "sector_peer_moderate_shock_same_ticker_cooldown_days"
RULE_VERSION = "sector_peer_moderate_positive_shock_top1_10d_ticker_cooldown_30d_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_021_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

SAME_TICKER_COOLDOWN_DAYS = 30
_BASE_SELECT_PAPER_TRADES = prior.source.framework._select_paper_trades


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(prior.source.framework.base._safe(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _select_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    last_selected_by_ticker: dict[str, date] = {}

    for row in candidates:
        ticker = str(row.get("ticker") or "").upper()
        signal_date = str(row.get("date") or "")
        parsed_signal_date = _parse_date(signal_date)
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= prior.MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        prior_selected_date = last_selected_by_ticker.get(ticker)
        if parsed_signal_date is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_for_cooldown"})
            continue
        if prior_selected_date is not None:
            days_since = (parsed_signal_date - prior_selected_date).days
            if days_since < SAME_TICKER_COOLDOWN_DAYS:
                filtered.append(
                    {
                        **row,
                        "filter_reason": "same_ticker_selected_admission_cooldown",
                        "cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
                        "days_since_prior_selected_admission": days_since,
                        "prior_selected_admission_date": prior_selected_date.isoformat(),
                    }
                )
                continue
        trade = prior.source.framework.base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(
            {
                **trade,
                "ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
                "prior_selected_admission_date": (
                    prior_selected_date.isoformat() if prior_selected_date else None
                ),
            }
        )
        used_date_counts[signal_date] += 1
        last_selected_by_ticker[ticker] = parsed_signal_date
    return selected, filtered


def _configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    prior.AFTER_AGG_JSON = AFTER_AGG_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.ARTIFACT_MD = ARTIFACT_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior._configure_source()
    prior.source.framework._select_paper_trades = _select_paper_trades


def _cooldown_summary(payload: dict[str, Any]) -> dict[str, Any]:
    filtered_reasons: Counter[str] = Counter()
    filtered_by_ticker: Counter[str] = Counter()
    filtered_by_window: Counter[str] = Counter()
    selected_by_ticker: Counter[str] = Counter()
    selected_by_window: Counter[str] = Counter()

    for label, rows in payload["filtered_candidates_sample_by_window"].items():
        for row in rows:
            reason = str(row.get("filter_reason") or "")
            filtered_reasons[reason] += 1
            if reason == "same_ticker_selected_admission_cooldown":
                filtered_by_ticker[str(row.get("ticker") or "").upper()] += 1
                filtered_by_window[label] += 1
    for label, trades in payload["target_trades_by_window"].items():
        selected_by_window[label] += len(trades)
        for trade in trades:
            selected_by_ticker[str(trade.get("ticker") or "").upper()] += 1

    return {
        "cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "filter_reason_counts_sample": dict(sorted(filtered_reasons.items())),
        "cooldown_filtered_by_ticker_sample": dict(sorted(filtered_by_ticker.items())),
        "cooldown_filtered_by_window_sample": dict(sorted(filtered_by_window.items())),
        "selected_by_ticker": dict(sorted(selected_by_ticker.items())),
        "selected_by_window": dict(sorted(selected_by_window.items())),
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_sector_peer_moderate_shock_ticker_cooldown"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    prediction = {
        "success_probability": 0.24,
        "expected_ev_delta": 0.75,
        "expected_pnl_delta": 12000.0,
        "main_failure_modes": [
            "edge_was_app_concentration",
            "window_regression",
            "target_sample_too_small",
            "cooldown_cuts_winners",
        ],
        "confidence_reason": (
            "exp-20260602-020 improved EV/PnL in all three windows but failed "
            "only concentration. A selected-admission cooldown directly tests "
            "whether the relation survives without repeated ticker exposure."
        ),
        "recorded_at": "2026-06-02T15:09:05+00:00",
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Sector peer moderate-shock paper candidates may keep the "
                "exp-20260602-020 all-window EV lift while reducing "
                "concentration if same-ticker selected admissions observe a "
                "fixed cooldown."
            ),
            "change_type": "default_off_paper_candidate_pool_governance",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260602-020",
                "exp-20260602-019",
                "exp-20260602-018",
                "exp-20260602-012",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "failure_mode_targeted_deconcentration",
            "prediction": {
                **prediction,
                "actual_decision": decision,
                "actual_success": actual_success,
                "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
                "actual_ev_delta": payload["expected_value_score_delta"],
                "actual_pnl_delta": payload["total_pnl_delta"],
                "realized_failure_modes": gate4["failed_reasons"],
            },
            "parameters": {
                **payload["parameters"],
                "same_ticker_selected_admission_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
                "selection_rank_locked_from_exp_20260602_020": True,
                "peer_shock_thresholds_locked_from_exp_20260602_020": True,
                "paper_notional_locked": True,
                "hold_days_locked": True,
            },
            "preflight_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry governance: the moderate same-sector "
                    "peer-shock relation from exp-20260602-020 may be real, but "
                    "the raw route over-admits repeated winners. A selected "
                    "same-ticker cooldown should reduce concentration while "
                    "leaving the free OHLCV relation itself fixed."
                ),
                "2_prior_experiments": {
                    "exp-20260602-020": (
                        "Same source, no cooldown: aggregate EV +2.6078 and "
                        "PnL +$58,440.11, 3/3 windows improved, but max single "
                        "positive share 0.761365 and HHI 0.602404 failed."
                    ),
                    "exp-20260602-019": (
                        "Post-earnings same-sector peer transfer was positive "
                        "in aggregate but failed late_strong EV and drawdown."
                    ),
                    "exp-20260602-018": (
                        "Sector-relative risk-adjusted momentum had 272 trades "
                        "but failed two windows and drawdown."
                    ),
                    "exp-20260602-012": (
                        "Early peer earnings transfer was thin and concentrated."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md late_strong, mid_weak, old_thin "
                    "windows; aggregate EV/PnL positive, no EV/PnL window "
                    "regression, >=20 target trades across all 3 windows, "
                    "drawdown drift <=0.5pp, survival >=5%, max single positive "
                    "share <=0.40, and HHI <=0.30."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_021_sector_peer_moderate_shock_ticker_cooldown.py"
                ),
            },
            "gate2": {
                **payload["gate2"],
                "target_trade_field_coverage": prior.source.framework._field_coverage(
                    all_target_trades,
                    [
                        "ticker",
                        "sector",
                        "sector_lookup",
                        "signal_date",
                        "entry_date",
                        "exit_date",
                        "entry_price",
                        "exit_price",
                        "pnl",
                        "known_at",
                        "peer_shock_bucket",
                        "peer_shock_score",
                        "peer_shock_count",
                        "peer_shock_unique_tickers",
                        "peer_shock_events_sample",
                        "ticker_cooldown_days",
                        "prior_selected_admission_date",
                    ],
                ),
            },
            "cooldown_summary": _cooldown_summary(payload),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "A passing replay still requires a shared default-off paper "
                    "adapter and parity tests before production reports or any "
                    "order path can use the source."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking due sparse replay-safe attribution. "
                "Skipped Companyfacts/VBB/FINRA/consensus/state-surface retunes "
                "because recent logs require forward rows or materially new "
                "fields. This run targets the exact exp020 failure mode instead "
                "of adding noise tickers or retuning peer-shock thresholds."
            ),
            "interpretation": (
                "The cooldown reduced concentration enough for a replay-only "
                "lead, but no shared production adapter was promoted."
                if gate4["passed"]
                else (
                    "The cooldown did not produce a promotable three-window "
                    "candidate-pool improvement. Do not retry nearby "
                    "sector-peer moderate-shock cooldown/threshold variants on "
                    "these frozen windows without forward replacement rows."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a materially stronger "
                "relation source such as customer/supplier links, source "
                "overlap, or audited multi-season early-peer earnings transfer."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(BEFORE_AGG_JSON),
        _repo_rel(AFTER_AGG_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.source.framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    cooldown = payload["cooldown_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Sector Peer Moderate-Shock Ticker Cooldown",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            f"Single variable: selected same-ticker admission cooldown = `{SAME_TICKER_COOLDOWN_DAYS}` calendar days on top of the fixed exp-20260602-020 moderate peer-shock source.",
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
            "## Cooldown Diagnostics",
            "",
            "```json",
            json.dumps(cooldown, indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _write_manifest() -> None:
    files = {
        "runner": _repo_rel(Path(__file__)),
        "result": _repo_rel(OUT_JSON),
        "before_aggregate": _repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": _repo_rel(AFTER_AGG_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "card": _repo_rel(CARD_MD),
        "artifact": _repo_rel(ARTIFACT_MD),
        "manifest": _repo_rel(MANIFEST_JSON),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    _write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    _write_json(LOG_JSON, payload)
    report = _build_report(payload)
    _write_text(ARTIFACT_MD, report)
    _write_text(CARD_MD, report)

    ticket = _load_json(TICKET_JSON)
    ticket.update(
        {
            "status": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)
    prior.source.framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def main() -> int:
    _configure_prior()
    payload = _postprocess_payload(prior.source.framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            prior.source.framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "cooldown_summary": payload["cooldown_summary"],
                    "artifact": _repo_rel(ARTIFACT_MD),
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
