# Alpha 搜索三命令工作流

目标不是删掉安全检查，而是删掉人必须逐条敲的重复命令。操作员只记三个动作：

```text
qualify  ->  start  ->  [实现并运行实验]  ->  finish
```

入口：

```powershell
.\.venv\Scripts\python.exe -B scripts\alpha_workflow.py --help
```

## 大白话版

### 1. qualify：这个想法够不够资格做实验？

输入 Investment Team 的研究卡，以及在研究开始前已经冻结的 scope、证据面、历史快照和实验 proposal。

它内部一次完成：

1. 规范化 Investment Team 研究卡；
2. 只把 `decision.disposition=test` 的卡投影成候选；
3. 冻结完整候选池并执行 D0-D3；
4. 有唯一胜出候选时生成 hash-bound promotion；
5. 最后发布 `qualification.json`。

它不会读实验 outcome，不会交易，也不会申请实验 ID。`park`、`reject`、D0-D3 没选出候选，都是正常的零 ID 结果。

```powershell
.\.venv\Scripts\python.exe -B scripts\alpha_workflow.py qualify `
  --card data\alpha_search\cards\idea_a.json `
  --scope-manifest data\alpha_search\scope.json `
  --surfaces data\alpha_search\surfaces.json `
  --prior-fingerprints data\alpha_search\prior_fingerprints.json `
  --proposal data\alpha_search\proposal.json `
  --output-dir data\alpha_search\qualified\idea_a
```

`--output-dir` 必须是新目录。中途失败可以留下诊断文件，但没有最终 `qualification.json` 就没有准入权。

### 2. start：正式占一个 ID 并开工

`start` 重新核对 qualification 里每个文件的 SHA-256，读取 promotion 中的精确 proposal，再执行当前动态守卫：novelty、saturation、reopen、observed-only streak、routine materialization、recipe lane 和 in-flight duplicate。之后才 reserve + claim。

```powershell
.\.venv\Scripts\python.exe -B scripts\alpha_workflow.py start `
  --qualification data\alpha_search\qualified\idea_a\qualification.json `
  --execution-spec data\alpha_search\qualified\idea_a\execution.json `
  --owner codex
```

它不提供 `--force`、novelty override 或 saturation override。正常路径保持三命令；真正需要治理例外时，回到底层命令显式说明证据轴，不把例外伪装成日常按钮。

所有 `start` 会经过一个很短的串行准入区，避免两个并发想法同时穿过 in-flight 检查。完全相同的输入重试会用 reservation intent 找回同一个开放 ID，并让 in-flight guard 忽略这个 ID 自身；同一个 promotion 一旦终态就永久消费。reserve 成功但 claim 失败时，错误输出一定包含已占用的 ID；不得换措辞再烧一票。

`execution.json` 的最小格式：

```json
{
  "schema_version": 1,
  "record_type": "alpha_workflow_execution_spec",
  "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json",
  "allowed_write_scope": [
    "quant/experiments/{experiment_id}_my_runner.py",
    "data/experiments/{experiment_id}/"
  ],
  "must_not_touch": [
    "quant/run.py",
    "data/open_positions.json"
  ],
  "locked_variables": [
    "entry_policy"
  ],
  "evaluation_windows": [],
  "acceptance_rule": "Use the predeclared falsifier and repository Gate contract.",
  "prior_trial_count": 0,
  "nearby_prior_experiments": [],
  "multiple_testing_risk_bucket": "minimal",
  "new_evidence_type": "new_data_source"
}
```

`causal_components` 直接从 promotion 以 JSON list 传入，不再经过逗号分割，所以组件正文中的逗号不会把一个组件拆成多个。

真正的新数据源如果还没被 fingerprint 分类器识别，`execution.json` 必须声明 `new_evidence_type=new_data_source`，并把 `scripts/experiment_fingerprint.py` 放进同票 `allowed_write_scope`；这样先占 ID、再在同一实验补分类覆盖，不会把新源永久挡在门外。

### 3. finish：用已有结果收尾并审计

`finish` 不跑策略，只消费已存在的 before/after：

```powershell
.\.venv\Scripts\python.exe -B scripts\alpha_workflow.py finish `
  --experiment-id exp-YYYYMMDD-NNN `
  --before data\experiments\exp-YYYYMMDD-NNN\before_measurement.json `
  --after data\experiments\exp-YYYYMMDD-NNN\after_measurement.json `
  --reflection-file data\experiments\exp-YYYYMMDD-NNN\reflection.json
