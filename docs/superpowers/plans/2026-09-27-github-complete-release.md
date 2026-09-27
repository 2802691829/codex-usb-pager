# Codex USB Pager Complete GitHub Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish one private `codex-usb-pager` GitHub repository containing the current program release, the final four-latch enclosure model, and a complete Chinese usage README.

**Architecture:** Keep the existing program release at repository root and add a self-contained `enclosure/` subtree for the final four-latch model. Copy only approved source, tests, documentation, and verified outputs from the handoff tree; then verify the inventory, secrets scan, enclosure audit, Git state, and remote repository before pushing `main`.

**Tech Stack:** Git, GitHub, Markdown, Python/pytest, FreeCAD Python sources, RP2040 Pico SDK/CMake, PowerShell.

## Global Constraints

- GitHub repository name is exactly `codex-usb-pager` and is private.
- Default branch is `main`.
- Do not upload unrelated `saltyfish` projects, old enclosure baselines, ZIP archives, caches, temporary test folders, object files, or duplicate outputs.
- Do not modify firmware behavior, host-side business logic, or enclosure geometry.
- Do not flash hardware.
- Never store or transmit the user's GitHub password in files, commands, commits, or logs.
- The source workspace remains untouched; all release edits happen in `C:\Users\28026\Documents\saltyfish\codex-usb-pager-github`.

---

### Task 1: Add the final four-latch enclosure release

**Files:**
- Create: `enclosure/cad/*`
- Create: `enclosure/tests/*`
- Create: `enclosure/outputs/*`
- Create: `enclosure/docs/plans/*`
- Create: `enclosure/docs/specs/*`

**Interfaces:**
- Consumes: final handoff source at `codex_usb_pager/docs/enclosure_handoff_2026-07-29`
- Produces: a self-contained `enclosure/` tree whose `outputs/audit.json` has `passed: true`

- [ ] **Step 1: Create the release directories**

```powershell
$release = 'C:\Users\28026\Documents\saltyfish\codex-usb-pager-github\enclosure'
New-Item -ItemType Directory -Force -Path "$release\cad", "$release\tests", "$release\outputs", "$release\docs\plans", "$release\docs\specs"
```

Expected: the five destination directories exist and contain no old baseline files.

- [ ] **Step 2: Copy the editable model sources and geometry tests**

```powershell
$source = 'C:\Users\28026\Documents\saltyfish\codex_usb_pager\docs\enclosure_handoff_2026-07-29'
$release = 'C:\Users\28026\Documents\saltyfish\codex-usb-pager-github\enclosure'
Copy-Item -LiteralPath "$source\cad\audit_blossom_enclosure.py", "$source\cad\build_blossom_enclosure.py", "$source\cad\enclosure_params.py", "$source\cad\openai-blossom-print-clean.svg", "$source\cad\render_blossom_review.FCMacro", "$source\cad\render_blossom_review.py" -Destination "$release\cad"
Copy-Item -LiteralPath "$source\tests\test_audit_blossom_enclosure.py", "$source\tests\test_four_latch_geometry.py", "$source\tests\test_retrofit_params.py", "$source\tests\test_retrofit_source_contract.py" -Destination "$release\tests"
```

Expected: six CAD files and four test files are present.

- [ ] **Step 3: Copy only final four-latch outputs**

```powershell
$final = 'C:\Users\28026\Documents\saltyfish\codex_usb_pager\docs\enclosure_handoff_2026-07-29\outputs\four-latch-retrofit'
$release = 'C:\Users\28026\Documents\saltyfish\codex-usb-pager-github\enclosure\outputs'
Copy-Item -LiteralPath "$final\audit.json", "$final\blossom-enclosure.FCStd", "$final\blossom-enclosure.step", "$final\blossom-front.stl", "$final\blossom-rear.stl", "$final\review-assembly-1-tilted.png", "$final\review-assembly-2-flat.png", "$final\review-assembly-3-locked.png", "$final\review-dimensions.txt", "$final\review-four-latch-cutaway.png", "$final\review-front-exterior.png", "$final\review-front-inside.png", "$final\review-rear-exterior.png", "$final\review-rear-inside.png", "$final\review-screen-setback-section.png", "$final\review-usb-shift.png" -Destination $release
```

Expected: exactly 16 final output files exist; no baseline output or ZIP exists below `enclosure/`.

- [ ] **Step 4: Copy final enclosure design history**

```powershell
$source = 'C:\Users\28026\Documents\saltyfish\codex_usb_pager\docs\enclosure_handoff_2026-07-29'
$release = 'C:\Users\28026\Documents\saltyfish\codex-usb-pager-github\enclosure\docs'
Copy-Item -Path "$source\plans\*.md" -Destination "$release\plans"
Copy-Item -Path "$source\specs\*.md" -Destination "$release\specs"
Copy-Item -LiteralPath "$source\outputs\README.md" -Destination "$release\README.md"
```

Expected: four plan documents, five specification documents, and one enclosure README exist.

- [ ] **Step 5: Verify the enclosure package**

```powershell
$audit = Get-Content -Raw 'enclosure\outputs\audit.json' | ConvertFrom-Json
if (-not $audit.passed) { throw 'Enclosure audit did not pass' }
$failed = $audit.checks.PSObject.Properties | Where-Object { -not $_.Value }
if ($failed) { throw "Failed enclosure checks: $($failed.Name -join ', ')" }
$required = @('blossom-enclosure.FCStd','blossom-enclosure.step','blossom-front.stl','blossom-rear.stl')
$missing = $required | Where-Object { -not (Test-Path -LiteralPath (Join-Path 'enclosure\outputs' $_)) }
if ($missing) { throw "Missing enclosure outputs: $($missing -join ', ')" }
```

