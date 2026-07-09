from pathlib import Path

import pytest

from src.agent_review import (
    AGENT_SCORE_FIELDS,
    PYTHON_FACT_FIELDS,
    build_agent_review_queue,
    load_agent_review_results,
    normalize_agent_review_result,
)


def test_score_ownership_is_explicit():
    assert AGENT_SCORE_FIELDS == [
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
    assert PYTHON_FACT_FIELDS == [
        "url_status",
        "publish_time_status",
        "dedup_status",
        "jd_completeness",
        "crawl_quality",
        "fallback_candidate_rank",
    ]


def test_build_agent_review_queue_contains_scoring_instructions_and_fallback_context():
    records = [
        {
            "run_record_id": "run-1:1",
            "raw_job": {
                "title": "AI产品前端工程师",
                "company": "腾讯",
                "duty": "负责 Web 前端开发、组件体系、Canvas 和代码质量。",
                "requirement": "熟悉前端工程化。",
                "url": "https://jobs.example/1",
            },
            "processing": {"stage": "ranked_candidate", "reason": None},
            "evaluation": {
                "source": "python_fallback",
                "score": 78,
                "final_decision": "apply",
                "semantic_decision": {"match_reasons": ["目标岗位方向匹配: ai产品"]},
                "scoring_breakdown": {"目标岗位匹配": 18, "风险扣分": 0},
            },
        }
    ]

    queue = build_agent_review_queue(
        records,
        profile={"name": "AI产品经理", "_profile_id": "ai_pm"},
        queue_id="queue-1",
    )

    assert queue["queue_id"] == "queue-1"
    assert queue["profile"]["profile_id"] == "ai_pm"
    assert "Python 只能提供机械事实和候选排序" in queue["instructions"]
    assert "Agent 必须先判断岗位真实角色" in queue["scoring_rubric"]
    assert queue["agent_score_fields"] == AGENT_SCORE_FIELDS
    assert queue["python_fact_fields"] == PYTHON_FACT_FIELDS
    assert queue["items"][0]["record_id"] == "run-1:1"
    assert queue["items"][0]["job"]["title"] == "AI产品前端工程师"
    assert queue["items"][0]["fallback"]["source"] == "python_fallback"
    assert queue["items"][0]["python_facts"]["jd_completeness"]["has_duty"] is True


def test_normalize_agent_review_result_maps_to_report_evaluation_schema():
    result = normalize_agent_review_result(
        {
            "record_id": "run-1:1",
            "agent_decision": "reject",
            "agent_score": 25,
            "role_family": "frontend_engineer",
            "role_fit": 1,
            "core_responsibility_fit": 1,
            "domain_fit": 3,
            "resume_evidence_fit": 2,
            "seniority_fit": 3,
            "risk_level": 5,
            "apply_priority": 1,
            "risk_tags": ["non_product_role", "frontend_engineer"],
            "jd_evidence": ["负责 Web 前端开发"],
            "resume_evidence": ["有 AI 产品经历，但不是前端开发背景"],
            "reason": "岗位本体是前端工程师，不是 AI 产品经理。",
            "confidence": "high",
        }
    )

    assert result["score"] == 25
    assert result["recommendation"] == "reject"
    assert result["semantic_decision"]["should_keep"] is False
    assert result["semantic_decision"]["evidence"]["role_family"] == ["frontend_engineer"]
    assert result["matched_evidence"][0]["job_requirement"] == "负责 Web 前端开发"
    assert result["scoring_breakdown"]["role_fit"] == 1
    assert result["scoring_breakdown"]["risk_level"] == 5
    assert "non_product_role" in result["risks"]


def test_load_agent_review_results_validates_required_records(tmp_path):
    result_path = tmp_path / "agent_review_results.json"
    result_path.write_text(
        """
{
  "queue_id": "queue-1",
  "results": [
    {
      "record_id": "run-1:1",
      "agent_decision": "apply",
      "agent_score": 82,
      "role_fit": 5,
      "core_responsibility_fit": 5,
      "domain_fit": 5,
      "resume_evidence_fit": 4,
      "seniority_fit": 3,
      "risk_level": 1,
      "apply_priority": 4,
      "reason": "岗位本体是 AI 产品经理。",
      "confidence": "high"
    }
  ]
}
""",
        encoding="utf-8",
    )

    loaded = load_agent_review_results(result_path, required_record_ids=["run-1:1"])

    assert loaded["run-1:1"]["score"] == 82
    assert loaded["run-1:1"]["recommendation"] == "apply"

    with pytest.raises(ValueError, match="Missing Agent review results"):
        load_agent_review_results(result_path, required_record_ids=["run-1:2"])
