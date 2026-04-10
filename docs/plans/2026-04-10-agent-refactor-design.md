# SmartJobHunter Agent 改造设计文档

> 创建时间：2026-04-10
> 状态：设计中

---

## 1. 设计目标

将 SmartJobHunter 从规则引擎改造为 **LLM 驱动的 Agent**，最终发布为可复用的 Skills。

### 核心目标
1. **节约 Token** - 按需加载 Memory，避免全量注入
2. **优化匹配评分** - Agent 智能评估岗位匹配度

### 发布目标
- 团队共享：放在项目的 `.claude/skills/` 目录
- 公开发布：发布到 skills 插件市场

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  Skills 层 (智能决策)                                        │
│  .claude/skills/jobhunter/                                  │
│  - 语义过滤、AI评估、报告生成                                 │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Python 工具层 (确定性逻辑)                                   │
│  src/                                                       │
│  - 爬虫、时间过滤、去重、数据清洗                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 职责划分

| 层级 | 职责 | 实现方式 |
|------|------|---------|
| **Skills 层** | 智能决策 | 语义过滤、AI评估、报告生成 |
| **Python 层** | 确定性工作 | 爬虫、时间过滤、去重、数据清洗 |

---

## 3. 目录结构

```
SmartJobHunter/
├── .claude/
│   └── skills/
│       └── jobhunter/
│           ├── skill.md              # Agent 主入口
│           ├── tools/
│           │   ├── crawl.md          # 抓取工具定义
│           │   ├── filter.md         # 确定性过滤工具
│           │   └── load_data.md      # 加载配置/简历/公司列表
│           └── prompts/
│               ├── semantic_filter.md  # 语义过滤 Agent prompt
│               ├── evaluate.md         # AI评估 Agent prompt
│               └── report.md           # 报告生成 Agent prompt
│
├── src/                              # Python 工具层
│   ├── __init__.py
│   ├── crawler.py                    # 爬虫模块
│   ├── filters.py                    # 确定性过滤
│   └── cli.py                        # CLI 入口
│
├── config/
│   ├── companies.yaml                # 公司列表（自动生成）
│   └── agent.yaml                    # Agent 配置
│
├── profiles/                         # 求职意向配置
│   ├── pm_tob.md
│   └── ai_pm.md
│
├── resumes/                          # 简历文件（多格式）
│   ├── pm_tob.md
│   ├── ai_pm.pdf
│   └── data_analyst.docx
│
├── memory/                           # Memory 存储
│   ├── seen_jobs.md                  # 去重 + 历史记录
│   └── company_cache.md              # 公司背调缓存
│
├── companies.md                      # 公司列表（用户编辑）
├── data/                             # 去重数据（旧格式，迁移后删除）
└── output/                           # 输出报告
```

---

## 4. 用户可编辑文件

| 文件 | 用途 | 格式 |
|------|------|------|
| `profiles/*.md` | 求职意向配置 | Markdown + frontmatter |
| `resumes/*` | 简历文件 | md/pdf/docx/txt |
| `companies.md` | 公司列表 | Markdown |
| `config/agent.yaml` | Agent 配置 | YAML |

---

## 5. 配置设计

### 5.1 求职意向配置 (profiles/pm_tob.md)

```markdown
---
name: 产品经理-TOB方向
enabled: true
job_type: 社招
resume: resumes/pm_tob.md
keywords:
  - 产品经理
  - TOB
  - SaaS
---

# 求职意向

寻找 TOB SaaS 产品经理岗位，偏好企业服务、AI方向。
有 5 年产品经验，期望薪资 30-50K，工作地点北京。
```

### 5.2 公司列表 (companies.md)

```markdown
# 公司列表

## 已启用
- 腾讯
- 字节跳动
- 美团

## 待开发
- 阿里巴巴
- 百度
```

### 5.3 Agent 配置 (config/agent.yaml)

```yaml
# Agent 决策配置
decision_level: "moderate"  # conservative / moderate / aggressive

# 模型选择策略
model_strategy:
  simple_tasks: "haiku"      # 简单任务：过滤、清洗
  complex_tasks: "sonnet"    # 复杂任务：评估、报告

# 语义过滤阈值（按决策级别）
semantic_filter:
  conservative: 0.8          # 匹配度 >= 80% 才保留
  moderate: 0.6              # 匹配度 >= 60%
  aggressive: 0.4            # 匹配度 >= 40%

# 输出配置
output:
  max_jobs_per_report: 20    # 每份报告最多岗位数
  include_company_background: true  # 是否包含公司背调
```

---

## 6. CLI 命令设计

