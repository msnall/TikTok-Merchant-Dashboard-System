"""Orchestrates parse -> deterministic rules -> citations -> append-only history."""
import json
import os
import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from .history import save_analysis
from .models import AIAnalysisRun
from .retrieval import search_knowledge
from .rule_engine import build_decision
from .text_parser import parse_operator_text
from .normalizer import normalize_analysis_input
from .llm import LLMClient, LLMUnavailable
from .state_machine import observation_plan, transition
from .confidence import assess_confidence
from .reasoning import build_reasoning_result
from .reasoning.diagnosis import build_diagnosis_result
from .explanation import build_operation_report
from .strategies import match_operator_strategies
from .strategy_ranking import rank_operator_strategies
from .strategy_impact import analyze_strategy_impact

def _delta(previous: AIAnalysisRun | None, current: dict) -> dict:
    if not previous:
        return {}
    pairs = (("spend", previous.input_spend, current.get("spend")),
             ("orders", previous.input_orders, current.get("orders")),
             ("revenue", previous.input_revenue, current.get("revenue")),
             ("roi", previous.input_current_roi, current.get("current_roi")),
             ("ctr", previous.input_ctr, current.get("ctr")),
             ("cvr", previous.input_cvr, current.get("cvr")),
             ("completion_rate", previous.input_completion_rate, current.get("official_completion_rate")))
    return {f"delta_{name}": round(now - old, 6) for name, old, now in pairs
            if old is not None and now is not None}

def _knowledge(rule_ids: list[str]) -> list[dict]:
    refs = []
    wanted = list(dict.fromkeys([*rule_ids, *(["R006"] if "R003" in rule_ids else [])]))
    for rule_id in wanted:
        match = next((item for item in search_knowledge(rule_id, top_k=5)
                      if item["rule_id"] == rule_id), None)
        if match:
            refs.append(match)
    return refs

def _safe_explanation_text(value: object, raw_text: str, decision: str | None = None,
                           evidence: dict | None = None) -> bool:
    if not isinstance(value, str) or re.search(r"已(?:关停|重建|调整|增加预算|修改目标)", value):
        return False
    if decision == "WAIT_OBSERVE" and re.search(r"关停|重建|调整目标|修改ROI|增加预算", value):
        return False
    allowed = set(re.findall(r"\d+(?:\.\d+)?", raw_text))
    if evidence:
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", json.dumps(evidence, ensure_ascii=False, default=str)))
    return set(re.findall(r"\d+(?:\.\d+)?", value)) <= allowed

def _grounded_number(text: str, key: str, value: int | float) -> bool:
    number = re.escape(str(value))
    if isinstance(value, float) and value.is_integer():
        number = rf"{int(value)}(?:\.0+)?"
    labels = {
        "spend": r"成本|消耗|花了|花费|spend",
        "orders": r"订单|单|出了|一单没有|一单都没|没有订单|没出单",
        "revenue": r"收入|营收|revenue",
        "current_roi": r"当前\s*ROI|现有\s*ROI|(?<!目标)\bROI",
        "target_roi": r"目标\s*(?:ROI)?",
        "ctr": r"CTR", "cvr": r"CVR",
        "official_completion_rate": r"(?:官方)?完播率",
    }[key]
    if key == "orders" and value == 0 and re.search(r"一单(?:都)?(?:没|没有)|没有订单|没出单|零单|0\s*单", text):
        return True
    if key == "current_roi":
        return parse_operator_text(text).get("current_roi") == value
    return bool(re.search(rf"(?:{labels})[^\S\r\n]*(?:[:：=]|是|为)?\s*(?<!\d){number}(?![\d.])", text, re.I)
                or key == "orders" and re.search(rf"(?<!\d){number}(?![\d.])\s*单", text))

