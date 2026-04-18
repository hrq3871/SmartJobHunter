#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Rule-guided semantic matching helpers.

The Claude Agent remains responsible for true LLM judgment. This module gives
the Python CLI a deterministic fallback that follows the same rubric: judge
role, domain, resume evidence, preferences, and risks instead of counting raw
keyword hits.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


DECISION_THRESHOLDS = {
    "conservative": 0.8,
    "moderate": 0.6,
    "aggressive": 0.4,
}

TERM_GROUPS = {
    "product": [
        "产品经理",
        "产品负责人",
        "产品规划",
        "产品设计",
        "产品策划",
        "需求分析",
        "prd",
        "product manager",
        "product owner",
    ],
    "ai": [
        "ai",
        "人工智能",
        "大模型",
        "llm",
        "gpt",
        "agent",
        "智能体",
        "rag",
        "生成式",
        "模型应用",
        "机器学习",
    ],
    "tob": [
        "tob",
        "to b",
        "b端",
        "企业级",
        "企业服务",
        "saas",
        "客户场景",
        "商业化",
    ],
    "data": [
        "数据分析",
        "指标",
        "看板",
        "sql",
        "ab实验",
        "a/b",
        "转化率",
        "数据驱动",
    ],
    "execution": [
        "跨部门",
        "跨团队",
        "项目管理",
        "推动",
        "落地",
        "0到1",
        "0-1",
        "上线",
    ],
}

NEGATIVE_ROLE_TERMS = [
    "标注",
    "审核",
    "质检",
    "排班",
    "外包",
    "客服",
    "销售",
    "供应商管理",
    "运营专员",
]


def _normalize(value: Any) -> str:
    return str(value or "").lower()


def _job_text(job: Dict[str, Any]) -> str:
    parts = [
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("category", ""),
        job.get("duty", ""),
        job.get("requirement", ""),
    ]
    return _normalize(" ".join(str(part or "") for part in parts))


def _profile_text(profile: Dict[str, Any]) -> str:
    keywords = " ".join(str(kw) for kw in profile.get("keywords", []) or [])
    return _normalize(f"{profile.get('intent', '')} {keywords} {profile.get('job_type', '')}")


def _hits(text: str, terms: Iterable[str]) -> List[str]:
    return [term for term in terms if _normalize(term) in text]


def _expected_groups(profile: Dict[str, Any]) -> List[str]:
    text = _profile_text(profile)
    expected = []
    for group, terms in TERM_GROUPS.items():
        if _hits(text, terms):
            expected.append(group)
    if not expected and profile.get("keywords"):
        expected.append("product")
    return expected


def _keyword_hits(job_text: str, profile: Dict[str, Any]) -> List[str]:
    return [
        str(keyword)
        for keyword in profile.get("keywords", []) or []
        if _normalize(keyword) in job_text
    ]


def _location_preference(profile: Dict[str, Any], job: Dict[str, Any]) -> Tuple[float, List[str]]:
    profile_text = _profile_text(profile)
    location = _normalize(job.get("location", ""))
    preferred_locations = [city for city in ["北京", "上海", "深圳", "广州", "杭州"] if city in profile_text]
    if not preferred_locations:
        return 0.05, []
    if any(city in location for city in preferred_locations):
        return 0.08, [f"地点符合偏好: {job.get('location', '')}"]
    return 0.0, [f"地点可能不符合偏好: {job.get('location', '')}"]


