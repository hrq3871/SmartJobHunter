#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""新版 Mokahr 招聘平台抓取策略 (Playwright DOM 提取).

适用条件：
- 新版 Mokahr (API 响应加密, api.type ≠ "intercept")
- URL 格式: https://app.mokahr.com/{type}/{company}/{id}#/jobs
- 岗位数据通过 SPA hash 路由渲染，无可用明文 API

本策略使用 Playwright 加载列表页 → JS 提取 DOM → 逐岗点入详情页获取完整 JD.
"""

from __future__ import annotations

import re
import sys
import time
from typing import Dict, List
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from .base import SiteStrategy

# 岗位列表页卡片容器 — 新版 Mokahr 使用 hash 后缀的 CSS Module class
JOB_LIST_CONTAINER_SELECTOR = '[class*="jobs-"]'
JOB_CARD_SELECTOR = 'div[class*="container-"][class*="card-"]'

# 卡片内字段选择器 (相对于卡片元素)
# 注意: 不同 Mokahr 实例可能用 <span> 或 <div>，统一用 * 匹配
TITLE_SELECTOR = '*[class*="title-"]'
PUBLISH_TIME_SELECTOR = '*[class*="published-at-"]'
LINK_SELECTOR = 'a[class*="link-"]'
INFO_ROW_SELECTOR = '[class*="ellipsis-"]'
INFO_CELL_SELECTOR = '[class*="foundation-body-secondary"]'

# 详情页选择器
JOB_DESCRIPTION_SELECTOR = '[class*="job-description"]'


def _ensure_hash_jobs(url: str) -> str:
    """确保 Mokahr URL 带有 #/jobs hash，否则 SPA 不会渲染岗位列表."""
    if "#/jobs" in url:
        return url
    if "#/job/" in url:
        # 详情页 URL，回退到列表
        base = url.split("#/job/")[0]
        return f"{base}#/jobs"
    if "#" in url:
        base = url.split("#")[0]
        return f"{base}#/jobs"
    return f"{url}#/jobs"


def _build_detail_url(list_url: str, job_uuid: str) -> str:
    """从列表页 URL 和岗位 UUID 构造详情页 URL."""
    base = list_url.split("#")[0]
    return f"{base}#/job/{job_uuid}"


def _parse_duty_requirement(desc_text: str) -> tuple[str, str]:
    """从详情页文本中分离岗位职责和任职要求."""
    duty = ""
    requirement = ""

    # 常见分隔标记
    patterns = [
        (r"岗位职责[：:]\s*", r"任职要求[：:]\s*"),
        (r"职位描述[：:]\s*", r"任职要求[：:]\s*"),
        (r"工作职责[：:]\s*", r"任职要求[：:]\s*"),
        (r"岗位职责[：:]\s*", r"任职资格[：:]\s*"),
        (r"职位描述[：:]\s*", r"任职资格[：:]\s*"),
        (r"工作内容[：:]\s*", r"岗位要求[：:]\s*"),
    ]

    for duty_pat, req_pat in patterns:
        m_duty = re.search(duty_pat, desc_text)
        m_req = re.search(req_pat, desc_text)
        if m_duty and m_req and m_duty.start() < m_req.start():
            duty = desc_text[m_duty.end():m_req.start()].strip()
            requirement = desc_text[m_req.end():].strip()
            break

    if not duty and not requirement:
        # 无标准分隔标记时，全文归入 duty
        duty = desc_text.strip()

    # 清理多余空行
    duty = re.sub(r"\n{3,}", "\n\n", duty)
    requirement = re.sub(r"\n{3,}", "\n\n", requirement)

    return duty, requirement


