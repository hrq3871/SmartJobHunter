# 配置驱动爬虫重构实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有的硬编码爬虫重构为配置驱动架构，添加新公司只需修改 YAML 配置，无需写代码。

**Architecture:** 采用"通用爬虫 + 配置解析"模式。每个公司的爬取逻辑由 YAML 配置声明（API匹配规则、字段映射、数据路径），一个通用爬虫类根据配置动态解析数据。

**Tech Stack:** Python 3.13, Playwright, PyYAML, dataclasses

---

## 背景分析

### 当前问题
1. `crawler.py` 有 1100+ 行，每个公司都有独立的 `parse_xxx_job` + `crawl_xxx` 函数
2. 代码高度重复，维护成本高
3. 添加新公司需要写 100+ 行代码

### 已验证可用的公司
| 公司 | 数据来源 | API Pattern | 状态 |
|------|----------|-------------|------|
| 腾讯 | API拦截 | `tencentcareer/api/post/Query` | ✅ |
| 字节跳动 | API拦截 | `search/job/posts` | ✅ |
| 美团 | API拦截 | `getJobList` | ✅ (待验证) |

### 需要新方案的公司
| 公司 | 数据来源 | 难度 |
|------|----------|------|
| 阿里巴巴 | SSR嵌入HTML | 中等 |

---

## 任务分解

### Task 1: 设计配置 Schema

**Files:**
- Create: `config/crawler_schema.py`

**Step 1: 创建配置数据类**

```python
"""爬虫配置 Schema 定义"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FieldMapping:
    """字段映射配置"""
    source: str  # 源字段路径，支持点号访问如 "data.list"
    default: Optional[str] = None
    transform: Optional[str] = None  # 转換函數名

@dataclass
class APIConfig:
    """API 配置"""
    pattern: str  # URL 匹配模式
    data_path: str  # 数据提取路径，如 "Data.Posts"
    method: str = "intercept"  # intercept | request | ssr

@dataclass
class CompanyCrawlerConfig:
    """公司爬虫配置"""
    id: str
    name: str
    api: APIConfig
    field_mappings: dict[str, FieldMapping]
    url_template: str  # 岗位详情页模板
    job_type_detection: dict[str, list[str]] = field(default_factory=dict)
    enabled: bool = True
```

**Step 2: 验证配置类可用**

Run: `python -c "from config.crawler_schema import CompanyCrawlerConfig; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add config/crawler_schema.py
git commit -m "feat: add crawler config schema"
```

---

### Task 2: 实现通用爬虫基类

**Files:**
- Create: `src/base_crawler.py`

**Step 1: 创建基础爬虫类**

```python
"""通用爬虫基类"""
import sys
import hashlib
from typing import Optional
from playwright.sync_api import sync_playwright, Page, Response

class BaseCrawler:
    """通用爬虫基类"""

    def __init__(self, config: dict):
        self.config = config
        self.jobs = []
        self.seen_ids = set()

    def generate_hash(self, job_id: str) -> str:
        """生成岗位唯一哈希"""
        return hashlib.md5(job_id.encode()).hexdigest()

    def create_browser(self, p, headless: bool = True):
        """创建浏览器实例"""
        browser = p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        return browser, context

    def extract_data(self, response_data: dict, data_path: str) -> list:
        """从响应数据中提取岗位列表"""
        keys = data_path.split('.')
        data = response_data
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key, [])
            elif isinstance(data, list) and key.isdigit():
                data = data[int(key)]
            else:
                return []
        return data if isinstance(data, list) else []

    def parse_field(self, item: dict, mapping: dict) -> str:
        """解析单个字段"""
        source = mapping.get('source', '')
        default = mapping.get('default', '')

        # 支持点号访问嵌套字段
        keys = source.split('.')
        value = item
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                value = value[int(key)]
            else:
                value = None
                break

        if value is None:
            return default
        if isinstance(value, list):
            return value[0] if value else default
        return str(value) if value else default

    def detect_job_type(self, title: str) -> str:
        """检测岗位类型"""
        detection = self.config.get('job_type_detection', {})
        title_lower = title.lower()

        for job_type, keywords in detection.items():
            for kw in keywords:
                if kw.lower() in title_lower:
                    return job_type
        return 'social'

    def parse_job(self, item: dict) -> Optional[dict]:
        """解析单个岗位 - 子类实现"""
        raise NotImplementedError

    def crawl(self, keyword: str, max_jobs: int = 50) -> list:
        """执行爬取 - 子类实现"""
        raise NotImplementedError
```

