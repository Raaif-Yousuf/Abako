"""Pins down the percentile-rank and competition-ranking fix in backend.grader.

Percentile definition used: the midrank (mean rank) percentile standard in
educational measurement:

    percentile = (below + 0.5 * tied_including_self) / n * 100

rounded to one decimal, where `below` is the number of students scoring
strictly lower than this student and `tied_including_self` is the number of
students (including this one) on the same final_score. Tied students
therefore always receive the same percentile, and an all-tied cohort lands
at 50.0 rather than being told everyone is at the bottom. A cohort of
exactly one student always gets 100.0.

Rank uses competition ranking ("1224"): tied students share the better rank
and the next distinct score skips the tied places.
"""

import openpyxl

from backend.grader import validate_and_grade


def _build_workbook(path, scores):
    """Build a gradeable workbook where student i's final_score == scores[i].

    Each student answers `score` questions correctly and leaves the rest
    unattempted, so raw_score == final_score == score (no negative clamping
    involved).
    """
    wb = openpyxl.Workbook()
    ws_meta = wb.create_sheet("Metadata")
    ws_meta.append(["Question_Number", "Chapter", "Correct_Answer"])
    for i in range(1, 61):
        ws_meta.append([i, "General", "A"])

    ws_entry = wb.create_sheet("Entry")
    ws_entry.append(["Student ID", "Name", "Date of Birth"] + [f"Q{i}" for i in range(1, 61)])

    for idx, score in enumerate(scores, start=1):
        responses = ["A - Correct"] * score + ["Unattempted"] * (60 - score)
        ws_entry.append([f"S{idx}", f"Student{idx}", "2010-01-01"] + responses)

    wb.save(path)


def _grade(tmp_path, scores, filename="grade.xlsx"):
    path = tmp_path / filename
    _build_workbook(str(path), scores)
    result = validate_and_grade(str(path))
    assert result["success"], result.get("errors")
    return {s["name"]: s for s in result["students"]}


def test_all_tied_cohort_gets_same_percentile(tmp_path):
    # n=5, everyone on 30: below=0, tied=5 -> (0 + 0.5*5)/5*100 = 50.0
    students = _grade(tmp_path, [30, 30, 30, 30, 30])
    percentiles = {s["percentile"] for s in students.values()}
    ranks = {s["rank"] for s in students.values()}
    assert percentiles == {50.0}
    assert ranks == {1}


def test_cohort_of_one_is_100th_percentile(tmp_path):
    students = _grade(tmp_path, [17])
    student = students["Student1"]
    assert student["percentile"] == 100.0
    assert student["rank"] == 1


def test_cohort_of_two(tmp_path):
    # n=2, scores 40 and 20 (each unique, tied=1):
    # 40: below=1, tied=1 -> (1 + 0.5)/2*100 = 75.0
    # 20: below=0, tied=1 -> (0 + 0.5)/2*100 = 25.0
    students = _grade(tmp_path, [40, 20])
    top = students["Student1"]
    bottom = students["Student2"]
    assert top["rank"] == 1
    assert top["percentile"] == 75.0
    assert bottom["rank"] == 2
    assert bottom["percentile"] == 25.0


def test_normal_spread_exact_values(tmp_path):
    # Scores (desc): 60, 45, 45, 30, 15, 15, 15, 0 -- n=8.
    # counts: 60:1, 45:2, 30:1, 15:3, 0:1
    # 60: below=7, tied=1 -> (7 + 0.5)/8*100   = 93.75 -> 93.8
    # 45: below=5, tied=2 -> (5 + 1.0)/8*100   = 75.0
    # 30: below=4, tied=1 -> (4 + 0.5)/8*100   = 56.25 -> 56.2
    # 15: below=1, tied=3 -> (1 + 1.5)/8*100   = 31.25 -> 31.2
    #  0: below=0, tied=1 -> (0 + 0.5)/8*100   = 6.25  -> 6.2
    scores = [60, 45, 45, 30, 15, 15, 15, 0]
    students = _grade(tmp_path, scores)

    expected = {
        "Student1": (60, 1, 93.8),
        "Student2": (45, 2, 75.0),
        "Student3": (45, 2, 75.0),
        "Student4": (30, 4, 56.2),
        "Student5": (15, 5, 31.2),
        "Student6": (15, 5, 31.2),
        "Student7": (15, 5, 31.2),
        "Student8": (0, 8, 6.2),
    }
    for name, (score, rank, percentile) in expected.items():
        s = students[name]
        assert s["final_score"] == score
        assert s["rank"] == rank
        assert s["percentile"] == percentile


def test_top_scorer_highest_bottom_scorer_lowest(tmp_path):
    scores = [60, 45, 45, 30, 15, 15, 15, 0]
    students = _grade(tmp_path, scores)
    top_percentile = students["Student1"]["percentile"]
    bottom_percentile = students["Student8"]["percentile"]
    all_percentiles = [s["percentile"] for s in students.values()]
    assert top_percentile == max(all_percentiles)
    assert bottom_percentile == min(all_percentiles)


def test_twenty_distinct_scores_top_and_bottom(tmp_path):
    # 20 distinct scores, each tied=1, n=20:
    # top: below=19, tied=1 -> (19 + 0.5)/20*100 = 97.5
    # bottom: below=0, tied=1 -> (0 + 0.5)/20*100 = 2.5
    scores = list(range(59, 39, -1))  # 59, 58, ..., 40 (20 distinct scores)
    assert len(scores) == 20
    students = _grade(tmp_path, scores)

    assert students["Student1"]["final_score"] == 59
    assert students["Student1"]["percentile"] == 97.5
    assert students["Student20"]["final_score"] == 40
    assert students["Student20"]["percentile"] == 2.5


def test_percentile_is_monotonic_in_score(tmp_path):
    scores = list(range(59, 39, -1))  # 20 distinct scores, descending
    students = _grade(tmp_path, scores)

    ordered = sorted(students.values(), key=lambda s: s["final_score"])
    percentiles = [s["percentile"] for s in ordered]
    assert percentiles == sorted(percentiles)
    assert len(set(percentiles)) == len(percentiles)  # all distinct, strictly increasing


def test_competition_ranking_two_tie_groups(tmp_path):
    # Scores (desc): 50, 50, 50, 30, 30, 10 -- two separate groups of ties
    # plus a unique bottom score.
    scores = [50, 50, 50, 30, 30, 10]
    students = _grade(tmp_path, scores)

    for name in ("Student1", "Student2", "Student3"):
        assert students[name]["rank"] == 1
    for name in ("Student4", "Student5"):
        assert students[name]["rank"] == 4
    assert students["Student6"]["rank"] == 6
