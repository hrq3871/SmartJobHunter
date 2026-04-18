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

## ✨ Features

| Feature | Description |
|:---:|:---|
| 🤖 **Agent-Driven** | LLM-powered intelligent job matching and evaluation |
| 🎯 **Multi-Profile** | Support multiple job directions with independent resume inspection |
| 📄 **Multi-Format Resume** | Support txt, md, docx, pdf, png, jpg formats |
| 🔍 **Smart Filtering** | Three-layer funnel: Time → Dedup+Keywords → Job Type |
| 📊 **AI Evaluation** | Auto scoring (0-100) + Match reasons |
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
3. Filter          → Time → Dedup → Keywords
4. Evaluate        → Score (0-100) + Match reasons
5. Generate Report → Markdown file in output/
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
[Keyword Filter] Match title/duty keywords
    ↓
[Data Clean] Truncate, normalize text
    ↓
Filtered Jobs
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
