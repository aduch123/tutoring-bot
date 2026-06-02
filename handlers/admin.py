"""Admin-facing handlers."""
import logging
from datetime import datetime, time, date
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
from config.db import get_db
from utils.error_handler import handle_errors, admin_only
from utils.helpers import reply, send

logger = logging.getLogger(__name__)


# ── Dashboard / Overview ──────────────────────────────────────────────────────

@handle_errors
@admin_only
async def admin_overview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.audit_service import AuditService
    from repositories.user import UserRepository
    from ui.templates import admin_dashboard
    from ui.keyboards import admin_dashboard as kbd
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        stats = AuditService(db).system_dashboard()
    await reply(update, admin_dashboard(user.full_name, user.user_id, stats), reply_markup=kbd())


# ── Tutor approval ────────────────────────────────────────────────────────────

@handle_errors
@admin_only
async def approve_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.registration import RegistrationService
    args = context.args
    if not args:
        await reply(update, "Usage: `/approve_tutor TUT-XXXX`")
        return
    tutor_id = args[0].upper()
    with next(get_db()) as db:
        result = RegistrationService(db).approve_tutor(tutor_id, update.effective_user.id)
    if not result["success"]:
        await reply(update, f"❌ {result['message']}")
        return
    await reply(update, f"✅ {result['message']}")
    if result.get("telegram_id"):
        await send(context.bot, result["telegram_id"],
            "🎉 *Your tutor application has been approved!*\n\n"
            "Welcome to EduConnect. Your dashboard is now active.\n"
            "Use /start to begin."
        )


@handle_errors
@admin_only
async def list_pending_tutors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository, TutorRepository
    from ui.keyboards import back
    with next(get_db()) as db:
        users = UserRepository(db).get_all_by_role("tutor")
        pending = [u for u in users if not u.is_verified]
        if not pending:
            await reply(update, "✅ *No pending tutor applications.*", reply_markup=back())
            return
        lines = [f"👥 *Pending Tutor Applications ({len(pending)})*\n"]
        for u in pending:
            tutor = TutorRepository(db).get(u.user_id)
            subjects = (tutor.primary_subjects or "N/A") if tutor else "N/A"
            lines.append(
                f"\n👨‍🏫 *{u.full_name}*\n"
                f"  ID: `{u.user_id}`\n"
                f"  Subjects: {subjects}\n"
                f"  → `/approve_tutor {u.user_id}`"
            )
    await reply(update, "\n".join(lines), reply_markup=back())


# ── Schedule management ───────────────────────────────────────────────────────

# States for new_schedule conversation
(SCH_STUDENT, SCH_TUTOR, SCH_SUBJECT, SCH_DAYS, SCH_TIME) = range(5)

DAY_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


async def new_schedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update,
        "📆 *Create New Schedule*\n\n"
        "Step 1/5 — Enter the *Student ID*:\n_(e.g. `STU-0001`)_"
    )
    return SCH_STUDENT


async def sch_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = update.message.text.strip().upper()
    from repositories.user import UserRepository
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(sid)
        if not user or user.role != "student":
            await update.message.reply_text(f"❌ Student `{sid}` not found. Try again:")
            return SCH_STUDENT
    context.user_data["sch_student"] = sid
    await update.message.reply_text("Step 2/5 — Enter the *Tutor ID*:\n_(e.g. `TUT-0001`)_", parse_mode=ParseMode.MARKDOWN)
    return SCH_TUTOR


async def sch_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.message.text.strip().upper()
    from repositories.user import UserRepository
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(tid)
        if not user or user.role != "tutor" or not user.is_verified:
            await update.message.reply_text(f"❌ Verified tutor `{tid}` not found. Try again:")
            return SCH_TUTOR
    context.user_data["sch_tutor"] = tid
    await update.message.reply_text("Step 3/5 — Enter the *subject*:\n_(e.g. Mathematics)_", parse_mode=ParseMode.MARKDOWN)
    return SCH_SUBJECT


