"""Coverage for the redesigned question paper, answer key and entry workbook.

These exercise the visual/structural contract the printed documents must
keep: the question paper renders every question without splitting one across
a page, unicode maths does not blow up generation, the answer key always
fits on a single page, and the entry workbook keeps every string and sheet
shape the grader depends on.
"""

import os

import openpyxl
import pytest
from pypdf import PdfReader

from backend.excel_manager import generate_data_entry_sheet
from backend.pdf_manager import generate_answer_key, generate_question_paper

SCHOOL_INFO = {
    "School Name": "Crescent Valley Academy",
    "Campus": "Main",
    "Grade": "Grade 9",
    "Exam Date": "2026-05-05",
}


def _questions(n=60):
    return [
        {
            "Question_ID": f"Q{i+1}",
            "Question_Text": f"[Arithmetic] What is {i} + {i + 1}?",
            "Correct_Answer": (2 * i) + 1,
            "Chapter": "Arithmetic",
        }
        for i in range(n)
    ]


def _pdf_text(path):
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_question_paper_renders_60_questions_with_school_and_last_number(tmp_path):
    path = str(tmp_path / "Question_Paper.pdf")
    questions = _questions(60)

    generate_question_paper(path, SCHOOL_INFO, questions)

    assert os.path.exists(path)
    reader = PdfReader(path)
    assert len(reader.pages) >= 1

    text = _pdf_text(path)
    assert "Crescent Valley Academy" in text
    assert "60." in text


def test_answer_key_is_one_page_and_has_every_answer(tmp_path):
    path = str(tmp_path / "Answer_Key.pdf")
    questions = _questions(60)

    generate_answer_key(
        path, questions,
        school_name=SCHOOL_INFO["School Name"], campus_name=SCHOOL_INFO["Campus"],
        grade=SCHOOL_INFO["Grade"], exam_date=SCHOOL_INFO["Exam Date"],
    )

    reader = PdfReader(path)
    assert len(reader.pages) == 1

    text = _pdf_text(path)
    for q in questions:
        assert str(q["Correct_Answer"]) in text


def test_answer_key_works_with_only_two_positional_arguments(tmp_path):
    path = str(tmp_path / "Answer_Key_Minimal.pdf")
    questions = _questions(60)

    generate_answer_key(path, questions)

    reader = PdfReader(path)
    assert len(reader.pages) == 1


def test_question_paper_handles_unicode_maths_without_error(tmp_path):
    path = str(tmp_path / "Question_Paper_Unicode.pdf")
    questions = _questions(10)
    questions[0]["Question_Text"] = (
        "If πr² = 36π and the diagonal of a square equals "
        "√2 × s, what is r ÷ 2 given that r ≤ 6√2?"
    )

    generate_question_paper(path, SCHOOL_INFO, questions)

    assert os.path.exists(path)
    reader = PdfReader(path)
    assert len(reader.pages) >= 1


def test_question_paper_handles_a_three_line_question(tmp_path):
    path = str(tmp_path / "Question_Paper_Long.pdf")
    questions = _questions(10)
    questions[0]["Question_Text"] = (
        "A rectangular garden has a length that is three times its width. "
        "The gardener wants to build a path of uniform width around the "
        "entire garden, and the total area covered by the garden and the "
        "path together must equal exactly twice the area of the garden "
        "alone. If the width of the garden is 8 meters, what is the width "
        "of the path, rounded to two decimal places?"
    )

    generate_question_paper(path, SCHOOL_INFO, questions)

    assert os.path.exists(path)
    reader = PdfReader(path)
    assert len(reader.pages) >= 1


@pytest.fixture
def workbook_path(tmp_path):
    path = str(tmp_path / "Data_Entry_Sheet.xlsx")
    questions = _questions(60)
    generate_data_entry_sheet(
        path, questions,
        school_name=SCHOOL_INFO["School Name"], campus_name=SCHOOL_INFO["Campus"],
        grade=SCHOOL_INFO["Grade"],
    )
    return path, questions


def test_workbook_has_the_three_required_sheets(workbook_path):
    path, _ = workbook_path
    wb = openpyxl.load_workbook(path)

    assert set(wb.sheetnames) >= {"Instructions", "Entry", "Metadata"}
    assert wb["Metadata"].sheet_state == "hidden"
    assert wb["Metadata"]["A1"].value == "EXAM_META"


def test_workbook_entry_header_row(workbook_path):
    path, _ = workbook_path
    wb = openpyxl.load_workbook(path)
    ws = wb["Entry"]

    header = [cell.value for cell in ws[1]]
    expected = ["Student ID", "Name", "Date of Birth"] + [f"Q{i+1}" for i in range(60)]
    assert header == expected


def test_workbook_dropdowns_offer_the_three_exact_grader_strings(workbook_path):
    path, questions = workbook_path
    wb = openpyxl.load_workbook(path)
    ws = wb["Entry"]

    for i, q in enumerate(questions):
        col_idx = i + 4
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        answer = str(q["Correct_Answer"])
        expected_options = {
            f"{answer} - Correct",
            f"Not {answer} - Incorrect",
            "Unattempted",
        }

        target_range = f"{col_letter}2:{col_letter}1000"
        matching_dv = None
        for dv in ws.data_validations.dataValidation:
            if target_range in str(dv.sqref):
                matching_dv = dv
                break

        assert matching_dv is not None, f"No dropdown found for column {col_letter}"
        formula = matching_dv.formula1.strip('"')
        actual_options = set(formula.split(","))
        assert actual_options == expected_options
