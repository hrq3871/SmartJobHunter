#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API探测工具 - 分析招聘网站的API结构
"""

import sys
import time
from playwright.sync_api import sync_playwright

def probe_api(url, headless=False, wait_time=10):
    """访问网站并监听所有API请求"""
    api_calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = context.new_page()

        def handle_response(response):
            url = response.url
            status = response.status
            content_type = response.headers.get('content-type', '')

            # 只记录JSON响应
            if 'json' in content_type or 'api' in url.lower():
                try:
                    data = response.json()
                    api_calls.append({
                        'url': url,
                        'status': status,
                        'data': data
                    })
                    print(f"\n[API] {url[:100]}...")
                    print(f"      Status: {status}")
                    if isinstance(data, dict):
                        print(f"      Keys: {list(data.keys())[:5]}")
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"\n[访问] {url}")
            page.goto(url, timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(wait_time * 1000)

            # 滚动页面触发更多请求
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(3000)

        except Exception as e:
            print(f"[错误] {e}")
        finally:
            browser.close()

    return api_calls


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python api_probe.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    api_calls = probe_api(url, headless=False)

    print(f"\n\n共捕获 {len(api_calls)} 个API调用")
    for i, call in enumerate(api_calls, 1):
        print(f"\n--- API #{i} ---")
        print(f"URL: {call['url'][:150]}")
        if call['data']:
            import json
            print(f"Response: {json.dumps(call['data'], ensure_ascii=False, indent=2)[:500]}...")
