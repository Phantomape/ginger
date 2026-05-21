# exp-20260521-003 Event Source-Capacity Scout

Decision: `rejected_event_source_capacity`

Alpha search, replay-only. Tests whether the accepted default-off event overlay is capacity constrained by one active paper position per source.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.6390 | 6.5204 | -0.1186 | $137,454.00 | $136,982.75 | $-471.25 |
| mid_weak | 3.6218 | 3.4492 | -0.1726 | $102,311.72 | $100,559.93 | $-1,751.79 |
| old_thin | 0.6850 | 0.7868 | +0.1018 | $43,082.99 | $47,111.69 | $+4,028.70 |

## Sweep

| Variant | Passed | dEV | dPnL | Improved | Regressed | Added trades | Added windows | Added PnL | Max positive share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| source_cap_2 | no | -0.1894 | $+1,805.66 | 1 | 2 | 9 | 3 | $+1,805.66 | 0.5438 |
| source_cap_3 | no | -0.2091 | $+2,378.73 | 1 | 2 | 11 | 3 | $+2,378.73 | 0.4503 |

## Incremental Selection

```json
{
  "added_by_source": {
    "sec_governance_procedural": 7,
    "sec_negative_reaction": 2
  },
  "added_max_single_positive_pnl_share": 0.5438,
  "added_tickers": [
    "AMZN",
    "APP",
    "CVX",
    "DE",
    "DIS",
    "GS"
  ],
  "added_total_pnl": 1805.66,
  "added_trade_count": 9,
  "added_win_rate": 0.7778,
  "added_windows_present": 3,
  "added_wins": 7,
  "by_window": {
    "late_strong": {
      "added_by_source": {
        "sec_governance_procedural": 2,
        "sec_negative_reaction": 1
      },
      "added_tickers": [
        "DIS",
        "GS"
      ],
      "added_total_pnl": -471.25,
      "added_trade_count": 3,
      "added_trades": [
        {
          "accepted_event_scalar": 1.0,
          "breadth_bucket": "mixed_breadth",
          "dispersion_bucket": "high_sector_dispersion",
          "entry_date": "2025-11-17",
          "exit_date": "2025-12-01",
          "pnl": 61.45,
          "source": "sec_negative_reaction",
          "state_surface": "balanced_state_leadership",
          "ticker": "DIS"
        },
        {
          "accepted_event_scalar": 3.0,
          "breadth_bucket": "mixed_breadth",
          "dispersion_bucket": "high_sector_dispersion",
          "entry_date": "2026-02-04",
          "exit_date": "2026-02-19",
          "pnl": -760.29,
          "source": "sec_governance_procedural",
          "state_surface": "rotation_breakout_leadership",
          "ticker": "GS"
        },
        {
          "accepted_event_scalar": 1.0,
          "breadth_bucket": "thin_breadth",
          "dispersion_bucket": "high_sector_dispersion",
          "entry_date": "2026-03-09",
          "exit_date": "2026-03-23",
          "pnl": 227.59,
          "source": "sec_governance_procedural",
          "state_surface": "balanced_state_leadership",
          "ticker": "GS"
        }
      ],
      "added_wins": 2
    },
    "mid_weak": {
      "added_by_source": {
        "sec_governance_procedural": 2
      },
      "added_tickers": [
        "AMZN",
        "APP"
      ],
      "added_total_pnl": -1751.79,
      "added_trade_count": 2,
      "added_trades": [
        {
          "accepted_event_scalar": 1.25,
          "breadth_bucket": "broad_breadth",
          "dispersion_bucket": "high_sector_dispersion",
          "entry_date": "2025-05-27",
          "exit_date": "2025-06-10",
          "pnl": 849.94,
          "source": "sec_governance_procedural",
          "state_surface": "broad_breadth_trend_persistence",
          "ticker": "AMZN"
        },
        {
          "accepted_event_scalar": 2.5,
          "breadth_bucket": "broad_breadth",
          "dispersion_bucket": "high_sector_dispersion",
          "entry_date": "2025-06-11",
          "exit_date": "2025-06-26",
          "pnl": -2601.73,
          "source": "sec_governance_procedural",
          "state_surface": "broad_breadth_trend_persistence",
          "ticker": "APP"
        }
      ],
      "added_wins": 1
    },
    "old_thin": {
      "added_by_source": {
        "sec_governance_procedural": 3,
        "sec_negative_reaction": 1
      },
      "added_tickers": [
        "CVX",
        "DE",
        "GS"
      ],
      "added_total_pnl": 4028.7,
      "added_trade_count": 4,
      "added_trades": [
        {
          "accepted_event_scalar": 2.5,
          "breadth_bucket": "broad_breadth",
          "dispersion_bucket": "mid_sector_dispersion",
          "entry_date": "2024-10-25",
          "exit_date": "2024-11-08",
          "pnl": 2810.43,
          "source": "sec_governance_procedural",
          "state_surface": "broad_breadth_trend_persistence",
          "ticker": "GS"
        },
        {
          "accepted_event_scalar": 2.0,
          "breadth_bucket": "mixed_breadth",
          "dispersion_bucket": "mid_sector_dispersion",
          "entry_date": "2025-01-30",
          "exit_date": "2025-02-13",
          "pnl": 68.4,
          "source": "sec_governance_procedural",
          "state_surface": "mid_dispersion_selective_leadership",
          "ticker": "GS"
        },
        {
          "accepted_event_scalar": 1.0,
          "breadth_bucket": "mixed_breadth",
          "dispersion_bucket": "mid_sector_dispersion",
          "entry_date": "2025-02-04",
          "exit_date": "2025-02-18",
          "pnl": 581.74,
          "source": "sec_negative_reaction",
          "state_surface": "mid_dispersion_selective_leadership",
          "ticker": "CVX"
        },
        {
          "accepted_event_scalar": 1.0,
          "breadth_bucket": "mixed_breadth",
          "dispersion_bucket": "high_sector_dispersion",
          "entry_date": "2025-03-04",
          "exit_date": "2025-03-18",
          "pnl": 568.13,
          "source": "sec_governance_procedural",
          "state_surface": "balanced_state_leadership",
          "ticker": "DE"
        }
      ],
      "added_wins": 4
    }
  }
}
```

## Production Impact

Replay only. No shared policy, production adapter, production report, core behavior, or live/default order path changed.
