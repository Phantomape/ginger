from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta

import pytest

from quant import fed_h8_bank_size_relative_value_paper_sleeve as sleeve


def _table(
    number: int,
    bank_size: str,
    *,
    other_deposits: float,
    ci_loans: float,
    units: str = "Seasonally adjusted, billions of dollars.",
    duplicate_other_deposits: bool = False,
    weekly_value_count: int = 4,
) -> str:
    duplicate = (
        f"<tr><th>36</th><td>Other deposits</td><td>{other_deposits}</td></tr>"
        if duplicate_other_deposits
        else ""
    )

    def weekly_values(latest: float, step: float) -> str:
        values = [latest - step * offset for offset in reversed(range(weekly_value_count))]
        return "".join(f"<td>{value:,.1f}</td>" for value in values)

    title = (
        f"Table {number}. Assets and Liabilities of {bank_size} "
        "Domestically Chartered Commercial Banks in the United States"
    )
    return f"""
      <h4>{title}</h4>
      <div data-table-popout class="data-table" id="h8table{number}">
      <span class="tableunit">{units}</span>
      <table class="pubtables" id="h8t{number}" title="{title}">
        <thead>
          <tr><th colspan="2">Account</th><th colspan="4">Week ending</th></tr>
          <tr><th colspan="2"></th><th>Jan 08</th><th>Jan 15</th>
              <th>Jan 22</th><th>Jan 29</th></tr>
        </thead>
        <tbody>
          <tr><th>Assets</th></tr>
          <tr><th>10</th><td>Commercial and industrial loans</td>
              {weekly_values(ci_loans, 5.0)}</tr>
          <tr><th>Liabilities</th></tr>
          <tr><th>36</th><td>Other deposits</td>
              {weekly_values(other_deposits, 10.0)}</tr>
          {duplicate}
        </tbody>
      </table>
      </div>
    """


def _html(
    release_date: str,
    *,
    large_other: float = 10_000.0,
    large_ci: float = 1_500.0,
    small_other: float = 5_000.0,
    small_ci: float = 750.0,
    include_large: bool = True,
    include_small: bool = True,
    large_units: str = "Seasonally adjusted, billions of dollars.",
    duplicate_small_other: bool = False,
    small_weekly_value_count: int = 4,
) -> str:
    human_date = date.fromisoformat(release_date).strftime("%B %d, %Y").replace(
        " 0", " "
    )
    tables: list[str] = []
    if include_large:
        tables.append(
            _table(
                6,
                "Large",
                other_deposits=large_other,
                ci_loans=large_ci,
                units=large_units,
            )
        )
    # A distractor proves table number and bank-size identity are both fixed.
    tables.append(
        _table(
            7,
            "Large",
            other_deposits=large_other + 999,
            ci_loans=large_ci + 999,
        )
    )
    if include_small:
        tables.append(
            _table(
                8,
                "Small",
                other_deposits=small_other,
                ci_loans=small_ci,
                duplicate_other_deposits=duplicate_small_other,
                weekly_value_count=small_weekly_value_count,
            )
        )
    return f"""
      <!doctype html>
      <html><head><title>Federal Reserve H.8</title></head><body>
        <h1>Assets and Liabilities of Commercial Banks in the United States - H.8</h1>
        <p>Release Date: {human_date}</p>
        {''.join(tables)}
      </body></html>
    """


def _parse(
    release_date: str,
    **values: float,
) -> dict:
    html = _html(release_date, **values)
    source_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    return sleeve.parse_h8_release_html(
        html,
        release_date,
        f"https://www.federalreserve.gov/releases/h8/{release_date.replace('-', '')}/",
        source_hash,
    )


