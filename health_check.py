#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 健康检测模块
检测爬虫是否正常工作，记录问题并触发修复
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# 设置环境变量解决编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from spider import crawl_company, get_enabled_companies


class HealthChecker:
    """爬虫健康检测器"""

    def __init__(self):
        self.log_file = Path("logs/health_check.jsonl")
        self.log_file.parent.mkdir(exist_ok=True)
        self.results = {}

    def check_crawler(self, company_id: str, keyword: str = "产品经理") -> Tuple[bool, str, int]:
        """
        检测单个爬虫是否正常
        返回: (是否成功, 错误信息, 获取数量)
        """
        try:
            print(f"[检测] {company_id}...")
            jobs = crawl_company(company_id, keyword, headless=True, max_jobs=5, job_type="social")

            if jobs and len(jobs) > 0:
                print(f"   [OK] {company_id} 正常，获取 {len(jobs)} 个岗位")
                return True, "", len(jobs)
            else:
                error = f"获取到0个岗位"
                print(f"   [WARN] {company_id} 异常: {error}")
                return False, error, 0

        except Exception as e:
            error = str(e)
            print(f"   [FAIL] {company_id} 失败: {error}")
            return False, error, 0

    def run_all_checks(self) -> Dict:
        """运行所有爬虫的健康检测"""
        print("="*50)
        print("[健康检测] 爬虫健康检测开始")
        print("="*50)

        # 从配置获取启用的公司
        companies = get_enabled_companies()

        results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "failed": [],
            "success_count": 0,
            "failed_count": 0
        }

        for company in companies:
            company_id = company.get('id')
            company_name = company.get('name')

            success, error, count = self.check_crawler(company_id)
            results["checks"][company_id] = {
                "name": company_name,
                "success": success,
                "error": error,
                "job_count": count
            }

            if success:
                results["success_count"] += 1
            else:
                results["failed_count"] += 1
                results["failed"].append({
                    "id": company_id,
                    "name": company_name,
                    "error": error
                })

        # 保存日志
        self._save_log(results)

        print("\n" + "="*50)
        print(f"[健康检测] 检测完成: {results['success_count']} 正常, {results['failed_count']} 异常")
        print("="*50)

        return results

    def _save_log(self, results: Dict):
        """保存检测日志"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(results, ensure_ascii=False) + '\n')

    def should_trigger_repair(self, results: Dict) -> bool:
        """判断是否需要触发修复"""
        return results["failed_count"] > 0

    def get_repair_prompt(self, results: Dict) -> str:
        """生成修复提示"""
        if not results["failed"]:
            return ""

        failed_list = "\n".join([
            f"- {item['name']}: {item['error']}"
            for item in results["failed"]
        ])

        return f"""爬虫健康检测发现以下问题：

{failed_list}

请分析问题原因并尝试修复。修复步骤：
1. 检查网站是否有更新（API路径变化、页面结构变化）
2. 使用浏览器F12开发者工具检查网络请求
3. 更新spider.py中的相关代码
4. 测试修复后的爬虫

修复时请遵循：先出计划 → Review → 执行测试 的流程。
"""


def main():
    """主函数"""
    checker = HealthChecker()
    results = checker.run_all_checks()

    if checker.should_trigger_repair(results):
        print("\n[WARN] 检测到异常，建议启动修复流程")
        print("运行以下命令启动修复：")
        print("  python scheduler.py --repair")
        return 1
    else:
        print("\n[OK] 所有爬虫运行正常")
        return 0


if __name__ == "__main__":
    sys.exit(main())
