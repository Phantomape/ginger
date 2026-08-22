# Investment Team 接入：一张卡片，三个出口

这次接入不改策略、不碰订单，也不在 `investment-team` 里做买卖决定。它只在现有 D0-D3 前增加一张可机器校验的投研卡片：

```text
系统候选
  → investment-team 四角色研究
  → Team Lead 填投研卡片
  → test   → 转成现有 HypothesisCandidate → D0-D3 → 实验/Gate
    park   → 等缺失证据，不进入 D0-D3
    reject → 结束，不进入 D0-D3
```

## 卡片只回答四件事

1. 四个角色是否都交付：商业、财务、行业、风险。
2. 每项关键结论来自哪里，信息在 `data_cutoff` 时是否已知。
3. 角色之间是否还有未解决冲突。
4. Team Lead 的出口是 `test`、`park` 还是 `reject`。

`researchability.grade` 的 A/B/C 只表示 AI 获取和核验信息的难度，不表示投资信心。无论 A 还是 B，投研卡片最多只能生成 `evidence_grade=lead`；后续成熟度仍由现有 D0-D3 决定。C 级不能进入 `test`。

## `test` 的最小门槛

- 四个角色全部为 `complete`，每个角色至少有一条带 `source` 与 `known_at` 的证据；
- 财务角色至少使用两个不同 `source_group`，且至少一个是 primary source；
- 所有 `known_at <= data_cutoff`；
- `conflicts` 为空；
- 内嵌候选通过现有 `HypothesisCandidate` 合同，交易、订单和 live 标志保持 false；
- `next_machine_action` 固定为 `run_d0_d3`。

任一条件不满足就 fail closed；可以改成 `park` 留下缺口，但不会生成机器候选。

## 使用命令

研究团队先产出 JSON，`card_id` 和候选的 `candidate_id` 可先填 `pending`：

```powershell
# 1. 计算语义 ID，并输出规范化卡片
.\.venv\Scripts\python.exe -B scripts\investment_team_research_card.py normalise input.json --output card.json

# 2. 核验卡片没有被修改
.\.venv\Scripts\python.exe -B scripts\investment_team_research_card.py validate card.json

# 3. 只有 test 卡片才能生成现有 D0-D3 输入
.\.venv\Scripts\python.exe -B scripts\investment_team_research_card.py project card.json --output candidate.json
```

字段的可运行示例和失败边界见 `quant/test_investment_team_research_card.py`。接入点是独立 CLI；`quant/run.py`、回测器、策略 helper 和 Gate 阈值均不导入它。
