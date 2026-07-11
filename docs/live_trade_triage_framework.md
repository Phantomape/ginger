# 人工实时交易判断框架

这个文档用于用户临时询问“今天要不要开仓 / 加仓 / 追不追 / 夜盘还要不要动”时的人工判断，例如 MUU、SNXX 这类高波动或杠杆 ETF。它的定位是 **discretionary triage**：把当前新闻、moomoo OpenD 行情、技术面和风险边界整理成可执行的人工判断。

它不是已回测 alpha，不是 Gate 1-4 结论，不是 live-ready 策略，也不能直接改变 `quant/run.py`、订单、ranking、sizing、exit 或任何真钱自动化行为。若要把其中某个规则升级成策略逻辑，必须另起实验 ID，按 `docs/agent_experiment_protocol.md` 和 `docs/backtesting.md` 走完整 Gate 1-4。

## 代码执行边界

完整实现说明、状态机、artifact 和故障降级见 `docs/intraday_code_driven_triage.md`。

定时盘中流程应优先使用代码产出的结构化事实，而不是让 LLM 重算：

- `quant/intraday_moomoo.py`：OpenD snapshot、日线/5 分钟线、VWAP、ATR%、RSI、SMA/EMA、区间位置和代理映射。
- `quant/intraday_triage.py`：退出优先、数据完整性、RTH、结构确认、底层/行业/大盘确认、组合热度和加仓风险上限。
- `quant/run_intraday.py`：编排并输出 `machine_triage.rows[].allowed_actions` 与安全默认动作。
- `quant/finalize_intraday_decision.py`：校验新闻语义响应，拒绝越权动作后排他写入最终 forward ledger。

LLM 只负责核验最新新闻是否形成 veto、在代码给定的 `allowed_actions` 中选一个动作，并给简短解释。它不得重算技术指标、修改确认位/失效位、扩大加仓上限或在代码未开放时选择 `ADD_SMALL`。

## 适用场景

- 用户明确询问某个标的当下是否开仓、加仓、减仓或追涨。
- 用户给出 moomoo 截图、AI 摘要、期权墙、KDJ/MA/IV/OI 等提示，希望判断有没有启发。
- 标的是杠杆 ETF、单名股票、半导体/AI 主题股、夜盘/盘前高波动品种，且决策高度依赖实时行情。
- 需要一个简洁答案，但必须能说明“为什么现在能动 / 为什么等 / 为什么不动”。

不适用：

- 回测策略改动、默认纸面 sleeve、新候选池、新过滤器、仓位模型、止损/止盈规则改动。
- 想证明某个技术指标长期有效。
- 想把当前一次判断写成 accepted alpha。

## 硬边界

1. 当前新闻和实时行情必须重新获取。不要依赖模型记忆回答“今天”“夜盘”“最新”。
2. 结论必须带明确时间戳和市场阶段，例如 `2026-07-10 12:40 ET，RTH 中段`。
3. 若 moomoo OpenD、新闻或仓位数据不可用，必须把缺口写出来，并降低结论置信度。
4. LLM 可以解释新闻、催化和风险，但不能把“我觉得”变成买卖硬规则。
5. 期权 IV/OI/put-call 只能作为上下文，不能单独当方向信号。仓库历史已经多次把 options-flow alpha 退回 forward/context 面。
6. 对杠杆 ETF，默认只讨论短线战术仓位；不要把 2x/3x 日内工具解释成可长期摊低成本的投资仓。
7. 不给保证性语气，不替用户下单，不在没有风险预算时给精确股数。

## 必取输入

### 1. 标的身份

先用 OpenD 确认标的是什么：

- `get_stock_basicinfo`：证券类型、交易所、名称、上市时间。
- 若是杠杆 ETF，识别底层标的或主题，例如 MUU -> MU，SNXX -> SNDK。
- 同时取底层、行业代理和大盘代理：半导体常用 `SMH` 或 `SOXX`，大盘常用 `QQQ`、`SPY`。

### 2. 当前快照

用 OpenD `get_market_snapshot` 至少取：

