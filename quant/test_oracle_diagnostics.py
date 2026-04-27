import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from oracle_diagnostics import build_oracle_diagnostics  # noqa: E402


def test_perfect_exit_oracle_computes_capture_and_regret(tmp_path):
    backtest = {
        "period": "2026-01-01 -> 2026-01-05",
        "known_biases": {
            "ohlcv_source": {
                "snapshot_path": str(tmp_path / "snapshot.json"),
            }
        },
        "trades": [
            {
                "ticker": "ABC",
                "strategy": "trend_long",
                "entry_price": 100.0,
                "exit_price": 105.0,
                "shares": 10,
                "pnl": 49.0,
                "entry_date": "2026-01-02",
                "exit_date": "2026-01-04",
                "exit_reason": "target",
            }
        ],
    }
    snapshot = {
        "ohlcv": {
            "ABC": [
                {"Date": "2026-01-01", "High": 101.0},
                {"Date": "2026-01-02", "High": 103.0},
                {"Date": "2026-01-03", "High": 112.0},
                {"Date": "2026-01-04", "High": 108.0},
            ]
        }
    }
    backtest_path = tmp_path / "backtest.json"
    snapshot_path = tmp_path / "snapshot.json"
    backtest_path.write_text(json.dumps(backtest), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    diagnostics = build_oracle_diagnostics(backtest_path)
    perfect_exit = diagnostics["oracle_metrics"]["perfect_exit"]
    trade = perfect_exit["top_regret_trades"][0]

    assert perfect_exit["trade_count"] == 1
    assert trade["oracle_exit_date"] == "2026-01-03"
    assert perfect_exit["oracle_pnl"] > perfect_exit["actual_pnl"]
    assert 0 < perfect_exit["capture_ratio"] < 1


def test_perfect_exit_oracle_reports_missing_snapshot_rows(tmp_path):
    backtest = {
        "known_biases": {
            "ohlcv_source": {
                "snapshot_path": str(tmp_path / "snapshot.json"),
            }
        },
        "trades": [
            {
                "ticker": "MISSING",
                "strategy": "breakout_long",
                "entry_price": 10.0,
                "shares": 1,
                "pnl": 0.0,
                "entry_date": "2026-01-02",
                "exit_date": "2026-01-04",
            }
        ],
    }
    snapshot = {"ohlcv": {}}
    backtest_path = tmp_path / "backtest.json"
    snapshot_path = tmp_path / "snapshot.json"
    backtest_path.write_text(json.dumps(backtest), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    diagnostics = build_oracle_diagnostics(backtest_path)
    perfect_exit = diagnostics["oracle_metrics"]["perfect_exit"]

    assert perfect_exit["trade_count"] == 0
    assert perfect_exit["missing_trade_count"] == 1
    assert perfect_exit["missing_trades"][0]["ticker"] == "MISSING"


def test_candidate_forward_oracle_uses_saved_candidate_dates(tmp_path):
    backtest = {
        "known_biases": {
            "ohlcv_source": {
                "snapshot_path": str(tmp_path / "snapshot.json"),
            },
            "llm_gate_unreplayed": {
                "candidate_tickers_by_date": {
                    "20260102": ["XYZ"],
                }
            },
        },
        "trades": [
            {
                "ticker": "XYZ",
                "entry_date": "2026-01-05",
                "entry_price": 10.0,
                "shares": 1,
                "pnl": 1.0,
                "exit_date": "2026-01-06",
            }
        ],
    }
    snapshot = {
        "ohlcv": {
            "XYZ": [
                {"Date": "2026-01-02", "Open": 10.0, "High": 10.0},
                {"Date": "2026-01-05", "Open": 10.0, "High": 12.0},
                {"Date": "2026-01-06", "Open": 11.0, "High": 13.0},
            ]
        }
    }
    backtest_path = tmp_path / "backtest.json"
    snapshot_path = tmp_path / "snapshot.json"
    backtest_path.write_text(json.dumps(backtest), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    diagnostics = build_oracle_diagnostics(backtest_path, candidate_horizon_days=2)
    candidate = diagnostics["oracle_metrics"]["candidate_forward"]

    assert candidate["candidate_count"] == 1
    assert candidate["actual_trade_overlap_count"] == 1
    assert candidate["best_max_forward_return_pct"] > 0.29


def test_candidate_selection_oracle_reports_rank_regret(tmp_path):
    backtest = {
        "known_biases": {
            "ohlcv_source": {
                "snapshot_path": str(tmp_path / "snapshot.json"),
            },
            "llm_gate_unreplayed": {
                "candidate_tickers_by_date": {
                    "20260102": ["AAA", "BBB"],
                }
            },
        },
        "trades": [
            {
                "ticker": "AAA",
                "entry_date": "2026-01-05",
                "entry_price": 10.0,
                "shares": 1,
                "pnl": 1.0,
                "exit_date": "2026-01-06",
            }
        ],
    }
    snapshot = {
        "ohlcv": {
            "AAA": [
                {"Date": "2026-01-05", "Open": 10.0, "High": 11.0},
                {"Date": "2026-01-06", "Open": 10.5, "High": 11.5},
            ],
            "BBB": [
                {"Date": "2026-01-05", "Open": 10.0, "High": 15.0},
                {"Date": "2026-01-06", "Open": 14.0, "High": 16.0},
            ],
        }
    }
    backtest_path = tmp_path / "backtest.json"
    snapshot_path = tmp_path / "snapshot.json"
    backtest_path.write_text(json.dumps(backtest), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    diagnostics = build_oracle_diagnostics(backtest_path, candidate_horizon_days=2)
    selection = diagnostics["oracle_metrics"]["candidate_selection"]

    assert selection["candidate_days"] == 1
    assert selection["top1_actual_hit_fraction"] == 0
    assert selection["largest_daily_selection_regrets"][0]["top_candidate"] == "BBB"
    assert selection["largest_daily_selection_regrets"][0]["best_actual_candidate"] == "AAA"
    assert selection["avg_top1_vs_actual_selection_regret_pct"] > 0.3


def test_no_trade_attribution_flags_missing_skip_logging(tmp_path):
    backtest = {
        "known_biases": {
            "ohlcv_source": {
                "snapshot_path": str(tmp_path / "snapshot.json"),
            },
            "llm_gate_unreplayed": {
                "candidate_tickers_by_date": {
                    "20260102": ["AAA"],
                }
            },
        },
        "trades": [],
    }
    snapshot = {
        "ohlcv": {
            "AAA": [
                {"Date": "2026-01-05", "Open": 10.0, "High": 12.0},
                {"Date": "2026-01-06", "Open": 10.5, "High": 13.0},
            ]
        }
    }
    backtest_path = tmp_path / "backtest.json"
    snapshot_path = tmp_path / "snapshot.json"
    backtest_path.write_text(json.dumps(backtest), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    diagnostics = build_oracle_diagnostics(backtest_path, candidate_horizon_days=2)
    attribution = diagnostics["oracle_metrics"]["no_trade_attribution"]

    assert attribution["no_actual_selection_days"] == 1
    assert attribution["reason_counts"] == {"needs_entry_skip_logging": 1}
    assert attribution["largest_no_trade_opportunities"][0]["top_candidate"] == "AAA"


def test_no_trade_attribution_flags_already_held_candidate(tmp_path):
    backtest = {
        "known_biases": {
            "ohlcv_source": {
                "snapshot_path": str(tmp_path / "snapshot.json"),
            },
            "llm_gate_unreplayed": {
                "candidate_tickers_by_date": {
                    "20260102": ["AAA"],
                }
            },
        },
        "trades": [
            {
                "ticker": "AAA",
                "entry_date": "2026-01-01",
                "exit_date": "2026-01-06",
                "entry_price": 10.0,
                "shares": 1,
                "pnl": 1.0,
            }
        ],
    }
    snapshot = {
        "ohlcv": {
            "AAA": [
                {"Date": "2026-01-05", "Open": 10.0, "High": 12.0},
                {"Date": "2026-01-06", "Open": 10.5, "High": 13.0},
            ]
        }
    }
    backtest_path = tmp_path / "backtest.json"
    snapshot_path = tmp_path / "snapshot.json"
    backtest_path.write_text(json.dumps(backtest), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    diagnostics = build_oracle_diagnostics(backtest_path, candidate_horizon_days=2)
    attribution = diagnostics["oracle_metrics"]["no_trade_attribution"]

    assert attribution["reason_counts"] == {"already_holding_candidate": 1}
    assert attribution["largest_no_trade_opportunities"][0][
        "already_holding_candidate_tickers"
    ] == ["AAA"]
