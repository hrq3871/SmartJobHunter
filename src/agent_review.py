"""Agent-led semantic review queue and result helpers.

Python owns mechanical facts and persistence. The current platform Agent owns
semantic scoring and final recommendation decisions, then writes review results
that this module validates and normalizes for reports.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


AGENT_SCORE_FIELDS = [
    "role_fit",
    "core_responsibility_fit",
    "domain_fit",
    "resume_evidence_fit",
    "seniority_fit",
    "risk_level",
    "apply_priority",
    "agent_score",
    "agent_decision",
]

PYTHON_FACT_FIELDS = [
    "url_status",
    "publish_time_status",
    "dedup_status",
    "jd_completeness",
    "crawl_quality",
    "fallback_candidate_rank",
]

AGENT_REVIEW_INSTRUCTIONS = (
    "Python 只能提供机械事实和候选排序；Agent 必须读取 JD、profile 和简历证据后，"
    "独立输出语义分数与最终推荐。正式推荐不得只依赖 python_fallback。"
)

AGENT_SCORING_RUBRIC = (
    "Agent 必须先判断岗位真实角色 role_family，再评分。"
    "role_fit 衡量岗位本体是否是目标角色；core_responsibility_fit 衡量核心职责是否是产品规划、"
    "需求分析、落地和指标闭环；domain_fit 衡量 AI/Agent/大模型是否真实出现在职责中；"
    "resume_evidence_fit 衡量简历证据能否支撑 JD；seniority_fit 衡量年限和复杂度；"
    "risk_level 衡量非目标角色、标题党和证据不足；apply_priority 给出投递优先级。"
    "如果岗位本体是公关传播、品牌、社媒、前端、后端、算法、工程师、销售、客服、审核或运营，"
    "而 profile 目标不是这些角色，应直接 reject 或给低分。"
)


def build_agent_review_queue(
    records: list[dict],
    profile: dict,
    queue_id: str,
    *,
    source_report: str | None = None,
) -> dict:
    """Build the JSON payload that the platform Agent must score."""
    items = []
    for index, record in enumerate(records, 1):
        raw_job = record.get("raw_job") or {}
        evaluation = record.get("evaluation") or {}
        items.append(
            {
                "record_id": record.get("run_record_id"),
                "fallback_candidate_rank": index,
                "job": {
                    "company": raw_job.get("company"),
                    "title": raw_job.get("title"),
                    "location": raw_job.get("location"),
                    "category": raw_job.get("category"),
                    "duty": raw_job.get("duty"),
                    "requirement": raw_job.get("requirement"),
                    "publish_time": raw_job.get("publish_time"),
                    "work_years": raw_job.get("work_years"),
                    "url": raw_job.get("url"),
                },
                "python_facts": _python_facts(record, index),
                "fallback": {
                    "source": evaluation.get("source"),
                    "score": evaluation.get("score"),
                    "final_decision": evaluation.get("final_decision"),
                    "semantic_decision": deepcopy(evaluation.get("semantic_decision") or {}),
                    "scoring_breakdown": deepcopy(evaluation.get("scoring_breakdown") or {}),
                    "risks": deepcopy(evaluation.get("risks") or []),
                },
            }
        )

    return {
        "queue_id": queue_id,
        "schema_version": 1,
        "source_report": source_report,
        "instructions": AGENT_REVIEW_INSTRUCTIONS,
        "scoring_rubric": AGENT_SCORING_RUBRIC,
        "agent_score_fields": AGENT_SCORE_FIELDS,
        "python_fact_fields": PYTHON_FACT_FIELDS,
        "profile": {
            "profile_id": profile.get("_profile_id") or profile.get("name"),
            "name": profile.get("name"),
            "target_roles": profile.get("target_roles") or [],
            "target_domains": profile.get("target_domains") or [],
            "must_have": profile.get("must_have") or [],
            "nice_to_have": profile.get("nice_to_have") or [],
            "avoid": profile.get("avoid") or profile.get("dealbreakers") or [],
        },
        "items": items,
        "required_output_schema": {
            "queue_id": queue_id,
            "results": [
                {
                    "record_id": "<from queue>",
                    "role_family": "<product_manager|frontend_engineer|communications|...>",
                    "agent_decision": "<strong_apply|apply|maybe|reject>",
                    "agent_score": "<0-100>",
                    "role_fit": "<1-5>",
                    "core_responsibility_fit": "<1-5>",
                    "domain_fit": "<1-5>",
                    "resume_evidence_fit": "<1-5>",
                    "seniority_fit": "<1-5>",
                    "risk_level": "<1-5>",
                    "apply_priority": "<1-5>",
                    "risk_tags": ["<optional>"],
                    "jd_evidence": ["<quoted or summarized JD evidence>"],
                    "resume_evidence": ["<resume evidence>"],
                    "reason": "<short final rationale>",
                    "confidence": "<high|medium|low>",
                }
            ],
        },
    }


def write_agent_review_queue(queue: dict, path: str | Path) -> Path:
    """Persist an Agent review queue as UTF-8 JSON."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def load_agent_review_results(
    path: str | Path,
    *,
    required_record_ids: list[str] | set[str] | None = None,
) -> dict[str, dict]:
    """Load and validate Agent-authored review results."""
    result_path = Path(path)
    data = json.loads(result_path.read_text(encoding="utf-8"))
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise ValueError("Agent review results must contain a results list")

    normalized: dict[str, dict] = {}
    for item in results:
        if not isinstance(item, dict) or not item.get("record_id"):
            raise ValueError("Each Agent review result must include record_id")
        normalized[str(item["record_id"])] = normalize_agent_review_result(item)

    required = {str(record_id) for record_id in (required_record_ids or [])}
    missing = sorted(required - set(normalized))
    if missing:
        raise ValueError(f"Missing Agent review results for: {', '.join(missing)}")
    return normalized


