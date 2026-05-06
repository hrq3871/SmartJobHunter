# SmartJobHunter Agent Instructions

SmartJobHunter 是一个 agent-platform 项目。当前 agent 平台负责语义判断，Python 负责工具执行和可复现 fallback。

## 用户说“运行巡检”

1. 读取 `docs/agent-platform-contract.md` 和 `docs/general-matching-design.md`。
2. 读取目标 profile 和简历。
3. 运行：

```bash
python -m src.cli
```

4. 检查 `output/` 报告，并从“JD 证据 + 简历证据 + profile 目标”角度评估岗位是否真的符合要求。

## 用户说“分析简历”或“评估岗位”

不要只看关键词。按顺序做：

1. 从简历生成 candidate profile。
2. 从 JD 生成 job profile。
3. 根据 candidate profile、job profile 和 `profiles/*.md` 的求职目标判断匹配。
4. 信息不足时输出 `needs_review`。

## 用户说“健康巡检”或“修复爬虫”

运行：

```bash
python -m src.health_monitor --check-all
```

如果某家公司失败，先收集证据，再由 agent 分析：

```bash
python -m src.crawler_evidence --company <company_id> --keyword "产品经理" --job-type social
```

Python 只产出证据。当前 agent 负责分析证据并决定如何修改配置或代码。
