from __future__ import annotations

import json
from pathlib import Path

import daily_non_ohlcv_snapshot as daily_snapshot


def test_daily_snapshot_writes_dated_artifacts_and_all_sec_text_items(tmp_path, monkeypatch):
    calls = {}

    def fake_sec_events(args):
        calls["sec_events"] = args
        Path(args.output).write_text('{"ticker":"CRDO"}\n', encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 1, "pit_safe_rows": 1}

    def fake_sec_text(args):
        calls["sec_text"] = args
        return (
            [{"ticker": "CRDO", "eight_k_item_codes": ["5.07"], "status": "ok"}],
            {"rows_written": 1, "item_codes": args.item_codes},
        )

    def fake_form4(args):
        calls["form4"] = args
        Path(args.output).write_text('{"ticker":"CRDO"}\n', encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 1, "pit_safe_count": 1}

    monkeypatch.setattr(daily_snapshot, "backfill_sec_filing_events", fake_sec_events)
    monkeypatch.setattr(daily_snapshot, "build_sec_filing_text_rows", fake_sec_text)
    monkeypatch.setattr(daily_snapshot, "backfill_form4_transactions", fake_form4)

    snapshot = daily_snapshot.persist_daily_non_ohlcv_snapshots(
        as_of="2026-05-04",
        data_dir=tmp_path,
        lookback_days=3,
    )

    assert snapshot["status"] == "ok"
    assert snapshot["borrow_availability"]["status"] == "skipped"
    assert calls["sec_events"].start == "2026-05-01"
    assert calls["sec_events"].end == "2026-05-04"
    assert calls["sec_events"].refresh_submissions is True
    assert "6-K" in calls["sec_events"].forms[0]
    assert "6-K" in calls["sec_text"].forms
    assert calls["sec_text"].item_codes == ["all"]
    assert calls["sec_text"].events.endswith("sec_filing_events_20260504.jsonl")
    assert calls["form4"].output.endswith("form4_transactions_20260504.jsonl")
    assert calls["form4"].refresh_submissions is True
    assert calls["form4"].refresh_xml is False
    assert (tmp_path / "sec_filing_text_20260504.jsonl").exists()
    assert (tmp_path / "form4_transactions_20260504.jsonl").exists()
    assert (tmp_path / "daily_non_ohlcv_snapshot_20260504.json").exists()


def test_daily_snapshot_keeps_form4_when_sec_source_fails(tmp_path, monkeypatch):
    def failing_sec_events(args):
        raise RuntimeError("sec unavailable")

    def should_not_fetch_text(args):
        raise AssertionError("SEC text fetch should be skipped when SEC events fail")

    def fake_form4(args):
        Path(args.output).write_text('{"ticker":"CRDO"}\n', encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 1, "pit_safe_count": 1}

    monkeypatch.setattr(daily_snapshot, "backfill_sec_filing_events", failing_sec_events)
    monkeypatch.setattr(daily_snapshot, "build_sec_filing_text_rows", should_not_fetch_text)
    monkeypatch.setattr(daily_snapshot, "backfill_form4_transactions", fake_form4)

    snapshot = daily_snapshot.persist_daily_non_ohlcv_snapshots(
        as_of="2026-05-04",
        data_dir=tmp_path,
    )

    assert snapshot["status"] == "partial"
    assert snapshot["sec_filing_events"]["status"] == "failed"
    assert snapshot["sec_filing_text"]["status"] == "skipped"
    assert snapshot["form4_transactions"]["status"] == "ok"
    assert (tmp_path / "form4_transactions_20260504.jsonl").exists()


def test_daily_snapshot_can_collect_options_as_data_only(tmp_path, monkeypatch):
    def fake_sec_events(args):
        Path(args.output).write_text("", encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 0, "pit_safe_rows": 0}

    def fake_sec_text(args):
        return ([], {"rows_written": 0, "item_codes": args.item_codes})

    def fake_form4(args):
        Path(args.output).write_text("", encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 0, "pit_safe_count": 0}

    def fake_options(**kwargs):
        assert kwargs["tickers"] == ["TSLA"]
        assert kwargs["underlying_prices"] == {"TSLA": 300.0}
        return {
            "status": "ok",
            "rows_written": 4,
            "pit_safe_rows": 4,
            "output_path": str(tmp_path / "options_onclickmedia_chain_20260504.jsonl"),
            "summary_output": str(tmp_path / "options_onclickmedia_summary_20260504.json"),
            "production_impact": {
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
            },
        }

    monkeypatch.setattr(daily_snapshot, "backfill_sec_filing_events", fake_sec_events)
    monkeypatch.setattr(daily_snapshot, "build_sec_filing_text_rows", fake_sec_text)
    monkeypatch.setattr(daily_snapshot, "backfill_form4_transactions", fake_form4)
    monkeypatch.setattr(daily_snapshot, "persist_daily_options_snapshot", fake_options)

    snapshot = daily_snapshot.persist_daily_non_ohlcv_snapshots(
        as_of="2026-05-04",
        data_dir=tmp_path,
        refresh_options=True,
        options_tickers=["TSLA"],
        option_underlying_prices={"TSLA": 300.0},
    )

    assert snapshot["status"] == "ok"
    assert snapshot["options_onclickmedia"]["status"] == "ok"
    assert snapshot["options_onclickmedia"]["rows_written"] == 4
    impact = snapshot["options_onclickmedia"]["production_impact"]
    assert impact["alters_signal_generation"] is False
    assert impact["alters_candidate_ranking"] is False
    assert impact["alters_sizing"] is False
    assert impact["alters_orders"] is False


