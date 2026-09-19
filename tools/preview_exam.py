"""Render the exam paper, answer key and entry workbook so they can be
eyeballed as images instead of guessed at from code.

Usage (from the repository root, with the project virtualenv active):

    python tools/preview_exam.py

Every page of the question paper and the answer key is rendered to a PNG at
150 dpi in a fresh, timestamped folder under the system temp directory - kept
outside the repository on purpose, since these are throwaway review images,
not build artifacts.
"""

import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pypdfium2 as pdfium

from backend.excel_manager import generate_data_entry_sheet
from backend.generator import generate_from_excel
from backend.pdf_manager import generate_answer_key, generate_question_paper

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTION_BANK = os.path.join(REPO_ROOT, "resources", "question_bank.xlsx")

PREVIEW_ROOT = os.path.join(tempfile.gettempdir(), "abako-preview-exam")


def _next_round_dir():
    os.makedirs(PREVIEW_ROOT, exist_ok=True)
    existing = [d for d in os.listdir(PREVIEW_ROOT) if d.startswith("round-")]
    nums = []
    for d in existing:
        try:
            nums.append(int(d.split("-", 1)[1]))
        except ValueError:
            continue
    next_num = max(nums, default=0) + 1
    round_dir = os.path.join(PREVIEW_ROOT, f"round-{next_num}")
    os.makedirs(round_dir, exist_ok=True)
    return round_dir


def _real_question_set():
    return generate_from_excel(
        QUESTION_BANK,
        selected_chapters=["Algebra", "Geometry", "Arithmetic"],
        chapter_allocations={"Algebra": 20, "Geometry": 20, "Arithmetic": 20},
        shuffle=True,
    )


def _awkward_question_set():
    """A synthetic 60-question set with deliberately awkward content, so the
    rendering loop exercises the layout's edge cases rather than just the
    easy, short questions in the sample bank."""
    questions = []

    long_question = (
        "A rectangular garden has a length that is three times its width. "
        "The gardener wants to build a path of uniform width around the "
        "entire garden, and the total area covered by the garden and the "
        "path together must equal exactly twice the area of the garden "
        "alone. If the width of the garden is 8 meters, what is the width "
        "of the path, rounded to two decimal places?"
    )
    questions.append({
        "Question_ID": "AWK_LONG",
        "Question_Text": long_question,
        "Correct_Answer": 2.34,
        "Chapter": "Geometry",
    })

    unicode_question = (
        "If πr² = 36π and the diagonal of a square equals "
        "√2 × s, what is r ÷ 2 given that r ≤ 6√2?"
    )
    questions.append({
        "Question_ID": "AWK_UNICODE",
        "Question_Text": unicode_question,
        "Correct_Answer": "3",
        "Chapter": "Algebra",
    })

    questions.append({
        "Question_ID": "AWK_LONGCHAPTER",
        "Question_Text": "[Advanced Number Theory and Modular Arithmetic Foundations] "
                          "What is 17 mod 5?",
        "Correct_Answer": 2,
    })

    for i in range(57):
        questions.append({
            "Question_ID": f"AWK_{i:02d}",
            "Question_Text": f"[Arithmetic] What is {i + 1} + {i + 2}?",
            "Correct_Answer": (2 * i) + 3,
            "Chapter": "Arithmetic",
        })

    return questions


def _render_pdf(pdf_path, out_dir, prefix, dpi=150):
    pdf = pdfium.PdfDocument(pdf_path)
    scale = dpi / 72
    for page_index in range(len(pdf)):
        page = pdf[page_index]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        out_path = os.path.join(out_dir, f"{prefix}-page{page_index + 1}.png")
        image.save(out_path)
        print(f"  wrote {out_path}")
    pdf.close()


def main():
    round_dir = _next_round_dir()
    print(f"Preview round: {round_dir}")

    school_info = {
        "School Name": "Abako Demo Academy",
        "Campus": "Main",
        "Grade": "Grade 10",
        "Exam Date": datetime.date.today().isoformat(),
    }
    long_school_info = {
        "School Name": "The International Academy of Advanced Mathematics and Applied Sciences",
        "Campus": "North Riverside Extension Campus",
        "Grade": "Grade 12",
        "Exam Date": datetime.date.today().isoformat(),
    }

    datasets = [
        ("real", _real_question_set(), school_info),
        ("awkward", _awkward_question_set(), long_school_info),
    ]

    for label, questions, info in datasets:
        print(f"\n[{label}] {len(questions)} questions")
        q_pdf = os.path.join(round_dir, f"{label}_question_paper.pdf")
        a_pdf = os.path.join(round_dir, f"{label}_answer_key.pdf")
        e_xlsx = os.path.join(round_dir, f"{label}_data_entry.xlsx")

        generate_question_paper(q_pdf, info, questions)
        generate_answer_key(
            a_pdf, questions,
            school_name=info["School Name"], campus_name=info["Campus"],
            grade=info["Grade"], exam_date=info["Exam Date"],
        )
        generate_data_entry_sheet(
            e_xlsx, questions,
            school_name=info["School Name"], campus_name=info["Campus"], grade=info["Grade"],
        )

        _render_pdf(q_pdf, round_dir, f"{label}-question-paper")
        _render_pdf(a_pdf, round_dir, f"{label}-answer-key")

    print(f"\nDone. Look at the PNGs in {round_dir}")


if __name__ == "__main__":
    main()
