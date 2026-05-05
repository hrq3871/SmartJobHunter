<div align="center">

# 🎯 SmartJobHunter

**🤖 LLM-Agent Driven Automated Job Hunting System**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

<p>
  <a href="README_CN.md"><b>🇨🇳 中文</b></a>
</p>

</div>

---

## Why This Project

SmartJobHunter is an intelligent job-hunting tool for **company career-site monitoring**.
Most job tools focus on platforms like Boss, LinkedIn, or other job boards.
Those platforms are useful, but browsing them is not the hardest part, and their own recommendation systems are already mature.

The opportunities people miss are often the first-party roles that only appear on company career sites.
For large companies, the official career site is often the earliest publishing channel.
Some roles never flow into external job boards at all.

Checking 10 company sites by hand every day is still barely manageable.
Checking 100 company sites consistently is not.
This is where AI is useful: turning manual monitoring into automated coverage.

This project uses AI to automate that workflow, and upgrades the process from "finding jobs by keyword" to "judging whether a role fits you and helping you apply better." The goal is to reduce both missed opportunities and false positives.

## What This Solves

Job hunting is hard not only because you need to search for roles, but because you need to keep the whole filtering process reliable:

- **Official career sites are fragmented**: each company has a different page structure, search behavior, and field quality.
- **Surface relevance is not real fit**: a title or keyword match does not mean the role fits your target direction or experience.
- **Multiple job directions make screening harder**: when you track campus roles, internships, AI product, TOB product, and other directions at the same time, information volume and filtering complexity grow quickly.
- **Recommendations need evidence**: a useful shortlist should explain why a role matches, where the risks are, and what gaps remain.
- **Applications take more work after discovery**: resume tailoring, ATS fit, JD-based writing, and interview preparation often take more effort than finding the opening.

## What Makes It Different

### 1. Focuses on official career sites, not duplicated platform data

The goal is to cover **career-site-first, career-site-only, and not-yet-synced** openings, reducing the chance of missing first-party opportunities.

### 2. Finds roles, then filters for real fit

SmartJobHunter does not simply crawl everything and push a long list to the user.
It combines resume content, job intention, and preferences to reduce roles that look relevant but are not actually suitable.

### 3. Gives resume and application advice, not just job links

The system can analyze:

- where the JD and resume match
- what strong signals already exist in the candidate's experience
- what risks and gaps remain
- how the resume can be improved for the role

## Current Capabilities

- Monitor roles across multiple company career sites
- Filter duplicate and low-relevance openings
- Score job fit based on resume evidence
- Output match reasons, supporting evidence, and risk warnings
- Generate structured job reports for faster application decisions

## Planned Capabilities

- **Personal experience library and JD-based resume generation**
  Maintain a local wiki-style experience library, then generate an HTML resume version from a target JD plus selected personal experiences. This is planned to integrate with an existing open-source GitHub resume project instead of rebuilding the rendering layer from scratch.

- **JD-specific interview preparation**
  Generate an interview assistance document for each target role, including high-frequency questions, suggested answers, and evidence-backed talking points focused on that JD rather than generic interview questions.

- **Feishu conversation and daily reminders**
  Mount a Feishu chat/dialog entry so the system can send daily reminders after job crawling, including newly found roles, high-score recommendations, and roles that need manual review.

- **Frontend management console**
  Provide a visual interface for configurable and interactive workflows: maintaining resumes, maintaining target companies, tracking application status, and recording which resume or generated file was used for each job.

- **Post-interview review and strategy improvement**
  Support interview retrospectives from uploaded recordings or transcripts, compare actual questions against predicted questions, calculate hit rate, summarize gaps, and improve future JD-specific prediction strategy.

- **From opportunity discovery to application assistance**
  Move from a job monitoring tool to a full job-search assistant agent covering discovery, matching, tailored materials, reminders, interview preparation, and post-interview learning.

## One-Line Summary

**SmartJobHunter is not just a job crawler. It is an intelligent job-search agent that monitors company career sites, finds real fit, and helps improve resumes and application materials.**

## ✨ Features

