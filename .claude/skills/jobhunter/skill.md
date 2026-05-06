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
INIT → LOADED → STRATEGY_INSPECTED → CRAWLED → FILTERED → EVALUATED → REPORTED → DONE
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

**目标**: 生成报告

**执行动作**:
1. 按评分从高到低排序 evaluations
2. 执行报告生成 (使用 report prompt)
3. 保存到 `output/{profile_id}_{YYYYMMDD_HHMM}.md`

**状态转换**: → REPORTED

---

### REPORTED

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
📄 报告: output/20260410_产品经理-TOB方向.md
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
[REPORTED] ✓ 报告生成: output/20260410_产品经理-TOB方向.md
[DONE] ✅ 巡检完成
```

---

## 错误处理

如果某状态执行失败:
1. 输出错误信息: `[ERROR] 状态: XXX, 错误: ...`
2. 停止执行，不进入下一状态
3. 提示用户检查配置或重试
