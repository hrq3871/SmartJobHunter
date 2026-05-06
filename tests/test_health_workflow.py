#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.health_monitor import HealthMonitor


def test_strategy_inspection_creates_task_for_unknown_strategy(tmp_path, monkeypatch):
    config_path = tmp_path / "companies.yaml"
    config_path.write_text(
        yaml.safe_dump({
            "companies": [
                {
                    "id": "example",
                    "name": "示例公司",
                    "enabled": True,
                    "links": {"social": "https://example.com/jobs"},
                }
            ]
        }, allow_unicode=True),
        encoding="utf-8",
    )

    from src import site_inspector
    from src import crawler_evidence

    monkeypatch.setattr(site_inspector, "inspect_link", lambda *args, **kwargs: {
        "ok": True,
        "signals": ["job_like"],
        "fingerprint": "abc",
        "final_url": "https://example.com/jobs",
    })
    monkeypatch.setattr(crawler_evidence, "collect_evidence", lambda *args, **kwargs: {
        "evidence_path": str(tmp_path / "evidence" / "evidence.json")
    })

    monitor = HealthMonitor(config_path=str(config_path))
    result = monitor.inspect_company_strategy(
        "example",
        keyword="产品经理",
        job_type="social",
        task_output_root=tmp_path / "strategy_tasks",
    )

    assert result["action"] == "collect_evidence"
    assert result["requires_agent"] is True
    assert Path(result["task_path"]).exists()


def test_strategy_inspection_marks_login_required_and_continues(tmp_path, monkeypatch):
    config_path = tmp_path / "companies.yaml"
    config_path.write_text(
        yaml.safe_dump({
            "companies": [
                {
                    "id": "loginco",
                    "name": "登录公司",
                    "enabled": True,
                    "links": {"social": "https://login.example/jobs"},
                },
                {
                    "id": "okco",
                    "name": "正常公司",
                    "enabled": True,
                    "links": {"social": "https://ok.example/jobs"},
                    "strategy": {"status": "verified", "type": "config_intercept", "fingerprint": "ok"},
                },
            ]
        }, allow_unicode=True),
        encoding="utf-8",
    )

    from src import site_inspector

    def fake_inspect(url, *args, **kwargs):
        if "login" in url:
            return {"ok": True, "signals": ["login_required"], "fingerprint": "login"}
        return {"ok": True, "signals": ["job_like"], "fingerprint": "ok"}

    monkeypatch.setattr(site_inspector, "inspect_link", fake_inspect)

    monitor = HealthMonitor(config_path=str(config_path))
    summary = monitor.inspect_all_strategies(
        keyword="产品经理",
        job_type="social",
        task_output_root=tmp_path / "strategy_tasks",
    )

    assert summary["total"] == 2
    assert summary["blocked"] == 1
    assert summary["ready"] == 1
    assert {item["company_id"] for item in summary["results"]} == {"loginco", "okco"}


def test_health_check_is_legacy_wrapper_without_old_crawler_import():
    source = Path("src/health_check.py").read_text(encoding="utf-8")

    assert "from src.crawler import" not in source


def test_health_monitor_does_not_call_legacy_auto_analyzer_for_repair():
    source = Path("src/health_monitor.py").read_text(encoding="utf-8")

    assert "AutoAnalyzer" not in source
    assert "analyze_company" not in source


def test_scheduler_uses_strategy_inspection_and_no_spider_instructions():
    source = Path("src/scheduler.py").read_text(encoding="utf-8")
    run_bat = Path("run_scheduled.bat").read_text(encoding="utf-8")

    assert "HealthMonitor" in source
    assert "inspect_all_strategies" in source
    assert "spider.py" not in source
    assert "python health_check.py" not in source
    assert "python -m src.scheduler --schedule" in run_bat
    assert "push=args.push" in source
    assert "--feishu-push" in source


def test_scheduler_skips_not_ready_companies():
    from src.scheduler import _not_ready_company_ids

    summary = {
        "results": [
            {"company_id": "ready", "action": "crawl"},
            {"company_id": "unknown", "action": "collect_evidence"},
            {"company_id": "login", "action": "blocked"},
        ]
    }

    assert _not_ready_company_ids(summary) == ["unknown", "login"]
