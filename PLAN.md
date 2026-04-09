# SmartJobHunter Agent 实现计划

## 背景
将原 Python 实现的求职巡检系统改造为基于 Claude Code Agent 能力的版本。

## 核心设计

### 技术栈替换
| 原 Python 方案 | Agent 方案 |
|---------------|-----------|
| Playwright 爬虫 | Bash + curl / Playwright (本地) |
| SQLite 数据库 | JSONL 文件 |
| PyYAML 配置 | Read + YAML |
| asyncio 并发 | Agent subagent |
| Gemini API | 原生大模型 |

### 目录结构
```
D:\ccworkplace\Smarthunter\
├── CLAUDE.md              # Agent 行为指导
├── config.yaml            # 主配置
├── spider.py              # 爬虫脚本（本地运行）
├── resumes/               # 简历文件
│   └── pm_tob.txt
├── data/
│   └── seen_jobs.jsonl    # 去重记录
├── output/                # 输出结果
└── logs/                  # 运行日志
```

### 执行流程
1. **读取配置** → 解析 config.yaml
2. **抓取岗位** → spider.py (Playwright) 获取岗位数据
3. **三层过滤**：
   - 时间过滤（最近 N 天）
   - 去重 + 关键词匹配
   - 详情抓取 + 清洗压缩
4. **AI 评估** → 大模型评估 + 公司背调
5. **输出结果** → 写入 Markdown 文件

### Subagent 分层（防上下文溢出）
- **协调器 Agent**：读取配置，分配任务
- **Profile Agent**：处理单个求职意向
- **评估器 Agent**：评估单个岗位

## 实现步骤

### Step 1: 基础结构 ✅
- [x] 创建目录结构
- [x] 创建 config.yaml
- [x] 创建简历文件
- [x] 创建去重数据库

### Step 2: 数据获取
- [x] 安装 Playwright
- [x] 编写 spider.py
- [ ] 测试爬虫（当前网络问题）
- [ ] 备选方案：手动提供数据

### Step 3: 核心逻辑
- [ ] 时间过滤
- [ ] 去重机制
- [ ] 关键词匹配
- [ ] 文本清洗

### Step 4: AI 评估
- [ ] 评估 Prompt 模板
- [ ] 结构化 JSON 输出
- [ ] 公司背调

### Step 5: 输出
- [ ] Markdown 报告
- [ ] 端到端测试

## 当前问题
- Playwright 访问招聘网站时连接被关闭（可能是网站反爬）
- 需要测试其他数据源或使用代理

## 下一步
1. 解决爬虫网络问题
2. 或使用模拟数据测试完整流程
