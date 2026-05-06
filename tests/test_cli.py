#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import JobHunter, _parse_profile_md


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
    monkeypatch.setattr(hunter, "filter_jobs", lambda jobs, profile: jobs)
    monkeypatch.setattr(hunter, "evaluate_job", lambda job, profile: {
        "score": 88,
        "recommendation": "apply",
        "match_reasons": ["目标岗位匹配"],
    })
    monkeypatch.setattr(hunter, "generate_report", lambda jobs, profile, evaluations: "output/report.md")
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
