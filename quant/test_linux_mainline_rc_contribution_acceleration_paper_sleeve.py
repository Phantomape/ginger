from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import shutil

import pytest

from quant.constants import ROUND_TRIP_COST_PCT
from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET
from quant.linux_mainline_rc_contribution_acceleration_paper_sleeve import (
    DOMAIN_TO_ISSUER,
    DEFAULT_SOURCE_BUNDLE_DIR,
    HOLD_SESSIONS,
    MAX_ACTIVE_POSITIONS,
    PAPER_NOTIONAL_USD,
    LinuxMainlineRCContractError,
    build_linux_mainline_rc_contribution_acceleration_historical_trades,
    build_linux_mainline_rc_contribution_acceleration_snapshot,
    evaluate_linux_mainline_rc_contribution_acceleration_decisions,
    load_linux_mainline_rc_source_bundle,
    normalise_linux_mainline_rc_contribution_rows,
    normalise_linux_mainline_rc_tag_rows,
)


def _sha(value: int) -> str:
    return f"{value:040x}"


def _tags(count: int = 9, *, start: str = "2025-01-05") -> list[dict[str, object]]:
    first = date.fromisoformat(start)
    rows = []
    for index in range(count):
        tagger = datetime.combine(
            first + timedelta(days=7 * index),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).replace(hour=20)
        rows.append(
            {
                "tag_name": f"v6.20-rc{index + 1}",
                "tag_object_type": "tag",
                "tag_object_sha": _sha(1000 + index),
                "tag_commit_sha": _sha(2000 + index),
                "tagger_at": tagger.isoformat().replace("+00:00", "Z"),
                "signature_verified": True,
                "prior_tag_name": "v6.19" if index == 0 else f"v6.20-rc{index}",
                "prior_tag_object_sha": _sha(999 + index),
                "prior_tag_commit_sha": _sha(1999 + index),
            }
        )
    return rows


def _commit(
    tag: dict[str, object],
    *,
    index: int,
    email: str,
    ticker: str,
) -> dict[str, object]:
    tagger = datetime.fromisoformat(str(tag["tagger_at"]).replace("Z", "+00:00"))
    return {
        **tag,
        "commit_sha": _sha(10000 + index),
        "parent_count": 1,
        "author_email": email,
        "author_domain": email.rsplit("@", 1)[1],
        "authored_at": (tagger - timedelta(days=2)).isoformat(),
        "committed_at": (tagger - timedelta(days=1)).isoformat(),
        "ticker": ticker,
        "mapping_effective_from": "2024-01-01",
        "mapping_provenance": DOMAIN_TO_ISSUER[email.rsplit("@", 1)[1]][
            "provenance"
        ],
    }


def _business_bars(start: str, count: int):
    day = date.fromisoformat(start)
    rows = []
    while len(rows) < count:
        if day.weekday() < 5:
            base = 100.0 + len(rows) * 0.2
            rows.append(
                {
                    "date": day.isoformat(),
                    "open": base,
                    "high": base + 1.0,
                    "low": base - 1.0,
                    "close": base + 0.1,
                }
            )
        day += timedelta(days=1)
    return rows


def test_exact_raw_domain_map_and_acquisition_provenance_are_frozen():
    assert DOMAIN_TO_ISSUER["google.com"]["ticker"] == "GOOG"
    assert DOMAIN_TO_ISSUER["redhat.com"] == {
        "ticker": "IBM",
        "effective_from": "2024-01-01",
        "provenance": "IBM acquired Red Hat 2019-07-09",
    }
    assert DOMAIN_TO_ISSUER["vmware.com"]["ticker"] == "AVGO"
    assert DOMAIN_TO_ISSUER["linutronix.de"]["ticker"] == "INTC"


