"""exp-20260602-029: exact-industry moderate peer-shock candidate pool.

This alpha search keeps the exp-20260602-020 moderate OHLCV peer-shock bucket
but changes the relation source from broad sector to exact cached industry.
The experiment is replay-only/default-off paper; it does not alter core
signals, ranking, sizing, exits, watchlists, LLM/news, or live orders.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_013_same_industry_peer_shock_candidate_pool as prior


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-029"
STEM = "industry_peer_moderate_shock_candidate_pool"
TRIAL_FAMILY = "industry_peer_moderate_shock_candidate_pool"
CHANGED_VARIABLE = "moderate_positive_industry_peer_shock_candidate_source_v1"
RULE_VERSION = "industry_peer_moderate_positive_shock_top1_10d_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_029_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

LOOKBACK_DAYS = 5
MIN_PEER_ABS_GAP = 0.05
MIN_PEER_VOLUME_RATIO = 1.80
MIN_WEIGHTED_PEER_SHOCK_SCORE = 0.000001
MAX_WEIGHTED_PEER_SHOCK_SCORE = 0.03
MIN_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MIN_CLOSE_PRICE = 10.0
MIN_RS_20D_VS_SPY = 0.0
MIN_INDUSTRY_MEMBERS = 2

MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

_BASE_CANDIDATE_ROWS_FOR_WINDOW = prior._candidate_rows_for_window


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(prior.framework.base._safe(payload), handle, indent=2, sort_keys=True)
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


def _detect_peer_shocks(
    snapshot: dict[str, list[dict[str, Any]]],
    eligible: set[str],
    industry_by_ticker: dict[str, str],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, set[str]], Counter[str]]:
    by_industry_date: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    own_shock_dates: dict[str, set[str]] = defaultdict(set)
    audit: Counter[str] = Counter()

    for ticker in sorted(eligible):
        industry = industry_by_ticker.get(ticker)
        if not industry:
            audit["missing_industry_for_shock_detection"] += 1
            continue
        rows = prior.framework.ohlcv_helper._series(snapshot, ticker)
        for idx in range(max(prior.VOLUME_LOOKBACK_DAYS, 1), len(rows)):
            date = str(rows[idx].get("Date") or "")
            gap = prior._gap_return(rows, idx)
            day_ret = prior._day_return(rows, idx)
            volume_ratio = prior._volume_ratio(rows, idx, prior.VOLUME_LOOKBACK_DAYS)
            if gap is None or day_ret is None or volume_ratio is None:
                audit["missing_shock_context"] += 1
                continue
            if abs(gap) < MIN_PEER_ABS_GAP:
                audit["peer_abs_gap_below_threshold"] += 1
                continue
            if volume_ratio < MIN_PEER_VOLUME_RATIO:
                audit["peer_volume_ratio_below_threshold"] += 1
                continue
            own_shock_dates[ticker].add(date)
            by_industry_date[industry][date].append(
                {
                    "ticker": ticker,
                    "date": date,
                    "gap_return": prior.framework.base._round(gap, 6),
                    "day_return": prior.framework.base._round(day_ret, 6),
                    "volume_ratio_20d": prior.framework.base._round(volume_ratio, 6),
                    "shock_direction": "positive" if day_ret > 0 else "negative",
                }
            )
            audit["peer_gap_volume_shocks"] += 1
            if day_ret > 0:
                audit["peer_positive_day_return_shocks"] += 1
            else:
                audit["peer_non_positive_day_return_shocks"] += 1
    return by_industry_date, own_shock_dates, audit


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_candidates, audit = _BASE_CANDIDATE_ROWS_FOR_WINDOW(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    bucket_audit: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for row in raw_candidates:
        score = float(row.get("peer_shock_score") or 0.0)
        if score <= 0.0:
            bucket_audit["peer_shock_score_not_positive"] += 1
            continue
        if score >= MAX_WEIGHTED_PEER_SHOCK_SCORE:
            bucket_audit["peer_shock_score_above_moderate_bucket"] += 1
            continue
        enriched = dict(row)
        enriched["strategy"] = STEM
        enriched["rule_version"] = RULE_VERSION
        enriched["peer_shock_bucket"] = "moderate_positive_industry"
        enriched["peer_relation_source"] = "exact_yfinance_industry_match"
        enriched["peer_relation_key"] = enriched.get("industry")
        enriched["peer_shock_thresholds"] = {
            "min_peer_abs_gap": MIN_PEER_ABS_GAP,
            "min_peer_volume_ratio": MIN_PEER_VOLUME_RATIO,
            "min_weighted_peer_shock_score": MIN_WEIGHTED_PEER_SHOCK_SCORE,
            "max_weighted_peer_shock_score": MAX_WEIGHTED_PEER_SHOCK_SCORE,
        }
        candidates.append(enriched)

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["peer_shock_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    audit = dict(audit)
    audit["raw_pre_bucket_candidate_count"] = len(raw_candidates)
    audit["moderate_bucket_reject_counts"] = dict(sorted(bucket_audit.items()))
    audit["moderate_bucket_candidate_count"] = len(candidates)
    audit["relation_source"] = "exact_yfinance_industry_match"
    audit["rule_version"] = RULE_VERSION
    return candidates, audit


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
    prior.LOOKBACK_DAYS = LOOKBACK_DAYS
    prior.MIN_PEER_GAP = MIN_PEER_ABS_GAP
    prior.MIN_PEER_VOLUME_RATIO = MIN_PEER_VOLUME_RATIO
    prior.MIN_PEER_DAY_RETURN = -1.0
    prior.MIN_WEIGHTED_PEER_SHOCK_SCORE = MIN_WEIGHTED_PEER_SHOCK_SCORE
    prior.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    prior.MIN_CLOSE_PRICE = MIN_CLOSE_PRICE
    prior.MIN_RS_20D_VS_SPY = MIN_RS_20D_VS_SPY
    prior.MIN_INDUSTRY_MEMBERS = MIN_INDUSTRY_MEMBERS
    prior.framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    prior.framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    prior.framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    prior.framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    prior.framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    prior.framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    prior._detect_positive_peer_shocks = _detect_peer_shocks
    prior._candidate_rows_for_window = _candidate_rows_for_window
    prior._build_report = _build_report
    prior._patch_framework()


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_industry_peer_moderate_shock_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    predicted_success_probability = 0.24
    expected_ev_delta = 0.35
    expected_pnl_delta = 7500.0
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Moderate positive exact-industry OHLCV peer shocks may produce "
                "cleaner delayed-continuation paper candidates than same-sector "
                "peer shocks."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260531-013",
                "exp-20260602-020",
                "exp-20260602-021",
                "exp-20260602-012",
                "exp-20260602-019",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_production_visible_relation_field",
            "prediction": {
                "success_probability": predicted_success_probability,
                "expected_ev_delta": expected_ev_delta,
                "expected_pnl_delta": expected_pnl_delta,
                "main_failure_modes": [
                    "target_sample_too_small",
                    "window_regression",
                    "target_concentration_failed",
                    "industry_relation_too_sparse",
                ],
                "confidence_reason": (
                    "Sector moderate peer shock had large aggregate evidence "
                    "but failed concentration. Exact industry is a stronger "
                    "free relation source, while prior strong industry shock "
                    "was too noisy."
                ),
                "recorded_at": "2026-06-02T21:06:04+00:00",
                "actual_decision": decision,
                "actual_success": actual_success,
                "brier_score": round((predicted_success_probability - actual_success) ** 2, 6),
                "actual_ev_delta": payload["expected_value_score_delta"],
                "actual_pnl_delta": payload["total_pnl_delta"],
                "realized_failure_modes": gate4["failed_reasons"],
            },
            "calibration": {
                "actual_decision": decision,
                "actual_success": actual_success,
                "predicted_success_probability": predicted_success_probability,
                "brier_score": round((predicted_success_probability - actual_success) ** 2, 6),
                "expected_ev_delta": expected_ev_delta,
                "actual_ev_delta": payload["expected_value_score_delta"],
                "ev_prediction_error": prior.framework.base._round(
                    payload["expected_value_score_delta"] - expected_ev_delta,
                    6,
                ),
                "expected_pnl_delta": expected_pnl_delta,
                "actual_pnl_delta": payload["total_pnl_delta"],
                "pnl_prediction_error": prior.framework.base._round(
                    payload["total_pnl_delta"] - expected_pnl_delta,
                    2,
                ),
                "predicted_failure_modes": [
                    "target_sample_too_small",
                    "window_regression",
                    "target_concentration_failed",
                    "industry_relation_too_sparse",
                ],
                "realized_failure_mode": (
                    gate4["failed_reasons"][0] if gate4.get("failed_reasons") else None
                ),
                "predicted_failure_mode_hit": bool(
                    set(gate4.get("failed_reasons") or set()).intersection(
                        {
                            "target_sample_too_small",
                            "window_ev_regression",
                            "window_pnl_regression",
                            "target_concentration_failed",
                            "drawdown_drift_too_high",
                        }
                    )
                ),
            },
        }
    )
    payload["preflight_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: exact-industry moderate peer shocks may "
            "transfer delayed continuation with less sector-level noise. This "
            "matches the playbook preference for free production-visible "
            "relation fields and candidate-pool paper adapters."
        ),
        "2_prior_experiments": {
            "exp-20260531-013": (
                "Strong exact-industry peer shock was rejected; the shock bucket "
                "was too strong/noisy and did not survive Gate 4."
            ),
            "exp-20260602-020": (
                "Moderate same-sector peer shock improved all windows by "
                "+2.6078 EV / +$58,440.11 but failed concentration, led by APP."
            ),
            "exp-20260602-021": (
                "A 30-day ticker cooldown cut the repeated winners and caused "
                "late_strong regression, so simple governance did not retain "
                "the edge."
            ),
            "exp-20260602-012/019": (
                "Post-earnings exact-industry and same-sector peer transfer had "
                "positive aggregate evidence but failed robustness/sample or "
                "drawdown gates."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md late_strong, mid_weak, old_thin windows; "
            "positive aggregate EV/PnL, no EV/PnL-regressed window, >=20 target "
            "trades across all 3 windows, drawdown drift <=0.5pp, survival >=5%, "
            "max single positive share <=0.40, and positive HHI <=0.30."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260602_029_industry_peer_moderate_shock_candidate_pool.py"
        ),
    }
    payload["parameters"].update(
        {
            "base_source": "exact industry moderate peer-shock candidate source",
            "lookback_days": LOOKBACK_DAYS,
            "min_peer_abs_gap": MIN_PEER_ABS_GAP,
            "min_peer_volume_ratio": MIN_PEER_VOLUME_RATIO,
            "min_weighted_peer_shock_score": MIN_WEIGHTED_PEER_SHOCK_SCORE,
            "max_weighted_peer_shock_score": MAX_WEIGHTED_PEER_SHOCK_SCORE,
            "min_industry_members": MIN_INDUSTRY_MEMBERS,
            "relation_source": "data/reference/broad_market_sector_map.json industry",
            "paper_notional_usd": prior.framework.base.BASE_NOTIONAL_USD,
            "hold_days": prior.framework.base.HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        }
    )
    payload["gate2"]["target_trade_field_coverage"] = prior.framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "industry",
            "sector",
            "relation_lookup",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "peer_shock_bucket",
            "peer_relation_source",
            "peer_relation_key",
            "peer_shock_score",
            "peer_shock_count",
            "peer_shock_unique_tickers",
            "peer_shock_events_sample",
            "avg_dollar_volume_20d",
            "ma50",
            "rs20_vs_spy",
        ],
    )
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV rows for signal-date relative strength",
        "data/reference/broad_market_sector_map.json industry/sector cache",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The source uses only signal-date-known OHLCV, prior peer shock rows, "
        "cached industry metadata, and SPY OHLCV. It does not add LLM authority "
        "or infer hidden production fields."
    )
    payload["production_impact"] = {
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
            "A passing replay still requires a shared default-off paper adapter "
            "and parity tests before production reports or any order path can "
            "use the source."
        ),
    }
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because replay-safe joins remain sparse. "
        "Skipped Companyfacts/VBB/FINRA/consensus/Space/state-surface/post-"
        "earnings threshold retunes because recent logs require forward rows "
        "or materially new fields. This changes relation construction instead "
        "of peer-shock thresholds, ticker blacklist, notional, hold, or rank."
    )
    payload["interpretation"] = (
        "The exact-industry moderate peer-shock source cleared Gate 4 as a "
        "replay-only lead, but no production/shared adapter was promoted."
        if gate4["passed"]
        else (
            "The exact-industry moderate peer-shock source did not clear Gate "
            "4. Do not retry nearby OHLCV peer-shock relation/threshold variants "
            "on these frozen windows without forward replacement rows or a "
            "stronger non-price relation source."
        )
    )
    payload["rejection_reason"] = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    payload["next_evidence_needed"] = (
        "Forward replacement-value rows or a materially stronger non-price "
        "relation source such as customer/supplier links, source overlap, or "
        "audited multi-season early-peer earnings transfer."
    )
    payload["anti_js"] = "No JavaScript was used."
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
    for label in prior.framework.base.WINDOWS:
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
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Exact-Industry Moderate Peer-Shock Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: default-off paper candidates from liquid unshocked peers after moderate positive exact-industry OHLCV peer shocks.",
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
    prior.framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def main() -> int:
    _configure_prior()
    payload = _postprocess_payload(prior.framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            prior.framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
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
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
