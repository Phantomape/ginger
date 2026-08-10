from __future__ import annotations

import importlib
import json
import math
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "quant" / "experiments"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(EXPERIMENTS))
sys.path.insert(0, str(SCRIPTS))

preflight = importlib.import_module(
    "exp_20260721_003_sp1500_constituent_addition_preflight"
)
from experiment_fingerprint import infer_fingerprint  # noqa: E402


def _business_days(start: str, end: str) -> list[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    rows: list[str] = []
    while current <= final:
        if current.weekday() < 5:
            rows.append(current.isoformat())
        current += timedelta(days=1)
    return rows


def _warehouse(
    path: Path,
    *,
    tickers: tuple[str, ...],
    dates: list[str],
    amplitudes: dict[str, float],
) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "create table ohlcv (ticker text, date text, open real, high real, low real, close real, volume real)"
        )
        for ticker in tickers:
            close = 100.0
            amplitude = amplitudes.get(ticker, 0.01)
            for index, day in enumerate(dates):
                # Alternating log returns give deterministic non-zero sample sigma.
                if index:
                    close *= math.exp(amplitude if index % 2 else -amplitude)
                connection.execute(
                    "insert into ohlcv values (?, ?, ?, ?, ?, ?, ?)",
                    (ticker, day, close, close, close, close, 1_000_000.0),
                )
        connection.commit()
    return path


def _release_html(rows: list[tuple[str, str, str, str, str, str]]) -> str:
    body = "\n".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"""
    <html><body><table>
      <tr>
        <th>Effective Date</th><th>Index Name</th><th>Action</th>
        <th>Company Name</th><th>Ticker</th><th>GICS Sector</th>
      </tr>
      {body}
    </table></body></html>
    """


def _parsed_release(
    rows: list[tuple[str, str, str, str, str, str]],
    *,
    url: str,
    published: str,
) -> list[dict]:
    return preflight.parse_release_html(
        _release_html(rows),
        source_url=url,
        published_date=published,
        title="Synthetic Set to Join S&P fixture",
    )


def test_archive_and_release_tables_are_strict_and_date_only():
    archive = """
    <ul>
      <li class="wd_item">
        <div class="wd_date">March&nbsp;24,2025 9:30 AM EDT</div>
        <div class="wd_title"><a href="/release-a">Alpha Set to Join S&amp;P 500</a></div>
      </li>
      <li class="wd_item">
        <div class="wd_date">March 25, 2025</div>
        <div class="wd_title"><a href="/other">Unrelated index note</a></div>
      </li>
    </ul>
    """
    releases = preflight.parse_archive_html(
        archive,
        archive_url="https://press.spglobal.com/index.php?s=2429&year=2025",
    )
    assert releases == [
        {
            "published_date": "2025-03-24",
            "publication_precision": "date_only",
            "availability_rule": "publication_date_conservative_eod",
            "title": "Alpha Set to Join S&P 500",
            "source_url": "https://press.spglobal.com/release-a",
        }
    ]

    rows = _parsed_release(
        [
            ("March 31,2025", "S&P 500", "Addition", "Alpha", "AAA", "Information Technology"),
            ("March 31,2025", "S&P MidCap 400", "Deletion", "Beta", "BBB", "Industrials"),
            ("March 31,2025", "S&P SmallCap 600", "Add", "Not exact", "CCC", "Healthcare"),
            ("March 31,2025", "S&P 100", "Addition", "Wrong index", "DDD", "Financials"),
        ],
        url="https://press.spglobal.com/release-a",
        published="March 24,2025",
    )
    assert [(row["action"], row["index_tier"], row["ticker"]) for row in rows] == [
        ("Addition", 500, "AAA"),
        ("Deletion", 400, "BBB"),
    ]
    assert all(row["published_at"] is None for row in rows)
    assert all(row["publication_precision"] == "date_only" for row in rows)