async def sch_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sch_subject"] = update.message.text.strip()
    await update.message.reply_text(
        "Step 4/5 — Which *days of the week*?\n"
        "_(Comma-separated, e.g. `Mon, Wed, Fri`)_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return SCH_DAYS


async def sch_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip().lower()
    parts = [p.strip() for p in raw.replace("/", ",").split(",")]
    day_nums = []
    for p in parts:
        if p in DAY_MAP:
            day_nums.append(DAY_MAP[p])
        else:
            await update.message.reply_text(
                f"❌ Unrecognised day: *{p}*\n"
                f"Use: Mon, Tue, Wed, Thu, Fri, Sat, Sun",
                parse_mode=ParseMode.MARKDOWN,
            )
            return SCH_DAYS
    context.user_data["sch_days"] = ",".join(str(d) for d in sorted(set(day_nums)))
    await update.message.reply_text(
        "Step 5/5 — Session *start and end time*?\n"
        "_(Format: `HH:MM-HH:MM`, e.g. `15:00-18:00`)_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return SCH_TIME


async def sch_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.schedule_service import ScheduleService
    from ui.keyboards import back
    raw = update.message.text.strip()
    try:
        start_str, end_str = raw.split("-")
        start_t = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_t = datetime.strptime(end_str.strip(), "%H:%M").time()
    except Exception:
        await update.message.reply_text("❌ Invalid format. Use `HH:MM-HH:MM` (e.g. `15:00-18:00`):", parse_mode=ParseMode.MARKDOWN)
        return SCH_TIME

    with next(get_db()) as db:
        result = ScheduleService(db).create_schedule(
            admin_telegram_id=update.effective_user.id,
            student_id=context.user_data["sch_student"],
            tutor_id=context.user_data["sch_tutor"],
            subject=context.user_data["sch_subject"],
            days_str=context.user_data["sch_days"],
            start_time=start_t,
            end_time=end_t,
        )

    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}", reply_markup=back())
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ *Schedule Created!*\n\n"
        f"ID: `{result['schedule_id']}`\n"
        f"Student: {result['student']}\n"
        f"Tutor: {result['tutor']}\n"
        f"Subject: {result['subject']}\n"
        f"Days: {result['days']}\n"
        f"Time: {result['time']}\n\n"
        f"Sessions will be auto-generated nightly.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back(),
    )

    # Notify student and tutor
    from repositories.user import UserRepository
    with next(get_db()) as db:
        student = UserRepository(db).get_by_user_id(context.user_data["sch_student"])
        tutor = UserRepository(db).get_by_user_id(context.user_data["sch_tutor"])

    msg = (
        f"📆 *New Schedule Assigned*\n\n"
        f"📚 Subject: {result['subject']}\n"
        f"📅 Days: {result['days']}\n"
        f"🕐 Time: {result['time']}"
    )
    if student:
        await send(context.bot, student.telegram_id,
            msg + f"\n👨‍🏫 Tutor: {result['tutor']}")
    if tutor:
        await send(context.bot, tutor.telegram_id,
            msg + f"\n👤 Student: {result['student']}")

    context.user_data.clear()
    return ConversationHandler.END


@handle_errors
@admin_only
async def deactivate_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.schedule_service import ScheduleService
    args = context.args
    if not args:
        await reply(update, "Usage: `/deactivate_schedule SCH-XXXX`")
        return
    with next(get_db()) as db:
        result = ScheduleService(db).deactivate_schedule(update.effective_user.id, args[0].upper())
    await reply(update, f"{'✅' if result['success'] else '❌'} {result['message']}")


@handle_errors
@admin_only
async def view_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.schedule import ScheduleRepository
    from repositories.user import UserRepository
    from ui.keyboards import back
    from services.schedule_service import _day_label
    with next(get_db()) as db:
        scheds = ScheduleRepository(db).get_all_active()
        if not scheds:
            await reply(update, "📆 *No active schedules.*", reply_markup=back())
            return
        lines = [f"📆 *All Active Schedules ({len(scheds)})*\n"]
        for s in scheds:
            student = UserRepository(db).get_by_user_id(s.student_id)
            tutor = UserRepository(db).get_by_user_id(s.tutor_id)
            lines.append(
                f"\n`{s.schedule_id}` *{s.subject}*\n"
                f"  👤 {student.full_name if student else s.student_id}\n"
                f"  👨‍🏫 {tutor.full_name if tutor else s.tutor_id}\n"
                f"  📅 {_day_label(s.days_of_week)} · {s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}"
            )
    await reply(update, "\n".join(lines), reply_markup=back())


# ── User management ───────────────────────────────────────────────────────────

@handle_errors
@admin_only
async def audit_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.audit_service import AuditService
    from ui.templates import admin_user_audit
    from ui.keyboards import back
    args = context.args
    if not args:
        await reply(update, "Usage: `/audit STU-XXXX` or `/audit TUT-XXXX`")
        return
    with next(get_db()) as db:
        result = AuditService(db).user_audit(args[0].upper())
    if not result["success"]:
        await reply(update, f"❌ {result['message']}")
        return
    await reply(update, admin_user_audit(result), reply_markup=back())


