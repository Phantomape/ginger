from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from quant import orange_book_newa_release_basket_paper_sleeve as sleeve


def _business_bars(start: str, count: int, *, slope: float = 0.5):
    day = date.fromisoformat(start)
    rows = []
    while len(rows) < count:
        if day.weekday() < 5:
            index = len(rows)
            close = 100.0 + slope * index
            rows.append(
                {
                    "date": day.isoformat(),
                    "open": close - 0.2,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                }
            )
        day += timedelta(days=1)
    return rows


def _document(
    root: Path,
    *,
    media_id: int,
    month: str,
    last_modified: str,
    raw: bytes | None = None,
):
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw or f"fake-pdf-{media_id}".encode()
    path = raw_dir / f"orange_{media_id}.pdf"
    path.write_bytes(payload)
    return {
        "month": month,
        "media_id": media_id,
        "relative_path": f"raw/{path.name}",
        "source_url": sleeve.DOCUMENT_URL_PATTERN.format(media_id=media_id),
        "official_http_last_modified_utc": last_modified,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _write_manifest(root: Path, documents):
    path = root / "source_manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": {"landing_page_url": sleeve.LANDING_URL},
                "documents": documents,
            }
        ),
        encoding="utf-8",
    )
    return path


def _application(
    *,
    ticker="ABBV",
    application_number="123456",
    media_id=100,
    month="2025-01",
    signal_timestamp="2025-01-03T18:00:00Z",
):
    signal_date = signal_timestamp[:10]
    return {
        "application_event_id": (
            f"orange_book:{media_id}:{ticker}:{application_number}"
        ),
        "ticker": ticker,
        "application_number": application_number,
        "signal_timestamp": signal_timestamp,
        "signal_date": signal_date,
        "official_http_last_modified_utc": signal_timestamp,
        "month": month,
        "media_id": media_id,
        "source_url": sleeve.DOCUMENT_URL_PATTERN.format(media_id=media_id),
        "source_relative_path": f"raw/orange_{media_id}.pdf",
        "source_pdf_sha256": "a" * 64,
        "source_line_sha256s": [hashlib.sha256(application_number.encode()).hexdigest()],
    }


def test_exact_event_date_mapping_rejects_partial_ambiguous_and_wrong_parent():
    assert sleeve.map_holder_line_exact(
        ">A> ABBVIE 5MG N 123456 001 JAN 02, 2025 JAN NEWA",
        event_date="2025-01-10",
    ) == "ABBV"
    assert sleeve.map_holder_line_exact(
        ">A> ABBVIETHERAPEUTICS 5MG N 123456 001 JAN 02, 2025 JAN NEWA",
        event_date="2025-01-10",
    ) is None
    assert sleeve.map_holder_line_exact(
        ">A> ABBVIE PFIZER 5MG N 123456 001 JAN 02, 2025 JAN NEWA",
        event_date="2025-01-10",
    ) is None
    assert sleeve.map_holder_line_exact(
        ">A> MYLAN 5MG N 123456 001 JAN 02, 2019 JAN NEWA",
        event_date="2019-01-10",
    ) is None
    # Fresenius Kabi belongs to Fresenius SE, not FMS; fail closed because the
    # fixed executable universe has no approved listed-parent mapping.
    assert sleeve.map_holder_line_exact(
        ">A> FRESENIUS KABI USA 5MG N 123456 001 JAN 02, 2025 JAN NEWA",
        event_date="2025-01-10",
    ) is None


