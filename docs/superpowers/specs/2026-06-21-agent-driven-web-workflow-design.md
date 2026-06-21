# Agent 驱动的 Web 巡检工作流设计

## 目标

修复 Web 控制台中简历上传、候选人画像、岗位匹配和策略修复之间的断链：上传阶段只保存简历与用户搜索意向；点击巡检或修复后打开可见 CMD，由 Claude Code 在较高但保留安全边界的 `auto` 权限模式下执行真实 Agent 工作流。

同时全局停止支持 DOCX 和图片简历，仅允许 PDF、Markdown 和 TXT。

## 核心概念

系统必须区分两个对象：

- `search_intent`：用户提供的关键词、岗位类型、启用状态及期望名称。它决定搜索范围，但不代表候选人能力。
- `profile`：Claude Code 阅读简历后生成的正式候选人及求职画像。它包含目标角色、领域、能力证据、项目证据、偏好、风险和缺口。

上传简历时不得创建 `profiles/*.md`。简单关键词不能被包装成正式 profile。

## 数据存储

### 搜索意向

搜索意向统一保存在本地私有文件：

```text
config/resume_intents.yaml
```

该文件加入 `.gitignore`，不得提交。建议结构：

```yaml
resumes:
  resume-id:
    filename: candidate.pdf
    resume_path: resumes/candidate.pdf
    display_name: candidate
    enabled: true
    keywords:
      - AI 产品经理
    job_types:
      - 校招
      - 实习
    profile_path: null
    profile_status: pending_agent
    resume_sha256: "..."
    updated_at: "..."
```

### 正式 Profile

Claude Code 在巡检开始时读取简历和 `resume_intents.yaml`，生成：

```text
profiles/<profile_id>.md
```

YAML frontmatter 至少包含：

- `name`
- `enabled`
- `resume`
- `resume_sha256`
- `job_types`
- `keywords`
- `target_roles`
- `target_domains`
- `must_have`
- `nice_to_have`
- `avoid`
- `locations`
- `employment_types`

Markdown 正文保存候选人摘要、角色经历、技能、项目证据、约束和信息缺口。所有判断必须引用简历事实。

当正式 profile 不存在或 `resume_sha256` 变化时重新生成；简历未变化时允许复用，并结合最新搜索意向更新目标字段。

## 手动加入简历的同步规则

触发点采用“启动扫描 + 列表刷新兜底”：

1. Web 服务启动时扫描 `resumes/`。
2. 每次请求简历列表时再次执行幂等扫描，以发现服务运行期间手动加入的文件。
3. 新发现的 PDF、MD、TXT 自动创建 `search_intent`，`enabled` 默认为 `true`。
4. 已存在记录的 `enabled`、关键词和岗位类型不得被扫描覆盖。
5. 新文件关键词为空时显示“待补充关键词”；启动巡检前必须要求用户补充。
6. DOCX 和图片不进入意向列表，不自动启用，并显示明确的格式不支持提示。

## 巡检启动流程

```text
用户选择简历并点击启动巡检
  -> Web API 校验文件、启用状态、关键词和岗位类型
  -> 创建 run_id 与运行任务记录
  -> Windows 新建可见 CMD
  -> Claude Code 以 --permission-mode auto 启动
  -> Claude 读取 CLAUDE.md、搜索意向、简历与 jobhunter prompts
  -> 生成或刷新正式 profile
  -> 执行官网策略巡检、岗位抓取和去重
  -> Agent 建立 JD 画像并完成候选人—岗位语义匹配
  -> 生成审计报告与运行结果
```

启动命令采用交互模式，不使用 `-p`：

```powershell
claude --permission-mode auto --name "SmartHunter-巡检-<run_id>" "<任务 Prompt>"
```

CMD 保持可见，用户可以查看进度、批准特殊操作或继续追问。

## 策略修复流程

策略修复使用现有 Claude Code Agent：

```powershell
claude --permission-mode auto --agent crawler-strategy-inspector --name "SmartHunter-策略修复-<run_id>" "<批量任务 Prompt>"
```

