# AI 数据契约 V0.1

金额保留原导出币种；比率存 0–1 小数，ROI 存倍数。`current_roi` 对应现有广告快照的 `actual_roi`，不等于利润 ROI。`roi_policy` 为档位标签，不是数值；`target_roi` 来自计划名最后的独立数字或已有人工配置，不能由利润公式推导。`snapshot_at` 是导入时间，报表时间另存。

数据 `source_type`：`uploaded_source`、`manual_entry`、`synthetic_demo`。合成数据仅用于测试，真实历史统计必须排除。表中“可用”均以来源、时段、关联可靠为前提，Phase 0 不调用 LLM。

## Campaign

| 字段 | 含义 | 单位 | 数据来源 / source_type | 可用 | 缺失时 |
| --- | --- | --- | --- | --- | --- |
| campaign_id | 平台计划标识 | 字符串 | 报表 / uploaded_source | 精确关联 | 不自动关联 |
| campaign_name | 原计划名称 | 文本 | 报表 / uploaded_source | 可解析名称 | 不推断 A/B |
| product | 产品 | 文本 | 报表或人工 / 同源 | 有依据时可用 | 未知 |
| market | 市场 | 文本 | 报表或人工 / 同源 | 有依据时可用 | 未知 |
| link_type | A/B 等链接类型 | 代码 | 名称解析 / 同源 | A/B 可映射策略 | UNKNOWN |
| roi_policy | break_even / profit_5pct / profit_10pct | 代码 | 经验配置 / manual_entry | 仅作为策略 | requires_confirmation |
| target_roi | 当前目标 ROI | 倍数 | 名称尾数或人工配置 / 同源 | 可与同口径 ROI 比较 | 不计算利润公式 |
| spend | 广告成本 | 导出币种 | 报表 / uploaded_source | 有时段可用 | 不判空烧 |
| orders | SKU 订单数 | 单 | 报表 / uploaded_source | 可用 | UNKNOWN |
| revenue | 归因收入 | 导出币种 | 报表 / uploaded_source | 有时段可用 | UNKNOWN |
| current_roi | 报表 ROI，即现有 actual_roi | 倍数 | 报表 / uploaded_source | 同口径可比 | UNKNOWN |

## Video

视频投放指标独立于制作资产 `VideoWork`。真实官方完播率的导出列名未知，不能用 6 秒播放数/展示数代替。

| 字段 | 含义 | 单位 | 数据来源 / source_type | 可用 | 缺失时 |
| --- | --- | --- | --- | --- | --- |
| video_id | 投放视频 ID | 字符串 | 视频报表 / uploaded_source 或 synthetic_demo | 可归集 | 不入库 |
| campaign_id | 所属计划 ID | 字符串 | 视频报表 / 同源 | 精确匹配可用 | 不自动关联 |
| report_date | 报表日期 | 日 | 视频报表 / 同源 | 可用 | 不入库 |
| impressions | 展示次数 | 次 | 视频报表 / 同源 | 核对 CTR | 数据不足 |
| clicks | 点击次数 | 次 | 视频报表 / 同源 | 核对 CTR/CVR | 数据不足 |
| ctr | 点击率 | 0–1 | 导出或明确同口径计算 / 同源 | 可用 | VIDEO_UNKNOWN |
| orders | 视频归因订单 | 单 | 视频报表 / 同源 | 不自动等于计划订单 | 数据不足 |
| cvr | 转化率 | 0–1 | 导出或明确同口径计算 / 同源 | 可用 | VIDEO_UNKNOWN |
| official_completion_rate | 平台官方完播率 | 0–1 | 已确认原始列 / uploaded_source；固定演示值 / synthetic_demo | 真实分析只用确认列 | VIDEO_UNKNOWN |

`source_field_name` 与 `source_document` 必须保留来源。未知真实列名时官方完播率留空。视频花费与收入可以另存，但不能与计划数据无条件相加。

## Spend Time Series

| 字段 | 含义 | 单位 | 数据来源 / source_type | 可用 | 缺失时 |
| --- | --- | --- | --- | --- | --- |
| campaign_id | 计划标识 | 字符串 | 有时段的报表 / uploaded_source 或 synthetic_demo | 可归集 | 不入库 |
| timestamp | 样本统计时间 | 时间 | 报表 / 同源 | 可用 | 不进行时序判断 |
| spend | 样本成本 | 导出币种 | 报表 / 同源 | 明确累计/区间口径时可用 | 数据不足 |
| orders | 样本订单 | 单 | 报表 / 同源 | 同口径可用 | 数据不足 |
| revenue | 样本收入 | 导出币种 | 报表 / 同源 | 同口径可用 | 数据不足 |

时间序列须附 `measurement_type`（`cumulative` 或 `interval`）。当前 Demo 的日汇总不支持真实实时 saturation 判断；两个日汇总样本也不够。
