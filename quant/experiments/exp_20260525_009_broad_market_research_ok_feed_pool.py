"""exp-20260525-009: broad-market research-ok feed quality scout.

This alpha search tests one candidate-pool quality variable for the default-off
broad-market leadership paper sleeve. It keeps the accepted broad-market
profile, rank profile, notional scalars, hold period, and slots fixed, but
restricts the current production-visible universe_state observation feed to
research records with full history, ok liquidity, and no separate pilot sleeve.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-009"
EXPERIMENT_SLUG = "broad_market_research_ok_feed_pool"
TRIAL_FAMILY = "broad_market_research_ok_feed_candidate_pool"
CHANGED_VARIABLE = "broad_market_research_ok_non_sleeve_candidate_pool_source"
VARIANT_NAME = "research_ok_non_sleeve_feed_pool"
VARIANT_SOURCE = "broad_market_research_ok_non_sleeve_universe_state_feed_v1"
BASELINE_EXPERIMENT_ID = "exp-20260520-004"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"
REFERENCE_EXPERIMENT_ID = "exp-20260524-036"

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260519-035",
    "exp-20260519-036",
    "exp-20260520-004",
    "exp-20260524-023",
    "exp-20260524-024",
    "exp-20260524-027",
    "exp-20260524-030",
    "exp-20260524-036",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for import_path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260524_036_broad_market_production_feed_pool as base  # noqa: E402
from broad_market_paper_sleeve import (  # noqa: E402
    UNIVERSE_STATE_FEED_RULE_VERSION,
    build_broad_market_candidate_universe_from_universe_state,
)


WINDOWS = base.WINDOWS
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _quality_feed_from_universe_state(
    *,
    universe_state: dict[str, Any],
    production_feed: dict[str, Any],
    frozen_tickers: set[str],
) -> dict[str, Any]:
    records = universe_state.get("records") or {}
    production_tickers = sorted(
        str(ticker).upper() for ticker in production_feed.get("tickers") or []
    )
    selected: list[str] = []
    selected_records: dict[str, dict[str, Any]] = {}
    excluded: list[dict[str, Any]] = []

    for ticker in production_tickers:
        record = records.get(ticker) or {}
        reasons: list[str] = []
        if ticker not in frozen_tickers:
            reasons.append("not_in_accepted_frozen_broad_market_universe")
        if record.get("status") != "research":
            reasons.append("status_not_research")
        if record.get("history_class") != "full_history":
            reasons.append("history_not_full")
        if record.get("liquidity_tier") != "ok":
            reasons.append("liquidity_not_ok")
        if record.get("pilot_sleeve"):
            reasons.append("belongs_to_separate_pilot_or_shadow_sleeve")
        if record.get("theme_segment") in {"theme_beta_benchmark", "quarantine_meme"}:
            reasons.append("theme_beta_or_quarantine")

        if reasons:
            excluded.append({"ticker": ticker, "reasons": reasons})
            continue

        selected.append(ticker)
        selected_records[ticker] = {
            key: record.get(key)
            for key in (
                "status",
                "theme",
                "theme_segment",
                "history_class",
                "liquidity_tier",
                "pilot_sleeve",
                "source",
                "source_reason",
            )
        }

    return {
        "status": "research_ok_non_sleeve_feed",
        "rule_version": VARIANT_SOURCE,
        "base_feed_rule_version": production_feed.get("rule_version"),
        "as_of": production_feed.get("as_of") or universe_state.get("as_of"),
        "selection_rule": (
            "ticker is in the production universe_state observation feed, "
            "status == research, history_class == full_history, liquidity_tier == ok, "
            "pilot_sleeve is empty, theme is not benchmark/quarantine, and ticker is "
            "available in the accepted frozen broad-market OHLCV universe"
        ),
        "why_this_pool_is_not_noise": (
            "The pool is a conservative subset of the existing production-visible "
            "universe_state observation feed. It excludes watch-liquidity names, "
            "specialist crypto/HPC rows, quarantine rows, and Space/AI pilot sleeves "
            "that have their own default-off attribution paths."
        ),
        "ticker_count": len(selected),
        "tickers": selected,
        "records": selected_records,
        "excluded_count": len(excluded),
        "excluded_sample": excluded[:40],
    }


def _identity_control(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed": (
            abs(float(identity["delta_metrics"]["aggregate_ev_delta"])) < 1e-9
            and abs(float(identity["delta_metrics"]["aggregate_pnl_delta"])) < 0.01
            and abs(float(identity["gate4"]["max_drawdown_worse_max"])) < 1e-9
        ),
        "variant_name": identity["variant_name"],
        "aggregate_ev_delta_vs_accepted_artifact": identity["delta_metrics"][
            "aggregate_ev_delta"
        ],
        "aggregate_pnl_delta_vs_accepted_artifact": identity["delta_metrics"][
            "aggregate_pnl_delta"
        ],
        "max_drawdown_worse_max_vs_accepted_artifact": identity["gate4"][
            "max_drawdown_worse_max"
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Broad-Market Research-Ok Feed Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: restrict the production universe_state observation feed to research/full-history/ok-liquidity/non-sleeve records for the default-off broad-market paper sleeve.",
            "",
            "## Candidate Pool",
            "",
            f"- tickers: `{', '.join(payload['candidate_universe']['quality_feed']['tickers'])}`",
            f"- count: `{payload['candidate_universe']['quality_feed']['ticker_count']}`",
            "",
            "## Sweep",
            "",
            "| Variant | Gate 4 | Candidates | Trades | Changed | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse |",
            "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            *[
                "| {variant} | {gate} | {candidates} | {trades} | {changed} | {ev:+.4f} | {rel:+.2%} | ${pnl:+,.2f} | {wi} | {wr} | {dd:+.4%} |".format(
                    variant=row["variant_name"],
                    gate="PASS" if row["passed"] else "FAIL",
                    candidates=row["candidate_ticker_count"],
                    trades=row["selected_trade_count"],
                    changed=row["changed_trade_count"],
                    ev=float(row["aggregate_ev_delta"] or 0.0),
                    rel=float(row["relative_ev_improvement"] or 0.0),
                    pnl=float(row["aggregate_pnl_delta"] or 0.0),
                    wi=row["windows_ev_improved"],
                    wr=row["windows_ev_regressed"],
                    dd=float(row["max_drawdown_worse_max"] or 0.0),
                )
                for row in payload["sweep_summary"]
            ],
            "",
            "## Three-Window Evidence",
            "",
            *rows,
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only/default-off paper only. No shared policy, production adapter, backtester adapter, order path, core signal generation, ranking, sizing, exits, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": base._compact_metrics(payload["before_metrics"]),
        "after_metrics": base._compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }


def build_payload() -> dict[str, Any]:
    if not base.BASELINE_JSON.exists():
        raise RuntimeError(f"Missing baseline artifact: {_repo_rel(base.BASELINE_JSON)}")
    if not base.CONTROL_JSON.exists():
        raise RuntimeError(f"Missing control artifact: {_repo_rel(base.CONTROL_JSON)}")

    gate2 = base.p35._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = base._json_load(base.BASELINE_JSON)
    control_payload = base._json_load(base.CONTROL_JSON)
    if baseline_payload.get("decision") != "accepted_default_off_broad_market_trend_persistence_notional":
        raise RuntimeError(f"Unexpected baseline decision: {baseline_payload.get('decision')}")

    universe_state_path = base._latest_universe_state_path()
    universe_state = base._json_load(universe_state_path)
    universe_state["artifact_path"] = _repo_rel(universe_state_path)
    production_feed = build_broad_market_candidate_universe_from_universe_state(universe_state)
    if production_feed.get("status") != "universe_state_observation_feed":
        raise RuntimeError(f"Unexpected production feed: {production_feed}")

    control_metrics = control_payload["before_metrics"]
    before_metrics = baseline_payload["after_metrics"]
    candidate_universe = baseline_payload["candidate_universe"]
    frozen_tickers = list(candidate_universe["tickers"])
    frozen_set = {str(ticker).upper() for ticker in frozen_tickers}
    quality_feed = _quality_feed_from_universe_state(
        universe_state=universe_state,
        production_feed=production_feed,
        frozen_tickers=frozen_set,
    )
    quality_tickers = sorted(set(quality_feed["tickers"]) & frozen_set)
    prices = base.p35._load_price_rows(frozen_tickers)
    indexes = base.p35._index_by_date(prices)

    identity = base._variant_payload(
        variant_name=base.BASELINE_VARIANT,
        candidate_source="accepted_exp_20260520_004_frozen_pool",
        control_metrics=control_metrics,
        before_metrics=before_metrics,
        candidate_tickers=frozen_tickers,
        prices=prices,
        indexes=indexes,
        identity_keys=None,
    )
    identity_keys = set(identity["trade_keys"])
    quality_variant = base._variant_payload(
        variant_name=VARIANT_NAME,
        candidate_source=VARIANT_SOURCE,
        control_metrics=control_metrics,
        before_metrics=before_metrics,
        candidate_tickers=quality_tickers,
        prices=prices,
        indexes=indexes,
        identity_keys=identity_keys,
    )
    variants = [identity, quality_variant]
    identity_control = _identity_control(identity)
    selected = base._choose_selected(variants)
    selected["gate4"]["identity_control_passed"] = identity_control["passed"]
    if not identity_control["passed"]:
        selected["gate4"]["passed"] = False

    accepted = bool(selected["gate4"]["passed"])
    decision = (
        "promising_replay_only_broad_market_research_ok_feed_pool"
        if accepted
        else "rejected_broad_market_research_ok_feed_pool"
    )
    aggregate_before = base.p35._aggregate(before_metrics)
    aggregate_after = base.p35._aggregate(selected["after_metrics"])
    gate3 = {
        "signals_generated": {
            label: before_metrics[label].get("signals_generated") for label in WINDOWS
        },
        "signals_survived": {
            label: before_metrics[label].get("signals_survived") for label in WINDOWS
        },
        "survival_rate": {
            label: before_metrics[label].get("survival_rate") for label in WINDOWS
        },
        "survival_rate_min": aggregate_before["survival_rate_min"],
        "passed": aggregate_before["survival_rate_min"] >= 0.05,
        "note": "No core filter was added; this is default-off broad-market paper candidate routing only.",
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "uses_existing_universe_state_fields": True,
        "base_feed_rule_version": UNIVERSE_STATE_FEED_RULE_VERSION,
        "replay_only": True,
        "default_off_paper_only": True,
        "parity_test_added": False,
        "live_order_path_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "promotion_requirement": (
            "Any positive result would need a shared default-off feed-quality adapter, "
            "point-in-time feed history, forward closed outcomes, and parity tests before orders."
        ),
    }
    for row in variants:
        row.pop("trade_keys", None)

    related_files = {
        "script": _repo_rel(Path(__file__)),
        "output": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "artifact": _repo_rel(ARTIFACT_MD),
        "experiment_log": _repo_rel(EXPERIMENT_LOG),
        "baseline": _repo_rel(base.BASELINE_JSON),
        "control": _repo_rel(base.CONTROL_JSON),
        "universe_state": _repo_rel(universe_state_path),
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": "promising_replay_only" if accepted else "rejected",
        "decision": decision,
        "hypothesis": (
            "The rejected broad-market production feed may be hurt by watch-liquidity, "
            "specialist, quarantine, and separate-sleeve names. A conservative "
            "production-visible research/full-history/ok-liquidity/non-sleeve feed "
            "may improve default-off broad-market replacement value without adding "
            "new noisy tickers."
        ),
        "change_type": "default_off_paper_candidate_pool_quality",
        "mechanism_family": "broad_market_candidate_pool_quality",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": selected["variant_name"],
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": len(NEARBY_PRIOR_EXPERIMENTS),
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_universe_state_governance_quality_field",
        "single_causal_variable": "candidate pool source quality rule on top of the existing universe_state feed",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "reference_experiment_id": REFERENCE_EXPERIMENT_ID,
            "selected_variant": selected["variant_name"],
            "minimum_relative_ev_improvement": base.MIN_RELATIVE_EV_IMPROVEMENT,
            "minimum_changed_trades": base.MIN_CHANGED_TRADES,
            "minimum_changed_windows": base.MIN_CHANGED_WINDOWS,
            "baseline_candidate_count": len(frozen_tickers),
            "production_feed_candidate_count": len(production_feed.get("tickers") or []),
            "quality_feed_candidate_count": len(quality_tickers),
            "quality_feed_rule_version": VARIANT_SOURCE,
            "universe_state_path": _repo_rel(universe_state_path),
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"]} for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted exp-20260520-004 "
            "trend-persistence broad-market adapter is the before state; after state keeps "
            "the same profile/rank/notional/hold/slots and changes only the universe_state "
            "feed subset used as the paper candidate source."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(base.BASELINE_JSON),
            "control_artifact": _repo_rel(base.CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
        },
        "gate2": gate2,
        "gate3": gate3,
        "identity_control": identity_control,
        "gate4": selected["gate4"],
        "before_metrics": before_metrics,
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "expected_value_score_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_ev_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "total_pnl_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_pnl_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["total_pnl"]
                for label in WINDOWS
            },
        },
        "sweep_summary": base._sweep_summary(variants),
        "selected_variant": {
            "variant_name": selected["variant_name"],
            "candidate_source": selected["candidate_source"],
            "candidate_ticker_count": selected["candidate_ticker_count"],
            "candidate_tickers": quality_tickers,
            "selected_trade_count": selected["selected_trade_count"],
            "changed_trade_count": selected["changed_trade_count"],
            "changed_windows": selected["changed_windows"],
            "removed_trade_count": selected["removed_trade_count"],
            "added_trade_count": selected["added_trade_count"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "selected_trades_sample": selected["selected_trades_sample"],
            "added_trades_sample": selected["added_trades_sample"],
        },
        "broad_market_sleeve": selected["broad_market_sleeve"],
        "candidate_universe": {
            "baseline": candidate_universe,
            "production_feed": {
                "status": production_feed.get("status"),
                "rule_version": production_feed.get("rule_version"),
                "as_of": production_feed.get("as_of"),
                "ticker_count": len(production_feed.get("tickers") or []),
                "tickers": production_feed.get("tickers") or [],
                "excluded_count": production_feed.get("excluded_count"),
                "excluded_sample": production_feed.get("excluded_sample"),
                "source_counts": production_feed.get("source_counts"),
            },
            "quality_feed": quality_feed,
        },
        "warehouse_audit": base.p35._warehouse_audit(),
        "llm_metrics": {
            "changed": False,
            "used_llm": False,
            "reason": "LLM soft-ranking remains replay-sparse; this run uses only deterministic universe_state/OHLCV fields.",
        },
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate_pool / capital allocation: production-visible governance "
                "quality fields may make the broad-market default-off paper feed less noisy."
            ),
            "2_past_similar_experiments": (
                "exp-20260524-036 tested the full production feed and failed old_thin, "
                "drawdown, concentration, and 10% materiality; exp-20260524-030 tested "
                "avg-dollar-volume notional and failed. This changes candidate membership "
                "by governance fields, not notional or price thresholds."
            ),
            "3_single_variable": CHANGED_VARIABLE,
            "4_acceptance": (
                "Gate 4 requires positive aggregate EV/PnL, 3/3 EV improvement, no PnL "
                "regressed window, >=4 changed trades across >=2 windows, concentration "
                "guard, <=0.5pp drawdown worsening, identity control, and >=10% aggregate "
                "EV improvement for a broad-market selection surface."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260525_009_broad_market_research_ok_feed_pool.py"
            ),
        },
        "interpretation": (
            "The governance-quality feed subset cleared the strict replay gate, but remains "
            "default-off/replay-only until implemented as a shared adapter with forward rows."
            if accepted
            else (
                "The governance-quality feed subset did not clear the strict broad-market "
                "three-window Gate 4; keep it as a research note, not a production rule."
            )
        ),
        "rejection_reason": None
        if accepted
        else "Research/full-history/ok-liquidity/non-sleeve feed subset did not clear the strict three-window broad-market Gate 4.",
        "next_evidence_needed": (
            "Forward broad-market paper replacement-value rows with point-in-time universe_state "
            "feed history; do not retry nearby feed-quality subsets on the frozen sample without "
            "new forward evidence or a materially different production-visible data edge."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": payload["lane"],
            "status": payload["status"],
            "decision": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "gate4": payload["gate4"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "quality_feed": payload["candidate_universe"]["quality_feed"],
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
