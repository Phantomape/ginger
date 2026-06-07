# Experiment Ticket Schema

This file defines the minimum contract for multi-agent experiments. The goal is
to let agents explore in parallel while preserving one baseline, one judge, and
one attributable decision hypothesis or fixed policy bundle per experiment.

Operational sequence:

- `docs/agent_experiment_protocol.md`

Primary index:

- `docs/experiment_registry.json`

Per-experiment state:

- `experiments/tickets/exp-*.json`
- `experiments/logs/exp-*.json`

The registry is intentionally only a small index. Each agent mostly writes its
own ticket and final log file, so parallel experiments do not fight over one
large shared JSON document.

## Status Values

- `proposed`: ticket exists, no agent owns it yet.
- `claimed`: an agent owns the ticket and may start work inside the allowed scope.
- `running`: work is actively being evaluated.
- `accepted`: judge result passed the acceptance rule.
- `rejected`: judge result failed the acceptance rule.
- `observed_only`: analysis/instrumentation result with no strategy acceptance claim.
- `stale`: ticket should not be continued without refreshing the baseline.

## Lanes

- `alpha_search`: preferred lane for new entry, exit, ranking, allocation, or
  strategy hypotheses.
- `alpha_discovery`: new entry, exit, ranking, allocation, or strategy hypothesis.
- `loss_attribution`: bad-trade source analysis and failure taxonomy.
- `universe_scout`: new ticker universe, candidate source, or external alpha source.
- `measurement_repair`: replay, attribution, data snapshot, or production/backtest parity work.

## Required Ticket Fields

```json
{
  "experiment_id": "exp-20260425-001",
  "status": "proposed",
  "lane": "loss_attribution",
  "owner": null,
  "hypothesis": "Breakout losses cluster in one reproducible follow-through failure mode.",
  "change_type": "analysis_only",
  "implementation_mode": "observed_only_attribution",
  "mechanism_family": "breakout_loss_attribution",
  "trial_family": "breakout_follow_through_taxonomy",
  "trial_variant_id": "breakout_follow_through_taxonomy_v1",
  "single_causal_variable": "breakout follow-through taxonomy",
  "changed_variable": "breakout follow-through taxonomy",
  "causal_components": [
    "fixed taxonomy labels",
    "read-only attribution report"
  ],
  "prior_trial_count": 0,
  "nearby_prior_experiments": [],
  "multiple_testing_risk_bucket": "minimal",
  "new_evidence_type": "new_failure_taxonomy",
  "baseline_result_file": "data/backtests/backtest_results_20260425.json",
  "allowed_write_scope": [
    "quant/experiments/exp_20260425_001_breakout_follow_through_taxonomy.py",
    "data/experiments/exp-20260425-001/exp_20260425_001_breakout_follow_through_taxonomy.json",
    "experiments/cards/exp-20260425-001.md",
    "experiments/manifests/exp-20260425-001.json",
    "experiments/tickets/exp-20260425-001.json",
    "experiments/logs/exp-20260425-001.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json"
  ],
  "must_not_touch": [
    "quant/constants.py",
    "quant/signal_engine.py"
  ],
  "locked_variables": [
    "breakout follow-through taxonomy"
  ],
  "evaluation_windows": [
    {
      "start": "2025-10-23",
      "end": "2026-04-21"
    }
  ],
  "acceptance_rule": "observed_only; must produce reproducible bad-trade taxonomy",
  "prediction": {
    "success_probability": 0.35,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
      "sample_too_thin",
      "single_ticker_concentration",
      "replacement_value_failed"
    ],
    "confidence_reason": "Prior related evidence is positive, but forward rows are thin.",
    "recorded_at": "2026-04-25T00:00:00+00:00"
  },
  "production_impact": {
    "shared_policy_changed": false,
    "backtester_adapter_changed": false,
    "run_adapter_changed": false,
    "replay_only": false,
    "trade_enabled": false,
    "daily_snapshot_exposed": false,
    "live_realism_evaluated": false,
    "live_ready": false,
    "activation_envelope": null,
    "parity_test_added": false
  },
  "created_at": "2026-04-25T00:00:00-07:00",
  "claimed_at": null,
  "completed_at": null,
  "card_file": "experiments/cards/exp-20260425-001.md",
  "revision_manifest_file": "experiments/manifests/exp-20260425-001.json",
  "result": null
}
```

Reservation tooling writes `card_file` and `revision_manifest_file`
automatically. The experiment card is the human-readable summary; the revision
manifest records git revision, dirty status, and file hashes available at
reservation time.

Trial accounting fields help `quant/meta_research_engine.py` count nearby
research attempts without changing strategy behavior. Use them when they add
real meta-learning value; do not delay a good alpha test just to over-specify
labels that the tooling can default.