**Step 2: 验证基类可用**

Run: `python -c "from src.base_crawler import BaseCrawler; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add src/base_crawler.py
git commit -m "feat: add base crawler class"
```

---

### Task 3: 实现配置驱动爬虫

**Files:**
- Create: `src/config_crawler.py`

**Step 1: 创建配置驱动爬虫**

```python
"""配置驱动爬虫"""
import sys
from typing import Optional
from playwright.sync_api import sync_playwright
from .base_crawler import BaseCrawler

class ConfigCrawler(BaseCrawler):
    """配置驱动爬虫 - 根据 YAML 配置动态解析"""

    def __init__(self, company_config: dict):
        super().__init__(company_config)
        self.company_id = company_config.get('id')
        self.company_name = company_config.get('name')
        self.api_config = company_config.get('api', {})
        self.field_mappings = company_config.get('field_mappings', {})
        self.url_template = company_config.get('url_template', '')

    def parse_job(self, item: dict) -> Optional[dict]:
        """根据字段映射解析岗位"""
        if not item:
            return None

        # 获取岗位ID
        id_field = self.field_mappings.get('id', {})
        job_id = self.parse_field(item, id_field)
        if not job_id:
            return None

        # 解析标题
        title_field = self.field_mappings.get('title', {})
        title = self.parse_field(item, title_field)

        # 解析其他字段
        job = {
            'title': title,
            'company': self.company_name,
            'location': self.parse_field(item, self.field_mappings.get('location', {})),
            'category': self.parse_field(item, self.field_mappings.get('category', {})),
            'url': self.url_template.format(id=job_id),
            'publish_time': self.parse_field(item, self.field_mappings.get('publish_time', {})),
            'duty': self.parse_field(item, self.field_mappings.get('duty', {})),
            'requirement': self.parse_field(item, self.field_mappings.get('requirement', {})),
            'hash': self.generate_hash(job_id),
            'source': self.company_id,
            'job_type': self.detect_job_type(title),
        }

        return job

    def crawl(self, keyword: str, max_jobs: int = 50, headless: bool = True) -> list:
        """执行爬取"""
        jobs = []
        seen_ids = set()

        # 获取URL
        urls = self.config.get('urls', {})
        url = urls.get('social', urls.get('campus', ''))
        if not url:
            print(f"[Error] No URL for {self.company_name}", file=sys.stderr)
            return []

        url = url.format(keyword=keyword)

        with sync_playwright() as p:
            browser, context = self.create_browser(p, headless)
            page = context.new_page()

            intercepted_data = []

            def handle_response(response):
                pattern = self.api_config.get('pattern', '')
                if pattern in response.url and response.status == 200:
                    try:
                        data = response.json()
                        intercepted_data.append(data)
                        print(f"  [API] Captured: {response.url[:60]}...", file=sys.stderr)
                    except:
                        pass

            page.on('response', handle_response)

            try:
                print(f"[Crawler] Accessing {self.company_name}...", file=sys.stderr)
                page.goto(url, timeout=60000, wait_until='networkidle')
                page.wait_for_timeout(5000)

                # 解析拦截的数据
                data_path = self.api_config.get('data_path', '')
                for data in intercepted_data:
                    items = self.extract_data(data, data_path)
                    for item in items:
                        job_id = self.parse_field(item, self.field_mappings.get('id', {}))
                        if job_id and job_id not in seen_ids:
                            seen_ids.add(job_id)
                            job = self.parse_job(item)
                            if job:
                                jobs.append(job)

                print(f"[Done] {self.company_name}: {len(jobs)} jobs", file=sys.stderr)

            except Exception as e:
                print(f"[Error] {self.company_name} crawl failed: {e}", file=sys.stderr)
            finally:
                context.close()
                browser.close()

        return jobs[:max_jobs]
```

