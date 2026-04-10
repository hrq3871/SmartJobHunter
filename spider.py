#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 爬虫模块
使用 Playwright 抓取各大公司招聘网站
支持翻页获取更多数据
从 companies.yaml 读取公司配置
"""

import json
import sys
import time
import hashlib
import argparse
import yaml
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

# 加载公司配置
def load_companies_config():
    """从 companies.yaml 加载公司配置"""
    config_path = Path(__file__).parent / "companies.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# 全局配置
COMPANIES_CONFIG = load_companies_config()


def generate_hash(url):
    """生成URL的MD5哈希"""
    return hashlib.md5(url.encode()).hexdigest()


def get_enabled_companies(job_type: str = None) -> list:
    """获取启用的公司列表

    Args:
        job_type: 筛选支持该岗位性质的公司 (social/campus/internship)

    Returns:
        公司配置列表
    """
    companies = []
    for company in COMPANIES_CONFIG.get('companies', []):
        if not company.get('enabled', False):
            continue

        # 如果指定了岗位类型，检查公司是否支持
        if job_type:
            urls = company.get('urls', {})
            if job_type not in urls:
                continue

        companies.append(company)

    return companies


def get_company_by_id(company_id: str) -> dict:
    """根据ID获取公司配置"""
    for company in COMPANIES_CONFIG.get('companies', []):
        if company.get('id') == company_id:
            return company
    return None


def create_browser(p, headless=True):
    """创建浏览器实例"""
    browser = p.chromium.launch(
        headless=headless,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-infobars',
            '--disable-extensions',
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
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
    """)
    return browser, context


