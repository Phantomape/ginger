# Ginger — 量化辅助交易系统

每日运行一次，输出量化日报、可审计 JSON 和 AI 提示词文件。把提示词粘贴到
ChatGPT 或 Claude，得到结构化的持仓决策 JSON。

> 设计原则：简单信号 · 严格风控 · 共享策略逻辑 · LLM 只做新闻/语义判断

---

## 文档优先级

本 README 是使用入口和系统概览。策略实验、生产/回测一致性、回测窗口和
LLM 职责边界以以下文档为准：

- `AGENTS.md`
- `docs/alpha-optimization-playbook.md`
- `docs/backtesting.md`
- `docs/production_backtest_parity.md`

如果 README 中的示例参数与上述文档或 `quant/constants.py` 不一致，以代码和
上述规范文档为准。

## 目录

- [快速开始](#快速开始)
- [持仓配置](#持仓配置)
- [使用流程](#使用流程)
- [系统架构](#系统架构)
- [策略说明](#策略说明)
- [风险规则](#风险规则)
- [输出文件](#输出文件)
- [开发与测试](#开发与测试)

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r news_collector/requirements.txt
```

主要依赖：`yfinance` · `pandas` · `feedparser` · `python-dateutil` · `openai`

### 2. 配置持仓

编辑 `data/open_positions.json`（见[持仓配置](#持仓配置)）

### 3. 运行

```bash
cd d:/Github/ginger
python quant/run.py
```

### 4. 使用输出

打开 `data/llm_prompt_YYYYMMDD.txt`，复制全部内容，粘贴到 ChatGPT / Claude，获得持仓决策 JSON。

---

## 持仓配置

编辑 `data/open_positions.json`：

```json
{
  "portfolio_value_usd": 70000,
  "cash_usd": 5000,
  "positions": [
    {
      "ticker": "NVDA",
      "direction": "long",
      "shares": 41,
      "avg_cost": 102.17,
      "entry_date": "2025-11-15",
      "target_price": 145.00,
      "risk_notes": "核心 AI 持仓"
    }
  ]
}
```

**字段说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `portfolio_value_usd` | 是 | 账户总市值（含现金），用于热度和定仓计算 |
| `cash_usd` | 否 | 现金余额，用于计算实时组合价值 |
| `ticker` | 是 | 股票代码（大写） |
| `shares` | 是 | 持仓股数 |
| `avg_cost` | 是 | 平均建仓成本 |
| `entry_date` | 推荐 | 建仓日期 `YYYY-MM-DD`；缺失则时间止损（45天）无法触发 |
| `target_price` | 推荐 | 原始信号目标价；缺失则 SIGNAL_TARGET 出场规则无法触发 |
| `override_stop_price` | 否 | 手动覆盖止损价（用于保本止损：盈利 ≥ 20% 后将此值设为 avg_cost） |

**自选股列表**：编辑 `quant/filter.py` 中的 `_BASE_WATCHLIST`，加入你想追踪新闻的标的。已持仓标的自动纳入监控。

---

## 使用流程

### 每日操作（约 2 分钟）

```
python quant/run.py
    ↓
data/llm_prompt_YYYYMMDD.txt  ← 复制此文件内容
    ↓
粘贴到 ChatGPT / Claude
    ↓
获得 JSON 决策：new_trade + add_on_trades + position_actions
    ↓
按输出操作（手动下单）
```

### AI 输出格式

```json
{
  "new_trade": "NO NEW TRADE",
  "add_on_trades": [],
  "add_on_vetoes": [],
  "position_actions": [
    {
      "ticker": "NVDA",
      "action": "HOLD",
      "reason": "position_state=HOLD，无出场信号",
      "exit_rule_triggered": "NONE",
      "shares_to_sell": null,
      "decision_mode": "forced_rule",
      "data_quality": "clean",
      "suggested_new_stop": null
    },
    {
      "ticker": "APP",
      "action": "EXIT",
      "reason": "HISTORIC_BREACH：止损价远高于当前价，强制清仓",
      "exit_rule_triggered": "HARD_STOP",
      "shares_to_sell": null,
      "decision_mode": "forced_rule",
      "data_quality": "inconsistent",
      "suggested_new_stop": null
    }
  ]
}
```

**当 `suggested_new_stop` 非 null 时**，将该值写入对应持仓的 `override_stop_price` 字段，保本止损才会在下次运行时生效。

---

## 系统架构

```
python quant/run.py
│
├── Step 1  open_positions.json       持仓 + 自选股
├── Step 2  regime.py                 市场方向（SPY/QQQ vs 200日均线）
├── Step 3  data_layer.py             OHLCV + 财报数据（yfinance）
├── Step 4  feature_layer.py          趋势特征、ATR、财报特征
├── Step 5  trend_signals.py          持仓出场信号检测
│           preflight_validator.py    ← 预判断：account_state / position_states
├── Step 6  signal_engine.py          三策略信号生成
│           risk_engine.py            R:R / TQS / 止损止盈
│           portfolio_engine.py       定仓 / 热度计算
├── Step 7  report_generator.py       日报 → data/report_YYYYMMDD.txt
├── Step 8  fetch_news.py + filter.py RSS 新闻 → 过滤 → T1/T2/T3 分层
└── Step 9  llm_advisor.py            组装提示词 → data/llm_prompt_YYYYMMDD.txt
```

**关键设计：共享策略逻辑 + preflight_validator.py**

会影响买、卖、加仓、减仓、仓位大小、候选排序、组合热度和仓位槽的逻辑，
必须在共享模块中实现，并同时被 `quant/backtester.py` 与 `quant/run.py`
调用或暴露。详见 `docs/production_backtest_parity.md`。

在数据到达 LLM 之前，代码层预判断所有硬规则，注入 section 4：

| 字段 | 含义 |
|------|------|
| `account_state` | `FIRE` / `DEFENSIVE` / `NORMAL` |
| `new_trade_locked` | `true` 时 AI 直接输出 NO NEW TRADE，不分析新机会 |
| `position_states` | `{ticker: CRITICAL_EXIT \| HIGH_REDUCE \| WATCH \| HOLD}` |
| `suggested_reduce_pct` | `{ticker: 25\|33\|50\|100}` — HIGH_REDUCE 仓位的预计算减仓比例 |
| `bear_emergency_stops` | `{ticker: float}` — BEAR 市场下每个仓位的紧急止损价 |
| `current_prices` | `{ticker: float}` — 所有持仓的当日收盘价 |

AI 读这些字段得出结论，不再做条件推理——减少了"LLM自行判断 vs 代码预判断"的不一致。

---

## 策略说明

### Strategy A — 趋势跟踪 (trend_long)

| 条件 | 说明 |
|------|------|
| 价格 > 200日均线 | 大趋势向上 |
| 今日收盘 > 20日最高价 | 突破确认 |
| 成交量 > 20日均量 × 1.5 | 放量支撑 |
| 近10日涨幅 ≥ 0% | RS 门（非下跌股） |

### Strategy B — 波动突破 (breakout_long)

| 条件 | 说明 |
|------|------|
| 当日波幅 > 1.5 × ATR | 异常大阳线 |
| 今日收盘 > 20日最高价 | 突破确认 |
| 成交量 > 1.2 × 均量 | 量价配合 |

### Strategy C — 财报事件 (earnings_event_long)

当前默认禁用，直到 earnings 数据质量和事件分级重新通过多窗口验证。

| 条件 | 说明 |
|------|------|
| 财报在 6–8 天内 | 最佳 PEAD 窗口 |
| 近10日涨幅 > SPY 同期 | 跑赢大盘（RS 强制门） |
| 历史财报正向超预期 | 正向惊喜历史 |
| ATR / 价格 ≤ 5% | 波动率控制 |

**信号质量分（TQS）**：用于风险和候选质量审计；具体门槛和风险乘数以
`quant/constants.py`、`quant/risk_engine.py` 为准。

---

## 风险规则

### 开仓参数

```
止损    = entry − 1.5 × ATR
目标    = entry + 3.5 × ATR       R:R ≈ 2.3:1
定仓    = floor(portfolio × 1% / (entry − stop + 执行成本))
热度上限 = 8%（全组合最大风险敞口）
仓位上限 = 以 `quant/constants.py` 的 `MAX_POSITION_PCT` 为准
```

财报仓位额外缩减约 60–75%（用 max(ATR止损, 8%跳空风险) 定仓，防止财报缺口绕过止损）。

### 出场规则优先级

| 优先级 | 规则 | 触发 | 动作 |
|--------|------|------|------|
| 1 | HARD_STOP | 价格 ≤ hard_stop_price | EXIT |
| 2 | ATR_STOP | 价格 ≤ current_price − 1.5×ATR | EXIT |
| 3 | TRAILING_STOP | 价格 ≤ 20日高点 × 0.92 | EXIT / REDUCE |
| 4 | SIGNAL_TARGET | 价格 ≥ 3.5×ATR 目标价 | REDUCE 33% |
| 5 | PROFIT_TARGET | 盈利 ≥ 20% | REDUCE 50% + 保本止损 |
| 6 | PROFIT_LADDER_50 | 盈利 ≥ 50% | REDUCE 25% |
| 7 | TIME_STOP | ≥ 45 交易日且不足目标一半 | EXIT |

### 市场方向

| 状态 | 判断 | 行为 |
|------|------|------|
| BULL | SPY + QQQ 均在 200日均线上方 | 允许新多仓 |
| NEUTRAL | 混合信号 | 仅 confidence ≥ 0.88 的信号可入场 |
| BEAR | 均在 200日均线下方 | 禁止新仓；止损收紧至 current_price × 0.95 |

---

## 输出文件

每次运行生成以下文件（`data/` 目录）：

| 文件 | 说明 |
|------|------|
| `llm_prompt_YYYYMMDD.txt` | **★ 主输出** — 粘贴到 AI 使用 |
| `report_YYYYMMDD.txt` | 人类可读日报（信号摘要） |
| `quant_signals_YYYYMMDD.json` | 完整量化信号 JSON |
| `trend_signals_YYYYMMDD.json` | 持仓出场信号 JSON |
| `clean_trade_news_YYYYMMDD.json` | 过滤后新闻（含 tier 字段） |
| `news_YYYYMMDD.json` | 原始新闻 |

## 实验日志

策略修改和失败尝试统一记录到：

- `docs/experiment_log.jsonl`：结构化实验主日志
- `docs/experiment_log_format.md`：字段说明与填写规范

原则：

- 成功实验要记
- 失败实验更要记
- 失败记录必须包含参数、窗口、改前/改后指标，避免以后重复试错
- 生产/回测一致性改动还必须记录 `production_impact`

---

## 开发与测试

### 运行测试

```bash
cd d:/Github/ginger
python -m pytest quant/test_quant.py -v
```

测试覆盖包括：
- 策略逻辑（Strategy A/B/C 信号条件）
- 风险计算（TQS、R:R、定仓）
- 出场规则（止损、止盈、移动止损）
- **Contract 测试**（代码↔提示词接口验证）

### Contract 测试（防止代码与提示词漂移）

`PROMPT_FIELD_REGISTRY` 是代码层与 `trade_advice.txt` 的接口契约：

```python
# quant/test_quant.py
PROMPT_FIELD_REGISTRY = {
    "section4_top":      ["new_trade_locked", "position_states", "suggested_reduce_pct", ...],
    "section3a_signal":  ["trade_quality_score", "exec_lag_adj_net_rr", "entry_note", ...],
    "section3b_position":["breach_status", "daily_return_pct", "exit_levels", ...],
}
```

两个互锁测试：
- `test_registry_fields_exist_in_code_output` — 代码必须产出 registry 里的每个字段
- `test_registry_fields_referenced_in_prompt` — 提示词必须引用 registry 里的每个字段名

改字段名时三处同步更新（代码 + registry + 提示词），测试失败即发现漂移。

### 文件结构

```
ginger/
├── quant/
│   ├── run.py                  # ★ 每日入口
│   ├── data_layer.py           # OHLCV + 财报数据
│   ├── feature_layer.py        # 特征计算
│   ├── signal_engine.py        # 信号生成（3策略）
│   ├── risk_engine.py          # R:R / TQS / 止损止盈
│   ├── portfolio_engine.py     # 定仓 / 热度
│   ├── performance_engine.py   # 交易日志 / P&L
│   ├── trend_signals.py        # 持仓出场信号
│   ├── preflight_validator.py  # 预判断状态机
│   ├── regime.py               # 市场方向
│   ├── llm_advisor.py          # 提示词构建
│   ├── filter.py               # 新闻过滤 + 自选股
│   ├── report_generator.py     # 日报生成
│   └── test_quant.py           # 测试（含 contract 测试）
│
├── data/
│   ├── open_positions.json     # ★ 持仓配置（手动维护）
│   └── llm_prompt_YYYYMMDD.txt # ★ 每日 AI 提示词
│
└── instructinos/prompts/
    └── trade_advice.txt        # LLM 系统提示词
```

---

*Python 3.10+ · yfinance · pandas · feedparser · openai*
