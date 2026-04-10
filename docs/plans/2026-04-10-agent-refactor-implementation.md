# SmartJobHunter Agent 重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 SmartJobHunter 从规则引擎重构为 LLM 驱动的 Agent 架构

**Architecture:** Skills 层负责智能决策（语义过滤、AI评估、报告生成），Python 工具层负责确定性工作（爬虫、时间过滤、去重）。使用状态机控制流程，Markdown 格式存储配置和 Memory。

**Tech Stack:** Python 3.8+, Playwright, Anthropic SDK, Markdown, YAML

---

## Phase 0: 备份原有代码

### Task 0.1: 创建备份分支

**Files:**
- 无文件修改

**Step 1: 创建备份分支**

```bash
git checkout -b backup/legacy-python
git push origin backup/legacy-python
git checkout main
```

**Step 2: 验证分支创建成功**

```bash
git branch -a | grep backup/legacy-python
```

Expected: 显示 `backup/legacy-python` 分支

---

## Phase 1: 创建新目录结构

### Task 1.1: 创建核心目录

**Files:**
- Create: `src/`
- Create: `.claude/skills/jobhunter/`
- Create: `.claude/skills/jobhunter/tools/`
- Create: `.claude/skills/jobhunter/prompts/`
- Create: `memory/`
- Create: `config/`
- Create: `profiles/`

**Step 1: 创建目录**

```bash
mkdir -p src
mkdir -p .claude/skills/jobhunter/tools
mkdir -p .claude/skills/jobhunter/prompts
mkdir -p memory
mkdir -p config
mkdir -p profiles
```

**Step 2: 验证目录创建**

```bash
ls -la src/ .claude/skills/jobhunter/ memory/ config/ profiles/
```

**Step 3: 提交**

```bash
git add .
git commit -m "chore: 创建新目录结构"
```

---

## Phase 2: 迁移 Python 代码

### Task 2.1: 创建 src/__init__.py

**Files:**
- Create: `src/__init__.py`

**Step 1: 创建文件**

```python
# src/__init__.py
"""
SmartJobHunter Python 工具层
提供爬虫、过滤、数据清洗等确定性功能
"""

__version__ = "2.0.0"
```

**Step 2: 提交**

```bash
git add src/__init__.py
git commit -m "feat: 创建 src 模块"
```

---

### Task 2.2: 迁移爬虫模块

**Files:**
- Create: `src/crawler.py`
- Modify: 从 `spider.py` 提取核心逻辑

**Step 1: 创建 src/crawler.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
爬虫模块
使用 Playwright 抓取各大公司招聘网站
"""

import json
import sys
import time
import hashlib
import yaml
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

# 加载公司配置
def load_companies_config():
    """从 config/companies.yaml 加载公司配置"""
    config_path = Path(__file__).parent.parent / "config" / "companies.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

COMPANIES_CONFIG = load_companies_config()


def generate_hash(url):
    """生成URL的MD5哈希"""
    return hashlib.md5(url.encode()).hexdigest()


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


# 爬虫函数（从 spider.py 迁移）
def crawl_tencent(keyword, headless=True, max_jobs=50):
    """抓取腾讯招聘"""
    # ... 从 spider.py 复制实现
    pass


def crawl_bytedance(keyword, headless=True, max_jobs=50, job_type="campus"):
    """抓取字节跳动招聘"""
    # ... 从 spider.py 复制实现
    pass


def crawl_meituan(keyword, headless=True, max_jobs=50):
    """抓取美团招聘"""
    # ... 从 spider.py 复制实现
    pass


def crawl_company(company_id: str, keyword: str, headless=True, max_jobs=50, job_type=None):
    """根据公司ID抓取岗位"""
    crawlers = {
        "tencent": crawl_tencent,
        "bytedance": crawl_bytedance,
        "bytedance_social": lambda k, h, m: crawl_bytedance(k, h, m, "social"),
        "meituan": crawl_meituan,
    }
    
    crawler = crawlers.get(company_id.lower())
    if crawler:
        return crawler(keyword, headless, max_jobs)
    return []
```

**Step 2: 从 spider.py 复制完整爬虫实现**

将 spider.py 中的爬虫函数完整复制到 src/crawler.py

**Step 3: 提交**

```bash
git add src/crawler.py
git commit -m "feat: 迁移爬虫模块到 src/crawler.py"
```

---

### Task 2.3: 创建过滤模块

**Files:**
- Create: `src/filters.py`

**Step 1: 创建 src/filters.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
过滤模块
提供时间过滤、去重、数据清洗等确定性功能
"""