**Step 2: 验证模块可用**

Run: `python -c "from src.config_crawler import ConfigCrawler; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add src/config_crawler.py
git commit -m "feat: add config-driven crawler"
```

---

### Task 4: 更新公司配置添加字段映射

**Files:**
- Modify: `config/companies.yaml`

**Step 1: 为腾讯添加字段映射**

在腾讯配置中添加:

```yaml
  # 腾讯
  - id: tencent
    name: 腾讯
    enabled: true
    urls:
      social: "https://careers.tencent.com/search.html?query={keyword}"
      campus: "https://careers.tencent.com/search.html?query={keyword}"
    api:
      pattern: "tencentcareer/api/post/Query"
      data_path: "Data.Posts"
      type: "intercept"
    field_mappings:
      id:
        source: "PostId"
      title:
        source: "RecruitPostName"
      location:
        source: "LocationName"
      category:
        source: "CategoryName"
      publish_time:
        source: "LastUpdateTime"
      duty:
        source: "Responsibility"
      product:
        source: "ProductName"
      bg:
        source: "BGName"
      work_years:
        source: "RequireWorkYearsName"
    url_template: "https://careers.tencent.com/position_detail.html?id={id}"
    job_type_detection:
      internship: ["实习", "intern"]
      campus: ["校招", "应届"]
      social: []
```

**Step 2: 为字节跳动添加字段映射**

```yaml
  # 字节跳动 - 校招/实习
  - id: bytedance
    name: 字节跳动
    enabled: true
    urls:
      campus: "https://jobs.bytedance.com/campus/position?keyword={keyword}"
    api:
      pattern: "search/job/posts"
      data_path: "data.job_post_list"
      type: "intercept"
    field_mappings:
      id:
        source: "id"
      title:
        source: "title"
      location:
        source: "city_info.name"
      category:
        source: "job_category.name"
      publish_time:
        source: "publish_time"
      duty:
        source: "description"
      requirement:
        source: "requirement"
    url_template: "https://jobs.bytedance.com/campus/position/detail/{id}"
    job_type_detection:
      internship: ["实习", "intern"]
      campus: ["校招", "应届", "ByteIntern"]
      social: []
```

**Step 3: Commit**

```bash
git add config/companies.yaml
git commit -m "feat: add field mappings for tencent and bytedance"
```

---

### Task 5: 创建爬虫工厂

**Files:**
- Create: `src/crawler_factory.py`

**Step 1: 创建爬虫工厂**

```python
"""爬虫工厂 - 根据公司ID创建爬虫实例"""
import yaml
from pathlib import Path
from typing import Optional
from .config_crawler import ConfigCrawler

# 加载公司配置
def load_companies_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "companies.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

COMPANIES_CONFIG = load_companies_config()

def get_company_config(company_id: str) -> Optional[dict]:
    """获取公司配置"""
    for company in COMPANIES_CONFIG.get('companies', []):
        if company.get('id') == company_id:
            return company
    return None

def create_crawler(company_id: str) -> Optional[ConfigCrawler]:
    """创建爬虫实例"""
    config = get_company_config(company_id)
    if not config:
        print(f"[Error] Company not found: {company_id}")
        return None

    if not config.get('enabled', False):
        print(f"[Warn] Company disabled: {config.get('name')}")
        return None

    # 检查是否有字段映射配置
    if 'field_mappings' in config:
        return ConfigCrawler(config)

    # 回退到旧爬虫（兼容）
    print(f"[Warn] No field_mappings for {company_id}, using legacy crawler")
    return None

def get_enabled_companies(job_type: str = None) -> list:
    """获取启用的公司列表"""
    companies = []
    for company in COMPANIES_CONFIG.get('companies', []):
        if not company.get('enabled', False):
            continue
        if job_type:
            urls = company.get('urls', {})
            if job_type not in urls:
                continue
        companies.append(company)
    return companies

def crawl_all(keyword: str, job_type: str = 'social', max_jobs: int = 50) -> list:
    """爬取所有启用的公司"""
    all_jobs = []
    companies = get_enabled_companies(job_type)

    print(f"[Crawler] Found {len(companies)} enabled companies")

    for company in companies:
        company_id = company.get('id')
        crawler = create_crawler(company_id)

        if crawler:
            try:
                jobs = crawler.crawl(keyword, max_jobs)
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"[Error] {company.get('name')} failed: {e}")

    return all_jobs
```

