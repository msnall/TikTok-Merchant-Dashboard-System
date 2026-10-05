"""Optional OpenAI-compatible JSON adapter; never chooses business states."""
import json
import os
import math
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FIELDS = ("campaign_name", "link_type", "target_roi", "spend", "orders", "revenue",
          "current_roi", "ctr", "cvr", "official_completion_rate", "spend_pattern", "report_time")
NUMERIC_FIELDS = set(FIELDS) - {"campaign_name", "link_type", "spend_pattern", "report_time"}
EXPLANATION_FIELDS = ("summary", "diagnosis", "recommendations", "next_observation", "uncertainties")


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self):
        self.key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL")
        if not all((self.key, self.base_url, self.model)):
            raise LLMUnavailable("LLM_API_KEY、LLM_BASE_URL、LLM_MODEL 未完整配置")

    def _json(self, system: str, payload: dict) -> dict:
        url = self.base_url.rstrip("/") + "/chat/completions"
        body = json.dumps({"model": self.model, "temperature": 0,
            "response_format": {"type": "json_object"}, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]}).encode("utf-8")
        request = Request(url, body, {"Authorization": f"Bearer {self.key}",
                                   "Content-Type": "application/json"}, method="POST")
        # Live evaluation sends several small requests in sequence. Retry only
        # transient transport/server failures; schema and business errors must
        # still fail immediately and be handled by the caller's fallback path.
        data = None
        for attempt in range(2):
            try:
                with urlopen(request, timeout=20) as response:
                    if "explain" in system:
                        print(f"LLM_EXPLANATION_HTTP_STATUS={response.status}", flush=True)
                    data = json.load(response)
                break
            except HTTPError as error:
                if error.code not in (408, 429, 500, 502, 503, 504) or attempt:
                    raise
                time.sleep(0.5)
            except (URLError, TimeoutError, OSError):
                if attempt:
                    raise
                time.sleep(0.5)
        if data is None:
            raise LLMUnavailable("LLM 请求未返回数据")
        value = json.loads(data["choices"][0]["message"]["content"])
        if not isinstance(value, dict):
            raise ValueError("LLM 输出不是 JSON 对象")
        return value

    def extract(self, text: str, *, allow_missing: bool = False) -> dict:
        result = self._json(
            "你是TikTok跨境广告运营分析助手。只提取用户明确写出的事实；"
            "必须输出包含指定全部字段的JSON对象，缺失字段为null。不得猜测、推导指标或行动。"
            "百分数保留用户写出的数值，例如2.6%写为2.6。不得把建议当作已执行动作。",
            {"text": text, "fields": FIELDS},
        )
        if not allow_missing and set(result) != set(FIELDS):
            raise ValueError("LLM 提取字段不完整")
        if not set(result).issubset(set(FIELDS)) and not allow_missing:
            raise ValueError("LLM 提取包含额外字段")
        if allow_missing:
            # Providers occasionally add explanatory keys despite the JSON
            # schema. Keep the declared contract and discard only extras;
            # missing declared fields are normalized to None below.
            result = {key: value for key, value in result.items() if key in FIELDS}
        result = {field: result.get(field) for field in FIELDS}
        for key, value in result.items():
            if value is None:
                continue
            if key in NUMERIC_FIELDS:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"LLM 提取字段类型错误: {key}")
                if key == "orders" and not isinstance(value, int):
                    raise ValueError("orders 必须为整数")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(f"LLM 提取字段类型错误: {key}")
        if result["link_type"] not in (None, "A", "B"):
            raise ValueError("link_type 只能为 A、B 或 null")
        return result

    def explain(self, evidence: dict) -> dict:
        print("LLM_EXPLANATION_STARTED", flush=True)
        print(f"LLM_EXPLANATION_MODEL={getattr(self, 'model', os.getenv('LLM_MODEL'))}", flush=True)
        result = self._json(
            "你是TikTok跨境广告运营分析助手。只能解释系统提供的事实、规则、决策、"
            "历史delta和知识引用；不能修改它们，不能编造指标、平台规则或声称已执行广告操作。"
            "数据不足时明确说明。如果decision为WAIT_OBSERVE，明确说“先放着不动，等待下一次数据。”"
            "并说明下次观察什么。仅输出summary字符串及diagnosis、recommendations、"
            "next_observation、uncertainties字符串数组的JSON对象。",
            evidence,
        )
        if set(result) != set(EXPLANATION_FIELDS) or not isinstance(result["summary"], str) or not result["summary"].strip():
            raise ValueError("LLM 解释结构错误")
        if any(not isinstance(result[key], list) or any(not isinstance(item, str) for item in result[key])
               for key in EXPLANATION_FIELDS[1:]):
            raise ValueError("LLM 解释列表类型错误")
        return result
