"""
Session lifecycle handlers:
- Start confirmation (5 mins before)
- End confirmation (at session end)
- Replacement tutor assignment
- Recording approval
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode
from config.db import get_db
from utils.helpers import reply, send
from utils.error_handler import handle_errors

logger = logging.getLogger(__name__)

def _kb(rows): return InlineKeyboardMarkup(rows)
def _back(cb="back"): return _kb([[InlineKeyboardButton("‹ Back", callback_data=cb)]])

REPLACEMENT_SELECT = 0


@handle_errors
async def handle_start_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tutor or student confirms they are in the session."""
    query = update.callback_query
    await query.answer()
    data = query.data  # start_confirm_{session_id} or start_confirm_stu_{session_id}

    is_student = "start_confirm_stu_" in data
    session_id = data.replace("start_confirm_stu_", "").replace("start_confirm_", "")

    with next(get_db()) as db:
        from repositories.schedule import SessionRepository
        from repositories.user import UserRepository
        ses = SessionRepository(db).get(session_id)
        if not ses:
            await query.edit_message_text("❌ Session not found.")
            return
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not user:
            return

        if is_student:
            ses.student_start_confirmed = True
        else:
            ses.tutor_start_confirmed = True

        # If both confirmed, mark in_progress
        if ses.tutor_start_confirmed and ses.student_start_confirmed:
            ses.status = "in_progress"
            ses.start_confirmed_at = datetime.now()

        db.commit()

    await query.edit_message_text(
        f"✅ *Attendance confirmed!*\n\n"
        f"Session `{session_id}` — you've been marked as present.\n\n"
        f"Have a great session! 🎓",
        parse_mode=ParseMode.MARKDOWN)

