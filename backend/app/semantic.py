"""Small deterministic semantic index used locally; replaceable with pgvector embeddings."""
import json
import math
import re
import hashlib

DIMENSIONS = 96

def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", (text or "").lower())

def embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for token in tokenize(text):
        index = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16) % DIMENSIONS
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]

def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return round(max(0.0, min(1.0, sum(a * b for a, b in zip(left, right)))), 4)

def stored_embedding(item) -> list[float]:
    raw = getattr(item, "embedding_json", None)
    if raw:
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            pass
    return embed(item_text(item))

def item_text(item) -> str:
    fields = ("name", "title", "description", "semantic_summary", "tags_text", "full_text", "hook", "body", "ending", "cta", "structure", "notes")
    return " ".join(str(getattr(item, field, "") or "") for field in fields)