@handle_errors
@admin_only
async def suspend_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository
    args = context.args
    if not args:
        await reply(update, "Usage: `/suspend STU-XXXX`")
        return
    user_id = args[0].upper()
    with next(get_db()) as db:
        repo = UserRepository(db)
        user = repo.get_by_user_id(user_id)
        if not user:
            await reply(update, f"❌ User {user_id} not found.")
            return
        repo.set_active(user_id, False)
        telegram_id = user.telegram_id
        name = user.full_name
    await reply(update, f"🚫 *{name}* (`{user_id}`) has been suspended.")
    await send(context.bot, telegram_id, "🚫 Your account has been suspended. Contact an admin for details.")


@handle_errors
@admin_only
async def activate_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository
    args = context.args
    if not args:
        await reply(update, "Usage: `/activate STU-XXXX`")
        return
    user_id = args[0].upper()
    with next(get_db()) as db:
        repo = UserRepository(db)
        user = repo.get_by_user_id(user_id)
        if not user:
            await reply(update, f"❌ User {user_id} not found.")
            return
        repo.set_active(user_id, True)
        telegram_id = user.telegram_id
        name = user.full_name
    await reply(update, f"✅ *{name}* (`{user_id}`) has been reactivated.")
    await send(context.bot, telegram_id, "✅ Your account has been reactivated. Use /start to continue.")


# ── Admin management ──────────────────────────────────────────────────────────

@handle_errors
@admin_only
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.admin_manager import AdminManagerService
    args = context.args
    if not args:
        await reply(update, "Usage: `/add_admin TELEGRAM_ID`")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await reply(update, "❌ Please provide a valid numeric Telegram ID.")
        return
    with next(get_db()) as db:
        result = AdminManagerService(db).add_admin(update.effective_user.id, target_id)
    await reply(update, f"{'✅' if result['success'] else '❌'} {result['message']}")


@handle_errors
@admin_only
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.admin_manager import AdminManagerService
    args = context.args
    if not args:
        await reply(update, "Usage: `/remove_admin TELEGRAM_ID`")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await reply(update, "❌ Please provide a valid numeric Telegram ID.")
        return
    with next(get_db()) as db:
        result = AdminManagerService(db).remove_admin(update.effective_user.id, target_id)
    await reply(update, f"{'✅' if result['success'] else '❌'} {result['message']}")


@handle_errors
@admin_only
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository
    from ui.keyboards import back
    with next(get_db()) as db:
        admins = UserRepository(db).get_all_by_role("admin")
    lines = [f"👑 *Admin List ({len(admins)})*\n"]
    for a in admins:
        master = " 👑 Master" if a.is_master_admin else ""
        lines.append(f"• {a.full_name} (`{a.user_id}`){master}")
    await reply(update, "\n".join(lines), reply_markup=back())


# ── Finance ───────────────────────────────────────────────────────────────────

@handle_errors
@admin_only
async def set_student_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /set_rate STU-XXXX 500"""
    from services.payment_service import PaymentService
    args = context.args
    if len(args) < 2:
        await reply(update, "Usage: `/set_rate STU-XXXX 500`")
        return
    try:
        rate = float(args[1])
    except ValueError:
        await reply(update, "❌ Rate must be a number.")
        return
    with next(get_db()) as db:
        result = PaymentService(db).set_student_rate(update.effective_user.id, args[0].upper(), rate)
    await reply(update, f"{'✅' if result['success'] else '❌'} {result['message']}")


@handle_errors
@admin_only
async def create_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /create_invoice STU-XXXX YYYY-MM amount"""
    from services.payment_service import PaymentService
    from decimal import Decimal
    args = context.args
    if len(args) < 3:
        await reply(update, "Usage: `/create_invoice STU-XXXX YYYY-MM amount`")
        return
    try:
        month = datetime.strptime(args[1], "%Y-%m").date().replace(day=1)
        amount = Decimal(args[2])
    except Exception:
        await reply(update, "❌ Invalid format. Use: `/create_invoice STU-0001 2025-06 1200`")
        return
    with next(get_db()) as db:
        result = PaymentService(db).create_invoice(update.effective_user.id, args[0].upper(), month, amount)
    if not result["success"]:
        await reply(update, f"❌ {result['message']}")
        return
    await reply(update,
        f"🧾 *Invoice Created*\n\n"
        f"Student: {result['student_name']}\n"
        f"Month: {result['month']}\n"
        f"Amount: {result['amount']:.0f} ETB\n"
        f"TXN: `{result['transaction_id']}`"
    )


