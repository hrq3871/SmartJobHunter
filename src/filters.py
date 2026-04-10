#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter 过滤模块
提供时间过滤、去重、数据清洗等功能
"""

import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional


def filter_by_time(jobs: List[dict], days: int = 3) -> List[dict]:
    """时间过滤：只保留最近N天的岗位

    Args:
        jobs: 岗位列表
        days: 天数阈值

    Returns:
        过滤后的岗位列表
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered = []

    for job in jobs:
        publish_time = job.get('publish_time', '')
        job_date = _parse_publish_time(publish_time)

        if job_date and job_date >= cutoff_date:
            job['_parsed_date'] = job_date
            filtered.append(job)
        elif not job_date:
            # 无法解析时间的岗位保留
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

    # 格式3: Unix时间戳（毫秒）
    try:
        if time_str.isdigit() and len(time_str) > 10:
            timestamp = int(time_str) / 1000
            return datetime.fromtimestamp(timestamp)
        elif time_str.isdigit():
            return datetime.fromtimestamp(int(time_str))
    except:
        pass

    return None


def dedup(jobs: List[dict], seen_hashes: set) -> List[dict]:
    """去重过滤：排除已处理的岗位

    Args:
        jobs: 岗位列表
        seen_hashes: 已处理的hash集合

    Returns:
        过滤后的岗位列表
    """
    return [job for job in jobs if job.get('hash', '') not in seen_hashes]


def load_seen_hashes(memory_path: str) -> set:
    """从 memory/seen_jobs.md 加载已处理的 hash

    Args:
        memory_path: memory 文件路径

    Returns:
        已处理的hash集合
    """
    seen = set()
    path = Path(memory_path)

    if not path.exists():
        return seen

    content = path.read_text(encoding='utf-8')

    # 解析 Markdown 表格中的 hash
    # 格式: | hash | ... |
    for line in content.split('\n'):
        if line.startswith('|') and 'hash' not in line.lower():
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2:
                # 第一个非空部分是 hash
                for part in parts[1:]:
                    if part and len(part) >= 8:
                        seen.add(part)
                        break

    return seen


def clean_data(jobs: List[dict], truncate_length: int = 6000) -> List[dict]:
    """清洗和压缩岗位数据

    Args:
        jobs: 岗位列表
        truncate_length: 文本截断长度

    Returns:
        清洗后的岗位列表
    """
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
            "product": job.get('product', ''),
            "bg": job.get('bg', ''),
            "work_years": job.get('work_years', ''),
            "hash": job.get('hash', ''),
            "source": job.get('source', ''),
            "job_type": job.get('job_type', '')
        }
        cleaned.append(cleaned_job)
    return cleaned


def _clean_text(text: str, max_length: int = 6000) -> str:
    """清洗文本

    Args:
        text: 原始文本
        max_length: 最大长度

    Returns:
        清洗后的文本
    """
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length] + "..."
    return text


def update_memory(jobs: List[dict], evaluations: List[dict], memory_path: str):
    """更新 Memory 文件

    Args:
        jobs: 岗位列表
        evaluations: 评估结果列表
        memory_path: memory 文件路径
    """
    path = Path(memory_path)

    # 如果文件不存在，创建头部
    if not path.exists():
        header = """# Seen Jobs Memory

> 自动记录已处理的岗位，用于去重

| hash | company | title | score | date |
|------|---------|-------|-------|------|
"""
        path.write_text(header, encoding='utf-8')

    # 追加新记录
    existing_content = path.read_text(encoding='utf-8')

    with open(path, 'a', encoding='utf-8') as f:
        for i, job in enumerate(jobs):
            score = evaluations[i].get('score', 0) if i < len(evaluations) else 0
            hash_val = job.get('hash', '')[:8]
            company = job.get('company', '')[:10]
            title = job.get('title', '')[:20]
            date = datetime.now().strftime('%Y-%m-%d')

            # 检查是否已存在
            if hash_val in existing_content:
                continue

            f.write(f"| {hash_val} | {company} | {title} | {score} | {date} |\n")


def load_seen_hashes_jsonl(jsonl_path: str) -> set:
    """从 JSONL 文件加载已处理的 hash（兼容旧格式）

    Args:
        jsonl_path: JSONL 文件路径

    Returns:
        已处理的hash集合
    """
    seen = set()
    path = Path(jsonl_path)

    if not path.exists():
        return seen

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                try:
                    record = json.loads(line)
                    seen.add(record.get('hash', ''))
                except json.JSONDecodeError:
                    continue

    return seen


def save_seen_job_jsonl(job: dict, profile_name: str, score: int, jsonl_path: str):
    """保存已处理的岗位记录到 JSONL 文件

    Args:
        job: 岗位数据
        profile_name: 意向名称
        score: 评分
        jsonl_path: JSONL 文件路径
    """
    record = {
        "hash": job.get('hash', ''),
        "url": job.get('url', ''),
        "title": job.get('title', ''),
        "company": job.get('company', ''),
        "processed_at": datetime.now().isoformat(),
        "profile": profile_name,
        "score": score
    }

    path = Path(jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
