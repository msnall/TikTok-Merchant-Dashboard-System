# Phase 6.1 字段语义核查与 Schema 设计

本阶段仅完成只读核查和数据契约设计。不修改数据库、API、前端或既有业务逻辑，不执行 migration。

## 1. 当前字段语义核查

### `DecisionAction` / `decision_actions`

| 字段 | 当前实际含义 | 不能推断为 |
| --- | --- | --- |
| `analysis_run_id` | 关联一次 AI 分析 Run | 广告平台操作 ID |
| `action_type` | 运营对建议的反馈类型：`ACCEPT`、`REJECT`、`MODIFY` | 已批准或已执行 |
| `actual_action` | 运营人员填写的动作描述，例如“调整 ROI 到 1.0” | TikTok 后台已成功执行该动作 |
| `operator_note` | 运营备注 | 执行回执或结果数据 |
| `created_at` | 反馈/动作描述记录时间 | 实际执行时间 |

当前 POST `/api/ai/analyses/{analysis_id}/actions` 只创建上述一条 append-only 记录；没有执行状态、执行来源、平台回执或执行时间。`ACCEPT` 不等于执行，`MODIFY` 也不表示修改已成功。

当前 `/api/ai/feedback/stats` 的 `accept/reject/modify` 是动作记录统计；`agreement` 只比较 `actual_action` 文本与推荐数组，不能解释为执行率、建议有效率或收益改善率。

### Analysis / Snapshot / Reasoning / Strategy

- `AIAnalysisRun.decision`、`AIAnalysisRun.rules_used`、数值输入字段是系统分析事实与确定性结果；应作为 AI 建议的不可变基线。
- `AIAnalysisSnapshot.source_information` 是一次分析时的快照容器，当前保存 normalized input、RAG 引用、Reasoning、Diagnosis、Strategy ranking/impact、历史 Delta 等；适合保存“系统当时看到了什么”，不适合冒充平台执行回执。
- `reasoning_result`、`diagnosis_result` 和 `strategy_*` 是候选解释/候选策略；它们不改变 Decision/State，也不表示运营采纳或执行。
- `source_type` 当前允许 `uploaded_source`、`manual_entry`、`synthetic_demo`。它描述输入来源，不等于案例已经通过真实数据核验。未来案例库需要独立的 `case_source_type` 和 `verification_status`。
- 当前 RAG 检索 `docs/ai/AI运营决策知识库_V0.1.md` 的规则块；Pattern/Strategy 文档及运营案例尚未自动进入检索索引。Phase 7 才评审真实案例知识增强，不能将本阶段设计文档视为已接入 RAG。

只读开发库核查（执行本报告时）：Alembic `0011_stateful_decisions`；`decision_actions` 0 行；`ai_analysis_runs` 15 行；`ai_analysis_snapshots` 15 行。此处不将开发库行数作为案例统计。

## 2. 四层事件模型

四层必须保持独立，并通过 `analysis_id`/`analysis_run_id` 关联：

1. **AI Recommendation**：系统生成的 Decision、Strategy、候选动作和引用。不可被反馈覆盖。
2. **Human Feedback**：运营是否认可建议，以及原因和备注。
3. **Execution Record**：是否真的发生操作，包含执行来源和平台回执。
4. **Outcome Observation**：后续事实、时间窗口、前后指标和数据来源。

`ACCEPT` 只写入第二层；没有第三层记录时，执行状态必须是 `UNKNOWN`，不能由接口默认成 `EXECUTED`。
若一次分析存在多个候选动作，未来反馈应引用稳定的 `recommendation_id`（或分析快照内不可变的候选序号与内容摘要）；只关联 `analysis_id` 会无法确定运营认可了哪一条建议。

## 3. Decision Feedback Schema（设计，不落库）

建议实体：`decision_feedback`。

```yaml
id: integer
analysis_id: integer              # FK ai_analysis_runs.id
recommendation_id: string         # 指向本次分析中不可变的具体建议
feedback_type: ACCEPT|REJECT|MODIFY
reason_code: string               # 受控码，按 feedback_type 校验
operator_comment: string|null
created_at: datetime
source: operator_input            # 明确不是执行来源
```

建议原因码：

- `ACCEPT`: `REASONABLE`、`TIME_SAVING`、`OTHER`
- `REJECT`: `INSUFFICIENT_DATA`、`INCORRECT`、`OTHER_EXPERIENCE`、`NOT_ACTIONABLE`
- `MODIFY`: `NEEDS_ADJUSTMENT`、`MISSING_CONTEXT`、`OTHER`

同一分析允许追加多条反馈，但不得覆盖历史记录。反馈不写入 Decision/State。
兼容旧数据时，`decision_actions` 可关联其分析 Run，但缺少可靠候选建议标识，不得自动分配 `recommendation_id` 或纳入逐建议采纳率。

## 4. Execution Schema（设计，不落库）

建议实体：`execution_records`，与反馈一对多但语义独立。

```yaml
id: integer
analysis_id: integer              # FK ai_analysis_runs.id
feedback_id: integer|null        # 可选 FK decision_feedback.id
action_type: string              # 人工动作名称，不自动执行
execution_status: NOT_EXECUTED|EXECUTED|UNKNOWN
source: operator_input|tiktok_import|api|manual_upload
executed_at: datetime|null
external_reference: string|null  # 平台/人工凭证，非凭证时为空
operator_comment: string|null
created_at: datetime
```

默认值应为 `UNKNOWN`，而不是 `EXECUTED`。`actual_action` 迁移到此层时也只能作为描述复制，不能把旧记录回填成已执行。

## 5. Outcome Observation Schema（设计，不落库）

