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
| 🔍 **智能过滤** | 三层漏斗：时间 → 去重 → 语义意向匹配 |
| 📊 **AI 评估** | 规则指导评分（0-100分）+ 基于证据的匹配理由 |
| 📊 **岗位分类** | 区分实习/校招/社招 |
| ⏰ **定时执行** | 每天 20:00 自动巡检 |
| 🔧 **自愈系统** | 爬虫健康监控与自动修复 |
| 🏢 **56 家公司** | 42 家已启用，API 已验证 |
| ⚙️ **配置驱动** | 添加新公司无需写代码 |

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
│   ├── cli.py               # CLI 入口 & JobHunter 类
│   ├── crawler.py           # 传统爬虫（腾讯、字节等）
│   ├── crawler_factory.py   # 爬虫工厂（含自愈逻辑）
│   ├── config_crawler.py    # 配置驱动爬虫
│   ├── base_crawler.py      # 爬虫基类（API 拦截）
│   ├── health_monitor.py    # 健康监控与诊断
│   ├── auto_analyzer.py     # 新公司自动分析
│   ├── notifier.py          # 用户通知系统
│   ├── filters.py           # 过滤函数（时间、去重、清洗）
│   ├── matching.py          # 语义匹配 fallback 与评分规则
│   ├── resume_parser.py     # 简历解析（txt/md/docx/pdf/图片）
│   ├── scheduler.py         # 定时调度（每天 20:00）
│   ├── health_check.py      # 健康检测
│   └── git_auto_push.py     # Git 自动推送
│
├── 📂 config/               # 配置文件
│   ├── agent.yaml           # Agent 设置
│   ├── companies.yaml       # 公司列表（56 家）
│   └── system_templates.yaml # 招聘系统模板
│
├── 📂 profiles/             # 求职意向（Markdown + YAML frontmatter）
├── 📂 resumes/              # 简历文件
├── 📂 memory/               # 去重数据（seen_jobs.md）
├── 📂 output/               # 生成的报告
├── 📂 logs/                 # 日志文件
├── 📂 tests/                # 测试文件
│
├── 📂 .claude/skills/       # Claude Code Agent Skills
│   └── jobhunter/           # JobHunter Agent
│
└── 📄 公司列表.md           # 公司列表文档
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
time_filter_days: 3         # 只显示最近 N 天的岗位
threshold_score: 70         # 最低评分阈值
jd_truncate_length: 6000    # JD 最大长度

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

## 🧠 匹配与评分逻辑

SmartJobHunter 不再把关键词命中本身视为匹配。

匹配流程：

1. **确定性过滤**：时间窗口和去重仍由 Python 处理。
2. **语义意向过滤**：Agent 判断岗位真实职责是否符合求职意向，关键词只作为辅助证据。
3. **简历-岗位匹配评分**：Agent 按角色匹配、领域匹配、简历证据、偏好、证据质量和风险扣分评分。
4. **Python fallback**：当没有 Agent 执行 prompt 时，`src.matching` 用同一套规则支持 CLI 运行和自动化测试。

评分维度：

| 维度 | 权重 | 含义 |
|:--|:--:|:--|
| `core_role_fit` | 30 | 岗位核心角色是否符合目标方向 |
| `domain_fit` | 25 | 是否符合 AI Agent、大模型应用、ToB SaaS 等目标领域 |
| `resume_evidence` | 25 | 简历是否有能支撑 JD 要求的证据 |
| `preference_fit` | 10 | 地点、岗位性质和其他偏好是否一致 |
| `evidence_quality` | 10 | JD 和简历证据是否清晰、可验证 |
| `risk_penalty` | -20 | 关键词噪声、角色偏离或核心证据缺失 |

Agent 提示词位于 `.claude/skills/jobhunter/prompts/`，要求输出有证据支撑的 JSON。例如，“AI 标注运营”不能只因为包含 “AI” 就被评为强匹配 AI 产品岗位。

## 💻 命令参考

### CLI 命令

| 命令 | 说明 |
|:-----|:-----|
| `python -m src.cli` | 运行所有启用的意向 |
| `python -m src.cli -t social` | 只运行社招 |
| `python -m src.cli -t internship` | 只运行实习 |
| `python -m src.cli -t campus` | 只运行校招 |
| `python -m src.cli -p "意向名"` | 运行指定意向 |
| `python -m src.cli --list-profiles` | 列出所有意向 |

## ✅ 测试

