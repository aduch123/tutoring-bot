"""
Subject registry — single source of truth for all subjects.
Used in registration (student + tutor) and tutor assignment.
"""

SUBJECTS = {
    "Grade 1":            ["Mathematics", "English", "Environmental Science"],
    "Grade 2":            ["Mathematics", "English", "Environmental Science"],
    "Grade 3":            ["Mathematics", "English", "Environmental Science"],
    "Grade 4":            ["Mathematics", "English", "Environmental Science"],
    "Grade 5":            ["Mathematics", "English", "Integrated Science", "Social Science"],
    "Grade 6":            ["Mathematics", "English", "Integrated Science", "Social Science"],
    "Grade 7":            ["Mathematics", "English", "General Science", "Social Science"],
    "Grade 8":            ["Mathematics", "English", "General Science", "Social Science"],
    "Grade 9":            ["Mathematics", "Physics", "Chemistry", "Biology", "English"],
    "Grade 10":           ["Mathematics", "Physics", "Chemistry", "Biology", "English"],
    "Grade 11 — Natural": ["Mathematics", "Physics", "Chemistry", "Biology", "English"],
    "Grade 11 — Social":  ["Mathematics", "Economics", "English"],
    "Grade 12 — Natural": ["Mathematics", "Physics", "Chemistry", "Biology", "English"],
    "Grade 12 — Social":  ["Mathematics", "Economics", "English"],
}

GRADE_LEVELS = list(SUBJECTS.keys())


def get_subjects_for_grade(grade: str) -> list:
    """Returns flat list of subjects for a grade."""
    return SUBJECTS.get(grade, [])


def get_all_subjects_for_grade(grade: str) -> list:
    """Alias for get_subjects_for_grade — returns flat list."""
    return get_subjects_for_grade(grade)


def is_valid_subject(subject: str, grade: str = None) -> bool:
    """Check if a subject is valid (optionally for a specific grade)."""
    if grade:
        return subject in get_subjects_for_grade(grade)
    for subjects in SUBJECTS.values():
        if subject in subjects:
            return True
    return False


def get_all_unique_subjects() -> list:
    """Get all unique subjects across all grades — for tutor registration."""
    all_subjects = set()
    for subjects in SUBJECTS.values():
        all_subjects.update(subjects)
    return sorted(list(all_subjects))