#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量测试爬虫脚本
测试所有已配置的爬虫，生成测试报告
"""

__test__ = False

import sys
import time
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler_factory import (
    get_companies_config,
    create_crawler,
    reload_config,
)


def test_single_crawler(company_id: str, keyword: str = '产品经理', max_jobs: int = 5, headless: bool = True):
    """测试单个爬虫

    Returns:
        dict: 测试结果
    """
    reload_config()

    result = {
        'company_id': company_id,
        'status': 'unknown',
        'jobs_count': 0,
        'sample_jobs': [],
        'error': None,
        'api_captured': False,
    }

    try:
        crawler = create_crawler(company_id)
        if not crawler:
            result['status'] = 'config_error'
            result['error'] = 'Cannot create crawler (missing config)'
            return result

        jobs = crawler.crawl(
            keyword=keyword,
            max_jobs=max_jobs,
            headless=headless,
        )

        if jobs:
            result['status'] = 'success'
            result['jobs_count'] = len(jobs)
            result['sample_jobs'] = [
                {
                    'title': j.get('title', ''),
                    'location': j.get('location', ''),
                    'url': j.get('url', '')[:80] + '...' if len(j.get('url', '')) > 80 else j.get('url', ''),
                }
                for j in jobs[:3]
            ]
        else:
            result['status'] = 'no_jobs'
            result['error'] = 'Crawler returned 0 jobs'

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:200]

    return result


def test_all_crawlers(
    keyword: str = '产品经理',
    max_jobs: int = 5,
    headless: bool = True,
    include_disabled: bool = False,
):
    """测试所有爬虫

    Returns:
        dict: 测试报告
    """
    reload_config()
    config = get_companies_config()

    report = {
        'timestamp': datetime.now().isoformat(),
        'keyword': keyword,
        'max_jobs': max_jobs,
        'results': [],
        'summary': {
            'total': 0,
            'success': 0,
            'failed': 0,
            'config_error': 0,
            'no_jobs': 0,
        }
    }

    companies = config.get('companies', [])

    if not include_disabled:
        # 只测试启用的公司
        companies = [c for c in companies if c.get('enabled', False)]

    # 也测试有 field_mappings 但未启用的公司
    if not include_disabled:
        companies_with_mapping = [
            c for c in config.get('companies', [])
            if c.get('field_mappings') and not c.get('enabled', False)
        ]
        print(f"\n[Info] Found {len(companies_with_mapping)} disabled companies with field_mappings", file=sys.stderr)

    report['summary']['total'] = len(companies)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Testing {len(companies)} crawlers with keyword: {keyword}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    for i, company in enumerate(companies, 1):
        company_id = company.get('id')
        company_name = company.get('name')
        enabled = company.get('enabled', False)
        has_mapping = 'field_mappings' in company

        print(f"[{i}/{len(companies)}] Testing {company_name} ({company_id})...", file=sys.stderr)
        print(f"    enabled={enabled}, has_mapping={has_mapping}", file=sys.stderr)

        if not has_mapping:
            print(f"    SKIP: No field_mappings", file=sys.stderr)
            result = {
                'company_id': company_id,
                'company_name': company_name,
                'status': 'config_error',
                'error': 'No field_mappings defined',
            }
        else:
            result = test_single_crawler(company_id, keyword, max_jobs, headless)
            result['company_name'] = company_name

        report['results'].append(result)

        # 更新统计
        status = result.get('status', 'unknown')
        if status == 'success':
            report['summary']['success'] += 1
            print(f"    SUCCESS: {result['jobs_count']} jobs", file=sys.stderr)
        elif status == 'config_error':
            report['summary']['config_error'] += 1
            print(f"    CONFIG_ERROR: {result.get('error', '')}", file=sys.stderr)
        elif status == 'no_jobs':
            report['summary']['no_jobs'] += 1
            print(f"    NO_JOBS: {result.get('error', '')}", file=sys.stderr)
        else:
            report['summary']['failed'] += 1
            print(f"    FAILED: {result.get('error', '')}", file=sys.stderr)

        # 避免请求过快
        time.sleep(2)

    return report


def print_report(report: dict):
    """打印测试报告"""
    print(f"\n{'='*60}")
    print("TEST REPORT SUMMARY")
    print(f"{'='*60}")
    print(f"Timestamp: {report['timestamp']}")
    print(f"Keyword: {report['keyword']}")
    print(f"Max Jobs: {report['max_jobs']}")
    print(f"\nSummary:")
    print(f"  Total:      {report['summary']['total']}")
    print(f"  Success:    {report['summary']['success']}")
    print(f"  No Jobs:    {report['summary']['no_jobs']}")
    print(f"  Config Err: {report['summary']['config_error']}")
    print(f"  Failed:     {report['summary']['failed']}")

    print(f"\n{'='*60}")
    print("DETAILED RESULTS")
    print(f"{'='*60}")

    # 按状态分组
    success_results = [r for r in report['results'] if r.get('status') == 'success']
    no_jobs_results = [r for r in report['results'] if r.get('status') == 'no_jobs']
    failed_results = [r for r in report['results'] if r.get('status') in ('error', 'config_error')]

    if success_results:
        print(f"\n[OK] SUCCESS ({len(success_results)}):")
        for r in success_results:
            print(f"   {r['company_name']}: {r['jobs_count']} jobs")
            for j in r.get('sample_jobs', [])[:2]:
                print(f"      - {j['title']} | {j['location']}")

    if no_jobs_results:
        print(f"\n[WARN] NO JOBS ({len(no_jobs_results)}):")
        for r in no_jobs_results:
            print(f"   {r['company_name']}: {r.get('error', '')}")

    if failed_results:
        print(f"\n[FAIL] FAILED ({len(failed_results)}):")
        for r in failed_results:
            print(f"   {r['company_name']}: {r.get('error', '')}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Test crawlers')
    parser.add_argument('--company', type=str, help='Test single company by ID')
    parser.add_argument('--keyword', type=str, default='产品经理', help='Search keyword')
    parser.add_argument('--max-jobs', type=int, default=5, help='Max jobs per company')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window')
    parser.add_argument('--include-disabled', action='store_true', help='Include disabled companies')
    parser.add_argument('--output', type=str, help='Output report to JSON file')

    args = parser.parse_args()

    headless = not args.no_headless

    if args.company:
        # 测试单个公司
        result = test_single_crawler(args.company, args.keyword, args.max_jobs, headless)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 测试所有公司
        report = test_all_crawlers(
            keyword=args.keyword,
            max_jobs=args.max_jobs,
            headless=headless,
            include_disabled=args.include_disabled,
        )

        print_report(report)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\nReport saved to: {args.output}")


if __name__ == '__main__':
    main()
