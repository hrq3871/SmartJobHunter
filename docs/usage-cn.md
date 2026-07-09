# SmartJobHunter 操作手册

> **文档用途**
> 本文档用于维护者和高级用户查阅 SmartJobHunter 的完整操作路径、常用命令、配置文件和排障入口。
> 主要读者是项目开发者、Agent 维护者，以及需要手动修复抓取策略或维护评估体系的人。
> 不用于普通求职用户第一次上手；最简单的使用方式看根目录 `README_CN.md`。

这份文档回答三个问题：能做什么、怎么触发、要改哪些文件。它不是内部 Agent 定义文档；完整运行架构看 `CLAUDE.md` / `AGENTS.md`，设计细节看 `docs/smartjobhunter-agent-design.md`。

## 你能用它做什么

| 功能 | 怎么触发 | 输出在哪里 |
|------|----------|------------|
| 每日求职巡检 | 让 AI 执行“运行今天的求职巡检”，或直接跑 `python -m src.cli` | `output/{日期}/` 下的岗位报告和投递包 |
| 只跑社招/实习/校招 | `python -m src.cli -t social` / `internship` / `campus` | 对应类型的巡检报告 |
| 只跑某个求职意向 | `python -m src.cli -p "意向名称"` | 该 profile 的报告 |
| 抓取某家公司岗位 | `python -m src.crawler_factory --crawl <company_id> --keyword "关键词"` | 命令行输出抓取结果 |
| 检查某家公司策略 | `python -m src.health_monitor --inspect-company <company_id> --keyword "关键词"` | `logs/strategy_tasks/` 和 `logs/crawler_evidence/` |
| 修复官网抓取策略 | 对 AI 说“分析/修复 XX 公司抓取策略” | AI 会读证据包并修改 `config/companies.yaml` 或 `src/site_strategies/` |
| 生成 Top 3 投递包 | 完整巡检自动触发 | `output/{日期}/application_packages/` |
| 推送飞书 | 开启 `config/agent.yaml` 后运行巡检 | 飞书 Wiki / 多维表格 |
| 评估系统是否跑偏 | `python -m src.evaluation --fail-under 1.0` | `output/evals/{日期}/` |

## 第一次使用要改哪些文件

| 文件/目录 | 谁维护 | 用来做什么 |
|-----------|--------|------------|
| `resumes/` | 用户 | 放简历原件，仅支持 PDF、Markdown、TXT |
| `config/resume_intents.yaml` | Web / 程序 | 保存用户填写的搜索关键词、岗位类型、启用状态；本地私有，不提交 |
| `profiles/*.md` | Agent 生成 | Agent 读取简历原件和 `search_intent` 后生成的正式求职画像 |
| `config/companies.yaml` | 用户 + AI | 维护公司官网/招聘链接、是否启用、抓取策略 |
| `config/agent.yaml` | 用户本地 | 飞书配置、通知配置等私有配置；从 `config/agent.sample.yaml` 复制 |
| `memory/seen_jobs.md` | 程序自动维护 | 记录已经处理过的岗位，避免重复报告 |
| `output/` | 程序自动生成 | 巡检报告、投递包、评估输出 |
| `logs/` | 程序自动生成 | 抓取证据、策略诊断、失败原因 |
| `CLAUDE.md` / `AGENTS.md` | 维护者 | 定义 AI Agent 的运行规则；普通使用不需要改 |
| `.claude/skills/jobhunter/skill.md` | 维护者 | Skillmap，告诉 AI 什么时候进入求职巡检、策略修复、评估等路径 |

## Profile 怎么来

新用户不应该手写 `profiles/*.md`。正确链路是：

1. 用户把 PDF、Markdown 或 TXT 简历放入 `resumes/`，或通过 Web 控制台上传。
2. 用户在 Web 控制台填写搜索关键词和岗位类型，这只会保存为 `config/resume_intents.yaml` 中的 `search_intent`。
3. 点击“启动巡检”后，Claude Code 读取完整简历和 `search_intent`，生成或刷新 `profiles/<profile_id>.md`。
4. 后续 CLI 的 `python -m src.cli -p "<profile_id>"` 读取的是这个 Agent 生成后的正式 profile。

