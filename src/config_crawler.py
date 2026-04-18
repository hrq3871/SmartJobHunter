#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 配置驱动爬虫
根据 YAML 配置动态解析岗位数据，无需为每个公司写代码
"""

import sys
from typing import Optional, List
from .base_crawler import InterceptCrawler
from .dom_crawler import DomCrawler


class ConfigCrawler(InterceptCrawler):
    """配置驱动爬虫

    根据 YAML 配置动态解析岗位数据
    添加新公司只需修改配置文件，无需写代码
    """

    def __init__(self, company_config: dict):
        """初始化配置驱动爬虫

        Args:
            company_config: 公司配置字典，包含:
                - id: 公司ID
                - name: 公司名称
                - api: API配置 (pattern, data_path)
                - field_mappings: 字段映射
                - url_template: 岗位详情页模板
                - urls: 不同岗位类型的URL
        """
        super().__init__(company_config)
        self.company_id = company_config.get('id', '')
        self.company_name = company_config.get('name', '')
        self.field_mappings = company_config.get('field_mappings', {})
        self.url_template = company_config.get('url_template', '')
        self.urls = company_config.get('urls', {})

    def parse_job(self, item: dict) -> Optional[dict]:
        """根据字段映射解析岗位

        Args:
            item: 原始岗位数据

        Returns:
            标准化的岗位字典
        """
        if not item:
            return None

        # 获取岗位ID
        id_mapping = self.field_mappings.get('id', {})
        job_id = self.parse_field(item, id_mapping)
        if not job_id:
            return None

        # 解析标题
        title_mapping = self.field_mappings.get('title', {})
        title = self.parse_field(item, title_mapping)
        if not title:
            return None

        # 解析其他字段
        location_mapping = self.field_mappings.get('location', {})
        category_mapping = self.field_mappings.get('category', {})
        publish_time_mapping = self.field_mappings.get('publish_time', {})
        duty_mapping = self.field_mappings.get('duty', {})
        requirement_mapping = self.field_mappings.get('requirement', {})

        # 构建岗位URL
        if self.url_template:
            job_url = self.url_template.format(id=job_id)
        else:
            job_url = f"https://example.com/job/{job_id}"

        # 检测岗位类型
        job_type = self.detect_job_type(title)

        # 构建标准化岗位数据
        job = {
            'title': title,
            'company': self.company_name,
            'location': self.parse_field(item, location_mapping),
            'category': self.parse_field(item, category_mapping),
            'url': job_url,
            'publish_time': self.parse_field(item, publish_time_mapping),
            'duty': self.parse_field(item, duty_mapping),
            'requirement': self.parse_field(item, requirement_mapping),
            'hash': self.generate_hash(job_id),
            'source': self.company_id,
            'job_type': job_type,
        }

        # 添加可选字段
        product_mapping = self.field_mappings.get('product', {})
        if product_mapping:
            job['product'] = self.parse_field(item, product_mapping)

        bg_mapping = self.field_mappings.get('bg', {})
        if bg_mapping:
            job['bg'] = self.parse_field(item, bg_mapping)

        work_years_mapping = self.field_mappings.get('work_years', {})
        if work_years_mapping:
            job['work_years'] = self.parse_field(item, work_years_mapping)

        return job

    def crawl(
        self,
        keyword: str,
        max_jobs: int = 50,
        headless: bool = True,
        job_type: str = 'social',
        max_pages: int = 5,
    ) -> List[dict]:
        """执行爬取

        Args:
            keyword: 搜索关键词
            max_jobs: 最大岗位数
            headless: 是否无头模式
            job_type: 岗位类型 (social/campus)
            max_pages: 最大翻页数

        Returns:
            岗位列表
        """
        # 获取URL
        url = self.urls.get(job_type, self.urls.get('social', ''))
        if not url:
            print(f"[Error] No URL for {self.company_name} (job_type={job_type})", file=sys.stderr)
            return []

        # 替换关键词占位符
        url = url.replace('{keyword}', keyword)
        if '{keyword}' not in self.urls.get(job_type, ''):
            # 如果URL模板没有占位符，尝试添加查询参数
            if '?' in url:
                url = f"{url}&keyword={keyword}"
            else:
                url = f"{url}?keyword={keyword}"

        return self.crawl_with_intercept(
            url=url,
            keyword=keyword,
            max_jobs=max_jobs,
            headless=headless,
            max_pages=max_pages,
        )


def create_crawler_from_config(company_config: dict) -> Optional[object]:
    """从配置创建爬虫实例

    Args:
        company_config: 公司配置字典

    Returns:
        ConfigCrawler 或 DomCrawler 实例，如果配置无效则返回 None
    """
    # 检查必要字段
    if not company_config.get('id') or not company_config.get('name'):
        print(f"[Error] Invalid company config: missing id or name", file=sys.stderr)
        return None

    # 检查是否有字段映射
    if not company_config.get('field_mappings'):
        print(f"[Warn] No field_mappings for {company_config.get('id')}", file=sys.stderr)
        return None

    api_config = company_config.get('api', {})
    api_type = api_config.get('type', 'intercept')

    # DOM 类型：使用 DOM 解析爬虫
    if api_type == 'dom':
        selectors = api_config.get('selectors', {})
        if not selectors.get('job_container'):
            print(f"[Warn] Missing DOM selectors for {company_config.get('id')}", file=sys.stderr)
            return None
        return DomCrawler(company_config)

    # Intercept 类型：使用 API 拦截爬虫
    if not api_config.get('pattern') or not api_config.get('data_path'):
        print(f"[Warn] Missing API config for {company_config.get('id')}", file=sys.stderr)
        return None

    return ConfigCrawler(company_config)
