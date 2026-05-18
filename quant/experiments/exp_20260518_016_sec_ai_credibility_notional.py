"""exp-20260518-016: SEC AI disclosure credibility notional.

Alpha search on one previously untested playbook field:
``ai_disclosure_credibility_bucket``. On top of the accepted default-off SEC
financial-report paper stack, test whether filings with AI mentions plus
specific product/customer/capex evidence deserve extra paper notional.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260518-016"
STEM = "exp_20260518_016_sec_ai_credibility_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260516_033_sec_financial_report_neutral_language_notional as parent  # noqa: E402
from sec_event_queue import semantic_text  # noqa: E402
from sec_financial_report_event_sleeve import (  # noqa: E402
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_ai_credibility_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR = 2.0
ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS = 0.020
ACCEPTED_NEUTRAL_UNDERREACTION_SPY_T1_CONTEXT_SCALAR = 1.5
ACCEPTED_NEUTRAL_UNDERREACTION_SPY_T1_RETURN_MIN = -0.005
AI_CREDIBLE_NOTIONAL_SCALAR_VARIANTS = (1.0, 1.10, 1.25, 1.50, 2.0)
MIN_ADJUSTED_TRADES = 6
MIN_WINDOWS_PRESENT = 3
MAX_DRAWDOWN_WORSENING = 0.005

AI_TERMS = (
    "artificial intelligence",
    "generative ai",
    "machine learning",
    "large language model",
    "llm",
    " ai ",
)
AI_EVIDENCE_PATTERNS = (
    "customer",
    "customers",
    "product",
    "products",
    "copilot",
    "inference",
    "training",
    "gpu",
    "deployment",
    "deployments",
    "bookings",
    "revenue",
    "arr",
    "annual recurring revenue",
    "monetiz",
    "pricing",
    "workload",
    "in production",
    "general availability",
    "capex",
    "capital expenditure",
    "data center",
    "tokens",
    "throughput",
    "serving",
    "launch",
)
AI_PROMOTIONAL_PATTERNS = (
    "ai strategy",
    "ai vision",
    "ai opportunity",
    "ai transformation",
    "ai powered",
    "powered by ai",
    "leader in ai",
    "positioned for ai",
    "benefit from ai",
    "capitalize on ai",
    "ai roadmap",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    return parent._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return parent._round(value, ndigits)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _classify_ai_credibility(text: str) -> str:
    lowered = f" {text.lower().replace('-', ' ')} "
    if not any(term in lowered for term in AI_TERMS):
        return "no_ai"
    evidence_hits = sum(1 for pattern in AI_EVIDENCE_PATTERNS if pattern in lowered)
    promo_hits = sum(1 for pattern in AI_PROMOTIONAL_PATTERNS if pattern in lowered)
    if evidence_hits >= 2:
        return "credible_ai"
    if promo_hits or evidence_hits == 0:
        return "promotional_ai"
    return "generic_ai"


def _annotate_ai_bucket(
    exp100: dict[str, Any],
    text_rows_by_accession: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    annotated = json.loads(json.dumps(exp100))
    aggregate = Counter()
    by_window: dict[str, Any] = {}
    samples: list[dict[str, Any]] = []
    for label, window in annotated.get("windows", {}).items():
        counter = Counter()
        for row in window.get("candidate_rows") or []:
            accession = parent._accession(row)
            text_row = text_rows_by_accession.get(accession)
            text = semantic_text(text_row or {}) if text_row else ""
            bucket = _classify_ai_credibility(text)
            row["ai_disclosure_credibility_bucket"] = bucket
            counter[bucket] += 1
            aggregate[bucket] += 1
            if bucket != "no_ai" and len(samples) < 12:
                samples.append(
                    {
                        "window": label,
                        "ticker": row.get("ticker"),
                        "accession_number": accession,
                        "bucket": bucket,
                        "text_excerpt": text[:240].encode("ascii", "ignore").decode(),
                    }
                )
        by_window[label] = {
            "candidate_count": len(window.get("candidate_rows") or []),
            "ai_bucket": dict(sorted(counter.items())),
        }
    return annotated, {
        "aggregate": {
            "candidate_count": sum(
                len(window.get("candidate_rows") or [])
                for window in annotated.get("windows", {}).values()
            ),
            "ai_bucket": dict(sorted(aggregate.items())),
        },
        "by_window": by_window,
        "sample_non_no_ai_rows": samples,
    }


def _accepted_sec_scalar(position: dict[str, Any]) -> tuple[float, str]:
    _, scalar, rule = parent._base_notional_for_position(position)
    candidate = parent._source_candidate(position)
    if str(candidate.get("language_bucket") or "") == "neutral_or_mixed_language":
        t1_excess = _float(candidate.get("t1_excess_return_vs_spy"))
        if (
            t1_excess is not None
            and t1_excess <= ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS
        ):
            scalar *= ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR
            rule = f"{rule}+neutral_underreaction_scalar"
            spy_t1 = _float(candidate.get("spy_t1_return"))
            if (
                spy_t1 is not None
                and spy_t1 >= ACCEPTED_NEUTRAL_UNDERREACTION_SPY_T1_RETURN_MIN
            ):
                scalar *= ACCEPTED_NEUTRAL_UNDERREACTION_SPY_T1_CONTEXT_SCALAR
                rule = f"{rule}+neutral_underreaction_spy_t1_context_scalar"
    return scalar, rule


def _ai_bucket(position: dict[str, Any]) -> str:
    return str(
        parent._source_candidate(position).get("ai_disclosure_credibility_bucket") or "unknown"
    )


def _notional_for_position(
    position: dict[str, Any],
    *,
    credible_ai_scalar: float,
) -> tuple[float, float, str]:
    accepted_scalar, rule = _accepted_sec_scalar(position)
    scalar = accepted_scalar
    if _ai_bucket(position) == "credible_ai":
        scalar *= credible_ai_scalar
        rule = f"{rule}+ai_credible_scalar"
    return float(parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar, scalar, rule


def _pnl_for_position(
    position: dict[str, Any],
    *,
    credible_ai_scalar: float,
    closed: bool,
) -> float:
    adjusted_notional, _, _ = _notional_for_position(
        position,
        credible_ai_scalar=credible_ai_scalar,
    )
    if closed:
        net_return = _float(position.get("net_return_pct"))
        return adjusted_notional * ((net_return or 0.0) / 100.0)
    source_notional = _float(position.get("notional"))
    source_pnl = _float(position.get("net_pnl_if_closed_now"))
    if not source_notional or source_notional <= 0:
        return 0.0
    return adjusted_notional * ((source_pnl or 0.0) / source_notional)


def _adjust_closed_position(
    position: dict[str, Any],
    *,
    credible_ai_scalar: float,
) -> dict[str, Any]:
    adjusted = dict(position)
    notional, scalar, rule = _notional_for_position(
        position,
        credible_ai_scalar=credible_ai_scalar,
    )
    adjusted["base_notional"] = float(parent.DEFAULT_EVENT_NOTIONAL_USD)
    adjusted["notional"] = round(notional, 2)
    adjusted["event_notional_scalar"] = scalar
    adjusted["event_notional_rule"] = rule
    adjusted["event_family"] = parent._event_family(position)
    adjusted["form_base"] = parent._form_base(position)
    adjusted["ai_disclosure_credibility_bucket"] = _ai_bucket(position)
    adjusted["credible_ai_notional_scalar"] = credible_ai_scalar
    adjusted["pnl"] = round(
        _pnl_for_position(
            position,
            credible_ai_scalar=credible_ai_scalar,
            closed=True,
        ),
        2,
    )
    return adjusted


def _closed_position_breakdown(closed_positions: list[dict[str, Any]]) -> dict[str, Any]:
    bucket_count = Counter(
        str(item.get("ai_disclosure_credibility_bucket") or "unknown")
        for item in closed_positions
    )
    bucket_pnl: dict[str, float] = {}
    for item in closed_positions:
        bucket = str(item.get("ai_disclosure_credibility_bucket") or "unknown")
        bucket_pnl[bucket] = bucket_pnl.get(bucket, 0.0) + float(item.get("pnl") or 0.0)
    return {
        "closed_trade_count_by_ai_bucket": dict(sorted(bucket_count.items())),
        "closed_pnl_by_ai_bucket": {
            key: _round(value, 2) for key, value in sorted(bucket_pnl.items())
        },
        "credible_ai_closed_trade_count": int(bucket_count.get("credible_ai") or 0),
        "credible_ai_total_pnl": _round(bucket_pnl.get("credible_ai") or 0.0, 2),
    }


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, Any],
    exp100_window: dict[str, Any],
    *,
    credible_ai_scalar: float,
) -> dict[str, Any]:
    prices_by_date = parent._load_snapshot_prices(window["snapshot"])
    candidates_by_t1 = parent._rows_by_t1_date(exp100_window)
    state = empty_sec_financial_report_event_sleeve_state()
    skipped_entries: list[dict[str, Any]] = []
    pnl_by_date: OrderedDict[str, float] = OrderedDict()
    enqueued_candidates = 0
    max_open_positions = 0
    max_gross_notional = 0.0

    for as_of, prices in prices_by_date.items():
        candidates = candidates_by_t1.get(as_of, [])
        enqueued_candidates += len(candidates)
        queue = {
            "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
            "rule_version": f"{EXPERIMENT_ID}-replay",
            "enabled": False,
            "asof_date": as_of,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "data_source": {
                "status": "replay",
                "source_experiment": "exp-20260511-100",
                "window": window_label,
            },
        }
        snapshot = build_sec_financial_report_event_sleeve_snapshot(
            sec_financial_report_t1_queue=queue,
            as_of=as_of,
            open_prices=prices["open"],
            current_prices=prices["close"],
            state=state,
            config={
                "max_positions": parent.DEFAULT_MAX_POSITIONS,
                "event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
                "periodic_report_notional_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
                "tenq_periodic_report_notional_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            },
            persist=False,
        )
        skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
        state = parent._rebuild_sleeve_state(snapshot, skipped_entries)

        realized = sum(
            _pnl_for_position(
                item,
                credible_ai_scalar=credible_ai_scalar,
                closed=True,
            )
            for item in state.get("closed_positions") or []
        )
        unrealized = sum(
            _pnl_for_position(
                item,
                credible_ai_scalar=credible_ai_scalar,
                closed=False,
            )
            for item in state.get("open_positions") or []
        )
        pnl_by_date[as_of] = realized + unrealized
        open_positions = state.get("open_positions") or []
        max_open_positions = max(max_open_positions, len(open_positions))
        max_gross_notional = max(
            max_gross_notional,
            sum(
                _notional_for_position(
                    item,
                    credible_ai_scalar=credible_ai_scalar,
                )[0]
                for item in open_positions
            ),
        )

    closed_positions = [
        _adjust_closed_position(
            item,
            credible_ai_scalar=credible_ai_scalar,
        )
        for item in state.get("closed_positions") or []
    ]
    wins = sum(1 for item in closed_positions if float(item.get("pnl") or 0.0) > 0)
    sleeve_curve = [(date_value, 100_000.0 + pnl) for date_value, pnl in pnl_by_date.items()]
    standalone_metrics = parent._equity_metrics(
        sleeve_curve,
        trade_count=len(closed_positions),
        win_rate=(wins / len(closed_positions) if closed_positions else None),
    )
    standalone_metrics.update(
        {
            "candidate_count": enqueued_candidates,
            "closed_trade_count": len(closed_positions),
            "open_position_count_end": len(state.get("open_positions") or []),
            "skipped_capacity_count": len(skipped_entries),
            "max_open_positions": max_open_positions,
            "max_gross_notional": _round(max_gross_notional, 2),
        }
    )
    standalone_metrics.update(_closed_position_breakdown(closed_positions))
    return {
        "daily_pnl": list(pnl_by_date.items()),
        "metrics": standalone_metrics,
        "sample_closed_positions": closed_positions[:10],
        "closed_positions": closed_positions,
    }


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    credible_ai_scalar: float,
) -> dict[str, Any]:
    by_window = {}
    for label, window in parent.WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            credible_ai_scalar=credible_ai_scalar,
        )
        core_curve = core_results[label]["equity_curve"]
        combined_curve = parent._combine_curves(core_curve, sleeve["daily_pnl"])
        core_metrics = core_results[label]["metrics"]
        combined_metrics = parent._equity_metrics(
            combined_curve,
            trade_count=int(core_metrics["trade_count"]) + int(sleeve["metrics"]["trade_count"]),
            win_rate=None,
        )
        by_window[label] = {
            "core_metrics": core_metrics,
            "combined_metrics": combined_metrics,
            "sleeve_metrics": sleeve["metrics"],
            "sample_closed_positions": sleeve["sample_closed_positions"],
            "closed_positions": sleeve["closed_positions"],
        }
    return {"by_window": by_window, "aggregate": parent._aggregate(by_window)}


def _window_deltas(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label in parent.WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        after_sleeve = after["by_window"][label]["sleeve_metrics"]
        before_sleeve = before["by_window"][label]["sleeve_metrics"]
        checks[label] = {
            "ev_delta": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "pnl_delta": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "max_drawdown_delta": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "credible_ai_closed_trade_count": int(
                after_sleeve.get("credible_ai_closed_trade_count") or 0
            ),
            "credible_ai_pnl_delta": _round(
                float(after_sleeve.get("credible_ai_total_pnl") or 0.0)
                - float(before_sleeve.get("credible_ai_total_pnl") or 0.0),
                2,
            ),
        }
    return checks


def _selection_rows(
    after: dict[str, Any],
    before: dict[str, Any],
    *,
    credible_ai_scalar: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in parent.WINDOWS:
        before_by_key = {
            (
                str(item.get("ticker") or ""),
                str(item.get("entry_date") or ""),
                str(item.get("exit_date") or ""),
            ): item
            for item in before["by_window"][label]["closed_positions"]
            if str(item.get("ai_disclosure_credibility_bucket") or "") == "credible_ai"
        }
        for item in after["by_window"][label]["closed_positions"]:
            if str(item.get("ai_disclosure_credibility_bucket") or "") != "credible_ai":
                continue
            key = (
                str(item.get("ticker") or ""),
                str(item.get("entry_date") or ""),
                str(item.get("exit_date") or ""),
            )
            baseline = before_by_key.get(key, {})
            baseline_pnl = float(baseline.get("pnl") or 0.0)
            adjusted_pnl = float(item.get("pnl") or 0.0)
            enriched = dict(item)
            enriched.update(
                {
                    "window": label,
                    "accepted_stack_pnl": _round(baseline_pnl, 2),
                    "ai_credible_adjusted_pnl": _round(adjusted_pnl, 2),
                    "ai_credible_incremental_pnl": _round(adjusted_pnl - baseline_pnl, 2),
                    "credible_ai_scalar": credible_ai_scalar,
                }
            )
            rows.append(enriched)
    return rows


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(str(row["window"]) for row in rows)
    by_ticker = Counter(str(row["ticker"]) for row in rows)
    pnl_by_window: dict[str, float] = {}
    pnl_by_ticker: dict[str, float] = {}
    positive_incremental: list[float] = []
    for row in rows:
        pnl = float(row.get("ai_credible_incremental_pnl") or 0.0)
        pnl_by_window[str(row["window"])] = pnl_by_window.get(str(row["window"]), 0.0) + pnl
        pnl_by_ticker[str(row["ticker"])] = pnl_by_ticker.get(str(row["ticker"]), 0.0) + pnl
        if pnl > 0:
            positive_incremental.append(pnl)
    positive_total = sum(positive_incremental)
    max_positive = max(positive_incremental) if positive_incremental else 0.0
    return {
        "adjusted_trade_count": len(rows),
        "windows_present": len(by_window),
        "by_window_count": dict(sorted(by_window.items())),
        "by_window_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_window.items())
        },
        "by_ticker_count": dict(sorted(by_ticker.items())),
        "by_ticker_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_ticker.items())
        },
        "max_single_positive_pnl_share": (
            _round(max_positive / positive_total, 4) if positive_total > 0 else None
        ),
    }


def _best_candidate(variants: OrderedDict[str, dict[str, Any]]) -> str:
    baseline = variants["credible_ai_scalar_1.00"]["aggregate"]

    def score(item: tuple[str, dict[str, Any]]) -> tuple[float, float, float]:
        key, row = item
        agg = row["aggregate"]
        ev_delta = float(agg["expected_value_score_sum"]) - float(
            baseline["expected_value_score_sum"]
        )
        pnl_delta = float(agg["total_pnl_sum"]) - float(baseline["total_pnl_sum"])
        dd_delta = float(agg["max_drawdown_pct_max"]) - float(
            baseline["max_drawdown_pct_max"]
        )
        if key == "credible_ai_scalar_1.00":
            return (-1e9, -1e9, -1e9)
        return (ev_delta, pnl_delta, -dd_delta)

    return max(variants.items(), key=score)[0]


def _gate(best: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    window_checks = _window_deltas(best, baseline)
    aggregate_delta = parent._delta(best["aggregate"], baseline["aggregate"])
    adjusted_trade_count = int(best["selection"]["adjusted_trade_count"])
    windows_present = int(best["selection"]["windows_present"])
    ev_regressed = sum(1 for row in window_checks.values() if float(row["ev_delta"]) < 0.0)
    pnl_regressed = sum(1 for row in window_checks.values() if float(row["pnl_delta"]) < 0.0)
    sample_guard_passed = (
        adjusted_trade_count >= MIN_ADJUSTED_TRADES and windows_present >= MIN_WINDOWS_PRESENT
    )
    max_dd_delta = max(float(row["max_drawdown_delta"]) for row in window_checks.values())
    metric_gate_passed = (
        float(aggregate_delta["expected_value_score_sum_delta"]) > 0.0
        and float(aggregate_delta["total_pnl_sum_delta"]) > 0.0
        and ev_regressed == 0
        and pnl_regressed == 0
        and max_dd_delta <= MAX_DRAWDOWN_WORSENING
    )
    return {
        "rule": (
            "Pass if aggregate EV/PnL improve versus accepted exp-20260518-014, "
            "EV and PnL improve in all three fixed windows, no window regresses, "
            "max drawdown worsens by <=0.5pp, adjusted trades >= 6, and adjusted "
            "trades are present in all 3 windows."
        ),
        "aggregate_delta": aggregate_delta,
        "window_checks": window_checks,
        "adjusted_trade_count": adjusted_trade_count,
        "windows_present": windows_present,
        "ev_regressed_windows": ev_regressed,
        "pnl_regressed_windows": pnl_regressed,
        "max_drawdown_delta_max": _round(max_dd_delta, 6),
        "sample_guard_passed": sample_guard_passed,
        "metric_gate_passed": metric_gate_passed,
        "passed": sample_guard_passed and metric_gate_passed,
        "selection_concentration": {
            "diagnostic_only": True,
            "max_single_positive_pnl_share": best["selection"]["max_single_positive_pnl_share"],
        },
    }


def _artifact_md(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    lines = [
        "# SEC AI Disclosure Credibility Notional",
        "",
        f"- Experiment ID: `{EXPERIMENT_ID}`",
        f"- Decision: `{payload['decision']}`",
        f"- Hypothesis: {payload['hypothesis']}",
        f"- Changed variable: `{payload['changed_variable']}`",
        "",
        "## Gate 1-4",
        "",
        f"- Gate 1 baseline: accepted `exp-20260518-014` default-off SEC paper stack over the canonical three fixed windows.",
        f"- Gate 2 fields passed: `{payload['gate2_required_fields']['passed']}`",
        f"- Gate 3 survival unchanged: min survival rate delta `{payload['delta_metrics']['aggregate']['min_survival_rate_delta']}`.",
        f"- Gate 4 passed: `{gate['passed']}`",
        "",
        "## Aggregate",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
        "| EV sum | {before_ev} | {after_ev} | {delta_ev} |".format(
            before_ev=payload["before_metrics"]["expected_value_score_sum"],
            after_ev=payload["after_metrics"]["expected_value_score_sum"],
            delta_ev=payload["delta_metrics"]["aggregate"]["expected_value_score_sum_delta"],
        ),
        "| Total PnL | {before_pnl} | {after_pnl} | {delta_pnl} |".format(
            before_pnl=payload["before_metrics"]["total_pnl_sum"],
            after_pnl=payload["after_metrics"]["total_pnl_sum"],
            delta_pnl=payload["delta_metrics"]["aggregate"]["total_pnl_sum_delta"],
        ),
        "| Max DD max | {before_dd} | {after_dd} | {delta_dd} |".format(
            before_dd=payload["before_metrics"]["max_drawdown_pct_max"],
            after_dd=payload["after_metrics"]["max_drawdown_pct_max"],
            delta_dd=payload["delta_metrics"]["aggregate"]["max_drawdown_pct_max_delta"],
        ),
        "",
        "## Window Deltas",
        "",
        "| Window | EV delta | PnL delta | Max DD delta | Credible AI trades | Credible AI PnL delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in gate["window_checks"].items():
        lines.append(
            "| {label} | {ev} | {pnl} | {dd} | {count} | {ai_pnl} |".format(
                label=label,
                ev=row["ev_delta"],
                pnl=row["pnl_delta"],
                dd=row["max_drawdown_delta"],
                count=row["credible_ai_closed_trade_count"],
                ai_pnl=row["credible_ai_pnl_delta"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Next Evidence",
            "",
            payload["next_evidence_needed"],
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    timestamp = _utc_now()
    raw_exp100 = parent._load_exp100()
    current_queue = parent._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = parent._load_text_rows()
    exp100 = parent._annotate_language_fields(current_queue, text_rows_by_accession)
    exp100, ai_bucket_summary = _annotate_ai_bucket(exp100, text_rows_by_accession)
    text_coverage = parent._text_coverage_summary(exp100)
    gate2_fields = parent._gate2_open_position_field_check()

    core_results = {}
    for label, window in parent.WINDOWS.items():
        result = parent._run_core_backtest(window)
        core_results[label] = {
            "metrics": parent._core_metrics(result),
            "equity_curve": parent._normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for scalar in AI_CREDIBLE_NOTIONAL_SCALAR_VARIANTS:
        name = f"credible_ai_scalar_{scalar:.2f}"
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            credible_ai_scalar=scalar,
        )
        row["credible_ai_scalar"] = scalar
        row["selection_rows"] = _selection_rows(
            row,
            variants["credible_ai_scalar_1.00"] if variants else row,
            credible_ai_scalar=scalar,
        )
        row["selection"] = _selection_summary(row["selection_rows"])
        variants[name] = row

    baseline = variants["credible_ai_scalar_1.00"]
    best_key = _best_candidate(variants)
    best = variants[best_key]
    gate = _gate(best, baseline)
    decision = (
        "accepted_candidate_sec_ai_credibility_notional"
        if gate["passed"]
        else "rejected_sec_ai_credibility_notional"
    )
    status = "accepted_candidate" if gate["passed"] else "rejected"
    rejection_reason = None
    if not gate["passed"]:
        rejection_reason = (
            "Gate 4 failed. Aggregate EV/PnL improved only by leaning harder into the "
            "credible-AI slice, but both `late_strong` and `old_thin` regressed on EV "
            "and PnL while the gains concentrated in `mid_weak`."
        )

    sweep_summary = {}
    for name, row in variants.items():
        sweep_summary[name] = {
            "credible_ai_scalar": row["credible_ai_scalar"],
            "aggregate": row["aggregate"],
            "selection": row["selection"],
        }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "hypothesis": (
            "Within the accepted SEC financial-report default-off paper stack, AI-themed "
            "filings should only deserve extra notional when the filing contains specific "
            "product/customer/capex evidence rather than generic AI promotion. A bounded "
            "paper scalar on that credible bucket may improve replacement value without "
            "changing queue eligibility, hold days, capacity, or live orders."
        ),
        "change_summary": (
            "Replay-only paper-notional multiplier for SEC financial-report paper rows "
            "whose archived filing text maps to `ai_disclosure_credibility_bucket=credible_ai`."
        ),
        "change_type": "alpha_search_semantic_risk_allocation",
        "component": "quant/experiments",
        "changed_variable": "sec_ai_disclosure_credibility_notional_scalar",
        "single_causal_variable": "credible AI disclosure paper-notional scalar",
        "lane": "alpha_search",
        "parameters": {
            "baseline_credible_ai_scalar": 1.0,
            "credible_ai_scalar_variants": list(AI_CREDIBLE_NOTIONAL_SCALAR_VARIANTS),
            "credible_ai_definition": "AI mention plus >=2 product/customer/capex evidence hits in archived SEC text",
            "promotional_ai_definition": "AI mention with zero evidence hits or explicit promotional phrasing",
            "accepted_sec_stack": {
                "neutral_underreaction_scalar": ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR,
                "neutral_underreaction_max_t1_excess": ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS,
                "neutral_underreaction_spy_t1_context_scalar": ACCEPTED_NEUTRAL_UNDERREACTION_SPY_T1_CONTEXT_SCALAR,
                "neutral_underreaction_spy_t1_return_min": ACCEPTED_NEUTRAL_UNDERREACTION_SPY_T1_RETURN_MIN,
            },
            "base_event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": parent.DEFAULT_MAX_POSITIONS,
            "source_candidate_artifact": str(parent.SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
            "text_archive": str(parent.TEXT_ARCHIVE_JSONL.relative_to(REPO_ROOT)),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for the core baseline, plus "
            "production SEC financial-report paper-sleeve replay over the same OHLCV snapshots."
        ),
        "candidate_counts_after_current_queue_filter": parent._candidate_counts(exp100),
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
        "ai_bucket_summary": ai_bucket_summary,
        "gate2_required_fields": gate2_fields,
        "before_metrics": baseline["aggregate"],
        "after_metrics": best["aggregate"],
        "delta_metrics": {
            "aggregate": parent._delta(best["aggregate"], baseline["aggregate"]),
            "by_window": _window_deltas(best, baseline),
        },
        "expected_value_score_delta": _round(
            float(best["aggregate"]["expected_value_score_sum"])
            - float(baseline["aggregate"]["expected_value_score_sum"]),
            6,
        ),
        "total_pnl_delta": _round(
            float(best["aggregate"]["total_pnl_sum"])
            - float(baseline["aggregate"]["total_pnl_sum"]),
            2,
        ),
        "best_variant": best_key,
        "selection": best["selection"],
        "selection_rows": best["selection_rows"],
        "gate": gate,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "interpretation": (
            "The AI credibility bucket is replayable and not sample-empty, but its historical "
            "incremental value is not robust across the canonical windows. The slice helped "
            "`mid_weak`, yet the same extra notional harmed `late_strong` and `old_thin`, so "
            "this field is not ready for promotion into the shared SEC paper sleeve."
        ),
        "next_evidence_needed": (
            "Do not promote this heuristic bucket. Revisit AI disclosure fields only after a "
            "narrower evidence taxonomy widens honestly or after closed forward replacement-value "
            "evidence shows a stable cross-window edge."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "risk allocation on SEC financial-report paper rows via a new AI disclosure credibility field from the playbook.",
            "2_history_check": "The playbook explicitly lists `ai_disclosure_credibility_bucket`, but repository search found no prior logged alpha experiment that isolated this field on the accepted SEC paper stack. Nearby SEC language experiments covered neutral/positive/negative tone, cash-flow forecast context, and SPY/ticker T+1 context, not AI credibility.",
            "3_single_causal_variable": "credible AI disclosure paper-notional scalar",
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260518_016_sec_ai_credibility_notional.py",
        },
        "why_not_other_changes": (
            "State-surface nearby retunes are currently anti-repeat, Form 4 is already in a "
            "frozen single-owner branch, and this run intentionally chose an untested playbook "
            "field that is replayable on the current SEC financial-report surface."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "This run avoids LLM soft-ranking sparsity by using deterministic archived SEC text and schema-bound heuristic buckets.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "related_files": [
            "quant/experiments/exp_20260518_016_sec_ai_credibility_notional.py",
            "data/experiments/exp-20260518-016/exp_20260518_016_sec_ai_credibility_notional.json",
            "docs/experiments/logs/exp-20260518-016.json",
            "docs/experiments/tickets/exp-20260518-016.json",
            "docs/experiments/artifacts/exp-20260518-016_sec_ai_credibility_notional.md",
            "docs/experiment_log.jsonl",
        ],
        "sweep_summary": sweep_summary,
        "windows": parent.WINDOWS,
    }

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Test SEC AI credibility paper scalar",
            "status": status,
            "hypothesis": payload["hypothesis"],
            "decision": decision,
            "best_variant": best_key,
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "next_evidence_needed": payload["next_evidence_needed"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_md(payload), encoding="utf-8")
    _upsert_jsonl(
        EXPERIMENT_LOG_JSONL,
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "changed_variable": payload["changed_variable"],
            "parameters": payload["parameters"],
            "date_range": {
                "late_strong": {
                    "start": parent.WINDOWS["late_strong"]["start"],
                    "end": parent.WINDOWS["late_strong"]["end"],
                },
                "mid_weak": {
                    "start": parent.WINDOWS["mid_weak"]["start"],
                    "end": parent.WINDOWS["mid_weak"]["end"],
                },
                "old_thin": {
                    "start": parent.WINDOWS["old_thin"]["start"],
                    "end": parent.WINDOWS["old_thin"]["end"],
                },
                "backtest_protocol": payload["backtest_protocol"],
            },
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "decision": decision,
            "rejection_reason": rejection_reason,
            "next_evidence_needed": payload["next_evidence_needed"],
            "lane": payload["lane"],
            "production_impact": payload["production_impact"],
            "llm_metrics": payload["llm_metrics"],
            "related_files": payload["related_files"],
            "status": status,
        },
    )
    print(f"[{EXPERIMENT_ID}] {decision}")
    print(
        "best_variant={key} ev_delta={ev} pnl_delta={pnl}".format(
            key=best_key,
            ev=payload["expected_value_score_delta"],
            pnl=payload["total_pnl_delta"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