def _weekdays(start: str, end: str) -> list[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    result: list[str] = []
    while current <= final:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def test_policy_constants_are_fixed_and_default_off() -> None:
    assert sleeve.TRADE_ENABLED is False
    assert sleeve.LAG_RELEASES == 4
    assert sleeve.NOTIONAL_USD_PER_LEG == 4_000.0
    assert sleeve.ROUND_TRIP_COST_PCT_PER_LEG == 0.0035
    assert sleeve.MAX_CONCURRENT_PAIRS == 1
    assert sleeve.TICKERS == ("KRE", "KBE")
    assert sleeve.TABLE_SPECS["large"]["table_number"] == 6
    assert sleeve.TABLE_SPECS["small"]["table_number"] == 8
    assert sleeve.FIELD_SPECS["other_deposits"]["line_number"] == 36
    assert sleeve.FIELD_SPECS["commercial_and_industrial_loans"]["line_number"] == 10


def test_parser_uses_rightmost_values_from_only_tables_6_and_8() -> None:
    release = _parse(
        "2025-01-31",
        large_other=10_100.0,
        large_ci=1_510.0,
        small_other=5_080.0,
        small_ci=765.0,
    )
    assert release["schema_version"] == sleeve.H8_RELEASE_SCHEMA_VERSION
    assert release["release_date"] == "2025-01-31"
    assert release["latest_values"] == {
        "large": {
            "other_deposits": 10_100.0,
            "commercial_and_industrial_loans": 1_510.0,
        },
        "small": {
            "other_deposits": 5_080.0,
            "commercial_and_industrial_loans": 765.0,
        },
    }
    assert release["tables"]["large"]["fields"]["other_deposits"][
        "reported_value_count"
    ] == 4
    assert release["tables"]["large"]["fields"]["other_deposits"][
        "reported_numeric_value_count"
    ] == 4
    assert release["tables"]["large"]["fields"]["other_deposits"][
        "weekly_value_count"
    ] == 4
    assert release["tables"]["large"]["fields"]["other_deposits"][
        "latest_value_selection"
    ] == "rightmost_of_four_terminal_weekly_numeric_cells"
    assert release["tables"]["small"]["table_number"] == 8
    assert release["tables"]["large"]["table_id"] == "h8t6"
    assert release["tables"]["small"]["table_id"] == "h8t8"
    assert release["trade_enabled"] is False


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (lambda html: html, "source_sha256_mismatch"),
        (
            lambda html: html.replace("Release Date: January 31, 2025", "Release Date: January 30, 2025"),
            "html_release_date_mismatch",
        ),
        (
            lambda html: html.replace("Table 8.", "Table 9."),
            "expected_one_table_8_found_0",
        ),
        (
            lambda html: html.replace('id="h8t6"', 'id="h8t99"', 1),
            "expected_one_table_6_found_0",
        ),
        (
            lambda html: html.replace("Seasonally adjusted, billions of dollars.", "Not seasonally adjusted, millions.", 1),
            "table_6_units_or_adjustment_mismatch",
        ),
        (
            lambda html: html.replace("<th colspan=\"4\">Week ending</th>", "<th colspan=\"4\">Recent values</th>", 1),
            "table_6_missing_four_week_ending_block",
        ),
    ],
)
def test_parser_fails_closed_on_hash_date_table_and_units(
    mutator, reason: str
) -> None:
    original = _html("2025-01-31")
    html = mutator(original)
    source_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if reason != "source_sha256_mismatch":
        source_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    else:
        source_hash = "0" * 64
    with pytest.raises(sleeve.H8SchemaError, match=reason):
        sleeve.parse_h8_release_html(
            html,
            "2025-01-31",
            "https://www.federalreserve.gov/releases/h8/20250131/",
            source_hash,
        )


def test_parser_rejects_nonofficial_url_and_ambiguous_required_row() -> None:
    html = _html("2025-01-31", duplicate_small_other=True)
    source_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    with pytest.raises(sleeve.H8SchemaError, match="non_official_h8_source_url"):
        sleeve.parse_h8_release_html(
            html,
            "2025-01-31",
            "https://example.com/releases/h8/20250131/",
            source_hash,
        )
    with pytest.raises(
        sleeve.H8SchemaError,
        match="expected_one_other_deposits_row_found_2",
    ):
        sleeve.parse_h8_release_html(
            html,
            "2025-01-31",
            "https://www.federalreserve.gov/releases/h8/20250131/",
            source_hash,
        )


def test_parser_rejects_fewer_than_four_terminal_weekly_cells() -> None:
    html = _html("2025-01-31", small_weekly_value_count=3)
    source_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    with pytest.raises(
        sleeve.H8SchemaError,
        match="insufficient_terminal_weekly_cells_for_other_deposits",
    ):
        sleeve.parse_h8_release_html(
            html,
            "2025-01-31",
            "https://www.federalreserve.gov/releases/h8/20250131/",
            source_hash,
        )


