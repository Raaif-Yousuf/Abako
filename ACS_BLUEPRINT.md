# ACS_BLUEPRINT.md — Abako Competition Suite
## The Single Source of Truth for All Development

---

## 🤖 Instructions for Claude Code (Read Every Session)

**Before touching any code, every session:**
1. Read this entire file.
2. Identify the current `ACTIVE TASK` from the roadmap.
3. Complete that task only.
4. Run `pytest` — all tests must pass before marking anything done.
5. Update the `## 📝 Session Log` at the bottom with what you did.
6. Mark the completed task `[x]` in the roadmap.
7. Stop. Do not proceed to the next task without a new instruction from the developer.

**Hard rules:**
- Never skip the audit/read phase.
- Never print anything from Python to stdout except the single startup JSON line.
- Never use stdin/stdout for IPC after startup.
- Never hardcode file paths — use `backend/config.py` constants.
- Never use React, Vue, Tkinter, or any non-Electron UI framework.
- Never use a database — this app is stateless.
- Always update this file after completing a task.

---

## 🏗 Project Overview

**Client:** Abako Tech (Pakistan) — a scientific calculator company running math competitions.

**What this app does:**
1. **Generate Mode** — Takes a question bank Excel file, lets staff configure a test, and outputs a Question Paper PDF (free-response, not multiple choice), an Answer Key PDF, and a Data Entry Excel sheet.
2. **Grade Mode** — Takes the filled Data Entry Excel, grades all students, and outputs individual student report PDFs and a school-wide report PDF.

**Who uses it:** Abako office staff. Used up to 8 hours a day during competition season. Needs to be clean, fast, and reliable.

---

## 🛠 Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Desktop Shell | Electron.js | Windows-only target |
| UI | HTML + Tailwind CSS (compiled) | No JS frameworks |
| Backend | Python 3.11 via Flask | HTTP server, not stdin/stdout |
| IPC | fetch() from renderer → localhost Flask | Port passed via single stdout line at startup |
| Data | Pandas, Openpyxl | Excel read/write |
| PDFs | ReportLab | Canvas-based layouts |
| Charts | Matplotlib | In-memory, embedded in PDFs |
| Packaging | PyInstaller (sidecar .exe) + electron-builder | Portable Windows .exe |
| Tests | pytest | Python logic only |

---

## 📐 Business Logic Rules (Never Change Without Explicit Instruction)

### The 60-Question Rule
Every test has exactly 60 questions. No exceptions.

### The Filler Rule
- Questions are divided equally among selected chapters.
- If a chapter has fewer questions than needed, the deficit is filled **strictly from the "Filler" tab**.
- **Never pull from unselected chapters.**
- Total must always equal 60.

### Scoring
- Correct: **+1**
- Unattempted: **0**
- Incorrect: **-1**
- Final score floor: **max(0, raw_score)** — no negatives on the report.

### Velocity Index
```
V = (Correct + Incorrect) / EXAM_DURATION_MINUTES
```
Defined in `backend/config.py` as `EXAM_DURATION_MINUTES = 30`. Never hardcode 30.

### Rank
Only displayed if student is in the **Top 10** of their class. Otherwise shown as N/A.

### Answer Format
Answers in the question bank Excel are **plain text** and must be printed exactly as stored. If the answer is `5π`, print `5π`. Do not interpret, convert, or reformat answers.

### Question Paper Format
The exam is **FREE RESPONSE**. Students write a numerical answer on paper.
- Each question: numbered label + question text + a blank answer line/box.
- **No multiple choice options. Ever.**
- 2-column layout, header with school info, Honor Code at bottom.

---

## 📁 File Structure

