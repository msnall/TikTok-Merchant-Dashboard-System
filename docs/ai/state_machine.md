# Stateful AI Decision State Machine

状态只由代码根据 normalized facts、Rule Engine decision 和上一轮快照决定；LLM 不能写入或覆盖状态、迁移、Delta 或规则。

| state | 含义 | 允许到达 |
|---|---|---|
| NEW | 计划尚无分析历史 | WAIT_OBSERVE, ACTIONABLE, CLOSED_REBUILD, NEEDS_CONFIRMATION |
| OBSERVING | 已开始收集可比数据 | WAIT_OBSERVE, ACTIONABLE, CLOSED_REBUILD, NEEDS_CONFIRMATION |
| WAIT_OBSERVE | 当前证据不足，等待下一轮 | WAIT_OBSERVE, ACTIONABLE, CLOSED_REBUILD, NEEDS_CONFIRMATION |
| ACTIONABLE | 规则已给出可执行建议，仍需人工确认 | ACTIONABLE, CLOSED_REBUILD, NEEDS_CONFIRMATION, WAIT_OBSERVE |
| CLOSED_REBUILD | 规则建议关停并重建；不代表已执行 | ACTIONABLE, WAIT_OBSERVE |
| NEEDS_CONFIRMATION | 证据冲突或需要人工确认 | ACTIONABLE, CLOSED_REBUILD, WAIT_OBSERVE, NEEDS_CONFIRMATION |

决策到状态的确定性映射：`WAIT_OBSERVE -> WAIT_OBSERVE`；`CLOSE_REBUILD_*` 和 `EMPTY_BURN -> CLOSED_REBUILD`；`NEEDS_CONFIRMATION -> NEEDS_CONFIRMATION`；其余规则决策 -> `ACTIONABLE`。

每次分析追加一个 `ai_state_transitions` 记录。WAIT_OBSERVE 追加 observation plan，包含计划 ID、上一轮分析 ID、原因和下一轮必须比较的 spend、orders、ROI、CTR、CVR、completion_rate。人工 ACCEPT、REJECT、MODIFY 与实际动作保存到 `decision_actions`，不调用广告平台 API。
