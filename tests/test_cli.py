#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import JobHunter, _parse_profile_md


class _FixedDatetime:
    @classmethod
    def now(cls):
        return cls()

    def strftime(self, fmt):
        if fmt == "%Y%m%d_%H%M%S_%f":
            return "20260709_120000_000001"
        if fmt == "%Y-%m-%d":
            return "2026-07-09"
        if fmt == "%Y%m%d_%H%M":
            return "20260709_1200"
        if fmt == "%Y-%m-%d %H:%M":
            return "2026-07-09 12:00"
        return "20260709"


def test_rank_and_filter_results_applies_threshold_sorting_and_report_limit():
    hunter = JobHunter()
    hunter.config = {
        "global": {"threshold_score": 70},
        "output": {"max_jobs_per_report": 2},
    }
    jobs = [
        {"title": "medium"},
        {"title": "low"},
        {"title": "high"},
        {"title": "also-high"},
    ]
    evaluations = [
        {"score": 75},
        {"score": 69},
        {"score": 94},
        {"score": 88},
    ]

    ranked_jobs, ranked_evaluations = hunter._rank_and_filter_results(jobs, evaluations)

    assert [job["title"] for job in ranked_jobs] == ["high", "also-high"]
    assert [evaluation["score"] for evaluation in ranked_evaluations] == [94, 88]


def test_filter_jobs_runs_semantic_match_for_new_profile_fields():
    hunter = JobHunter()
    hunter.config = {
        "global": {
            "time_filter_days": 30,
            "decision_level": "moderate",
        }
    }
    hunter.seen_hashes = set()
    jobs = [
        {
            "title": "数据分析实习生",
            "duty": "负责 SQL 取数、指标分析和看板建设。",
            "requirement": "熟悉 Python 和数据分析项目。",
            "hash": "data-job",
        },
        {
            "title": "数据产品销售顾问",
            "duty": "负责电话销售和客户转化。",
            "requirement": "有销售经验优先。",
            "hash": "sales-job",
        },
    ]
    profile = {
        "name": "数据分析",
        "target_roles": ["数据分析师"],
        "must_have": ["SQL", "Python", "指标分析"],
        "avoid": ["销售", "电话销售"],
    }

    filtered = hunter.filter_jobs(jobs, profile)

    assert [job["hash"] for job in filtered] == ["data-job"]
    assert filtered[0]["semantic_match"]["fallback_quality"] == "coarse"


def test_filter_jobs_keeps_stale_social_jobs_when_run_type_is_social():
    hunter = JobHunter()
    hunter.config = {
        "global": {
            "time_filter_days": 7,
        }
    }
    hunter.seen_hashes = set()
    jobs = [
        {
            "title": "AI创作者产品经理",
            "publish_time": "2024-11-11",
            "hash": "stale-social",
        }
    ]

    filtered = hunter.filter_jobs(jobs, {"name": "AI产品经理"}, job_type="social")

    assert [job["hash"] for job in filtered] == ["stale-social"]
    assert filtered[0]["_time_filter_status"] == "stale_social_kept"


def test_run_profile_marks_stale_non_social_jobs_as_time_filtered(monkeypatch, tmp_path):
    hunter = JobHunter()
    hunter.memory_dir = tmp_path
    hunter.output_dir = tmp_path
    hunter.config = {"global": {"time_filter_days": 7, "threshold_score": 70}, "output": {}}
    hunter.seen_hashes = set()
    raw_job = {
        "id": "old-campus",
        "hash": "old-campus",
        "title": "AI产品经理校招",
        "company": "示例公司",
        "publish_time": "2026-03-11",
        "duty": "负责 AI 产品设计",
        "requirement": "产品经理",
        "url": "https://example.com/jobs/old-campus",
    }
    captured = {}

    monkeypatch.setattr(hunter, "crawl_jobs", lambda *args, **kwargs: [raw_job])
    monkeypatch.setattr(
        hunter,
        "evaluate_job",
        lambda job, profile: {"score": 80, "recommendation": "apply", "scoring_breakdown": {}},
    )

    def fake_report(jobs, profile, evaluations, run_records=None):
        captured["records"] = run_records
        return "output/time-filtered-report.md"

    monkeypatch.setattr(hunter, "generate_report", fake_report)

    result = hunter.run_profile(
        {"name": "AI产品经理", "_profile_id": "ai_pm_task", "job_type": "校招"},
        job_type_override="campus",
    )

    assert result == []
    assert captured["records"][0]["processing"] == {
        "stage": "time_filtered",
        "reason": "publish_time_outside_window",
    }


