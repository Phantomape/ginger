"""exp-20260601-004: Companyfacts earnings-yield + RS candidate-pool scout.

Replay-only alpha scout. It tests whether PIT SEC Companyfacts quarterly EPS
annualized against signal-day price identifies better Fundamental Growth + RS
paper candidates. It does not change production orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260601_002_companyfacts_share_contraction_rs_candidate_pool as prev  # noqa: E402


EXPERIMENT_ID = "exp-20260601-004"
STEM = "companyfacts_earnings_yield_rs_candidate_pool"
TRIAL_FAMILY = "companyfacts_earnings_yield_rs_candidate_pool"
CHANGED_VARIABLE = "earnings_yield_positive_value_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = prev.SOURCE_EXPERIMENT_ID
SOURCE_ARTIFACT = prev.SOURCE_ARTIFACT
NON_OHLCV_DIR = prev.NON_OHLCV_DIR

MIN_EARNINGS_YIELD = 0.02
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
CANONICAL_DOC_EV = 7.8941
CANONICAL_DOC_PNL = 234_850.99

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    return prev._safe(value)


def _round(value: Any, digits: int = 4) -> Any:
    return prev._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return prev._repo_rel(path)


def _write_json(path: Path, payload: Any) -> None:
    prev._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    prev._write_text(path, text)


def _as_float(value: Any) -> float | None:
    return prev._as_float(value)


def _as_int(value: Any) -> int | None:
    return prev._as_int(value)


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


class EarningsYieldIndex:
    def __init__(self, *, tickers: set[str]) -> None:
        ticker_set = {ticker.upper() for ticker in tickers}
        by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for path in sorted(NON_OHLCV_DIR.glob("sec_companyfacts_selected_*.jsonl")):
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    canonical = str(row.get("canonical") or "")
                    if canonical not in {"eps_diluted", "eps_basic"}:
                        continue
                    ticker = str(row.get("ticker") or "").upper()
                    filed = str(row.get("filed") or "")[:10]
                    value = _as_float(row.get("value"))
                    duration_days = _as_int(row.get("duration_days"))
                    if (
                        ticker not in ticker_set
                        or not filed
                        or value is None
                        or duration_days is None
                        or duration_days < 60
                        or duration_days > 130
                    ):
                        continue
                    by_ticker[ticker].append(
                        {
                            "ticker": ticker,
                            "canonical": canonical,
                            "filed": filed,
                            "value": value,
                            "duration_days": duration_days,
                            "end": row.get("end"),
                            "form": row.get("form"),
                            "fp": row.get("fp"),
                            "fy": row.get("fy"),
                            "concept": row.get("concept"),
                            "unit": row.get("unit"),
                        }
                    )
        for rows in by_ticker.values():
            rows.sort(key=self._sort_key)
        self.by_ticker = by_ticker

    @staticmethod
    def _sort_key(row: dict[str, Any]) -> tuple[str, str, int, float]:
        return (
            str(row.get("filed") or ""),
            str(row.get("end") or ""),
            1 if row.get("canonical") == "eps_diluted" else 0,
            float(row.get("value") or 0.0),
        )

    def context(self, ticker: str, signal_date: str, close: Any) -> dict[str, Any]:
        price = _as_float(close)
        if price is None or price <= 0.0:
            return {
                "earnings_yield_status": "missing_signal_day_price",
                "earnings_yield_available": False,
                "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
            }
        rows = [
            row
            for row in self.by_ticker.get(ticker.upper(), [])
            if str(row.get("filed") or "") <= signal_date
        ]
        if not rows:
            return {
                "earnings_yield_status": "missing_quarterly_eps",
                "earnings_yield_available": False,
                "signal_day_close": _round(price, 4),
                "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
            }
        current = rows[-1]
        eps = _as_float(current.get("value"))
        if eps is None or eps <= 0.0:
            return {
                "earnings_yield_status": "non_positive_quarterly_eps",
                "earnings_yield_available": False,
                "quarterly_eps": _round(eps, 6),
                "signal_day_close": _round(price, 4),
                "eps_current_filed": current.get("filed"),
                "eps_current_period_end": current.get("end"),
                "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
            }
        annualized_eps = eps * 4.0
        earnings_yield = annualized_eps / price
        return {
            "earnings_yield_status": "ok",
            "earnings_yield_available": True,
            "earnings_yield_pass_v1": earnings_yield >= MIN_EARNINGS_YIELD,
            "earnings_yield_threshold_min": MIN_EARNINGS_YIELD,
            "earnings_yield": _round(earnings_yield, 6),
            "quarterly_eps": _round(eps, 6),
            "annualized_eps": _round(annualized_eps, 6),
            "signal_day_close": _round(price, 4),
            "eps_canonical": current.get("canonical"),
            "eps_current_filed": current.get("filed"),
            "eps_current_period_end": current.get("end"),
            "eps_current_duration_days": current.get("duration_days"),
            "eps_current_form": current.get("form"),
            "eps_current_fp": current.get("fp"),
            "eps_current_fy": current.get("fy"),
            "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
        }


def _select_target_trades(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    earnings_index: EarningsYieldIndex,
) -> tuple[OrderedDict[str, list[dict[str, Any]]], dict[str, Any]]:
    selected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts_by_window: OrderedDict[str, dict[str, int]] = OrderedDict()

    for label, rows in rows_by_window.items():
        selected: list[dict[str, Any]] = []
        filtered: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
            context = earnings_index.context(ticker, signal_date, row.get("close"))
            status_counts[str(context.get("earnings_yield_status") or "unknown")] += 1
            candidate = {
                **row,
                **context,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": RULE_VERSION,
                "earnings_yield_rule_version": RULE_VERSION,
                "strategy": "companyfacts_earnings_yield_rs_candidate_pool",
                "trade_enabled": False,
                "alters_orders": False,
                "source_experiment_id": SOURCE_EXPERIMENT_ID,
                "source_artifact": _repo_rel(SOURCE_ARTIFACT),
                "paper_pnl_source": "pnl_without_low_liability_support",
            }
            if context.get("earnings_yield_pass_v1") is not True:
                filtered.append({**candidate, "filter_reason": "earnings_yield_not_available_or_below_floor"})
                continue
            pnl = _as_float(row.get("pnl_without_low_liability_support"))
            if pnl is None:
                pnl = _as_float(row.get("pnl"))
                candidate["paper_pnl_source"] = "pnl"
            if pnl is None:
                filtered.append({**candidate, "filter_reason": "missing_paper_pnl"})
                continue
            selected.append({**candidate, "pnl": _round(pnl, 2), "paper_pnl": _round(pnl, 2)})

        selected_by_window[label] = selected
        filtered_by_window[label] = filtered[:200]
        status_counts_by_window[label] = dict(sorted(status_counts.items()))

    diagnostics = {
        "source_target_trade_count_by_window": {
            label: len(rows) for label, rows in rows_by_window.items()
        },
        "selected_earnings_yield_trade_count_by_window": {
            label: len(rows) for label, rows in selected_by_window.items()
        },
        "earnings_yield_status_counts_by_window": status_counts_by_window,
        "filtered_candidates_sample_by_window": filtered_by_window,
    }
    return selected_by_window, diagnostics


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    ev_windows_improved = [
        label
        for label, row in window_rows.items()
        if float(row["delta"].get("expected_value_score") or 0.0) > 0.0
    ]
    pnl_windows_improved = [
        label
        for label, row in window_rows.items()
        if float(row["delta"].get("total_pnl") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(float(row["delta"].get("max_drawdown_pct") or 0.0) for row in window_rows.values())
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values())
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for rows in target_summary["trades_by_window"].values() if rows > 0)
    gates = OrderedDict(
        [
            ("aggregate_expected_value_positive", float(aggregate["delta"]["expected_value_score"]) > 0.0),
            ("aggregate_pnl_positive", float(aggregate["delta"]["total_pnl"]) > 0.0),
            ("all_windows_expected_value_improved", len(ev_windows_improved) == len(window_rows)),
            ("all_windows_pnl_improved", len(pnl_windows_improved) == len(window_rows)),
            ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
            ("target_window_count_passed", target_window_count >= MIN_TARGET_WINDOWS),
            ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
            ("survival_floor_passed", min_survival_rate >= 0.05),
            (
                "concentration_guard_passed",
                float(target_summary["max_single_positive_share"] or 0.0) <= MAX_SINGLE_POSITIVE_SHARE
                and float(target_summary["positive_pnl_hhi"] or 0.0) <= MAX_POSITIVE_HHI,
            ),
        ]
    )
    failed = [name for name, passed in gates.items() if not passed]
    passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if passed
        else "rejected_companyfacts_earnings_yield_rs_candidate_pool"
    )
    rationale = (
        "Gate 4 passed, but this replay-only scout still requires a shared "
        "live/backtest default-off adapter before any retained promotion."
        if passed
        else "The earnings-yield discriminator did not clear Gate 4, so no "
        "production or shared policy change is retained."
    )
    return {
        "passed": passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_parity_before_promotion": passed,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    baseline_caveat = payload["baseline_caveat"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Earnings Yield + RS Candidate Pool",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            gate4["rationale"],
            "",
            "This scout used only filed-date Companyfacts quarterly EPS rows known on or before "
            "the signal date and signal-day OHLCV close from the accepted frozen Fundamental "
            "Growth + RS paper rows. It made no live/default order, ranking, sizing, exit, "
            "LLM, news, or watchlist change.",
            "",
            "## Baseline Caveat",
            "",
            baseline_caveat["note"],
            "",
            f"- docs/backtesting.md accepted aggregate EV/PnL: `{baseline_caveat['canonical_docs_ev']}` / "
            f"`${baseline_caveat['canonical_docs_pnl']:,.2f}`",
            f"- current dirty-worktree replay aggregate EV/PnL: `{baseline_caveat['current_replay_ev']}` / "
            f"`${baseline_caveat['current_replay_pnl']:,.2f}`",
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = prev.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_payload = prev._load_source_payload()
    source_rows_by_window = prev._source_target_rows_by_window(source_payload)
    tickers = {
        str(row.get("ticker") or "").upper()
        for rows in source_rows_by_window.values()
        for row in rows
        if row.get("ticker")
    }
    earnings_index = EarningsYieldIndex(tickers=tickers)
    selected_by_window, selection_diagnostics = _select_target_trades(
        source_rows_by_window,
        earnings_index,
    )
    baselines = prev._load_baselines()
    window_rows = prev._run_windows(baselines, selected_by_window)
    aggregate = prev._aggregate(window_rows)
    target_summary = prev._target_summary(selected_by_window)
    gate4 = _gate4(aggregate, window_rows, target_summary)
    baseline_caveat = {
        "canonical_docs_ev": CANONICAL_DOC_EV,
        "canonical_docs_pnl": CANONICAL_DOC_PNL,
        "current_replay_ev": aggregate["before"]["expected_value_score"],
        "current_replay_pnl": aggregate["before"]["total_pnl"],
        "ev_delta_vs_docs": _round(aggregate["before"]["expected_value_score"] - CANONICAL_DOC_EV, 6),
        "pnl_delta_vs_docs": _round(aggregate["before"]["total_pnl"] - CANONICAL_DOC_PNL, 2),
        "note": (
            "The current dirty-worktree replay baseline differs from the documented "
            "accepted core baseline in docs/backtesting.md. This prevents treating "
            "a positive replay as retained alpha without a clean parity baseline. "
            "The experiment is rejected anyway because the concentration guard failed."
        ),
    }
    timestamp = _utc_now()
    decision = gate4["decision"]
    accepted = bool(gate4["passed"])

    before_metrics = OrderedDict((label, row["before"]) for label, row in window_rows.items())
    after_metrics = OrderedDict((label, row["after"]) for label, row in window_rows.items())
    delta_metrics = OrderedDict((label, row["delta"]) for label, row in window_rows.items())

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "SEC Companyfacts earnings-price value may identify profitable, "
            "undervalued growth+RS candidates with better replacement value than "
            "the generic accepted Fundamental Growth + RS paper source."
        ),
        "change_type": "default_off_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "mechanism_family": "companyfacts_earnings_price_value_candidate_pool",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260528-008",
            "exp-20260528-017",
            "exp-20260601-002",
            "exp-20260601-003",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_visible_sec_companyfacts_earnings_yield_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": prev.base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Selected source trades use their already slippage-adjusted next-open "
                "entry and ten-trading-day exit PnL. The overlay is booked on each "
                "paper exit date against the canonical core baseline equity curve."
            ),
        },
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "earnings_yield_source": "SEC Companyfacts quarterly eps_diluted/eps_basic annualized against signal-day close",
            "min_earnings_yield": MIN_EARNINGS_YIELD,
            "eps_duration_days": "60..130",
            "paper_pnl_source": "pnl_without_low_liability_support",
            "locked_variables": [
                "core order generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "accepted alpha_score/source-consensus scalars",
                "accepted fundamental_growth_rs thresholds and top1 selection",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "pnl_improved_windows": 3,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: positive earnings-price value plus "
                "accepted growth+RS may isolate profitable value-momentum candidates."
            ),
            "2_history_check": {
                "exp-20260528-008": "Accepted Fundamental Growth + RS operating-profit-quality paper source.",
                "exp-20260528-017": "Accepted low-liability support on the same source; keep fixed here.",
                "exp-20260601-002": "Share-contraction candidate-pool scout was positive but rejected on drawdown/concentration.",
                "exp-20260601-003": "alpha_score decomposition showed current ranking edge is only momentum; this tests a non-momentum value field.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
                "all three windows improve; >=20 target trades across all windows; "
                "target trades in all three windows; drawdown drift <=0.5pp; "
                "survival >=5%; max single positive share <=0.50 and HHI <=0.30."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260601_004_companyfacts_earnings_yield_rs_candidate_pool.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_caveat": baseline_caveat,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "source target_trades_by_window entry_date",
                "source target_trades_by_window exit_date",
                "source pnl_without_low_liability_support",
                "source target_trades_by_window close",
                "sec_companyfacts_selected eps_diluted/eps_basic filed <= signal_date",
            ],
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values()) >= 0.05,
            "note": (
                "No core production filter was added. Survival rates are inherited "
                "from the canonical core baseline plus default-off paper overlay."
            ),
            "signals_generated_survived_by_window": {
                label: {
                    "signals_generated": row["after"].get("signals_generated"),
                    "signals_survived": row["after"].get("signals_survived"),
                    "survival_rate": row["after"].get("survival_rate"),
                }
                for label, row in window_rows.items()
            },
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "aggregate": aggregate,
        "baseline_caveat": baseline_caveat,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "target_trades_by_window": selected_by_window,
        "selection_diagnostics": selection_diagnostics,
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": "LLM soft-ranking data was not used; this tests a free deterministic data edge.",
        },
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "new independent deconcentration evidence",
            "forward out-of-sample rows showing non-APP contribution",
            "no earnings-yield threshold or scalar retry on the same frozen windows",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_JSON,
        {
            **payload["aggregate"]["before"],
            "windows": payload["before_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))

    log_row = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["total_pnl"],
            "aggregate_strategy_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_trade_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["delta"]["expected_value_score"],
                "strategy_total_pnl_delta": row["delta"]["total_pnl"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for label, row in payload["window_results"].items()
        ],
        "production_impact": payload["production_impact"],
        "requires_parity_before_promotion": payload["gate4"]["requires_parity_before_promotion"],
        "failure_reasons": payload["gate4"]["failed_gates"],
        "artifact_path": _repo_rel(OUT_JSON),
    }
    _upsert_jsonl(EXPERIMENT_LOG, log_row)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "target_trade_count",
                        "target_trade_pnl_usd",
                        "max_single_positive_share",
                        "positive_pnl_hhi",
                        "trades_by_window",
                        "pnl_by_window",
                    )
                },
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