**Step 2: 验证工厂可用**

Run: `python -c "from src.crawler_factory import create_crawler; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add src/crawler_factory.py
git commit -m "feat: add crawler factory"
```

---

### Task 6: 测试新爬虫

**Files:**
- Create: `tests/test_config_crawler.py`

**Step 1: 创建测试文件**

```python
"""测试配置驱动爬虫"""
import pytest
from src.crawler_factory import create_crawler, get_company_config

def test_get_tencent_config():
    """测试获取腾讯配置"""
    config = get_company_config('tencent')
    assert config is not None
    assert config['name'] == '腾讯'
    assert 'field_mappings' in config

def test_create_tencent_crawler():
    """测试创建腾讯爬虫"""
    crawler = create_crawler('tencent')
    assert crawler is not None
    assert crawler.company_name == '腾讯'

def test_create_bytedance_crawler():
    """测试创建字节爬虫"""
    crawler = create_crawler('bytedance')
    assert crawler is not None
    assert crawler.company_name == '字节跳动'

def test_crawl_tencent():
    """测试爬取腾讯（集成测试）"""
    crawler = create_crawler('tencent')
    jobs = crawler.crawl('产品经理', max_jobs=5)
    assert len(jobs) > 0
    assert jobs[0]['company'] == '腾讯'
    assert jobs[0]['title'] != ''
```

**Step 2: 运行测试**

Run: `pytest tests/test_config_crawler.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_config_crawler.py
git commit -m "test: add config crawler tests"
```

---

### Task 7: 更新 CLI 支持新爬虫

**Files:**
- Modify: `src/cli.py`

**Step 1: 添加新爬虫命令**

在 CLI 中添加使用新爬虫的选项:

```python
# 在现有代码中添加
from .crawler_factory import crawl_all, create_crawler

# 添加命令: python -m src.cli crawl --company tencent --keyword "产品经理"
```

**Step 2: 测试 CLI**

Run: `python -m src.cli crawl --company tencent --keyword "产品经理" --max-jobs 5`
Expected: 输出岗位列表

**Step 3: Commit**

```bash
git add src/cli.py
git commit -m "feat: add new crawler to CLI"
```

---

### Task 8: 测试更多公司

**目标:** 验证美团、百度等公司的 API

**Step 1: 测试美团**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    captured = []
    def capture(response):
        if 'getJobList' in response.url:
            try:
                captured.append(response.json())
            except:
                pass

    page.on('response', capture)
    page.goto('https://zhaopin.meituan.com/jobs', timeout=60000)
    page.wait_for_timeout(5000)

    browser.close()

    if captured:
        print(f"Meituan API works! Data: {captured[0]}")
```

**Step 2: 根据测试结果更新配置**

---

### Task 9: 文档更新

**Files:**
- Modify: `README.md`

**Step 1: 更新 README 说明新架构**

添加:
- 如何添加新公司（只需修改 YAML）
- 配置字段说明
- 示例配置

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for new crawler architecture"
```

---

## 验收标准

1. ✅ 腾讯爬虫正常工作
2. ✅ 字节跳动爬虫正常工作
3. ✅ 美团爬虫正常工作
4. ✅ 添加新公司只需修改 YAML
5. ✅ 旧爬虫代码保留作为兼容

---

## 风险与回退

- **风险**: 新爬虫可能无法处理某些公司的特殊数据结构
- **回退**: 保留旧 `crawler.py`，通过配置开关选择使用哪个爬虫
