# 结构化实验日志格式

本仓库把策略修改视为实验，而不是一次性代码调整。

主日志文件：

- `docs/experiment_log.jsonl`

记录原则：

1. 一次实验写一行 JSON
2. 成功和失败都要记录
3. 若实验被拒绝或回滚，仍然必须记录
4. 参数、窗口、指标必须可复现
5. 禁止只写“试过了，不行”这类不可验证结论

推荐流程：

1. 先查 `docs/experiment_log.jsonl` 是否已有相似尝试
2. 明确假设、参数和窗口
3. 跑基线
4. 做单一因果改动
5. 跑改后结果
6. 将实验结果追加写入 `docs/experiment_log.jsonl`
7. 如有必要，再把高层总结写入 `docs/iteration_analysis.md`

## JSONL 字段规范

每一行必须是一个完整 JSON 对象，推荐包含以下字段：

```json
{
  "experiment_id": "exp-20260417-001",
  "timestamp": "2026-04-17T12:30:00-07:00",
  "status": "rejected",
  "hypothesis": "放松某个过滤器后，可能提高 expected_value_score 且不显著恶化回撤",
  "change_summary": "将某阈值从 A 调整到 B",
  "change_type": "threshold",
  "component": "quant/signal_engine.py",
  "parameters": {
    "threshold_name": {
      "old": 0.9,
      "new": 0.88
    }
  },
  "date_range": {
    "start": "2025-10-20",
    "end": "2026-04-16"
  },
  "secondary_windows": [
    {
      "start": "2025-04-20",
      "end": "2025-10-19"
    }
  ],
  "market_regime_summary": {
    "primary": "NEUTRAL-heavy",
    "secondary": "BULL-heavy"
  },
  "before_metrics": {
    "expected_value_score": 0.403,
    "sharpe": 3.12,
    "sharpe_daily": 2.0,
    "total_return_pct": 0.2015,
    "max_drawdown_pct": 0.0459,
    "win_rate": 0.6207,
    "trade_count": 29,
    "survival_rate": 0.9804
  },
  "after_metrics": {
    "expected_value_score": 0.361,
    "sharpe": 2.84,
    "sharpe_daily": 1.8,
    "total_return_pct": 0.2006,
    "max_drawdown_pct": 0.061,
    "win_rate": 0.58,
    "trade_count": 33,
    "survival_rate": 0.991
  },
  "delta_metrics": {
    "expected_value_score": -0.042,
    "sharpe": -0.28,
    "sharpe_daily": -0.2,
    "total_return_pct": -0.0009,
    "max_drawdown_pct": 0.0151,
    "win_rate": -0.0407,
    "trade_count": 4,
    "survival_rate": 0.0106
  },
  "llm_metrics": {
    "used_llm": true,
    "llm_change_scope": "prompt_boundary",
    "llm_attribution_metric": "veto_precision_proxy",
    "before_value": 0.55,
    "after_value": 0.59
  },
  "decision": "rejected",
  "rejection_reason": "主目标退化，且回撤恶化，未通过 Gate 4",
  "next_retry_requires": [
    "需要新的回测窗口证据",
    "需要先修复生产/回测一致性差异"
  ],
  "related_files": [
    "quant/signal_engine.py",
    "data/backtest_results_20260417.json"
  ],
  "notes": "失败尝试保留，禁止简单重复"
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `experiment_id` | 是 | 唯一实验 ID，建议 `exp-YYYYMMDD-序号` |
| `timestamp` | 是 | 记录时间，ISO 8601 |
| `status` | 是 | `accepted` / `rejected` / `rolled_back` / `observed_only` |
| `hypothesis` | 是 | 本次实验要验证的因果假设 |
| `change_summary` | 是 | 一句话描述改动 |
| `change_type` | 是 | 如 `threshold` / `filter` / `llm_prompt` / `data_fix` / `parity_fix` |
| `component` | 是 | 主要修改模块或文件 |
| `parameters` | 是 | 改动参数，新旧值都要保留 |
| `date_range` | 是 | 主实验窗口 |
| `secondary_windows` | 否 | 非重叠辅助窗口列表 |
| `market_regime_summary` | 推荐 | 窗口内市场环境摘要 |
| `before_metrics` | 是 | 改动前指标 |
| `after_metrics` | 是 | 改动后指标 |
| `delta_metrics` | 是 | 指标变化值 |
| `llm_metrics` | 推荐 | 若涉及 LLM，则记录单独归因指标 |
| `decision` | 是 | 最终结论 |
| `rejection_reason` | 条件必填 | 被拒绝或回滚时必须写 |
| `next_retry_requires` | 推荐 | 未来想重试，需要什么新证据 |
| `related_files` | 推荐 | 相关文件、结果文件、日志文件 |
| `notes` | 否 | 补充说明 |

## 最低填写要求

即使是一次失败的小实验，也至少要填：

- `experiment_id`
- `timestamp`
- `hypothesis`
- `change_type`
- `parameters`
- `date_range`
- `before_metrics`
- `after_metrics`
- `delta_metrics`
- `decision`

## 什么时候还要写进 Alpha 文档

`docs/experiment_log.jsonl` 负责记录“这次具体怎么试、结果怎样”。

但如果一次实验带来的主要价值是下面这类内容，就不应只停留在 JSONL，还应同步写进
`docs/alpha-optimization-playbook.md` 或当日研究文档：

- 证伪了一整类重复出现的思路
- 改变了某个子策略的默认优化方向
- 改变了未来 2-3 轮实验的优先级排序

推荐补充格式：

- `mechanism_insight`: 这次实验告诉我们 alpha 更可能来自哪里 / 不来自哪里
- `anti_repeat_rule`: 以后什么条件下禁止简单重复这类尝试
- `priority_update`: 这次实验后，下一轮默认该优先测什么

## 示例使用

追加一条实验记录时，确保每条 JSON 独占一行。不要写 Markdown，不要写注释，不要跨多行。

适合机器读取的后续操作：

- 统计哪些 `change_type` 最容易失败
- 查找某个参数以前试过哪些值
- 比较同类实验在不同市场状态下的结果
- 过滤出所有 `decision = rejected` 的失败样本
