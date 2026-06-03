"""
Subject registry — single source of truth for all subjects.
Used in registration (student + tutor) and tutor assignment.
"""

SUBJECTS = {
    "Grade 1": {
        "Natural": ["Mathematics", "Science", "Physical Education"],
        "Social": ["English", "Environmental Science"],
    },
    "Grade 2": {
        "Natural": ["Mathematics", "Science", "Physical Education"],
        "Social": ["English", "Environmental Science"],
    },
    "Grade 3": {
        "Natural": ["Mathematics", "Science", "Physical Education"],
        "Social": ["English", "Environmental Science", "Arts"],
    },
    "Grade 4": {
        "Natural": ["Mathematics", "Science", "Physical Education"],
        "Social": ["English", "Environmental Science", "Arts"],
    },
    "Grade 5": {
        "Natural": ["Mathematics", "General Science", "Physical Education"],
        "Social": ["Amharic", "English", "Social Studies", "Arts"],
    },
    "Grade 6": {
        "Natural": ["Mathematics", "General Science", "Physical Education"],
        "Social": ["Amharic", "English", "Social Studies", "Arts"],
    },
    "Grade 7": {
        "Natural": ["Mathematics", "Biology", "Chemistry", "Physics", "Physical Education"],
        "Social": ["Amharic", "English", "History", "Geography", "Civics"],
    },
    "Grade 8": {
        "Natural": ["Mathematics", "Biology", "Chemistry", "Physics", "Physical Education"],
        "Social": ["Amharic", "English", "History", "Geography", "Civics"],
    },
    "Grade 9": {
        "Natural": ["Mathematics", "Biology", "Chemistry", "Physics", "Technical Drawing"],
        "Social": ["Amharic", "English", "History", "Geography", "Civics", "Economics"],
    },
    "Grade 10": {
        "Natural": ["Mathematics", "Biology", "Chemistry", "Physics", "Technical Drawing"],
        "Social": ["Amharic", "English", "History", "Geography", "Civics", "Economics"],
    },
    "Grade 11 — Natural": {
        "Natural": ["Mathematics", "Biology", "Chemistry", "Physics", "Technical Drawing"],
        "Social": ["English", "Amharic"],
    },
    "Grade 11 — Social": {
        "Natural": ["Mathematics"],
        "Social": ["Amharic", "English", "History", "Geography", "Economics", "Civics"],
    },
    "Grade 12 — Natural": {
        "Natural": ["Mathematics", "Biology", "Chemistry", "Physics", "Technical Drawing"],
        "Social": ["English", "Amharic"],
    },
    "Grade 12 — Social": {
        "Natural": ["Mathematics"],
        "Social": ["Amharic", "English", "History", "Geography", "Economics", "Civics"],
    },
}

GRADE_LEVELS = list(SUBJECTS.keys())


def get_subjects_for_grade(grade: str) -> dict:
    """Returns {'Natural': [...], 'Social': [...]} for a grade."""
    return SUBJECTS.get(grade, SUBJECTS["Other"])


def get_all_subjects_for_grade(grade: str) -> list:
    """Returns flat list of all subjects for a grade."""
    groups = get_subjects_for_grade(grade)
    return groups.get("Natural", []) + groups.get("Social", [])


def is_valid_subject(subject: str, grade: str = None) -> bool:
    """Check if a subject is valid (optionally for a specific grade)."""
    if grade:
        return subject in get_all_subjects_for_grade(grade)
    # Check across all grades
    for grade_data in SUBJECTS.values():
        for group_subjects in grade_data.values():
            if subject in group_subjects:
                return True
    return False


def get_all_unique_subjects() -> list:
    """Get all unique subjects across all grades — for tutor registration."""
    all_subjects = set()
    for grade_data in SUBJECTS.values():
        for group_subjects in grade_data.values():
            all_subjects.update(group_subjects)
    return sorted(list(all_subjects))
