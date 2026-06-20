#!/usr/bin/env python
# -*- coding: utf-8 -*-

from src import crawler_factory


class EmptyCrawler:
    def crawl(self, **kwargs):
        return []


def test_zero_jobs_creates_strategy_task(monkeypatch):
    company = {
        "id": "emptyco",
        "name": "Empty Co",
        "enabled": True,
        "strategy": {"status": "verified", "type": "config_intercept", "fingerprint": "abc"},
        "api": {"type": "intercept", "pattern": "jobs", "data_path": "data"},
        "field_mappings": {"title": {"source": "title"}},
    }
    reasons = []

    monkeypatch.setattr(crawler_factory, "get_company_config", lambda company_id: company)
    monkeypatch.setattr(crawler_factory, "create_crawler", lambda company_id: EmptyCrawler())
    monkeypatch.setattr(
        crawler_factory,
        "_write_strategy_needed_task",
        lambda company_config, keyword, job_type, reason: reasons.append(reason) or "task.json",
    )

    jobs = crawler_factory.crawl_company("emptyco", "产品经理", auto_repair=True)

    assert jobs == []
    assert reasons == ["zero_jobs_returned"]