def parse_tencent_job(item: dict) -> dict:
    """解析腾讯岗位数据"""
    title = item.get('RecruitPostName', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    return {
        "title": title,
        "company": "腾讯",
        "location": item.get('LocationName', ''),
        "category": item.get('CategoryName', ''),
        "url": f"https://careers.tencent.com/position_detail.html?id={item.get('PostId', '')}",
        "publish_time": item.get('LastUpdateTime', ''),
        "duty": item.get('Responsibility', ''),
        "requirement": "",
        "product": item.get('ProductName', ''),
        "bg": item.get('BGName', ''),
        "work_years": item.get('RequireWorkYearsName', ''),
        "hash": generate_hash(str(item.get('PostId', ''))),
        "source": "tencent",
        "job_type": job_type_label
    }


def crawl_tencent(keyword, headless=True, max_jobs=50, max_pages=5):
    """抓取腾讯招聘 - 支持翻页"""
    jobs = []
    seen_ids = set()

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        # 用于拦截API响应
        intercepted_data = []

        def handle_response(response):
            if "tencentcareer/api/post/Query" in response.url and response.status == 200:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                    print(f"🎯 拦截到API响应", file=sys.stderr)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"🌐 正在访问腾讯招聘...", file=sys.stderr)
            page.goto(f"https://careers.tencent.com/search.html?query={keyword}", timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(3000)

            # 解析拦截到的数据
            for data in intercepted_data:
                if 'Data' in data:
                    posts = data.get('Data', {}).get('Posts', [])
                    for item in posts:
                        post_id = str(item.get('PostId', ''))
                        if post_id and post_id not in seen_ids:
                            seen_ids.add(post_id)
                            job = parse_tencent_job(item)
                            jobs.append(job)

            print(f"   第 1 页获取 {len(jobs)} 个岗位", file=sys.stderr)

            # 翻页获取更多数据
            page_count = 2
            while len(jobs) < max_jobs and page_count <= max_pages:
                # 尝试点击下一页
                clicked = False

                # 先尝试找到可点击的下一页元素
                try:
                    # 腾讯的翻页按钮通常在列表底部
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(1000)

                    next_btns = page.query_selector_all('[class*="next"]')
                    for btn in next_btns:
                        try:
                            if btn.is_visible() and btn.is_enabled():
                                btn.click()
                                page.wait_for_timeout(3000)
                                clicked = True
                                print(f"   点击翻页按钮", file=sys.stderr)
                                break
                        except:
                            continue
                except:
                    pass

                if not clicked:
                    # 尝试其他选择器
                    for selector in ['[class*="arrow-right"]', '[class*="page-next"]', '.next']:
                        try:
                            element = page.query_selector(selector)
                            if element and element.is_visible():
                                element.click()
                                page.wait_for_timeout(3000)
                                clicked = True
                                print(f"   点击翻页: {selector}", file=sys.stderr)
                                break
                        except:
                            continue

                if not clicked:
                    print(f"   无法翻页，停止", file=sys.stderr)
                    break

                # 解析新拦截的数据
                new_count = 0
                for data in intercepted_data:
                    if 'Data' in data:
                        posts = data.get('Data', {}).get('Posts', [])
                        for item in posts:
                            post_id = str(item.get('PostId', ''))
                            if post_id and post_id not in seen_ids:
                                seen_ids.add(post_id)
                                job = parse_tencent_job(item)
                                jobs.append(job)
                                new_count += 1

                print(f"   第 {page_count} 页，新增 {new_count} 个岗位", file=sys.stderr)
                page_count += 1
                intercepted_data.clear()

            print(f"✅ 腾讯招聘共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"❌ 抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


def parse_bytedance_job(item: dict, job_type: str) -> dict:
    """解析字节跳动岗位数据"""
    city_info = item.get('city_info', {})
    city_name = city_info.get('name', '') if city_info else ''

    job_category = item.get('job_category', {})
    category_name = job_category.get('name', '') if job_category else ''

    publish_time = item.get('publish_time', '')
    if isinstance(publish_time, (int, float)) and publish_time > 0:
        try:
            dt = datetime.fromtimestamp(publish_time / 1000)
            publish_time = dt.strftime('%Y年%m月%d日')
        except:
            pass

    job_type_label = "社招" if job_type == "social" else "校招/实习"
    title = item.get('title', '')
    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"

    detail_url_prefix = "https://jobs.bytedance.com/experienced/position/detail" if job_type == "social" else "https://jobs.bytedance.com/campus/position/detail"

    return {
        "title": title,
        "company": "字节跳动",
        "location": city_name,
        "category": category_name,
        "url": f"{detail_url_prefix}/{item.get('id', '')}",
        "publish_time": publish_time,
        "duty": item.get('description', ''),
        "requirement": item.get('requirement', ''),
        "hash": generate_hash(str(item.get('id', ''))),
        "source": "bytedance",
        "job_type": job_type_label
    }


def crawl_bytedance(keyword, headless=True, max_jobs=50, max_pages=5, job_type="campus"):
    """抓取字节跳动招聘 - 支持翻页
    job_type: campus(校招) 或 social(社招)
    """
    jobs = []
    seen_ids = set()

    if job_type == "social":
        base_url = "https://jobs.bytedance.com/experienced/position"
    else:
        base_url = "https://jobs.bytedance.com/campus/position"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        # 用于拦截API响应
        intercepted_data = []

        def handle_response(response):
            if "search/job/posts" in response.url and response.status == 200:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"🌐 正在访问字节跳动招聘 ({'社招' if job_type == 'social' else '校招/实习'})...", file=sys.stderr)
            search_url = f"{base_url}?keyword={keyword}"
            page.goto(search_url, timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(3000)

            # 解析第一页拦截到的数据
            for data in intercepted_data:
                if 'data' in data and 'job_post_list' in data['data']:
                    posts = data['data']['job_post_list']
                    for item in posts:
                        job_id = str(item.get('id', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_bytedance_job(item, job_type)
                            jobs.append(job)

            print(f"   第 1 页获取 {len(jobs)} 个岗位", file=sys.stderr)

            # 翻页获取更多数据
            page_count = 2
            while len(jobs) < max_jobs and page_count <= max_pages:
                # 尝试点击下一页
                clicked = False
                selectors = [
                    '[class*="pagination"] [class*="next"]',
                    '.ant-pagination-next',
                    'button[aria-label="下一页"]',
                ]

                for selector in selectors:
                    try:
                        element = page.query_selector(selector)
                        if element and element.is_visible():
                            element.click()
                            page.wait_for_timeout(3000)
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    print(f"   无法翻页，停止", file=sys.stderr)
                    break

                # 解析新拦截的数据
                new_count = 0
                for data in intercepted_data:
                    if 'data' in data and 'job_post_list' in data['data']:
                        posts = data['data']['job_post_list']
                        for item in posts:
                            job_id = str(item.get('id', ''))
                            if job_id and job_id not in seen_ids:
                                seen_ids.add(job_id)
                                job = parse_bytedance_job(item, job_type)
                                jobs.append(job)
                                new_count += 1

                print(f"   第 {page_count} 页获取，新增 {new_count} 个岗位", file=sys.stderr)
                page_count += 1
                intercepted_data.clear()

            print(f"✅ 字节跳动共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"❌ 抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


def crawl_bytedance_social(keyword, headless=True, max_jobs=50, max_pages=5):
    """抓取字节跳动社招岗位"""
    return crawl_bytedance(keyword, headless, max_jobs, max_pages, job_type="social")


# ==================== 阿里巴巴爬虫 ====================

def parse_alibaba_job(item: dict) -> dict:
    """解析阿里巴巴岗位数据"""
    title = item.get('name', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    # 解析工作地点
    locations = item.get('workLocationList', [])
    location = locations[0] if locations else ''

    return {
        "title": title,
        "company": "阿里巴巴",
        "location": location,
        "category": item.get('categoryName', ''),
        "url": f"https://talent.alibaba.com/position/{item.get('id', '')}",
        "publish_time": item.get('gmtCreate', ''),
        "duty": item.get('description', ''),
        "requirement": item.get('requirement', ''),
        "product": item.get('departmentName', ''),
        "bg": '',
        "work_years": item.get('workYears', ''),
        "hash": generate_hash(str(item.get('id', ''))),
        "source": "alibaba",
        "job_type": job_type_label
    }


def crawl_alibaba(keyword, headless=True, max_jobs=50, max_pages=5, job_type="social"):
    """抓取阿里巴巴招聘 - 支持翻页"""
    jobs = []
    seen_ids = set()

    if job_type == "campus":
        base_url = "https://talent.alibaba.com/campus/position-list"
    else:
        base_url = "https://talent.alibaba.com/off-campus/position-list"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        intercepted_data = []

        def handle_response(response):
            # 阿里巴巴API路径
            if "api/position/list" in response.url or "position/query" in response.url:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                    print(f"   [API] 拦截到响应", file=sys.stderr)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[爬虫] 正在访问阿里巴巴招聘...", file=sys.stderr)
            page.goto(f"{base_url}?keyword={keyword}", timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(5000)

            # 解析拦截到的数据
            for data in intercepted_data:
                if isinstance(data, dict):
                    # 尝试不同的数据结构
                    posts = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', []) or []
                    for item in posts:
                        job_id = str(item.get('id', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_alibaba_job(item)
                            jobs.append(job)

            print(f"   第 1 页获取 {len(jobs)} 个岗位", file=sys.stderr)

            # 翻页
            page_count = 2
            while len(jobs) < max_jobs and page_count <= max_pages:
                clicked = False
                for selector in ['.next', '[class*="next"]', 'button[aria-label="下一页"]']:
                    try:
                        element = page.query_selector(selector)
                        if element and element.is_visible():
                            element.click()
                            page.wait_for_timeout(3000)
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    break

                new_count = 0
                for data in intercepted_data:
                    if isinstance(data, dict):
                        posts = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', []) or []
                        for item in posts:
                            job_id = str(item.get('id', ''))
                            if job_id and job_id not in seen_ids:
                                seen_ids.add(job_id)
                                job = parse_alibaba_job(item)
                                jobs.append(job)
                                new_count += 1

                print(f"   第 {page_count} 页，新增 {new_count} 个岗位", file=sys.stderr)
                page_count += 1
                intercepted_data.clear()

            print(f"[完成] 阿里巴巴共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"[错误] 阿里巴巴抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


# ==================== 百度爬虫 ====================

def parse_baidu_job(item: dict) -> dict:
    """解析百度岗位数据"""
    title = item.get('name', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    return {
        "title": title,
        "company": "百度",
        "location": item.get('workPlace', ''),
        "category": item.get('serviceType', ''),
        "url": f"https://talent.baidu.com/jobs/detail/{item.get('id', '')}",
        "publish_time": item.get('publishTime', ''),
        "duty": item.get('responsibility', ''),
        "requirement": item.get('qualification', ''),
        "product": item.get('department', ''),
        "bg": '',
        "work_years": item.get('workYears', ''),
        "hash": generate_hash(str(item.get('id', ''))),
        "source": "baidu",
        "job_type": job_type_label
    }


def crawl_baidu(keyword, headless=True, max_jobs=50, max_pages=5, job_type="social"):
    """抓取百度招聘"""
    jobs = []
    seen_ids = set()

    if job_type == "campus":
        base_url = "https://talent.baidu.com/campus/jobs/list"
    else:
        base_url = "https://talent.baidu.com/jobs/list"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        intercepted_data = []

        def handle_response(response):
            if "api/job/list" in response.url or "job/query" in response.url:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[爬虫] 正在访问百度招聘...", file=sys.stderr)
            page.goto(f"{base_url}?keyword={keyword}", timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(5000)

            for data in intercepted_data:
                if isinstance(data, dict):
                    posts = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', []) or []
                    for item in posts:
                        job_id = str(item.get('id', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_baidu_job(item)
                            jobs.append(job)

            print(f"[完成] 百度共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"[错误] 百度抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


# ==================== 美团爬虫 ====================

def parse_meituan_job(item: dict) -> dict:
    """解析美团岗位数据"""
    title = item.get('name', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    # 解析城市列表
    city_list = item.get('cityList', [])
    location = ', '.join([c.get('name', '') for c in city_list]) if city_list else ''

    # 解析部门
    dept_list = item.get('department', [])
    department = ', '.join([d.get('name', '') for d in dept_list]) if dept_list else ''

    # 解析发布时间
    refresh_time = item.get('refreshTime', 0)
    publish_time = ''
    if refresh_time:
        from datetime import datetime
        try:
            dt = datetime.fromtimestamp(refresh_time / 1000)
            publish_time = dt.strftime('%Y-%m-%d')
        except:
            pass

    return {
        "title": title,
        "company": "美团",
        "location": location,
        "category": item.get('jobFamily', ''),
        "url": f"https://zhaopin.meituan.com/jobs/{item.get('jobUnionId', '')}",
        "publish_time": publish_time,
        "duty": item.get('jobDuty', ''),
        "requirement": item.get('jobRequirement', ''),
        "product": department,
        "bg": item.get('jobFamilyGroup', ''),
        "work_years": item.get('workYear', ''),
        "hash": generate_hash(str(item.get('jobUnionId', ''))),
        "source": "meituan",
        "job_type": job_type_label
    }


def crawl_meituan(keyword, headless=True, max_jobs=50, max_pages=5, job_type="social"):
    """抓取美团招聘"""
    jobs = []
    seen_ids = set()

    base_url = "https://zhaopin.meituan.com/jobs" if job_type == "social" else "https://zhaopin.meituan.com/campus"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        intercepted_data = []

        def handle_response(response):
            if "getJobList" in response.url:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[爬虫] 正在访问美团招聘...", file=sys.stderr)
            page.goto(base_url, timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(5000)

            for data in intercepted_data:
                if isinstance(data, dict):
                    posts = data.get('data', {}).get('list', [])
                    for item in posts:
                        job_id = str(item.get('jobUnionId', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_meituan_job(item)
                            jobs.append(job)

            print(f"[完成] 美团共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"[错误] 美团抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


# ==================== 京东爬虫 ====================

def parse_jd_job(item: dict) -> dict:
    """解析京东岗位数据"""
    title = item.get('name', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    return {
        "title": title,
        "company": "京东",
        "location": item.get('workPlace', ''),
        "category": item.get('category', ''),
        "url": f"https://zhaopin.jd.com/job/{item.get('id', '')}",
        "publish_time": item.get('publishDate', ''),
        "duty": item.get('jobDesc', ''),
        "requirement": item.get('jobRequire', ''),
        "product": item.get('department', ''),
        "bg": '',
        "work_years": item.get('workYear', ''),
        "hash": generate_hash(str(item.get('id', ''))),
        "source": "jd",
        "job_type": job_type_label
    }


def crawl_jd(keyword, headless=True, max_jobs=50, max_pages=5, job_type="social"):
    """抓取京东招聘"""
    jobs = []
    seen_ids = set()

    base_url = "https://zhaopin.jd.com/social" if job_type == "social" else "https://zhaopin.jd.com/campus"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        intercepted_data = []

        def handle_response(response):
            if "api/job/list" in response.url or "position/list" in response.url:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[爬虫] 正在访问京东招聘...", file=sys.stderr)
            page.goto(f"{base_url}?keyword={keyword}", timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(5000)

            for data in intercepted_data:
                if isinstance(data, dict):
                    posts = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', []) or []
                    for item in posts:
                        job_id = str(item.get('id', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_jd_job(item)
                            jobs.append(job)

            print(f"[完成] 京东共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"[错误] 京东抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


# ==================== 华为爬虫 ====================

def parse_huawei_job(item: dict) -> dict:
    """解析华为岗位数据"""
    title = item.get('name', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    return {
        "title": title,
        "company": "华为",
        "location": item.get('workPlace', ''),
        "category": item.get('category', ''),
        "url": f"https://career.huawei.com/job/{item.get('id', '')}",
        "publish_time": item.get('publishDate', ''),
        "duty": item.get('jobDesc', ''),
        "requirement": item.get('jobRequire', ''),
        "product": item.get('department', ''),
        "bg": '',
        "work_years": item.get('workYear', ''),
        "hash": generate_hash(str(item.get('id', ''))),
        "source": "huawei",
        "job_type": job_type_label
    }


def crawl_huawei(keyword, headless=True, max_jobs=50, max_pages=5, job_type="social"):
    """抓取华为招聘"""
    jobs = []
    seen_ids = set()

    base_url = "https://career.huawei.com/reccampportal/portal5/index.html"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        intercepted_data = []

        def handle_response(response):
            if "portal5/queryJobList" in response.url or "job/list" in response.url:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[爬虫] 正在访问华为招聘...", file=sys.stderr)
            page.goto(base_url, timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(5000)

            # 尝试输入关键词搜索
            try:
                search_input = page.query_selector('input[placeholder*="关键词"]') or page.query_selector('input[type="text"]')
                if search_input:
                    search_input.fill(keyword)
                    page.wait_for_timeout(1000)
                    search_input.press('Enter')
                    page.wait_for_timeout(3000)
            except:
                pass

            for data in intercepted_data:
                if isinstance(data, dict):
                    posts = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', []) or []
                    for item in posts:
                        job_id = str(item.get('id', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_huawei_job(item)
                            jobs.append(job)

            print(f"[完成] 华为共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"[错误] 华为抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


# ==================== 小米爬虫 ====================

def parse_xiaomi_job(item: dict) -> dict:
    """解析小米岗位数据"""
    title = item.get('name', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    return {
        "title": title,
        "company": "小米",
        "location": item.get('workPlace', ''),
        "category": item.get('category', ''),
        "url": f"https://hr.xiaomi.com/job/{item.get('id', '')}",
        "publish_time": item.get('publishDate', ''),
        "duty": item.get('jobDesc', ''),
        "requirement": item.get('jobRequire', ''),
        "product": item.get('department', ''),
        "bg": '',
        "work_years": item.get('workYear', ''),
        "hash": generate_hash(str(item.get('id', ''))),
        "source": "xiaomi",
        "job_type": job_type_label
    }


def crawl_xiaomi(keyword, headless=True, max_jobs=50, max_pages=5, job_type="social"):
    """抓取小米招聘"""
    jobs = []
    seen_ids = set()

    base_url = "https://hr.xiaomi.com/job" if job_type == "social" else "https://hr.xiaomi.com/campus"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        intercepted_data = []

        def handle_response(response):
            if "api/job/list" in response.url or "position/list" in response.url:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[爬虫] 正在访问小米招聘...", file=sys.stderr)
            page.goto(f"{base_url}?keyword={keyword}", timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(5000)

            for data in intercepted_data:
                if isinstance(data, dict):
                    posts = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', []) or []
                    for item in posts:
                        job_id = str(item.get('id', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_xiaomi_job(item)
                            jobs.append(job)

            print(f"[完成] 小米共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"[错误] 小米抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


# ==================== 滴滴爬虫 ====================

def parse_didi_job(item: dict) -> dict:
    """解析滴滴岗位数据"""
    title = item.get('name', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    return {
        "title": title,
        "company": "滴滴出行",
        "location": item.get('workPlace', ''),
        "category": item.get('category', ''),
        "url": f"https://didichuxing.zhiye.com/job/{item.get('id', '')}",
        "publish_time": item.get('publishDate', ''),
        "duty": item.get('jobDesc', ''),
        "requirement": item.get('jobRequire', ''),
        "product": item.get('department', ''),
        "bg": '',
        "work_years": item.get('workYear', ''),
        "hash": generate_hash(str(item.get('id', ''))),
        "source": "didi",
        "job_type": job_type_label
    }


def crawl_didi(keyword, headless=True, max_jobs=50, max_pages=5, job_type="social"):
    """抓取滴滴招聘"""
    jobs = []
    seen_ids = set()

    base_url = "https://didichuxing.zhiye.com/home/social" if job_type == "social" else "https://didichuxing.zhiye.com/home/campus"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        intercepted_data = []

        def handle_response(response):
            if "api/job/list" in response.url or "position/list" in response.url:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[爬虫] 正在访问滴滴招聘...", file=sys.stderr)
            page.goto(base_url, timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(5000)

            for data in intercepted_data:
                if isinstance(data, dict):
                    posts = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', []) or []
                    for item in posts:
                        job_id = str(item.get('id', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_didi_job(item)
                            jobs.append(job)

            print(f"[完成] 滴滴共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"[错误] 滴滴抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


# ==================== 拼多多爬虫 ====================

def parse_pinduoduo_job(item: dict) -> dict:
    """解析拼多多岗位数据"""
    title = item.get('name', '')
    job_type_label = "社招"

    if '实习' in title or 'intern' in title.lower():
        job_type_label = "实习"
    elif '校招' in title or '应届' in title:
        job_type_label = "校招"

    return {
        "title": title,
        "company": "拼多多",
        "location": item.get('workPlace', ''),
        "category": item.get('category', ''),
        "url": f"https://careers.pinduoduo.com/jobs/{item.get('id', '')}",
        "publish_time": item.get('publishDate', ''),
        "duty": item.get('jobDesc', ''),
        "requirement": item.get('jobRequire', ''),
        "product": item.get('department', ''),
        "bg": '',
        "work_years": item.get('workYear', ''),
        "hash": generate_hash(str(item.get('id', ''))),
        "source": "pinduoduo",
        "job_type": job_type_label
    }


def crawl_pinduoduo(keyword, headless=True, max_jobs=50, max_pages=5, job_type="social"):
    """抓取拼多多招聘"""
    jobs = []
    seen_ids = set()

    base_url = "https://careers.pinduoduo.com/jobs" if job_type == "social" else "https://careers.pinduoduo.com/campus"

    with sync_playwright() as p:
        browser, context = create_browser(p, headless)
        page = context.new_page()

        intercepted_data = []

        def handle_response(response):
            if "api/job/list" in response.url or "position/list" in response.url:
                try:
                    data = response.json()
                    intercepted_data.append(data)
                except:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[爬虫] 正在访问拼多多招聘...", file=sys.stderr)
            page.goto(f"{base_url}?keyword={keyword}", timeout=60000, wait_until='networkidle')
            page.wait_for_timeout(5000)

            for data in intercepted_data:
                if isinstance(data, dict):
                    posts = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', []) or []
                    for item in posts:
                        job_id = str(item.get('id', ''))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = parse_pinduoduo_job(item)
                            jobs.append(job)

            print(f"[完成] 拼多多共获取 {len(jobs)} 个岗位", file=sys.stderr)

        except Exception as e:
            print(f"[错误] 拼多多抓取失败: {e}", file=sys.stderr)
        finally:
            context.close()
            browser.close()

    return jobs[:max_jobs]


def crawl_company(company_id: str, keyword: str, headless: bool = True, max_jobs: int = 50, job_type: str = None):
    """根据公司ID抓取岗位

    Args:
        company_id: 公司ID (如 tencent, bytedance)
        keyword: 搜索关键词
        headless: 是否无头模式
        max_jobs: 最大岗位数
        job_type: 岗位类型 (social/campus/internship)
    """
    # 爬虫映射
    crawlers = {
        "tencent": crawl_tencent,
        "bytedance": crawl_bytedance,
        "bytedance_social": crawl_bytedance_social,
        "alibaba": crawl_alibaba,
        "baidu": crawl_baidu,
        "meituan": crawl_meituan,
        "jd": crawl_jd,
        "huawei": crawl_huawei,
        "xiaomi": crawl_xiaomi,
        "didi": crawl_didi,
        "pinduoduo": crawl_pinduoduo,
    }

    crawler = crawlers.get(company_id.lower())
    if crawler:
        return crawler(keyword, headless, max_jobs)
    else:
        # 从配置中查找
        company = get_company_by_id(company_id)
        if company:
            print(f"公司 {company.get('name')} 已配置但爬虫未实现", file=sys.stderr)
        else:
            print(f"未找到公司配置: {company_id}", file=sys.stderr)
        return []


def crawl_all_companies(keyword: str, job_type: str = "social", max_jobs: int = 50) -> list:
    """抓取所有启用的公司

    Args:
        keyword: 搜索关键词
        job_type: 岗位类型 (social/campus/internship)
        max_jobs: 每个公司最大岗位数

    Returns:
        所有岗位列表
    """
    all_jobs = []
    companies = get_enabled_companies(job_type)

    print(f"[爬虫] 找到 {len(companies)} 个启用的公司", file=sys.stderr)

    for company in companies:
        company_id = company.get('id')
        company_name = company.get('name')

        print(f"[爬虫] 正在抓取 {company_name}...", file=sys.stderr)

        try:
            jobs = crawl_company(company_id, keyword, max_jobs=max_jobs, job_type=job_type)
            all_jobs.extend(jobs)
            print(f"[爬虫] {company_name} 获取 {len(jobs)} 个岗位", file=sys.stderr)
        except Exception as e:
            print(f"[爬虫] {company_name} 抓取失败: {e}", file=sys.stderr)

    return all_jobs


def list_companies():
    """列出所有公司配置"""
    print("="*60)
    print("公司列表")
    print("="*60)

    for company in COMPANIES_CONFIG.get('companies', []):
        status = "[启用]" if company.get('enabled') else "[禁用]"
        name = company.get('name', '未知')
        company_id = company.get('id', '')

        # 支持的岗位类型
        urls = company.get('urls', {})
        supported_types = list(urls.keys())

        print(f"{status} {name} ({company_id})")
        print(f"      支持类型: {', '.join(supported_types) if supported_types else '无'}")

        note = company.get('note')
        if note:
            print(f"      备注: {note}")
        print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='SmartJobHunter 爬虫')
    parser.add_argument('company', nargs='?', help='公司ID (tencent, bytedance)')
    parser.add_argument('keyword', nargs='?', help='搜索关键词')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('--no-headless', action='store_true', help='显示浏览器界面')
    parser.add_argument('--max-jobs', type=int, default=50, help='最大抓取数量')
    parser.add_argument('--max-pages', type=int, default=5, help='最大翻页数')
    parser.add_argument('-t', '--job-type', choices=['social', 'campus', 'internship'], help='岗位类型')
    parser.add_argument('--list', action='store_true', help='列出所有公司')
    parser.add_argument('--all', action='store_true', help='抓取所有启用的公司')

    args = parser.parse_args()

    if args.list:
        list_companies()
        return

    if args.all:
        if not args.keyword:
            print("错误: 请指定搜索关键词", file=sys.stderr)
            return
        jobs = crawl_all_companies(args.keyword, args.job_type or "social", args.max_jobs)
    elif args.company:
        if not args.keyword:
            print("错误: 请指定搜索关键词", file=sys.stderr)
            return
        headless = not args.no_headless
        jobs = crawl_company(args.company, args.keyword, headless, args.max_jobs, args.job_type)
    else:
        parser.print_help()
        return

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(jobs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
