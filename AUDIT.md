# AUDIT.md — Abako Competition Suite
## Phase 0 Audit Results
**Date:** 2026-05-06 | **Auditor:** Claude Code (claude-sonnet-4-6)

---

## Summary Table

| File | Status | Critical Issues |
|---|---|---|
| `backend/config.py` | **MISSING** | Does not exist |
| `backend/main.py` | **WRONG ARCH** | stdin/stdout IPC — must become Flask |
| `backend/generator.py` | MOSTLY WORKS | Hardcoded 60, no shuffle param, no custom allocations |
| `backend/grader.py` | MOSTLY WORKS | Velocity index hardcodes `/ 30.0` |
| `backend/reporter.py` | PARTIALLY BROKEN | Wrong output structure, wrong logo path, wrong filenames |
| `backend/pdf_manager.py` | **CRITICALLY BROKEN** | Generates multiple-choice; must be free-response |
| `backend/excel_manager.py` | WORKS | Minor: answer default is `'A'` |
| `backend/demo_manager.py` | MOSTLY WORKS | Old output path, thin demo data |
| `main.js` | **WRONG ARCH** | stdin/stdout; no port-reading; no fetch IPC |
| `preload.js` | **WRONG ARCH** | Must expose `window.api.call(endpoint, body)` via fetch |
| `index.html` | **SKELETON ONLY** | No real UI; wrong colors; no forms |
| `tests/test_generator.py` | WORKS | Good coverage |
| `tests/test_grader.py` | WORKS | Implicitly validates hardcoded /30 |
| `tests/test_resilience.py` | WORKS | Good edge-case coverage |

---

## File-by-File Findings

---

### `backend/config.py` — MISSING

**Status: Does not exist.**

The blueprint calls for this file as the single source of all global constants. Nothing that should be in it has been centralized. Instead, constants are scattered and hardcoded across multiple files:

- `generator.py:10`: `TOTAL_QUESTIONS = 60` — local constant, not from config
- `grader.py:88`: `/ 30.0` — `EXAM_DURATION_MINUTES` hardcoded, not from config

**What is missing:**
- `TOTAL_QUESTIONS = 60`
- `EXAM_DURATION_MINUTES = 30`
- `RESOURCES_DIR` path constant
- `OUTPUT_DIR` fallback path constant
- `QUESTION_BANK_PATH` constant

---

### `backend/main.py` — WRONG ARCHITECTURE

**Status: Functional in isolation but architecturally wrong. Must be replaced.**

Currently implements a `while True: sys.stdin.readline()` loop dispatching on `command` keys. This is the old stdin/stdout IPC model. The blueprint mandates a Flask HTTP server.

**What it handles (commands):**
- `ping` → works
- `generate-logic-test` → calls `generator.py`, works
- `generate-files` → calls generator + pdf_manager + excel_manager, works
- `grade-competition` → calls grader + reporter, works
- `run-demo` → calls `demo_manager.py`, works

**Bugs:**
1. No startup JSON line — does not print `{"status": "ready", "port": <PORT>}`. A Flask server would need to do this.
2. Output dir: `output_dir = os.path.join("output", competition_date)` — wrong format per new spec.
3. The fallback mock data in `generate-files` includes `Option_A/B/C/D` and `Correct_Answer: "A"` fields — still in multiple-choice thinking.
4. `grade-competition` passes `all_topics` hardcoded as `["Algebra", "Geometry", "Calculus"]` — not dynamic.

**What is missing:**
- Flask app with `/ping`, `/check-bank`, `/save-bank`, `/get-chapters`, `/generate`, `/grade` endpoints
- Startup JSON line printing the bound port
- Silence after startup (no additional stdout)

---

### `backend/generator.py` — MOSTLY WORKS

**Status: Core selection logic is correct. Needs fixes for config integration and new API contract.**

**What works:**
- `select_questions(data_dict, selected_chapters)`:
  - Raises `ValueError` if Filler tab is missing ✓
  - Computes equal `target_per_chapter = 60 // num_chapters` ✓
  - Remainder filler (when 60 % num_chapters != 0): `filler_needed = 60 - (target * n)` ✓
  - Shortfall filler: when a chapter has fewer questions than needed ✓
  - Strict isolation: only loops over `selected_chapters`, never touches unselected ✓
  - Global shuffle via `random.shuffle` ✓
  - Raises `ValueError` if filler is also insufficient ✓