def test_parse_profile_adds_file_level_task_id(tmp_path):
    profile_path = tmp_path / "ai_pm_task.md"
    profile_path.write_text(
        """---
name: AI产品经理
enabled: true
target_roles:
  - AI产品经理
---

# 求职意向
""",
        encoding="utf-8",
    )

    profile = _parse_profile_md(str(profile_path))

    assert profile["name"] == "AI产品经理"
    assert profile["_profile_id"] == "ai_pm_task"
    assert profile["_profile_path"] == str(profile_path)


def test_generate_report_uses_profile_id_to_avoid_same_name_overwrite(tmp_path):
    hunter = JobHunter()
    hunter.output_dir = tmp_path

    report_path = hunter.generate_report(
        jobs=[],
        profile={
            "name": "AI产品经理",
            "_profile_id": "ai_pm_task",
            "_profile_path": "profiles/ai_pm_task.md",
        },
        evaluations=[],
    )

    path = Path(report_path)
    assert path.name.startswith("ai_pm_task_")
    report = path.read_text(encoding="utf-8")
    assert "**Profile ID**: ai_pm_task" in report
    assert "**Profile File**: profiles/ai_pm_task.md" in report
    assert path.parent.name.count("-") == 2


def test_generate_report_appends_all_run_records(tmp_path):
    from src.run_records import attach_evaluation, create_run_records

    hunter = JobHunter()
    hunter.output_dir = tmp_path
    url = "https://example.com/jobs/123?source=official&keyword=AI%20PM"
    records = create_run_records(
        [
            {
                "id": "123",
                "hash": "h123",
                "title": "AI 产品经理",
                "company": "示例公司",
                "duty": "完整职责",
                "requirement": "完整任职要求",
                "url": url,
            }
        ],
        run_id="run-audit",
    )
    attach_evaluation(
        records[0],
        {"score": 80, "recommendation": "apply", "scoring_breakdown": {"target_role_fit": 20}},
        "python_fallback",
    )

    report_path = hunter.generate_report(
        jobs=[],
        profile={"name": "AI产品经理", "_profile_id": "ai_pm_task"},
        evaluations=[],
        run_records=records,
    )

    report = Path(report_path).read_text(encoding="utf-8")
    assert "## 全量抓取与判断记录" in report
    assert f"[{url}]({url})" in report
    assert "完整职责" in report
    assert "完整任职要求" in report


def test_run_profile_generates_audit_report_when_no_jobs_survive_filtering(monkeypatch, tmp_path):
    hunter = JobHunter()
    hunter.memory_dir = tmp_path
    hunter.output_dir = tmp_path
    hunter.config = {"global": {"time_filter_days": 30, "threshold_score": 70}, "output": {}}
    hunter.seen_hashes = set()
    raw_job = {
        "id": "raw-1",
        "hash": "raw-1",
        "title": "过期岗位",
        "company": "示例公司",
        "duty": "职责",
        "requirement": "要求",
        "url": "https://example.com/jobs/raw-1",
    }
    captured = {}

    monkeypatch.setattr(hunter, "crawl_jobs", lambda *args, **kwargs: [raw_job])
    monkeypatch.setattr(hunter, "filter_jobs", lambda jobs, profile, job_type=None: [])
    monkeypatch.setattr(
        hunter,
        "evaluate_job",
        lambda job, profile: {"score": 10, "recommendation": "skip", "scoring_breakdown": {}},
    )

    def fake_report(jobs, profile, evaluations, run_records=None):
        captured["jobs"] = jobs
        captured["records"] = run_records
        return "output/zero-report.md"

    monkeypatch.setattr(hunter, "generate_report", fake_report)

    result = hunter.run_profile(
        {"name": "AI产品经理", "_profile_id": "ai_pm_task", "keywords": ["AI产品经理"]}
    )

    assert result == []
    assert captured["jobs"] == []
    assert len(captured["records"]) == 1
    assert captured["records"][0]["evaluation"]["source"] == "python_fallback"


