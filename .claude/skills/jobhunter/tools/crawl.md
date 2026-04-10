---
name: crawl
description: 抓取岗位数据
---

# crawl 工具

## 功能
从配置的公司招聘网站抓取岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| companies | list | 是 | 公司列表 |
| job_type | string | 否 | 岗位类型 (social/campus/internship) |
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
`src/crawler.py` → `crawl_company()`

## 调用方式
```python
from src.crawler import crawl_company, get_enabled_companies

companies = get_enabled_companies(job_type="social")
for company in companies:
    jobs = crawl_company(company['id'], keyword, max_jobs=50)
```