@handle_errors
@admin_only
async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /confirm_payment TXN-XXXX"""
    from services.payment_service import PaymentService
    from ui.templates import payment_confirmed_student
    args = context.args
    if not args:
        await reply(update, "Usage: `/confirm_payment TXN-XXXX`")
        return
    with next(get_db()) as db:
        result = PaymentService(db).confirm_payment(update.effective_user.id, args[0])
    if not result["success"]:
        await reply(update, f"❌ {result['message']}")
        return
    await reply(update, f"✅ Payment confirmed for *{result['student_name']}* — {result['month']}")
    if result.get("student_telegram_id"):
        await send(context.bot, result["student_telegram_id"],
            payment_confirmed_student(result["student_name"], result["month"], result["amount"]))


@handle_errors
@admin_only
async def generate_payouts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /generate_payouts YYYY-MM"""
    from services.payment_service import PaymentService
    args = context.args
    if not args:
        await reply(update, "Usage: `/generate_payouts YYYY-MM`")
        return
    try:
        month = datetime.strptime(args[0], "%Y-%m").date().replace(day=1)
    except Exception:
        await reply(update, "❌ Use format YYYY-MM (e.g. 2025-06)")
        return
    with next(get_db()) as db:
        result = PaymentService(db).generate_monthly_payouts(update.effective_user.id, month)
    if not result["success"]:
        await reply(update, f"❌ {result['message']}")
        return
    lines = [f"💸 *Payouts Generated — {result['month']}*\n\nTotal: {result['created']} tutors\n"]
    for p in result["payouts"]:
        lines.append(f"• {p['tutor']} — {p['sessions']} sessions — *{p['net']:.0f} ETB*")
    await reply(update, "\n".join(lines))


@handle_errors
@admin_only
async def mark_payout_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /payout_paid TUT-XXXX YYYY-MM"""
    from services.payment_service import PaymentService
    from ui.templates import payout_paid_tutor
    args = context.args
    if len(args) < 2:
        await reply(update, "Usage: `/payout_paid TUT-XXXX YYYY-MM`")
        return
    try:
        month = datetime.strptime(args[1], "%Y-%m").date().replace(day=1)
    except Exception:
        await reply(update, "❌ Use format YYYY-MM")
        return
    with next(get_db()) as db:
        result = PaymentService(db).mark_payout_paid(update.effective_user.id, args[0].upper(), month)
    if not result["success"]:
        await reply(update, f"❌ {result['message']}")
        return
    await reply(update, f"✅ Payout marked paid for *{result['tutor_name']}* — {result['month']}")
    if result.get("tutor_telegram_id"):
        await send(context.bot, result["tutor_telegram_id"],
            payout_paid_tutor(result["tutor_name"], result["month"], result["net"]))


# ── Emergencies ───────────────────────────────────────────────────────────────

@handle_errors
@admin_only
async def check_emergencies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.emergency_service import EmergencyService
    from ui.templates import admin_emergencies
    from ui.keyboards import back
    with next(get_db()) as db:
        items = EmergencyService(db).get_open()
    await reply(update, admin_emergencies(items), reply_markup=back())


@handle_errors
@admin_only
async def resolve_emergency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /resolve EMG-XXXX resolution notes here"""
    from services.emergency_service import EmergencyService
    args = context.args
    if len(args) < 2:
        await reply(update, "Usage: /resolve EMG-XXXX your resolution notes")
        return
    emg_id = args[0].upper()
    notes = " ".join(args[1:])
    with next(get_db()) as db:
        result = EmergencyService(db).resolve(update.effective_user.id, emg_id, notes)
    if not result["success"]:
        await reply(update, f"❌ {result['message']}")
        return
    await reply(update, f"✅ Emergency `{emg_id}` resolved.")
    if result.get("reporter_telegram_id"):
        await send(context.bot, result["reporter_telegram_id"],
            f"✅ *Your issue has been resolved*\n\n"
            f"Ticket: `{emg_id}`\n"
            f"Resolution: {notes}"
        )


# ── Conversation handler for new_schedule ────────────────────────────────────

def new_schedule_conv_handler():
    async def _cancel(update, context):
        context.user_data.clear()
        await reply(update, "❌ Cancelled.")
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(new_schedule_start, pattern="^new_schedule$"),
            CommandHandler("new_schedule", new_schedule_start),
        ],
        states={
            SCH_STUDENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sch_student)],
            SCH_TUTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, sch_tutor)],
            SCH_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sch_subject)],
            SCH_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, sch_days)],
            SCH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sch_time)],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
        name="new_schedule",
        persistent=False,
    )
