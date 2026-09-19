"""Dev tool for the report-card design loop.

Builds a handful of deliberately awkward student cohorts (top scorer, a
zero-score student, a mid performer, a very long name, a single-student
cohort, and a nine-topic run with long topic names), renders the individual
report and school report for each, then rasterises every page of every PDF
to PNG so they can actually be looked at.

Usage (from the repo root):

    python tools/preview_reports.py [--round N]

Images land in a folder outside the repo:
    %LOCALAPPDATA%\\Temp\\abako-preview\\round-<N>\\
"""

import argparse
import os
import random
import re
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pypdfium2 as pdfium  # noqa: E402

from backend.reporter import generate_individual_report, generate_school_report  # noqa: E402

PREVIEW_ROOT = os.path.join(tempfile.gettempdir(), "abako-preview")

MAIN_TOPICS = [
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


def _make_student(student_id, name, topics, topic_pcts, totals=None):
    if totals is None:
        totals = [10] * len(topics)
    topic_breakdown = {}
    total_correct = total_incorrect = 0
    for t, p, total in zip(topics, topic_pcts, totals, strict=True):
        correct = max(0, min(total, round(total * p / 100)))
        remaining = total - correct
        incorrect = remaining // 2
        unattempted = remaining - incorrect
        topic_breakdown[t] = {
            "percentage": round(correct / total * 100, 1) if total else 0.0,
            "correct": correct,
            "incorrect": incorrect,
            "unattempted": unattempted,
            "total": total,
        }
        total_correct += correct
        total_incorrect += incorrect

    raw_score = total_correct - total_incorrect
    final_score = max(0, raw_score)
    attempts = total_correct + total_incorrect
    return {
        "student_id": student_id,
        "name": name,
        "raw_score": raw_score,
        "final_score": final_score,
        "velocity_index": round(attempts / 30, 2),
        "topic_breakdown": topic_breakdown,
    }


def _rank_and_percentile(students):
    students = sorted(students, key=lambda s: s["final_score"], reverse=True)
    n = len(students)
    for i, s in enumerate(students, start=1):
        s["rank"] = i
        s["percentile"] = round(((n - i) / n) * 100, 1) if n > 1 else 100.0
    return students


def _build_main_cohort():
    rng = random.Random(42)
    students = [
        _make_student("S001", "Aarav Sharma", MAIN_TOPICS, [96, 92, 90, 94, 88, 91]),
        _make_student("S002", "Zainab Al-Farouq", MAIN_TOPICS, [8, 5, 10, 8, 5, 6]),
        _make_student("S003", "Priya Venkataraman-Subramaniam of the Riyadh International Campus",
                     MAIN_TOPICS, [64, 58, 70, 55, 60, 62]),
    ]
    for i in range(4, 16):
        pcts = [rng.randint(20, 95) for _ in MAIN_TOPICS]
        students.append(_make_student(f"S{i:03d}", f"Demo Student {i}", MAIN_TOPICS, pcts))
    return _rank_and_percentile(students)


def _build_solo_cohort():
    student = _make_student("S901", "Solo Student", MAIN_TOPICS, [78, 74, 80, 70, 76, 72])
    return _rank_and_percentile([student])


def _build_long_topic_cohort():
    rng = random.Random(7)
    totals = [7, 7, 6, 7, 6, 6, 7, 7, 7]  # sums to 60
    students = [
        _make_student("S501", "Chen Wei", LONG_TOPICS,
                     [70, 55, 80, 60, 40, 65, 58, 72, 50], totals=totals),
    ]
    for i in range(2, 10):
        pcts = [rng.randint(15, 90) for _ in LONG_TOPICS]
        students.append(_make_student(f"S5{i:02d}", f"Cohort Student {i}", LONG_TOPICS, pcts, totals=totals))
    return _rank_and_percentile(students)


def render_pdf_to_pngs(pdf_path, out_dir, dpi=150):
    os.makedirs(out_dir, exist_ok=True)
    base = re.sub(r"[^\w\-]", "_", os.path.splitext(os.path.basename(pdf_path))[0])
    scale = dpi / 72
    pdf = pdfium.PdfDocument(pdf_path)
    out_paths = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            out_path = os.path.join(out_dir, f"{base}_p{i + 1}.png")
            pil_image.save(out_path)
            out_paths.append(out_path)
    finally:
        pdf.close()
    return out_paths


def _next_round(preview_root):
    if not os.path.isdir(preview_root):
        return 1
    existing = [d for d in os.listdir(preview_root) if re.match(r"round-\d+$", d)]
    if not existing:
        return 1
    return max(int(d.split("-")[1]) for d in existing) + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", type=int, default=None, help="Round number (auto-detected if omitted).")
    args = parser.parse_args()

    round_n = args.round or _next_round(PREVIEW_ROOT)
    round_dir = os.path.join(PREVIEW_ROOT, f"round-{round_n}")
    pdf_dir = os.path.join(round_dir, "_pdf")
    png_dir = round_dir
    os.makedirs(pdf_dir, exist_ok=True)

    school_info = {
        "School Name": "Abako Demo Academy",
        "Campus": "Main",
        "Grade": "Grade 10",
        "Exam Date": "2026-05-05",
    }

    jobs = []  # (pdf_path, description)

    main_cohort = _build_main_cohort()
    class_avg = round(sum(s["final_score"] for s in main_cohort) / len(main_cohort), 1)
    by_id = {s["student_id"]: s for s in main_cohort}
    for tag, student in (
        ("top_scorer", by_id["S001"]),
        ("zero_scorer", by_id["S002"]),
        ("long_name", by_id["S003"]),
    ):
        pdf_path = os.path.join(pdf_dir, f"individual_{tag}.pdf")
        generate_individual_report(student, school_info, MAIN_TOPICS, class_avg, pdf_path, demo=True)
        jobs.append((pdf_path, f"individual report - {tag}"))

    school_pdf = os.path.join(pdf_dir, "school_report_main.pdf")
    generate_school_report(main_cohort, school_info, MAIN_TOPICS, school_pdf, demo=True)
    jobs.append((school_pdf, "school report - main cohort"))

    solo_cohort = _build_solo_cohort()
    solo_avg = solo_cohort[0]["final_score"]
    solo_pdf = os.path.join(pdf_dir, "individual_solo_cohort.pdf")
    generate_individual_report(solo_cohort[0], school_info, MAIN_TOPICS, solo_avg, solo_pdf, demo=True)
    jobs.append((solo_pdf, "individual report - solo cohort"))

    solo_school_pdf = os.path.join(pdf_dir, "school_report_solo.pdf")
    generate_school_report(solo_cohort, school_info, MAIN_TOPICS, solo_school_pdf, demo=True)
    jobs.append((solo_school_pdf, "school report - solo cohort"))

    long_cohort = _build_long_topic_cohort()
    long_avg = round(sum(s["final_score"] for s in long_cohort) / len(long_cohort), 1)
    long_pdf = os.path.join(pdf_dir, "individual_nine_topics.pdf")
    generate_individual_report(long_cohort[0], school_info, LONG_TOPICS, long_avg, long_pdf, demo=True)
    jobs.append((long_pdf, "individual report - 9 topics / long names"))

    long_school_pdf = os.path.join(pdf_dir, "school_report_nine_topics.pdf")
    generate_school_report(long_cohort, school_info, LONG_TOPICS, long_school_pdf, demo=True)
    jobs.append((long_school_pdf, "school report - 9 topics / long names"))

    print(f"Round {round_n}: rendering {len(jobs)} PDFs to {png_dir}")
    for pdf_path, desc in jobs:
        pages = render_pdf_to_pngs(pdf_path, png_dir, dpi=150)
        print(f"  {desc}: {len(pages)} page(s) -> {[os.path.basename(p) for p in pages]}")

    print(f"Done. Look at the PNGs under: {round_dir}")


if __name__ == "__main__":
    main()
