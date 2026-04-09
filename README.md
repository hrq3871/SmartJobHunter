<div align="center">

# 🎯 SmartJobHunter

**🤖 Automated Job Hunting Inspection System based on Claude Code Agent**

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
| 🎯 **Multi-Profile** | Support multiple job directions with independent resume inspection |
| 📄 **Multi-Format Resume** | Support txt, md, docx, pdf formats |
| 🔍 **Smart Filtering** | Three-layer funnel: Time → Dedup+Keywords → Job Type |
| 🤖 **AI Evaluation** | Auto scoring (0-100) + Match reasons |
| 📊 **Job Classification** | Distinguish internship/campus/social recruitment |
| ⏰ **Scheduled Execution** | Daily automatic inspection |
| 🔧 **Self-Repair** | Automatic crawler anomaly detection |
| 📤 **Git Sync** | Auto push changes |

## 🚀 Quick Start

### 1️⃣ Install Dependencies

```bash
pip install playwright pyyaml
playwright install chromium

# Optional: Support docx/pdf resumes
pip install python-docx PyMuPDF
```

### 2️⃣ Configure Resume & Profile

```bash
# 📂 Put your resume
cp your_resume.txt resumes/

# ⚙️ Edit config
vim config.yaml
```

### 3️⃣ Run Inspection

```bash
# 🏃 Run all enabled profiles
python main.py

# 🏷️ Specify job type
python main.py -t social      # Social recruitment
python main.py -t internship  # Internship
python main.py -t campus      # Campus recruitment

# 🎯 Specify profile
python main.py -p "Product Manager"
```

### 4️⃣ View Report

```bash
ls output/
# 📄 20260410_Product_Manager.md
```

## 📁 Directory Structure

```
SmartJobHunter/
├── 📄 config.yaml          # Main config (job profiles)
├── 📄 companies.yaml       # Company list
├── 🐍 main.py              # Main program
├── 🕷️ spider.py            # Crawler module
├── ⏰ scheduler.py         # Scheduler
├── 📝 resume_parser.py     # Resume parser
├── 💊 health_check.py      # Health check
├── 📤 git_auto_push.py     # Git auto push
│
├── 📂 resumes/             # Resume directory
│   ├── example_resume.md
│   └── your_resume.txt
│
├── 📂 output/              # Output reports
├── 📂 data/                # Dedup data
└── 📂 logs/                # Logs
```

## ⚙️ Configuration

### 📋 config.yaml - Job Profile

```yaml
profiles:
  - name: "Product Manager"
    enabled: true
    intent: "Job intention description..."
    resume_path: "./resumes/pm.txt"
    job_type: "social"
    keywords:
      - "Product Manager"
      - "TOB"
      - "AI Product"
```

### 🏢 companies.yaml - Company List

```yaml
companies:
  - id: tencent
    name: Tencent
    enabled: true
    urls:
      social: "https://..."
      campus: "https://..."
```

## ⏰ Scheduled Tasks

```bash
# Windows - Run as Administrator
setup_schedule.bat

# Auto execute at 8 PM daily 🌙
```

## 💻 Command Reference

| Command | Description |
|:--------|:------------|
| `python main.py` | 🏃 Run all enabled profiles |
| `python main.py -t social` | 👔 Run social recruitment only |
| `python main.py -p "name"` | 🎯 Run specific profile |
| `python main.py --list-profiles` | 📋 List all profiles |
| `python spider.py --list` | 🏢 List companies |
| `python scheduler.py --check` | 💊 Health check |
| `python scheduler.py --run` | ▶️ Run immediately |

## 🏢 Supported Companies

### 🥇 Tier 1 (10 companies)

| Company | Social | Campus/Intern |
|:--------|:------:|:-------------:|
| Tencent | ✅ | ✅ |
| ByteDance | ✅ | ✅ |
| Alibaba | 🚧 | 🚧 |
| Baidu | 🚧 | 🚧 |
| Meituan | 🚧 | 🚧 |
| Didi | 🚧 | 🚧 |
| JD.com | 🚧 | 🚧 |
| Pinduoduo | 🚧 | 🚧 |
| Huawei | 🚧 | 🚧 |
| Xiaomi | 🚧 | 🚧 |

### 🥈 Tier 2 (15 companies)

| Company | Social | Campus/Intern |
|:--------|:------:|:-------------:|
| NetEase | 🚧 | 🚧 |
| Kuaishou | 🚧 | 🚧 |
| Bilibili | 🚧 | 🚧 |
| Xiaohongshu | 🚧 | 🚧 |
| Ctrip | 🚧 | 🚧 |
| Weibo | 🚧 | 🚧 |
| Zhihu | 🚧 | 🚧 |
| Vipshop | 🚧 | 🚧 |
| 58.com | 🚧 | 🚧 |
| OPPO | 🚧 | 🚧 |
| vivo | 🚧 | 🚧 |
| ZTE | 🚧 | 🚧 |
| Lenovo | 🚧 | 🚧 |
| Ant Group | 🚧 | 🚧 |
| Cainiao | 🚧 | 🚧 |

### 🎮 Gaming (5 companies)

| Company | Social | Campus/Intern |
|:--------|:------:|:-------------:|
| NetEase Games | 🚧 | 🚧 |
| miHoYo | 🚧 | 🚧 |
| Lilith Games | 🚧 | 🚧 |
| Perfect World | 🚧 | 🚧 |
| 37Games | 🚧 | 🚧 |

### 🌍 International Tech (8 companies)

| Company | Social |
|:--------|:------:|
| Microsoft China | 🚧 |
| Apple China | 🚧 |
| NVIDIA China | 🚧 |
| Tesla China | 🚧 |
| Intel China | 🚧 |
| AMD China | 🚧 |
| Cisco China | 🚧 |
| SAP China | 🚧 |

> **📊 Total: 38 companies** (✅ Implemented 🚧 Pending)

## ➕ Add New Company

1. 📝 Add config in `companies.yaml`
2. 🔒 Set `enabled: false`
3. 🕷️ Implement crawler in `spider.py`
4. ✅ Set `enabled: true` after testing

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
