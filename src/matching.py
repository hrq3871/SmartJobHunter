#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""General-purpose matching helpers used as Python fallback.

The agent platform remains responsible for true semantic judgment. This module
only provides a deterministic, conservative fallback for CLI runs and tests. It
must derive matching signals from the user's profile, resume evidence, and job
content instead of assuming a product-manager target role.
"""

from __future__ import annotations

import re
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
        "产品总监",
        "产品专家",
        "产品规划",
        "产品设计",
        "产品策划",
        "需求分析",
        "prd",
        "product manager",
        "product owner",
    ],
    "data": [
        "数据分析",
        "数据分析师",
        "商业分析",
        "指标",
        "看板",
        "sql",
        "python",
        "ab实验",
        "a/b",
        "转化率",
        "数据驱动",
    ],
    "engineering": [
        "工程师",
        "后端",
        "前端",
        "客户端",
        "开发",
        "研发",
        "架构",
        "接口",
        "数据库",
        "分布式",
        "服务端",
        "java",
        "python",
        "go",
        "c++",
    ],
    "design": [
        "设计师",
        "交互设计",
        "视觉设计",
        "用户体验",
        "ux",
        "ui",
    ],
    "marketing": [
        "市场",
        "增长",
        "品牌",
        "投放",
        "内容营销",
        "用户增长",
    ],
    "operations": [
        "运营",
        "用户运营",
        "内容运营",
        "活动运营",
        "策略运营",
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
    "电话销售",
    "供应商管理",
    "运营",
    "用户运营",
    "市场营销",
    "运营专员",
]


def _normalize(value: Any) -> str:
    return str(value or "").lower()


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        normalized = _normalize(item).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(str(item).strip())
    return result


def _expand_term(term: str) -> List[str]:
    """Generate conservative variants for matching Chinese/English role terms."""
    normalized = _normalize(term).strip()
    if not normalized:
        return []

    variants = [normalized]
    replacements = [
        ("数据分析师", "数据分析"),
        ("商业分析师", "商业分析"),
        ("后端开发工程师", "后端开发"),
        ("前端开发工程师", "前端开发"),
        ("开发工程师", "开发"),
        ("算法工程师", "算法"),
        ("接口开发", "接口"),
        ("分布式系统", "分布式"),
        ("数据分析项目", "数据分析"),
        ("实习生", "实习"),
        ("工程师", ""),
    ]
    for old, new in replacements:
        if old in normalized:
            candidate = normalized.replace(old, new).strip()
            if len(candidate) >= 2:
                variants.append(candidate)

    if normalized == "agent":
        variants.append("智能体")
    if normalized == "llm":
        variants.append("大模型")
    if normalized == "sql":
        variants.append("取数")
    if normalized == "产品经理":
        variants.extend([
            "产品负责人",
            "产品总监",
            "产品专家",
            "产品策划",
            "产品规划",
            "产品经验",
            "需求分析",
            "prd",
            "product manager",
        ])
    if "产品经理" in normalized and normalized != "产品经理":
        prefix = normalized.replace("产品经理", "").strip()
        if prefix:
            variants.extend([
                f"{prefix}产品",
                f"{prefix}产品负责人",
                f"{prefix}产品专家",
            ])

    return _dedupe(variants)


def _expand_terms(terms: Iterable[str]) -> List[str]:
    expanded: List[str] = []
    for term in terms:
        expanded.extend(_expand_term(str(term)))
    return _dedupe(expanded)


def _hits(text: str, terms: Iterable[str]) -> List[str]:
    normalized = _normalize(text)
    return [term for term in terms if _normalize(term) in normalized]


def _unique_hits(text: str, terms: Iterable[str]) -> List[str]:
    return sorted(set(_hits(text, terms)))


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


def _job_core_text(job: Dict[str, Any]) -> str:
    return _normalize(" ".join([
        str(job.get("duty", "") or ""),
        str(job.get("requirement", "") or ""),
    ]))


def _profile_text(profile: Dict[str, Any]) -> str:
    fields = [
        profile.get("name", ""),
        profile.get("intent", ""),
        profile.get("job_type", ""),
        " ".join(_as_list(profile.get("keywords"))),
        " ".join(_as_list(profile.get("target_roles"))),
        " ".join(_as_list(profile.get("target_domains"))),
        " ".join(_as_list(profile.get("must_have"))),
        " ".join(_as_list(profile.get("nice_to_have"))),
        " ".join(_as_list(profile.get("employment_types"))),
    ]
    return _normalize(" ".join(str(field or "") for field in fields))


def _terms_from_groups(text: str, groups: Iterable[str] | None = None) -> List[str]:
    selected = groups or TERM_GROUPS.keys()
    terms: List[str] = []
    for group in selected:
        group_terms = TERM_GROUPS.get(group, [])
        terms.extend(_hits(text, group_terms))
    return _dedupe(terms)


def _profile_target_terms(profile: Dict[str, Any]) -> Dict[str, List[str]]:
    profile_text = _profile_text(profile)

    target_roles = _as_list(profile.get("target_roles"))
    if not target_roles:
        role_groups = ["product", "data", "engineering", "design", "marketing", "operations"]
        target_roles = _terms_from_groups(profile_text, role_groups)
    if not target_roles and profile.get("name"):
        target_roles = [str(profile.get("name"))]

    must_have = _as_list(profile.get("must_have"))
    if not must_have:
        must_have = _as_list(profile.get("keywords"))

    target_domains = _as_list(profile.get("target_domains"))
    if not target_domains:
        domain_groups = ["ai", "tob", "data", "execution"]
        target_domains = [
            term
            for term in _terms_from_groups(profile_text, domain_groups)
            if term not in target_roles and term not in must_have
        ]

    return {
        "target_roles": _expand_terms(target_roles),
        "target_domains": _expand_terms(target_domains),
        "must_have": _expand_terms(must_have),
        "nice_to_have": _expand_terms(_as_list(profile.get("nice_to_have"))),
        "avoid": _expand_terms(
            _as_list(profile.get("avoid"))
            + _as_list(profile.get("dealbreakers"))
            + _as_list(profile.get("exclude_keywords"))
        ),
        "locations": _expand_terms(_as_list(profile.get("locations"))),
    }


def _expected_groups(profile: Dict[str, Any]) -> List[str]:
    """Compatibility helper for older tests and reports."""
    text = _profile_text(profile)
    expected = []
    for group, terms in TERM_GROUPS.items():
        if _hits(text, terms):
            expected.append(group)
    return expected


def _keyword_hits(job_text: str, profile: Dict[str, Any]) -> List[str]:
    return [
        str(keyword)
        for keyword in profile.get("keywords", []) or []
        if _normalize(keyword) in job_text
    ]


def _profile_exclude_terms(profile: Dict[str, Any]) -> List[str]:
    return _profile_target_terms(profile)["avoid"]


def _title_has_target_role(job: Dict[str, Any], profile_terms: Dict[str, List[str]]) -> bool:
    title = _normalize(job.get("title", ""))
    return bool(_hits(title, profile_terms["target_roles"]))


def _title_has_product_role(job: Dict[str, Any]) -> bool:
    title = _normalize(job.get("title", ""))
    return bool(_hits(title, TERM_GROUPS["product"]))


def _is_strong_role_term(term: str) -> bool:
    normalized = _normalize(term)
    strong_markers = [
        "经理",
        "负责人",
        "专家",
        "总监",
        "工程师",
        "分析师",
        "设计师",
        "顾问",
        "架构师",
        "manager",
        "owner",
        "engineer",
        "analyst",
        "designer",
        "consultant",
    ]
    return any(marker in normalized for marker in strong_markers)


def _profile_targets_negative_role(profile_terms: Dict[str, List[str]], negative_hit: str) -> bool:
    return any(negative_hit in _normalize(term) for term in profile_terms["target_roles"])


def _title_negative_role_conflict(job: Dict[str, Any], profile_terms: Dict[str, List[str]]) -> List[str]:
    """Detect titles that are likely a different role family despite broad target terms."""
    title = _normalize(job.get("title", ""))
    title_negative_hits = _unique_hits(title, NEGATIVE_ROLE_TERMS)
    if not title_negative_hits:
        return []

    conflicts = []
    strong_target_hits = [
        term for term in profile_terms["target_roles"]
        if _normalize(term) in title and _is_strong_role_term(term)
    ]
    for hit in title_negative_hits:
        if _profile_targets_negative_role(profile_terms, hit):
            continue
        if strong_target_hits:
            continue
        conflicts.append(hit)
    return conflicts


def _profile_exclude_hits(job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    profile_terms = _profile_target_terms(profile)
    terms = profile_terms["avoid"]
    if not terms:
        return {"hits": [], "title_hits": [], "hard": False}

    title_hits = _unique_hits(_normalize(job.get("title", "")), terms)
    all_hits = _unique_hits(_job_text(job), terms)
    hard = bool(title_hits and not _title_has_target_role(job, profile_terms))

    return {
        "hits": all_hits,
        "title_hits": title_hits,
        "hard": hard,
    }


def _location_preference(profile: Dict[str, Any], job: Dict[str, Any]) -> Tuple[float, List[str]]:
    profile_terms = _profile_target_terms(profile)
    location = _normalize(job.get("location", ""))
    preferred_locations = profile_terms["locations"]
    if not preferred_locations:
        fallback_text = _profile_text(profile)
        preferred_locations = [
            city for city in ["北京", "上海", "深圳", "广州", "杭州"] if city in fallback_text
        ]
    if not preferred_locations:
        return 0.05, []
    if any(city in location for city in preferred_locations):
        return 0.08, [f"地点符合偏好: {job.get('location', '')}"]
    return 0.0, [f"地点可能不符合偏好: {job.get('location', '')}"]


def _term_evidence(job: Dict[str, Any], terms: Iterable[str]) -> Dict[str, Any]:
    expanded_terms = _expand_terms(terms)
    title_hits = _unique_hits(_normalize(job.get("title", "")), expanded_terms)
    category_hits = _unique_hits(_normalize(job.get("category", "")), expanded_terms)
    duty_hits = _unique_hits(_normalize(job.get("duty", "")), expanded_terms)
    requirement_hits = _unique_hits(_normalize(job.get("requirement", "")), expanded_terms)
    all_hits = _dedupe(title_hits + category_hits + duty_hits + requirement_hits)
    core_hits = _dedupe(duty_hits + requirement_hits)
    title_only = bool(all_hits and not core_hits)

    if not all_hits:
        strength = 0.0
    else:
        strength = 0.25
        if title_hits:
            strength += 0.18
        if category_hits:
            strength += 0.08
        if core_hits:
            strength += 0.32
        strength += min(0.17, 0.04 * max(0, len(all_hits) - 1))
        strength = min(1.0, strength)

    return {
        "hits": all_hits,
        "title_hits": title_hits,
        "category_hits": category_hits,
        "duty_hits": duty_hits,
        "requirement_hits": requirement_hits,
        "core_hits": core_hits,
        "title_only": title_only,
        "strength": strength,
    }


def match_job_intent(
    job: Dict[str, Any],
    profile: Dict[str, Any],
    decision_level: str = "moderate",
) -> Dict[str, Any]:
    """Judge whether a job should pass the intent filter."""
    job_text = _job_text(job)
    profile_terms = _profile_target_terms(profile)
    threshold = DECISION_THRESHOLDS.get(decision_level, DECISION_THRESHOLDS["moderate"])

    score = 0.0
    reasons: List[str] = []
    concerns: List[str] = []
    evidence: Dict[str, List[str]] = {}

    role_evidence = _term_evidence(job, profile_terms["target_roles"])
    if role_evidence["hits"]:
        role_score = 0.18 + 0.24 * role_evidence["strength"]
        score += min(0.42, role_score)
        evidence["target_role"] = role_evidence["hits"][:5]
        reasons.append(f"目标岗位方向匹配: {', '.join(role_evidence['hits'][:3])}")
    elif profile_terms["target_roles"]:
        concerns.append("岗位标题和核心职责未明显体现目标岗位方向")

    must_evidence = _term_evidence(job, profile_terms["must_have"])
    if must_evidence["hits"]:
        must_score = min(0.36, 0.12 * len(must_evidence["hits"]))
        if must_evidence["core_hits"]:
            must_score += 0.08
        if must_evidence["title_only"]:
            must_score -= 0.08
            concerns.append(
                "核心要求只有标题或孤立关键词证据，需复核岗位职责是否真的匹配"
            )
        score += max(0.0, min(0.42, must_score))
        evidence["must_have"] = must_evidence["hits"][:6]
        reasons.append(f"关键要求命中: {', '.join(must_evidence['hits'][:4])}")
    elif profile_terms["must_have"]:
        concerns.append("岗位未明显体现 profile 中的关键要求")

    domain_evidence = _term_evidence(job, profile_terms["target_domains"])
    if domain_evidence["hits"]:
        domain_score = 0.06 + 0.14 * domain_evidence["strength"]
        if domain_evidence["title_only"]:
            domain_score *= 0.55
            concerns.append(
                f"目标领域只有弱证据，可能只是标题或孤立关键词: {', '.join(domain_evidence['hits'][:3])}"
            )
        score += min(0.2, domain_score)
        evidence["target_domains"] = domain_evidence["hits"][:5]
        reasons.append(f"目标领域证据: {', '.join(domain_evidence['hits'][:3])}")

    nice_evidence = _term_evidence(job, profile_terms["nice_to_have"])
    if nice_evidence["hits"]:
        score += min(0.08, 0.025 * len(nice_evidence["hits"]))
        evidence["nice_to_have"] = nice_evidence["hits"][:5]

    keyword_hits = _keyword_hits(job_text, profile)
    if keyword_hits:
        score += min(0.06, 0.02 * len(keyword_hits))
        evidence["keywords"] = keyword_hits[:5]

    preference_score, preference_notes = _location_preference(profile, job)
    score += preference_score
    for note in preference_notes:
        if note.startswith("地点符合"):
            reasons.append(note)
        else:
            concerns.append(note)

    exclude_result = _profile_exclude_hits(job, profile)
    if exclude_result["hits"]:
        evidence["excluded_terms"] = exclude_result["hits"][:5]
        if exclude_result["hard"]:
            score -= 0.6
            concerns.append(
                f"岗位标题命中排除方向: {', '.join(exclude_result['title_hits'][:3])}"
            )
        else:
            score -= 0.18
            concerns.append(
                f"岗位内容命中排除词，需人工复核: {', '.join(exclude_result['hits'][:3])}"
            )

    title_negative_conflicts = _title_negative_role_conflict(job, profile_terms)
    if title_negative_conflicts:
        evidence["negative_role"] = _dedupe(
            evidence.get("negative_role", []) + title_negative_conflicts
        )[:5]
        score -= 0.38
        concerns.append(
            f"岗位标题更像非目标角色: {', '.join(title_negative_conflicts[:3])}"
        )

    negative_hits = _hits(job_text, NEGATIVE_ROLE_TERMS)
    if negative_hits and not role_evidence["hits"]:
        score -= 0.25
        evidence["negative_role"] = _dedupe(
            evidence.get("negative_role", []) + negative_hits[:4]
        )[:5]
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
        "exclude_severity": "hard" if exclude_result["hard"] else "soft" if exclude_result["hits"] else None,
        "decision_level": decision_level,
        "threshold": threshold,
        "fallback_quality": "coarse",
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
            implicit_abilities.append({
                "ability": group,
                "evidence": f"简历体现 {', '.join(group_hits[:4])}",
                "confidence": "medium",
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
    return bool(_hits(text, _expand_terms(terms)))


def _job_group_evidence(job: Dict[str, Any], group: str) -> Dict[str, Any]:
    return _term_evidence(job, TERM_GROUPS[group])


def _score_target_role_fit(job: Dict[str, Any], profile_terms: Dict[str, List[str]]) -> Tuple[int, Dict[str, Any]]:
    evidence = _term_evidence(job, profile_terms["target_roles"])
    if not profile_terms["target_roles"]:
        return 12, evidence
    if not evidence["hits"]:
        return 5, evidence
    score = 8
    if evidence["title_hits"]:
        score += 10
    if evidence["category_hits"]:
        score += 3
    if evidence["core_hits"]:
        score += 7
    return max(0, min(25, score)), evidence


def _score_core_responsibility_fit(
    job: Dict[str, Any],
    profile_terms: Dict[str, List[str]],
) -> Tuple[int, Dict[str, Any]]:
    core_terms = profile_terms["must_have"] + profile_terms["nice_to_have"]
    evidence = _term_evidence(job, core_terms)
    if not core_terms:
        return 6, evidence
    if not evidence["hits"]:
        return 0, evidence
    score = min(10, 3 * len(evidence["hits"]))
    if evidence["core_hits"]:
        score += 5
    if evidence["title_only"]:
        score -= 4
    return max(0, min(10, score)), evidence


def _score_domain_fit(
    job: Dict[str, Any],
    expected: List[str] | Dict[str, List[str]],
) -> Tuple[int, List[str], Dict[str, float]]:
    if isinstance(expected, dict):
        domain_terms = expected.get("target_domains", [])
    else:
        domain_terms = []
        for group in expected:
            if group != "product":
                domain_terms.extend(TERM_GROUPS.get(group, []))

    evidence = _term_evidence(job, domain_terms)
    if not domain_terms:
        return 0, [], {}
    if not evidence["hits"]:
        return 0, [], {"target_domains": 0.0}

    score = int(round(20 * evidence["strength"]))
    if evidence["title_only"]:
        score = min(score, 8)
    reasons = [f"领域匹配: {', '.join(evidence['hits'][:3])} ({score}/20)"]
    return min(20, score), reasons, {"target_domains": evidence["strength"]}


def _resume_source_snippets(
    ability_profile: Dict[str, Any],
    terms: Iterable[str],
    limit: int = 2,
) -> List[str]:
    raw_text = str(ability_profile.get("raw_text", "") or "")
    normalized_terms = [_normalize(term) for term in _expand_terms(terms) if _normalize(term)]
    if not raw_text or not normalized_terms:
        return []

    chunks = [
        re.sub(r"\s+", " ", chunk).strip(" ，,。；;：:")
        for chunk in re.split(r"[\n。；;]", raw_text)
    ]

    snippets: List[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        normalized_chunk = _normalize(chunk)
        if any(term in normalized_chunk for term in normalized_terms):
            snippets.append(chunk)
        if len(snippets) >= limit:
            break

    return snippets


def _score_resume_fit(
    job: Dict[str, Any],
    ability_profile: Dict[str, Any],
    profile_terms: Dict[str, List[str]] | None = None,
) -> Tuple[int, List[Dict[str, str]], List[Dict[str, str]], Dict[str, float]]:
    profile_terms = profile_terms or {"target_roles": [], "must_have": [], "target_domains": []}
    required_terms = _dedupe(
        profile_terms.get("target_roles", [])
        + profile_terms.get("must_have", [])
        + profile_terms.get("target_domains", [])
    )

    job_evidence = _term_evidence(job, required_terms)
    job_terms = job_evidence["hits"] or required_terms
    if not job_terms:
        return 0, [], [], {}

    strong_matches: List[Dict[str, str]] = []
    potential_matches: List[Dict[str, str]] = []
    resume_strengths: Dict[str, float] = {}
    matched_count = 0

    for term in _dedupe(job_terms):
        term_variants = _expand_term(term)
        if _resume_has_any(ability_profile, term_variants):
            matched_count += 1
            snippets = _resume_source_snippets(ability_profile, term_variants)
            candidate_evidence = (
                f"简历证据: {'；'.join(snippets)}"
                if snippets
                else f"简历体现相关经验: {term}"
            )
            match = {
                "requirement": term,
                "candidate_evidence": candidate_evidence,
                "match_level": "strong",
            }
            strong_matches.append(match)
            resume_strengths[term] = 1.0
        else:
            potential_matches.append({
                "requirement": term,
                "candidate_evidence": "简历未直接命中，但可面试确认",
                "match_level": "potential",
                "suggestion": f"补充 {term} 相关案例",
            })
            resume_strengths[term] = 0.0

    ratio = matched_count / max(1, len(_dedupe(job_terms)))
    score = int(round(25 * ratio))
    if strong_matches and score < 12:
        score = 12
    return min(25, score), strong_matches, potential_matches, resume_strengths


def _score_core_role_fit(job: Dict[str, Any], expected: List[str]) -> int:
    terms: List[str] = []
    for group in expected:
        terms.extend(TERM_GROUPS.get(group, []))
    score, _ = _score_target_role_fit(job, {"target_roles": _dedupe(terms)})
    return score


def _score_preference_fit(intent_result: Dict[str, Any]) -> int:
    concerns = intent_result["concerns"]
    if not concerns:
        return 10
    if any("地点" in concern for concern in concerns):
        return 4
    if any("排除" in concern for concern in concerns):
        return 3
    return 7


def _score_evidence_quality(
    job: Dict[str, Any],
    strong_matches: List[Dict[str, str]],
    potential_matches: List[Dict[str, str]],
) -> int:
    duty = _normalize(job.get("duty", ""))
    requirement = _normalize(job.get("requirement", ""))
    jd_detail = 0
    if len(duty) >= 25:
        jd_detail += 2
    if len(requirement) >= 25:
        jd_detail += 2

    resume_detail = min(4, len(strong_matches))
    if potential_matches and strong_matches:
        resume_detail += 1

    clarity = 2 if strong_matches else 0
    return min(10, jd_detail + resume_detail + clarity)


def evaluate_job_fit(
    job: Dict[str, Any],
    profile: Dict[str, Any],
    resume_text: str = "",
    ability_profile: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Score candidate/job fit using a general fallback rubric."""
    ability_profile = ability_profile or summarize_resume_ability(resume_text)
    profile_terms = _profile_target_terms(profile)
    intent_result = match_job_intent(job, profile, decision_level="moderate")

    target_role_fit, role_evidence = _score_target_role_fit(job, profile_terms)
    core_responsibility_fit, core_evidence = _score_core_responsibility_fit(job, profile_terms)
    domain_fit, domain_reasons, domain_strengths = _score_domain_fit(job, profile_terms)
    resume_fit, strong_matches, potential_matches, _ = _score_resume_fit(
        job,
        ability_profile,
        profile_terms,
    )

    preference_fit = _score_preference_fit(intent_result)
    evidence_quality = _score_evidence_quality(job, strong_matches, potential_matches)
    risk_penalty = 0
    gaps = []

    if not role_evidence["hits"] and profile_terms["target_roles"]:
        risk_penalty += 8
        gaps.append({
            "requirement": "目标岗位方向",
            "gap_type": "role_mismatch",
            "suggestion": "岗位核心角色与 profile 目标岗位不够一致，建议人工复核",
        })

    if core_evidence["title_only"]:
        risk_penalty += 6
        gaps.append({
            "requirement": "核心职责证据",
            "gap_type": "weak_core_evidence",
            "suggestion": "关键要求只在标题或孤立字段出现，职责证据不足",
        })

    exclude_severity = intent_result.get("exclude_severity")
    if exclude_severity == "hard":
        risk_penalty += 18
        gaps.append({
            "requirement": "岗位方向排除",
            "gap_type": "excluded_role",
            "suggestion": "岗位标题命中 profile 排除词，默认不作为优先投递岗位",
        })
    elif exclude_severity == "soft":
        risk_penalty += 6
        gaps.append({
            "requirement": "岗位内容命中排除词",
            "gap_type": "review_needed",
            "suggestion": "岗位仍可能匹配，但需要人工确认排除词是否只是协作背景",
        })

    if any("噪声" in concern for concern in intent_result["concerns"]):
        risk_penalty += 12
        gaps.append({
            "requirement": "核心岗位职责",
            "gap_type": "keyword_noise",
            "suggestion": "岗位关键词可能误导，建议跳过或人工复核",
        })

    if any("非目标角色" in concern for concern in intent_result["concerns"]):
        risk_penalty += 12
        gaps.append({
            "requirement": "岗位角色",
            "gap_type": "role_family_conflict",
            "suggestion": "岗位标题更像运营、销售、客服、标注等非目标角色，建议跳过",
        })

    for concern in intent_result["concerns"]:
        if "未明显体现" in concern or "未体现" in concern:
            gaps.append({
                "requirement": concern,
                "gap_type": "uncertain",
                "suggestion": "需要人工确认 JD 或补充简历证据",
            })

    risk_penalty = min(20, risk_penalty)

    score = (
        target_role_fit
        + domain_fit
        + resume_fit
        + preference_fit
        + evidence_quality
        + core_responsibility_fit
        - risk_penalty
    )
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
            "target_role_fit": target_role_fit,
            "core_responsibility_fit": core_responsibility_fit,
            "core_role_fit": target_role_fit,
            "domain_fit": domain_fit,
            "resume_evidence": resume_fit,
            "preference_fit": preference_fit,
            "evidence_quality": evidence_quality,
            "risk_penalty": risk_penalty,
            "fallback_quality": "coarse",
            "domain_strengths": domain_strengths,
        },
        "semantic_filter": intent_result,
    }