| Feature | Description |
|:---:|:---|
| 🤖 **Agent-Driven** | LLM-powered intelligent job matching and evaluation |
| 🎯 **Multi-Profile** | Support multiple job directions with independent resume inspection |
| 📄 **Multi-Format Resume** | Support txt, md, docx, pdf, png, jpg formats |
| 🔍 **Smart Filtering** | Three-layer funnel: Time → Dedup → semantic intent match |
| 📊 **AI Evaluation** | Rule-guided scoring (0-100) + evidence-based match reasons |
| 📊 **Job Classification** | Distinguish internship/campus/social recruitment |
| ⏰ **Scheduled Execution** | Daily automatic inspection at 20:00 |
| 🔧 **Self-Healing** | Automatic crawler health monitoring and repair |
| 🏢 **56 Companies** | 42 enabled crawlers with verified API patterns |
| ⚙️ **Config-Driven** | Add new companies without writing code |

## 🚀 Quick Start

### 1️⃣ Install Dependencies

```bash
pip install playwright pyyaml
playwright install chromium

# Optional: Support docx/pdf resumes
pip install python-docx PyMuPDF
```

### 2️⃣ Configure Profile

Create a profile in `profiles/` directory:

```bash
# Create profile with YAML frontmatter
cat > profiles/my_profile.md << 'EOF'
---
name: Product Manager
enabled: true
job_type: 社招
resume: resumes/my_resume.md
keywords:
  - Product Manager
  - TOB
  - AI Product
---

# Job Intention

Looking for TOB SaaS Product Manager positions...
EOF
```

### 3️⃣ Run Inspection

```bash
# Run all enabled profiles
python -m src.cli

# Specify job type
python -m src.cli -t social      # Social recruitment
python -m src.cli -t internship  # Internship
python -m src.cli -t campus      # Campus recruitment

# Specify profile
python -m src.cli -p "Product Manager"

# List all profiles
python -m src.cli --list-profiles
```

### 4️⃣ View Report

```bash
ls output/
# 20260410_Product_Manager.md
```

## 📁 Directory Structure

```
SmartJobHunter/
├── 📂 src/                  # Python modules
│   ├── cli.py               # CLI entry point & JobHunter class
│   ├── crawler.py           # Legacy crawlers (Tencent, ByteDance, etc.)
│   ├── crawler_factory.py   # Crawler factory with self-healing
│   ├── config_crawler.py    # Config-driven crawler
│   ├── base_crawler.py      # Base crawler class (API intercept)
│   ├── health_monitor.py    # Health monitoring & diagnosis
│   ├── auto_analyzer.py     # New company auto-analysis
│   ├── notifier.py          # User notification system
│   ├── filters.py           # Filter functions (time, dedup, clean)
│   ├── matching.py          # Semantic matching fallback and scoring rubric
│   ├── resume_parser.py     # Resume parser (txt/md/docx/pdf/image)
│   ├── scheduler.py         # Job scheduler (daily at 20:00)
│   ├── health_check.py      # Health checker
│   └── git_auto_push.py     # Git auto push
│
├── 📂 config/               # Configuration
│   ├── agent.yaml           # Agent settings
│   ├── companies.yaml       # Company list (56 companies)
│   └── system_templates.yaml # Recruiting system templates
│
├── 📂 profiles/             # Job profiles (Markdown + YAML frontmatter)
├── 📂 resumes/              # Resume files
├── 📂 memory/               # Dedup data (seen_jobs.md)
├── 📂 output/               # Generated reports
├── 📂 logs/                 # Log files
├── 📂 tests/                # Test files
│
├── 📂 .claude/skills/       # Claude Code Agent Skills
│   └── jobhunter/           # JobHunter Agent
│
└── 📄 公司列表.md           # Company list documentation (Chinese)
```

## ⚙️ Configuration

### 📋 Profile Format (profiles/*.md)

```markdown
---
name: Product Manager
enabled: true
job_type: 社招
resume: resumes/pm.md
keywords:
  - Product Manager
  - TOB
  - AI Product
---

# Job Intention

Looking for TOB SaaS Product Manager positions...
```

### 🤖 Agent Configuration (config/agent.yaml)

```yaml
decision_level: "moderate"  # conservative / moderate / aggressive
time_filter_days: 3         # Only show jobs from last N days
threshold_score: 70         # Minimum score to include in report
jd_truncate_length: 6000    # Max job description length

model_strategy:
  simple_tasks: "haiku"
  complex_tasks: "sonnet"

semantic_filter:
  conservative: 0.8
  moderate: 0.6
  aggressive: 0.4

output:
  max_jobs_per_report: 20  # Keep only the top N scored jobs in the report
```

