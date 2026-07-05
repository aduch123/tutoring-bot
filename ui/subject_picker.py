"""
Reusable subject picker using inline buttons.
Subjects are toggled on/off. "Done" confirms selection.
Used in student registration, tutor registration, and assignment.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from data.subjects import get_subjects_for_grade, GRADE_LEVELS


def grade_picker_keyboard(back_cb: str = "back") -> InlineKeyboardMarkup:
    """Show all grade levels as buttons for selection."""
    rows = []
    row = []
    for i, grade in enumerate(GRADE_LEVELS):
        row.append(InlineKeyboardButton(grade, callback_data=f"grade_pick_{grade}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("‹ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def subject_picker_keyboard(grade: str, selected: list,
                             done_cb: str = "subjects_done",
                             back_cb: str = "back") -> InlineKeyboardMarkup:
    """
    Show subjects for a grade as toggle buttons.
    selected: list of already-selected subject names
    """
    from data.subjects import get_subjects_for_grade
    subjects = get_subjects_for_grade(grade)
    rows = []
    row = []
    for subj in subjects:
        is_selected = subj in selected
        prefix = "✅ " if is_selected else ""
        row.append(InlineKeyboardButton(
            f"{prefix}{subj}",
            callback_data=f"subj_toggle_{subj.replace(' ', '_')}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    count = len(selected)
    done_label = f"✅ Done ({count} selected)" if count > 0 else "✅ Done"
    rows.append([InlineKeyboardButton(done_label, callback_data=done_cb)])
    rows.append([InlineKeyboardButton("‹ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def subject_picker_text(grade: str, selected: list,
                         purpose: str = "learn",
                         step: int = None, total: int = None) -> str:
    """Header text for the subject picker screen."""
    bar = f"`{'●' * step}{'○' * (total - step)}`  Step {step} of {total}\n\n" \
          if step and total else ""
    action = "learn" if purpose == "learn" else "teach"
    sel_text = (f"\n\n✅ *Selected:* {', '.join(selected)}"
                if selected else "\n\n_Tap subjects to select them_")
    return (
        f"{bar}"
        f"📚 *Select subjects you want to {action}*\n"
        f"Grade: _{grade}_"
        f"{sel_text}"
    )


def tutor_subject_picker_keyboard(selected: list,
                                   done_cb: str = "tutor_subjects_done",
                                   back_cb: str = "back") -> InlineKeyboardMarkup:
    """
    Subject picker for tutors — shows ALL unique subjects across all grades.
    Used for primary and secondary subject selection.
    """
    from data.subjects import get_all_unique_subjects
    all_subjects = get_all_unique_subjects()
    rows = []
    row = []
    for subj in all_subjects:
        is_selected = subj in selected
        prefix = "✅ " if is_selected else ""
        row.append(InlineKeyboardButton(
            f"{prefix}{subj}",
            callback_data=f"subj_toggle_{subj.replace(' ', '_')}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    count = len(selected)
    done_label = f"✅ Done ({count} selected)" if count > 0 else "✅ Done"
    rows.append([InlineKeyboardButton(done_label, callback_data=done_cb)])
    rows.append([InlineKeyboardButton("‹ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)
