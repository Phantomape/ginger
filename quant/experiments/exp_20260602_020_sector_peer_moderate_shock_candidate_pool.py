"""exp-20260602-020: sector peer moderate-shock candidate pool.

This alpha search tests one free, production-visible OHLCV relation field:
after a moderate positive same-sector peer shock bucket, a liquid unshocked
peer with basic trend/RS confirmation becomes a default-off paper candidate.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_012_same_sector_peer_shock_candidate_pool as source


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-020"
STEM = "sector_peer_moderate_shock_candidate_pool"
TRIAL_FAMILY = "sector_peer_moderate_shock_candidate_pool"
CHANGED_VARIABLE = "moderate_positive_sector_peer_shock_candidate_source_v1"
RULE_VERSION = "sector_peer_moderate_positive_shock_top1_10d_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_020_{STEM}.json"
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
MIN_SECTOR_MEMBERS = 4

MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

_BASE_CANDIDATE_ROWS_FOR_WINDOW = source._candidate_rows_for_window


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(source.framework.base._safe(payload), handle, indent=2, sort_keys=True)
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


def _configure_source() -> None:
    source.EXPERIMENT_ID = EXPERIMENT_ID
    source.STEM = STEM
    source.TRIAL_FAMILY = TRIAL_FAMILY
    source.CHANGED_VARIABLE = CHANGED_VARIABLE
    source.RULE_VERSION = RULE_VERSION
    source.OUT_DIR = OUT_DIR
    source.OUT_JSON = OUT_JSON
    source.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    source.AFTER_AGG_JSON = AFTER_AGG_JSON
    source.LOG_JSON = LOG_JSON
    source.TICKET_JSON = TICKET_JSON
    source.CARD_MD = CARD_MD
    source.ARTIFACT_MD = ARTIFACT_MD
    source.EXPERIMENT_LOG = EXPERIMENT_LOG
    source.LOOKBACK_DAYS = LOOKBACK_DAYS
    source.MIN_PEER_GAP = MIN_PEER_ABS_GAP
    source.MIN_PEER_VOLUME_RATIO = MIN_PEER_VOLUME_RATIO
    source.MIN_PEER_DAY_RETURN = -1.0
    source.MIN_WEIGHTED_PEER_SHOCK_SCORE = MIN_WEIGHTED_PEER_SHOCK_SCORE
    source.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    source.MIN_CLOSE_PRICE = MIN_CLOSE_PRICE
    source.MIN_RS_20D_VS_SPY = MIN_RS_20D_VS_SPY
    source.MIN_SECTOR_MEMBERS = MIN_SECTOR_MEMBERS
    source.framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    source.framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    source.framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    source.framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    source.framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    source.framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    source._detect_positive_peer_shocks = _detect_peer_shocks
    source._candidate_rows_for_window = _candidate_rows_for_window
    source._patch_framework()


def _detect_peer_shocks(
    snapshot: dict[str, list[dict[str, Any]]],
    eligible: set[str],
    sector_by_ticker: dict[str, str],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, set[str]], Counter[str]]:
    by_sector_date: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    own_shock_dates: dict[str, set[str]] = defaultdict(set)
    audit: Counter[str] = Counter()

    for ticker in sorted(eligible):
        sector = sector_by_ticker.get(ticker)
        if not sector:
            audit["missing_sector_for_shock_detection"] += 1
            continue
        rows = source.framework.ohlcv_helper._series(snapshot, ticker)
        for idx in range(max(source.VOLUME_LOOKBACK_DAYS, 1), len(rows)):
            date = str(rows[idx].get("Date") or "")
            gap = source._gap_return(rows, idx)
            day_ret = source._day_return(rows, idx)
            volume_ratio = source._volume_ratio(rows, idx, source.VOLUME_LOOKBACK_DAYS)
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
            by_sector_date[sector][date].append(
                {
                    "ticker": ticker,
                    "date": date,
                    "gap_return": source.framework.base._round(gap, 6),
                    "day_return": source.framework.base._round(day_ret, 6),
                    "volume_ratio_20d": source.framework.base._round(volume_ratio, 6),
                    "shock_direction": "positive" if day_ret > 0 else "negative",
                }
            )
            audit["peer_gap_volume_shocks"] += 1
            if day_ret > 0:
                audit["peer_positive_day_return_shocks"] += 1
            else:
                audit["peer_non_positive_day_return_shocks"] += 1
    return by_sector_date, own_shock_dates, audit


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
        enriched["peer_shock_bucket"] = "moderate_positive"
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
    audit["rule_version"] = RULE_VERSION
    return candidates, audit


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_sector_peer_moderate_shock_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    prediction = {
        "success_probability": 0.22,
        "expected_ev_delta": 0.25,
        "expected_pnl_delta": 5000.0,
        "main_failure_modes": [
            "window_regression",
            "drawdown_drift_too_high",
            "target_sample_too_small",
            "peer_shock_noise",
        ],
        "confidence_reason": (
            "Read-only peer_earnings_transfer_probe found the sector moderate "
            "positive bucket had stronger beta-neutralized 5d/10d lift than "
            "the extreme positive bucket; prior strong peer-shock variants "
            "failed robustness."
        ),
        "recorded_at": "2026-06-02T14:08:02+00:00",
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Moderate positive same-sector OHLCV peer-shock buckets may "
                "identify delayed continuation candidates better than the "
                "previous strong peer-shock source."
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
                "exp-20260531-012",
                "exp-20260531-013",
                "exp-20260602-012",
                "exp-20260602-019",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "free_ohlcv_moderate_peer_shock_bucket_from_read_only_probe"
            ),
            "prediction": {
                **prediction,
                "actual_decision": decision,
                "actual_success": actual_success,
                "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
                "actual_ev_delta": payload["expected_value_score_delta"],
                "actual_pnl_delta": payload["total_pnl_delta"],
            },
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(source.EXCLUDED_TICKERS),
                "paper_notional_usd": source.framework.base.BASE_NOTIONAL_USD,
                "hold_days": source.framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "lookback_days": LOOKBACK_DAYS,
                "min_peer_abs_gap": MIN_PEER_ABS_GAP,
                "min_peer_volume_ratio": MIN_PEER_VOLUME_RATIO,
                "min_weighted_peer_shock_score": MIN_WEIGHTED_PEER_SHOCK_SCORE,
                "max_weighted_peer_shock_score": MAX_WEIGHTED_PEER_SHOCK_SCORE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_close_price": MIN_CLOSE_PRICE,
                "min_rs_20d_vs_spy": MIN_RS_20D_VS_SPY,
                "min_sector_members": MIN_SECTOR_MEMBERS,
                "acceptance": payload["parameters"]["acceptance"],
            },
            "preflight_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: moderate positive same-sector "
                    "peer shock score from free OHLCV may transfer into "
                    "delayed continuation for liquid unshocked peers. It "
                    "follows the playbook's free data-edge and candidate-pool "
                    "adapter direction."
                ),
                "2_prior_experiments": {
                    "peer_earnings_transfer_probe.py": (
                        "Read-only late_strong probe found sector moderate "
                        "positive buckets had positive beta-neutralized 5d/10d "
                        "lift while extreme positive buckets were muted."
                    ),
                    "exp-20260531-012/013": (
                        "Strong same-sector and same-industry peer shock "
                        "candidate pools were rejected."
                    ),
                    "exp-20260602-012/019": (
                        "Post-earnings exact-industry and same-sector peer "
                        "transfer were positive in aggregate but failed window "
                        "or drawdown/sample robustness gates."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md late_strong, mid_weak, old_thin "
                    "windows; aggregate EV/PnL positive, no EV/PnL window "
                    "regression, >=20 target trades across all 3 windows, "
                    "drawdown drift <=0.5pp, survival >=5%, and concentration "
                    "guardrails pass."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_020_sector_peer_moderate_shock_candidate_pool.py"
                ),
            },
            "gate2": {
                **payload["gate2"],
                "target_trade_field_coverage": source.framework._field_coverage(
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
                        "avg_dollar_volume_20d",
                        "ma50",
                        "rs20_vs_spy",
                    ],
                ),
                "runtime_fields": [
                    "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                    "SPY OHLCV rows for signal-date relative strength",
                    "offline deterministic broad_market_sector_map cache",
                    "operator_inputs/open_positions.json entry_date",
                    "operator_inputs/open_positions.json target_price",
                ],
                "note": (
                    "The source uses only signal-date-known OHLCV, prior peer "
                    "shock rows, sector cache metadata, and SPY OHLCV. It does "
                    "not ask the LLM or production code to infer hidden fields."
                ),
            },
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
                "Skipped LLM soft-ranking because replay-safe joins remain "
                "sparse. Skipped Companyfacts/VBB/FINRA/consensus/Space/"
                "state-surface retunes because the playbook asks for forward "
                "rows or materially new fields. This run tests one free-OHLCV "
                "peer-shock bucket instead of adding noisy tickers."
            ),
            "interpretation": (
                "The sector peer moderate-shock source cleared Gate 4 as a "
                "replay-only lead, but no production/shared policy was "
                "promoted."
                if gate4["passed"]
                else (
                    "The sector peer moderate-shock source did not clear Gate "
                    "4. Do not promote it or retry nearby peer-shock bucket "
                    "thresholds on these frozen windows without forward rows "
                    "or a stronger relation source."
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
    for label in source.framework.base.WINDOWS:
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
            f"# {EXPERIMENT_ID} Sector Peer Moderate-Shock Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits liquid same-sector peers when the prior 1..5 trading-day peer-shock score is positive but below the strong bucket.",
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
    source.framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def main() -> int:
    _configure_source()
    payload = _postprocess_payload(source.framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            source.framework.base._safe(
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
