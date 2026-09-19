import os

import openpyxl

from backend import config
from backend.grader import validate_and_grade


def test_grader():
    wb = openpyxl.Workbook()
    ws_meta = wb.create_sheet("Metadata")
    ws_meta.append(["Question_Number", "Chapter", "Correct_Answer"])
    for i in range(1, 61):
        ws_meta.append([i, "Algebra" if i <= 30 else "Geometry", "A"])

    ws_entry = wb.create_sheet("Entry")
    ws_entry.append(["Student ID", "Name", "Date of Birth"] + [f"Q{i}" for i in range(1, 61)])

    # Student 1: 60 correct — new format: "A - Correct"
    ws_entry.append(["S1", "Alice", "2010-01-01"] + ["A - Correct"] * 60)

    # Student 2: 10 correct, 50 incorrect. Raw = -40. Floor = 0.
    ws_entry.append(["S2", "Bob", "2010-02-02"] + ["A - Correct"] * 10 + ["Not A - Incorrect"] * 50)

    # Student 3: Blank Q5
    ws_entry.append(["S3", "Charlie", "2010-03-03"] + ["A - Correct"] * 4 + [""] + ["A - Correct"] * 55)

    temp_file = "test_grader.xlsx"
    wb.save(temp_file)

    res = validate_and_grade(temp_file)
    assert not res["success"]
    assert any("Row 4: Q5 is blank" in err for err in res["errors"])

    # Fix the blank error
    ws_entry.cell(row=4, column=8, value="Unattempted")  # Q5 is column H (8th col)
    wb.save(temp_file)

    res = validate_and_grade(temp_file)
    assert res["success"]

    students = res["students"]
    assert len(students) == 3

    alice = next(s for s in students if s["name"] == "Alice")
    assert alice["final_score"] == 60
    assert alice["velocity_index"] == round(60 / config.EXAM_DURATION_MINUTES, 2)
    assert alice["rank"] == 1
    assert alice["topic_breakdown"]["Algebra"]["percentage"] == 100.0

    bob = next(s for s in students if s["name"] == "Bob")
    assert bob["final_score"] == 0  # Flooring verification
    assert bob["velocity_index"] == round(60 / config.EXAM_DURATION_MINUTES, 2)

    charlie = next(s for s in students if s["name"] == "Charlie")
    assert charlie["final_score"] == 59
    assert charlie["velocity_index"] == round(59 / config.EXAM_DURATION_MINUTES, 2)

    if os.path.exists(temp_file):
        os.remove(temp_file)