def analyze_text(db: Session, campaign_id: str, text: str) -> dict:
    parsed = parse_operator_text(text, campaign_id)
    raw_llm_extraction = None
    llm = None
    llm_model = None
    llm_status = "fallback_parser"
    if all(os.getenv(name) for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")):
        try:
            llm = LLMClient()
            llm_model = getattr(llm, "model", os.getenv("LLM_MODEL"))
            try:
                extracted = llm.extract(text, allow_missing=True)
            except TypeError:
                # Compatibility with injected adapters using the original
                # single-argument test double signature.
                extracted = llm.extract(text)
            raw_llm_extraction = dict(extracted)
            llm_status = "live_success"
        except (LLMUnavailable, ValueError, KeyError, IndexError, TypeError, TimeoutError, OSError) as error:
            llm = None
            llm_status = "llm_error"
            print(f"LLM_EXTRACTION_ERROR={type(error).__name__}: {error}", flush=True)
    llm_candidates = None
    if raw_llm_extraction is not None:
        llm_candidates = dict(raw_llm_extraction)
        for key in ("spend", "orders", "revenue", "current_roi", "target_roi", "ctr", "cvr", "official_completion_rate"):
            candidate = llm_candidates.get(key)
            if candidate is not None and not _grounded_number(text, key, candidate):
                llm_candidates[key] = None
    parsed = normalize_analysis_input(text, parsed, llm_candidates)
    campaign = {"campaign_id": campaign_id, "campaign_name": parsed.get("campaign_name"),
                "link_type": parsed.get("link_type"),
                "source_type": "manual_entry", "currency": parsed.get("currency"), **{key: parsed.get(key) for key in
                ("spend", "orders", "revenue", "current_roi", "target_roi", "roi_policy")}}
    video = {"campaign_id": campaign_id, "source_type": "manual_entry",
             "report_date": parsed.get("report_time") or "manual_date_unspecified", "ctr": parsed.get("ctr"), "cvr": parsed.get("cvr"),
             "official_completion_rate": parsed.get("official_completion_rate"),
             "source_field_name": "operator_report_completion_rate" if "完播率" in text else None,
             "source_document": "operator_manual_text"}
    # User-facing reports commonly express rates as percentages; the rule engine
    # uses normalized ratios. Missing rates remain missing.
    for key in ("ctr", "cvr", "official_completion_rate"):
        if video[key] is not None:
            label = {"ctr": "CTR", "cvr": "CVR", "official_completion_rate": "完播率"}[key]
            has_percent = bool(re.search(label + r"\s*(?:是|为|[:：=])?\s*\d+(?:\.\d+)?\s*%", text, re.I))
            video[key] = video[key] / 100 if has_percent or video[key] > 1 else video[key]
    previous = db.scalars(select(AIAnalysisRun).where(AIAnalysisRun.campaign_id == campaign_id,
                                  AIAnalysisRun.source_type != "synthetic_demo").order_by(AIAnalysisRun.id.desc())).first()
    previous_state = None
    if previous and previous.snapshot:
        try:
            previous_state = json.loads(previous.snapshot.source_information or "{}").get("state")
        except (TypeError, json.JSONDecodeError):
            previous_state = None
    result = build_decision(campaign, video)
    if "完播率" in text and "官方完播率" not in text:
        result["uncertainties"].append("口述完播率未核验平台原始字段，需人工核对指标口径")
    if parsed.get("report_time") is None and any(video.get(key) is not None for key in ("ctr", "cvr", "official_completion_rate")):
        result["uncertainties"].append("视频指标的报表时间未提供；仅按本次人工报告判断，需核对时段口径")
    # A text report does not provide reliable samples for saturation; keep the
    # existing uncertainty rather than upgrading a phrase into a decision.
    refs = _knowledge(result["rules_used"])
    result["knowledge_refs"] = refs
    if not refs:
        result["uncertainties"].append("NO_KNOWLEDGE_EVIDENCE")
    delta_input = {**parsed, "ctr": video["ctr"], "cvr": video["cvr"],
                   "official_completion_rate": video["official_completion_rate"]}
    historical_delta = _delta(previous, delta_input)
    confidence, confidence_reasons = assess_confidence(parsed, historical_delta=historical_delta)
    result["confidence"] = confidence
    result["confidence_reasons"] = confidence_reasons
    if previous:
        result["historical_comparison"] = {"previous_analysis_id": previous.id,
            "previous_decision": previous.decision, "delta": historical_delta}
        if previous.decision == "WAIT_OBSERVE":
            changes = []
            if "delta_roi" in historical_delta:
                changes.append(f"ROI 变化 {historical_delta['delta_roi']:+g}")
            if "delta_orders" in historical_delta:
                changes.append(f"订单变化 {historical_delta['delta_orders']:+g}")
            result["historical_comparison"]["summary"] = (
                "上一轮建议继续观察；本轮" + "，".join(changes) + "。" if changes else
                "上一轮建议继续观察；本轮缺少可比指标。")
    else:
        result["historical_comparison"] = {"previous_analysis_id": None, "delta": {}}
    if result["decision"] == "WAIT_OBSERVE":
        result["next_observation"] = ["先放着不动", "继续观察成本变化", "继续观察新增订单", "比较下一轮 ROI", "检查 CTR、CVR 和官方完播率是否持续稳定"]
    else:
        result["next_observation"] = ["复核下一轮成本、订单、ROI 和视频指标"]
    result["summary"] = ("先放着不动，等待下一次数据。" if result["decision"] == "WAIT_OBSERVE"
                         else "当前分析由结构化输入和确定性规则生成，建议由运营人员确认后执行。")
    from_state, to_state, transition_trigger = transition(previous_state, result["decision"])
    result["state"] = to_state
    result["state_transition"] = {"from_state": from_state, "to_state": to_state,
                                   "trigger": transition_trigger}
    result["observation_plan"] = observation_plan(
        campaign_id, previous.id if previous else None, to_state,
        "WAIT_OBSERVE 需要下一轮比较当前指标和历史变化" if to_state == "WAIT_OBSERVE" else None)
    reasoning_input = {"current_analysis": parsed, "rule_result": result,
                       "decision": result["decision"], "state": to_state,
                       "reported_first_day": bool(re.search(r"第一天|首日", text)),
                       "historical_delta": historical_delta,
                       "historical_comparison": result["historical_comparison"],
                       "confidence": confidence, "knowledge_refs": refs, "video": video}
    result["reasoning_result"] = build_reasoning_result(reasoning_input)
    result["diagnosis_result"] = build_diagnosis_result(result["reasoning_result"], result)
    strategy_result = match_operator_strategies({**reasoning_input,
                                                  "reasoning_result": result["reasoning_result"]})
    result["strategy_refs"] = strategy_result["strategy_refs"]
    result["strategy_candidate_actions"] = strategy_result["candidate_actions"]
    result["strategy_ranking"] = rank_operator_strategies({**reasoning_input,
                                                             "reasoning_result": result["reasoning_result"],
                                                             "strategy_refs": result["strategy_refs"]})
    result["strategy_impact"] = analyze_strategy_impact(
        result["strategy_ranking"]["primary_strategy"], result["reasoning_result"], to_state)
    result["operation_report"] = build_operation_report(
        result["reasoning_result"], decision=result["decision"], state=to_state)
    result["explanation"] = None
    if llm:
        try:
            explanation = llm.explain({"current_snapshot": parsed,
                "previous_snapshot": serialize_run(previous) if previous else None,
                "historical_delta": historical_delta, "rule_result": result,
                "retrieved_knowledge": refs})
            explanation_evidence = {"current_snapshot": parsed, "historical_delta": historical_delta,
                                   "rule_result": result}
            result["explanation"] = {
                key: [item for item in explanation.get(key, []) if _safe_explanation_text(item, text, result["decision"], explanation_evidence)]
                if isinstance(explanation.get(key), list) else []
                for key in ("diagnosis", "recommendations", "next_observation", "uncertainties")
            }
            summary = explanation.get("summary")
            if result["decision"] == "WAIT_OBSERVE" and (not isinstance(summary, str) or "先放着不动" not in summary):
                raise ValueError("LLM 解释未遵守等待观察结论")
            if _safe_explanation_text(summary, text, result["decision"], explanation_evidence):
                result["summary"] = summary
            result["operation_report"] = build_operation_report(
                result["reasoning_result"], decision=result["decision"], state=to_state,
                llm_explanation=explanation)
        except (ValueError, KeyError, IndexError, TypeError, TimeoutError, OSError) as error:
            result["explanation"] = None
            llm_status = "fallback_explanation"
            print(f"LLM_EXPLANATION_ERROR={type(error).__name__}: {error}", flush=True)
    result["llm_status"] = llm_status
    result["llm_model"] = llm_model
    pattern_ids = [item["pattern_id"] for item in result["reasoning_result"].get("pattern_refs", [])]
    recommendation_snapshots = [
        {"strategy_id": strategy_id, "content": content,
         "reasoning_snapshot": result["reasoning_result"], "pattern_refs": pattern_ids}
        for strategy_id, content in zip(result["strategy_refs"], result["strategy_candidate_actions"])
    ]
    if not recommendation_snapshots:
        recommendation_snapshots = [
            {"strategy_id": None, "content": content,
             "reasoning_snapshot": result["reasoning_result"], "pattern_refs": pattern_ids}
            for content in result["recommendations"]
        ]
    run = save_analysis(db, campaign, video, {"parser": "deterministic_with_optional_llm", "raw_text": text,
                        "raw_llm_extraction": raw_llm_extraction,
                        "normalized_input": parsed,
                        "structured_input": parsed, "summary": result["summary"],
                        "explanation": result["explanation"],
                        "confidence": confidence, "confidence_reasons": confidence_reasons,
                        "reasoning_result": result["reasoning_result"],
                        "diagnosis_result": result["diagnosis_result"],
                        "strategy_refs": result["strategy_refs"],
                        "strategy_candidate_actions": result["strategy_candidate_actions"],
                        "strategy_ranking": result["strategy_ranking"],
                        "strategy_impact": result["strategy_impact"],
                        "operation_report": result["operation_report"],
                        "llm_status": llm_status, "llm_model": llm_model,
                        "historical_comparison": result["historical_comparison"]}, result,
                        raw_input_text=text, historical_delta=historical_delta,
                        state_transition=(from_state, to_state, transition_trigger),
                        recommendation_snapshots=recommendation_snapshots)
    result["analysis_id"] = run.id
    result["current_analysis"] = parsed
    return result

def serialize_run(run: AIAnalysisRun) -> dict:
    def load(value, fallback):
        try: return json.loads(value) if value else fallback
        except (TypeError, json.JSONDecodeError): return fallback
    source = load(run.snapshot.source_information if run.snapshot else None, {})
    fallback_input = {"spend": run.input_spend,
            "orders": run.input_orders, "revenue": run.input_revenue, "current_roi": run.input_current_roi,
            "target_roi": run.input_target_roi, "ctr": run.input_ctr, "cvr": run.input_cvr,
            "official_completion_rate": run.input_completion_rate}
    return {"analysis_id": run.id, "campaign_id": run.campaign_id, "decision": run.decision,
            "raw_input_text": source.get("raw_input_text"), "raw_llm_extraction": source.get("raw_llm_extraction"),
            "normalized_input": source.get("normalized_input", source.get("structured_input", fallback_input)),
            "current_analysis": source.get("normalized_input", source.get("structured_input", fallback_input)),
            "summary": source.get("summary"), "historical_comparison": source.get("historical_comparison", {}),
            "explanation": source.get("explanation"),
            "llm_status": source.get("llm_status"), "llm_model": source.get("llm_model"),
            "next_observation": source.get("next_observation", []), "rules_used": load(run.rules_used, []),
            "recommendations": load(run.recommendations, []), "knowledge_refs": source.get("retrieved_knowledge", []),
            "historical_delta": source.get("historical_delta", {}),
            "state": source.get("state"),
            "observation_plan": source.get("observation_plan"),
            "state_transition": source.get("state_transition"),
            "confidence": source.get("confidence"),
            "confidence_reasons": source.get("confidence_reasons", []),
            "reasoning_result": source.get("reasoning_result"),
            "diagnosis_result": source.get("diagnosis_result"),
            "strategy_refs": source.get("strategy_refs", []),
            "strategy_candidate_actions": source.get("strategy_candidate_actions", []),
            "strategy_ranking": source.get("strategy_ranking"),
            "strategy_impact": source.get("strategy_impact"),
            "operation_report": source.get("operation_report"),
            "uncertainties": load(run.uncertainties, []), "created_at": run.created_at}
