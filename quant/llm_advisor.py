"""
LLM-based investment advisor using OpenAI API.

Analyzes filtered trade news and current positions to provide investment recommendations.
"""

import os
import json
import logging
from datetime import datetime
from openai import OpenAI

logger = logging.getLogger(__name__)


def _load_json_if_exists(path):
    """Best-effort JSON loader for optional replay sidecar files."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load optional JSON sidecar {path}: {e}")
        return None


def _build_archive_context(date_str, data_dir):
    """Attach prompt-time production context to dated advice / replay archives.

    The top alpha branch (`LLM soft ranking`) is blocked not just by missing
    replies, but by lacking prompt-time candidate context. This helper mirrors
    enough program-side state into the saved advice wrapper so replay readiness
    can later distinguish:
      - ranking-eligible candidate days
      - prompt days that were hard-locked by heat / regime rules
      - days with no prompt candidates at all
    """
    decision_log = _load_json_if_exists(
        os.path.join(data_dir, f"llm_decision_log_{date_str}.json")
    )
    quant_signals = _load_json_if_exists(
        os.path.join(data_dir, f"quant_signals_{date_str}.json")
    )

    signal_details = []
    if isinstance(decision_log, dict):
        signal_details = decision_log.get("signal_details") or []

    signal_tickers = []
    for item in signal_details:
        if not isinstance(item, dict):
            continue
        ticker = item.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            signal_tickers.append(ticker.strip().upper())

    source = None
    new_trade_locked = None
    account_state = None
    lock_reason = None
    if isinstance(decision_log, dict):
        source = "llm_decision_log"
        new_trade_locked = decision_log.get("new_trade_locked")
        account_state = decision_log.get("account_state")
        lock_reason = decision_log.get("lock_reason")
        if not signal_tickers:
            for ticker in decision_log.get("signals_presented", []) or []:
                if isinstance(ticker, str) and ticker.strip():
                    signal_tickers.append(ticker.strip().upper())
    elif isinstance(quant_signals, dict):
        source = "quant_signals"
        for item in quant_signals.get("signals", []) or []:
            if not isinstance(item, dict):
                continue
            ticker = item.get("ticker")
            if isinstance(ticker, str) and ticker.strip():
                signal_tickers.append(ticker.strip().upper())

    if source is None:
        return None

    signal_tickers = list(dict.fromkeys(signal_tickers))
    if new_trade_locked is True:
        ranking_eligible = False
    elif signal_tickers:
        ranking_eligible = True
    else:
        ranking_eligible = False

    context = {
        "source": source,
        "signals_presented": signal_tickers,
        "signals_presented_count": len(signal_tickers),
        "ranking_eligible": ranking_eligible,
    }
    if new_trade_locked is not None:
        context["new_trade_locked"] = bool(new_trade_locked)
    if account_state is not None:
        context["account_state"] = account_state
    if lock_reason:
        context["lock_reason"] = lock_reason
    return context


def load_open_positions(filepath="../data/open_positions.json"):
    """
    Load open positions from JSON file.

    Args:
        filepath (str): Path to open_positions.json

    Returns:
        dict: Open positions data or None if file not found
    """
    try:
        # Try relative path first
        if not os.path.exists(filepath):
            # Try from project root
            filepath = "data/open_positions.json"

        if not os.path.exists(filepath):
            logger.warning(f"Open positions file not found: {filepath}")
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load open positions: {e}")
        return None


def load_prompt_template(template_path="../instructinos/prompts/trade_advice.txt"):
    """
    Load the prompt template file.

    Args:
        template_path (str): Path to trade_advice.txt

    Returns:
        str: Template content or None if file not found
    """
    try:
        # Try relative path first
        if not os.path.exists(template_path):
            # Try from project root
            template_path = "instructinos/prompts/trade_advice.txt"

        if not os.path.exists(template_path):
            logger.warning(f"Prompt template file not found: {template_path}")
            return None

        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt template: {e}")
        return None


def build_prompt(trade_news, open_positions, trend_signals=None):
    """
    Build prompt from template by inserting positions, news, and trend signals.

    Args:
        trade_news (list): List of filtered trade news items
        open_positions (dict): Current portfolio positions
        trend_signals (dict): Optional trend signal data from trend_signals module

    Returns:
        tuple: (system_message, user_message) or (None, None) if failed
    """
    # Load template
    template = load_prompt_template()
    if not template:
        logger.error("Failed to load prompt template, using fallback")
        return None, None

    # Parse template to extract SYSTEM and USER sections
    lines = template.split('\n')
    system_lines = []
    user_lines = []
    current_section = None

    for line in lines:
        if line.strip() == "SYSTEM:":
            current_section = "system"
            continue
        elif line.strip() == "USER:":
            current_section = "user"
            continue

        if current_section == "system":
            system_lines.append(line)
        elif current_section == "user":
            user_lines.append(line)

    system_message = '\n'.join(system_lines).strip()

    # Build user message with dynamic data
    # Replace date — template uses Chinese prefix "今天是"
    import re
    today = datetime.now().strftime("%b. %d, %Y, %I:%M %p EST")
    user_message = '\n'.join(user_lines)
    user_message = re.sub(r'今天是.*', f'今天是 {today}', user_message)

    # Replace positions JSON (remove 'as_of' field since date is in "今天是..." line)
    if open_positions:
        positions_copy = open_positions.copy()
        positions_copy.pop('as_of', None)  # Remove as_of field if present
        positions_json = json.dumps(positions_copy, indent=4)
    else:
        positions_json = "{}"

    # Find and replace the positions section — template uses Chinese header "1) 当前持仓"
    positions_pattern = r'1\) 当前持仓.*?\n\{[\s\S]*?\n\}'
    user_message = re.sub(
        positions_pattern,
        lambda _: f'1) 当前持仓（手动录入，可能为近似值）：\n{positions_json}',
        user_message,
        count=1
    )

    # Replace news JSON — template uses Chinese header "2) 近期精选股票新闻"
    news_json = json.dumps(trade_news, indent=2)
    # Compute news quality summary so LLM doesn't need to scan all items to know if
    # actionable news exists.  T3-only days are extremely common; the summary prevents
    # T3 content from subtly influencing decisions even when rules say "ignore T3".
    _tier_counts = {"T1": 0, "T2": 0, "T3": 0}
    for _item in trade_news:
        _tier_counts[_item.get("tier", "T3")] += 1
    _has_actionable = _tier_counts["T1"] > 0 or _tier_counts["T2"] > 0
    news_quality_summary = json.dumps({
        "T1": _tier_counts["T1"],
        "T2": _tier_counts["T2"],
        "T3": _tier_counts["T3"],
        "has_actionable_news": _has_actionable,
        "note": "T3新闻为噪音，不得影响任何交易决策" if not _has_actionable else "",
    })
    news_pattern = r'2\) 近期精选股票新闻.*?\n\[[\s\S]*?\n\]'
    user_message = re.sub(
        news_pattern,
        lambda _: (
            f'2) 近期精选股票新闻（过去 72 小时，仅自选股）：\n{news_json}\n\n'
            f'news_quality_summary: {news_quality_summary}'
        ),
        user_message,
        count=1
    )

    # Build sections 3a (quant signals) + 3b (technical context for held positions).
    # Only include tickers relevant to the decision — not the full 30-ticker universe.
    sections_3 = ""

    # --- 3a: Pre-computed quant signals (new trade candidates) ---
    quant_signals = trend_signals.get("quant_signals", []) if trend_signals else []
    if quant_signals:
        sections_3 += (
            f"\n\n3a) 量化信号 QUANT SIGNALS（预计算完成，直接使用）：\n"
            f"每条信号已含 strategy / entry_price / stop_price / target_price / "
            f"risk_reward_ratio / trade_quality_score / confidence_score。\n"
            f"{json.dumps(quant_signals, indent=2)}\n"
        )
    else:
        sections_3 += "\n\n3a) 量化信号 QUANT SIGNALS：今日无满足条件的量化信号。\n"

    # --- 3b: Technical context — only tickers with open positions that have triggered exits ---
    raw_signals = trend_signals.get('signals', {}) if trend_signals else {}
    attention_tickers = set()
    for t, s in raw_signals.items():
        pos_ctx = s.get('position', {})
        if pos_ctx.get('exit_signals', {}).get('any_triggered'):
            attention_tickers.add(t)
    # Also include tickers that have quant signals
    signal_tickers = {s["ticker"] for s in quant_signals}
    relevant_tickers = attention_tickers | signal_tickers

    if relevant_tickers:
        filtered = {t: raw_signals[t] for t in relevant_tickers if t in raw_signals}
        if filtered:
            sections_3 += (
                f"\n\n3b) 技术背景 TECHNICAL CONTEXT（仅含有信号或需关注的标的）：\n"
                f"{json.dumps(filtered, indent=2)}\n"
            )

    if sections_3:
        task_a_pos = user_message.find("任务 A")
        if task_a_pos != -1:
            user_message = user_message[:task_a_pos] + sections_3 + "\n" + user_message[task_a_pos:]
        else:
            user_message += sections_3

    # Add position management section (insert before TASK A, after trend signals)
    # Use portfolio_engine: it applies effective stops (ATR/trailing) not just hard stops,
    # giving a more accurate heat reading for positions with large unrealised gains.
    from portfolio_engine import compute_portfolio_heat

    stored_pv = open_positions.get('portfolio_value_usd') if open_positions else None

    # Extract current prices + effective-stop inputs from trend signals first —
    # these are needed for the live portfolio value calculation below.
    current_prices   = {}
    features_for_heat = {}
    if trend_signals and trend_signals.get('signals'):
        for t, s in trend_signals['signals'].items():
            if s.get('close') is not None:
                current_prices[t] = s['close']
            # portfolio_engine needs atr + high_20d to compute effective stop
            features_for_heat[t] = {
                "atr":     s.get("atr"),
                "high_20d": s.get("20d_high"),
            }

    # Auto-compute live portfolio value from current prices × shares.
    # stored portfolio_value_usd can be stale, causing 2× heat inflation.
    portfolio_value = stored_pv
    if open_positions and open_positions.get("positions") and current_prices:
        equity_pv = sum(
            pos.get("shares", 0) * current_prices.get(pos.get("ticker", ""), pos.get("avg_cost", 0))
            for pos in open_positions["positions"]
            if pos.get("ticker") and pos.get("shares", 0) > 0
        )
        # Build live_pv only when cash_usd is populated. Collapsing missing cash
        # to 0 silently under-reports PV and inflates heat/sector ratios; better
        # to keep stored_pv and warn so the operator knows the field is stale.
        cash_raw = open_positions.get("cash_usd")
        if cash_raw is None:
            if stored_pv:
                logger.warning(
                    f"cash_usd missing in open_positions.json — using stored "
                    f"portfolio_value_usd={stored_pv:,.0f} for heat/sector. "
                    f"Fill cash_usd to enable live PV."
                )
        else:
            live_pv = equity_pv + cash_raw
            if live_pv > 0:
                portfolio_value = live_pv
                if stored_pv and abs(live_pv - stored_pv) / stored_pv > 0.15:
                    logger.warning(
                        f"Portfolio value drift: stored={stored_pv:,.0f}  "
                        f"live={live_pv:,.0f} USD (equity={equity_pv:,.0f} + cash={cash_raw:,.0f}) — "
                        f"using live value for heat/sector calculations."
                    )

    # Portfolio heat (using effective stops — ATR/trailing — not just avg_cost stop)
    heat = None
    if portfolio_value and open_positions:
        try:
            heat = compute_portfolio_heat(
                open_positions, current_prices, portfolio_value,
                features_dict=features_for_heat,
            )
        except Exception as e:
            logger.warning(f"Failed to compute portfolio heat: {e}")

    # Market regime from trend signals
    regime = trend_signals.get('market_regime', {}) if trend_signals else {}

    # Sector concentration: compute per-sector market value and weight.
    # The LLM prompt requires ">40% sector weight → block new positions in that sector"
    # but previously had NO sector data — rule was enforced blindly from LLM training.
    # Now we inject pre-computed weights so the rule can actually be enforced.
    sector_weights = {}
    if open_positions and portfolio_value and portfolio_value > 0:
        try:
            from risk_engine import SECTOR_MAP
            sector_mv: dict = {}
            total_mv = 0.0
            for pos in open_positions.get("positions", []):
                t_  = pos.get("ticker", "")
                sh_ = pos.get("shares", 0)
                px_ = current_prices.get(t_) or pos.get("avg_cost", 0)
                mv_ = sh_ * px_
                sec = SECTOR_MAP.get(t_, "Unknown")
                sector_mv[sec] = sector_mv.get(sec, 0.0) + mv_
                total_mv += mv_
            if total_mv > 0:
                # Use portfolio_value (total account incl. cash) as denominator,
                # NOT total_mv (invested portion only).  When significant cash is
                # held, total_mv << portfolio_value and sector weights are overstated
                # by the ratio total_mv/portfolio_value, falsely triggering the
                # >40% sector block and preventing valid new trades.
                # portfolio_value > 0 is guaranteed by the outer if-guard on line 242.
                sector_denom = portfolio_value
                sector_weights = {
                    sec: round(mv / sector_denom, 3)
                    for sec, mv in sorted(sector_mv.items(), key=lambda x: -x[1])
                }
        except Exception as e:
            logger.warning(f"Sector concentration calc failed: {e}")

    # Data quality check: detect positions missing fields required for exit rules.
    # entry_date  → required by TIME_STOP (45-day stagnation rule)
    # target_price → required by SIGNAL_TARGET (3.5×ATR partial-exit rule)
    # Without these, two exit rules silently never fire.
    _data_warnings = []
    if open_positions:
        _missing_entry_date  = [p["ticker"] for p in open_positions.get("positions", [])
                                 if p.get("ticker") and not p.get("entry_date")]
        _missing_target_price = [p["ticker"] for p in open_positions.get("positions", [])
                                  if p.get("ticker") and not p.get("target_price")]
        if _missing_entry_date:
            _data_warnings.append(
                f"TIME_STOP disabled for {_missing_entry_date}: add 'entry_date': 'YYYY-MM-DD' "
                "to each position in open_positions.json (45-day stagnation rule cannot fire)"
            )
        if _missing_target_price:
            _data_warnings.append(
                f"SIGNAL_TARGET disabled for {_missing_target_price}: add 'target_price' "
                "from the original entry signal to each position in open_positions.json "
                "(3.5×ATR partial-exit rule cannot fire, +7% to +20% zone has no exit guidance)"
            )

    # ── Preflight: compute machine states BEFORE data reaches LLM ──────────
    # This converts raw flags (BEAR? heat%? CRITICAL exists?) into a single
    # account_state verdict + per-position decision_state.  The LLM reads the
    # verdict, not the raw flags — reducing the chance of conflicting rule
    # interpretations and "优先HOLD"/"必须EXIT" contradictions.
    from preflight_validator import enrich_positions_with_breach_status, compute_account_state
    from pending_actions import get_open_pending_actions
    if trend_signals:
        enrich_positions_with_breach_status(trend_signals)
    preflight = compute_account_state(
        trend_signals = trend_signals,
        heat_data     = heat,
        regime_data   = regime,
    )
    if isinstance(trend_signals, dict):
        # Persist the machine-state summary alongside the day payload so later
        # decision logs / replay archives can recover prompt-time gating state.
        trend_signals["preflight"] = preflight
    # Merge preflight data_warnings with the existing field-missing warnings
    combined_warnings = (preflight.get("data_warnings") or []) + (_data_warnings or [])
    pending_actions = get_open_pending_actions(open_positions, data_dir="data")

    pos_mgmt_data = {
        # ── Machine state summary (LLM reads this first) ──────────────────
        "account_state":    preflight["account_state"],
        "new_trade_locked": preflight["new_trade_locked"],
        "lock_reason":      preflight["lock_reason"],
        "position_states":      preflight["position_states"],   # {ticker: CRITICAL_EXIT | HIGH_REDUCE | HOLD}
        "pending_unexecuted_actions": pending_actions,
        # Pre-computed reduce % for HIGH_REDUCE positions — LLM reads directly, no table lookup needed.
        "suggested_reduce_pct": preflight["suggested_reduce_pct"],  # {ticker: int}
        # Pre-computed BEAR emergency stops — LLM uses directly if regime=BEAR.
        "bear_emergency_stops": preflight["bear_emergency_stops"],  # {ticker: float} empty if not BEAR
        # Current prices for ALL held tickers — required by BEAR stop-tightening rule
        # ("收紧至 current_price × 0.95") which applies to HOLD positions not in section 3b.
        # Without this, BEAR tightening silently fails for AMD/GOOG/MCD/NFLX etc.
        "current_prices":       {t: p for t, p in current_prices.items()
                                 if open_positions and any(
                                     pos.get("ticker") == t
                                     for pos in open_positions.get("positions", [])
                                 )},
        # ── Market context ─────────────────────────────────────────────────
        "market_regime": {
            "regime":  regime.get("regime", "UNKNOWN"),
            "note":    regime.get("note", ""),
            "indices": regime.get("indices", {}),
        },
        "portfolio_heat": heat if heat else {
            "note": "Set portfolio_value_usd in open_positions.json to enable heat tracking"
        },
        "sector_concentration": sector_weights if sector_weights else {
            "note": "Sector weights unavailable (missing portfolio_value_usd or current prices)"
        },
        "sizing_note": (
            "shares = floor(portfolio_value_usd * 0.01 / (entry_price - stop_price))"
            if portfolio_value
            else "Set portfolio_value_usd in open_positions.json to enable position sizing"
        ),
        "data_warnings": combined_warnings,
        "positions_requiring_attention": [],
    }

    # Collect positions with triggered exit signals from trend signals.
    # MEDIUM+ urgency is always surfaced.  LOW urgency rules are skipped unless the
    # rule requires an action (REDUCE 33%) rather than monitoring (HOLD).
    #
    # SIGNAL_TARGET (LOW urgency) requires REDUCE 33% → always surface even when it
    # is the only triggered rule.  Without this, winners reaching the +7%–+20% dead
    # zone get no explicit LLM attention in section 4 and the REDUCE is missed.
    #
    # PROFIT_LADDER_30 (LOW urgency, action=HOLD) is still excluded — including it
    # would flood section 4 with every +30% winner and dilute critical signals.
    _urgency_rank = {"CRITICAL": 4, "HIGH": 3, "WARNING": 2, "MEDIUM": 1, "LOW": 0}
    _min_surface_rank = 1   # MEDIUM and above always surfaced
    _action_required_low_rules = {"SIGNAL_TARGET"}   # LOW urgency but requires REDUCE
    if trend_signals and trend_signals.get('signals'):
        for ticker, sig in trend_signals['signals'].items():
            pos_ctx   = sig.get('position', {})
            exit_sigs = pos_ctx.get('exit_signals', {})
            rules     = exit_sigs.get('triggered_rules', [])
            if not (exit_sigs.get('any_triggered') and rules):
                continue
            max_urgency = max(rules, key=lambda r: _urgency_rank.get(r['urgency'], 0))['urgency']
            # Include if MEDIUM+ urgency OR if an action-required LOW rule fired
            has_action_required_low = any(
                r["rule"] in _action_required_low_rules for r in rules
            )
            if _urgency_rank.get(max_urgency, 0) < _min_surface_rank and not has_action_required_low:
                continue
            entry = {
                "ticker":                      ticker,
                "current_price":               sig['close'],
                "urgency":                     max_urgency,
                "triggered_rules":             rules,
                # Pre-computed position data — LLM prompt says "直接使用" these fields
                "shares":                      pos_ctx.get('shares'),
                "avg_cost":                    pos_ctx.get('avg_cost'),
                "unrealized_pnl_pct":          pos_ctx.get('unrealized_pnl_pct'),
                "legacy_basis":                pos_ctx.get('legacy_basis'),
                "exit_levels":                 pos_ctx.get('exit_levels'),
                "trailing_stop_from_20d_high": pos_ctx.get('trailing_stop_from_20d_high'),
                "drawdown_from_20d_high_pct":  pos_ctx.get('drawdown_from_20d_high_pct'),
                # Daily price change — required for post-earnings gap rules:
                # "daily_return_pct > +8% → REDUCE 50%" and "< -5% → EXIT"
                # Without this field the LLM cannot distinguish a single-day gap
                # event from cumulative unrealised P&L since entry.
                "daily_return_pct":            pos_ctx.get('daily_return_pct'),
                "prev_close":                  pos_ctx.get('prev_close'),
            }
            # Include days_to_earnings so LLM can apply the "dte ≤ 2 → reduce 50%"
            # earnings pre-exit rule. Sourced from qp_features injected by run_pipeline.py
            # (trend_signals.generate_trend_signals() doesn't fetch earnings data).
            _dte = pos_ctx.get('days_to_earnings') or sig.get('days_to_earnings')
            if _dte is not None:
                entry["days_to_earnings"] = _dte
            pos_mgmt_data['positions_requiring_attention'].append(entry)

    pos_mgmt_json = json.dumps(pos_mgmt_data, indent=2)
    pos_mgmt_section = (
        f"\n\n4) POSITION MANAGEMENT (pre-computed — use these directly):\n"
        f"{pos_mgmt_json}\n"
    )

    task_a_pos = user_message.find("任务 A")
    if task_a_pos != -1:
        user_message = user_message[:task_a_pos] + pos_mgmt_section + "\n" + user_message[task_a_pos:]
    else:
        user_message += pos_mgmt_section

    return system_message, user_message


def _save_decision_log(date_str, trade_news, trend_signals):
    """
    Save a structured log of what the code pre-decided before handing off to LLM.

    This enables future analysis: compare LLM veto/pass decisions against
    actual price outcomes to quantify the LLM's net contribution.
    """
    try:
        quant_signals = trend_signals.get("quant_signals", []) if trend_signals else []
        signals_presented = [s["ticker"] for s in quant_signals]

        # Extract machine-state context from the preflight data embedded in
        # trend_signals (injected by build_prompt -> preflight_validator).
        position_states = {}
        suggested_reduce = {}
        new_trade_locked = None
        account_state = None
        lock_reason = None
        if isinstance(trend_signals, dict):
            preflight = trend_signals.get("preflight") or {}
            if isinstance(preflight, dict):
                position_states = preflight.get("position_states") or {}
                suggested_reduce = preflight.get("suggested_reduce_pct") or {}
                new_trade_locked = preflight.get("new_trade_locked")
                account_state = preflight.get("account_state")
                lock_reason = preflight.get("lock_reason")

        # Count news tiers
        tier_counts = {"T1": 0, "T2": 0, "T3": 0}
        for item in (trade_news or []):
            tier_counts[item.get("tier", "T3")] += 1

        log_entry = {
            "date": date_str,
            "signals_presented": signals_presented,
            "signal_details": [
                {
                    "ticker": s.get("ticker"),
                    "strategy": s.get("strategy"),
                    "entry_price": s.get("entry_price"),
                    "stop_price": s.get("stop_price"),
                    "target_price": s.get("target_price"),
                    "trade_quality_score": s.get("trade_quality_score"),
                    "risk_reward_ratio": s.get("risk_reward_ratio"),
                }
                for s in quant_signals
            ],
            "news_summary": tier_counts,
            "has_actionable_news": tier_counts["T1"] > 0,
            "new_trade_locked": new_trade_locked,
            "account_state": account_state,
            "lock_reason": lock_reason,
            "position_states": position_states,
            "suggested_reduce_pct": suggested_reduce,
        }

        log_file = f"data/llm_decision_log_{date_str}.json"
        os.makedirs("data", exist_ok=True)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)
        logger.info(f"Decision log saved to {log_file}")

    except Exception as e:
        logger.warning(f"Failed to save decision log: {e}")


def _save_prompt_file(date_str, system_message, user_message, trade_news, trend_signals):
    """Persist the rendered prompt for auditability, regardless of API usage."""
    prompt_file = f"data/llm_prompt_{date_str}.txt"

    os.makedirs("data", exist_ok=True)

    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("SYSTEM MESSAGE\n")
        f.write("=" * 80 + "\n\n")
        f.write(system_message)
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("USER MESSAGE\n")
        f.write("=" * 80 + "\n\n")
        f.write(user_message)
        f.write("\n")

    logger.info(f"Prompt saved to {prompt_file}")

    # Save decision log: what signals/positions the code pre-decided,
    # so we can later compare LLM veto/pass against actual outcomes.
    _save_decision_log(date_str, trade_news, trend_signals)
    return prompt_file


def get_investment_advice(trade_news, open_positions=None, trend_signals=None, model="gpt-4o", max_tokens=4000, save_prompt_only=True):
    """
    Get investment advice from OpenAI based on filtered trade news and trend signals.

    Args:
        trade_news (list): List of filtered trade news items
        open_positions (dict): Optional open positions data
        trend_signals (dict): Optional trend signal data
        model (str): OpenAI model to use (default: gpt-4o, latest and most capable)
        max_tokens (int): Maximum tokens in response
        save_prompt_only (bool): If True, save prompt to file instead of calling API

    Returns:
        dict: {
            "success": bool,
            "advice": str or None,
            "error": str or None,
            "token_usage": dict or None
        }
    """
    # Load open positions if not provided
    if open_positions is None:
        open_positions = load_open_positions()

    # Build prompt
    try:
        system_message, user_message = build_prompt(trade_news, open_positions, trend_signals)
        if not system_message or not user_message:
            raise Exception("Failed to build prompt from template")
        logger.info(f"Built prompt with {len(trade_news)} news items")
    except Exception as e:
        logger.error(f"Failed to build prompt: {e}")
        return {
            "success": False,
            "advice": None,
            "error": f"Failed to build prompt: {e}",
            "token_usage": None
        }

    today = datetime.now().strftime("%Y%m%d")
    try:
        prompt_file = _save_prompt_file(
            today,
            system_message,
            user_message,
            trade_news,
            trend_signals,
        )
    except Exception as e:
        logger.error(f"Failed to save prompt: {e}")
        return {
            "success": False,
            "advice": None,
            "error": f"Failed to save prompt: {e}",
            "token_usage": None
        }

    # If save_prompt_only, save to file and return
    if save_prompt_only:
        try:
            return {
                "success": True,
                "advice": f"Prompt saved to {prompt_file}\n\nTo use this prompt:\n1. Copy the content\n2. Paste into ChatGPT or Claude\n3. Review the structured JSON response",
                "error": None,
                "token_usage": None
            }
        except Exception as e:
            logger.error(f"Failed to save prompt: {e}")
            return {
                "success": False,
                "advice": None,
                "error": f"Failed to save prompt: {e}",
                "token_usage": None
            }

    # Call OpenAI API
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return {
            "success": False,
            "advice": None,
            "error": "OPENAI_API_KEY environment variable not set. Please set it before running.",
            "token_usage": None
        }

    try:
        logger.info(f"Calling OpenAI API with model: {model}")
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=max_tokens,
            temperature=0.1  # Near-zero for strict rule-following; 0.3 caused occasional rule violations
        )

        advice = response.choices[0].message.content
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

        logger.info(f"OpenAI API call successful. Tokens used: {token_usage['total_tokens']}")

        return {
            "success": True,
            "advice": advice,
            "error": None,
            "token_usage": token_usage
        }

    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        return {
            "success": False,
            "advice": None,
            "error": str(e),
            "token_usage": None
        }


def parse_json_advice(advice_text):
    """
    Try to parse JSON from the advice text.

    Args:
        advice_text (str): The raw advice text from LLM

    Returns:
        dict: Parsed JSON or None if parsing failed
    """
    try:
        # Try to find JSON block in the response
        import re
        json_match = re.search(r'\{[\s\S]*\}', advice_text)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        return None
    except Exception as e:
        logger.warning(f"Failed to parse JSON from advice: {e}")
        return None


def save_advice(advice, filepath, token_usage=None):
    """
    Save investment advice to a file.

    Args:
        advice (str): The investment advice text
        filepath (str): Path to save the advice
        token_usage (dict): Optional token usage statistics

    Returns:
        bool: True if successful
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Try to parse structured JSON from advice
        parsed_advice = parse_json_advice(advice)
        basename = os.path.basename(filepath)
        data_dir = os.path.dirname(filepath) or "data"
        advice_date = None
        if basename.startswith("investment_advice_") and basename.endswith(".json"):
            advice_date = basename[len("investment_advice_"):-len(".json")]

        pending_overrides = []
        if isinstance(parsed_advice, dict):
            try:
                from pending_actions import (
                    apply_pending_action_overrides,
                    load_pending_actions,
                    register_pending_actions_from_advice,
                    save_pending_actions,
                )

                open_positions = load_open_positions()
                parsed_advice, pending_overrides = apply_pending_action_overrides(
                    parsed_advice,
                    open_positions,
                    data_dir=data_dir,
                    as_of_date=advice_date,
                )
                pending_records = register_pending_actions_from_advice(
                    parsed_advice,
                    open_positions,
                    existing_actions=load_pending_actions(data_dir),
                    as_of_date=advice_date,
                    source_file=basename,
                )
                save_pending_actions(pending_records, data_dir)
            except Exception as e:
                logger.warning("Pending-action reconciliation skipped: %s", e)

        output = {
            "timestamp": datetime.now().isoformat(),
            "advice_raw": advice,
            "advice_parsed": parsed_advice,
            "token_usage": token_usage
        }
        if pending_overrides:
            output["pending_action_overrides"] = [
                {
                    "ticker": item.get("ticker"),
                    "action": item.get("action"),
                    "first_advice_date": item.get("first_advice_date"),
                    "exit_rule_triggered": item.get("exit_rule_triggered"),
                }
                for item in pending_overrides
            ]

        if basename.startswith("investment_advice_") and basename.endswith(".json"):
            date_str = basename[len("investment_advice_"):-len(".json")]
            if len(date_str) == 8 and date_str.isdigit():
                archive_context = _build_archive_context(date_str, os.path.dirname(filepath))
                if archive_context:
                    output["archive_context"] = archive_context

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved investment advice to {filepath}")
        _maybe_write_replay_log(filepath, output)
        return True

    except Exception as e:
        logger.error(f"Failed to save advice: {e}")
        return False


def _maybe_write_replay_log(filepath, output):
    """Mirror real dated advice files to llm replay logs for backtest parity."""
    basename = os.path.basename(filepath)
    if not basename.startswith("investment_advice_") or not basename.endswith(".json"):
        return

    date_str = basename[len("investment_advice_"):-len(".json")]
    if len(date_str) != 8 or not date_str.isdigit():
        return

    parsed_advice = output.get("advice_parsed")
    is_real_response = isinstance(parsed_advice, dict) and "new_trade" in parsed_advice
    if not is_real_response:
        logger.info(
            "Skipping LLM replay log for %s: parsed payload has no 'new_trade' key",
            basename,
        )
        return

    replay_path = os.path.join(os.path.dirname(filepath), f"llm_prompt_resp_{date_str}.json")
    if os.path.exists(replay_path):
        logger.info("LLM replay log already exists, skipping: %s", replay_path)
        return

    with open(replay_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info("Saved LLM replay log to %s", replay_path)
