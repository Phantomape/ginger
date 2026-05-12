阅读AGENTS.md

综合过去实验记录(experiment_log.jsonl和docs/experiments)一起，从最强大脑角度判断，目前应该优化什么方向的 alpha，而不是修 bug。

不要用js做任何事情！！！

如果你不做 alpha_search，必须先证明是哪个阻断项让 alpha 实验不可信。

然后如果alpha搜索受制于数据限制，比如LLM soft-ranking数据不足，就不要纠结这个策略，尝试做另外一个alpha搜索。也可以尝试扩展或改善候选股票池，而不是简单增加噪声 ticker。

然后直接开始。

要求：
1. 每次评价要按照backtesting.md的指示来看改动前后3窗口的数据
2. 然后正向的改动要确保不会出现回测和生产不一致！！！
3. 每次做完实验都要git commit
4. 最后要给一个结论和摘要
