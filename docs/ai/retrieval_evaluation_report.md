# Retrieval Evaluation Report

## Scope

本报告评测当前本地 `SimpleKeywordRetrieval`，不引入 Embedding、LLM 或 Agent。案例均为模拟的真实运营问法，`source_type=operator_experience`；它们是检索评测数据，不是历史业务案例。

## Dataset

- 案例数：27
- 覆盖：空烧、个位数订单、视频正常但 ROI 低、视频数据差、ROI 高于目标、消耗趋平、新品起量、A/B 目标 ROI、组合问题、模糊口语和知识库外问题
- 评测文件：`backend/tests/fixtures/ai_retrieval_cases.json`

## Recall

| 指标 | 命中案例 | 总案例 | Recall |
| --- | ---: | ---: | ---: |
| Recall@1 | 20 | 27 | 74.1% |
| Recall@3 | 25 | 27 | 92.6% |
| Recall@5 | 25 | 27 | 92.6% |

命中定义为该案例所有 `expected_rule_ids` 都出现在对应 Top-K。`acceptable_rule_ids` 用于记录业务上可接受的相关规则，不替代 expected 统计。

## Rule coverage (Recall@5)

| Rule | 测试数量 | 正确召回 | 未召回 |
| --- | ---: | ---: | ---: |
| R001 | 1 | 1 | 0 |
| R002 | 2 | 2 | 0 |
| R003 | 7 | 6 | 1 |
| R004 | 3 | 3 | 0 |
| R005 | 6 | 5 | 1 |
| R006 | 1 | 1 | 0 |
| R007 | 2 | 2 | 0 |
| R008 | 3 | 3 | 0 |
| EMPTY_BURN_USD_3 | 3 | 3 | 0 |

## Failure analysis

- `ORDER_001`（“出了3单，但是一直起不来”）：5 个结果内未召回 R003。原因是问题没有明确 ROI 低或视频指标，属于**Query 过于模糊/多规则竞争**；不应凭订单数自动推断视频或 ROI 结论。
- `COMBO_002`（视频正常、先快后平）：R005 能召回，但 R003 未进入 Top 5。原因是**多规则竞争**，趋平词和视频正常词权重较高；该问题仍已召回核心 R005。

Top-K 不足不是唯一原因，扩大到 Top 5 后上述两个组合案例仍有部分缺失，暂不通过添加臆测规则修复。

## Conclusion

当前关键词检索已经适合 Phase 1.5 的可解释基线：Top 3/5 对明确业务问法达到 92.6%，未知问题保持空结果。暂不建议立即进入 Embedding；下一阶段可先继续扩充真实问法、同义词和多规则排序评测，若业务问法规模和语义变化明显增加，再以本报告作为 Embedding 对照基线。
