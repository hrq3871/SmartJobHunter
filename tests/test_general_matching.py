#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.matching import evaluate_job_fit, match_job_intent, summarize_resume_ability


def test_data_profile_keeps_data_analyst_job_without_product_terms():
    profile = {
        "name": "数据分析",
        "target_roles": ["数据分析师", "商业分析师"],
        "must_have": ["SQL", "Python", "指标分析"],
        "avoid": ["销售", "客服"],
    }
    job = {
        "title": "数据分析实习生",
        "company": "Example",
        "location": "上海",
        "category": "数据",
        "duty": "负责业务指标分析、SQL取数、看板建设和专题分析。",
        "requirement": "熟悉 Python 和 SQL，有数据分析项目经验。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is True
    assert result["match_score"] >= 0.6
    assert "fallback_quality" in result


def test_engineering_profile_keeps_backend_engineer_job():
    profile = {
        "name": "后端开发",
        "target_roles": ["后端开发工程师"],
        "must_have": ["Python", "分布式系统", "数据库"],
        "avoid": ["销售", "运营"],
    }
    job = {
        "title": "后端开发工程师",
        "company": "Example",
        "location": "北京",
        "category": "技术",
        "duty": "负责服务端架构、接口开发、数据库性能优化和稳定性建设。",
        "requirement": "熟悉 Python 或 Go，了解分布式系统和数据库。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is True
    assert result["match_score"] >= 0.6


def test_avoid_terms_filter_sales_noise_for_any_profile():
    profile = {
        "name": "数据分析",
        "target_roles": ["数据分析师"],
        "must_have": ["SQL"],
        "avoid": ["销售", "电话销售"],
    }
    job = {
        "title": "数据产品销售顾问",
        "company": "Example",
        "location": "广州",
        "category": "销售",
        "duty": "负责电话销售、客户转化和销售线索跟进。",
        "requirement": "有销售经验优先。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is False
    assert result["exclude_severity"] == "hard"


def test_operations_title_noise_is_rejected_for_product_profile():
    profile = {
        "name": "产品经理-TOB方向",
        "target_roles": ["产品经理"],
        "must_have": ["TOB", "SaaS", "企业服务"],
        "target_domains": ["AI"],
    }
    job = {
        "title": "资深用户运营（市场营销方向）",
        "company": "Example",
        "location": "北京",
        "category": "运营",
        "duty": "负责用户运营策略、营销活动和商家增长，协同产品团队优化工具。",
        "requirement": "有本地生活运营经验，了解 B 端商家场景。",
    }

    result = match_job_intent(job, profile, decision_level="moderate")

    assert result["should_keep"] is False
    assert result["match_score"] < 0.6
    assert "negative_role" in result["evidence"]


def test_general_fit_scores_resume_evidence_for_engineering_role():
    profile = {
        "name": "后端开发",
        "target_roles": ["后端开发工程师"],
        "must_have": ["Python", "数据库", "接口开发"],
        "target_domains": ["分布式系统"],
        "avoid": ["销售", "运营"],
    }
    resume = """
    3年后端开发经验，主要使用 Python 和 FastAPI 开发业务接口。
    负责订单系统数据库建模、SQL 优化和服务稳定性建设。
    参与分布式任务调度系统改造，将任务延迟降低 35%。
    """
    job = {
        "title": "后端开发工程师",
        "company": "Example",
        "location": "北京",
        "category": "技术",
        "duty": "负责后端服务接口开发、数据库性能优化和分布式系统稳定性建设。",
        "requirement": "熟悉 Python、数据库、接口设计，有分布式系统经验优先。",
    }

    ability_profile = summarize_resume_ability(resume)
    result = evaluate_job_fit(job, profile, resume_text=resume, ability_profile=ability_profile)

    assert result["score"] >= 75
    assert result["recommendation"] in {"strong_apply", "apply"}
    assert result["scoring_breakdown"]["target_role_fit"] >= 18
    assert result["match_analysis"]["strong_matches"]
