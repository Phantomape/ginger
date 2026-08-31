"""exp-20260831-001: quiet-tape delayed repricing falsification (observed-only).

Frozen contract: data/alpha_search/promotions/phase2_exploitation_quiet_tape_20260830.json
(promotion_hash e2049b64209069a47047d7b21e8e071857854eb4a986a4f23f3ed639ee993268 superseded by
the reworded reserve-time promotion; the bars below are byte-equal to the bound proposal).

Cohort: the 802 quiet-tape conditioned qualified non-flat mapped estimate-revision
decisions frozen outcome-blind in
data/alpha_search/phase2_estimate_revision_quiet_tape_density_20260830.json.
Conditioning rule (frozen): anchor A = last warehouse session <= as_of_date;
R5 = ln(close_A/close_{A-5}); sigma5 = stdev(60 daily log returns strictly before
the 5-session window) * sqrt(5), >=40 returns required fail-closed;
quiet <=> dir_sign * R5 <= 1.0 * sigma5.

Falsification bars (ALL must pass for an observed_only accept):
  F1 spread mean(h_ret|up) - mean(h_ret|down) > 0 at >=2/3 horizons incl H10
  F2 sum(h_replacement_value_vs_cash_usd|up) > 0 at >=2/3 horizons incl H10
  F3 sum(h_rv_vs_spy|up) > 0 AND sum(h_rv_vs_qqq|up) > 0 at H10
  F4 date placebo (H10, 200 draws, simple next-open->10th-close methodology):
     real simple-methodology spread > p90(placebo spreads)
  F5 ticker shuffle within session (H10, 200 draws, same methodology):
     real > p90(shuffled spreads)
  F6 F1 spread > 0 at BOTH H5 and H10 on the PIT-verified subset
     (data/alpha_search/phase2_estimate_revision_ohlcv_context_pit_reconstruction_20260830.json)
Secondary (reported, non-gating): magnitude terciles, non-quiet contrast,
H20 PIT-verified subset spread.

Reads the append-only settled outcome ledgers and OHLCV warehouse only; changes
no production behavior; trade_enabled stays false; max conclusion observed_only.
"""
import json, glob, math, sqlite3, hashlib, random, collections
from datetime import datetime, timezone
from statistics import stdev, mean
from pathlib import Path

K_SIGMA = 1.0
PATH_SESSIONS = 5
ENVELOPE_SESSIONS = 60
MIN_ENVELOPE_RETURNS = 40
N_DRAWS = 200
SEED = 20260831
HORIZONS = ('h5', 'h10', 'h20')

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / 'data' / 'experiments' / 'exp-20260831-001'
OUT_DIR.mkdir(parents=True, exist_ok=True)
WAREHOUSE = REPO / 'data' / 'warehouse' / 'warehouse_main_hot.sqlite'


def load_decisions():
    files = sorted(glob.glob(str(REPO / 'data/non_ohlcv/estimate_revision_outcomes_*.jsonl')))
    fileset = hashlib.sha256()
    rows = {}
    for f in files:
        raw = open(f, 'rb').read()
        fileset.update(hashlib.sha256(raw).digest())
        for line in raw.decode('utf-8').splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if not r.get('decision_qualified'):
                continue
            if r.get('revision_direction') not in ('up', 'down'):
                continue
            if not r.get('instrument_mapping_qualified'):
                continue
            did = r.get('decision_id')
            if not did or did in rows:
                continue
            rows[did] = r
    return rows, len(files), fileset.hexdigest()


