# AI 跨境运营决策知识库 V0.2

> 未接入系统的历史草稿。当前 Phase 0 基线为 `AI运营决策知识库_V0.1.md`；本草稿的规则口径不可直接用于决策。

本文件是 Phase 0 的规则基线。规则 ID 唯一，所有动作仅供运营人员参考。现有广告六状态规则和提醒逻辑不受本文件影响。

## 来源类型与指标边界

| `source_type` | 含义 | 边界 |
| --- | --- | --- |
| `operator_experience` | 当前团队的运营经验 | 不称为 TikTok 官方规则 |
| `official_platform_definition` | TikTok 平台公开指标定义 | 仅解释指标，不提供团队阈值 |
| `synthetic_demo` | 合成测试数据 | 不作为真实历史案例或真实账户决策依据 |

当前 Campaign Excel 的 `ROI` 口径约为 `总收入 / 成本`，数学上接近 ROAS。系统既有 `actual_roi`/`target_roi` 字段不改名、不改义；**利润 ROI 需要商品成本、物流、平台费等完整模型**。视频 6 秒播放数与官方完播率不同，不得由 `views_6s / impressions` 推导后冒称官方值。

平台指标定义参考：

- https://ads.tiktok.com/resources/help/article/video-play?lang=zh
- https://ads.tiktok.com/help/article/basic-data?lang=en
- https://ads.tiktok.com/business/en-US/guides/what-is-roas

## 结构化业务规则

### R001 视频数据正常

- `rule_id`: `R001`
- `title`: 视频数据正常
- `source_type`: `operator_experience`
- `version`: `V0.2`
- `business_scope`: 有可信投放视频表现的广告视频
- `conditions`: CTR > 2%，按点击数计算的 CVR > 10%，平台官方完播率 > 30%；三项同时满足，等于阈值不满足
- `conclusion`: `video_normal`
- `evidence_required`: 三项指标、统计时段、视频 ID、分母口径、来源类型；真实分析还须确认官方导出列
- `action`: 标注视频符合当前团队经验阈值，再结合成本、订单及目标 ROI 判断
- `uncertainty`: 阈值不是 TikTok 官方标准；任一指标缺失时为 `insufficient_data`

### R002 视频数据不好

- `rule_id`: `R002`
- `title`: 视频指标未达到当前正常标准
- `source_type`: `operator_experience`
- `version`: `V0.2`
- `business_scope`: 有可信投放视频表现的广告视频
- `conditions`: R001 三项指标齐全，至少一项小于或等于对应阈值
- `conclusion`: `video_poor`
- `evidence_required`: 同 R001，并指出未达标指标
- `action`: 当前经验倾向人工检查后关停或换素材；系统不执行关停
- `uncertainty`: 未达标不等于已证明亏损；数据缺失不触发本规则

### R003 视频正常而 ROI 低于目标

- `rule_id`: `R003`
- `title`: 视频正常但实际 ROI 低于目标
- `source_type`: `operator_experience`
- `version`: `V0.2`
- `business_scope`: 广告与视频能可靠关联且统计口径一致的计划
- `conditions`: R001 成立且 `actual_roi < target_roi`
- `conclusion`: 不能直接把低 ROI 归因于视频
- `evidence_required`: 视频指标、实际/目标 ROI、成本、订单、统计时段及关联依据
- `action`: 继续观察消耗与转化；可由运营人员测试不同利润目标 ROI
- `uncertainty`: 缺少利润模型时不得计算新目标数值；关联不可靠时不触发

### R004 当前 ROI 偏高

- `rule_id`: `R004`
- `title`: 当前 ROI 偏高
- `source_type`: `operator_experience`
- `version`: `V0.2`
- `business_scope`: 拟调整 ROI 目标的广告计划
- `conditions`: ROI 明显高于希望维持的区间；“明显”的数值阈值待确认
- `conclusion`: 可考虑重建并提高目标 ROI
- `evidence_required`: 实际 ROI、当前目标、业务期望区间和报表时段
- `action`: 提示人工考虑关停旧计划、重建及提高目标
- `uncertainty`: 不能自动判断触发条件，也不能自行设定提高幅度

### R005 消耗突增后变平

- `rule_id`: `R005`
- `title`: 消耗突增后变平
- `source_type`: `operator_experience`
- `version`: `V0.2`
- `business_scope`: 同一计划、同一口径的可靠时间序列
- `conditions`: 消耗先快速增加，之后连续多个采样点增长趋平；阈值及采样间隔待确认
- `conclusion`: 可能已难以继续消耗，需要人工核查
- `evidence_required`: 各采样点报表起止时间、成本、订单、收入、累计/区间口径
- `action`: 人工核查后可考虑关停并重建，重新探索人群
- `uncertainty`: 当前日级 Demo 只能保留规则，不能声称检测到真实实时 saturation

### R006 最终目标 ROI

- `rule_id`: `R006`
- `title`: 目标 ROI 接近且略高于当前 ROI
- `source_type`: `operator_experience`
- `version`: `V0.2`
- `business_scope`: 人工确认计划表现并拟调整目标的场景
- `conditions`: 目标由运营人员结合产品经济性确认；“略高”的增量未定义
- `conclusion`: 目标通常接近当前 ROI，并略高于当前 ROI
- `evidence_required`: 当前 ROI、原目标、A/B 政策及相关商品经济性数据
- `action`: 提醒人工核对目标数值
- `uncertainty`: 禁止自动使用固定百分比或加数；禁止混淆利润 ROI 与收入/广告费比值

### R007 新品快速起量

- `rule_id`: `R007`
- `title`: 新品逐步扩量
- `source_type`: `operator_experience`
- `version`: `V0.2`
- `business_scope`: 发货和退货结果尚未验证的新品
- `conditions`: 可靠数据表明消耗快速增加、订单和视频表现正常；“订单正常”的阈值待确认
- `conclusion`: 可以小步探索预算，同时关注履约和退货风险
- `evidence_required`: 消耗序列、订单、视频指标、预算变化、发货/退货状态
- `action`: 10 → 20 → 30 美元仅为当前案例中的人工参考
- `uncertainty`: 案例金额不是所有新品固定规则，系统不自动加预算

### R008 A/B 目标 ROI 政策

- `rule_id`: `R008`
- `title`: A/B 链接使用不同目标 ROI 政策
- `source_type`: `operator_experience`
- `version`: `V0.2`
- `business_scope`: 明确标识为 A 或 B 的产品广告链接
- `conditions`: A 对应 `target_roi_policy = break_even`；B 对应 `target_roi_policy = profit_5pct`
- `conclusion`: A 使用保本 ROI 政策；B 使用 5% 利润 ROI 政策
- `evidence_required`: 可信链接类型、产品身份；如需比较数值，还需现有人工录入目标
- `action`: 显示政策类型，具体目标数值仍取现有 ROI 配置或人工确认
- `uncertainty`: 保本与 5% 利润的换算公式待确认；C/D 及未知类型不推断为 A/B

## Demo 与待确认事项

Demo `Campaign_Data` 标为 `uploaded_source`；`Video_Data` 的 20 条视频是 `synthetic_demo`。即使合成视频引用了真实 Campaign ID，也不构成真实视频投放历史。

价格与目标 ROI 的方向性假设，以及“提价、改 ROI、第一条链接加计划”的触发条件，仍为 `clarify_required`，不赋予 Rule ID 或执行逻辑。后续需要真实商品成本、物流、平台费、佣金和退货数据才能定义利润模型。
