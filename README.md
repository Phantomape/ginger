# Ginger

Ginger 目前是一套交易辅助和研究工具，尚未证明能稳定赚钱。
现阶段只保留两条工作线：每天出报告；一次完成一个实验。

## 每天怎么用

在 root 仓库运行现有入口：

```powershell
cd D:\Github\ginger
.\.venv\Scripts\python.exe -B quant\run.py
```

Daily Report 定时任务保留，正常出报告时无需手动再跑。
持仓输入在 `operator_inputs/open_positions.json`；账户、成交和成本仍由现有流程核对。

运行后主要看：

- `data/report_YYYYMMDD.txt`：当天报告，分别查看 core 与 paper sleeve 的信号。
- `data/quant_signals_YYYYMMDD.json`：需要追查时查看完整信号和归属信息。
- `data/daily/llm/advice/investment_advice_YYYYMMDD.json`：生成成功时的 AI 建议。

报告、建议和研究结果不等于已成交或已赚到的钱；paper 信号不代表真钱授权。
报告的 broker PnL 只有在订单能归属到策略时，才能用来评价该策略。
AI 建议未生成时，提示词在 `data/daily/llm/prompts/`；手动导入步骤见旧版使用说明。

## 研究怎么做

围绕一个问题，固定数据和测法，跑完先复盘，再决定修复、补数据、验证新版本或停止。
一个结论只需说清：**测什么、多少样本、扣成本后比对照怎样、支持还是不支持、重测需要什么新证据。**
程序错了可以自己修，样本不足可以按预定计划补；旧结果保留，修复后重新验证。
有依据的新想法可以另开实验，用没参与修改的新数据检验；不能反复改同一份考卷直到及格。

- 自动化启停以应用设置为准，日常运行和研究任务分别控制。
- 自主决定下一步，但先写清它能排除什么疑点及有限研究预算；不按固定重试次数决定是否值得继续。
- 没有新依据或需要等待数据时停止；不追赶实验数量、扩建平台或批量修旧问题。
- 新研究只在 `D:/Github/ginger/.codex/worktrees/edge-v2` 进行，root 继续日常运行。
- 原始数据、实验记录和已有观察流程保留；这次整理没有更改交易规则或增加真钱权限。

执行者只需从 [简化运行协议](docs/quant_agent_protocol_v2.md) 开始；按当前问题读取必要合同。
协议已吸收 Asness、Carver、Chan 和 Man AHL 的公开研究方法，原文与适用边界见其中的来源表。
实验结论以各自 `experiments/logs/<id>.json` 和绑定结果为准，摘要不是第二套账。

可选使用 [SoL-Pi 研究助手](.codex/worktrees/edge-v2/tools/sol-pi/README.md)：入口固定进入研究工作区，在 Pi 中按现有协议辅助读代码、核对证据和验证修复。

## 需要细节时

[旧版完整使用说明](docs/archive/README_before_simplification_20260910.md) 保留安装、手动导入、运行开关、
盘中和回测说明。它是历史参考；当前代码和简化运行协议决定实际行为。
