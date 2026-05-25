# Alpha Direction: Expectation Drift × Residual Leadership × PEAD Continuation

> 目标：把 Ginger 下一阶段 alpha 搜索从“更多规则 / 更多 surface”收敛到一个更高信息密度、更可 replay、更接近 institutional medium-term systematic research 的主线。

---

## 1. 一句话结论

当前最值得深挖的 alpha 方向是：

```text
Expectation Drift
+
Residual Leadership
+
Post-Earnings Drift Continuation
```

也就是：

```text
市场预期在持续上修，
股票相对市场 / 行业 / theme 持续领先，
且财报后仍然有机构再定价 / 资金继续流入。
```

不要优先继续挖：

```text
更多 breakout rule
更多 filter
更多 top-up scalar
更多 regime subclass
更多 latent state abstraction
```

而应该优先挖：

```text
哪些股票在预期变化后，
还能持续成为 residual leader。
```

---

## 2. 为什么是这个方向

### 2.1 它是真正的数据 edge，不只是 OHLCV remix

Ginger 目前很多 alpha 仍来自：

```text
price momentum
breakout
relative strength
cap-aware sizing
slot condition
```

这些有用，但很容易变成：

```text
同一套 OHLCV 信息的不同包装
```

真正提高 alpha 上限的方向，是更上游的信息：

```text
expectation change
```

价格告诉我们：

```text
市场已经怎么反应
```

预期变化告诉我们：

```text
市场为什么可能继续反应
```

这比单纯价格形态的信息密度更高。

---

### 2.2 它和 Ginger 的系统结构高度匹配

Ginger 不是高频系统，也不是 intraday stat-arb。

它最适合：

```text
EOD
medium-term
event-enhanced
cross-sectional
replayable
paper-first
```

而 expectation drift / PEAD continuation 正好符合这些约束：

- 非日内；
- 可 daily snapshot；
- 可 replay；
- 可做 attribution；
- 可做 cross-sectional ranking；
- 可和已有 earnings / SEC / event infra 结合；
- 合理持仓周期可以是 5-20 trading days。

这比 options flow、order book、tick alpha 更适合当前 Ginger。

---

### 2.3 Core stack 的 scalar / cap 微调已经进入边际收益递减

当前 core stack 已经叠加了很多小型 sizing / cap / top-up 规则。

继续挖：

```text
1.025x top-up
1.05x top-up
再加一个 slot rule
再加一个 sector exception
```

边际收益大概率越来越低。

因此，下一阶段更应该提升：

```text
每个 candidate 背后的信息密度
```

而不是继续调已有 candidate 的微小 sizing scalar。

---

### 2.4 它符合 Ginger 现有 playbook 的经验结论

Ginger 历史上更有效的方向通常是：

```text
固定 candidate set
+
更好的 sizing / ranking / capital routing
```

而不是：

```text
broad filters
broad overlays
broad reranking
```

所以 expectation drift 不应该一开始做成 hard filter。

正确方式是：

```text
用 expectation drift 提高 ranking / sizing confidence，
而不是直接过滤所有股票。
```

也就是说：

```text
entry 可以继续由现有系统产生，
但 ranking_score / replacement value / paper sleeve attribution
应该加入 expectation drift 和 residual leadership。
```

---

## 3. 核心 alpha 假设

### Main Hypothesis

```text
同时满足 positive expectation drift 和 residual leadership 的股票，
在未来 5-20 trading days 的 realized R / PnL，
显著优于普通 breakout / trend candidates。
```

### 更具体地说

一个高质量 candidate 应该满足：

```text
市场预期在上修
+
价格相对市场 / QQQ / sector / theme 在超额上涨
+
财报后或事件后没有快速失败
+
后续仍有资金继续 reposition
```

---

## 4. 要挖的三个子方向

## 4.1 Expectation Revision Velocity

核心问题：

```text
EPS / revenue estimate 在过去 7d、30d 是否持续上修？
```

优先特征：

```text
eps_revision_velocity_7d
eps_revision_velocity_30d
eps_revision_acceleration
revenue_revision_velocity_30d
analyst_count_delta_30d
```

最重要的不是：

```text
当前 EPS estimate 是多少
```

而是：

```text
estimate trajectory 在怎么变化
```

高价值状态：

```text
EPS estimate 上修
+
revenue estimate 上修
+
analyst count 增加
+
surprise history 正
```

这比单纯 breakout 信息密度更高。

---

## 4.2 Post-Earnings Drift Continuation

核心问题：

```text
财报后 T+2 到 T+15，
是否还有机构持续 reposition？
```

不要赌财报当天。

重点是：

```text
财报后市场已经知道信息，
但资金还没完全完成换仓。
```

候选条件：