```bash
# 基础用法
python -m src.cli run --profile pm_tob

# 指定决策级别
python -m src.cli run --profile pm_tob --level conservative
python -m src.cli run --profile pm_tob --level aggressive

# 指定评分阈值
python -m src.cli run --profile pm_tob --min-score 70
python -m src.cli run --profile pm_tob --min-score 0  # 输出所有

# 指定岗位类型
python -m src.cli run --profile pm_tob --job-type social

# 指定公司
python -m src.cli run --profile pm_tob --companies 腾讯,字节跳动

# 其他命令
python -m src.cli list-profiles          # 列出所有意向
python -m src.cli list-companies         # 列出所有公司
python -m src.cli sync-companies         # 同步 companies.md → companies.yaml
python -m src.cli stats                  # 查看统计
```

### CLI 参数总览

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--profile` | `-p` | 指定求职意向 | 所有启用的 |
| `--job-type` | `-t` | 岗位类型 | 配置文件中的值 |
| `--level` | `-l` | 决策级别 | moderate |
| `--min-score` | `-s` | 最低评分 | 0（输出所有） |
| `--companies` | `-c` | 指定公司 | 所有启用的 |
| `--max-jobs` | `-m` | 最大岗位数 | 50 |
| `--no-background` | | 跳过公司背调 | false |

---

## 7. Memory 设计

### 7.1 存储结构

```
memory/
├── seen_jobs.md          # 去重 + 历史记录
└── company_cache.md      # 公司背调缓存
```

### 7.2 seen_jobs.md 格式

```markdown
# 已处理岗位记录

## 腾讯
- [x] AI产品经理 | 2026-04-10 | 85分 | [投递] | hash:abc123
- [ ] 数据产品经理 | 2026-04-09 | 72分 | [忽略] | hash:def456

## 字节跳动
- [x] 产品经理-TOB | 2026-04-10 | 90分 | [投递] | hash:ghi789
```

### 7.3 查询方式

| 需求 | 查询方式 |
|------|---------|
| 精确去重 | `grep "hash:abc123"` 或加载 hash 到 set |
| 投过哪些公司 | `grep "^\[x\]"` 或 qmd 搜索 |
| 某公司历史 | qmd 搜索公司名 |
| 高分岗位 | qmd 搜索分数模式 |

### 7.4 扩展预留

> 当前使用 Markdown + qmd 方案，满足精确匹配和历史查询需求。
>
> **未来可升级方案：**
> - 向量数据库 (Chroma/Qdrant)：支持语义检索、相似岗位推荐
> - 混合检索：精确 + 语义，优化匹配评分
> - RAG：检索增强生成，更智能的上下文注入
>
> **升级触发条件：**
> - 数据量 > 10000 条
> - 需要语义去重（相似岗位识别）
> - 需要基于历史优化匹配评分

---

## 8. Pipeline 流程设计

### 8.1 整体流程

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: 准备阶段 (Python 确定性)                           │
├─────────────────────────────────────────────────────────────┤
│  Step 1: 加载配置                                           │
│          - 读取 profiles/*.md                               │
│          - 读取 companies.md → 同步到 companies.yaml        │
│          - 读取 config/agent.yaml                           │
│                                                             │
│  Step 2: 抓取岗位                                           │
│          - 遍历启用的公司                                    │
│          - Playwright + API 拦截                            │
│          - 输出: List[Job]                                  │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: 过滤阶段 (Python + Agent 混合)                     │
├─────────────────────────────────────────────────────────────┤
│  Step 3: 时间过滤 (Python)                                  │
│          - 最近 N 天                                        │
│                                                             │
│  Step 4: 精确去重 (Python)                                  │
│          - hash in seen_jobs.md                             │
│                                                             │
│  Step 5: 语义过滤 ⭐ Agent                                   │
│          - 理解求职意向                                      │
│          - 判断岗位是否匹配 (语义级别)                        │
│          - 输出: 匹配度 + 理由                               │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: 评估阶段 (Agent 智能)                              │
├─────────────────────────────────────────────────────────────┤
│  Step 6: 数据清洗 (Python)                                  │
│          - 文本截断、标准化                                  │
│                                                             │
│  Step 7: AI 评估 ⭐ Agent (两阶段)                           │
│          - Stage 1: 简历深度分析 → 能力画像                  │
│          - Stage 2: 岗位匹配评估 → 评分 + 建议               │
│          - 公司背调 (可选)                                   │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 4: 输出阶段 (Agent 智能)                              │
├─────────────────────────────────────────────────────────────┤
│  Step 8: 生成报告 ⭐ Agent                                   │
│          - Markdown 格式                                    │
│          - 个性化内容、投递建议                              │
│                                                             │
│  Step 9: 更新 Memory (Python)                               │
│          - 追加到 seen_jobs.md                              │
│          - 更新 company_cache.md (可选)                     │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Agent 驱动的核心步骤

| Step | Agent 任务 | 输入 | 输出 |
|------|-----------|------|------|
| **语义过滤** | 判断岗位是否匹配求职意向 | 意向描述 + 岗位 JD | 匹配度 (0-1) + 理由 |
| **AI 评估** | 深度分析匹配度 | 简历 + 岗位 JD + 公司信息 | 评分 (0-100) + 分析 |
| **生成报告** | 个性化输出 | 岗位列表 + 评估结果 | Markdown 报告 |

---

## 9. Step 5: 语义过滤详细设计

### 9.1 目标

从"关键词匹配"升级为"语义理解匹配"，判断岗位是否真正符合求职意向。

### 9.2 输入输出

```
输入:
- profile.intent: 求职意向描述
- profile.keywords: 关键词列表
- job: 岗位信息

