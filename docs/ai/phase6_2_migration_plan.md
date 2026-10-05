# Phase 6.2 Migration Plan

范围：仅新增四张表，不改旧表字段、不回填旧 `decision_actions`，不把人工动作文本解释为平台执行。

## 迁移前基线与备份

- 开发库：`backend/content_system.db`
- 备份：`backend/backup/phase6_2_before_migration/content_system.db`
- 备份核验：Alembic `0011_stateful_decisions`，15 条 Analysis Run、15 条 Snapshot；SQLite `integrity_check=ok`、`foreign_key_check=0`。
- 迁移前再次读取开发库版本、Run/Snapshot 数量和备份完整性；若与备份基线不一致，先暂停开发库迁移并重新对账。

## 0012 内容

文件：`backend/alembic/versions/0012_recommendation_feedback_execution.py`，revision `0012_feedback_loop`。

仅创建 `ai_recommendations`、`ai_recommendation_feedback`、`ai_execution_records`、`ai_outcome_observations`，以及它们的 FK、来源/状态检查约束和索引。四张表初始为空。`causal_assessment` 的数据库默认值是 `UNKNOWN`，`validation_status` 默认 `UNVERIFIED`。

## 安全演练顺序

1. 后端服务停机，防止 FastAPI startup 的 `create_all()` 抢先创建表。
2. 从已验证备份复制一份独立 SQLite 副本。
3. 在副本依次执行 `0011 -> 0012 -> 0011 -> 0012`，每步核对 Alembic version、新旧表、Run/Snapshot 数量及外键检查。
4. 新表有业务记录时不执行 downgrade；downgrade 会删除 0012 新表，必须先备份且经单独批准。
5. 演练通过、开发库仍与迁移前基线一致后，才对开发库执行一次 upgrade；若版本或行数变化则停止。

## 验收

开发库版本为 `0012_feedback_loop`；旧 15 条 Run 和 15 条 Snapshot 保留；新增表结构与 ORM 一致；无外键错误。重启服务后不得出现启动时补建 0012 表的情况。离线测试和新闭环测试必须通过。

## 执行记录

- 迁移前开发库：`0011_stateful_decisions`，Run 15，Snapshot 15；与在线备份的完整 SQL dump SHA-256 相同。SQLite 在线备份文件的二进制 SHA 不相同，原因是备份重排了文件页，不能用文件 SHA 直接比较两者。
- 备份副本演练：`0011 -> 0012 -> 0011 -> 0012` 全部通过；各步 Run/Snapshot 均为 15/15，`integrity_check=ok`，外键违规 0。
- 开发库执行：升级到 `0012_feedback_loop`；Run/Snapshot 仍为 15/15；四张新表均为 0 行；`integrity_check=ok`，外键违规 0。
- 旧分析不自动回填建议 ID；旧 `decision_actions` 不转换成已执行记录。新分析才会在同一保存事务中创建建议快照。
- 离线回归：200 passed，5 deselected，0 failed；其中 Phase 6.2 专项 5 passed。未运行 live LLM。
