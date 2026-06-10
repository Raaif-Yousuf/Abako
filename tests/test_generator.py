import random
import pytest
import numpy as np
import pandas as pd
from backend.generator import select_questions

def test_select_questions_equal_division():
    # 3 chapters, should get 20 each
    data_dict = {
        "Chapter A": pd.DataFrame({"Question_ID": [f"A_{i}" for i in range(30)]}),
        "Chapter B": pd.DataFrame({"Question_ID": [f"B_{i}" for i in range(30)]}),
        "Chapter C": pd.DataFrame({"Question_ID": [f"C_{i}" for i in range(30)]}),
        "Chapter D": pd.DataFrame({"Question_ID": [f"D_{i}" for i in range(30)]}), # Unselected
        "Filler": pd.DataFrame({"Question_ID": [f"Filler_{i}" for i in range(50)]})
    }
    
    questions = select_questions(data_dict, ["Chapter A", "Chapter B", "Chapter C"])
    assert len(questions) == 60
    
    # Count occurrences
    a_count = sum(1 for q in questions if q["Question_ID"].startswith("A_"))
    b_count = sum(1 for q in questions if q["Question_ID"].startswith("B_"))
    c_count = sum(1 for q in questions if q["Question_ID"].startswith("C_"))
    f_count = sum(1 for q in questions if q["Question_ID"].startswith("Filler_"))
    d_count = sum(1 for q in questions if q["Question_ID"].startswith("D_"))
    
    assert a_count == 20
    assert b_count == 20
    assert c_count == 20
    assert f_count == 0
    assert d_count == 0

def test_select_questions_shortage_and_indivisible():
    # 7 chapters selected => 60 // 7 = 8 each. (7 * 8 = 56). Remainder = 4.
    # Chapter A has only 5 questions (shortage of 3).
    # Total filler needed = 4 (remainder) + 3 (shortage) = 7.
    data_dict = {
        "Chapter A": pd.DataFrame({"Question_ID": [f"A_{i}" for i in range(5)]}),
        "Filler": pd.DataFrame({"Question_ID": [f"Filler_{i}" for i in range(50)]})
    }
    # Add Chapter B through G with plenty of questions
    for letter in ['B', 'C', 'D', 'E', 'F', 'G']:
        data_dict[f"Chapter {letter}"] = pd.DataFrame({"Question_ID": [f"{letter}_{i}" for i in range(20)]})
        
    selected = [f"Chapter {l}" for l in ['A', 'B', 'C', 'D', 'E', 'F', 'G']]
    questions = select_questions(data_dict, selected)
    
    assert len(questions) == 60
    a_count = sum(1 for q in questions if q["Question_ID"].startswith("A_"))
    f_count = sum(1 for q in questions if q["Question_ID"].startswith("Filler_"))
    
    assert a_count == 5
    assert f_count == 7

def test_strict_isolation():
    # Ensure unselected chapter D is NEVER pulled from
    data_dict = {
        "Chapter A": pd.DataFrame({"Question_ID": [f"A_{i}" for i in range(10)]}), # Shortage of 20
        "Chapter D": pd.DataFrame({"Question_ID": [f"D_{i}" for i in range(100)]}), # Has plenty
        "Filler": pd.DataFrame({"Question_ID": [f"Filler_{i}" for i in range(50)]})
    }
    questions = select_questions(data_dict, ["Chapter A"])

    assert len(questions) == 60
    d_count = sum(1 for q in questions if q["Question_ID"].startswith("D_"))
    assert d_count == 0  # Must be strictly isolated
    f_count = sum(1 for q in questions if q["Question_ID"].startswith("Filler_"))
    assert f_count == 50  # Pulled from filler instead of Chapter D

def test_chapter_allocations():
    # Custom allocations: Chapter A gets 25, Chapter B gets 35 (sum = 60)
    data_dict = {
        "Chapter A": pd.DataFrame({"Question_ID": [f"A_{i}" for i in range(30)]}),
        "Chapter B": pd.DataFrame({"Question_ID": [f"B_{i}" for i in range(40)]}),
        "Filler": pd.DataFrame({"Question_ID": [f"Filler_{i}" for i in range(30)]}),
    }
    allocations = {"Chapter A": 25, "Chapter B": 35}
    questions = select_questions(data_dict, ["Chapter A", "Chapter B"], chapter_allocations=allocations)

    assert len(questions) == 60
    a_count = sum(1 for q in questions if q["Question_ID"].startswith("A_"))
    b_count = sum(1 for q in questions if q["Question_ID"].startswith("B_"))
    assert a_count == 25
    assert b_count == 35

def test_chapter_allocations_invalid_sum():
    data_dict = {
        "Chapter A": pd.DataFrame({"Question_ID": [f"A_{i}" for i in range(30)]}),
        "Filler": pd.DataFrame({"Question_ID": [f"Filler_{i}" for i in range(30)]}),
    }
    with pytest.raises(ValueError, match="sum"):
        select_questions(data_dict, ["Chapter A"], chapter_allocations={"Chapter A": 50})

def test_shuffle_false_deterministic():
    # With the same numpy/random seed and shuffle=False, two calls must return identical order.
    data_dict = {
        "Chapter A": pd.DataFrame({"Question_ID": [f"A_{i}" for i in range(30)]}),
        "Chapter B": pd.DataFrame({"Question_ID": [f"B_{i}" for i in range(30)]}),
        "Filler": pd.DataFrame({"Question_ID": [f"Filler_{i}" for i in range(30)]}),
    }

    random.seed(42)
    np.random.seed(42)
    result1 = select_questions(data_dict, ["Chapter A", "Chapter B"], shuffle=False)

    random.seed(42)
    np.random.seed(42)
    result2 = select_questions(data_dict, ["Chapter A", "Chapter B"], shuffle=False)

    assert len(result1) == 60
    assert [q["Question_ID"] for q in result1] == [q["Question_ID"] for q in result2]
