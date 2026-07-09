#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter CLI 模块
提供命令行接口和配置加载功能
"""

import os
import re
import sys
import yaml
import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 设置环境变量解决编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 导入模块
from . import crawler_factory
from . import filters
from . import matching
from . import resume_parser
from .agent_review import (
    build_agent_review_queue,
    load_agent_review_results,
    write_agent_review_queue,
)
from .reporting import render_full_crawl_audit
from .run_records import (
    attach_evaluation,
    create_run_records,
    select_record_ids_for_jobs,
    update_record_stage,
)
from .exceptions import ConfigError, ProfileNotFoundError


DEFAULT_AGENT_REVIEW_MAX_CANDIDATES = 40


def _job_filter_key(job: dict) -> Tuple[str, str, str, str]:
    return (
        str(job.get("hash") or ""),
        str(job.get("url") or ""),
        str(job.get("company") or ""),
        str(job.get("title") or ""),
    )


def validate_profile(profile: dict) -> bool:
    """验证意向配置

    Args:
        profile: 意向配置字典

    Raises:
        ConfigError: 配置无效时抛出
    """
    required = ['name']
    for field in required:
        if not profile.get(field):
            raise ConfigError(f"Profile missing required field: {field}")

    # 检查列表型字段。旧字段 keywords/exclude_keywords 继续兼容。
    list_fields = [
        'keywords',
        'exclude_keywords',
        'target_roles',
        'target_domains',
        'employment_types',
        'must_have',
        'nice_to_have',
        'avoid',
        'dealbreakers',
        'locations',
    ]
    for field in list_fields:
        value = profile.get(field)
        if value and not isinstance(value, list):
            raise ConfigError(f"Profile '{profile.get('name')}' {field} must be a list")

    return True


def validate_company_config(company: dict) -> bool:
    """验证公司配置

    Args:
        company: 公司配置字典

    Raises:
        ConfigError: 配置无效时抛出
    """
    required = ['id', 'name']
    for field in required:
        if not company.get(field):
            raise ConfigError(f"Company config missing required field: {field}")

    return True


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
        profiles = [
            p for p in profiles
            if p.get('name') == profile_name or p.get('_profile_id') == profile_name
        ]
    else:
        profiles = [p for p in profiles if p.get('enabled', True)]

    # 加载公司配置
    companies = crawler_factory.get_enabled_companies()

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
    profile = {
        'name': path.stem,
        'enabled': True,
        '_profile_id': path.stem,
        '_profile_path': str(path),
    }

    # 解析 YAML frontmatter (--- ... ---)
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                fm_data = yaml.safe_load(parts[1].strip())
                if fm_data:
                    profile.update(fm_data)
                    profile['_profile_id'] = path.stem
                    profile['_profile_path'] = str(path)
            except Exception:
                pass

            # 提取正文作为 intent
            body = parts[2].strip()
            if body and 'intent' not in profile:
                profile['intent'] = body[:500]

    # 验证
    try:
        validate_profile(profile)
    except ConfigError as e:
        print(f"[Warn] Invalid profile {file_path}: {e}", file=sys.stderr)
        return None

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
        self._pending_repairs: List[dict] = []
        self._last_filter_reasons: Dict[Tuple[str, str, str, str], Tuple[str, str]] = {}

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

    def crawl_jobs(self, keywords: list, max_jobs: int = 50, job_type: str = None) -> List[dict]:
        """调度爬虫抓取岗位

        对每个搜索词遍历所有启用公司。0 结果或异常的公司自动收集为
        待修复批次，写入 logs/strategy_tasks/。

        Args:
            keywords: 搜索关键词列表
            max_jobs: 最大岗位数（每个词每条公司上限）
            job_type: 岗位类型

        Returns:
            岗位列表（多词合并、按 hash 去重）
        """
        all_jobs: List[dict] = []
        seen_hashes: set = set()
        self._pending_repairs = []
        failed_companies: set = set()  # 只标记一次

        companies = crawler_factory.get_enabled_companies(job_type)
        print(f"[Crawler] {len(companies)} companies × {len(keywords)} keyword(s) for {job_type or 'all'}")

        for kw in keywords:
            print(f"\n[Crawler] ── keyword: {kw} ──")
            for company in companies:
                company_id = company.get('id')
                company_name = company.get('name')

                print(f"[Crawler] Crawling {company_name}...")
                try:
                    jobs = crawler_factory.crawl_company(company_id, kw, max_jobs=max_jobs, job_type=job_type)
                    new_count = 0
                    for job in jobs:
                        h = job.get('hash', '')
                        if h and h not in seen_hashes:
                            seen_hashes.add(h)
                            all_jobs.append(job)
                            new_count += 1
                    print(f"   Got {len(jobs)} jobs ({new_count} new)")

                    if not jobs and company_id not in failed_companies:
                        failed_companies.add(company_id)
                        self._pending_repairs.append({
                            "company_id": company_id,
                            "company_name": company_name,
                            "reason": "no_jobs_found",
                            "detail": f"抓取返回 0 个岗位（关键词: {kw}）",
                        })
                        print(f"   → marked for repair batch")

                except Exception as e:
                    if company_id not in failed_companies:
                        failed_companies.add(company_id)
                        self._pending_repairs.append({
                            "company_id": company_id,
                            "company_name": company_name,
                            "reason": "crawl_exception",
                            "detail": str(e),
                        })
                    print(f"   Crawl failed: {e} → marked for repair batch")

        return all_jobs

    def _resolve_search_keywords(self, profile: dict) -> List[str]:
        """Return the ordered crawl keywords for a profile."""
        raw_keywords = profile.get('search_keywords') or profile.get('keywords') or ["产品经理"]
        if isinstance(raw_keywords, str):
            raw_keywords = [item for item in re.split(r"[,，、\s]+", raw_keywords) if item]
        return [str(item).strip() for item in raw_keywords if str(item).strip()]

    def write_batch_repair_task(self, keyword: str, job_type: str) -> str:
        """将本轮全部失败公司写入一份批量修复 task，供 Agent 一次性委派子 Agent。"""
        if not self._pending_repairs:
            return ""

        batch = {
            "batch_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "keyword": keyword,
            "job_type": job_type,
            "failed_companies": self._pending_repairs,
        }

        # 写入日志目录供 Agent 读取
        task_dir = Path("logs") / "strategy_tasks" / f"_batch_{batch['batch_id']}"
        task_dir.mkdir(parents=True, exist_ok=True)
        task_path = task_dir / "task.json"
        task_path.write_text(
            json.dumps(batch, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"\n[Repair] Batch task written: {task_path}")
        print(f"[Repair] {len(self._pending_repairs)} companies need strategy repair:")
        for c in self._pending_repairs:
            print(f"  - {c['company_name']} ({c['company_id']}) : {c['reason']}")

        return str(task_path)

    def _record_filter_drops(
        self,
        before_jobs: List[dict],
        after_jobs: List[dict],
        stage: str,
        reason: str,
    ) -> None:
        kept_keys = {_job_filter_key(job) for job in after_jobs}
        for job in before_jobs:
            if _job_filter_key(job) not in kept_keys:
                self._last_filter_reasons[_job_filter_key(job)] = (stage, reason)

    def filter_jobs(self, jobs: List[dict], profile: dict, job_type: str = None) -> List[dict]:
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
        self._last_filter_reasons = {}

        # 时间过滤
        print(f"\n[Filter] Time filter (last {time_filter_days} days)...")
        before_time_filter = list(jobs)
        profile_job_type = self._map_job_type_to_key(profile.get('job_type')) or profile.get('job_type')
        jobs = filters.filter_by_time(
            jobs,
            time_filter_days,
            job_type=job_type or profile_job_type,
        )
        self._record_filter_drops(
            before_time_filter,
            jobs,
            "time_filtered",
            "publish_time_outside_window",
        )
        print(f"   Remaining: {len(jobs)} jobs")

        # 去重
        print("\n[Filter] Dedup...")
        before_dedup = list(jobs)
        jobs = filters.dedup(jobs, self.seen_hashes)
        self._record_filter_drops(
            before_dedup,
            jobs,
            "deduplicated",
            "seen_job_hash",
        )
        print(f"   Remaining: {len(jobs)} jobs")

        # 数据清洗
        print("\n[Filter] Cleaning data...")
        jobs = filters.clean_data(jobs, truncate_length)

        # 语义过滤：Python fallback 按 Agent 评分规则判断，不再只做关键词包含。
        # 新版 profile 由 target_roles/must_have/avoid 等字段驱动，旧版 keywords/intent 继续兼容。
        semantic_fields = [
            'keywords',
            'intent',
            'target_roles',
            'target_domains',
            'must_have',
            'nice_to_have',
            'avoid',
            'dealbreakers',
            'exclude_keywords',
        ]
        if any(profile.get(field) for field in semantic_fields):
            decision_level = global_config.get('decision_level', 'moderate')
            semantic_thresholds = global_config.get('semantic_filter', {})
            print(f"\n[Filter] Semantic intent match ({decision_level})...")
            matched_jobs = []
            for job in jobs:
                semantic = matching.match_job_intent(job, profile, decision_level)
                if decision_level in semantic_thresholds:
                    threshold = semantic_thresholds[decision_level]
                    semantic['threshold'] = threshold
                    semantic['should_keep'] = semantic.get('match_score', 0) >= threshold
                job['semantic_match'] = semantic
                if semantic.get('should_keep'):
                    matched_jobs.append(job)
                else:
                    self._last_filter_reasons[_job_filter_key(job)] = (
                        "semantic_rejected",
                        "semantic_intent_mismatch",
                    )
            jobs = matched_jobs
            print(f"   Remaining: {len(jobs)} jobs")

        return jobs

    def evaluate_job(self, job: dict, profile: dict) -> dict:
        """评估岗位匹配度（Python fallback，Agent 可用更深度 LLM 评估）

        Args:
            job: 岗位数据
            profile: 意向配置

        Returns:
            评估结果
        """
        return matching.evaluate_job_fit(
            job,
            profile,
            resume_text=profile.get('_resume_content', ''),
            ability_profile=profile.get('_ability_profile'),
        )

    def _rank_and_filter_results(
        self,
        jobs: List[dict],
        evaluations: List[dict],
        *,
        max_jobs: Optional[int] = None,
    ) -> Tuple[List[dict], List[dict]]:
        """按评分排序，并应用阈值和调用方指定的数量上限。"""
        global_config = self.config.get('global', {}) if self.config else {}
        output_config = self.config.get('output', {}) if self.config else {}
        threshold_score = global_config.get('threshold_score', 70)
        if max_jobs is None:
            max_jobs = output_config.get('max_jobs_per_report')

        paired = list(zip(jobs, evaluations))
        paired.sort(key=lambda item: item[1].get('score', 0), reverse=True)

        if threshold_score is not None:
            paired = [
                (job, evaluation)
                for job, evaluation in paired
                if evaluation.get('score', 0) >= threshold_score
            ]

        if max_jobs:
            paired = paired[:int(max_jobs)]

        if not paired:
            return [], []

        ranked_jobs, ranked_evaluations = zip(*paired)
        return list(ranked_jobs), list(ranked_evaluations)

    def _daily_output_dir(self) -> Path:
        """Return the date archive directory for generated artifacts."""
        date_dir = self.output_dir / datetime.now().strftime('%Y-%m-%d')
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir

    def _agent_review_required(self) -> bool:
        agent_review = self.config.get('agent_review', {}) if self.config else {}
        return bool(agent_review.get('required_for_recommendation', True))

    def _agent_review_candidate_limit(self) -> Optional[int]:
        """Return how many fallback-ranked jobs should be sent to Agent review."""
        agent_review = self.config.get('agent_review', {}) if self.config else {}
        configured = agent_review.get('max_candidates')
        if configured not in (None, ""):
            try:
                limit = int(configured)
            except (TypeError, ValueError):
                limit = DEFAULT_AGENT_REVIEW_MAX_CANDIDATES
            return limit if limit > 0 else None

        output_limit = None
        if self.config:
            output_limit = self.config.get('output', {}).get('max_jobs_per_report')
        try:
            output_limit = int(output_limit) if output_limit not in (None, "") else 0
        except (TypeError, ValueError):
            output_limit = 0
        return max(DEFAULT_AGENT_REVIEW_MAX_CANDIDATES, output_limit)

    def _agent_review_results_path(self, queue_path: Path) -> Path:
        agent_review = self.config.get('agent_review', {}) if self.config else {}
        configured = agent_review.get('results_path')
        if configured:
            return Path(configured)
        return queue_path.with_name(f"{queue_path.stem}_results.json")

    def _write_agent_review_queue(
        self,
        records: List[dict],
        profile: dict,
        run_id: str,
    ) -> Path:
        """Write the Agent semantic scoring queue for ranked fallback candidates."""
        profile_id = profile.get('_profile_id') or profile.get('name', 'unknown')
        queue_dir = self._daily_output_dir() / "agent_review_queues"
        queue_path = queue_dir / f"{profile_id}_{run_id}.json"
        queue = build_agent_review_queue(
            records,
            profile,
            queue_id=f"{profile_id}_{run_id}",
        )
        return write_agent_review_queue(queue, queue_path)

    def _mark_pre_review_omissions(
        self,
        run_records: List[dict],
        filtered_record_ids: set[str],
        review_record_ids: set[str],
        threshold_score: int | float | None,
    ) -> None:
        records_by_id = self._records_by_id(run_records)
        below_threshold: set[str] = set()
        candidate_limit_omitted: set[str] = set()
        for record_id in filtered_record_ids - review_record_ids:
            record = records_by_id.get(record_id) or {}
            score = ((record.get("evaluation") or {}).get("score") or 0)
            if threshold_score is not None and score < threshold_score:
                below_threshold.add(record_id)
            else:
                candidate_limit_omitted.add(record_id)
        update_record_stage(run_records, below_threshold, "below_threshold", "score_below_threshold")
        update_record_stage(
            run_records,
            candidate_limit_omitted,
            "candidate_limit_omitted",
            "agent_review_queue_limit",
        )

    @staticmethod
    def _records_by_id(records: List[dict]) -> Dict[str, dict]:
        return {str(record.get("run_record_id")): record for record in records}

    def _url_is_available(self, url: str, timeout: int = 8) -> bool:
        """Return True only when a report URL is reachable and not 404-like."""
        if not url or not str(url).startswith(("http://", "https://")):
            return False

        headers = {"User-Agent": "Mozilla/5.0 SmartJobHunter URL Validator"}
        for method in ("HEAD", "GET"):
            request = urllib.request.Request(url, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return 200 <= response.status < 400
            except urllib.error.HTTPError as exc:
                if exc.code == 405 and method == "HEAD":
                    continue
                return 200 <= exc.code < 400
            except Exception:
                if method == "HEAD":
                    continue
                return False
        return False

    def _filter_live_urls(self, jobs: List[dict], evaluations: List[dict]) -> Tuple[List[dict], List[dict]]:
        """Drop jobs whose links are missing or not reachable."""
        valid_pairs = []
        for job, evaluation in zip(jobs, evaluations):
            url = job.get('url', '')
            if self._url_is_available(url):
                valid_pairs.append((job, evaluation))
            else:
                print(f"[URL] Dropped unavailable link: {job.get('company', '')} - {job.get('title', '')} ({url})")

        if not valid_pairs:
            return [], []
        valid_jobs, valid_evaluations = zip(*valid_pairs)
        return list(valid_jobs), list(valid_evaluations)

    def generate_application_package(self, jobs: List[dict], profile: dict, evaluations: List[dict]) -> str:
        """Generate a Top 3 application package with customized cover letters."""
        profile_name = profile.get('name', 'unknown')
        profile_id = profile.get('_profile_id') or profile_name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        package_dir = self._daily_output_dir() / "application_packages" / f"{profile_id}_{timestamp}"
        package_dir.mkdir(parents=True, exist_ok=True)

        paired = list(zip(jobs, evaluations))
        paired.sort(key=lambda item: item[1].get('score', 0), reverse=True)
        top_pairs = paired[:3]

        index_lines = [
            "# Application Package",
            "",
            f"- Profile: {profile_name}",
            f"- Profile ID: {profile_id}",
            f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Top 3",
            "",
        ]

        for index, (job, evaluation) in enumerate(top_pairs, 1):
            filename = f"cover_letter_{index:02d}_{self._safe_filename(job.get('company', 'company'))}.md"
            letter_path = package_dir / filename
            letter_path.write_text(
                self._build_cover_letter(job, profile, evaluation),
                encoding='utf-8',
            )
            index_lines.append(
                f"{index}. {job.get('company', '')} - {job.get('title', '')} "
                f"({evaluation.get('score', 0)}) -> {filename}"
            )

        (package_dir / "index.md").write_text("\n".join(index_lines) + "\n", encoding='utf-8')
        print(f"[Package] Generated: {package_dir}")
        return str(package_dir)

    def _build_cover_letter(self, job: dict, profile: dict, evaluation: dict) -> str:
        company = job.get('company', '贵公司')
        title = job.get('title', '目标岗位')
        resume_text = profile.get('_resume_content', '') or profile.get('intent', '')
        resume_evidence = self._brief_text(resume_text, 260)
        duty = self._brief_text(job.get('duty', ''), 220)
        requirement = self._brief_text(job.get('requirement', ''), 180)
        reasons = "；".join(evaluation.get('match_reasons', [])[:4]) or "岗位方向与求职目标匹配"
        risk = evaluation.get('risk_warning') or "暂无明显风险"

        return f"""# Cover Letter - {company} {title}