import re
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


def filter_by_time(jobs: List[dict], days: int = 3) -> List[dict]:
    """时间过滤：只保留最近N天的岗位"""
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered = []
    
    for job in jobs:
        publish_time = job.get('publish_time', '')
        job_date = _parse_publish_time(publish_time)
        
        if job_date and job_date >= cutoff_date:
            job['_parsed_date'] = job_date
            filtered.append(job)
        elif not job_date:
            filtered.append(job)
    
    return filtered


def _parse_publish_time(time_str) -> Optional[datetime]:
    """解析发布时间"""
    if not time_str:
        return None
    
    time_str = str(time_str).strip()
    
    # 格式1: 2026年04月10日
    match = re.match(r'(\d{4})年(\d{2})月(\d{2})日', time_str)
    if match:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    
    # 格式2: 2026-04-10
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})', time_str)
    if match:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    
    # 格式3: Unix时间戳
    try:
        if time_str.isdigit() and len(time_str) > 10:
            return datetime.fromtimestamp(int(time_str) / 1000)
        elif time_str.isdigit():
            return datetime.fromtimestamp(int(time_str))
    except:
        pass
    
    return None


def dedup(jobs: List[dict], seen_hashes: set) -> List[dict]:
    """去重过滤：排除已处理的岗位"""
    return [job for job in jobs if job.get('hash', '') not in seen_hashes]


