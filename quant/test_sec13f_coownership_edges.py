"""Focused tests for the SEC 13F co-ownership network peer surface."""

from __future__ import annotations

from datetime import date

try:
    from sec13f_coownership_edges import (
        coownership_peers,
        latest_label_for,
        manager_ticker_edges,
        window_end_date,
    )
except ImportError:  # pragma: no cover - package-style import
    from quant.sec13f_coownership_edges import (
        coownership_peers,
        latest_label_for,
        manager_ticker_edges,
        window_end_date,
    )


# Keys mirror load_company_name_index output: normalize_issuer_name uppercases.
NAME_INDEX = {
    "ALPHA": "AAA",
    "BETA": "BBB",
    "GAMMA": "CCC",
    "DELTA": "DDD",
}
UNIVERSE = {"AAA", "BBB", "CCC", "DDD"}


def _rows(*pairs):
    return [{"manager_cik": cik, "name_of_issuer": name} for cik, name in pairs]


def test_window_end_date_parses_filing_window_label():
    assert window_end_date("01jun2024-31aug2024") == date(2024, 8, 31)
    assert window_end_date("01dec2025-28feb2026") == date(2026, 2, 28)


def test_latest_label_for_is_point_in_time():
    labels = ["01jun2024-31aug2024", "01sep2024-30nov2024", "01dec2024-28feb2025"]
    # Before any window end -> nothing available yet.
    assert latest_label_for("2024-08-30", labels) is None
    # Right after the first window closes.
    assert latest_label_for("2024-09-01", labels) == "01jun2024-31aug2024"
    # On 2025-01-15 the Dec-Feb window has NOT closed yet -> newest available is Sep-Nov.
    assert latest_label_for("2025-01-15", labels) == "01sep2024-30nov2024"
    # After the Dec-Feb window closes, it becomes the newest available.
    assert latest_label_for("2025-03-15", labels) == "01dec2024-28feb2025"


def test_manager_ticker_edges_universe_scoped_and_deduped():
    rows = _rows(
        ("100", "Alpha"), ("100", "Beta"), ("100", "Outside Co"),
        ("200", "Beta"), ("200", "Gamma"),
    )
    edges = manager_ticker_edges(rows, name_index=NAME_INDEX, universe=UNIVERSE)
    assert edges["100"] == {"AAA", "BBB"}  # "Outside Co" not in name index -> dropped
    assert edges["200"] == {"BBB", "CCC"}


def test_coownership_lift_demotes_ubiquitous_pairs():
    # AAA+BBB are co-held by every concentrated manager (popular but NOT a
    # specific cluster); CCC+DDD are co-held only by the two managers that hold
    # them, so their lift over independence should be much higher.
    edges = {
        "m1": {"AAA", "BBB", "CCC", "DDD"},
        "m2": {"AAA", "BBB", "CCC", "DDD"},
        "m3": {"AAA", "BBB"},
        "m4": {"AAA", "BBB"},
        "m5": {"AAA", "BBB"},
        "m6": {"AAA", "BBB"},
    }
    peers, contributing = coownership_peers(
        edges, manager_min_holdings=2, manager_max_holdings=10,
        top_k=5, min_shared_managers=2,
    )
    assert contributing == 6
    # CCC's only solid peer is DDD with lift > 1 (co-held beyond popularity).
    ccc = {p["peer"]: p for p in peers["CCC"]}
    assert "DDD" in ccc
    assert ccc["DDD"]["lift"] > 1.0
    # The ubiquitous AAA-BBB pair has lift at/below the perfectly-correlated CCC-DDD pair.
    aaa = {p["peer"]: p for p in peers["AAA"]}
    assert aaa["BBB"]["lift"] <= ccc["DDD"]["lift"] + 1e-9


def test_coownership_excludes_mega_diversified_and_tiny_managers():
    edges = {
        "index_fund": {"AAA", "BBB", "CCC", "DDD"},   # too diversified
        "one_namer": {"AAA"},                          # too concentrated
        "active_a": {"AAA", "BBB"},
        "active_b": {"AAA", "BBB"},
    }
    peers, contributing = coownership_peers(
        edges, manager_min_holdings=2, manager_max_holdings=3,
        top_k=5, min_shared_managers=2,
    )
    # Only the two active managers contribute (index_fund holds 4 > max, one_namer holds 1 < min).
    assert contributing == 2
    aaa = {p["peer"]: p for p in peers["AAA"]}
    assert aaa["BBB"]["shared_managers"] == 2