def normalize_agent_review_result(item: dict[str, Any]) -> dict[str, Any]:
    """Convert Agent JSON into the common report evaluation schema."""
    decision = str(item.get("agent_decision") or "").strip() or "reject"
    score = _to_int(item.get("agent_score"), default=0)
    should_keep = decision in {"strong_apply", "apply", "maybe"} and score >= 55
    role_family = str(item.get("role_family") or "").strip()
    risk_tags = [str(tag) for tag in item.get("risk_tags") or [] if str(tag).strip()]
    jd_evidence = [str(value) for value in item.get("jd_evidence") or [] if str(value).strip()]
    resume_evidence = [
        str(value) for value in item.get("resume_evidence") or [] if str(value).strip()
    ]
    reason = str(item.get("reason") or "").strip()

    matched_evidence = []
    for jd_item in jd_evidence:
        matched_evidence.append(
            {
                "job_requirement": jd_item,
                "resume_evidence": "; ".join(resume_evidence) if resume_evidence else "",
                "strength": "agent_review",
            }
        )

    risks = list(risk_tags)
    if item.get("risk_level") is not None:
        risks.append(f"risk_level={item.get('risk_level')}")

    return {
        "score": score,
        "recommendation": decision,
        "semantic_decision": {
            "should_keep": should_keep,
            "match_score": round(score / 100, 2),
            "match_reasons": [reason] if reason else [],
            "concerns": risks,
            "evidence": {
                "role_family": [role_family] if role_family else [],
                "jd_evidence": jd_evidence,
                "resume_evidence": resume_evidence,
                "risk_tags": risk_tags,
            },
        },
        "matched_evidence": matched_evidence,
        "gaps": deepcopy(item.get("gaps") or []),
        "risks": risks,
        "risk_warning": "; ".join(risks) if risks else None,
        "scoring_breakdown": {
            "role_fit": _to_int(item.get("role_fit")),
            "core_responsibility_fit": _to_int(item.get("core_responsibility_fit")),
            "domain_fit": _to_int(item.get("domain_fit")),
            "resume_evidence_fit": _to_int(item.get("resume_evidence_fit")),
            "seniority_fit": _to_int(item.get("seniority_fit")),
            "risk_level": _to_int(item.get("risk_level")),
            "apply_priority": _to_int(item.get("apply_priority")),
            "agent_score": score,
            "agent_decision": decision,
            "confidence": item.get("confidence"),
        },
    }


def _python_facts(record: dict, rank: int) -> dict:
    raw_job = record.get("raw_job") or {}
    processing = record.get("processing") or {}
    url = str(raw_job.get("url") or "")
    return {
        "url_status": {
            "has_url": bool(url),
            "looks_http": url.startswith(("http://", "https://")),
        },
        "publish_time_status": {
            "publish_time": raw_job.get("publish_time"),
            "processing_stage": processing.get("stage"),
            "processing_reason": processing.get("reason"),
        },
        "dedup_status": {
            "job_hash": record.get("job_hash"),
        },
        "jd_completeness": {
            "has_title": bool(raw_job.get("title")),
            "has_company": bool(raw_job.get("company")),
            "has_duty": bool(raw_job.get("duty")),
            "has_requirement": bool(raw_job.get("requirement")),
        },
        "crawl_quality": {
            "source": raw_job.get("source"),
            "original_job_id": record.get("original_job_id"),
        },
        "fallback_candidate_rank": rank,
    }


def _to_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
