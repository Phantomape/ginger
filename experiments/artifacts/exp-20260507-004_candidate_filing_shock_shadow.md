# exp-20260507-004: Candidate Filing-Shock Shadow Tags

Decision: `shadow_only`

## Coverage Table

| Window | Candidates | Recent filing | Selected | Selected recent | Complete fraction |
| --- | ---: | ---: | ---: | ---: | ---: |
| late_strong | 41 | 19 | 38 | 17 | 1.0 |
| mid_weak | 42 | 21 | 37 | 18 | 1.0 |
| old_thin | 55 | 31 | 38 | 22 | 1.0 |

## Data Availability

- SEC accepted/usable trade timestamps are complete in the canonical replay artifacts.
- Directional EPS/revenue surprise and guidance fields remain missing without a PIT consensus/guidance source.
- Recent filing context mostly acts as an event-presence tag, not a true positive/negative financial-shock grade.

## Tagged Candidate Forward Returns

| Tag | Candidates | 5d | 10d | 20d | 60d |
| --- | ---: | --- | --- | --- | --- |
| A_no_recent_filing_event | 67 | n=64, avg=0.48%, med=-0.24%, win=45.3% | n=63, avg=1.73%, med=0.71%, win=55.6% | n=59, avg=2.85%, med=1.38%, win=55.9% | n=43, avg=0.98%, med=-0.84%, win=48.8% |
| B_positive_filing_shock | 0 | n=0 | n=0 | n=0 | n=0 |
| C_negative_filing_shock | 0 | n=0 | n=0 | n=0 | n=0 |
| D_unclear_or_missing_data | 71 | n=69, avg=0.82%, med=0.74%, win=50.7% | n=67, avg=1.09%, med=0.53%, win=53.7% | n=65, avg=2.86%, med=0.15%, win=50.8% | n=46, avg=11.23%, med=8.13%, win=63.0% |

## Slot Value

