from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


RUNNER_PATH = (
    Path(__file__).resolve().parent
    / "experiments"
    / "exp_20260719_003_sec_cash_tender_spread.py"
)
SPEC = importlib.util.spec_from_file_location("exp_20260719_003_runner_test", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def _contract(accession: str, filing_date: str, *, ticker: str = "TEND") -> dict:
    return {
        "accession_number": accession,
        "subject_cik": "0000000001",
        "filing_date": filing_date,
        "accepted_at": f"{filing_date}T18:00:00",
        "policy_eligible": True,
        "eligibility": {"eligible": True},
        "raw_submission_sha256": "a" * 64,
        "primary_schedule_to": {"source_sha256": "b" * 64},
        "offer_to_purchase_exhibit": {"source_sha256": "c" * 64},
        "terms": {
            "target_ticker": ticker,
            "target_exchange": "NASDAQ",
            "agreement_or_announcement_date": filing_date,
            "scheduled_expiration_date": "2026-12-01",
            "offer_price_usd": 10.0,
            "evidence_spans": [{"field": "offer_price_usd"}],
        },
        "outcome": {
            "outcome_type": "pending",
            "outcome_date": None,
            "evidence_spans": [],
        },
        "amendments": [],
    }


def test_exchange_mapping_and_price_range_are_locked() -> None:
    assert runner.ortex_exchange_symbol("NASDAQ") == "nasdaq"
    assert runner.ortex_exchange_symbol("NYSE") == "nyse"
    assert runner.ortex_exchange_symbol("NYSE_AMERICAN") == "amex"
    with pytest.raises(runner.EvaluationContractError, match="unsupported"):
        runner.ortex_exchange_symbol("OTC")

    episode = _contract("acc-old", "2024-10-30")
    episode["terms"]["agreement_or_announcement_date"] = "2024-10-14"
    assert runner.price_request_range(episode) == ("2024-08-05", "2025-04-22")
    episode["outcome"] = {
        "outcome_type": "completed",
        "outcome_date": "2024-11-29",
    }
    assert runner.price_request_range(episode) == ("2024-08-05", "2024-12-09")


def test_price_collection_passes_asof_and_hard_credit_floor_without_writing(
    tmp_path: Path,
) -> None:
    episode = _contract("acc-mid", "2025-05-01")
    calls: list[dict] = []

    def fake_price(ticker, exchange, start, end, **kwargs):
        calls.append(
            {
                "ticker": ticker,
                "exchange": exchange,
                "start": start,
                "end": end,
                **kwargs,
            }
        )
        return {
            "source": "fixture",
            "ticker": ticker,
            "request_metadata": {"credits_used": 0.0, "credits_left": 999.0},
            "rows": [],
        }

    payload = runner.collect_ortex_prices(
        {
            "episodes_rowset_sha256": "rowset",
            "episodes": [episode],
        },
        fetch_price=fake_price,
        write=False,
        reuse_existing=False,
    )

    assert set(payload["episodes"]) == {"acc-mid"}
    assert calls[0]["ticker_as_of_date"] == "2025-05-01"
    assert calls[0]["min_credits_left"] == 250.0
    assert calls[0]["credit_budget"] == 82.0
    assert payload["request_metadata"]["sensitive_material_persisted"] is False
    cache_result = runner.tender_prices.write_immutable_price_cache(
        tmp_path / "prices.json", payload
    )
    assert cache_result["created"] is True


def test_price_supplement_retries_only_exact_no_data_parser_failures() -> None:
    repaired = _contract("acc-repair", "2025-05-01", ticker="FIX")
    untouched = _contract("acc-good", "2025-05-02", ticker="GOOD")
    calls: list[str] = []

    def fake_price(ticker, exchange, start, end, **kwargs):
        calls.append(ticker)
        return {
            "source": "fixture",
            "ticker": ticker,
            "request_metadata": {"credits_used": 0.0, "credits_left": 999.0},
            "rows": [],
        }

    contracts = {
        "episodes_rowset_sha256": "rowset",
        "episodes": [repaired, untouched],
    }
    base = {
        "contracts_rowset_sha256": "rowset",
        "request_metadata": {},
        "episodes": {"acc-good": {"ticker": "GOOD", "rows": []}},
        "failures": [
            {
                "accession_number": "acc-repair",
                "error_type": "OrtexPayloadError",
                "error": "ORTEX data/rows must be a list of objects",
            }
        ],
    }

    supplement = runner.collect_ortex_price_supplement(
        contracts,
        base,
        fetch_price=fake_price,
        write=False,
        reuse_existing=False,
    )
    merged = runner._merge_price_documents(base, supplement)

    assert calls == ["FIX"]
    assert set(supplement["episodes"]) == {"acc-repair"}
    assert set(merged["episodes"]) == {"acc-good", "acc-repair"}
    assert merged["failures"] == []
    assert merged["request_metadata"]["successful_episode_count"] == 2


def test_price_request_contract_allows_superset_and_weekend_only_tail_gap() -> None:
    episode = _contract("acc", "2024-12-13", ticker="SAFE")
    episode["outcome"] = {
        "outcome_type": "terminated_negative",
        "outcome_date": "2025-02-06",
    }
    expected_start, expected_end = runner.price_request_range(episode)
    assert expected_end == "2025-02-16"
    result = {
        "acc": {
            "ticker": "SAFE",
            "ticker_as_of_date": "2024-12-13",
            "start_date": expected_start,
            "end_date": "2025-02-15",
            "status": "complete",
            "rows": [],
        },
        "old-extra-accession": {"status": "complete"},
    }

    assert runner._price_request_contract_failures([episode], result) == []
    result["acc"]["end_date"] = "2025-02-13"
    assert "price_request_end_does_not_cover_sessions" in runner._price_request_contract_failures(
        [episode], result
    )[0]


def test_capital_conserving_blend_is_not_a_full_core_overlay() -> None:
    core = np.asarray([0.10, -0.02])
    sleeve = np.asarray([0.20, 0.01])
    blended = runner.capital_conserving_blend_returns(core, sleeve)

    assert blended.tolist() == pytest.approx([0.11, -0.017])
    assert blended[0] != pytest.approx(core[0] + 0.10 * sleeve[0])
    with pytest.raises(runner.EvaluationContractError, match="equal-length"):
        runner.capital_conserving_blend_returns([0.1], [0.1, 0.2])


def test_runner_metrics_preserve_negative_ev_sign() -> None:
    metrics = runner._metrics([-0.01, -0.02, 0.001], capital=10_000.0)

    assert metrics["total_return_fraction"] < 0
    assert metrics["sharpe_daily"] < 0
    assert metrics["expected_value_score"] < 0


def test_trade_gate_requires_contract_cash_target_and_sec_provenance() -> None:
    contract = _contract("acc", "2025-05-01")
    trade = {
        "accession_number": "acc",
        "ticker": "TEND",
        "entry_date": "2025-05-02",
        "entry_price": 9.5,
        "target_price": 10.0,
        "target_price_role": "contract_cash_offer_price",
        "net_pnl_usd": 10.0,
        "valuation_date": "2025-05-10",
        "valuation_price": 9.8,
        "exit_date": None,
        "actual_close": False,
        "right_censored": True,
    }

    assert runner._trade_gate([trade], {"acc": contract})["passed"] is True
    trade["target_price_role"] = "unknown"
    assert runner._trade_gate([trade], {"acc": contract})["passed"] is False


def test_realized_and_right_censored_concentration_populations_stay_separate() -> None:
    closed = {"ticker": "DONE", "net_pnl_usd": 100.0, "actual_close": True}
    censored = {"ticker": "OPEN", "net_pnl_usd": 300.0, "right_censored": True}

    realized = runner._absolute_pnl_concentration(
        [closed], population="actual_closed_realized_rows"
    )
    inclusive = runner._absolute_pnl_concentration(
        [closed, censored],
        population="entered_rows_including_right_censored_window_end_mtm",
    )

    assert realized["row_count"] == 1
    assert realized["ticker_trade_counts"] == {"DONE": 1}
    assert inclusive["row_count"] == 2
    assert inclusive["maximum_single_deal_absolute_pnl_share"] == pytest.approx(0.75)


def test_evaluate_emits_binding_rejection_and_judge_headline_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    episodes = [
        _contract("acc-old", "2024-10-30", ticker="OLD"),
        _contract("acc-mid", "2025-05-01", ticker="MID"),
        _contract("acc-late", "2025-11-03", ticker="LATE"),
    ]

    def fake_replay(window_episodes, prices, start, end, **kwargs):
        calendar = kwargs["calendar_sessions"]
        return {
            "daily_returns": [
                {"as_of": day.isoformat(), "daily_return": 0.0} for day in calendar
            ],
            "daily_ledger": [],
            "signals_generated": len(window_episodes),
            "signals_survived": 0,
            "candidate_evaluations": [
                {"accession_number": row["accession_number"]}
                for row in window_episodes
            ],
            "candidate_rejections": [],
            "trades": [],
            "measurement_failures": [],
            "metrics": {
                "cash_nonnegative": True,
                "cash_conservation_passed": True,
            },
            "summary": {
                "cash_nonnegative": True,
                "cash_conservation_passed": True,
            },
            "event_fee_sensitivity": {},
        }

    monkeypatch.setattr(runner.sleeve, "replay_sec_cash_tender_spread_sleeve", fake_replay)
    monkeypatch.setattr(
        runner.sleeve,
        "build_sec_cash_tender_spread_paper_snapshot",
        lambda *args, **kwargs: {"trade_enabled": False, "orders": []},
    )
    contracts = {
        "episodes_rowset_sha256": "same",
        "master_index_coverage_complete": True,
        "parse_error_count": 0,
        "episodes": episodes,
    }
    prices = {
        "contracts_rowset_sha256": "same",
        "request_metadata": {},
        "episodes": {
            row["accession_number"]: {
                "ticker": row["terms"]["target_ticker"],
                "ticker_as_of_date": row["filing_date"],
                "start_date": runner.price_request_range(row)[0],
                "end_date": runner.price_request_range(row)[1],
                "status": "complete",
                "rows": [],
            }
            for row in episodes
        },
    }

    result = runner.evaluate(contracts, prices, write=False)

    assert result["decision"] == "rejected_cash_tender_spread_policy"
    assert result["accepted_alpha"] is False
    assert result["gate2"]["passed"] is True
    assert result["gate3"]["passed"] is False
    assert result["portfolio_promotion"]["passed"] is False
    assert result["expected_value_score"] < runner.BASELINE_EV
    assert result["total_pnl"] < runner.BASELINE_PNL_USD
    assert result["benchmarks"]["strategy_total_return_pct"] == round(
        result["total_pnl"] / 100_000.0, 4
    )
