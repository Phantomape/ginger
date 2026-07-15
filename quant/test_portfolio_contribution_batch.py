from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from quant.portfolio_contribution_batch import (
    allocate_sleeve_capital,
    circular_block_indices,
    load_ohlcv_snapshot,
    max_t_lower_bounds,
    pnl_to_returns,
    reconstruct_trade_daily_pnl,
    return_metrics,
    simultaneous_max_t_bounds,
    trade_required_price_dates,
)


def _row(**overrides):
    row = {
        "ticker": "ABC",
        "entry_date": "2025-01-02",
        "entry_price": 100.0,
        "exit_date": "2025-01-04",
        "exit_price": 110.0,
        "paper_notional_usd": 1000.0,
        "pnl": 96.5,
    }
    row.update(overrides)
    return row


def _calendar():
    return [date(2025, 1, day) for day in (2, 3, 4)]


def _prices():
    return {
        "ABC": {
            date(2025, 1, 2): {"close": 102.0},
            date(2025, 1, 3): {"close": 105.0},
            date(2025, 1, 4): {"close": 106.0},
        }
    }


def test_normal_exit_uses_source_price_and_reconciles_split_costs():
    series, diagnostic = reconstruct_trade_daily_pnl(
        _row(), _calendar(), _prices()
    )

    assert diagnostic["usable"] is True
    assert diagnostic["forced_close"] is False
    assert diagnostic["entry_cost_usd"] == pytest.approx(1.75)
    assert diagnostic["exit_cost_usd"] == pytest.approx(1.75)
    assert sum(series.values()) == pytest.approx(96.5)
    assert diagnostic["formula_net_pnl"] == pytest.approx(96.5)
    assert diagnostic["normal_exit_reconciliation_error"] == pytest.approx(0.0)
    # The normal booking date consumes the source exit price, not warehouse.
    assert ("ABC", date(2025, 1, 4)) not in trade_required_price_dates(
        _row(), _calendar()
    )


def test_fixed_boundary_force_closes_and_excludes_late_entry():
    forced_row = _row(exit_date="2025-01-10", exit_price=999.0, pnl=999.0)
    series, diagnostic = reconstruct_trade_daily_pnl(
        forced_row, _calendar(), _prices()
    )

    assert diagnostic["usable"] is True
    assert diagnostic["forced_close"] is True
    assert diagnostic["effective_exit_date"] == "2025-01-04"
    assert diagnostic["forced_exit_raw_close"] == pytest.approx(106.0)
    assert diagnostic["effective_exit_price"] == pytest.approx(106.0 * 0.9995)
    assert sum(series.values()) == pytest.approx(55.97)
    assert ("ABC", date(2025, 1, 4)) in trade_required_price_dates(
        forced_row, _calendar()
    )

    excluded, late_diagnostic = reconstruct_trade_daily_pnl(
        _row(entry_date="2025-01-05"), _calendar(), _prices()
    )
    assert excluded == {}
    assert late_diagnostic["excluded"] is True
    assert late_diagnostic["reason"] == "entry_after_window_end"


def test_return_metrics_compound_drawdown_tail_and_ev():
    metrics = return_metrics(np.asarray([0.10, -0.05]))

    assert metrics["total_return_fraction"] == pytest.approx(0.045)
    assert metrics["total_pnl"] == pytest.approx(4500.0)
    assert metrics["max_drawdown_pct"] == pytest.approx(0.05)
    assert metrics["expected_shortfall_95"] == pytest.approx(0.05)
    expected_sharpe = np.mean([0.10, -0.05]) / np.std(
        [0.10, -0.05], ddof=1
    ) * np.sqrt(252.0)
    assert metrics["sharpe_daily"] == pytest.approx(expected_sharpe)
    assert metrics["expected_value_score"] == pytest.approx(
        0.045 * expected_sharpe
    )


def test_cash_allocator_is_same_day_pro_rata_and_order_invariant():
    calendar = [date(2025, 1, day) for day in (2, 3, 4, 5)]
    rows = [
        _row(
            ticker="AAA",
            entry_date="2025-01-02",
            exit_date="2025-01-04",
            paper_notional_usd=8000.0,
            pnl=800.0,
        ),
        _row(
            ticker="BBB",
            entry_date="2025-01-02",
            exit_date="2025-01-05",
            paper_notional_usd=4000.0,
            pnl=400.0,
        ),
    ]
    first = allocate_sleeve_capital(rows, calendar)
    second = allocate_sleeve_capital(list(reversed(rows)), calendar)

    expected_ratio = 10000.0 / (12000.0 * 1.00175)
    first_fills = {
        row["ticker"]: row["paper_notional_usd"]
        for row in first["allocated_rows"]
    }
    second_fills = {
        row["ticker"]: row["paper_notional_usd"]
        for row in second["allocated_rows"]
    }
    assert first_fills == pytest.approx(second_fills)
    assert first_fills == pytest.approx(
        {"AAA": 8000.0 * expected_ratio, "BBB": 4000.0 * expected_ratio}
    )
    assert first["partial_fill_count"] == 2
    assert first["zero_fill_count"] == 0
    assert first["min_cash_usd"] == pytest.approx(0.0, abs=1e-9)
    assert first["cash_nonnegative"] is True
    scaled_aaa = next(
        row for row in first["allocated_rows"] if row["ticker"] == "AAA"
    )
    assert scaled_aaa["pnl"] == pytest.approx(800.0 * expected_ratio)


