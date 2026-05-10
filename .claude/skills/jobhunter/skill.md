---
name: jobhunter
description: 智能求职巡检 Agent
user_invocable: true
---

# SmartJobHunter Agent

基于 Agent 平台的智能求职巡检系统。Python 负责抓取、清洗、fallback 粗筛和报告落盘；候选人画像、岗位画像、语义过滤和最终匹配判断由当前 Claude/Codex agent 执行。

## 快速开始

用户说"运行巡检"、"找工作"或"帮我看看有什么岗位"时，按以下流程执行：

如果用户说"分析简历"、"这个岗位适合我吗"、"评估岗位"，先走 `profile.md` 和 `match.md`，不要直接套用产品经理示例。

---

## 状态机流程

```
INIT → LOADED → STRATEGY_INSPECTED → CRAWLED → FILTERED → EVALUATED → URL_VALIDATED → REPORTED → PACKAGED → DONE
```

---

### INIT

**目标**: 初始化并加载所有配置

**执行动作**:
1. 调用 `load_config` 工具
2. 读取 `profiles/*.md` 获取求职意向；每个文件的 `_profile_id` 是独立巡检任务 ID
3. 读取 `resumes/{resume_file}` 获取简历内容
4. 读取 `config/companies.yaml` 获取公司列表
5. 读取 `config/agent.yaml` 获取 Agent 配置

**输出变量**:
```
profile = {name, target_roles, must_have, nice_to_have, avoid, intent, resume_path}
resume = "简历文本内容"
companies = ["腾讯", "字节跳动"]
candidate_profile = {role_experience, skills, project_evidence, constraints}
agent_config = {decision_level, model_strategy, ...}
```

**完成条件**: 所有配置加载成功，无缺失文件

**状态转换**: → LOADED

---

### LOADED

**目标**: 每日策略巡检，确认公司链接和抓取策略是否可用

**执行动作**:
1. 运行 `python -m src.health_monitor --inspect-strategies --keyword "<关键词>" --job-type <social|campus|internship>`。
2. 对 `collect_evidence` 或 `blocked` 结果，读取 `logs/strategy_tasks/.../task.json`。
3. 如果有 evidence 目录，读取 `evidence.json`、`network.json`、`page.html/page.txt`、`page.png`。
4. 当前 Agent 判断策略类型并修改 `config/companies.yaml` 或 `src/site_strategies/*.py`。
5. 修改后运行单公司验证：`python tests/test_all_crawlers.py --company <id> --keyword "<关键词>" --max-jobs 3`。
6. 当前公司无法处理时跳过，继续其他公司，最终汇总原因。

**策略类型**:
`config_intercept`、`config_dom`、`legacy_python`、`custom_python`、`browser_operation`、`unsupported`。

**职责边界**:
- Python 负责采集证据、生成 task、执行已固化策略。
- 当前 Claude/Codex Agent 负责分析证据和修改配置/代码。
- Python 不调用外部大模型 API。

**状态转换**: → STRATEGY_INSPECTED

---

### STRATEGY_INSPECTED

**目标**: 抓取岗位数据

**执行动作**:
1. 调用 `crawl` 工具，传入 companies、job_type 和已确认可用的 strategy。
2. 对策略未就绪、登录、验证码、反爬的网站跳过，不阻塞其他公司。
3. 等待爬虫完成，获取岗位列表。

**输入变量**: companies, job_type

**输出变量**:
```
jobs = [
  {title, company, location, duty, requirement, url, hash, ...},
  ...
]
```

**完成条件**: jobs 列表不为空（或确认无新岗位）

**状态转换**: → CRAWLED

---

### CRAWLED

**目标**: 过滤岗位（确定性 + 语义）

**执行动作**:
1. 调用 `filter_by_time` 工具，传入 jobs 和 time_filter_days
2. 调用 `dedup` 工具，传入过滤后的 jobs，读取 memory/seen_jobs.md
3. 对每个剩余岗位，执行 AI 语义过滤:
   - 使用 `semantic_filter` prompt
   - 输入: profile.intent, profile.keywords, job
   - 输出: match_score, match_reason, match_reasons, concerns, evidence, should_keep
4. 根据 decision_level 阈值过滤

**判断边界**:
- 时间过滤和去重属于 Python 确定性逻辑。
- 岗位语义是否匹配由 AI 做主判，Python CLI 只提供 `src.matching` fallback。
- 不允许只用关键词命中决定保留；必须看岗位核心职责。

**输入变量**: jobs, profile, agent_config.decision_level

**输出变量**:
```
matched_jobs = [
  {job, match_score, match_reason},
  ...
]
```

**完成条件**: 所有岗位完成语义过滤判断

**状态转换**: → FILTERED

---

### FILTERED

**目标**: 深度评估匹配岗位

**执行动作**:
1. 调用 `clean_data` 工具，截断过长文本
2. 检查 memory/profile_cache.md 是否有缓存的能力画像
3. 执行简历分析 (使用 analyze_resume prompt)
4. 对每个 matched_job 执行岗位评估 (使用 evaluate prompt)

**职责边界**:
- AI 负责匹配判断、简历能力画像、投递建议。
- Python 负责数据清洗、fallback 评分、Markdown 文件落盘。
- ReportGenerator 只做格式化，不替代 AI 判断。

**状态转换**: → EVALUATED

---

### EVALUATED

**目标**: 校验岗位详情链接

**执行动作**:
1. 按评分从高到低排序 evaluations。
2. 生成报告前校验岗位详情 URL。
3. 空链接、404、不可访问链接不要进入最终报告或飞书。
4. 如果链接校验后没有岗位，停止报告生成并说明原因。

**状态转换**: → URL_VALIDATED

---