def test_daily_snapshot_can_collect_borrow_availability_as_data_only(tmp_path, monkeypatch):
    borrow_manifest = tmp_path / "borrow_availability" / "manifest.json"
    borrow_rows = tmp_path / "borrow_availability" / "rows.jsonl"

    def fake_sec_events(args):
        Path(args.output).write_text("", encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 0, "pit_safe_rows": 0}

    def fake_sec_text(args):
        return ([], {"rows_written": 0, "item_codes": args.item_codes})

    def fake_form4(args):
        Path(args.output).write_text("", encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 0, "pit_safe_count": 0}

    def fake_borrow(*, broad):
        assert broad is True
        borrow_manifest.parent.mkdir(parents=True, exist_ok=True)
        borrow_rows.write_text('{"ticker":"TSLA","borrow_populated":true}\n', encoding="utf-8")
        borrow_manifest.write_text(
            json.dumps(
                {
                    "source": "moomoo_openapi_market_snapshot",
                    "rows_appended_this_run": 1,
                    "borrow_populated_this_run": 1,
                    "borrow_populated_pct": 100.0,
                    "trade_enabled": False,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(daily_snapshot, "backfill_sec_filing_events", fake_sec_events)
    monkeypatch.setattr(daily_snapshot, "build_sec_filing_text_rows", fake_sec_text)
    monkeypatch.setattr(daily_snapshot, "backfill_form4_transactions", fake_form4)
    monkeypatch.setattr(daily_snapshot, "run_borrow_availability_sidecar", fake_borrow)
    monkeypatch.setattr(daily_snapshot, "BORROW_AVAILABILITY_MANIFEST_PATH", borrow_manifest)
    monkeypatch.setattr(daily_snapshot, "BORROW_AVAILABILITY_ROWS_PATH", borrow_rows)

    snapshot = daily_snapshot.persist_daily_non_ohlcv_snapshots(
        as_of="2026-05-04",
        data_dir=tmp_path,
        refresh_borrow_availability=True,
        borrow_availability_broad=True,
    )

    assert snapshot["status"] == "ok"
    assert snapshot["borrow_availability"]["status"] == "ok"
    assert snapshot["borrow_availability"]["rows_appended_this_run"] == 1
    assert snapshot["borrow_availability"]["borrow_populated_this_run"] == 1
    assert snapshot["borrow_availability"]["trade_enabled"] is False
    assert snapshot["borrow_availability"]["daily_snapshot_wired"] is True
    impact = snapshot["borrow_availability"]["production_impact"]
    assert impact["alters_signal_generation"] is False
    assert impact["alters_candidate_ranking"] is False
    assert impact["alters_sizing"] is False
    assert impact["alters_orders"] is False


def test_daily_snapshot_borrow_availability_failure_is_fail_soft(tmp_path, monkeypatch):
    borrow_manifest = tmp_path / "borrow_availability" / "manifest.json"
    borrow_rows = tmp_path / "borrow_availability" / "rows.jsonl"

    def fake_sec_events(args):
        Path(args.output).write_text("", encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 0, "pit_safe_rows": 0}

    def fake_sec_text(args):
        return ([], {"rows_written": 0, "item_codes": args.item_codes})

    def fake_form4(args):
        Path(args.output).write_text("", encoding="utf-8")
        Path(args.summary_output).write_text("{}\n", encoding="utf-8")
        return {"rows_written": 0, "pit_safe_count": 0}

    def failing_borrow(*, broad):
        raise RuntimeError("moomoo OpenD unavailable")

    monkeypatch.setattr(daily_snapshot, "backfill_sec_filing_events", fake_sec_events)
    monkeypatch.setattr(daily_snapshot, "build_sec_filing_text_rows", fake_sec_text)
    monkeypatch.setattr(daily_snapshot, "backfill_form4_transactions", fake_form4)
    monkeypatch.setattr(daily_snapshot, "run_borrow_availability_sidecar", failing_borrow)
    monkeypatch.setattr(daily_snapshot, "BORROW_AVAILABILITY_MANIFEST_PATH", borrow_manifest)
    monkeypatch.setattr(daily_snapshot, "BORROW_AVAILABILITY_ROWS_PATH", borrow_rows)

    snapshot = daily_snapshot.persist_daily_non_ohlcv_snapshots(
        as_of="2026-05-04",
        data_dir=tmp_path,
        refresh_borrow_availability=True,
    )

    assert snapshot["status"] == "partial"
    assert snapshot["borrow_availability"]["status"] == "failed"
    assert "moomoo OpenD unavailable" in snapshot["borrow_availability"]["error"]
    assert (tmp_path / "daily_non_ohlcv_snapshot_20260504.json").exists()
    impact = snapshot["borrow_availability"]["production_impact"]
    assert impact["scope"] == "borrow_availability_data_collection_failed_only"
    assert impact["alters_signal_generation"] is False
    assert impact["alters_orders"] is False
