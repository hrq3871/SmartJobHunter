#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 调度器
1. 定时执行求职巡检（每天20:00）
2. 健康检测 + 自动修复
3. 测试通过后自动推送到 GitHub
"""

import sys
import os
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# 设置环境变量解决编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入自动推送模块
from git_auto_push import auto_commit_push


def run_job_hunt(job_type: str = "social"):
    """执行求职巡检"""
    print("="*60)
    print(f"[巡检] 开始求职巡检 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    # 直接运行main.py，不捕获输出
    result = subprocess.run(
        [sys.executable, "main.py", "-t", job_type]
    )

    return result.returncode == 0


def run_health_check() -> dict:
    """运行健康检测"""
    from health_check import HealthChecker

    checker = HealthChecker()
    results = checker.run_all_checks()
    return results


def trigger_self_repair(results: dict):
    """触发自我修复（输出修复提示，由Agent执行）"""
    print("\n" + "="*60)
    print("[修复] 启动自我修复流程")
    print("="*60)

    failed_list = results.get("failed", [])
    if not failed_list:
        print("没有需要修复的问题")
        return

    # 生成修复任务文件
    repair_file = Path("logs/repair_tasks.json")
    repair_file.parent.mkdir(exist_ok=True)

    repair_tasks = {
        "timestamp": datetime.now().isoformat(),
        "tasks": failed_list,
        "status": "pending"
    }

    with open(repair_file, 'w', encoding='utf-8') as f:
        json.dump(repair_tasks, f, ensure_ascii=False, indent=2)

    print(f"\n修复任务已记录到: {repair_file}")
    print("\n需要修复的爬虫:")
    for item in failed_list:
        print(f"  - {item['name']}: {item['error']}")

    print("\n" + "-"*60)
    print("修复步骤:")
    print("1. 使用浏览器F12检查网站API变化")
    print("2. 更新spider.py中的相关代码")
    print("3. 运行测试: python health_check.py")
    print("-"*60)


def scheduled_run():
    """定时执行入口（每天20:00）"""
    print(f"\n[定时] 定时任务触发 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 1. 先运行健康检测
    results = run_health_check()

    # 2. 如果有问题，尝试修复
    if results["failed_count"] > 0:
        print("\n[WARN] 检测到爬虫异常，尝试修复...")
        trigger_self_repair(results)
        return False

    # 3. 执行求职巡检
    success = run_job_hunt("social")

    if success:
        print("\n[OK] 巡检完成")
        # 4. 自动推送到 GitHub
        print("\n[Git] 自动推送更新...")
        auto_commit_push(f"巡检完成 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    else:
        print("\n[FAIL] 巡检失败")

    return success


def main():
    parser = argparse.ArgumentParser(description='SmartJobHunter 调度器')
    parser.add_argument('--run', action='store_true', help='立即执行巡检')
    parser.add_argument('--check', action='store_true', help='运行健康检测')
    parser.add_argument('--repair', action='store_true', help='触发修复流程')
    parser.add_argument('--schedule', action='store_true', help='定时模式（由系统调度调用）')
    parser.add_argument('-t', '--job-type', default='social', help='岗位类型')

    args = parser.parse_args()

    if args.run:
        # 立即执行巡检
        success = run_job_hunt(args.job_type)
        sys.exit(0 if success else 1)

    elif args.check:
        # 健康检测
        results = run_health_check()
        if results["failed_count"] > 0:
            print("\n⚠️ 检测到异常，运行 --repair 启动修复")
            sys.exit(1)
        sys.exit(0)

    elif args.repair:
        # 修复模式
        results = run_health_check()
        if results["failed_count"] > 0:
            trigger_self_repair(results)
        sys.exit(0)

    elif args.schedule:
        # 定时模式
        scheduled_run()
        sys.exit(0)

    else:
        # 默认：显示帮助
        parser.print_help()
        print("\n使用示例:")
        print("  python scheduler.py --run          # 立即执行巡检")
        print("  python scheduler.py --check        # 健康检测")
        print("  python scheduler.py --repair       # 修复异常爬虫")
        print("  python scheduler.py --schedule     # 定时模式（由系统调用）")


if __name__ == "__main__":
    main()