尊敬的 {company} 招聘团队：

您好。我正在申请 {title} 岗位。这个岗位吸引我的核心原因是：{reasons}。

结合岗位描述，我理解该岗位重点关注：
- {duty or title}
- {requirement or '候选人需要能结合业务目标推进产品落地'}

我的相关经历可以支撑这类工作：
- {resume_evidence or '我具备产品规划、需求分析和跨团队推进经验，可结合岗位要求补充具体项目案例。'}

如果进入面试，我会重点准备以下内容：
- 与 {title} 最相关的项目背景、目标、方案和结果
- 如何把 AI 能力转化为真实业务价值
- 对岗位风险点的回应：{risk}

感谢您的时间，期待有机会进一步沟通。
"""

    def _brief_text(self, text: str, limit: int) -> str:
        text = re.sub(r'\s+', ' ', str(text or '')).strip()
        return text[:limit]

    def _safe_filename(self, value: str) -> str:
        value = re.sub(r'[\\/:*?"<>|\s]+', '_', str(value or 'item')).strip('_')
        return value[:40] or 'item'

    def generate_report(
        self,
        jobs: List[dict],
        profile: dict,
        evaluations: List[dict],
        run_records: List[dict] | None = None,
    ) -> str:
        """生成报告

        Args:
            jobs: 岗位列表
            profile: 意向配置
            evaluations: 评估结果列表

        Returns:
            输出文件路径
        """
        profile_name = profile.get('name', 'unknown')
        profile_id = profile.get('_profile_id') or profile_name
        # 新格式：{简历标识}_{YYYYMMDD_HHMM}.md
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        output_filename = f"{profile_id}_{timestamp}.md"
        output_path = self._daily_output_dir() / output_filename

        report = f"""# Job Hunting Report

