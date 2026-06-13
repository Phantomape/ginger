from __future__ import annotations

import io
import json
import zipfile

from quant.sec13f_ingest import (
    aggregate_universe_holdings,
    ingest_universe_13f,
    latest_available_window,
    window_label,
    window_url,
)
from quant.sec13f_universe_map import normalize_issuer_name


def test_window_label_and_url_use_filing_window_format() -> None:
    # SEC switched from {year}q{quarter} to filing-window naming around 2024.
    assert window_label(2026, 3) == "01mar2026-31may2026"
    assert window_label(2025, 12) == "01dec2025-28feb2026"  # spans year, non-leap Feb
    assert window_url(2026, 3).endswith("/01mar2026-31may2026_form13f.zip")


def test_latest_available_window_picks_newest_passed_window() -> None:
    # As of 2026-06-11 the Mar-May 2026 window has closed; Jun-Aug has not.
    assert latest_available_window("2026-06-11", head_check=None) == (2026, 3)
    # As of 2026-09-05 the Jun-Aug window has closed.
    assert latest_available_window("2026-09-05", head_check=None) == (2026, 6)


def test_latest_available_window_walks_back_on_head_check() -> None:
    newest = window_url(2026, 3)
    # Simulate the newest window not yet published; expect fallback to prior.
    seen = {newest: False, window_url(2025, 12): True}
    chosen = latest_available_window("2026-06-11", head_check=lambda url: seen.get(url, False))
    assert chosen == (2025, 12)


def test_aggregate_universe_holdings_per_ticker() -> None:
    name_index = {
        normalize_issuer_name("APPLE INC"): "AAPL",
        normalize_issuer_name("NVIDIA CORP"): "NVDA",
        normalize_issuer_name("OFF UNIVERSE"): "ZZZZ",
    }
    rows = [
        {"cusip": "037833100", "name_of_issuer": "APPLE INC", "manager_cik": "1",
         "value_usd_thousands": 100.0, "shares": 10.0, "report_period": "2026-03-31"},
        {"cusip": "037833100", "name_of_issuer": "APPLE INC", "manager_cik": "2",
         "value_usd_thousands": 50.0, "shares": 5.0, "report_period": "2026-03-31"},
        {"cusip": "67066G104", "name_of_issuer": "NVIDIA CORP", "manager_cik": "1",
         "value_usd_thousands": 200.0, "shares": 20.0, "report_period": "2026-03-31"},
        {"cusip": "999", "name_of_issuer": "OFF UNIVERSE", "manager_cik": "1",
         "value_usd_thousands": 9.0, "shares": 1.0},  # ticker not in universe
    ]
    by_ticker, cusip_map = aggregate_universe_holdings(
        rows, name_index=name_index, universe={"AAPL", "NVDA"}
    )
    assert set(by_ticker) == {"AAPL", "NVDA"}
    assert by_ticker["AAPL"]["holder_count"] == 2
    assert by_ticker["AAPL"]["position_row_count"] == 2
    assert by_ticker["AAPL"]["total_value_usd"] == 150.0
    assert by_ticker["AAPL"]["total_shares"] == 15.0
    assert by_ticker["NVDA"]["holder_count"] == 1
    assert cusip_map == {"037833100": "AAPL", "67066G104": "NVDA"}


def _synthetic_zip(path) -> None:
    info = (
        "ACCESSION_NUMBER\tCUSIP\tNAMEOFISSUER\tTITLEOFCLASS\tVALUE\tSSHPRNAMT\tINVESTMENTDISCRETION\n"
        "0001-26-1\t037833100\tAPPLE INC\tCOM\t100\t10\tSOLE\n"
        "0001-26-2\t67066G104\tNVIDIA CORP\tCOM\t200\t20\tSOLE\n"
        "0002-26-1\t037833100\tAPPLE INC\tCOM\t50\t5\tSOLE\n"
    )
    submission = (
        "ACCESSION_NUMBER\tFILING_DATE\tFILINGMANAGER_NAME\tCIK\tPERIODOFREPORT\n"
        "0001-26-1\t2026-05-10\tManager One\t1\t2026-03-31\n"
        "0001-26-2\t2026-05-10\tManager One\t1\t2026-03-31\n"
        "0002-26-1\t2026-05-12\tManager Two\t2\t2026-03-31\n"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("INFOTABLE.tsv", info)
        archive.writestr("SUBMISSION.tsv", submission)


def test_ingest_is_idempotent_and_writes_real_holdings(tmp_path) -> None:
    company = {
        "0": {"cik_str": 1, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 2, "ticker": "NVDA", "title": "NVIDIA Corp"},
    }
    company_path = tmp_path / "company_tickers.json"
    company_path.write_text(json.dumps(company), encoding="utf-8")
    out_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"

    downloads: list[str] = []

    def fake_download(url: str, dest):
        downloads.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        _synthetic_zip(dest)
        return dest

    summary = ingest_universe_13f(
        universe=["AAPL", "NVDA", "TSLA"],
        as_of="2026-06-11",
        out_dir=out_dir,
        cache_dir=cache_dir,
        company_tickers_path=company_path,
        head_check=None,
        download=fake_download,
    )
    assert summary["status"] == "ingested"
    assert summary["window_label"] == "01mar2026-31may2026"
    assert summary["universe_covered_count"] == 2  # AAPL + NVDA, not TSLA
    assert len(downloads) == 1

    payload = json.loads((out_dir / "holdings_01mar2026-31may2026.json").read_text(encoding="utf-8"))
    aapl = next(h for h in payload["holdings"] if h["ticker"] == "AAPL")
    assert aapl["holder_count"] == 2
    assert aapl["total_value_usd"] == 150.0
    assert (out_dir / "latest.json").exists()

    # Second call for the same window: no re-download, reuses existing file.
    again = ingest_universe_13f(
        universe=["AAPL", "NVDA", "TSLA"],
        as_of="2026-06-12",
        out_dir=out_dir,
        cache_dir=cache_dir,
        company_tickers_path=company_path,
        head_check=None,
        download=fake_download,
    )
    assert again["status"] == "current"
    assert again["reused_existing"] is True
    assert len(downloads) == 1  # unchanged
