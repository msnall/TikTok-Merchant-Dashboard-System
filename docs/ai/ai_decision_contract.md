# AI 决策契约 V0.1

Phase 0 的“AI”仅为确定性规则，不调用大模型、RAG 或外部广告账户。相同输入和配置必须产生相同结构化输出。运营建议由人工确认。

```json
{
  "campaign_id": "synthetic-C001",
  "facts": [{"field": "current_roi", "value": 0.71, "source_type": "synthetic_demo"}],
  "rules_used": ["R001", "R003"],
  "inference": ["VIDEO_NORMAL", "BELOW_TARGET"],
  "recommendations": ["CLOSE_REBUILD_LOWER_ROI"],
  "uncertainties": ["缺少可靠时序，无法判断消耗是否趋平"],
  "requires_human_confirmation": true
}
```

- `facts` 是有来源、时段和单位的事实，不混入推断。
- `rules_used` 是证据条件满足的唯一 Rule ID，运营经验不称为官方规则。
- `inference` 是确定规则形成的状态；证据不足输出 UNKNOWN/INSUFFICIENT_DATA。
- `recommendations` 是建议，**不是**已执行关停、重建、改 ROI 或改预算。
- `uncertainties` 记录缺失来源、关联、指标、时段和待确认阈值。

`synthetic_demo` 分析仅供评测，真实历史查询必须排除。每次分析和当时使用的 campaign/video/source 快照都须另存，不覆盖旧记录。`roi_near_threshold` 默认 `requires_confirmation`，不得私设 ±5% 或 ±10%。策略档位变更不生成新的目标 ROI 数字；只能读取已有人工配置。
