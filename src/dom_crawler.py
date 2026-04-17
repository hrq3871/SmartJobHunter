#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter DOM 爬虫
使用 CDP Proxy (localhost:3456) 解析 DOM 提取岗位数据
"""

import sys
import time
import json
import subprocess
from typing import Optional, List, Dict, Any
from .base_crawler import InterceptCrawler


class DomCrawler(InterceptCrawler):
    """DOM 解析爬虫

    通过 CDP Proxy (localhost:3456) 访问页面，使用 CSS 选择器提取岗位数据
    适用于没有公开 API 的网站（如 Workday）
    """

    def __init__(self, company_config: dict):
        """初始化 DOM 爬虫

        Args:
            company_config: 公司配置字典，需要包含:
                - id: 公司ID
                - name: 公司名称
                - urls: 不同岗位类型的URL
                - api.selectors: DOM 选择器配置
                - url_template: 岗位详情页模板
        """
        super().__init__(company_config)
        self.company_id = company_config.get("id", "")
        self.company_name = company_config.get("name", "")
        self.selectors = company_config.get("api", {}).get("selectors", {})
        self.url_template = company_config.get("url_template", "")
        self.urls = company_config.get("urls", {})
        self.proxy_port = 3456

    def _curl(self, path: str, method: str = "GET", data: str = None) -> Any:
        """通过 curl 调用 CDP Proxy API

        Args:
            path: API 路径 (如 /targets, /eval?target=xxx)
            method: HTTP 方法
            data: POST 数据

        Returns:
            JSON 响应，失败返回 None
        """
        url = f"http://localhost:{self.proxy_port}{path}"

        cmd = ["curl", "-s"]
        if method == "POST":
            cmd.extend(["-X", "POST"])
            if data:
                cmd.extend(["-d", data])
        cmd.append(url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            text = result.stdout.strip()
            if text:
                return json.loads(text)
            return None
        except subprocess.TimeoutExpired:
            print(f"[Error] CDP Proxy timeout", file=sys.stderr)
            return None
        except json.JSONDecodeError:
            return text
        except Exception as e:
            print(f"[Error] CDP Proxy error: {e}", file=sys.stderr)
            return None

    def _list_targets(self) -> List[dict]:
        """列出所有打开的 tab"""
        return self._curl("/targets") or []

    def _new_tab(self, url: str) -> str:
        """创建新 tab，返回 targetId"""
        result = self._curl(f"/new?url={url}")
        if isinstance(result, dict):
            return result.get("targetId", "")
        return ""

    def _close_tab(self, target_id: str) -> bool:
        """关闭 tab"""
        self._curl(f"/close?target={target_id}")
        return True

    def _eval_js(self, target_id: str, script: str) -> Any:
        """执行 JavaScript"""
        return self._curl(f"/eval?target={target_id}", method="POST", data=script)

    def _click(self, target_id: str, selector: str) -> bool:
        """点击元素"""
        self._curl(f"/click?target={target_id}", method="POST", data=selector)
        return True

    def _scroll(self, target_id: str, direction: str = "bottom") -> bool:
        """滚动页面"""
        self._curl(f"/scroll?target={target_id}&direction={direction}")
        return True

    def _extract_jobs_dom(self, target_id: str, max_jobs: int = 50) -> List[dict]:
        """使用 DOM 选择器提取岗位

        Args:
            target_id: 目标 tab ID
            max_jobs: 最大岗位数

        Returns:
            岗位列表
        """
        container_selector = self.selectors.get("job_container", ".job-item")

        # 构建提取脚本
        script = f"""
        (function() {{
            const jobs = [];
            const containers = document.querySelectorAll('{container_selector}');
            const maxJobs = {max_jobs};

            for (let i = 0; i < Math.min(containers.length, maxJobs); i++) {{
                const container = containers[i];
                const job = {{}};

                // 提取各字段
                const fields = {json.dumps(list(self.selectors.keys()))};
                const selectorsMap = {json.dumps(self.selectors)};

                for (const field of fields) {{
                    if (field === 'job_container') continue;
                    const sel = selectorsMap[field];
                    const el = container.querySelector(sel);
                    if (el) {{
                        if (el.tagName === 'A') {{
                            job[field] = el.href || el.textContent.trim();
                        }} else {{
                            job[field] = el.textContent.trim();
                        }}
                    }}
                }}

                if (job.title || job.id) {{
                    jobs.push(job);
                }}
            }}

            return jobs;
        }})();
        """

        return self._eval_js(target_id, script) or []

    def parse_job(self, item: dict) -> Optional[dict]:
        """解析单个岗位数据

        Args:
            item: 从 DOM 提取的原始数据

        Returns:
            标准化的岗位字典
        """
        if not item:
            return None

        # 获取岗位ID（从 URL 或其他字段）
        job_id = item.get("id", "")
        if not job_id:
            # 尝试从 URL 提取 ID
            url = item.get("url", "")
            if url:
                import hashlib
                job_id = hashlib.md5(url.encode()).hexdigest()[:12]

        if not job_id:
            return None

        # 获取标题
        title = item.get("title", "")
        if not title:
            return None

        # 构建岗位 URL
        job_url = item.get("url", "")
        if not job_url and self.url_template and job_id:
            job_url = self.url_template.format(id=item.get("id", job_id))

        # 检测岗位类型
        job_type = self.detect_job_type(title)

        return {
            "title": title,
            "company": self.company_name,
            "location": item.get("location", ""),
            "category": item.get("category", ""),
            "url": job_url,
            "publish_time": item.get("publish_time", ""),
            "duty": item.get("duty", ""),
            "requirement": item.get("requirement", ""),
            "hash": self.generate_hash(job_id),
            "source": self.company_id,
            "job_type": job_type,
        }

    def crawl(
        self,
        keyword: str,
        max_jobs: int = 50,
        headless: bool = True,
        job_type: str = "social",
        max_pages: int = 5,
    ) -> List[dict]:
        """执行爬取

        Args:
            keyword: 搜索关键词
            max_jobs: 最大岗位数
            headless: 是否无头模式（CDP 模式忽略）
            job_type: 岗位类型
            max_pages: 最大翻页数

        Returns:
            岗位列表
        """
        jobs = []
        seen_ids = set()

        # 获取 URL
        url = self.urls.get(job_type, self.urls.get("social", ""))
        if not url:
            print(f"[Error] No URL for {self.company_name} (job_type={job_type})", file=sys.stderr)
            return []

        # 替换关键词
        url = url.replace("{keyword}", keyword)

        print(f"[DomCrawler] Opening {self.company_name}...", file=sys.stderr)

        target_id = None
        try:
            # 创建新 tab
            target_id = self._new_tab(url)
            if not target_id:
                print(f"[Error] Failed to create tab", file=sys.stderr)
                return []

            # 等待页面加载
            time.sleep(3)

            # 尝试搜索
            self._try_search(target_id, keyword)
            time.sleep(2)

            # 提取岗位
            page = 1
            while len(jobs) < max_jobs and page <= max_pages:
                items = self._extract_jobs_dom(target_id, max_jobs - len(jobs))

                new_count = 0
                for item in items:
                    job = self.parse_job(item)
                    if job and job.get("hash") not in seen_ids:
                        seen_ids.add(job["hash"])
                        jobs.append(job)
                        new_count += 1

                print(f"   Page {page}: +{new_count} jobs", file=sys.stderr)

                if new_count == 0 or len(jobs) >= max_jobs:
                    break

                # 翻页
                if not self._click_next(target_id):
                    break

                time.sleep(2)
                page += 1

            print(f"[Done] {self.company_name}: {len(jobs)} jobs", file=sys.stderr)

        except Exception as e:
            print(f"[Error] DomCrawl failed: {e}", file=sys.stderr)
        finally:
            # 关闭 tab
            if target_id:
                self._close_tab(target_id)

        return jobs[:max_jobs]

    def _try_search(self, target_id: str, keyword: str) -> bool:
        """尝试在页面搜索

        Args:
            target_id: 目标 tab ID
            keyword: 搜索关键词

        Returns:
            是否成功搜索
        """
        search_selectors = [
            'input[placeholder*="搜索"]',
            'input[placeholder*="职位"]',
            'input[placeholder*="关键词"]',
            'input[type="text"]',
            ".search-input",
            "#search-input",
        ]

        for selector in search_selectors:
            try:
                # 检查元素是否存在
                exists = self._eval_js(
                    target_id,
                    f'document.querySelector("{selector}") !== null'
                )
                if exists:
                    # 填入关键词
                    self._eval_js(
                        target_id,
                        f'document.querySelector("{selector}").value = "{keyword}"'
                    )
                    # 按 Enter
                    self._eval_js(
                        target_id,
                        f'document.querySelector("{selector}").dispatchEvent(new KeyboardEvent("keydown", {{key: "Enter", code: "Enter"}}))'
                    )
                    return True
            except:
                continue

        return False

    def _click_next(self, target_id: str) -> bool:
        """点击下一页

        Args:
            target_id: 目标 tab ID

        Returns:
            是否成功点击
        """
        next_selectors = [
            '[class*="next"]',
            '[class*="pagination"] [class*="next"]',
            ".ant-pagination-next",
            'button[aria-label="下一页"]',
            ".next",
        ]

        for selector in next_selectors:
            try:
                if self._click(target_id, selector):
                    return True
            except:
                continue

        return False


def create_dom_crawler(company_config: dict) -> Optional[DomCrawler]:
    """创建 DOM 爬虫实例

    Args:
        company_config: 公司配置

    Returns:
        DomCrawler 实例
    """
    # 检查必要字段
    if not company_config.get("id") or not company_config.get("name"):
        return None

    # 检查选择器
    selectors = company_config.get("api", {}).get("selectors", {})
    if not selectors.get("job_container"):
        print(f"[Warn] No job_container selector for {company_config.get('id')}", file=sys.stderr)
        return None

    return DomCrawler(company_config)