建议实体：`outcome_observations`。

```yaml
id: integer
analysis_id: integer              # FK ai_analysis_runs.id
execution_id: integer|null
observation_window_value: number
observation_window_unit: hours|days|weeks|custom
observation_window_source: operator_input|platform_data|configured_rule
metrics_before: json              # 事实快照，允许字段缺失
metrics_after: json               # 事实快照，允许字段缺失
data_source: operator_input|tiktok_import|manual_upload|system_calculated|synthetic_demo
verification_status: UNVERIFIED|PARTIALLY_VERIFIED|VERIFIED
notes: text|null
created_at: datetime
```

观察窗口必须由输入数据或明确配置提供，不默认 7 天。`metrics_before/after` 只记录事实；差值可以由代码计算，但不应由该记录自动推断因果。

## 6. No Causal Claim Policy

建议独立字段或独立评估实体：

```yaml
causal_assessment: UNKNOWN|POSSIBLE|SUPPORTED
causal_basis: string|null
assessed_by: operator_input|system_review|experiment
```

默认 `UNKNOWN`。即使执行后 ROI 上升，也不能自动写成 `SUPPORTED`。`POSSIBLE` 至少需要明确时间关系和已知混杂因素范围；`SUPPORTED` 需要对照实验、重复案例或其他经审核的证据。任何结果都不能被表述为“AI 建议造成”。

## 7. 数据来源定义

| 来源 | 含义 | 核验边界 |
| --- | --- | --- |
| `operator_input` | 运营人员直接填写反馈、动作声明或观察值 | 真实人工记录，不自动等于平台事实已核验 |
| `manual_upload` | 人工上传的报表/附件 | 需保留原文件标识、导出时间和字段映射；上传本身不保证真实性 |
| `tiktok_import` | 未来适配的 TikTok 导出数据 | 当前未接入；仍需核对计划 ID、时段和指标口径 |
| `api` | 未来外部执行/查询接口回执 | 当前未接入；需保留请求与回执标识 |
| `system_calculated` | 系统基于已记录事实计算的 Delta 或聚合 | 必须可回溯输入和算法，不能伪装成原始平台值 |
| `synthetic_demo` | 合成测试数据 | 只用于开发、回归和评测，不进入真实案例统计 |

知识文档的 `operator_experience`、`official_platform_definition` 是知识来源类别；它们不是一次广告结果的采集渠道。案例的 `real_operator_case` 是案例类别；它不等同于已核验。现有 `manual_entry/uploaded_source` 是分析输入类别，不能直接替代上述来源和核验状态。

## 8. Case Quality Gate

未来 `case_library` 进入真实统计或知识检索前，至少检查：

| 检查项 | 允许值 | 统计规则 |
| --- | --- | --- |
| `case_source_type` | `real_operator_case`、`synthetic_demo` | 只有 `real_operator_case` 可进入真实统计；`synthetic_demo` 仅测试/回归 |
| `verification_status` | `UNVERIFIED`、`PARTIALLY_VERIFIED`、`VERIFIED` | 未核验案例不得作为已验证经验；报表导出/平台数据可支持 `VERIFIED` |
| `observation_window` | 明确数值、单位、来源 | 缺失时只能记录结果不完整，不能补默认周期 |
| `causal_assessment` | `UNKNOWN`、`POSSIBLE`、`SUPPORTED` | 默认 `UNKNOWN`，不由 ROI 前后差自动升级 |
| `data_source` | `operator_input`、`tiktok_import`、`manual_upload`、`system_calculated`、`synthetic_demo` | 必须逐项保留；系统计算不得伪装成平台原始数据 |

真实案例统计可报告：采纳率、修改率、拒绝原因分布、结果跟踪覆盖率、按 Pattern/Strategy 的案例数量和核验数量。采纳率/修改率的分母应为有有效反馈的真实建议，按 `recommendation_id` 去重并明确采用哪次反馈；结果跟踪覆盖率的分母应为可跟踪的真实建议。没有反馈的建议单独计数，不当作拒绝。禁止报告“AI 赚钱率”或把案例结果直接归因于 AI。

使用门槛分开执行：`synthetic_demo` 不参与任何真实指标；`real_operator_case` 且有人工反馈可进入反馈统计；只有观察窗口和来源明确的案例才进入结果跟踪覆盖；结果质量分析应单独呈现 `UNVERIFIED/PARTIALLY_VERIFIED/VERIFIED` 数量，不能将未核验口述写成已验证经验。进入未来 RAG 的案例必须保留来源与核验标签，是否允许检索未核验案例需在 Phase 7 单独评审。

## 9. 后续 Migration 评估（不执行）

优先新增独立表，而不是扩展 `decision_actions` 承载四种事件：

1. `decision_feedback`：反馈原因、备注和来源。
2. `execution_records`：执行状态、执行来源、时间和外部凭证。
3. `outcome_observations`：观察窗口、前后事实、数据来源和核验状态。
4. `case_library`：经过质量门槛的案例索引，引用上述实体，不复制并改写原始事实。

`decision_actions` 保持向后兼容，语义固定为既有“反馈 + 人工动作描述”。现有 `ai_analysis_snapshots` 继续保存分析时快照，不承载可变的后续结果。正式迁移前必须先备份开发库，并在临时 SQLite 完成 upgrade/downgrade/upgrade 和孤立记录检查。

## 10. 下一阶段边界

本设计完成后停止。下一步只有在 Schema 评审通过后，才可单独实现迁移和 API。当前不接 TikTok API，不修改 Rule Engine、State Machine、Reasoning、Decision、Target ROI，不实现 Agent 或自动广告操作。
