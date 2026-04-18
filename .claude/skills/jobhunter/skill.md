---
name: jobhunter
description: 智能求职巡检 Agent
user_invocable: true
---

# SmartJobHunter Agent

基于 LLM 的智能求职巡检系统，自动抓取、过滤、评估岗位并生成报告。

## 快速开始

用户说"运行巡检"、"找工作"或"帮我看看有什么岗位"时，按以下流程执行：

---

## 状态机流程

```
INIT → LOADED → CRAWLED → FILTERED → EVALUATED → REPORTED → DONE
```

---

### INIT

**目标**: 初始化并加载所有配置

**执行动作**:
1. 调用 `load_config` 工具
2. 读取 `profiles/{profile_name}.md` 获取求职意向
3. 读取 `resumes/{resume_file}` 获取简历内容
4. 读取 `config/companies.yaml` 获取公司列表
5. 读取 `config/agent.yaml` 获取 Agent 配置

**输出变量**:
```
profile = {name, intent, keywords, job_type, resume_path}
resume = "简历文本内容"
companies = ["腾讯", "字节跳动"]
agent_config = {decision_level, model_strategy, ...}
```

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
3. 保存到 `output/{date}_{profile_name}.md`

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
