#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 通用爬虫基类
提供所有爬虫共用的基础功能
"""

import sys
import hashlib
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Response, Browser, BrowserContext

from .browser_interactions import click_generic_search_button, perform_generic_search


class BaseCrawler:
    """通用爬虫基类

    提供浏览器创建、数据提取、字段解析等通用功能
    子类需要实现 parse_job 和 crawl 方法
    """

    def __init__(self, config: dict):
        """初始化爬虫

        Args:
            config: 公司配置字典
        """
        self.config = config
        self.jobs: List[dict] = []
        self.seen_ids: set = set()

    def generate_hash(self, job_id: str) -> str:
        """生成岗位唯一哈希

        Args:
            job_id: 岗位ID

        Returns:
            MD5 哈希字符串
        """
        return hashlib.md5(job_id.encode()).hexdigest()

    def create_browser(self, p, headless: bool = True) -> tuple:
        """创建浏览器实例

        Args:
            p: Playwright 实例
            headless: 是否无头模式

        Returns:
            (browser, context) 元组
        """
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        return browser, context

    def extract_data(self, response_data: dict, data_path: str) -> list:
        """从响应数据中提取岗位列表

        支持点号分隔的路径，如 "Data.Posts" 或 "data.job_post_list"

        Args:
            response_data: API 响应数据
            data_path: 数据路径

        Returns:
            岗位列表
        """
        if not data_path:
            return []

        keys = data_path.split('.')
        data = response_data

        for key in keys:
            if data is None:
                return []

            if isinstance(data, dict):
                data = data.get(key)
            elif isinstance(data, list) and key.isdigit():
                idx = int(key)
                data = data[idx] if idx < len(data) else None
            else:
                return []

        return data if isinstance(data, list) else []

    def parse_field(self, item: dict, mapping: dict) -> str:
        """解析单个字段

        支持点号访问嵌套字段，如 "city_info.name"

        Args:
            item: 原始数据项
            mapping: 字段映射配置 {"source": "xxx", "default": "xxx"}

        Returns:
            字段值字符串
        """
        if not mapping:
            return ''

        source = mapping.get('source', '')
        if not source:
            return mapping.get('default', '')

        # 支持点号访问嵌套字段
        keys = source.split('.')
        value = item

        for key in keys:
            if value is None:
                break

            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list):
                if key.isdigit():
                    idx = int(key)
                    value = value[idx] if idx < len(value) else None
                elif len(value) > 0:
                    # 如果是列表且不是数字索引，取第一个元素继续
                    value = value[0].get(key) if isinstance(value[0], dict) else None
                else:
                    value = None
            else:
                value = None
                break

        if value is None:
            return mapping.get('default', '')

        # 处理列表类型
        if isinstance(value, list):
            if len(value) > 0 and isinstance(value[0], dict):
                # 尝试获取 name 字段
                return value[0].get('name', str(value[0]))
            return value[0] if value else mapping.get('default', '')

        # 处理时间戳
        if isinstance(value, (int, float)) and value > 1000000000000:
            try:
                dt = datetime.fromtimestamp(value / 1000)
                return dt.strftime('%Y-%m-%d')
            except:
                pass

        return str(value) if value else mapping.get('default', '')

    def detect_job_type(self, title: str) -> str:
        """检测岗位类型

        Args:
            title: 岗位标题

        Returns:
            岗位类型: internship/campus/social
        """
        detection = self.config.get('job_type_detection', {})
        title_lower = title.lower()

        # 按优先级检测
        for job_type in ['internship', 'campus']:
            keywords = detection.get(job_type, [])
            for kw in keywords:
                if kw.lower() in title_lower:
                    return job_type

        return 'social'

    def parse_job(self, item: dict) -> Optional[dict]:
        """解析单个岗位数据

        子类必须实现此方法

        Args:
            item: 原始岗位数据

        Returns:
            标准化的岗位字典，或 None（解析失败）
        """
        raise NotImplementedError("Subclass must implement parse_job()")

    def crawl(self, keyword: str, max_jobs: int = 50, **kwargs) -> list:
        """执行爬取

        子类必须实现此方法

        Args:
            keyword: 搜索关键词
            max_jobs: 最大岗位数

        Returns:
            岗位列表
        """
        raise NotImplementedError("Subclass must implement crawl()")


class InterceptCrawler(BaseCrawler):
    """API 拦截爬虫

    通过拦截浏览器 XHR/Fetch 请求获取数据
    适用于大多数现代招聘网站
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_pattern = config.get('api', {}).get('pattern', '')
        self.data_path = config.get('api', {}).get('data_path', '')

    def handle_response(self, response: Response, intercepted: list):
        """处理响应，拦截匹配的 API

        Args:
            response: Playwright Response 对象
            intercepted: 拦截数据列表
        """
        if self.api_pattern in response.url and response.status == 200:
            try:
                data = response.json()
                intercepted.append(data)
                print(f"  [API] Captured: {response.url[:80]}...", file=sys.stderr)
            except Exception as e:
                print(f"  [API] Parse error: {e}", file=sys.stderr)

    def _try_search(self, page: Page, keyword: str):
        """尝试在页面上搜索关键词

        Args:
            page: Playwright Page 对象
            keyword: 搜索关键词
        """
        actions = perform_generic_search(page, keyword)
        if actions:
            print(f"  [Search] Searched for: {keyword}", file=sys.stderr)
        return bool(actions)

    def _click_search_button(self, page: Page) -> bool:
        """Click a visible search button when Enter alone is not enough."""
        return click_generic_search_button(page)

    def crawl_with_intercept(
        self,
        url: str,
        keyword: str,
        max_jobs: int = 50,
        headless: bool = True,
        max_pages: int = 5,
    ) -> list:
        """使用拦截模式爬取

        Args:
            url: 起始 URL
            keyword: 搜索关键词
            max_jobs: 最大岗位数
            headless: 是否无头模式
            max_pages: 最大翻页数

        Returns:
            岗位列表
        """
        jobs = []
        seen_ids = set()

        with sync_playwright() as p:
            browser, context = self.create_browser(p, headless)
            page = context.new_page()

            intercepted_data = []

            def handle_response(response):
                self.handle_response(response, intercepted_data)

            page.on('response', handle_response)

            try:
                print(f"[Crawler] Accessing {self.config.get('name', 'Unknown')}...", file=sys.stderr)
                page.goto(url, timeout=60000, wait_until='domcontentloaded')
                page.wait_for_timeout(5000)

                # 很多官网首屏会先返回默认岗位列表；有关键词时必须主动尝试搜索，
                # 否则会把默认列表当成搜索结果。
                if keyword:
                    initial_data = list(intercepted_data)
                    intercepted_data.clear()
                    searched = self._try_search(page, keyword)
                    if searched:
                        page.wait_for_timeout(5000)
                    if not searched or not intercepted_data:
                        intercepted_data.extend(initial_data)
                elif not intercepted_data:
                    print(f"  [Search] No API captured, trying search interaction...", file=sys.stderr)
                    self._try_search(page, keyword)
                    page.wait_for_timeout(5000)

                # 解析拦截的数据
                for data in intercepted_data:
                    items = self.extract_data(data, self.data_path)
                    for item in items:
                        job = self.parse_job(item)
                        if job and job.get('hash') not in seen_ids:
                            seen_ids.add(job['hash'])
                            jobs.append(job)

                print(f"   Page 1: {len(jobs)} jobs", file=sys.stderr)

                # 翻页
                page_count = 2
                while len(jobs) < max_jobs and page_count <= max_pages:
                    clicked = self.click_next_page(page)
                    if not clicked:
                        break

                    page.wait_for_timeout(3000)

                    # 解析新数据
                    new_count = 0
                    for data in intercepted_data:
                        items = self.extract_data(data, self.data_path)
                        for item in items:
                            job = self.parse_job(item)
                            if job and job.get('hash') not in seen_ids:
                                seen_ids.add(job['hash'])
                                jobs.append(job)
                                new_count += 1

                    print(f"   Page {page_count}: +{new_count} jobs", file=sys.stderr)
                    page_count += 1
                    intercepted_data.clear()

                print(f"[Done] {self.config.get('name', 'Unknown')}: {len(jobs)} jobs", file=sys.stderr)

            except Exception as e:
                print(f"[Error] Crawl failed: {e}", file=sys.stderr)
            finally:
                context.close()
                browser.close()

        return jobs[:max_jobs]

    def click_next_page(self, page: Page) -> bool:
        """点击下一页

        Args:
            page: Playwright Page 对象

        Returns:
            是否成功点击
        """
        selectors = [
            '[class*="next"]',
            '[class*="pagination"] [class*="next"]',
            '.ant-pagination-next',
            'button[aria-label="下一页"]',
            '.next',
        ]

        for selector in selectors:
            try:
                element = page.query_selector(selector)
                if element and element.is_visible() and element.is_enabled():
                    element.click()
                    return True
            except:
                continue

        return False
