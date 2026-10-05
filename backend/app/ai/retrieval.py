"""Interchangeable local retrieval; scores express lexical relevance, not truth."""

from dataclasses import asdict
from typing import Protocol
import re

from .knowledge import KnowledgeChunk, load_knowledge


class RetrievalProvider(Protocol):
    def search(self, query: str, top_k: int = 5,
               source_type: str | None = None) -> list[dict]: ...


DOMAIN_TERMS = {
    "空烧": 4, "视频": 1, "正常": 1, "差": 1, "roi": 1,
    "低于": 3, "高于": 3, "目标": 1, "消耗": 1,
    "突增": 3, "趋平": 4, "不再增加": 3, "新品": 3,
    "快速起量": 4, "预算": 2, "保本": 2, "利润": 2,
    "ctr": 2, "cvr": 2, "完播": 2, "重建": 1,
    "低": 3, "高": 3, "超过": 3, "不错": 1, "不行": 2, "起不来": 2,
    "没出单": 3, "单子很少": 2, "爆了": 3, "跑通": 3,
    "烧不动": 3, "花不动": 3, "消耗不下去": 3, "不怎么花": 3,
}
QUERY_ALIASES = {
    "突然增加": "突增", "不再消耗": "趋平", "消耗不动": "趋平",
    "跑起来": "快速起量", "跑量": "快速起量", "跑通": "快速起量",
    "烧不动": "趋平", "花不动": "趋平", "消耗不下去": "趋平",
    "不怎么花": "趋平", "后面平了": "趋平", "消耗突然没了": "趋平",
    "没出单": "空烧", "一单都没有": "空烧", "0单": "空烧",
    "视频还行": "正常", "素材不行": "差", "数据不行": "差",
    "点击率太低": "差", "点击率低": "差", "视频的数据明显不行": "差",
    "出了订单": "正常", "出了3单": "单子很少", "出了5单": "单子很少",
    "roi有点低": "低于", "roi跑高了": "高于", "现有roi比较大": "高于",
}
STOP_BIGRAMS = {"怎么", "应该", "如何", "但是", "一下", "之后", "什么", "当前", "数据"}


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", text.casefold())


def _terms(text: str) -> set[str]:
    normalized = _normalized(text)
    terms = {term for term in DOMAIN_TERMS if term in normalized}
    terms.update(re.findall(r"[a-z]+\d*|\d+(?:\.\d+)?", normalized))
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        terms.update(phrase[index:index + 2] for index in range(len(phrase) - 1))
    return terms - STOP_BIGRAMS


class SimpleKeywordRetrieval:
    def __init__(self, chunks: tuple[KnowledgeChunk, ...] | None = None):
        self.chunks = chunks if chunks is not None else load_knowledge()

    def search(self, query: str, top_k: int = 5,
               source_type: str | None = None) -> list[dict]:
        if not query.strip() or top_k < 1:
            return []
        expanded = _normalized(query)
        for phrase, replacement in QUERY_ALIASES.items():
            if phrase in expanded:
                expanded += replacement
        query_terms = _terms(expanded)
        if not query_terms:
            return []
        matches = []
        for chunk in self.chunks:
            if source_type is not None and chunk.source_type != source_type:
                continue
            # A non-zero order phrase must not be confused with the zero-order
            # empty-burn rule merely because the query contains a number.
            if chunk.rule_id == "EMPTY_BURN_USD_3" and re.search(r"(?:出了|有|已有)\s*\d+\s*单", expanded):
                continue
            full_text = " ".join((chunk.rule_id, chunk.title, chunk.business_scope,
                                  chunk.conditions, chunk.action, chunk.uncertainty, chunk.content))
            content_terms = _terms(full_text)
            overlap = query_terms & content_terms
            if not overlap and chunk.rule_id.casefold() not in expanded:
                continue
            weighted = sum(DOMAIN_TERMS.get(term, 0.4) for term in overlap)
            possible = sum(DOMAIN_TERMS.get(term, 0.4) for term in query_terms)
            score = weighted / possible if possible else 0.0
            if chunk.rule_id.casefold() in expanded:
                score = 1.0
            elif _terms(chunk.title) & query_terms:
                score = min(1.0, score + 0.08)
            if score < 0.12:
                continue
            matches.append({**asdict(chunk), "score": round(min(1.0, score), 4)})
        return sorted(matches, key=lambda item: (-item["score"], item["rule_id"]))[:top_k]


def search_knowledge(query: str, top_k: int = 5,
                     source_type: str | None = None,
                     provider: RetrievalProvider | None = None) -> list[dict]:
    return (provider or SimpleKeywordRetrieval()).search(query, top_k, source_type)
