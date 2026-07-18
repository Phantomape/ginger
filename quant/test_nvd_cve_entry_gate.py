import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from quant.entry_universe_ledger import membership_hash
from quant.nvd_cve_entry_gate import (
    EVENT_NAME,
    NvdEntryUniverseResolver,
    NvdSourceContractError,
    RULE_VERSION,
    SOURCE,
    VENDOR_MAP_HASH,
    build_nvd_cve_clusters,
    build_nvd_cve_entry_gate_snapshot,
    build_nvd_exclusion_index,
    fetch_nvd_change_history_archive,
    load_nvd_change_history_archive,
    normalize_nvd_initial_analysis_events,
    persist_daily_nvd_cve_entry_gate_snapshot,
    prepare_nvd_cve_entry_gate_snapshot,
)


def _change(
    cve_id: str,
    created: str,
    *,
    vendor: str = "microsoft",
    event_name: str = "Initial Analysis",
    action: str = "Added",
    detail_type: str = "CPE Configuration",
    part: str = "a",
) -> dict:
    return {
        "change": {
            "cveId": cve_id,
            "cveChangeId": f"change-{cve_id}-{created}",
            "eventName": event_name,
            "created": created,
            # This tempting clock must never affect normalization.
            "published": "2099-01-01T00:00:00.000Z",
            "details": [
                {
                    "action": action,
                    "type": detail_type,
                    "newValue": json.dumps(
                        {"nodes": [{"cpeMatch": [{"criteria": f"cpe:2.3:{part}:{vendor}:product:*:*:*:*:*:*:*"}]}]}
                    ),
                }
            ],
        }
    }


def _three_msft_changes() -> list[dict]:
    return [
        _change("CVE-2025-1001", "2025-01-06T09:00:00.000Z"),
        _change("CVE-2025-1002", "2025-01-07T10:00:00.000Z"),
        _change("CVE-2025-1003", "2025-01-08T20:00:00.000Z"),
    ]


def test_normalization_requires_exact_event_action_type_and_known_cpe_vendor():
    rows = [
        *_three_msft_changes()[:1],
        _change("CVE-2025-2001", "2025-01-06T10:00:00Z", event_name="Reanalysis"),
        _change("CVE-2025-2002", "2025-01-06T11:00:00Z", action="added"),
        _change("CVE-2025-2003", "2025-01-06T12:00:00Z", detail_type="CPE configuration"),
        _change("CVE-2025-2004", "2025-01-06T13:00:00Z", vendor="unknown_vendor"),
        _change("CVE-2025-2005", "2025-01-06T14:00:00Z", part="x"),
    ]

    events = normalize_nvd_initial_analysis_events(rows)

    assert [(row["cve_id"], row["ticker"]) for row in events] == [
        ("CVE-2025-1001", "MSFT")
    ]
    assert events[0]["created"] == "2025-01-06T09:00:00.000Z"
    assert events[0]["published_clock_used"] is False
    assert events[0]["reanalysis_used"] is False
    assert events[0]["vendor_map_hash"] == VENDOR_MAP_HASH


def test_distinct_cve_dedupe_and_third_created_timestamp_is_immutable_trigger():
    events = normalize_nvd_initial_analysis_events(
        [
            *_three_msft_changes(),
            # A second strict detail/change for an already-counted CVE cannot
            # manufacture the third distinct CVE.
            _change("CVE-2025-1002", "2025-01-07T12:00:00.000Z"),
            _change("CVE-2025-1004", "2025-01-09T08:00:00.000Z"),
        ]
    )

    clusters = build_nvd_cve_clusters(events)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["distinct_cve_count"] == 4
    assert cluster["trigger_cve_ids"] == [
        "CVE-2025-1001",
        "CVE-2025-1002",
        "CVE-2025-1003",
    ]
    assert cluster["trigger_cve_id"] == "CVE-2025-1003"
    assert cluster["trigger_created"] == "2025-01-08T20:00:00.000Z"


def test_next_session_five_day_index_and_resolver_provenance_match_backtester_contract():
    clusters = build_nvd_cve_clusters(
        normalize_nvd_initial_analysis_events(_three_msft_changes())
    )
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
        "2025-01-14",
        "2025-01-15",
        "2025-01-16",
    ]
    index = build_nvd_exclusion_index(
        clusters, sessions, source_manifest_sha256="a" * 64
    )

    assert index["clusters"][0]["activation_session"] == "2025-01-09"
    assert index["clusters"][0]["exclusion_sessions"] == [
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
        "2025-01-14",
        "2025-01-15",
    ]
    pre_open_cluster = [{**clusters[0], "trigger_created": "2025-01-08T13:00:00.000Z"}]
    assert build_nvd_exclusion_index(pre_open_cluster, sessions)["clusters"][0][
        "activation_session"
    ] == "2025-01-08"
    resolver = NvdEntryUniverseResolver(
        base_tickers=["MSFT", "AAPL"],
        exclusion_index=index,
        trading_sessions=sessions,
        source_manifest_sha256="a" * 64,
    )

    # Jan 8 signal fills Jan 9 and is excluded; Jan 7 fills Jan 8 and remains.
    assert resolver("2025-01-08") == {"AAPL"}
    assert resolver("2025-01-07") == {"AAPL", "MSFT"}
    resolved = resolver.resolve("2025-01-08")
    assert resolved["source"] == SOURCE
    assert resolved["membership_hash"] == membership_hash(["AAPL"])
    assert resolved["snapshot_as_of"] == "2025-01-08"
    assert resolved["provenance"]["entry_session"] == "2025-01-09"
    assert "next_trading_session fill" in resolved["provenance"]["fill_semantics"]
    assert resolved["provenance"]["trade_enabled"] is False
    assert resolver.metadata["rule_version"] == RULE_VERSION

    # Exercise BacktestEngine's actual provenance validator without building a
    # full engine or reading prices.
    from quant.backtester import BacktestEngine

    engine = object.__new__(BacktestEngine)
    engine.universe = ["AAPL", "MSFT"]
    engine.entry_universe_resolver = resolver
    eligible, provenance = BacktestEngine._core_entry_universe_as_of(
        engine, "2025-01-08"
    )
    assert eligible == {"AAPL"}
    assert provenance["membership_hash"] == membership_hash(["AAPL"])
    assert provenance["source"] == SOURCE


