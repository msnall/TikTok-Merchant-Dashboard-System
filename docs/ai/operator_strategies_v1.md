# Operator Strategies v1

策略是可追溯的运营经验知识，不是 Rule，也不是已执行动作。策略只能提供候选动作，不能覆盖 Rule Engine 的 `decision`、State Machine 的 `state`、目标 ROI 或历史 Delta。第一版策略来源均为 `operator_experience`。

每条策略固定包含：`strategy_id`、`title`、`source_type`、`conditions`、`candidate_actions`、`reasoning`、`evidence_required`、`uncertainty`、`not_apply_conditions`。

## S001 空烧计划关闭重建

```yaml
strategy_id: S001
title: 空烧计划关闭重建
source_type: operator_experience
conditions: [spend > 3 USD, orders == 0]
candidate_actions: [候选：关停并重建计划，保留当前ROI策略供人工确认]
reasoning: 消耗超过当前业务空烧阈值且没有订单
evidence_required: [spend, orders, currency]
uncertainty: [需确认报表时间和币种]
not_apply_conditions: [currency != USD, orders unknown, spend unknown]
```

## S002 有订单但订单少

```yaml
strategy_id: S002
title: 有订单但订单少
source_type: operator_experience
conditions: [orders >= 1, orders <= 9]
candidate_actions: [候选：继续观察订单和ROI，检查转化链路]
reasoning: 个位数订单样本不足以单独支持激进调整
evidence_required: [orders, spend, current_roi, target_roi]
uncertainty: [个位数订单的业务阈值属于经验口径]
not_apply_conditions: [orders unknown, orders == 0]
```

## S003 ROI低但视频正常

```yaml
strategy_id: S003
title: ROI低但视频正常
source_type: operator_experience
conditions: [roi_status == LOW, video_quality == NORMAL]
candidate_actions: [候选：检查商品页和CVR，人工确认后测试相邻ROI档位]
reasoning: 视频指标正常时不能直接把ROI问题归因于素材
evidence_required: [current_roi, target_roi, CTR, CVR, completion_rate]
uncertainty: [缺少人群、价格和商品页数据]
not_apply_conditions: [target ROI missing, video metrics incomplete]
```

## S004 视频差导致ROI低

```yaml
strategy_id: S004
title: 视频差导致ROI低
source_type: operator_experience
conditions: [roi_status == LOW, video_quality == LOW]
candidate_actions: [候选：检查Hook和素材结构，测试新素材]
reasoning: 视频质量指标未达到当前业务正常标准，同时ROI低
evidence_required: [CTR, CVR, completion_rate, current_roi, target_roi]
uncertainty: [视频指标差不等于唯一原因]
not_apply_conditions: [video metrics missing, ROI status unknown]
```

## S005 新品快速起量加预算

```yaml
strategy_id: S005
title: 新品快速起量加预算
source_type: operator_experience
conditions: [is_new_product == true, spend_growth_confirmed == true, orders_normal_confirmed == true, video_quality == NORMAL]
candidate_actions: [候选：小步增加预算进行探索，需人工确认]
reasoning: 新品消耗、订单和视频表现同时出现扩量信号
evidence_required: [spend delta, orders, video metrics, fulfillment data]
uncertainty: [案例预算不是通用固定增幅，履约和退货未确认]
not_apply_conditions: [orders abnormal, video quality not normal, budget action not approved]
```

## S006 ROI提升策略

```yaml
strategy_id: S006
title: ROI提升策略
source_type: operator_experience
conditions: [roi_status == LOW, evidence supports conversion optimization]
candidate_actions: [候选：检查CVR和商品页，测试相邻ROI档位，不自动修改目标ROI]
reasoning: ROI低时优先补充转化证据并进行受控候选测试
evidence_required: [current_roi, target_roi, CVR, orders, landing_page_conversion]
uncertainty: [没有利润和商品页数据不能确认最佳档位]
not_apply_conditions: [target ROI missing, current ROI missing]
```

## S007 多ROI档位测试

```yaml
strategy_id: S007
title: 多ROI档位测试
source_type: operator_experience
conditions: [link_type in [A, B], target_roi present, human test approval]
candidate_actions: [候选：设计多个ROI档位进行对照测试，需人工确认]
reasoning: A/B策略标签和目标ROI已明确时可以提出测试设计
evidence_required: [link_type, target_roi, policy, historical_delta]
uncertainty: [不推导保本或利润公式，不预设具体档位数值]
not_apply_conditions: [target ROI missing, no human approval]
```

策略引用必须保留 `strategy_id`、条件和来源；策略命中不代表广告账户已经关闭、改预算或改 ROI。
