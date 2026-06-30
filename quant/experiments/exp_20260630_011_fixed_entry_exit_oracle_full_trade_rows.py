"""exp-20260630-011: full fixed-entry exit-oracle trade rows.

Measurement repair for the exit-policy alpha line.  The prior diagnostic
(`exp-20260630-009`) found a stable oracle-regret cohort, but rejected it
because the saved oracle blocks exposed only top-regret samples.  This runner
materializes every fixed-entry trade-level oracle row for the canonical
2026-06-04 windows so future exit-policy tests can measure denominators and
false-positive rates before trying any shared exit rule.

No entry, exit, ranking, sizing, paper, live, watchlist, LLM, or news behavior
is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-011"
OWNER = "alpha-explore"
SLUG = "fixed_entry_exit_oracle_full_trade_rows"
RUNNER = f"quant/experiments/exp_20260630_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from oracle_diagnostics import (  # noqa: E402
    _ohlcv_rows_by_date,
    _oracle_exit_for_trade,
    _window_rows,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ARCHIVE_DIR = (
    REPO_ROOT / "data" / "backtests" / "archive" / "20260604_ohlcv_warehouse_replay"
)
WINDOW_FILES = {
    "late_strong": ARCHIVE_DIR / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    "mid_weak": ARCHIVE_DIR / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    "old_thin": ARCHIVE_DIR / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_011_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Repair fixed-entry exit-oracle diagnostics to persist full trade-level "
    "oracle rows so future exit-policy alpha tests can measure cohort "
    "denominators instead of top-regret samples only."
)
ALPHA_HYPOTHESIS = (
    "Exit-policy alpha may exist where current canonical exits leave avoidable "
    "intratrade giveback, but it is only testable if every fixed-entry trade "
    "has an oracle row, not just the top-regret tail."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "exit_policy_oracle_diagnostic"
TRIAL_FAMILY = "fixed_entry_exit_oracle_full_trade_rows"
TRIAL_VARIANT_ID = "canonical_20260604_full_trade_rows_v1"
CHANGED_VARIABLE = "fixed_entry_exit_oracle_full_trade_rows_v1"
CAUSAL_COMPONENTS = [
    "canonical_window_backtest_artifacts",
    "matching_ohlcv_snapshot_replay",
    "full_trade_level_fixed_entry_oracle_rows",
    "cohort_denominator_summary",
    "no_strategy_change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260429-032",
    "exp-20260623-003",
    "exp-20260623-020",
    "exp-20260630-009",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, set):
        return sorted(safe(item) for item in value)
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def rounded(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    return round(number, digits) if number is not None else None


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number:.2%}"


def load_ticket() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return ticket if isinstance(ticket, dict) else {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "windows": windows,
    }


def resolve_snapshot_path(backtest: Mapping[str, Any]) -> Path | None:
    source = ((backtest.get("known_biases") or {}).get("ohlcv_source") or {})
    raw = source.get("snapshot_path") or source.get("warehouse_snapshot_source")
    if not raw:
        return None
    path = Path(str(raw))
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def date_offset(rows: list[Mapping[str, Any]], start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    dates = [str(row.get("Date")) for row in rows if row.get("Date")]
    try:
        return dates.index(end) - dates.index(start)
    except ValueError:
        return None


def classify_exit_error(row: Mapping[str, Any]) -> str:
    regret = as_float(row.get("regret_vs_oracle")) or 0.0
    oracle_pnl = as_float(row.get("oracle_pnl")) or 0.0
    actual_pnl = as_float(row.get("actual_pnl")) or 0.0
    actual_exit_date = row.get("actual_exit_date")
    oracle_exit_date = row.get("oracle_exit_date")
    if oracle_pnl <= 0 and actual_pnl <= 0:
        return "bad_entry_no_positive_oracle"
    if regret <= max(100.0, abs(oracle_pnl) * 0.05):
        return "no_material_oracle_gap"
    if oracle_exit_date and actual_exit_date and oracle_exit_date < actual_exit_date:
        return "giveback_or_late_exit"
    if str(row.get("exit_reason") or "").lower() == "stop":
        return "stop_loss_with_intraday_oracle_gap"
    if oracle_exit_date == actual_exit_date:
        return "same_day_capture_gap"
    return "other_exit_gap"


def enrich_trade_oracle(
    *,
    window_label: str,
    trade: Mapping[str, Any],
    oracle: Mapping[str, Any],
    hold_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    entry_price = as_float(trade.get("entry_price"))
    actual_pnl = as_float(oracle.get("actual_pnl")) or 0.0
    shares = as_float(trade.get("shares"))
    highs = [as_float(row.get("High")) for row in hold_rows]
    lows = [as_float(row.get("Low")) for row in hold_rows]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]

    capital = entry_price * shares if entry_price and shares else None
    realized_return = actual_pnl / capital if capital else None
    max_favorable = (
        (max(highs) * (1 - 0.0035) / entry_price) - 1
        if highs and entry_price
        else None
    )
    max_adverse = (
        (min(lows) * (1 - 0.0035) / entry_price) - 1
        if lows and entry_price
        else None
    )
    giveback = (
        max_favorable - realized_return
        if max_favorable is not None and realized_return is not None
        else None
    )

    row = {
        **dict(oracle),
        "oracle_eligible": True,
        "oracle_missing_reason": None,
        "window": window_label,
        "trade_key": trade.get("trade_key"),
        "sector": trade.get("sector"),
        "target_mult_used": rounded(trade.get("target_mult_used"), 4),
        "initial_risk_pct": rounded(trade.get("initial_risk_pct"), 6),
        "base_risk_pct": rounded(trade.get("base_risk_pct"), 6),
        "actual_risk_pct": rounded(trade.get("actual_risk_pct"), 6),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": rounded(trade.get("regime_exit_score"), 6),
        "addon_count": as_int(trade.get("addon_count")) or 0,
        "exit_advisory_rules_seen": list(trade.get("exit_advisory_rules_seen") or []),
        "sizing_multiplier_tags": sorted(
            str(key) for key in (trade.get("sizing_multipliers") or {}).keys()
        ),
        "hold_trading_days": len(hold_rows),
        "oracle_exit_offset_trading_days": date_offset(
            hold_rows, trade.get("entry_date"), oracle.get("oracle_exit_date")
        ),
        "actual_exit_offset_trading_days": date_offset(
            hold_rows, trade.get("entry_date"), trade.get("exit_date")
        ),
        "realized_return_pct": rounded(realized_return, 6),
        "max_favorable_excursion_pct": rounded(max_favorable, 6),
        "max_adverse_excursion_pct": rounded(max_adverse, 6),
        "giveback_pct": rounded(giveback, 6),
    }
    row["exit_error_bucket"] = classify_exit_error(row)
    return row


def missing_trade_denominator_row(
    *,
    window_label: str,
    trade: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    actual_pnl = as_float(trade.get("pnl"))
    entry_price = as_float(trade.get("entry_price"))
    shares = as_float(trade.get("shares"))
    capital = entry_price * shares if entry_price and shares else None
    return {
        "window": window_label,
        "oracle_eligible": False,
        "oracle_missing_reason": reason,
        "exit_error_bucket": "not_oracle_eligible_" + reason,
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "trade_key": trade.get("trade_key"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "actual_exit_date": trade.get("exit_date"),
        "oracle_exit_date": None,
        "entry_price": rounded(entry_price, 4),
        "actual_exit_price": trade.get("exit_price"),
        "oracle_exit_price": None,
        "shares": trade.get("shares"),
        "actual_pnl": rounded(actual_pnl, 2),
        "oracle_pnl": None,
        "regret_vs_oracle": None,
        "capture_ratio": None,
        "exit_reason": trade.get("exit_reason"),
        "target_mult_used": rounded(trade.get("target_mult_used"), 4),
        "initial_risk_pct": rounded(trade.get("initial_risk_pct"), 6),
        "base_risk_pct": rounded(trade.get("base_risk_pct"), 6),
        "actual_risk_pct": rounded(trade.get("actual_risk_pct"), 6),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": rounded(trade.get("regime_exit_score"), 6),
        "addon_count": as_int(trade.get("addon_count")) or 0,
        "exit_advisory_rules_seen": list(trade.get("exit_advisory_rules_seen") or []),
        "sizing_multiplier_tags": sorted(
            str(key) for key in (trade.get("sizing_multipliers") or {}).keys()
        ),
        "hold_trading_days": 0,
        "oracle_exit_offset_trading_days": None,
        "actual_exit_offset_trading_days": None,
        "realized_return_pct": rounded(actual_pnl / capital, 6) if capital else None,
        "max_favorable_excursion_pct": None,
        "max_adverse_excursion_pct": None,
        "giveback_pct": None,
    }


def build_window_rows(label: str, path: Path) -> dict[str, Any]:
    backtest = read_json(path, {})
    snapshot_path = resolve_snapshot_path(backtest)
    snapshot = read_json(snapshot_path, {}) if snapshot_path else {}
    rows_by_ticker = _ohlcv_rows_by_date(snapshot)
    trades = list(backtest.get("trades") or [])
    full_rows: list[dict[str, Any]] = []
    missing = []

    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        ticker_rows = rows_by_ticker.get(ticker)
        if not ticker_rows:
            reason = "missing_ohlcv"
            missing.append({"ticker": ticker, "trade_key": trade.get("trade_key"), "reason": reason})
            full_rows.append(
                missing_trade_denominator_row(
                    window_label=label,
                    trade=trade,
                    reason=reason,
                )
            )
            continue
        hold_rows = _window_rows(ticker_rows, trade.get("entry_date"), trade.get("exit_date"))
        oracle = _oracle_exit_for_trade(trade, hold_rows)
        if oracle is None:
            reason = "insufficient_trade_or_price_data"
            missing.append({"ticker": ticker, "trade_key": trade.get("trade_key"), "reason": reason})
            full_rows.append(
                missing_trade_denominator_row(
                    window_label=label,
                    trade=trade,
                    reason=reason,
                )
            )
            continue
        full_rows.append(
            enrich_trade_oracle(
                window_label=label,
                trade=trade,
                oracle=oracle,
                hold_rows=hold_rows,
            )
        )

    eligible_rows = [row for row in full_rows if row.get("oracle_eligible")]
    full_actual = round(sum(float(row.get("actual_pnl") or 0.0) for row in eligible_rows), 2)
    full_oracle = round(sum(float(row.get("oracle_pnl") or 0.0) for row in eligible_rows), 2)
    full_regret = round(full_oracle - full_actual, 2)
    perfect_exit = ((backtest.get("oracle_diagnostics") or {}).get("oracle_metrics") or {}).get(
        "perfect_exit"
    ) or {}
    expected_regret = rounded(perfect_exit.get("regret_vs_oracle"), 2)
    return {
        "window": label,
        "source_file": repo_rel(path),
        "snapshot_file": repo_rel(snapshot_path) if snapshot_path else None,
        "backtest_trade_count": len(trades),
        "full_trade_oracle_row_count": len(full_rows),
        "eligible_trade_oracle_row_count": len(eligible_rows),
        "ineligible_trade_denominator_row_count": len(missing),
        "missing_trade_count": len(missing),
        "missing_trades": missing,
        "actual_pnl": full_actual,
        "oracle_pnl": full_oracle,
        "regret_vs_oracle": full_regret,
        "capture_ratio": round(full_actual / full_oracle, 6) if full_oracle > 0 else None,
        "expected_existing_oracle": {
            "trade_count": perfect_exit.get("trade_count"),
            "missing_trade_count": perfect_exit.get("missing_trade_count"),
            "actual_pnl": perfect_exit.get("actual_pnl"),
            "oracle_pnl": perfect_exit.get("oracle_pnl"),
            "regret_vs_oracle": perfect_exit.get("regret_vs_oracle"),
            "top_regret_trade_count": len(perfect_exit.get("top_regret_trades") or []),
        },
        "regret_matches_existing_oracle": (
            expected_regret is not None and abs(full_regret - expected_regret) <= 0.05
        ),
        "oracle_missing_matches_existing": len(missing)
        == int(perfect_exit.get("missing_trade_count") or 0),
        "trade_rows": full_rows,
    }


def group_rows(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            tuple(str(row.get(key) or "missing") for key in keys)
        ].append(row)

    out = {}
    for key, members in sorted(grouped.items()):
        actual = sum(float(row.get("actual_pnl") or 0.0) for row in members)
        oracle = sum(float(row.get("oracle_pnl") or 0.0) for row in members)
        regret = oracle - actual
        windows = sorted({str(row.get("window")) for row in members})
        out["|".join(key)] = {
            "keys": dict(zip(keys, key)),
            "trade_count": len(members),
            "window_count": len(windows),
            "windows": windows,
            "actual_pnl": round(actual, 2),
            "oracle_pnl": round(oracle, 2),
            "regret_vs_oracle": round(regret, 2),
            "avg_regret_vs_oracle": round(regret / len(members), 2) if members else None,
            "capture_ratio": round(actual / oracle, 6) if oracle > 0 else None,
            "tickers": sorted({str(row.get("ticker")) for row in members}),
            "exit_error_buckets": dict(
                sorted(Counter(str(row.get("exit_error_bucket")) for row in members).items())
            ),
        }
    return out


def summarize(windows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = [row for window in windows.values() for row in window["trade_rows"]]
    eligible_rows = [row for row in rows if row.get("oracle_eligible")]
    ineligible_rows = [row for row in rows if not row.get("oracle_eligible")]
    actual = sum(float(row.get("actual_pnl") or 0.0) for row in eligible_rows)
    oracle = sum(float(row.get("oracle_pnl") or 0.0) for row in eligible_rows)
    regret = oracle - actual
    top_rows = sorted(
        eligible_rows,
        key=lambda row: float(row.get("regret_vs_oracle") or 0.0),
        reverse=True,
    )[:10]
    by_strategy_exit = group_rows(eligible_rows, ("strategy", "exit_reason"))
    return {
        "denominator_trade_row_count": len(rows),
        "eligible_trade_oracle_row_count": len(eligible_rows),
        "ineligible_trade_denominator_row_count": len(ineligible_rows),
        "ineligible_trade_denominator_rows": ineligible_rows,
        "full_trade_oracle_row_count": len(rows),
        "window_count": len(windows),
        "actual_pnl": round(actual, 2),
        "oracle_pnl": round(oracle, 2),
        "regret_vs_oracle": round(regret, 2),
        "capture_ratio": round(actual / oracle, 6) if oracle > 0 else None,
        "top_regret_trade_count": len(top_rows),
        "top_regret_rows": top_rows,
        "top_regret_share_of_total_regret": round(
            sum(float(row.get("regret_vs_oracle") or 0.0) for row in top_rows) / regret,
            6,
        )
        if regret > 0
        else None,
        "by_strategy": group_rows(eligible_rows, ("strategy",)),
        "by_exit_reason": group_rows(eligible_rows, ("exit_reason",)),
        "by_strategy_exit_reason": by_strategy_exit,
        "by_exit_error_bucket": group_rows(eligible_rows, ("exit_error_bucket",)),
        "by_ticker": group_rows(eligible_rows, ("ticker",)),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = load_ticket()
    baseline = load_baseline_metrics()
    windows = {label: build_window_rows(label, path) for label, path in WINDOW_FILES.items()}
    summary = summarize(windows)
    expected_trade_count = baseline["trade_count"]
    denominator_rows = summary["denominator_trade_row_count"]
    eligible_rows = summary["eligible_trade_oracle_row_count"]
    existing_oracle_trade_count = sum(
        int((window["expected_existing_oracle"].get("trade_count") or 0))
        for window in windows.values()
    )
    missing_files = [repo_rel(path) for path in WINDOW_FILES.values() if not path.exists()]
    failed = []
    if not BASELINE_RESULT.exists():
        failed.append("baseline_missing")
    if missing_files:
        failed.append("canonical_window_backtest_missing")
    if denominator_rows != expected_trade_count:
        failed.append("full_trade_row_count_does_not_match_baseline_trade_count")
    if eligible_rows != existing_oracle_trade_count:
        failed.append("eligible_trade_row_count_does_not_match_existing_oracle_count")
    if not all(window["regret_matches_existing_oracle"] for window in windows.values()):
        failed.append("recomputed_oracle_does_not_match_existing_summary")
    if not all(window["oracle_missing_matches_existing"] for window in windows.values()):
        failed.append("oracle_missing_rows_do_not_match_existing_summary")

    accepted = not failed
    decision = (
        "accepted_measurement_repair_full_fixed_entry_exit_oracle_rows"
        if accepted
        else "blocked_fixed_entry_exit_oracle_full_rows_incomplete"
    )
    status = "accepted_measurement_repair" if accepted else "blocked"
    prediction = ticket.get("prediction") or {
        "success_probability": 0.8,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "snapshot_path_missing",
            "recomputed_oracle_mismatch",
            "missing_trade_price_data",
        ],
        "confidence_reason": (
            "The existing oracle summary is produced from per-trade calculations; "
            "the likely repair is exposing those rows from saved window artifacts "
            "and matching OHLCV snapshots, with no strategy behavior change."
        ),
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
    }
    success_probability = as_float(prediction.get("success_probability")) or 0.0
    actual_success = 1.0 if accepted else 0.0
    failure_modes = list(prediction.get("main_failure_modes") or [])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "measurement_repair",
        "owner": OWNER,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "full_trade_level_oracle_denominator_rows",
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260429-032": "Rejected bare target/SIGNAL_TARGET partial trim replay.",
                "exp-20260623-003": "Earlier fixed-entry oracle cluster remained diagnostic only.",
                "exp-20260630-009": (
                    "Rejected only because full trade-level oracle rows were missing."
                ),
                "novelty_gate": "Reservation passed; this is measurement repair, not an exit-rule retry.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept as measurement repair only if every canonical-window trade has "
                "one denominator row, oracle-eligible rows match existing oracle counts, "
                "no strategy metrics move, and recomputed oracle regret matches existing "
                "oracle summaries."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "window_files": {label: repo_rel(path) for label, path in WINDOW_FILES.items()},
            "diagnostic_boundary": (
                "Fixed-entry oracle uses future intratrade highs over the realized "
                "holding window; it is denominator repair only, not an exit rule."
            ),
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "window_files_loaded": {
                label: path.exists() for label, path in WINDOW_FILES.items()
            },
            "passed": BASELINE_RESULT.exists() and not missing_files,
        },
        "gate2": {
            "dependencies_validated": True,
            "fields_checked": [
                "trades.entry_date",
                "trades.exit_date",
                "trades.entry_price",
                "trades.exit_price",
                "trades.shares",
                "trades.pnl",
                "trades.exit_reason",
                "known_biases.ohlcv_source.warehouse_snapshot_source",
                "ohlcv.<ticker>.Date/Open/High/Low/Close",
            ],
            "entry_date_present": all(
                bool(row.get("entry_date"))
                for window in windows.values()
                for row in window["trade_rows"]
            ),
            "target_price_relevance": (
                "Not applicable. This repair emits diagnostic fixed-entry rows and "
                "does not schedule target exits or orders."
            ),
            "passed": denominator_rows == expected_trade_count,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, ranking, sizing, or exit rule was added.",
            "passed": True,
        },
        "gate4": {
            "decision": decision,
            "passed": accepted,
            "failed_reasons": failed,
            "measurement_repair_only": True,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
                "survival_rate": 0.0,
            },
            "acceptance_checks": {
                "denominator_rows_equal_baseline_trades": denominator_rows == expected_trade_count,
                "eligible_trade_rows_equal_existing_oracle_trades": (
                    eligible_rows == existing_oracle_trade_count
                ),
                "oracle_missing_rows_match_existing_summary": all(
                    window["oracle_missing_matches_existing"] for window in windows.values()
                ),
                "recomputed_oracle_matches_existing_summary": all(
                    window["regret_matches_existing_oracle"] for window in windows.values()
                ),
                "strategy_behavior_changed": False,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "full_trade_oracle_rows_written": denominator_rows,
            "eligible_trade_oracle_rows_written": eligible_rows,
            "ineligible_trade_denominator_rows_written": (
                summary["ineligible_trade_denominator_row_count"]
            ),
            "expected_trade_count": expected_trade_count,
            "existing_oracle_trade_count": existing_oracle_trade_count,
            "oracle_regret_vs_current_exits": summary["regret_vs_oracle"],
        },
        "oracle_full_trade_rows": {
            "summary": summary,
            "windows": windows,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "llm_prompt_changed": False,
            "daily_snapshot_exposed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "replay_only": False,
            "parity_note": (
                "Experiment-owned diagnostic artifact only; no production, backtest, "
                "paper, order, or LLM behavior changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": round(success_probability, 4),
            "actual_success": bool(accepted),
            "brier_score": round((success_probability - actual_success) ** 2, 6),
            "predicted_failure_modes": failure_modes,
            "realized_failure_modes": failed,
            "predicted_failure_mode_hit": bool(failed),
            "expected_ev_delta": prediction.get("expected_ev_delta", 0.0),
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": prediction.get("expected_pnl_delta", 0.0),
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "The repair succeeded by reconstructing rows from existing trade logs "
                "and matching warehouse snapshot sources."
                if accepted
                else "The repair remained incomplete; see failed_reasons."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The saved canonical window artifacts already contain every completed "
                "trade and the matching PIT OHLCV snapshot source. Recomputing the "
                "same oracle logic produces full denominators and matches the existing "
                "top-level oracle summaries."
                if accepted
                else "At least one canonical artifact or trade row could not be matched "
                "to the required OHLCV window."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use these oracle rows to retune target trims, trailing stops, "
                "stop distances, hold days, target prices, or response curves. The "
                "next alpha step must predeclare one production-visible exit signal "
                "and run a shared Gate 1-4 policy test."
            ),
            "new_evidence_required": (
                "A valid exit-policy alpha retry now needs a shared production/backtest "
                "exit helper using only pre-exit fields, or prospective shadow exit "
                "advisory rows with settled replacement value. Oracle exit dates/prices "
                "remain future-only labels."
            ),
        },
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            *(repo_rel(path) for path in WINDOW_FILES.values()),
            "quant/oracle_diagnostics.py",
            "experiments/logs/exp-20260630-009.json",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no JavaScript tooling invoked.",
        },
    }


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "oracle_summary": payload["oracle_full_trade_rows"]["summary"],
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "related_files": payload["related_files"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": bool(payload["accepted"]),
        "anti_js": payload["anti_js"],
    }


def build_card(payload: Mapping[str, Any]) -> str:
    rows = [
        "| Window | Full rows | Regret vs oracle | Capture ratio | Existing summary match |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, window in payload["oracle_full_trade_rows"]["windows"].items():
        rows.append(
            "| {label} | {count} | {regret} | {capture} | {match} |".format(
                label=label,
                count=window["full_trade_oracle_row_count"],
                regret=money(window["regret_vs_oracle"]),
                capture=pct(window["capture_ratio"]),
                match=str(window["regret_matches_existing_oracle"]).lower(),
            )
        )
    summary = payload["oracle_full_trade_rows"]["summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: fixed-entry exit oracle full trade rows",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production behavior changed: no",
            "- Accepted alpha: no; accepted measurement repair only",
            "",
            "## Full Rows",
            "",
            *rows,
            "",
            f"- Aggregate full rows: `{summary['full_trade_oracle_row_count']}`",
            f"- Aggregate regret vs oracle: `{money(summary['regret_vs_oracle'])}`",
            f"- Aggregate capture ratio: `{pct(summary['capture_ratio'])}`",
            f"- Top-regret share of total regret: `{pct(summary['top_regret_share_of_total_regret'])}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_row = compact_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload.get("prediction"),
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    summary = payload["oracle_full_trade_rows"]["summary"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "gate4": payload["gate4"],
                "full_trade_oracle_row_count": summary["full_trade_oracle_row_count"],
                "regret_vs_oracle": summary["regret_vs_oracle"],
                "capture_ratio": summary["capture_ratio"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