def test_archive_splits_120_day_chunks_paginates_and_detects_raw_tamper(tmp_path):
    calls: list[dict[str, list[str]]] = []
    sleeps: list[float] = []

    def fake_get(url: str, *, timeout: float) -> dict:
        assert timeout == 7.0
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        calls.append(query)
        assert query["eventName"] == [EVENT_NAME]
        start_index = int(query["startIndex"][0])
        # First 120-day chunk has three rows (two pages); the tail has one.
        chunk_is_first = query["changeStartDate"][0].startswith("2025-01-01")
        source = (
            [
                _change("CVE-2025-3001", "2025-01-02T00:00:00Z"),
                _change("CVE-2025-3002", "2025-01-03T00:00:00Z"),
                _change("CVE-2025-3003", "2025-01-04T00:00:00Z"),
            ]
            if chunk_is_first
            else [_change("CVE-2025-3004", "2025-05-02T00:00:00Z")]
        )
        page = source[start_index : start_index + 2]
        return {
            "resultsPerPage": len(page),
            "startIndex": start_index,
            "totalResults": len(source),
            "format": "NVD_CVEHistory",
            "version": "2.0",
            "timestamp": "2025-05-05T00:00:00.000Z",
            "cveChanges": page,
        }

    manifest = fetch_nvd_change_history_archive(
        start="2025-01-01",
        end="2025-05-05",
        archive_dir=tmp_path / "nvd",
        page_size=2,
        timeout=7.0,
        min_interval_seconds=0.25,
        http_get=fake_get,
        sleep_fn=sleeps.append,
    )

    assert manifest["query"]["event_name"] == EVENT_NAME
    assert manifest["chunk_count"] == 2
    assert manifest["page_count"] == 3
    assert manifest["total_results"] == 4
    first_end = datetime.fromisoformat(
        manifest["chunks"][0]["change_end_date"].replace("Z", "+00:00")
    )
    second_start = datetime.fromisoformat(
        manifest["chunks"][1]["change_start_date"].replace("Z", "+00:00")
    )
    assert second_start - first_end == timedelta(milliseconds=1)
    assert len(calls) == 3
    assert sleeps == [0.25, 0.25]
    assert len(load_nvd_change_history_archive(manifest)) == 4

    page_path = Path(manifest["manifest_path"]).parent / manifest["pages"][0]["file"]
    page_path.write_bytes(page_path.read_bytes() + b" ")
    with pytest.raises(NvdSourceContractError, match="raw page hash mismatch"):
        load_nvd_change_history_archive(manifest)


def test_daily_snapshot_reuses_cluster_rule_and_is_persistently_default_off(tmp_path):
    raw = _three_msft_changes()
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
        "2025-01-14",
        "2025-01-15",
    ]
    expected_events = normalize_nvd_initial_analysis_events(raw)
    expected_clusters = build_nvd_cve_clusters(expected_events)
    snapshot, stored = prepare_nvd_cve_entry_gate_snapshot(
        as_of_date="2025-01-08",
        existing_events=[],
        fetched_change_rows=raw,
        trading_sessions=sessions,
        source_manifest_sha256="b" * 64,
    )
    direct = build_nvd_cve_entry_gate_snapshot(
        as_of_date="2025-01-08",
        events=expected_events,
        trading_sessions=sessions,
        source_manifest_sha256="b" * 64,
    )

    assert stored == expected_events
    assert snapshot["clusters"] == expected_clusters == direct["clusters"]
    assert snapshot["excluded_tickers_for_next_session"] == ["MSFT"]
    assert snapshot["trade_enabled"] is False
    assert snapshot["strategy_behavior_changed"] is False
    assert snapshot["alters_orders"] is False

    persisted = persist_daily_nvd_cve_entry_gate_snapshot(
        today="20250108",
        repo_root=tmp_path,
        fetched_change_rows=raw,
        trading_sessions=sessions,
    )
    assert persisted["as_of_date"] == "2025-01-08"
    assert persisted["clusters"] == expected_clusters
    assert persisted["trade_enabled"] is False
    assert persisted["alters_live_orders"] is False
    assert Path(persisted["state_path"]).exists()
    assert Path(persisted["snapshot_path"]).exists()
    on_disk = json.loads(Path(persisted["snapshot_path"]).read_text(encoding="utf-8"))
    assert on_disk["trade_enabled"] is False
    assert on_disk["strategy_behavior_changed"] is False
