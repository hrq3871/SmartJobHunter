# SmartJobHunter 通用匹配设计

## 核心定位

SmartJobHunter 不是只面向产品经理的岗位脚本，而是一个依托 Claude/Codex 等 agent 平台运行的通用求职代理。

项目真正的智能判断来自当前 agent 平台。Python 层只做可复现工具：简历文本抽取、官网岗位抓取、确定性预过滤、fallback 粗评分、报告落盘和测试验证。

## 通用输入

- 用户简历：`resumes/` 中的 txt、md、docx、pdf 或图片文件。
- 求职目标：`profiles/*.md` 中的 `target_roles`、`must_have`、`avoid` 等字段。
- 岗位 JD：由 Playwright 爬虫从公司官网抓取。
- 候选人画像：由 agent 根据简历生成。
- 岗位画像：由 agent 根据 JD 生成。

## 标准工作流

1. Python 抽取简历原文。
2. Agent 把简历转成结构化候选人画像。
3. Python 抓取公司官网岗位。
4. Agent 把每个 JD 转成结构化岗位画像。
5. Agent 根据候选人画像、求职目标、岗位画像做匹配判断。
6. Python 保存 JSON 结果并渲染 Markdown 报告。

## 匹配可靠性的最低标准

- 岗位实际核心工作匹配 `target_roles`，不能只看标题关键词。
- 简历中有可以引用的经历证据支撑岗位核心要求。
- 输出必须同时引用 JD 证据和简历证据。
- 结果要区分 `strong_apply`、`apply`、`consider`、`needs_review`、`skip`。
- 信息不足时输出 `needs_review`，不能编造简历能力或岗位内容。

## Python fallback 边界

Python fallback 是保守粗筛，不是最终智能判断：

- 可用于没有 agent 介入时跑通 CLI。
- 可用于测试排序、过滤、报告落盘等工程链路。
- 不应该把某个职业方向写死成全局规则。
- 不应该把关键词命中当作强匹配。

## 局限

- 如果没有 agent 主动执行 prompts，CLI 结果只是 fallback 质量。
- JD 文本太弱时，系统只能给低置信度或人工复核建议。
- 用户 profile 写得太泛，匹配结果也会变泛。
- 对任何“看起来相关但证据不足”的岗位，应降低分数或标记复核。
