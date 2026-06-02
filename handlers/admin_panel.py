"""
Full admin panel — button-driven CRUD for all entities.
No technical knowledge required.
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters,
)
from telegram.constants import ParseMode
from config.db import get_db
from utils.helpers import reply, send
from utils.error_handler import handle_errors, admin_only

logger = logging.getLogger(__name__)

PAGE_SIZE = 8

DAY_MAP = {
    "mon": 0, "monday": 0, "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2, "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4, "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _day_label(days_str: str) -> str:
    return ", ".join(DAY_NAMES[int(d)] for d in days_str.split(",") if d.strip().isdigit())


def _kb(rows): return InlineKeyboardMarkup(rows)
def _back(cb): return _kb([[InlineKeyboardButton("‹ Back", callback_data=cb)]])
def _back_row(cb): return [InlineKeyboardButton("‹ Back", callback_data=cb)]

# States
(
    EDIT_STU_VALUE, EDIT_TUT_VALUE, EDIT_ADM_VALUE,
    ASSIGN_SUBJECTS, ASSIGN_DAYS, ASSIGN_TIME,
    ADD_ADMIN_ID, ADD_ADMIN_CONFIRM,
) = range(8)


# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

@handle_errors
@admin_only
async def admin_overview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.audit_service import AuditService
    from repositories.user import UserRepository
    from ui.templates import admin_dashboard
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        stats = AuditService(db).system_dashboard()
    from ui.keyboards import back
    await reply(update, admin_dashboard(user.full_name, user.user_id, stats),
                reply_markup=back("admin_home"))


# ══════════════════════════════════════════════════════════════════════════════
# STUDENT LIST & DETAIL
# ══════════════════════════════════════════════════════════════════════════════

@handle_errors
@admin_only
async def show_students_list(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              filter_type: str = "all", page: int = 0):
    from services.audit_service import AuditService
    from ui.keyboards import admin_students_filter

    with next(get_db()) as db:
        data = AuditService(db).get_students_filtered(filter_type)

    total = len(data)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = data[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    rows = []
    for s in chunk:
        icons = ("✅" if s["is_active"] else "🚫")
        icons += (" 💳" if s["is_paid"] else " ❌")
        icons += (" 👨‍🏫" if s["has_tutor"] else " 🔍")
        rows.append([InlineKeyboardButton(
            f"{icons}  {s['full_name']}",
            callback_data=f"stu_detail_{s['user_id']}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Prev",
                    callback_data=f"students_filter_{filter_type}_page_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next →",
                    callback_data=f"students_filter_{filter_type}_page_{page+1}"))
    if nav:
        rows.append(nav)

    # Filter tabs
    rows.append([
        InlineKeyboardButton("All" if filter_type != "all" else "● All",
                              callback_data="students_filter_all"),
        InlineKeyboardButton("Unpaid" if filter_type != "unpaid" else "● Unpaid",
                              callback_data="students_filter_unpaid"),
        InlineKeyboardButton("No Tutor" if filter_type != "no_tutor" else "● No Tutor",
                              callback_data="students_filter_no_tutor"),
    ])
    rows.append(_back_row("admin_home"))

    legend = "✅=Active  💳=Paid  👨‍🏫=Has Tutor  🚫=Suspended  ❌=Unpaid  🔍=No Tutor"
    text = f"📚 *Students ({total})*\n_{legend}_\n\nTap a student for details:"
    await reply(update, text, reply_markup=_kb(rows))


@handle_errors
@admin_only
async def student_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: str):
    from repositories.user import UserRepository, StudentRepository
    from repositories.schedule import ScheduleRepository
    from services.payment_service import PaymentService

    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(student_id)
        if not user:
            await reply(update, "❌ Student not found.", reply_markup=_back("list_students_all"))
            return
        stu = StudentRepository(db).get(student_id)
        rate = PaymentService(db).get_student_rate(student_id)
        pay_status = PaymentService(db).get_student_payment_status(student_id)
        scheds = ScheduleRepository(db).get_by_student(student_id)

        pay_icon = {"paid": "✅", "screenshot_uploaded": "⏳", "unpaid": "❌"}.get(
            pay_status["status"], "❓")

        sched_lines = []
        for s in scheds:
            tutor = UserRepository(db).get_by_user_id(s.tutor_id)
            sched_lines.append(
                f"  • {s.subject}  ·  {tutor.full_name if tutor else s.tutor_id}\n"
                f"    {_day_label(s.days_of_week)}  ·  "
                f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}  "
                f"`{s.schedule_id}`"
            )

    text = (
        f"📋 *Student Details*\n\n"
        f"👤 *{user.full_name}*\n"
        f"{'─'*26}\n"
        f"🆔  `{user.user_id}`\n"
        f"📱  {user.phone}\n"
        f"🎓  Grade: {stu.grade if stu else '—'}\n"
        f"📚  Subjects: {stu.subjects if stu else '—'}\n"
        f"👪  Parent: {stu.parent_phone if stu else '—'}\n"
        f"💵  Rate: {rate:.0f} ETB/hr\n"
        f"💳  Payment: {pay_icon} {pay_status['status'].replace('_',' ').title()}\n"
        f"⚡  Status: {'✅ Active' if user.is_active else '🚫 Suspended'}\n"
        f"📅  Joined: {user.created_at.strftime('%d %b %Y')}\n\n"
    )
    if sched_lines:
        text += f"📆 *Schedules ({len(scheds)}):*\n" + "\n".join(sched_lines)
    else:
        text += "📆 *Schedules:* None — tap Assign Tutor to create one"

    rows = [
        [InlineKeyboardButton("➕ Assign Tutor", callback_data=f"assign_tutor_{student_id}"),
         InlineKeyboardButton("✏️ Edit", callback_data=f"edit_student_{student_id}")],
        [InlineKeyboardButton("💵 Set Rate", callback_data=f"setrate_stu_{student_id}"),
         InlineKeyboardButton("📆 Schedules", callback_data=f"edit_schedule_stu_{student_id}")],
        [InlineKeyboardButton("✉️ Send Message", callback_data=f"send_message_{student_id}")],
        [InlineKeyboardButton(
            "🚫 Suspend" if user.is_active else "✅ Activate",
            callback_data=f"toggle_active_stu_{student_id}"),
         InlineKeyboardButton("🗑️ Delete", callback_data=f"confirm_delete_stu_{student_id}")],
        _back_row("students_filter_all"),
    ]
    await reply(update, text, reply_markup=_kb(rows))


# ══════════════════════════════════════════════════════════════════════════════
# TUTOR LIST & DETAIL
# ══════════════════════════════════════════════════════════════════════════════

@handle_errors
@admin_only
async def show_tutors_list(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            filter_type: str = "all", page: int = 0):
    from services.audit_service import AuditService

    with next(get_db()) as db:
        data = AuditService(db).get_tutors_filtered(filter_type)

    total = len(data)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = data[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    rows = []
    for t in chunk:
        status = "✅" if t["is_verified"] and t["is_active"] else ("⏳" if not t["is_verified"] else "🚫")
        rows.append([InlineKeyboardButton(
            f"{status}  {t['full_name']}  ·  {(t['subjects'] or '—')[:30]}",
            callback_data=f"tut_detail_{t['user_id']}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Prev",
                    callback_data=f"tutors_filter_{filter_type}_page_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next →",
                    callback_data=f"tutors_filter_{filter_type}_page_{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("● All" if filter_type == "all" else "All",
                              callback_data="tutors_filter_all"),
        InlineKeyboardButton("● Pending" if filter_type == "pending" else "⏳ Pending",
                              callback_data="tutors_filter_pending"),
        InlineKeyboardButton("● Suspended" if filter_type == "suspended" else "🚫 Suspended",
                              callback_data="tutors_filter_suspended"),
    ])
    rows.append(_back_row("admin_home"))

    await reply(update,
        f"👨‍🏫 *Tutors ({total})*\n_✅=Verified  ⏳=Pending  🚫=Suspended_\n\nTap a tutor for details:",
        reply_markup=_kb(rows))


@handle_errors
@admin_only
async def tutor_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, tutor_id: str):
    from repositories.user import UserRepository, TutorRepository
    from repositories.schedule import ScheduleRepository
    from services.payment_service import PaymentService

    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(tutor_id)
        if not user:
            await reply(update, "❌ Tutor not found.", reply_markup=_back("tutors_filter_all"))
            return
        tut = TutorRepository(db).get(tutor_id)
        scheds = ScheduleRepository(db).get_by_tutor(tutor_id)
        earnings = PaymentService(db).get_tutor_earnings(user.telegram_id)
        total_earned = earnings.get("total_earned", 0) if earnings["success"] else 0

        sched_lines = []
        for s in scheds:
            student = UserRepository(db).get_by_user_id(s.student_id)
            sched_lines.append(
                f"  • {s.subject}  ·  {student.full_name if student else s.student_id}\n"
                f"    {_day_label(s.days_of_week)}  ·  "
                f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}  "
                f"`{s.schedule_id}`"
            )

    text = (
        f"📋 *Tutor Details*\n\n"
        f"👨‍🏫 *{user.full_name}*\n"
        f"{'─'*26}\n"
        f"🆔  `{user.user_id}`\n"
        f"📱  {user.phone}\n"
        f"★  Primary: {tut.primary_subjects if tut else '—'}\n"
        f"○  Secondary: {tut.secondary_subjects if tut else '—'}\n"
        f"🎓  Experience: {tut.experience if tut else '—'}\n"
        f"📊  Total sessions: {tut.total_sessions if tut else 0}\n"
        f"💰  Total earned: {total_earned:.0f} ETB\n"
        f"✅  Verified: {'Yes' if user.is_verified else '⏳ Pending'}\n"
        f"⚡  Status: {'✅ Active' if user.is_active else '🚫 Suspended'}\n"
        f"📅  Joined: {user.created_at.strftime('%d %b %Y')}\n\n"
    )
    if sched_lines:
        text += f"📆 *Schedules ({len(scheds)}):*\n" + "\n".join(sched_lines)
    else:
        text += "📆 *Schedules:* None assigned"

    rows = []
    approval_status = tut.approval_status if tut else None
    if approval_status == "pending_documents":
        rows.append([
            InlineKeyboardButton("✅ Approve Docs", callback_data=f"approve_docs_{tutor_id}"),
            InlineKeyboardButton("❌ Reject Docs", callback_data=f"reject_docs_{tutor_id}"),
        ])
    elif approval_status == "pending_video":
        rows.append([
            InlineKeyboardButton("✅ Approve Video", callback_data=f"approve_video_{tutor_id}"),
            InlineKeyboardButton("🚫 Reject & Blacklist", callback_data=f"reject_video_{tutor_id}"),
        ])
    elif not user.is_verified:
        rows.append([InlineKeyboardButton(
            "✅ Approve Tutor", callback_data=f"approve_tut_{tutor_id}")])
    rows.append([
        InlineKeyboardButton("✏️ Edit", callback_data=f"edit_tutor_{tutor_id}"),
        InlineKeyboardButton("📆 Schedules", callback_data=f"edit_schedule_tut_{tutor_id}"),
    ])
    rows.append([
        InlineKeyboardButton(
            "🚫 Suspend" if user.is_active else "✅ Activate",
            callback_data=f"toggle_active_tut_{tutor_id}"),
        InlineKeyboardButton("🗑️ Delete", callback_data=f"confirm_delete_tut_{tutor_id}"),
    ])
    rows.append(_back_row("tutors_filter_all"))
    await reply(update, text, reply_markup=_kb(rows))


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN LIST & DETAIL
# ══════════════════════════════════════════════════════════════════════════════

@handle_errors
@admin_only
async def show_admins_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    from repositories.user import UserRepository

    with next(get_db()) as db:
        users = UserRepository(db).get_all_by_role("admin")
        data = [{"user_id": u.user_id, "full_name": u.full_name,
                 "phone": u.phone, "is_master": u.is_master_admin}
                for u in users]

    total = len(data)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = data[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    rows = []
    for a in chunk:
        crown = "👑" if a["is_master"] else "🔑"
        rows.append([InlineKeyboardButton(
            f"{crown}  {a['full_name']}  ·  {a['phone']}",
            callback_data=f"adm_detail_{a['user_id']}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Prev", callback_data=f"admins_page_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next →", callback_data=f"admins_page_{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("➕ Add New Admin", callback_data="add_admin_flow")])
    rows.append(_back_row("admin_home"))
    await reply(update, f"👑 *Admins ({total})*\n\nTap an admin for details:",
                reply_markup=_kb(rows))


@handle_errors
@admin_only
async def admin_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: str):
    from repositories.user import UserRepository

    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(admin_id)
        caller = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        is_master_caller = caller and caller.is_master_admin if caller else False

    if not user:
        await reply(update, "❌ Admin not found.", reply_markup=_back("admins_filter_all"))
        return

    text = (
        f"📋 *Admin Details*\n\n"
        f"{'👑' if user.is_master_admin else '🔑'} *{user.full_name}*\n"
        f"{'─'*26}\n"
        f"🆔  `{user.user_id}`\n"
        f"📱  {user.phone}\n"
        f"👑  Master admin: {'Yes' if user.is_master_admin else 'No'}\n"
        f"📅  Joined: {user.created_at.strftime('%d %b %Y')}"
    )
    rows = [
        [InlineKeyboardButton("✏️ Edit Name", callback_data=f"edit_adm_name_{admin_id}"),
         InlineKeyboardButton("📱 Edit Phone", callback_data=f"edit_adm_phone_{admin_id}")],
    ]
    if is_master_caller and not user.is_master_admin:
        rows.append([InlineKeyboardButton(
            "🗑️ Remove Admin", callback_data=f"confirm_delete_adm_{admin_id}")])
    rows.append(_back_row("admins_filter_all"))
    await reply(update, text, reply_markup=_kb(rows))


# ══════════════════════════════════════════════════════════════════════════════
# ADD ADMIN FLOW
# ══════════════════════════════════════════════════════════════════════════════

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.admin_service import AdminService
    with next(get_db()) as db:
        if not AdminService.is_master_admin(update.effective_user.id, db):
            await reply(update, "🚫 Only master admins can add new admins.",
                        reply_markup=_back("admins_filter_all"))
            return ConversationHandler.END

    await reply(update,
        "➕ *Add New Admin*\n\n"
        "Send me the *Telegram ID* of the person to promote.\n\n"
        "They can get their ID by sending `/myid` to this bot.",
        reply_markup=_back("admins_filter_all"))
    return ADD_ADMIN_ID


async def add_admin_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ That doesn't look like a Telegram ID. Please send a number:",
            reply_markup=_back("admins_filter_all"))
        return ADD_ADMIN_ID

    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(target_id)

    if not user:
        await update.message.reply_text(
            f"❌ No registered user found with Telegram ID `{target_id}`.\n\n"
            f"They must register with the bot first.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_back("admins_filter_all"))
        return ADD_ADMIN_ID

    if user.role == "admin":
        await update.message.reply_text(
            f"⚠️ *{user.full_name}* is already an admin.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_back("admins_filter_all"))
        return ConversationHandler.END

    context.user_data["new_admin_telegram_id"] = target_id
    context.user_data["new_admin_name"] = user.full_name
    context.user_data["new_admin_user_id"] = user.user_id

    await update.message.reply_text(
        f"👤 Found: *{user.full_name}*\n"
        f"Role: {user.role.capitalize()}\n"
        f"ID: `{user.user_id}`\n\n"
        f"Promote this person to admin?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([
            [InlineKeyboardButton("✅ Yes, Promote", callback_data="confirm_add_admin"),
             InlineKeyboardButton("❌ Cancel", callback_data="admins_filter_all")],
        ]))
    return ADD_ADMIN_CONFIRM


async def add_admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = context.user_data.get("new_admin_telegram_id")
    name = context.user_data.get("new_admin_name")

    from services.admin_manager import AdminManagerService
    with next(get_db()) as db:
        result = AdminManagerService(db).add_admin(update.effective_user.id, target_id)

    if not result["success"]:
        await query.edit_message_text(f"❌ {result['message']}")
        return ConversationHandler.END

    await query.edit_message_text(
        f"✅ *{name}* has been promoted to admin!\n\n"
        f"They will be notified.",
        parse_mode=ParseMode.MARKDOWN)

    try:
        from utils.helpers import send
        await send(update.effective_user._bot if hasattr(update.effective_user, '_bot')
                   else query.message.get_bot(),
                   target_id,
                   "🎉 *You have been promoted to Admin!*\n\n"
                   "Use /start to access your admin dashboard.")
    except Exception:
        pass

    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# EMERGENCIES & ISSUES
# ══════════════════════════════════════════════════════════════════════════════

@handle_errors
@admin_only
async def show_emergencies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.emergency_service import EmergencyService
    from models.emergency import Emergency
    from ui.keyboards import claim_emergency_button

    with next(get_db()) as db:
        items = EmergencyService(db).get_open()
        # Separate emergencies from issues
        emergency_types = {"internet", "no_show", "technical", "behaviour", "urgent"}
        emergencies = [e for e in items if any(
            t in e["issue_type"].lower() for t in
            ["internet", "no-show", "technical", "behaviour", "urgent"])]

    if not emergencies:
        await reply(update, "✅ *No open emergencies.*\n\nAll clear!",
                    reply_markup=_back("admin_home"))
        return

    lines = [f"🚨 *Open Emergencies ({len(emergencies)})*\n"]
    rows = []
    for e in emergencies:
        claimed = f"\n    🔒 Claimed by: {e['claimed_by']}" if e.get("claimed_by") else ""
        lines.append(
            f"\n🔴 `{e['emergency_id']}`\n"
            f"    By: {e['reporter']}  ·  {e['created_at']}\n"
            f"    {e['issue_type']}\n"
            f"    _{e['description'][:80]}_"
            f"{claimed}"
        )
        if not e.get("claimed_by"):
            rows.append([InlineKeyboardButton(
                f"🚨 Handle {e['emergency_id']}",
                callback_data=f"claim_emergency_{e['emergency_id']}")])

    rows.append(_back_row("admin_home"))
    await reply(update, "\n".join(lines), reply_markup=_kb(rows))


@handle_errors
@admin_only
async def show_issues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.emergency_service import EmergencyService
    from ui.keyboards import claim_report_button

    with next(get_db()) as db:
        all_items = EmergencyService(db).get_open()
        issues = [e for e in all_items if any(
            t in e["issue_type"].lower() for t in ["other", "payment", "dispute", "❓"])]

    if not issues:
        await reply(update, "✅ *No open issues.*\n\nAll clear!",
                    reply_markup=_back("admin_home"))
        return

    lines = [f"⚠️ *Open Issues ({len(issues)})*\n"]
    rows = []
    for e in issues:
        claimed = f"\n    🔒 Claimed by: {e['claimed_by']}" if e.get("claimed_by") else ""
        lines.append(
            f"\n🟡 `{e['emergency_id']}`\n"
            f"    By: {e['reporter']}  ·  {e['created_at']}\n"
            f"    _{e['description'][:80]}_"
            f"{claimed}"
        )
        if not e.get("claimed_by"):
            rows.append([InlineKeyboardButton(
                f"📝 Handle {e['emergency_id']}",
                callback_data=f"claim_emergency_{e['emergency_id']}")])

    rows.append(_back_row("admin_home"))
    await reply(update, "\n".join(lines), reply_markup=_kb(rows))


# ══════════════════════════════════════════════════════════════════════════════
# FINANCE
# ══════════════════════════════════════════════════════════════════════════════

@handle_errors
@admin_only
async def show_invoices(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         filter_type: str = "all"):
    from services.audit_service import AuditService
    from ui.keyboards import admin_invoices_filter, invoice_actions

    with next(get_db()) as db:
        invoices = AuditService(db).get_invoices_filtered(filter_type)

    if not invoices:
        await reply(update, f"📋 *No invoices found.*\n\nFilter: _{filter_type}_",
                    reply_markup=admin_invoices_filter())
        return

    rows = []
    for inv in invoices[:20]:
        icon = {"completed": "✅", "screenshot_uploaded": "⏳", "pending": "❌"}.get(
            inv["status"], "❓")
        rows.append([InlineKeyboardButton(
            f"{icon}  {inv['student_name']}  ·  {inv['month']}  ·  {inv['amount']:.0f} ETB",
            callback_data=f"invoice_detail_{inv['transaction_id']}"
        )])

    # Filter tabs
    filters = [("All", "all"), ("Unpaid", "unpaid"), ("Review", "screenshot"), ("Paid", "paid")]
    tab_row = []
    for label, ftype in filters:
        prefix = "● " if ftype == filter_type else ""
        tab_row.append(InlineKeyboardButton(
            f"{prefix}{label}", callback_data=f"invoices_filter_{ftype}"))
    rows.append(tab_row)
    rows.append(_back_row("admin_finance"))

    await reply(update,
        f"🧾 *Invoices ({len(invoices)})*\n\nTap an invoice to view details:",
        reply_markup=_kb(rows))


@handle_errors
@admin_only
async def invoice_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, txn_id: str):
    from repositories.payment import PaymentRepository
    from repositories.user import UserRepository
    from ui.keyboards import invoice_actions

    with next(get_db()) as db:
        payment = PaymentRepository(db).get_by_transaction(txn_id)
        if not payment:
            await reply(update, "❌ Invoice not found.", reply_markup=_back("finance_invoices"))
            return
        student = UserRepository(db).get_by_user_id(payment.student_id)
        icon = {"completed": "✅", "screenshot_uploaded": "⏳", "pending": "❌"}.get(
            payment.status, "❓")

        has_screenshot = bool(payment.screenshot_file_id)
        screenshot_file_id = payment.screenshot_file_id

    text = (
        f"🧾 *Invoice Detail*\n\n"
        f"Student: *{student.full_name if student else payment.student_id}*\n"
        f"Month: {payment.month.strftime('%B %Y')}\n"
        f"Amount: *{float(payment.amount):.0f} ETB*\n"
        f"Status: {icon} {payment.status.replace('_',' ').title()}\n"
        f"TXN: `{payment.transaction_id}`"
    )

    if has_screenshot:
        # Send screenshot first then detail
        try:
            if update.callback_query:
                await update.callback_query.message.reply_photo(
                    photo=screenshot_file_id,
                    caption="📸 Payment screenshot")
        except Exception:
            pass

    await reply(update, text, reply_markup=invoice_actions(txn_id))


@handle_errors
@admin_only
async def show_payouts(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        filter_type: str = "all"):
    from services.audit_service import AuditService
    from ui.keyboards import admin_payouts_filter, payout_actions

    with next(get_db()) as db:
        payouts = AuditService(db).get_payouts_filtered(filter_type)

    if not payouts:
        await reply(update, f"💸 *No payouts found.*\n\nFilter: _{filter_type}_",
                    reply_markup=admin_payouts_filter())
        return

    rows = []
    for p in payouts:
        icon = "✅" if p["status"] == "paid" else "⏳"
        rows.append([InlineKeyboardButton(
            f"{icon}  {p['tutor_name']}  ·  {p['month']}  ·  {p['net']:.0f} ETB",
            callback_data=f"payout_detail_{p['tutor_id']}_{p['month_raw']}"
        )])

    filters = [("All", "all"), ("Pending", "pending"), ("Paid", "paid")]
    tab_row = []
    for label, ftype in filters:
        prefix = "● " if ftype == filter_type else ""
        tab_row.append(InlineKeyboardButton(
            f"{prefix}{label}", callback_data=f"payouts_filter_{ftype}"))
    rows.append(tab_row)
    rows.append([InlineKeyboardButton("💸 Generate This Month",
                                       callback_data="generate_payouts_now")])
    rows.append(_back_row("admin_finance"))

    await reply(update,
        f"💸 *Payouts ({len(payouts)})*\n\nTap a payout to manage it:",
        reply_markup=_kb(rows))


@handle_errors
@admin_only
async def payout_detail(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         tutor_id: str, month_str: str):
    from repositories.payment import PayoutRepository
    from repositories.user import UserRepository
    from ui.keyboards import payout_actions

    with next(get_db()) as db:
        month = datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
        payout = PayoutRepository(db).get_by_tutor_month(tutor_id, month)
        if not payout:
            await reply(update, "❌ Payout not found.", reply_markup=_back("finance_payouts"))
            return
        tutor = UserRepository(db).get_by_user_id(tutor_id)

    icon = "✅" if payout.status == "paid" else "⏳"
    # Get tutor payment accounts
    import json
    accounts_text = ""
    if tutor:
        from models.user import Tutor as TutorModel
        with next(get_db()) as db2:
            tut_rec = db2.query(TutorModel).filter(TutorModel.user_id == tutor_id).first()
            if tut_rec and tut_rec.payment_accounts:
                try:
                    accounts = json.loads(tut_rec.payment_accounts)
                    accounts_text = "\n\n💳 *Tutor Payment Accounts:*\n"
                    for method, number in accounts.items():
                        accounts_text += f"  • {method}: `{number}`\n"
                except Exception:
                    pass
    text = (
        f"💸 *Payout Detail*\n\n"
        f"Tutor: *{tutor.full_name if tutor else tutor_id}*\n"
        f"📱 Phone: {tutor.phone if tutor else '—'}\n"
        f"Month: {payout.month.strftime('%B %Y')}\n"
        f"Sessions ✅ approved: {payout.sessions_completed}\n"
        f"Gross: {float(payout.total_amount):.0f} ETB\n"
        f"Commission: -{float(payout.platform_commission):.0f} ETB\n"
        f"Net: *{float(payout.net_amount):.0f} ETB*\n"
        f"Status: {icon} {payout.status.title()}"
        f"{accounts_text}"
    )
    await reply(update, text, reply_markup=payout_actions(tutor_id, month_str))


# ══════════════════════════════════════════════════════════════════════════════
# ASSIGN TUTOR FLOW
# ══════════════════════════════════════════════════════════════════════════════

@handle_errors
@admin_only
async def show_compatible_tutors(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  student_id: str, filter_type: str = "all"):
    from repositories.user import UserRepository, StudentRepository
    from services.tutor_service import TutorService

    with next(get_db()) as db:
        stu_user = UserRepository(db).get_by_user_id(student_id)
        stu = StudentRepository(db).get(student_id)
        if not stu or not stu.subjects:
            await reply(update,
                "⚠️ This student has no subjects listed.\n\nEdit the student first to add subjects.",
                reply_markup=_back(f"stu_detail_{student_id}"))
            return

        # Get all subjects for this student
        student_subjects = [s.strip() for s in stu.subjects.split(",") if s.strip()]
        svc = TutorService(db)

        # Collect compatible tutors across all student subjects
        seen = {}
        for subj in student_subjects:
            for t in svc.get_available_tutors_for_subject(subj, include_full=True):
                uid = t["user_id"]
                if uid not in seen:
                    seen[uid] = t
                    seen[uid]["matching_subjects"] = []
                seen[uid]["matching_subjects"].append(
                    f"{subj} ({'★' if t['match_type']=='primary' else '○'})")

        compatible = list(seen.values())

    context.user_data["assigning_student_id"] = student_id
    context.user_data["student_subjects"] = stu.subjects
    context.user_data["student_name"] = stu_user.full_name if stu_user else student_id
    context.user_data["student_phone"] = stu_user.phone if stu_user else "—"
    context.user_data["student_days_per_week"] = stu.days_per_week or 3

    if not compatible:
        await reply(update,
            f"⚠️ *No compatible tutors found*\n\n"
            f"Student's subjects: _{stu.subjects}_\n\n"
            f"No verified tutors teach any of these subjects yet.\n\n"
            f"You can approve more tutors or update tutor subject lists.",
            reply_markup=_kb([
                [InlineKeyboardButton("📝 Contact Admin", callback_data="report_issue")],
                _back_row(f"stu_detail_{student_id}"),
            ]))
        return

    # Apply filter
    if filter_type == "primary":
        filtered = [t for t in compatible if t["match_type"] == "primary"]
    elif filter_type == "secondary":
        filtered = [t for t in compatible if t["match_type"] == "secondary"]
    else:
        filtered = compatible

    rows = []
    for t in filtered:
        status_icon = "✅" if t["status"] == "available" else ("🔴" if t["status"] == "full" else "⏳")
        match_label = ", ".join(t.get("matching_subjects", [])[:2])
        rows.append([InlineKeyboardButton(
            f"{status_icon} {t['full_name']}  ·  {t['load']}",
            callback_data=f"tutor_briefing_{t['user_id']}"
        )])
        rows.append([InlineKeyboardButton(
            f"  Matches: {match_label}",
            callback_data="noop"
        )])

    # Filter tabs
    rows.append([
        InlineKeyboardButton("● All" if filter_type == "all" else "All",
                              callback_data=f"assign_filter_all_{student_id}"),
        InlineKeyboardButton("● ★ Primary" if filter_type == "primary" else "★ Primary",
                              callback_data=f"assign_filter_primary_{student_id}"),
        InlineKeyboardButton("● ○ Secondary" if filter_type == "secondary" else "○ Secondary",
                              callback_data=f"assign_filter_secondary_{student_id}"),
    ])
    rows.append(_back_row(f"stu_detail_{student_id}"))

    await reply(update,
        f"👨‍🏫 *Select a Tutor*\n\n"
        f"Student: *{context.user_data['student_name']}*\n"
        f"Subjects: _{stu.subjects}_\n\n"
        f"✅=Available  🔴=Full  ★=Primary match  ○=Secondary\n\n"
        f"Tap a tutor to view briefing before assigning:",
        reply_markup=_kb(rows))


async def show_tutor_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE,
                               tutor_id: str):
    """Show full briefing before admin commits to assignment."""
    import json
    from repositories.user import UserRepository, TutorRepository
    from services.tutor_service import TutorService

    student_id = context.user_data.get("assigning_student_id", "")
    student_name = context.user_data.get("student_name", "Student")
    student_phone = context.user_data.get("student_phone", "—")
    student_subjects = context.user_data.get("student_subjects", "—")
    student_days = context.user_data.get("student_days_per_week", 3)

    with next(get_db()) as db:
        tut_user = UserRepository(db).get_by_user_id(tutor_id)
        tut = TutorRepository(db).get(tutor_id)
        svc = TutorService(db)
        assigned_days = svc.get_weekly_assigned_days(tutor_id)
        max_days = tut.max_teaching_hours if tut else 3
        accounts_text = ""
        if tut and tut.payment_accounts:
            try:
                accounts = json.loads(tut.payment_accounts)
                accounts_text = "\n💳 Accounts: " + ", ".join(
                    f"{k}: {v}" for k, v in accounts.items())
            except Exception:
                pass

    text = (
        f"📋 *Tutor Briefing*\n\n"
        f"{'─'*26}\n"
        f"👨‍🏫 *Tutor*\n"
        f"  Name: *{tut_user.full_name if tut_user else tutor_id}*\n"
        f"  Phone: {tut_user.phone if tut_user else '—'}\n"
        f"  Primary: {tut.primary_subjects if tut else '—'}\n"
        f"  Secondary: {tut.secondary_subjects if tut else '—'}\n"
        f"  Current load: {assigned_days}/{max_days} days/week\n"
        f"{accounts_text}\n"
        f"{'─'*26}\n"
        f"👤 *Student*\n"
        f"  Name: *{student_name}*\n"
        f"  Phone: {student_phone}\n"
        f"  Subjects: {student_subjects}\n"
        f"  Days/week preference: {student_days}\n"
        f"{'─'*26}\n\n"
        f"📞 *Contact both parties to agree on a schedule.*\n\n"
        f"Did they agree on a schedule?"
    )

    context.user_data["assigning_tutor_id"] = tutor_id
    context.user_data["assigning_tutor_name"] = tut_user.full_name if tut_user else tutor_id

    await reply(update, text, reply_markup=_kb([
        [InlineKeyboardButton("✅ Schedule Agreed — Proceed",
                               callback_data=f"do_assign_{tutor_id}"),
         InlineKeyboardButton("❌ No Agreement",
                               callback_data=f"assign_tutor_{student_id}")],
        _back_row(f"assign_tutor_{student_id}"),
    ]))


async def assign_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tutor_id = query.data.replace("do_assign_", "")

    from repositories.user import UserRepository, TutorRepository
    with next(get_db()) as db:
        tutor_user = UserRepository(db).get_by_user_id(tutor_id)
        tut = TutorRepository(db).get(tutor_id)

    context.user_data["assigning_tutor_id"] = tutor_id
    context.user_data["assigning_tutor_name"] = tutor_user.full_name if tutor_user else tutor_id
    student_subjects = context.user_data.get("student_subjects", "")

    await query.edit_message_text(
        f"📆 *Create Schedule*\n\n"
        f"Student: *{context.user_data.get('student_name', 'Student')}*\n"
        f"Tutor: *{tutor_user.full_name if tutor_user else tutor_id}*\n\n"
        f"{'─'*26}\n"
        f"Step 1/3 — Which subjects will this tutor cover?\n\n"
        f"Student's subjects: _{student_subjects}_\n\n"
        f"Type the subjects for this schedule:\n"
        f"_(e.g. `Mathematics, Physics`)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back(f"assign_tutor_{context.user_data.get('assigning_student_id', '')}"),
    )
    return ASSIGN_SUBJECTS


async def assign_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["assign_subjects"] = update.message.text.strip()
    await update.message.reply_text(
        f"Step 2/3 — Which *days of the week*?\n\n"
        f"_(e.g. `Mon, Wed, Fri`)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back(f"assign_tutor_{context.user_data.get('assigning_student_id', '')}"))
    return ASSIGN_DAYS


async def assign_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip().lower()
    parts = [p.strip() for p in raw.replace("/", ",").split(",")]
    day_nums = []
    for p in parts:
        if p in DAY_MAP:
            day_nums.append(DAY_MAP[p])
        else:
            await update.message.reply_text(
                f"❌ Unrecognised day: *{p}*\nUse: Mon, Tue, Wed, Thu, Fri, Sat, Sun",
                parse_mode=ParseMode.MARKDOWN)
            return ASSIGN_DAYS
    context.user_data["assign_days"] = ",".join(str(d) for d in sorted(set(day_nums)))
    days_label = _day_label(context.user_data["assign_days"])
    await update.message.reply_text(
        f"Step 3/3 — Session *start and end time*?\n\n"
        f"Days: _{days_label}_\n\n"
        f"_(Format: `HH:MM-HH:MM`, e.g. `15:00-18:00`)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back(f"assign_tutor_{context.user_data.get('assigning_student_id', '')}"))
    return ASSIGN_TIME


async def assign_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.schedule_service import ScheduleService
    raw = update.message.text.strip()
    try:
        start_str, end_str = raw.split("-")
        start_t = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_t = datetime.strptime(end_str.strip(), "%H:%M").time()
    except Exception:
        await update.message.reply_text(
            "❌ Invalid format. Use `HH:MM-HH:MM` (e.g. `15:00-18:00`):",
            parse_mode=ParseMode.MARKDOWN)
        return ASSIGN_TIME

    student_id = context.user_data["assigning_student_id"]
    tutor_id = context.user_data["assigning_tutor_id"]
    subjects = context.user_data["assign_subjects"]
    days_str = context.user_data["assign_days"]

    with next(get_db()) as db:
        result = ScheduleService(db).create_schedule(
            admin_telegram_id=update.effective_user.id,
            student_id=student_id, tutor_id=tutor_id,
            subject=subjects, days_str=days_str,
            start_time=start_t, end_time=end_t,
        )

    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}",
                                         reply_markup=_back(f"stu_detail_{student_id}"))
        return ConversationHandler.END

    days_label = _day_label(days_str)
    await update.message.reply_text(
        f"✅ *Schedule Created!*\n\n"
        f"🆔 `{result['schedule_id']}`\n"
        f"👤 {result['student']}\n"
        f"👨‍🏫 {result['tutor']}\n"
        f"📚 {subjects}\n"
        f"📅 {days_label}\n"
        f"🕐 {start_t.strftime('%H:%M')} – {end_t.strftime('%H:%M')}\n\n"
        f"Both have been notified.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back(f"stu_detail_{student_id}"))

    from repositories.user import UserRepository
    with next(get_db()) as db:
        student = UserRepository(db).get_by_user_id(student_id)
        tutor = UserRepository(db).get_by_user_id(tutor_id)
    msg = (f"📆 *New Schedule Assigned*\n\n"
           f"📚 {subjects}\n📅 {days_label}\n🕐 {start_t.strftime('%H:%M')} – {end_t.strftime('%H:%M')}")
    if student:
        await send(context.bot, student.telegram_id, msg + f"\n👨‍🏫 Tutor: {result['tutor']}")
    if tutor:
        await send(context.bot, tutor.telegram_id, msg + f"\n👤 Student: {result['student']}")

    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# EDIT FLOWS
# ══════════════════════════════════════════════════════════════════════════════

async def edit_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: str):
    context.user_data["editing_student"] = student_id
    context.user_data["editing_type"] = "student"
    rows = [
        [InlineKeyboardButton("👤 Name", callback_data="edit_stu_name"),
         InlineKeyboardButton("📱 Phone", callback_data="edit_stu_phone")],
        [InlineKeyboardButton("🎓 Grade", callback_data="edit_stu_grade"),
         InlineKeyboardButton("📚 Subjects", callback_data="edit_stu_subjects")],
        [InlineKeyboardButton("👪 Parent Phone", callback_data="edit_stu_parent_phone")],
        _back_row(f"stu_detail_{student_id}"),
    ]
    await reply(update, "✏️ *Edit Student*\n\nWhat would you like to change?",
                reply_markup=_kb(rows))


async def edit_student_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("edit_stu_", "")
    context.user_data["editing_stu_field"] = field
    labels = {"name": "full name", "phone": "phone number",
               "grade": "grade or level", "subjects": "subjects (comma-separated)",
               "parent_phone": "parent phone number"}
    await query.edit_message_text(
        f"✏️ Enter the new *{labels.get(field, field)}*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back(f"edit_student_{context.user_data.get('editing_student', '')}"))
    return EDIT_STU_VALUE


async def edit_student_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository, StudentRepository
    value = update.message.text.strip()
    student_id = context.user_data.get("editing_student")
    field = context.user_data.get("editing_stu_field")
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(student_id)
        stu = StudentRepository(db).get(student_id)
        if field == "name" and user: user.full_name = value; db.commit()
        elif field == "phone" and user: user.phone = value; db.commit()
        elif field == "grade" and stu: stu.grade = value; db.commit()
        elif field == "subjects" and stu: stu.subjects = value; db.commit()
        elif field == "parent_phone" and stu: stu.parent_phone = value; db.commit()
    await update.message.reply_text("✅ Updated.",
                                     reply_markup=_back(f"stu_detail_{student_id}"))
    context.user_data.clear()
    return ConversationHandler.END


async def edit_tutor_start(update: Update, context: ContextTypes.DEFAULT_TYPE, tutor_id: str):
    context.user_data["editing_tutor"] = tutor_id
    rows = [
        [InlineKeyboardButton("👤 Name", callback_data="edit_tut_name"),
         InlineKeyboardButton("📱 Phone", callback_data="edit_tut_phone")],
        [InlineKeyboardButton("📚 Subjects", callback_data="edit_tut_subjects"),
         InlineKeyboardButton("🎓 Experience", callback_data="edit_tut_experience")],
        _back_row(f"tut_detail_{tutor_id}"),
    ]
    await reply(update, "✏️ *Edit Tutor*\n\nWhat would you like to change?",
                reply_markup=_kb(rows))


async def edit_tutor_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("edit_tut_", "")
    context.user_data["editing_tut_field"] = field
    labels = {"name": "full name", "phone": "phone number",
               "subjects": "subjects (comma-separated)", "experience": "experience"}
    await query.edit_message_text(
        f"✏️ Enter the new *{labels.get(field, field)}*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back(f"edit_tutor_{context.user_data.get('editing_tutor', '')}"))
    return EDIT_TUT_VALUE


async def edit_tutor_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository, TutorRepository
    value = update.message.text.strip()
    tutor_id = context.user_data.get("editing_tutor")
    field = context.user_data.get("editing_tut_field")
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(tutor_id)
        tut = TutorRepository(db).get(tutor_id)
        if field == "name" and user: user.full_name = value; db.commit()
        elif field == "phone" and user: user.phone = value; db.commit()
        elif field == "subjects" and tut: tut.subjects = value; db.commit()
        elif field == "experience" and tut: tut.experience = value; db.commit()
    await update.message.reply_text("✅ Updated.",
                                     reply_markup=_back(f"tut_detail_{tutor_id}"))
    context.user_data.clear()
    return ConversationHandler.END


async def edit_admin_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from repositories.user import UserRepository
    value = update.message.text.strip()
    admin_id = context.user_data.get("editing_admin")
    field = context.user_data.get("editing_adm_field")
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(admin_id)
        if user:
            if field == "name": user.full_name = value
            elif field == "phone": user.phone = value
            db.commit()
    await update.message.reply_text("✅ Updated.",
                                     reply_markup=_back(f"adm_detail_{admin_id}"))
    context.user_data.clear()
    return EDIT_ADM_VALUE


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULE EDIT
# ══════════════════════════════════════════════════════════════════════════════

async def edit_schedule_list(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              user_id: str, back_cb: str):
    from repositories.schedule import ScheduleRepository
    from repositories.user import UserRepository
    with next(get_db()) as db:
        from_student = ScheduleRepository(db).get_by_student(user_id)
        from_tutor = ScheduleRepository(db).get_by_tutor(user_id)
        scheds = from_student if from_student else from_tutor
        if not scheds:
            await reply(update, "📆 No active schedules.", reply_markup=_back(back_cb))
            return
        rows = []
        for s in scheds:
            other_id = s.tutor_id if s.student_id == user_id else s.student_id
            other = UserRepository(db).get_by_user_id(other_id)
            rows.append([InlineKeyboardButton(
                f"📚 {s.subject}  ·  {other.full_name if other else other_id}  ·  {_day_label(s.days_of_week)}",
                callback_data="noop")])
            rows.append([
                InlineKeyboardButton("❌ Deactivate",
                                      callback_data=f"deactivate_sch_{s.schedule_id}_{back_cb}"),
            ])
    rows.append(_back_row(back_cb))
    await reply(update, "📆 *Active Schedules*\n\nSelect an action:",
                reply_markup=_kb(rows))


# ══════════════════════════════════════════════════════════════════════════════
# TOGGLE ACTIVE / DELETE
# ══════════════════════════════════════════════════════════════════════════════

async def toggle_active_student(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: str):
    from repositories.user import UserRepository
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(student_id)
        if not user:
            await reply(update, "❌ Student not found.")
            return
        new_state = not user.is_active
        UserRepository(db).set_active(student_id, new_state)
        name, telegram_id = user.full_name, user.telegram_id
    action = "reactivated" if new_state else "suspended"
    await reply(update, f"{'✅' if new_state else '🚫'} *{name}* has been {action}.",
                reply_markup=_back(f"stu_detail_{student_id}"))
    await send(context.bot, telegram_id,
               "✅ Your account has been reactivated. Use /start." if new_state
               else "🚫 Your account has been suspended. Contact an admin.")


async def toggle_active_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE, tutor_id: str):
    from repositories.user import UserRepository
    from repositories.schedule import ScheduleRepository
    from models.schedule import Session as SM
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(tutor_id)
        if not user:
            await reply(update, "❌ Tutor not found.")
            return
        new_state = not user.is_active
        UserRepository(db).set_active(tutor_id, new_state)
        name, telegram_id = user.full_name, user.telegram_id
        affected_students = set()
        if not new_state:
            scheds = ScheduleRepository(db).get_by_tutor(tutor_id)
            for s in scheds:
                s.is_active = False
                affected_students.add(s.student_id)
                future = db.query(SM).filter(
                    SM.schedule_id == s.schedule_id,
                    SM.status.in_(["scheduled", "zoom_pending", "zoom_ready"]),
                    SM.scheduled_start > datetime.now()).all()
                for ses in future:
                    ses.status = "cancelled"
            db.commit()
            for sid in affected_students:
                student = UserRepository(db).get_by_user_id(sid)
                if student:
                    await send(context.bot, student.telegram_id,
                        "⚠️ *Sessions Paused*\n\nYour tutor's account has been suspended.\n"
                        "An admin will assign a new tutor shortly.")
            from config.config import ADMIN_GROUP_CHAT_ID
            if ADMIN_GROUP_CHAT_ID and affected_students:
                await send(context.bot, ADMIN_GROUP_CHAT_ID,
                    f"⚠️ *Tutor Suspended*\n\n"
                    f"Tutor: *{name}* (`{tutor_id}`)\n"
                    f"Affected students: {len(affected_students)}\n"
                    f"Please reassign tutors.")
    action = "reactivated" if new_state else "suspended"
    await reply(update, f"{'✅' if new_state else '🚫'} *{name}* has been {action}.",
                reply_markup=_back(f"tut_detail_{tutor_id}"))
    await send(context.bot, telegram_id,
               "✅ Your account has been reactivated. Use /start." if new_state
               else "🚫 Your account has been suspended. Contact an admin.")


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          entity_type: str, entity_id: str):
    labels = {"stu": "student", "tut": "tutor", "adm": "admin"}
    label = labels.get(entity_type, "user")
    await reply(update,
        f"⚠️ *Are you sure?*\n\nThis will permanently delete this {label} and all their data.",
        reply_markup=_kb([
            [InlineKeyboardButton("🗑️ Yes, Delete", callback_data=f"do_delete_{entity_type}_{entity_id}"),
             InlineKeyboardButton("❌ Cancel", callback_data=f"{entity_type}_detail_{entity_id}")],
        ]))


async def do_delete_student(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: str):
    from repositories.user import UserRepository, StudentRepository
    from repositories.schedule import ScheduleRepository
    from models.schedule import Session as SM
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(student_id)
        if not user:
            await reply(update, "❌ Student not found.", reply_markup=_back("students_filter_all"))
            return
        name = user.full_name
        for s in ScheduleRepository(db).get_by_student(student_id):
            s.is_active = False
            for ses in db.query(SM).filter(SM.schedule_id == s.schedule_id,
                                            SM.scheduled_start > datetime.now()).all():
                ses.status = "cancelled"
        stu = StudentRepository(db).get(student_id)
        if stu: db.delete(stu)
        db.delete(user)
        db.commit()
    await reply(update, f"🗑️ *{name}* has been deleted.", reply_markup=_back("students_filter_all"))


async def do_delete_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE, tutor_id: str):
    from repositories.user import UserRepository, TutorRepository
    from repositories.schedule import ScheduleRepository
    from models.schedule import Session as SM
    with next(get_db()) as db:
        user = UserRepository(db).get_by_user_id(tutor_id)
        if not user:
            await reply(update, "❌ Tutor not found.", reply_markup=_back("tutors_filter_all"))
            return
        name, telegram_id = user.full_name, user.telegram_id
        affected = set()
        for s in ScheduleRepository(db).get_by_tutor(tutor_id):
            s.is_active = False
            affected.add(s.student_id)
            for ses in db.query(SM).filter(SM.schedule_id == s.schedule_id,
                                            SM.scheduled_start > datetime.now()).all():
                ses.status = "cancelled"
        tut = TutorRepository(db).get(tutor_id)
        if tut: db.delete(tut)
        db.delete(user)
        db.commit()
        for sid in affected:
            student = UserRepository(db).get_by_user_id(sid)
            if student:
                await send(context.bot, student.telegram_id,
                    "⚠️ Your tutor has been removed. An admin will assign a new one shortly.")
        from config.config import ADMIN_GROUP_CHAT_ID
        if ADMIN_GROUP_CHAT_ID and affected:
            await send(context.bot, ADMIN_GROUP_CHAT_ID,
                f"🗑️ *Tutor Deleted*\n\n*{name}*\nAffected students: {len(affected)}")
    await reply(update, f"🗑️ *{name}* deleted. {len(affected)} student(s) notified.",
                reply_markup=_back("tutors_filter_all"))


async def do_delete_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: str):
    from repositories.user import UserRepository
    from services.admin_service import AdminService
    with next(get_db()) as db:
        caller = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not caller or not caller.is_master_admin:
            await reply(update, "🚫 Only master admins can remove admins.")
            return
        user = UserRepository(db).get_by_user_id(admin_id)
        if not user:
            await reply(update, "❌ Admin not found.", reply_markup=_back("admins_filter_all"))
            return
        if user.is_master_admin:
            await reply(update, "🚫 Cannot delete a master admin.", reply_markup=_back(f"adm_detail_{admin_id}"))
            return
        name = user.full_name
        db.delete(user)
        db.commit()
    await reply(update, f"🗑️ Admin *{name}* removed.", reply_markup=_back("admins_filter_all"))


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATION HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def _cancel(update, context):
    context.user_data.clear()
    await reply(update, "❌ Cancelled.")
    return ConversationHandler.END


def assign_tutor_conv_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(assign_start, pattern=r"^do_assign_")],
        states={
            ASSIGN_SUBJECTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, assign_subjects)],
            ASSIGN_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, assign_days)],
            ASSIGN_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, assign_time)],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
        name="assign_tutor", per_message=False, persistent=False,
    )


def edit_student_conv_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_student_field, pattern=r"^edit_stu_")],
        states={EDIT_STU_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_student_value)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
        name="edit_student", per_message=False, persistent=False,
    )


def edit_tutor_conv_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_tutor_field, pattern=r"^edit_tut_")],
        states={EDIT_TUT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_tutor_value)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
        name="edit_tutor", per_message=False, persistent=False,
    )


def edit_admin_conv_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: _start_edit_adm(u, c), pattern=r"^edit_adm_")],
        states={EDIT_ADM_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_admin_value)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
        name="edit_admin", per_message=False, persistent=False,
    )


async def _start_edit_adm(update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("edit_adm_", "").split("_", 1)
    field, admin_id = parts[0], parts[1] if len(parts) > 1 else ""
    context.user_data["editing_admin"] = admin_id
    context.user_data["editing_adm_field"] = field
    await query.edit_message_text(
        f"✏️ Enter the new *{'full name' if field == 'name' else 'phone number'}*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back(f"adm_detail_{admin_id}"))
    return EDIT_ADM_VALUE


def add_admin_conv_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_admin_start, pattern=r"^add_admin_flow$")],
        states={
            ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_get_id)],
            ADD_ADMIN_CONFIRM: [CallbackQueryHandler(add_admin_confirm, pattern=r"^confirm_add_admin$")],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
        name="add_admin", per_message=False, persistent=False,
    )
