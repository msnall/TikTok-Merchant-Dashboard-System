# Decision Evaluation Framework

Phase 4 分层评价，不把系统压缩成单一“AI 准确率”。

| 层级 | 评价内容 | Oracle |
|---|---|---|
| Extraction Quality | LLM 是否提取用户明确事实、缺失字段是否为 null | deterministic fixture / schema |
| Normalization Quality | 计划、A/B、target ROI 和数值归一化 | normalization tests |
| Rule Decision Accuracy | Rule Engine decision 与业务案例期望是否一致 | deterministic expected decision |
| State Transition Accuracy | from/to state 与状态机规则是否一致 | state machine oracle |
| Explanation Quality | 解释是否只引用事实、规则和证据 | grounded validation |
| Human Acceptance | AI recommendation 与人工 ACCEPT/REJECT/MODIFY 的代码统计 | action records |

数据质量 confidence 由代码计算，表示事实是否足以支持判断，不表示 LLM 信心：`HIGH`、`MEDIUM`、`LOW`、`INSUFFICIENT`。target ROI、spend 或 orders 缺失时为 `INSUFFICIENT`。

每个案例分别记录 extraction、normalization、decision、state 和 missing-data 结果，并按 Rule ID 分组；RAG evidence coverage 只统计实际返回的 knowledge chunk，未命中时使用 `NO_KNOWLEDGE_EVIDENCE`。
