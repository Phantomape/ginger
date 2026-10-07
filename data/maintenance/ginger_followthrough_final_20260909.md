# 本轮最终交付与剩余问题

已经落地两项工程修复：每日决策与券商订单的明确归属，以及 Edge 实验终态的一致解析。主仓库 145 项相关测试、真实券商只读核对、原始记录保留和重放检查通过；主仓库严格流程审计通过。Edge 状态修复的 40 项专项测试及独立复查通过。

详细实现和固定观察队列见 `data/maintenance/ginger_followthrough_20260909.md`。主仓库实验 `exp-20260909-002 / expuid-1818c9a28a3342b6` 与 Edge 实验 `exp-20260909-001 / expuid-c9d8f5fd490044b6` 均为工程验收，不是盈利验收。

## 本轮研究尝试的错误及处理

我派出的研究任务错误地重用了已经被看过结果、明确不能原样重试的 OnClickMedia 样本，并一度修改来源分类以通过准入。root 在收益读取及 runner 执行前发现并叫停，恢复了分类代码。

该尝试 `exp-20260909-003 / expuid-9b8de362b3844bb6` 已终结为 `rejected / invalid_contaminated`。没有读取价格收益，没有生成 runner、attempt lock、测量行或订单。它不算有效 alpha 实验，不支持任何正负经济结论，实际历史与校准消费者均已排除。原始错误材料保留。

Edge 的总体严格审计仍有一个 `alpha_promotion_integrity / invalid_historical_snapshot` 红项。这是被暴露的坏准入记录，不是正在运行的实验或策略资格；没有修改审计规则来消红。不能因此宣称整个仓库全部审计通过。

还有两个未跟踪研究文件无法精确撤回本轮修改：

- `.codex/worktrees/edge-v2/scripts/prepare_v2_onclickmedia_options_vega_concordance_h5_scout.py`
- `.codex/worktrees/edge-v2/quant/test_prepare_v2_onclickmedia_options_vega_concordance_h5_scout.py`

执行任务没有保留其修改前的完整字节；Git 和已检查的旧冻结包也没有这两个文件的原版。当前内容已另存为该实验的 `live_untracked_*` 审计副本，未猜测覆盖或删除。这个候选继续停用，不能使用这两个文件重建旧包后重新准入。

最终研究隔离证据：`.codex/worktrees/edge-v2/data/v2/hourly_runs/exp-20260909-003_onclickmedia_options_vega_concordance_h5_completed.json`。独立复查确认终态及消费端隔离通过；恢复检查只发现事后副本，未发现修改前的可信完整副本。

## 赚钱目标的真实进度

本轮新增有效 alpha 验证为 0，经济进展为 false。没有提交券商订单。历史 786 个逻辑订单仍不能冒充某个策略的收益；新机制要等今后带身份的完整买卖闭环才开始积累可归属净额。

新闻配对与预期修订两个既有冻结观察方向仍按原门槛采证。样本及历史身份核对未齐备，不调整成本、持有期或筛选条件来凑通过。工程修复已可用，盈利能力仍未证明。
