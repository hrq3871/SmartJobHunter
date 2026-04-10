---
name: filter_by_time
description: 时间过滤
---

# filter_by_time 工具

## 功能
过滤最近N天的岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| days | int | 否 | 最近N天，默认3 |

## 输出
过滤后的岗位列表

## 实现位置
`src/filters.py` → `filter_by_time()`

---

---
name: dedup
description: 去重过滤
---

# dedup 工具

## 功能
排除已处理过的岗位

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |

## 输出
去重后的岗位列表

## 实现位置
`src/filters.py` → `dedup()`, `load_seen_hashes()`

---

---
name: clean_data
description: 数据清洗
---

# clean_data 工具

## 功能
清洗和标准化岗位数据

## 输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| jobs | list | 是 | 岗位列表 |
| truncate_length | int | 否 | 文本截断长度，默认6000 |

## 输出
清洗后的岗位列表

## 实现位置
`src/filters.py` → `clean_data()`
