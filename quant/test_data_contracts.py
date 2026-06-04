from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STANDARD_WINDOWS = {"late_strong", "mid_weak", "old_thin"}
WINDOW_METRICS = {
    "expected_value_score",
    "max_drawdown_pct",
    "sharpe_daily",
    "signals_generated",
    "signals_survived",
    "strategy_total_return_pct",
    "survival_rate",
    "total_pnl",
    "trade_count",
}


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} is not valid JSON: {exc}") from exc
    assert isinstance(payload, dict), f"{path} must contain a JSON object"
    return payload


def _jsonl_sample(path: Path, *, limit: int) -> list[tuple[int, dict[str, Any]]]:
    assert path.exists(), f"missing required data file: {path}"
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise AssertionError(f"{path}:{line_no} is not valid JSONL: {exc}") from exc
            assert isinstance(row, dict), f"{path}:{line_no} must be a JSON object"
            rows.append((line_no, row))
            if len(rows) >= limit:
                break
    assert rows, f"{path} must contain at least one JSONL row"
    return rows


def _as_date(value: Any) -> date:
    text = str(value or "")[:10]
    assert text, f"missing date value: {value!r}"
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise AssertionError(f"invalid date value: {value!r}") from exc


def _accepted_date(value: Any) -> date:
    text = str(value or "")
    assert text, "missing accepted_at"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise AssertionError(f"invalid accepted_at value: {value!r}") from exc


def test_form4_transaction_jsonl_sample_has_required_pit_contract() -> None:
    path = ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
    rows = _jsonl_sample(path, limit=500)
    required = {
        "ticker",
        "accession_number",
        "accepted_at",
        "transaction_date",
        "usable_trade_date",
        "pit_safe_flag",
        "open_market_purchase_flag",
        "transaction_value",
        "owner_name",
        "issuer_name",
        "archive_url",
    }
    pit_safe_count = 0

    for line_no, row in rows:
        missing = required.difference(row)
        assert not missing, f"{path}:{line_no} missing required fields: {sorted(missing)}"
        assert isinstance(row["ticker"], str) and row["ticker"], f"{path}:{line_no}"
        assert row["ticker"] == row["ticker"].upper(), f"{path}:{line_no} ticker not uppercase"
        assert isinstance(row["pit_safe_flag"], bool), f"{path}:{line_no} pit flag type"
        assert isinstance(
            row["open_market_purchase_flag"],
            bool,
        ), f"{path}:{line_no} purchase flag type"
        if row["open_market_purchase_flag"]:
            assert isinstance(
                row["transaction_value"],
                (int, float),
            ), f"{path}:{line_no} open-market purchase missing transaction_value"
            assert row["transaction_value"] > 0, f"{path}:{line_no} non-positive purchase value"

        usable = _as_date(row["usable_trade_date"])
        accepted = _accepted_date(row["accepted_at"])
        transaction = _as_date(row["transaction_date"])
        assert usable >= accepted, f"{path}:{line_no} usable date before accepted_at"
        assert usable >= transaction, f"{path}:{line_no} usable date before transaction_date"
        if row["pit_safe_flag"]:
            pit_safe_count += 1

    assert pit_safe_count > 0, "sample should include PIT-safe Form 4 rows"


def test_open_positions_have_gate2_required_fields() -> None:
    path = ROOT / "operator_inputs" / "open_positions.json"
    payload = _json(path)
    rows = (
        list(payload.get("positions") or [])
        + list(payload.get("core_positions") or [])
        + list(payload.get("observations") or [])
    )
    assert rows, f"{path} must contain open position rows"

    for idx, row in enumerate(rows):
        label = f"{path}:position[{idx}]"
        for field in ("ticker", "entry_date", "target_price", "sleeve", "slot_policy"):
            assert row.get(field) not in (None, ""), f"{label} missing {field}"
        assert isinstance(row["ticker"], str) and row["ticker"] == row["ticker"].upper()
        _as_date(row["entry_date"])
        assert isinstance(row["target_price"], (int, float)), f"{label} target_price type"
        assert row["target_price"] > 0, f"{label} target_price must be positive"


def test_recent_experiment_artifact_has_three_window_metric_contract() -> None:
    path = ROOT / "experiments" / "logs" / "exp-20260530-013.json"
    payload = _json(path)

    assert set(payload["windows"]) == STANDARD_WINDOWS
    assert set(payload["delta_metrics"]["by_window"]) == STANDARD_WINDOWS

    for label, window in payload["windows"].items():
        for side in ("before", "after"):
            metrics = window[side]
            missing = WINDOW_METRICS.difference(metrics)
            assert not missing, f"{path}:windows.{label}.{side} missing {sorted(missing)}"
            assert metrics["signals_generated"] >= metrics["signals_survived"]
            assert metrics["trade_count"] >= 0
            assert metrics["survival_rate"] >= 0

    gate4 = payload["gate4"]
    assert isinstance(gate4["passed"], bool)
    assert isinstance(gate4["failed_reasons"], list)
    protocol = payload["backtest_protocol"]
    protocol_source = protocol.get("source") if isinstance(protocol, dict) else protocol
    assert protocol_source.startswith("docs/backtesting.md")

    impact = payload["production_impact"]
    assert impact["shared_policy_changed"] is False
    assert impact["alters_orders"] is False
    assert impact["replay_only"] is True