def test_cash_allocator_does_not_reuse_same_day_exit_but_reuses_prior_exit():
    calendar = [date(2025, 1, day) for day in (2, 3, 4, 5)]
    rows = [
        _row(
            ticker="AAA",
            entry_date="2025-01-02",
            exit_date="2025-01-03",
            exit_price=110.0,
            paper_notional_usd=10000.0,
        ),
        _row(
            ticker="BBB",
            entry_date="2025-01-03",
            exit_date="2025-01-05",
            paper_notional_usd=4000.0,
        ),
        _row(
            ticker="CCC",
            entry_date="2025-01-04",
            exit_date="2025-01-05",
            paper_notional_usd=4000.0,
        ),
    ]
    allocation = allocate_sleeve_capital(rows, calendar)
    diagnostics = {
        item["source_order"]: item for item in allocation["diagnostics"]
    }

    assert diagnostics[0]["status"] == "partial_fill"  # entry fee is funded
    assert diagnostics[1]["reason"] == "sleeve_cap_no_cash"
    assert diagnostics[1]["filled_notional_usd"] == pytest.approx(0.0)
    assert diagnostics[2]["status"] == "full_fill"
    assert diagnostics[2]["filled_notional_usd"] == pytest.approx(4000.0)
    assert allocation["same_day_exit_reuse"] is False
    assert allocation["min_cash_usd"] >= -1e-9
    assert allocation["ending_all_positions_settled"] is True


def test_candidate_return_denominator_is_ten_thousand_dollar_sleeve():
    calendar = [date(2025, 1, 2), date(2025, 1, 3)]
    returns = pnl_to_returns(
        {calendar[0]: 100.0},
        calendar,
        initial_capital=10_000.0,
    )

    assert returns.tolist() == pytest.approx([0.01, 0.0])
    assert return_metrics(returns, capital=10_000.0)["total_pnl"] == pytest.approx(
        100.0
    )


def test_frozen_snapshot_hash_verification_rejects_tamper():
    payload = {
        "schema": "ginger.portfolio_contribution_ohlcv_rowset.v1",
        "experiment_id": "exp-test",
        "selection_contract": "test superset",
        "potential_requested_pair_count": 1,
        "actual_consumed_pair_count": 1,
        "unused_superset_pair_count": 0,
        "row_count": 1,
        "missing_pairs": [],
        "missing_actual_consumed_pairs": [],
        "rows": [
            {
                "ticker": "ABC",
                "date": "2025-01-02",
                "open": 99.0,
                "high": 102.0,
                "low": 98.0,
                "close": 101.0,
                "volume": 1000.0,
            }
        ],
    }
    compressed = gzip.compress(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8"),
        mtime=0,
    )
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        path = Path(temp_dir) / "snapshot.json.gz"
        path.write_bytes(compressed)
        digest = hashlib.sha256(compressed).hexdigest()
        Path(f"{path}.sha256").write_text(
            f"{digest}  {path.name}\n", encoding="ascii"
        )

        rows, identity = load_ohlcv_snapshot(path)
        assert len(rows) == 1
        assert identity["gzip_sha256"] == digest
        path.write_bytes(compressed + b"tamper")
        with pytest.raises(ValueError, match="sha256 mismatch"):
            load_ohlcv_snapshot(path)


def test_circular_indices_and_max_t_are_deterministic_and_panel_shaped():
    first_indices = circular_block_indices(
        7,
        replicates=11,
        block_length=3,
        rng=np.random.default_rng(17),
    )
    second_indices = circular_block_indices(
        7,
        replicates=11,
        block_length=3,
        rng=np.random.default_rng(17),
    )
    assert np.array_equal(first_indices, second_indices)
    assert first_indices.shape == (11, 7)
    assert np.all((first_indices >= 0) & (first_indices < 7))

    core = {
        "late_strong": np.asarray([0.01, -0.004, 0.006, 0.002, -0.003, 0.005]),
        "mid_weak": np.asarray([0.002, -0.006, 0.004, 0.003, -0.001, 0.002]),
        "old_thin": np.asarray([0.004, -0.002, 0.001, 0.005, -0.003, 0.003]),
    }
    candidates = {
        "candidate-a": {
            window: values + 0.001 for window, values in core.items()
        },
        "candidate-b": {
            window: values[::-1].copy() for window, values in core.items()
        },
    }
    first = simultaneous_max_t_bounds(
        core,
        candidates,
        replicates=200,
        block_length=3,
        seed=1234,
    )
    second = simultaneous_max_t_bounds(
        core,
        candidates,
        replicates=200,
        block_length=3,
        seed=1234,
    )

    assert first == second
    assert first["candidate_ids"] == ["candidate-a", "candidate-b"]
    assert first["bootstrap_matrix_shape"] == [200, 2]
    assert len(first["simultaneous_lower_bound"]) == 2
    assert np.all(np.isfinite(first["simultaneous_lower_bound"]))


def test_max_t_lower_bound_uses_upper_bootstrap_error_tail():
    observed = np.asarray([1.0, 2.0])
    bootstrap = np.asarray(
        [
            [1.8, 2.1],
            [1.4, 2.6],
            [0.9, 1.8],
            [1.1, 2.2],
            [1.2, 2.0],
        ]
    )
    lower, standard_errors, critical = max_t_lower_bounds(
        observed,
        bootstrap,
        confidence=0.80,
    )

    manual_t = (bootstrap - observed[None, :]) / standard_errors[None, :]
    expected_critical = np.quantile(np.max(manual_t, axis=1), 0.80)
    assert critical == pytest.approx(expected_critical)
    assert lower == pytest.approx(observed - expected_critical * standard_errors)
    opposite_tail = np.quantile(
        np.max((observed[None, :] - bootstrap) / standard_errors[None, :], axis=1),
        0.80,
    )
    assert critical != pytest.approx(opposite_tail)