### 🏢 Company Configuration (config/companies.yaml)

```yaml
companies:
  - id: tencent
    name: Tencent
    enabled: true
    urls:
      social: "https://careers.tencent.com/search.html?query={keyword}"
      campus: "https://careers.tencent.com/search.html?query={keyword}"
    api:
      pattern: "tencentcareer/api/post/Query"
      data_path: "Data.Posts"
      type: "intercept"
    field_mappings:
      id: {source: "PostId"}
      title: {source: "RecruitPostName"}
      location: {source: "LocationName"}
      category: {source: "CategoryName"}
      publish_time: {source: "LastUpdateTime"}
      duty: {source: "Responsibility"}
    url_template: "https://careers.tencent.com/position_detail.html?id={id}"
    job_type_detection:
      internship: ["实习", "intern"]
      campus: ["校招", "应届"]
```

## 🧠 Matching & Scoring Logic

SmartJobHunter no longer treats keyword hits as a match by themselves.

The matching flow is:

1. **Deterministic filters**: time window and deduplication stay in Python.
2. **Semantic intent filter**: the Agent judges whether the job's real responsibilities match the profile intent. Keywords are only supporting evidence.
3. **Resume-job fit scoring**: the Agent scores role fit, domain fit, resume evidence, preferences, evidence quality, and risk penalties.
4. **Report ranking**: jobs are sorted by final score, filtered by `threshold_score`, and capped by `output.max_jobs_per_report`.
5. **Python fallback**: `src.matching` mirrors the same rubric for CLI runs and tests when no Agent is executing the prompts.

Scoring dimensions:

| Dimension | Weight | Meaning |
|:--|:--:|:--|
| `core_role_fit` | 30 | Whether the job's core role matches the target role |
| `domain_fit` | 25 | Whether the domain matches the intent, such as AI Agent, LLM apps, ToB SaaS |
| `resume_evidence` | 25 | Whether the resume contains evidence for the JD requirements |
| `preference_fit` | 10 | Location, job type, and other stated preferences |
| `evidence_quality` | 10 | How clear and verifiable the JD/resume evidence is |
| `risk_penalty` | -20 | Keyword noise, role mismatch, or missing core evidence |

The Agent prompts live in `.claude/skills/jobhunter/prompts/` and require evidence-backed JSON output. For example, an "AI labeling operations" role should not be scored as a strong AI product match just because it contains "AI".

## 💻 Command Reference

### CLI Commands

| Command | Description |
|:--------|:------------|
| `python -m src.cli` | Run all enabled profiles |
| `python -m src.cli -t social` | Run social recruitment only |
| `python -m src.cli -t internship` | Run internship only |
| `python -m src.cli -t campus` | Run campus recruitment only |
| `python -m src.cli -p "name"` | Run specific profile |
| `python -m src.cli --list-profiles` | List all profiles |

## ✅ Testing

```bash
# Unit and non-network tests
pytest -q -p no:cacheprovider -m "not integration"

# Matching/scoring tests only
pytest -q -p no:cacheprovider tests/test_matching.py
```

Integration crawler tests require browser/network access and are marked with `integration`.

### Crawler Commands

| Command | Description |
|:--------|:------------|
| `python -m src.crawler_factory --list` | List all companies |
| `python -m src.crawler_factory --test <id>` | Test specific crawler |
| `python -m src.crawler_factory --crawl <id>` | Crawl specific company |

### Scheduler Commands

| Command | Description |
|:--------|:------------|
| `python -m src.scheduler --run` | Run inspection immediately |
| `python -m src.scheduler --check` | Run health check |
| `python -m src.scheduler --repair` | Trigger repair flow |
| `python -m src.scheduler --schedule` | Scheduled mode (called by system) |

### Health Monitor Commands

| Command | Description |
|:--------|:------------|
| `python -m src.health_monitor --check <id>` | Check single crawler |
| `python -m src.health_monitor --check-all` | Check all crawlers |
| `python -m src.health_monitor --report` | Generate health report |

## 🏢 Supported Companies

