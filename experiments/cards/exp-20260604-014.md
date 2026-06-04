# exp-20260604-014 SEC Text-Price Peer/Theme Propagation

- Trial family: `sec_text_peer_theme_propagation_candidate_pool`
- Changed variable: `sec_text_price_alignment_same_sector_peer_propagation_candidate_source_v1`
- Decision: `rejected_sec_text_peer_theme_propagation_candidate_pool`
- Aggregate EV delta: +0.3353
- Aggregate PnL delta: $+8,825.48
- Target trades: 33
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7 | $0.61 | 5.1628 | 5.1562 | -0.0066 | $+918.15 | -0.0001 |
| mid_weak | 9 | $4,842.25 | 2.1402 | 2.4077 | +0.2675 | $+4,913.89 | -0.0011 |
| old_thin | 17 | $2,993.44 | 0.5911 | 0.6655 | +0.0744 | $+2,993.44 | +0.0068 |

## Gate 2 Field Coverage

```json
{
  "open_positions_required_fields": {
    "coverage": {
      "entry_date": {
        "non_null_count": 15,
        "non_null_share": 1.0,
        "present_count": 15,
        "total_count": 15
      },
      "target_price": {
        "non_null_count": 15,
        "non_null_share": 1.0,
        "present_count": 15,
        "total_count": 15
      },
      "ticker": {
        "non_null_count": 15,
        "non_null_share": 1.0,
        "present_count": 15,
        "total_count": 15
      }
    },
    "path": "operator_inputs/open_positions.json",
    "position_count": 15
  },
  "peer_target_trade_field_coverage": {
    "entry_date": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "exit_date": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "known_at": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "peer_avg_dollar_volume_20d": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "peer_rs20_vs_spy_pct": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "peer_signal_excess_vs_spy_pct": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "pnl": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "signal_date": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "source_accession_number": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "source_language_bucket": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "source_signal_day_excess_vs_spy_pct": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "source_ticker": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "ticker": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    },
    "usable_trade_date": {
      "non_null_count": 33,
      "non_null_share": 1.0,
      "present_count": 33,
      "total_count": 33
    }
  },
  "production_boundary": {
    "adapter_status": "replay_only_no_live_adapter",
    "alters_orders": false,
    "backtester_adapter_changed": false,
    "default_off_paper_only": true,
    "lookahead_guard": "Source issuer filing text and source/peer OHLCV reactions are observed only through the signal-date close. The paper event usable_trade_date is shifted to the peer's next trading session before the existing next-open event helper prices the trade.",
    "parity_note": "This experiment changes no production code. A positive replay result cannot be promoted until the same SEC source filter, sector peer relation, peer OHLCV confirmations, next-session entry shift, and selection order are implemented in a shared default-off adapter with production/backtest parity tests.",
    "parity_test_added": false,
    "production_orders_changed": false,
    "production_signal_path_changed": false,
    "replay_only": true,
    "run_adapter_changed": false,
    "shared_policy_changed": false,
    "trade_enabled": false
  },
  "source_fields": {
    "required_fields": [
      "ticker",
      "usable_trade_date",
      "accepted_at",
      "form_type",
      "form_base",
      "eight_k_item_codes",
      "combined_text",
      "pit_source"
    ],
    "sec_text_path": "data/non_ohlcv/sec_filing_text_20241002_20260421.jsonl",
    "source_decision_time": "SEC text accepted_at/usable_trade_date plus signal-date OHLCV close; entry shifted to next trading session."
  }
}
```

## Gate 3 Survival Audit

```json
{
  "by_window": {
    "late_strong": {
      "signals_generated": 51,
      "signals_survived": 41,
      "survival_rate": 0.8039,
      "survival_rate_floor_passed": true
    },
    "mid_weak": {
      "signals_generated": 53,
      "signals_survived": 42,
      "survival_rate": 0.7925,
      "survival_rate_floor_passed": true
    },
    "old_thin": {
      "signals_generated": 60,
      "signals_survived": 52,
      "survival_rate": 0.8667,
      "survival_rate_floor_passed": true
    }
  },
  "min_survival_rate": 0.7925,
  "passed": true,
  "survival_rate_floor": 0.05
}
```

## Gate 4 Checks

- `aggregate_expected_value_positive`: True
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: True
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: False
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Decision Rationale

One or more Gate 4 checks failed, so the SEC text-price peer/theme propagation candidate source is not retained.

## Lookahead / Parity Guard

Source issuer filing text and source/peer OHLCV reactions are observed only through the signal-date close. The paper event usable_trade_date is shifted to the peer's next trading session before the existing next-open event helper prices the trade.

This experiment changes no production code. A positive replay result cannot be promoted until the same SEC source filter, sector peer relation, peer OHLCV confirmations, next-session entry shift, and selection order are implemented in a shared default-off adapter with production/backtest parity tests.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260604_014_sec_text_peer_theme_propagation.py

No JavaScript was used.
