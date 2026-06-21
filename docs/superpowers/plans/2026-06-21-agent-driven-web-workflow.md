# Agent-Driven Web Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Web uploads create only persisted search intents, launch visible Claude Code sessions for real profile/matching/repair work, auto-enable manually added supported resumes, and globally restrict resumes to PDF/MD/TXT.

**Architecture:** Extract resume intent persistence and Claude process launching from `src/web_ui.py` into focused modules. The Web API validates and records requests; Claude Code runs interactively in a new Windows console with `--permission-mode auto` and creates the formal Agent profile before inspection. Supported-format policy is shared by Web and CLI parsing.

**Tech Stack:** Python 3.13, FastAPI, PyYAML, subprocess/Windows CMD, vanilla HTML/CSS/JS, pytest.

**Design spec:** `docs/superpowers/specs/2026-06-21-agent-driven-web-workflow-design.md`

---

## File map

- Create `src/resume_intents.py`: supported-format policy, SHA256, local YAML persistence, directory reconciliation.
- Create `src/claude_launcher.py`: prompt construction, safe Claude command construction, visible CMD launch, run metadata.
- Modify `src/web_ui.py`: delegate upload/intent/run/repair operations and return honest launch status.
- Modify `src/resume_parser.py`: reject every format except PDF/MD/TXT.
- Modify `templates/index.html`: only accept/preview PDF/MD/TXT and render intent/profile/launch states.
- Create `tests/test_resume_intents.py`: intent persistence and manual-file synchronization.
- Create `tests/test_claude_launcher.py`: command and launch behavior without opening a real process.
- Modify `tests/test_web_console.py`: remove destructive live-console test and cover APIs in isolated temp directories.
- Modify `tests/test_profile_schema.py`: enforce Agent-generated profile fields where applicable.
- Modify `.gitignore`: ignore `config/resume_intents.yaml`.
- Modify active Agent/Skill/docs: `CLAUDE.md`, `AGENTS.md`, `.claude/skills/jobhunter/profile.md`, relevant prompts, `README.md`, `README_CN.md`, and `docs/smartjobhunter-agent-design.md`.

---

### Task 1: Persist search intents and reconcile manual files

**Files:**
- Create: `tests/test_resume_intents.py`
- Create: `src/resume_intents.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing tests**

Cover:

```python
def test_sync_new_supported_files_defaults_enabled(tmp_path): ...
def test_sync_preserves_existing_disabled_state(tmp_path): ...
def test_sync_rejects_docx_and_images(tmp_path): ...
def test_save_intent_does_not_create_profile(tmp_path): ...
```

- [ ] **Step 2: Verify RED**

Run: `python -X utf8 -m pytest tests/test_resume_intents.py -v`

Expected: import failure because `src.resume_intents` does not exist.

- [ ] **Step 3: Implement minimal module**

Public API:

```python
SUPPORTED_RESUME_EXTENSIONS = {".pdf", ".md", ".txt"}