def load_seen_hashes(memory_path: str = "memory/seen_jobs.md") -> set:
    """从 memory/seen_jobs.md 加载已处理的 hash"""
    seen = set()
    memory_file = Path(memory_path)
    
    if not memory_file.exists():
        return seen
    
    with open(memory_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取所有 hash:xxx 模式
    hashes = re.findall(r'hash:([a-f0-9]{32})', content)
    seen.update(hashes)
    
    return seen


def clean_data(jobs: List[dict], truncate_length: int = 6000) -> List[dict]:
    """数据清洗"""
    cleaned = []
    for job in jobs:
        cleaned_job = {
            "title": _clean_text(job.get('title', '')),
            "company": job.get('company', ''),
            "location": job.get('location', ''),
            "category": job.get('category', ''),
            "url": job.get('url', ''),
            "publish_time": job.get('publish_time', ''),
            "duty": _clean_text(job.get('duty', ''), truncate_length),
            "requirement": _clean_text(job.get('requirement', ''), truncate_length // 2),
            "hash": job.get('hash', ''),
            "source": job.get('source', '')
        }
        cleaned.append(cleaned_job)
    return cleaned


def _clean_text(text: str, max_length: int = 6000) -> str:
    """清洗文本"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length] + "..."
    return text


def update_memory(jobs: List[dict], evaluations: List[dict], memory_path: str = "memory/seen_jobs.md"):
    """更新 Memory 文件"""
    memory_file = Path(memory_path)
    memory_file.parent.mkdir(exist_ok=True)
    
    # 按公司分组
    companies = {}
    for i, job in enumerate(jobs):
        company = job.get('company', '未知')
        if company not in companies:
            companies[company] = []
        
        score = evaluations[i].get('score', 0) if i < len(evaluations) else 0
        companies[company].append({
            'title': job.get('title', ''),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'score': score,
            'hash': job.get('hash', '')
        })
    
    # 追加到文件
    with open(memory_file, 'a', encoding='utf-8') as f:
        for company, job_list in companies.items():
            f.write(f"\n## {company}\n")
            for job in job_list:
                f.write(f"- [ ] {job['title']} | {job['date']} | {job['score']}分 | hash:{job['hash']}\n")
```

**Step 2: 提交**

```bash
git add src/filters.py
git commit -m "feat: 创建过滤模块 src/filters.py"
```

---

### Task 2.4: 创建简历解析模块

**Files:**
- Create: `src/resume_parser.py`

**Step 1: 创建 src/resume_parser.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简历解析模块
支持多种格式：txt, md, docx, pdf, png, jpg
"""

import os
import hashlib
from pathlib import Path
from typing import Optional


def parse_resume(file_path: str) -> dict:
    """
    解析简历文件
    
    Returns:
        {
            "content": "简历文本内容",
            "format": "md",
            "hash": "abc123",
            "length": 2000
        }
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    ext = Path(file_path).suffix.lower()
    content = _parse_by_format(file_path, ext)
    
    return {
        "content": content,
        "format": ext,
        "hash": hashlib.md5(content.encode()).hexdigest(),
        "length": len(content)
    }


def _parse_by_format(file_path: str, ext: str) -> str:
    """根据格式解析"""
    parsers = {
        '.txt': _parse_txt,
        '.md': _parse_txt,
        '.docx': _parse_docx,
        '.pdf': _parse_pdf,
        '.png': _parse_image,
        '.jpg': _parse_image,
        '.jpeg': _parse_image,
    }
    
    parser = parsers.get(ext)
    if not parser:
        raise ValueError(f"不支持的格式: {ext}，支持: {list(parsers.keys())}")
    
    return parser(file_path)


def _parse_txt(file_path: str) -> str:
    """解析 txt/md 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def _parse_docx(file_path: str) -> str:
    """解析 docx 文件"""
    try:
        from docx import Document
        doc = Document(file_path)
        text = []
        for para in doc.paragraphs:
            text.append(para.text)
        return '\n'.join(text)
    except ImportError:
        raise ImportError("需要安装 python-docx: pip install python-docx")


def _parse_pdf(file_path: str) -> str:
    """解析 pdf 文件"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text = []
        for page in doc:
            text.append(page.get_text())
        return '\n'.join(text)
    except ImportError:
        raise ImportError("需要安装 PyMuPDF: pip install PyMuPDF")


def _parse_image(file_path: str) -> str:
    """解析图片简历 (使用 Claude Vision)"""
    try:
        import base64
        from anthropic import Anthropic
        
        with open(file_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode()
        
        # 判断图片类型
        ext = Path(file_path).suffix.lower()
        media_type = "image/png" if ext == '.png' else "image/jpeg"
        
        client = Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": "请提取这张简历图片中的所有文字内容，保持原有格式。"}
                ]
            }]
        )
        
        return response.content[0].text
    except ImportError:
        raise ImportError("需要安装 anthropic: pip install anthropic")
```

**Step 2: 提交**

```bash
git add src/resume_parser.py
git commit -m "feat: 创建简历解析模块，支持图片格式"
```

---

### Task 2.5: 创建 CLI 模块

**Files:**
- Create: `src/cli.py`

**Step 1: 创建 src/cli.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CLI 入口
提供命令行接口
"""

import argparse
import sys
from pathlib import Path

from .crawler import get_enabled_companies, crawl_company
from .filters import filter_by_time, dedup, load_seen_hashes, clean_data, update_memory
from .resume_parser import parse_resume


def load_config(profile_name: str = None) -> dict:
    """加载所有配置"""
    # 加载 profiles
    profiles = []
    profiles_dir = Path("profiles")
    
    if profiles_dir.exists():
        for profile_file in profiles_dir.glob("*.md"):
            profile = _parse_profile_md(profile_file)
            if profile:
                if profile_name:
                    if profile.get('name') == profile_name:
                        profiles.append(profile)
                elif profile.get('enabled', True):
                    profiles.append(profile)
    
    # 加载 agent 配置
    agent_config = {}
    agent_config_path = Path("config/agent.yaml")
    if agent_config_path.exists():
        import yaml
        with open(agent_config_path, 'r', encoding='utf-8') as f:
            agent_config = yaml.safe_load(f) or {}
    
    return {
        "profiles": profiles,
        "agent_config": agent_config
    }


def _parse_profile_md(file_path: Path) -> dict:
    """解析 profile Markdown 文件"""
    import yaml
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取 frontmatter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1])
            body = parts[2].strip()
            
            return {
                "name": frontmatter.get('name', file_path.stem),
                "enabled": frontmatter.get('enabled', True),
                "job_type": frontmatter.get('job_type', '社招'),
                "resume": frontmatter.get('resume', ''),
                "keywords": frontmatter.get('keywords', []),
                "intent": body
            }
    
    return None


def sync_companies():
    """同步 companies.md → config/companies.yaml"""
    # TODO: 实现同步逻辑
    print("同步公司列表...")