## Basic Info
- **Profile**: {profile_name}
- **Profile ID**: {profile_id}
- **Profile File**: {profile.get('_profile_path', 'N/A')}
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
            recommendation = evaluation.get('recommendation', 'N/A')
            risk_warning = evaluation.get('risk_warning')

            score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"

            report += f"""### {i}. {job.get('company', '')}－{job.get('title', 'Unknown')} [{score_emoji}] Score: {score}

| Field | Value |
|-------|-------|
| Company | {job.get('company', '')} |
| Location | {job.get('location', '')} |
| Category | {job.get('category', '')} |
| Published | {job.get('publish_time', '')} |
| Work Years | {job.get('work_years', '')} |
| Recommendation | {recommendation} |

**Match Reasons**: {', '.join(evaluation.get('match_reasons', [])) or 'N/A'}

**Risk Warning**: {risk_warning or 'N/A'}

**Duties**:
{job.get('duty', 'N/A')[:500]}...

**Link**: [{job.get('url', '')}]({job.get('url', '')})

---

"""

        report += "\n" + render_full_crawl_audit(run_records or [])

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\n[Report] Generated: {output_path}")
        return str(output_path)

    # 岗位类型映射表
    JOB_TYPE_MAPPING = {
        'social': 'social',
        'campus': 'campus',
        'internship': 'internship',
        '社招': 'social',
        '校招': 'campus',
        '实习': 'internship',
        '全部': None
    }

    def _map_job_type_to_key(self, job_type: str) -> Optional[str]:
        """将中文岗位类型映射到英文键

        Args:
            job_type: 中文岗位类型（社招/校招/实习）

        Returns:
            英文键（social/campus/internship）或 None
        """
        return self.JOB_TYPE_MAPPING.get(job_type) if job_type else None

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
        profile = dict(profile)
        resume_path = profile.get('resume_path') or profile.get('resume') or ''

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
                print("   [Profile] Configured resume is unavailable; skip this profile to avoid low-confidence recommendations")
                return []
            print(f"   Resume loaded ({resume_result['length']} chars)")
            profile['_resume_content'] = resume_result.get('content', '')
            profile['_ability_profile'] = matching.summarize_resume_ability(profile['_resume_content'])

        # 获取全局配置
        global_config = self.config.get('global', {}) if self.config else {}
        time_filter_days = global_config.get('time_filter_days', 3)
        threshold_score = global_config.get('threshold_score', 70)

        # Step 1: 抓取岗位
        print("\n[Step 1] Crawling jobs...")
        search_keywords = self._resolve_search_keywords(profile)
        search_keyword_label = "、".join(search_keywords)
        job_type_key = self._map_job_type_to_key(job_type)
        jobs = self.crawl_jobs(search_keywords, max_jobs=50, job_type=job_type_key)

        # Step 1.5: 若存在抓取失败的公司，写入批量修复 task 并打印提示，
        # 但不中断流程——报告照常生成，Agent 可在跑完后修复。
        if self._pending_repairs:
            batch_path = self.write_batch_repair_task(search_keyword_label, job_type_key)
            print(f"\n[Repair Notice] {len(self._pending_repairs)} company(s) failed to crawl.")
            print(f"[Repair Notice] Batch task: {batch_path}")
            print(f"[Repair Notice] Run crawler-strategy-inspector to fix, then re-run crawl.")
            self._last_batch_task = batch_path

        if not jobs:
            print("[Warn] No jobs found")
            return []

        print(f"   Total: {len(jobs)} jobs")

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_records = create_run_records(jobs, run_id)
        for record in run_records:
            fallback_evaluation = self.evaluate_job(record["raw_job"], profile)
            attach_evaluation(record, fallback_evaluation, source="python_fallback")

        # Step 2-3: 过滤
        jobs = self.filter_jobs(jobs, profile, job_type_key)
        filtered_record_ids = select_record_ids_for_jobs(run_records, jobs)
        all_record_ids = {record["run_record_id"] for record in run_records}
        filtered_out_record_ids = all_record_ids - filtered_record_ids
        attributed_record_ids = set()
        for record in run_records:
            record_id = record["run_record_id"]
            if record_id not in filtered_out_record_ids:
                continue
            filter_reason = self._last_filter_reasons.get(_job_filter_key(record.get("raw_job") or {}))
            if not filter_reason:
                continue
            stage, reason = filter_reason
            update_record_stage(run_records, {record_id}, stage, reason)
            attributed_record_ids.add(record_id)
        update_record_stage(
            run_records,
            filtered_out_record_ids - attributed_record_ids,
            "filtered_out",
            "filtered_before_recommendation",
        )
        update_record_stage(run_records, filtered_record_ids, "filtered_in")

        if not jobs:
            print("[Warn] No jobs after filtering")
            self.generate_report([], profile, [], run_records=run_records)
            return []

        # Step 4: AI 评估
        print("\n[Step 4] Evaluating jobs...")
        evaluations = []
        for job in jobs:
            eval_result = self.evaluate_job(job, profile)
            evaluations.append(eval_result)
            print(f"   [{job.get('company')}] {job.get('title')[:20]}... -> {eval_result['score']}")

        review_candidate_limit = self._agent_review_candidate_limit()
        review_jobs, review_evaluations = self._rank_and_filter_results(
            jobs,
            evaluations,
            max_jobs=review_candidate_limit,
        )
        review_record_ids = select_record_ids_for_jobs(run_records, review_jobs)
        self._mark_pre_review_omissions(
            run_records,
            filtered_record_ids,
            review_record_ids,
            threshold_score,
        )
        update_record_stage(run_records, review_record_ids, "ranked_candidate")
        if not review_jobs:
            print("[Warn] No jobs meet threshold_score after evaluation")
            self.generate_report([], profile, [], run_records=run_records)
            seen_jobs_path = self.memory_dir / "seen_jobs.md"
            filters.update_memory(jobs, evaluations, str(seen_jobs_path))
            for job in jobs:
                self.seen_hashes.add(job.get('hash', ''))
            return []

        report_jobs, report_evaluations = review_jobs, review_evaluations
        ranked_record_ids = set(review_record_ids)
        ranked_records = [
            record for record in run_records
            if record.get("run_record_id") in review_record_ids
        ]
        agent_review_required = self._agent_review_required()
        queue_path = self._write_agent_review_queue(ranked_records, profile, run_id)
        results_path = self._agent_review_results_path(queue_path)
        profile["_agent_review_queue_path"] = str(queue_path)
        profile["_agent_review_results_path"] = str(results_path)
        print(f"\n[Agent Review] Queue written: {queue_path}")

        if results_path.exists():
            print(f"[Agent Review] Loading results: {results_path}")
            agent_results = load_agent_review_results(
                results_path,
                required_record_ids=review_record_ids,
            )
            records_by_id = self._records_by_id(run_records)
            for record_id, agent_evaluation in agent_results.items():
                record = records_by_id.get(record_id)
                if record:
                    attach_evaluation(record, agent_evaluation, source="agent")

            agent_pairs = []
            eligible_agent_record_ids: set[str] = set()
            for record_id in review_record_ids:
                record = records_by_id.get(record_id)
                if not record:
                    continue
                evaluation = (record.get("evaluation") or {}).get("raw") or {}
                decision = evaluation.get("recommendation")
                score = evaluation.get("score", 0) or 0
                if decision in {"strong_apply", "apply", "maybe"} and score >= threshold_score:
                    agent_pairs.append((record.get("raw_job") or {}, evaluation))
                    eligible_agent_record_ids.add(record_id)
                else:
                    update_record_stage(
                        run_records,
                        {record_id},
                        "agent_rejected",
                        "agent_semantic_decision_not_recommended",
                    )

            agent_pairs.sort(key=lambda item: item[1].get("score", 0), reverse=True)
            max_jobs = self.config.get('output', {}).get('max_jobs_per_report') if self.config else None
            if max_jobs:
                agent_pairs = agent_pairs[:int(max_jobs)]
            if agent_pairs:
                report_jobs, report_evaluations = map(list, zip(*agent_pairs))
            else:
                report_jobs, report_evaluations = [], []
            ranked_record_ids = select_record_ids_for_jobs(run_records, report_jobs)
            update_record_stage(
                run_records,
                eligible_agent_record_ids - ranked_record_ids,
                "report_limit_omitted",
                "final_report_limit",
            )
            update_record_stage(run_records, ranked_record_ids, "agent_ranked_candidate")
        elif agent_review_required:
            print("[Agent Review] Results missing; formal recommendations require Agent scoring.")
            update_record_stage(
                run_records,
                review_record_ids,
                "needs_agent_review",
                "agent_review_required_for_final_recommendation",
            )
            self.generate_report([], profile, [], run_records=run_records)
            return []

        # Step 5: URL 校验
        print("\n[Step 5] Validating job links...")
        report_jobs, report_evaluations = self._filter_live_urls(report_jobs, report_evaluations)
        recommended_record_ids = select_record_ids_for_jobs(run_records, report_jobs)
        update_record_stage(
            run_records,
            ranked_record_ids - recommended_record_ids,
            "url_rejected",
            "unreachable_or_invalid_url",
        )
        if not report_jobs:
            print("[Warn] No jobs with reachable URLs after validation")
            self.generate_report([], profile, [], run_records=run_records)
            return []

        update_record_stage(run_records, recommended_record_ids, "recommended")

        # Step 6: 生成报告和投递包
        print("\n[Step 6] Generating report...")
        report_path = self.generate_report(
            report_jobs,
            profile,
            report_evaluations,
            run_records=run_records,
        )
        self.generate_application_package(report_jobs, profile, report_evaluations)

        # Step 7: 推送到飞书
        profile_export_name = profile.get('_profile_id') or profile_name
        feishu_config = self.config.get('feishu', {}) if self.config else {}
        if feishu_config.get('enabled'):
            print("\n[Step 7] Pushing to Feishu...")
            try:
                from .feishu_push import push_to_feishu
                feishu_result = push_to_feishu(report_path, profile_export_name)
                report_url = feishu_result.get('url') if feishu_result else None
            except ImportError:
                print("[Feishu] 模块未安装，跳过推送")
                report_url = None
        else:
            print("\n[Step 7] Feishu push disabled")
            report_url = None

        # Step 8: 添加到多维表格
        if feishu_config.get('enabled') and feishu_config.get('bitable_token') and feishu_config.get('bitable_table_id'):
            print("\n[Step 8] Adding to Bitable...")
            try:
                from .feishu_bitable import add_jobs_to_bitable
                # 为岗位添加评分信息
                for i, job in enumerate(report_jobs):
                    if i < len(report_evaluations):
                        job['score'] = report_evaluations[i].get('score', 0)
                    job['job_type'] = job_type or profile.get('job_type', '社招')
                add_jobs_to_bitable(report_jobs, profile_export_name, report_url)
            except ImportError:
                print("[Bitable] 模块未安装，跳过添加")
        else:
            print("\n[Step 8] Bitable push disabled")

        # Step 9: 更新去重数据库
        print("\n[Step 9] Updating seen jobs...")
        seen_jobs_path = self.memory_dir / "seen_jobs.md"
        filters.update_memory(jobs, evaluations, str(seen_jobs_path))
        # 更新 hash 集合
        for job in jobs:
            self.seen_hashes.add(job.get('hash', ''))

        return report_jobs

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
        if profile_name:
            profiles = [
                p for p in profiles
                if p.get('name') == profile_name or p.get('_profile_id') == profile_name
            ]

        if not profiles:
            print("[Warn] No profiles found")
            return

        print(f"\nFound {len(profiles)} profiles to process:")
        for p in profiles:
            profile_id = p.get('_profile_id') or p.get('name')
            print(f"  - {p.get('name')} [{profile_id}] ({p.get('job_type', 'All')})")

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
            profile_id = profile.get('_profile_id') or profile.get('name', 'Unnamed')
            profile_path = profile.get('_profile_path', '')
            print(f"  - {profile.get('name', 'Unnamed')} [{profile_id}] [{job_type}] {profile_path}")
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