```bash
# 单元测试和非联网测试
pytest -q -p no:cacheprovider -m "not integration"

# 仅运行匹配/评分测试
pytest -q -p no:cacheprovider tests/test_matching.py
```

集成爬虫测试需要浏览器和网络访问，并使用 `integration` 标记。

### 爬虫命令

| 命令 | 说明 |
|:-----|:-----|
| `python -m src.crawler_factory --list` | 列出所有公司 |
| `python -m src.crawler_factory --test <id>` | 测试指定爬虫 |
| `python -m src.crawler_factory --crawl <id>` | 抓取指定公司 |

### 调度器命令

| 命令 | 说明 |
|:-----|:-----|
| `python -m src.scheduler --run` | 立即执行巡检 |
| `python -m src.scheduler --check` | 运行健康检测 |
| `python -m src.scheduler --repair` | 触发修复流程 |
| `python -m src.scheduler --schedule` | 定时模式（系统调用） |

### 健康监控命令

| 命令 | 说明 |
|:-----|:-----|
| `python -m src.health_monitor --check <id>` | 检测单个爬虫 |
| `python -m src.health_monitor --check-all` | 检测所有爬虫 |
| `python -m src.health_monitor --report` | 生成健康报告 |

## 🏢 支持的公司

### ✅ 已启用（42 家）

**第一梯队 - BAT + TMD：**
| 公司 | 社招 | 校招 | 系统 |
|:-----|:----:|:----:|:-----|
| 腾讯 | ✅ | ✅ | 自建 |
| 字节跳动 | ✅ | ✅ | 飞书 |
| 字节跳动(社招) | ✅ | - | 飞书 |
| 阿里巴巴 | ✅ | ✅ | 自建 |
| 美团 | ✅ | ✅ | 自建 |
| 百度 | ✅ | ✅ | 自建 |
| 滴滴出行 | ✅ | ✅ | 自建 |
| 京东 | ✅ | ✅ | 自建 |
| 拼多多 | ✅ | ✅ | 自建 |
| 华为 | ✅ | ✅ | 自建 |
| 小米 | ✅ | ✅ | 自建 |

**第二梯队 - 互联网公司：**
| 公司 | 社招 | 校招 | 系统 |
|:-----|:----:|:----:|:-----|
| 网易 | ✅ | ✅ | 自建 |
| 快手 | ✅ | ✅ | 自建 |
| B站 | ✅ | ✅ | 自建 |
| 小红书 | ✅ | ✅ | 自建 |
| 携程 | ✅ | ✅ | 自建 |
| 微博 | ✅ | ✅ | 自建 |
| 知乎 | ✅ | ✅ | Mokahr |
| OPPO | ✅ | ✅ | 自建 |
| vivo | ✅ | ✅ | 自建 |
| 中兴 | ✅ | ✅ | Mokahr |
| 联想 | ✅ | ✅ | Workday |

**游戏公司：**
| 公司 | 社招 | 校招 | 系统 |
|:-----|:----:|:----:|:-----|
| 米哈游 | ✅ | ✅ | 自建 |
| 莉莉丝 | ✅ | ✅ | 飞书 |
| 三七互娱 | ✅ | ✅ | 自建 |

**飞书系统：**
| 公司 | 社招 | 校招 |
|:-----|:----:|:----:|
| 商汤 | ✅ | - |
| Keep | ✅ | - |
| SHEIN | ✅ | - |
| 蔚来 | ✅ | - |
| 理想 | ✅ | - |
| 小鹏 | ✅ | - |

**其他：**
| 公司 | 社招 | 校招 | 系统 |
|:-----|:----:|:----:|:-----|
| 苹果中国 | ✅ | - | 自建 |
| 吉利 | ✅ | ✅ | Mokahr |
| 长城汽车 | ✅ | ✅ | 自建 |
| 大疆 | ✅ | ✅ | 自建 |
| 海康威视 | ✅ | ✅ | 自建 |
| 科大讯飞 | ✅ | ✅ | 自建 |
| 深信服 | ✅ | ✅ | 自建 |
| 工商银行 | ✅ | ✅ | 银行系统 |

### 🔧 待开发（14 家）

