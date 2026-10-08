# V3 落地进度

规则来源：[docs/v3_minimal_architecture.md](../docs/v3_minimal_architecture.md) 第 6 节。每步验收通过才进入下一步。

## 步骤 1：数据落地并冻结 — **通过（2026-10-08）**

做了什么：
- `v3/data/fetch.py`：追赶式下载，只用可回补的来源。
  - 26 只 ETF（yfinance，未按分红复权的收盘价，加分红、拆股、资本利得列；丢弃会整段重算的 Adj Close）。
  - FRED：DTB3、DGS3MO、DGS2、DGS10。
  - Ken French 月频：49 行业市值加权、三因子、动量因子；按内容变化存带日期的版本。
  - 已存的行永不覆盖；重新下载和已存行不一致时写入 `raw/revisions/` 并告警；只存已收盘的交易日（纽约时间 18:00 后）。
- `v3/data/check.py`：每次按 now − 最后日期重新计算状态（ETF 落后 >1 个工作日、FRED >5 个工作日、French >3 个月即告警），
  检查缺失交易日、重复、非正价格、>25% 的单日跳变；可选交叉核对 V1 warehouse 和 OpenD。
- `v3/tests/test_data.py`：8 个合成数据单测。

验收证据：

| 验收项 | 结果 |
|---|---|
| 历史起点 | SPY 1993-01-29；其他 ETF 均从成立日起（XLC 2018-06、XLRE 2015-10 是成立晚）；DTB3 1954、DGS10 1962；Ken French 1926-07 起 |
| 空目录重建 | 在临时目录从零重跑，33 个文件的冻结哈希（≤ 2026-06-30）全部一致 |
| 追赶式补数 | SPY/XLK/BIL/DGS10 各删 10 行后重跑，补回的文件和原文件 SHA256 完全一致 |
| 历史被改 | 人为把 QQQ 2010-06-01 收盘改 +1% 后重跑：告警、写入 revisions、已存行未被覆盖 |
| 交叉核对 V1 warehouse | 12 只重叠 ETF、约 690 天（2023-08 → 2026-06），非除息日日收益差 >0.1% 的天数：10 只为 0，IEF/TLT 各 1 天 |
| 交叉核对 OpenD | 26 只全部比对（2000 年起，未复权收盘价）。近 3 年 0 天不一致；更早有零星差异（中位约 0.2%，集中在 2007–08，XLB/XLF 各约 100 天），yfinance 与 warehouse 一致，判断为 OpenD 早期数据口径问题，记为警告 |
| 单测 | `pytest v3/tests`：8 passed |
| 没有做的 | 没有在任何数据上计算策略收益 |

已知事项：
- yfinance 把 XLF 2016 年分拆 XLRE 记为拆股（比例约 1.231），XLK 2025-12-05 有一次拆股；核对 OpenD 时已按拆股还原。总收益计算（第 2 步）需要正确处理这类事件。
- OpenD 交叉核对每次消耗约 26 个历史 K 线额度（30 天 100 个），所以只在需要时加 `--opend`。
- 数据约 10 MB。每周例行运行：`.venv/Scripts/python.exe v3/data/fetch.py`，然后 `.venv/Scripts/python.exe v3/data/check.py --warehouse`。

## 步骤 2：evaluator + 成本模型 + 单测 + 门槛可达性表 + lock — 未开始

## 待用户决定

- （无）
