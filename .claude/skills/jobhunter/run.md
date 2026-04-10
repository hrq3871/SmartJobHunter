---
name: run
description: 运行求职巡检 Agent
user_invocable: true
---

# 运行求职巡检

用户请求运行求职巡检时，按照以下流程执行：

## 执行流程

### Step 1: 加载配置
调用 `load_config` 工具，读取：
- `profiles/*.md` - 求职意向配置
- `config/agent.yaml` - Agent 配置
- `config/companies.yaml` - 公司列表

### Step 2: 抓取岗位
调用 `crawl` 工具，从启用的公司抓取岗位数据。

### Step 3: 确定性过滤
调用 `filter_by_time` → `dedup` 工具：
- 时间过滤：只保留最近 3 天的岗位
- 去重：排除 memory/seen_jobs.md 中已处理的岗位

### Step 4: 语义过滤（AI）
对每个岗位，使用 `semantic_filter` prompt 进行 LLM 判断：

```
判断岗位是否符合求职意向：
- 求职意向：{从 profile 读取}
- 岗位标题：{title}
- 岗位描述：{duty}

输出：{match_score, should_keep, match_reason}
```

只保留 `should_keep: true` 的岗位。

### Step 5: 深度评估（AI）
对通过过滤的岗位，使用 `evaluate` prompt 进行深度评估：

```
评估候选人与岗位的匹配度：
- 候选人画像：{从简历提取}
- 岗位信息：{title, company, duty}

输出：{score, match_reasons, suggestions, recommendation}
```

### Step 6: 生成报告
使用 `report` prompt 生成 Markdown 报告，保存到 `output/` 目录。

### Step 7: 更新 Memory
调用 `update_memory` 工具，将处理过的岗位写入 `memory/seen_jobs.md`。

## 输出格式

完成后输出：
```
✅ 巡检完成
- 抓取岗位: X 个
- 过滤后: Y 个
- 推荐岗位: Z 个
- 报告: output/YYYYMMDD_{profile_name}.md
```

## 错误处理

如果任何步骤失败，输出错误信息并询问用户是否继续。
