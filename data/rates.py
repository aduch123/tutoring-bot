"""
Grade-based payment rates (ETB per hour).
Admin can override per student at any time.
Monthly payment = days_per_week * 4 * rate_per_hour
"""

from config.config import DEFAULT_SESSION_RATE_ETB


GRADE_RATES = {
    "Grade 1":            DEFAULT_SESSION_RATE_ETB,
    "Grade 2":            DEFAULT_SESSION_RATE_ETB,
    "Grade 3":            DEFAULT_SESSION_RATE_ETB,
    "Grade 4":            DEFAULT_SESSION_RATE_ETB,
    "Grade 5":            DEFAULT_SESSION_RATE_ETB,
    "Grade 6":            DEFAULT_SESSION_RATE_ETB,
    "Grade 7":            DEFAULT_SESSION_RATE_ETB,
    "Grade 8":            DEFAULT_SESSION_RATE_ETB,
    "Grade 9":            DEFAULT_SESSION_RATE_ETB,
    "Grade 10":           DEFAULT_SESSION_RATE_ETB,
    "Grade 11 — Natural": DEFAULT_SESSION_RATE_ETB,
    "Grade 11 — Social":  DEFAULT_SESSION_RATE_ETB,
    "Grade 12 — Natural": DEFAULT_SESSION_RATE_ETB,
    "Grade 12 — Social":  DEFAULT_SESSION_RATE_ETB,
}

DEFAULT_RATE = DEFAULT_SESSION_RATE_ETB


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