`profiles/*.md` 可以作为生成结果复核和维护。它应包含目标角色、必须项、排除项、简历证据和偏好；不要把简单关键词列表手动冒充正式画像。

```yaml
---
name: AI 产品经理
enabled: true
job_type: 社招
resume: resumes/ai_pm.md
search_keywords:
  - 产品经理
  - AI产品
keywords:
  - AI产品经理
  - Agent产品
  - 大模型产品
target_roles:
  - AI产品经理
  - AI应用产品经理
target_domains:
  - AI Agent
  - 大模型应用
  - ToB SaaS
must_have:
  - 需求分析
  - 产品规划
  - 跨团队推进
nice_to_have:
  - RAG
  - 企业客户
avoid:
  - 销售
  - 客服
  - 标注
  - 审核
---

# 求职意向说明

这里可以补充更自然语言的偏好，比如行业、城市、薪资、公司阶段、不能接受的工作内容。
```

生成后的关键字段：

| 字段 | 必填 | 说明 |
|------|:----:|------|
| `enabled` | 是 | 是否启用这个巡检任务 |
| `job_type` | 是 | Profile 文件里写 `社招`、`校招`、`实习`；命令行 `-t` 才使用 `social`、`campus`、`internship` |
| `resume` | 是 | 关联的简历原件 |
| `search_keywords` | 建议 | 实际写入招聘网站搜索框的 2-3 个抓取词，建议一宽一窄 |
| `keywords` | 建议 | 语义匹配和证据判断使用的辅助关键词，不建议只靠它决定抓取范围 |
| `target_roles` | 是 | 目标岗位名，不要只写一个过窄关键词 |
| `target_domains` | 建议 | 目标行业/业务方向 |
| `must_have` | 是 | 必须匹配的能力或职责 |
| `nice_to_have` | 否 | 加分项 |
| `avoid` | 是 | 明确排除的岗位、职责或行业 |

## 常用命令

### 初始化本地配置

```powershell
Copy-Item config\agent.sample.yaml config\agent.yaml
```

`config/agent.yaml` 是本地私有配置，不提交到 GitHub。飞书应用、Wiki 节点、多维表格 token 都写在这里。

### 运行求职巡检

```powershell
# 运行所有启用的 profile
python -m src.cli

# 查看所有 profile
python -m src.cli --list-profiles

# 只跑社招
python -m src.cli -t social

# 只跑实习
python -m src.cli -t internship

# 只跑校招
python -m src.cli -t campus

# 指定某个 profile
python -m src.cli -p "AI 产品经理"
```

### 查看和测试公司抓取

```powershell
# 列出所有公司
python -m src.crawler_factory --list

# 测试某家公司是否能抓
python -m src.crawler_factory --test <company_id>

# 抓取某家公司岗位
python -m src.crawler_factory --crawl <company_id> --keyword "产品经理" --max-jobs 10
```

### 检查和修复抓取策略

```powershell
# 每日策略巡检
python -m src.health_monitor --inspect-strategies --keyword "产品经理" --job-type social

# 检查单家公司
python -m src.health_monitor --inspect-company <company_id> --keyword "产品经理"

# 修改策略后验证单家公司
python tests/test_all_crawlers.py --company <company_id> --keyword "产品经理" --max-jobs 3
```

如果策略巡检生成了 `logs/strategy_tasks/.../task.json`，可以直接让 AI 读这个任务和对应证据包：

```text
帮我分析 logs/strategy_tasks/.../task.json，修复这家公司抓取策略。
```

### 飞书推送

```powershell
# 查看飞书推送状态
python -m src.scheduler --feishu-push status

# 开启每日巡检后推送飞书
python -m src.scheduler --feishu-push on

# 关闭飞书推送
python -m src.scheduler --feishu-push off
```

注意：`python -m src.scheduler --schedule --push` 里的 `--push` 是 Git commit/push，不是飞书推送。

### 评估和回归

```powershell
# 标准评估
python -m src.evaluation --fail-under 1.0

# 多轮稳定性评估
python -m src.evaluation --trials 3 --fail-under 1.0

# 只跑 hard cases
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml --fail-under 1.0

# 评估相关单测
python -m pytest tests/test_evaluation.py -v
```