def run(profile_name: str = None, job_type: str = None, level: str = "moderate", 
        min_score: int = 0, companies: str = None, max_jobs: int = 50):
    """运行求职巡检"""
    print("=" * 60)
    print("SmartJobHunter Agent 启动")
    print("=" * 60)
    
    # Step 1: 加载配置
    print("\n[INIT] 加载配置...")
    config = load_config(profile_name)
    
    if not config["profiles"]:
        print("[ERROR] 未找到匹配的求职意向")
        return
    
    print(f"[LOADED] 找到 {len(config['profiles'])} 个求职意向")
    
    # TODO: 实现完整流程
    # 这里将由 Agent 通过 Skills 调用


def main():
    parser = argparse.ArgumentParser(description='SmartJobHunter CLI')
    subparsers = parser.add_subparsers(dest='command')
    
    # run 命令
    run_parser = subparsers.add_parser('run', help='运行求职巡检')
    run_parser.add_argument('-p', '--profile', help='指定求职意向')
    run_parser.add_argument('-t', '--job-type', choices=['social', 'campus', 'internship'])
    run_parser.add_argument('-l', '--level', choices=['conservative', 'moderate', 'aggressive'], default='moderate')
    run_parser.add_argument('-s', '--min-score', type=int, default=0)
    run_parser.add_argument('-c', '--companies', help='指定公司，逗号分隔')
    run_parser.add_argument('-m', '--max-jobs', type=int, default=50)
    
    # 其他命令
    subparsers.add_parser('list-profiles', help='列出所有求职意向')
    subparsers.add_parser('list-companies', help='列出所有公司')
    subparsers.add_parser('sync-companies', help='同步公司列表')
    subparsers.add_parser('stats', help='查看统计')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        run(
            profile_name=args.profile,
            job_type=args.job_type,
            level=args.level,
            min_score=args.min_score,
            companies=args.companies,
            max_jobs=args.max_jobs
        )
    elif args.command == 'list-profiles':
        config = load_config()
        for profile in config["profiles"]:
            print(f"  - {profile['name']} ({profile['job_type']})")
    elif args.command == 'sync-companies':
        sync_companies()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Step 2: 提交**

```bash
git add src/cli.py
git commit -m "feat: 创建 CLI 模块"
```

---

## Phase 3: 创建 Skills 文件

### Task 3.1: 创建 skill.md

**Files:**
- Create: `.claude/skills/jobhunter/skill.md`

**Step 1: 创建文件**

