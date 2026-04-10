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

## 执行流程

### Step 1: 加载配置 [INIT]

读取 `profiles/*.md`、`config/agent.yaml`、`config/companies.yaml`

**输出**: 找到 X 个求职意向，Y 家启用的公司

---

### Step 2: 抓取岗位 [CRAWL]

对每个启用的公司调用 Python 爬虫抓取岗位。

**输出**: 抓取了 X 个岗位

---

### Step 3: 确定性过滤 [FILTER-1]

调用 Python 工具：
1. `filter_by_time` - 只保留最近 3 天的岗位
2. `dedup` - 排除 `memory/seen_jobs.md` 中已处理的岗位

**输出**: 过滤后剩余 X 个岗位

---

### Step 4: 语义过滤 [FILTER-2] ⭐ AI

**关键：用 LLM 判断岗位类型和匹配度，不要用简单关键词匹配。**

对每个岗位，判断：
1. 这是产品岗还是技术岗？
2. 是否符合求职者意向？
3. 匹配度评分 (0-1)，只保留 >= 0.6 的岗位

**判断参考**：
- 产品岗：标题含"产品经理/总监/负责人"，职责含"需求分析/产品规划/用户研究"
- 技术岗：标题含"工程师/架构师/算法/开发"，职责含"编码/系统设计/模型训练"

---

### Step 5: 深度评估 [EVALUATE] ⭐ AI

对通过过滤的岗位，输出：
- 匹配分数 (0-100)
- 匹配理由
- 风险提示
- 建议

---

### Step 6: 生成报告 [REPORT]

保存到 `output/YYYYMMDD_{profile_name}.md`

---

### Step 7: 更新记录 [MEMORY]

写入 `memory/seen_jobs.md`

---

## 输出格式

```
✅ 巡检完成
- 抓取岗位: X 个
- 时间过滤后: Y 个
- 语义过滤后: Z 个
- 推荐岗位: N 个
- 报告: output/YYYYMMDD_{profile_name}.md
```

---

## 错误处理

任何步骤失败时，输出错误信息并询问用户是否继续。
