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

    print(f"[OK] 迁移完成: {len(companies)} 个公司")


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

        print(f"[OK] 迁移意向: {name}")

    print(f"[OK] 迁移完成: {len(config.get('profiles', []))} 个意向")


if __name__ == "__main__":
    print("开始数据迁移...")
    migrate_seen_jobs()
    migrate_config_to_profiles()
    print("迁移完成！")
