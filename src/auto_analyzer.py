#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Legacy recruitment-system template analyzer.

This module does not call an external LLM and does not perform agent-side
reasoning. It only recognizes known recruitment-system URL/API patterns and can
generate a draft config when the caller already provides enough evidence.

For the current daily workflow, use:
1. `python -m src.health_monitor --inspect-strategies`
2. `python -m src.crawler_evidence --company <id> ...`
3. current Claude/Codex agent reads the evidence and patches config/code.
"""

import sys
import re
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class CompanyConfig:
    """公司配置"""
    id: str
    name: str
    urls: Dict[str, str]
    api: Dict[str, Any]
    field_mappings: Dict[str, Any]
    url_template: str = ""
    note: str = ""
    enabled: bool = True


class AutoAnalyzer:
    """Legacy template matcher for known recruitment systems."""

    # 系统识别规则
    SYSTEM_RULES = {
        'mokahr': {
            'url_patterns': ['mokahr.com', 'app.mokahr.com'],
            'api_patterns': ['jobs', 'mokahr'],
            'api_type': 'intercept',
        },
        'workday': {
            'url_patterns': ['myworkdayjobs.com', 'wd1.myworkdayjobs.com'],
            'api_type': 'dom',
            'selectors': {
                'job_container': "[data-automation-id='compositeContainer']",
                'title': "[data-automation-id='jobTitle']",
                'location': "[data-automation-id='location']",
                'url': "[data-automation-id='jobTitle']",
            },
        },
        'feishu': {
            'url_patterns': ['jobs.feishu.cn', '.jobs.feishu.cn'],
            'api_patterns': ['search/job/posts'],
            'api_type': 'intercept',
        },
        'zhiye': {
            'url_patterns': ['zhiye.com'],
            'api_type': 'intercept',
        },
        'beisen': {
            'url_patterns': ['beisen.com'],
            'api_type': 'intercept',
        },
    }

    def __init__(self, templates_path: str = None):
        """初始化分析器

        Args:
            templates_path: 系统模板路径
        """
        self.templates_path = templates_path or Path(__file__).parent.parent / "config" / "system_templates.yaml"
        self.templates = self._load_templates()

    def _load_templates(self) -> dict:
        """加载系统模板"""
        if not Path(self.templates_path).exists():
            return {}
        with open(self.templates_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def analyze_new_company(self, company_name: str) -> Optional[CompanyConfig]:
        """分析新公司并生成配置

        Args:
            company_name: 公司名称

        Returns:
            公司配置，失败返回 None
        """
        print(f"[Analyzer] Analyzing {company_name}...", file=sys.stderr)

        # 1. 搜索招聘官网
        official_url = self.search_official_site(company_name)
        if not official_url:
            print(f"[Analyzer] No official site found for {company_name}", file=sys.stderr)
            return None

        print(f"[Analyzer] Found official site: {official_url}", file=sys.stderr)

        # 2. 分析网站
        return self.analyze_url(official_url, company_name)

    def analyze_url(self, url: str, company_name: str = None) -> Optional[CompanyConfig]:
        """分析指定 URL

        Args:
            url: 招聘网站 URL
            company_name: 公司名称（可选）

        Returns:
            公司配置
        """
        # 3. 访问并捕获 API
        apis = self._capture_api_requests(url)

        # 4. 识别系统类型
        system_type = self.identify_system(url, apis)

        print(f"[Analyzer] System type: {system_type}", file=sys.stderr)

        # 5. 生成配置
        config = self.generate_config(
            company_name=company_name or self._extract_company_name(url),
            url=url,
            apis=apis,
            system_type=system_type
        )

        return config

    def search_official_site(self, company_name: str) -> Optional[str]:
        """搜索公司招聘官网

        Args:
            company_name: 公司名称

        Returns:
            招聘官网 URL
        """
        # Python cannot invoke the current agent platform's search judgment from
        # here. The agent should search/verify the official URL and then pass it
        # to analyze_url(), or patch config/companies.yaml directly.

        # 常见招聘 URL 模式
        patterns = [
            f"https://talent.{company_name.lower()}.com",
            f"https://hr.{company_name.lower()}.com",
            f"https://jobs.{company_name.lower()}.com",
            f"https://career.{company_name.lower()}.com",
            f"https://careers.{company_name.lower()}.com",
        ]

        # 返回 None，需要当前 Agent 外部搜索/验证。
        return None

    def _capture_api_requests(self, url: str) -> List[dict]:
        """捕获 API 请求

        Args:
            url: 页面 URL

        Returns:
            API 请求列表
        """
        # Evidence collection now lives in src.crawler_evidence. Keep this hook
        # empty for backward compatibility with old callers.
        return []

    def identify_system(self, url: str, apis: List[dict] = None) -> str:
        """识别招聘系统类型

        Args:
            url: 网站 URL
            apis: API 请求列表

        Returns:
            系统类型: mokahr/workday/feishu/zhiye/beisen/self_built
        """
        url_lower = url.lower()
        apis = apis or []

        # 检查 URL 模式
        for system, rules in self.SYSTEM_RULES.items():
            for pattern in rules.get('url_patterns', []):
                if pattern in url_lower:
                    return system

        # 检查 API 模式
        for api in apis:
            api_url = api.get('url', '').lower()
            for system, rules in self.SYSTEM_RULES.items():
                for pattern in rules.get('api_patterns', []):
                    if pattern in api_url:
                        return system

        # 默认为自建系统
        return 'self_built'

    def generate_config(
        self,
        company_name: str,
        url: str,
        apis: List[dict],
        system_type: str
    ) -> CompanyConfig:
        """生成公司配置

        Args:
            company_name: 公司名称
            url: 招聘网站 URL
            apis: API 请求列表
            system_type: 系统类型

        Returns:
            公司配置
        """
        # 生成 ID
        company_id = self._generate_id(company_name)

        # 获取模板
        template = self.templates.get(system_type, {})

        # 构建 URL 配置
        urls = self._build_urls(url)

        # 构建 API 配置
        api = self._build_api(apis, template, system_type)

        # 构建字段映射
        field_mappings = template.get('field_mappings', self._default_field_mappings())

        # 构建 URL 模板
        url_template = template.get('url_template', '')

        return CompanyConfig(
            id=company_id,
            name=company_name,
            urls=urls,
            api=api,
            field_mappings=field_mappings,
            url_template=url_template,
            note=f"{system_type} 招聘系统",
            enabled=True
        )

    def _generate_id(self, company_name: str) -> str:
        """生成公司 ID"""
        # 转小写，移除特殊字符
        id_str = company_name.lower()
        id_str = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', id_str)

        # 中文转拼音或使用英文名
        # 这里简化处理，实际可能需要拼音库
        common_names = {
            '比亚迪': 'byd',
            '浪潮': 'inspur',
            '微软': 'microsoft',
            '英伟达': 'nvidia',
            '特斯拉': 'tesla',
            '英特尔': 'intel',
            '思科': 'cisco',
            '建设银行': 'ccb',
            '中国移动': 'cmcc',
            '中国电信': 'chinatelecom',
        }

        return common_names.get(company_name, id_str)

    def _extract_company_name(self, url: str) -> str:
        """从 URL 提取公司名"""
        parsed = urlparse(url)
        domain = parsed.netloc

        # 移除常见前缀
        for prefix in ['talent.', 'hr.', 'jobs.', 'career.', 'careers.', 'www.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
                break

        # 移除后缀
        for suffix in ['.com', '.cn', '.com.cn']:
            if domain.endswith(suffix):
                domain = domain[:-len(suffix)]
                break

        return domain

    def _build_urls(self, url: str) -> Dict[str, str]:
        """构建 URL 配置"""
        return {
            'social': url,
        }

    def _build_api(self, apis: List[dict], template: dict, system_type: str) -> Dict[str, Any]:
        """构建 API 配置

        Args:
            apis: 捕获的 API 请求列表
            template: 系统模板
            system_type: 系统类型

        Returns:
            API 配置字典
        """
        system_rules = self.SYSTEM_RULES.get(system_type, {})

        # 如果模板有完整配置
        if template.get('api'):
            api_config = template['api'].copy()
            # 如果是 DOM 类型但缺少 selectors，补充
            if api_config.get('type') == 'dom' and not api_config.get('selectors'):
                api_config['selectors'] = template.get('selectors') or system_rules.get('selectors', {})
            return api_config

        # 根据系统类型判断 API 类型
        api_type = template.get('api_type') or system_rules.get('api_type', 'intercept')

        # DOM 类型：需要选择器配置
        if api_type == 'dom':
            selectors = template.get('selectors') or system_rules.get('selectors', {})
            return {
                'type': 'dom',
                'selectors': selectors,
            }

        # Intercept 类型：需要 API pattern
        if apis:
            for api in apis:
                url = api.get('url', '')
                if any(kw in url for kw in ['job', 'position', 'search', 'list']):
                    return {
                        'type': 'intercept',
                        'pattern': self._extract_pattern(url),
                        'data_path': 'data',
                    }

        return {
            'type': 'intercept',
            'pattern': None,
            'data_path': 'data',
        }

    def _extract_pattern(self, url: str) -> str:
        """从 URL 提取 API pattern"""
        # 提取路径中的关键部分
        parsed = urlparse(url)
        path = parsed.path

        # 移除变量部分
        parts = path.split('/')
        meaningful = [p for p in parts if p and not p.startswith('{') and not re.match(r'^\d+$', p)]

        if meaningful:
            return '/'.join(meaningful[-2:])  # 取最后两部分

        return path

    def _default_field_mappings(self) -> Dict[str, Any]:
        """默认字段映射"""
        return {
            'id': {'source': 'id'},
            'title': {'source': 'title'},
            'location': {'source': 'location'},
            'category': {'source': 'category'},
        }

    def to_yaml(self, config: CompanyConfig) -> str:
        """将配置转换为 YAML

        Args:
            config: 公司配置

        Returns:
            YAML 字符串
        """
        data = {
            'id': config.id,
            'name': config.name,
            'enabled': config.enabled,
            'urls': config.urls,
            'api': config.api,
            'field_mappings': config.field_mappings,
        }

        if config.url_template:
            data['url_template'] = config.url_template
        if config.note:
            data['note'] = config.note

        return yaml.dump([data], allow_unicode=True, default_flow_style=False)

    def save_config(self, config: CompanyConfig, config_path: str = None):
        """保存配置到文件

        Args:
            config: 公司配置
            config_path: 配置文件路径
        """
        config_path = config_path or Path(__file__).parent.parent / "config" / "companies.yaml"

        # 读取现有配置
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {'companies': []}

        # 检查是否已存在
        existing_ids = [c.get('id') for c in data.get('companies', [])]

        new_company = {
            'id': config.id,
            'name': config.name,
            'enabled': config.enabled,
            'urls': config.urls,
            'api': config.api,
            'field_mappings': config.field_mappings,
        }

        if config.url_template:
            new_company['url_template'] = config.url_template
        if config.note:
            new_company['note'] = config.note

        if config.id in existing_ids:
            # 更新现有配置
            for i, c in enumerate(data['companies']):
                if c.get('id') == config.id:
                    data['companies'][i] = new_company
                    break
        else:
            # 添加新配置
            data['companies'].append(new_company)

        # 保存
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        print(f"[Analyzer] Config saved for {config.name}", file=sys.stderr)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='SmartJobHunter legacy 模板分析器')
    parser.add_argument('--analyze', type=str, help='分析指定公司')
    parser.add_argument('--url', type=str, help='分析指定 URL')
    parser.add_argument('--save', action='store_true', help='保存配置')

    args = parser.parse_args()

    analyzer = AutoAnalyzer()

    if args.analyze:
        config = analyzer.analyze_new_company(args.analyze)
        if config:
            print(analyzer.to_yaml(config))
            if args.save:
                analyzer.save_config(config)

    elif args.url:
        config = analyzer.analyze_url(args.url)
        if config:
            print(analyzer.to_yaml(config))
            if args.save:
                analyzer.save_config(config)

    else:
        parser.print_help()
