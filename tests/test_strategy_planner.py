#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategy_planner import plan_strategy_action, update_strategy_task_status, write_strategy_task


def test_unknown_strategy_requires_agent_analysis():
    company = {"id": "x", "name": "X", "strategy": {"status": "unknown"}}
    inspection = {"signals": [], "fingerprint": "abc"}

    decision = plan_strategy_action(company, inspection)

    assert decision["action"] == "collect_evidence"
    assert decision["requires_agent"] is True


def test_verified_unchanged_strategy_can_crawl():
    company = {
        "id": "x",
        "name": "X",
        "strategy": {"status": "verified", "fingerprint": "abc", "type": "config_intercept"},
    }
    inspection = {"signals": [], "fingerprint": "abc"}

    decision = plan_strategy_action(company, inspection)

    assert decision["action"] == "crawl"
    assert decision["requires_agent"] is False


def test_login_required_blocks_auto_strategy():
    company = {"id": "x", "name": "X", "strategy": {"status": "unknown"}}
    inspection = {"signals": ["login_required"], "fingerprint": "abc"}

    decision = plan_strategy_action(company, inspection)

    assert decision["action"] == "blocked"
    assert decision["block_type"] == "login_required"


def test_fingerprint_change_requires_evidence_collection():
    company = {
        "id": "x",
        "name": "X",
        "strategy": {"status": "verified", "fingerprint": "old", "type": "config_intercept"},
    }
    inspection = {"signals": [], "fingerprint": "new"}

    decision = plan_strategy_action(company, inspection)

    assert decision["action"] == "collect_evidence"
    assert "fingerprint_changed" in decision["reason"]


def test_verified_strategy_without_fingerprint_requires_evidence_collection():
    company = {
        "id": "x",
        "name": "X",
        "strategy": {"status": "verified", "fingerprint": None, "type": "config_intercept"},
    }
    inspection = {"signals": [], "fingerprint": "new"}

    decision = plan_strategy_action(company, inspection)

    assert decision["action"] == "collect_evidence"
    assert decision["reason"] == "missing_strategy_fingerprint"


def test_write_strategy_task_contains_agent_commands(tmp_path):
    company = {"id": "x", "name": "X", "links": {"social": "https://x.example/jobs"}}
    decision = {
        "action": "collect_evidence",
        "reason": "unknown_strategy",
        "requires_agent": True,
        "next_commands": ["python -m src.crawler_evidence --company x"],
    }

    task_path = write_strategy_task(company, decision, output_root=tmp_path)

    task = json.loads(task_path.read_text(encoding="utf-8"))
    assert task["company"]["id"] == "x"
    assert task["status"] == "pending"
    assert task["requires_agent"] is True
    assert "crawler_evidence" in task["next_commands"][0]


def test_strategy_task_lifecycle_records_terminal_result(tmp_path):
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps({"status": "pending", "company": {"id": "x"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    analyzing = update_strategy_task_status(task_path, "analyzing")
    repaired = update_strategy_task_status(
        task_path,
        "repaired",
        result={"verification_path": "verification.json", "jobs_count": 3},
    )

    assert analyzing["status"] == "analyzing"
    assert repaired["status"] == "repaired"
    assert repaired["result"]["jobs_count"] == 3
    assert repaired["completed_at"]


def test_strategy_task_lifecycle_rejects_invalid_transition(tmp_path):
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps({"status": "pending", "company": {"id": "x"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    try:
        update_strategy_task_status(task_path, "repaired")
    except ValueError as exc:
        assert "pending -> repaired" in str(exc)
    else:
        raise AssertionError("invalid lifecycle transition should fail")