输出:
- match_score: 0.0 - 1.0
- match_reason: 匹配理由
- should_keep: true/false
```

### 9.3 Prompt 设计

```markdown
# 语义过滤 Agent

你是一个求职匹配专家，判断岗位是否符合求职者的意向。

## 求职意向
{intent}

## 关键词参考
{keywords}

## 岗位信息
- 标题: {title}
- 公司: {company}
- 地点: {location}
- 类别: {category}

## 岗位描述
{duty}

---

请判断这个岗位是否匹配求职意向。

**注意：**
- 不要只看标题，要理解岗位描述的实际内容
- 标题可能不完全匹配，但职责符合也算匹配
- 例如：求职"产品经理"，"产品策划"、"产品运营"如果职责类似也算匹配

**输出格式 (JSON):**
\`\`\`json
{
  "match_score": 0.8,
  "match_reason": "岗位是TOB SaaS产品方向，符合求职者的企业服务偏好",
  "should_keep": true,
  "concerns": ["地点在上海，求职者期望北京"]
}
\`\`\`

**评分标准:**
- 0.8-1.0: 高度匹配
- 0.6-0.8: 基本匹配
- 0.4-0.6: 部分匹配
- 0.0-0.4: 不匹配
```

### 9.4 过滤逻辑

```python
# 根据 decision_level 决定阈值
thresholds = {
    "conservative": 0.8,
    "moderate": 0.6,
    "aggressive": 0.4
}

def should_keep(result, level):
    return result["match_score"] >= thresholds[level]
```

---

## 10. Step 7: AI 评估详细设计

### 10.1 核心改进

```
❌ 旧方案: 技能关键词匹配
   - 简历有"Python" → JD要求Python → 匹配
   - 简历没有"SQL" → JD要求SQL → 不匹配

✅ 新方案: 经历深度分析
   - 简历有"搭建数据看板，分析用户行为" → 推断懂SQL/数据分析 → 匹配
   - 简历有"主导产品从0到1上线" → 推断有项目管理能力 → 匹配
```

### 10.2 两阶段评估

```
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: 简历深度分析                                       │
├─────────────────────────────────────────────────────────────┤
│  目标: 从简历经历中提取显性 + 隐性能力                        │
│  输入: 简历内容                                              │
│  输出: 能力画像 (显性技能 + 隐性能力 + 经验亮点)              │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: 岗位匹配评估                                       │
├─────────────────────────────────────────────────────────────┤
│  目标: 能力画像 vs JD 要求                                   │
│  输入: 能力画像 + 岗位 JD                                    │
│  输出: 评分 + 匹配分析 + 建议                                 │
└─────────────────────────────────────────────────────────────┘
```

### 10.3 Stage 1: 简历深度分析 Prompt

```markdown
# 简历深度分析 Agent

你是一个资深HR，擅长从简历中挖掘候选人的真实能力。

## 简历内容
{resume}

---

请深度分析这份简历，提取候选人的能力画像。

**分析要点:**
1. **显性技能** - 简历明确写出的技能
2. **隐性能力** - 从经历推断的能力（即使没明说）
3. **经验亮点** - 最有竞争力的经历
4. **潜在短板** - 可能欠缺的方面

**隐性能力推断示例:**
- "搭建数据看板" → 推断: 数据分析能力、可能懂SQL
- "主导产品0-1上线" → 推断: 项目管理能力、产品规划能力
- "跨部门协调资源" → 推断: 沟通能力、推动能力
- "负责3人团队" → 推断: 团队管理经验
- "优化流程提升效率30%" → 推断: 数据驱动、流程优化能力

**输出格式 (JSON):**
\`\`\`json
{
  "explicit_skills": ["产品规划", "需求分析", "Axure", "SQL"],
  "implicit_abilities": [
    {
      "ability": "项目管理",
      "evidence": "主导过3个产品从0到1上线",
      "confidence": "high"
    },
    {
      "ability": "数据分析",
      "evidence": "搭建用户行为分析看板，指导产品迭代",
      "confidence": "medium"
    }
  ],
  "highlights": [
    "5年TOB产品经验，有完整的产品生命周期经验",
    "有AI产品落地经验，熟悉大模型应用场景"
  ],
  "potential_gaps": [
    "简历未体现团队管理经验",
    "技术背景较弱，可能影响与技术团队沟通"
  ],
  "career_summary": "资深TOB产品经理，擅长数据驱动决策，有AI产品经验"
}
\`\`\`
```

