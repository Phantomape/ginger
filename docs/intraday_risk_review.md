# Intraday Risk Review（盘中风控复评，~10:00 PT）

## 定位

`quant/run_intraday.py` 是一个**advisory-only 执行监控工具**：在盘中（建议美西
10:00 / 美东 13:00）用近实时价格重新评估**已有**的退出规则、市场 regime 和
portfolio heat，把破位/逼近情况整理成报告供人工决策。典型场景：NFP/CPI/FOMC
公布导致的盘中重挫，EOD 流程要到第二天才能反映。

它**不是**策略改动：

- 不生成任何入场信号，不改变 ranking / sizing / orders；
- 破位判定直接调用生产同一份代码（`trend_signals.compute_position_context`），
  只是把评估价格从昨日收盘换成盘中报价；
- "APPROACHING"（距 stop/target < 2%）只是报告展示层字段，**不进**
  `evaluate_exit_signals`，不构成新退出规则；
- 不写 `operator_inputs/`，不写任何 EOD artifact 路径；输出全部落在
  `data/daily/intraday/`（故意不注册进 `data_paths.DAILY_ARTIFACTS`，
  EOD/回测代码无法解析到这些文件）。

因此本工具不触发 Gate 1-4 / parity 协议。**边界提醒**：若要把盘中触发变成
自动规则（如"SPY 盘中跌超 X% 减仓"）或启用
`position_manager.py` 中实验关闭的 advisory 开关，即落入 Gate 1-4 范围，
必须走 `docs/agent_experiment_protocol.md`。

## 用法

```powershell
# 盘中正常运行（美西 10:00 左右手动触发）
.\.venv\Scripts\python.exe -B quant\run_intraday.py

# 跳过盘中新闻抓取
.\.venv\Scripts\python.exe -B quant\run_intraday.py --no-news

# 离线冒烟（不打报价网络，全部降级为昨收；隐含 --no-news）
.\.venv\Scripts\python.exe -B quant\run_intraday.py --offline
```

## 输出（文件名带 ET 时间戳，一天可多跑）

```
data/daily/intraday/reports/intraday_report_{YYYYMMDD}_{HHMM}ET.txt     人读报告
data/daily/intraday/llm/intraday_llm_prompt_{YYYYMMDD}_{HHMM}ET.txt    可贴给 LLM 的盘中风险 prompt
data/daily/intraday/snapshots/intraday_review_{YYYYMMDD}_{HHMM}ET.json 机器可读全量 payload
data/daily/intraday/news/intraday_news_raw_{...}.json                  盘中 RSS 原始
data/daily/intraday/news/intraday_trade_news_{...}.json                trade 过滤后
```

报告段落：宏观事件日标记（含日历过期警告）→ 盘中 regime（对比昨收口径，
盘中翻转高亮）→ 盘中 portfolio heat → BREACHED → APPROACHING → OK →
NOT REVIEWED（报价缺失，需人工核对）→ open pending actions → 盘中新闻 →
DATA QUALITY（报价来源统计）。

## 报价语义（yfinance）

降级链（`quant/intraday_quotes.py`，每 ticker 独立）：
`fast_info`（近实时）→ 1 分钟 bar → 昨收（标 `STALE`）→ `unavailable`
（报告标 "manual check required"，不参与 heat 汇总）。每个价格都带
`source` 标注，stale/缺失绝不静默。若未来需要更强 SLA 或盘前触发，
换行情源只需改 `intraday_quotes.py` 一个文件。

已知口径：日线历史是复权价而实时报价是原始价，除息日附近 stop/ATR 可能有
微小错位（EOD 流程本身同口径）；legacy 持仓的 `auto_rolling` stop 随盘中价
浮动，报告中已标注。

## 关键正确性约束

盘中跑时 yfinance 日线的最后一行是**当日未完成 bar**。
`intraday_review.split_completed_sessions` 把它从 MA200 / ATR / high_20d /
prev_close / high_since_entry 的计算中剔除——否则 prev_close 会变成盘中价
本身（session return 恒为 0），所有滚动统计被半日 bar 污染。改动相关逻辑时
必须保留 `quant/test_intraday_review.py` 中对应测试。

## 宏观事件日历（种子 + 自动积累 overlay）

`quant/macro_events.py` 是 NFP/CPI/FOMC 官方发布日的单一真相源
（从 `macro_relief_leadership_paper_sleeve.py` 抽出并 re-export，对象同一性
有测试锁定）。结构分两层：

- **种子列表**（模块内字面量）：手工核实的历史 + 已核实日期，自动化**永不
  改动**（sleeve replay 与多个 experiment 依赖）；
- **overlay**（`data/reference/macro_events_overlay.json`）：由
  `quant/macro_events_refresh.py` 在每日生产运行中自动从官方源抓取追加，
  **append-only 且只接受 `OVERLAY_MIN_DATE`（2026-06-10）之后的未来日期**，
  导入时合并进同一个列表对象（identity 不变）。

自动抓取已挂载到 `run.py`（Step 1.6）和 `run_intraday.py`，默认 7 天限频：
NFP/CPI 优先走 FRED release/dates API（设 `FRED_API_KEY` 时），否则解析
bls.gov 官方日程页；FOMC 解析 federalreserve.gov 官方会议日历（取每次会议
最后一天为 decision day）。任何源失败都不改动任何文件，由审计继续报警，
下次运行自动重试——所以日期会随日常生产任务自然积累，不再依赖手工维护。

## 市场假日（规则生成，永不过期）

`quant/market_calendar.py` 按 NYSE 交易所规则生成任意年份的全天休市日
（含 Good Friday 复活节算法和周末顺延规则，包括"元旦逢周六不补休"特例）。
`finra_iwm_paper_sleeve.US_MARKET_HOLIDAYS` = 已核实的 2025-2027 验证钉 ∪
规则生成（自动延伸到明年）；测试断言生成器逐年复现全部验证钉，因此冻结
窗口 replay 不受影响。突发特别休市（如哀悼日）无法预测，发生时手工补钉。

## 静态日历审计（防"静默过期"类 bug）

`quant/calendar_audit.py` 统一审计上述日期表，结果出现在盘中报告的
DATA QUALITY 段（`[!]` = stale/gap，`[i]` = info）：

- `MACRO_EVENTS`：按 family 检测覆盖过期（提前 45 天预警）+ NFP/CPI 的
  "未来缺月"检测（FOMC 日程不规则不适用）；只查未来月份，不会误报历史上
  真实的发布中断。自动抓取正常时这些告警会自行消失。
- `US_MARKET_HOLIDAYS`：覆盖年份检测——现在它报警意味着规则生成接线坏了，
  而不是例行数据录入任务。
- `PUBLICATION_OVERRIDES`：信息性提示验证钉边界。已核实现有每条钉都等于
  "剔除假日后第 7 个工作日"规则的输出，钉之外回退到该规则（snapshot 中
  `publication_date_method` 字段标注来源），假日表自动延伸后回退结果持续正确。

维护原则：审计报警且自动抓取持续失败时，才需要人工从官方源核对补录，
**不要凭记忆或推算录入**。冻结的标准回测窗口（如 `form4_shadow_outcomes`
里的三窗口、SEC backfill 的 DEFAULT_END=2026-04-21）是协议固定值，
不属于陈旧数据，不要"修"。

## 测试

```powershell
.\.venv\Scripts\python.exe -B -m pytest quant\test_macro_events.py quant\test_intraday_review.py quant\test_macro_relief_leadership_paper_sleeve.py quant\test_production_parity.py -q
```
