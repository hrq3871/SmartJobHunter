#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Legacy compatibility entrypoint.

Prefer `python -m src.health_monitor --inspect-strategies` for daily crawler
strategy inspection. This wrapper exists so older scheduler commands keep
working without using the old src.crawler path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.health_monitor import HealthMonitor


class HealthChecker:
    """Compatibility wrapper around HealthMonitor."""

    def __init__(self):
        self.monitor = HealthMonitor()

    def run_all_checks(self) -> Dict:
        summary = self.monitor.inspect_all_strategies()
        failed = []
        for item in summary.get("results", []):
            if item.get("action") != "crawl":
                failed.append({
                    "id": item.get("company_id"),
                    "name": item.get("company_name"),
                    "error": item.get("reason") or item.get("block_type") or item.get("action"),
                    "task_path": item.get("task_path"),
                })
        return {
            "timestamp": summary.get("timestamp"),
            "checks": {
                item.get("company_id"): {
                    "name": item.get("company_name"),
                    "success": item.get("action") == "crawl",
                    "error": item.get("reason") or item.get("block_type") or "",
                    "task_path": item.get("task_path"),
                }
                for item in summary.get("results", [])
            },
            "failed": failed,
            "success_count": summary.get("ready", 0),
            "failed_count": len(failed),
            "summary": summary,
        }

    def should_trigger_repair(self, results: Dict) -> bool:
        return results.get("failed_count", 0) > 0

    def get_repair_prompt(self, results: Dict) -> str:
        if not results.get("failed"):
            return ""
        failed_list = "\n".join(
            f"- {item['name']}: {item['error']} ({item.get('task_path') or 'no task'})"
            for item in results["failed"]
        )
        return f"""爬虫策略巡检发现以下问题：

{failed_list}

请读取对应 strategy task 和 crawler evidence，判断网站类型、是否需要登录、是否反爬，以及应固化为 YAML 配置还是 Python strategy。
"""


def main() -> int:
    checker = HealthChecker()
    results = checker.run_all_checks()
    if checker.should_trigger_repair(results):
        print("[WARN] 检测到需要 Agent 分析的爬虫策略任务")
        print(checker.get_repair_prompt(results))
        return 1
    print("[OK] 所有已启用公司策略可继续抓取")
    return 0


if __name__ == "__main__":
    sys.exit(main())