{
  "candidate_count": 138,
  "overlap_with_existing_signals": {
    "selected_by_entry_plan_rows": 113,
    "selected_with_recent_filing": 57
  },
  "scarce_slot_opportunity_cost": {
    "same_day_comparable_count": 16,
    "overall_delta_20d_distribution": {
      "count": 16,
      "avg_pct": -2.2776,
      "median_pct": -1.8267,
      "win_rate": 0.4375,
      "best_pct": 34.6789,
      "worst_pct": -26.2463
    },
    "by_tag": {
      "A_no_recent_filing_event": {
        "count": 8,
        "delta_20d_distribution": {
          "count": 8,
          "avg_pct": -2.1703,
          "median_pct": -0.099,
          "win_rate": 0.5,
          "best_pct": 5.887,
          "worst_pct": -25.0522
        },
        "positive_delta_count": 4
      },
      "D_unclear_or_missing_data": {
        "count": 8,
        "delta_20d_distribution": {
          "count": 8,
          "avg_pct": -2.3849,
          "median_pct": -9.6088,
          "win_rate": 0.375,
          "best_pct": 34.6789,
          "worst_pct": -26.2463
        },
        "positive_delta_count": 3
      }
    },
    "examples": [
      {
        "window": "late_strong",
        "candidate_date": "2026-01-21",
        "ticker": "IWM",
        "strategy": "breakout_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "A_no_recent_filing_event",
        "candidate_ret_20d": -0.015412,
        "same_day_selected_avg_ret_20d": 0.032372,
        "slot_conflict_delta_20d": -0.047784
      },
      {
        "window": "late_strong",
        "candidate_date": "2026-01-21",
        "ticker": "AMD",
        "strategy": "breakout_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "D_unclear_or_missing_data",
        "candidate_ret_20d": -0.189369,
        "same_day_selected_avg_ret_20d": 0.032372,
        "slot_conflict_delta_20d": -0.221741
      },
      {
        "window": "late_strong",
        "candidate_date": "2026-01-29",
        "ticker": "META",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "D_unclear_or_missing_data",
        "candidate_ret_20d": -0.125576,
        "same_day_selected_avg_ret_20d": 0.019007,
        "slot_conflict_delta_20d": -0.144583
      },
      {
        "window": "mid_weak",
        "candidate_date": "2025-09-02",
        "ticker": "IAU",
        "strategy": "breakout_long",
        "plan_status": "scarce_slot_breakout_deferred",
        "filing_shock_tag": "A_no_recent_filing_event",
        "candidate_ret_20d": 0.088323,
        "same_day_selected_avg_ret_20d": 0.088272,
        "slot_conflict_delta_20d": 5.1e-05
      },
      {
        "window": "old_thin",
        "candidate_date": "2024-10-30",
        "ticker": "GOOG",
        "strategy": "breakout_long",
        "plan_status": "scarce_slot_breakout_deferred",
        "filing_shock_tag": "D_unclear_or_missing_data",
        "candidate_ret_20d": -0.033703,
        "same_day_selected_avg_ret_20d": 0.166579,
        "slot_conflict_delta_20d": -0.200282
      },
      {
        "window": "old_thin",
        "candidate_date": "2024-11-01",
        "ticker": "CVX",
        "strategy": "breakout_long",
        "plan_status": "scarce_slot_breakout_deferred",
        "filing_shock_tag": "D_unclear_or_missing_data",
        "candidate_ret_20d": 0.067021,
        "same_day_selected_avg_ret_20d": 0.061068,
        "slot_conflict_delta_20d": 0.005953
      },
      {
        "window": "old_thin",
        "candidate_date": "2024-11-06",
        "ticker": "GS",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "A_no_recent_filing_event",
        "candidate_ret_20d": 0.002837,
        "same_day_selected_avg_ret_20d": -0.056033,
        "slot_conflict_delta_20d": 0.05887
      },
      {
        "window": "old_thin",
        "candidate_date": "2024-11-06",
        "ticker": "IWM",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "A_no_recent_filing_event",
        "candidate_ret_20d": 0.000125,
        "same_day_selected_avg_ret_20d": -0.056033,
        "slot_conflict_delta_20d": 0.056158
      },
      {
        "window": "old_thin",
        "candidate_date": "2024-11-06",
        "ticker": "JPM",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "A_no_recent_filing_event",
        "candidate_ret_20d": -0.009895,
        "same_day_selected_avg_ret_20d": -0.056033,
        "slot_conflict_delta_20d": 0.046138
      },
      {
        "window": "old_thin",
        "candidate_date": "2024-11-06",
        "ticker": "PLTR",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "D_unclear_or_missing_data",
        "candidate_ret_20d": 0.290755,
        "same_day_selected_avg_ret_20d": -0.056033,
        "slot_conflict_delta_20d": 0.346789
      },
      {
        "window": "old_thin",
        "candidate_date": "2024-11-06",
        "ticker": "TSLA",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "D_unclear_or_missing_data",
        "candidate_ret_20d": 0.277095,
        "same_day_selected_avg_ret_20d": -0.056033,
        "slot_conflict_delta_20d": 0.333128
      },
      {
        "window": "old_thin",
        "candidate_date": "2024-11-07",
        "ticker": "PLTR",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "D_unclear_or_missing_data",
        "candidate_ret_20d": 0.362642,
        "same_day_selected_avg_ret_20d": 0.625105,
        "slot_conflict_delta_20d": -0.262463
      },
      {
        "window": "old_thin",
        "candidate_date": "2025-01-28",
        "ticker": "DDOG",
        "strategy": "breakout_long",
        "plan_status": "scarce_slot_breakout_deferred",
        "filing_shock_tag": "A_no_recent_filing_event",
        "candidate_ret_20d": -0.257105,
        "same_day_selected_avg_ret_20d": -0.006583,
        "slot_conflict_delta_20d": -0.250522
      },
      {
        "window": "old_thin",
        "candidate_date": "2025-01-30",
        "ticker": "MA",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "A_no_recent_filing_event",
        "candidate_ret_20d": 0.014697,
        "same_day_selected_avg_ret_20d": 0.016729,
        "slot_conflict_delta_20d": -0.002031
      },
      {
        "window": "old_thin",
        "candidate_date": "2025-01-30",
        "ticker": "META",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "D_unclear_or_missing_data",
        "candidate_ret_20d": -0.030865,
        "same_day_selected_avg_ret_20d": 0.016729,
        "slot_conflict_delta_20d": -0.047594
      },
      {
        "window": "old_thin",
        "candidate_date": "2025-01-30",
        "ticker": "SLV",
        "strategy": "trend_long",
        "plan_status": "slot_sliced",
        "filing_shock_tag": "A_no_recent_filing_event",
        "candidate_ret_20d": -0.017776,
        "same_day_selected_avg_ret_20d": 0.016729,
        "slot_conflict_delta_20d": -0.034504
      }
    ]
  }
}

## Next Action

Do not promote a filing-presence sizing rule; exp-20260507-003 already failed. The next valid SEC/earnings step needs a richer event-quality discriminator with directional PIT fields or closed forward paper outcomes.
