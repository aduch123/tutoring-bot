"""Tutor-facing handlers — fully button driven."""
import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)
from telegram.constants import ParseMode
from config.db import get_db
from utils.error_handler import handle_errors
from utils.helpers import reply, send

logger = logging.getLogger(__name__)

ASK_SESSION_ID, RECEIVE_VIDEO = range(2)


def _kb(rows): return InlineKeyboardMarkup(rows)
def _back(cb="back"): return _kb([[InlineKeyboardButton("‹ Back", callback_data=cb)]])


@handle_errors
async def tutor_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.schedule_service import ScheduleService
    from repositories.user import UserRepository
    from models.schedule import Session as SM
    from ui.templates import tutor_sessions
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not user:
            await reply(update, "❌ User not found.")
            return
        svc = ScheduleService(db)
        upcoming = svc.get_tutor_all_upcoming_sessions(user.user_id, limit=10)
        past_rows = (
            db.query(SM)
            .filter(SM.tutor_id == user.user_id, SM.scheduled_start < datetime.now())
            .order_by(SM.scheduled_start.desc()).limit(5).all()
        )
        past = []
        for s in past_rows:
            student = UserRepository(db).get_by_user_id(s.student_id)
            past.append({
                "session_id": s.session_id, "subject": s.subject,
                "student_name": student.full_name if student else s.student_id,
                "start": s.scheduled_start.strftime("%a %d %b · %H:%M"),
                "status": s.status,
            })
    await reply(update, tutor_sessions(upcoming, past), reply_markup=_back())


@handle_errors
async def tutor_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.schedule_service import ScheduleService
    from repositories.user import UserRepository
    from ui.templates import tutor_schedule
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        schedules = ScheduleService(db).get_tutor_schedules(user.user_id) if user else []
    await reply(update, tutor_schedule(schedules), reply_markup=_back())


@handle_errors
async def tutor_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.payment_service import PaymentService
    from ui.templates import tutor_earnings
    with next(get_db()) as db:
        data = PaymentService(db).get_tutor_earnings(update.effective_user.id)
    if not data["success"]:
        await reply(update, f"❌ {data['message']}", reply_markup=_back())
        return
    await reply(update, tutor_earnings(data["total_earned"], data["payouts"]),
                reply_markup=_back())


@handle_errors
async def tutor_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository, TutorRepository
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not user:
            await reply(update, "❌ User not found.")
            return
        tutor = TutorRepository(db).get(user.user_id)
        primary = tutor.primary_subjects if tutor else "N/A"
        secondary = tutor.secondary_subjects if tutor else "N/A"
        max_hours = tutor.max_teaching_hours if tutor else 3
        total = tutor.total_sessions if tutor else 0
        status = tutor.approval_status if tutor else "unknown"

    text = (
        f"👤 *My Profile*\n\n{'─'*26}\n"
        f"🆔  `{user.user_id}`\n"
        f"👤  {user.full_name}\n"
        f"📱  {user.phone}\n"
        f"★  Primary: {primary}\n"
        f"○  Secondary: {secondary}\n"
        f"⏱  Max hours/week: {max_hours}\n"
        f"📊  Total sessions: {total}\n"
        f"✅  Status: {status.replace('_',' ').title()}\n"
        f"📅  Joined: {user.created_at.strftime('%d %b %Y')}"
    )
    await reply(update, text, reply_markup=_back())


@handle_errors
async def confirm_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy command handler — redirects to button flow."""
    from handlers.confirm_flow import confirm_start
    await confirm_start(update, context)


# ── Recording upload ──────────────────────────────────────────────────────────

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of sessions needing recording upload."""
    from repositories.user import UserRepository
    from models.schedule import Session as SM

    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not user:
            await reply(update, "❌ User not found.")
            return ConversationHandler.END

        sessions = (
            db.query(SM)
            .filter(
                SM.tutor_id == user.user_id,
                SM.status.in_(["in_progress", "completed"]),
                SM.recording_path == None,
                SM.tutor_confirmed == True,
            )
            .order_by(SM.scheduled_start.desc())
            .limit(8)
            .all()
        )

        if not sessions:
            await reply(update,
                "📹 *No sessions pending recording upload.*\n\n"
                "Sessions appear here after you confirm attendance.",
                reply_markup=_back())
            return ConversationHandler.END

        rows = []
        for s in sessions:
            student = UserRepository(db).get_by_user_id(s.student_id)
            rows.append([InlineKeyboardButton(
                f"📹 {s.subject} · {s.scheduled_start.strftime('%d %b')} · "
                f"{student.full_name if student else s.student_id}",
                callback_data=f"upload_select_{s.session_id}"
            )])
        rows.append([InlineKeyboardButton("‹ Back", callback_data="back")])

    await reply(update,
        "📹 *Upload Recording*\n\nSelect the session to upload for:",
        reply_markup=_kb(rows))
    return ConversationHandler.END


async def upload_session_selected(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("upload_select_", "")
    context.user_data["upload_session_id"] = session_id
    await query.edit_message_text(
        f"📹 *Upload Recording*\n\n"
        f"Session: `{session_id}`\n\n"
        f"Send the recording file:\n"
        f"_(MP4, MKV, or AVI — max 2000MB)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([[
            InlineKeyboardButton("✕ Cancel", callback_data="back")
        ]]))
    return RECEIVE_VIDEO


async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.recording_service import RecordingService
    session_id = context.user_data.get("upload_session_id")
    file_obj = update.message.video or update.message.document
    if not file_obj:
        await update.message.reply_text(
            "⚠️ Please send a video file.",
            reply_markup=_kb([[InlineKeyboardButton("✕ Cancel", callback_data="back")]]))
        return RECEIVE_VIDEO

    file_name = getattr(file_obj, "file_name", "recording.mp4") or "recording.mp4"
    file_ext = os.path.splitext(file_name)[1] or ".mp4"
    file_size = file_obj.file_size or 0

    with next(get_db()) as db:
        result = RecordingService(db).upload(
            tutor_telegram_id=update.effective_user.id,
            session_id=session_id,
            file_id=file_obj.file_id,
            file_size=file_size,
            file_ext=file_ext,
        )

    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}", reply_markup=_back())
        return ConversationHandler.END

    # Forward the actual video to admins for review (server-side copy — no download, no size limit)
    from config.config import ADMIN_GROUP_CHAT_ID
    if ADMIN_GROUP_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_CHAT_ID,
                text=f"📹 *New Recording Submitted*\n\n"
                     f"Session: `{session_id}`\n"
                     f"Submitted: {datetime.now().strftime('%d %b %Y · %H:%M')}\n\n"
                     f"Tap below to claim and review this recording.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎬 Claim & Review",
                        callback_data=f"claim_review_recording_{session_id}")
                ]]))
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ *Recording uploaded!*\n\n"
        f"Session: `{session_id}`\n"
        f"An admin will review and approve it.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back())

    context.user_data.clear()
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await reply(update, "❌ Cancelled.")
    return ConversationHandler.END


def upload_conv_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(upload_start, pattern="^upload_recording$"),
            CallbackQueryHandler(upload_start, pattern="^📹 Recording$"),
        ],
        states={
            RECEIVE_VIDEO: [
                CallbackQueryHandler(upload_session_selected, pattern="^upload_select_"),
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern="^back$"),
        ],
        name="upload_recording",
        per_message=False, persistent=False,
    )