- last / prev close / open / high / low。
- bid / ask / spread，特别是夜盘、盘前和低流动性 ETF。
- pre / after / overnight price，如可用。
- volume / volume ratio / 52w high-low。
- 标的、底层、行业 ETF、QQQ、SPY 同时取，避免只看单一票。

### 3. 日线技术面

用 `request_history_kline(..., KLType.K_DAY, AuType.QFQ)` 计算：

- SMA5 / SMA10 / SMA20 / SMA50，EMA8 / EMA21。
- RSI14、MACD histogram。
- ATR14 和 ATR%。
- 当日 close location：`(close - low) / (high - low)`。
- `ret2d / ret5d / ret20d`。
- 当前价距 20 日高低点、52 周高低点。
- 当日成交量相对 20 日均量。

ATR 是平均真实波幅。真实波幅使用 `max(high-low, abs(high-prev_close), abs(low-prev_close))`，ATR14 是最近 14 根日线真实波幅的平均。ATR% 很高时，仓位必须自然缩小。

### 4. 分时结构

用 `request_history_kline(..., KLType.K_5M, extended_time=True, session=Session.ALL)` 取当日分时，并按阶段拆开看：

- RTH VWAP、全时段 VWAP，必要时再算 after-hours / overnight VWAP。
- last vs VWAP。
- session high / low。
- 最近 6-12 根 5m 收盘序列。
- 盘中是否冲高回落、低位收盘、重新站回 VWAP、突破后回踩守住。
- 夜盘和盘前必须额外看成交量与 spread，低量跳动不能当强确认。

### 5. 新闻和催化

最近新闻必须重新查：

- 公司硬催化：财报、指引、评级、监管、并购、产能、客户、供应链。
- 行业催化：同业消息、价格周期、供需、政策、分析师行业报告。
- 大盘和宏观：利率、CPI/PPI、FOMC、科技股风险偏好。
- 分清硬催化、软情绪、旧新闻再传播。
- 回答里给来源链接；若新闻没查到或工具不可用，明说。

### 6. 期权上下文

只有在用户截图或行情明显涉及期权墙、IV、OI 时使用：

- 最近到期期权的关键 strike、call/put OI、volume、IV、bid/ask。
- 关注大整数位或高 OI strike 是否与现价、VWAP、日内高低点重合。
- 解释为“磁吸/阻力/支撑候选”和“波动预期”，不要解释成确定方向。
- IV 很高且价差很宽时，倾向提示不适合直接买短期期权。

### 7. 仓位和组合暴露

如果问题是加仓，必须知道当前是否已有仓位：

- 优先读 `operator_inputs/open_positions.json`，或让用户说明实际持仓。
- 若仓位不明，只能回答“是否适合新增风险”，不能假装知道可加多少。
- 对同主题已有暴露，例如 MUU、SNXX、半导体、AI 硬件，要合并看风险。

## 判断顺序

### A. 先看是否有资格动手

满足越多，越接近可小仓试：

- 标的在 VWAP 之上，且回踩 VWAP 或关键位不破。
- 底层标的也在 VWAP 之上。
- 行业 ETF 和 QQQ/SPY 至少不拖后腿。
- close location 偏高，而不是高开低走收在日内低位。
- 当天强势来自硬催化或行业确认，而不是无量夜盘跳动。
- spread 可接受，成交量足够。

出现这些，默认不追或不加：

- 跌破 RTH VWAP、关键整数位或期权墙后收不回。
- 冲高回落，收在日内低位附近。
- 标的涨但底层、行业或 QQQ/SPY 不确认。
- 夜盘低量反抽或低量下破，无法验证。
- ATR% 极高且价格已经远离支撑，止损只能放很宽。
- 用户已经有同主题高 beta 暴露。

### B. 再看关键价位

至少列出这些价位：

- 前收、当日开盘、日内高低点。
- RTH VWAP / 全时段 VWAP。
- 盘前、夜盘 high-low。
- SMA10 / SMA20 / EMA8 / EMA21，视当前结构选择最相关的 2-3 个。
- 重要整数位或期权高 OI strike。
- 底层标的的同类关键位。

关键位的用法：

