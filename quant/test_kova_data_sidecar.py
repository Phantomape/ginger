from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pandas as pd

import kova_data_sidecar as sidecar


def test_alpha_vantage_intraday_parser_filters_future_rows() -> None:
    payload = {
        "Meta Data": {"2. Symbol": "ABC"},
        "Time Series (15min)": {
            "2026-05-27 10:00:00": {
                "1. open": "11",
                "2. high": "12",
                "3. low": "10",
                "4. close": "11.5",
                "5. volume": "2000",
            },
            "2026-05-26 15:45:00": {
                "1. open": "10",
                "2. high": "11",
                "3. low": "9",
                "4. close": "10.5",
                "5. volume": "1000",
            },
        },
    }

    rows = sidecar.parse_alpha_vantage_intraday_payload(
        payload,
        ticker="abc",
        interval="15min",
        asof_date="2026-05-26",
        provider_asof_utc="2026-05-26T21:00:00Z",
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "ABC"
    assert rows[0]["timestamp"] == "2026-05-26 15:45:00"
    assert rows[0]["close"] == 10.5
    assert rows[0]["alters_orders"] is False


def test_companyfacts_growth_uses_only_filed_rows_before_asof() -> None:
    rows = [
        {
            "ticker": "ABC",
            "cik": "0000000123",
            "canonical": "revenue",
            "value": 100.0,
            "end": "2024-03-31",
            "filed": "2024-04-20",
            "form": "10-Q",
            "fp": "Q1",
            "fy": 2024,
            "duration_days": 91,
        },
        {
            "ticker": "ABC",
            "cik": "0000000123",
            "canonical": "revenue",
            "value": 130.0,
            "end": "2025-03-31",
            "filed": "2025-04-20",
            "form": "10-Q",
            "fp": "Q1",
            "fy": 2025,
            "duration_days": 91,
        },
        {
            "ticker": "ABC",
            "cik": "0000000123",
            "canonical": "revenue",
            "value": 999.0,
            "end": "2026-03-31",
            "filed": "2026-04-20",
            "form": "10-Q",
            "fp": "Q1",
            "fy": 2026,
            "duration_days": 91,
        },
    ]

    growth = sidecar.derive_companyfacts_growth_rows(
        rows,
        asof_date="2025-05-01",
        tickers=["ABC"],
    )

    ok = [row for row in growth if row["growth_status"] == "ok"]
    assert len(ok) == 1
    assert ok[0]["asof_date"] == "2025-04-20"
    assert ok[0]["yoy_growth"] == 0.3
    assert all(row["current_period_end"] != "2026-03-31" for row in growth)


def test_companyfacts_loader_uses_filed_window_and_file_dates(tmp_path: Path) -> None:
    old_path = tmp_path / "sec_companyfacts_selected_20200101_20200131.jsonl"
    recent_path = tmp_path / "sec_companyfacts_selected_20250101_20260501.jsonl"
    sidecar._write_jsonl(
        old_path,
        [
            {
                "ticker": "ABC",
                "canonical": "revenue",
                "value": 50.0,
                "filed": "2020-01-15",
                "end": "2019-12-31",
            }
        ],
    )
    sidecar._write_jsonl(
        recent_path,
        [
            {
                "ticker": "ABC",
                "canonical": "revenue",
                "value": 100.0,
                "filed": "2025-04-20",
                "end": "2025-03-31",
            },
            {
                "ticker": "ABC",
                "canonical": "revenue",
                "value": 999.0,
                "filed": "2026-04-20",
                "end": "2026-03-31",
            },
        ],
    )

    paths = sidecar.selected_companyfacts_paths(
        tmp_path,
        min_filed="2025-01-01",
        max_filed="2025-12-31",
    )
    rows = sidecar.load_selected_companyfacts_rows(
        non_ohlcv_dir=tmp_path,
        min_filed="2025-01-01",
        max_filed="2025-12-31",
        tickers=["ABC"],
    )

    assert paths == [recent_path]
    assert [row["value"] for row in rows] == [100.0]


def test_rs_proxy_uses_rows_on_or_before_asof_only() -> None:
    def rows(closes: list[float], future: float) -> list[dict]:
        out = [
            {"Date": f"2026-01-{idx + 1:02d}", "Close": close}
            for idx, close in enumerate(closes)
        ]
        out.append({"Date": "2026-02-15", "Close": future})
        return out

    ohlcv = {
        "SPY": rows([100 + i for i in range(25)], 500),
        "AAA": rows([100 + i * 2 for i in range(25)], 10),
        "BBB": rows([100 + i for i in range(25)], 1000),
    }

    rs = sidecar.compute_rs_proxy_rows(
        ohlcv,
        asof_date="2026-01-25",
        tickers=["AAA", "BBB"],
        windows=(20,),
    )

    by_ticker = {row["ticker"]: row for row in rs}
    assert by_ticker["AAA"]["rs_proxy_rank_pct_20d"] == 1.0
    assert by_ticker["BBB"]["rs_proxy_rank_pct_20d"] == 0.0
    assert by_ticker["AAA"]["asof_price_date"] == "2026-01-25"


def test_parse_sec13f_zip_joins_with_optional_cusip_map(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample13f.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        info = "ACCESSION_NUMBER\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tVALUE\tSSHPRNAMT\n"
        info += "0001\tExample Inc\tCOM\t123456789\t50\t1000\n"
        info += "0002\tFuture Inc\tCOM\t999999999\t75\t2000\n"
        archive.writestr("INFOTABLE.tsv", info)
        submission = "ACCESSION_NUMBER\tFILING_DATE\tFILINGMANAGER_NAME\tCIK\tPERIODOFREPORT\n"
        submission += "0001\t2026-05-01\tManager A\t0001111111\t2026-03-31\n"
        submission += "0002\t2026-06-01\tManager B\t0002222222\t2026-03-31\n"
        archive.writestr("SUBMISSION.tsv", submission)

    rows = sidecar.parse_sec13f_zip(
        zip_path,
        asof_date="2026-05-15",
        cusip_ticker_map={"123456789": "ABC"},
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "ABC"
    assert rows[0]["ticker_mapping_status"] == "cusip_map_exact"
    assert rows[0]["asof_date"] == "2026-05-01"
    assert rows[0]["manager_name"] == "Manager A"


def test_load_kova_context_selects_latest_nonfuture_surface(tmp_path: Path) -> None:
    path = tmp_path / "fundamentals" / "companyfacts_growth_20260501.jsonl"
    sidecar._write_jsonl(
        path,
        [
            {"surface": "sec_companyfacts_growth", "ticker": "ABC", "asof_date": "2026-05-01", "yoy_growth": 0.2},
            {"surface": "sec_companyfacts_growth", "ticker": "ABC", "asof_date": "2026-05-20", "yoy_growth": 0.9},
            {"surface": "sec_companyfacts_growth", "ticker": "ABC", "asof_date": "2026-05-03", "canonical": "eps_diluted", "yoy_growth": 0.4},
            {"surface": "sec13f_institutional_ownership", "ticker": "ABC", "asof_date": "2026-05-02", "manager_name": "Manager A"},
            {"surface": "ginger_rs_proxy", "ticker": "ABC", "asof_date": "2026-04-30", "rs_proxy_rank_pct_20d": 0.8},
        ],
    )

    context = sidecar.load_kova_context(ticker="ABC", asof_date="2026-05-10", data_dir=tmp_path)

    assert context["surfaces"]["sec_companyfacts_growth"]["yoy_growth"] != 0.9
    assert context["fundamental_growth_by_canonical"]["eps_diluted"]["yoy_growth"] == 0.4
    assert context["institutional_ownership_rows"][0]["manager_name"] == "Manager A"
    assert context["surfaces"]["ginger_rs_proxy"]["rs_proxy_rank_pct_20d"] == 0.8


def test_persist_kova_snapshot_writes_default_off_sidecars(tmp_path: Path) -> None:
    non_ohlcv = tmp_path / "non_ohlcv"
    non_ohlcv.mkdir()
    companyfacts_path = non_ohlcv / "sec_companyfacts_selected_20250101_20260501.jsonl"
    sidecar._write_jsonl(
        companyfacts_path,
        [
            {
                "ticker": "ABC",
                "cik": "0000000123",
                "canonical": "eps_diluted",
                "value": 1.0,
                "end": "2024-03-31",
                "filed": "2024-04-20",
                "form": "10-Q",
                "fp": "Q1",
                "fy": 2024,
                "duration_days": 91,
            },
            {
                "ticker": "ABC",
                "cik": "0000000123",
                "canonical": "eps_diluted",
                "value": 1.5,
                "end": "2025-03-31",
                "filed": "2025-04-20",
                "form": "10-Q",
                "fp": "Q1",
                "fy": 2025,
                "duration_days": 91,
            },
        ],
    )
    ohlcv_path = tmp_path / "ohlcv.json"
    ohlcv_path.write_text(
        json.dumps(
            {
                "ohlcv": {
                    "SPY": [{"Date": f"2026-01-{idx + 1:02d}", "Close": 100 + idx} for idx in range(25)],
                    "ABC": [{"Date": f"2026-01-{idx + 1:02d}", "Close": 100 + idx * 2} for idx in range(25)],
                }
            }
        ),
        encoding="utf-8",
    )

    snapshot = sidecar.persist_kova_data_snapshot(
        asof_date="2026-01-25",
        tickers=["ABC"],
        data_dir=tmp_path / "kova",
        non_ohlcv_dir=non_ohlcv,
        ohlcv_snapshot=ohlcv_path,
    )

    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["intraday_ohlcv"]["rows_written"] == 1
    assert snapshot["fundamental_growth"]["rows_written"] == 2
    assert snapshot["rs_proxy"]["rows_written"] == 1
    assert snapshot["institutional_ownership"]["rows_written"] == 1
    assert Path(tmp_path / "kova" / "snapshots" / "kova_data_snapshot_20260125.json").exists()


def test_normalize_ohlcv_mapping_accepts_dataframes() -> None:
    frame = pd.DataFrame(
        [
            {"Date": pd.Timestamp("2026-01-01"), "Open": 10, "High": 11, "Low": 9, "Close": 10.5, "Volume": 1000},
            {"Date": pd.Timestamp("2026-01-02"), "Open": 11, "High": 12, "Low": 10, "Close": 11.5, "Volume": 1100},
        ]
    )

    rows = sidecar.normalize_ohlcv_mapping({"abc": frame})

    assert rows["ABC"][0]["Date"] == "2026-01-01"
    assert rows["ABC"][1]["Close"] == 11.5
