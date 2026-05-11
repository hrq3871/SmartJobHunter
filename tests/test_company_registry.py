#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.company_registry import (
    choose_company_url,
    company_needs_strategy,
    load_companies,
    normalize_company,
)


def test_load_company_with_minimal_user_links():
    raw = {
        "id": "example",
        "name": "示例公司",
        "enabled": True,
        "links": {"career_home": "https://example.com/careers"},
    }

    company = normalize_company(raw)

    assert company["links"]["career_home"] == "https://example.com/careers"
    assert company["strategy"]["status"] == "unknown"
    assert company_needs_strategy(company) is True


def test_old_urls_are_compatible_with_links():
    raw = {
        "id": "legacy",
        "name": "旧配置",
        "enabled": True,
        "urls": {"social": "https://legacy.example/jobs?keyword={keyword}"},
        "api": {"type": "intercept", "pattern": "jobs", "data_path": "data"},
        "field_mappings": {"title": {"source": "title"}},
    }

    company = normalize_company(raw)

    assert company["links"]["social"] == raw["urls"]["social"]
    assert company["strategy"]["type"] == "config_intercept"
    assert company["strategy"]["status"] == "verified"
    assert company_needs_strategy(company) is False


def test_choose_company_url_prefers_job_type_and_applies_keyword():
    company = normalize_company({
        "id": "example",
        "name": "示例公司",
        "enabled": True,
        "links": {
            "career_home": "https://example.com/careers",
            "social": "https://example.com/jobs?q={keyword}",
        },
    })

    url = choose_company_url(company, keyword="AI产品经理", job_type="social")

    assert url == "https://example.com/jobs?q=AI产品经理"


def test_load_companies_normalizes_config_file(tmp_path):
    config_path = tmp_path / "companies.yaml"
    config_path.write_text(
        yaml.safe_dump({
            "companies": [
                {"id": "a", "name": "A", "enabled": True, "links": {"career_home": "https://a.example"}},
                {"id": "b", "name": "B", "enabled": False, "links": {"career_home": "https://b.example"}},
            ]
        }, allow_unicode=True),
        encoding="utf-8",
    )

    companies = load_companies(config_path)

    assert [company["id"] for company in companies] == ["a"]
    assert companies[0]["strategy"]["status"] == "unknown"
