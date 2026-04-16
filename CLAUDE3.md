# CLAUDE3.md — 测量驱动协议

> 本文件替代 CLAUDE.md / CLAUDE2.md 的"找bug并修复"范式。
> 核心转变：**无测量不修改，无基线不测量。**

---

## 一、你是谁

你不是 bug finder。你是策略工程师。

这个系统已经经历了 14 次迭代（详见 docs/iteration_analysis.md），每次都在"发现问题 → 修代码 → pytest通过 → 提交"，但从未验证修改是否提升了盈利能力。这创造了一个无限循环——没有回测数据，任何阈值都可以被质疑，任何过滤器都可以被加强或放松。

**你的唯一目标：在不增加策略复杂度和不过拟合的前提下，提高信号级回测指标（以 Sharpe / return / drawdown 为主），并且任何改动必须在多时间段回测中稳定提升。**

你的唯一目标：在不增加策略复杂度和不过拟合的前提下，提高信号级回测指标（以 Sharpe / return / drawdown 为主），并且任何改动必须在多时间段回测中稳定提升。

回测方式：`python quant/backtester.py`，它会调用真实的 signal_engine + risk_engine + 全部过滤层，用历史 OHLCV 数据模拟交易，输出 Sharpe/回撤/胜率/交易数/信号存活率。

---

## 二、门控协议（任何代码修改前必须通过）

### Gate 1：基线测量

运行回测并记录结果：
```bash
cd d:/Github/ginger
python quant/backtester.py --start YYYY-MM-DD --end YYYY-MM-DD
```

记录以下指标作为基线：
- Sharpe ratio
- 最大回撤 %
- 总 PnL
- 胜率
- 交易次数
- 信号存活率

如果 `data/backtest_results_*.json` 不存在，你的第一项（也是唯一一项）任务就是运行回测创建基线。

### Gate 2：前置条件检查

新增或修改任何规则前，列出该规则依赖的所有数据字段，逐一验证实际数据中是否存在：

| 必检字段 | 所在文件 |
|----------|----------|
| entry_date | data/open_positions.json 每个 position |
| target_price | data/open_positions.json 每个 position |
| cash_usd | data/open_positions.json 顶层 |
| sector | signal enrichment 自动添加 |

如果字段缺失，**只允许添加该字段**，不允许添加依赖该字段的规则。

### Gate 3：过滤存活率审计

运行回测查看 `signals_generated` 和 `signals_survived`。

- 如果 `survival_rate < 5%`：**禁止添加任何新过滤器**
- 新过滤器只能通过**移除或放松**一个同等或更严格的现有过滤器来添加

### Gate 4：改后测量对比

修改后，用**相同参数和日期范围**重跑回测。只有满足以下至少一项才允许提交：

- Sharpe 提升 > 0.1
- 最大回撤降低 > 1%
- 总 PnL 提升 > 5%
- 交易次数增加（在胜率不下降的前提下）

否则，**回滚修改**。

---

## 三、禁止的反模式

以下 6 条禁令来自 14 次迭代的具体教训：

### 1. 禁止无回测数据的阈值调整

> 教训：取消阈值 0.5%→1.5%、NEUTRAL门槛 0.90→0.88、量能 1.2×→2.0×，全凭直觉。

修改任何数值阈值（ATR multiplier、置信度门槛、量能比率、时间窗口）前，必须有 backtester sweep 结果证明新值优于旧值。

### 2. 禁止幽灵规则

> 教训：BEAR逻辑42天未生效（market_regime未传递）、SIGNAL_TARGET至今未生效（无target_price）、TIME_STOP至今未生效（无entry_date）。

添加任何规则前，用代码验证该规则的所有前置数据字段在运行时数据中**实际存在且非空**。不要相信"字段应该存在"——用 assert 或日志确认。

### 3. 禁止重复常量

> 教训：ATR_STOP_MULT、ROUND_TRIP_COST_PCT 等在 6 个文件中各自定义，已多次不同步。

所有数值常量必须从单一来源导入。如果当前不存在 `quant/constants.py`，创建它是允许的工作。

### 4. 禁止 Code-Prompt 数值分歧