- `generate_from_excel(file_path, selected_chapters)`:
  - Reads all sheets with `pd.read_excel(..., sheet_name=None)` ✓
  - Auto-generates `Question_ID` if column is missing ✓
  - Assigns `Chapter` field to each row ✓

**Bugs / Missing:**
1. `TOTAL_QUESTIONS = 60` is a local constant (line 10). Must come from `config.TOTAL_QUESTIONS`.
2. No `shuffle` parameter. Blueprint's `/generate` endpoint passes `"shuffle": bool`. Currently always shuffles.
3. No support for `chapter_allocations`. The new `/generate` API spec sends `{"ChapterName": int}` custom per-chapter counts. The generator only does equal division. The new API requires honoring these custom counts directly instead of computing `60 // n`.
4. `generate_from_excel` takes `selected_chapters` but the new spec sends `chapter_allocations` — the function signature will need to change.

**Tests in `test_generator.py` cover:** equal division, shortage + indivisibility remainder, strict isolation. All pass against current code.

---

### `backend/grader.py` — MOSTLY WORKS

**Status: Scoring logic is correct. One hardcoded constant must be fixed.**

**What works:**
- Excel validation: checks for "Entry" and "Metadata" sheets ✓
- Metadata parsing: maps `question_number → chapter` ✓
- Row validation: detects blank, invalid, and missing Q columns ✓
- Scoring: `correct +1`, `incorrect -1`, `unattempted 0` ✓
- Floor: `final_score = max(0, raw_score)` ✓
- Per-chapter breakdown with percentage, correct, incorrect, unattempted ✓
- Ranking: sorted by `final_score` descending, ranks 1..n ✓
- Percentile: `round(((n - rank) / n) * 100, 1)` for n > 1; `100.0` for single student ✓
- Returns `tested_topics` list ✓

**Bugs:**
1. **Line 88:** `velocity_index = round(attempts / 30.0, 2)` — **hardcoded `30`**. Must be `config.EXAM_DURATION_MINUTES`. Listed as known issue in blueprint.

