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
    news_pattern = r'2\) 近期精选股票新闻.*?\n\[[\s\S]*?\n\]'
    user_message = re.sub(
        news_pattern,
        lambda _: f'2) 近期精选股票新闻（过去 72 小时，仅自选股）：\n{news_json}',
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
        # Include cash so heat/sector/sizing reflect the full account (not just equity).
        cash_usd = open_positions.get("cash_usd", 0) or 0
        live_pv = equity_pv + cash_usd
        if live_pv > 0:
            portfolio_value = live_pv
            if stored_pv and abs(live_pv - stored_pv) / stored_pv > 0.15:
                logger.warning(
                    f"Portfolio value drift: stored={stored_pv:,.0f}  "
                    f"live={live_pv:,.0f} USD (equity={equity_pv:,.0f} + cash={cash_usd:,.0f}) — "
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

    pos_mgmt_data = {
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
        "data_warnings": _data_warnings if _data_warnings else [],
        "positions_requiring_attention": [],
    }

    # Collect positions with triggered exit signals from trend signals.
    # LOW urgency (PROFIT_LADDER_30) is omitted — it would flood this list with every
    # winner and dilute attention away from genuine CRITICAL/HIGH/MEDIUM signals.
    _urgency_rank = {"CRITICAL": 4, "HIGH": 3, "WARNING": 2, "MEDIUM": 1, "LOW": 0}
    _min_surface_rank = 1   # MEDIUM and above only
    if trend_signals and trend_signals.get('signals'):
        for ticker, sig in trend_signals['signals'].items():
            pos_ctx   = sig.get('position', {})
            exit_sigs = pos_ctx.get('exit_signals', {})
            rules     = exit_sigs.get('triggered_rules', [])
            if not (exit_sigs.get('any_triggered') and rules):
                continue
            max_urgency = max(rules, key=lambda r: _urgency_rank.get(r['urgency'], 0))['urgency']
            # Only surface MEDIUM and above — skip positions that only have LOW triggers
            if _urgency_rank.get(max_urgency, 0) < _min_surface_rank:
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

    # Section 5: recent closed trades — required by the loss-streak cool-down rule.
    # trade_advice.txt: "若第 5 节 recent_trades 中最近 3 笔交易全部亏损 → 暂停新交易 3 个交易日"
    # Without this data the prompt rule says "ignore" and the cool-down NEVER fires.
    # Providing the last 10 closed trades enables the LLM to apply the rule correctly.
    recent_trades_section = ""
    try:
        from performance_engine import load_trades
        all_trades    = load_trades()
        closed_trades = [t for t in all_trades
                         if t.get("status") == "closed" and t.get("profit_loss") is not None]
        # Sort most-recent first, take last 10 for context
        closed_sorted = sorted(closed_trades, key=lambda t: t.get("exit_date") or "", reverse=True)
        last_trades   = closed_sorted[:10]
        if last_trades:
            trade_summary = [
                {
                    "ticker":      t["ticker"],
                    "strategy":    t["strategy"],
                    "exit_date":   t.get("exit_date"),
                    "profit_loss": t["profit_loss"],
                    "result":      "WIN" if t["profit_loss"] > 0 else "LOSS",
                }
                for t in last_trades
            ]
            recent_trades_section = (
                f"\n\n5) RECENT TRADES (最近 {len(trade_summary)} 笔已关闭交易 — 供冷却机制判断):\n"
                f"{json.dumps(trade_summary, indent=2)}\n"
            )
            logger.info(
                f"Section 5: injected {len(trade_summary)} recent trades "
                f"(last 3: {[t['result'] for t in trade_summary[:3]]})"
            )
        else:
            recent_trades_section = (
                "\n\n5) RECENT TRADES: 尚无已关闭交易记录。冷却机制不适用。\n"
            )
    except Exception as e:
        logger.warning(f"Failed to load recent trades for section 5: {e}")
        recent_trades_section = "\n\n5) RECENT TRADES: 数据不可用。冷却机制不适用。\n"

    task_a_pos = user_message.find("任务 A")
    if task_a_pos != -1:
        user_message = user_message[:task_a_pos] + recent_trades_section + "\n" + user_message[task_a_pos:]
    else:
        user_message += recent_trades_section

    return system_message, user_message


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

    # If save_prompt_only, save to file and return
    if save_prompt_only:
        try:
            today = datetime.now().strftime("%Y%m%d")
            prompt_file = f"data/llm_prompt_{today}.txt"

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

        output = {
            "timestamp": datetime.now().isoformat(),
            "advice_raw": advice,
            "advice_parsed": parsed_advice,
            "token_usage": token_usage
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved investment advice to {filepath}")
        return True

    except Exception as e:
        logger.error(f"Failed to save advice: {e}")
        return False