def test_manifest_hash_and_strict_fresh_newa_parser(monkeypatch, tmp_path):
    document = _document(
        tmp_path,
        media_id=100,
        month="2025-01",
        last_modified="2025-01-31T18:00:00Z",
        raw=b"fixed-fake-pdf",
    )
    manifest = _write_manifest(tmp_path, [document])
    lines = [
        ">A> ABBVIE 5MG N 123456 001 JAN 15, 2025 JAN NEWA",
        ">A> ABBVIE 10MG N 123456 002 JAN 15, 2025 JAN NEWA",
        ">A> PFIZER 5MG N 223456 001 JAN 15, 2025 JAN NEWG",
        ">D> PFIZER 5MG N 323456 001 JAN 15, 2025 JAN NEWA",
        ">A> PFIZER 5MG N 423456 001 NOV 01, 2024 JAN NEWA",
        ">A> PRIVATE HOLDER 5MG N 523456 001 JAN 15, 2025 JAN NEWA",
    ]
    monkeypatch.setattr(
        sleeve, "_extract_pdf_lines", lambda path: list(enumerate(lines, start=1))
    )
    decisions, identity = sleeve.load_and_verify_source(manifest)
    assert len(decisions) == 1
    assert decisions[0]["ticker"] == "ABBV"
    assert decisions[0]["application_number"] == "123456"
    assert decisions[0]["product_numbers"] == ["001", "002"]
    assert decisions[0]["signal_timestamp"] == "2025-01-31T18:00:00Z"
    assert decisions[0]["approval_date_role"].startswith("freshness_metadata")
    assert identity["verified_document_count"] == 1
    assert identity["parse_reject_totals"] == {
        "addition_not_terminal_newa": 1,
        "approval_outside_0_45_day_freshness": 1,
        "unmapped_or_ambiguous_holder": 1,
    }

    pdf = tmp_path / document["relative_path"]
    pdf.write_bytes(b"tampered-fake!")  # same byte length, different SHA-256.
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        sleeve.load_and_verify_source(manifest)


def test_release_leg_dedupe_and_equal_budget_to_the_cent():
    decisions = [
        _application(ticker="ABBV", application_number="123456"),
        _application(ticker="ABBV", application_number="123457"),
        _application(ticker="PFE", application_number="223456"),
        _application(ticker="LLY", application_number="323456"),
    ]
    legs = sleeve.build_historical_release_legs(
        decisions, start="2025-01-01", end="2025-01-31"
    )
    assert [row["ticker"] for row in legs] == ["ABBV", "LLY", "PFE"]
    assert sum(row["paper_notional_usd"] for row in legs) == 16_000.0
    assert max(row["paper_notional_usd"] for row in legs) - min(
        row["paper_notional_usd"] for row in legs
    ) == pytest.approx(0.01)
    abbv = next(row for row in legs if row["ticker"] == "ABBV")
    assert abbv["application_numbers"] == ["123456", "123457"]
    assert abbv["application_count"] == 2
    assert abbv["release_leg_count"] == 3


def test_replay_enters_next_nyse_open_exits_tenth_session_and_charges_cost():
    decisions = [
        _application(ticker="ABBV", application_number="123456"),
        _application(ticker="PFE", application_number="223456"),
    ]
    spy = _business_bars("2025-01-01", 35, slope=0.0)
    abbv = _business_bars("2025-01-01", 35, slope=0.8)
    pfe = _business_bars("2025-01-01", 35, slope=0.3)
    replay = sleeve.replay_orange_book_newa_release_basket_paper_trades(
        decisions=decisions,
        ohlcv_by_ticker={"SPY": spy, "ABBV": abbv, "PFE": pfe},
        start="2025-01-01",
        end="2025-02-28",
    )
    assert replay["signals_generated"] == 2
    assert replay["signals_survived"] == 2
    assert replay["survival_rate"] == 1.0
    assert replay["reject_totals"] == {}
    assert len(replay["trades"]) == 2
    trade = next(row for row in replay["trades"] if row["ticker"] == "ABBV")
    # 18:00 UTC is after the NYSE open on Friday Jan 3, so entry is Monday Jan 6.
    assert trade["entry_date"] == "2025-01-06"
    entry_spy_index = next(
        index for index, row in enumerate(spy) if row["date"] == trade["entry_date"]
    )
    assert trade["exit_date"] == spy[entry_spy_index + 9]["date"]
    assert trade["hold_sessions_realized"] == 10
    assert trade["target_price"] > trade["entry_price"]
    assert "ATR_metadata_only" in trade["target_price_role"]
    expected = trade["paper_notional_usd"] * (
        trade["exit_price"] / trade["entry_price"]
        - 1.0
        - sleeve.ROUND_TRIP_COST_PCT
    )
    assert trade["pnl"] == pytest.approx(expected, abs=0.02)
    assert trade["trade_enabled"] is False


