#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Lightweight career-site inspection used before daily crawling."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List


LOGIN_PATTERNS = [
    "请登录",
    "登录后",
    "请先登录",
    "登录后查看",
    "login",
    "sign in",
    "signin",
    "unauthorized",
]

CAPTCHA_PATTERNS = [
    "captcha",
    "验证码",
    "人机验证",
    "安全验证",
]

BLOCKED_PATTERNS = [
    "access denied",
    "forbidden",
    "blocked",
    "风控",
    "访问受限",
]

NO_JOB_PATTERNS = [
    "暂无岗位",
    "暂无职位",
    "no jobs",
    "no positions",
    "no openings",
]

JOB_LIKE_PATTERNS = [
    "职位",
    "岗位",
    "招聘",
    "careers",
    "jobs",
    "positions",
    "recruit",
]


def inspect_html_signals(html: str, text: str = "") -> Dict[str, Any]:
    """Detect login, captcha, blocked, empty, and job-like page signals."""
    html_content = (html or "").lower()
    visible_text = (text or _html_to_visible_text(html or "")).lower()
    content = f"{html_content}\n{visible_text}"
    signals: List[str] = []

    if _contains_any(visible_text, LOGIN_PATTERNS):
        signals.append("login_required")
    if _contains_any(content, CAPTCHA_PATTERNS):
        signals.append("captcha")
    if _contains_any(content, BLOCKED_PATTERNS):
        signals.append("blocked")
    if _contains_any(content, NO_JOB_PATTERNS):
        signals.append("no_jobs")
    if _contains_any(content, JOB_LIKE_PATTERNS):
        signals.append("job_like")

    return {"signals": sorted(set(signals))}


def build_page_fingerprint(title: str, body_text: str, network_patterns: List[str] | None = None) -> str:
    """Build a stable fingerprint for change detection."""
    normalized_text = re.sub(r"\s+", " ", body_text or "").strip()[:4000]
    network = "|".join(sorted(network_patterns or []))
    raw = f"{title or ''}\n{normalized_text}\n{network}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def inspect_link(url: str, headless: bool = True, timeout_ms: int = 30000) -> Dict[str, Any]:
    """Open a link and collect lightweight inspection metadata."""
    from playwright.sync_api import sync_playwright

    inspected_at = datetime.now().isoformat()
    network_patterns: List[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()

            def handle_request(request):
                if request.resource_type in {"xhr", "fetch"}:
                    network_patterns.append(_network_pattern(request.url))

            page.on("request", handle_request)
            response = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            title = page.title()
            body_text = page.locator("body").inner_text(timeout=5000) if page.locator("body").count() else ""
            html = page.content()
            final_url = page.url
            browser.close()

        signal_result = inspect_html_signals(html, body_text)
        return {
            "ok": True,
            "url": url,
            "final_url": final_url,
            "status": response.status if response else None,
            "title": title,
            "text_sample": body_text[:1000],
            "signals": signal_result["signals"],
            "fingerprint": build_page_fingerprint(title, body_text, network_patterns),
            "network_patterns": sorted(set(network_patterns))[:30],
            "inspected_at": inspected_at,
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "final_url": "",
            "status": None,
            "title": "",
            "text_sample": "",
            "signals": ["network_error"],
            "fingerprint": "",
            "network_patterns": [],
            "error": str(exc),
            "inspected_at": inspected_at,
        }


def _contains_any(content: str, patterns: List[str]) -> bool:
    return any(pattern.lower() in content for pattern in patterns)


def _html_to_visible_text(html: str) -> str:
    without_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"<[^>]+>", " ", without_scripts)


def _network_pattern(url: str) -> str:
    return url.split("?")[0].lower()