| Field | Meaning |
| --- | --- |
| `mechanism_family` | Durable mechanism-level family used for playbook synthesis. |
| `trial_family` | Narrow family used with `changed_variable` for repeated-trial counting. |
| `trial_variant_id` | Specific variant name for this sweep/scout/run. |
| `single_causal_variable` | Legacy field name for the one attributable decision hypothesis or fixed policy bundle under test. |
| `changed_variable` | Stable accounting key for the same decision hypothesis or policy bundle. |
| `causal_components` | Optional fixed components inside a predeclared bundle. These are not individually accepted unless separately ablated. |
| `prior_trial_count` | Known count of prior same-family or nearby trials before this run. |
| `nearby_prior_experiments` | Relevant accepted/rejected experiment IDs. |
| `multiple_testing_risk_bucket` | `minimal`, `low`, `moderate`, or `high`. |
| `new_evidence_type` | What makes this more than another nearby retry, or `not_declared`. |

`implementation_mode` is recommended for alpha and scout tickets. Use
`shared_paper_first` when the same helper will power historical replay and daily
default-off observation, `private_replay_scout` only for uncertain data-shape
discovery, `observed_only_attribution` for measurement without acceptance,
`activation_envelope` when the experiment only evaluates missing live-capital
constraints for an already accepted signal, and `live_release` when an
unchanged, already measured envelope is being enabled through configuration.

Do not interpret `single_causal_variable` as "only one code edit" or "only one
file." A ticket can reserve all files needed to evaluate one policy bundle:
shared helper, replay runner, daily snapshot/report/ledger wiring, parity tests,
activation envelope, card, manifest, and log. Splitting those mechanical pieces
into separate experiments is usually process waste. The boundary is attribution:
if the ticket combines unrelated alpha sources or multiple tunable degrees of
freedom, either predeclare the whole composite as the only accepted object or
split/ablate it before claiming component-level evidence.

For pure `measurement_repair` tickets these fields are recommended but may be
omitted when no alpha family is being evaluated.

`scripts/create_experiment_ticket.py` exposes matching optional flags:
`--mechanism-family`, `--trial-family`, `--trial-variant-id`,
`--changed-variable`, `--prior-trial-count`, `--nearby-prior-experiments`,
`--multiple-testing-risk-bucket`, and `--new-evidence-type`.

## Pre-Run Prediction

Every `alpha_search`, `alpha_discovery`, and `universe_scout` ticket must
include a pre-run `prediction` before the experiment starts. The ticket
creation code rejects these lanes unless `success_probability` and
`main_failure_modes` are present. This is the system's "exam estimate": it
records what the agent believed before seeing the result, so later
meta-learning can distinguish good judgement from lucky outcomes.

Keep the prediction concise but substantive. `confidence_reason` should carry
the hypothesis inference: why the edge should exist, which related experiments
raise or lower confidence, and which disconfirmers would make the result
unreliable. Do not add extra fields when that reasoning is already clear here.

Strategy-facing `measurement_repair` tickets should include a prediction when
the repair has a clear acceptance rule, but pure process repairs may omit it.

Fields:

| Field | Meaning |
| --- | --- |
| `success_probability` | Required for alpha/scout tickets. Probability from `0` to `1` that Gate 4 or the ticket acceptance rule will pass. |
| `expected_ev_delta` | Expected aggregate `expected_value_score` delta. |
| `expected_pnl_delta` | Expected aggregate PnL delta in dollars. |
| `main_failure_modes` | Required for alpha/scout tickets. Short normalized failure modes expected before the run. |
| `confidence_reason` | Short reason for the probability estimate. |
| `recorded_at` | Filled by tooling when the prediction is created. |

`scripts/create_experiment_ticket.py` exposes:
`--success-probability`, `--expected-ev-delta`, `--expected-pnl-delta`,
`--main-failure-modes`, and `--confidence-reason`.

`scripts/judge_experiment.py` copies the prediction into the final log draft
and adds a `calibration` block with the actual decision, Brier score,
overconfident / underconfident label, EV/PnL prediction error, and optional
failure-mode hit. Use `--realized-failure-mode` and `--surprise-note` when the
result has a clear post-run lesson.

`scripts/experiment.py audit` separates historical gaps into
`legacy_pre_enforcement_*` and `post_enforcement_*`. Use `--strict` to fail on
post-enforcement gaps only; do not backfill legacy predictions from hindsight.

## Acceptance Rule

For strategy-affecting experiments, `scripts/judge_experiment.py` uses the
repository gate:

- `expected_value_score` improves by more than 10%, or
- Sharpe improves by more than 0.1, or
- max drawdown falls by more than 1 percentage point, or
- total PnL improves by more than 5%, or
- trade count increases while win rate does not decline.

Measurement and analysis tickets may be marked `observed_only`, but they must
still record the artifact that makes the next alpha experiment more testable.

## Production Impact Rule

Every ticket that can affect executable trade behavior must include
`production_impact`. The fields mean:

