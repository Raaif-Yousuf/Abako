import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation


def generate_data_entry_sheet(filename, questions, school_name='', campus_name='', grade=''):
    os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)

    wb = Workbook()

    # --- Tab 1: Instructions ---
    ws_instr = wb.active
    ws_instr.title = "Instructions"
    ws_instr.append(["Instructions for Data Entry"])
    ws_instr.append([])
    ws_instr.append(["1. Do not rename any columns or move the sheets."])
    ws_instr.append(["2. Fill in Student ID, Name, and Date of Birth."])
    ws_instr.append(["3. For Q1 to Q60, use the dropdowns. Each question shows its correct answer as one option."])
    ws_instr.append(["4. Do not modify or unhide the Metadata sheet (it breaks the grader!)."])

    # --- Tab 2: Entry ---
    ws_entry = wb.create_sheet("Entry")

    q_headers = [f"Q{i+1}" for i in range(60)]
    headers = ["Student ID", "Name", "Date of Birth"] + q_headers
    ws_entry.append(headers)

    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws_entry[1]:
        cell.fill = header_fill
        cell.font = header_font

    ws_entry.freeze_panes = "D2"

    # Per-question dynamic dropdowns: "X - Correct, Not X - Incorrect, Unattempted"
    for i, q in enumerate(questions):
        col_idx = i + 4  # Q1 → column D (4)
        col_letter = ws_entry.cell(row=1, column=col_idx).column_letter
        answer = str(q.get('Correct_Answer', ''))
        formula = f'"{answer} - Correct,Not {answer} - Incorrect,Unattempted"'
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        dv.error = 'Your entry is not in the list'
        dv.errorTitle = 'Invalid Entry'
        dv.prompt = 'Select from the dropdown'
        dv.promptTitle = 'Validation'
        ws_entry.add_data_validation(dv)
        dv.add(f"{col_letter}2:{col_letter}1000")

    ws_entry.column_dimensions['B'].width = 25
    ws_entry.column_dimensions['C'].width = 15
    for col_idx in range(4, 64):
        col_letter = ws_entry.cell(row=1, column=col_idx).column_letter
        ws_entry.column_dimensions[col_letter].width = 14

    # --- Tab 3: Metadata (Hidden) ---
    ws_meta = wb.create_sheet("Metadata")
    # Row 1: exam info marker (read by /read-metadata endpoint)
    ws_meta.append(["EXAM_META", school_name, campus_name, grade])
    # Row 2: question data header
    ws_meta.append(["Question_Number", "Chapter", "Correct_Answer"])
    for i, q in enumerate(questions):
        chapter = q.get('Chapter', 'Unknown')
        ans = q.get('Correct_Answer', '')
        ws_meta.append([i + 1, chapter, ans])

    ws_meta.sheet_state = 'hidden'

    wb.save(filename)
