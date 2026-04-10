#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
百度招聘 API 分析脚本
使用 Playwright 访问网站并监听网络请求
"""

import json
import sys
from playwright.sync_api import sync_playwright


def analyze_baidu_api():
    """分析百度招聘API结构"""

    # 存储拦截到的API请求和响应
    api_calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 显示浏览器方便观察
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        """)

        page = context.new_page()

        def handle_request(request):
            """拦截请求"""
            url = request.url
            # 过滤可能的API请求
            if any(keyword in url.lower() for keyword in ['api', 'job', 'search', 'list', 'query', 'post', 'position']):
                api_info = {
                    'type': 'request',
                    'url': url,
                    'method': request.method,
                    'headers': dict(request.headers),
                    'post_data': request.post_data,
                }
                api_calls.append(api_info)
                print(f"\n[REQUEST] {request.method} {url}", file=sys.stderr)
                if request.post_data:
                    print(f"  Post Data: {request.post_data[:500]}", file=sys.stderr)

        def handle_response(response):
            """拦截响应"""
            url = response.url
            # 过滤可能的API响应
            if any(keyword in url.lower() for keyword in ['api', 'job', 'search', 'list', 'query', 'post', 'position']):
                if response.status == 200:
                    try:
                        content_type = response.headers.get('content-type', '')
                        if 'json' in content_type or 'javascript' in content_type:
                            data = response.json()
                            api_info = {
                                'type': 'response',
                                'url': url,
                                'status': response.status,
                                'headers': dict(response.headers),
                                'body': data,
                            }
                            api_calls.append(api_info)
                            print(f"\n[RESPONSE] {url}", file=sys.stderr)
                            print(f"  Status: {response.status}", file=sys.stderr)
                            print(f"  Data Preview: {json.dumps(data, ensure_ascii=False)[:1000]}...", file=sys.stderr)
                    except Exception as e:
                        # 尝试获取文本内容
                        try:
                            text = response.text()
                            if len(text) < 2000:
                                api_info = {
                                    'type': 'response_text',
                                    'url': url,
                                    'status': response.status,
                                    'body': text,
                                }
                                api_calls.append(api_info)
                                print(f"\n[RESPONSE TEXT] {url}", file=sys.stderr)
                                print(f"  Content: {text[:500]}", file=sys.stderr)
                        except:
                            pass

        page.on('request', handle_request)
        page.on('response', handle_response)

        try:
            print("=" * 60, file=sys.stderr)
            print("百度招聘 API 分析", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

            target_url = "https://talent.baidu.com/jobs/list"
            print(f"\n正在访问: {target_url}", file=sys.stderr)

            page.goto(target_url, timeout=60000, wait_until='networkidle')

            # 等待页面完全加载
            page.wait_for_timeout(5000)

            # 尝试在搜索框输入关键词触发搜索
            print("\n尝试触发搜索请求...", file=sys.stderr)

            # 查找搜索框
            search_selectors = [
                'input[placeholder*="搜索"]',
                'input[placeholder*="职位"]',
                'input[type="text"]',
                '.search-input',
                '#search-input',
            ]

            for selector in search_selectors:
                try:
                    search_input = page.query_selector(selector)
                    if search_input and search_input.is_visible():
                        print(f"找到搜索框: {selector}", file=sys.stderr)
                        search_input.fill("Python")
                        page.wait_for_timeout(1000)

                        # 尝试点击搜索按钮或按回车
                        search_btn_selectors = [
                            'button[type="submit"]',
                            '.search-btn',
                            '.search-button',
                        ]

                        clicked = False
                        for btn_selector in search_btn_selectors:
                            try:
                                btn = page.query_selector(btn_selector)
                                if btn and btn.is_visible():
                                    btn.click()
                                    clicked = True
                                    break
                            except:
                                pass

                        if not clicked:
                            search_input.press('Enter')

                        page.wait_for_timeout(3000)
                        break
                except:
                    continue

            # 尝试点击筛选条件触发更多请求
            print("\n尝试点击筛选条件...", file=sys.stderr)

            # 滚动页面
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(2000)

            # 截图保存
            page.screenshot(path='baidu_jobs_screenshot.png')
            print("截图已保存: baidu_jobs_screenshot.png", file=sys.stderr)

            # 获取页面内容
            page_content = page.content()
            with open('baidu_jobs_page.html', 'w', encoding='utf-8') as f:
                f.write(page_content)
            print("页面HTML已保存: baidu_jobs_page.html", file=sys.stderr)

        except Exception as e:
            print(f"访问失败: {e}", file=sys.stderr)

        finally:
            # 等待用户观察
            print("\n浏览器将在5秒后关闭...", file=sys.stderr)
            page.wait_for_timeout(5000)
            context.close()
            browser.close()

    # 保存API分析结果
    with open('baidu_api_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(api_calls, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60, file=sys.stderr)
    print("API 分析结果", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # 分析并输出结果
    for call in api_calls:
        if call['type'] == 'request':
            print(f"\n[请求] {call['method']} {call['url']}")
            if call.get('post_data'):
                print(f"  请求体: {call['post_data']}")
        elif call['type'] == 'response':
            print(f"\n[响应] {call['url']}")
            print(f"  状态: {call['status']}")
            if call.get('body'):
                body_str = json.dumps(call['body'], ensure_ascii=False, indent=2)
                print(f"  响应体:\n{body_str[:2000]}")

    print(f"\n完整分析结果已保存到: baidu_api_analysis.json", file=sys.stderr)

    return api_calls


if __name__ == "__main__":
    analyze_baidu_api()