### ✅ Enabled & Working (42 companies)

**Tier 1 - BAT + TMD:**
| Company | Social | Campus | System |
|:--------|:------:|:------:|:-------|
| Tencent | ✅ | ✅ | Self-built |
| ByteDance | ✅ | ✅ | Feishu |
| ByteDance(社招) | ✅ | - | Feishu |
| Alibaba | ✅ | ✅ | Self-built |
| Meituan | ✅ | ✅ | Self-built |
| Baidu | ✅ | ✅ | Self-built |
| Didi | ✅ | ✅ | Self-built |
| JD.com | ✅ | ✅ | Self-built |
| Pinduoduo | ✅ | ✅ | Self-built |
| Huawei | ✅ | ✅ | Self-built |
| Xiaomi | ✅ | ✅ | Self-built |

**Tier 2 - Internet Companies:**
| Company | Social | Campus | System |
|:--------|:------:|:------:|:-------|
| NetEase | ✅ | ✅ | Self-built |
| Kuaishou | ✅ | ✅ | Self-built |
| Bilibili | ✅ | ✅ | Self-built |
| Xiaohongshu | ✅ | ✅ | Self-built |
| Ctrip | ✅ | ✅ | Self-built |
| Weibo | ✅ | ✅ | Self-built |
| Zhihu | ✅ | ✅ | Mokahr |
| OPPO | ✅ | ✅ | Self-built |
| vivo | ✅ | ✅ | Self-built |
| ZTE | ✅ | ✅ | Mokahr |
| Lenovo | ✅ | ✅ | Workday |

**Game Companies:**
| Company | Social | Campus | System |
|:--------|:------:|:------:|:-------|
| Mihoyo | ✅ | ✅ | Self-built |
| Lilith | ✅ | ✅ | Feishu |
| 37Games | ✅ | ✅ | Self-built |

**Feishu System:**
| Company | Social | Campus |
|:--------|:------:|:------:|
| SenseTime | ✅ | - |
| Keep | ✅ | - |
| SHEIN | ✅ | - |
| NIO | ✅ | - |
| Li Auto | ✅ | - |
| XPeng | ✅ | - |

**Others:**
| Company | Social | Campus | System |
|:--------|:------:|:------:|:-------|
| Apple China | ✅ | - | Self-built |
| Geely | ✅ | ✅ | Mokahr |
| GWM | ✅ | ✅ | Self-built |
| DJI | ✅ | ✅ | Self-built |
| Hikvision | ✅ | ✅ | Self-built |
| iFlytek | ✅ | ✅ | Self-built |
| Sangfor | ✅ | ✅ | Self-built |
| ICBC | ✅ | ✅ | Bank System |

### 🔧 Pending Development (14 companies)

| Company | Recruiting System | Note |
|:--------|:------------------|:-----|
| Microsoft China | Phenom | Need API analysis |
| NVIDIA China | Workday + Eightfold | Need DOM parsing |
| Tesla China | Mokahr | URL verified |
| Intel China | Workday | Need DOM parsing |
| AMD China | Workday | Need DOM parsing |
| Cisco China | Workday | Need DOM parsing |
| SAP China | Workday | Need DOM parsing |
| Inspur | Beisen | Need DOM parsing |
| CCB | Bank System | Need API analysis |
| CMCC | SOE System | Need API analysis |
| China Telecom | SOE System | Need API analysis |
| BYD | Self-built | Need API analysis |
| Ant Group | Alibaba-like | Need verification |
| Cainiao | Alibaba-like | Need verification |

> **📊 Total: 56 companies configured (42 enabled, 14 pending)**

### 🔧 Adding New Companies

The config-driven architecture makes it easy to add new companies:

1. Edit `config/companies.yaml`
2. Add `field_mappings` section
3. No code changes needed!

Example:

```yaml
- id: new_company
  name: New Company
  enabled: true
  urls:
    social: "https://jobs.example.com/search?keyword={keyword}"
  api:
    pattern: "api/job/list"
    data_path: "data.jobs"
    type: "intercept"
  field_mappings:
    id: {source: "jobId"}
    title: {source: "title"}
    location: {source: "city"}
    category: {source: "category"}
    publish_time: {source: "publishDate"}
    duty: {source: "description"}
  url_template: "https://jobs.example.com/detail/{id}"
  job_type_detection:
    internship: ["实习", "intern"]
    campus: ["校招", "应届"]
```

