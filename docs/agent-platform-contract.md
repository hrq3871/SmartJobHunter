# SmartJobHunter Agent Platform Contract

## Product Position

SmartJobHunter is an agent-platform project, not a standalone autonomous Python bot.

## Agent Responsibilities

- Understand user requests such as "运行巡检", "分析简历", "评估岗位", "健康巡检", and "修复爬虫".
- Build a structured candidate profile from the resume.
- Analyze each JD into a structured job profile.
- Judge fit using candidate evidence, target profile, and JD evidence.
- Inspect health reports and crawler evidence when a company crawler fails.
- Modify `profiles/`, `config/companies.yaml`, docs, or Python code when evidence supports the change.
- Run targeted tests and live official-site validation.

## Python Responsibilities

- Extract raw text from resume files.
- Crawl configured company career pages.
- Apply deterministic time filtering, deduplication, fallback matching, ranking, and report rendering.
- Capture network evidence with Playwright when crawler repair is needed.
- Validate config shape and run tests.

## Non-goals

- Python does not call external LLM APIs for analysis.
- Python does not silently rewrite crawler config after guessing.
- Python fallback does not replace agent semantic judgment.
- Health check is not proof that the full job recommendation workflow is correct.
