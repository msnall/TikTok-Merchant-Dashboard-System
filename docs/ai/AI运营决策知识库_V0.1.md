# AI 运营决策知识库 V0.1

以下均为运营人员经验，`source_type=operator_experience`，不是 TikTok 官方投放规则。建议均需人工确认，不能视为账户中已执行的操作。

## R001 视频正常

- rule_id: R001
- title: 视频达到团队正常标准
- source_type: operator_experience
- business_scope: 有可信投放视频数据的计划
- conditions: CTR > 2%，CVR > 10%，平台官方完播率 > 30%，三项同时满足
- conclusion: VIDEO_NORMAL
- action: 结合订单、成本和 ROI 继续判断
- evidence_required: 视频/计划 ID、报表日期、三项指标、官方完播率原始字段
- uncertainty: 团队阈值不是平台推荐阈值；缺失指标返回 UNKNOWN

## R002 视频差

- rule_id: R002
- title: 视频未达到团队正常标准
- source_type: operator_experience
- business_scope: 三项关键视频指标齐全的计划
- conditions: R001 中至少一项指标小于或等于对应阈值
- conclusion: VIDEO_POOR
- action: 倾向人工关停并重建，默认保持目标 ROI
- evidence_required: 同 R001，及未达标项
- uncertainty: 缺失值不能当作视频差；建议不等于执行

## R003 视频正常且 ROI 低

- rule_id: R003
- title: 视频正常但 ROI 低于目标
- source_type: operator_experience
- business_scope: 视频与计划关联可靠且时段可比
- conditions: VIDEO_NORMAL 且 current_roi < target_roi；订单 1–9 为 FEW_ORDERS
- conclusion: 不能直接归因于素材；少量订单时倾向降低一个策略档位并重建
- action: 人工考虑 profit_10pct → profit_5pct → break_even；缺下一档数值时只输出政策变化
- evidence_required: 当前/目标 ROI、订单、成本、视频指标和关联依据
- uncertainty: 策略档位不是目标数值；利润换算公式待确认

## R004 ROI 高

- rule_id: R004
- title: 视频正常且 ROI 高于目标
- source_type: operator_experience
- business_scope: ROI 与视频报表可比的计划
- conditions: VIDEO_NORMAL 且 current_roi > target_roi
- conclusion: 可考虑关停重建并提高一个策略档位
- action: 下一档具体目标值只从已有配置读取；缺失时返回 null
- evidence_required: 当前/目标 ROI、现有策略、下一档人工配置
- uncertainty: 不计算新 ROI；最高档位或缺配置时 requires_confirmation

## R005 消耗突增后趋平

- rule_id: R005
- title: 消耗增长后趋平
- source_type: operator_experience
- business_scope: 同一计划、同口径的可靠时间序列
- conditions: 成本先明显增加后基本不增长；量化阈值及采样间隔待确认
- conclusion: 可能消耗不动，但两个日汇总点不足以判断
- action: 人工检查后可考虑关停重建、重新探索人群
- evidence_required: 连续样本的报表时间、成本、订单、收入及累计/区间口径
- uncertainty: Phase 0 不自动检测 saturation；requires_confirmation

## R006 目标 ROI 略高

- rule_id: R006
- title: 最终目标接近且略高于当前 ROI
- source_type: operator_experience
- business_scope: 人工调整目标 ROI 的计划
- conditions: 运营人员确认经济性；“略高”幅度待确认
- conclusion: 目标通常在当前 ROI 附近并略高
- action: 提醒人工核对策略与数值
- evidence_required: 当前 ROI、原目标、策略和商品经济性
- uncertainty: 不自动使用固定加数或百分比；requires_confirmation

## R007 新品快速起量

- rule_id: R007
- title: 新品逐步探索预算
- source_type: operator_experience
- business_scope: 新品投放探索
- conditions: 新品、可信消耗增长、订单表现正常、VIDEO_NORMAL；增长/订单阈值待确认
- conclusion: 可人工逐步增加预算
- action: 10 → 20 → 30 美元仅为案例经验，不是通用规则
- evidence_required: 新品标记、时序、订单、视频和履约/退货数据
- uncertainty: 不自动扩量；requires_confirmation

## R008 A/B ROI 策略

- rule_id: R008
- title: A/B 链接目标 ROI 政策
- source_type: operator_experience
- business_scope: 名称可识别 A/B 的广告计划
- conditions: A=break_even；B=profit_5pct；计划名最后独立数字为当前 target_roi
- conclusion: 策略档位与目标数值分开
- action: 只解析名称或读取已有人工配置，不推导利润公式
- evidence_required: 原计划名称及人工配置（若有）
- uncertainty: C/D 策略及利润换算公式待确认

## 独立优先规则

AI 决策层的独立规则代码 `EMPTY_BURN_USD_3` 为 `spend > 3 USD AND orders = 0`，输出 `EMPTY_BURN` 和建议 `CLOSE_REBUILD_KEEP_ROI`。现有广告中心六状态使用不同阈值，本阶段不修改。订单 1–9 为 `FEW_ORDERS`，不是空烧。`roi_near_threshold` 尚未确认；不私设固定范围。真实官方完播率字段名未知，不能用 `views_6s / impressions` 冒充。合成数据必须标记 `synthetic_demo`，不能进入真实历史统计。
