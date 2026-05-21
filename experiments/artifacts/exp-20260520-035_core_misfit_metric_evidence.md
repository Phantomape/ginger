# exp-20260520-035 paper_replay_reference_v1

Decision: `accepted_default_off_observation_not_live`.

## Hypothesis

Core-misfit should mature as no-trade avoided-value evidence before any live short, haircut, or exclusion path.

## Trial Accounting

- mechanism_family: `core_misfit_no_trade`
- trial_family: `core_misfit_no_trade_forward_maturation`
- changed_variable: `core_misfit_trend_only_paper_scope`
- prior_trial_count: `3`
- multiple_testing_risk_bucket: `minimal`

## Metric Evidence

```json
{
  "conditioned_short_shadow_reference": {
    "condition_gate_summaries": {
      "all_identity": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 1065.59,
            "trade_count": 2,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 2
          },
          "ISRG": {
            "losses": 1,
            "pnl": -568.07,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 1
          },
          "TSM": {
            "losses": 1,
            "pnl": 105.76,
            "trade_count": 3,
            "win_rate": 0.6667,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 2
          },
          "V": {
            "losses": 1,
            "pnl": 5476.38,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 1,
            "pnl": -776.16,
            "trade_count": 2,
            "win_rate": 0.5,
            "wins": 1
          },
          "old_thin": {
            "losses": 2,
            "pnl": 6855.82,
            "trade_count": 7,
            "win_rate": 0.7143,
            "wins": 5
          }
        },
        "max_consecutive_losses": 2,
        "max_drawdown_pct": 0.007345,
        "positive_windows": [
          "old_thin"
        ],
        "total_pnl": 6079.66,
        "total_return_pct": 0.060797,
        "trade_count": 9,
        "win_rate": 0.6667,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 1,
        "wins": 6,
        "worst_trade_pct": -0.045299
      },
      "available_slots_lte_3": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 0.01,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "ISRG": {
            "losses": 0,
            "pnl": 216.9,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "TSM": {
            "losses": 0,
            "pnl": 8.81,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "mid_weak"
            ],
            "wins": 1
          },
          "V": {
            "losses": 1,
            "pnl": 5476.38,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 0,
            "pnl": 8.81,
            "trade_count": 1,
            "win_rate": 1.0,
            "wins": 1
          },
          "old_thin": {
            "losses": 1,
            "pnl": 5693.29,
            "trade_count": 4,
            "win_rate": 0.75,
            "wins": 3
          }
        },
        "max_consecutive_losses": 1,
        "max_drawdown_pct": 0.001869,
        "positive_windows": [
          "mid_weak",
          "old_thin"
        ],
        "total_pnl": 5702.1,
        "total_return_pct": 0.057021,
        "trade_count": 5,
        "win_rate": 0.8,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 2,
        "wins": 4,
        "worst_trade_pct": -0.003693
      },
      "breakout_long_only": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 1065.58,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "ISRG": {
            "losses": 1,
            "pnl": -784.97,
            "trade_count": 1,
            "win_rate": 0.0,
            "windows": [
              "mid_weak"
            ],
            "wins": 0
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 1,
            "pnl": -784.97,
            "trade_count": 1,
            "win_rate": 0.0,
            "wins": 0
          },
          "old_thin": {
            "losses": 0,
            "pnl": 1065.58,
            "trade_count": 1,
            "win_rate": 1.0,
            "wins": 1
          }
        },
        "max_consecutive_losses": 1,
        "max_drawdown_pct": 0.007767,
        "positive_windows": [
          "old_thin"
        ],
        "total_pnl": 280.61,
        "total_return_pct": 0.002806,
        "trade_count": 2,
        "win_rate": 0.5,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 1,
        "wins": 1,
        "worst_trade_pct": -0.045299
      },
      "not_risk_on_tagged": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 0.01,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "TSM": {
            "losses": 1,
            "pnl": 105.76,
            "trade_count": 3,
            "win_rate": 0.6667,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 2
          },
          "V": {
            "losses": 1,
            "pnl": 5476.38,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 0,
            "pnl": 8.81,
            "trade_count": 1,
            "win_rate": 1.0,
            "wins": 1
          },
          "old_thin": {
            "losses": 2,
            "pnl": 5573.34,
            "trade_count": 5,
            "win_rate": 0.6,
            "wins": 3
          }
        },
        "max_consecutive_losses": 2,
        "max_drawdown_pct": 0.00196,
        "positive_windows": [
          "mid_weak",
          "old_thin"
        ],
        "total_pnl": 5582.15,
        "total_return_pct": 0.055822,
        "trade_count": 6,
        "win_rate": 0.6667,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 2,
        "wins": 4,
        "worst_trade_pct": -0.020301
      },
      "risk_on_tagged": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 1065.58,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "ISRG": {
            "losses": 1,
            "pnl": -568.07,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 1,
            "pnl": -784.97,
            "trade_count": 1,
            "win_rate": 0.0,
            "wins": 0
          },
          "old_thin": {
            "losses": 0,
            "pnl": 1282.48,
            "trade_count": 2,
            "win_rate": 1.0,
            "wins": 2
          }
        },
        "max_consecutive_losses": 1,
        "max_drawdown_pct": 0.00775,
        "positive_windows": [
          "old_thin"
        ],
        "total_pnl": 497.51,
        "total_return_pct": 0.004975,
        "trade_count": 3,
        "win_rate": 0.6667,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 1,
        "wins": 2,
        "worst_trade_pct": -0.045299
      },
      "target_mult_gte_6": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 0.01,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "TSM": {
            "losses": 1,
            "pnl": 105.76,
            "trade_count": 3,
            "win_rate": 0.6667,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 2
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 0,
            "pnl": 8.81,
            "trade_count": 1,
            "win_rate": 1.0,
            "wins": 1
          },
          "old_thin": {
            "losses": 1,
            "pnl": 96.96,
            "trade_count": 3,
            "win_rate": 0.6667,
            "wins": 2
          }
        },
        "max_consecutive_losses": 1,
        "max_drawdown_pct": 8.8e-05,
        "positive_windows": [
          "mid_weak",
          "old_thin"
        ],
        "total_pnl": 105.77,
        "total_return_pct": 0.001058,
        "trade_count": 4,
        "win_rate": 0.75,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 2,
        "wins": 3,
        "worst_trade_pct": -0.020301
      },
      "trade_quality_gte_0_95": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 0.01,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "ISRG": {
            "losses": 0,
            "pnl": 216.9,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "TSM": {
            "losses": 1,
            "pnl": 96.95,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "old_thin": {
            "losses": 1,
            "pnl": 313.86,
            "trade_count": 4,
            "win_rate": 0.75,
            "wins": 3
          }
        },
        "max_consecutive_losses": 1,
        "max_drawdown_pct": 8.8e-05,
        "positive_windows": [
          "old_thin"
        ],
        "total_pnl": 313.86,
        "total_return_pct": 0.003139,
        "trade_count": 4,
        "win_rate": 0.75,
        "windows": [
          "old_thin"
        ],
        "windows_positive_count": 1,
        "wins": 3,
        "worst_trade_pct": -0.020301
      },
      "trade_quality_lt_0_95": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 1065.58,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "ISRG": {
            "losses": 1,
            "pnl": -784.97,
            "trade_count": 1,
            "win_rate": 0.0,
            "windows": [
              "mid_weak"
            ],
            "wins": 0
          },
          "TSM": {
            "losses": 0,
            "pnl": 8.81,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "mid_weak"
            ],
            "wins": 1
          },
          "V": {
            "losses": 1,
            "pnl": 5476.38,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 1,
            "pnl": -776.16,
            "trade_count": 2,
            "win_rate": 0.5,
            "wins": 1
          },
          "old_thin": {
            "losses": 1,
            "pnl": 6541.96,
            "trade_count": 3,
            "win_rate": 0.6667,
            "wins": 2
          }
        },
        "max_consecutive_losses": 1,
        "max_drawdown_pct": 0.007367,
        "positive_windows": [
          "old_thin"
        ],
        "total_pnl": 5765.8,
        "total_return_pct": 0.057658,
        "trade_count": 5,
        "win_rate": 0.6,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 1,
        "wins": 3,
        "worst_trade_pct": -0.045299
      },
      "trend_long_only": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 0.01,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "ISRG": {
            "losses": 0,
            "pnl": 216.9,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "TSM": {
            "losses": 1,
            "pnl": 105.76,
            "trade_count": 3,
            "win_rate": 0.6667,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 2
          },
          "V": {
            "losses": 1,
            "pnl": 5476.38,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 0,
            "pnl": 8.81,
            "trade_count": 1,
            "win_rate": 1.0,
            "wins": 1
          },
          "old_thin": {
            "losses": 2,
            "pnl": 5790.24,
            "trade_count": 6,
            "win_rate": 0.6667,
            "wins": 4
          }
        },
        "max_consecutive_losses": 2,
        "max_drawdown_pct": 0.001955,
        "positive_windows": [
          "mid_weak",
          "old_thin"
        ],
        "total_pnl": 5799.05,
        "total_return_pct": 0.057991,
        "trade_count": 7,
        "win_rate": 0.7143,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 2,
        "wins": 5,
        "worst_trade_pct": -0.020301
      }
    },
    "decision": "promising_replay_only_conditioned_short_shadow_not_live_promotable",
    "rejection_reason": null,
    "selection": {
      "all_passing_gates": [
        "trend_long_only",
        "available_slots_lte_3",
        "not_risk_on_tagged"
      ],
      "condition_gate_passed": true,
      "identity_summary": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 1065.59,
            "trade_count": 2,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 2
          },
          "ISRG": {
            "losses": 1,
            "pnl": -568.07,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 1
          },
          "TSM": {
            "losses": 1,
            "pnl": 105.76,
            "trade_count": 3,
            "win_rate": 0.6667,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 2
          },
          "V": {
            "losses": 1,
            "pnl": 5476.38,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 1,
            "pnl": -776.16,
            "trade_count": 2,
            "win_rate": 0.5,
            "wins": 1
          },
          "old_thin": {
            "losses": 2,
            "pnl": 6855.82,
            "trade_count": 7,
            "win_rate": 0.7143,
            "wins": 5
          }
        },
        "max_consecutive_losses": 2,
        "max_drawdown_pct": 0.007345,
        "positive_windows": [
          "old_thin"
        ],
        "total_pnl": 6079.66,
        "total_return_pct": 0.060797,
        "trade_count": 9,
        "win_rate": 0.6667,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 1,
        "wins": 6,
        "worst_trade_pct": -0.045299
      },
      "live_short_promotable": false,
      "live_short_rejected_reason": "This is still historical fixed-window evidence only; it ignores borrow/locate costs and lacks the forward CORE_MISFIT_PAPER closed-outcome gate required before live shorting.",
      "selected_gate": "trend_long_only",
      "selected_summary": {
        "by_ticker": {
          "DDOG": {
            "losses": 0,
            "pnl": 0.01,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "ISRG": {
            "losses": 0,
            "pnl": 216.9,
            "trade_count": 1,
            "win_rate": 1.0,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          },
          "TSM": {
            "losses": 1,
            "pnl": 105.76,
            "trade_count": 3,
            "win_rate": 0.6667,
            "windows": [
              "mid_weak",
              "old_thin"
            ],
            "wins": 2
          },
          "V": {
            "losses": 1,
            "pnl": 5476.38,
            "trade_count": 2,
            "win_rate": 0.5,
            "windows": [
              "old_thin"
            ],
            "wins": 1
          }
        },
        "by_window": {
          "mid_weak": {
            "losses": 0,
            "pnl": 8.81,
            "trade_count": 1,
            "win_rate": 1.0,
            "wins": 1
          },
          "old_thin": {
            "losses": 2,
            "pnl": 5790.24,
            "trade_count": 6,
            "win_rate": 0.6667,
            "wins": 4
          }
        },
        "max_consecutive_losses": 2,
        "max_drawdown_pct": 0.001955,
        "positive_windows": [
          "mid_weak",
          "old_thin"
        ],
        "total_pnl": 5799.05,
        "total_return_pct": 0.057991,
        "trade_count": 7,
        "win_rate": 0.7143,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "windows_positive_count": 2,
        "wins": 5,
        "worst_trade_pct": -0.020301
      }
    },
    "source_artifact": "data/experiments/exp-20260518-019/core_misfit_conditioned_short_shadow.json",
    "source_experiment": "exp-20260518-019"
  },
  "core_metrics_changed": false,
  "decision": "accepted_default_off_core_misfit_trend_only_paper_scope",
  "evidence_type": "paper_replay_no_trade_and_conditioned_short_shadow",
  "gate4": {
    "acceptance_standard": "retain >=95% identity paper PnL and improve positive windows, worst trade, and max drawdown without changing core metrics",
    "live_short_promotable": false,
    "live_short_rejected_reason": "The forward CORE_MISFIT_PAPER closed-outcome gate is still not met; this only changes default-off observation scope.",
    "paper_after": {
      "by_ticker": {
        "DDOG": {
          "losses": 0,
          "pnl": 0.01,
          "trade_count": 1,
          "win_rate": 1.0,
          "windows": [
            "old_thin"
          ],
          "wins": 1
        },
        "ISRG": {
          "losses": 0,
          "pnl": 216.9,
          "trade_count": 1,
          "win_rate": 1.0,
          "windows": [
            "old_thin"
          ],
          "wins": 1
        },
        "TSM": {
          "losses": 1,
          "pnl": 105.76,
          "trade_count": 3,
          "win_rate": 0.6667,
          "windows": [
            "mid_weak",
            "old_thin"
          ],
          "wins": 2
        },
        "V": {
          "losses": 1,
          "pnl": 5476.38,
          "trade_count": 2,
          "win_rate": 0.5,
          "windows": [
            "old_thin"
          ],
          "wins": 1
        }
      },
      "by_window": {
        "late_strong": {
          "losses": 0,
          "pnl": 0.0,
          "trade_count": 0,
          "win_rate": null,
          "wins": 0
        },
        "mid_weak": {
          "losses": 0,
          "pnl": 8.81,
          "trade_count": 1,
          "win_rate": 1.0,
          "wins": 1
        },
        "old_thin": {
          "losses": 2,
          "pnl": 5790.24,
          "trade_count": 6,
          "win_rate": 0.6667,
          "wins": 4
        }
      },
      "canonical_windows": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ],
      "max_consecutive_losses": 2,
      "max_drawdown_pct": 0.001955,
      "positive_windows": [
        "mid_weak",
        "old_thin"
      ],
      "total_pnl": 5799.05,
      "total_return_pct": 0.057991,
      "trade_count": 7,
      "win_rate": 0.7143,
      "windows": [
        "mid_weak",
        "old_thin"
      ],
      "windows_positive_count": 2,
      "wins": 5,
      "worst_trade_pct": -0.020301,
      "zero_trade_windows": [
        "late_strong"
      ]
    },
    "paper_before": {
      "by_ticker": {
        "DDOG": {
          "losses": 0,
          "pnl": 1065.59,
          "trade_count": 2,
          "win_rate": 1.0,
          "windows": [
            "old_thin"
          ],
          "wins": 2
        },
        "ISRG": {
          "losses": 1,
          "pnl": -568.07,
          "trade_count": 2,
          "win_rate": 0.5,
          "windows": [
            "mid_weak",
            "old_thin"
          ],
          "wins": 1
        },
        "TSM": {
          "losses": 1,
          "pnl": 105.76,
          "trade_count": 3,
          "win_rate": 0.6667,
          "windows": [
            "mid_weak",
            "old_thin"
          ],
          "wins": 2
        },
        "V": {
          "losses": 1,
          "pnl": 5476.38,
          "trade_count": 2,
          "win_rate": 0.5,
          "windows": [
            "old_thin"
          ],
          "wins": 1
        }
      },
      "by_window": {
        "late_strong": {
          "losses": 0,
          "pnl": 0.0,
          "trade_count": 0,
          "win_rate": null,
          "wins": 0
        },
        "mid_weak": {
          "losses": 1,
          "pnl": -776.16,
          "trade_count": 2,
          "win_rate": 0.5,
          "wins": 1
        },
        "old_thin": {
          "losses": 2,
          "pnl": 6855.82,
          "trade_count": 7,
          "win_rate": 0.7143,
          "wins": 5
        }
      },
      "canonical_windows": [
        "late_strong",
        "mid_weak",
        "old_thin"
      ],
      "max_consecutive_losses": 2,
      "max_drawdown_pct": 0.007345,
      "positive_windows": [
        "old_thin"
      ],
      "total_pnl": 6079.66,
      "total_return_pct": 0.060797,
      "trade_count": 9,
      "win_rate": 0.6667,
      "windows": [
        "mid_weak",
        "old_thin"
      ],
      "windows_positive_count": 1,
      "wins": 6,
      "worst_trade_pct": -0.045299,
      "zero_trade_windows": [
        "late_strong"
      ]
    },
    "paper_delta": {
      "max_drawdown_pct_delta": -0.00539,
      "pnl_retention_ratio": 0.953844,
      "positive_window_delta": 1,
      "total_pnl_delta": -280.61,
      "trade_count_delta": -2,
      "win_rate_delta": 0.0476,
      "worst_trade_pct_delta": 0.024998
    },
    "passed": true
  },
  "interpretation": "Trend-only keeps 95%+ of the paper inverse PnL while improving positive window count, win rate, worst trade, and max drawdown. Promote only the default-off paper candidate scope; live orders and live shorts remain disabled.",
  "live_gate_blocker": "Need at least 20 closed 10d CORE_MISFIT_PAPER outcomes before live-path haircut or exclusion tests.",
  "paper_after": {
    "by_ticker": {
      "DDOG": {
        "losses": 0,
        "pnl": 0.01,
        "trade_count": 1,
        "win_rate": 1.0,
        "windows": [
          "old_thin"
        ],
        "wins": 1
      },
      "ISRG": {
        "losses": 0,
        "pnl": 216.9,
        "trade_count": 1,
        "win_rate": 1.0,
        "windows": [
          "old_thin"
        ],
        "wins": 1
      },
      "TSM": {
        "losses": 1,
        "pnl": 105.76,
        "trade_count": 3,
        "win_rate": 0.6667,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "wins": 2
      },
      "V": {
        "losses": 1,
        "pnl": 5476.38,
        "trade_count": 2,
        "win_rate": 0.5,
        "windows": [
          "old_thin"
        ],
        "wins": 1
      }
    },
    "by_window": {
      "late_strong": {
        "losses": 0,
        "pnl": 0.0,
        "trade_count": 0,
        "win_rate": null,
        "wins": 0
      },
      "mid_weak": {
        "losses": 0,
        "pnl": 8.81,
        "trade_count": 1,
        "win_rate": 1.0,
        "wins": 1
      },
      "old_thin": {
        "losses": 2,
        "pnl": 5790.24,
        "trade_count": 6,
        "win_rate": 0.6667,
        "wins": 4
      }
    },
    "canonical_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_consecutive_losses": 2,
    "max_drawdown_pct": 0.001955,
    "positive_windows": [
      "mid_weak",
      "old_thin"
    ],
    "total_pnl": 5799.05,
    "total_return_pct": 0.057991,
    "trade_count": 7,
    "win_rate": 0.7143,
    "windows": [
      "mid_weak",
      "old_thin"
    ],
    "windows_positive_count": 2,
    "wins": 5,
    "worst_trade_pct": -0.020301,
    "zero_trade_windows": [
      "late_strong"
    ]
  },
  "paper_before": {
    "by_ticker": {
      "DDOG": {
        "losses": 0,
        "pnl": 1065.59,
        "trade_count": 2,
        "win_rate": 1.0,
        "windows": [
          "old_thin"
        ],
        "wins": 2
      },
      "ISRG": {
        "losses": 1,
        "pnl": -568.07,
        "trade_count": 2,
        "win_rate": 0.5,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "wins": 1
      },
      "TSM": {
        "losses": 1,
        "pnl": 105.76,
        "trade_count": 3,
        "win_rate": 0.6667,
        "windows": [
          "mid_weak",
          "old_thin"
        ],
        "wins": 2
      },
      "V": {
        "losses": 1,
        "pnl": 5476.38,
        "trade_count": 2,
        "win_rate": 0.5,
        "windows": [
          "old_thin"
        ],
        "wins": 1
      }
    },
    "by_window": {
      "late_strong": {
        "losses": 0,
        "pnl": 0.0,
        "trade_count": 0,
        "win_rate": null,
        "wins": 0
      },
      "mid_weak": {
        "losses": 1,
        "pnl": -776.16,
        "trade_count": 2,
        "win_rate": 0.5,
        "wins": 1
      },
      "old_thin": {
        "losses": 2,
        "pnl": 6855.82,
        "trade_count": 7,
        "win_rate": 0.7143,
        "wins": 5
      }
    },
    "canonical_windows": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ],
    "max_consecutive_losses": 2,
    "max_drawdown_pct": 0.007345,
    "positive_windows": [
      "old_thin"
    ],
    "total_pnl": 6079.66,
    "total_return_pct": 0.060797,
    "trade_count": 9,
    "win_rate": 0.6667,
    "windows": [
      "mid_weak",
      "old_thin"
    ],
    "windows_positive_count": 1,
    "wins": 6,
    "worst_trade_pct": -0.045299,
    "zero_trade_windows": [
      "late_strong"
    ]
  },
  "paper_delta": {
    "max_drawdown_pct_delta": -0.00539,
    "pnl_retention_ratio": 0.953844,
    "positive_window_delta": 1,
    "total_pnl_delta": -280.61,
    "trade_count_delta": -2,
    "win_rate_delta": 0.0476,
    "worst_trade_pct_delta": 0.024998
  },
  "source_artifact": "data/experiments/exp-20260518-022/core_misfit_trend_only_paper_scope.json",
  "source_experiment": "exp-20260518-022"
}
```

## Next Evidence Needed

Reach 20 closed 10d CORE_MISFIT_PAPER outcomes, then test exactly one live-path haircut or exclusion variable.
