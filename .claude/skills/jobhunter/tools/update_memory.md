---
name: update_memory
description: 更新 Memory
---

# update_memory 工具

## 功能
将处理的岗位追加到 memory/seen_jobs.md

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| evaluations | list | 是 | 评估结果 |

## 输出
成功/失败状态

## 实现位置
`src/filters.py` → `update_memory()`

## Memory 文件格式
```markdown
# Seen Jobs Memory

> 自动记录已处理的岗位，用于去重

| hash | company | title | score | date |
|------|---------|-------|-------|------|
| abc123 | 腾讯 | AI产品经理 | 85 | 2026-04-10 |
```