```markdown
---
name: jobhunter
description: 智能求职巡检 Agent
---

# SmartJobHunter Agent

## 状态机流程

```
INIT → LOADED → CRAWLED → FILTERED → EVALUATED → REPORTED → DONE
```

---

### INIT

**目标**: 初始化并加载所有配置

**执行动作**:
1. 调用 `load_config` 工具
2. 读取 `profiles/{profile_name}.md` 获取求职意向
3. 读取 `resumes/{resume_file}` 获取简历内容
4. 读取 `companies.md` 获取公司列表
5. 读取 `config/agent.yaml` 获取 Agent 配置

**输出变量**:
```
profile = {name, intent, keywords, job_type, resume_path}
resume = "简历文本内容"
companies = ["腾讯", "字节跳动", "美团"]
agent_config = {decision_level, model_strategy, ...}
```

**完成条件**: 所有配置加载成功，无缺失文件

**状态转换**: → LOADED

---

### LOADED

**目标**: 抓取岗位数据

**执行动作**:
1. 调用 `crawl` 工具，传入 companies 和 job_type
2. 等待爬虫完成，获取岗位列表

**输入变量**: companies, job_type

**输出变量**:
```
jobs = [
  {title, company, location, duty, requirement, url, hash, ...},
  ...
]
```

**完成条件**: jobs 列表不为空（或确认无新岗位）

**状态转换**: → CRAWLED

---

### CRAWLED

**目标**: 过滤岗位（确定性 + 语义）

**执行动作**:
1. 调用 `filter_by_time` 工具，传入 jobs 和 time_filter_days
2. 调用 `dedup` 工具，传入过滤后的 jobs，读取 memory/seen_jobs.md
3. 对每个剩余岗位，执行语义过滤:
   - 使用 `semantic_filter` prompt
   - 输入: profile.intent, profile.keywords, job
   - 输出: match_score, match_reason, should_keep
4. 根据 decision_level 阈值过滤

**输入变量**: jobs, profile, agent_config.decision_level

**输出变量**:
```
matched_jobs = [
  {job, match_score, match_reason},
  ...
]
```

**完成条件**: 所有岗位完成语义过滤判断

**状态转换**: → FILTERED

---

### FILTERED

**目标**: 深度评估匹配岗位

**执行动作**:
1. 调用 `clean_data` 工具，截断过长文本
2. 检查 memory/profile_cache.md 是否有缓存的能力画像
3. 执行简历分析 (使用 analyze_resume prompt)
4. 对每个 matched_job 执行岗位评估 (使用 evaluate prompt)
5. (可选) 执行公司背调

**状态转换**: → EVALUATED

---

### EVALUATED

**目标**: 生成报告

**执行动作**:
1. 按评分从高到低排序 evaluations
2. 执行报告生成 (使用 report prompt)
3. 调用 `save_report` 工具

**状态转换**: → REPORTED

---

### REPORTED

**目标**: 更新 Memory

**执行动作**:
1. 调用 `update_memory` 工具
2. 将处理的岗位追加到 memory/seen_jobs.md

**状态转换**: → DONE

---

### DONE

**输出**:
```
✅ 巡检完成
📄 报告: output/20260410_产品经理-TOB方向.md
📊 匹配岗位: 5 个
```

---

## 执行日志格式

```
[INIT] 开始加载配置...
[LOADED] ✓ 配置加载完成
[CRAWLED] ✓ 抓取完成 (50 个岗位)
[FILTERED] ✓ 过滤完成
[EVALUATED] ✓ 评估完成
[REPORTED] ✓ 报告生成
[DONE] ✅ 巡检完成
```

---

## 错误处理

如果某状态执行失败:
1. 输出错误信息: `[ERROR] 状态: XXX, 错误: ...`
2. 停止执行，不进入下一状态
3. 提示用户检查配置或重试
```

**Step 2: 提交**

```bash
git add .claude/skills/jobhunter/skill.md
git commit -m "feat: 创建 Agent skill.md"
```

---

### Task 3.2: 创建工具定义文件

**Files:**
- Create: `.claude/skills/jobhunter/tools/crawl.md`
- Create: `.claude/skills/jobhunter/tools/filter.md`
- Create: `.claude/skills/jobhunter/tools/load_config.md`
- Create: `.claude/skills/jobhunter/tools/update_memory.md`

**Step 1: 创建 tools/crawl.md**

```markdown
---
name: crawl
description: 抓取岗位数据
---

# crawl 工具

## 功能
从配置的公司招聘网站抓取岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| companies | list | 是 | 公司列表 |
| job_type | string | 否 | 岗位类型 (social/campus/internship) |
| max_jobs | int | 否 | 每个公司最大岗位数，默认50 |

## 输出
```json
[
  {
    "title": "AI产品经理",
    "company": "腾讯",
    "location": "北京",
    "duty": "...",
    "requirement": "...",
    "url": "...",
    "hash": "abc123"
  }
]
```

## 实现位置
`src/crawler.py` → `crawl_company()`

## 调用方式
```python
from src.crawler import crawl_company, get_enabled_companies

companies = get_enabled_companies(job_type="social")
for company in companies:
    jobs = crawl_company(company['id'], keyword, max_jobs=50)
```
```

**Step 2: 创建 tools/filter.md**

```markdown
---
name: filter_by_time
description: 时间过滤
---

# filter_by_time 工具

## 功能
过滤最近N天的岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| days | int | 否 | 最近N天，默认3 |

## 输出
过滤后的岗位列表

## 实现位置
`src/filters.py` → `filter_by_time()`

---

---
name: dedup
description: 去重过滤
---

# dedup 工具

## 功能
排除已处理过的岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |

## 输出
去重后的岗位列表

## 实现位置
`src/filters.py` → `dedup()`, `load_seen_hashes()`

---

---
name: clean_data
description: 数据清洗
---

# clean_data 工具

## 功能
清洗和标准化岗位数据

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| truncate_length | int | 否 | 文本截断长度，默认6000 |

## 输出
清洗后的岗位列表

## 实现位置
`src/filters.py` → `clean_data()`
```

**Step 3: 创建 tools/load_config.md**

