#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tests import test_all_crawlers as runner


class CompleteCrawler:
    def crawl(self, **kwargs):
        return [{
            "company": "Example",
            "title": "AI 产品经理",
            "location": "上海",
            "url": "https://jobs.example.com/detail/123456789?source=campus&token=abcdef",
            "duty": "负责 AI 产品设计与交付",
            "requirement": "三年以上产品经验",
        }]


def test_single_crawler_uses_strict_verification_and_keeps_full_url(monkeypatch):
    monkeypatch.setattr(runner, "reload_config", lambda: None)
    monkeypatch.setattr(runner, "create_crawler", lambda company_id: CompleteCrawler())

    result = runner.test_single_crawler("example")

    assert result["status"] == "success"
    assert result["verification"]["status"] == "passed"
    assert result["sample_jobs"][0]["url"].endswith("token=abcdef")
    assert "..." not in result["sample_jobs"][0]["url"]


def test_test_runner_exit_code_is_nonzero_for_failed_verification():
    assert runner.result_exit_code({"status": "success"}) == 0
    assert runner.result_exit_code({"status": "invalid_jobs"}) == 1
