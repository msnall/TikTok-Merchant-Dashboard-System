# Phase 2 Analysis Evaluation

## Scope

Phase 2 在原广告六状态和 Phase 0 Rule Engine 之上提供自然语言分析入口。评测使用隔离 SQLite 数据库，不写入演示数据库或真实历史记录。真实 LLM 服务未配置；LLM 分支通过 fake client 验证，测试不依赖外部 API。

## Dataset and Results

- `tests/fixtures/ai_analysis_cases.json`：20 个自然语言案例。
- 结构化字段（案例标注的成本与订单）正确：20/20。
- 确定性决策正确：20/20。
- 历史 delta：三轮同计划追加测试通过；成本、订单、ROI、CTR delta 均由代码计算。
- RAG 引用：空烧及有规则决策的分析记录可保存、读取 Rule ID 引用；不由 RAG 决定状态。
- WAIT_OBSERVE：3 个案例通过，输出“先放着不动”和下一轮观察项。
- 无时序数据：不会仅凭“后面不花了”判定 `SPEND_SATURATION`。
- 合成数据：既有历史查询默认过滤 `synthetic_demo`。

## Known Limits

- `roi_near_threshold` 尚未由业务确认，只有当前 ROI 与目标 ROI 完全相等才返回 `NEAR_TARGET`；不会自行定义“接近”区间。
- 自然语言写“视频正常”但缺少可信 CTR、CVR、官方完播率时，视频状态仍为 `UNKNOWN`。
- 仅有自然语言“消耗变平”而无可靠连续采样时，不自动认定饱和。
- 人工报告未写报表时间时会返回时段口径不确定性。
- LLM 是可选的 OpenAI-compatible JSON 接口；通过 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 配置。未配置时使用本地确定性解析和说明。LLM 输出不能覆盖 Rule Engine 的 decision、rules_used 或计算出的 delta。
- LLM 文本解释仅作为说明，仍需运营人员人工核对；系统不连接或操作 TikTok 账户。

## Storage

不改变 Phase 0 表结构：每轮新增 `ai_analysis_runs` 和一条 `ai_analysis_snapshots`。原始报告、结构化输入、引用、历史 delta、摘要和下一次观察项存入该轮 snapshot 的 `source_information` JSON；原有 run 列继续存决策和核心指标。历史查询按 campaign_id 与 run ID 读取，不覆盖旧记录。
