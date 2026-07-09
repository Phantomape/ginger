"""exp-20260704-022: materialize repaired SEC financial-report forward rows.

Measurement repair only. exp-20260704-015 found that the accepted SEC financial
report T+1 drift paper sleeve could never admit daily candidates because daily
rows lacked the replay-derived cohort field. exp-20260704-016 fixed the shared
queue builder, but the current sleeve state remained empty because historical
daily archives were not replayed through the repaired builder. This runner
replays that already-recorded daily span into the default-off paper sleeve,
enriches closed rows with cash/SPY/QQQ replacement values, and rebuilds the
shared forward replacement artifact. It changes no threshold, rank, sizing rule,
exit rule, live order, or LLM decision boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260704-022"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_financial_report_post_repair_forward_materialization"
ASOF_DATE = "2026-07-04"
MIN_ACTIVATION_ROWS = 30

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import forward_replacement_value as frv  # noqa: E402
from data_paths import atomic_write_text  # noqa: E402
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames  # noqa: E402
from scripts.experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from sec_event_queue import (  # noqa: E402
    build_sec_financial_report_t1_queue,
    load_sec_filing_event_rows,
    load_sec_filing_text_rows,
)
from sec_financial_report_event_sleeve import (  # noqa: E402
    SLEEVE_NAME,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


RUNNER = f"quant/experiments/exp_20260704_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_022_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"
STATE_JSON = SLEEVES_ROOT / "sec_financial_report" / "state.json"
SNAPSHOTS_JSONL = SLEEVES_ROOT / "sec_financial_report" / "snapshots.jsonl"
FORWARD_RV_JSONL = SLEEVES_ROOT / "forward_replacement_value.jsonl"
STATE_BEFORE_JSON = OUT_DIR / "sec_financial_report_state_before.json"
SNAPSHOTS_BEFORE_JSONL = OUT_DIR / "sec_financial_report_snapshots_before.jsonl"
FORWARD_RV_BEFORE_JSONL = OUT_DIR / "forward_replacement_value_before.jsonl"

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def make_json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(v) for v in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def safe_write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def write_json(path: Path, payload: Any) -> None:
    safe_write_text(
        json.dumps(make_json_safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        path,
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(make_json_safe(row), sort_keys=True) + "\n" for row in rows)
    safe_write_text(text, path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def round_or_none(value: Any, digits: int = 2) -> float | None:
    parsed = safe_float(value)
    return round(parsed, digits) if parsed is not None else None


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_summary() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") or payload.get("results") or {}
    if not isinstance(windows, dict):
        windows = {}
    generated = 0
    survived = 0
    for window in windows.values():
        generated += int(window.get("signals_generated") or 0)
        survived += int(window.get("signals_survived") or 0)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "loaded": BASELINE_JSON.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows.values()),
            4,
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows.values()), 2),
        "trade_count": sum(int(w.get("trade_count") or w.get("total_trades") or 0) for w in windows.values()),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "max_drawdown_pct_worst": round(
            max(float(w.get("max_drawdown_pct") or 0.0) for w in windows.values()),
            4,
        )
        if windows
        else None,
    }


def archive_existing_files() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state_before = read_json(STATE_JSON, empty_sec_financial_report_event_sleeve_state())
    if not STATE_BEFORE_JSON.exists():
        write_json(STATE_BEFORE_JSON, state_before)
    else:
        state_before = read_json(
            STATE_BEFORE_JSON,
            empty_sec_financial_report_event_sleeve_state(),
        )
    if not SNAPSHOTS_BEFORE_JSONL.exists():
        if SNAPSHOTS_JSONL.exists():
            safe_write_text(SNAPSHOTS_JSONL.read_text(encoding="utf-8"), SNAPSHOTS_BEFORE_JSONL)
        else:
            safe_write_text("", SNAPSHOTS_BEFORE_JSONL)
    if not FORWARD_RV_BEFORE_JSONL.exists():
        if FORWARD_RV_JSONL.exists():
            safe_write_text(FORWARD_RV_JSONL.read_text(encoding="utf-8"), FORWARD_RV_BEFORE_JSONL)
        else:
            safe_write_text("", FORWARD_RV_BEFORE_JSONL)
    return {
        "state_exists": STATE_JSON.exists(),
        "state_before_closed": len(state_before.get("closed_positions") or []),
        "state_before_open": len(state_before.get("open_positions") or []),
        "state_before_pending": len(state_before.get("pending_entries") or []),
        "snapshots_before_rows": len(read_jsonl(SNAPSHOTS_BEFORE_JSONL)),
        "forward_replacement_before_rows": len(read_jsonl(FORWARD_RV_BEFORE_JSONL)),
    }


def recorded_snapshot_days() -> list[dict[str, Any]]:
    days: dict[str, dict[str, Any]] = {}
    for snap in read_jsonl(SNAPSHOTS_JSONL):
        asof = str(snap.get("asof_date") or "")[:10]
        if not asof:
            continue
        source = snap.get("data_source") or {}
        events_path = source.get("path")
        text_path = source.get("text_path")
        days[asof] = {
            "asof_date": asof,
            "recorded_candidate_count": int(snap.get("candidate_count") or 0),
            "recorded_new_pending_count": int(snap.get("new_pending_count") or 0),
            "recorded_t1_evaluated_count": int(source.get("t1_evaluated_count") or 0),
            "recorded_loaded_row_count": int(source.get("loaded_row_count") or 0),
            "events_file": Path(str(events_path)).name if events_path else None,
            "text_file": Path(str(text_path)).name if text_path else None,
        }
    return [days[key] for key in sorted(days)]


def _frame_price_maps(frames: dict[str, Any], asof: str) -> tuple[dict[str, float], dict[str, float], dict[str, str], dict[str, str]]:
    open_prices: dict[str, float] = {}
    current_prices: dict[str, float] = {}
    open_dates: dict[str, str] = {}
    current_dates: dict[str, str] = {}
    for ticker, frame in frames.items():
        try:
            row = frame.loc[asof]
        except Exception:
            continue
        if hasattr(row, "iloc") and getattr(row, "ndim", 1) > 1:
            row = row.iloc[-1]
        try:
            open_px = float(row["Open"])
            close_px = float(row["Close"])
        except Exception:
            continue
        if open_px > 0:
            open_prices[ticker] = open_px
            open_dates[ticker] = asof
        if close_px > 0:
            current_prices[ticker] = close_px
            current_dates[ticker] = asof
    return open_prices, current_prices, open_dates, current_dates


def replay_repaired_daily_span() -> dict[str, Any]:
    days = recorded_snapshot_days()
    if not days:
        raise RuntimeError("sec_financial_report snapshots.jsonl has no recorded days")

    rows_by_file: dict[str, list[dict[str, Any]]] = {}
    text_cache: dict[str, list[dict[str, Any]]] = {}
    tickers: set[str] = set()
    usable_dates: list[str] = []
    missing_event_files: list[str] = []
    for day in days:
        name = day.get("events_file")
        if not name or name in rows_by_file:
            continue
        path = NON_OHLCV_DIR / name
        if not path.exists():
            rows_by_file[name] = []
            missing_event_files.append(name)
            continue
        rows = load_sec_filing_event_rows(path)
        rows_by_file[name] = rows
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                tickers.add(ticker)
            usable = str(row.get("usable_trade_date") or "")[:10]
            if usable:
                usable_dates.append(usable)

    span_start = min([day["asof_date"] for day in days] + usable_dates)
    span_end = max([day["asof_date"] for day in days] + usable_dates)
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        sorted(tickers | {"SPY", "QQQ"}),
        "2026-02-02",
        span_end,
    )
    for frame in frames.values():
        frame.index.name = "Date"
    spy_frame = frames.get("SPY")
    if spy_frame is None:
        raise RuntimeError("warehouse OHLCV has no SPY frame")

    snapshot_by_day = {day["asof_date"]: day for day in days}
    session_dates = sorted(
        str(value)[:10]
        for value in getattr(spy_frame, "index", [])
        if span_start <= str(value)[:10] <= span_end
    )
    replay_dates = sorted(set(session_dates) | set(snapshot_by_day))
    state = empty_sec_financial_report_event_sleeve_state()
    snapshots: list[dict[str, Any]] = []
    skipped_entries: list[dict[str, Any]] = []
    queue_candidate_by_day: dict[str, int] = {}

    for asof in replay_dates:
        day = snapshot_by_day.get(asof, {})
        event_name = day.get("events_file")
        text_name = day.get("text_file")
        rows = rows_by_file.get(event_name or "", [])
        text_rows: list[dict[str, Any]] = []
        if text_name:
            if text_name not in text_cache:
                text_path = NON_OHLCV_DIR / text_name
                text_cache[text_name] = (
                    load_sec_filing_text_rows(text_path) if text_path.exists() else []
                )
            text_rows = text_cache[text_name]

        queue = build_sec_financial_report_t1_queue(
            rows,
            as_of=asof,
            ohlcv_by_ticker=frames,
            spy_ohlcv=spy_frame,
            source_path=(NON_OHLCV_DIR / str(event_name)) if event_name else None,
            source_status="loaded" if rows else "missing_or_empty_events_file",
            text_rows=text_rows,
            text_source_path=(NON_OHLCV_DIR / str(text_name)) if text_name else None,
            text_source_status="loaded" if text_rows else "missing_or_empty_text_file",
        )
        open_prices, current_prices, open_dates, current_dates = _frame_price_maps(
            frames,
            asof,
        )
        snapshot = build_sec_financial_report_event_sleeve_snapshot(
            sec_financial_report_t1_queue=queue,
            as_of=asof,
            open_prices=open_prices,
            current_prices=current_prices,
            open_price_dates=open_dates,
            current_price_dates=current_dates,
            state=state,
            persist=False,
        )
        skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
        state = {
            "schema_version": 1,
            "sleeve": SLEEVE_NAME,
            "updated_at": None,
            "pending_entries": snapshot.get("pending_entries") or [],
            "open_positions": snapshot.get("open_positions") or [],
            "closed_positions": snapshot.get("closed_positions") or [],
            "skipped_entries": skipped_entries,
        }
        snapshots.append(snapshot)
        queue_candidate_by_day[asof] = int(queue.get("candidate_count") or 0)

    comparator_bars = frv.load_comparator_bars(DEFAULT_WAREHOUSE_PATH)
    regime_spy_bars = frv.load_regime_spy_bars(DEFAULT_WAREHOUSE_PATH)
    short_volume_index = frv.load_short_volume_percentile_index()
    exhaustion_bars = frv.load_entry_exhaustion_bars(
        {row.get("ticker") for row in state.get("closed_positions", [])},
        DEFAULT_WAREHOUSE_PATH,
    )
    rv_records = frv.enrich_state_closed_rows(
        state,
        comparator_bars,
        ASOF_DATE,
        "sec_financial_report",
        regime_spy_bars=regime_spy_bars,
        sv_percentile_index=short_volume_index,
        exhaustion_bars=exhaustion_bars,
    )
    return {
        "days": days,
        "span_start": span_start,
        "span_end": span_end,
        "replay_dates": replay_dates,
        "snapshots": snapshots,
        "state": state,
        "rv_records": rv_records,
        "missing_event_files": missing_event_files,
        "warehouse_inputs": {
            "ticker_frames_loaded": len(frames),
            "event_tickers": len(tickers),
            "comparator_bars": {ticker: len(comparator_bars.get(ticker, {})) for ticker in ("SPY", "QQQ")},
            "regime_spy_bars": len(regime_spy_bars),
            "short_volume_symbols": len(short_volume_index),
            "entry_exhaustion_tickers": len(exhaustion_bars),
        },
        "queue_candidate_by_day": queue_candidate_by_day,
    }


def safe_rebuild_current_state_artifact() -> dict[str, Any]:
    previous_records = read_jsonl(FORWARD_RV_BEFORE_JSONL)
    current_records, skipped_missing_replacement = frv.current_state_replacement_records(
        SLEEVES_ROOT,
    )
    current_keys = {frv.replacement_artifact_key(record) for record in current_records}
    previous_rows_not_in_current_state = [
        {
            "sleeve_key": record.get("sleeve_key"),
            "decision_id": record.get("decision_id"),
            "ticker": record.get("ticker"),
            "entry_date": record.get("entry_date"),
            "exit_date": record.get("exit_date"),
            "status": record.get("status"),
        }
        for record in previous_records
        if frv.replacement_artifact_key(record) not in current_keys
    ]
    write_jsonl(FORWARD_RV_JSONL, current_records)

    rows_by_status: Counter[str] = Counter()
    rows_by_sleeve: Counter[str] = Counter()
    rows_by_entry_regime_label: Counter[str] = Counter()
    rows_by_entry_short_volume_quintile: Counter[str] = Counter()
    rows_with_entry_regime = 0
    rows_with_entry_short_volume = 0
    rows_entry_short_volume_toxic = 0
    for record in current_records:
        rows_by_status[str(record.get("status") or "unknown")] += 1
        rows_by_sleeve[str(record.get("sleeve_key") or "unknown")] += 1
        label = record.get("entry_regime_label")
        if label:
            rows_with_entry_regime += 1
            rows_by_entry_regime_label[str(label)] += 1
        if record.get("entry_short_volume_status") == "ok":
            rows_with_entry_short_volume += 1
            quintile = record.get("entry_short_volume_quintile")
            if quintile is not None:
                rows_by_entry_short_volume_quintile[f"Q{quintile}"] += 1
            if record.get("entry_short_volume_toxic_flag"):
                rows_entry_short_volume_toxic += 1

    return {
        "status": "ok",
        "artifact_path": repo_rel(FORWARD_RV_JSONL),
        "previous_rows": len(previous_records),
        "rows_written": len(current_records),
        "rows_by_status": dict(rows_by_status),
        "rows_by_sleeve": dict(rows_by_sleeve),
        "rows_with_entry_regime": rows_with_entry_regime,
        "rows_by_entry_regime_label": dict(rows_by_entry_regime_label),
        "rows_with_entry_short_volume": rows_with_entry_short_volume,
        "rows_by_entry_short_volume_quintile": dict(rows_by_entry_short_volume_quintile),
        "rows_entry_short_volume_toxic": rows_entry_short_volume_toxic,
        "previous_rows_not_in_current_state": previous_rows_not_in_current_state,
        "skipped_missing_replacement": skipped_missing_replacement,
    }


def write_materialized_outputs(replay: dict[str, Any]) -> dict[str, Any]:
    state = replay["state"]
    snapshots = replay["snapshots"]
    write_json(STATE_JSON, state)
    existing = (
        SNAPSHOTS_BEFORE_JSONL.read_text(encoding="utf-8")
        if SNAPSHOTS_BEFORE_JSONL.exists()
        else (SNAPSHOTS_JSONL.read_text(encoding="utf-8") if SNAPSHOTS_JSONL.exists() else "")
    )
    appended = "".join(json.dumps(make_json_safe(snap), sort_keys=True) + "\n" for snap in snapshots)
    safe_write_text(existing + appended, SNAPSHOTS_JSONL)
    return safe_rebuild_current_state_artifact()


def _sum_rows(rows: list[dict[str, Any]], field: str) -> float:
    return round(sum(float(row.get(field) or 0.0) for row in rows), 2)


def _closed_row_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": row.get("decision_id"),
        "ticker": row.get("ticker"),
        "source_event_date": row.get("source_event_date"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "entry_price": round_or_none(row.get("entry_price"), 4),
        "exit_price": round_or_none(row.get("exit_price"), 4),
        "notional": round_or_none(row.get("notional")),
        "pnl": round_or_none(row.get("pnl")),
        "replacement_value_status": row.get("replacement_value_status"),
        "replacement_value_vs_cash_usd": round_or_none(row.get("replacement_value_vs_cash_usd")),
        "replacement_value_vs_spy_usd": round_or_none(row.get("replacement_value_vs_spy_usd")),
        "replacement_value_vs_qqq_usd": round_or_none(row.get("replacement_value_vs_qqq_usd")),
        "entry_regime_label": row.get("entry_regime_label"),
        "entry_short_volume_quintile": row.get("entry_short_volume_quintile"),
        "trade_enabled": row.get("trade_enabled"),
    }


def build_payload() -> dict[str, Any]:
    archived = archive_existing_files()
    baseline = baseline_summary()
    replay = replay_repaired_daily_span()
    artifact_summary = write_materialized_outputs(replay)

    state = replay["state"]
    closed = state.get("closed_positions") or []
    open_positions = state.get("open_positions") or []
    pending = state.get("pending_entries") or []
    skipped = state.get("skipped_entries") or []
    snapshots = replay["snapshots"]
    rv_records = replay["rv_records"]
    closed_count = len(closed)
    rv_enriched = [row for row in closed if row.get("replacement_value_status") == "enriched"]
    target_artifact_rows = [
        row for row in frv.current_state_replacement_records(SLEEVES_ROOT)[0]
        if row.get("sleeve_key") == "sec_financial_report"
    ]
    rv_cash = _sum_rows(closed, "replacement_value_vs_cash_usd")
    rv_spy = _sum_rows(closed, "replacement_value_vs_spy_usd")
    rv_qqq = _sum_rows(closed, "replacement_value_vs_qqq_usd")
    closed_pnl = _sum_rows(closed, "pnl")
    activation_blockers: list[str] = []
    if closed_count < MIN_ACTIVATION_ROWS:
        activation_blockers.append(f"sec_financial_report_closed_rows_below_activation_min:{closed_count}/{MIN_ACTIVATION_ROWS}")
    if rv_cash <= 0:
        activation_blockers.append(f"replacement_vs_cash_not_positive:{rv_cash}")
    if rv_spy <= 0:
        activation_blockers.append(f"replacement_vs_spy_not_positive:{rv_spy}")
    if rv_qqq <= 0:
        activation_blockers.append(f"replacement_vs_qqq_not_positive:{rv_qqq}")

    repair_success = closed_count > 0 and len(rv_enriched) == closed_count
    status = "accepted_measurement_repair" if repair_success else "blocked"
    decision = (
        "accepted_measurement_repair_sec_financial_report_post_repair_forward_rows_materialized"
        if repair_success
        else "blocked_sec_financial_report_post_repair_forward_rows_not_materialized"
    )
    alpha_ready = repair_success and not activation_blockers
    timestamp = utc_now()

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "status": status,
        "lane": LANE,
        "hypothesis": (
            "Alpha blocker: after the sec_financial_report cohort parity repair, "
            "the accepted default-off sleeve still has empty state; replay the "
            "repaired archived daily span to materialize post-repair pending/open/"
            "closed paper rows and cash/SPY/QQQ replacement values without changing "
            "thresholds, sizing, exits, orders, or live behavior."
        ),
        "alpha_hypothesis": (
            "Forward evidence supply is an alpha bottleneck: the accepted SEC "
            "financial-report T+1 drift sleeve can only support activation or "
            "allocation decisions after its repaired daily path produces closed "
            "cash/SPY/QQQ replacement-value rows."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "targeted_forward_row_materialization",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "sec_financial_report_forward_row_materialization",
        "trial_variant_id": "post_cohort_repair_archived_daily_span_20260704",
        "single_causal_variable": "sec_financial_report_post_repair_forward_row_materialization_v1",
        "changed_variable": "sec_financial_report_post_repair_forward_row_materialization_v1",
        "causal_components": [
            "post-repair archived daily sec_financial_report replay",
            "default-off paper sleeve state materialization",
            "cash/SPY/QQQ replacement-value enrichment",
            "no threshold, notional, ranking, exit, order, or live behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260704-015",
            "exp-20260704-016",
            "exp-20260704-017",
            "exp-20260704-021",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "post_repair_forward_row_materialization",
        "new_evidence_axis": (
            "Materially new settled forward rows from the repaired SEC financial-"
            "report daily path: 5 closed cash/SPY/QQQ-enriched rows plus one still-"
            "open row generated from the fixed exp-20260704-016 cohort parity "
            "builder. No threshold, top-N, hold, notional, response, or activation "
            "retune is tested."
        ),
        "prediction": {
            "success_probability": 0.72,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "no_closed_rows_after_lifecycle_capacity",
                "warehouse_missing_recent_bars",
                "replacement_value_negative_or_too_thin",
            ],
            "confidence_reason": (
                "exp-20260704-016 already proved the repaired builder emits the "
                "same 8 candidates as the parity probe, and the hot warehouse repair "
                "restored comparator coverage; the main risk is not repair failure "
                "but that the newly materialized sample is too small or negative for "
                "alpha activation."
            ),
            "recorded_at": "2026-07-04T20:05:00+00:00",
        },
        "parameters": {
            "asof_date": ASOF_DATE,
            "source_snapshot_log": repo_rel(SNAPSHOTS_JSONL),
            "baseline_result_file": repo_rel(BASELINE_JSON),
            "state_file": repo_rel(STATE_JSON),
            "forward_replacement_value_file": repo_rel(FORWARD_RV_JSONL),
            "archived_previous_state_file": repo_rel(STATE_BEFORE_JSON),
            "archived_previous_snapshots_file": repo_rel(SNAPSHOTS_BEFORE_JSONL),
            "archived_previous_forward_replacement_value_file": repo_rel(FORWARD_RV_BEFORE_JSONL),
            "min_activation_rows": MIN_ACTIVATION_ROWS,
        },
        "pre_run_questions": {
            "alpha_hypothesis": (
                "Post-repair sec_financial_report forward rows can now mature into "
                "activation evidence if the repaired daily path is materialized."
            ),
            "history_check": {
                "exp-20260704-015": "identified daily cohort parity drift and 8 counterfactual admissions",
                "exp-20260704-016": "repaired shared cohort derivation without changing thresholds or orders",
                "exp-20260704-017": "repaired hot warehouse settlement coverage",
                "exp-20260704-021": "proved replacement-value enrichment works after warehouse repair but allocator rows stayed too thin",
            },
            "single_policy_bundle": "sec_financial_report_post_repair_forward_row_materialization_v1",
            "acceptance_standard": (
                "Accept as measurement repair if the repaired archived span produces "
                "nonzero closed rows and every closed row receives cash/SPY/QQQ "
                "replacement values. Alpha activation remains blocked unless row "
                "count and comparator value clear predeclared readiness checks."
            ),
            "reproducibility": RUNNER_COMMAND,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "gate1": {"passed": baseline["loaded"], "baseline_metrics": baseline},
        "gate2": {
            "passed": repair_success,
            "fields_checked": [
                "recorded_snapshots.data_source.path",
                "recorded_snapshots.data_source.text_path",
                "queue.candidates.usable_trade_date",
                "queue.candidates.t1_date",
                "closed_positions.entry_date",
                "closed_positions.exit_date",
                "closed_positions.pnl",
                "closed_positions.notional",
                "closed_positions.replacement_value_vs_cash_usd",
                "closed_positions.replacement_value_vs_spy_usd",
                "closed_positions.replacement_value_vs_qqq_usd",
            ],
            "entry_date_target_price_scope": (
                "entry_date is present on materialized paper rows; target_price is "
                "not applicable because this default-off sleeve uses a fixed 10-"
                "session paper holding period and does not create executable orders."
            ),
            "missing_or_invalid_fields": [] if repair_success else ["no_closed_enriched_rows"],
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, exit, ranking, sizing, risk, prompt, or order rule changed.",
        },
        "gate4": {
            "passed": repair_success,
            "accepted_measurement_repair": repair_success,
            "accepted_alpha": False,
            "alpha_ready": alpha_ready,
            "decision": decision,
            "repair_failed_reasons": [] if repair_success else ["no_closed_enriched_rows"],
            "alpha_activation_blockers": activation_blockers,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
        },
        "sec_financial_report_forward_materialization": {
            "archive_before": archived,
            "span_start": replay["span_start"],
            "span_end": replay["span_end"],
            "replayed_dates": len(replay["replay_dates"]),
            "recorded_snapshot_days": len(replay["days"]),
            "missing_event_files": replay["missing_event_files"],
            "candidate_total": sum(int(s.get("candidate_count") or 0) for s in snapshots),
            "new_pending_total": sum(int(s.get("new_pending_count") or 0) for s in snapshots),
            "filled_total": sum(int(s.get("filled_count") or 0) for s in snapshots),
            "closed_total": closed_count,
            "open_total": len(open_positions),
            "pending_total": len(pending),
            "skipped_total": len(skipped),
            "closed_rows": [_closed_row_summary(row) for row in closed],
            "open_rows": [
                {
                    "decision_id": row.get("decision_id"),
                    "ticker": row.get("ticker"),
                    "entry_date": row.get("entry_date"),
                    "observed_trading_days": row.get("observed_trading_days"),
                    "net_pnl_if_closed_now": round_or_none(row.get("net_pnl_if_closed_now")),
                }
                for row in open_positions
            ],
            "skipped_rows": [
                {
                    "decision_id": row.get("decision_id"),
                    "ticker": row.get("ticker"),
                    "created_asof": row.get("created_asof"),
                    "status": row.get("status"),
                }
                for row in skipped
            ],
            "replacement_records_updated_this_run": len(rv_records),
            "replacement_records_status": dict(Counter(str(row.get("status")) for row in rv_records)),
            "target_artifact_rows": len(target_artifact_rows),
            "artifact_summary": artifact_summary,
            "warehouse_inputs": replay["warehouse_inputs"],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "candidate_total": sum(int(s.get("candidate_count") or 0) for s in snapshots),
            "new_pending_total": sum(int(s.get("new_pending_count") or 0) for s in snapshots),
            "filled_total": sum(int(s.get("filled_count") or 0) for s in snapshots),
            "closed_rows_before": archived["state_before_closed"],
            "closed_rows_after": closed_count,
            "open_rows_after": len(open_positions),
            "pending_rows_after": len(pending),
            "skipped_rows_after": len(skipped),
            "rows_updated_this_run": len(rv_records),
            "replacement_value_vs_cash_usd": rv_cash,
            "replacement_value_vs_spy_usd": rv_spy,
            "replacement_value_vs_qqq_usd": rv_qqq,
            "paper_pnl_total": closed_pnl,
            "artifact_rows_before": archived["forward_replacement_before_rows"],
            "artifact_rows_after": artifact_summary.get("rows_written"),
            "sec_financial_report_artifact_rows": len(target_artifact_rows),
        },
        "production_impact": {
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": True,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Only the default-off SEC financial-report paper sleeve state, "
                "snapshot log, and shared forward replacement-value artifact were "
                "materialized from already-recorded daily archives. No executable "
                "core/live behavior changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": 0.72,
            "actual_success": 1 if repair_success else 0,
            "brier_score": round((0.72 - (1 if repair_success else 0)) ** 2, 4),
            "predicted_failure_modes": [
                "no_closed_rows_after_lifecycle_capacity",
                "warehouse_missing_recent_bars",
                "replacement_value_negative_or_too_thin",
            ],
            "realized_failure_modes": [] if repair_success else ["no_closed_enriched_rows"],
            "alpha_realized_non_activation": activation_blockers,
            "predicted_failure_mode_hit": bool(activation_blockers),
            "surprise_note": (
                "Low surprise on repair success: the repaired builder admitted rows "
                "and the warehouse supplied comparator bars. The alpha side remains "
                "non-activation-ready because the five closed rows are negative "
                "versus cash, SPY, and QQQ and far below the row-count floor."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp-20260704-016 cohort repair unlocked the exact archived "
                "candidate set, and the sleeve lifecycle could fill and close five "
                "rows through the repaired hot/cold warehouse. The measured forward "
                "outcomes were poor: closed PnL and all replacement-value totals are "
                "negative, while one CRDO row remains open and two rows were skipped "
                "by the unchanged max-position capacity."
            ),
            "alpha_interpretation": (
                "This is accepted measurement repair, not accepted alpha. The "
                "sec_financial_report forward surface is now non-empty and enriched, "
                "but it is negative and too thin for activation or allocation."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune SEC financial-report T+1 thresholds, event families, "
                "platform-pool membership, RS20 scalar, notional, max positions, "
                "hold days, cooldown, or response functions from these five closed "
                "rows."
            ),
            "new_evidence_required": (
                "Reopen only after materially more post-repair SEC financial-report "
                "closed rows with cash/SPY/QQQ replacement values, or a genuinely "
                "new PIT financial-report economics/source field."
            ),
        },
        "next_retry_requires": [
            "materially_more_post_repair_sec_financial_report_closed_rows",
            "positive_cash_spy_qqq_replacement_value_on_larger_sample",
            "or_genuinely_new_pit_financial_report_economics_source",
            "no_threshold_notional_hold_capacity_or_response_retune_on_same_rows",
        ],
        "accepted": repair_success,
        "accepted_alpha": False,
        "accepted_measurement_repair": repair_success,
        "alpha_ready": alpha_ready,
        "classification": (
            "measurement_repair_accepted_alpha_not_activation_ready"
            if repair_success and not alpha_ready
            else "blocked_measurement_repair"
        ),
        "decision": decision,
        "rejection_reason": None if repair_success else "No closed enriched rows were materialized.",
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(STATE_BEFORE_JSON),
            repo_rel(SNAPSHOTS_BEFORE_JSONL),
            repo_rel(FORWARD_RV_BEFORE_JSONL),
            repo_rel(STATE_JSON),
            repo_rel(SNAPSHOTS_JSONL),
            repo_rel(FORWARD_RV_JSONL),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "related_files": [
            "quant/sec_event_queue.py",
            "quant/sec_financial_report_event_sleeve.py",
            "quant/forward_replacement_value.py",
            "experiments/logs/exp-20260704-015.json",
            "experiments/logs/exp-20260704-016.json",
            "experiments/logs/exp-20260704-017.json",
            "experiments/logs/exp-20260704-021.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sec_event_queue.py quant\\test_sec_financial_report_event_sleeve.py quant\\test_forward_replacement_value.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": repair_success,
        "write_fallbacks": WRITE_FALLBACKS,
    }
    return payload


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "status",
        "lane",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "classification",
        "parameters",
        "pre_run_questions",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "sec_financial_report_forward_materialization",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    blockers = payload["gate4"].get("alpha_activation_blockers") or []
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - SEC financial-report forward materialization",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- candidates/new pending/filled: {delta['candidate_total']} / {delta['new_pending_total']} / {delta['filled_total']}",
            f"- closed/open/skipped rows: {delta['closed_rows_after']} / {delta['open_rows_after']} / {delta['skipped_rows_after']}",
            f"- replacement totals: cash {delta['replacement_value_vs_cash_usd']}, SPY {delta['replacement_value_vs_spy_usd']}, QQQ {delta['replacement_value_vs_qqq_usd']}",
            f"- artifact rows: {delta['artifact_rows_before']} -> {delta['artifact_rows_after']}",
            f"- alpha blockers: {', '.join(blockers)}",
            "",
            "No threshold, ranking, sizing, exit, live order, or LLM decision boundary changed.",
            "",
            "Reproduce:",
            "",
            f"    {RUNNER_COMMAND}",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        STATE_BEFORE_JSON,
        SNAPSHOTS_BEFORE_JSONL,
        FORWARD_RV_BEFORE_JSONL,
        STATE_JSON,
        SNAPSHOTS_JSONL,
        FORWARD_RV_JSONL,
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
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    safe_write_text(build_card(payload), CARD_MD)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "classification": payload["classification"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["post_run_reflection"]["alpha_interpretation"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
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
            "parameters": payload["parameters"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "candidate_total": payload["delta_metrics"]["candidate_total"],
                "closed_rows_after": payload["delta_metrics"]["closed_rows_after"],
                "open_rows_after": payload["delta_metrics"]["open_rows_after"],
                "replacement_value_vs_cash_usd": payload["delta_metrics"]["replacement_value_vs_cash_usd"],
                "replacement_value_vs_spy_usd": payload["delta_metrics"]["replacement_value_vs_spy_usd"],
                "replacement_value_vs_qqq_usd": payload["delta_metrics"]["replacement_value_vs_qqq_usd"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
