# Decision Patterns v1

Pattern 是带来源和不确定性的运营经验推理，不是确定性 Rule，也不是 TikTok 官方阈值。第一版全部按 `operator_experience` 管理；没有官方平台定义时不得标记为 `official_platform_definition`。

## P001 视频正常但 ROI 低

```yaml
pattern_id: P001
title: 视频正常但ROI低
version: v1.0
source_type: operator_experience
conditions: [video_quality == NORMAL, roi_status == LOW]
possible_causes: [人群匹配效率不足, 商品页或价格转化效率不足, 目标ROI策略不适配]
candidate_strategies: [继续观察ROI与订单, 检查CVR和商品页, 在人工确认后测试不同目标ROI]
evidence_required: [historical_delta, orders, CVR, 商品页转化数据]
uncertainty: [当前视频正常不能证明商品页或人群没有问题]
priority: medium
```

为什么匹配：视频质量未显示异常而 ROI 未达目标。缺少商品页、人群和利润数据时只能列候选原因。

## P002 视频质量差导致转化不足

```yaml
pattern_id: P002
title: 视频质量差导致转化不足
version: v1.0
source_type: operator_experience
conditions: [video_quality == LOW]
possible_causes: [素材前几秒吸引力不足, 卖点表达与人群不匹配]
candidate_strategies: [检查Hook和素材结构, 测试新素材]
evidence_required: [CTR, CVR, official_completion_rate, video_id]
uncertainty: [低视频指标不等于唯一转化原因]
priority: high
```

## P003 CTR低但CVR正常

```yaml
pattern_id: P003
title: CTR低但CVR正常
version: v1.0
source_type: operator_experience
conditions: [ctr_status == LOW, cvr_status == NORMAL]
possible_causes: [素材首屏或Hook吸引力不足]
candidate_strategies: [测试首帧和Hook, 保留落地页并比较CTR]
evidence_required: [CTR history, impressions, video variants]
uncertainty: [曝光质量和受众规模未确认]
priority: medium
```

## P004 CTR正常但CVR低

```yaml
pattern_id: P004
title: CTR正常但CVR低
version: v1.0
source_type: operator_experience
conditions: [ctr_status == NORMAL, cvr_status == LOW]
possible_causes: [商品页承接或价格转化不足, 广告承诺与详情页不一致]
candidate_strategies: [检查商品页和价格, 对比点击到订单漏斗]
evidence_required: [clicks, orders, landing_page_conversion, price]
uncertainty: [当前没有完整落地页漏斗]
priority: high
```

## P005 ROI高但消耗趋平

```yaml
pattern_id: P005
title: ROI高但消耗趋平
version: v1.0
source_type: operator_experience
conditions: [roi_status == HIGH, reliable_timeseries == true, spend_status == HIGH|UNKNOWN]
possible_causes: [可探索人群逐渐减少, 投放进入饱和候选状态]
candidate_strategies: [核对可靠时序, 在人工确认后测试新计划或人群]
evidence_required: [campaign_metric_timeseries, spend slope, orders trend]
uncertainty: [没有可靠时间序列时不能判断趋平]
priority: medium
```

## P006 消耗增长但订单没有同步增长

```yaml
pattern_id: P006
title: 消耗增长但订单没有同步增长
version: v1.0
source_type: operator_experience
conditions: [delta_spend > 0, delta_orders <= 0]
possible_causes: [流量质量或转化承接效率下降]
candidate_strategies: [检查CVR和商品页, 比较新增消耗对应订单]
evidence_required: [historical_delta, clicks, CVR, product_page_data]
uncertainty: [时间窗口和归因延迟未确认]
priority: medium
```

## P007 新品快速起量

```yaml
pattern_id: P007
title: 新品快速起量
version: v1.0
source_type: operator_experience
conditions: [is_new_product == true, spend_growth_confirmed == true, orders_normal_confirmed == true, video_quality == NORMAL]
possible_causes: [当前素材和初始人群表现出扩量信号]
candidate_strategies: [小步增加预算进行探索]
evidence_required: [spend delta, orders, video metrics, fulfillment data]
uncertainty: [案例预算不是通用固定规则]
priority: medium
```

## P008 多轮 WAIT_OBSERVE

```yaml
pattern_id: P008
title: 多轮WAIT_OBSERVE
version: v1.0
source_type: operator_experience
conditions: [consecutive_wait_observe >= 2]
possible_causes: [指标仍接近目标且没有足够新证据]
candidate_strategies: [继续比较关键指标, 检查是否产生新的可执行证据]
evidence_required: [analysis history, historical_delta]
uncertainty: [没有业务配置不能创造观察截止时间]
priority: low
```

## P009 数据缺失无法判断

```yaml
pattern_id: P009
title: 数据缺失无法判断
version: v1.0
source_type: operator_experience
conditions: [target_roi or spend or orders or required_video_metric is missing]
possible_causes: [当前数据不足以支持完整诊断]
candidate_strategies: [补充缺失字段, 暂不将候选原因当成结论]
evidence_required: [missing field values]
uncertainty: [缺失字段具体影响取决于缺失项]
priority: high
```

## P010 指标互相矛盾

```yaml
pattern_id: P010
title: 指标互相矛盾
version: v1.0
source_type: operator_experience
conditions: [signals conflict or source definitions differ]
possible_causes: [统计窗口不同, 字段口径不同, 数据源不一致]
candidate_strategies: [核对报表时间和字段定义, 暂缓经验归因]
evidence_required: [report dates, source fields, metric definitions]
uncertainty: [未完成口径核对前不能选择单一原因]
priority: high
```

## Boundary

Pattern 不能覆盖 Rule Engine 的 decision、rules_used、state、Delta 或 target ROI。所有 Pattern 结论都必须使用“可能”“候选”等表达，并保留支持证据、缺失证据和不确定性。