### 10.4 Stage 2: 岗位匹配评估 Prompt

```markdown
# 岗位匹配评估 Agent

你是一个资深招聘顾问，评估候选人与岗位的匹配度。

## 候选人能力画像
{ability_profile}

## 求职意向
{intent}

## 岗位信息
- 标题: {title}
- 公司: {company}
- 地点: {location}

## 岗位职责
{duty}

## 任职要求
{requirement}

---

请评估候选人与岗位的匹配度。

**评估要点:**
1. 对比能力画像与JD要求，区分"明确具备"和"可能具备"
2. 识别能力亮点是否契合岗位核心需求
3. 分析潜在短板是否影响岗位核心职责
4. 给出投递建议和准备方向

**输出格式 (JSON):**
\`\`\`json
{
  "score": 85,
  "match_analysis": {
    "strong_matches": [
      {
        "requirement": "5年产品经验",
        "candidate_evidence": "5年TOB产品经验，完整产品生命周期",
        "match_level": "strong"
      }
    ],
    "potential_matches": [
      {
        "requirement": "数据分析能力",
        "candidate_evidence": "搭建过用户行为分析看板（隐性能力）",
        "match_level": "potential",
        "suggestion": "面试时可展开讲数据分析案例"
      }
    ],
    "gaps": [
      {
        "requirement": "熟悉SQL",
        "gap_type": "uncertain",
        "suggestion": "简历未明确体现，建议确认或补充学习"
      }
    ]
  },
  "match_reasons": [
    "TOB产品经验丰富，与岗位方向高度契合",
    "有AI产品落地经验，满足JD的AI方向要求"
  ],
  "suggestions": [
    "投递时重点突出TOB SaaS项目经验",
    "面试准备: 准备数据分析案例"
  ],
  "risk_warning": null,
  "recommendation": "强烈推荐投递"
}
\`\`\`

**评分标准:**
- 90-100: 完美匹配，核心竞争力完全契合
- 75-89: 高度匹配，核心能力满足
- 60-74: 基本匹配，主要能力满足
- 40-59: 部分匹配，有差距但有机会
- 0-39: 不太匹配，核心能力差距较大
```

### 10.5 能力画像缓存

```
简历深度分析只需做一次，结果可缓存:

memory/profile_cache.md

## pm_tob 能力画像
- 显性技能: ...
- 隐性能力: ...
- 分析时间: 2026-04-10
- 简历hash: abc123 (用于检测简历是否更新)

下次评估时:
- 简历未更新 → 直接读取缓存的能力画像
- 简历已更新 → 重新分析
```

### 10.6 公司背调 (可选)

```markdown
# 公司背调子任务

当 config.agent.output.include_company_background = true 时触发。

## 任务
搜索 {company} 的以下信息：
1. 公司规模、主营业务
2. 近期新闻（融资、裁员、业务调整）
3. 该部门/团队情况（如果能找到）
4. 面试评价（牛客、脉脉等）

## 输出格式
\`\`\`json
{
  "company": "字节跳动",
  "summary": "互联网大厂，主要业务抖音、TikTok",
  "recent_news": ["2026年3月完成新一轮融资"],
  "team_info": "飞书团队，企业协作方向",
  "interview_reviews": "面试流程规范，3-4轮",
  "risk_level": "low"
}
\`\`\`

**风险等级:**
- low: 公司稳定，推荐投递
- medium: 有一些风险因素，建议了解
- high: 风险较大，慎重考虑
```

---

## 11. Step 8: 报告生成详细设计

### 11.1 目标

生成个性化、易读的 Markdown 报告，包含评估结果和投递建议。

### 11.2 输入输出

```
输入:
- profile: 求职意向信息
- jobs: 岗位列表 (含评估结果)
- stats: 统计信息 (总数、过滤数、匹配数)

输出:
- Markdown 报告文件
```

### 11.3 Prompt 设计