Expected: command exits successfully with no output.

- [ ] **Step 6: Commit the enclosure release**

```powershell
git add enclosure
git diff --cached --check
git commit -m "feat: add final four-latch enclosure release"
```

Expected: one commit containing only `enclosure/` additions.

---

### Task 2: Replace the root README with a complete Chinese usage guide

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `PROGRAM_HANDOFF.md`, `ports/rp2040-zero/README.md`, `enclosure/README.md`, and `enclosure/outputs/audit.json`
- Produces: the repository entry point for building, using, flashing, and printing the pager

- [ ] **Step 1: Write the complete README**

Replace `README.md` with a Chinese document containing these exact top-level sections in this order:

```markdown
# Codex USB Pager

## 项目简介
## 硬件与接线
## USB 状态协议
## 屏幕与蜂鸣器行为
## 快速使用已验证固件
## 从源码构建固件
## 主机端工具
## 最终四卡扣外壳
## 测试
## 目录结构
## 维护说明
```

The guide must state all of the following without changing values:

- RP2040-Zero; ST7789 240×240; display GP12/GP11/GP10/GP9/GP8; active-low buzzer GP14; WS2812 GP16.
- `STATE <state> RUN=<n> WAIT=<n> DONE=<n> BAL=<token> EV=<event>` and the valid states/events.
- The verified UF2 path is `firmware-release/codex_pager_rp2040.uf2`; flashing requires the RP2040-Zero BOOT procedure.
- The source build command is `powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1`.
- Host dependencies are Python 3, `pyserial`, and `pytest`; the daemon entry point is `tools/pager_daemon.py`.
- The final editable enclosure is `enclosure/outputs/blossom-enclosure.FCStd`; STEP and two STL paths are listed.
- Printing guidance includes tilted placement, supports on hidden internal surfaces, 1.50 mm ordinary walls, 1.30 mm force-bearing roots/guides, and 0.80 mm minimum known bridges/stops.
- Closing sequence is upper tabs inserted at an angle, front shell laid flat, then slid upward 2.50 mm.
- Printing is allowed only when `enclosure/outputs/audit.json` has `passed=true` and every `checks` value is true.
- The repository intentionally excludes old enclosure baselines, build caches, and unrelated workspace files.

- [ ] **Step 2: Check README paths and commands against the repository**

```powershell
$paths = @(
  'firmware-release\codex_pager_rp2040.uf2',
  'tools\build_rp2040.ps1',
  'tools\pager_daemon.py',
  'enclosure\outputs\blossom-enclosure.FCStd',
  'enclosure\outputs\blossom-enclosure.step',
  'enclosure\outputs\blossom-front.stl',
  'enclosure\outputs\blossom-rear.stl',
  'enclosure\outputs\audit.json'
)
$missing = $paths | Where-Object { -not (Test-Path -LiteralPath $_) }
if ($missing) { throw "README references missing paths: $($missing -join ', ')" }
```

Expected: command exits successfully with no output.

- [ ] **Step 3: Commit the README**

```powershell
git add README.md
git diff --cached --check
git commit -m "docs: add complete Chinese usage guide"
```

Expected: one commit modifying only `README.md`.

---

### Task 3: Validate the complete local release

**Files:**
- Verify: entire repository

**Interfaces:**
- Consumes: Tasks 1 and 2 outputs
- Produces: a clean, upload-ready `main` branch with no detected credential material

- [ ] **Step 1: Scan tracked content for credentials**

```powershell
rg -n -i --hidden --glob '!.git/**' --glob '!firmware-release/*.uf2' --glob '!**/*.png' '(api[_-]?key|access[_-]?token|client[_-]?secret|password\s*[=:]|authorization:\s*bearer|ghp_[A-Za-z0-9]{20,}|github_pat_|-----BEGIN .*PRIVATE KEY-----)' .
```

Expected: no matches and exit code 1 from `rg`.

- [ ] **Step 2: Confirm tracked inventory and repository cleanliness**

```powershell
git status --short
git ls-files | Sort-Object
git log --oneline --decorate -5
```

Expected: `git status --short` is empty; files belong only to the pager program, documentation, and final enclosure.

- [ ] **Step 3: Verify binary size and GitHub limits**

```powershell
$oversized = Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch '\\.git\\' -and $_.Length -ge 100MB }
if ($oversized) { throw "GitHub size limit exceeded: $($oversized.FullName -join ', ')" }
```

Expected: no file is 100 MB or larger.

---

### Task 4: Create the private GitHub repository and push main

**Files:**
- Modify Git metadata: `.git/config`

**Interfaces:**
- Consumes: authenticated GitHub account `2802691829` and clean local `main`
- Produces: `https://github.com/2802691829/codex-usb-pager`

- [ ] **Step 1: Create the repository in the authenticated GitHub UI**

Create `codex-usb-pager`, set visibility to Private, and do not initialize it with a README, `.gitignore`, or license because the local repository already contains commits.

Expected: GitHub shows an empty private repository owned by `2802691829`.

- [ ] **Step 2: Configure the local remote**

```powershell
git remote add origin https://github.com/2802691829/codex-usb-pager.git
git remote -v
```

Expected: fetch and push URLs both point to the exact repository above.

- [ ] **Step 3: Push the release**

```powershell
git push -u origin main
```

Expected: `main` is created on GitHub and tracks `origin/main`.

- [ ] **Step 4: Verify the published result**

Open `https://github.com/2802691829/codex-usb-pager` and confirm that the root README renders, `enclosure/outputs/` contains the four primary model outputs, and the repository is marked Private.

