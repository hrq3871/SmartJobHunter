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


def test_intent_match_limits_title_only_domain_keyword_score():
    profile = {
        "intent": "寻找 AI 产品经理岗位，偏好大模型应用和 Agent 方向。",
        "keywords": ["AI", "大模型", "Agent"],
    }
    strong_job = {
        "title": "大模型 Agent 产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责大模型 Agent 产品规划，设计 LLM 应用工作流并推动模型应用落地。",
        "requirement": "需要 AI 产品经验，熟悉 RAG、Agent 和跨团队协作。",
    }
    title_only_job = {
        "title": "AI 产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责内部工具的需求收集、PRD撰写、版本排期和用户反馈跟进。",
        "requirement": "需要产品经理经验，具备沟通协调能力。",
    }

    strong_result = match_job_intent(strong_job, profile, decision_level="moderate")
    title_only_result = match_job_intent(title_only_job, profile, decision_level="moderate")

    assert title_only_result["match_score"] <= 0.65
    assert strong_result["match_score"] - title_only_result["match_score"] >= 0.1


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


def test_evaluate_job_fit_separates_deep_domain_match_from_title_only_keyword():
    profile = {
        "intent": "寻找 AI 产品经理岗位，偏好大模型应用和 Agent 方向。",
        "keywords": ["AI", "大模型", "Agent"],
    }
    resume = """
    4年产品经理经验，负责需求分析、PRD和跨团队上线。
    主导过企业知识库 AI 助手，熟悉 LLM、RAG、Agent 工作流和产品指标。
    """
    ability_profile = summarize_resume_ability(resume)
    strong_job = {
        "title": "大模型 Agent 产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责大模型 Agent 产品规划，设计 LLM 应用工作流，推动企业客户场景上线。",
        "requirement": "需要 AI 产品经验，理解 RAG、模型应用边界和跨团队落地。",
    }
    title_only_job = {
        "title": "AI 产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责内部工具的需求收集、PRD撰写、版本排期和用户反馈跟进。",
        "requirement": "需要产品经理经验，具备沟通协调能力和项目推动经验。",
    }

    strong_result = evaluate_job_fit(
        strong_job,
        profile,
        resume_text=resume,
        ability_profile=ability_profile,
    )
    title_only_result = evaluate_job_fit(
        title_only_job,
        profile,
        resume_text=resume,
        ability_profile=ability_profile,
    )

    assert strong_result["score"] - title_only_result["score"] >= 12
    assert title_only_result["scoring_breakdown"]["domain_fit"] < 20


def test_profile_exclude_keywords_reject_engineering_noise_for_product_profile():
    profile = {
        "intent": "寻找 AI 产品经理岗位，偏好大模型应用和 ToB SaaS。",
        "keywords": ["产品经理", "AI产品", "B端"],
        "exclude_keywords": ["工程师", "算法", "开发", "架构师", "研发", "测试"],
    }
    job = {
        "title": "AI数据工程师",
        "company": "Example",
        "location": "北京",
        "category": "技术",
        "duty": "负责大模型数据平台建设，参与业务需求分析和数据治理，支持 B端 AI 产品落地。",
        "requirement": "需要 Python、SQL、数据仓库和模型训练经验，有研发背景优先。",
    }

    intent_result = match_job_intent(job, profile, decision_level="moderate")
    fit_result = evaluate_job_fit(
        job,
        profile,
        resume_text="5年 ToB SaaS 产品经理经验，负责 AI 产品规划、需求分析和客户场景落地。",
    )

    assert intent_result["should_keep"] is False
    assert "excluded_terms" in intent_result["evidence"]
    assert fit_result["score"] < 70
    assert fit_result["recommendation"] in {"consider", "skip"}