```markdown
---
name: load_config
description: 加载所有配置文件
---

# load_config 工具

## 功能
加载求职意向、简历、公司列表、Agent配置

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| profile_name | string | 否 | 指定意向名称，为空则加载所有启用的 |

## 输出
```json
{
  "profiles": [...],
  "agent_config": {...}
}
```

## 实现位置
`src/cli.py` → `load_config()`
```

**Step 4: 创建 tools/update_memory.md**

```markdown
---
name: update_memory
description: 更新 Memory
---

# update_memory 工具

## 功能
将处理的岗位追加到 memory/seen_jobs.md

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| evaluations | list | 是 | 评估结果 |

## 输出
成功/失败状态

## 实现位置
`src/filters.py` → `update_memory()`
```

**Step 5: 提交**

```bash
git add .claude/skills/jobhunter/tools/
git commit -m "feat: 创建工具定义文件"
```

---

### Task 3.3: 创建 prompt 文件

**Files:**
- Create: `.claude/skills/jobhunter/prompts/semantic_filter.md`
- Create: `.claude/skills/jobhunter/prompts/analyze_resume.md`
- Create: `.claude/skills/jobhunter/prompts/evaluate.md`
- Create: `.claude/skills/jobhunter/prompts/report.md`

**Step 1: 创建 prompts/semantic_filter.md**

```markdown
# 语义过滤 Agent

你是一个求职匹配专家，判断岗位是否符合求职者的意向。

## 求职意向
{intent}

## 关键词参考
{keywords}

## 岗位信息
- 标题: {title}
- 公司: {company}
- 地点: {location}
- 类别: {category}

## 岗位描述
{duty}

---

请判断这个岗位是否匹配求职意向。

**注意：**
- 不要只看标题，要理解岗位描述的实际内容
- 标题可能不完全匹配，但职责符合也算匹配

**输出格式 (JSON):**
```json
{
  "match_score": 0.8,
  "match_reason": "岗位是TOB SaaS产品方向，符合求职者的企业服务偏好",
  "should_keep": true,
  "concerns": ["地点在上海，求职者期望北京"]
}
```

**评分标准:**
- 0.8-1.0: 高度匹配
- 0.6-0.8: 基本匹配
- 0.4-0.6: 部分匹配
- 0.0-0.4: 不匹配
```

**Step 2: 创建 prompts/analyze_resume.md**

```markdown
# 简历深度分析 Agent

你是一个资深HR，擅长从简历中挖掘候选人的真实能力。

## 简历内容
{resume}

---

请深度分析这份简历，提取候选人的能力画像。

**分析要点:**
1. **显性技能** - 简历明确写出的技能
2. **隐性能力** - 从经历推断的能力
3. **经验亮点** - 最有竞争力的经历
4. **潜在短板** - 可能欠缺的方面

**隐性能力推断示例:**
- "搭建数据看板" → 数据分析能力、可能懂SQL
- "主导产品0-1上线" → 项目管理能力

**输出格式 (JSON):**
```json
{
  "explicit_skills": ["产品规划", "需求分析"],
  "implicit_abilities": [
    {"ability": "项目管理", "evidence": "...", "confidence": "high"}
  ],
  "highlights": ["5年TOB产品经验"],
  "potential_gaps": ["未体现团队管理经验"],
  "career_summary": "资深TOB产品经理"
}
```
```

**Step 3: 创建 prompts/evaluate.md**

```markdown
# 岗位匹配评估 Agent

你是一个资深招聘顾问，评估候选人与岗位的匹配度。

## 候选人能力画像
{ability_profile}

## 求职意向
{intent}

## 岗位信息
- 标题: {title}
- 公司: {company}
- 地点: {location}

## 岗位职责
{duty}

## 任职要求
{requirement}

---

请评估候选人与岗位的匹配度。

**输出格式 (JSON):**
```json
{
  "score": 85,
  "match_analysis": {
    "strong_matches": [...],
    "potential_matches": [...],
    "gaps": [...]
  },
  "match_reasons": ["TOB产品经验丰富"],
  "suggestions": ["投递时重点突出TOB SaaS项目经验"],
  "recommendation": "强烈推荐投递"
}
```

**评分标准:**
- 90-100: 完美匹配
- 75-89: 高度匹配
- 60-74: 基本匹配
- 40-59: 部分匹配
- 0-39: 不太匹配
```