def test_migration_exclusion_date_clock_and_inverse_vol_budget(tmp_path: Path):
    dates = _business_days("2025-04-21", "2025-06-09")
    warehouse = _warehouse(
        tmp_path / "warehouse.sqlite",
        tickers=("AAA", "BBB", "CCC", "DDD"),
        dates=dates,
        amplitudes={"AAA": 0.005, "BBB": 0.01, "CCC": 0.02, "DDD": 0.04},
    )
    # A huge entry-day price is present in SQLite. The risk query must exclude it.
    with sqlite3.connect(warehouse) as connection:
        connection.execute(
            "update ohlcv set close=1000000 where ticker='BBB' and date='2025-06-02'"
        )
        connection.commit()

    first = _parsed_release(
        [
            ("June 9, 2025", "S&P 500", "Addition", "Tier migrant", "AAA", "Information Technology"),
            ("June 9, 2025", "S&P MidCap 400", "Addition", "Beta", "BBB", "Information Technology"),
            ("June 9, 2025", "S&P SmallCap 600", "Addition", "Gamma", "CCC", "Healthcare"),
        ],
        url="https://press.spglobal.com/release-one",
        published="2025-06-01",
    )
    second = _parsed_release(
        [
            ("June 9, 2025", "S&P MidCap 400", "Deletion", "Tier migrant", "AAA", "Information Technology"),
            ("June 9, 2025", "S&P 500", "Addition", "Delta", "DDD", "Industrials"),
        ],
        url="https://press.spglobal.com/release-two",
        published="2025-06-01",
    )

    artifact = preflight.build_preflight(first + second, warehouse_paths=[warehouse])
    mid = artifact["windows"]["mid_weak"]

    assert mid["counts"] == {
        "all_additions": 4,
        "migrations": 1,
        "net_new": 3,
        "eligible": 3,
        "clocks": 1,
        "unique_ticker": 3,
    }
    assert mid["failure_reasons"]["sp1500_tier_migration_same_event_clock"] == 1
    assert mid["counts"]["clocks"] == 1  # two URLs on one calendar date merge
    sigmas = {}
    risk_details = {}
    for ticker in ("BBB", "CCC", "DDD"):
        sigma, detail = preflight.strict_prepublication_sigma(
            [warehouse], ticker, "2025-06-01"
        )
        assert sigma is not None
        sigmas[ticker] = sigma
        risk_details[ticker] = detail
    allocations = preflight.inverse_vol_weights(sigmas)
    assert sum(row["risk_weight"] for row in allocations.values()) == pytest.approx(1.0)
    contributions = [row["risk_contribution"] for row in allocations.values()]
    assert max(contributions) == pytest.approx(min(contributions))
    weights = {ticker: row["risk_weight"] for ticker, row in allocations.items()}
    assert weights["BBB"] > weights["CCC"] > weights["DDD"]
    assert all(detail["last_close_date"] == "2025-05-30" for detail in risk_details.values())
    assert all(detail["return_count"] == 20 for detail in risk_details.values())
    assert preflight._schedule("2025-06-01", "2025-06-09", dates) == (
        "2025-06-02",
        "2025-06-06",
        None,
    )


def test_entry_exit_and_window_lifecycle_fail_closed(tmp_path: Path):
    dates = _business_days("2025-09-01", "2025-10-31")
    warehouse = _warehouse(
        tmp_path / "warehouse.sqlite",
        tickers=("EARLY", "CROSS"),
        dates=dates,
        amplitudes={"EARLY": 0.01, "CROSS": 0.02},
    )
    rows = []
    rows += _parsed_release(
        [("October 20, 2025", "S&P 500", "Addition", "Too early", "EARLY", "Industrials")],
        url="https://press.spglobal.com/release-early",
        published="2025-10-17",  # Friday: next session equals effective date
    )
    rows += _parsed_release(
        [("October 27, 2025", "S&P 500", "Addition", "Cross window", "CROSS", "Industrials")],
        url="https://press.spglobal.com/release-cross",
        published="2025-10-21",  # mid window, but pre-effective exit is after it
    )

    artifact = preflight.build_preflight(rows, warehouse_paths=[warehouse])
    mid = artifact["windows"]["mid_weak"]
    assert mid["counts"]["net_new"] == 2
    assert mid["counts"]["eligible"] == 0
    assert mid["failure_reasons"] == {
        "entry_not_before_exit": 1,
        "lifecycle_outside_standard_window": 1,
    }


