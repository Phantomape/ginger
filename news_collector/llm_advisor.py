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
    # Replace date
    today = datetime.now().strftime("%b. %d, %Y, %I:%M %p EST")
    user_message = '\n'.join(user_lines)
    user_message = user_message.replace("Today is Jan. 15th, 2026, 4:30 PM EST", f"Today is {today}")

    # Replace positions JSON (remove 'as_of' field since date is in "Today is..." format)
    if open_positions:
        positions_copy = open_positions.copy()
        positions_copy.pop('as_of', None)  # Remove as_of field if present
        positions_json = json.dumps(positions_copy, indent=4)
    else:
        positions_json = "{}"

    # Find and replace the positions section using a lambda to avoid escape issues
    import re
    positions_pattern = r'1\) CURRENT OPEN POSITIONS.*?\n\{[\s\S]*?\n\}'
    user_message = re.sub(
        positions_pattern,
        lambda _: f'1) CURRENT OPEN POSITIONS (manually entered, may be approximate):\n{positions_json}',
        user_message,
        count=1
    )

    # Replace news JSON using a lambda to avoid escape issues
    news_json = json.dumps(trade_news, indent=2)
    news_pattern = r'2\) RECENT, PRE-FILTERED STOCK NEWS.*?\n\[[\s\S]*?\n\]'
    user_message = re.sub(
        news_pattern,
        lambda _: f'2) RECENT, PRE-FILTERED STOCK NEWS (last 72h, watchlist only):\n{news_json}',
        user_message,
        count=1
    )

    # Add trend signals if available (insert before TASK A)
    if trend_signals and trend_signals.get('signals'):
        trend_json = json.dumps(trend_signals.get('signals', {}), indent=2)
        trend_section = f"\n\n3) TREND SIGNALS (20-day breakout, technical analysis):\n{trend_json}\n"

        task_a_pos = user_message.find("TASK A")
        if task_a_pos != -1:
            user_message = user_message[:task_a_pos] + trend_section + "\n" + user_message[task_a_pos:]
        else:
            user_message += trend_section

    # Add position management section (insert before TASK A, after trend signals)
    portfolio_value = open_positions.get('portfolio_value_usd') if open_positions else None
    pos_mgmt_data = {
        "portfolio_value_usd": portfolio_value,
        "risk_per_trade_pct": 0.01,
        "sizing_note": (
            "shares = floor(portfolio_value_usd * 0.01 / (entry_price - stop_price))"
            if portfolio_value
            else "Set portfolio_value_usd in open_positions.json to enable position sizing"
        ),
        "exit_rules": {
            "hard_stop_pct":      -0.12,
            "atr_stop_multiplier": 2.0,
            "trailing_stop_pct":  -0.08,
            "profit_target_pct":   0.20,
            "time_stop_days":      20,
        },
        "positions_requiring_attention": [],
    }

    # Collect positions with triggered exit signals from trend signals
    if trend_signals and trend_signals.get('signals'):
        for ticker, sig in trend_signals['signals'].items():
            pos_ctx = sig.get('position', {})
            exit_sigs = pos_ctx.get('exit_signals', {})
            if exit_sigs.get('any_triggered'):
                pos_mgmt_data['positions_requiring_attention'].append({
                    "ticker":          ticker,
                    "current_price":   sig['close'],
                    "urgency":         "CRITICAL" if exit_sigs['critical_exit'] else "HIGH",
                    "triggered_rules": exit_sigs['triggered_rules'],
                })

    pos_mgmt_json = json.dumps(pos_mgmt_data, indent=2)
    pos_mgmt_section = (
        f"\n\n4) POSITION MANAGEMENT (pre-computed rules — use these directly):\n"
        f"{pos_mgmt_json}\n"
    )

    task_a_pos = user_message.find("TASK A")
    if task_a_pos != -1:
        user_message = user_message[:task_a_pos] + pos_mgmt_section + "\n" + user_message[task_a_pos:]
    else:
        user_message += pos_mgmt_section

    return system_message, user_message


def get_investment_advice(trade_news, open_positions=None, trend_signals=None, model="gpt-4o", max_tokens=2000, save_prompt_only=True):
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
            temperature=0.3  # Lower temperature for more focused, consistent advice
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
