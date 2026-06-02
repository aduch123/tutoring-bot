"""
Grade-based payment rates (ETB per hour).
Admin can override per student at any time.
Monthly payment = days_per_week * 4 * rate_per_hour
"""

GRADE_RATES = {
    "Grade 1":  300,
    "Grade 2":  300,
    "Grade 3":  300,
    "Grade 4":  300,
    "Grade 5":  350,
    "Grade 6":  350,
    "Grade 7":  380,
    "Grade 8":  380,
    "Grade 9":  400,
    "Grade 10": 400,
    "Grade 11 — Natural": 450,
    "Grade 11 — Social":  430,
    "Grade 12 — Natural": 500,
    "Grade 12 — Social":  480,
    "University": 600,
    "Other": 400,
}

DEFAULT_RATE = 400  # fallback if grade not found


def get_rate_for_grade(grade: str) -> int:
    return GRADE_RATES.get(grade, DEFAULT_RATE)


def calculate_monthly_payment(grade: str, days_per_week: int,
                               override_rate: float = None) -> float:
    """
    Monthly payment = days_per_week * 4 weeks * rate_per_hour
    Sessions are 1 hour each.
    """
    rate = override_rate if override_rate else get_rate_for_grade(grade)
    return days_per_week * 4 * rate
