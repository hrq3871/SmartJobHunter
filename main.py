#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SmartJobHunter Agent 主运行脚本
整合爬虫、过滤、评估、输出全流程
"""

import json
import yaml
import hashlib
import argparse
import sys
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# 设置环境变量解决编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 导入爬虫模块
from spider import crawl_company, get_enabled_companies, COMPANIES_CONFIG


class JobHunter:
    """求职巡检Agent主类"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.seen_jobs_path = Path("data/seen_jobs.jsonl")
        self.output_dir = Path("output")
        self.data_dir = Path("data")

        # 确保目录存在
        self.output_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # 加载已处理的岗位
        self.seen_hashes = self._load_seen_jobs()

    def _load_config(self) -> dict:
        """加载配置文件"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _load_seen_jobs(self) -> set:
        """加载已处理岗位的hash集合"""
        seen = set()
        if self.seen_jobs_path.exists():
            with open(self.seen_jobs_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            record = json.loads(line)
                            seen.add(record.get('hash', ''))
                        except json.JSONDecodeError:
                            continue
        return seen

    def _save_seen_job(self, job: dict, profile_name: str, score: int = 0):
        """保存已处理的岗位记录"""
        record = {
            "hash": job.get('hash', ''),
            "url": job.get('url', ''),
            "title": job.get('title', ''),
            "company": job.get('company', ''),
            "processed_at": datetime.now().isoformat(),
            "profile": profile_name,
            "score": score
        }
        with open(self.seen_jobs_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        self.seen_hashes.add(record['hash'])

    # ==================== 第一层过滤：时间 ====================

    def filter_by_time(self, jobs: List[dict], days: int = 3) -> List[dict]:
        """时间过滤：只保留最近N天的岗位"""
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered = []

        for job in jobs:
            publish_time = job.get('publish_time', '')
            job_date = self._parse_publish_time(publish_time)

            if job_date and job_date >= cutoff_date:
                job['_parsed_date'] = job_date
                filtered.append(job)
            elif not job_date:
                filtered.append(job)

        return filtered

    def _parse_publish_time(self, time_str) -> Optional[datetime]:
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

    # ==================== 第二层过滤：去重+关键词+岗位性质 ====================

    def filter_by_dedup(self, jobs: List[dict]) -> List[dict]:
        """去重过滤：排除已处理的岗位"""
        return [job for job in jobs if job.get('hash', '') not in self.seen_hashes]

    def filter_by_keywords(self, jobs: List[dict], keywords: List[str]) -> List[dict]:
        """关键词过滤：匹配标题或职责中的关键词"""
        if not keywords:
            return jobs

        filtered = []
        for job in jobs:
            title = job.get('title', '').lower()
            duty = job.get('duty', '').lower()
            category = job.get('category', '').lower()

            for keyword in keywords:
                keyword_lower = keyword.lower()
                if (keyword_lower in title or
                    keyword_lower in duty or
                    keyword_lower in category):
                    filtered.append(job)
                    break

        return filtered

    def filter_by_job_type(self, jobs: List[dict], job_type: str) -> List[dict]:
        """岗位性质过滤：区分实习/校招/社招"""
        if not job_type or job_type == "全部":
            return jobs

        job_types_config = self.config.get('job_types', {})
        type_config = job_types_config.get(job_type, {})

        if not type_config:
            return jobs

        include_keywords = [k.lower() for k in type_config.get('keywords', [])]
        exclude_keywords = [k.lower() for k in type_config.get('exclude', [])]

        filtered = []
        for job in jobs:
            # 首先检查job自带的job_type字段
            job_type_field = job.get('job_type', '').lower()
            type_name = type_config.get('name', '').lower()

            # 如果job_type字段匹配，直接通过
            if job_type_field and type_name in job_type_field:
                filtered.append(job)
                continue

            title = job.get('title', '').lower()
            duty = job.get('duty', '').lower()
            combined_text = title + ' ' + duty

            # 检查排除关键词
            should_exclude = False
            for kw in exclude_keywords:
                if kw in combined_text:
                    should_exclude = True
                    break

            if should_exclude:
                continue

            # 检查包含关键词
            if include_keywords:
                for kw in include_keywords:
                    if kw in combined_text:
                        filtered.append(job)
                        break
            else:
                filtered.append(job)

        return filtered

    # ==================== 第三层过滤：文本清洗 ====================

    def clean_job_data(self, jobs: List[dict], truncate_length: int = 6000) -> List[dict]:
        """清洗和压缩岗位数据"""
        cleaned = []
        for job in jobs:
            cleaned_job = {
                "title": self._clean_text(job.get('title', '')),
                "company": job.get('company', ''),
                "location": job.get('location', ''),
                "category": job.get('category', ''),
                "url": job.get('url', ''),
                "publish_time": job.get('publish_time', ''),
                "duty": self._clean_text(job.get('duty', ''), truncate_length),
                "requirement": self._clean_text(job.get('requirement', ''), truncate_length // 2),
                "product": job.get('product', ''),
                "bg": job.get('bg', ''),
                "work_years": job.get('work_years', ''),
                "hash": job.get('hash', ''),
                "source": job.get('source', '')
            }
            cleaned.append(cleaned_job)
        return cleaned

    def _clean_text(self, text: str, max_length: int = 6000) -> str:
        """清洗文本"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        if len(text) > max_length:
            text = text[:max_length] + "..."
        return text

    # ==================== 爬虫调度 ====================

    def crawl_jobs(self, keyword: str, max_jobs: int = 50, job_type: str = None) -> List[dict]:
        """调度爬虫抓取岗位 - 从配置文件读取公司列表"""
        all_jobs = []

        # 从配置获取启用的公司
        companies = get_enabled_companies(job_type)
        print(f"[爬虫] 找到 {len(companies)} 个支持 {job_type or '全部'} 的公司")

        for company in companies:
            company_id = company.get('id')
            company_name = company.get('name')

            print(f"[爬虫] 正在抓取 {company_name}...")
            try:
                jobs = crawl_company(company_id, keyword, max_jobs=max_jobs, job_type=job_type)
                all_jobs.extend(jobs)
                print(f"   获取 {len(jobs)} 个岗位")
            except Exception as e:
                print(f"   抓取失败: {e}")

        return all_jobs

    # ==================== AI 评估 ====================

    def evaluate_job(self, job: dict, profile: dict) -> dict:
        """AI评估岗位匹配度（使用内置能力）"""
        intent = profile.get('intent', '')
        title = job.get('title', '')
        company = job.get('company', '')
        duty = job.get('duty', '')[:2000]
        requirement = job.get('requirement', '')[:1000]

        # 构建评估prompt（这里返回结构化数据，实际评估由Agent完成）
        evaluation = {
            "score": 0,
            "match_reasons": [],
            "missing_skills": [],
            "risk_warning": "",
            "recommendation": ""
        }

        # 简单的关键词匹配评分（基础评估）
        keywords = profile.get('keywords', [])
        title_lower = title.lower()
        duty_lower = duty.lower()

        matched_keywords = []
        for kw in keywords:
            if kw.lower() in title_lower or kw.lower() in duty_lower:
                matched_keywords.append(kw)

        # 计算基础分数
        if matched_keywords:
            evaluation["score"] = min(60 + len(matched_keywords) * 5, 85)
            evaluation["match_reasons"] = [f"匹配关键词: {', '.join(matched_keywords)}"]

        # 检查是否包含AI相关
        ai_keywords = ['ai', '人工智能', '大模型', '机器学习', '深度学习', 'llm', 'gpt']
        for kw in ai_keywords:
            if kw in duty_lower:
                evaluation["match_reasons"].append("涉及AI/大模型方向")
                evaluation["score"] = min(evaluation["score"] + 10, 95)
                break

        # 检查TOB相关
        tob_keywords = ['tob', 'b端', '企业服务', 'saas', '企业级']
        for kw in tob_keywords:
            if kw in duty_lower:
                evaluation["match_reasons"].append("TOB/企业服务方向")
                evaluation["score"] = min(evaluation["score"] + 5, 95)
                break

        return evaluation

    # ==================== 公司背调 ====================

    def company_background_check(self, company: str) -> str:
        """公司背调（搜索近期新闻）"""
        # 这里返回基础信息，实际搜索由Agent完成
        known_companies = {
            "腾讯": "互联网大厂，总部深圳，主要业务：社交、游戏、云服务、金融科技",
            "字节跳动": "互联网大厂，总部北京，主要业务：抖音、TikTok、飞书、火山引擎",
            "阿里巴巴": "互联网大厂，总部杭州，主要业务：电商、云计算、金融科技",
            "美团": "互联网大厂，总部北京，主要业务：外卖、到店、酒旅",
            "百度": "互联网大厂，总部北京，主要业务：搜索、AI、自动驾驶",
        }
        return known_companies.get(company, f"{company}，建议自行了解公司背景")

    # ==================== 输出 ====================

    def generate_report(self, jobs: List[dict], profile: dict, output_path: Path, evaluations: List[dict] = None):
        """生成Markdown报告"""
        profile_name = profile.get('name', 'unknown')
        intent = profile.get('intent', '')
        job_type = profile.get('job_type', '全部')

        report = f"""# 求职巡检报告

## 基本信息
- **求职意向**: {profile_name}
- **岗位性质**: {job_type}
- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **岗位数量**: {len(jobs)}

## 意向描述
{intent}

---

## 推荐岗位列表

"""

        for i, job in enumerate(jobs, 1):
            evaluation = evaluations[i-1] if evaluations and i <= len(evaluations) else {}
            score = evaluation.get('score', 0)
            match_reasons = evaluation.get('match_reasons', [])
            missing_skills = evaluation.get('missing_skills', [])
            risk_warning = evaluation.get('risk_warning', '')

            # 评分颜色标记
            score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"

            report += f"""### {i}. {job.get('title', '未知岗位')} {score_emoji} {score}分

| 字段 | 内容 |
|------|------|
| 公司 | {job.get('company', '')} |
| 地点 | {job.get('location', '')} |
| 类别 | {job.get('category', '')} |
| 发布时间 | {job.get('publish_time', '')} |
| 工作年限 | {job.get('work_years', '')} |
| 产品/部门 | {job.get('product', '')} / {job.get('bg', '')} |

**匹配理由**: {', '.join(match_reasons) if match_reasons else '暂无'}

**缺失技能**: {', '.join(missing_skills) if missing_skills else '暂无'}

**岗位职责**:
{job.get('duty', '暂无')[:500]}...

**任职要求**:
{job.get('requirement', '暂无')[:300]}...

**链接**: [{job.get('url', '')}]({job.get('url', '')})

---

"""

        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"📄 报告已生成: {output_path}")

    # ==================== 主流程 ====================

    def run_profile(self, profile: dict, job_type_override: str = None) -> List[dict]:
        """运行单个求职意向的巡检"""
        profile_name = profile.get('name', 'unknown')
        keywords = profile.get('keywords', [])
        job_type = job_type_override or profile.get('job_type', '全部')

        print(f"\n{'='*50}")
        print(f"🎯 开始处理求职意向: {profile_name}")
        print(f"📋 岗位性质: {job_type}")
        print(f"{'='*50}")

        # 获取全局配置
        global_config = self.config.get('global', {})
        time_filter_days = global_config.get('time_filter_days', 3)
        threshold_score = global_config.get('threshold_score', 70)
        jd_truncate_length = global_config.get('jd_truncate_length', 6000)

        # Step 1: 抓取岗位
        print("\n[Step 1] 抓取岗位数据...")
        keyword = keywords[0] if keywords else "产品经理"
        jobs = self.crawl_jobs(keyword, max_jobs=50, job_type=job_type)

        if not jobs:
            print("⚠️ 未获取到任何岗位数据")
            return []

        print(f"   共获取 {len(jobs)} 个岗位")

        # Step 2: 第一层过滤 - 时间
        print(f"\n📍 Step 2: 时间过滤（最近 {time_filter_days} 天）...")
        jobs = self.filter_by_time(jobs, time_filter_days)
        print(f"   过滤后剩余 {len(jobs)} 个岗位")

        # Step 3: 第二层过滤 - 去重
        print("\n📍 Step 3: 去重过滤...")
        jobs = self.filter_by_dedup(jobs)
        print(f"   过滤后剩余 {len(jobs)} 个岗位")

        # Step 4: 第二层过滤 - 关键词
        print(f"\n📍 Step 4: 关键词过滤...")
        jobs = self.filter_by_keywords(jobs, keywords)
        print(f"   过滤后剩余 {len(jobs)} 个岗位")

        # Step 5: 第二层过滤 - 岗位性质
        print(f"\n📍 Step 5: 岗位性质过滤（{job_type}）...")
        jobs = self.filter_by_job_type(jobs, job_type)
        print(f"   过滤后剩余 {len(jobs)} 个岗位")

        # Step 6: 第三层过滤 - 清洗
        print("\n📍 Step 6: 数据清洗...")
        jobs = self.clean_job_data(jobs, jd_truncate_length)

        # Step 7: AI 评估
        print("\n📍 Step 7: AI 评估...")
        evaluations = []
        for job in jobs:
            eval_result = self.evaluate_job(job, profile)
            evaluations.append(eval_result)
            print(f"   [{job.get('company')}] {job.get('title')[:20]}... → {eval_result['score']}分")

        # Step 8: 生成报告
        print("\n📍 Step 8: 生成报告...")
        output_filename = f"{datetime.now().strftime('%Y%m%d')}_{profile_name}.md"
        output_path = self.output_dir / output_filename
        self.generate_report(jobs, profile, output_path, evaluations)

        # Step 9: 更新去重数据库
        print("\n📍 Step 9: 更新去重数据库...")
        for i, job in enumerate(jobs):
            score = evaluations[i]['score'] if i < len(evaluations) else 0
            self._save_seen_job(job, profile_name, score)

        return jobs

    def run(self, profile_name: Optional[str] = None, job_type: Optional[str] = None):
        """运行完整的求职巡检"""
        print("="*60)
        print("🚀 SmartJobHunter Agent 启动")
        print("="*60)

        profiles = self.config.get('profiles', [])

        if profile_name:
            profiles = [p for p in profiles if p.get('name') == profile_name]

        if not profiles:
            print("⚠️ 未找到匹配的求职意向配置")
            return

        all_jobs = []
        for profile in profiles:
            jobs = self.run_profile(profile, job_type)
            all_jobs.extend(jobs)

        print("\n" + "="*60)
        print(f"✅ 巡检完成！共处理 {len(all_jobs)} 个岗位")
        print("="*60)


def parse_command(command: str) -> dict:
    """解析用户指令"""
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
    parser = argparse.ArgumentParser(description='SmartJobHunter Agent')
    parser.add_argument('-c', '--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('-p', '--profile', help='指定求职意向名称')
    parser.add_argument('-t', '--job-type', choices=['internship', 'campus', 'social'], help='岗位性质')
    parser.add_argument('-k', '--keyword', help='搜索关键词')
    parser.add_argument('--list-profiles', action='store_true', help='列出所有求职意向')
    parser.add_argument('command', nargs='?', help='自然语言指令')

    args = parser.parse_args()

    hunter = JobHunter(args.config)

    if args.list_profiles:
        print("📋 已配置的求职意向:")
        for profile in hunter.config.get('profiles', []):
            job_type = profile.get('job_type', '全部')
            print(f"  - {profile.get('name', '未命名')} [{job_type}]")
        print("\n📋 可用的岗位性质:")
        for type_key, type_config in hunter.config.get('job_types', {}).items():
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