class Strategy(SiteStrategy):
    """新版 Mokahr DOM 抓取策略."""

    def crawl(
        self,
        keyword: str,
        max_jobs: int,
        job_type: str,
        headless: bool = True,
    ) -> List[dict]:
        url = self.company_config.get("links", {}).get(job_type) or ""
        if not url:
            urls = self.company_config.get("urls", {})
            url = urls.get(job_type) or urls.get("campus") or urls.get("social") or ""
        if not url:
            print(f"[Mokahr] No URL configured for {self.company_id}", file=sys.stderr)
            return []

        url = _ensure_hash_jobs(url)
        if "{keyword}" in url:
            url = url.replace("{keyword}", keyword)

        company_name = self.company_config.get("name", self.company_id)
        print(f"[Mokahr] Crawling {company_name}: {url}", file=sys.stderr)

        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            page = context.new_page()

            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)

                # 提取岗位列表 — 使用 href="#/job/<uuid>" 作为锚点，兼容各版 Mokahr
                card_data = page.evaluate(
                    f"""
                    () => {{
                        const container = document.querySelector('{JOB_LIST_CONTAINER_SELECTOR}');
                        if (!container) return [];
                        // 以指向详情页的 <a> 为准，不再依赖 card- class
                        const links = container.querySelectorAll('a[href*="#/job/"]');
                        return Array.from(links).map(link => {{
                            // 向上找最近的 container- div（可能在外层也可能在内层）
                            const card = link.closest('div[class*="container-"]')
                                      || link.querySelector('div[class*="container-"]')
                                      || link.parentElement;
                            const titleEl = (card || link).querySelector('{TITLE_SELECTOR}');
                            const timeEl = (card || link).querySelector('{PUBLISH_TIME_SELECTOR}');
                            const cells = (card || link).querySelectorAll(
                                '{INFO_ROW_SELECTOR} {INFO_CELL_SELECTOR}'
                            );
                            const infoFields = Array.from(cells).map(el =>
                                el.textContent.trim()
                            );
                            return {{
                                href: link ? link.getAttribute('href') : '',
                                title: titleEl ? titleEl.textContent.trim() : '',
                                publish_time: timeEl ? timeEl.textContent.trim().replace('发布于 ', '') : '',
                                info_fields: infoFields,
                            }};
                        }});
                    }}
                    """
                )

                if not card_data:
                    print(f"[Mokahr] No job cards found on {url}", file=sys.stderr)
                    return []

                print(f"[Mokahr] Found {len(card_data)} cards, extracting up to {max_jobs}", file=sys.stderr)

                detail_collect = max_jobs <= 10  # 超过 10 个时不逐岗取详情

                for idx, card in enumerate(card_data[:max_jobs]):
                    href = card.get("href", "")
                    title = card.get("title", "")
                    if not title:
                        continue

                    job_uuid = href.split("/")[-1] if "/" in href else ""
                    detail_url = _build_detail_url(url, job_uuid) if job_uuid else url

                    info = card.get("info_fields", [])
                    # info_fields 顺序通常为: [类型, 部门, 学历, 地点]
                    # 最后一项多为地点，倒数第二可能是学历
                    location = info[-1] if len(info) >= 1 else ""
                    category = info[1] if len(info) >= 2 else ""
                    education = info[2] if len(info) >= 3 else ""
                    inferred_job_type = _detect_job_type(info[0] if info else "", job_type)

                    duty = ""
                    requirement = ""

                    # 点入详情页获取完整 JD
                    if detail_collect and job_uuid:
                        try:
                            page.goto(detail_url, timeout=30000, wait_until="domcontentloaded")
                            page.wait_for_timeout(3000)
                            desc_el = page.query_selector(JOB_DESCRIPTION_SELECTOR)
                            if desc_el:
                                desc_text = desc_el.inner_text()
                                duty, requirement = _parse_duty_requirement(desc_text)
                        except Exception as exc:
                            print(f"  [Mokahr] Detail fetch failed for {title[:30]}: {exc}", file=sys.stderr)

                    import hashlib
                    job_hash = hashlib.md5(
                        f"{self.company_id}:{job_uuid or title}".encode()
                    ).hexdigest()

                    jobs.append({
                        "title": title,
                        "company": company_name,
                        "location": location,
                        "category": category,
                        "education": education,
                        "url": detail_url,
                        "publish_time": card.get("publish_time", ""),
                        "duty": duty,
                        "requirement": requirement,
                        "hash": job_hash,
                        "source": self.company_id,
                        "job_type": inferred_job_type,
                        "raw_info": info,
                    })

                    if idx < len(card_data[:max_jobs]) - 1 and detail_collect:
                        # 回到列表页继续下一个
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        page.wait_for_timeout(2000)

            except Exception as exc:
                print(f"[Mokahr] Crawl error: {exc}", file=sys.stderr)
            finally:
                context.close()
                browser.close()

        print(f"[Mokahr] {company_name}: {len(jobs)} jobs extracted", file=sys.stderr)
        return jobs


def _detect_job_type(raw: str, default_type: str = "social") -> str:
    """从 info row 第一个字段推断岗位类型，无匹配时使用请求的默认类型."""
    text = raw.lower()
    if any(kw in text for kw in ["实习", "intern"]):
        return "internship"
    if any(kw in text for kw in ["校招", "应届", "campus", "graduate"]):
        return "campus"
    return default_type or "social"
