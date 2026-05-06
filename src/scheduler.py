#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SmartJobHunter scheduler.

Daily execution is strategy-aware:
1. inspect configured company links and crawler strategies;
2. create evidence/strategy tasks for new, changed, blocked, or failed sites;
3. skip companies that are not ready and continue crawling verified ones;
4. print task paths so the current Claude/Codex agent can analyze and patch.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

os.environ["PYTHONIOENCODING"] = "utf-8"

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.git_auto_push import auto_commit_push
from src.health_monitor import HealthMonitor
from src.feishu_push import get_feishu_push_status, set_feishu_push_enabled


def run_job_hunt(job_type: str = "social", skip_companies: Iterable[str] | None = None) -> bool:
    """Run the CLI job hunt, optionally skipping strategy-problem companies."""
    skip_list = [company_id for company_id in (skip_companies or []) if company_id]
    env = os.environ.copy()
    if skip_list:
        env["SMARTHUNTER_SKIP_COMPANIES"] = ",".join(sorted(set(skip_list)))

    print("=" * 60)
    print(f"[巡检] 开始求职巡检 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if skip_list:
        print(f"[巡检] 跳过待分析公司: {', '.join(sorted(set(skip_list)))}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "-t", job_type],
        env=env,
    )
    return result.returncode == 0


def run_health_check(
    keyword: str = "产品经理",
    job_type: str = "social",
    headless: bool = True,
) -> Dict[str, Any]:
    """Run the daily strategy inspection workflow."""
    monitor = HealthMonitor()
    return monitor.inspect_all_strategies(keyword=keyword, job_type=job_type, headless=headless)


def print_strategy_summary(summary: Dict[str, Any]) -> None:
    """Print a compact strategy inspection summary and task list."""
    print("\n" + "=" * 60)
    print("[策略巡检] 公司链接与爬虫策略检查")
    print("=" * 60)
    print(
        f"总数: {summary.get('total', 0)} | "
        f"可抓取: {summary.get('ready', 0)} | "
        f"需 Agent 分析: {summary.get('needs_agent', 0)} | "
        f"阻塞: {summary.get('blocked', 0)} | "
        f"失败: {summary.get('failed', 0)}"
    )

    task_items = [
        item for item in summary.get("results", [])
        if item.get("task_path") or item.get("requires_agent") or item.get("action") == "blocked"
    ]
    if not task_items:
        print("[策略巡检] 未发现需要单独处理的策略任务")
        return

    print("\n[策略巡检] 待处理任务:")
    for item in task_items:
        company = item.get("company_name") or item.get("company_id")
        action = item.get("action")
        reason = item.get("reason") or item.get("block_type") or ""
        task_path = item.get("task_path") or "未生成 task"
        print(f"  - {company}: {action} {reason} -> {task_path}")
        for command in item.get("next_commands") or []:
            print(f"    command: {command}")


def _not_ready_company_ids(summary: Dict[str, Any]) -> List[str]:
    return [
        item.get("company_id")
        for item in summary.get("results", [])
        if item.get("company_id") and item.get("action") != "crawl"
    ]


def trigger_self_repair(results: Dict[str, Any]) -> None:
    """Compatibility wrapper: print strategy tasks for the current agent."""
    print_strategy_summary(results.get("summary", results))
    print("\n处理方式:")
    print("1. 读取对应 logs/strategy_tasks/.../task.json")
    print("2. 读取 evidence.json、network.json、page.html/page.txt、page.png")
    print("3. 由当前 Agent 修改 config/companies.yaml 或 src/site_strategies/*.py")
    print("4. 运行 python tests/test_all_crawlers.py --company <id> --keyword \"产品经理\" --max-jobs 3")


def scheduled_run(
    job_type: str = "social",
    keyword: str = "产品经理",
    headless: bool = True,
    push: bool = False,
) -> bool:
    """Daily scheduled entrypoint."""
    print(f"\n[定时] 定时任务触发 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    summary = run_health_check(keyword=keyword, job_type=job_type, headless=headless)
    print_strategy_summary(summary)

    skip_companies = _not_ready_company_ids(summary)
    if summary.get("ready", 0) == 0:
        print("\n[WARN] 没有可直接抓取的公司。本次只生成策略任务，不运行岗位巡检。")
        return False

    success = run_job_hunt(job_type, skip_companies=skip_companies)

    if success:
        print("\n[OK] 巡检完成")
        if push:
            print("\n[Git] 自动提交/推送巡检产物...")
            auto_commit_push(f"巡检完成 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        else:
            print("\n[Git] 默认不自动提交/推送；如需开启请显式传入 --push")
    else:
        print("\n[FAIL] 巡检失败")

    if skip_companies:
        print("\n[策略巡检] 以下公司已跳过，等待 Agent 分析或用户处理:")
        for company_id in skip_companies:
            print(f"  - {company_id}")

    return success


def main() -> int:
    parser = argparse.ArgumentParser(description="SmartJobHunter 调度器")
    parser.add_argument("--run", action="store_true", help="立即执行岗位巡检")
    parser.add_argument("--check", action="store_true", help="运行每日策略巡检")
    parser.add_argument("--repair", action="store_true", help="输出待 Agent 处理的策略任务")
    parser.add_argument("--schedule", action="store_true", help="定时模式（由系统调度调用）")
    parser.add_argument("-t", "--job-type", default="social", help="岗位类型 social/campus/internship")
    parser.add_argument("-k", "--keyword", default="产品经理", help="策略巡检关键词")
    parser.add_argument("--headful", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--push", action="store_true", help="定时巡检完成后自动提交/推送")
    parser.add_argument("--no-push", action="store_true", help="兼容旧参数；默认已经不自动提交/推送")
    parser.add_argument(
        "--feishu-push",
        choices=["on", "off", "status"],
        help="开启/关闭/查看每日巡检后的飞书 Wiki 和多维表格推送",
    )

    args = parser.parse_args()
    headless = not args.headful

    if args.feishu_push:
        if args.feishu_push == "on":
            status = set_feishu_push_enabled(True)
        elif args.feishu_push == "off":
            status = set_feishu_push_enabled(False)
        else:
            status = get_feishu_push_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0

    if args.run:
        return 0 if run_job_hunt(args.job_type) else 1

    if args.check:
        summary = run_health_check(keyword=args.keyword, job_type=args.job_type, headless=headless)
        print_strategy_summary(summary)
        return 0 if not _not_ready_company_ids(summary) else 1

    if args.repair:
        summary = run_health_check(keyword=args.keyword, job_type=args.job_type, headless=headless)
        trigger_self_repair(summary)
        return 0

    if args.schedule:
        scheduled_run(
            job_type=args.job_type,
            keyword=args.keyword,
            headless=headless,
            push=args.push and not args.no_push,
        )
        return 0

    parser.print_help()
    print("\n使用示例:")
    print("  python -m src.scheduler --run")
    print("  python -m src.scheduler --check --keyword \"产品经理\"")
    print("  python -m src.scheduler --repair")
    print("  python -m src.scheduler --schedule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