def test_daily_bootstrap_never_forwards_seed_then_warehouse_fills_and_closes(
    monkeypatch, tmp_path
):
    source_root = tmp_path / "source"
    output_root = tmp_path / "paper"
    old_document = _document(
        source_root,
        media_id=100,
        month="2024-12",
        last_modified="2025-01-03T18:00:00Z",
    )
    new_document = _document(
        source_root,
        media_id=101,
        month="2025-01",
        last_modified="2025-01-20T18:00:00Z",
    )
    lines = {
        "orange_100.pdf": [
            ">A> ABBVIE 5MG N 123456 001 JAN 02, 2025 DEC NEWA"
        ],
        "orange_101.pdf": [
            ">A> PFIZER 5MG N 223456 001 JAN 17, 2025 JAN NEWA"
        ],
    }
    monkeypatch.setattr(
        sleeve,
        "_extract_pdf_lines",
        lambda path: [(1, row) for row in lines[path.name]],
    )
    manifest = _write_manifest(source_root, [old_document])
    bars = {
        "SPY": _business_bars("2025-01-01", 40, slope=0.1),
        "PFE": _business_bars("2025-01-01", 40, slope=0.5),
    }
    warehouse_calls = []

    def fake_warehouse(tickers, *, warehouse_paths=None):
        warehouse_calls.append((tickers, warehouse_paths))
        return bars, {
            "status": "ok",
            "requested_tickers": len(tickers),
            "returned_tickers": 2,
        }

    monkeypatch.setattr(sleeve, "_load_default_warehouse_bars", fake_warehouse)
    first = sleeve.persist_daily_orange_book_newa_release_basket_paper_sleeve(
        "2025-01-10",
        manifest_path=manifest,
        output_root=output_root,
        observed_at="2025-01-10T23:00:00Z",
    )
    assert first["bootstrap_historical_seed"] is True
    assert first["historical_seed_documents_appended"] == 1
    assert first["new_forward_decision_count"] == 0
    assert first["decision_count"] == 0
    assert warehouse_calls == []

    _write_manifest(source_root, [old_document, new_document])
    second = sleeve.persist_daily_orange_book_newa_release_basket_paper_sleeve(
        "2025-01-21",
        manifest_path=manifest,
        output_root=output_root,
        observed_at="2025-01-21T23:00:00Z",
    )
    assert second["new_forward_decision_count"] == 1
    assert second["decision_count"] == 1
    assert second["closed_trade_count"] == 0
    assert second["open_position_count"] == 1
    assert warehouse_calls[-1][0] == ["PFE", "SPY"]

    third = sleeve.persist_daily_orange_book_newa_release_basket_paper_sleeve(
        "2025-02-10",
        manifest_path=manifest,
        output_root=output_root,
        observed_at="2025-02-10T23:00:00Z",
    )
    assert third["new_forward_decision_count"] == 0
    assert third["new_closed_trade_count"] == 1
    assert third["closed_trade_count"] == 1
    state = json.loads((output_root / "state.json").read_text(encoding="utf-8"))
    assert state["seen_documents"]["100"]["seed_not_forward"] is True
    assert state["seen_documents"]["100"]["forward_status"] == (
        "historical_manifest_seed_not_forward"
    )
    assert len(state["decisions"]) == 1
    assert state["decisions"][0]["entry_date"] == "2025-01-21"
    assert state["decisions"][0]["target_price"] is not None
    assert len(state["closed_trades"]) == 1
    assert state["closed_trades"][0]["trade_enabled"] is False

    fourth = sleeve.persist_daily_orange_book_newa_release_basket_paper_sleeve(
        "2025-02-11",
        manifest_path=manifest,
        output_root=output_root,
        observed_at="2025-02-11T23:00:00Z",
    )
    assert fourth["new_forward_decision_count"] == 0
    assert fourth["new_closed_trade_count"] == 0
    assert fourth["closed_trade_count"] == 1

