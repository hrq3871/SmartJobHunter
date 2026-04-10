<div align="center">

# 🎯 SmartJobHunter

**🤖 基于 LLM-Agent 的自动化求职巡检系统**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

<p>
  <a href="README.md"><b>🇺🇸 English</b></a>
</p>

</div>

---

## ✨ 功能特性

| 功能 | 描述 |
|:---:|:---|
| 🤖 **Agent 驱动** | 大模型驱动的智能岗位匹配与评估 |
| 🎯 **多意向并行** | 支持多个求职方向，每份简历独立巡检 |
| 📄 **多格式简历** | 支持 txt、md、docx、pdf、png、jpg 格式 |
| 🔍 **智能过滤** | 三层漏斗：时间 → 去重+关键词 → 岗位性质 |
| 📊 **AI 评估** | 自动评分（0-100分）+ 匹配理由 |
| 📊 **岗位分类** | 区分实习/校招/社招 |
| ⏰ **定时执行** | 每天自动巡检 |
| 🔧 **自我修复** | 爬虫异常自动检测 |

## 🚀 快速开始

### 1️⃣ 安装依赖

```bash
pip install playwright pyyaml
playwright install chromium

# 可选：支持 docx/pdf 简历
pip install python-docx PyMuPDF
```

### 2️⃣ 配置求职意向

在 `profiles/` 目录创建配置文件：

```bash
# 创建带 YAML frontmatter 的配置文件
cat > profiles/my_profile.md << 'EOF'
---
name: 产品经理
enabled: true
job_type: 社招
resume: resumes/my_resume.md
keywords:
  - 产品经理
  - TOB
  - AI产品
---

# 求职意向

寻找 TOB SaaS 产品经理岗位...
EOF
```

### 3️⃣ 运行巡检

```bash
# 运行所有启用的意向
python -m src.cli

# 指定岗位类型
python -m src.cli -t social      # 社招
python -m src.cli -t internship  # 实习
python -m src.cli -t campus      # 校招

# 指定意向
python -m src.cli -p "产品经理"

# 列出所有意向
python -m src.cli --list-profiles
```

### 4️⃣ 查看报告

```bash
ls output/
# 20260410_产品经理.md
```

## 📁 目录结构

```
SmartJobHunter/
├── 📂 src/                  # Python 模块
│   ├── cli.py               # CLI 入口
│   ├── crawler.py           # 爬虫模块
│   ├── filters.py           # 过滤函数
│   ├── resume_parser.py     # 简历解析
│   ├── scheduler.py         # 定时调度
│   ├── health_check.py      # 健康检测
│   └── git_auto_push.py     # Git 自动推送
│
├── 📂 config/               # 配置文件
│   ├── agent.yaml           # Agent 设置
│   └── companies.yaml       # 公司列表
│
├── 📂 profiles/             # 求职意向（Markdown + YAML frontmatter）
│   ├── pm_tob.md
│   └── AI产品经理.md
│
├── 📂 memory/               # 去重数据（Markdown）
│   └── seen_jobs.md
│
├── 📂 resumes/              # 简历文件
├── 📂 output/               # 生成的报告
│
├── 📂 .claude/skills/       # Claude Code Agent Skills
│   └── jobhunter/           # JobHunter Agent
│       ├── skill.md         # 主入口
│       ├── tools/           # 工具定义
│       └── prompts/         # AI 提示词
│
└── 📄 companies.md          # 用户可编辑的公司列表
```

## ⚙️ 配置说明

### 📋 意向配置格式 (profiles/*.md)

```markdown
---
name: 产品经理
enabled: true
job_type: 社招
resume: resumes/pm.md
keywords:
  - 产品经理
  - TOB
  - AI产品
---

# 求职意向

寻找 TOB SaaS 产品经理岗位...
```

### 🤖 Agent 配置 (config/agent.yaml)

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

### 🏢 公司配置 (config/companies.yaml)

```yaml
companies:
  - id: tencent
    name: 腾讯
    enabled: true
    urls:
      social: "https://careers.tencent.com/search.html?query={keyword}"
      campus: "https://careers.tencent.com/search.html?query={keyword}"
```

## 💻 命令参考

| 命令 | 说明 |
|:-----|:-----|
| `python -m src.cli` | 运行所有启用的意向 |
| `python -m src.cli -t social` | 只运行社招 |
| `python -m src.cli -p "意向名"` | 运行指定意向 |
| `python -m src.cli --list-profiles` | 列出所有意向 |

## 🏢 支持的公司

### 🥇 第一梯队 (10家)

| 公司 | 社招 | 校招/实习 |
|:-----|:----:|:---------:|
| 腾讯 | ✅ | ✅ |
| 字节跳动 | ✅ | ✅ |
| 美团 | ✅ | ✅ |
| 阿里巴巴 | 🚧 | 🚧 |
| 百度 | 🚧 | 🚧 |
| 滴滴出行 | 🚧 | 🚧 |
| 京东 | 🚧 | 🚧 |
| 拼多多 | 🚧 | 🚧 |
| 华为 | 🚧 | 🚧 |
| 小米 | 🚧 | 🚧 |

### 🥈 第二梯队 (15家)

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

> **📊 总计: 38家公司** (✅ 已实现 🚧 待开发)

## 🤖 Agent 架构

SmartJobHunter 采用 LLM-Agent 架构：

```
用户请求 → Agent (Claude) → 工具层 (Python) → 输出
                ↓
          ┌─────────┐
          │  状态机  │
          └─────────┘
                ↓
  INIT → LOADED → CRAWLED → FILTERED → EVALUATED → REPORTED → DONE
```

### Agent Skills

位于 `.claude/skills/jobhunter/`：

- `skill.md` - Agent 主入口
- `tools/*.md` - 工具定义（crawl, filter, load_config）
- `prompts/*.md` - Agent 提示词（evaluate, report）

## 📄 输出示例

```markdown
### 1. AI产品经理 🟢 85分

| 字段 | 内容 |
|:-----|:-----|
| 公司 | 腾讯 |
| 地点 | 北京 |
| 匹配理由 | 产品经理, AI产品, TOB |

**岗位职责**: ...
```

---

<div align="center">

## 📜 许可证

**MIT License** © 2026 SmartJobHunter

**⭐ 如果这个项目对你有帮助，请给个 Star！⭐**

Made with ❤️ by SmartJobHunter Team

</div>
