import os
import random

import openpyxl
import pandas as pd

from backend.config import OUTPUT_BASE_PATH, QUESTION_BANK_PATH
from backend.excel_manager import generate_data_entry_sheet
from backend.generator import generate_from_excel
from backend.grader import validate_and_grade
from backend.pdf_manager import generate_answer_key, generate_question_paper
from backend.reporter import generate_all_reports

# Fictional demo roster, mixing Middle Eastern and Western names. Purely
# cosmetic - grading and ranking are keyed on student_id/final_score, never
# on name - but a real-looking name reads far better in a sample report
# than a bare placeholder.
DEMO_STUDENT_NAMES = [
    "Omar Haddad", "Layla Nasser", "Yusuf Karim", "Amira Saleh",
    "Zaid Mansour", "Nadia Rahman", "Hassan Qureshi", "Sara Aziz",
    "Emma Whitfield", "Daniel Brooks", "Grace Sullivan", "Noah Bennett",
    "Khalid Farouk", "Mariam Idris", "Tariq Aziz", "Leila Haddad",
    "Samuel Whitfield", "Olivia Bennett", "Yasmin Karim", "Ibrahim Nasser",
]


def run_demo():
    try:
        if not os.path.exists(QUESTION_BANK_PATH):
            return {"success": False, "errors": ["No question bank loaded. Load a bank first."]}

        school_info = {
            "School Name": "Abako Demo Academy",
            "Campus": "Main",
            "Grade": "Grade 10",
            "Exam Date": "2026-05-05",
        }

        demo_dir = os.path.join(OUTPUT_BASE_PATH, "Demo_Abako_Demo_Academy")
        os.makedirs(demo_dir, exist_ok=True)

        xl = pd.ExcelFile(QUESTION_BANK_PATH)
        chapters = [s for s in xl.sheet_names if s != "Filler"]
        if not chapters:
            return {"success": False, "errors": ["No chapters found in question bank"]}

        per = 60 // len(chapters)
        rem = 60 % len(chapters)
        allocs = {ch: per for ch in chapters}
        for i in range(rem):
            allocs[chapters[i]] += 1

        questions = generate_from_excel(
            QUESTION_BANK_PATH, chapters,
            chapter_allocations=allocs, shuffle=True
        )

        q_pdf  = os.path.join(demo_dir, "Question_Paper.pdf")
        a_pdf  = os.path.join(demo_dir, "Answer_Key.pdf")
        e_xlsx = os.path.join(demo_dir, "Data_Entry_Sheet.xlsx")

        generate_question_paper(q_pdf, school_info, questions)
        generate_answer_key(a_pdf, questions)
        generate_data_entry_sheet(e_xlsx, questions)

        wb = openpyxl.load_workbook(e_xlsx)
        ws = wb["Entry"]

        # The entry sheet's dropdowns are per question: "<answer> - Correct",
        # "Not <answer> - Incorrect" or "Unattempted". The grader only accepts
        # those three shapes, so the demo has to fill the same values a marker
        # would pick rather than a bare "Correct".
        answers = [str(q.get("Correct_Answer", "")) for q in questions]
        options = [
            (f"{a} - Correct", f"Not {a} - Incorrect", "Unattempted")
            for a in answers
        ]

        for i in range(1, 21):
            row = [
                random.choices(opts, weights=[0.6, 0.3, 0.1], k=1)[0]
                for opts in options
            ]
            ws.append([f"S{i:03d}", DEMO_STUDENT_NAMES[i - 1], "2010-01-01"] + row)
        wb.save(e_xlsx)

        result = validate_and_grade(e_xlsx)
        if not result.get("success"):
            return {"success": False, "errors": result.get("errors", ["Grading failed"])}

        generate_all_reports(result, school_info, base_dir=demo_dir)

        return {"success": True, "output_dir": demo_dir}

    except Exception as e:
        return {"success": False, "errors": [str(e)]}