def match_job_intent(
    job: Dict[str, Any],
    profile: Dict[str, Any],
    decision_level: str = "moderate",
) -> Dict[str, Any]:
    """Judge whether a job should pass the intent filter.

    Returns a JSON-like dict compatible with the Claude semantic_filter prompt.
    """
    job_text = _job_text(job)
    title_text = _normalize(job.get("title", ""))
    expected = _expected_groups(profile)
    threshold = DECISION_THRESHOLDS.get(decision_level, DECISION_THRESHOLDS["moderate"])

    score = 0.0
    reasons: List[str] = []
    concerns: List[str] = []
    evidence: Dict[str, List[str]] = {}

    role_hits = _hits(f"{title_text} {job_text}", TERM_GROUPS["product"])
    if "product" in expected:
        if role_hits:
            score += 0.35
            evidence["core_role"] = role_hits[:4]
            reasons.append(f"核心岗位方向匹配: {', '.join(role_hits[:3])}")
        else:
            score += 0.05
            concerns.append("岗位未体现产品规划/需求分析等核心产品职责")
    elif role_hits:
        score += 0.15
        evidence["role_signal"] = role_hits[:3]

    domain_groups = [group for group in expected if group != "product"]
    if domain_groups:
        per_group = 0.38 / len(domain_groups)
        for group in domain_groups:
            group_hits = _hits(job_text, TERM_GROUPS[group])
            if group_hits:
                score += per_group
                evidence[group] = group_hits[:4]
                reasons.append(f"{group} 方向证据: {', '.join(group_hits[:3])}")
            else:
                concerns.append(f"岗位未明显体现 {group} 方向")

    keyword_hits = _keyword_hits(job_text, profile)
    if keyword_hits:
        score += min(0.12, 0.04 * len(keyword_hits))
        evidence["keywords"] = keyword_hits[:5]
        reasons.append(f"关键词可作为辅助证据: {', '.join(keyword_hits[:3])}")

    preference_score, preference_notes = _location_preference(profile, job)
    score += preference_score
    for note in preference_notes:
        if note.startswith("地点符合"):
            reasons.append(note)
        else:
            concerns.append(note)

    negative_hits = _hits(f"{title_text} {job_text}", NEGATIVE_ROLE_TERMS)
    if negative_hits and "product" in expected and not role_hits:
        score -= 0.15
        evidence["negative_role"] = negative_hits[:4]
        concerns.append(f"表面关键词可能是噪声，岗位更像: {', '.join(negative_hits[:3])}")

    score = max(0.0, min(1.0, score))
    should_keep = score >= threshold

    if not reasons:
        reasons.append("未找到足够的核心职责和领域证据")

    return {
        "match_score": round(score, 2),
        "match_reason": "；".join(reasons[:4]),
        "match_reasons": reasons,
        "should_keep": should_keep,
        "concerns": concerns,
        "evidence": evidence,
        "decision_level": decision_level,
        "threshold": threshold,
    }


def summarize_resume_ability(resume_text: str) -> Dict[str, Any]:
    """Build a lightweight ability profile from resume text."""
    text = _normalize(resume_text)
    explicit_skills: List[str] = []
    implicit_abilities: List[Dict[str, str]] = []
    highlights: List[str] = []
    gaps: List[str] = []

    for group, terms in TERM_GROUPS.items():
        group_hits = _hits(text, terms)
        explicit_skills.extend(group_hits)
        if group_hits:
            highlights.append(f"{group} 相关经验: {', '.join(group_hits[:4])}")

    if _hits(text, TERM_GROUPS["data"]):
        implicit_abilities.append({
            "ability": "数据分析",
            "evidence": "简历体现指标、看板、SQL 或转化率分析",
            "confidence": "medium",
        })
    if _hits(text, TERM_GROUPS["execution"]):
        implicit_abilities.append({
            "ability": "跨团队项目推进",
            "evidence": "简历体现跨部门推动、0到1或上线落地",
            "confidence": "high",
        })

    if "管理" not in text and "团队" not in text:
        gaps.append("简历未明确体现团队管理经验")

    return {
        "explicit_skills": sorted(set(explicit_skills)),
        "implicit_abilities": implicit_abilities,
        "highlights": highlights,
        "potential_gaps": gaps,
        "career_summary": "；".join(highlights[:3]) if highlights else "简历证据较少，需要人工复核",
        "raw_text": resume_text,
    }


