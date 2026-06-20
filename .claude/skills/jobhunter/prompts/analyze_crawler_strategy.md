# Analyze Crawler Strategy

你是当前 Claude/Codex Agent，不是 Python 里的外部 LLM API。你的任务是读取 crawler evidence，判断一个公司官网应该如何固化抓取策略。

批量任务必须委派给 `.claude/agents/crawler-strategy-inspector.md` 定义的单个子 Agent，由它串行处理全部公司；不得按公司拆分 Agent，也不得嵌套更多 Agent。主 Agent 只接收最终摘要和 artifact 路径。

## 输入

请读取并引用以下文件：

- `logs/strategy_tasks/<company>/<timestamp>/task.json`
- `logs/crawler_evidence/<company>/<timestamp>/evidence.json`
- `logs/crawler_evidence/<company>/<timestamp>/network.json`
- `logs/crawler_evidence/<company>/<timestamp>/page.html`
- `logs/crawler_evidence/<company>/<timestamp>/page.txt`
- `logs/crawler_evidence/<company>/<timestamp>/page.png`

如果 evidence 不存在，先运行：

```powershell
python -m src.crawler_evidence --company <company_id> --keyword "产品经理" --job-type social
```

## 分析步骤

1. 确认页面是否可访问：HTTP 状态、final_url、title、正文样本。
2. 判断是否有登录、验证码、强反爬、地域限制或空岗位信号。
3. 检查 `network.json` 和 `xhr_samples/`，寻找返回岗位数组的 XHR/fetch。
4. 对候选数组确认：
   - `api.pattern`
   - `api.data_path`
   - `field_mappings`：id、title、location、category、publish_time、duty、requirement、url 所需字段
   - `url_template`
5. 如果没有稳定 API，检查 DOM 是否有可复现 selector。
6. 如果 API/DOM 都不足，但浏览器操作可重复，记录 `browser_operation` 步骤和限制。
7. 如果必须登录、验证码、强反爬或证据不足，标记 `unsupported` 并写明原因。
8. 所有输入和输出 URL 必须原封不动，禁止切片、摘要、省略号或改写查询参数。

## 输出要求

必须输出以下结构：

```yaml
company_id: <id>
recommended_strategy:
  type: config_intercept | config_dom | legacy_python | custom_python | browser_operation | unsupported
  status: verified | needs_review | unsupported
evidence:
  page_status: <summary>
  network_requests: <key requests>
  candidate_job_arrays:
    - path: <data_path>
      count: <count>
      sample_keys: [...]
patch_plan:
  files:
    - config/companies.yaml
    - src/site_strategies/<module>.py
  changes:
    - <具体修改>
verification:
  commands:
    - python tests/test_all_crawlers.py --company <company_id> --keyword "产品经理" --max-jobs 3
unsupported_reason: null | <登录/验证码/反爬/无岗位/证据不足>
```

## 修改规则

- 优先使用 `config_intercept` 或 `config_dom`，只有配置表达不了时才写 Python strategy。
- 保留旧 `src.crawler` 中已经能工作的手写逻辑，可标记为 `legacy_python`，不要直接删除。
- 自动修改配置或代码后必须运行验证命令。
- 验证失败时不要继续堆改动，先回到 evidence 找根因。
