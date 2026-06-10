import pandas as pd
import random
from backend import config

def select_questions(data_dict, selected_chapters, shuffle=True, chapter_allocations=None):
    """
    Core Question Selection Engine Logic.
    data_dict: dict mapping sheet name (chapter) to a pandas DataFrame.
    selected_chapters: list of selected chapter names.
    shuffle: if True, globally shuffle the final question list.
    chapter_allocations: optional dict {ChapterName: int}. When provided, uses exact
        per-chapter counts instead of equal division. Sum must equal config.TOTAL_QUESTIONS.
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
    base_per_chapter = TOTAL_QUESTIONS // num_chapters if num_chapters > 0 else 0

    selected_questions = []
    # Remainder filler only applies for equal-division mode
    filler_needed = 0 if chapter_allocations is not None else TOTAL_QUESTIONS - (base_per_chapter * num_chapters)

    for chapter in selected_chapters:
        target = chapter_allocations[chapter] if chapter_allocations is not None else base_per_chapter

        if chapter not in data_dict:
            filler_needed += target
            continue

        df = data_dict[chapter].dropna(how='all')
        available = len(df)

        if available >= target:
            sampled = df.sample(n=target).to_dict('records')
            selected_questions.extend(sampled)
        else:
            sampled = df.to_dict('records')
            selected_questions.extend(sampled)
            filler_needed += (target - available)

    if filler_needed > 0:
        filler_df = data_dict["Filler"].dropna(how='all')
        if len(filler_df) >= filler_needed:
            sampled_filler = filler_df.sample(n=filler_needed).to_dict('records')
            selected_questions.extend(sampled_filler)
        else:
            sampled_filler = filler_df.to_dict('records')
            selected_questions.extend(sampled_filler)
            raise ValueError(f"Not enough filler questions. Needed {filler_needed}, found {len(filler_df)}")

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
