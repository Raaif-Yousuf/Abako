import os
import random
import pandas as pd
import openpyxl
from backend.config import QUESTION_BANK_PATH, OUTPUT_BASE_PATH
from backend.generator import generate_from_excel
from backend.pdf_manager import generate_question_paper, generate_answer_key
from backend.excel_manager import generate_data_entry_sheet
from backend.grader import validate_and_grade
from backend.reporter import generate_all_reports


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
        for i in range(1, 21):
            ws.append(
                [f"S{i:03d}", f"Demo Student {i}", "2010-01-01"] +
                random.choices(
                    ["Correct", "Incorrect", "Unattempted"],
                    weights=[0.6, 0.3, 0.1], k=60
                )
            )
        wb.save(e_xlsx)

        result = validate_and_grade(e_xlsx)
        if not result.get("success"):
            return {"success": False, "errors": result.get("errors", ["Grading failed"])}

        generate_all_reports(result, school_info, base_dir=demo_dir)

        return {"success": True, "output_dir": demo_dir}

    except Exception as e:
        return {"success": False, "errors": [str(e)]}
