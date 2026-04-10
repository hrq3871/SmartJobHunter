#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter CLI 模块
提供命令行接口和配置加载功能
"""

import os
import re
import yaml
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 设置环境变量解决编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 导入模块
from . import crawler
from . import filters
from . import resume_parser


def load_config(profile_name: str = None) -> Dict:
    """加载所有配置

    Args:
        profile_name: 指定意向名称，None则返回所有配置

    Returns:
        配置字典，包含:
        - global: 全局配置
        - profiles: 当前意向配置列表
        - job_types: 岗位类型配置
        - companies: 公司配置
    """
    # 加载 Agent 全局配置
    agent_config_path = Path(__file__).parent.parent / "config" / "agent.yaml"
    if agent_config_path.exists():
        with open(agent_config_path, 'r', encoding='utf-8') as f:
            agent_config = yaml.safe_load(f) or {}
    else:
        agent_config = {}

    # 加载 profiles (从 Markdown 文件)
    profiles_dir = Path(__file__).parent.parent / "profiles"
    profiles = []
    if profiles_dir.exists():
        for profile_file in profiles_dir.glob("*.md"):
            profile = _parse_profile_md(str(profile_file))
            if profile:
                profiles.append(profile)

    if profile_name:
        profiles = [p for p in profiles if p.get('name') == profile_name]
    else:
        profiles = [p for p in profiles if p.get('enabled', True)]

    # 加载公司配置
    companies = crawler.get_enabled_companies()

    return {
        'global': agent_config,
        'profiles': profiles,
        'job_types': {
            'internship': {'name': '实习'},
            'campus': {'name': '校招'},
            'social': {'name': '社招'}
        },
        'companies': companies,
        'output': agent_config.get('output', {})
    }


def _parse_profile_md(file_path: str) -> Dict:
    """解析 profile Markdown 文件 (YAML frontmatter 格式)

    Args:
        file_path: profile 文件路径

    Returns:
        profile 配置字典
    """
    path = Path(file_path)
    if not path.exists():
        return None

    content = path.read_text(encoding='utf-8')

    # 解析 YAML frontmatter
    profile = {
        'name': path.stem,
        'enabled': True
    }

    # 提取 frontmatter (--- ... ---)
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = parts[1].strip()
            try:
                fm_data = yaml.safe_load(frontmatter)
                if fm_data:
                    profile.update(fm_data)
            except:
                pass

    # 提取正文作为 intent
    if '---' in content:
        parts = content.split('---', 2)
        if len(parts) >= 3:
            body = parts[2].strip()
            if body and 'intent' not in profile:
                profile['intent'] = body[:500]  # 限制长度

    return profile


def sync_companies():
    """同步 companies.md -> config/companies.yaml

    从 Markdown 文件读取公司配置，更新到 YAML 文件
    """
    companies_md_path = Path(__file__).parent.parent / "公司列表.md"
    companies_yaml_path = Path(__file__).parent.parent / "config" / "companies.yaml"

    if not companies_md_path.exists():
        print("[Warn] companies.md not found")
        return

    # 读取现有 YAML 配置
    if companies_yaml_path.exists():
        with open(companies_yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {'companies': []}
    else:
        config = {'companies': []}

    # 解析 Markdown 并更新
    content = companies_md_path.read_text(encoding='utf-8')

    # 简单同步：从 Markdown 表格提取
    for line in content.split('\n'):
        if line.startswith('|') and '---' not in line:
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 2 and parts[0] not in ['公司', '名称']:
                company_name = parts[0]
                # 查找或创建配置
                existing = next(
                    (c for c in config['companies'] if c.get('name') == company_name),
                    None
                )
                if not existing:
                    config['companies'].append({
                        'id': company_name.lower().replace(' ', '_'),
                        'name': company_name,
                        'enabled': False
                    })

    # 保存
    companies_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with open(companies_yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    print(f"[Done] Synced {len(config['companies'])} companies")


class JobHunter:
    """求职巡检主类"""

    def __init__(self, config_path: str = None):
        """初始化

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path) if config_path else None
        self.config = None
        self.seen_hashes = set()
        self.output_dir = Path("output")
        self.memory_dir = Path("memory")

        # 确保目录存在
        self.output_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)

    def load_config(self):
        """加载配置"""
        if self.config_path:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = load_config()

        # 加载已处理的岗位
        seen_jobs_path = self.memory_dir / "seen_jobs.md"
        self.seen_hashes = filters.load_seen_hashes(str(seen_jobs_path))

    def crawl_jobs(self, keyword: str, max_jobs: int = 50, job_type: str = None) -> List[dict]:
        """调度爬虫抓取岗位

        Args:
            keyword: 搜索关键词
            max_jobs: 最大岗位数
            job_type: 岗位类型

        Returns:
            岗位列表
        """
        all_jobs = []

        # 从配置获取启用的公司
        companies = crawler.get_enabled_companies(job_type)
        print(f"[Crawler] Found {len(companies)} companies for {job_type or 'all'}")

        for company in companies:
            company_id = company.get('id')
            company_name = company.get('name')

            print(f"[Crawler] Crawling {company_name}...")
            try:
                jobs = crawler.crawl_company(company_id, keyword, max_jobs=max_jobs, job_type=job_type)
                all_jobs.extend(jobs)
                print(f"   Got {len(jobs)} jobs")
            except Exception as e:
                print(f"   Crawl failed: {e}")

        return all_jobs

    def filter_jobs(self, jobs: List[dict], profile: dict) -> List[dict]:
        """过滤岗位

        Args:
            jobs: 原始岗位列表
            profile: 意向配置

        Returns:
            过滤后的岗位列表
        """
        global_config = self.config.get('global', {}) if self.config else {}
        time_filter_days = global_config.get('time_filter_days', 3)
        truncate_length = global_config.get('jd_truncate_length', 6000)

        # 时间过滤
        print(f"\n[Filter] Time filter (last {time_filter_days} days)...")
        jobs = filters.filter_by_time(jobs, time_filter_days)
        print(f"   Remaining: {len(jobs)} jobs")

        # 去重
        print("\n[Filter] Dedup...")
        jobs = filters.dedup(jobs, self.seen_hashes)
        print(f"   Remaining: {len(jobs)} jobs")

        # 关键词过滤
        keywords = profile.get('keywords', [])
        if keywords:
            print(f"\n[Filter] Keywords: {keywords}...")
            filtered = []
            for job in jobs:
                title = job.get('title', '').lower()
                duty = job.get('duty', '').lower()
                for kw in keywords:
                    if kw.lower() in title or kw.lower() in duty:
                        filtered.append(job)
                        break
            jobs = filtered
            print(f"   Remaining: {len(jobs)} jobs")

        # 数据清洗
        print("\n[Filter] Cleaning data...")
        jobs = filters.clean_data(jobs, truncate_length)

        return jobs

    def evaluate_job(self, job: dict, profile: dict) -> dict:
        """评估岗位匹配度（基础评估，实际由 Agent 完成）

        Args:
            job: 岗位数据
            profile: 意向配置

        Returns:
            评估结果
        """
        keywords = profile.get('keywords', [])
        title = job.get('title', '').lower()
        duty = job.get('duty', '').lower()[:2000]

        matched_keywords = []
        for kw in keywords:
            if kw.lower() in title or kw.lower() in duty:
                matched_keywords.append(kw)

        score = 0
        if matched_keywords:
            score = min(60 + len(matched_keywords) * 5, 85)

        # AI 相关加分
        ai_keywords = ['ai', '人工智能', '大模型', '机器学习', '深度学习', 'llm', 'gpt']
        for kw in ai_keywords:
            if kw in duty:
                score = min(score + 10, 95)
                break

        return {
            'score': score,
            'match_reasons': [f"Matched keywords: {', '.join(matched_keywords)}"] if matched_keywords else [],
            'missing_skills': [],
            'risk_warning': ''
        }

    def generate_report(self, jobs: List[dict], profile: dict, evaluations: List[dict]):
        """生成报告

        Args:
            jobs: 岗位列表
            profile: 意向配置
            evaluations: 评估结果列表
        """
        profile_name = profile.get('name', 'unknown')
        output_filename = f"{datetime.now().strftime('%Y%m%d')}_{profile_name}.md"
        output_path = self.output_dir / output_filename

        report = f"""# Job Hunting Report

## Basic Info
- **Profile**: {profile_name}
- **Job Type**: {profile.get('job_type', 'All')}
- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **Jobs Found**: {len(jobs)}

## Intent
{profile.get('intent', 'N/A')}

---

## Recommended Jobs

"""

        for i, job in enumerate(jobs, 1):
            evaluation = evaluations[i-1] if i <= len(evaluations) else {}
            score = evaluation.get('score', 0)

            score_emoji = "Green" if score >= 80 else "Yellow" if score >= 60 else "Red"

            report += f"""### {i}. {job.get('title', 'Unknown')} [{score_emoji}] Score: {score}

| Field | Value |
|-------|-------|
| Company | {job.get('company', '')} |
| Location | {job.get('location', '')} |
| Category | {job.get('category', '')} |
| Published | {job.get('publish_time', '')} |
| Work Years | {job.get('work_years', '')} |

**Match Reasons**: {', '.join(evaluation.get('match_reasons', [])) or 'N/A'}

**Duties**:
{job.get('duty', 'N/A')[:500]}...

**Link**: [{job.get('url', '')}]({job.get('url', '')})

---

"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\n[Report] Generated: {output_path}")

    def _map_job_type_to_key(self, job_type: str) -> Optional[str]:
        """将中文岗位类型映射到英文键

        Args:
            job_type: 中文岗位类型（社招/校招/实习）

        Returns:
            英文键（social/campus/internship）或 None
        """
        mapping = {
            '社招': 'social',
            '校招': 'campus',
            '实习': 'internship',
            '全部': None
        }
        return mapping.get(job_type, None) if job_type else None

    def run_profile(self, profile: dict, job_type_override: str = None) -> List[dict]:
        """运行单个求职意向的巡检

        Args:
            profile: 意向配置
            job_type_override: 覆盖岗位类型

        Returns:
            处理的岗位列表
        """
        profile_name = profile.get('name', 'unknown')
        keywords = profile.get('keywords', [])
        job_type = job_type_override or profile.get('job_type', '全部')
        resume_path = profile.get('resume_path', '')

        print(f"\n{'='*50}")
        print(f"[Profile] {profile_name}")
        print(f"[Type] {job_type}")
        if resume_path:
            print(f"[Resume] {resume_path}")
        print(f"{'='*50}")

        # 加载简历
        if resume_path:
            resume_result = resume_parser.parse_resume(resume_path)
            if resume_result.get('content', '').startswith("[错误]"):
                print(f"   {resume_result['content']}")
            else:
                print(f"   Resume loaded ({resume_result['length']} chars)")

        # 获取全局配置
        global_config = self.config.get('global', {}) if self.config else {}
        time_filter_days = global_config.get('time_filter_days', 3)
        threshold_score = global_config.get('threshold_score', 70)

        # Step 1: 抓取岗位
        print("\n[Step 1] Crawling jobs...")
        keyword = keywords[0] if keywords else "产品经理"
        # 将中文岗位类型映射到英文键
        job_type_key = self._map_job_type_to_key(job_type)
        jobs = self.crawl_jobs(keyword, max_jobs=50, job_type=job_type_key)

        if not jobs:
            print("[Warn] No jobs found")
            return []

        print(f"   Total: {len(jobs)} jobs")

        # Step 2-3: 过滤
        jobs = self.filter_jobs(jobs, profile)

        if not jobs:
            print("[Warn] No jobs after filtering")
            return []

        # Step 4: AI 评估
        print("\n[Step 4] Evaluating jobs...")
        evaluations = []
        for job in jobs:
            eval_result = self.evaluate_job(job, profile)
            evaluations.append(eval_result)
            print(f"   [{job.get('company')}] {job.get('title')[:20]}... -> {eval_result['score']}")

        # Step 5: 生成报告
        print("\n[Step 5] Generating report...")
        self.generate_report(jobs, profile, evaluations)

        # Step 6: 更新去重数据库
        print("\n[Step 6] Updating seen jobs...")
        seen_jobs_path = self.memory_dir / "seen_jobs.md"
        filters.update_memory(jobs, evaluations, str(seen_jobs_path))
        # 更新 hash 集合
        for job in jobs:
            self.seen_hashes.add(job.get('hash', ''))

        return jobs

    def run(self, profile_name: str = None, job_type: str = None):
        """运行完整的求职巡检

        Args:
            profile_name: 指定意向名称
            job_type: 覆盖岗位类型
        """
        print("="*60)
        print("SmartJobHunter Agent Started")
        print("="*60)

        # 加载配置
        self.load_config()

        profiles = self.config.get('profiles', []) if self.config else []

        if not profiles:
            print("[Warn] No profiles found")
            return

        print(f"\nFound {len(profiles)} profiles to process:")
        for p in profiles:
            print(f"  - {p.get('name')} ({p.get('job_type', 'All')})")

        all_jobs = []
        for profile in profiles:
            jobs = self.run_profile(profile, job_type)
            all_jobs.extend(jobs)

        print("\n" + "="*60)
        print(f"[Done] Total {len(all_jobs)} jobs processed")
        print("="*60)


def parse_command(command: str) -> dict:
    """解析用户指令

    Args:
        command: 自然语言指令

    Returns:
        解析结果
    """
    result = {
        "action": "run",
        "profile": None,
        "job_type": None,
        "keyword": None
    }

    command = command.lower()

    # 解析岗位性质
    if "实习" in command:
        result["job_type"] = "internship"
    elif "校招" in command:
        result["job_type"] = "campus"
    elif "社招" in command:
        result["job_type"] = "social"

    # 解析关键词
    keywords_match = re.search(r'搜索["\']?(.+?)["\']?', command)
    if keywords_match:
        result["keyword"] = keywords_match.group(1).strip()

    return result


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(description='SmartJobHunter Agent')
    parser.add_argument('-c', '--config', default=None, help='Config file path (optional)')
    parser.add_argument('-p', '--profile', help='Profile name')
    parser.add_argument('-t', '--job-type', choices=['internship', 'campus', 'social'], help='Job type')
    parser.add_argument('-k', '--keyword', help='Search keyword')
    parser.add_argument('--list-profiles', action='store_true', help='List all profiles')
    parser.add_argument('command', nargs='?', help='Natural language command')

    args = parser.parse_args()

    hunter = JobHunter(args.config)

    if args.list_profiles:
        config = load_config()
        print("Available profiles:")
        for profile in config.get('profiles', []):
            job_type = profile.get('job_type', 'All')
            print(f"  - {profile.get('name', 'Unnamed')} [{job_type}]")
        print("\nAvailable job types:")
        for type_key, type_config in config.get('job_types', {}).items():
            print(f"  - {type_key}: {type_config.get('name', '')}")
        return

    # 解析自然语言指令
    job_type = args.job_type
    if args.command:
        parsed = parse_command(args.command)
        if parsed["job_type"] and not job_type:
            job_type = parsed["job_type"]

    hunter.run(args.profile, job_type)


if __name__ == "__main__":
    main()