```
C:\Users\raaif\Abako\
│   index.html              ← Full UI (rebuilt)
│   main.js                 ← Electron main process
│   preload.js              ← Exposes fetch-based API to renderer
│   package.json
│   tailwind.config.js
│   ACS_BLUEPRINT.md        ← THIS FILE
│
├───backend\
│       config.py           ← All global constants (NEW)
│       main.py             ← Flask server (REBUILT)
│       generator.py        ← Question selection logic (keep, verify)
│       grader.py           ← Scoring + analytics (keep, verify)
│       reporter.py         ← PDF report generation (keep, verify)
│       pdf_manager.py      ← Question paper + answer key PDFs (fix format)
│       excel_manager.py    ← Data Entry sheet builder (keep, verify)
│       demo_manager.py     ← Demo/test mode (keep, verify)
│       __init__.py
│
├───resources\
│       question_bank.xlsx  ← Active question bank (user-loaded, persists)
│       abako_logo.png      ← Logo (placeholder until client provides)
│       abako_sidecar.exe   ← PyInstaller output
│
├───src\
│       input.css           ← Tailwind source
│
├───dist\
│       output.css          ← Compiled Tailwind
│
├───output\                 ← Default fallback output dir
│
└───tests\
        test_generator.py
        test_grader.py
        test_resilience.py
        __init__.py
```

---

## 🔌 Flask API Endpoints

All requests are POST with a JSON body. All responses are JSON.

| Endpoint | Body | Returns | Description |
|---|---|---|---|
| `/ping` | `{}` | `{"status": "ok"}` | Health check |
| `/check-bank` | `{}` | `{"exists": bool, "filename": str or null}` | Check if question_bank.xlsx is loaded |
| `/save-bank` | `{"source_path": str}` | `{"status": "ok"}` | Copy user-selected .xlsx to resources/ |
| `/get-chapters` | `{}` | `{"chapters": [str]}` | Read chapter/tab names from question bank |
| `/generate` | see below | `{"output_dir": str, "files": [...]}` | Run full generation pipeline |
| `/grade` | see below | `{"output_dir": str}` | Run full grading + reporting pipeline |

**`/generate` body:**
```json
{
  "school_name": "str",
  "campus_name": "str",
  "grade": "str",
  "exam_date": "YYYY-MM-DD",
  "chapter_allocations": {"ChapterName": int, ...},
  "shuffle": true
}
```

**`/grade` body:**
```json
{
  "entry_sheet_path": "str",
  "output_folder": "str"
}
```

---

## 📂 Output Folder Structure (Grading)

```
[user-selected folder]/
└── [SchoolName]_[CampusName]_[Grade]/
    ├── School_Report.pdf
    └── Individual_Reports/
        ├── [StudentName].pdf
        └── ...
```
Student PDF filename = student name from Entry sheet, sanitized (spaces → underscores, remove special chars).

---

## 🎨 UI Design Spec

**Layout:** Left sidebar navigation (Generate | Grade) + main content panel.

**Color palette (Abako brand — black, red, white):**
- Page background: `#0a0a0a`
- Card/panel background: `#1a1a1a`
- Border: `#2a2a2a`
- Primary accent: `#cc0000` (Abako red)
- Success: `#22c55e`
- Error: `#ff4444`
- Text primary: `#ffffff`
- Text muted: `#a0a0a0`

**Typography:** Inter (Google Fonts). Headings 600 weight, body 400.

**Component rules:**
- Inputs: dark background, visible border, focus ring in accent color.
- Buttons: filled accent for primary actions, ghost for secondary.
- Status messages: colored banner (success green / error red), not an alert box.
- No modals — use inline state changes.
- File pickers: show selected filename inline next to button.

**Generate Mode flow:**
1. Question bank status bar at top ("Using: question_bank.xlsx | Change Bank" button).
2. Form: School Name, Campus Name, Grade, Exam Date.
3. Chapter list (loaded after bank confirmed) with editable question counts.
4. Running total counter — turns red if > 60.
5. Shuffle toggle.
6. Generate button → inline progress → success with output path + "Open Folder" button.

**Grade Mode flow:**
1. File picker → select Data_Entry_Sheet.xlsx.
2. Folder picker → select output root folder.
3. Generate Reports button → inline progress → success with output path + "Open Folder" button.

---

## 🗺 Roadmap