```text
positive surprise
or positive guidance / non-negative guidance
or positive estimate revision
+
post-earnings gap 没有快速失败
+
T+2 / T+5 后仍然相对 QQQ / sector 强
```

这比普通 breakout 更适合作为中短线 / 中频 alpha。

---

## 4.3 Residual Leadership

核心问题：

```text
它是真的强，
还是只是 QQQ / AI / sector 都在涨？
```

要看：

```text
ret20_excess_spy
ret20_excess_qqq
ret20_excess_theme
ret20_excess_sector
```

例子：

```text
META 涨 8%
```

不一定有 alpha。

但如果：

```text
META 涨 8%
QQQ 涨 2%
mega-cap peers 涨 1%
communication services 涨 0%
```

那才可能是 residual leadership。

---

## 5. 第一个实验设计

# EXP_EXPECTATION_RESIDUAL_LEADERSHIP_001

## Hypothesis

```text
positive expectation drift + residual leadership 的股票，
未来 5-20 trading days 的 realized R / PnL，
显著优于普通 breakout / trend candidates。
```

## Mode

第一阶段必须是：

```text
read-only attribution
```

不得直接改变 live entry / sizing / ranking / orders。

---

## 6. Attribution 分桶

把 candidate / trade 分成四组：

```text
Bucket A:
positive expectation drift + residual leader

Bucket B:
positive expectation drift + no residual leadership

Bucket C:
residual leader + no expectation drift

Bucket D:
neither
```

---

## 7. 观察指标

每个 bucket 至少看：

```text
avg_R
win_rate
avg_pnl
total_pnl
tail_loss
worst_trade
top5_contribution
max_drawdown contribution
replacement value vs next core slot
```

理想结果：

```text
Bucket A 明显 outperform B/C/D，
且不是只靠少数 jackpot trade。
```

---

## 8. 第二个实验：PEAD Paper Sleeve

如果第一个 attribution 通过，再做：

```text
SHORT_HORIZON_PEAD_PAPER
```

仍然默认 paper-only。

## Candidate Window

```text
T+2 到 T+10 after earnings
```

## Requires

```text
positive surprise or positive revision
residual strength > threshold
market not risk_off
no immediate gap failure
```

## Hold

```text
5-15 trading days
```

## Exit

```text
time-based
or loss-based
```

核心不是：

```text
财报好就买
```

而是：

```text
财报后仍然有 residual follow-through 才进入 paper queue。
```

---

## 9. 第三个实验：Ranking Score Replacement Test

目标：验证新的 expectation / residual component 是否改善 ranking。

比较：

```text
old alpha_score
vs
old alpha_score + expectation_residual_component
```

观察：

```text
top_decile 是否更 monotonic
top_decile - bottom_quintile spread 是否扩大
component_predictive_value 是否更稳定
```

如果 monotonicity 没改善：

```text
直接拒绝。
```

不要强行解释。

---

## 10. 为什么不是优先挖 theme lifecycle / state transition

Theme lifecycle 很有价值，但更适合作为：

```text
risk / context / concentration modifier
```

而不是第一 alpha source。

当前优先级应该是：

```text
1. expectation drift
2. residual leadership
3. PEAD continuation
4. breadth alignment
5. theme lifecycle as risk context
```

而不是：

```text
1. theme state machine
2. regime subclass
3. latent vectors
```

原因：

```text
state machine / lifecycle abstraction 很容易漂亮但过拟合。
```

---

## 11. 过拟合防线

这个方向虽然合理，但必须避免：

```text
beautiful overfitting
```

硬约束：

1. 不允许直接 live；
2. 先做 read-only attribution；
3. 必须证明 bucket monotonicity；
4. 必须跨窗口；
5. 必须看 tail / concentration；
6. 必须证明不是 SPY / QQQ beta；
7. 必须可以 production daily snapshot；
8. 如果 evidence 不清楚，拒绝而不是复杂化。

---

## 12. 判断标准

一个 feature / component 可以继续推进，必须至少满足：

```text
top bucket > mid bucket > bottom bucket
```

或至少：

```text
top bucket 显著优于 bottom bucket
```

并且：

```text
不是靠 1-2 笔 jackpot trade 支撑。
```

如果：

```text
feature 看起来合理，
但 attribution 不稳定，
monotonicity 不存在，
或者只在单窗口有效，
```

则：

```text
拒绝。
```

---

## 13. 最终方向

Ginger 下一阶段最值得挖的 alpha 主线是：

```text
Expectation Drift × Residual Leadership
```

原因：

```text
它更接近真正的数据 edge，
更适合中频系统，
更容易 replay，
更容易 attribution，
也更不容易沦为 OHLCV rule remix。
```

这是当前最符合 Ginger 阶段的 alpha 搜索方向。
