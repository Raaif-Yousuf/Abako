"""Structural checks on the report card / certificate PDFs.

Pixel-level correctness is what tools/preview_reports.py and eyeballing the
rendered PNGs are for. These tests check the load-bearing facts that a
regression would actually break: the individual report is a two-page
document, the student's name and score are present in its extracted text,
and every awkward cohort shape (zero score, a single-student cohort, nine
topics with long names) renders without raising.
"""

from pypdf import PdfReader

from backend.reporter import generate_individual_report, generate_school_report

SCHOOL_INFO = {
    "School Name": "Abako Demo Academy",
    "Campus": "Main",
    "Grade": "Grade 10",
    "Exam Date": "2026-05-05",
}

TOPICS = [
    "Algebra", "Geometry", "Number Theory",
    "Combinatorics", "Statistics & Probability", "Word Problems",
]

LONG_TOPICS = [
    "Algebra", "Geometry", "Number Theory", "Combinatorics",
    "Trigonometry Fundamentals", "Coordinate Geometry",
    "Word Problems and Applications",
    "Statistics, Probability and Data Interpretation",
    "Advanced Sequences and Series for Competition Mathematics",
]


def _topic_breakdown(topics, pct=70, total=10):
    breakdown = {}
    for t in topics:
        correct = round(total * pct / 100)
        remaining = total - correct
        incorrect = remaining // 2
        unattempted = remaining - incorrect
        breakdown[t] = {
            "percentage": round(correct / total * 100, 1),
            "correct": correct,
            "incorrect": incorrect,
            "unattempted": unattempted,
            "total": total,
        }
    return breakdown


def _student(name, student_id, final_score, percentile, rank, pct=70, topics=TOPICS):
    return {
        "student_id": student_id,
        "name": name,
        "raw_score": final_score,
        "final_score": final_score,
        "velocity_index": 1.5,
        "topic_breakdown": _topic_breakdown(topics, pct=pct),
        "rank": rank,
        "percentile": percentile,
    }


def test_individual_report_has_two_pages_with_name_and_score(tmp_path):
    student = _student("Demo Student One", "S001", 42, 88.0, 2)
    out = tmp_path / "report.pdf"
    generate_individual_report(student, SCHOOL_INFO, TOPICS, 30.0, str(out))

    assert out.exists()
    assert out.stat().st_size > 0

    reader = PdfReader(str(out))
    assert len(reader.pages) == 2

    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Demo Student One" in text
    assert "42" in text


def test_individual_report_zero_score_student(tmp_path):
    student = _student("Zero Scorer", "S002", 0, 0.0, None, pct=5)
    out = tmp_path / "zero.pdf"
    generate_individual_report(student, SCHOOL_INFO, TOPICS, 20.0, str(out))

    assert out.exists()
    assert out.stat().st_size > 0
    assert len(PdfReader(str(out)).pages) == 2


def test_individual_report_single_student_cohort(tmp_path):
    student = _student("Solo Student", "S900", 40, 100.0, 1)
    out = tmp_path / "solo.pdf"
    generate_individual_report(student, SCHOOL_INFO, TOPICS, 40.0, str(out))

    assert out.exists()
    assert out.stat().st_size > 0
    assert len(PdfReader(str(out)).pages) == 2


def test_individual_report_nine_topics_long_names(tmp_path):
    student = _student("Cohort Student", "S501", 35, 75.0, 3, topics=LONG_TOPICS)
    out = tmp_path / "nine_topics.pdf"
    generate_individual_report(student, SCHOOL_INFO, LONG_TOPICS, 28.0, str(out))

    assert out.exists()
    assert out.stat().st_size > 0
    assert len(PdfReader(str(out)).pages) == 2


def test_school_report_renders(tmp_path):
    students = [
        _student("Top Student", "S001", 55, 96.0, 1),
        _student("Mid Student", "S002", 30, 50.0, 2),
        _student("Low Student", "S003", 5, 4.0, 3, pct=10),
    ]
    out = tmp_path / "school.pdf"
    generate_school_report(students, SCHOOL_INFO, TOPICS, str(out))

    assert out.exists()
    assert out.stat().st_size > 0
    assert len(PdfReader(str(out)).pages) >= 1
