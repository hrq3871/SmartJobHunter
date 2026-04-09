<div align="center">

# 🎯 SmartJobHunter

**🤖 基于 Claude Code Agent 的自动化求职巡检系统**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

**[English](#-english-documentation)** | **[中文文档](#-中文文档)**

</div>

---

## 📖 中文文档

<details open>
<summary><b>👉 点击切换语言 / Click to switch language</b></summary>

### ✨ 功能特性

| 功能 | 描述 |
|:---:|:---|
| 🎯 **多意向并行** | 支持多个求职方向，每份简历独立巡检 |
| 📄 **多格式简历** | 支持 txt、md、docx、pdf 格式 |
| 🔍 **智能过滤** | 三层漏斗：时间 → 去重+关键词 → 岗位性质 |
| 🤖 **AI 评估** | 自动评分（0-100分）+ 匹配理由 |
| 📊 **岗位分类** | 区分实习/校招/社招 |
| ⏰ **定时执行** | 每天自动巡检 |
| 🔧 **自我修复** | 爬虫异常自动检测 |
| 📤 **Git 同步** | 自动推送变更 |

### 🚀 快速开始

#### 1️⃣ 安装依赖

```bash
pip install playwright pyyaml
playwright install chromium

# 可选：支持 docx/pdf 简历
pip install python-docx PyMuPDF
```

#### 2️⃣ 配置简历和意向

```bash
# 📂 放入简历
cp your_resume.txt resumes/

# ⚙️ 编辑配置
vim config.yaml
```

#### 3️⃣ 运行巡检

```bash
# 🏃 运行所有启用的意向
python main.py

# 🏷️ 指定岗位类型
python main.py -t social      # 社招
python main.py -t internship  # 实习
python main.py -t campus      # 校招

# 🎯 指定意向
python main.py -p "产品经理-TOB方向"
```

#### 4️⃣ 查看报告

```bash
ls output/
# 📄 20260410_产品经理-TOB方向.md
```

### 📁 目录结构

```
SmartJobHunter/
├── 📄 config.yaml          # 主配置（求职意向）
├── 📄 companies.yaml       # 公司列表
├── 🐍 main.py              # 主程序
├── 🕷️ spider.py            # 爬虫模块
├── ⏰ scheduler.py         # 调度器
├── 📝 resume_parser.py     # 简历解析
├── 💊 health_check.py      # 健康检测
├── 📤 git_auto_push.py     # Git自动推送
│
├── 📂 resumes/             # 简历目录
│   ├── example_resume.md
│   └── your_resume.txt
│
├── 📂 output/              # 输出报告
├── 📂 data/                # 去重数据
└── 📂 logs/                # 日志
```

### ⚙️ 配置说明

#### 📋 config.yaml - 求职意向

```yaml
profiles:
  - name: "产品经理-TOB方向"
    enabled: true
    intent: "求职意向描述..."
    resume_path: "./resumes/pm_tob.txt"
    job_type: "社招"
    keywords:
      - "产品经理"
      - "TOB"
      - "AI产品"
```

#### 🏢 companies.yaml - 公司列表

```yaml
companies:
  - id: tencent
    name: 腾讯
    enabled: true
    urls:
      social: "https://..."
      campus: "https://..."
```

### ⏰ 定时任务

```bash
# Windows - 管理员运行
setup_schedule.bat

# 每天晚上8点自动执行 🌙
```

### 💻 命令参考

| 命令 | 说明 |
|:-----|:-----|
| `python main.py` | 🏃 运行所有启用的意向 |
| `python main.py -t social` | 👔 只运行社招 |
| `python main.py -p "意向名"` | 🎯 运行指定意向 |
| `python main.py --list-profiles` | 📋 列出所有意向 |
| `python spider.py --list` | 🏢 列出公司 |
| `python scheduler.py --check` | 💊 健康检测 |
| `python scheduler.py --run` | ▶️ 立即巡检 |

### 🏢 支持的公司

<details>
<summary><b>🥇 第一梯队 (10家)</b></summary>

| 公司 | 社招 | 校招/实习 |
|:-----|:----:|:---------:|
| 腾讯 | ✅ | ✅ |
| 字节跳动 | ✅ | ✅ |
| 阿里巴巴 | 🚧 | 🚧 |
| 百度 | 🚧 | 🚧 |
| 美团 | 🚧 | 🚧 |
| 滴滴出行 | 🚧 | 🚧 |
| 京东 | 🚧 | 🚧 |
| 拼多多 | 🚧 | 🚧 |
| 华为 | 🚧 | 🚧 |
| 小米 | 🚧 | 🚧 |

</details>

<details>
<summary><b>🥈 第二梯队 (15家)</b></summary>

| 公司 | 社招 | 校招/实习 |
|:-----|:----:|:---------:|
| 网易 | 🚧 | 🚧 |
| 快手 | 🚧 | 🚧 |
| 哔哩哔哩 | 🚧 | 🚧 |
| 小红书 | 🚧 | 🚧 |
| 携程 | 🚧 | 🚧 |
| 微博 | 🚧 | 🚧 |
| 知乎 | 🚧 | 🚧 |
| 唯品会 | 🚧 | 🚧 |
| 58同城 | 🚧 | 🚧 |
| OPPO | 🚧 | 🚧 |
| vivo | 🚧 | 🚧 |
| 中兴通讯 | 🚧 | 🚧 |
| 联想 | 🚧 | 🚧 |
| 蚂蚁集团 | 🚧 | 🚧 |
| 菜鸟网络 | 🚧 | 🚧 |

</details>

<details>
<summary><b>🎮 游戏公司 (5家)</b></summary>

| 公司 | 社招 | 校招/实习 |
|:-----|:----:|:---------:|
| 网易游戏 | 🚧 | 🚧 |
| 米哈游 | 🚧 | 🚧 |
| 莉莉丝游戏 | 🚧 | 🚧 |
| 完美世界 | 🚧 | 🚧 |
| 三七互娱 | 🚧 | 🚧 |

</details>

<details>
<summary><b>🌍 外资科技 (8家)</b></summary>

| 公司 | 社招 |
|:-----|:----:|
| 微软中国 | 🚧 |
| 苹果中国 | 🚧 |
| 英伟达中国 | 🚧 |
| 特斯拉中国 | 🚧 |
| 英特尔中国 | 🚧 |
| AMD中国 | 🚧 |
| 思科中国 | 🚧 |
| SAP中国 | 🚧 |

</details>

> **📊 总计: 38家公司** (✅ 已实现 🚧 待开发)

### ➕ 添加新公司

1. 📝 在 `companies.yaml` 添加配置
2. 🔒 设置 `enabled: false`
3. 🕷️ 在 `spider.py` 实现爬虫
4. ✅ 测试通过后设置 `enabled: true`

### 📄 输出示例

```markdown
### 1. AI产品经理 🟢 85分

| 字段 | 内容 |
|:-----|:-----|
| 公司 | 腾讯 |
| 地点 | 北京 |
| 匹配理由 | 产品经理, AI产品, TOB |

**岗位职责**: ...
```

</details>

---

## 📖 English Documentation

<details>
<summary><b>👉 Click to switch language / 点击切换语言</b></summary>

### ✨ Features

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

### 🚀 Quick Start

#### 1️⃣ Install Dependencies

```bash
pip install playwright pyyaml
playwright install chromium

# Optional: Support docx/pdf resumes
pip install python-docx PyMuPDF
```

#### 2️⃣ Configure Resume & Profile

```bash
# 📂 Put your resume
cp your_resume.txt resumes/

# ⚙️ Edit config
vim config.yaml
```

#### 3️⃣ Run Inspection

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

#### 4️⃣ View Report

```bash
ls output/
# 📄 20260410_Product_Manager.md
```

### 📁 Directory Structure

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
├── 📂 output/              # Output reports
├── 📂 data/                # Dedup data
└── 📂 logs/                # Logs
```

### ⚙️ Configuration

#### 📋 config.yaml - Job Profile

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

### 💻 Command Reference

| Command | Description |
|:--------|:------------|
| `python main.py` | 🏃 Run all enabled profiles |
| `python main.py -t social` | 👔 Run social recruitment only |
| `python main.py -p "name"` | 🎯 Run specific profile |
| `python main.py --list-profiles` | 📋 List all profiles |
| `python spider.py --list` | 🏢 List companies |
| `python scheduler.py --check` | 💊 Health check |
| `python scheduler.py --run` | ▶️ Run immediately |

### 🏢 Supported Companies

> **📊 Total: 38 companies** (✅ Implemented 🚧 Pending)

<details>
<summary><b>🥇 Tier 1 (10 companies)</b></summary>

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

</details>

<details>
<summary><b>🥈 Tier 2 (15 companies)</b></summary>

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

</details>

<details>
<summary><b>🎮 Gaming (5 companies)</b></summary>

| Company | Social | Campus/Intern |
|:--------|:------:|:-------------:|
| NetEase Games | 🚧 | 🚧 |
| miHoYo | 🚧 | 🚧 |
| Lilith Games | 🚧 | 🚧 |
| Perfect World | 🚧 | 🚧 |
| 37Games | 🚧 | 🚧 |

</details>

<details>
<summary><b>🌍 International Tech (8 companies)</b></summary>

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

</details>

### ➕ Add New Company

1. 📝 Add config in `companies.yaml`
2. 🔒 Set `enabled: false`
3. 🕷️ Implement crawler in `spider.py`
4. ✅ Set `enabled: true` after testing

### 📄 Output Example

```markdown
### 1. AI Product Manager 🟢 85 points

| Field | Content |
|:------|:--------|
| Company | Tencent |
| Location | Beijing |
| Match Reason | Product Manager, AI Product, TOB |

**Responsibilities**: ...
```

</details>

---

<div align="center">

## 📜 License

**MIT License** © 2026 SmartJobHunter

**⭐ If this project helps you, please give it a star! ⭐**

Made with ❤️ by SmartJobHunter Team

</div>