```markdown
# 报告生成 Agent

你是一个求职顾问，为求职者生成清晰、实用的岗位推荐报告。

## 求职意向
- 名称: {profile_name}
- 类型: {job_type}
- 描述: {intent}

## 统计信息
- 抓取岗位: {total_jobs}
- 过滤后: {filtered_jobs}
- 匹配岗位: {matched_jobs}

## 岗位列表 (含评估结果)
{jobs_with_evaluations}

---

请生成一份 Markdown 格式的求职报告。

**报告要求:**
1. 结构清晰，重点突出
2. 按评分从高到低排序
3. 每个岗位包含: 基本信息、匹配分析、投递建议
4. 末尾添加总结和行动建议

**输出格式:**
\`\`\`markdown
# 求职巡检报告

> 生成时间: {datetime}
> 求职意向: {profile_name}
> 岗位类型: {job_type}

## 📊 本次巡检统计

| 指标 | 数量 |
|------|------|
| 抓取岗位 | {total} |
| 时间过滤后 | {after_time} |
| 去重后 | {after_dedup} |
| 匹配岗位 | {matched} |

---

## 🎯 推荐岗位

### 1. AI产品经理 🟢 89分

**基本信息**
| 字段 | 内容 |
|------|------|
| 公司 | 腾讯 |
| 地点 | 北京 |
| 部门 | 飞书团队 |
| 发布时间 | 2026-04-10 |

**匹配分析**
- ✅ 5年TOB产品经验，满足岗位核心要求
- ✅ 有AI产品落地经验，与岗位方向高度契合
- ⚠️ SQL技能未明确体现，建议补充

**投递建议**
> 重点突出AI产品落地经验，面试时准备数据分析案例展示数据驱动能力。

**岗位职责** (摘要)
> 负责AI产品的规划与设计，推动大模型在业务场景的落地应用...

**链接**: [查看详情](https://...)

---

## 📝 总结与建议

### 本次亮点
- 发现 {high_score_count} 个高分岗位

### 行动建议
1. 优先投递: 腾讯-AI产品经理 (89分)
2. 需要准备: SQL基础学习

---

*报告由 SmartJobHunter Agent 生成*
\`\`\`
```

### 11.4 报告文件命名

```
output/{date}_{profile_name}.md

示例:
output/20260410_产品经理-TOB方向.md
```

---

## 12. Skills 工具定义

### 12.1 skill.md (Agent 主入口)

```markdown
---
name: jobhunter
description: 智能求职巡检 Agent
---

# SmartJobHunter Agent

## 状态机流程

\`\`\`
INIT → LOADED → CRAWLED → FILTERED → EVALUATED → REPORTED → DONE
\`\`\`

---

### INIT

**目标**: 初始化并加载所有配置

**执行动作**:
1. 调用 `load_config` 工具
2. 读取 `profiles/{profile_name}.md` 获取求职意向
3. 读取 `resumes/{resume_file}` 获取简历内容
4. 读取 `companies.md` 获取公司列表
5. 读取 `config/agent.yaml` 获取 Agent 配置

**输出变量**:
\`\`\`
profile = {name, intent, keywords, job_type, resume_path}
resume = "简历文本内容"
companies = ["腾讯", "字节跳动", "美团"]
agent_config = {decision_level, model_strategy, ...}
\`\`\`

**完成条件**: 所有配置加载成功，无缺失文件

**状态转换**: → LOADED

---

### LOADED

**目标**: 抓取岗位数据

**执行动作**:
1. 调用 `crawl` 工具，传入 companies 和 job_type
2. 等待爬虫完成，获取岗位列表

**输入变量**: companies, job_type

**输出变量**:
\`\`\`
jobs = [
  {title, company, location, duty, requirement, url, hash, ...},
  ...
]
\`\`\`

**完成条件**: jobs 列表不为空（或确认无新岗位）

**状态转换**: → CRAWLED

---

### CRAWLED

**目标**: 过滤岗位（确定性 + 语义）

**执行动作**:
1. 调用 `filter_by_time` 工具，传入 jobs 和 time_filter_days
2. 调用 `dedup` 工具，传入过滤后的 jobs，读取 memory/seen_jobs.md
3. 对每个剩余岗位，执行语义过滤:
   - 使用 `semantic_filter` prompt
   - 输入: profile.intent, profile.keywords, job
   - 输出: match_score, match_reason, should_keep
4. 根据 decision_level 阈值过滤

**输入变量**: jobs, profile, agent_config.decision_level

**输出变量**:
\`\`\`
matched_jobs = [
  {job, match_score, match_reason},
  ...
]
\`\`\`

**完成条件**: 所有岗位完成语义过滤判断

**状态转换**: → FILTERED

---

### FILTERED

**目标**: 深度评估匹配岗位

**执行动作**:
1. 调用 `clean_data` 工具，截断过长文本
2. 检查 memory/profile_cache.md 是否有缓存的能力画像
   - 有缓存且简历未更新 → 直接使用
   - 无缓存 → 执行简历分析
3. 执行简历分析:
   - 使用 `analyze_resume` prompt
   - 输入: resume
   - 输出: ability_profile
4. 对每个 matched_job 执行岗位评估:
   - 使用 `evaluate` prompt
   - 输入: ability_profile, job
   - 输出: score, match_analysis, suggestions
5. (可选) 执行公司背调:
   - 使用 `company_background` prompt
   - 输入: company
   - 输出: company_info

**输入变量**: matched_jobs, resume, ability_profile (cached or new)

**输出变量**:
\`\`\`
evaluations = [
  {
    job: {...},
    score: 85,
    match_analysis: {...},
    suggestions: [...],
    company_info: {...}  // 可选
  },
  ...
]
\`\`\`

**完成条件**: 所有 matched_jobs 完成评估

**状态转换**: → EVALUATED

---

### EVALUATED

**目标**: 生成报告

**执行动作**:
1. 按评分从高到低排序 evaluations
2. 执行报告生成:
   - 使用 `report` prompt
   - 输入: profile, evaluations, stats
   - 输出: markdown 报告内容
3. 调用 `save_report` 工具，写入 output/{date}_{profile_name}.md

**输入变量**: profile, evaluations

**输出变量**:
\`\`\`
report_path = "output/20260410_产品经理-TOB方向.md"
\`\`\`

**完成条件**: 报告文件写入成功

**状态转换**: → REPORTED

---

### REPORTED

**目标**: 更新 Memory

**执行动作**:
1. 调用 `update_memory` 工具
2. 将处理的岗位追加到 memory/seen_jobs.md
3. (可选) 更新 memory/company_cache.md
4. (如有) 更新 memory/profile_cache.md

**输入变量**: jobs, evaluations

**完成条件**: Memory 文件更新成功

**状态转换**: → DONE

---

### DONE

**目标**: 完成

**输出**:
\`\`\`
✅ 巡检完成
📄 报告: output/20260410_产品经理-TOB方向.md
📊 匹配岗位: 5 个
🎯 最高分: 腾讯-AI产品经理 (89分)
\`\`\`

---

## 执行日志格式

每个状态转换时输出:
\`\`\`
[INIT] 开始加载配置...
[LOADED] ✓ 配置加载完成 (profile: 产品经理-TOB, companies: 3)
[CRAWLED] ✓ 抓取完成 (50 个岗位)
[FILTERED] ✓ 过滤完成 (时间:50 → 去重:45 → 语义:12)
[EVALUATED] ✓ 评估完成 (12 个岗位)
[REPORTED] ✓ 报告生成: output/20260410_产品经理-TOB方向.md
[DONE] ✅ 巡检完成
\`\`\`

---

## 错误处理

如果某状态执行失败:
1. 输出错误信息: `[ERROR] 状态: XXX, 错误: ...`
2. 停止执行，不进入下一状态
3. 提示用户检查配置或重试
```

