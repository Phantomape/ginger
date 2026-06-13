from __future__ import annotations

import json

from quant.sec13f_universe_map import (
    build_cusip_ticker_map,
    load_company_name_index,
    normalize_issuer_name,
)


def test_normalize_strips_suffixes_and_share_class() -> None:
    assert normalize_issuer_name("Apple Inc.") == normalize_issuer_name("APPLE INC")
    assert normalize_issuer_name("Alphabet Inc. Class A") == normalize_issuer_name("ALPHABET INC CL A")
    assert normalize_issuer_name("NVIDIA CORP") == "NVIDIA"
    assert normalize_issuer_name("") == ""


def test_load_company_name_index_drops_collisions(tmp_path) -> None:
    payload = {
        "0": {"cik_str": 1, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 2, "ticker": "NVDA", "title": "NVIDIA Corp"},
        # Two different tickers normalizing to the same name -> ambiguous, dropped.
        "2": {"cik_str": 3, "ticker": "DUPA", "title": "Dup Co"},
        "3": {"cik_str": 4, "ticker": "DUPB", "title": "Dup Company"},
    }
    path = tmp_path / "company_tickers.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    index = load_company_name_index(path)
    assert index[normalize_issuer_name("APPLE INC")] == "AAPL"
    assert index[normalize_issuer_name("NVIDIA CORP")] == "NVDA"
    assert normalize_issuer_name("DUP CO") not in index  # collision removed


def test_build_cusip_map_matches_universe_and_drops_conflicts() -> None:
    name_index = {
        normalize_issuer_name("APPLE INC"): "AAPL",
        normalize_issuer_name("NVIDIA CORP"): "NVDA",
        normalize_issuer_name("OFF UNIVERSE CO"): "ZZZZ",
    }
    rows = [
        {"cusip": "037833100", "name_of_issuer": "APPLE INC."},
        {"cusip": "037833100", "name_of_issuer": "Apple Inc"},     # same -> ok
        {"cusip": "67066G104", "name_of_issuer": "NVIDIA CORP"},
        {"cusip": "999999999", "name_of_issuer": "Off Universe Co"},  # ticker not in universe
        {"cusip": "111111111", "name_of_issuer": "Totally Unknown Issuer"},  # no match
    ]
    mapping = build_cusip_ticker_map(
        rows, name_index=name_index, universe={"AAPL", "NVDA"}
    )
    assert mapping == {"037833100": "AAPL", "67066G104": "NVDA"}


def test_build_cusip_map_drops_conflicting_ticker_for_same_cusip() -> None:
    name_index = {
        normalize_issuer_name("APPLE INC"): "AAPL",
        normalize_issuer_name("BANANA INC"): "BNNA",
    }
    rows = [
        {"cusip": "037833100", "name_of_issuer": "APPLE INC"},
        {"cusip": "037833100", "name_of_issuer": "BANANA INC"},  # conflict on same cusip
    ]
    mapping = build_cusip_ticker_map(
        rows, name_index=name_index, universe={"AAPL", "BNNA"}
    )
    assert "037833100" not in mapping