def test_complete_rc_sequence_preserves_zero_interval_in_prior_eight():
    tags = _tags()
    rows = []
    commit_index = 0
    # The third prior RC has no AMD contribution and must remain an explicit 0.
    for tag_index in (0, 1, 3, 4, 5, 6, 7):
        rows.append(
            _commit(
                tags[tag_index],
                index=commit_index,
                email="engineer@amd.com",
                ticker="AMD",
            )
        )
        commit_index += 1
    for _ in range(3):
        rows.append(
            _commit(
                tags[8],
                index=commit_index,
                email="engineer@amd.com",
                ticker="AMD",
            )
        )
        commit_index += 1
    result = evaluate_linux_mainline_rc_contribution_acceleration_decisions(
        rows,
        rc_tag_rows=tags,
        as_of="2025-03-10",
        require_frozen_sequence=False,
    )
    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]
    assert decision["prior_eight_rc_counts"] == [1, 1, 0, 1, 1, 1, 1, 1]
    assert decision["prior_eight_rc_median"] == 1.0
    assert decision["current_contribution_count"] == 3
    assert decision["contribution_acceleration"] == 2.0


def test_omitted_rc_tag_breaks_authoritative_predecessor_sequence():
    tags = _tags()
    with pytest.raises(LinuxMainlineRCContractError, match="predecessor discontinuity"):
        normalise_linux_mainline_rc_tag_rows(
            [*tags[:2], *tags[3:]], require_frozen_sequence=False
        )


def test_threshold_strict_acceleration_and_top_three_ranking():
    tags = _tags()
    rows = []
    index = 0
    for ticker, email, count in (
        ("AMD", "dev@amd.com", 6),
        ("NVDA", "dev@nvidia.com", 5),
        ("INTC", "dev@intel.com", 4),
        ("MSFT", "dev@microsoft.com", 3),
        ("ORCL", "dev@oracle.com", 2),
    ):
        for _ in range(count):
            rows.append(_commit(tags[-1], index=index, email=email, ticker=ticker))
            index += 1
    result = evaluate_linux_mainline_rc_contribution_acceleration_decisions(
        rows,
        rc_tag_rows=tags,
        as_of="2025-03-10",
        require_frozen_sequence=False,
    )
    assert [row["ticker"] for row in result["eligible_rows"]] == [
        "AMD",
        "NVDA",
        "INTC",
        "MSFT",
    ]
    assert [row["ticker"] for row in result["decisions"]] == [
        "AMD",
        "NVDA",
        "INTC",
    ]


def test_h20_next_strictly_later_open_costs_and_snapshot_parity():
    tags = _tags(start="2025-01-05")
    rows = [
        _commit(tags[-1], index=index, email="dev@amd.com", ticker="AMD")
        for index in range(3)
    ]
    bars = _business_bars("2024-12-01", 100)
    market = {"SPY": bars, "AMD": bars}
    replay = build_linux_mainline_rc_contribution_acceleration_historical_trades(
        source_rows=rows,
        rc_tag_rows=tags,
        ohlcv_by_ticker=market,
        start="2025-02-20",
        end="2025-04-15",
        require_frozen_sequence=False,
    )
    assert replay["trade_enabled"] is False
    assert len(replay["trades"]) == 1
    trade = replay["trades"][0]
    assert trade["entry_date"] == "2025-03-03"
    assert trade["exit_date"] == "2025-03-28"
    assert trade["hold_sessions_realized"] == HOLD_SESSIONS
    assert trade["paper_notional_usd"] == PAPER_NOTIONAL_USD
    assert trade["round_trip_cost_pct"] == ROUND_TRIP_COST_PCT
    assert trade["entry_slippage_bps"] == SLIPPAGE_BPS_ENTRY
    assert trade["exit_slippage_bps"] == SLIPPAGE_BPS_TARGET
    assert trade["target_price"] > trade["entry_price"]
    assert trade["trade_enabled"] is False
    assert trade["alters_orders"] is False

    snapshot = build_linux_mainline_rc_contribution_acceleration_snapshot(
        source_rows=rows,
        rc_tag_rows=tags,
        ohlcv_by_ticker=market,
        as_of="2025-04-15",
        start="2025-02-20",
        require_frozen_sequence=False,
    )
    assert snapshot["trade_enabled"] is False
    assert snapshot["execution_envelope"]["max_concurrent_positions"] == MAX_ACTIVE_POSITIONS
    assert snapshot["execution_envelope"]["one_active_position_per_ticker"] is True
    assert [row["decision_id"] for row in snapshot["replay"]["window_decisions"]] == [
        row["decision_id"] for row in replay["window_decisions"]
    ]


