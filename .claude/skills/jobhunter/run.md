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
先做每日策略巡检，再抓取岗位：

```powershell
python -m src.health_monitor --inspect-strategies --keyword "产品经理" --job-type social
```

如果输出 `logs/strategy_tasks/.../task.json`：
- 读取 task 和 evidence 目录。
- 使用 `prompts/analyze_crawler_strategy.md` 判断策略类型。
- 可自动修改 `config/companies.yaml` 或 `src/site_strategies/*.py`。
- 修改后运行：

```powershell
python tests/test_all_crawlers.py --company <company_id> --keyword "产品经理" --max-jobs 3
```

如果某家公司需要登录、验证码、强反爬或证据不足，跳过该公司，继续其他公司，并在最终结果中说明原因。

策略可用后调用 `crawl` 工具，从启用且策略可用的公司抓取岗位数据。

### Step 3: 构建候选人画像
使用 `profile.md` / `prompts/build_candidate_profile.md` 从简历生成 candidate profile。

注意：不要默认用户是产品经理。目标岗位来自 `profiles/*.md` 的 `target_roles`。

### Step 4: 确定性过滤
调用 `filter_by_time` → `dedup` 工具：
- 时间过滤：只保留最近 3 天的岗位
- 去重：排除 memory/seen_jobs.md 中已处理的岗位

### Step 5: 岗位画像与语义过滤（Agent 主判，Python fallback）
对每个岗位，先使用 `prompts/analyze_job.md` 生成 job profile，再使用 `match.md` / `prompts/match_candidate_job.md` 判断：

```
判断岗位是否符合求职意向：
- candidate_profile：{从简历读取}
- profile：{target_roles, must_have, avoid, preferences}
- job_profile：{role_family, core_responsibilities, must_have_requirements}

输出：{match_score, should_keep, match_reason, match_reasons, concerns, evidence}
```

判断时必须遵守：
- AI 根据职责语义做主判，关键词只作为辅助证据。
- 标题或 JD 命中关键词但职责偏运营、销售、标注、审核、客服时，应降分。
- 信息不足时保留 concerns，不要编造候选人能力或岗位内容。
- 只保留 `should_keep: true` 的岗位。

在非 Agent CLI 模式下，`src.matching.match_job_intent()` 提供保守 Python fallback。fallback 质量不等同于 Agent 语义判断。

### Step 6: 深度评估（Agent 主评，Python fallback）
对通过过滤的岗位，使用 `evaluate` prompt 进行深度评估：

```
评估候选人与岗位的匹配度：
- 候选人画像：{从简历提取}
- 岗位信息：{title, company, duty}

输出：{score, match_analysis, match_reasons, suggestions, risk_warning, recommendation, scoring_breakdown}
```

Python CLI 模式下，`src.matching.evaluate_job_fit()` 作为可测试 fallback，避免退回粗暴关键词评分。

### Step 7: 生成报告
Agent 模式优先使用 `report` prompt 生成 Markdown 报告；CLI 模式使用 Python 模板渲染同样的评分和风险字段，保存到 `output/` 目录。

CLI 生成报告后会自动尝试飞书输出：
- `src.feishu_push.push_to_feishu()` 推送到飞书 Wiki。
- `src.feishu_bitable.add_jobs_to_bitable()` 写入飞书多维表格。
- 是否执行由 `config/agent.yaml` 的 `feishu.enabled`、`wiki_node_token`、`bitable_token`、`bitable_table_id` 控制。
- 这不是 Git push；`python -m src.scheduler --schedule --push` 指远程仓库提交/推送，默认关闭。
- 飞书推送开关：

```powershell
python -m src.scheduler --feishu-push status
python -m src.scheduler --feishu-push on
python -m src.scheduler --feishu-push off
```

### Step 8: 更新 Memory
调用 `update_memory` 工具，将处理过的岗位写入 `memory/seen_jobs.md`。

## 输出格式

完成后输出：
```
✅ 巡检完成
- 抓取岗位: X 个
- 过滤后: Y 个
- 推荐岗位: Z 个
- 报告: output/{profile_id}_{YYYYMMDD_HHMM}.md
```

## 错误处理

如果单家公司抓取或策略分析失败，不要停止整个巡检。生成或引用对应 strategy task，跳过该公司继续处理其他公司，最后汇总：
- 已成功抓取公司
- 已固化或更新策略公司
- 需要 Agent 继续分析公司
- 需要登录/验证码/反爬/不支持公司