改了抓取、过滤、评分、报告、投递包、`CLAUDE.md`、`AGENTS.md` 或 `.claude/skills/jobhunter/skill.md` 后，都要跑评估。

## 输出怎么看

```text
output/
└── 2026-05-11/
    ├── ai_pm_20260511_0930.md
    └── application_packages/
        └── ai_pm_20260511_0930/
            ├── company_a_role.md
            ├── company_b_role.md
            └── company_c_role.md
```

| 输出 | 说明 |
|------|------|
| `output/{日期}/{profile_id}_{时间}.md` | 主报告，包含岗位列表、匹配理由、风险、链接 |
| `output/{日期}/application_packages/` | Top 3 岗位投递包和定制 Cover Letter |
| `logs/strategy_tasks/` | 需要 AI 分析的策略任务 |
| `logs/crawler_evidence/` | 页面、接口、字段样例等抓取证据 |
| `output/evals/` | 评估运行结果 |

报告里的分数不是单纯关键词分。完整判断应同时看岗位 JD 证据、简历证据、profile 目标、缺失项和风险信号。

## 在 AI 对话里怎么说

| 你可以这样说 | Agent 应该做什么 |
|--------------|------------------|
| “运行今天的社招巡检” | 读取 profile、公司配置、简历，跑巡检并生成报告 |
| “只跑 AI 产品经理这个意向” | 只执行指定 profile |
| “这个 JD 适合我吗？” | 读取简历/profile，对单个岗位做匹配分析 |
| “腾讯抓不到岗位，帮我看一下” | 跑 health monitor，读取证据包，判断是否要改策略 |
| “这次推荐明显不准，沉淀成 eval case” | 把失败样例写进评估集，并说明预期行为 |
| “开启飞书推送” | 检查本地配置并打开 `feishu.enabled` |
| “改了 Agent 指令，跑一下评估” | 运行 `src.evaluation` 检查 instruction drift |

## 常见场景

### 新增一个求职方向

1. 在 `resumes/` 放对应简历，或通过 Web 上传。
2. 在 Web 控制台填写搜索关键词和岗位类型，保存 `search_intent`。
3. 点击“启动巡检”，让 Claude Code 读取简历并生成正式 profile。
4. 生成后如需复核，可查看 `profiles/<profile_id>.md` 中的 `target_roles`、`must_have`、`avoid`。
5. 后续可运行：

```powershell
python -m src.cli -p "新意向名称"
```

### 新增一家公司

1. 在 `config/companies.yaml` 增加公司 ID、名称、招聘链接和启用状态。
2. 先跑策略巡检：

```powershell
python -m src.health_monitor --inspect-company <company_id> --keyword "产品经理"
```

3. 如果生成策略任务，让 AI 分析证据并固化策略。
4. 修改后验证：

```powershell
python tests/test_all_crawlers.py --company <company_id> --keyword "产品经理" --max-jobs 3
```

### 某家公司没有结果

先不要直接判断“没有合适岗位”。按顺序排查：

1. 公司链接是否失效。
2. 是否需要登录、验证码或被反爬。
3. 搜索关键词是否太窄。
4. profile 的 `avoid` 或 `must_have` 是否过严。
5. 抓取字段映射是否拿不到完整 JD。
6. 过滤阈值是否过高。

### 推荐结果不准

1. 对比原始抓取样本和最终报告。
2. 判断问题属于关键词、profile、字段映射、JD 质量、评分规则还是 Agent 指令漂移。
3. 把典型失败样例沉淀为 eval case。
4. 跑：

```powershell
python -m src.evaluation --fail-under 1.0
```

## 不要手动改或不要提交的东西

| 路径 | 规则 |
|------|------|
| `config/agent.yaml` | 本地私有配置，不提交 |
| `output/` | 运行产物，不提交 |
| `logs/` | 运行日志和证据，不提交 |
| `docs/optimization-log.md` | 本地私有优化记录，不提交 |
| `memory/seen_jobs.md` | 通常由程序维护，除非明确要清理去重记录 |

不要直接 push 到 `main`。日常开发应在功能分支完成、测试通过、确认合并方式后再进入主分支。