**Minor observations:**
- `Correct_Answer` column is read from Metadata but never used for grading (grader trusts the Entry sheet's pre-marked Correct/Incorrect/Unattempted values). This is correct by design.
- No class-level rank separation. Blueprint says "Top 10 of their class." Current implementation ranks globally. If the app is single-class per run (one school/grade at a time), this is fine. But if multiple classes share one entry sheet, it will not separate ranks by class.

---

### `backend/reporter.py` — PARTIALLY BROKEN

**Status: Functional but output structure, file paths, and filenames are wrong.**

**What works:**
- Individual report PDF generation: name, student ID, score, percentile, rank logic, chart, table ✓
- School report: class average, top 10 table, aggregate topic chart ✓
- Rank display: `if student['rank'] <= 10` shows rank — correct rule ✓
- Stacked bar chart via matplotlib, embedded as PNG in PDF ✓

**Bugs:**
1. **Logo path:** `os.path.join('assets', 'logo.png')` (lines 51, 113). The `assets/` directory does not exist. Blueprint specifies `resources/abako_logo.png`. File is missing anyway (only `abako_sidecar.exe` is in resources). The fallback condition handles the missing file gracefully (no crash), but the logo is never shown.
2. **Output folder structure (critical):** `generate_all_reports` puts all individual reports directly in `out_dir` — no `Individual_Reports/` subfolder. Spec requires:
   ```
   [user-folder]/[SchoolName]_[CampusName]_[Grade]/
   ├── School_Report.pdf
   └── Individual_Reports/
       ├── [StudentName].pdf
   ```
3. **Individual report filename:** Currently `{student_id}_{safe_name}.pdf`. Spec says `[StudentName].pdf` only (sanitized: spaces → underscores, remove special chars).
4. **Rank = N/A behavior:** When `student['rank'] > 10`, reporter shows class average instead of a rank field. Blueprint implies rank should show "N/A" for non-top-10, not be replaced by class avg. Class avg can appear separately.
5. **`safe_name` sanitization (line 172):** Only replaces spaces with `_` and strips `/`. Other special characters (e.g., `.`, `:`, `\`, `*`, `?`) are not removed — could cause file creation errors on Windows.
6. **Fallback output path:** Without `base_dir`, falls back to `output/[date]/Reports`. This doesn't match new spec at all and will conflict with the new folder naming convention.

---

### `backend/pdf_manager.py` — CRITICALLY BROKEN

**Status: The question paper format is wrong. This is the #1 known issue.**

**What works:**
- 2-column layout using `BaseDocTemplate` + `Frame` ✓
- Header with school info (school, campus, grade, date) ✓
- Footer with honor code signature line ✓
- `generate_answer_key`: produces a simple numbered answer list ✓

**Bugs:**
1. **CRITICAL — Multiple choice output (lines 64–68):**
   ```python
   opt_A = q.get('Option_A', 'Option A')
   opt_B = q.get('Option_B', 'Option B')
   opt_C = q.get('Option_C', 'Option C')
   opt_D = q.get('Option_D', 'Option D')
   text = f"<b>{i+1}.</b> {q_text}<br/> A) {opt_A}<br/> B) {opt_B}<br/> C) {opt_C}<br/> D) {opt_D}"
   ```
   The exam is **free-response**. Each question must have a blank answer line/box, not A/B/C/D options. This is the critical fix for Phase 2.

2. **Logo path:** `os.path.join('assets', 'logo.png')` — same wrong path as reporter.py.

3. **`generate_answer_key` default:** `q.get('Correct_Answer', 'A')` defaults to `'A'` if the field is missing. For free-response, the answer should be whatever text is in the bank (e.g., `5π`). The default `'A'` is wrong but won't crash.

4. **Answer key has no header info:** No school name, date, or metadata — just "Answer Key" and numbers. Should at minimum include exam metadata.

---

### `backend/excel_manager.py` — WORKS

**Status: Functionally correct for its purpose.**

**What works:**
- Three sheets: Instructions, Entry, Metadata ✓
- 60 Q columns (Q1–Q60) with dropdown validation (Correct/Incorrect/Unattempted) ✓
- Metadata hidden sheet with question_number, chapter, correct_answer mapping ✓
- Header styling, freeze panes at D2 ✓
- Dropdown validation applied to D2:BK1000 ✓
- Column width adjustments ✓

**Minor issues:**
1. `ans = q.get('Correct_Answer', 'A')` (line 65) — defaults to `'A'` if no answer column exists. For a free-response bank this could be misleading, but doesn't break functionality.
2. No column-width setting for column A (Student ID). Only B (Name) and C (DOB) are explicitly widened.

---

### `backend/demo_manager.py` — MOSTLY WORKS

**Status: Pipeline integration is correct. Demo data is thin and output path is wrong.**

**What works:**
- Full pipeline: select → generate PDFs → generate Excel → fill mock data → grade → report ✓
- 20 mock students with weighted random responses ✓
- Calls `generate_all_reports` with `base_dir` so output is controlled ✓
- Exception handling with descriptive return ✓

**Bugs:**
1. **Thin demo data:** Mock `data_dict` has only `Question_ID` column. No `Question_Text`, `Correct_Answer`, or other fields. The question paper PDF will show the fallback text `"Sample math question containing symbols like π and √..."` for all 60 questions. The answer key will use default `'A'`.
2. **Output path:** `output_dir = os.path.join("output", competition_date)` — old format. Spec is `[user-folder]/[School]_[Campus]_[Grade]/`.
3. **`all_topics` hardcoded** as `["Algebra", "Geometry", "Calculus"]` — fine for demo, but should be derived from the bank for production.

---

### `main.js` — WRONG ARCHITECTURE

**Status: Must be replaced to implement Flask IPC.**

**Current behavior:**
- Spawns `resources/abako_sidecar.exe` directly ✓
- Handles `.exe` not found gracefully with log message ✓
- Reads stdout and broadcasts all JSON to renderer via `python-reply` IPC event
- Accepts `send-to-python` IPC from renderer, writes JSON to `pythonProcess.stdin`
- Kills Python on `will-quit` ✓

**What is wrong:**
1. **No port-reading logic.** New arch requires reading the first stdout line `{"status": "ready", "port": N}` to extract the port, then silencing stdout.
2. **stdin write is the IPC mechanism.** Must be replaced: renderer calls `fetch("http://localhost:PORT/endpoint")`, not stdin writes.
3. **`ipcMain.handle('send-to-python')`** must be replaced with `ipcMain.handle('call-api', ...)` that proxies fetch calls from renderer to Flask, OR renderer can call Flask directly (if `nodeIntegration: false` + CSP allows localhost).
4. **Window size** is 800×600 — too small for the full UI spec with sidebar + forms. Needs to be larger.

---

### `preload.js` — WRONG ARCHITECTURE

**Status: Must be replaced.**

Currently exposes:
- `window.api.sendToPython(data)` → stdin write
- `window.api.onPythonReply(callback)` → stdout event listener

Spec requires:
- `window.api.call(endpoint, body)` → `fetch("http://localhost:PORT/endpoint", { method: "POST", body: JSON.stringify(body) })`

Port must be stored after startup and used in all calls.

---

### `index.html` — SKELETON ONLY

**Status: Full rebuild required.**

Current state: Two buttons (Ping, Run Demo) + a raw JSON output div. No real UI.

**What is missing:**
- Sidebar navigation (Generate | Grade)
- Dark theme (`#0f1117` background, `#1a1d27` cards)
- Generate Mode: bank status bar, form (school/campus/grade/date), chapter list with editable counts, running total counter, shuffle toggle, generate button, result display
- Grade Mode: file picker, folder picker, generate button, result display
- Any connection to the new `window.api.call()` API
- `Inter` font loading from Google Fonts

**What exists:**
- `dist/output.css` — compiled but against the old skeleton; content config (`"*.{html,js}"`) is broad enough to pick up new classes after recompile
- Tailwind classes used are basic utility classes — mostly fine, but the full dark theme palette colors are not in the config `extend` block and must be added or used as arbitrary values

---

### `tailwind.config.js` — VERSION MISMATCH

**Status: Config is Tailwind v3 format; installed package is v4.**

`package.json` has `"tailwindcss": "^4.2.4"` and `"@tailwindcss/cli": "^4.2.4"`. Tailwind v4 does not use `tailwind.config.js` with `module.exports`. It uses a CSS-first configuration via `@theme` in the CSS file. The `src/input.css` only has the three `@tailwind` directives (v3 syntax). This will cause the Tailwind CLI to fail or silently use defaults.

**Note:** `dist/output.css` exists and is non-empty, suggesting a prior compile succeeded, possibly with v3 installed at the time. The current config will likely break when recompiling.

---

### `tests/` — ALL TESTS APPEAR SOUND

**Status: Tests are well-written. Likely all pass against current code.**

**`test_generator.py`:**
- `test_select_questions_equal_division`: 3 chapters, 20 each, no filler, no leakage ✓
- `test_select_questions_shortage_and_indivisible`: 7 chapters, 5-question shortage + remainder = 7 filler ✓
- `test_strict_isolation`: unselected chapter D never touched ✓

**`test_grader.py`:**
- Blank cell detection ✓
- Score floor (Bob: raw=-40, final=0) ✓
- Velocity calculation — `round(59/30, 2)` passes because grader also hardcodes 30 ✓
- Rank=1 for Alice ✓
- Percentile and topic breakdown ✓

**`test_resilience.py`:**
- Corrupted file raises graceful error ✓
- Missing Q columns detected ✓
- 1 student → percentile=100.0 ✓
- 1000 students → all graded ✓

**Note:** No tests currently cover: PDF generation, Excel entry sheet generation, reporter output, the Flask endpoints (don't exist yet), or the demo pipeline. These will be needed in Phase 2.

---

## Missing Files

| Expected File | Status | Notes |
|---|---|---|
| `backend/config.py` | **MISSING** | Must be created in Phase 1 |
| `resources/abako_logo.png` | **MISSING** | Blueprint says "placeholder until client provides" |
| `output/` directory | Not present | Created on demand by code — OK |
| `build_sidecar.py` | **MISSING** | Referenced in `package.json scripts.build` |
| `requirements.txt` | **MISSING** | No Python dependency manifest |

---

## Missing Package Dependencies

| Dependency | Where Needed | Status |
|---|---|---|
| `flask` | `backend/main.py` (new arch) | Not in any manifest |
| `electron-builder` | `package.json scripts.build` | Not in `devDependencies` |
| `requirements.txt` | Python: pandas, openpyxl, reportlab, matplotlib | No file exists |

---

## Ordered Fix Priority for Phase 1 → Phase 2

1. **Create `backend/config.py`** — unblocks all constant fixes.
2. **Convert `backend/main.py` to Flask** — unblocks all UI work.
3. **Update `main.js`** — read startup port, remove stdin IPC.
4. **Update `preload.js`** — expose `window.api.call()` via fetch.
5. **Fix `backend/grader.py`** — replace `30.0` with `config.EXAM_DURATION_MINUTES`.
6. **Fix `backend/pdf_manager.py`** — remove A/B/C/D, add blank answer line per question.
7. **Fix `backend/reporter.py`** — correct output folder structure, filenames, logo path.
8. **Rebuild `index.html`** — full UI per spec.
9. **Fix Tailwind config** — migrate to v4 CSS-first format or pin to v3.
10. **Add `requirements.txt`** and `electron-builder` to `package.json`.