| 公司 | 招聘系统 | 说明 |
|:-----|:---------|:-----|
| 微软中国 | Phenom | 需分析 API |
| 英伟达中国 | Workday + Eightfold | 需 DOM 解析 |
| 特斯拉中国 | Mokahr | URL 已验证 |
| 英特尔中国 | Workday | 需 DOM 解析 |
| AMD 中国 | Workday | 需 DOM 解析 |
| 思科中国 | Workday | 需 DOM 解析 |
| SAP 中国 | Workday | 需 DOM 解析 |
| 浪潮集团 | 北森 | 需 DOM 解析 |
| 建设银行 | 银行系统 | 需分析 API |
| 中国移动 | 国企系统 | 需分析 API |
| 中国电信 | 国企系统 | 需分析 API |
| 比亚迪 | 自建 | 需分析 API |
| 蚂蚁集团 | 阿里系 | 需验证 |
| 菜鸟网络 | 阿里系 | 需验证 |

> **📊 总计：56 家公司（42 家已启用，14 家待开发）**

### 🔧 添加新公司

配置驱动架构，添加新公司无需写代码：

1. 编辑 `config/companies.yaml`
2. 添加 `field_mappings` 配置
3. 无需修改代码！

示例：

```yaml
- id: new_company
  name: 新公司
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

## 🔧 自愈系统

SmartJobHunter 内置自动自愈系统：

### 架构

```
爬取请求 → 爬虫工厂 → 健康监控
                ↓            ↓
          自动分析器 ← 诊断结果
                ↓            ↓
          配置更新 ← 修复动作
                ↓
          通知器 → 用户
```

### 组件

| 模块 | 功能 |
|:-----|:-----|
| `health_monitor.py` | 检测爬虫健康，诊断失败原因 |
| `auto_analyzer.py` | 分析新公司，识别招聘系统 |
| `notifier.py` | 通知用户修复结果 |
| `crawler_factory.py` | 集成自愈逻辑 |

### 失败类型

| 类型 | 自动修复 | 处理方式 |
|:-----|:--------:|:---------|
| 网络错误 | ❌ | 稍后重试 |
| API 变化 | ✅ | 重新分析 API |
| URL 失效 | ✅ | 搜索新 URL |
| 需要登录 | ❌ | 通知用户 |
| 反爬拦截 | ❌ | 调整频率 |
| 配置错误 | ❌ | 通知用户 |

### 招聘系统模板

位于 `config/system_templates.yaml`：

| 系统 | API Pattern | 数据路径 | 代表公司 |
|:-----|:------------|:---------|:---------|
| Mokahr | `jobs` | `data.jobs` | 知乎、中兴、吉利、特斯拉 |
| 飞书 | `search/job/posts` | `data.job_post_list` | 字节、莉莉丝、商汤、蔚来 |
| Workday | DOM 解析 | - | Intel、AMD、思科、SAP、联想 |
| 北森 | DOM 解析 | - | 浪潮 |
| Phenom | API 拦截 | - | 微软 |
| 自建 | 各异 | 各异 | 腾讯、阿里、美团等 |

## 🔄 工作流程

### 巡检流程

```
1. 加载配置     → 读取意向、公司、简历
2. 抓取岗位     → Playwright API 拦截
3. 过滤         → 时间 → 去重 → 关键词
4. 评估         → 评分（0-100）+ 匹配理由
5. 生成报告     → Markdown 文件到 output/
6. 更新记忆     → 追加到 seen_jobs.md
```

### 过滤管道

```
原始岗位（来自爬虫）
    ↓
[时间过滤] 保留最近 N 天（默认 3 天）
    ↓
[去重过滤] 移除已见岗位（基于 hash）
    ↓
[关键词过滤] 匹配标题/职责关键词
    ↓
[数据清洗] 截断、规范化文本
    ↓
过滤后岗位
```

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
# 求职巡检报告

## 基本信息
- **意向**: 产品经理
- **类型**: 社招
- **生成时间**: 2026-04-18 20:00
- **岗位数**: 15

## 求职意向
寻找 TOB SaaS 产品经理岗位...

---

## 推荐岗位

### 1. AI产品经理 🟢 85分

| 字段 | 内容 |
|:-----|:-----|
| 公司 | 腾讯 |
| 地点 | 北京 |
| 类别 | 产品 |
| 发布时间 | 2026-04-17 |

**匹配理由**: 产品经理, AI产品, TOB

**岗位职责**:
负责AI产品的规划和设计...

**链接**: [查看岗位](https://careers.tencent.com/position_detail.html?id=xxx)

---
```

## 📜 许可证

**MIT License** © 2026 SmartJobHunter

**⭐ 如果这个项目对你有帮助，请给个 Star！⭐**

Made with ❤️ by SmartJobHunter Team
