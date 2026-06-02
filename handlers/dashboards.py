"""Dashboard display for all roles."""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from config.db import get_db
from utils.helpers import reply

logger = logging.getLogger(__name__)


async def show_student_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository, StudentRepository
    from services.schedule_service import ScheduleService
    from services.payment_service import PaymentService
    from ui.templates import student_dashboard
    from ui.keyboards import student_reply_keyboard, student_locked_menu
    from ui.payment_page import locked_dashboard
    from telegram.constants import ParseMode

    telegram_id = update.effective_user.id

    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(telegram_id)
        if not user:
            await reply(update, "❌ User not found. Please use /start.")
            return

        pay_svc = PaymentService(db)
        unlocked = pay_svc.is_student_unlocked(user.user_id)

        if not unlocked:
            pay_status = pay_svc.get_student_payment_status(user.user_id)
            has_screenshot = pay_status["status"] == "screenshot_uploaded"
            text = locked_dashboard(user.full_name, has_screenshot)
            kbd = student_locked_menu()
        else:
            upcoming = ScheduleService(db).get_student_upcoming_sessions(user.user_id)
            rate = pay_svc.get_student_rate(user.user_id)
            pay_status_data = pay_svc.get_student_payment_status(user.user_id)
            payment_status = pay_status_data["status"]
            amount_due = 0.0
            if pay_status_data["payment"] and payment_status != "paid":
                amount_due = float(pay_status_data["payment"].amount)
            text = student_dashboard(
                full_name=user.full_name, user_id=user.user_id,
                upcoming=upcoming, payment_status=payment_status,
                amount_due=amount_due, rate=rate)
            kbd = student_reply_keyboard()

    # Send dashboard text + set reply keyboard
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        await update.callback_query.message.reply_text(
            "👇 Use the buttons below:", reply_markup=kbd)
    elif update.message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kbd, disable_web_page_preview=True)


async def show_tutor_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository, TutorRepository
    from services.schedule_service import ScheduleService
    from services.payment_service import PaymentService
    from ui.templates import tutor_dashboard
    from ui.keyboards import tutor_reply_keyboard
    from telegram.constants import ParseMode
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    telegram_id = update.effective_user.id

    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(telegram_id)
        if not user:
            await reply(update, "❌ User not found. Please use /start.")
            return
        tut = TutorRepository(db).get(user.user_id)
        approval_status = tut.approval_status if tut else None

    # ── Pending states: show a holding screen instead of the full dashboard ──
    if approval_status == "pending_documents":
        text = (
            "⏳ *Application Under Review*\n\n"
            "Your documents have been submitted and are being reviewed by our team.\n\n"
            "You will be notified here once they are approved or if anything is needed."
        )
        await reply(update, text)
        return

    if approval_status == "pending_video":
        text = (
            "📹 *Teaching Video Required*\n\n"
            "Your documents have been approved! ✅\n\n"
            "Please send a teaching video (30–50 minutes) of yourself tutoring a subject.\n\n"
            "Just send the video file here in this chat.\n"
            "_If you send the wrong video, simply send a new one — it will replace it._"
        )
        await reply(update, text)
        return

    # ── Full dashboard for approved tutors ────────────────────────────────────
    with next(get_db()) as db:
        upcoming = ScheduleService(db).get_tutor_upcoming_sessions(user.user_id)
        earnings = PaymentService(db).get_tutor_earnings(telegram_id)
        total_earned = earnings.get("total_earned", 0) if earnings["success"] else 0
        text = tutor_dashboard(
            full_name=user.full_name, user_id=user.user_id,
            upcoming_count=len(upcoming), total_earned=total_earned,
            is_verified=user.is_verified)

    kbd = tutor_reply_keyboard()
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        await update.callback_query.message.reply_text("👇 Use the buttons below:", reply_markup=kbd)
    elif update.message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kbd, disable_web_page_preview=True)


async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository
    from services.audit_service import AuditService
    from ui.templates import admin_dashboard
    from ui.keyboards import admin_reply_keyboard
    from telegram.constants import ParseMode

    telegram_id = update.effective_user.id

    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(telegram_id)
        if not user:
            await reply(update, "❌ User not found.")
            return
        stats = AuditService(db).system_dashboard()

    text = admin_dashboard(full_name=user.full_name, user_id=user.user_id, stats=stats)
    kbd = admin_reply_keyboard()

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        await update.callback_query.message.reply_text("👇 Use the buttons below:", reply_markup=kbd)
    elif update.message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kbd, disable_web_page_preview=True)


async def route_to_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)

    if not user:
        from ui.templates import welcome_unregistered
        from ui.keyboards import unregistered_menu
        await reply(update, welcome_unregistered(update.effective_user.first_name),
                    reply_markup=unregistered_menu())
        return

    if not user.is_active:
        await reply(update, "🚫 Your account has been suspended. Please contact an admin.")
        return

    if user.role == "student":
        await show_student_dashboard(update, context)
    elif user.role == "tutor":
        await show_tutor_dashboard(update, context)
    elif user.role == "admin":
        await show_admin_dashboard(update, context)