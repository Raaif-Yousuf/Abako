# How Abako Competition Suite works

Notes for anyone (including future me) picking this codebase up. The README is
the short version; this is the part that would otherwise live in my head.

## Shape of the app

An Electron shell talks to a Python process over HTTP on localhost. There is no
database and no network access: everything is a file on disk.

```
index.html / preload.js  ->  main.js  ->  backend/main.py (Flask)
   renderer                  Electron       Python sidecar
```

`main.js` spawns the Python process and reads exactly one line from its stdout:

```json
{"status": "ready", "port": 51234}
```

The port is random, chosen by binding to port 0. `main.js` pushes it to the
renderer over IPC, and `preload.js` exposes `window.api.call(endpoint, body)`
which POSTs JSON to `http://127.0.0.1:<port>/<endpoint>`. After that one line
the Python side writes nothing to stdout ever again, including Werkzeug's
banner, because anything else would corrupt the handshake.

In development the sidecar is the venv interpreter running `backend/main.py`.
In a packaged build it is `resources/abako_sidecar/abako_sidecar.exe`, a
PyInstaller `--onedir` bundle. `main.js` prefers whichever exists.

## The two modes

**Generate** takes an Excel question bank (one sheet per chapter, plus a sheet
named `Filler`) and produces three files:

- `Question_Paper.pdf` - free response, 60 numbered questions with ruled answer
  space. Never multiple choice.
- `Answer_Key.pdf` - the 60 correct answers.
- `Data_Entry_Sheet.xlsx` - the workbook a marker fills in.

**Grade** takes the filled workbook back and produces an individual PDF report
per student plus one school summary.

## Rules I do not change casually

These come from how the competition is actually run, not from the code.

- **Exactly 60 questions.** `config.TOTAL_QUESTIONS`. No exceptions.
- **Filler only.** Questions are divided among the chapters the user selected.
  If a chapter cannot supply its share, the shortfall comes from the `Filler`
  sheet and never from a chapter the user did not select.
- **Scoring.** Correct +1, unattempted 0, incorrect -1. The reported score is
  `max(0, raw)`, so nothing negative appears on a document a parent reads.
- **Velocity index.** `(correct + incorrect) / config.EXAM_DURATION_MINUTES`.
  Never hardcode the 30.
- **Rank is shown only inside the top 10.** Below that it reads N/A, because a
  rank of 143 is not useful feedback for a child.
- **Answers print exactly as stored.** If the bank says `5π`, the key says
  `5π`. No parsing, no reformatting.

## The data entry workbook

This is the fiddly part, and the place two components have to agree.

`generate_data_entry_sheet` writes three sheets:

- `Instructions` - plain text for the person marking.
- `Entry` - `Student ID | Name | Date of Birth | Q1 ... Q60`, one row per
  student, header frozen.
- `Metadata` - hidden. Row 1 is `EXAM_META, school, campus, grade` (read back
  by `/read-metadata` so Grade mode can prefill its form). Row 2 is a header,
  and every row after it is `question number, chapter, correct answer`.

Each question column carries its own dropdown offering exactly three options:

```
<answer> - Correct
Not <answer> - Incorrect
Unattempted
```

`grader.validate_and_grade` accepts those three shapes and nothing else, which
is what makes a mis-typed cell impossible rather than merely discouraged. If
you change either side, change both.

## HTTP endpoints

All POST, all JSON in and out.

| Endpoint | Body | Returns |
|---|---|---|
| `/ping` | `{}` | `{"status": "ok"}` |
| `/check-bank` | `{}` | `{"exists": bool, "filename": str\|null}` |
| `/save-bank` | `{"source_path": str}` | `{"status": "ok"}` |
| `/get-chapters` | `{}` | `{"chapters": [str]}` |
| `/read-metadata` | `{"path": str}` | school, campus, grade from `EXAM_META` |
| `/generate` | school/campus/grade/exam_date, `chapter_allocations`, `shuffle` | `{"output_dir", "files"}` |
| `/grade` | `entry_sheet_path`, `output_folder`, school info | `{"output_dir"}` |
| `/run-demo` | `{}` | runs the whole pipeline on demo data |

## Output layout

```
<folder the user picked>/
├── Question_Paper.pdf
├── Answer_Key.pdf
├── Data_Entry_Sheet.xlsx
├── School_Report.pdf
└── Individual_Reports/
    └── <Student_Name>.pdf
```

Student filenames are sanitised: spaces become underscores, anything that is
not a word character or a hyphen is dropped.

## PDF look and feel

`backend/pdf_theme.py` holds the palette, type scale, spacing scale, page
geometry and the shared header/footer drawing. Every document imports from it,
so the question paper, the answer key, the report card and the school summary
read as one set. Colours come from the wordmark (charcoal `#363434`, red
`#EB3238`); red is a signal colour and marks one number per page, gold appears
only on the certificate. Only the PDF base-14 fonts are used, so no font file
has to survive the PyInstaller bundle.

## Building

```
npx tailwindcss -i src/input.css -o dist/output.css   # after editing index.html
python build_sidecar.py                                # after editing backend/
npm run build                                          # portable Windows .exe
```

`build_sidecar.py` writes `resources/abako_sidecar/`, and `npm run build` runs
it before electron-builder. Neither output is tracked in git.
