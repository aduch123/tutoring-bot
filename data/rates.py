"""
Grade-based payment rates (ETB per hour).
Admin can override per student at any time.
Monthly payment = days_per_week * 4 * rate_per_hour
"""

GRADE_RATES = {
    "Grade 1":            350,
    "Grade 2":            350,
    "Grade 3":            350,
    "Grade 4":            350,
    "Grade 5":            350,
    "Grade 6":            350,
    "Grade 7":            350,
    "Grade 8":            350,
    "Grade 9":            350,
    "Grade 10":           350,
    "Grade 11 — Natural": 350,
    "Grade 11 — Social":  350,
    "Grade 12 — Natural": 350,
    "Grade 12 — Social":  350,
}

DEFAULT_RATE = 350


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