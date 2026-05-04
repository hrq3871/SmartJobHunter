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
