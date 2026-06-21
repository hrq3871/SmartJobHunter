#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
联想招聘抓取策略
- 社招: jobs.lenovo.com (SuccessFactors DOM 提取)
- 校招/实习: talent.lenovo.com.cn (API intercept)
"""

from __future__ import annotations

import re
import sys
import hashlib
import json as json_mod
from typing import List

from playwright.sync_api import sync_playwright

# ── SuccessFactors DOM selectors (社招) ──────────────────────────
JOB_CARD_SELECTOR = "article.article--result"
TITLE_LINK_SELECTOR = ".article__header__text__title a"
CATEGORY_SELECTOR = "span.paragraph"
SUBTITLE_SPANS_SELECTOR = ".article__header__text__subtitle span"

# ── talent.lenovo.com.cn API (校招/实习) ─────────────────────────
TALENT_API = "gateway/jobBase/list"


def _parse_date(text: str) -> str:
    months = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
        "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
        "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
    }
    m = re.match(r"(\d{1,2})-(\w{3})-(\d{4})", text)
    if m:
        day, mon, year = m.group(1), m.group(2), m.group(3)
        return f"{year}-{month_num}-{int(day):02d}"
    return text


def _extract_id_from_url(url: str) -> str:
    m = re.search(r"JobDetail/(\d+)", url)
    if m:
        return m.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _dismiss_cookie_banner(page) -> None:
    try:
        for text in ["全都接受", "Accept All", "拒绝所有", "跳过"]:
            btn = page.query_selector(f"a:has-text('{text}')")
            if not btn:
                btn = page.query_selector(f"button:has-text('{text}')")
            if btn:
                btn.click()
                page.wait_for_timeout(1000)
                return
    except Exception:
        pass


class Strategy:
    """Playwright strategy: DOM for social, API intercept for campus/internship."""

    def __init__(self, company_config: dict):
        self.company_config = company_config
        self.company_id = company_config.get("id", "lenovo")
        self.company_name = company_config.get("name", "联想")
        self.urls = company_config.get("urls", {})

    def crawl(
        self,
        keyword: str,
        max_jobs: int = 50,
        job_type: str = "social",
        headless: bool = True,
    ) -> List[dict]:
        url = self.urls.get(job_type) or self.urls.get("campus") or self.urls.get("social") or ""
        if not url:
            print(f"[Lenovo] No URL configured for {self.company_id} (job_type={job_type})", file=sys.stderr)
            return []

        # 校招/实习走 talent.lenovo.com.cn API
        if "talent.lenovo.com.cn" in url:
            return self._crawl_talent_api(keyword, max_jobs, job_type, headless, url)

        # 社招走 SuccessFactors DOM
        return self._crawl_successfactors(keyword, max_jobs, job_type, headless, url)

    # ── talent.lenovo.com.cn API 抓取 ──────────────────────────

    def _crawl_talent_api(
        self, keyword: str, max_jobs: int, job_type: str, headless: bool, url: str
    ) -> List[dict]:
        jobs: List[dict] = []
        seen_ids: set = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            try:
                page_num = 1
                while len(jobs) < max_jobs:
                    api_url = f"{url.split('?')[0].replace('/position','')}/gateway/jobBase/list"
                    # Extract projectType from original URL
                    pt_match = re.search(r"projectType=(\d+)", url)
                    project_type = pt_match.group(1) if pt_match else "1"
                    full_url = f"{api_url}?projectType={project_type}&pageNum={page_num}&pageSize=20&keyword={keyword}"

                    print(f"[Lenovo] API: {full_url}", file=sys.stderr)
                    page.goto(full_url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)

                    body_text = page.inner_text("body") or ""
                    try:
                        data = json_mod.loads(body_text)
                    except json_mod.JSONDecodeError:
                        pre = page.inner_text("pre") or body_text
                        try:
                            data = json_mod.loads(pre)
                        except json_mod.JSONDecodeError:
                            print(f"   Page {page_num}: JSON parse failed", file=sys.stderr)
                            break

                    rows = (data.get("result") or {}).get("rows") or data.get("rows") or []
                    total = (data.get("result") or {}).get("total") or data.get("total") or 0

                    if not rows:
                        print(f"   Page {page_num}: 0 jobs (total={total}) — stopping", file=sys.stderr)
                        break

                    for row in rows:
                        if len(jobs) >= max_jobs:
                            break
                        jid = str(row.get("id") or row.get("jobId") or "")
                        if jid in seen_ids:
                            continue
                        seen_ids.add(jid)

                        title = row.get("jobName") or row.get("positionTitle") or row.get("title") or ""
                        location = row.get("workCity") or row.get("workCities") or row.get("location") or ""
                        category = row.get("deptName") or row.get("bgs") or row.get("category") or ""
                        detail_url = row.get("jobUrl") or row.get("url") or ""

                        if not detail_url:
                            detail_url = f"https://talent.lenovo.com.cn/position/detail?jobId={jid}"

                        job_hash = hashlib.md5((detail_url or title).encode()).hexdigest()[:12]

                        jobs.append({
                            "title": str(title).strip(),
                            "company": self.company_name,
                            "location": str(location).strip(),
                            "category": str(category).strip(),
                            "url": str(detail_url).strip(),
                            "publish_time": str(row.get("publishTime") or row.get("publishDate") or "").strip(),
                            "duty": str(row.get("jobDesc") or row.get("duty") or "").strip(),
                            "requirement": str(row.get("jobRequire") or row.get("requirement") or "").strip(),
                            "hash": job_hash,
                            "source": self.company_id,
                            "job_type": job_type,
                        })

                    print(f"   Page {page_num}: +{len(rows)} jobs ({len(jobs)} total, {total} total)", file=sys.stderr)
                    page_num += 1

                    if len(jobs) >= max_jobs or len(rows) < 20:
                        break

            except Exception as e:
                print(f"[Lenovo] Talent API error: {e}", file=sys.stderr)
            finally:
                browser.close()

        print(f"[Done] {self.company_name}: {len(jobs)} jobs", file=sys.stderr)
        return jobs

    # ── SuccessFactors DOM 抓取 (社招) ──────────────────────────

    def _crawl_successfactors(
        self, keyword: str, max_jobs: int, job_type: str, headless: bool, url: str
    ) -> List[dict]:
        search_base = url.split("?")[0]
        search_url = f"{search_base}?keyword={keyword}"

        print(f"[Lenovo] Crawling {self.company_name}: {search_url}", file=sys.stderr)

        jobs: List[dict] = []
        seen_ids: set = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            page = context.new_page()

            try:
                page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
                _dismiss_cookie_banner(page)
                page.wait_for_timeout(1000)

                page_num = 0
                while len(jobs) < max_jobs:
                    page_num += 1
                    cards = page.query_selector_all(JOB_CARD_SELECTOR)
                    if not cards:
                        print(f"   Page {page_num}: 0 cards found — stopping", file=sys.stderr)
                        break

                    new_in_page = 0
                    for card in cards:
                        if len(jobs) >= max_jobs:
                            break
                        try:
                            title_el = card.query_selector(TITLE_LINK_SELECTOR)
                            if not title_el:
                                continue
                            title = (title_el.inner_text() or "").strip()
                            if not title:
                                continue

                            detail_url = title_el.get_attribute("href") or ""
                            job_id = _extract_id_from_url(detail_url)
                            if job_id in seen_ids:
                                continue
                            seen_ids.add(job_id)

                            cat_el = card.query_selector(CATEGORY_SELECTOR)
                            category = (cat_el.inner_text() or "").strip() if cat_el else ""

                            subtitle_spans = card.query_selector_all(SUBTITLE_SPANS_SELECTOR)
                            location = ""
                            publish_time = ""

                            for i, sp in enumerate(subtitle_spans):
                                text = (sp.inner_text() or "").strip()
                                if i == 0:
                                    location = text
                                elif "已发布" in text:
                                    publish_time = _parse_date(text.replace("已发布", "").strip())

                            job = {
                                "title": title,
                                "company": self.company_name,
                                "location": location,
                                "category": category,
                                "url": detail_url,
                                "publish_time": publish_time,
                                "duty": "",
                                "requirement": "",
                                "hash": hashlib.md5((detail_url or title).encode()).hexdigest()[:12],
                                "source": self.company_id,
                                "job_type": job_type,
                            }
                            jobs.append(job)
                            new_in_page += 1

                        except Exception:
                            continue

                    print(f"   Page {page_num}: +{new_in_page} jobs ({len(jobs)} total)", file=sys.stderr)

                    if new_in_page == 0 or len(jobs) >= max_jobs:
                        break

                    next_link = page.query_selector("a.tpt_paginationNext:not(.disabled)")
                    if not next_link:
                        next_link = page.query_selector("a:has-text('>>')")
                    if not next_link:
                        next_link = page.query_selector("a[rel='next']")
                    if next_link:
                        try:
                            next_link.click()
                            page.wait_for_timeout(3000)
                            _dismiss_cookie_banner(page)
                            page.wait_for_timeout(1000)
                            continue
                        except Exception:
                            pass

                    offset = page_num * 50
                    page_url = f"{search_url}&jobRecordsPerPage=50&jobOffset={offset}"
                    page.goto(page_url, timeout=60000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    _dismiss_cookie_banner(page)
                    page.wait_for_timeout(1000)

            except Exception as e:
                print(f"[Lenovo] Error: {e}", file=sys.stderr)
            finally:
                browser.close()

        print(f"[Done] {self.company_name}: {len(jobs)} jobs", file=sys.stderr)
        return jobs