```

`reflection.json` 把原先散落在命令行里的收尾说明合成一个文件：

```json
{
  "change_summary": "本轮到底改了什么",
  "why_result_happened": "为什么出现这个结果",
  "realized_failure_mode": "实际失败模式，或明确说明未出现失败",
  "forbidden_near_neighbor_retry": "下一轮禁止换皮重试什么",
  "new_evidence_required": "什么新证据出现后才值得重开"
}
```

它自动判 Gate；研究级 promotion 的正结果会自动封顶为 `observed_only`，canonical 结果才可能成为 `accepted`。人不能手工强制接受；如果数字虽然通过但 PIT、执行或归因有问题，可以加 `--reject` 保守拒绝。

收尾时会先把 before/after 内容哈希、反思和判定绑定进 ticket，再写终态和 durable log，最后刷新 frozen families、alpha memory 并运行 `experiment.py audit --lean-strict`。

完全相同的命令可安全重试：before/after 任一字节或反思发生变化都会拒绝；终态已写但 log 缺失时会从 ticket 中的绑定副本恢复 log，不会再次 close。底层登记器也拒绝覆写任何终态结果，并禁止把机器判定失败的 alpha 通过 `accepted` override 强行抬成成功。

## 从十多个显式动作删掉了什么

| 旧的人工动作 | 现在在哪里 | 为什么可从人工界面删除 |
|---|---|---|
| card `normalise` | `qualify` 内部 | 投影前必须做，但不必单独敲 |
| card `validate` | 删除独立调用 | `project` 会再次完整验证 |
| card `project` | `qualify` 内部 | 只处理 `test` 卡 |
| `validate-candidate` | 删除独立调用 | `build-panel` 会重新验证每个 candidate |
| 单独 `preflight` | 删除独立调用 | `build-panel` 内部执行 D0-D3 |
| `build-panel` | `qualify` 内部 | 仍然保留完整候选池和预算检查 |
| `verify-panel` | 删除独立调用 | `build-promotion` 会严格重验 panel/scope/surface/history |
| `build-promotion` | `qualify` 内部 | 仍产出不可变 promotion |
| `experiment.py new` | `start` 内部 | 动态 guards 后原子 reserve |
| `experiment.py claim` | `start` 内部 | 仍生成 claim receipt/CAS 快照 |
| `experiment.py close` | `finish` 内部 | 保留唯一判定/登记路径 |
| `experiment.py audit --lean-strict` | `finish` 内部 | close 后自动执行 |

没有删掉的只有真正的研究工作：写 runner、跑 Gate、检查执行包络、解释结果。它发生在 `start` 和 `finish` 之间，不能靠改命令名字省略。

`build-history`、`build-scope` 和 surface registry 更新属于准入基础设施，应由定时任务在 Investment Team 开始研究前生成并冻结，不应由操作员在看完候选后临时补造。`report`、`failure-map`、`rebuild-log` 是诊断/维护命令，不属于每轮主路径。

## Investment Team 的权限边界

Investment Team 提高的是“问题定义质量”：商业机制、财务证据、行业结构和反方风险被整理成同一张研究卡。它不是第五个投票模型，也没有交易权限。

当前适配器只允许研究卡产出 `evidence_grade=lead`。因此它可以进入 D0-D3 和 research replay，但不能凭四个角色都赞成就升级成 canonical alpha、paper 或 live。证据成熟度、PIT、settled rows、Gate 和生产一致性仍由机器合同决定。

## 暂不隐藏的例外

`finish` 只适用于现有 `judge_experiment.py` 能重算的 before/after。仓库目前还没有统一的 private-replay scout closeout schema；遇到自定义 scout 指标时，先补统一 evaluator，再把它接进 `finish`，不要把自由文本 verdict 自动包装成“已通过”。