### 12.2 工具定义文件

#### tools/load_config.md

```markdown
---
name: load_config
description: 加载所有配置文件
---

# load_config 工具

## 功能
加载求职意向、简历、公司列表、Agent配置

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| profile_name | string | 否 | 指定意向名称，为空则加载所有启用的 |

## 输出
```json
{
  "profile": {...},
  "resume": "...",
  "companies": [...],
  "agent_config": {...}
}
```

## 实现位置
`src/cli.py` → `load_config()`
```

#### tools/crawl.md

```markdown
---
name: crawl
description: 抓取岗位数据
---

# crawl 工具

## 功能
从配置的公司招聘网站抓取岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| companies | list | 是 | 公司列表 |
| job_type | string | 否 | 岗位类型 (social/campus/internship) |
| max_jobs | int | 否 | 每个公司最大岗位数，默认50 |

## 输出
```json
[
  {
    "title": "AI产品经理",
    "company": "腾讯",
    "location": "北京",
    "duty": "...",
    "requirement": "...",
    "url": "...",
    "hash": "abc123"
  }
]
```

## 实现位置
`src/crawler.py` → `crawl_company()`
```

#### tools/filter.md

```markdown
---
name: filter_by_time
description: 时间过滤
---

# filter_by_time 工具

## 功能
过滤最近N天的岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| days | int | 否 | 最近N天，默认3 |

## 输出
过滤后的岗位列表

## 实现位置
`src/filters.py` → `filter_by_time()`
```

```markdown
---
name: dedup
description: 去重过滤
---

# dedup 工具

## 功能
排除已处理过的岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |

## 输出
去重后的岗位列表

## 实现位置
`src/filters.py` → `dedup()`
```

```markdown
---
name: clean_data
description: 数据清洗
---

# clean_data 工具

## 功能
清洗和标准化岗位数据

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| truncate_length | int | 否 | 文本截断长度，默认6000 |

## 输出
清洗后的岗位列表

## 实现位置
`src/filters.py` → `clean_data()`
```

#### tools/update_memory.md

```markdown
---
name: update_memory
description: 更新 Memory
---

# update_memory 工具

## 功能
将处理的岗位追加到 memory/seen_jobs.md

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| evaluations | list | 是 | 评估结果 |

## 输出
成功/失败状态

## 实现位置
`src/filters.py` → `update_memory()`
```

---

## 13. 公司列表同步机制