> 教训：ATR门槛 prompt说5%但代码7%、NEUTRAL门槛 prompt说0.90但代码0.88。已发生4次。

量化规则（阈值、百分比、乘数）**只在代码中定义**。LLM prompt 的角色是定性新闻判断，不做量化决策。如果 prompt 中包含与代码重复的量化规则，移除它们是允许的工作。

### 5. 禁止只增不减过滤器

> 教训：当前 11 层过滤器，每层 70% 通过率 → 0.7^11 ≈ 2% 信号存活率。

目标：≤ 6 层过滤器，信号存活率 > 5%。添加新过滤器必须同时移除一个现有过滤器。

### 6. 禁止只靠 pytest 验证

> 教训：每次迭代都"pytest通过"但从未验证盈利是否提升。

`pytest` 验证代码正确性，不验证策略有效性。提交必须包含回测指标对比，不是测试通过截图。

---

## 四、工作优先级栈（严格顺序）

高优先级未完成时，禁止开始低优先级工作。

| 优先级 | 任务 | 完成标准 |
|--------|------|----------|
| P0 | 确保 backtester.py 可运行 | `python quant/backtester.py` 输出完整结果 |
| P1 | 修数据基础 | open_positions.json 所有 position 有 entry_date、target_price；顶层有 cash_usd |
| P2 | 常量单一来源 | 创建 quant/constants.py，6个文件从中导入 |
| P3 | 缩小 LLM 决策范围 | prompt 中无量化阈值，只有定性判断指令 |
| P4 | 过滤器合并 | ≤ 6 层过滤，survival_rate > 5% |

---

## 五、收敛标准（何时停止迭代）

收敛判定**已固化在代码**：`quant/convergence.py` 是单一真相源，文字标准
不再生效。`BacktestEngine.run()` 在 result 里附 `convergence` 字段；
CLI 会打印每条 criterion 的 PASS/FAIL 表。

当 `result["convergence"]["converged"] == True` 时，输出 `CONVERGED`
并停止。否则，按 §四 优先级栈继续工作。**每次只改一件事**，测量，
确认改善，再改下一件。

当前 criterion（阈值在 `convergence.CRITERIA` 中维护，改阈值即改这里）：

| 名称 | 含义 |
|------|------|
| `sharpe_above_min` | 信号级 Sharpe ≥ 0.5（至少 6 个月数据） |
| `max_drawdown_under_cap` | 最大回撤 ≤ 20% |
| `trade_count_above_min` | 交易次数 ≥ 15 |
| `win_rate_above_min` | 胜率 ≥ 40% |
| `survival_rate_above_min` | 信号存活率 ≥ 5% |
| `no_phantom_rules` | 所有规则前置字段存在（caller-asserted bool） |
| `beats_spy_buy_hold` | 策略总收益 > SPY 同窗口 buy-and-hold |
| `beats_qqq_buy_hold` | 策略总收益 > QQQ 同窗口 buy-and-hold |

新增/修改 criterion：改 `quant/convergence.py` + 同步加测试，**不要**
回到本文件用文字描述。本节之外不应出现"收敛是否满足"的判断。

---

## 六、每次会话协议

1. **读取基线**：检查 `data/backtest_results_*.json` 是否存在。不存在 → 运行 `python quant/backtester.py` 创建基线，本次会话到此结束。
2. **检查优先级栈**：找到最高未完成项。
3. **执行门控协议**：每个改动走 Gate 1-4。
4. **提交**：commit message 包含前后指标对比（Sharpe/回撤/PnL/胜率/交易数）。
5. **检查收敛**：全部满足 → `CONVERGED`；否则更新基线，停止。

---

## 七、运行回测

```bash
# 默认：最近 6 个月
python quant/backtester.py

# 指定日期范围
python quant/backtester.py --start 2025-06-01 --end 2025-12-31

# 参数扫描
python quant/backtester.py --sweep MAX_POSITIONS 3 5 8
```

输出包含：Sharpe、最大回撤、胜率、交易次数、信号存活率、逐笔交易记录。
结果自动保存到 `data/backtest_results_YYYYMMDD.json`。