### Phase 0: Audit ⬅ START HERE IF UNSURE
- [x] Read all backend Python files and write AUDIT.md documenting what works, what is broken, and what is missing. **No code changes in this phase.**

### Phase 1: Foundation (Architecture Swap)
- [x] Create `backend/config.py` with all global constants.
- [x] Convert `backend/main.py` from stdin/stdout to Flask server. On startup, print exactly: `{"status": "ready", "port": <PORT>}` then silence.
- [x] Update `main.js` to spawn Python, read the one startup line, extract port, store globally.
- [x] Update `preload.js` to expose `window.api.call(endpoint, body)` using fetch to localhost.
- [x] Verify with `/ping` from renderer.

### Phase 2: Backend Fixes
- [x] Fix `backend/pdf_manager.py` — question paper must be free-response (blank answer line per question, no options).
- [x] Add `/check-bank`, `/save-bank`, `/get-chapters` endpoints to Flask server.
- [x] Audit and fix `backend/generator.py` — verify filler logic, shuffle, chapter allocation.
- [x] Audit and fix `backend/grader.py` — verify scoring floor, velocity index uses config constant.
- [x] Audit and fix `backend/reporter.py` — verify output folder structure matches spec above.
- [x] Run `pytest` — all tests must pass.

### Phase 3: UI Rebuild
- [x] Rebuild `index.html` from scratch per the UI Design Spec above.
- [x] Generate Mode: bank status bar, form, chapter list with editable counts, total counter, shuffle toggle, generate button, result display.
- [x] Grade Mode: file picker, folder picker, generate button, result display.
- [x] Wire all UI actions to `window.api.call()`.
- [x] Compile Tailwind (`npx tailwindcss -i src/input.css -o dist/output.css`).
- [x] Full end-to-end test: generate → manually fill demo data → grade → verify output folder structure.

### Phase 4: Polish & Packaging ✅
- [x] Add Abako logo to all PDFs (real logo at resources/abako_logo.png, paths verified in pdf_manager.py and reporter.py).
- [x] Update color theme to Abako brand (black, red, white) — CSS custom properties updated in index.html, tailwind.config.js updated.
- [x] Add "Run Demo" button (dev only — shown when window.api.isDev is true; hidden in packaged exe).
- [x] Add `/run-demo` endpoint to backend/main.py; rewrote demo_manager.py to use real question bank.
- [x] Create build_sidecar.py (PyInstaller --onedir, --distpath resources, all hidden imports).
- [x] Built sidecar: resources/abako_sidecar/abako_sidecar.exe — confirmed startup JSON line.
- [x] Installed electron-builder, finalized package.json build config (portable target).
- [x] Packaged app: dist/Abako Competition Suite 1.0.0.exe (portable, ~240 MB).
- [x] Removed mainWindow.webContents.openDevTools() from main.js.
- [x] All 10 pytest tests pass.
- [x] Tailwind recompiled.

---

## 📝 Session Log

