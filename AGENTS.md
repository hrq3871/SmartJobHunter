# SmartJobHunter Agent 操作指南

## Agent 工作流程

SmartJobHunter 是 agent-platform 项目。Python 只负责抓取、文本抽取、确定性过滤、fallback 粗评分和报告落盘；简历画像、岗位画像、语义过滤、最终匹配判断和修复分析由当前 Claude/Codex Agent 执行。

项目不只面向产品经理。产品经理只是示例 profile。真实目标岗位必须从 `profiles/*.md` 的 `target_roles`、`must_have`、`avoid` 等字段读取。

`CLAUDE.md` 和 `AGENTS.md` 面向不同 AI 平台，但必须表达同一套规则。更新其中一个文件时，要同步另一个文件，避免 Claude、Codex 或其他 agent 读到不同工作流。

## Python 过滤与 Agent 判断的关系

不要废掉原有“已爬取岗位过滤”设计。它是工具链的一部分，用来把官网岗位变成可处理的候选集：

1. `filters.filter_by_time`：按 `time_filter_days` 做时间过滤。
2. `filters.dedup`：按 `memory/seen_jobs.md` 去重。
3. `filters.clean_data`：清洗和截断 JD。
4. `matching.match_job_intent`：根据 profile 做 fallback 意向过滤。
5. `matching.evaluate_job_fit`：根据 profile、JD、简历文本做 fallback 粗评分。
6. `_rank_and_filter_results`：按 `threshold_score` 和 `max_jobs_per_report` 控制报告输出。
7. `filters.update_memory`：记录已处理岗位，避免重复报告。

Agent 的作用不是替换这些步骤，而是把它们纳入判断闭环：

- 运行前：从简历和求职目标补全 profile，确认 `target_roles`、`target_domains`、`must_have`、`nice_to_have`、`avoid` 是否覆盖真实方向。
- 抓取时：根据 profile 选择搜索关键词。目标较宽时，不要只依赖单个关键词；可用 `python -m src.crawler_factory --crawl <company_id> --keyword "<关键词>" --max-jobs 10` 对多个代表关键词抽样。
- 过滤后：不要把 Python fallback 分数当成最终结论。Agent 必须检查报告岗位是否有 JD 证据、简历证据和 profile 目标三者闭环。
- 结果异常时：如果出现“没有岗位”“岗位很机械”“明显不匹配岗位进入报告”，先用原始抓取样本对比过滤结果，判断问题出在关键词、profile、过滤阈值、字段映射还是 JD 质量。
- 收尾前：至少用 3 家公司做真实官网验证，并人工评估抽样岗位是否符合目标。

当用户请求运行求职巡检时，Agent 应按以下步骤执行：

### Step 1: 读取配置
```
1. 读取 config/companies.yaml 获取公司配置
2. 读取 profiles/ 目录下的求职意向配置
3. 读取 resumes/ 目录下的简历文件
4. 读取 memory/seen_jobs.md 获取已处理岗位
```

### Step 2: 抓取岗位数据
```
使用 crawler_factory 抓取岗位：
python -m src.crawler_factory --crawl <company_id> --keyword "关键词"
```

### Step 3: 候选人画像
```
1. 读取简历原文
2. 使用 .claude/skills/jobhunter/prompts/build_candidate_profile.md 生成 candidate_profile
3. 每个能力点必须有简历证据；信息不足写入 missing_or_unclear
```

### Step 4: 三层过滤
```
第一层 - 时间过滤：只保留最近N天的岗位（默认3天）
第二层 - 去重过滤：排除 seen_jobs.md 中已有的岗位
第三层 - 语义意向匹配：结合 target_roles、must_have、avoid、候选人画像、岗位职责/要求和风险信号判断是否保留
```

第三层目前由 Python fallback 先执行，Agent 需要复核结果质量。不要因为 CLI 输出为空就直接判断“没有合适岗位”；应抽查同一公司、同一关键词下的原始抓取结果，确认是否是搜索词、profile 或过滤阈值导致的漏召回。

### Step 5: 岗位画像与 AI 评估
```
对每个通过过滤的岗位，Agent 进行深度评估：
1. 使用 .claude/skills/jobhunter/prompts/analyze_job.md 生成 job_profile
2. 使用 .claude/skills/jobhunter/prompts/match_candidate_job.md 评估匹配度 (0-100)
3. 输出 JD 证据、简历证据、缺失技能/风险
4. 公司背调（可选）
```

### Step 6: 生成报告
```
将评估结果写入 output/ 目录的 Markdown 文件
格式：{日期}_{意向名称}.md
```

### Step 7: 更新去重数据库
```
将处理过的岗位追加到 memory/seen_jobs.md
```

## 常用命令

```bash
# 立即执行巡检
python -m src.cli                    # 运行所有启用的意向
python -m src.cli -t social          # 仅社招
python -m src.cli -t internship      # 仅实习
python -m src.cli -t campus          # 仅校招
python -m src.cli -p "意向名称"       # 指定意向

# 爬虫管理
python -m src.crawler_factory --list              # 列出所有公司
python -m src.crawler_factory --test <id>         # 测试爬虫
python -m src.crawler_factory --crawl <id>        # 抓取指定公司

# 健康检测
python -m src.health_monitor --check <id>         # 检测单个爬虫
python -m src.health_monitor --check-all          # 检测所有爬虫
```

## 健康检测与 Agent 辅助修复

当爬虫失败时，Python 只做健康检测、诊断和证据生成；Agent 负责分析和修复决策：