### 13.1 companies.md 格式

```markdown
# 公司列表

## 已启用

### 腾讯
- 社招: https://careers.tencent.com/search.html
- 校招: https://careers.tencent.com/search.html

### 字节跳动
- 社招: https://jobs.bytedance.com/experienced/position
- 校招: https://jobs.bytedance.com/campus/position

### 美团
- 社招: https://zhaopin.meituan.com/jobs
- 校招: https://zhaopin.meituan.com/campus

## 待开发

### 阿里巴巴
- 社招: https://talent.alibaba.com/off-campus/position-list
- 校招: https://talent.alibaba.com/campus/position-list

### 百度
- 社招: https://talent.baidu.com/jobs/list
```

### 13.2 同步逻辑

```python
def sync_companies():
    """
    1. 读取 companies.md
    2. 解析 Markdown 结构（公司名 + 链接）
    3. 与 companies.yaml 合并:
       - 已存在的公司: 更新 enabled 和 urls
       - 新公司: 添加到列表，enabled=false，需要后续实现爬虫
    4. 写入 config/companies.yaml
    """
    
    # 解析 companies.md
    user_companies = parse_companies_md("companies.md")
    # 返回: [
    #   {"name": "腾讯", "enabled": True, "urls": {"social": "...", "campus": "..."}},
    #   {"name": "阿里巴巴", "enabled": False, "urls": {...}},
    # ]
    
    # 读取完整配置
    full_config = load_yaml("config/companies.yaml")
    
    # 合并
    merged = merge_companies(full_config, user_companies)
    
    # 写回
    save_yaml("config/companies.yaml", merged)
```

### 13.3 合并策略

| 情况 | 处理方式 |
|------|---------|
| 公司已存在于 yaml | 更新 enabled 和 urls |
| 公司不存在于 yaml | 新增，设置 enabled=false，标记"需要实现爬虫" |
| yaml 中有但 md 中没有 | 保持原样（可能是待开发的公司） |

### 13.4 同步时机

| 时机 | 触发方式 |
|------|---------|
| 执行前 | `python -m src.cli run` 自动同步 |
| 手动同步 | `python -m src.cli sync-companies` |
| 添加新公司 | 用户编辑 companies.md 后自动同步 |

---

## 14. 简历解析模块改造

### 14.1 改造目标

| 改造点 | 说明 |
|--------|------|
| **支持图片** | 新增图片格式支持 (png/jpg) |
| **计算 hash** | 用于检测简历是否更新 |
| **缓存能力画像** | 解析后自动缓存到 memory/profile_cache.md |

### 14.2 改造后设计

```python
# src/resume_parser.py

def parse_resume(file_path: str) -> dict:
    """
    解析简历文件
    
    Returns:
        {
            "content": "简历文本内容",
            "format": "md",
            "hash": "abc123",
            "length": 2000
        }
    """
    ext = Path(file_path).suffix.lower()
    content = _parse_by_format(file_path, ext)
    
    return {
        "content": content,
        "format": ext,
        "hash": hashlib.md5(content.encode()).hexdigest(),
        "length": len(content)
    }

def _parse_by_format(file_path: str, ext: str) -> str:
    """根据格式解析"""
    parsers = {
        '.txt': _parse_txt,
        '.md': _parse_txt,
        '.docx': _parse_docx,
        '.pdf': _parse_pdf,
        '.png': _parse_image,  # 新增
        '.jpg': _parse_image,  # 新增
        '.jpeg': _parse_image, # 新增
    }
    
    parser = parsers.get(ext)
    if not parser:
        raise ValueError(f"不支持的格式: {ext}")
    
    return parser(file_path)

def _parse_image(file_path: str) -> str:
    """解析图片简历 (使用 Claude Vision)"""
    import base64
    
    with open(file_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode()
    
    # 调用 Claude Vision API
    response = client.messages.create(
        model="claude-sonnet-4-6",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                {"type": "text", "text": "请提取这张简历图片中的所有文字内容，保持原有格式。"}
            ]
        }]
    )
    
    return response.content[0].text
```

---

## 15. 迁移方案

### 15.1 Git 分支策略

```
当前 main 分支
      │
      ├──→ 创建 backup/legacy-python 分支（保存原有代码）
      │
      └──→ main 分支（更新为 Agent 架构）
```

### 15.2 文件迁移对照

