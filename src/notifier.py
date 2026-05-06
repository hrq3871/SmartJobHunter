#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 用户通知器

功能：
1. 通知用户爬虫策略任务或错误
2. 写入日志
3. 可选：发送到飞书/邮件
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List


class Notifier:
    """用户通知器"""

    def __init__(self, log_dir: str = None):
        """初始化通知器

        Args:
            log_dir: 日志目录
        """
        self.log_dir = Path(log_dir or Path(__file__).parent.parent / "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def notify_repair_failed(self, company_id: str, reason: str, suggestions: List[str] = None):
        """通知用户需要 Agent 处理策略任务

        Args:
            company_id: 公司ID
            reason: 失败原因
            suggestions: 建议操作
        """
        suggestions = suggestions or [
            "检查招聘网站是否变更",
            "读取 strategy task 和 crawler evidence",
            "由当前 Agent 更新配置或 Python strategy",
        ]

        message = f"""
⚠️ 爬虫策略需要 Agent 分析

公司: {company_id}
原因: {reason}

建议操作:
"""
        for i, s in enumerate(suggestions, 1):
            message += f"{i}. {s}\n"

        # 输出到控制台
        print(message, file=sys.stderr)

        # 写入日志
        self.write_log(f"[REPAIR FAILED] {company_id}: {reason}")

        # 写入详细日志文件
        self._write_detail_log(company_id, reason, suggestions)

    def notify_repair_success(self, company_id: str, action: str):
        """通知用户策略更新成功

        Args:
            company_id: 公司ID
            action: 修复动作
        """
        message = f"✅ 爬虫策略已更新: {company_id} - {action}"
        print(message, file=sys.stderr)
        self.write_log(f"[REPAIR SUCCESS] {company_id}: {action}")

    def notify_crawler_error(self, company_id: str, error: str):
        """通知用户爬虫错误

        Args:
            company_id: 公司ID
            error: 错误信息
        """
        message = f"❌ 爬虫错误: {company_id} - {error}"
        print(message, file=sys.stderr)
        self.write_log(f"[CRAWLER ERROR] {company_id}: {error}")

    def notify_new_company_added(self, company_name: str, company_id: str):
        """通知用户新公司已添加

        Args:
            company_name: 公司名称
            company_id: 公司ID
        """
        message = f"✅ 新公司已添加: {company_name} ({company_id})"
        print(message, file=sys.stderr)
        self.write_log(f"[NEW COMPANY] {company_name}: {company_id}")

    def notify_login_required(self, company_id: str, url: str):
        """通知用户需要登录

        Args:
            company_id: 公司ID
            url: 登录页面 URL
        """
        message = f"""
🔐 需要登录

公司: {company_id}
请在浏览器中访问以下地址并登录:
{url}

登录完成后，重新运行爬虫即可。
"""
        print(message, file=sys.stderr)
        self.write_log(f"[LOGIN REQUIRED] {company_id}: {url}")

    def write_log(self, message: str, log_file: str = "notifier.log"):
        """写入日志

        Args:
            message: 日志消息
            log_file: 日志文件名
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_path = self.log_dir / log_file

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")

    def _write_detail_log(self, company_id: str, reason: str, suggestions: List[str]):
        """写入详细日志

        Args:
            company_id: 公司ID
            reason: 原因
            suggestions: 建议
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = self.log_dir / f"repair_failed_{company_id}_{timestamp}.json"

        data = {
            "timestamp": datetime.now().isoformat(),
            "company_id": company_id,
            "reason": reason,
            "suggestions": suggestions,
        }

        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def generate_summary_report(self, reports: dict) -> str:
        """生成摘要报告

        Args:
            reports: 健康报告字典

        Returns:
            报告文本
        """
        lines = ["# 爬虫运行报告\n"]
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        success = []
        failed = []
        warnings = []

        for company_id, report in reports.items():
            status = report.get('status', 'unknown')
            if status == 'healthy':
                success.append(report)
            elif status == 'warning':
                warnings.append(report)
            else:
                failed.append(report)

        lines.append(f"## 概览\n\n")
        lines.append(f"| 状态 | 数量 |\n")
        lines.append(f"|------|------|\n")
        lines.append(f"| ✅ 成功 | {len(success)} |\n")
        lines.append(f"| ⚠️ 警告 | {len(warnings)} |\n")
        lines.append(f"| ❌ 失败 | {len(failed)} |\n\n")

        if failed:
            lines.append(f"## 失败详情\n\n")
            for report in failed:
                lines.append(f"### {report.get('company_name', report.get('company_id'))}\n\n")
                lines.append(f"- **原因**: {report.get('error_message', '未知')}\n")
                if report.get('suggestions'):
                    lines.append(f"- **建议**:\n")
                    for s in report['suggestions']:
                        lines.append(f"  - {s}\n")
                lines.append("\n")

        return "".join(lines)


# 全局通知器实例
_notifier = None


def get_notifier() -> Notifier:
    """获取全局通知器"""
    global _notifier
    if _notifier is None:
        _notifier = Notifier()
    return _notifier


def notify_repair_failed(company_id: str, reason: str, suggestions: List[str] = None):
    """便捷方法：通知修复失败"""
    get_notifier().notify_repair_failed(company_id, reason, suggestions)


def notify_repair_success(company_id: str, action: str):
    """便捷方法：通知修复成功"""
    get_notifier().notify_repair_success(company_id, action)


def notify_crawler_error(company_id: str, error: str):
    """便捷方法：通知爬虫错误"""
    get_notifier().notify_crawler_error(company_id, error)


def notify_login_required(company_id: str, url: str):
    """便捷方法：通知需要登录"""
    get_notifier().notify_login_required(company_id, url)


if __name__ == '__main__':
    # 测试
    notifier = Notifier()
    notifier.notify_repair_failed(
        "test_company",
        "API 结构已变化",
        ["重新分析 API", "更新配置文件"]
    )
    notifier.notify_repair_success("test_company", "URL 已更新")
    print("测试完成，请检查 logs 目录")