@handle_errors
async def handle_start_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tutor or student declines session start."""
    query = update.callback_query
    await query.answer()
    data = query.data

    is_student = "start_decline_stu_" in data
    session_id = data.replace("start_decline_stu_", "").replace("start_decline_", "")

    with next(get_db()) as db:
        from repositories.schedule import SessionRepository
        from repositories.user import UserRepository
        from config.config import ADMIN_GROUP_CHAT_ID
        ses = SessionRepository(db).get(session_id)
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not ses or not user:
            return

        if is_student:
            ses.status = "student_absent"
            role = "Student"
        else:
            ses.status = "tutor_absent"
            role = "Tutor"
        db.commit()

        # Notify admin group
        tutor = UserRepository(db).get_by_user_id(ses.tutor_id)
        student = UserRepository(db).get_by_user_id(ses.student_id)

        # Capture everything needed after the block closes — BEFORE closing
        session_subject = ses.subject
        session_time = ses.scheduled_start.strftime('%H:%M')
        tutor_name = tutor.full_name if tutor else ses.tutor_id
        student_name = student.full_name if student else ses.student_id

    await query.edit_message_text(
        "✅ Noted. An admin has been notified.",
        parse_mode=ParseMode.MARKDOWN)

    from services.notification_service import notify_admin_group
    kb = None
    if not is_student:
        kb = _kb([[InlineKeyboardButton(
            "🚨 Claim & Handle Absence",
            callback_data=f"claim_absence_{session_id}")]])
    await notify_admin_group(
        context.bot,
        f"🚨 *{role} Declined Session*\n\n"
        f"Session: `{session_id}`\n"
        f"Subject: {session_subject}\n"
        f"Tutor: {tutor_name}\n"
        f"Student: {student_name}\n"
        f"Time: {session_time}",
        reply_markup=kb)

@handle_errors
async def handle_end_confirm_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tutor confirms session end."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("end_confirm_tut_", "")

    with next(get_db()) as db:
        from repositories.schedule import SessionRepository
        ses = SessionRepository(db).get(session_id)
        if not ses:
            await query.edit_message_text("❌ Session not found.")
            return
        ses.tutor_confirmed = True
        if ses.student_confirmed:
            ses.end_confirmed_at = datetime.now()
        db.commit()

    await query.edit_message_text(
        f"✅ *Session confirmed!*\n\n"
        f"Please upload the session recording within 24 hours.\n"
        f"Tap 📹 *Upload Recording* on your dashboard.",
        parse_mode=ParseMode.MARKDOWN)

@handle_errors
async def handle_end_confirm_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Student confirms session end."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("end_confirm_stu_", "")

    with next(get_db()) as db:
        from repositories.schedule import SessionRepository
        ses = SessionRepository(db).get(session_id)
        if not ses:
            return
        ses.student_confirmed = True
        if ses.tutor_confirmed:
            ses.end_confirmed_at = datetime.now()
        db.commit()

    await query.edit_message_text(
        f"✅ *Attendance confirmed!*\n\nThank you for confirming. 🎓",
        parse_mode=ParseMode.MARKDOWN)

@handle_errors
async def handle_end_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User reports issue at session end."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("end_issue_stu_", "").replace("end_issue_", "")
    context.user_data["reporting_session_id"] = session_id

    await query.edit_message_text(
        f"📝 *Report Session Issue*\n\n"
        f"Session: `{session_id}`\n\n"
        f"Please describe what happened:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back())

@handle_errors
async def handle_recording_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin approves a recording — session counts toward payout."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("approve_recording_", "")

    with next(get_db()) as db:
        from repositories.schedule import SessionRepository
        from repositories.user import UserRepository
        ses = SessionRepository(db).get(session_id)
        if not ses:
            await query.edit_message_text("❌ Session not found.")
            return
        admin = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        ses.recording_approved = True
        ses.recording_approved_by = admin.user_id if admin else "admin"
        ses.status = "completed"
        # Increment tutor session count
        from models.user import Tutor
        payout_tutor_id = ses.replacement_tutor_id or ses.tutor_id
        tut = db.query(Tutor).filter(Tutor.user_id == payout_tutor_id).first()
        if tut:
            tut.total_sessions = (tut.total_sessions or 0) + 1
        db.commit()
        tutor = UserRepository(db).get_by_user_id(ses.tutor_id)

        # Capture everything needed after the block closes — BEFORE closing
        session_subject = ses.subject

    await query.edit_message_text(
        f"✅ *Recording approved!*\n\n"
        f"Session `{session_id}` is now marked as completed and counts toward payout.",
        parse_mode=ParseMode.MARKDOWN)

    if tutor:
        await send(context.bot, tutor.telegram_id,
            f"✅ *Session Approved*\n\n"
            f"Your recording for `{session_id}` ({session_subject}) has been approved.\n"
            f"This session counts toward your monthly payout. 🎉")

@handle_errors
async def handle_recording_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rejects a recording."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("reject_recording_", "")
    context.user_data["rejecting_recording"] = session_id
    await query.edit_message_text(
        f"❌ *Reject Recording*\n\n"
        f"Session: `{session_id}`\n\n"
        f"Please state the reason for rejection:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back())

# ── Replacement tutor assignment ──────────────────────────────────────────────

@handle_errors
async def assign_replacement_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin assigns a replacement tutor for an absent tutor's session."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("assign_replacement_", "")

    with next(get_db()) as db:
        from repositories.schedule import SessionRepository
        from repositories.user import UserRepository
        from services.tutor_service import TutorService
        ses = SessionRepository(db).get(session_id)
        if not ses:
            await query.edit_message_text("❌ Session not found.")
            return

        tutors = TutorService(db).get_available_tutors_for_subject(
            ses.subject, exclude_tutor_id=ses.tutor_id)
        student = UserRepository(db).get_by_user_id(ses.student_id)
        original_tutor = UserRepository(db).get_by_user_id(ses.tutor_id)

        if not tutors:
            await query.edit_message_text(
                f"⚠️ No available tutors found for *{ses.subject}*.\n\n"
                f"Please contact tutors manually.",
                parse_mode=ParseMode.MARKDOWN)
            return

        context.user_data["replacement_session_id"] = session_id
        context.user_data["replacement_subject"] = ses.subject

        rows = []
        for t in tutors[:8]:
            rows.append([InlineKeyboardButton(
                f"{'★' if t['match_type']=='primary' else '○'} {t['full_name']} · {t['load']}",
                callback_data=f"do_replace_{session_id}_{t['user_id']}")])

        rows.append([InlineKeyboardButton("‹ Back", callback_data="back")])
        await query.edit_message_text(
            f"🔄 *Assign Replacement Tutor*\n\n"
            f"Session: `{session_id}`\n"
            f"Subject: {ses.subject}\n"
            f"Student: {student.full_name if student else ses.student_id}\n"
            f"Original tutor: {original_tutor.full_name if original_tutor else ses.tutor_id}\n\n"
            f"Available tutors (★=primary match):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_kb(rows))
    return REPLACEMENT_SELECT

@handle_errors
async def do_assign_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin confirms replacement tutor selection."""
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("do_replace_", "").split("_", 1)
    session_id, tutor_id = parts[0], parts[1]

    with next(get_db()) as db:
        from repositories.schedule import SessionRepository
        from repositories.user import UserRepository
        ses = SessionRepository(db).get(session_id)
        if not ses:
            await query.edit_message_text("❌ Session not found.")
            return
        new_tutor = UserRepository(db).get_by_user_id(tutor_id)
        student = UserRepository(db).get_by_user_id(ses.student_id)

        # Extract all values needed outside the session BEFORE closing
        ses.replacement_tutor_id = tutor_id
        ses.status = "zoom_ready" if ses.zoom_link else "zoom_pending"
        db.commit()

        # Capture everything needed after the block
        new_tutor_name = new_tutor.full_name if new_tutor else tutor_id
        new_tutor_telegram_id = new_tutor.telegram_id if new_tutor else None
        student_name = student.full_name if student else ses.student_id
        student_telegram_id = student.telegram_id if student else None
        session_subject = ses.subject
        session_time = ses.scheduled_start.strftime('%H:%M')
        zoom_link = ses.zoom_link

    await query.edit_message_text(
        f"✅ *Replacement Assigned*\n\n"
        f"Session: `{session_id}`\n"
        f"New tutor: *{new_tutor_name}*",
        parse_mode=ParseMode.MARKDOWN)

    if new_tutor_telegram_id:
        await send(context.bot, new_tutor_telegram_id,
            f"🔄 *You've Been Assigned as Replacement Tutor*\n\n"
            f"Session: `{session_id}`\n"
            f"Subject: {session_subject}\n"
            f"Student: {student_name}\n"
            f"Time: {session_time}\n\n"
            + (f"🔗 Zoom: {zoom_link}" if zoom_link else
               "Please submit your Zoom link — tap the button in your Sessions screen."))

    if student_telegram_id:
        await send(context.bot, student_telegram_id,
            f"✅ *Replacement Tutor Assigned*\n\n"
            f"A new tutor has been assigned for your {session_subject} session.\n"
            f"Time: {session_time}")