| 当前文件 | 迁移后位置 | 处理方式 |
|---------|-----------|---------|
| `spider.py` | `src/crawler.py` | 重构，保留爬虫逻辑 |
| `main.py` (过滤部分) | `src/filters.py` | 提取过滤函数 |
| `main.py` (评估部分) | 删除 | 由 Agent prompt 替代 |
| `main.py` (报告部分) | 删除 | 由 Agent prompt 替代 |
| `resume_parser.py` | `src/resume_parser.py` | 改造，增加 hash 和图片支持 |
| `scheduler.py` | `src/scheduler.py` | 保留，调用新的 CLI |
| `health_check.py` | `src/health_check.py` | 保留 |
| `git_auto_push.py` | `src/git_auto_push.py` | 保留 |
| `config.yaml` | `profiles/*.md` | 拆分为多个意向文件 |
| `companies.yaml` | `config/companies.yaml` | 移动到 config/ |
| `data/seen_jobs.jsonl` | `memory/seen_jobs.md` | 格式转换 |

### 15.3 迁移步骤

```
Step 1: 备份原有代码
├── git checkout -b backup/legacy-python
├── git push origin backup/legacy-python
└── git checkout main

Step 2: 创建新目录结构
├── mkdir -p src/ .claude/skills/jobhunter/tools .claude/skills/jobhunter/prompts
├── mkdir -p memory/ config/ profiles/

Step 3: 迁移 Python 代码
├── spider.py → src/crawler.py (重构)
├── 提取过滤函数 → src/filters.py
├── resume_parser.py → src/resume_parser.py (改造)
├── 创建 src/cli.py (新)
└── scheduler.py → src/scheduler.py (调整)

Step 4: 创建 Skills 文件
├── skill.md
├── tools/*.md
└── prompts/*.md

Step 5: 迁移配置文件
├── config.yaml → profiles/*.md (拆分)
├── companies.yaml → config/companies.yaml
└── 创建 config/agent.yaml

Step 6: 迁移数据文件
├── data/seen_jobs.jsonl → memory/seen_jobs.md
└── 简历文件 → resumes/

Step 7: 清理旧文件
├── 删除 main.py
├── 删除旧 config.yaml
└── 删除 data/ 目录

Step 8: 提交到 main
├── git add .
├── git commit -m "refactor: 重构为 Agent 架构"
└── git push origin main
```

### 15.4 数据迁移脚本

```python
# scripts/migrate.py

def migrate_seen_jobs():
    """迁移去重数据: jsonl → md"""
    old_file = "data/seen_jobs.jsonl"
    new_file = "memory/seen_jobs.md"
    
    # 按公司分组
    companies = {}
    
    with open(old_file, 'r') as f:
        for line in f:
            record = json.loads(line)
            company = record.get('company', '未知')
            if company not in companies:
                companies[company] = []
            companies[company].append(record)
    
    # 写入 Markdown
    with open(new_file, 'w') as f:
        f.write("# 已处理岗位记录\n\n")
        for company, jobs in companies.items():
            f.write(f"## {company}\n")
            for job in jobs:
                status = "[x]" if job.get('applied') else "[ ]"
                f.write(f"- {status} {job['title']} | {job['date']} | {job['score']}分 | hash:{job['hash']}\n")
            f.write("\n")

def migrate_config_to_profiles():
    """迁移配置: config.yaml → profiles/*.md"""
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    for profile in config.get('profiles', []):
        name = profile.get('name', 'unknown')
        filename = name.replace('/', '-').replace(' ', '_')
        
        # 生成 Markdown 文件
        md_content = f"""---
name: {profile.get('name')}
enabled: {profile.get('enabled', True)}
job_type: {profile.get('job_type', '社招')}
resume: {profile.get('resume_path', '')}
keywords:
{yaml.dump(profile.get('keywords', []), default_flow_style=False)}
---

# 求职意向

{profile.get('intent', '')}
"""
        
        with open(f"profiles/{filename}.md", 'w') as f:
            f.write(md_content)
```

---

## 16. 设计完成检查清单

- [x] 设计目标
- [x] 架构设计
- [x] 目录结构
- [x] 配置设计
- [x] CLI 命令设计
- [x] Memory 设计
- [x] Pipeline 流程设计
- [x] Step 5 语义过滤详细设计
- [x] Step 7 AI 评估详细设计
- [x] Step 8 报告生成详细设计
- [x] Skills 工具定义
- [x] 公司列表同步机制
- [x] 简历解析模块改造
- [x] 迁移方案

---

## 9. 设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 架构模式 | 混合模式 | Python 工具层 + Skills 智能层 |
| Agent 调用方式 | 一次性执行 | 用户无需交互，自动完成 |
| Skills 发布形式 | 团队共享 + 公开发布 | 放在 .claude/skills/ |
| Agent 决策权 | 可配置 | conservative/moderate/aggressive |
| 模型选择 | 动态选择 | 简单任务 Haiku，复杂任务 Sonnet |
| 意向配置格式 | Markdown + frontmatter | 统一格式，易编辑 |
| 简历存储 | 分离存储 | 支持 pdf/docx/图片 等多格式 |
| Memory 格式 | Markdown | 可读、可搜索、qmd 支持 |
| 去重方案 | Markdown + qmd | 满足精确匹配，未来可升级 |
