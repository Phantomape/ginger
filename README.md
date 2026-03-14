# Ginger — Modular Quant Trading System

A modular quantitative trading system that generates probabilistic trade ideas using structural market signals, earnings events, and trend analysis. The goal is not prediction, but to systematically trade small statistical edges with strict risk management.

> **设计原则 / Design Principles:** Simple signals over complex models · Persistent structural edges · Strict risk control · Track real P&L

---

## 目录 / Table of Contents

- [系统架构 / Architecture](#系统架构--architecture)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [模块说明 / Modules](#模块说明--modules)
- [策略说明 / Strategies](#策略说明--strategies)
- [风险规则 / Risk Rules](#风险规则--risk-rules)
- [配置 / Configuration](#配置--configuration)
- [输出文件 / Output Files](#输出文件--output-files)
- [交易日志 / Trade Diary](#交易日志--trade-diary)

---

## 系统架构 / Architecture

```
ginger/
├── quant/                      # 核心模块 / Core modules
│   ├── run.py                  # ★ 统一入口 / Unified entry point
│   │
│   ├── data_layer.py           # [1] 数据层 — OHLCV + 财报数据
│   ├── feature_layer.py        # [2] 特征层 — 趋势/ATR/财报特征
│   ├── signal_engine.py        # [3] 信号引擎 — 3种策略
│   ├── risk_engine.py          # [4] 风险引擎 — 止损/止盈计算
│   ├── portfolio_engine.py     # [5] 组合引擎 — 仓位大小/热度
│   ├── performance_engine.py   # [6] 绩效引擎 — 交易日志/P&L
│   ├── report_generator.py     # 日报生成器
│   │
│   ├── regime.py               # 市场方向 — SPY/QQQ vs 200日均线
│   ├── position_manager.py     # 出场规则 — ATR止损/移动止损
│   ├── trend_signals.py        # 持仓上下文 — 出场信号检测
│   ├── llm_advisor.py          # LLM分析 — 构建AI提示词
│   │
│   ├── filter.py               # 新闻过滤 + 自选股列表 (WATCHLIST)
│   ├── fetch_news.py           # RSS 新闻抓取
│   ├── sources.py              # 新闻源列表
│   ├── parser.py               # 新闻解析
│   ├── clean_news.py           # 新闻清洗
│   ├── forward_tester.py       # 前向测试验证
│   │
│   ├── run_pipeline.py         # (旧) 仅新闻+LLM流程
│   └── run_quant.py            # (旧) 仅量化信号流程
│
├── data/                       # 所有输出文件
│   ├── open_positions.json     # ★ 持仓配置 (需手动维护)
│   ├── trades.json             # 交易日志 (自动生成)
│   ├── quant_signals_YYYYMMDD.json
│   ├── trend_signals_YYYYMMDD.json
│   ├── report_YYYYMMDD.txt
│   ├── llm_prompt_YYYYMMDD.txt
│   └── ...
│
├── instructinos/
│   └── prompts/
│       └── trade_advice.txt    # LLM 系统提示词
│
└── news_collector/             # (已迁移到 quant/) 保留文档
    ├── README.md
    └── requirements.txt        # ★ 依赖列表
```

---

## 快速开始 / Quick Start

### 安装依赖 / Install dependencies

```bash
pip install -r news_collector/requirements.txt
```

依赖 / Dependencies:
```
feedparser>=6.0
requests>=2.31
python-dateutil>=2.8
openai>=1.0
yfinance>=0.2.28
pandas>=2.0
```

### 配置持仓 / Configure positions

编辑 `data/open_positions.json`，填入你的持仓和组合总市值：

Edit `data/open_positions.json` with your holdings and total portfolio value:

```json
{
  "portfolio_value_usd": 70000,
  "positions": [
    {
      "ticker": "NVDA",
      "direction": "long",
      "shares": 41,
      "avg_cost": 102.17,
      "risk_notes": "Core AI holding"
    }
  ]
}
```

可选字段 / Optional field per position:
- `"override_stop_price": 850.0` — 手动覆盖止损价 / Manual stop price override

### 运行 / Run

```bash
cd d:/Github/ginger
python quant/run.py
```

---

## 模块说明 / Modules

| 模块 / Module | 职责 / Responsibility |
|---|---|
| `data_layer.py` | 下载 OHLCV (350天) + yfinance 财报数据 |
| `feature_layer.py` | 计算趋势特征 (200MA、20日突破、ATR) 和财报特征 |
| `signal_engine.py` | 运行3个策略，输出 `{ticker, strategy, entry, stop, confidence}` |
| `risk_engine.py` | 添加目标价: `target = entry + 3×ATR`，R:R = 2:1 |
| `portfolio_engine.py` | 仓位计算: `shares = floor(portfolio × 1% / (entry - stop))` |
| `performance_engine.py` | 记录已开/已平仓交易，计算 win_rate、EV、最大回撤 |
| `regime.py` | SPY+QQQ vs 200日MA → BULL / NEUTRAL / BEAR |
| `position_manager.py` | 持仓出场规则: 硬止损、ATR止损、移动止损、止盈、时间止损 |
| `trend_signals.py` | 为持仓计算出场信号，注入 LLM 提示词 |
| `llm_advisor.py` | 整合所有数据生成 AI 提示词，保存到 `llm_prompt_YYYYMMDD.txt` |
| `report_generator.py` | 生成每日文字报告 |

---

## 策略说明 / Strategies

### Strategy A — Trend Following (趋势跟踪)

| 条件 / Condition | 描述 |
|---|---|
| `price > 200MA` | 股价在200日均线上方 |
| `20-day breakout` | 今日收盘 > 过去20日最高价 |
| `volume spike` | 今日成交量 > 20日均量 × 1.5 |

信号 / Signal: `trend_long`

---

### Strategy B — Volatility Breakout (波动突破)

| 条件 / Condition | 描述 |
|---|---|
| `daily_range > 1.5 ATR` | 当日波幅超过 ATR 的1.5倍 |
| `20-day breakout` | 突破20日新高 |
| `volume expansion > 1.2×` | 成交量扩张 |

信号 / Signal: `breakout_long`

---

### Strategy C — Earnings Event Setup (财报事件)

| 条件 / Condition | 描述 |
|---|---|
| `earnings within 5–15 days` | 财报在5到15天内 |
| `momentum_10d > +2%` | 近10日涨幅 > 2% |
| `positive surprise history` | 历史财报平均超预期 |

信号 / Signal: `earnings_event_long`

---

### 置信度计算 / Confidence Score

每个信号的 `confidence_score` (0–1) 为各条件加权平均。核心条件权重 1.0，辅助条件权重 0.5。

Each signal's `confidence_score` (0–1) is a weighted average of conditions. Core conditions weight 1.0, supporting conditions weight 0.5.

---

## 风险规则 / Risk Rules

### 开仓风险 / Entry Risk

```
stop_price  = entry − 1.5 × ATR(14)
target      = entry + 3.0 × ATR(14)
R:R ratio   = 2:1

risk_amount = portfolio_value × 1%
shares      = floor(risk_amount / (entry − stop))

portfolio_heat_cap = 8%   (总组合最大风险敞口)
```

### 出场优先级 / Exit Rule Hierarchy

| 优先级 | 规则 | 触发条件 | 紧急程度 |
|---|---|---|---|
| 1 | **HARD STOP** | 价格 ≤ avg_cost × 0.88 | 🔴 CRITICAL |
| 2 | **ATR STOP** | 价格 ≤ entry − 2×ATR | 🔴 HIGH |
| 3 | **TRAILING STOP** | 价格 ≤ 20日高点 × 0.92 | 🟠 HIGH |
| 4 | **PROFIT TARGET** | 价格 ≥ avg_cost × 1.20 | 🟡 MEDIUM |
| 5 | **TIME STOP** | 持仓 ≥ 20 交易日无进展 | 🔵 REVIEW |

### Legacy 持仓处理 / Legacy Position Handling

对于未实现盈利 > 100% 的持仓（如持有多年的仓位），`avg_cost` 已失去参考意义。系统自动切换到滚动止损模式：

For positions with unrealized PnL > 100% (long-held positions), `avg_cost` loses meaning. The system automatically switches to rolling stop mode:

```
stop_source = "auto_rolling"
hard_stop   = current_price × 0.88    (−12% from today, not from old cost)
atr_stop    = current_price − 2×ATR   (ATR reference = current price)
trailing    = 20d_high × 0.92          (−8% from recent peak)
```

---

## 配置 / Configuration

### 自选股列表 / Watchlist

编辑 `quant/filter.py` 中的 `WATCHLIST`：

Edit `WATCHLIST` in `quant/filter.py`:

```python
WATCHLIST = ["NVDA", "META", "AMD", "QQQ", "TSLA", "GOOG", "NFLX", ...]
```

### 关键参数 / Key Parameters

| 参数 | 文件 | 默认值 | 说明 |
|---|---|---|---|
| `RISK_PER_TRADE_PCT` | `portfolio_engine.py` | `0.01` | 每笔交易风险 1% |
| `MAX_PORTFOLIO_HEAT` | `portfolio_engine.py` | `0.08` | 组合最大热度 8% |
| `HARD_STOP_PCT` | `position_manager.py` | `0.12` | 硬止损 -12% |
| `TRAILING_STOP_PCT` | `position_manager.py` | `0.08` | 移动止损 -8% |
| `PROFIT_TARGET_PCT` | `position_manager.py` | `0.20` | 止盈 +20% |
| `ATR_PERIOD` | `position_manager.py` | `14` | ATR 周期 |
| `ATR_STOP_MULT` | `risk_engine.py` | `1.5` | 开仓止损 = 1.5×ATR |
| `ATR_TARGET_MULT` | `risk_engine.py` | `3.0` | 开仓目标 = 3.0×ATR |

---

## 输出文件 / Output Files

每次运行 `python quant/run.py` 生成以下文件：

Running `python quant/run.py` produces:

| 文件 | 说明 |
|---|---|
| `data/report_YYYYMMDD.txt` | 人类可读的每日量化报告 |
| `data/quant_signals_YYYYMMDD.json` | 完整信号 + 特征数据 (JSON) |
| `data/trend_signals_YYYYMMDD.json` | 趋势信号 + 持仓出场状态 (for LLM) |
| `data/news_YYYYMMDD.json` | 原始新闻 |
| `data/clean_trade_news_YYYYMMDD.json` | 过滤后新闻 (仅自选股事件) |
| `data/llm_prompt_YYYYMMDD.txt` | AI 提示词 (复制到 ChatGPT / Claude 使用) |

### 使用 LLM 提示词 / Using the LLM prompt

`llm_prompt_YYYYMMDD.txt` 包含完整的系统提示 + 用户消息，可直接粘贴到任意 AI 对话框：

The `llm_prompt_YYYYMMDD.txt` file contains a complete system + user message ready to paste into any AI chat:

1. 打开 `data/llm_prompt_YYYYMMDD.txt`
2. 复制全部内容
3. 粘贴到 ChatGPT、Claude 等
4. 获得结构化的投资建议 JSON

---

## 交易日志 / Trade Diary

`performance_engine.py` 维护 `data/trades.json` 记录已实现 P&L，用于策略验证。

`performance_engine.py` maintains `data/trades.json` to track realized P&L for strategy validation.

```python
from quant.performance_engine import open_trade, close_trade, compute_metrics

# 开仓 / Open trade
trade_id = open_trade(
    ticker="NVDA", strategy="trend_long",
    entry_price=920.0, stop_price=895.0, shares=15,
    target_price=957.5
)

# 平仓 / Close trade
close_trade(trade_id, exit_price=955.0)

# 查看绩效 / View metrics
metrics = compute_metrics()
# → win_rate, avg_win, avg_loss, expected_value, max_drawdown, by_strategy
```

### 绩效指标 / Performance Metrics

| 指标 | 说明 |
|---|---|
| `win_rate` | 盈利交易比例 |
| `avg_win_usd` | 平均盈利金额 |
| `avg_loss_usd` | 平均亏损金额 |
| `expected_value_usd` | 期望收益 = win_rate × avg_win + loss_rate × avg_loss |
| `max_drawdown_usd` | 最大回撤 (已实现 P&L 曲线) |
| `by_strategy` | 按策略分类的胜率和 P&L |

> **策略评估原则 / Evaluation Principle:** 系统使用已实现 P&L 而非预测准确率来评估策略优劣。
> The system evaluates strategies using realized P&L, not prediction accuracy.

---

## 市场方向过滤 / Market Regime Filter

```
BULL    → SPY & QQQ both above 200-day MA    → 允许开新多仓
NEUTRAL → one above, one below               → 高度精选，避免新仓
BEAR    → SPY & QQQ both below 200-day MA   → 禁止开新多仓，偏向减仓
```

BEAR 模式下，系统仍会生成信号供参考，但提示词会明确指示 AI 不建议新建仓位。

In BEAR regime, signals are still generated for reference, but the LLM prompt explicitly instructs against new positions.

---

## 未来扩展 / Future Extensions

- [ ] 期权流量分析 / Options flow analysis
- [ ] ETF 资金流向检测 / ETF flow detection
- [ ] 空头兴趣信号 / Short interest signals
- [ ] 自动执行 / Automated execution
- [ ] 回测引擎 / Backtesting engine
- [ ] 财报超预期数据集成 / Earnings surprise database
- [ ] 相对强度排名 / Relative strength ranking

---

*Built with Claude Code · Python 3.10+ · yfinance · pandas*
