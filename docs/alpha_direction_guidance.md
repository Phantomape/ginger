# Alpha Direction Guidance

> This document turns the current analyst-style alpha menu into a repository
> guidance note. It is not a trading rule, not an experiment log, and not
> acceptance evidence. Use it to choose the next alpha hypothesis before
> reserving an experiment ID.

Last updated: 2026-06-06.

---

## 1. One-Sentence Decision

The next highest-value alpha direction is:

```text
Analyst Revision / Expectation Trajectory
+
Earnings Drift / PEAD Continuation
```

The reason is not just theoretical alpha potential. It is the intersection of:

- high information content;
- replayable daily data;
- fit with Ginger's medium-term EOD system;
- existing measurement infrastructure;
- recent experiment history showing that OHLCV, source-consensus, Space, and
  small notional-scalar lanes are now crowded or saturated.

---

## 2. Adjusted Priority Table

The analyst table is directionally right, but Ginger should rank by
implementation value, not only theoretical alpha.

| Direction | Theory alpha | Ginger priority | Current verdict | Next valid work |
|---|---:|---:|---|---|
| Earnings Drift | 10/10 | 9/10 | High potential, but simple surprise / PEAD threshold mining is saturated. | Model surprise history, post-event underreaction, and 10d+ continuation. |
| Analyst Revision | 9/10 | 10/10 | Best underdeveloped free-data lane. | Build PIT revision velocity, persistence, and analyst-count trajectory fields. |
| SEC Filing + LLM | 9/10 | 8/10 | High potential, but simple phrase/source/recurrence tests failed often. | Extract schema-bound semantic fields with evidence spans; no LLM trade authority. |
| Insider Buy | 8/10 | 6/10 | Form 4 as a consensus source failed; still useful if signal is richer. | Test ownership intensity, purchase value vs liquidity, and forward outcomes. |
| Quality Factor | 6/10 | 6/10 | Companyfacts has accepted roots but nearby scalar mining is crowded. | Use materially new PIT fields, not more support-scalar tweaks. |
| Breakout Momentum | 7/10 | 3/10 | Core implementation is mature; OHLCV remixes have weak marginal value. | Use only as confirmation or replacement-value context. |
| Trend Following | 5/10 | 2/10 | Core implementation is mature. | Do not make it the next alpha-search lead without new data. |
| Stat Arb | 3/10 | 1/10 | Poor fit for current data frequency and execution model. | Defer. |
| HFT | 1/10 | 0/10 | Not compatible with this system. | Do not pursue. |

---

## 3. Why The Ranking Changed

### Earnings Drift

Keep this as a top lane, but do not repeat the weak variants.

Past evidence says simple forms are not enough:

- generic post-earnings reaction pools were rejected;
- latest surprise minus average surprise support failed cross-window Gate 4;
- nearby high-liquidity, sector-residual, and core-overlap support layers are
  already saturated.

Valid next work:

- surprise-history trajectory;
- expectation adjustment before and after earnings;
- T+10 / T+15 continuation instead of only 5d;
- replacement value versus the exact displaced core or paper candidate.

Invalid next work:

- another `latest_surprise_pct` threshold;
- another PEAD notional scalar;
- another same-window retune of the accepted
  `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` stack.

### Analyst Revision

This is the best current alpha target because it supplies information upstream
of price while still fitting the daily, replayable system.

Valid next work:

- `eps_revision_velocity_7d`;
- `eps_revision_velocity_30d`;
- `revision_persistence_bucket`;
- `revision_acceleration_bucket`;
- `analyst_count_delta_30d`;
- `revenue_revision_velocity_30d`, if available;
- strict PIT snapshot provenance and missing-data buckets.

If PIT coverage or field shape is unknown, start with attribution or
observed-only coverage measurement. Once coverage is adequate, the first
serious alpha test should be a shared default-off paper helper, not a private
replay scout. Do not promote it into live ranking or sizing until the shared
field is replayable, production-visible, and passes Gate 1-4 activation.

### SEC Filing + LLM

The high-potential version is not "LLM reads SEC and buys stocks." The valid
version is deterministic, schema-bound semantic extraction.

Valid next fields:

- guidance raise / cut / reaffirmed;
- customer demand strength;
- backlog or order-book expansion;
- margin pressure vs revenue strength;
- risk-disclosure deterioration;
- text-price alignment with evidence spans;
- source-span provenance and parse-failure buckets.

Hard boundary:

- LLM may classify evidence;
- LLM may propose hypotheses;
- LLM must not own entry, sizing, ranking, exits, or orders.

### Insider Buy

Form 4 is not dead, but the naive version is weak. Same-day insertion into the
accepted consensus source family produced zero selected rows. Owner-count alone
also failed prior gates.

Valid next work:

- purchase value relative to daily dollar volume;
- insider role and repeat-buy intensity;
- cluster purchase intensity;
- purchase price relative to recent range;
- forward replacement value versus the raw Form 4 queue and current candidates.

Invalid next work:

- same-day Form 4 consensus source-family retry;
- owner-count-only retry;
- single-ticker insider anecdote.