def main():
    decisions, n_files, fileset_sha = load_decisions()
    con = sqlite3.connect(WAREHOUSE)
    cur = con.cursor()

    bars_cache = {}

    def bars(ticker):
        if ticker not in bars_cache:
            bars_cache[ticker] = cur.execute(
                "SELECT date, open, close, updated_at FROM ohlcv WHERE ticker=? ORDER BY date",
                (ticker,)).fetchall()
        return bars_cache[ticker]

    def closes_upto(ticker, as_of, n):
        rows = [r for r in bars(ticker) if r[0] <= as_of]
        return rows[-n:]

    cohort = []          # conditioned quiet-tape decisions
    nonquiet = []        # already-moved comparator leg
    need = PATH_SESSIONS + ENVELOPE_SESSIONS + 1
    for did, r in decisions.items():
        t = r.get('instrument_ticker') or r.get('ticker')
        as_of = r.get('as_of_date')
        if not t or not as_of:
            continue
        rows = closes_upto(t, as_of, need)
        if len(rows) < PATH_SESSIONS + MIN_ENVELOPE_RETURNS + 2:
            continue
        closes = [c for _, _, c, _ in rows]
        r5 = math.log(closes[-1] / closes[-1 - PATH_SESSIONS])
        env = closes[:-PATH_SESSIONS]
        rets = [math.log(env[i] / env[i - 1]) for i in range(1, len(env))][-ENVELOPE_SESSIONS:]
        if len(rets) < MIN_ENVELOPE_RETURNS:
            continue
        sigma5 = stdev(rets) * math.sqrt(PATH_SESSIONS)
        if sigma5 <= 0:
            continue
        dir_sign = 1.0 if r['revision_direction'] == 'up' else -1.0
        rec = {
            'decision_id': did, 'ticker': t, 'as_of': as_of,
            'direction': r['revision_direction'],
            'abs_delta': abs(r.get('eps_estimate_delta_prev') or 0.0),
            'entry_date': r.get('actual_entry_date') or r.get('usable_entry_date') or r.get('entry_date'),
        }
        for h in HORIZONS:
            rec[h + '_status'] = r.get(h + '_status')
            if r.get(h + '_status') == 'closed':
                rec[h + '_ret'] = r.get(h + '_return_pct')
                rec[h + '_rv_cash'] = r.get(h + '_replacement_value_vs_cash_usd')
                rec[h + '_rv_spy'] = r.get(h + '_replacement_value_vs_spy_usd')
                rec[h + '_rv_qqq'] = r.get(h + '_replacement_value_vs_qqq_usd')
        # PIT-verified flag (same rule as the reconstruction artifact)
        max_updated = max(u for _, _, _, u in rows)
        rec['pit_verified'] = bool(rec['entry_date']) and max_updated <= f"{rec['entry_date']}T13:30:00+00:00"
        if (dir_sign * r5) <= (K_SIGMA * sigma5):
            cohort.append(rec)
        else:
            nonquiet.append(rec)

    def spread(recs, h, key='_ret'):
        up = [x[h + key] for x in recs if x['direction'] == 'up' and x.get(h + key) is not None]
        dn = [x[h + key] for x in recs if x['direction'] == 'down' and x.get(h + key) is not None]
        if not up or not dn:
            return None, len(up), len(dn)
        return mean(up) - mean(dn), len(up), len(dn)

    # ---- F1
    f1 = {}
    for h in HORIZONS:
        s, nu, nd = spread(cohort, h)
        f1[h] = {'spread_pct': s, 'n_up': nu, 'n_down': nd, 'pass': (s is not None and s > 0)}
    f1_pass = sum(1 for h in HORIZONS if f1[h]['pass']) >= 2 and f1['h10']['pass']

    # ---- F2 / F3
    f2 = {}
    for h in HORIZONS:
        vals = [x[h + '_rv_cash'] for x in cohort if x['direction'] == 'up' and x.get(h + '_rv_cash') is not None]
        f2[h] = {'sum_rv_vs_cash_usd': sum(vals) if vals else None, 'n': len(vals),
                 'pass': bool(vals) and sum(vals) > 0}
    f2_pass = sum(1 for h in HORIZONS if f2[h]['pass']) >= 2 and f2['h10']['pass']
    spy10 = [x['h10_rv_spy'] for x in cohort if x['direction'] == 'up' and x.get('h10_rv_spy') is not None]
    qqq10 = [x['h10_rv_qqq'] for x in cohort if x['direction'] == 'up' and x.get('h10_rv_qqq') is not None]
    f3 = {'sum_rv_vs_spy_h10_usd': sum(spy10), 'sum_rv_vs_qqq_h10_usd': sum(qqq10),
          'n_spy': len(spy10), 'n_qqq': len(qqq10)}
    f3_pass = bool(spy10) and bool(qqq10) and sum(spy10) > 0 and sum(qqq10) > 0

    # ---- simple methodology for F4/F5: entry next session open strictly after as_of,
    #      exit close of the 10th session counting the entry session as the first.
    def simple_ret(ticker, as_of):
        rows = bars(ticker)
        idx = None
        for i, (d, _, _, _) in enumerate(rows):
            if d > as_of:
                idx = i
                break
        if idx is None or idx + 9 >= len(rows):
            return None
        entry_open = rows[idx][1]
        exit_close = rows[idx + 9][2]
        if not entry_open or entry_open <= 0:
            return None
        return (exit_close / entry_open) - 1.0

    def simple_spread(assignments):
        up, dn = [], []
        for ticker, as_of, direction in assignments:
            v = simple_ret(ticker, as_of)
            if v is None:
                continue
            (up if direction == 'up' else dn).append(v)
        if not up or not dn:
            return None
        return mean(up) - mean(dn)

    real_assign = [(x['ticker'], x['as_of'], x['direction']) for x in cohort]
    real_simple = simple_spread(real_assign)
    sessions = sorted({x['as_of'] for x in cohort})
    rng = random.Random(SEED)

    placebo = []
    for _ in range(N_DRAWS):
        assign = []
        for x in cohort:
            others = [s for s in sessions if s != x['as_of']]
            assign.append((x['ticker'], rng.choice(others), x['direction']))
        v = simple_spread(assign)
        if v is not None:
            placebo.append(v)
    placebo.sort()
    p90_placebo = placebo[int(0.9 * len(placebo))] if placebo else None
    f4_pass = real_simple is not None and p90_placebo is not None and real_simple > p90_placebo

    by_session = collections.defaultdict(list)
    for x in cohort:
        by_session[x['as_of']].append(x)
    shuffled = []
    for _ in range(N_DRAWS):
        assign = []
        for s, members in by_session.items():
            tickers = [m['ticker'] for m in members]
            rng.shuffle(tickers)
            for m, t in zip(members, tickers):
                assign.append((t, s, m['direction']))
        v = simple_spread(assign)
        if v is not None:
            shuffled.append(v)
    shuffled.sort()
    p90_shuffle = shuffled[int(0.9 * len(shuffled))] if shuffled else None
    f5_pass = real_simple is not None and p90_shuffle is not None and real_simple > p90_shuffle

    # ---- F6 PIT-verified subset
    pit_cohort = [x for x in cohort if x['pit_verified']]
    f6 = {}
    for h in ('h5', 'h10'):
        s, nu, nd = spread(pit_cohort, h)
        f6[h] = {'spread_pct': s, 'n_up': nu, 'n_down': nd, 'pass': (s is not None and s > 0)}
    f6_pass = f6['h5']['pass'] and f6['h10']['pass']

    # ---- secondary (non-gating)
    s20, n20u, n20d = spread(pit_cohort, 'h20')
    terciles = {}
    for h in HORIZONS:
        rows = [x for x in cohort if x.get(h + '_ret') is not None]
        rows.sort(key=lambda x: x['abs_delta'])
        n = len(rows)
        if n >= 30:
            cut = n // 3
            groups = [rows[:cut], rows[cut:2 * cut], rows[2 * cut:]]
            dirmeans = []
            for g in groups:
                vals = [(x[h + '_ret'] if x['direction'] == 'up' else -x[h + '_ret']) for x in g]
                dirmeans.append(mean(vals))
            terciles[h] = {'directional_mean_by_abs_delta_tercile': dirmeans,
                           'monotone_increasing': dirmeans[0] <= dirmeans[1] <= dirmeans[2]}
    nonquiet_contrast = {}
    for h in HORIZONS:
        s, nu, nd = spread(nonquiet, h)
        nonquiet_contrast[h] = {'spread_pct': s, 'n_up': nu, 'n_down': nd}

    all_pass = all([f1_pass, f2_pass, f3_pass, f4_pass, f5_pass, f6_pass])
    result = {
        'schema_version': 1,
        'experiment_id': 'exp-20260831-001',
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'candidate_id': 'cand-1a665d7350fd8d6349e8',
        'cohort': {
            'conditioned_quiet_tape': len(cohort),
            'nonquiet_comparator': len(nonquiet),
            'pit_verified_conditioned': len(pit_cohort),
            'decision_sessions': len(sessions),
        },
        'bars': {
            'F1_sign_spread': {**f1, 'rule': '>0 at >=2/3 horizons incl h10', 'pass': f1_pass},
            'F2_long_leg_net_vs_cash': {**f2, 'rule': '>0 at >=2/3 horizons incl h10', 'pass': f2_pass},
            'F3_comparators_h10': {**f3, 'pass': f3_pass},
            'F4_date_placebo_h10': {'real_simple_spread': real_simple, 'p90_placebo': p90_placebo,
                                    'n_draws_valid': len(placebo), 'pass': f4_pass},
            'F5_ticker_shuffle_h10': {'real_simple_spread': real_simple, 'p90_shuffle': p90_shuffle,
                                      'n_draws_valid': len(shuffled), 'pass': f5_pass},
            'F6_pit_verified_subset': {**f6, 'pass': f6_pass},
        },
        'secondary_non_gating': {
            'h20_pit_verified_spread_pct': s20, 'h20_pit_n_up': n20u, 'h20_pit_n_down': n20d,
            'magnitude_terciles': terciles,
            'nonquiet_contrast': nonquiet_contrast,
        },
        'verdict': 'observed_only_positive_lead' if all_pass else 'rejected',
        'all_bars_pass': all_pass,
        'inputs': {
            'outcome_files_count': n_files,
            'outcome_fileset_sha256': fileset_sha,
            'warehouse': 'data/warehouse/warehouse_main_hot.sqlite',
            'seed': SEED,
            'n_draws': N_DRAWS,
            'density_artifact': 'data/alpha_search/phase2_estimate_revision_quiet_tape_density_20260830.json',
            'pit_artifact': 'data/alpha_search/phase2_estimate_revision_ohlcv_context_pit_reconstruction_20260830.json',
            'promotion': 'data/alpha_search/promotions/phase2_exploitation_quiet_tape_20260830.json',
        },
        'trade_enabled': False,
    }
    out = OUT_DIR / 'quiet_tape_falsification_result.json'
    out.write_text(json.dumps(result, indent=1, sort_keys=True), encoding='utf-8')
    print(json.dumps({'verdict': result['verdict'],
                      'F1': f1_pass, 'F2': f2_pass, 'F3': f3_pass,
                      'F4': f4_pass, 'F5': f5_pass, 'F6': f6_pass,
                      'cohort': result['cohort']}, indent=1))
    print('written', out)


if __name__ == '__main__':
    main()
