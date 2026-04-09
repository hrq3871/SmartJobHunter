# SmartJobHunter

基于 Claude Code Agent 的自动化求职巡检系统。

## 功能特性

- **多意向并行** - 支持多个求职方向，每份简历独立巡检
- **多格式简历** - 支持 txt、md、docx、pdf 格式
- **智能过滤** - 三层漏斗：时间 → 去重+关键词 → 岗位性质
- **AI 评估** - 自动评分（0-100分）+ 匹配理由
- **岗位分类** - 区分实习/校招/社招
- **定时执行** - 每天自动巡检
- **自我修复** - 爬虫异常自动检测
- **Git 同步** - 自动推送变更

## 快速开始

### 1. 安装依赖

```bash
pip install playwright pyyaml
playwright install chromium

# 可选：支持 docx/pdf 简历
pip install python-docx PyMuPDF
```

### 2. 配置简历和意向

```bash
# 放入简历
cp your_resume.txt resumes/

# 编辑配置
vim config.yaml
```

### 3. 运行巡检

```bash
# 运行所有启用的意向
python main.py

# 指定岗位类型
python main.py -t social      # 社招
python main.py -t internship  # 实习
python main.py -t campus      # 校招

# 指定意向
python main.py -p "产品经理-TOB方向"
```

### 4. 查看报告

```bash
ls output/
# 20260410_产品经理-TOB方向.md
```

## 目录结构

```
SmartJobHunter/
├── config.yaml          # 主配置（求职意向）
├── companies.yaml       # 公司列表
├── main.py              # 主程序
├── spider.py            # 爬虫模块
├── scheduler.py         # 调度器
├── resume_parser.py     # 简历解析
├── health_check.py      # 健康检测
├── git_auto_push.py     # Git自动推送
│
├── resumes/             # 简历目录
│   ├── example_resume.md
│   └── your_resume.txt
│
├── output/              # 输出报告
├── data/                # 去重数据
└── logs/                # 日志
```

## 配置说明

### config.yaml - 求职意向

```yaml
profiles:
  - name: "产品经理-TOB方向"
    enabled: true
    intent: "求职意向描述..."
    resume_path: "./resumes/pm_tob.txt"
    job_type: "社招"
    keywords:
      - "产品经理"
      - "TOB"
      - "AI产品"
```

### companies.yaml - 公司列表

```yaml
companies:
  - id: tencent
    name: 腾讯
    enabled: true
    urls:
      social: "https://..."
      campus: "https://..."
```

## 定时任务

```bash
# Windows - 管理员运行
setup_schedule.bat

# 每天晚上8点自动执行
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `python main.py` | 运行所有启用的意向 |
| `python main.py -t social` | 只运行社招 |
| `python main.py -p "意向名"` | 运行指定意向 |
| `python main.py --list-profiles` | 列出所有意向 |
| `python spider.py --list` | 列出公司 |
| `python scheduler.py --check` | 健康检测 |
| `python scheduler.py --run` | 立即巡检 |

## 支持的公司

### 第一梯队 (10家)
| 公司 | 社招 | 校招/实习 |
|------|------|----------|
| 腾讯 | ✅ | ✅ |
| 字节跳动 | ✅ | ✅ |
| 阿里巴巴 | 🚧 | 🚧 |
| 百度 | 🚧 | 🚧 |
| 美团 | 🚧 | 🚧 |
| 滴滴出行 | 🚧 | 🚧 |
| 京东 | 🚧 | 🚧 |
| 拼多多 | 🚧 | 🚧 |
| 华为 | 🚧 | 🚧 |
| 小米 | 🚧 | 🚧 |

### 第二梯队 (15家)
| 公司 | 社招 | 校招/实习 |
|------|------|----------|
| 网易 | 🚧 | 🚧 |
| 快手 | 🚧 | 🚧 |
| 哔哩哔哩 | 🚧 | 🚧 |
| 小红书 | 🚧 | 🚧 |
| 携程 | 🚧 | 🚧 |
| 微博 | 🚧 | 🚧 |
| 知乎 | 🚧 | 🚧 |
| 唯品会 | 🚧 | 🚧 |
| 58同城 | 🚧 | 🚧 |
| OPPO | 🚧 | 🚧 |
| vivo | 🚧 | 🚧 |
| 中兴通讯 | 🚧 | 🚧 |
| 联想 | 🚧 | 🚧 |
| 蚂蚁集团 | 🚧 | 🚧 |
| 菜鸟网络 | 🚧 | 🚧 |

### 游戏公司 (5家)
| 公司 | 社招 | 校招/实习 |
|------|------|----------|
| 网易游戏 | 🚧 | 🚧 |
| 米哈游 | 🚧 | 🚧 |
| 莉莉丝游戏 | 🚧 | 🚧 |
| 完美世界 | 🚧 | 🚧 |
| 三七互娱 | 🚧 | 🚧 |

### 外资科技 (8家)
| 公司 | 社招 |
|------|------|
| 微软中国 | 🚧 |
| 苹果中国 | 🚧 |
| 英伟达中国 | 🚧 |
| 特斯拉中国 | 🚧 |
| 英特尔中国 | 🚧 |
| AMD中国 | 🚧 |
| 思科中国 | 🚧 |
| SAP中国 | 🚧 |

**总计: 38家公司** (✅ 已实现 🚧 待开发)

## 添加新公司

1. 在 `companies.yaml` 添加配置
2. 设置 `enabled: false`
3. 在 `spider.py` 实现爬虫
4. 测试通过后设置 `enabled: true`

## 输出示例

```markdown
### 1. AI产品经理 🟢 85分

| 字段 | 内容 |
|------|------|
| 公司 | 腾讯 |
| 地点 | 北京 |
| 匹配理由 | 产品经理, AI产品, TOB |

**岗位职责**: ...
```

## License

MIT
