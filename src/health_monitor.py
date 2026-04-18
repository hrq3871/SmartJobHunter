#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 爬虫健康监控与自愈系统

功能：
1. 检测爬虫健康状态
2. 诊断失败原因
3. 尝试自动修复
"""

import sys
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


class FailureType(Enum):
    """失败类型"""
    NETWORK_ERROR = "network_error"      # 网络问题
    API_CHANGED = "api_changed"          # API 变化
    URL_INVALID = "url_invalid"          # URL 失效
    ANTI_CRAWL = "anti_crawl"             # 反爬拦截
    CONFIG_ERROR = "config_error"         # 配置错误
    LOGIN_REQUIRED = "login_required"    # 需要登录
    UNKNOWN = "unknown"


@dataclass
class HealthReport:
    """健康报告"""
    company_id: str
    company_name: str
    status: HealthStatus
    jobs_found: int = 0
    error_message: str = ""
    suggestions: List[str] = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


@dataclass
class Diagnosis:
    """诊断结果"""
    company_id: str
    failure_type: FailureType
    reason: str
    can_auto_repair: bool = False
    repair_action: str = ""


class HealthMonitor:
    """爬虫健康监控与自愈系统"""

    def __init__(self, config_path: str = None):
        """初始化健康监控器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "companies.yaml"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """加载配置"""
        if not Path(self.config_path).exists():
            return {"companies": []}
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {"companies": []}

    def check_crawler(self, company_id: str, max_jobs: int = 5) -> HealthReport:
        """检测单个爬虫健康状态

        Args:
            company_id: 公司ID
            max_jobs: 测试爬取的岗位数量

        Returns:
            健康报告
        """
        from .crawler_factory import create_crawler, get_company_config

        company_config = get_company_config(company_id)
        if not company_config:
            return HealthReport(
                company_id=company_id,
                company_name="Unknown",
                status=HealthStatus.ERROR,
                error_message="公司配置不存在",
                suggestions=["检查 companies.yaml 中是否有该公司配置"]
            )

        company_name = company_config.get('name', company_id)

        # 检查配置完整性
        config_issues = self._check_config_integrity(company_config)
        if config_issues:
            return HealthReport(
                company_id=company_id,
                company_name=company_name,
                status=HealthStatus.WARNING,
                error_message="配置不完整",
                suggestions=config_issues
            )

        # 尝试爬取少量岗位
        try:
            crawler = create_crawler(company_id)
            if not crawler:
                return HealthReport(
                    company_id=company_id,
                    company_name=company_name,
                    status=HealthStatus.ERROR,
                    error_message="无法创建爬虫实例",
                    suggestions=["检查 field_mappings 配置"]
                )

            jobs = crawler.crawl(keyword="", max_jobs=max_jobs)

            if jobs:
                return HealthReport(
                    company_id=company_id,
                    company_name=company_name,
                    status=HealthStatus.HEALTHY,
                    jobs_found=len(jobs)
                )
            else:
                return HealthReport(
                    company_id=company_id,
                    company_name=company_name,
                    status=HealthStatus.WARNING,
                    jobs_found=0,
                    error_message="未获取到岗位数据",
                    suggestions=["检查网站是否有岗位发布", "检查 API pattern 是否正确"]
                )

        except Exception as e:
            return HealthReport(
                company_id=company_id,
                company_name=company_name,
                status=HealthStatus.ERROR,
                error_message=str(e),
                suggestions=["运行 diagnose_failure 获取详细诊断"]
            )

    def _check_config_integrity(self, config: dict) -> List[str]:
        """检查配置完整性

        Args:
            config: 公司配置

        Returns:
            问题列表
        """
        issues = []

        # 检查必要字段
        if not config.get('urls'):
            issues.append("缺少 urls 配置")

        if not config.get('api'):
            issues.append("缺少 api 配置")
        else:
            api = config['api']
            if api.get('type') == 'intercept':
                if not api.get('pattern'):
                    issues.append("intercept 类型需要 pattern 配置")
                if not api.get('data_path'):
                    issues.append("缺少 data_path 配置")

        if not config.get('field_mappings'):
            issues.append("缺少 field_mappings 配置")
        else:
            mappings = config['field_mappings']
            if 'id' not in mappings:
                issues.append("field_mappings 缺少 id 字段")
            if 'title' not in mappings:
                issues.append("field_mappings 缺少 title 字段")

        return issues

    def diagnose_failure(self, company_id: str, error: Exception) -> Diagnosis:
        """诊断失败原因

        Args:
            company_id: 公司ID
            error: 异常对象

        Returns:
            诊断结果
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # 网络问题
        if any(kw in error_str for kw in ['timeout', 'connection', 'network', 'dns']):
            return Diagnosis(
                company_id=company_id,
                failure_type=FailureType.NETWORK_ERROR,
                reason=f"网络连接问题: {error}",
                can_auto_repair=False,
                repair_action="检查网络连接后重试"
            )

        # URL 失效
        if any(kw in error_str for kw in ['404', 'not found', '页面不存在']):
            return Diagnosis(
                company_id=company_id,
                failure_type=FailureType.URL_INVALID,
                reason="招聘页面 URL 已失效",
                can_auto_repair=True,
                repair_action="搜索新的招聘官网 URL"
            )

        # 需要登录
        if any(kw in error_str for kw in ['login', '登录', 'auth', 'unauthorized']):
            return Diagnosis(
                company_id=company_id,
                failure_type=FailureType.LOGIN_REQUIRED,
                reason="需要登录才能访问",
                can_auto_repair=False,
                repair_action="请用户先在浏览器中登录"
            )

        # 反爬拦截
        if any(kw in error_str for kw in ['blocked', 'forbidden', 'captcha', '验证码', '风控']):
            return Diagnosis(
                company_id=company_id,
                failure_type=FailureType.ANTI_CRAWL,
                reason="触发反爬机制",
                can_auto_repair=False,
                repair_action="调整爬取频率或使用代理"
            )

        # API 变化
        if any(kw in error_str for kw in ['json', 'parse', 'key', 'attribute']):
            return Diagnosis(
                company_id=company_id,
                failure_type=FailureType.API_CHANGED,
                reason="API 结构可能已变化",
                can_auto_repair=True,
                repair_action="重新分析 API 结构"
            )

        # 未知错误
        return Diagnosis(
            company_id=company_id,
            failure_type=FailureType.UNKNOWN,
            reason=f"未知错误: {error_type}: {error}",
            can_auto_repair=False,
            repair_action="需要人工排查"
        )

    def auto_repair(self, company_id: str, diagnosis: Diagnosis) -> bool:
        """尝试自动修复

        Args:
            company_id: 公司ID
            diagnosis: 诊断结果

        Returns:
            是否修复成功
        """
        if not diagnosis.can_auto_repair:
            return False

        if diagnosis.failure_type == FailureType.URL_INVALID:
            # 搜索新的 URL
            return self._repair_url(company_id)

        if diagnosis.failure_type == FailureType.API_CHANGED:
            # 重新分析 API
            return self._repair_api(company_id)

        return False

    def _repair_url(self, company_id: str) -> bool:
        """修复 URL

        Args:
            company_id: 公司ID

        Returns:
            是否修复成功
        """
        # 调用 AutoAnalyzer 搜索新 URL
        try:
            from .auto_analyzer import AutoAnalyzer
            analyzer = AutoAnalyzer()

            company_config = self._get_company_config(company_id)
            if not company_config:
                return False

            company_name = company_config.get('name', company_id)
            new_config = analyzer.analyze_company(company_name)

            if new_config and new_config.get('urls'):
                self._update_company_config(company_id, new_config)
                return True

        except Exception as e:
            print(f"[Repair] URL repair failed: {e}", file=sys.stderr)

        return False

    def _repair_api(self, company_id: str) -> bool:
        """修复 API 配置

        Args:
            company_id: 公司ID

        Returns:
            是否修复成功
        """
        try:
            from .auto_analyzer import AutoAnalyzer
            analyzer = AutoAnalyzer()

            company_config = self._get_company_config(company_id)
            if not company_config:
                return False

            # 使用现有 URL 重新分析
            url = company_config.get('urls', {}).get('social', '')
            if not url:
                return False

            new_config = analyzer.analyze_url(url)
            if new_config and new_config.get('api'):
                self._update_company_config(company_id, new_config)
                return True

        except Exception as e:
            print(f"[Repair] API repair failed: {e}", file=sys.stderr)

        return False

    def _get_company_config(self, company_id: str) -> Optional[dict]:
        """获取公司配置"""
        for company in self.config.get('companies', []):
            if company.get('id') == company_id:
                return company
        return None

    def _update_company_config(self, company_id: str, new_config: dict):
        """更新公司配置"""
        for i, company in enumerate(self.config.get('companies', [])):
            if company.get('id') == company_id:
                # 合并配置
                self.config['companies'][i].update(new_config)
                self.config['companies'][i]['enabled'] = True
                break

        # 保存配置
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)

    def check_all(self) -> Dict[str, HealthReport]:
        """检查所有启用的爬虫

        Returns:
            健康报告字典
        """
        from .crawler_factory import get_enabled_companies

        reports = {}
        companies = get_enabled_companies()

        for company in companies:
            company_id = company.get('id')
            print(f"[Health] Checking {company.get('name')}...", file=sys.stderr)
            reports[company_id] = self.check_crawler(company_id)

        return reports

    def generate_health_report(self, reports: Dict[str, HealthReport]) -> str:
        """生成健康报告文本

        Args:
            reports: 健康报告字典

        Returns:
            报告文本
        """
        lines = ["# 爬虫健康报告\n"]

        healthy = []
        warning = []
        error = []

        for company_id, report in reports.items():
            if report.status == HealthStatus.HEALTHY:
                healthy.append(report)
            elif report.status == HealthStatus.WARNING:
                warning.append(report)
            else:
                error.append(report)

        lines.append(f"## 概览\n")
        lines.append(f"- 健康: {len(healthy)}\n")
        lines.append(f"- 警告: {len(warning)}\n")
        lines.append(f"- 错误: {len(error)}\n")

        if error:
            lines.append("\n## 错误\n")
            for report in error:
                lines.append(f"- **{report.company_name}**: {report.error_message}\n")
                for s in report.suggestions:
                    lines.append(f"  - {s}\n")

        if warning:
            lines.append("\n## 警告\n")
            for report in warning:
                lines.append(f"- **{report.company_name}**: {report.error_message}\n")

        return "".join(lines)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='SmartJobHunter 健康监控')
    parser.add_argument('--check', type=str, help='检查指定公司')
    parser.add_argument('--check-all', action='store_true', help='检查所有公司')
    parser.add_argument('--report', action='store_true', help='生成健康报告')

    args = parser.parse_args()

    monitor = HealthMonitor()

    if args.check:
        report = monitor.check_crawler(args.check)
        print(f"状态: {report.status.value}")
        print(f"岗位数: {report.jobs_found}")
        if report.error_message:
            print(f"错误: {report.error_message}")

    elif args.check_all:
        reports = monitor.check_all()
        print(monitor.generate_health_report(reports))

    else:
        parser.print_help()