1. **健康检测** (`health_monitor.py`) - 诊断失败原因
2. **证据采集** (`crawler_evidence.py`) - 记录页面、XHR/fetch、候选 data_path 和字段样例
3. **Agent 分析** - 判断 URL、API pattern、data_path、field mapping、登录/反爬或无岗位问题
4. **用户通知** (`notifier.py`) - 通知修复结果

### 失败类型处理

| 类型 | Python 自动修复 | Agent 处理方式 |
|------|:--------:|----------|
| 网络错误 | ❌ | 稍后重试 |
| API变化 | ❌ | 读取证据后修改 API pattern / data_path / field_mappings |
| URL失效 | ❌ | 搜索新 URL 并验证 |
| 需要登录 | ❌ | 通知用户 |
| 反爬拦截 | ❌ | 调整频率 |

## 支持的公司

**已启用 (42家)：**
- BAT+TMD: 腾讯、字节、阿里、美团、百度、滴滴、京东、拼多多、华为、小米
- 互联网: 网易、快手、B站、小红书、携程、微博、知乎、OPPO、vivo、中兴、联想
- 游戏: 米哈游、莉莉丝、三七互娱
- 飞书系: 商汤、Keep、SHEIN、蔚来、理想、小鹏
- 其他: 苹果、吉利、长城、大疆、海康、科大讯飞、深信服、工商银行

**待开发 (14家)：**
- 外资: 微软、英伟达、特斯拉、Intel、AMD、思科、SAP
- 国央企: 建行、移动、电信
- 其他: 比亚迪、浪潮、蚂蚁、菜鸟

完整列表见 `公司列表.md` 和 `config/companies.yaml`

## 文件管理规范

### 项目优化记录

功能优化过程记录在本地私有文档 `docs/optimization-log.md`，该文件不提交到 GitHub。

只有在功能优化的开发计划已经讨论并确认后，才更新该文档；只是提出想法、整理 roadmap、讨论可能方向时不更新。

当改动属于已确认要执行的功能优化时，需要同步记录：

1. **问题** - 发现了什么具体问题
2. **方案** - 采用了什么策略或实现
3. **效果** - 行为变化、验证方式和结果
4. **后续** - 还需要观察或继续优化的点

需要更新优化记录的情况：

- 调整岗位筛选、语义匹配、评分、排序、报告生成、投递建议等核心产品行为
- 新增或重构会改变用户使用方式的功能
- 对现有功能做策略优化，并改变结果质量、覆盖范围、误判率或使用体验

不需要更新优化记录的情况：

- 只是提出想法、讨论方向，或还没有确认开发计划
- 只修 bug，且没有改变产品策略
- 只更新 README、注释、格式或普通文案
- 只做配置安全、Git 历史、依赖、测试环境等工程卫生清理
- 只补测试，且不改变功能行为

### 飞书推送配置

每日扫描结果可推送到飞书 Wiki / 多维表格。

Git 只提交示例配置 `config/agent.sample.yaml`；真实配置必须复制到本地 `config/agent.yaml`，该文件已被 `.gitignore` 忽略，禁止提交到 GitHub。

```powershell
Copy-Item config\agent.sample.yaml config\agent.yaml
```

本地 `config/agent.yaml` 示例：

```yaml
feishu:
  app_id: "cli_xxx"           # 飞书应用 ID
  app_secret: "xxx"           # 飞书应用 Secret
  wiki_node_token: "xxx"      # Wiki 节点 token
  bitable_token: "xxx"        # 多维表格 token（可选，首次运行自动创建）
  bitable_table_id: "xxx"     # 数据表 ID（可选）
  enabled: true               # 是否启用推送
```

**报告命名格式**：`{简历标识}_{YYYYMMDD_HHMM}.md`

**多维表格字段**：
- 岗位标题、公司、岗位链接
- AI评分、投递状态、录取状态
- 岗位类型（社招/校招/实习）
- 投递简历、报告链接、创建时间

### 临时文件清理

**一次性文件用完必须清理：**

| 类型 | 示例 | 处理 |
|------|------|------|
| API分析输出 | `*_api.json` | 用完删除 |
| 一次性脚本 | `scripts/analyze_*.py` | 用完删除 |
| 迁移脚本 | `scripts/migrate.py` | 执行后删除 |
| 调试输出 | `debug_*.json` | 用完删除 |

**删除方式：**
```bash
# 使用 PowerShell 进回收站（可恢复）
powershell -Command "Remove-Item -LiteralPath '文件路径' -Force"
```

**禁止使用 `rm` 命令**（永久删除，不可恢复）

### 目录结构

```
SmartJobHunter/
├── config/           # 配置文件（长期保留）
├── src/              # 源代码（长期保留）
├── profiles/         # 求职意向（用户维护）
├── resumes/          # 简历文件（用户维护）
├── memory/           # 去重数据（自动更新）
├── output/           # 输出报告（自动生成）
├── logs/             # 日志文件（自动生成）
├── tests/            # 测试文件（长期保留）
└── docs/             # 文档（长期保留，含 optimization-log.md）
```

## Bug修复流程

每次修复bug必须遵循：

1. **出计划** - 分析问题，制定方案
2. **Review** - 检查方案合理性
3. **执行测试** - 验证修复效果
4. **清理临时文件** - 删除一次性脚本和输出

如果只是修 bug，不需要更新 `docs/optimization-log.md`；只有当修复同时改变了筛选、评分、推荐或用户工作流等功能策略时，才需要补充优化记录。
