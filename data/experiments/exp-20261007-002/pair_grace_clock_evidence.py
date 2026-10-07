"""Read-only, identity-only evidence capture + replay for the pair-sleeve grace-clock repair.

Prints statuses/blockers only; never prints or persists a PnL/return value.
Usage: python pair_grace_clock_evidence.py <label>   (label = before | after)
"""
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('D:/Github/ginger')
sys.path.insert(0, str(REPO / 'quant'))
import news_propagation_pair_paper_sleeve as sleeve  # noqa: E402

LABEL = sys.argv[1] if len(sys.argv) > 1 else 'before'
BASKET = 'news-first-seen-39644ff3bf36cb2bdb66'
LEDGER = REPO / 'data/paper_sleeves/news_propagation_pair/ledger.jsonl'
STATE = REPO / 'data/paper_sleeves/news_propagation_pair/state.json'
HOT = REPO / 'data/warehouse/warehouse_main_hot.sqlite'
MASSIVE = REPO / 'data/warehouse/massive_history.sqlite'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def status_only(result):
    outcome, blocker = result
    if outcome is None:
        return {'outcome': None, 'blocker': blocker}
    return {'outcome_status': outcome.get('outcome_status'),
            'unpriceable_legs': outcome.get('unpriceable_legs'),
            'has_pnl_fields': any(k.endswith('_usd') or k.endswith('_return') for k in outcome)}


rows = [json.loads(l) for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]
decision = next(r for r in rows if r['basket_id'] == BASKET and r['record_type'] == 'basket_decision')
outcome_rows = [r for r in rows if r['basket_id'] == BASKET and r['record_type'] == 'basket_outcome']
ledger_outcome = [{k: r.get(k) for k in ('outcome_status', 'entry_session', 'exit_session', 'unpriceable_legs', 'reason')}
                  for r in outcome_rows]

legs = sorted(set(decision['long_leg']['weights']) | set(decision['short_leg']['weights']))
hot = sqlite3.connect(f'file:{HOT.as_posix()}?mode=ro', uri=True)
mas = sqlite3.connect(f'file:{MASSIVE.as_posix()}?mode=ro', uri=True)
bar_presence = {}
for t in legs:
    bar_presence[t] = {
        'hot_rows': hot.execute('select count(*) from ohlcv where ticker=?', (t,)).fetchone()[0],
        'hot_has_0914_0925': hot.execute("select count(*) from ohlcv where ticker=? and date in ('2026-09-14','2026-09-25')", (t,)).fetchone()[0],
        'massive_has_0914_0925': mas.execute("select count(*) from daily_bars where ticker=? and trade_date in ('2026-09-14','2026-09-25')", (t,)).fetchone()[0],
    }
checkpoints = {k: v for k, v in mas.execute(
    "select checkpoint_key, updated_at_utc from fetch_checkpoint where checkpoint_key in "
    "('grouped:2026-09-24','grouped:2026-09-25','grouped:2026-09-28','grouped:2026-10-05')")}

tickers = set(legs) | set(sleeve.COMPARATOR_TICKERS) | {sleeve.SESSION_ANCHOR_TICKER}
bars_now = sleeve.load_pair_bars(tickers)
# settlement-time counterfactual: massive-sourced tickers (absent from the hot tier) pruned to <= 2026-09-24
bars_then = {k: (dict(v) if isinstance(v, dict) else v) for k, v in bars_now.items()}
for t in legs:
    if bar_presence[t]['hot_rows'] == 0 and t in bars_then:
        bars_then[t] = {d: b for d, b in bars_then[t].items() if d <= '2026-09-24'}
if '__source_last_sessions__' in bars_then:
    src = dict(bars_then['__source_last_sessions__'])
    src['massive'] = '2026-09-24'
    bars_then['__source_last_sessions__'] = src

out = {
    'label': LABEL,
    'captured_at_utc': datetime.now(timezone.utc).isoformat(),
    'sleeve_module_sha256': sha(REPO / 'quant/news_propagation_pair_paper_sleeve.py'),
    'ledger_sha256': sha(LEDGER),
    'state_sha256': sha(STATE),
    'state_updated_at': json.loads(STATE.read_text(encoding='utf-8'))['updated_at'],
    'basket': BASKET,
    'decision_identity': {k: decision.get(k) for k in ('decision_date', 'first_seen_at', 'hold_sessions', 'rule_version')},
    'admission_priceability_sessions': (decision.get('admission_priceability') or {}).get('sessions'),
    'ledger_outcome_rows': ledger_outcome,
    'leg_bar_presence': bar_presence,
    'massive_fetch_checkpoints_utc': checkpoints,
    'bars_source_last_sessions_now': bars_now.get('__source_last_sessions__'),
    'anchor_calendar_last': max(bars_now[sleeve.SESSION_ANCHOR_TICKER]),
    'replay_settlement_time_state_massive_le_0924': status_only(sleeve.settle_pair_basket(decision, bars_then)),
    'replay_now_full_bars': status_only(sleeve.settle_pair_basket(decision, bars_now)),
    'pnl_fields_read': False,
}
print(json.dumps(out, indent=2, ensure_ascii=False))
