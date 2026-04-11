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
| ⏰ **Scheduled Execution** | Daily automatic inspection |
| 🔧 **Self-Repair** | Automatic crawler anomaly detection |

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
│   ├── cli.py               # CLI entry point
│   ├── crawler.py           # Crawler module
│   ├── filters.py           # Filter functions
│   ├── resume_parser.py     # Resume parser
│   ├── scheduler.py         # Job scheduler
│   ├── health_check.py      # Health checker
│   └── git_auto_push.py     # Git auto push
│
├── 📂 config/               # Configuration
│   ├── agent.yaml           # Agent settings
│   └── companies.yaml       # Company list
│
├── 📂 profiles/             # Job profiles (Markdown + YAML frontmatter)
│   ├── pm_tob.md
│   └── AI产品经理.md
│
├── 📂 memory/               # Dedup data (Markdown)
│   └── seen_jobs.md
│
├── 📂 resumes/              # Resume files
├── 📂 output/               # Generated reports
│
├── 📂 .claude/skills/       # Claude Code Agent Skills
│   └── jobhunter/           # JobHunter Agent
│       ├── skill.md         # Main entry
│       ├── tools/           # Tool definitions
│       └── prompts/         # AI prompts
│
└── 📄 companies.md          # User-editable company list
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
```

## 💻 Command Reference

| Command | Description |
|:--------|:------------|
| `python -m src.cli` | Run all enabled profiles |
| `python -m src.cli -t social` | Run social recruitment only |
| `python -m src.cli -p "name"` | Run specific profile |
| `python -m src.cli --list-profiles` | List all profiles |

## 🏢 Supported Companies

### 🥇 Tier 1 (10 companies)

| Company | Social | Campus/Intern | Notes |
|:--------|:------:|:-------------:|:------|
| Tencent | ✅ | ✅ | Config-driven |
| ByteDance | ✅ | ✅ | Config-driven |
| Meituan | ✅ | ✅ | Config-driven |
| NetEase | ✅ | ✅ | Config-driven |
| Alibaba | 🚧 | 🚧 | SSR, needs special handling |
| Baidu | 🚧 | 🚧 | Needs analysis |
| Didi | 🚧 | 🚧 | Needs analysis |
| JD.com | 🚧 | 🚧 | Needs analysis |
| Pinduoduo | 🚧 | 🚧 | Needs analysis |
| Huawei | 🚧 | 🚧 | Needs analysis |

### 🥈 Tier 2 (15 companies)

| Company | Social | Campus/Intern |
|:--------|:------:|:-------------:|
| Kuaishou | ❌ | ❌ |
| Bilibili | ❌ | ❌ |
| Xiaohongshu | ❌ | ❌ |
| Ctrip | 🚧 | 🚧 |
| Weibo | ❌ | ❌ |
| Zhihu | 🚧 | 🚧 |
| Vipshop | 🚧 | 🚧 |
| 58.com | 🚧 | 🚧 |
| OPPO | 🚧 | 🚧 |
| vivo | ❌ | ❌ |
| ZTE | 🚧 | 🚧 |
| Lenovo | 🚧 | 🚧 |
| Ant Group | 🚧 | 🚧 |
| Cainiao | 🚧 | 🚧 |
| Xiaomi | 🚧 | 🚧 |

> **📊 Working: 4 companies** | **🚧 Pending: 18 companies** | **❌ Unavailable: 4 companies**

### 🔧 Adding New Companies

The new config-driven architecture makes it easy to add new companies:

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
  field_mappings:
    id: {source: "jobId"}
    title: {source: "title"}
    location: {source: "city"}
    # ... more fields
  url_template: "https://jobs.example.com/detail/{id}"
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
### 1. AI Product Manager 🟢 85 points

| Field | Content |
|:------|:--------|
| Company | Tencent |
| Location | Beijing |
| Match Reason | Product Manager, AI Product, TOB |

**Responsibilities**: ...
```

---

<div align="center">

## 📜 License

**MIT License** © 2026 SmartJobHunter

**⭐ If this project helps you, please give it a star! ⭐**

Made with ❤️ by SmartJobHunter Team

</div>
