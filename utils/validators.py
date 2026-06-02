"""Input validation functions used throughout registration flows."""
import re


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Valid Ethiopian phone: starts with 09 or +251, total 10-13 digits.
    Returns (is_valid, error_message)
    """
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("+251"):
        digits = cleaned[1:]  # keep the +
    else:
        digits = cleaned

    if not re.match(r'^(\+251|09)\d+$', cleaned):
        return False, "Phone must start with 09 or +251.\nExample: 0912345678 or +251912345678"

    if len(cleaned.replace("+", "").replace("251", "0", 1)) != 10:
        if not (10 <= len(cleaned) <= 13):
            return False, "Phone number must be 10-13 digits.\nExample: 0912345678"

    return True, ""


def validate_name(name: str) -> tuple[bool, str]:
    """
    Name must be at least 3 characters, letters and spaces only.
    """
    name = name.strip()
    if len(name) < 3:
        return False, "Name must be at least 3 characters long."
    if not re.match(r"^[A-Za-z\u1200-\u137F\s]+$", name):
        return False, "Name can only contain letters and spaces."
    return True, ""


def validate_days_per_week(value: str) -> tuple[bool, str]:
    """Must be integer between 3 and 5."""
    try:
        days = int(value.strip())
        if days < 3 or days > 5:
            return False, "Days per week must be between 3 and 5."
        return True, ""
    except ValueError:
        return False, "Please enter a number (3, 4, or 5)."


def validate_account_number(number: str) -> tuple[bool, str]:
    """Account number must be at least 8 numeric digits."""
    cleaned = number.strip().replace(" ", "").replace("-", "")
    if not cleaned.isdigit():
        return False, "Account number must contain only digits."
    if len(cleaned) < 8:
        return False, "Account number must be at least 8 digits."
    return True, ""


def validate_zoom_link(link: str) -> tuple[bool, str]:
    """Must be a valid URL starting with http."""
    link = link.strip()
    if not link.startswith("http"):
        return False, "Please send a valid Zoom link starting with https://"
    if "zoom.us" not in link and "zoom" not in link.lower():
        return False, "This doesn't look like a Zoom link. Please send a valid Zoom meeting URL."
    return True, ""


def validate_session_id(session_id: str) -> tuple[bool, str]:
    """Must match SES-XXXX format."""
    session_id = session_id.strip().upper()
    if not re.match(r'^SES-\d{4}$', session_id):
        return False, "Session ID must be in format SES-XXXX (e.g. SES-0001)."
    return True, ""


def validate_time_range(time_str: str) -> tuple[bool, str]:
    """Must be in HH:MM-HH:MM format."""
    import re
    pattern = r'^\d{2}:\d{2}-\d{2}:\d{2}$'
    if not re.match(pattern, time_str.strip()):
        return False, "Please use format HH:MM-HH:MM (e.g. 15:00-18:00)"
    start, end = time_str.strip().split("-")
    try:
        from datetime import datetime
        s = datetime.strptime(start, "%H:%M")
        e = datetime.strptime(end, "%H:%M")
        if e <= s:
            return False, "End time must be after start time."
    except ValueError:
        return False, "Invalid time format. Use HH:MM-HH:MM (e.g. 15:00-18:00)"
    return True, ""
