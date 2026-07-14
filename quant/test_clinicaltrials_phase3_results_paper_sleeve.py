from __future__ import annotations

import sys
from pathlib import Path

import pytest

QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import clinicaltrials_phase3_results_paper_sleeve as sleeve


def _history_payload(*, sponsor="Eli Lilly and Company", nct="NCT00000001", posted="2025-01-06"):
    return {
        "study": {
            "hasResults": True,
            "protocolSection": {
                "identificationModule": {"nctId": nct},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": sponsor}},
                "designModule": {"phases": ["PHASE3"]},
                "statusModule": {
                    "resultsFirstPostDateStruct": {"date": posted, "type": "ACTUAL"}
                },
            },
            "resultsSection": {"outcomeMeasuresModule": {}},
        },
        "history_version": 7,
        "source_url": f"https://clinicaltrials.gov/api/int/studies/{nct}/history/7",
        "raw_sha256": "a" * 64,
    }


def _bars(closes, start_day=1):
    return [
        {
            "Date": f"2025-01-{idx + start_day:02d}",
            "Open": close - 0.2,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
        }
        for idx, close in enumerate(closes)
    ]


def test_exact_fixed_sponsor_map_and_version_contract():
    assert len(sleeve.SPONSOR_TO_TICKER) == 12
    rows = sleeve.normalise_clinicaltrials_result_events([_history_payload()])
    assert rows[0]["ticker"] == "LLY"
    assert rows[0]["history_version"] == "7"
    assert rows[0]["raw_sha256"] == "a" * 64
    unknown = _history_payload(sponsor="Unregistered Sponsor", nct="NCT00000002")
    assert sleeve.normalise_clinicaltrials_result_events([unknown]) == []


def test_unversioned_historical_row_fails_closed():
    row = _history_payload()
    row.pop("history_version")
    assert sleeve.normalise_clinicaltrials_result_events([row]) == []


def test_estimated_first_post_date_fails_closed():
    row = _history_payload()
    row["study"]["protocolSection"]["statusModule"]["resultsFirstPostDateStruct"]["type"] = "ESTIMATED"
    assert sleeve.normalise_clinicaltrials_result_events([row]) == []


def test_history_change_parser_uses_public_result_module_only():
    payload = {
        "changes": [
            {"version": 40, "moduleLabels": ["Outcome Measures"]},
            {
                "version": 41,
                "moduleLabels": ["Outcome Measures (Results)"],
                "reviewNotPassed": True,
            },
            {"version": 42, "moduleLabels": ["Outcome Measures (Results)"]},
        ]
    }
    assert sleeve._history_versions(payload) == [40, 41, 42]
    assert sleeve._public_result_version_candidates(payload) == [42]


def test_price_confirmation_top1_and_replay_cost_contract():
    events = sleeve.normalise_clinicaltrials_result_events(
        [
            _history_payload(nct="NCT00000001", posted="2025-01-03"),
            _history_payload(sponsor="Novo Nordisk A/S", nct="NCT00000002", posted="2025-01-03"),
        ]
    )
    # Jan 3 issuer return: LLY +2%, NVO +1%, SPY flat -> LLY top1.
    ohlcv = {
        "SPY": _bars([100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]),
        "LLY": _bars([100, 100, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115]),
        "NVO": _bars([100, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]),
    }
    replay = sleeve.replay_clinicaltrials_phase3_results_paper_trades(
        events=events, ohlcv_by_ticker=ohlcv, start="2025-01-01", end="2025-01-16"
    )
    assert len(replay["trades"]) == 1
    trade = replay["trades"][0]
    assert trade["ticker"] == "LLY"
    assert trade["entry_date"] == "2025-01-04"
    assert trade["exit_date"] == "2025-01-14"
    expected = 4000 * (113 / 102.8 - 1 - 0.0035)
    assert trade["pnl"] == pytest.approx(expected, abs=0.01)
    assert trade["target_price"] > trade["entry_price"]
    assert trade["trade_enabled"] is False


def test_daily_old_discovery_is_seed_only_and_default_off():
    snapshot, observations = sleeve.prep_and_build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
        as_of_date="20260713",
        existing_observations=[],
        fetched_events=[
            {
                "nct_id": "NCT00000003",
                "ticker": "MRK",
                "results_first_post_date": "2026-07-01",
            }
        ],
    )
    assert observations[0]["first_seen_date"] == "2026-07-13"
    assert snapshot["candidate_count"] == 0
    assert snapshot["seed_only_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["alters_signal_generation"] is False
    assert snapshot["alters_candidate_ranking"] is False


def test_today_first_seen_can_only_be_pending_not_traded():
    snapshot, _ = sleeve.prep_and_build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
        as_of_date="2026-07-13",
        existing_observations=[],
        fetched_events=[
                {
                    "nct_id": "NCT00000004",
                    "ticker": "REGN",
                    "results_first_post_date": "2026-07-13",
                    "history_version": "12",
                    "source_url": "https://clinicaltrials.gov/api/int/studies/NCT00000004/history/12",
                    "raw_sha256": "b" * 64,
                }
        ],
    )
    assert snapshot["candidate_count"] == 0
    assert snapshot["pending_confirmation_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["settled_count"] == 0
    assert snapshot["trade_enabled"] is False


def test_as_of_accepts_daily_yyyymmdd_contract():
    snapshot = sleeve.build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
        as_of_date="20260713", observations=[]
    )
    assert snapshot["as_of_date"] == "2026-07-13"