### URL_VALIDATED

**目标**: 生成日期归档报告

**执行动作**:
1. 执行报告生成（使用 report prompt）。
2. 保存到 `output/{YYYY-MM-DD}/{profile_id}_{YYYYMMDD_HHMM}.md`。
3. 如果 `config/agent.yaml` 中 `feishu.enabled: true` 且 token 完整，可推送到飞书 Wiki/多维表格。
4. 飞书推送开关命令：`python -m src.scheduler --feishu-push status`、`python -m src.scheduler --feishu-push on`、`python -m src.scheduler --feishu-push off`。

**状态转换**: → REPORTED

---

### REPORTED

**目标**: 生成 Top 3 投递包

**执行动作**:
1. 为评分最高的 3 个岗位生成 `index.md` 和 `cover_letter_*.md`。
2. 路径为 `output/{YYYY-MM-DD}/application_packages/{profile_id}_{YYYYMMDD_HHMM}/`。
3. Cover Letter 必须结合公司、岗位、JD 证据、简历证据和风险点，不要写通用模板。

**状态转换**: → PACKAGED

---

### PACKAGED

**目标**: 更新 Memory

**执行动作**:
1. 调用 `update_memory` 工具
2. 将处理的岗位追加到 memory/seen_jobs.md

**状态转换**: → DONE

---

### DONE

**输出**:
```
✅ 巡检完成
📄 报告: output/2026-05-07/pm_tob_20260507_2000.md
📦 投递包: output/2026-05-07/application_packages/pm_tob_20260507_2000/
📊 匹配岗位: 5 个
🎯 最高分: 腾讯-AI产品经理 (89分)
```

---

## 执行日志格式

```
[INIT] 开始加载配置...
[LOADED] ✓ 配置加载完成 (profile: 产品经理-TOB, companies: 2)
[CRAWLED] ✓ 抓取完成 (50 个岗位)
[FILTERED] ✓ 过滤完成 (时间:50 → 去重:45 → 语义:12)
[EVALUATED] ✓ 评估完成 (12 个岗位)
[URL_VALIDATED] ✓ 链接校验完成 (12 → 10)
[REPORTED] ✓ 报告生成: output/2026-05-07/pm_tob_20260507_2000.md
[PACKAGED] ✓ 投递包生成: output/2026-05-07/application_packages/pm_tob_20260507_2000/
[DONE] ✅ 巡检完成
```

---

## 评估命令

每次修改抓取策略、岗位过滤、评分、报告、投递包或本 skill 文档后，运行：

```powershell
python -m src.evaluation --fail-under 1.0
python -m src.evaluation --trials 3 --fail-under 1.0
python -m src.evaluation --dataset evals/capability/jobhunter_hard_cases.yaml
```

默认回归评测集是 `evals/regression/jobhunter_core.yaml`，用于防倒退；`evals/capability/jobhunter_hard_cases.yaml` 用于观察难例和能力边界。

评估结果写入 `output/evals/{YYYY-MM-DD}/{YYYYMMDD_HHMMSS_microseconds}/`，用于检查策略路由、岗位匹配、输出质量和 Agent 指令漂移。这个目录是本地运行产物，不提交 Git。

评估流程：

```text
+----------------+     +-------------------------+     +-------------+
| 评测集 YAML    | --> | 评估 harness            | --> | Case runner |
| regression /   |     | python -m src.evaluation|     | 逐 case 执行|
| capability     |     +-------------------------+     +------+------+
+----------------+                                          |
                                                            |
                         +----------------------------------+------------------+
                         |                                                     |
                         v                                                     v
                  +---------------+                                  +-----------------+
                  | Code graders  |                                  | Transcript JSONL|
                  | pass / fail   |                                  | 可回放轨迹      |
                  +-------+-------+                                  +--------+--------+
                          |                                                   |
                          v                                                   v
                  +---------------+                                  +-----------------+
                  | 指标聚合      |                                  | 失败定位证据    |
                  +-------+-------+                                  +-----------------+
                          |
                          v
                  +------------------------+
                  | Markdown + JSON 报告   |
                  +------------------------+
```

输出含义：

```text
agent_eval_results.json      完整机器可读结果，包含 metrics、graders、case details
agent_eval_report.md         人类可读摘要，列出通过率、失败归因和 transcript 路径
transcripts/<case_id>.jsonl  单 case 执行轨迹，用于失败回放
artifacts/                   投递包类 case 生成的临时产物
wf/                          workflow_outcome case 的报告、投递包和 memory 产物
```

评估归因：

```text
+------------------------+-----------------------------------------------+
| 归因模块               | 测试内容                                      |
+------------------------+-----------------------------------------------+
| crawler_strategy       | crawl / collect_evidence / blocked 路由       |
| matching_filtering     | 保留目标岗位，拒绝关键词噪音                  |
| recommendation_quality | 评分和推荐等级边界                            |
| output_quality         | URL 过滤、报告、Top 3 投递包、memory          |
| instruction_drift      | AGENTS / CLAUDE / jobhunter skill 一致性      |
+------------------------+-----------------------------------------------+
```

Grader 规则：

- 默认只启用 code grader，检查客观事实：action、分数区间、URL 过滤、文件存在、必需文本。
- model grader 和 human grader 已有 YAML schema，但离线 runner 默认 skipped。
- Cover Letter 语义质量和人工 gold label 参考 `docs/evaluation-grader-rubrics.md`。
- 真实失败样本回流参考 `docs/eval-case-feedback-loop.md`。

---

## 错误处理

如果某状态执行失败:
1. 输出错误信息: `[ERROR] 状态: XXX, 错误: ...`
2. 停止执行，不进入下一状态
3. 提示用户检查配置或重试