| Date | Task Completed | Notes |
|---|---|---|
| 2026-05-05 | Phase 1–6 (Gemini build) | stdin/stdout IPC, UI skeleton only, question paper incorrectly generated as multiple choice. Core Python logic written but unverified in new architecture. |
| 2026-05-06 | Switched to Claude Code. New blueprint written. | Architecture decisions: Flask IPC, full UI rebuild, free-response PDF fix, new output folder structure, question bank file management added. |
| 2026-05-06 | Phase 0: Audit complete. | AUDIT.md written. Critical findings: config.py missing, main.py/main.js/preload.js on wrong stdin/stdout arch, pdf_manager.py generates multiple-choice (must be free-response), reporter.py has wrong output folder structure and logo path, grader.py hardcodes /30.0, Tailwind config is v3 format but v4 installed. All 3 test files appear sound. Full fix order documented in AUDIT.md. |
| 2026-05-06 | Phase 1: Foundation complete. | Created backend/config.py with all constants. Rewrote backend/main.py as Flask server (6 endpoints: /ping /check-bank /save-bank /get-chapters /generate /grade); stdout silenced after startup JSON via NullWriter. Rewrote main.js: 1200×800 window, spawnBackend with python→sidecar fallback, ipcMain handlers for get-port/open-file/open-folder. Rewrote preload.js: window.api.call(), openFile(), openFolder(). Created requirements.txt. Downgraded Tailwind v4→v3 in package.json (removed @tailwindcss/cli). Ran npm install + npx tailwindcss compile → dist/output.css. Verified: Flask prints exactly one JSON line to stdout, /ping and /check-bank respond correctly. Known mismatches flagged in comments: chapter_allocations ignored by generator, shuffle param ignored, school_info missing from /grade payload. |
| 2026-05-06 | Phase 2: Backend Fixes complete. | grader.py: replaced hardcoded /30.0 with /config.EXAM_DURATION_MINUTES; added `from backend import config`. generator.py: rewrote with config.TOTAL_QUESTIONS, shuffle=True param, chapter_allocations dict support (validates sum == TOTAL_QUESTIONS, uses exact counts, still applies filler for shortages); updated generate_from_excel() signature. pdf_manager.py: fixed logo path (resources/abako_logo.png), rewrote generate_question_paper() as free-response format — numbered label + question text + "Answer: ___" blank line, no A/B/C/D options. reporter.py: fixed logo path; rewrote generate_all_reports() for [base_dir]/[School]_[Campus]_[Grade]/Individual_Reports/[Name].pdf structure; filename sanitized with re.sub; rank field shows "N/A" if rank > 10; class average is always its own separate field. main.py: wired shuffle + chapter_allocations into /generate; added school_name/campus_name/grade to /grade body → school_info passed to reporter. tests: test_grader.py uses config.EXAM_DURATION_MINUTES in velocity assertions; test_generator.py adds test_chapter_allocations, test_chapter_allocations_invalid_sum, test_shuffle_false_deterministic. All 10 tests pass. |
| 2026-05-06 | Phase 3: UI Rebuild complete. | Created create_test_bank.py → generates resources/question_bank.xlsx (3 chapters × 20 questions + 15 Filler). Rebuilt index.html from scratch: two-panel layout (220px sidebar + main), CSS custom properties, Inter font, Generate Mode (bank bar, exam details 2-col grid, chapter config with running total, shuffle toggle, generate button/result), Grade Mode (3-step: entry sheet picker, exam info form, folder picker + generate button). Added shell-open-path IPC handler to main.js + get-version handler. Updated preload.js: openPath(), appVersion. Installed Python deps (flask, flask-cors, pandas, openpyxl, etc.) in venv. Compiled Tailwind. End-to-end test: /generate with chapter_allocations={Algebra:20, Geometry:20, Arithmetic:20} → produced Question_Paper.pdf, Answer_Key.pdf, Data_Entry_Sheet.xlsx in output/Test_School_Main_Campus_Grade_7/. All 10 pytest tests pass. Electron app launches and stays open. |
| 2026-05-06 | Bug fixes (manual testing). Phase 4 NOT started. | Bug 1 (Change Bank does nothing): added try/catch wrapper to change-bank-btn click handler so any IPC or fetch error is surfaced in the error banner instead of swallowed silently. Bug 2 (Escape can't exit fullscreen): added fullscreenable:false to BrowserWindow options; imported globalShortcut and Menu from electron; registered F11 (toggle fullscreen) and Escape (exit fullscreen only) via globalShortcut.register inside app.whenReady; added globalShortcut.unregisterAll() to will-quit handler. Bug 3 (Grade tab won't switch): changed panel.style.display from '' (relying on browser default) to explicit 'block' in the nav-item click handler for both panels. Bug 4 (default Electron menu): added buildMenu() which calls Menu.buildFromTemplate with File → (Open Output Folder, separator, Exit) and Help → (About); called before createWindow(). No Phase 4 tasks touched. |
| 2026-05-06 | Bug fix session — Grade tab + Change Bank (two persistent bugs). | Root-cause analysis: The entire renderer script halted before any event listeners were attached because `window.api.appVersion` (line 446, bare property access) would throw TypeError if preload.js failed for any reason, stopping all subsequent code. Fix 1 (Grade tab not clickable): wrapped the full `<script>` block in `document.addEventListener('DOMContentLoaded', ...)` so it runs after full DOM parse; protected the `window.api.appVersion` access in a try/catch with optional-chaining guard; added `console.log('[nav] clicked:', panel)` + `console.log('grade clicked')` inside nav click handler for DevTools visibility. Fix 2 (Change Bank does nothing): added `pingFlask()` (Node.js `http` module POST to /ping) and `waitForBackend()` (polls every 500 ms up to 10 s) to main.js; `waitForBackend(flaskPort)` is now awaited after `startPythonProcess()` and before `createWindow()`, ensuring Flask is verified ready before the window opens; added `console.log` at each step of the change-bank-btn handler (file picker return, path before save-bank call, save-bank response). Fix 3 (backend status dot): added an 8 px dot (red by default) to the sidebar footer; `checkBackendStatus()` calls /ping on page load and after a successful bank change — turns green on 200 OK, stays red on failure. Phase 4 NOT started. |
| 2026-05-06 | Three bug fixes: IPC channel rename, venv Python, sidebar credit. | Bug 1 (window.api.openFile undefined): renamed IPC channels from `open-file`→`open-file-dialog` and `open-folder`→`open-folder-dialog` in both preload.js (ipcRenderer.invoke) and main.js (ipcMain.handle) to ensure consistent naming; added `isDev: process.env.NODE_ENV !== 'production'` to the contextBridge so window.api now exposes all six expected properties (appVersion, isDev, call, openFile, openFolder, openPath). Bug 2 (red status dot / Flask not starting): root cause was system `python` resolving to a Python installation without Flask; fix is `startPythonProcess()` now prefers `venv/Scripts/python.exe` when it exists, falling back to system `python` only if the venv is absent. Added detailed logging to `spawnBackend()`: logs command being run, every stdout line, every stderr line, spawn errors, and exit code. UI: added "· Made by Raaif Yousuf" in `--muted` color at 11px in the sidebar footer on the same line as the status dot and version number. |
| 2026-05-07 | Renderer IPC architecture fix — port push model, status dot, file pickers. | Bug 1 (renderer never gets Flask port): switched preload.js from pull model (`ipcRenderer.invoke('get-port')` on every call) to push model. main.js now calls `mainWindow.webContents.send('backend-port', flaskPort)` inside a `webContents.once('did-finish-load', ...)` handler added in `app.whenReady()` after `createWindow()`. preload.js now stores port in a module-level `let flaskPort = null`, populates it via `ipcRenderer.on('backend-port', ...)`, and `call()` uses the stored variable with a "Backend not ready yet" guard if it is still null. Bug 2 (status dot stays red): removed the eager IIFE in index.html that called `checkBackendStatus()` immediately on DOMContentLoaded. Replaced with `window.addEventListener('backend-ready', ...)` — preload.js dispatches the `backend-ready` CustomEvent on `window` after storing the port, guaranteeing the port is known before the first /ping. Bug 3 (openFile/openFolder): confirmed `ipcMain.handle('open-file-dialog')` and `ipcMain.handle('open-folder-dialog')` are at module level in main.js (lines 223–236), which is synchronously before any async code including `app.whenReady()` and `createWindow()` — no reordering needed. All five handlers (get-port, get-version, shell-open-path, open-file-dialog, open-folder-dialog) verified present and correctly named to match preload.js invoke calls. |
| 2026-05-09 | Phase 4: Polish & Packaging complete. | 1. Logo: verified resources/abako_logo.png exists; pdf_manager.py and reporter.py both load it correctly — no code changes needed. 2. Colors: updated all CSS custom properties in index.html to Abako brand (bg #0a0a0a, card #1a1a1a, border #2a2a2a, accent #cc0000, error #ff4444, text #ffffff, muted #a0a0a0); updated all derived rgba() values and button hover colors; updated tailwind.config.js with accent color. 3. Run Demo: rewrote backend/demo_manager.py to use real question_bank.xlsx via generate_from_excel, renamed function to run_demo(); added /run-demo POST endpoint to backend/main.py; added hidden demo-area div to sidebar in index.html; JS shows button only when window.api.isDev is true; click calls run-demo and shows result banner in active panel. 4. PyInstaller sidecar: rewrote build_sidecar.py with --onedir, --distpath resources, all 6 hidden imports, --add-data for xlsx and logo; built successfully → resources/abako_sidecar/abako_sidecar.exe; confirmed startup JSON line via bash test. Updated main.js sidecar paths from abako_sidecar.exe to abako_sidecar/abako_sidecar.exe (both dev and production paths). 5. electron-builder: installed electron-builder; updated package.json build script to "python build_sidecar.py && electron-builder --win portable"; added build config block (appId, productName, win portable target, files, extraResources); ran npm run build → dist/Abako Competition Suite 1.0.0.exe (240 MB portable). 6. Final: removed mainWindow.webContents.openDevTools(); all 10 pytest tests pass; Tailwind recompiled; How to Build section added to blueprint; Phase 4 marked complete. |
| 2026-05-09 | 5-fix bug-fix session. | Fix 1 (Open Folder): wiring was correct (preload.js openPath → ipcMain shell-open-path → shell.openPath); added console.log in showBanner click handler and ipcMain handler for path tracing. Fix 2 (Logo bigger/centered in PDFs): pdf_manager.py — logo resized to 180×50pt, centered horizontally via (page_w - logo_w)/2; school info line moved below logo and centered; topMargin increased 1.5→2.0*inch and frame heights updated accordingly. reporter.py — both generate_individual_report and generate_school_report logo updated to 180×50pt with hAlign='CENTER'. Fix 3 (Answer Key header): generate_answer_key() signature updated to accept school_name/campus_name/grade/exam_date; now draws centered logo + header info line before the answer list; call in main.py /generate updated to pass these fields. Fix 4 (Dynamic per-question dropdowns): excel_manager.py rewrites the DataValidation loop — one DataValidation per question column with formula "{answer} - Correct,Not {answer} - Incorrect,Unattempted"; Metadata tab now starts with EXAM_META row (school/campus/grade), then the question header, then question rows. grader.py: int(row[0]) wrapped in try/except to skip EXAM_META and header rows; validation now uses .endswith('- Correct')/.endswith('- Incorrect')/val==None; classification updated to match. test_grader.py and test_resilience.py updated to "A - Correct"/"Not A - Incorrect"/"Unattempted" format. Fix 5 (Grade mode auto-load): excel_manager.py stores school_name/campus_name/grade in EXAM_META row of Metadata tab; /read-metadata POST endpoint added to main.py (reads EXAM_META row, returns school/campus/grade); index.html select-entry-btn handler now calls read-metadata after file selection and auto-populates g-school-name/g-campus-name/g-grade; metadata-warning div shown if read fails. All 10 pytest tests pass. |

---

## ⚠️ Known Issues (Fix Before Shipping)

All critical issues resolved in Phases 1–4.

---

## 🔨 How to Build

### Recompile Tailwind CSS
```
npx tailwindcss -i src/input.css -o dist/output.css
```
Run this whenever `index.html` or `tailwind.config.js` changes.

### Rebuild the Python Sidecar
```
venv\Scripts\python.exe build_sidecar.py
```
Output: `resources/abako_sidecar/abako_sidecar.exe`  
Requires PyInstaller in the venv (`pip install pyinstaller`).  
Needed when any `backend/*.py` file changes.

### Package the Electron App (portable Windows .exe)
```
npm run build
```
This runs `python build_sidecar.py` first, then `electron-builder --win portable`.  
Output: `dist/Abako Competition Suite <version>.exe`