- 开仓看“站上并守住”，不是只看瞬间刺破。
- 加仓看“突破后回踩不破”或“失守后重新收回”，不要在失守 VWAP 后摊低。
- 止损/失效位应绑定结构，例如 VWAP、日内低点、前低，而不是随口给固定百分比。

### C. 最后决定动作

可用这些标签，但回答时要用人话说清楚：

- `NO_TRADE`：不开新仓，风险收益不合适。
- `WAIT`：有机会，但必须等某个价位收回或回踩确认。
- `OPEN_SMALL`：可以试小仓，条件是当前结构仍有效。
- `ADD_SMALL`：已有仓位时，只允许顺势小加，不在破位后摊低。
- `HOLD_ONLY`：已有仓位可观察，但不增加风险。
- `REDUCE_RISK`：破关键位、底层背离或催化转坏时降低风险。

对 2x 杠杆 ETF 的默认仓位语气：

- “小仓试”通常比“开满”合理。
- ATR% 超过 15%-20% 时，仓位要明显低于普通股票。
- ATR% 接近或超过 25% 时，只能按投机仓位看，不能用普通止损宽度。
- 不把加仓建立在“已经跌了很多应该反弹”上；必须看到结构收复。

## 验证框架

这套机制不能保证单次盈利。它只能通过严格记录和结算来证明自己是否有正期望：是否比“立刻追涨”“永远不交易”“买底层股票”“买行业 ETF/QQQ”这些替代方案更好，且尾部风险更小。

### 1. 先定义可赚钱的假设

人工 triage 的赚钱机制只能来自这些可检验假设：

- VWAP、关键位和底层确认能减少追在日内衰竭点上的概率。
- ATR% 仓位缩放能降低杠杆 ETF 的尾部损失。
- `WAIT` 比直接追高有更好的入场价或更少假突破。
- `NO_TRADE` 能避开更多负期望交易，机会成本小于避免的亏损。
- `ADD_SMALL` 只在重新站回关键位后加仓，优于破位后摊低。
- 新闻硬催化 + 技术确认的组合，优于只有技术指标或只有新闻标题。

如果未来要把这些假设写进策略逻辑，必须拆成一个单一可归因决策假设，并走实验 Gate 1-4。

### 2. 每次判断都要先入账

每次用户问到具体标的，先记录一条不可事后修改的 decision row。最低字段：

- `timestamp_et`、`market_phase`、`agent`、`user_question`。
- `ticker`、`underlying`、`sector_proxy`、`market_proxy`。
- `action_label`：`NO_TRADE` / `WAIT` / `OPEN_SMALL` / `ADD_SMALL` / `HOLD_ONLY` / `REDUCE_RISK`。
- `confidence`：低 / 中 / 高，或 0-1 概率。
- `reference_price`：做判断时的标的价格。
- `entry_condition`：若是 `WAIT`，写清触发价位或结构。
- `invalidation_level`：判断失效位。
- `time_horizon`：例如 H1、RTH close、next day、3 trading days。
- `raw_snapshot_ref`、`news_refs`、`notes`。

不要只记录出手交易。`NO_TRADE` 和 `WAIT` 必须同样记录，否则无法衡量避险价值和机会成本。

### 3. 结算时看反事实

每条 decision row 到期后结算这些结果：

- `ret_to_h1`、`ret_to_rth_close`、`ret_to_next_close`、`ret_to_3d_close`。
- `max_favorable_excursion` 和 `max_adverse_excursion`，最好用 ATR 归一化。
- 是否先触发 `invalidation_level`。
- 若 `OPEN_SMALL` / `ADD_SMALL`，按预设执行语义计算纸面 PnL。
- 若 `WAIT`，计算等待条件触发后的表现，以及若当时直接追入会怎样。
- 若 `NO_TRADE`，计算“当时追入”的反事实收益，区分避开亏损和错过上涨。
- 与底层股票、行业 ETF、QQQ/SPY、现金比较 replacement value。

杠杆 ETF 要把底层和 ETF 分开结算：判断可能对了方向，但 ETF 因杠杆、spread、隔夜或波动衰减让执行价值变差。

### 4. 最小验收指标

样本太少时只能叫观察，不叫有效。默认读法：

