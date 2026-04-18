# SmartJobHunter Agent 操作指南

## Agent 工作流程

当用户请求运行求职巡检时，Agent 应按以下步骤执行：

### Step 1: 读取配置
```
1. 读取 config/companies.yaml 获取公司配置
2. 读取 profiles/ 目录下的求职意向配置
3. 读取 resumes/ 目录下的简历文件
4. 读取 memory/seen_jobs.md 获取已处理岗位
```

### Step 2: 抓取岗位数据
```
使用 crawler_factory 抓取岗位：
python -m src.crawler_factory --crawl <company_id> --keyword "关键词"
```

### Step 3: 三层过滤
```
第一层 - 时间过滤：只保留最近N天的岗位（默认3天）
第二层 - 去重过滤：排除 seen_jobs.md 中已有的岗位
第三层 - 关键词过滤：匹配标题/职责中的关键词
```

### Step 4: AI 评估
```
对每个通过过滤的岗位，Agent 进行深度评估：
1. 匹配度评分 (0-100)
2. 匹配理由
3. 缺失技能/风险
4. 公司背调（可选）
```

### Step 5: 生成报告
```
将评估结果写入 output/ 目录的 Markdown 文件
格式：{日期}_{意向名称}.md
```

### Step 6: 更新去重数据库
```
将处理过的岗位追加到 memory/seen_jobs.md
```

## 常用命令

```bash
# 立即执行巡检
python -m src.cli                    # 运行所有启用的意向
python -m src.cli -t social          # 仅社招
python -m src.cli -t internship      # 仅实习
python -m src.cli -t campus          # 仅校招
python -m src.cli -p "意向名称"       # 指定意向

# 爬虫管理
python -m src.crawler_factory --list              # 列出所有公司
python -m src.crawler_factory --test <id>         # 测试爬虫
python -m src.crawler_factory --crawl <id>        # 抓取指定公司

# 健康检测
python -m src.health_monitor --check <id>         # 检测单个爬虫
python -m src.health_monitor --check-all          # 检测所有爬虫
```

## 自愈系统

当爬虫失败时，系统自动执行：

1. **健康检测** (`health_monitor.py`) - 诊断失败原因
2. **自动分析** (`auto_analyzer.py`) - 分析新公司/修复API
3. **用户通知** (`notifier.py`) - 通知修复结果

### 失败类型处理

| 类型 | 自动修复 | 处理方式 |
|------|:--------:|----------|
| 网络错误 | ❌ | 稍后重试 |
| API变化 | ✅ | 重新分析API |
| URL失效 | ✅ | 搜索新URL |
| 需要登录 | ❌ | 通知用户 |
| 反爬拦截 | ❌ | 调整频率 |

## 支持的公司

**已启用 (42家)：**
- BAT+TMD: 腾讯、字节、阿里、美团、百度、滴滴、京东、拼多多、华为、小米
- 互联网: 网易、快手、B站、小红书、携程、微博、知乎、OPPO、vivo、中兴、联想
- 游戏: 米哈游、莉莉丝、三七互娱
- 飞书系: 商汤、Keep、SHEIN、蔚来、理想、小鹏
- 其他: 苹果、吉利、长城、大疆、海康、科大讯飞、深信服、工商银行

**待开发 (14家)：**
- 外资: 微软、英伟达、特斯拉、Intel、AMD、思科、SAP
- 国央企: 建行、移动、电信
- 其他: 比亚迪、浪潮、蚂蚁、菜鸟

完整列表见 `公司列表.md` 和 `config/companies.yaml`

## 文件管理规范

### 临时文件清理

**一次性文件用完必须清理：**

| 类型 | 示例 | 处理 |
|------|------|------|
| API分析输出 | `*_api.json` | 用完删除 |
| 一次性脚本 | `scripts/analyze_*.py` | 用完删除 |
| 迁移脚本 | `scripts/migrate.py` | 执行后删除 |
| 调试输出 | `debug_*.json` | 用完删除 |

**删除方式：**
```bash
# 使用 PowerShell 进回收站（可恢复）
powershell -Command "Remove-Item -Path '文件路径' -Force"
```

**禁止使用 `rm` 命令**（永久删除，不可恢复）

### 目录结构

```
SmartJobHunter/
├── config/           # 配置文件（长期保留）
├── src/              # 源代码（长期保留）
├── profiles/         # 求职意向（用户维护）
├── resumes/          # 简历文件（用户维护）
├── memory/           # 去重数据（自动更新）
├── output/           # 输出报告（自动生成）
├── logs/             # 日志文件（自动生成）
├── tests/            # 测试文件（长期保留）
└── docs/             # 文档（长期保留）
```

## Bug修复流程

每次修复bug必须遵循：

1. **出计划** - 分析问题，制定方案
2. **Review** - 检查方案合理性
3. **执行测试** - 验证修复效果
4. **清理临时文件** - 删除一次性脚本和输出
