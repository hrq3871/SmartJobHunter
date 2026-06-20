#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler_evidence import (
    build_evidence_manifest,
    find_job_array_candidates,
    sanitize_post_data,
    sanitize_url,
)


def test_find_job_array_candidates_scores_job_like_arrays():
    payload = {
        "data": {
            "job_post_list": [
                {
                    "id": "1",
                    "title": "AI 产品经理",
                    "description": "负责大模型产品规划",
                    "requirement": "熟悉 LLM 应用",
                }
            ]
        }
    }

    candidates = find_job_array_candidates(payload)

    assert candidates[0]["path"] == "data.job_post_list"
    assert candidates[0]["item_count"] == 1
    assert "title" in candidates[0]["field_hints"]


def test_sanitize_url_removes_obvious_tokens():
    url = "https://example.com/jobs?keyword=pm&token=secret&access_token=abc"

    sanitized = sanitize_url(url)

    assert "secret" not in sanitized
    assert "abc" not in sanitized
    assert "keyword=pm" in sanitized


def test_evidence_manifest_contains_agent_inputs(tmp_path):
    manifest = build_evidence_manifest(
        company_id="example",
        company_name="示例公司",
        url="https://example.com/jobs",
        keyword="产品经理",
        job_type="social",
        output_dir=tmp_path,
        network_requests=[{"url": "https://api.example.com/jobs", "method": "GET"}],
        candidates=[{"path": "data.jobs", "item_count": 3}],
    )

    assert manifest["agent_next_step"] == "analyze_strategy"
    assert manifest["company"]["id"] == "example"
    assert manifest["input"]["job_type"] == "social"
    assert manifest["artifacts"]["network_log"].endswith("network.json")
    assert "config_intercept" in manifest["allowed_strategy_types"]


def test_evidence_manifest_records_main_response_timing_and_actions(tmp_path):
    actions = [
        {"action": "fill", "selector": "input", "value": "产品经理"},
        {"action": "press", "selector": "input", "key": "Enter"},
    ]

    manifest = build_evidence_manifest(
        company_id="example",
        company_name="示例公司",
        url="https://example.com/jobs",
        keyword="产品经理",
        job_type="social",
        output_dir=tmp_path,
        main_status=200,
        elapsed_ms=1234,
        actions=actions,
    )

    assert manifest["page"]["http_status"] == 200
    assert manifest["page"]["elapsed_ms"] == 1234
    assert manifest["artifacts"]["actions"].endswith("actions.json")
    assert manifest["action_count"] == 2


def test_sanitize_post_data_masks_tokens_without_losing_search_terms():
    sanitized = sanitize_post_data("keyword=产品经理&token=secret&access_token=abc123")

    assert "产品经理" in sanitized
    assert "secret" not in sanitized
    assert "abc123" not in sanitized
    assert "[REDACTED]" in sanitized