def resume_id(filename: str) -> str: ...
def resume_sha256(path: Path) -> str: ...
def load_intents(path: Path) -> dict: ...
def save_intents(path: Path, data: dict) -> None: ...
def upsert_intent(path: Path, *, filename: str, keywords: list[str], job_types: list[str], display_name: str, enabled: bool = True) -> dict: ...
def sync_resume_directory(resume_dir: Path, intent_path: Path) -> dict: ...
```

New supported files receive `enabled: true`, empty keywords, `profile_status: pending_agent`, and SHA256. Existing entries retain user fields.

- [ ] **Step 4: Verify GREEN**

Run: `python -X utf8 -m pytest tests/test_resume_intents.py -v`

- [ ] **Step 5: Ignore local data and commit**

```powershell
git add src/resume_intents.py tests/test_resume_intents.py .gitignore
git commit -m "feat: persist resume search intents"
```

### Task 2: Enforce PDF/MD/TXT globally

**Files:**
- Modify: `tests/test_resume_parser.py` or create it if absent
- Modify: `src/resume_parser.py`
- Modify: `templates/index.html`
- Modify: `src/web_ui.py`

- [ ] **Step 1: Write failing parser and upload-policy tests**

Assert PDF/MD/TXT are accepted and DOCX/PNG/JPG/JPEG are rejected with an explicit unsupported-format result.

- [ ] **Step 2: Verify RED**

Run targeted parser and Web tests; expect current DOCX/image support to violate assertions.

- [ ] **Step 3: Implement shared policy**

Import `SUPPORTED_RESUME_EXTENSIONS` into Web and parser code. Remove DOCX/image extraction and preview branches. Update `<input accept>` to `.pdf,.md,.txt`. Remove JSZip and docx-preview CDN scripts while retaining PDF.js and Markdown rendering.

- [ ] **Step 4: Verify GREEN**

Run targeted tests and static checks for banned extensions:

```powershell
rg -n "docx|png|jpg|jpeg|docx-preview|jszip" src templates/index.html tests
```

Any remaining matches must be explicit rejection tests/messages, not support paths.

- [ ] **Step 5: Commit**

```powershell
git add src/resume_parser.py src/web_ui.py templates/index.html tests
git commit -m "fix: restrict resumes to pdf markdown and text"
```

### Task 3: Build the visible Claude Code launcher

**Files:**
- Create: `tests/test_claude_launcher.py`
- Create: `src/claude_launcher.py`

- [ ] **Step 1: Write failing tests**

Cover command construction, `--permission-mode auto`, named sessions, the repair agent, all selected company IDs, visible Windows console flags, run metadata, missing-Claude errors, and `Popen` failures.

- [ ] **Step 2: Verify RED**

Run: `python -X utf8 -m pytest tests/test_claude_launcher.py -v`

- [ ] **Step 3: Implement minimal launcher**

Public API:

```python
class ClaudeLaunchError(RuntimeError): ...
def build_inspection_prompt(...): ...
def build_repair_prompt(...): ...
def launch_claude(*, prompt: str, session_name: str, run_dir: Path, agent: str | None = None) -> dict: ...
```

On Windows resolve `claude.cmd`, construct `cmd.exe /d /k`, apply `CREATE_NEW_CONSOLE`, and return the real PID. Persist `request.json` before launch and `launch.json` only after success. Never swallow exceptions.

- [ ] **Step 4: Verify GREEN**

Run targeted tests.

- [ ] **Step 5: Commit**

```powershell
git add src/claude_launcher.py tests/test_claude_launcher.py
git commit -m "feat: launch visible Claude Code workflows"
```

### Task 4: Replace fake Web profile and run flows

**Files:**
- Modify: `tests/test_web_console.py`
- Modify: `src/web_ui.py`

- [ ] **Step 1: Write isolated failing API tests**

Cover:

- `/api/resumes/analyze` rejects banned formats.
- `/api/resumes/confirm` saves resume + intent but creates no `profiles/*.md`.
- `/api/resumes` reconciles manually added supported files and defaults them enabled.
- `/api/run` rejects missing keywords and launches Claude instead of Python CLI.
- `/api/health/repair` launches one `crawler-strategy-inspector` session and passes exactly the selected companies.
- launch failures return non-2xx.

Use temp directories and monkeypatch launcher calls. Do not start a real server or modify `config/companies.yaml`.

- [ ] **Step 2: Verify RED**

Run: `python -X utf8 -m pytest tests/test_web_console.py -v`

- [ ] **Step 3: Implement Web delegation**

Remove `_suggest_profile()` as a profile generator. `confirm_resume()` calls `upsert_intent()` only. `run_inspection()` reads the selected intent, builds the Agent prompt, and calls `launch_claude()`. `trigger_health_repair()` passes selected IDs to one Agent session. Import errors and launch failures become HTTP 4xx/5xx responses.

- [ ] **Step 4: Verify GREEN**

Run targeted tests.

- [ ] **Step 5: Commit**

```powershell
git add src/web_ui.py tests/test_web_console.py
git commit -m "fix: route web actions through Claude Code"
```

### Task 5: Update the Web interaction model

**Files:**
- Modify: `templates/index.html`
- Modify: `tests/test_web_console.py`

- [ ] **Step 1: Add failing HTML-contract tests**

Assert supported extensions, `search_intent` state labels, “待补充关键词”, “待 Agent 建档”, and launch status rendering. Assert no DOCX/image preview libraries.

- [ ] **Step 2: Verify RED**

Run the Web contract tests.

- [ ] **Step 3: Implement UI changes**

Resume rows are driven by resume + intent data, not existing profiles. Manual files default enabled. Users edit keywords/job types before running. Starting inspection displays the returned run_id/PID and says “Claude Code 已在新窗口打开”; it does not claim completion.

- [ ] **Step 4: Verify GREEN**

Run Web tests.

- [ ] **Step 5: Commit**

```powershell
git add templates/index.html tests/test_web_console.py
git commit -m "feat: show intent and Claude launch states"
```

### Task 6: Align Agent profile generation and active documentation

**Files:**
- Modify: `.claude/skills/jobhunter/profile.md`
- Modify: `.claude/skills/jobhunter/prompts/build_candidate_profile.md`
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/smartjobhunter-agent-design.md`
- Modify: `docs/plans/2026-06-21-web-console.md`
- Test: existing instruction-drift/profile tests

- [ ] **Step 1: Add failing instruction contract tests**

Require the search-intent/profile distinction, formal profile output path, Claude launch command, `auto` permission mode, single repair Agent, and PDF/MD/TXT-only policy.

- [ ] **Step 2: Verify RED**

Run the relevant profile/platform/contract tests.

- [ ] **Step 3: Update Skill and docs**

Remove image/DOCX instructions. Require Claude to write the formal profile with resume evidence and SHA256 before matching. Document that Python output is fallback and Web buttons open visible Claude Code sessions.

- [ ] **Step 4: Sync reusable Skill if required**

Use `copyskill jobhunter` only after reading its Skill instructions and verifying the project-local Skill is the intended synchronization source.

- [ ] **Step 5: Verify GREEN and commit**

```powershell
git add .claude/skills/jobhunter CLAUDE.md AGENTS.md README.md README_CN.md docs tests
git commit -m "docs: define Agent-driven resume workflow"
```

Do not stage user-owned `docs/quick-reference.md` or `profiles/AI产品经理.md` unless they are explicitly part of a reviewed diff.

### Task 7: Full verification and visible smoke test

**Files:**
- No planned production edits; fix only failures caused by this feature.

- [ ] **Step 1: Run targeted suite**

```powershell
python -X utf8 -m pytest tests/test_resume_intents.py tests/test_claude_launcher.py tests/test_web_console.py -v
```

- [ ] **Step 2: Run full regression**

```powershell
python -X utf8 -m pytest -v
python -X utf8 -m src.evaluation --fail-under 1.0
```

- [ ] **Step 3: Verify repository contracts**

```powershell
git diff --check
git status -sb
```

- [ ] **Step 4: Perform an authorized visible-CMD smoke test**

Launch a harmless Claude Code session through the new launcher with a prompt that only reports readiness and writes no project files. Confirm a new visible CMD opens and the API returns a real PID. Do not start a paid/full inspection without a separate user action.

- [ ] **Step 5: Final local commit if verification fixes were needed**

Commit only scoped files, then report tests, commits, branch, worktree, and all preserved user changes.