## 🔧 Self-Healing System

SmartJobHunter includes an automatic self-healing system:

### Architecture

```
Crawl Request → Crawler Factory → Health Monitor
                      ↓                  ↓
                Auto Analyzer ← Diagnosis
                      ↓                  ↓
                Config Update ← Repair Action
                      ↓
                Notifier → User
```

### Components

| Module | Purpose |
|:-------|:--------|
| `health_monitor.py` | Detect crawler health, diagnose failures |
| `auto_analyzer.py` | Analyze new companies, identify recruiting systems |
| `notifier.py` | Notify user of repair results |
| `crawler_factory.py` | Integrate self-healing logic |

### Failure Types

| Type | Auto-Repair | Action |
|:-----|:-----------:|:-------|
| Network Error | ❌ | Retry later |
| API Changed | ✅ | Re-analyze API |
| URL Invalid | ✅ | Search new URL |
| Login Required | ❌ | Notify user |
| Anti-Crawl | ❌ | Adjust frequency |
| Config Error | ❌ | Notify user |

### Recruiting System Templates

Located in `config/system_templates.yaml`:

| System | API Pattern | Data Path | Companies |
|:-------|:------------|:----------|:----------|
| Mokahr | `jobs` | `data.jobs` | Zhihu, ZTE, Geely, Tesla |
| Feishu | `search/job/posts` | `data.job_post_list` | ByteDance, Lilith, SenseTime, NIO |
| Workday | DOM parsing | - | Intel, AMD, Cisco, SAP, Lenovo |
| Beisen | DOM parsing | - | Inspur |
| Phenom | API intercept | - | Microsoft |
| Self-built | Varies | Varies | Tencent, Alibaba, Meituan, etc. |

## 🔄 Workflow

### Inspection Flow

```
1. Load Config     → Read profiles, companies, resumes
2. Crawl Jobs      → API intercept via Playwright
3. Filter          → Time → Dedup → Semantic intent
4. Evaluate        → Score (0-100) + evidence-backed match reasons
5. Generate Report → Sort by score, apply threshold_score, write Markdown
6. Update Memory   → Append to seen_jobs.md
```

### Filter Pipeline

```
Raw Jobs (from crawlers)
    ↓
[Time Filter] Keep jobs from last N days (default: 3)
    ↓
[Dedup Filter] Remove seen jobs (hash-based)
    ↓
[Data Clean] Truncate, normalize text
    ↓
[Semantic Intent Filter] Judge real role fit; keywords are supporting evidence only
    ↓
[Resume Fit Scoring] Score, sort, threshold, cap report size
```

## 🤖 Agent Architecture

SmartJobHunter uses an LLM-Agent architecture:

```
User Request → Agent (Claude) → Tools (Python) → Output
                    ↓
              ┌─────────┐
              │  State  │
              │ Machine │
              └─────────┘
                    ↓
    INIT → LOADED → CRAWLED → FILTERED → EVALUATED → REPORTED → DONE
```

### Agent Skills

Located in `.claude/skills/jobhunter/`:

- `skill.md` - Main agent entry point
- `tools/*.md` - Tool definitions (crawl, filter, load_config)
- `prompts/*.md` - Agent prompts (evaluate, report)

## 📄 Output Example

```markdown
# Job Hunting Report

## Basic Info
- **Profile**: Product Manager
- **Job Type**: 社招
- **Generated**: 2026-04-18 20:00
- **Jobs Found**: 15

## Intent
Looking for TOB SaaS Product Manager positions...

---

## Recommended Jobs

### 1. AI Product Manager 🟢 85 points

| Field | Value |
|:------|:------|
| Company | Tencent |
| Location | Beijing |
| Category | Product |
| Published | 2026-04-17 |

**Match Reasons**: Product Manager, AI Product, TOB

**Duties**:
负责AI产品的规划和设计...

**Link**: [View Job](https://careers.tencent.com/position_detail.html?id=xxx)

---
```

## 📜 License

**MIT License** © 2026 SmartJobHunter

**⭐ If this project helps you, please give it a star! ⭐**

Made with ❤️ by SmartJobHunter Team