def test_signal_matches_locked_two_field_log_growth_formula_and_direction() -> None:
    lagged = _parse(
        "2025-01-03",
        large_other=10_000.0,
        large_ci=2_000.0,
        small_other=5_000.0,
        small_ci=1_000.0,
    )
    current = _parse(
        "2025-01-31",
        large_other=10_100.0,
        large_ci=1_980.0,
        small_other=5_150.0,
        small_ci=1_040.0,
    )
    signal = sleeve.compute_h8_signal(current, lagged)
    expected = (
        math.log(5_150.0 / 5_000.0)
        - math.log(10_100.0 / 10_000.0)
        + math.log(1_040.0 / 1_000.0)
        - math.log(1_980.0 / 2_000.0)
    )
    assert signal["signal"] == pytest.approx(expected)
    assert signal["direction"] == "long_kre_short_kbe"
    assert signal["long_ticker"] == "KRE"
    assert signal["short_ticker"] == "KBE"
    assert signal["lag_releases"] == 4
    assert signal["trade_enabled"] is False

    reverse = sleeve.compute_h8_signal(lagged, _parse(
        "2024-12-06",
        large_other=9_000.0,
        large_ci=1_500.0,
        small_other=5_500.0,
        small_ci=1_200.0,
    ))
    assert reverse["signal"] < 0
    assert reverse["direction"] == "long_kbe_short_kre"
    assert reverse["long_ticker"] == "KBE"
    assert reverse["short_ticker"] == "KRE"


def test_weekly_builder_uses_exact_i_minus_4_and_strict_next_opens() -> None:
    release_dates = [
        "2025-01-03",
        "2025-01-10",
        "2025-01-17",
        "2025-01-24",
        "2025-01-31",
        "2025-02-07",
    ]
    releases = [
        _parse(
            day,
            large_other=10_000.0 + index * 20,
            large_ci=2_000.0 + index * 5,
            small_other=5_000.0 + index * 30,
            small_ci=1_000.0 + index * 8,
        )
        for index, day in enumerate(release_dates)
    ]
    sessions = _weekdays("2025-01-02", "2025-02-11")
    decisions = sleeve.build_weekly_pair_decisions(reversed(releases), sessions)

    assert len(decisions) == 2
    first, second = decisions
    assert first["release_date"] == "2025-01-31"
    assert first["lag4_release_date"] == "2025-01-03"
    assert first["entry_date"] == "2025-02-03"
    assert first["entry_date"] > first["release_date"]
    assert first["next_release_date"] == "2025-02-07"
    assert first["exit_date"] == "2025-02-10"
    assert first["status"] == "settled"
    assert first["exit_date"] == second["entry_date"]
    assert second["lag4_release_date"] == "2025-01-10"
    assert second["next_release_date"] is None
    assert second["exit_date"] is None
    assert second["status"] == "open_awaiting_next_release"
    assert {leg["side"] for leg in first["legs"]} == {"long", "short"}
    assert {leg["paper_notional_usd"] for leg in first["legs"]} == {4_000.0}
    assert first["round_trip_cost_usd_pair"] == pytest.approx(28.0)
    assert first["trade_enabled"] is False


def test_builder_fails_closed_on_release_gap_duplicate_and_bad_session() -> None:
    dates = [
        "2025-01-03",
        "2025-01-10",
        "2025-01-17",
        "2025-01-31",  # missing weekly release
        "2025-02-07",
    ]
    releases = [_parse(day) for day in dates]
    with pytest.raises(
        sleeve.H8SchemaError,
        match="non_contiguous_weekly_release_sequence",
    ):
        sleeve.build_weekly_pair_decisions(releases, ["2025-02-10"])

    valid = [_parse("2025-01-03"), _parse("2025-01-10")]
    with pytest.raises(sleeve.H8SchemaError, match="duplicate_release_date"):
        sleeve.build_weekly_pair_decisions([valid[0], valid[0]], [])
    with pytest.raises(
        sleeve.H8SchemaError,
        match="weekend_cannot_be_regular_session",
    ):
        sleeve.build_weekly_pair_decisions(valid, ["2025-01-11"])


def test_compute_fails_closed_on_missing_field_and_wrong_lag_span() -> None:
    lagged = _parse("2025-01-03")
    current = _parse("2025-01-31")
    broken = {
        **current,
        "latest_values": {
            **current["latest_values"],
            "small": {
                "other_deposits": current["latest_values"]["small"]["other_deposits"]
            },
        },
    }
    with pytest.raises(
        sleeve.H8SchemaError,
        match="current_small_commercial_and_industrial_loans_invalid",
    ):
        sleeve.compute_h8_signal(broken, lagged)

    adjacent = _parse("2025-01-24")
    with pytest.raises(sleeve.H8SchemaError, match="lag4_release_span_invalid"):
        sleeve.compute_h8_signal(current, adjacent)