**Step 4: 创建 prompts/report.md**

```markdown
# 报告生成 Agent

你是一个求职顾问，为求职者生成清晰、实用的岗位推荐报告。

## 求职意向
- 名称: {profile_name}
- 类型: {job_type}
- 描述: {intent}

## 统计信息
- 抓取岗位: {total_jobs}
- 过滤后: {filtered_jobs}
- 匹配岗位: {matched_jobs}

## 岗位列表 (含评估结果)
{jobs_with_evaluations}

---

请生成一份 Markdown 格式的求职报告。

**报告要求:**
1. 结构清晰，重点突出
2. 按评分从高到低排序
3. 每个岗位包含: 基本信息、匹配分析、投递建议
4. 末尾添加总结和行动建议
```

**Step 5: 提交**

```bash
git add .claude/skills/jobhunter/prompts/
git commit -m "feat: 创建 Agent prompt 文件"
```

---

## Phase 4: 创建配置文件

### Task 4.1: 创建 agent.yaml

**Files:**
- Create: `config/agent.yaml`

**Step 1: 创建文件**

```yaml
# Agent 决策配置
decision_level: "moderate"  # conservative / moderate / aggressive

# 模型选择策略
model_strategy:
  simple_tasks: "haiku"
  complex_tasks: "sonnet"

# 语义过滤阈值
semantic_filter:
  conservative: 0.8
  moderate: 0.6
  aggressive: 0.4

# 输出配置
output:
  max_jobs_per_report: 20
  include_company_background: true
```

**Step 2: 提交**

```bash
git add config/agent.yaml
git commit -m "feat: 创建 Agent 配置文件"
```

---

### Task 4.2: 移动 companies.yaml

**Files:**
- Move: `companies.yaml` → `config/companies.yaml`

**Step 1: 移动文件**

```bash
mv companies.yaml config/companies.yaml
```

**Step 2: 提交**

```bash
git add config/companies.yaml
git rm companies.yaml
git commit -m "refactor: 移动 companies.yaml 到 config/"
```

---

### Task 4.3: 创建示例 profile

**Files:**
- Create: `profiles/pm_tob.md`

**Step 1: 创建文件**

```markdown
---
name: 产品经理-TOB方向
enabled: true
job_type: 社招
resume: resumes/pm_tob.md
keywords:
  - 产品经理
  - TOB
  - SaaS
  - 企业服务
  - AI产品
---

# 求职意向

寻找 TOB SaaS 产品经理岗位，偏好企业服务、AI方向。
有 5 年产品经验，期望薪资 30-50K，工作地点北京。
```

**Step 2: 提交**

```bash
git add profiles/pm_tob.md
git commit -m "feat: 创建示例求职意向配置"
```

---

### Task 4.4: 创建 companies.md

**Files:**
- Create: `companies.md`

**Step 1: 创建文件**

```markdown
# 公司列表

## 已启用

### 腾讯
- 社招: https://careers.tencent.com/search.html
- 校招: https://careers.tencent.com/search.html

### 字节跳动
- 社招: https://jobs.bytedance.com/experienced/position
- 校招: https://jobs.bytedance.com/campus/position

### 美团
- 社招: https://zhaopin.meituan.com/jobs
- 校招: https://zhaopin.meituan.com/campus

## 待开发

### 阿里巴巴
- 社招: https://talent.alibaba.com/off-campus/position-list
- 校招: https://talent.alibaba.com/campus/position-list
```

**Step 2: 提交**

```bash
git add companies.md
git commit -m "feat: 创建公司列表 Markdown 文件"
```

---

## Phase 5: 迁移数据文件

### Task 5.1: 创建迁移脚本

**Files:**
- Create: `scripts/migrate.py`

**Step 1: 创建目录和文件**