### Quality Factor

Quality can still help, but the accepted Companyfacts route has already been
mined heavily. The next useful test needs a materially new field.

Valid next fields:

- cash conversion durability;
- operating-margin durability;
- liability discipline;
- inventory discipline only if not repeating rejected variants;
- earnings quality paired with revision trajectory.

Invalid next work:

- another Companyfacts support scalar around the accepted operating-profit +
  RS stack;
- another threshold split with no new field.

### Breakout Momentum And Trend

These are no longer primary alpha-search directions. They are mature execution
and confirmation surfaces.

Use them as:

- confirmation for revision or SEC semantic candidates;
- displacement / replacement-value comparators;
- cost and liquidity context.

Do not use them as:

- another renamed OHLCV candidate pool;
- another top-N, range, volume, or high-close threshold sweep.

---

## 4. Recommended Next Experiments

### 4.1 Revision Drift Readiness And Attribution

Hypothesis:

```text
Tickers with positive, persistent PIT analyst/estimate revision trajectory have
better 10d/20d replacement value than ordinary momentum candidates.
```

Class:

```text
alpha_search or observed-only attribution, depending on field coverage.
```

Single causal variable:

```text
revision_trajectory_bucket_v1
```

Minimum buckets:

- positive persistent revision;
- positive one-shot revision;
- flat revision;
- negative revision;
- missing / not PIT-usable.

Acceptance clue:

- preferred bucket must beat comparison buckets across the standard windows;
- 10d/20d evidence matters more than 5d if the prior 5d PEAD work remains
  negative;
- concentration and replacement value must pass.

### 4.2 Revision × Post-Earnings Drift Paper Queue

Hypothesis:

```text
Post-earnings candidates with positive surprise history and positive revision
trajectory continue to drift better than post-earnings candidates without
revision support.
```

Class:

```text
shared default-off paper helper first; replay-only scout only if field shape is
still uncertain.
```

Hard constraints:

- no live orders;
- no core ranking change;
- no LLM authority;
- daily production must be able to emit the same fields in the same shared
  helper experiment when the fields are already PIT-safe.

### 4.3 SEC Semantic Field Scout

Hypothesis:

```text
SEC filings with audited positive business-quality semantics and supportive
price reaction have higher replacement value than generic SEC event rows.
```

Class:

```text
schema-bound LLM / rule extraction; use read-only attribution only when coverage
or parse quality is unknown, otherwise use a shared default-off paper helper.
```

Minimum provenance:

- accession number;
- filing timestamp;
- document span;
- semantic schema version;
- retrieval / parse / reasoning failure bucket;
- PIT usable trade date.

### 4.4 Insider Ownership Intensity

Hypothesis:

```text
Open-market insider purchases are useful only when purchase intensity is
material relative to liquidity and ownership context.
```

Class:

```text
shared default-off paper helper when PIT fields exist; observed-only
attribution only for coverage or provenance audit.
```

Minimum fields:

- purchase value vs 20d dollar volume;
- buyer role;
- repeat buyer flag;
- cluster count;
- purchase price vs recent close / range;
- same-ticker cooldown;
- replacement value versus the existing Form 4 queue.

---

## 5. Direction Selection Rules

When choosing the next alpha search:

1. Prefer Analyst Revision x Earnings Drift unless the PIT fields are not
   available or the bucket sample is too thin.
2. If revision data is blocked, move to SEC semantic fields with auditable
   spans.
3. If SEC semantic fields lack coverage, move to insider ownership intensity.
4. If all three are blocked, use forward replacement-value maturation for the
   accepted free-data paper adapters.
5. Do not spend the next primary search on Breakout, Trend, Space segment
   support, source-consensus retunes, or state-surface scalar mining unless new
   forward evidence changes the prior.

---

## 6. Anti-Repeat Guardrails

Do not re-run these as primary alpha directions on the current frozen windows:

- latest-surprise / average-surprise support scalars;
- nearby post-earnings underpriced drift support scalars;
- Form 4 same-day consensus source-family insertion;
- broad OHLCV pattern pools that only rename breakout momentum;
- VCP / QQQ / top-N / hold-period retunes;
- accepted lagged-consensus notional, rank, source-set, or window retunes;
- Space segment or Space event-state scalar mining;
- Companyfacts support-scalar tweaks without a new PIT field;
- LLM direct buy/sell/sizing/ranking authority.

---

## 7. Practical Default For Future Agents

If no measurement blocker exists, the default next alpha hypothesis should look
like this:

```text
Positive PIT revision trajectory plus post-earnings continuation produces
better 10d/20d replacement value than the current candidate it displaces.
```

The default rejection rule should be:

```text
Reject if the result only improves one window, only improves standalone PnL
versus cash, depends on one ticker, lacks PIT production visibility, or cannot
be represented as a shared production/backtest policy before promotion.
```

If field coverage is already known, the default implementation should be
shared-paper-first: one helper that powers historical replay and daily
default-off observation in the same accepted experiment.

The goal is to add a real information edge, not another layer of clever
allocation on the same old signals.