def test_run_profile_writes_agent_review_queue_and_blocks_fallback_recommendations(
    monkeypatch, tmp_path
):
    hunter = JobHunter()
    hunter.memory_dir = tmp_path
    hunter.output_dir = tmp_path
    hunter.config = {
        "global": {"time_filter_days": 30, "threshold_score": 70},
        "output": {},
        "agent_review": {"required_for_recommendation": True},
    }
    hunter.seen_hashes = set()
    job = {
        "id": "job-1",
        "hash": "job-1",
        "title": "AI产品前端工程师",
        "company": "腾讯",
        "duty": "负责 Web 前端开发、组件体系、Canvas 和代码质量。",
        "requirement": "熟悉前端工程化。",
        "url": "https://example.com/jobs/job-1",
    }
    captured = {}

    monkeypatch.setattr("src.cli.datetime", _FixedDatetime)
    monkeypatch.setattr(hunter, "crawl_jobs", lambda *args, **kwargs: [job])
    monkeypatch.setattr(hunter, "filter_jobs", lambda jobs, profile, job_type=None: jobs)
    monkeypatch.setattr(
        hunter,
        "evaluate_job",
        lambda job, profile: {
            "score": 78,
            "recommendation": "apply",
            "match_reasons": ["目标岗位方向匹配: ai产品"],
            "scoring_breakdown": {"目标岗位匹配": 18, "风险扣分": 0},
        },
    )

    def fake_report(jobs, profile, evaluations, run_records=None):
        captured["jobs"] = jobs
        captured["profile"] = profile
        captured["evaluations"] = evaluations
        captured["records"] = run_records
        return "output/review-required.md"

    monkeypatch.setattr(hunter, "generate_report", fake_report)

    result = hunter.run_profile(
        {"name": "AI产品经理", "_profile_id": "ai_pm_task", "target_roles": ["AI产品经理"]}
    )

    assert result == []
    queue_path = Path(captured["profile"]["_agent_review_queue_path"])
    assert queue_path.exists()
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert queue["items"][0]["job"]["title"] == "AI产品前端工程师"
    assert captured["jobs"] == []
    assert captured["records"][0]["processing"]["stage"] == "needs_agent_review"
    assert captured["records"][0]["evaluation"]["source"] == "python_fallback"