```bash
mkdir -p scripts
```

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据迁移脚本
将旧格式数据迁移到新格式
"""

import json
import yaml
from pathlib import Path


def migrate_seen_jobs():
    """迁移去重数据: jsonl → md"""
    old_file = Path("data/seen_jobs.jsonl")
    new_file = Path("memory/seen_jobs.md")
    
    if not old_file.exists():
        print("未找到旧数据文件，跳过迁移")
        return
    
    # 按公司分组
    companies = {}
    
    with open(old_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                record = json.loads(line)
                company = record.get('company', '未知')
                if company not in companies:
                    companies[company] = []
                companies[company].append(record)
            except json.JSONDecodeError:
                continue
    
    # 写入 Markdown
    new_file.parent.mkdir(exist_ok=True)
    with open(new_file, 'w', encoding='utf-8') as f:
        f.write("# 已处理岗位记录\n\n")
        for company, jobs in companies.items():
            f.write(f"## {company}\n")
            for job in jobs:
                status = "[x]" if job.get('applied') else "[ ]"
                score = job.get('score', 0)
                date = job.get('processed_at', '')[:10] if job.get('processed_at') else ''
                f.write(f"- {status} {job.get('title', '')} | {date} | {score}分 | hash:{job.get('hash', '')}\n")
            f.write("\n")
    
    print(f"✓ 迁移完成: {len(companies)} 个公司")


def migrate_config_to_profiles():
    """迁移配置: config.yaml → profiles/*.md"""
    old_file = Path("config.yaml")
    
    if not old_file.exists():
        print("未找到旧配置文件，跳过迁移")
        return
    
    with open(old_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    profiles_dir = Path("profiles")
    profiles_dir.mkdir(exist_ok=True)
    
    for profile in config.get('profiles', []):
        name = profile.get('name', 'unknown')
        filename = name.replace('/', '-').replace(' ', '_').replace('(', '').replace(')', '')
        
        keywords = profile.get('keywords', [])
        keywords_yaml = '\n'.join([f"  - {k}" for k in keywords])
        
        md_content = f"""---
name: {profile.get('name')}
enabled: {profile.get('enabled', True)}
job_type: {profile.get('job_type', '社招')}
resume: {profile.get('resume_path', '')}
keywords:
{keywords_yaml}
---

# 求职意向

{profile.get('intent', '')}
"""
        
        with open(profiles_dir / f"{filename}.md", 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"✓ 迁移意向: {name}")
    
    print(f"✓ 迁移完成: {len(config.get('profiles', []))} 个意向")


if __name__ == "__main__":
    print("开始数据迁移...")
    migrate_seen_jobs()
    migrate_config_to_profiles()
    print("迁移完成！")
```

**Step 2: 运行迁移脚本**

```bash
python scripts/migrate.py
```

**Step 3: 提交**

```bash
git add scripts/migrate.py memory/ profiles/
git commit -m "feat: 迁移数据文件到新格式"
```

---

## Phase 6: 清理旧文件

### Task 6.1: 删除旧文件

**Files:**
- Delete: `main.py`
- Delete: `config.yaml`
- Delete: `data/` 目录

**Step 1: 删除旧文件**

```bash
rm main.py
rm config.yaml
rm -rf data/
```

**Step 2: 更新 .gitignore**

```bash
echo -e "\n# 旧格式文件\nmain.py\nconfig.yaml\ndata/" >> .gitignore
```

**Step 3: 提交**

```bash
git add -A
git commit -m "refactor: 清理旧文件，完成迁移"
```

---

## Phase 7: 最终提交

### Task 7.1: 更新 README

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`

**Step 1: 更新 README 说明新架构**

更新 README 文件，说明新的目录结构和使用方式。

**Step 2: 提交**

```bash
git add README.md README_CN.md
git commit -m "docs: 更新 README 说明新架构"
```

---

### Task 7.2: 最终提交

**Step 1: 检查所有更改**

```bash
git status
git log --oneline -10
```

**Step 2: 推送到远程**

```bash
git push origin main
```

---

## 完成检查清单

- [ ] Phase 0: 备份原有代码
- [ ] Phase 1: 创建新目录结构
- [ ] Phase 2: 迁移 Python 代码
  - [ ] src/__init__.py
  - [ ] src/crawler.py
  - [ ] src/filters.py
  - [ ] src/resume_parser.py
  - [ ] src/cli.py
- [ ] Phase 3: 创建 Skills 文件
  - [ ] skill.md
  - [ ] tools/*.md
  - [ ] prompts/*.md
- [ ] Phase 4: 创建配置文件
  - [ ] config/agent.yaml
  - [ ] config/companies.yaml
  - [ ] profiles/*.md
  - [ ] companies.md
- [ ] Phase 5: 迁移数据文件
- [ ] Phase 6: 清理旧文件
- [ ] Phase 7: 最终提交
