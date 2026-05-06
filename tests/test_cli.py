#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import JobHunter


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