- 少于 20 条闭合判断：只看案例复盘。
- 20-50 条闭合判断：只能算 observed-only lead。
- 50-100 条闭合判断：可以看动作标签分组的稳定性。
- 100 条以上且跨多个市场阶段：才值得考虑拆成可回测策略假设。

核心指标：

- `OPEN_SMALL` / `ADD_SMALL` 的平均和中位 PnL，扣除 spread/slippage 后为正。
- `NO_TRADE` 的 avoided loss 大于 missed gain。
- `WAIT` 相对 immediate entry 改善 entry price 或降低 MAE。
- `REDUCE_RISK` 相对 hold 降低回撤，且没有过度砍掉后续收益。
- 置信度分桶校准：高置信判断的命中率和 EV 应高于低置信判断。
- 单一 ticker、单一主题、单一市场日贡献不能支配结果。

### 5. 通过阶梯

证据阶梯从低到高：

1. 案例解释：一次判断讲得通，但没有统计意义。
2. Forward ledger：所有判断先记录，后结算。
3. Observed-only lead：闭合样本显示某些动作标签有正 replacement value。
4. 固定规则提案：把 lead 拆成一个明确、不可事后调参的决策假设。
5. Gate 1-4 回测：若能取得点时间历史数据，用标准协议挑战基线。
6. Default-off paper：共享 helper 同时跑 historical replay 和 daily snapshot。
7. 小额 live envelope：只有在 execution envelope、容量、滑点、kill switch 都验证后，才讨论真钱放大。

任何阶段失败，都不能把失败样本删掉。失败样本是这套机制最重要的防重复资产。

## 输出模板

回答应先给结论，再给证据。不要先铺十段分析让用户猜。

```text
结论：现在不加 / 等价位 / 可以小仓试。

时间和数据：截至 YYYY-MM-DD HH:MM ET，处于 RTH / 盘前 / 夜盘；OpenD 快照时间；新闻来源时间。

标的身份：是否杠杆 ETF；底层是谁；行业和大盘代理。

技术结构：日线趋势、ATR%、VWAP、close location、分时尾部、底层/行业确认。

关键价位：上方确认位、下方失效位、VWAP、日内高低点、重要 strike 或均线。

新闻/催化：硬催化是什么；是否已经被价格反映；有没有反向风险。

期权/波动：若相关，说明 OI/IV 是上下文，不是方向结论。

执行条件：如果要动，只能在什么条件下小仓；什么条件下撤销判断。
```

第一句示例：

- “我不建议现在加仓；它虽然还是绿的，但已经失守 VWAP，底层也没确认。”
- “可以小仓试，但不是追满；条件是回踩 27.3-27.6 不破，且底层继续在 VWAP 上方。”
- “夜盘这个量不足以支持加仓，先等美股 RTH 重新站回关键位。”

## moomoo OpenD 取数提示

常用 SDK 调用：

- `OpenQuoteContext(host, port)`。
- `get_stock_basicinfo(Market.US, stock_type=SecurityType.STOCK/ETF)`。
- `get_market_snapshot([codes])`。
- `request_history_kline(code, start, end, ktype=KLType.K_DAY, autype=AuType.QFQ)`。
- `request_history_kline(code, start, end, ktype=KLType.K_5M, extended_time=True, session=Session.ALL)`。
- 期权仅在需要时取：expiration、chain、selected option snapshots。

在 Windows 上运行 moomoo SDK 时，若遇到日志或配置目录锁，可以在脚本开头把 `APPDATA`、`LOCALAPPDATA`、`TEMP` 指向仓库内临时目录，例如 `data/runtime/moomoo_sdk_appdata`，避免污染用户目录或卡住 OpenD 日志。

## 多 agent 协作

多个 agent 一起判断时，交接里必须留下：

- 标的和底层代码。
- 查询时间、时区、市场阶段。
- OpenD 原始快照摘要。
- 日线和分时派生指标。
- 新闻来源链接和发布时间。
- 关键价位、动作标签、失效条件。
- 哪些数据没拿到。

不要只留下“看多 / 看空”。下一位 agent 应该能从你的记录复现为什么当时判断“等”“不加”或“小仓试”。