def _resume_has_any(ability_profile: Dict[str, Any], terms: Iterable[str]) -> bool:
    text = _normalize(" ".join([
        " ".join(ability_profile.get("explicit_skills", [])),
        " ".join(ability_profile.get("highlights", [])),
        ability_profile.get("career_summary", ""),
        ability_profile.get("raw_text", ""),
    ]))
    return bool(_hits(text, terms))


def evaluate_job_fit(
    job: Dict[str, Any],
    profile: Dict[str, Any],
    resume_text: str = "",
    ability_profile: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Score candidate/job fit using a rubric aligned with the Agent prompt."""
    ability_profile = ability_profile or summarize_resume_ability(resume_text)
    intent_result = match_job_intent(job, profile, decision_level="moderate")
    job_text = _job_text(job)
    expected = _expected_groups(profile)

    role_hits = _hits(job_text, TERM_GROUPS["product"])
    core_role_fit = 30 if role_hits else 8 if "product" in expected else 15

    domain_fit = 0
    domain_reasons = []
    domain_groups = [group for group in expected if group != "product"]
    for group in domain_groups:
        group_hits = _hits(job_text, TERM_GROUPS[group])
        if group_hits:
            domain_fit += max(1, 25 // max(1, len(domain_groups)))
            domain_reasons.append(f"{group}: {', '.join(group_hits[:3])}")
    domain_fit = min(25, domain_fit)

    resume_fit = 0
    strong_matches = []
    potential_matches = []
    gaps = []

    for group in ["product", "ai", "tob", "data", "execution"]:
        job_hits = _hits(job_text, TERM_GROUPS[group])
        if not job_hits:
            continue
        if _resume_has_any(ability_profile, TERM_GROUPS[group]):
            resume_fit += 5
            strong_matches.append({
                "requirement": f"{group} capability",
                "candidate_evidence": f"简历体现 {group} 相关经验",
                "match_level": "strong",
            })
        else:
            potential_matches.append({
                "requirement": f"{group} capability",
                "candidate_evidence": "简历未直接命中，但可面试确认",
                "match_level": "potential",
                "suggestion": f"补充 {group} 相关案例",
            })
    resume_fit = min(25, resume_fit)

    preference_fit = 8 if not intent_result["concerns"] else 4
    evidence_quality = 7 if strong_matches else 3
    risk_penalty = 0

    if any("噪声" in concern for concern in intent_result["concerns"]):
        risk_penalty = 15
        gaps.append({
            "requirement": "核心岗位职责",
            "gap_type": "role_mismatch",
            "suggestion": "岗位关键词可能误导，建议跳过或人工复核",
        })
    for concern in intent_result["concerns"]:
        if "未明显体现" in concern or "未体现" in concern:
            gaps.append({
                "requirement": concern,
                "gap_type": "uncertain",
                "suggestion": "需要人工确认 JD 或补充简历证据",
            })

    score = core_role_fit + domain_fit + resume_fit + preference_fit + evidence_quality - risk_penalty
    score = max(0, min(100, int(score)))

    if score >= 85:
        recommendation = "strong_apply"
    elif score >= 70:
        recommendation = "apply"
    elif score >= 55:
        recommendation = "consider"
    else:
        recommendation = "skip"

    return {
        "score": score,
        "match_analysis": {
            "strong_matches": strong_matches,
            "potential_matches": potential_matches,
            "gaps": gaps,
        },
        "match_reasons": intent_result["match_reasons"] + domain_reasons,
        "suggestions": [
            "投递时突出与 JD 核心职责直接相关的项目证据",
            "面试前准备能量化结果的案例",
        ],
        "risk_warning": "；".join(intent_result["concerns"]) if intent_result["concerns"] else None,
        "recommendation": recommendation,
        "scoring_breakdown": {
            "core_role_fit": core_role_fit,
            "domain_fit": domain_fit,
            "resume_evidence": resume_fit,
            "preference_fit": preference_fit,
            "evidence_quality": evidence_quality,
            "risk_penalty": risk_penalty,
        },
        "semantic_filter": intent_result,
    }
