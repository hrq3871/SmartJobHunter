#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.matching import evaluate_job_fit, match_job_intent, summarize_resume_ability


def test_intent_match_uses_semantic_evidence_not_only_keyword_hits():
    profile = {
        "intent": "寻找 AI Agent 和大模型应用方向的产品经理岗位，偏好 ToB SaaS。",
        "keywords": ["AI产品", "大模型", "Agent"],
    }
    job = {
        "title": "智能体平台产品负责人",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责企业级智能体平台的产品规划，设计 LLM 应用工作流，推动客户场景落地。",
        "requirement": "3年以上 B 端产品经验，理解模型能力边界，有数据分析经验。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is True
    assert result["match_score"] >= 0.6
    assert any("智能体" in reason or "LLM" in reason for reason in result["match_reasons"])


def test_intent_match_rejects_surface_keyword_noise():
    profile = {
        "intent": "寻找 AI 产品经理岗位，偏好大模型应用和 Agent 方向。",
        "keywords": ["AI", "大模型", "Agent"],
    }
    job = {
        "title": "AI 标注运营专员",
        "company": "Example",
        "location": "上海",
        "category": "运营",
        "duty": "负责文本标注团队排班、质检和供应商管理，按规则完成数据标注交付。",
        "requirement": "接受倒班，有外包管理经验优先。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is False
    assert result["match_score"] < 0.6
    assert result["concerns"]


def test_evaluate_job_fit_scores_core_requirements_with_resume_evidence():
    profile = {
        "intent": "寻找 AI Agent 和大模型应用方向的产品经理岗位，偏好 ToB SaaS。",
        "keywords": ["AI产品", "大模型", "Agent", "ToB"],
    }
    resume = """
    5年 ToB SaaS 产品经验，主导企业知识库 AI 助手从0到1上线。
    负责需求分析、PRD、跨部门推进和客户访谈，搭建数据看板优化转化率。
    熟悉 LLM 应用、RAG、Agent 工作流和产品指标体系。
    """
    ability_profile = summarize_resume_ability(resume)
    job = {
        "title": "大模型 Agent 产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责大模型 Agent 产品规划、需求分析和商业化落地。",
        "requirement": "需要 ToB 产品经验、LLM 应用理解、数据分析和跨团队推动能力。",
    }

    result = evaluate_job_fit(job, profile, resume_text=resume, ability_profile=ability_profile)

    assert result["score"] >= 80
    assert result["recommendation"] in {"strong_apply", "apply"}
    assert result["match_analysis"]["strong_matches"]
    assert result["scoring_breakdown"]["core_role_fit"] >= 20