约束：

- 一次把全部选中公司传给一个 Agent 串行处理。
- 不按公司创建多个 Agent，也不嵌套更多 Agent。
- Prompt 必须包含准确的公司 ID、完整原链接、关键词、岗位类型和任务目录。
- 登录、验证码、网络、地域限制和强反爬继续按既有规则报告，不绕过。

## Claude 启动器

新增独立模块负责进程启动，Web API 不直接拼接命令。启动器必须：

1. 使用 `shutil.which("claude")`/`shutil.which("claude.cmd")` 验证 Claude Code 已安装。
2. 使用安全的 Windows 参数引用方式生成 `cmd.exe /d /k` 命令。
3. 使用 `subprocess.CREATE_NEW_CONSOLE` 打开可见窗口。
4. 返回真实 PID、run_id、命令类型和启动时间。
5. 启动失败时返回非 2xx，不得 `except Exception: pass`。
6. 把任务输入和状态写入 `logs/agent_runs/<run_id>/`，不得伪报成功。

前端显示的状态至少包括：未启动、已打开 Claude Code、启动失败。完成状态由 Claude 写回的结果文件确定，不根据 Toast 猜测。

## 格式约束

全局允许格式：

```text
.pdf .md .txt
```

全局禁止格式：

```text
.docx .png .jpg .jpeg 以及其他图片格式
```

约束必须同步应用到：

- Web 文件选择器
- 上传 API
- 手动目录扫描
- `src.resume_parser`
- 简历预览
- Agent/Skill 文档
- README 和全局设计文档
- 测试用例

已有禁用格式文件不自动删除，但不能上传、解析、预览或参与巡检。删除 DOCX 预览相关 JSZip 和 docx-preview 依赖；PDF.js 继续保留。

## Web 模块边界

为避免继续扩大 `src/web_ui.py`，新增：

- `src/resume_intents.py`：格式校验、目录同步、意向读写、SHA256。
- `src/claude_launcher.py`：Prompt 构建、Claude 命令构建、CMD 启动、运行记录。

`src/web_ui.py` 只负责参数校验、调用上述模块并返回 API 响应。

## 错误处理

- Claude Code 未安装：返回明确错误和安装/检查命令。
- 搜索意向缺少关键词：阻止启动并提示补充。
- 简历格式不支持：上传、扫描和运行入口一致拒绝。
- 简历不存在或 SHA256 不一致：阻止复用旧 profile，由 Agent 重新生成。
- CMD 启动失败：保留失败原因，不返回“启动成功”。
- Agent 运行失败：保留任务文件和错误结果，支持用户从可见 CMD 继续处理。

## 测试策略

采用 TDD：

1. 意向存储测试：上传只生成 intent，不生成 profile。
2. 手动文件同步测试：新 PDF/MD/TXT 默认启用；已有禁用值不被覆盖。
3. 格式测试：DOCX 和图片在上传、扫描、解析、预览入口均失败。
4. Claude 命令测试：包含 `--permission-mode auto`、正确任务 Prompt 和可见 CMD 参数。
5. 巡检测试：调用 Claude Code，不直接调用 `python -m src.cli`。
6. 修复测试：调用单个 `crawler-strategy-inspector`，准确传递全部选中公司。
7. 错误测试：缺少 Claude、Popen 失败或缺少关键词时不得报告成功。
8. 全量回归：运行项目完整 pytest 与 Agent eval。

测试不得打开真实 Claude 会话、修改真实 `companies.yaml` 或切换真实公司开关；进程创建和文件路径必须使用临时目录及 mock 验证。最终另做一次人工可见 CMD 冒烟测试。

## 文档同步

实现完成后更新：

- `README.md`
- `README_CN.md`
- `docs/smartjobhunter-agent-design.md`
- `CLAUDE.md`
- `AGENTS.md`
- `.claude/skills/jobhunter/profile.md` 及必要 Prompt

文档必须明确：搜索意向不是候选人画像、Python 仅为 fallback、Web 按钮会启动可见 Claude Code、全局只支持 PDF/MD/TXT。
