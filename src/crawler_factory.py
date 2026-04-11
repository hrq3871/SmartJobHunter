#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 爬虫工厂
根据公司ID创建爬虫实例，统一管理爬虫生命周期
"""

import sys
import yaml
from pathlib import Path
from typing import Optional, List, Dict

from .config_crawler import ConfigCrawler, create_crawler_from_config


# 加载公司配置
def _load_companies_config() -> dict:
    """加载公司配置文件"""
    config_path = Path(__file__).parent.parent / "config" / "companies.yaml"
    if not config_path.exists():
        print(f"[Error] Config file not found: {config_path}", file=sys.stderr)
        return {'companies': []}

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {'companies': []}


# 全局配置缓存
_COMPANIES_CONFIG = None


def get_companies_config() -> dict:
    """获取公司配置（带缓存）"""
    global _COMPANIES_CONFIG
    if _COMPANIES_CONFIG is None:
        _COMPANIES_CONFIG = _load_companies_config()
    return _COMPANIES_CONFIG


def reload_config():
    """重新加载配置"""
    global _COMPANIES_CONFIG
    _COMPANIES_CONFIG = None
    get_companies_config()


def get_company_config(company_id: str) -> Optional[dict]:
    """获取指定公司的配置

    Args:
        company_id: 公司ID

    Returns:
        公司配置字典，不存在则返回 None
    """
    config = get_companies_config()
    for company in config.get('companies', []):
        if company.get('id') == company_id:
            return company
    return None


def list_companies(enabled_only: bool = True) -> List[dict]:
    """列出所有公司

    Args:
        enabled_only: 是否只返回启用的公司

    Returns:
        公司配置列表
    """
    config = get_companies_config()
    companies = config.get('companies', [])

    if enabled_only:
        return [c for c in companies if c.get('enabled', False)]
    return companies


def get_enabled_companies(job_type: str = None) -> List[dict]:
    """获取启用的公司列表

    Args:
        job_type: 筛选支持该岗位性质的公司 (social/campus/internship)

    Returns:
        公司配置列表
    """
    config = get_companies_config()
    companies = []

    for company in config.get('companies', []):
        if not company.get('enabled', False):
            continue

        # 如果指定了岗位类型，检查公司是否支持
        if job_type:
            urls = company.get('urls', {})
            if job_type not in urls:
                continue

        companies.append(company)

    return companies


def create_crawler(company_id: str) -> Optional[ConfigCrawler]:
    """创建爬虫实例

    Args:
        company_id: 公司ID

    Returns:
        ConfigCrawler 实例，配置无效则返回 None
    """
    config = get_company_config(company_id)
    if not config:
        print(f"[Error] Company not found: {company_id}", file=sys.stderr)
        return None

    if not config.get('enabled', False):
        print(f"[Warn] Company disabled: {config.get('name', company_id)}", file=sys.stderr)
        return None

    # 使用配置驱动爬虫
    crawler = create_crawler_from_config(config)
    if crawler:
        return crawler

    # 回退提示
    print(f"[Warn] Cannot create crawler for {company_id}: missing field_mappings", file=sys.stderr)
    return None


def crawl_company(
    company_id: str,
    keyword: str,
    max_jobs: int = 50,
    job_type: str = 'social',
    headless: bool = True,
) -> List[dict]:
    """爬取单个公司的岗位

    Args:
        company_id: 公司ID
        keyword: 搜索关键词
        max_jobs: 最大岗位数
        job_type: 岗位类型
        headless: 是否无头模式

    Returns:
        岗位列表
    """
    crawler = create_crawler(company_id)
    if not crawler:
        return []

    try:
        return crawler.crawl(
            keyword=keyword,
            max_jobs=max_jobs,
            job_type=job_type,
            headless=headless,
        )
    except Exception as e:
        print(f"[Error] Crawl failed for {company_id}: {e}", file=sys.stderr)
        return []


def crawl_all(
    keyword: str,
    job_type: str = 'social',
    max_jobs: int = 50,
    headless: bool = True,
) -> List[dict]:
    """爬取所有启用的公司

    Args:
        keyword: 搜索关键词
        job_type: 岗位类型
        max_jobs: 每个公司最大岗位数
        headless: 是否无头模式

    Returns:
        所有岗位列表
    """
    all_jobs = []
    companies = get_enabled_companies(job_type)

    print(f"[Crawler] Found {len(companies)} enabled companies for {job_type}", file=sys.stderr)

    for company in companies:
        company_id = company.get('id')
        company_name = company.get('name')

        print(f"[Crawler] Crawling {company_name}...", file=sys.stderr)

        try:
            jobs = crawl_company(
                company_id=company_id,
                keyword=keyword,
                max_jobs=max_jobs,
                job_type=job_type,
                headless=headless,
            )
            all_jobs.extend(jobs)
            print(f"[Crawler] {company_name}: {len(jobs)} jobs", file=sys.stderr)
        except Exception as e:
            print(f"[Crawler] {company_name} failed: {e}", file=sys.stderr)

    print(f"[Crawler] Total: {len(all_jobs)} jobs from {len(companies)} companies", file=sys.stderr)
    return all_jobs


def test_crawler(company_id: str, keyword: str = '产品经理', max_jobs: int = 5) -> bool:
    """测试爬虫是否正常工作

    Args:
        company_id: 公司ID
        keyword: 测试关键词
        max_jobs: 测试岗位数

    Returns:
        是否成功
    """
    print(f"\n[Test] Testing crawler for {company_id}...")
    jobs = crawl_company(company_id, keyword, max_jobs)

    if jobs:
        print(f"[Test] SUCCESS: Got {len(jobs)} jobs")
        for i, job in enumerate(jobs[:3]):
            print(f"  {i+1}. {job.get('title', 'N/A')} - {job.get('location', 'N/A')}")
        return True
    else:
        print(f"[Test] FAILED: No jobs returned")
        return False


if __name__ == '__main__':
    # 命令行测试
    import argparse

    parser = argparse.ArgumentParser(description='SmartJobHunter Crawler Factory')
    parser.add_argument('--list', action='store_true', help='List all companies')
    parser.add_argument('--test', type=str, help='Test crawler for company ID')
    parser.add_argument('--crawl', type=str, help='Crawl company ID')
    parser.add_argument('--keyword', type=str, default='产品经理', help='Search keyword')
    parser.add_argument('--max-jobs', type=int, default=5, help='Max jobs per company')

    args = parser.parse_args()

    if args.list:
        print("\nEnabled Companies:")
        for company in get_enabled_companies():
            has_mapping = 'field_mappings' in company
            status = "[OK]" if has_mapping else "[WARN]"
            print(f"  {status} {company.get('id')}: {company.get('name')}")

    elif args.test:
        test_crawler(args.test, args.keyword, args.max_jobs)

    elif args.crawl:
        jobs = crawl_company(args.crawl, args.keyword, args.max_jobs)
        print(f"\nCrawled {len(jobs)} jobs:")
        for job in jobs:
            print(f"  - {job.get('title')}")

    else:
        parser.print_help()
