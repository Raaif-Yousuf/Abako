import random

import pandas as pd

from backend import config


def _sample_unique(df, target, used_ids):
    """Sample up to `target` rows from df, skipping any Question_ID already
    picked (a chapter sheet and the Filler sheet can share Question_IDs, and
    Filler can itself be a selected chapter).

    Returns (picked_records, shortage) where shortage is how many fewer than
    `target` rows were available to satisfy the request.
    """
    if target <= 0:
        return [], 0

    if "Question_ID" in df.columns and used_ids:
        pool = df[~df["Question_ID"].isin(used_ids)]
    else:
        pool = df

    available = len(pool)
    take_n = min(target, available)
    picked = pool.sample(n=take_n).to_dict('records') if take_n > 0 else []

    for rec in picked:
        qid = rec.get("Question_ID")
        if qid is not None:
            used_ids.add(qid)

    return picked, target - take_n


def select_questions(data_dict, selected_chapters, shuffle=True, chapter_allocations=None):
    """
    Core Question Selection Engine Logic.
    data_dict: dict mapping sheet name (chapter) to a pandas DataFrame.
    selected_chapters: list of selected chapter names.
    shuffle: if True, globally shuffle the final question list.
    chapter_allocations: optional dict {ChapterName: int}. When provided, uses exact
        per-chapter counts instead of equal division. Sum must equal config.TOTAL_QUESTIONS.

    Every returned question has a unique Question_ID, and on success exactly
    config.TOTAL_QUESTIONS questions are returned. If the bank cannot supply
    that many unique questions, a ValueError names how many were needed and
    how many were actually available.
    """
    TOTAL_QUESTIONS = config.TOTAL_QUESTIONS

    if "Filler" not in data_dict:
        raise ValueError("Filler tab is missing from the question bank.")

    if chapter_allocations is not None:
        alloc_sum = sum(chapter_allocations.values())
        if alloc_sum != TOTAL_QUESTIONS:
            raise ValueError(
                f"chapter_allocations values sum to {alloc_sum}, must equal {TOTAL_QUESTIONS}."
            )

    num_chapters = len(selected_chapters)
    if num_chapters == 0:
        raise ValueError("No chapters selected; cannot allocate any questions.")

    base_per_chapter = TOTAL_QUESTIONS // num_chapters
    selected_questions = []
    used_ids = set()
    # Remainder filler only applies for equal-division mode
    filler_needed = 0 if chapter_allocations is not None else TOTAL_QUESTIONS - (base_per_chapter * num_chapters)

    for chapter in selected_chapters:
        target = chapter_allocations[chapter] if chapter_allocations is not None else base_per_chapter

        if chapter not in data_dict:
            filler_needed += target
            continue

        df = data_dict[chapter].dropna(how='all')
        picked, shortage = _sample_unique(df, target, used_ids)
        selected_questions.extend(picked)
        filler_needed += shortage

    if filler_needed > 0:
        filler_df = data_dict["Filler"].dropna(how='all')
        pool = filler_df[~filler_df["Question_ID"].isin(used_ids)] if "Question_ID" in filler_df.columns else filler_df
        available = len(pool)

        if available < filler_needed:
            supplied = len(selected_questions) + available
            raise ValueError(
                f"Not enough unique questions in the question bank. "
                f"Needed {TOTAL_QUESTIONS}, but only {supplied} unique question(s) are available."
            )

        picked, _ = _sample_unique(filler_df, filler_needed, used_ids)
        selected_questions.extend(picked)

    if len(selected_questions) != TOTAL_QUESTIONS:
        # Defensive: the accounting above should always add up to exactly
        # TOTAL_QUESTIONS on a non-error path.
        raise ValueError(
            f"Question selection produced {len(selected_questions)} question(s), "
            f"expected {TOTAL_QUESTIONS}."
        )

    if shuffle:
        random.shuffle(selected_questions)
    return selected_questions

def generate_from_excel(file_path, selected_chapters, chapter_allocations=None, shuffle=True):
    """
    Reads the Excel question bank and returns selected questions.
    """
    data_dict = pd.read_excel(file_path, sheet_name=None)

    for sheet_name, df in data_dict.items():
        if "Question_ID" not in df.columns:
            df["Question_ID"] = [f"{sheet_name}_Q{i+1}" for i in range(len(df))]
        df["Chapter"] = sheet_name

    return select_questions(data_dict, selected_chapters, shuffle=shuffle, chapter_allocations=chapter_allocations)
