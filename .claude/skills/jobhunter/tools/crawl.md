---
name: crawl
description: 抓取岗位数据
---

# crawl 工具

## 功能
从 `config/companies.yaml` 中配置的公司招聘网站抓取岗位。抓取前必须先确认公司策略可用；新链接、失效链接、策略变化或失败站点先走 strategy task。

## 策略巡检命令

```powershell
python -m src.health_monitor --inspect-strategies --keyword "产品经理" --job-type social
python -m src.health_monitor --inspect-company <company_id> --keyword "产品经理" --job-type social
```

如果生成任务：

```powershell
python -m src.crawler_evidence --company <company_id> --keyword "产品经理" --job-type social
```

然后读取：
- `logs/strategy_tasks/.../task.json`
- `logs/crawler_evidence/.../evidence.json`
- `logs/crawler_evidence/.../network.json`
- `logs/crawler_evidence/.../page.html` / `page.txt` / `page.png`

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| companies | list | 是 | 公司列表 |
| job_type | string | 否 | 岗位类型 (social/campus/internship) |
| keyword | string | 否 | 搜索关键词 |
| max_jobs | int | 否 | 每个公司最大岗位数，默认50 |

## 输出
```json
[
  {
    "title": "AI产品经理",
    "company": "腾讯",
    "location": "北京",
    "duty": "...",
    "requirement": "...",
    "url": "...",
    "hash": "abc123"
  }
]
```

## 实现位置
主入口是 `src/crawler_factory.py`：
- `get_enabled_companies(job_type)`
- `crawl_company(company_id, keyword, max_jobs, job_type)`
- `crawl_all(keyword, job_type, max_jobs)`

策略路由：
- `config_intercept` / `config_dom` -> `src.config_crawler`
- `legacy_python` -> 旧 `src.crawler` 中已固化的手写逻辑
- `custom_python` -> `src/site_strategies/<module>.py`
- `unknown` / `browser_operation` / `unsupported` -> 生成 strategy task，跳过该公司

## 调用方式
```python
from src.crawler_factory import crawl_company, get_enabled_companies

companies = get_enabled_companies(job_type="social")
for company in companies:
    jobs = crawl_company(company["id"], keyword="AI产品经理", max_jobs=50, job_type="social")
```

## Agent 规则
- 不要把 Python 抓取失败描述成“AI 自动修好了”。Python 只生成证据和任务。
- 当前 Claude/Codex Agent 可以根据证据自动修改 `config/companies.yaml` 或 `src/site_strategies/*.py`。
- 修改后必须运行单公司验证：

```powershell
python tests/test_all_crawlers.py --company <company_id> --keyword "AI产品经理" --max-jobs 3
```
