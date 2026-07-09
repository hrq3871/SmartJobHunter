#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime

from src.filters import filter_by_time


def test_filter_by_time_keeps_stale_social_jobs_with_audit_marker():
    jobs = [
        {
            "title": "AI创作者产品经理",
            "publish_time": "2024-11-11",
            "job_type": "social",
        }
    ]

    filtered = filter_by_time(
        jobs,
        days=7,
        job_type="social",
        as_of=datetime(2026, 7, 9, 1, 1),
    )

    assert filtered == jobs
    assert filtered[0]["_time_filter_status"] == "stale_social_kept"


def test_filter_by_time_rejects_stale_campus_jobs():
    jobs = [
        {
            "title": "AI产品经理校招",
            "publish_time": "2026-03-11",
            "job_type": "campus",
        }
    ]

    filtered = filter_by_time(
        jobs,
        days=7,
        job_type="campus",
        as_of=datetime(2026, 7, 9, 1, 1),
    )

    assert filtered == []


def test_filter_by_time_keeps_boundary_date_inclusively():
    jobs = [
        {
            "title": "微信秒剪-AI产品经理",
            "publish_time": "2026年07月02日",
            "job_type": "campus",
        }
    ]

    filtered = filter_by_time(
        jobs,
        days=7,
        job_type="campus",
        as_of=datetime(2026, 7, 9, 1, 1),
    )

    assert filtered == jobs
    assert filtered[0]["_time_filter_status"] == "fresh"
