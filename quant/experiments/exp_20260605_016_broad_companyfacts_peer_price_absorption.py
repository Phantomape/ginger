"""exp-20260605-016: Broad Companyfacts peer price absorption.

This alpha search tests one replay-only/default-off paper candidate source:
own SEC Companyfacts dual realized growth is only eligible when a recent
same-industry peer dual-growth filing has also been absorbed by price action.
It keeps the Companyfacts relationship idea, but changes the independent
causal variable from peer fundamental confirmation to peer price absorption.

No production adapter, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260605_014_broad_companyfacts_peer_confirmed_filing_drift as peer_base


EXP_ID = "exp-20260605-016"
STEM = "broad_companyfacts_peer_price_absorption"
TRIAL_FAMILY = "broad_companyfacts_peer_price_absorption_candidate_pool"
TRIAL_VARIANT_ID = "broad_companyfacts_peer_price_absorption_top1_v1"
CHANGED_VARIABLE = "broad_companyfacts_peer_price_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = peer_base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_016_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"

PEER_ABSORPTION_LOOKBACK_DAYS = 45
MIN_PEER_ABSORPTION_AGE_DAYS = 5
MIN_PEER_ABSORPTION_RETURN = 0.02
MIN_PEER_ABSORPTION_EXCESS_SPY = 0.00
MIN_PEER_ABSORPTION_CLOSE_LOCATION = 0.55

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. A positive result would "
        "require a separate shared default-off Companyfacts peer-price "
        "absorption adapter, daily production exposure of the same "
        "filed-date-safe growth, industry, and OHLCV peer absorption fields, "
        "warehouse/snapshot replay parity, and focused tests before any "
        "report queue, paper ledger, candidate priority, or order surface "
        "could change."
    ),
}

_FRAMES: dict[str, pd.DataFrame] = {}
_ORIGINAL_GENERATE = peer_base._generate_candidates


def _repo_rel(path: Path | str) -> str:
    return peer_base.base._repo_rel(path)


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frame_pos(frame: pd.DataFrame, day: pd.Timestamp) -> int | None:
    return peer_base.base._frame_pos(frame, day)


def _peer_absorption_state(
    *,
    peer_ticker: str,
    peer_growth: dict[str, Any],
    signal_day_s: str,
) -> dict[str, Any] | None:
    peer_frame = _FRAMES.get(peer_ticker)
    spy_frame = _FRAMES.get("SPY")
    if peer_frame is None or spy_frame is None:
        return None

    signal_day = pd.Timestamp(signal_day_s)
    signal_pos = _frame_pos(peer_frame, signal_day)
    spy_signal_pos = _frame_pos(spy_frame, signal_day)
    if signal_pos is None or spy_signal_pos is None:
        return None

    filing_day = pd.Timestamp(peer_growth["filing_date"])
    filing_pos = int(peer_frame.index.searchsorted(filing_day, side="left"))
    spy_filing_pos = int(spy_frame.index.searchsorted(filing_day, side="left"))
    if filing_pos < 0 or spy_filing_pos < 0:
        return None
    if filing_pos >= signal_pos or spy_filing_pos >= spy_signal_pos:
        return None
    if filing_pos >= len(peer_frame) or spy_filing_pos >= len(spy_frame):
        return None

    absorption_age_days = (signal_day - filing_day).days
    if absorption_age_days < MIN_PEER_ABSORPTION_AGE_DAYS:
        return None
    if absorption_age_days > PEER_ABSORPTION_LOOKBACK_DAYS:
        return None

    start_close = float(peer_frame["Close"].iloc[filing_pos])
    signal_close = float(peer_frame["Close"].iloc[signal_pos])
    spy_start_close = float(spy_frame["Close"].iloc[spy_filing_pos])
    spy_signal_close = float(spy_frame["Close"].iloc[spy_signal_pos])
    if min(start_close, signal_close, spy_start_close, spy_signal_close) <= 0.0:
        return None

    peer_return = signal_close / start_close - 1.0
    spy_return = spy_signal_close / spy_start_close - 1.0
    excess_spy = peer_return - spy_return
    close_location = peer_base.base._close_location(peer_frame, signal_pos)
    if close_location is None:
        return None
    if peer_return < MIN_PEER_ABSORPTION_RETURN:
        return None
    if excess_spy < MIN_PEER_ABSORPTION_EXCESS_SPY:
        return None
    if close_location < MIN_PEER_ABSORPTION_CLOSE_LOCATION:
        return None

    return {
        "ticker": peer_ticker,
        "filing_date": peer_growth["filing_date"],
        "filing_age_days": peer_growth["filing_age_days"],
        "absorption_age_days": absorption_age_days,
        "absorption_return": round(peer_return, 6),
        "absorption_spy_return": round(spy_return, 6),
        "absorption_excess_spy": round(excess_spy, 6),
        "absorption_close_location": round(close_location, 6),
        "revenue_yoy_growth": round(peer_growth["revenue_growth"], 6),
        "profit_yoy_growth": round(peer_growth["profit_growth"], 6),
        "growth_score": round(peer_growth["growth_score"], 6),
    }


def _peer_absorption_confirmations(
    *,
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day_s: str,
    industry: str,
    industry_groups: dict[str, list[str]],
) -> list[dict[str, Any]]:
    confirmations: list[dict[str, Any]] = []
    for peer_ticker in industry_groups.get(industry, []):
        if peer_ticker == ticker:
            continue
        peer_growth = peer_base._latest_dual_growth(growth_index, peer_ticker, signal_day_s)
        if peer_growth is None:
            continue
        state = _peer_absorption_state(
            peer_ticker=peer_ticker,
            peer_growth=peer_growth,
            signal_day_s=signal_day_s,
        )
        if state is not None:
            confirmations.append(state)
    confirmations.sort(
        key=lambda row: (
            float(row["absorption_excess_spy"]),
            float(row["absorption_return"]),
            float(row["growth_score"]),
            -int(row["absorption_age_days"]),
        ),
        reverse=True,
    )
    return confirmations


def _score_candidate(
    *,
    own_growth_score: float,
    peer_confirmations: list[dict[str, Any]],
    ret20_excess_spy: float,
    close_location: float,
    volume_ratio_20d: float,
) -> float:
    peer_count = min(len(peer_confirmations), 4)
    absorption_score = sum(float(row["absorption_excess_spy"]) for row in peer_confirmations[:3])
    return (
        own_growth_score
        + 0.35 * peer_count
        + 3.5 * min(absorption_score, 0.35)
        + 3.0 * ret20_excess_spy
        + close_location
        + 0.10 * min(volume_ratio_20d, 3.0)
    )


def _generate_candidates(
    frames: dict[str, pd.DataFrame],
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    global _FRAMES
    _FRAMES = frames
    selected, audit = _ORIGINAL_GENERATE(frames, growth_index)
    audit["peer_absorption_rule"] = {
        "lookback_days": PEER_ABSORPTION_LOOKBACK_DAYS,
        "min_age_days": MIN_PEER_ABSORPTION_AGE_DAYS,
        "min_return": MIN_PEER_ABSORPTION_RETURN,
        "min_excess_spy": MIN_PEER_ABSORPTION_EXCESS_SPY,
        "min_close_location": MIN_PEER_ABSORPTION_CLOSE_LOCATION,
    }
    return selected, audit


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate4 = peer_base.base._gate4(aggregate_comparison, results, target_summary)
    if gate4["passed"]:
        gate4["decision"] = "positive_replay_lead_not_promoted_requires_shared_adapter"
    else:
        gate4["decision"] = "rejected_broad_companyfacts_peer_price_absorption_candidate_pool"
    gate4["requires_parity_before_promotion"] = True
    gate4["production_parity_note"] = PRODUCTION_IMPACT["parity_note"]
    return gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXP_ID
    payload["anti_js"] = "No JavaScript was used."
    payload["preflight"] = {
        "alpha_hypothesis": (
            "Broad Companyfacts filing events with positive realized growth "
            "and recent peer price absorption may add cleaner default-off "
            "paper candidates than same-industry growth confirmation."
        ),
        "category": "entry_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260605-014",
            "exp-20260605-015",
            "exp-20260605-011",
            "exp-20260604-014",
        ],
        "single_causal_variable": CHANGED_VARIABLE,
        "success_standard": (
            "Canonical three-window before/after aggregate EV and PnL must "
            "improve, no window EV/PnL regression, max drawdown drift <= "
            f"{peer_base.MAX_DRAWDOWN_WORSE}, target trades >= "
            f"{peer_base.MIN_TARGET_TRADES}, all three windows represented, "
            "concentration within guardrails."
        ),
        "reproducible_if_failed": True,
    }
    payload["parameters"] = {
        "paper_notional": peer_base.PAPER_NOTIONAL,
        "hold_days": peer_base.HOLD_DAYS,
        "max_fundamental_age_days": peer_base.MAX_FUNDAMENTAL_AGE_DAYS,
        "min_revenue_yoy_growth": peer_base.MIN_REVENUE_YOY_GROWTH,
        "min_profit_yoy_growth": peer_base.MIN_PROFIT_YOY_GROWTH,
        "min_price": peer_base.MIN_PRICE,
        "min_avg_dollar_volume_20d": peer_base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": peer_base.MIN_RET20_EXCESS_SPY,
        "min_close_location": peer_base.MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": peer_base.MIN_VOLUME_RATIO_20D,
        "same_ticker_cooldown_days": peer_base.SAME_TICKER_COOLDOWN_DAYS,
        "peer_absorption_lookback_days": PEER_ABSORPTION_LOOKBACK_DAYS,
        "min_peer_absorption_age_days": MIN_PEER_ABSORPTION_AGE_DAYS,
        "min_peer_absorption_return": MIN_PEER_ABSORPTION_RETURN,
        "min_peer_absorption_excess_spy": MIN_PEER_ABSORPTION_EXCESS_SPY,
        "min_peer_absorption_close_location": MIN_PEER_ABSORPTION_CLOSE_LOCATION,
        "daily_selection": "top_1_by_fixed_peer_price_absorbed_growth_drift_score",
        "round_trip_cost_pct": peer_base.base.ROUND_TRIP_COST_PCT,
        "trade_enabled": False,
    }
    payload["gate4"] = _gate4(
        payload["aggregate"]["comparison"],
        payload["results"],
        payload["target_summary"],
    )
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["next_retry_requires"] = [
        "do not retune Companyfacts peer absorption thresholds on the frozen windows",
        "collect forward paper replacement-value rows before revisiting this relation",
        "a positive result would still require a shared default-off adapter with parity tests",
        "use a genuinely new free-data relation if this fails",
    ]
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(TICKET_JSON),
        _repo_rel(peer_base.base.GROWTH_PATH),
        "data/reference/broad_market_sector_map.json",
    ]
    return payload


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    prediction = payload.get("prediction") or {}
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["completed_at"],
        "status": payload["gate4"]["status"],
        "lane": "alpha_search",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Tested a replay-only broad Companyfacts candidate source that "
            "requires own fresh dual growth plus a recent same-industry "
            "peer growth filing whose price action was absorbed before the "
            "signal date."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260605-014",
            "exp-20260605-015",
            "exp-20260605-011",
            "exp-20260604-014",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_companyfacts_price_relation_field",
        "component": _repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": comparison,
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["gate4"]["decision"],
        "rejection_reason": ";".join(payload["gate4"]["failed_reasons"])
        if payload["gate4"]["failed_reasons"]
        else None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "prediction": {
            **prediction,
            "actual_success": actual_success,
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - actual_success) ** 2,
                6,
            ),
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "anti_js": "No JavaScript was used.",
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} Broad Companyfacts Peer Price Absorption",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Hypothesis",
        "",
        payload["preflight"]["alpha_hypothesis"],
        "",
        "## Gate 1-4",
        "",
        peer_base.base._window_table(payload["results"]),
        "",
        "## Candidate Audit",
        "",
        "```json",
        json.dumps(payload["candidate_audit"], indent=2, sort_keys=True),
        "```",
        "",
        "## Gate 4",
        "",
    ]
    for key, value in payload["gate4"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_016_broad_companyfacts_peer_price_absorption.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    text = "\n".join(lines) + "\n"
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(text, encoding="utf-8")
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text(text, encoding="utf-8")


def _write_manifest() -> None:
    files = {
        "runner": Path(__file__),
        "result": OUT_JSON,
        "before_aggregate": BEFORE_JSON,
        "after_aggregate": AFTER_JSON,
        "log": LOG_JSON,
        "ticket": TICKET_JSON,
        "card": CARD_MD,
        "artifact": ARTIFACT_MD,
        "manifest": MANIFEST_JSON,
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXP_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": _repo_rel(path),
                "exists": path.exists(),
                "sha256": _sha256(path),
            }
            for label, path in files.items()
        },
    }
    peer_base.base._write_json(MANIFEST_JSON, manifest)


def _patch_modules() -> None:
    peer_base.EXP_ID = EXP_ID
    peer_base.STEM = STEM
    peer_base.TRIAL_FAMILY = TRIAL_FAMILY
    peer_base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    peer_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    peer_base.RULE_VERSION = RULE_VERSION
    peer_base.OUT_DIR = OUT_DIR
    peer_base.OUT_JSON = OUT_JSON
    peer_base.BEFORE_JSON = BEFORE_JSON
    peer_base.AFTER_JSON = AFTER_JSON
    peer_base.LOG_JSON = LOG_JSON
    peer_base.TICKET_JSON = TICKET_JSON
    peer_base.CARD_MD = CARD_MD
    peer_base.ARTIFACT_MD = ARTIFACT_MD
    peer_base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    peer_base._peer_confirmations = _peer_absorption_confirmations
    peer_base._score_candidate = _score_candidate
    peer_base._generate_candidates = _generate_candidates


def main() -> None:
    _patch_modules()
    peer_base._patch_base_module()
    peer_base.base._generate_candidates = peer_base._generate_candidates
    payload = _postprocess_payload(peer_base.base.build_payload())
    peer_base.base._write_json(OUT_JSON, payload)
    peer_base.base._write_json(LOG_JSON, _experiment_log_record(payload))
    peer_base.base._write_json(
        BEFORE_JSON,
        peer_base._judge_compatible_aggregate(payload["aggregate"]["before"]),
    )
    peer_base.base._write_json(
        AFTER_JSON,
        peer_base._judge_compatible_aggregate(payload["aggregate"]["after"]),
    )
    _write_artifact(payload)
    peer_base.base._update_ticket(payload)
    peer_base.base._update_registry(payload)
    peer_base.base._append_experiment_log(_experiment_log_record(payload))
    _write_manifest()
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": {
                    "target_trade_count": payload["target_summary"]["target_trade_count"],
                    "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
                    "max_single_positive_share": payload["target_summary"][
                        "max_single_positive_share"
                    ],
                    "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
                },
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
