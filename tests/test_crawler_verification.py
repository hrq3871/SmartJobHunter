#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json

from src.crawler_verification import verify_crawler_output, write_verification_report


def _valid_job(url="https://jobs.example.com/detail/123?from=campus"):
    return {
        "company": "Example",
        "title": "AI 产品经理",
        "url": url,
        "duty": "负责 AI 产品规划、需求分析与跨团队交付。",
        "requirement": "三年以上产品经验，理解大模型应用。",
    }


def test_verification_passes_complete_jobs_and_reports_field_rates():
    result = verify_crawler_output(
        [_valid_job(), _valid_job("https://jobs.example.com/detail/456")],
        elapsed_ms=1250,
    )

    assert result["status"] == "passed"
    assert result["jobs_count"] == 2
    assert result["valid_jobs_count"] == 2
    assert result["valid_jobs_rate"] == 1.0
    assert result["url_valid_rate"] == 1.0
    assert result["elapsed_ms"] == 1250
    assert result["field_completeness"]["requirement"] == 1.0


def test_verification_fails_zero_jobs_missing_fields_and_truncated_url():
    zero = verify_crawler_output([])
    incomplete = verify_crawler_output([
        {
            "company": "Example",
            "title": "AI 产品经理",
            "url": "https://jobs.example.com/detail/123...",
            "duty": "",
            "requirement": "任职要求",
        }
    ])

    assert zero["status"] == "failed"
    assert zero["failure_reason"] == "zero_jobs"
    assert incomplete["status"] == "failed"
    assert incomplete["valid_jobs_count"] == 0
    assert "invalid_url" in incomplete["jobs"][0]["issues"]
    assert "missing_duty" in incomplete["jobs"][0]["issues"]


def test_write_verification_report_preserves_full_url(tmp_path):
    url = "https://jobs.example.com/detail/123456789?source=campus&token=abcdef"
    report_path = write_verification_report(
        verify_crawler_output([_valid_job(url)]),
        tmp_path / "verification.json",
    )

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["jobs"][0]["url"] == url