def test_run_profile_uses_agent_review_results_for_formal_recommendations(
    monkeypatch, tmp_path
):
    hunter = JobHunter()
    hunter.memory_dir = tmp_path
    hunter.output_dir = tmp_path
    results_path = tmp_path / "agent_review_results.json"
    results_path.write_text(
        json.dumps(
            {
                "queue_id": "agent_review",
                "results": [
                    {
                        "record_id": "20260709_120000_000001:1",
                        "role_family": "product_manager",
                        "agent_decision": "apply",
                        "agent_score": 84,
                        "role_fit": 5,
                        "core_responsibility_fit": 5,
                        "domain_fit": 5,
                        "resume_evidence_fit": 4,
                        "seniority_fit": 3,
                        "risk_level": 1,
                        "apply_priority": 4,
                        "jd_evidence": ["负责 AI 产品规划和需求分析"],
                        "resume_evidence": ["ADP 智能体平台产品经历"],
                        "reason": "岗位本体是 AI 产品经理。",
                        "confidence": "high",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    hunter.config = {
        "global": {"time_filter_days": 30, "threshold_score": 70},
        "output": {},
        "agent_review": {
            "required_for_recommendation": True,
            "results_path": str(results_path),
        },
    }
    hunter.seen_hashes = set()
    job = {
        "id": "job-1",
        "hash": "job-1",
        "title": "AI产品经理",
        "company": "腾讯",
        "duty": "负责 AI 产品规划和需求分析。",
        "requirement": "需要 AI 产品经验。",
        "url": "https://example.com/jobs/job-1",
    }
    captured = {}

    monkeypatch.setattr("src.cli.datetime", _FixedDatetime)
    monkeypatch.setattr(hunter, "crawl_jobs", lambda *args, **kwargs: [job])
    monkeypatch.setattr(hunter, "filter_jobs", lambda jobs, profile, job_type=None: jobs)
    monkeypatch.setattr(
        hunter,
        "evaluate_job",
        lambda job, profile: {
            "score": 88,
            "recommendation": "apply",
            "match_reasons": ["fallback says yes"],
        },
    )
    monkeypatch.setattr(hunter, "_url_is_available", lambda url: True)
    monkeypatch.setattr(hunter, "generate_report", lambda jobs, profile, evaluations, run_records=None: (
        captured.update({"jobs": jobs, "profile": profile, "evaluations": evaluations, "records": run_records})
        or "output/agent-reviewed.md"
    ))

    result = hunter.run_profile(
        {"name": "AI产品经理", "_profile_id": "ai_pm_task", "target_roles": ["AI产品经理"]}
    )

    assert [job["title"] for job in result] == ["AI产品经理"]
    assert captured["evaluations"][0]["score"] == 84
    assert captured["evaluations"][0]["recommendation"] == "apply"
    assert captured["records"][0]["evaluation"]["source"] == "agent"
    assert captured["records"][0]["evaluation"]["score"] == 84


def test_run_profile_uses_search_keywords_for_crawl_and_repair_task(monkeypatch, tmp_path):
    hunter = JobHunter()
    hunter.memory_dir = tmp_path
    hunter.output_dir = tmp_path
    hunter.config = {"global": {"time_filter_days": 30, "threshold_score": 70}, "output": {}}
    hunter.seen_hashes = set()
    captured = {}

    def fake_crawl(search_keywords, max_jobs=50, job_type=None):
        captured["search_keywords"] = search_keywords
        captured["job_type"] = job_type
        hunter._pending_repairs = [
            {"company_id": "example", "company_name": "Example", "reason": "no_jobs_found"}
        ]
        return []

    def fake_repair_task(keyword, job_type):
        captured["repair_keyword"] = keyword
        captured["repair_job_type"] = job_type
        return "logs/strategy_tasks/_batch/task.json"

    monkeypatch.setattr(hunter, "crawl_jobs", fake_crawl)
    monkeypatch.setattr(hunter, "write_batch_repair_task", fake_repair_task)

    result = hunter.run_profile(
        {
            "name": "AI产品经理",
            "_profile_id": "ai_pm_task",
            "keywords": ["AI产品经理"],
            "search_keywords": ["产品经理", "AI产品"],
        },
        job_type_override="social",
    )

    assert result == []
    assert captured["search_keywords"] == ["产品经理", "AI产品"]
    assert captured["job_type"] == "social"
    assert captured["repair_keyword"] == "产品经理、AI产品"
    assert captured["repair_job_type"] == "social"


def test_validate_report_urls_drops_unavailable_links(monkeypatch):
    hunter = JobHunter()
    jobs = [
        {"title": "valid", "url": "https://example.com/ok"},
        {"title": "missing", "url": "https://example.com/404"},
        {"title": "empty", "url": ""},
    ]
    evaluations = [{"score": 90}, {"score": 88}, {"score": 80}]

    monkeypatch.setattr(hunter, "_url_is_available", lambda url: "ok" in url)

    valid_jobs, valid_evaluations = hunter._filter_live_urls(jobs, evaluations)

    assert [job["title"] for job in valid_jobs] == ["valid"]
    assert valid_evaluations == [{"score": 90}]


def test_generate_application_package_writes_top3_cover_letters(tmp_path):
    hunter = JobHunter()
    hunter.output_dir = tmp_path
    jobs = [
        {
            "title": "AI产品经理",
            "company": "A公司",
            "duty": "负责 AI 产品规划和需求分析。",
            "requirement": "需要 ToB 产品经验。",
            "url": "https://example.com/a",
        },
        {
            "title": "AI解决方案产品经理",
            "company": "B公司",
            "duty": "负责客户场景方案设计。",
            "requirement": "熟悉大模型应用。",
            "url": "https://example.com/b",
        },
        {
            "title": "Agent产品经理",
            "company": "C公司",
            "duty": "负责 Agent 工作流产品。",
            "requirement": "有产品落地经验。",
            "url": "https://example.com/c",
        },
        {
            "title": "普通产品经理",
            "company": "D公司",
            "duty": "负责通用产品。",
            "requirement": "沟通能力强。",
            "url": "https://example.com/d",
        },
    ]
    evaluations = [
        {"score": 95, "match_reasons": ["AI 产品方向匹配"], "risk_warning": None},
        {"score": 92, "match_reasons": ["解决方案经验匹配"], "risk_warning": None},
        {"score": 88, "match_reasons": ["Agent 方向匹配"], "risk_warning": None},
        {"score": 70, "match_reasons": ["一般匹配"], "risk_warning": None},
    ]
    profile = {
        "name": "AI产品经理",
        "_profile_id": "ai_pm_task",
        "_resume_content": "5年 ToB SaaS 产品经验，主导 AI 助手从0到1上线，负责需求分析和产品规划。",
    }

    package_dir = hunter.generate_application_package(jobs, profile, evaluations)

    path = Path(package_dir)
    assert path.exists()
    assert (path / "index.md").exists()
    cover_letters = sorted(path.glob("cover_letter_*.md"))
    assert len(cover_letters) == 3
    first_letter = cover_letters[0].read_text(encoding="utf-8")
    assert "A公司" in first_letter
    assert "AI产品经理" in first_letter
    assert "ToB SaaS" in first_letter


def test_run_profile_uses_profile_id_for_feishu_and_bitable(monkeypatch, tmp_path):
    hunter = JobHunter()
    hunter.memory_dir = tmp_path
    hunter.output_dir = tmp_path
    hunter.config = {
        "global": {"time_filter_days": 30, "threshold_score": 0},
        "output": {},
        "agent_review": {"required_for_recommendation": False},
        "feishu": {
            "enabled": True,
            "bitable_token": "test_base",
            "bitable_table_id": "test_table",
        },
    }
    hunter.seen_hashes = set()

    job = {
        "title": "AI解决方案产品经理",
        "company": "Example",
        "location": "北京",
        "category": "产品",
        "duty": "负责 AI 解决方案产品规划、需求分析和落地。",
        "requirement": "需要 AI 产品经验。",
        "url": "https://example.com/job/1",
        "hash": "job-1",
    }
    feishu_calls = []
    bitable_calls = []

    monkeypatch.setattr(hunter, "crawl_jobs", lambda *args, **kwargs: [job])
    monkeypatch.setattr(hunter, "filter_jobs", lambda jobs, profile, job_type=None: jobs)
    monkeypatch.setattr(hunter, "evaluate_job", lambda job, profile: {
        "score": 88,
        "recommendation": "apply",
        "match_reasons": ["目标岗位匹配"],
    })
    monkeypatch.setattr(
        hunter,
        "generate_report",
        lambda jobs, profile, evaluations, run_records=None: "output/report.md",
    )
    monkeypatch.setattr(hunter, "_url_is_available", lambda url: True)

    import src.feishu_push as feishu_push
    import src.feishu_bitable as feishu_bitable

    monkeypatch.setattr(feishu_push, "push_to_feishu", lambda report_path, profile_name: (
        feishu_calls.append((report_path, profile_name)) or {"url": "https://feishu.example/report"}
    ))
    monkeypatch.setattr(feishu_bitable, "add_jobs_to_bitable", lambda jobs, profile_name, report_url: (
        bitable_calls.append((jobs, profile_name, report_url)) or 1
    ))

    result = hunter.run_profile({
        "name": "AI产品经理",
        "_profile_id": "ai_pm_task",
        "keywords": ["AI产品经理"],
        "target_roles": ["AI产品经理"],
    })

    assert result
    assert feishu_calls == [("output/report.md", "ai_pm_task")]
    assert bitable_calls[0][1] == "ai_pm_task"
    assert bitable_calls[0][2] == "https://feishu.example/report"


def test_run_profile_skips_when_configured_resume_is_missing(monkeypatch):
    hunter = JobHunter()
    hunter.config = {"global": {}, "output": {}}
    called = {"crawl": False}

    def fake_crawl(*args, **kwargs):
        called["crawl"] = True
        return []

    monkeypatch.setattr(hunter, "crawl_jobs", fake_crawl)

    result = hunter.run_profile({
        "name": "AI产品经理",
        "_profile_id": "ai_pm_task",
        "resume": "resumes/not_exists.md",
        "keywords": ["AI产品经理"],
    })

    assert result == []
    assert called["crawl"] is False
