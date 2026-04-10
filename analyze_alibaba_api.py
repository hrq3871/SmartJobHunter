"""
阿里巴巴招聘网站 API 分析脚本
使用 Playwright 监听网络请求，分析 API 结构
"""

import asyncio
import json
from playwright.async_api import async_playwright

# 存储捕获的 API 请求
api_requests = []

async def handle_request(request):
    """处理请求事件"""
    url = request.url
    # 过滤可能包含岗位数据的 API 请求
    if any(keyword in url.lower() for keyword in ['position', 'job', 'list', 'api', 'talent', 'query', 'search']):
        print(f"\n[REQUEST] {request.method} {url}")
        headers = request.headers
        if request.post_data:
            print(f"  Post Data: {request.post_data[:500]}")
        api_requests.append({
            'type': 'request',
            'method': request.method,
            'url': url,
            'headers': dict(headers),
            'post_data': request.post_data
        })

async def handle_response(response):
    """处理响应事件"""
    url = response.url
    # 过滤可能包含岗位数据的 API 响应
    if any(keyword in url.lower() for keyword in ['position', 'job', 'list', 'api', 'talent', 'query', 'search']):
        try:
            content_type = response.headers.get('content-type', '')
            if 'json' in content_type or 'javascript' in content_type:
                body = await response.text()
                print(f"\n[RESPONSE] {response.status} {url}")
                print(f"  Content-Type: {content_type}")
                print(f"  Body (first 1000 chars): {body[:1000]}")
                api_requests.append({
                    'type': 'response',
                    'status': response.status,
                    'url': url,
                    'content_type': content_type,
                    'body': body[:5000]  # 截取前5000字符
                })
        except Exception as e:
            print(f"  Error reading response: {e}")

async def main():
    print("=" * 60)
    print("阿里巴巴招聘网站 API 分析")
    print("目标: https://talent.alibaba.com/off-campus/position-list")
    print("=" * 60)

    async with async_playwright() as p:
        # 使用非 headless 模式便于调试
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # 监听网络请求
        page.on('request', handle_request)
        page.on('response', handle_response)

        print("\n正在访问页面...")
        try:
            await page.goto('https://talent.alibaba.com/off-campus/position-list',
                          wait_until='networkidle',
                          timeout=60000)
        except Exception as e:
            print(f"页面加载超时或出错: {e}")

        # 等待一段时间让页面完全加载
        print("\n等待页面加载完成...")
        await asyncio.sleep(5)

        # 尝试滚动页面触发更多请求
        print("\n滚动页面以触发更多请求...")
        for i in range(3):
            await page.mouse.wheel(0, 500)
            await asyncio.sleep(1)

        # 尝试点击筛选按钮
        print("\n尝试查找并点击筛选按钮...")
        try:
            # 等待页面元素
            await page.wait_for_selector('text=技术', timeout=5000)
            print("找到技术类别按钮")
        except:
            print("未找到技术类别按钮")

        # 再等待一下
        await asyncio.sleep(3)

        print("\n" + "=" * 60)
        print("API 分析结果汇总")
        print("=" * 60)

        # 保存结果到文件
        with open('alibaba_api_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(api_requests, f, ensure_ascii=False, indent=2)
        print(f"\n已捕获 {len(api_requests)} 个相关请求，保存到 alibaba_api_analysis.json")

        # 分析关键 API
        print("\n关键 API 端点:")
        for req in api_requests:
            if req['type'] == 'request':
                print(f"  - {req['method']} {req['url']}")

        print("\n浏览器将保持打开，按 Enter 关闭...")
        input()

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
