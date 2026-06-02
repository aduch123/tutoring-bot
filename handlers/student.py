"""Student-facing handlers."""
import logging
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

REPORT_TEXT, EMERGENCY_TEXT = range(2)

def _kb(rows): return InlineKeyboardMarkup(rows)
def _back(cb="back"): return _kb([[InlineKeyboardButton("‹ Back", callback_data=cb)]])
def _back_cancel():
    return _kb([[InlineKeyboardButton("‹ Back", callback_data="back"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel_report")]])


# ── Sessions ──────────────────────────────────────────────────────────────────

@handle_errors
async def student_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.schedule_service import ScheduleService
    from repositories.user import UserRepository
    from models.schedule import Session as SM
    from ui.templates import student_sessions
    from datetime import datetime
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not user:
            await reply(update, "❌ User not found.")
            return
        svc = ScheduleService(db)
        upcoming = svc.get_student_all_upcoming_sessions(user.user_id, limit=20)
        past_rows = (
            db.query(SM)
            .filter(SM.student_id == user.user_id, SM.scheduled_start < datetime.now())
            .order_by(SM.scheduled_start.desc()).limit(5).all()
        )
        past = [{"session_id": s.session_id, "subject": s.subject,
                 "start": s.scheduled_start.strftime("%a %d %b · %H:%M"),
                 "status": s.status} for s in past_rows]
        text = student_sessions(upcoming, past)
    await reply(update, text, reply_markup=_back())


@handle_errors
async def student_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.schedule_service import ScheduleService
    from repositories.user import UserRepository
    from ui.templates import student_schedule
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        schedules = ScheduleService(db).get_student_schedules(user.user_id) if user else []
    rows = [[InlineKeyboardButton("📝 Contact Admin", callback_data="report_issue")]]
    rows.append([InlineKeyboardButton("‹ Back", callback_data="back")])
    await reply(update, student_schedule(schedules), reply_markup=_kb(rows))


@handle_errors
async def student_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.payment_service import PaymentService
    from ui.templates import student_payments
    from ui.keyboards import back
    with next(get_db()) as db:
        svc = PaymentService(db)
        data = svc.get_student_payments(update.effective_user.id)
    if not data["success"]:
        await reply(update, f"❌ {data['message']}", reply_markup=back())
        return
    has_pending = any(p["status"] in ("pending", "screenshot_uploaded")
                      for p in data["payments"])
    rows = []
    if has_pending:
        rows.append([InlineKeyboardButton("📸 Upload Payment Screenshot",
                                           callback_data="upload_payment_proof")])
    rows.append([InlineKeyboardButton("💳 View Payment Accounts",
                                       callback_data="show_payment_page")])
    rows.append([InlineKeyboardButton("‹ Back", callback_data="back")])
    await reply(update, student_payments(data["rate"], data["payments"]),
                reply_markup=_kb(rows))


@handle_errors
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository, StudentRepository
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not user:
            await reply(update, "❌ User not found.")
            return
        student = StudentRepository(db).get(user.user_id)
        rate = float(student.hourly_rate_etb) if student and student.hourly_rate_etb else 400
        grade = student.grade if student else "N/A"
        parent = student.parent_phone if student else "N/A"
        subjects = student.subjects if student else "N/A"
        days = student.days_per_week if student else 3
    text = (
        f"👤 *My Profile*\n\n{'─'*26}\n"
        f"🆔  `{user.user_id}`\n"
        f"👤  {user.full_name}\n"
        f"📱  {user.phone}\n"
        f"🎓  Grade: {grade}\n"
        f"📚  Subjects: {subjects}\n"
        f"📅  Days/week: {days}\n"
        f"👪  Parent: {parent}\n"
        f"💵  Rate: {rate:.0f} ETB/hr\n"
        f"📅  Joined: {user.created_at.strftime('%d %b %Y')}"
    )
    await reply(update, text, reply_markup=_back())


@handle_errors
async def confirm_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.confirmation_service import ConfirmationService
    from handlers.confirm_flow import confirm_start
    await confirm_start(update, context)
    return
    with next(get_db()) as db:
        result = ConfirmationService(db).confirm(update.effective_user.id, session_id)
    if not result["success"]:
        await reply(update, f"❌ {result['message']}", reply_markup=_back())
        return
    if result["completed"]:
        await reply(update, f"✅ *Session {session_id} completed!* 🎓", reply_markup=_back())
    else:
        await reply(update,
            f"✅ Confirmation recorded.\nWaiting for: _{', '.join(result['missing'])}_",
            reply_markup=_back())


# ── Issue reporting — plain text, no categories ───────────────────────────────

async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = context.user_data.pop("reporting_session_id", None)
    if session_id:
        context.user_data["report_session_id"] = session_id

    await reply(update,
        "📝 *Report an Issue*\n\n"
        "Please describe your issue in as much detail as possible.\n\n"
        "_Just type your message and send it:_",
        reply_markup=_back_cancel())
    return REPORT_TEXT


async def report_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.emergency_service import EmergencyService
    from services.notification_service import notify_admin_group
    from config.config import ADMIN_GROUP_CHAT_ID
    from ui.keyboards import claim_report_button

    description = update.message.text.strip()
    session_id = context.user_data.pop("report_session_id", None)

    with next(get_db()) as db:
        result = EmergencyService(db).create(
            reporter_telegram_id=update.effective_user.id,
            issue_type="other",
            description=description,
            session_id=session_id,
        )

    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}", reply_markup=_back())
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ *Issue Reported*\n\n"
        f"Ticket: `{result['emergency_id']}`\n\n"
        f"An admin will review and respond to you shortly.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back())

    if ADMIN_GROUP_CHAT_ID:
        try:
            await update.message.get_bot().send_message(
                chat_id=ADMIN_GROUP_CHAT_ID,
                text=f"📝 *New Issue Report*\n\n"
                     f"From: *{result['reporter_name']}* (`{result['reporter_id']}`)\n"
                     f"Session: {session_id or 'N/A'}\n\n"
                     f"*Message:*\n{description}\n\n"
                     f"Ticket: `{result['emergency_id']}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=claim_report_button(result["emergency_id"]))
        except Exception as e:
            logger.error(f"Failed to notify admin group: {e}")

    context.user_data.clear()
    return ConversationHandler.END


# ── Emergency reporting — plain text ─────────────────────────────────────────

async def emergency_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update,
        "🚨 *Emergency Report*\n\n"
        "Describe your emergency. Be as specific as possible.\n\n"
        "An admin will be notified immediately.\n\n"
        "_Just type your message and send it:_",
        reply_markup=_back_cancel())
    return EMERGENCY_TEXT


async def emergency_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.emergency_service import EmergencyService
    from config.config import ADMIN_GROUP_CHAT_ID
    from ui.keyboards import claim_emergency_button

    description = update.message.text.strip()

    with next(get_db()) as db:
        result = EmergencyService(db).create(
            reporter_telegram_id=update.effective_user.id,
            issue_type="urgent",
            description=description,
        )

    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}", reply_markup=_back())
        return ConversationHandler.END

    await update.message.reply_text(
        f"🚨 *Emergency Reported*\n\n"
        f"Ticket: `{result['emergency_id']}`\n\n"
        f"An admin has been notified immediately.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back())

    if ADMIN_GROUP_CHAT_ID:
        try:
            await update.message.get_bot().send_message(
                chat_id=ADMIN_GROUP_CHAT_ID,
                text=f"🚨 *EMERGENCY*\n\n"
                     f"From: *{result['reporter_name']}* (`{result['reporter_id']}`)\n\n"
                     f"*Message:*\n{description}\n\n"
                     f"Ticket: `{result['emergency_id']}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=claim_emergency_button(result["emergency_id"]))
        except Exception as e:
            logger.error(f"Failed to notify admin group: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def emergency_type_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy entry point kept for compatibility — redirects to plain text flow."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🚨 *Emergency Report*\n\n"
        "Describe your emergency:\n\n"
        "_Just type your message and send it:_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([[InlineKeyboardButton("‹ Back", callback_data="back"),
                           InlineKeyboardButton("❌ Cancel", callback_data="cancel_report")]]))
    return EMERGENCY_TEXT


async def _cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await reply(update, "❌ Cancelled.")
    return ConversationHandler.END


def report_conv_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(report_start, pattern="^report_issue$")],
        states={
            REPORT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_text_received)],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel_conv),
            CallbackQueryHandler(_cancel_conv, pattern="^back$"),
            CallbackQueryHandler(_cancel_conv, pattern="^cancel_report$"),
        ],
        name="report_issue", per_message=False, persistent=False,
    )


def emergency_conv_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(emergency_start, pattern="^emergency$"),
            CallbackQueryHandler(emergency_type_chosen, pattern="^emg_"),
        ],
        states={
            EMERGENCY_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, emergency_text_received)],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel_conv),
            CallbackQueryHandler(_cancel_conv, pattern="^back$"),
            CallbackQueryHandler(_cancel_conv, pattern="^cancel_report$"),
        ],
        name="emergency_report", per_message=False, persistent=False,
    )