| Field | Meaning |
| --- | --- |
| `shared_policy_changed` | A shared decision module or strategy constant changed. |
| `backtester_adapter_changed` | Historical replay wiring changed. |
| `run_adapter_changed` | Daily production wiring, report, JSON, or prompt exposure changed. |
| `replay_only` | The difference is an allowed historical-data limitation, not duplicate strategy logic. |
| `trade_enabled` | The experiment can place or alter live/default executable trades. |
| `daily_snapshot_exposed` | The same candidate/rule is visible through a daily default-off snapshot, report, or ledger path. |
| `live_realism_evaluated` | The experiment measured the real-capital envelope: notional/caps, liquidity/slippage, displacement, exposure, kill switch, and order semantics. |
| `live_ready` | The result is eligible for a `trade_enabled=true` release without another alpha search, assuming the envelope remains unchanged. |
| `activation_envelope` | Structured summary of the measured notional, capital cap, liquidity/slippage model, portfolio displacement, exposure limits, kill switch, and order semantics. |
| `parity_test_added` | A focused test or manifest update guards the production/backtest contract. |

If `shared_policy_changed=true`, then either `run_adapter_changed=true` or
`replay_only=true` must be true, except for
`implementation_mode=shared_paper_first` default-off alpha where
`trade_enabled=false`, `daily_snapshot_exposed=true`, and a parity test or
parity-contract update records the shared replay/daily semantics. Otherwise the
experiment is backtester-only and must not be accepted. Allowed replay-only
differences are listed in `docs/production_backtest_parity.md`.

If an alpha could plausibly be promoted to live capital, its ticket or final log
must say whether the live-realistic envelope is being measured. A positive
paper result with `live_realism_evaluated=false` may be accepted as
default-off/observe-ready, but it is not live-ready. If
`live_realism_evaluated=true`, `live_ready=true`, and the later release does not
change the envelope, enabling `trade_enabled=true` can be handled as a
release/config record instead of a new alpha experiment.

Example observed-only closeout:

```powershell
python scripts\judge_experiment.py `
  --experiment-id exp-20260425-001 `
  --before data\backtests\backtest_results_20260424.json `
  --after data\backtests\backtest_results_20260425.json `
  --status-override observed_only `
  --change-summary "Recorded a reproducible loss taxonomy." `
  --append-log `
  --write-registry
```

`--append-log` writes the generated row to
`experiments/logs/<experiment_id>.json`. Duplicate experiment IDs are
rejected unless `--allow-duplicate-log-id` is set.

## Conflict Rules

`scripts/claim_experiment.py` blocks a claim when another active ticket
(`claimed` or `running`) overlaps either:

- `allowed_write_scope`, or
- `locked_variables`.

The shared coordination files below are ignored for scope conflicts because
every agent needs them for closeout:

- `docs/experiment_log.jsonl`
- `docs/experiment_registry.json`

Actual writes to those files are still protected by lock files:

- `docs/experiment_log.jsonl.lock`
- `docs/experiment_registry.json.lock`

The scripts wait for the lock by default and recover stale locks after the
configured stale-lock window. Use `--lock-timeout-seconds` to fail faster in a
busy multi-agent run.

Use narrow write scopes. A broad scope such as `quant/` should be treated as
exclusive ownership of that whole area.

## Automatic Write Scopes

`scripts/create_experiment_ticket.py` now generates per-experiment write scopes
when `--allowed-write-scope` is omitted. This is the default for parallel
agents because the script knows the assigned `experiment_id` and can create
non-overlapping paths:

- `quant/experiments/<experiment_id_as_prefix>_<slug>.py`
- `data/experiments/<experiment_id>/<experiment_id_as_prefix>_<slug>.json`
- `experiments/tickets/<experiment_id>.json`
- `experiments/logs/<experiment_id>.json`
- `docs/experiment_log.jsonl`
- `docs/experiment_registry.json`

The default `<slug>` is derived from `--single-causal-variable` /
`--decision-variable`, so a ticket with
`single_causal_variable="bad trade hold-quality taxonomy"` creates names like
`exp_20260427_010_bad_trade_hold_quality_taxonomy.py`. If an agent wants a
shorter explicit name, pass `--file-slug hold_quality_audit`.

Do not use broad directory scopes such as `data/`, `quant/`, `docs/`, or
`scripts/` for ordinary experiments. They serialize unrelated agents because
claim conflict detection treats parent and child paths as overlapping. The
ticket creation script rejects those broad scopes unless
`--exclusive-scope-ok` is passed.

When a custom scope is needed but the experiment id is not known yet, use
templates:

```powershell
python scripts\create_experiment_ticket.py `
  --lane alpha_discovery `
  --hypothesis "One narrow shadow source." `
  --change-type new_strategy_shadow `
  --single-causal-variable "one shadow source" `
  --allowed-write-scope "quant/experiments/{experiment_id}_{lane}.py,data/experiments/{experiment_id}/{change_type}.json"
```