def test_artifact_contract_has_no_outcome_query_or_live_promotion(tmp_path: Path):
    dates = _business_days("2025-04-21", "2025-06-09")
    warehouse = _warehouse(
        tmp_path / "warehouse.sqlite",
        tickers=("AAA",),
        dates=dates,
        amplitudes={"AAA": 0.01},
    )
    rows = _parsed_release(
        [("June 9, 2025", "S&P 500", "Addition", "Alpha", "AAA", "Technology")],
        url="https://press.spglobal.com/release-a",
        published="2025-06-01",
    )
    artifact = preflight.build_preflight(rows, warehouse_paths=[warehouse])

    assert artifact["source_contract_authorized_for_investment_strategy"] is False
    assert artifact["publication_clock_provenance_verified"] is False
    assert artifact["pit_candidate"] is False
    assert artifact["post_manifest_date_price_or_return_data_read"] is False
    assert artifact["post_publication_price_or_return_data_read"] is None
    assert artifact["post_publication_read_status"] == "unknown_due_unverified_manifest_clock"
    assert artifact["outcome_reads_performed"] is False
    assert artifact["overall_passed"] is False
    assert artifact["decision"] == "source_contract_blocked_do_not_read_outcomes"
    assert artifact["trade_enabled"] is False
    assert artifact["candidate_eligible"] is False
    assert artifact["orders"] == []
    assert artifact["strategy_behavior_changed"] is False
    query_text = " ".join(
        " ".join(item.get("selected_columns", []))
        + " "
        + str(item.get("predicate", ""))
        for item in artifact["outcome_blind_query_contract"]
    ).casefold()
    assert "open" not in query_text
    assert "forward" not in query_text
    assert "return" not in query_text
    assert "pnl" not in query_text
    assert "date < supplied_manifest_date" in query_text
    persisted = json.dumps(artifact, sort_keys=True)
    assert "release-a" not in persisted
    assert "https://press.spglobal.com" not in persisted
    assert '"AAA"' not in persisted
    assert '"legs"' not in persisted
    assert '"unique_tickers":' not in persisted


def test_fingerprint_is_narrow_to_constituent_change_lifecycle():
    positive = infer_fingerprint(
        "sp1500_constituent_addition_forced_flow",
        "sp1500_addition_announcement_to_pre_effective_forced_flow_lifecycle",
    )
    assert positive["data_source"] == "sp_index_constituent_change"
    assert positive["gate_shape"] == "index_inclusion_forced_flow_lifecycle"

    family_only = infer_fingerprint("sp1500_constituent_addition_forced_flow")
    assert family_only["data_source"] == "sp_index_constituent_change"
    assert family_only["gate_shape"] == "index_inclusion_forced_flow_lifecycle"

    ordinary = infer_fingerprint("S&P index OHLCV addition")
    assert ordinary["data_source"] != "sp_index_constituent_change"
    assert ordinary["gate_shape"] != "index_inclusion_forced_flow_lifecycle"


def test_run_requires_explicit_local_injection_and_does_not_persist_html(tmp_path: Path):
    with pytest.raises(ValueError, match="live network fetch is disabled"):
        preflight.run_preflight(
            warehouse_paths=[],
            output_path=tmp_path / "should-not-exist.json",
        )
    assert not (tmp_path / "should-not-exist.json").exists()
