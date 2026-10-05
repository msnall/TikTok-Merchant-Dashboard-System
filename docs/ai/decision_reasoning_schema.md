# Decision Reasoning Result Schema v1

本契约定义 Rule Engine 和 State Machine 之后的运营推理结果。它只解释已有事实、经验模式和候选策略，不改变 `decision`、`state`、`rules_used`、Delta 或 `target_roi`。本阶段仅定义数据契约，不实现业务代码。

## Top-level object

```json
{
  "campaign_stage": "UNKNOWN|TESTING|LEARNING|SCALING|SATURATING|REBUILD_CANDIDATE",
  "fact_summary": {},
  "metric_diagnosis": {},
  "possible_causes": [],
  "candidate_strategies": [],
  "observation_plan": {},
  "references": {"pattern_refs": [], "knowledge_refs": []}
}
```

### campaign_stage

阶段只能由已有 normalized facts、历史 Delta、可靠时间序列和确定性 decision 推导。LLM 不得填写或覆盖。`UNKNOWN` 用于事实不足；`TESTING`、`LEARNING`、`SCALING`、`SATURATING` 和 `REBUILD_CANDIDATE` 是解释性阶段，不是广告账户状态。

### fact_summary

只保存系统确认事实：`campaign_id`、spend、orders、current_roi、target_roi、CTR、CVR、official_completion_rate、link_type、roi_policy、previous_decision、historical_delta 和 report/source metadata。不得写入原因、猜测、未经证实的商品页或人群结论。

### metric_diagnosis

固定字段：`video_quality`、`roi_status`、`ctr_status`、`cvr_status`、`spend_status`、`historical_status`。每个值只能是 `NORMAL`、`LOW`、`HIGH`、`MISSING` 或 `UNKNOWN`，并可附 `evidence` 和 `uncertainties`。缺失数据使用 `MISSING`，无法按当前口径判断使用 `UNKNOWN`。

### possible_causes

```json
{
  "cause": "可能存在商品页转化链路效率不足",
  "supporting_evidence": ["current_roi < target_roi"],
  "missing_evidence": ["商品页转化率"],
  "confidence": "LOW|MEDIUM|HIGH"
}
```

每个原因必须是可能性表达，不能写成确定结论；证据必须来自输入、Rule Engine、历史 Snapshot 或知识引用。

### candidate_strategies

```json
{"strategy":"检查商品页转化","reason":"视频指标未显示明显异常","risk":"当前没有商品页转化数据"}
```

候选策略不是执行动作，不代表广告账户已改变。任何实际执行只能由 Human Action 记录。

### observation_plan

```json
{
  "metrics_to_compare": ["spend", "orders", "ROI", "CTR", "CVR", "completion_rate"],
  "time_window": null,
  "trigger_conditions": [],
  "uncertainties": ["没有可靠实时消耗曲线"]
}
```

`time_window` 只能来自已有业务配置；没有配置时必须为 `null`，不得自行创建“观察 2 小时”等周期。

### references

`pattern_refs` 只允许已存在的 Pattern ID（P001-P010）；`knowledge_refs` 只允许检索实际返回的 Rule/knowledge chunk 引用，未命中时明确记录 `NO_KNOWLEDGE_EVIDENCE`，不得伪造引用。

## Authority boundary

```text
Rule Engine → decision / rules_used / facts
State Machine → state / transitions
Delta calculator → historical_delta
Reasoning Layer → causes / candidate strategies / observation plan
LLM → human-readable explanation only
Human → actual action
```

LLM 输出如果包含新的 decision、Rule ID、Pattern ID、数字事实或“已经关闭广告”等执行声明，必须被拒绝或降级为候选建议。
