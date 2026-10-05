"""Load versioned operator knowledge as rule-aligned chunks."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re


KNOWLEDGE_PATH = Path(__file__).resolve().parents[3] / "docs" / "ai" / "AI运营决策知识库_V0.1.md"
SOURCE_TYPES = {"operator_experience", "official_platform_definition", "synthetic_demo"}
RULE_HEADING = re.compile(r"^## (R\d{3})\s+(.+)$", re.MULTILINE)
FIELD = re.compile(r"^- ([a-z_]+):\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class KnowledgeChunk:
    knowledge_id: str
    rule_id: str
    title: str
    source_type: str
    version: str
    content: str
    business_scope: str
    conditions: str
    action: str
    uncertainty: str


def _rule_chunk(rule_id: str, heading: str, body: str, version: str) -> KnowledgeChunk:
    fields = dict(FIELD.findall(body))
    required = {"rule_id", "title", "source_type", "business_scope", "conditions", "action", "uncertainty"}
    if required - fields.keys() or fields["rule_id"] != rule_id:
        raise ValueError(f"知识规则 {rule_id} 字段缺失或 ID 不一致")
    if fields["source_type"] not in SOURCE_TYPES:
        raise ValueError(f"知识规则 {rule_id} 的 source_type 不支持")
    return KnowledgeChunk(
        knowledge_id=f"operations:{version}:{rule_id}", rule_id=rule_id,
        title=fields["title"] or heading, source_type=fields["source_type"],
        version=version, content=body.strip(), business_scope=fields["business_scope"],
        conditions=fields["conditions"], action=fields["action"],
        uncertainty=fields["uncertainty"],
    )


def parse_knowledge(document: str) -> tuple[KnowledgeChunk, ...]:
    version_match = re.search(r"^# .+\b(V\d+\.\d+)\s*$", document, re.MULTILINE)
    if not version_match:
        raise ValueError("知识库缺少版本号")
    version = version_match.group(1)
    headings = list(RULE_HEADING.finditer(document))
    if not headings:
        raise ValueError("知识库没有结构化规则")
    chunks = []
    for position, match in enumerate(headings):
        end = headings[position + 1].start() if position + 1 < len(headings) else len(document)
        body = document[match.end():end].split("\n## ", 1)[0]
        chunks.append(_rule_chunk(match.group(1), match.group(2), body, version))

    # The confirmed empty-burn priority rule lives outside the R001-R008 sequence.
    priority = re.search(r"^## 独立优先规则\s*\n(.+)$", document, re.MULTILINE | re.DOTALL)
    if priority and "EMPTY_BURN_USD_3" in priority.group(1):
        content = priority.group(1).strip()
        chunks.append(KnowledgeChunk(
            knowledge_id=f"operations:{version}:EMPTY_BURN_USD_3",
            rule_id="EMPTY_BURN_USD_3", title="空烧判断",
            source_type="operator_experience", version=version, content=content,
            business_scope="美元计价广告计划", conditions="spend > 3 USD AND orders = 0",
            action="CLOSE_REBUILD_KEEP_ROI，须人工确认",
            uncertainty="与现有广告中心阈值不同；不能自动操作账户",
        ))
    if len({chunk.rule_id for chunk in chunks}) != len(chunks):
        raise ValueError("知识库存在重复 Rule ID")
    return tuple(chunks)


@lru_cache(maxsize=4)
def _load_at_mtime(path: Path, modified_ns: int) -> tuple[KnowledgeChunk, ...]:
    return parse_knowledge(path.read_text(encoding="utf-8"))


def load_knowledge(path: Path = KNOWLEDGE_PATH) -> tuple[KnowledgeChunk, ...]:
    return _load_at_mtime(path, path.stat().st_mtime_ns)
