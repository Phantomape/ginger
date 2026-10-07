# V1 五组 paper 策略退休

实验：`exp-20260911-001` / `expuid-5bba748432754604`。性质：用户授权的生产维护，`measurement_repair`；不构成收益或 alpha 证据。

用户在[V1 审查](../../.codex/worktrees/edge-v2/docs/v1_paper_sleeve_review_20260910.md)后明确授权去掉五组。实施范围如下：

| 组 | 退休入口 |
|---|---|
| AI optical | AI optical paper sleeve 与独立候选扫描 |
| alpha-score 及派生共识 | alpha-score market-regime paper、accepted-source consensus、free-data cross-source consensus |
| source-priority allocator | allocator paper 与手工 pilot 推荐入口 |
| Space / satellite 细倍率 | Space 新观察计划、state-surface paper、event bundle 的 state-surface addon |
| 行业落后股修复 | industry-relative-laggard-repair paper |

合计七个注册 sleeve 从日报执行映射移除（41 → 34）。七者默认停止候选生成、新 pending 和纸上开仓；原 pending 移入既有 skip 记录，保留身份、金额、原状态与取消日期；已开仓按既有价格、持有期和成本规则继续结算，并防止同日重复推进。

退休 payload 保留在结构化输出中，供历史追溯与结算使用；日报活跃区块、归因激活候选和 allocator 手工推荐会排除它们。过滤只针对明确退休标记，其他默认关闭的观察模块不会被一并移除。Event bundle 的其他来源保持运行。

Space 只结算 `2026-09-11T06:06:56Z` claim 前已登记的 `(event_id, ticker)`，不再读取 seed 创建新事件，也不引入当前对照池。已成熟的 1/5/10/20 日结果原样保留，继续补齐未成熟部分；全部成熟后不再拉价或追加该事件。

## 验证与生效边界

296 项相关测试全部通过；`experiment.py audit --lean-strict` 通过（不回填其他历史 ticket 的元数据缺口）。以合成 pending、到期 open、未到期 open、历史 passed gate 和事件时序做行为回归；先复现退休边界失效，再修复。精确命令和最终结果见 [after.json](../../data/experiments/exp-20260911-001/after.json) 与 [pytest.txt](../../data/experiments/exp-20260911-001/pytest.txt)。

本次只落地代码和相关记录，未手工执行完整生产日报、未改写生产账本。新入口关闭立即成为代码默认；旧 pending 的取消、存量结算及展示更新在下一次日常运行生效。原始历史文件保留。核心 alpha-score 算法和真实交易权限没有改动。

## 判断与后续

原判断是简单关闭 paper 标志不足以退休策略；合成检查确认旧 pending、旧 passed gate 和直接读取状态的推荐入口确实会绕过单一开关。修复覆盖这些边界，接受依据是行为正确，不是收益改善。没有运行回测、查看新增评价窗口或支付外部数据费用。

不得根据同一批已消费的 V1 结果重新调参或自动恢复这些策略。重开需用户改变退休决定，并以独立新增 PIT/forward 证据按现有实验协议另行登记。预算为一个维护 ticket、至多三轮有界实现检查、零收益实验及零外部费用；收尾后不继续搜索相邻策略。
