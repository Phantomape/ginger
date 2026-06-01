"""exp-20260601-019: Companyfacts FCF yield + RS candidate-pool scout.

Replay-only alpha scout. It tests whether filed-date SEC Companyfacts free
cash flow yield identifies better Fundamental Growth + RS paper candidates.
It does not change production orders, shared ranking, sizing, exits, or LLM
decision boundaries.
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


EXPERIMENT_ID = "exp-20260601-019"
STEM = "companyfacts_fcf_yield_rs_candidate_pool"
TRIAL_FAMILY = "companyfacts_fcf_yield_rs_candidate_pool"
CHANGED_VARIABLE = "fcf_yield_positive_value_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = prev.SOURCE_EXPERIMENT_ID
SOURCE_ARTIFACT = prev.SOURCE_ARTIFACT
NON_OHLCV_DIR = prev.NON_OHLCV_DIR

MIN_FCF_YIELD = 0.03
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
CANONICAL_DOC_EV = 7.8941
CANONICAL_DOC_PNL = 234_850.99
DOC_BASELINE_TOLERANCE_EV = 0.001
DOC_BASELINE_TOLERANCE_PNL = 1.0

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
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


class FcfYieldIndex:
    def __init__(self, *, tickers: set[str]) -> None:
        ticker_set = {ticker.upper() for ticker in tickers}
        by_ticker: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: {"operating_cash_flow": [], "capex": [], "shares_diluted": []}
        )
        for path in sorted(NON_OHLCV_DIR.glob("sec_companyfacts_selected_*.jsonl")):
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    canonical = str(row.get("canonical") or "")
                    if canonical not in {"operating_cash_flow", "capex", "shares_diluted"}:
                        continue
                    ticker = str(row.get("ticker") or "").upper()
                    filed = str(row.get("filed") or "")[:10]
                    value = _as_float(row.get("value"))
                    duration_days = _as_int(row.get("duration_days"))
                    if ticker not in ticker_set or not filed or value is None:
                        continue
                    if canonical in {"operating_cash_flow", "capex"} and (
                        duration_days is None or duration_days < 60 or duration_days > 400
                    ):
                        continue
                    if canonical == "shares_diluted" and value <= 0.0:
                        continue
                    by_ticker[ticker][canonical].append(
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
        for field_map in by_ticker.values():
            for rows in field_map.values():
                rows.sort(key=self._sort_key)
        self.by_ticker = by_ticker

    @staticmethod
    def _sort_key(row: dict[str, Any]) -> tuple[str, str, int, float]:
        return (
            str(row.get("filed") or ""),
            str(row.get("end") or ""),
            int(row.get("duration_days") or 0),
            float(row.get("value") or 0.0),
        )

    def _latest(self, ticker: str, canonical: str, signal_date: str) -> dict[str, Any] | None:
        rows = [
            row
            for row in self.by_ticker.get(ticker.upper(), {}).get(canonical, [])
            if str(row.get("filed") or "") <= signal_date
        ]
        return rows[-1] if rows else None

    @staticmethod
    def _annualized(row: dict[str, Any]) -> float | None:
        value = _as_float(row.get("value"))
        duration_days = _as_int(row.get("duration_days"))
        if value is None or duration_days is None or duration_days <= 0:
            return None
        return value * (365.0 / float(duration_days))

    def context(self, ticker: str, signal_date: str, close: Any) -> dict[str, Any]:
        price = _as_float(close)
        if price is None or price <= 0.0:
            return {
                "fcf_yield_status": "missing_signal_day_price",
                "fcf_yield_available": False,
                "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
            }

        ocf_row = self._latest(ticker, "operating_cash_flow", signal_date)
        capex_row = self._latest(ticker, "capex", signal_date)
        shares_row = self._latest(ticker, "shares_diluted", signal_date)
        missing = [
            name
            for name, row in (
                ("operating_cash_flow", ocf_row),
                ("capex", capex_row),
                ("shares_diluted", shares_row),
            )
            if row is None
        ]
        if missing:
            return {
                "fcf_yield_status": "missing_" + "_and_".join(missing),
                "fcf_yield_available": False,
                "signal_day_close": _round(price, 4),
                "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
            }

        assert ocf_row is not None
        assert capex_row is not None
        assert shares_row is not None
        annualized_ocf = self._annualized(ocf_row)
        annualized_capex = self._annualized(capex_row)
        shares = _as_float(shares_row.get("value"))
        if annualized_ocf is None or annualized_capex is None or shares is None or shares <= 0.0:
            return {
                "fcf_yield_status": "invalid_cash_flow_or_share_value",
                "fcf_yield_available": False,
                "signal_day_close": _round(price, 4),
                "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
            }

        annualized_fcf = annualized_ocf - abs(annualized_capex)
        market_cap = price * shares
        if market_cap <= 0.0:
            return {
                "fcf_yield_status": "invalid_market_cap",
                "fcf_yield_available": False,
                "signal_day_close": _round(price, 4),
                "shares_diluted": _round(shares, 3),
                "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
            }

        fcf_yield = annualized_fcf / market_cap
        status = "ok" if annualized_fcf > 0.0 else "non_positive_annualized_fcf"
        return {
            "fcf_yield_status": status,
            "fcf_yield_available": True,
            "fcf_yield_pass_v1": fcf_yield >= MIN_FCF_YIELD,
            "fcf_yield_threshold_min": MIN_FCF_YIELD,
            "fcf_yield": _round(fcf_yield, 6),
            "annualized_free_cash_flow": _round(annualized_fcf, 2),
            "annualized_operating_cash_flow": _round(annualized_ocf, 2),
            "annualized_capex_abs": _round(abs(annualized_capex), 2),
            "market_cap": _round(market_cap, 2),
            "signal_day_close": _round(price, 4),
            "shares_diluted": _round(shares, 3),
            "ocf_filed": ocf_row.get("filed"),
            "ocf_period_end": ocf_row.get("end"),
            "ocf_duration_days": ocf_row.get("duration_days"),
            "ocf_form": ocf_row.get("form"),
            "capex_filed": capex_row.get("filed"),
            "capex_period_end": capex_row.get("end"),
            "capex_duration_days": capex_row.get("duration_days"),
            "capex_form": capex_row.get("form"),
            "shares_filed": shares_row.get("filed"),
            "shares_period_end": shares_row.get("end"),
            "shares_form": shares_row.get("form"),
            "known_at": "SEC Companyfacts filed date <= signal date; OHLCV close on signal date",
        }


def _select_target_trades(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    fcf_index: FcfYieldIndex,
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
            context = fcf_index.context(ticker, signal_date, row.get("close"))
            status_counts[str(context.get("fcf_yield_status") or "unknown")] += 1
            candidate = {
                **row,
                **context,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": RULE_VERSION,
                "fcf_yield_rule_version": RULE_VERSION,
                "strategy": "companyfacts_fcf_yield_rs_candidate_pool",
                "trade_enabled": False,
                "alters_orders": False,
                "source_experiment_id": SOURCE_EXPERIMENT_ID,
                "source_artifact": _repo_rel(SOURCE_ARTIFACT),
                "paper_pnl_source": "pnl_without_low_liability_support",
            }
            if context.get("fcf_yield_pass_v1") is not True:
                filtered.append({**candidate, "filter_reason": "fcf_yield_not_available_or_below_floor"})
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
        "selected_fcf_yield_trade_count_by_window": {
            label: len(rows) for label, rows in selected_by_window.items()
        },
        "fcf_yield_status_counts_by_window": status_counts_by_window,
        "filtered_candidates_sample_by_window": filtered_by_window,
    }
    return selected_by_window, diagnostics


def _baseline_caveat(aggregate: dict[str, Any]) -> dict[str, Any]:
    ev_delta = float(aggregate["before"]["expected_value_score"]) - CANONICAL_DOC_EV
    pnl_delta = float(aggregate["before"]["total_pnl"]) - CANONICAL_DOC_PNL
    matches = (
        abs(ev_delta) <= DOC_BASELINE_TOLERANCE_EV
        and abs(pnl_delta) <= DOC_BASELINE_TOLERANCE_PNL
    )
    return {
        "baseline_matches_docs": matches,
        "canonical_docs_ev": CANONICAL_DOC_EV,
        "canonical_docs_pnl": CANONICAL_DOC_PNL,
        "current_replay_ev": aggregate["before"]["expected_value_score"],
        "current_replay_pnl": aggregate["before"]["total_pnl"],
        "ev_delta_vs_docs": _round(ev_delta, 6),
        "pnl_delta_vs_docs": _round(pnl_delta, 2),
        "note": (
            "The current dirty-worktree replay baseline differs from the documented "
            "accepted core baseline in docs/backtesting.md. A positive replay lead "
            "cannot be retained or promoted until a clean baseline/parity decision "
            "explains or accepts the drift."
        )
        if not matches
        else (
            "The current replay aggregate baseline matches the documented accepted "
            "core baseline within tolerance."
        ),
    }


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
    baseline_caveat: dict[str, Any],
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
    alpha_gates = OrderedDict(
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
    gates = OrderedDict(alpha_gates)
    gates["baseline_matches_docs_for_retention"] = bool(baseline_caveat["baseline_matches_docs"])
    alpha_failed = [name for name, passed in alpha_gates.items() if not passed]
    failed = [name for name, passed in gates.items() if not passed]
    alpha_passed = not alpha_failed
    promotable_now = alpha_passed and bool(baseline_caveat["baseline_matches_docs"])

    if alpha_passed and not baseline_caveat["baseline_matches_docs"]:
        decision = "positive_replay_lead_not_promoted_baseline_mismatch"
        rationale = (
            "The FCF-yield discriminator cleared the alpha gates, but exp-20260601-016 "
            "style baseline drift blocks retention or production promotion."
        )
    elif alpha_passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_adapter"
        rationale = (
            "The FCF-yield discriminator cleared alpha gates on a clean baseline, "
            "but no shared live/backtest default-off adapter was added in this run."
        )
    else:
        decision = "rejected_companyfacts_fcf_yield_rs_candidate_pool"
        rationale = (
            "The FCF-yield discriminator did not clear Gate 4 alpha checks, so no "
            "production or shared policy change is retained."
        )

    return {
        "passed": promotable_now,
        "alpha_passed": alpha_passed,
        "promotable_now": promotable_now,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "alpha_failed_gates": alpha_failed,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_parity_before_promotion": alpha_passed and not baseline_caveat["baseline_matches_docs"],
        "requires_shared_adapter_before_promotion": alpha_passed,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    baseline_caveat = payload["baseline_caveat"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts FCF Yield + RS Candidate Pool",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- alpha failed gates: `{', '.join(gate4['alpha_failed_gates']) or 'none'}`",
        f"- retention failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
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
            "This scout used only filed-date Companyfacts operating cash flow, capex, "
            "and diluted-share rows known on or before the signal date, plus the "
            "signal-day close from the accepted frozen Fundamental Growth + RS paper "
            "rows. It made no live/default order, ranking, sizing, exit, LLM, news, "
            "or watchlist change.",
            "",
            "## Baseline Caveat",
            "",
            baseline_caveat["note"],
            "",
            f"- docs/backtesting.md accepted aggregate EV/PnL: `{baseline_caveat['canonical_docs_ev']}` / "
            f"`${baseline_caveat['canonical_docs_pnl']:,.2f}`",
            f"- current replay aggregate EV/PnL: `{baseline_caveat['current_replay_ev']}` / "
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


def _card(payload: dict[str, Any]) -> str:
    ticket = payload["ticket"]
    closeout = payload["closeout"]
    prediction = ticket.get("prediction") or {}
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'experiment_uid: "{ticket.get("experiment_uid")}"',
            f'status: "{payload["decision"]}"',
            'lane: "alpha_search"',
            'change_type: "default_off_candidate_pool_scout"',
            'mechanism_family: "companyfacts_fcf_yield_candidate_pool"',
            f'trial_family: "{TRIAL_FAMILY}"',
            f'trial_variant_id: "{CHANGED_VARIABLE}"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            'new_evidence_type: "production_visible_sec_companyfacts_fcf_yield_field"',
            f'created_at: "{ticket.get("created_at")}"',
            'baseline_result_file: "data/backtests/backtest_results_20260531.json"',
            'tags:',
            '  - "alpha_search"',
            '  - "companyfacts_fcf_yield_rs_candidate_pool"',
            '  - "production_visible_sec_companyfacts_fcf_yield_field"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["hypothesis"],
            "",
            "## Identity",
            "",
            f"- Status: `{payload['decision']}`",
            "- Lane: `alpha_search`",
            "- Change type: `default_off_candidate_pool_scout`",
            f"- Owner: `{ticket.get('owner')}`",
            f"- UID: `{ticket.get('experiment_uid')}`",
            "",
            "## Causal Variable",
            "",
            f"- Single causal variable: `{CHANGED_VARIABLE}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Pre-Run Prediction",
            "",
            "```json",
            json.dumps(_safe(prediction), indent=2, ensure_ascii=True, sort_keys=True),
            "```",
            "",
            "## Closeout Notes",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Before artifact: `{_repo_rel(BEFORE_JSON)}`",
            f"- After artifact: `{_repo_rel(AFTER_JSON)}`",
            f"- Main blocker or acceptance basis: {closeout['basis']}",
            f"- Next retry requires: {closeout['next_retry_requires']}",
            "",
        ]
    )


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "alpha_passed": payload["gate4"]["alpha_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "metrics": {
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
        "failed_gates": payload["gate4"]["failed_gates"],
    }
    _write_json(TICKET_JSON, ticket)


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
    fcf_index = FcfYieldIndex(tickers=tickers)
    selected_by_window, selection_diagnostics = _select_target_trades(
        source_rows_by_window,
        fcf_index,
    )
    baselines = prev._load_baselines()
    window_rows = prev._run_windows(baselines, selected_by_window)
    aggregate = prev._aggregate(window_rows)
    target_summary = prev._target_summary(selected_by_window)
    baseline_caveat = _baseline_caveat(aggregate)
    gate4 = _gate4(aggregate, window_rows, target_summary, baseline_caveat)
    timestamp = _utc_now()
    decision = gate4["decision"]
    accepted = bool(gate4["promotable_now"])
    ticket = _load_ticket()

    before_metrics = OrderedDict((label, row["before"]) for label, row in window_rows.items())
    after_metrics = OrderedDict((label, row["after"]) for label, row in window_rows.items())
    delta_metrics = OrderedDict((label, row["delta"]) for label, row in window_rows.items())

    closeout_basis = (
        "Alpha gates passed, but documented/current baseline drift blocks retention."
        if gate4["alpha_passed"] and not baseline_caveat["baseline_matches_docs"]
        else gate4["rationale"]
    )
    next_retry = (
        "clean baseline/parity decision plus forward replacement rows"
        if gate4["alpha_passed"]
        else "new independent FCF-quality evidence, not another same-sample threshold"
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "SEC Companyfacts free-cash-flow yield may identify profitable, "
            "cash-generative growth+RS candidates with better replacement value than "
            "the generic accepted Fundamental Growth + RS paper source."
        ),
        "change_type": "default_off_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "mechanism_family": "companyfacts_fcf_yield_candidate_pool",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260528-006",
            "exp-20260529-003",
            "exp-20260601-004",
            "exp-20260601-016",
            "exp-20260601-018",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_sec_companyfacts_fcf_yield_field",
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
            "fcf_yield_source": (
                "SEC Companyfacts operating_cash_flow minus abs(capex), annualized "
                "by duration_days, divided by signal-day close times latest shares_diluted"
            ),
            "min_fcf_yield": MIN_FCF_YIELD,
            "cash_flow_duration_days": "60..400",
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
                "baseline_matches_docs_for_retention": True,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: filed-date free-cash-flow yield plus "
                "accepted growth+RS may isolate profitable cash-generative value-momentum candidates."
            ),
            "2_history_check": {
                "exp-20260528-006": "Cash-conversion quality did not earn retention.",
                "exp-20260529-003": "Low-capex intensity was positive but rejected by gates.",
                "exp-20260601-004": "Earnings-yield value failed concentration on similar source rows.",
                "exp-20260601-016": "Current-code baseline drift blocks retained alpha promotion.",
                "exp-20260601-018": "Consensus capacity was a positive replay lead but not promotable due baseline drift.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
                "all three windows improve; >=20 target trades across all windows; "
                "target trades in all three windows; drawdown drift <=0.5pp; "
                "survival >=5%; max single positive share <=0.50 and HHI <=0.30; "
                "documented/current baseline must match for retention."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260601_019_companyfacts_fcf_yield_rs_candidate_pool.py"
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
                "sec_companyfacts_selected operating_cash_flow filed <= signal_date",
                "sec_companyfacts_selected capex filed <= signal_date",
                "sec_companyfacts_selected shares_diluted filed <= signal_date",
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
        "ticket": ticket,
        "closeout": {
            "basis": closeout_basis,
            "next_retry_requires": next_retry,
        },
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            next_retry,
            "no FCF-yield threshold/scalar retry on the same frozen windows without new evidence",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
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
            "baseline_caveat": payload["baseline_caveat"],
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
            "baseline_caveat": payload["baseline_caveat"],
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))
    _write_text(CARD_MD, _card(payload))
    _update_ticket(payload)

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
            "baseline_matches_docs": payload["baseline_caveat"]["baseline_matches_docs"],
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
        "requires_shared_adapter_before_promotion": payload["gate4"]["requires_shared_adapter_before_promotion"],
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
                "baseline_caveat": payload["baseline_caveat"],
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