def test_exclude_keywords_do_not_auto_reject_technical_product_manager():
    profile = {
        "intent": "寻找 AI 产品经理岗位，偏好大模型应用和 ToB SaaS。",
        "keywords": ["产品经理", "AI产品", "B端"],
        "exclude_keywords": ["工程师", "算法", "开发", "架构师", "研发", "测试", "技术"],
    }
    job = {
        "title": "技术产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责 B端 AI 平台产品规划、需求分析、路线图设计和跨团队落地。",
        "requirement": "需要产品经理经验，理解大模型应用场景，能与研发团队协作。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is True
    assert result["match_score"] >= 0.6


def test_resume_evidence_uses_source_snippet_in_strong_match():
    profile = {
        "intent": "寻找 AI Agent 和大模型应用方向的产品经理岗位，偏好 ToB SaaS。",
        "keywords": ["AI产品", "大模型", "Agent", "ToB"],
    }
    resume = """
    5年 ToB SaaS 产品经验，主导企业知识库 AI 助手从0到1上线。
    负责需求分析、PRD、跨部门推进和客户访谈，搭建数据看板优化转化率。
    熟悉 LLM 应用、RAG、Agent 工作流和产品指标体系。
    """
    job = {
        "title": "大模型 Agent 产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责大模型 Agent 产品规划、需求分析和商业化落地。",
        "requirement": "需要 ToB 产品经验、LLM 应用理解、数据分析和跨团队推动能力。",
    }

    result = evaluate_job_fit(job, profile, resume_text=resume)
    evidence_text = "\n".join(
        match["candidate_evidence"]
        for match in result["match_analysis"]["strong_matches"]
    )

    assert "主导企业知识库 AI 助手从0到1上线" in evidence_text


def test_ai_product_profile_rejects_ai_product_operations_noise():
    profile = {
        "target_roles": ["AI产品经理", "AI应用产品", "AI解决方案产品经理"],
        "target_domains": ["大模型应用", "Agent", "AI解决方案"],
        "must_have": ["产品规划", "需求分析", "AI产品"],
        "avoid": ["运营", "销售", "客服", "标注"],
    }
    job = {
        "title": "AI产品运营",
        "company": "Example",
        "location": "北京",
        "category": "运营",
        "duty": "负责 AI 产品用户运营、活动运营、内容配置和数据看板跟进。",
        "requirement": "有运营经验，能推动用户增长和活动转化。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is False
    assert result["match_score"] < 0.6
    assert "negative_role" in result["evidence"]


def test_ai_solution_product_manager_still_passes_broad_target_roles():
    profile = {
        "target_roles": ["AI产品经理", "AI应用产品", "AI解决方案产品经理"],
        "target_domains": ["大模型应用", "Agent", "AI解决方案"],
        "must_have": ["产品规划", "需求分析", "AI产品"],
        "avoid": ["运营", "销售", "客服", "标注"],
    }
    job = {
        "title": "AI解决方案产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责面向企业客户的大模型应用产品规划、需求分析、方案设计和落地交付。",
        "requirement": "需要 AI 产品经验，理解客户业务场景、Agent 工作流和跨团队协作。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is True
    assert result["match_score"] >= 0.6


def test_ai_product_profile_rejects_communications_and_frontend_false_positives():
    profile = {
        "target_roles": ["AI产品经理", "AI应用产品", "AI解决方案产品经理"],
        "target_domains": ["大模型应用", "Agent", "AI解决方案"],
        "must_have": ["产品规划", "需求分析", "AI产品", "落地推进"],
        "avoid": ["运营", "销售", "客服", "标注", "公关", "传播", "前端", "研发"],
    }
    resume = """
    5年 ToB SaaS 产品经理经验，负责 AI 产品规划、需求分析、PRD、跨团队推进和客户场景落地。
    主导企业知识库 AI 助手从0到1上线，熟悉 LLM、RAG、Agent 工作流和产品指标体系。
    """
    false_positive_jobs = [
        {
            "title": "腾讯-AI产品公关传播经理",
            "company": "腾讯",
            "location": "北京",
            "category": "市场公关",
            "duty": "负责 AI 产品品牌传播、公关策略、媒体关系、社媒内容、舆情监测和传播项目执行。",
            "requirement": "需要品牌传播、公关传播、媒体关系和舆情管理经验，能策划社媒传播内容。",
        },
        {
            "title": "AW项目组-AI产品前端工程师",
            "company": "阿里",
            "location": "杭州",
            "category": "技术",
            "duty": "负责 AI 产品 Web 前端开发、组件建设、Canvas 交互、代码质量和工程化优化。",
            "requirement": "熟悉前端框架、TypeScript、Canvas、组件库和工程质量，有研发经验。",
        },
    ]

    for job in false_positive_jobs:
        intent_result = match_job_intent(job, profile, decision_level="moderate")
        fit_result = evaluate_job_fit(job, profile, resume_text=resume)

        assert intent_result["should_keep"] is False
        assert intent_result["match_score"] < 0.6
        assert "negative_role" in intent_result["evidence"]
        assert fit_result["score"] <= 59
        assert fit_result["recommendation"] == "skip"
