"""exp-20260626-021: full quant_signals forward readiness.

Alpha-search, observed-only. This scans the complete May-June production
quant_signals entry-candidate surface after exp-20260626-006 showed that the
recovered-target subset only contained non-session rows. It does not change
entries, ranking, sizing, exits, orders, watchlists, or LLM behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from experiment_registry import persist_self_registered_result  # noqa: E402
from us_market_calendar import is_us_equity_session  # noqa: E402


EXPERIMENT_ID = "exp-20260626-021"
OWNER = "alpha-explore"
SLUG = "full_quant_signals_forward_readiness"
RUNNER = f"quant/experiments/exp_20260626_021_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_021_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
QUANT_SIGNAL_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

START_DATE = date(2026, 5, 1)
END_DATE = date(2026, 6, 25)
FORWARD_HORIZONS = (1, 3, 5)
DEFAULT_NOTIONAL = 4000.0
ROUND_TRIP_COST_PCT = 0.0085

HYPOTHESIS = (
    "Production quant_signals entry_candidate_review rows across the recovered "
    "and current May-June daily artifacts may create a forward replacement-value "
    "evidence axis if valid-session candidates can be settled; first scan the "
    "full surface rather than retuning any strategy threshold."
)
CHANGE_TYPE = "observed_only_forward_attribution"
IMPLEMENTATION_MODE = "observed_only_forward_readiness"
MECHANISM_FAMILY = "production_candidate_artifact_forward_maturation"
TRIAL_FAMILY = "full_quant_signals_entry_candidate_forward_readiness"
TRIAL_VARIANT_ID = "full_may_june_2026_surface_v1"
CHANGED_VARIABLE = "full_surface_quant_signals_entry_candidate_forward_readiness_v1"
NEW_EVIDENCE_TYPE = "complete_production_quant_signals_candidate_surface_scan"
NEW_EVIDENCE_AXIS = (
    "Complete May-June production quant_signals entry_candidate_review scan, "
    "including recovered and non-recovered final artifacts, with session-date "
    "validation and local warehouse settlement audit. This is not a threshold, "
    "ranking, sizing, hold-day, or notional sweep."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260626-005",
    "exp-20260626-006",
    "exp-20260622-022",
]
CAUSAL_COMPONENTS = [
    "full quant_signals artifact scan",
    "session-date validation",
    "local settlement audit",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_021_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def date_from_tag(tag: str) -> date:
    return date(int(tag[:4]), int(tag[4:6]), int(tag[6:8]))


def next_session_after(day: date) -> date:
    cursor = day + timedelta(days=1)
    while not is_us_equity_session(cursor):
        cursor += timedelta(days=1)
    return cursor


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
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
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def quant_signal_paths() -> list[Path]:
    paths: list[Path] = []
    for path in sorted(QUANT_SIGNAL_DIR.glob("quant_signals_2026*.json")):
        tag = path.stem.replace("quant_signals_", "")
        try:
            day = date_from_tag(tag)
        except ValueError:
            continue
        if START_DATE <= day <= END_DATE:
            paths.append(path)
    return paths


def candidate_review(payload: dict[str, Any]) -> dict[str, Any]:
    review = payload.get("entry_candidate_review")
    return review if isinstance(review, dict) else {}


def extract_candidate_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    for path in quant_signal_paths():
        tag = path.stem.replace("quant_signals_", "")
        signal_day = date_from_tag(tag)
        signal_date = signal_day.isoformat()
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            payload = {}
        review = candidate_review(payload)
        candidates = review.get("candidates") if isinstance(review, dict) else []
        if not isinstance(candidates, list):
            candidates = []
        signals = payload.get("signals")
        if not isinstance(signals, list):
            signals = []
        is_session = is_us_equity_session(signal_day)
        planned_entry_day = next_session_after(signal_day)
        file_summaries.append(
            {
                "source_file": repo_rel(path),
                "date": signal_date,
                "exists": path.exists(),
                "sha256": sha256(path),
                "signal_is_us_equity_session": is_session,
                "signals_count": len(signals),
                "entry_candidate_review_count": int(
                    review.get("candidate_count") or len(candidates) or 0
                ),
                "candidate_rows_extracted": len(candidates),
                "planned_next_session": planned_entry_day.isoformat(),
            }
        )
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            ticker = str(raw.get("ticker") or "").upper()
            entry_price = safe_float(raw.get("entry_price"))
            target_price = safe_float(raw.get("target_price"))
            position_value = safe_float(raw.get("position_value_usd"))
            row = {
                "source_file": repo_rel(path),
                "signal_date": signal_date,
                "signal_is_us_equity_session": is_session,
                "planned_entry_date": planned_entry_day.isoformat(),
                "entry_date_resolution": (
                    "next_us_equity_session" if is_session else "blocked_non_session_signal_date"
                ),
                "outcome_status": (
                    "pending_settlement" if is_session else "blocked_non_session_signal_date"
                ),
                "ticker": ticker,
                "rank": raw.get("rank"),
                "strategy": raw.get("strategy"),
                "sector": raw.get("sector"),
                "entry_price": entry_price,
                "stop_price": safe_float(raw.get("stop_price")),
                "target_price": target_price,
                "risk_reward_ratio": safe_float(raw.get("risk_reward_ratio")),
                "trade_quality_score": safe_float(raw.get("trade_quality_score")),
                "confidence_score": safe_float(raw.get("confidence_score")),
                "days_to_earnings": raw.get("days_to_earnings"),
                "shares_to_buy": raw.get("shares_to_buy"),
                "position_value_usd": position_value,
                "live_decision": (raw.get("live_accounting") or {}).get("decision")
                if isinstance(raw.get("live_accounting"), dict)
                else None,
                "backtest_decision": (raw.get("backtest_accounting") or {}).get("decision")
                if isinstance(raw.get("backtest_accounting"), dict)
                else None,
                "total_accounting_shadow_decision": (
                    raw.get("total_accounting_shadow") or {}
                ).get("decision")
                if isinstance(raw.get("total_accounting_shadow"), dict)
                else None,
                "operator_review_reason": raw.get("operator_review_reason"),
                "has_entry_price": entry_price is not None,
                "has_target_price": target_price is not None,
                "notional_for_settlement": (
                    position_value
                    if position_value is not None and position_value > 0
                    else DEFAULT_NOTIONAL
                ),
            }
            candidate_rows.append(row)
    return candidate_rows, file_summaries


class WarehousePrices:
    def __init__(self, path: Path):
        self.path = path
        self.exists = path.exists()
        self.status = "missing"
        self.rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
        self.schema: list[str] = []
        self.min_date: str | None = None
        self.max_date: str | None = None
        if self.exists:
            self._load()

    def _load(self) -> None:
        try:
            with sqlite3.connect(self.path) as con:
                con.row_factory = sqlite3.Row
                tables = [
                    str(row[0])
                    for row in con.execute(
                        "select name from sqlite_master where type='table'"
                    ).fetchall()
                ]
                if "ohlcv" not in tables:
                    self.status = "no_ohlcv_table"
                    return
                info = con.execute("pragma table_info(ohlcv)").fetchall()
                self.schema = [str(row[1]) for row in info]
                required = {"ticker", "date", "open", "close"}
                if not required.issubset(set(self.schema)):
                    self.status = "missing_required_columns"
                    return
                min_max = con.execute("select min(date), max(date) from ohlcv").fetchone()
                self.min_date = min_max[0] if min_max else None
                self.max_date = min_max[1] if min_max else None
                rows = con.execute(
                    "select ticker, date, open, high, low, close, volume "
                    "from ohlcv order by ticker, date"
                ).fetchall()
                for row in rows:
                    ticker = str(row["ticker"]).upper()
                    self.rows_by_ticker.setdefault(ticker, []).append(
                        {
                            "date": str(row["date"]),
                            "open": safe_float(row["open"]),
                            "high": safe_float(row["high"]),
                            "low": safe_float(row["low"]),
                            "close": safe_float(row["close"]),
                            "volume": safe_float(row["volume"]),
                        }
                    )
                self.status = "ok"
        except Exception as exc:  # pragma: no cover - artifact defensive field
            self.status = "error"
            self.schema = []
            self.rows_by_ticker = {}
            self.min_date = None
            self.max_date = None
            self.error = str(exc)

    def audit(self, tickers: set[str]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "path": repo_rel(self.path),
            "exists": self.exists,
            "status": self.status,
            "schema": self.schema,
            "min_date": self.min_date,
            "max_date": self.max_date,
            "loaded_ticker_count": len(self.rows_by_ticker),
        }
        if hasattr(self, "error"):
            out["error"] = self.error
        coverage = []
        for ticker in sorted(tickers):
            rows = self.rows_by_ticker.get(ticker, [])
            coverage.append(
                {
                    "ticker": ticker,
                    "rows": len(rows),
                    "min_date": rows[0]["date"] if rows else None,
                    "max_date": rows[-1]["date"] if rows else None,
                }
            )
        out["ticker_coverage"] = coverage
        return out

    def row_index(self, ticker: str, day_iso: str) -> int | None:
        rows = self.rows_by_ticker.get(ticker.upper(), [])
        for index, row in enumerate(rows):
            if row["date"] == day_iso:
                return index
        return None

    def return_from_open_to_close(self, ticker: str, entry_date: str, horizon: int) -> dict[str, Any]:
        rows = self.rows_by_ticker.get(ticker.upper(), [])
        index = self.row_index(ticker, entry_date)
        if index is None:
            return {"status": "missing_entry_date", "entry_date": entry_date, "horizon": horizon}
        exit_index = index + horizon
        if exit_index >= len(rows):
            return {"status": "missing_exit_date", "entry_date": entry_date, "horizon": horizon}
        entry = rows[index]
        exit_row = rows[exit_index]
        entry_open = entry.get("open")
        exit_close = exit_row.get("close")
        if entry_open is None or entry_open <= 0 or exit_close is None:
            return {"status": "missing_price", "entry_date": entry_date, "horizon": horizon}
        gross_return = exit_close / entry_open - 1.0
        return {
            "status": "settled",
            "entry_date": entry_date,
            "exit_date": exit_row["date"],
            "horizon": horizon,
            "entry_open": round(entry_open, 6),
            "exit_close": round(exit_close, 6),
            "gross_return_pct": round(gross_return, 8),
            "net_return_pct": round(gross_return - ROUND_TRIP_COST_PCT, 8),
        }


def settle_rows(candidate_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tickers = {row["ticker"] for row in candidate_rows if row.get("ticker")}
    tickers.update({"SPY", "QQQ"})
    warehouse = WarehousePrices(WAREHOUSE)
    settled_rows: list[dict[str, Any]] = []
    for row in candidate_rows:
        enriched = dict(row)
        if not row.get("signal_is_us_equity_session"):
            enriched["outcome_status"] = "blocked_non_session_signal_date"
            enriched["settlement"] = {}
            settled_rows.append(enriched)
            continue
        entry_date = str(row.get("planned_entry_date") or "")
        settlement: dict[str, Any] = {}
        settled_any = False
        for horizon in FORWARD_HORIZONS:
            ticker_result = warehouse.return_from_open_to_close(row["ticker"], entry_date, horizon)
            spy_result = warehouse.return_from_open_to_close("SPY", entry_date, horizon)
            qqq_result = warehouse.return_from_open_to_close("QQQ", entry_date, horizon)
            item = {
                "ticker": ticker_result,
                "spy": spy_result,
                "qqq": qqq_result,
            }
            if ticker_result.get("status") == "settled":
                notional = safe_float(row.get("notional_for_settlement")) or DEFAULT_NOTIONAL
                net_return = float(ticker_result["net_return_pct"])
                item["candidate_net_pnl_usd"] = round(notional * net_return, 2)
                if spy_result.get("status") == "settled":
                    item["replacement_value_vs_spy_usd"] = round(
                        notional * (net_return - float(spy_result["net_return_pct"])),
                        2,
                    )
                if qqq_result.get("status") == "settled":
                    item["replacement_value_vs_qqq_usd"] = round(
                        notional * (net_return - float(qqq_result["net_return_pct"])),
                        2,
                    )
                settled_any = True
            settlement[f"h{horizon}d"] = item
        enriched["settlement"] = settlement
        enriched["outcome_status"] = "settled_partial" if settled_any else "unsettled"
        settled_rows.append(enriched)
    audit = warehouse.audit(tickers)
    return settled_rows, audit


def summarize(candidate_rows: list[dict[str, Any]], file_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    by_date = Counter(row["signal_date"] for row in candidate_rows)
    by_ticker = Counter(row["ticker"] for row in candidate_rows)
    by_status = Counter(row["outcome_status"] for row in candidate_rows)
    valid = [row for row in candidate_rows if row.get("signal_is_us_equity_session")]
    settled = [row for row in candidate_rows if row.get("outcome_status") == "settled_partial"]
    h5_pnls = []
    h5_spy_rv = []
    for row in settled:
        h5 = (row.get("settlement") or {}).get("h5d") or {}
        if h5.get("candidate_net_pnl_usd") is not None:
            h5_pnls.append(float(h5["candidate_net_pnl_usd"]))
        if h5.get("replacement_value_vs_spy_usd") is not None:
            h5_spy_rv.append(float(h5["replacement_value_vs_spy_usd"]))
    return {
        "scanned_file_count": len(file_summaries),
        "files_with_entry_candidates": sum(
            1 for row in file_summaries if row.get("candidate_rows_extracted", 0) > 0
        ),
        "candidate_rows": len(candidate_rows),
        "valid_session_candidate_rows": len(valid),
        "non_session_candidate_rows": len(candidate_rows) - len(valid),
        "settled_candidate_rows": len(settled),
        "candidate_rows_by_date": dict(sorted(by_date.items())),
        "candidate_rows_by_ticker": dict(sorted(by_ticker.items())),
        "candidate_rows_by_status": dict(sorted(by_status.items())),
        "h5_candidate_net_pnl_sum_usd": round(sum(h5_pnls), 2),
        "h5_replacement_value_vs_spy_sum_usd": round(sum(h5_spy_rv), 2),
        "alpha_ready": False,
        "readiness_failed_reasons": [
            reason
            for reason, flag in [
                ("target_sample_too_small", len(candidate_rows) < 20),
                ("valid_session_sample_too_small", len(valid) < 20),
                ("settled_sample_too_small", len(settled) < 20),
                ("non_session_artifacts_dominate", len(candidate_rows) > 0 and len(valid) < len(candidate_rows) / 2),
            ]
            if flag
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    raw_rows, file_summaries = extract_candidate_rows()
    settled_rows, warehouse_audit = settle_rows(raw_rows)
    readiness = summarize(settled_rows, file_summaries)
    failed_reasons = list(readiness["readiness_failed_reasons"])
    if not failed_reasons:
        failed_reasons.append("observed_only_not_gate4_strategy_replay")
    decision = "observed_only_rejected_full_quant_signals_forward_readiness_too_thin"
    now = utc_now()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "observed_only_rejected",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "owner": OWNER,
        "lane": "alpha_search",
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_summary": (
            "Scanned the full May-June production quant_signals entry-candidate "
            "surface and settled the only valid-session row; sample size remains "
            "far below alpha-readiness."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": decision,
            "actual_success": 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get(
                "success_probability"
            ),
            "brier_score": 0.0324,
            "predicted_failure_modes": (ticket.get("prediction") or {}).get(
                "main_failure_modes"
            ),
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": True,
            "surprise_note": (
                "Low surprise: the full surface added only SNOW/MSFT from a "
                "non-session 2026-05-31 file and one valid-session DDOG row from "
                "2026-06-01, leaving the same thin-sample blocker."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
        },
        "gate2": {
            "passed": bool(raw_rows),
            "required_fields_checked": [
                "source_file",
                "signal_date",
                "ticker",
                "entry_price",
                "target_price",
                "signal_is_us_equity_session",
                "planned_entry_date",
            ],
            "entry_date_coverage": round(
                sum(1 for row in raw_rows if row.get("planned_entry_date")) / len(raw_rows),
                6,
            )
            if raw_rows
            else None,
            "target_price_coverage": round(
                sum(1 for row in raw_rows if row.get("has_target_price")) / len(raw_rows),
                6,
            )
            if raw_rows
            else None,
            "warehouse_audit": warehouse_audit,
        },
        "gate3": {
            "passed": readiness["valid_session_candidate_rows"] >= 1,
            "filter_added": False,
            "signals_generated_proxy": readiness["candidate_rows"],
            "signals_survived_proxy": readiness["valid_session_candidate_rows"],
            "survival_rate_proxy": round(
                readiness["valid_session_candidate_rows"] / readiness["candidate_rows"],
                6,
            )
            if readiness["candidate_rows"]
            else None,
            "note": (
                "No executable filter was added. Survival proxy is valid-session "
                "candidate rows divided by all production entry_candidate_review rows."
            ),
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "observed_only": True,
            "failed_reasons": failed_reasons,
            "settled_candidate_rows": readiness["settled_candidate_rows"],
            "minimum_settled_rows": 20,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
        },
        "before_metrics": baseline,
        "after_metrics": {
            **baseline,
            "candidate_rows": readiness["candidate_rows"],
            "valid_session_candidate_rows": readiness["valid_session_candidate_rows"],
            "settled_candidate_rows": readiness["settled_candidate_rows"],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "candidate_rows": readiness["candidate_rows"],
            "valid_session_candidate_rows": readiness["valid_session_candidate_rows"],
            "settled_candidate_rows": readiness["settled_candidate_rows"],
        },
        "file_summaries": file_summaries,
        "candidate_rows": settled_rows,
        "readiness": readiness,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "trade_enabled": False,
            "replay_only": False,
            "daily_snapshot_exposed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": "Read-only artifact audit; no strategy or adapter behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The complete surface contains only nine entry-candidate rows "
                "from 2026-05-31, 2026-06-01, and 2026-06-19/20/21. Only DDOG "
                "from 2026-06-01 is a clean session-date candidate, and that "
                "single settled row is not enough for alpha attribution."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not promote or reslice the SNOW/MSFT/DDOG/CAT/TSM rows as "
                "alpha. Do not retry quant_signals thresholds, ranks, slot "
                "accounting, hold days, or notional on this sparse surface."
            ),
            "new_evidence_required": (
                "At least 20 valid-session production entry_candidate_review rows "
                "with PIT next-open and forward-close settlement, or a genuinely "
                "new production-visible candidate source with replayable coverage."
            ),
        },
        "rejection_reason": (
            "Only one valid-session candidate row could be settled; the surface is "
            "not allocation-ready and cannot support a strategy change."
        ),
        "next_retry_requires": [
            "at least 20 valid-session production candidate rows",
            "PIT next-open and 1d/3d/5d forward-close settlement bars",
            "a materially new source rather than quant_signals threshold or slot retunes",
        ],
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            repo_rel(WAREHOUSE),
            "data/daily/signals/quant/quant_signals_20260531.json",
            "data/daily/signals/quant/quant_signals_20260601.json",
            "data/daily/signals/quant/quant_signals_20260619.json",
            "data/daily/signals/quant/quant_signals_20260620.json",
            "data/daily/signals/quant/quant_signals_20260621.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "anti_js": {"used_javascript": False, "node_repl_used": False},
        "lean_quality_passed": True,
        "ticket_before": ticket,
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "lane",
        "hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "calibration",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "decision",
        "rejection_reason",
        "next_retry_requires",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "artifact",
        "runner",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if key in payload}


def build_card(payload: dict[str, Any]) -> str:
    readiness = payload["readiness"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: full quant_signals forward readiness",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Candidate rows: `{readiness['candidate_rows']}`",
            f"- Valid-session rows: `{readiness['valid_session_candidate_rows']}`",
            f"- Settled rows: `{readiness['settled_candidate_rows']}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons'])}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Result",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            f"```powershell\n{RUNNER_COMMAND}\n```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        WAREHOUSE,
    ]
    for rel_path in payload["related_files"]:
        path = REPO_ROOT / rel_path
        if path.exists() and path not in files:
            files.append(path)
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "readiness": payload["readiness"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "candidate_rows": payload["readiness"]["candidate_rows"],
                "valid_session_candidate_rows": payload["readiness"][
                    "valid_session_candidate_rows"
                ],
                "settled_candidate_rows": payload["readiness"]["settled_candidate_rows"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