def test_unverified_moved_future_ambiguous_and_natural_key_conflicts_fail_closed():
    tags = _tags()
    base = _commit(tags[-1], index=1, email="dev@amd.com", ticker="AMD")
    with pytest.raises(LinuxMainlineRCContractError, match="unverified"):
        normalise_linux_mainline_rc_contribution_rows(
            [{**base, "signature_verified": False}]
        )
    with pytest.raises(LinuxMainlineRCContractError, match="mapping ambiguity"):
        normalise_linux_mainline_rc_contribution_rows([{**base, "ticker": "NVDA"}])
    with pytest.raises(LinuxMainlineRCContractError, match="future-visible"):
        normalise_linux_mainline_rc_contribution_rows(
            [{**base, "committed_at": "2025-04-01T00:00:00Z"}]
        )
    with pytest.raises(LinuxMainlineRCContractError, match="natural-key conflict"):
        normalise_linux_mainline_rc_contribution_rows(
            [base, {**base, "authored_at": "2025-02-25T00:00:00Z"}]
        )
    moved = {**base, "tag_object_sha": _sha(55555)}
    with pytest.raises(LinuxMainlineRCContractError, match="moved tag conflict"):
        normalise_linux_mainline_rc_contribution_rows([base, moved])


def test_one_active_position_per_ticker_rejects_overlapping_rc():
    tags = _tags(10)
    rows = []
    for offset, tag in enumerate(tags[-2:]):
        rows.extend(
            _commit(tag, index=offset * 10 + index, email="dev@amd.com", ticker="AMD")
            for index in range(3 + offset)
        )
    bars = _business_bars("2024-12-01", 110)
    replay = build_linux_mainline_rc_contribution_acceleration_historical_trades(
        source_rows=rows,
        rc_tag_rows=tags,
        ohlcv_by_ticker={"SPY": bars, "AMD": bars},
        start="2025-02-20",
        end="2025-04-30",
        require_frozen_sequence=False,
    )
    assert len(replay["window_decisions"]) == 2
    assert len(replay["trade_candidates"]) == 1
    assert replay["reject_totals"] == {"same_ticker_active": 1}


def test_materialized_gzip_bundle_roundtrip_and_hash_fail_closed(tmp_path):
    bundle = load_linux_mainline_rc_source_bundle()
    assert len(bundle["tags"]) == 102
    assert len(bundle["commit_rows"]) == 77060
    assert bundle["crosscheck"]["overlap_count"] == 80
    assert bundle["crosscheck"]["official_only_count"] == 22
    assert bundle["manifest"]["signature_audit"]["selected_rc_tag_count"] == 102
    assert bundle["manifest"]["signature_audit"]["verified_endpoint_count"] == 117
    commit_meta = bundle["manifest"]["files"]["mapped_nonmerge_commits.jsonl.gz"]
    assert commit_meta["compression"] == "gzip"
    assert commit_meta["gzip_mtime"] == 0
    assert Path(DEFAULT_SOURCE_BUNDLE_DIR, "mapped_nonmerge_commits.jsonl.gz").stat().st_size < commit_meta["uncompressed_bytes"]

    copied = tmp_path / "bundle"
    shutil.copytree(DEFAULT_SOURCE_BUNDLE_DIR, copied)
    commit_path = copied / "mapped_nonmerge_commits.jsonl.gz"
    payload = bytearray(commit_path.read_bytes())
    payload[-16] ^= 1
    commit_path.write_bytes(payload)
    with pytest.raises(LinuxMainlineRCContractError, match="hash mismatch"):
        load_linux_mainline_rc_source_bundle(copied)
