"""
Registration flows — fully overhauled.

Student flow (8 steps):
  terms → name → phone → grade → subjects → days/week → parent phone → confirm

Tutor flow (11 steps):
  terms → tutor_rules → name → phone → primary_subjects → secondary_subjects
  → max_days → payment_accounts → experience → documents → confirm
"""
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)
from telegram.constants import ParseMode
from config.db import get_db
from services.registration import RegistrationService
from data.terms import TERMS_TEXT, TUTOR_RULES_TEXT
from data.subjects import GRADE_LEVELS
from data.rates import get_rate_for_grade, calculate_monthly_payment
from ui.keyboards import tutor_hours_per_week_keyboard
from ui.subject_picker import (
    grade_picker_keyboard, subject_picker_keyboard,
    subject_picker_text, tutor_subject_picker_keyboard,
)
from utils.validators import validate_phone, validate_name
from utils.helpers import reply

logger = logging.getLogger(__name__)

PAYMENT_METHODS = ["Telebirr", "CBE Birr", "Commercial Bank of Ethiopia",
                   "Awash Bank", "Bank of Abyssinia"]

(
    STU_TERMS, STU_NAME, STU_PHONE, STU_GRADE,
    STU_SUBJECTS, STU_DAYS, STU_PARENT, STU_CONFIRM,
    TUT_TERMS, TUT_RULES, TUT_NAME, TUT_PHONE,
    TUT_PRIMARY_SUBJECTS, TUT_SECONDARY_SUBJECTS,
    TUT_MAX_DAYS, TUT_PAYMENT_METHODS, TUT_PAYMENT_ACCOUNTS,
    TUT_EXPERIENCE, TUT_DOCUMENTS, TUT_CONFIRM,
) = range(20)


def _kb(rows): return InlineKeyboardMarkup(rows)
def _back(cb="back"): return _kb([[InlineKeyboardButton("‹ Back", callback_data=cb)]])
def _back_cancel():
    return _kb([[
        InlineKeyboardButton("‹ Back", callback_data="back"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_registration"),
    ]])


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await reply(update, "❌ Registration cancelled.\n\nUse /start to begin again.")
    return ConversationHandler.END


async def check_channel_membership(bot, telegram_id: int) -> bool:
    from config.config import REQUIRED_CHANNEL
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, telegram_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return True


def channel_join_keyboard() -> InlineKeyboardMarkup:
    from config.config import REQUIRED_CHANNEL
    channel = REQUIRED_CHANNEL or "@EduConnectChannel"
    return _kb([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel.lstrip('@')}")],
        [InlineKeyboardButton("✅ I've Joined", callback_data="check_channel_join")],
    ])


async def _pre_registration_checks(update, context, role):
    """Returns True if user can proceed, False if blocked."""
    with next(get_db()) as db:
        from repositories.user import UserRepository
        from services.tutor_service import TutorService
        tid = update.effective_user.id
        if TutorService(db).is_telegram_id_blacklisted(tid):
            await reply(update,
                "🚫 *Your account has been permanently restricted.*",
                reply_markup=_back())
            return False
        if UserRepository(db).get_by_telegram_id(tid):
            await reply(update,
                "⚠️ You are already registered. Use /start.",
                reply_markup=_back())
            return False
    bot = update.get_bot() if hasattr(update, 'get_bot') else context.bot
    joined = await check_channel_membership(bot, update.effective_user.id)
    if not joined:
        await reply(update,
            "📢 *Join Our Channel First*\n\n"
            "You must join our official channel before registering.",
            reply_markup=channel_join_keyboard())
        return False
    return True


# ── Student Registration ──────────────────────────────────────────────────────

async def student_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _pre_registration_checks(update, context, "student"):
        return ConversationHandler.END
    context.user_data.clear()
    await reply(update,
        f"🎓 *Student Registration*\n\n"
        f"`○○○○○○○○`  Step 1 of 8\n\n{'─'*26}\n\n"
        f"📜 *Terms & Conditions*\n\n{TERMS_TEXT}\n\n{'─'*26}\n\n"
        f"Do you agree to these terms?",
        reply_markup=_kb([
            [InlineKeyboardButton("✅ I Agree", callback_data="stu_terms_agree"),
             InlineKeyboardButton("❌ I Disagree", callback_data="stu_terms_disagree")],
        ]))
    return STU_TERMS


async def stu_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if "disagree" in query.data:
        await query.edit_message_text(
            "❌ You must agree to the Terms to register.\n\nUse /start if you change your mind.",
            parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data["agreed_terms"] = True
    await query.edit_message_text(
        f"🎓 *Student Registration*\n\n`●○○○○○○○`  Step 2 of 8\n\n{'─'*26}\n\n"
        f"Please enter your *full name*:\n\n💡 _e.g. Adonay Tesfaye_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
    return STU_NAME


async def stu_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    valid, err = validate_name(name)
    if not valid:
        await update.message.reply_text(f"❌ {err}\n\nPlease enter your full name:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
        return STU_NAME
    context.user_data["full_name"] = name
    await update.message.reply_text(
        f"🎓 *Student Registration*\n\n`●●○○○○○○`  Step 3 of 8\n\n{'─'*26}\n\n"
        f"Please enter your *phone number*:\n\n💡 _e.g. 0912345678_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
    return STU_PHONE


async def stu_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    valid, err = validate_phone(phone)
    if not valid:
        await update.message.reply_text(f"❌ {err}\n\nPlease enter your phone number:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
        return STU_PHONE
    context.user_data["phone"] = phone
    await update.message.reply_text(
        f"🎓 *Student Registration*\n\n`●●●○○○○○`  Step 4 of 8\n\n{'─'*26}\n\n"
        f"Select your *grade or level*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=grade_picker_keyboard(back_cb="cancel_registration"))
    return STU_GRADE


async def stu_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    grade = query.data.replace("grade_pick_", "")
    context.user_data["grade"] = grade
    context.user_data["selected_subjects"] = []
    await query.edit_message_text(
        subject_picker_text(grade, [], purpose="learn", step=5, total=8),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=subject_picker_keyboard(grade, [], done_cb="stu_subjects_done", back_cb="back"))
    return STU_SUBJECTS


async def stu_subject_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subj = query.data.replace("subj_toggle_", "").replace("_", " ")
    selected = context.user_data.get("selected_subjects", [])
    if subj in selected:
        selected.remove(subj)
    else:
        selected.append(subj)
    context.user_data["selected_subjects"] = selected
    grade = context.user_data.get("grade", "")
    await query.edit_message_text(
        subject_picker_text(grade, selected, purpose="learn", step=5, total=8),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=subject_picker_keyboard(grade, selected, done_cb="stu_subjects_done", back_cb="back"))
    return STU_SUBJECTS


async def stu_subjects_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected = context.user_data.get("selected_subjects", [])
    if not selected:
        await query.answer("Please select at least one subject.", show_alert=True)
        return STU_SUBJECTS
    context.user_data["subjects"] = ", ".join(selected)
    await query.edit_message_text(
        f"🎓 *Student Registration*\n\n`●●●●●○○○`  Step 6 of 8\n\n{'─'*26}\n\n"
        f"How many days per week are you willing to study?\n\n_Minimum 3, maximum 5_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([
            [InlineKeyboardButton("3 days/week", callback_data="stu_days_3"),
             InlineKeyboardButton("4 days/week", callback_data="stu_days_4"),
             InlineKeyboardButton("5 days/week", callback_data="stu_days_5")],
            [InlineKeyboardButton("‹ Back", callback_data="back"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel_registration")],
        ]))
    return STU_DAYS


async def stu_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    days = int(query.data.replace("stu_days_", ""))
    context.user_data["days_per_week"] = days
    grade = context.user_data.get("grade", "")
    rate = get_rate_for_grade(grade)
    monthly = calculate_monthly_payment(grade, days)
    context.user_data["monthly_payment"] = monthly
    await query.edit_message_text(
        f"🎓 *Student Registration*\n\n`●●●●●●○○`  Step 7 of 8\n\n{'─'*26}\n\n"
        f"📅 Days/week: *{days}*\n"
        f"💵 Monthly payment: *{monthly:.0f} ETB*\n"
        f"_({rate} ETB/hr × {days} days × 4 weeks)_\n\n{'─'*26}\n\n"
        f"Please enter your *parent/guardian's phone number*:\n\n"
        f"💡 _This field is required_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
    return STU_PARENT


async def stu_parent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    valid, err = validate_phone(phone)
    if not valid:
        await update.message.reply_text(
            f"❌ {err}\n\nPlease enter the parent/guardian phone number:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
        return STU_PARENT
    context.user_data["parent_phone"] = phone
    d = context.user_data
    grade = d.get("grade", "—")
    monthly = d.get("monthly_payment", 0)
    summary = (
        f"🎓 *Registration Summary*\n\n`●●●●●●●○`  Step 8 of 8\n\n{'─'*26}\n\n"
        f"👤 Name: *{d.get('full_name')}*\n"
        f"📱 Phone: {d.get('phone')}\n"
        f"🎓 Grade: {grade}\n"
        f"📚 Subjects: {d.get('subjects')}\n"
        f"📅 Days/week: {d.get('days_per_week')}\n"
        f"👪 Parent phone: {phone}\n"
        f"💵 Monthly payment: *{monthly:.0f} ETB*\n\n{'─'*26}\n\n"
        f"Is everything correct?"
    )
    await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([
            [InlineKeyboardButton("✅ Confirm & Register", callback_data="stu_confirm")],
            [InlineKeyboardButton("✏️ Start Over", callback_data="register_student"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel_registration")],
        ]))
    return STU_CONFIRM


async def stu_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data
    with next(get_db()) as db:
        result = RegistrationService(db).register_student(
            telegram_id=update.effective_user.id,
            full_name=d["full_name"], phone=d["phone"],
            grade=d.get("grade"), parent_phone=d.get("parent_phone"),
            subjects=d.get("subjects"), days_per_week=d.get("days_per_week", 3),
        )
    if not result["success"]:
        await query.edit_message_text(f"❌ {result['message']}")
        return ConversationHandler.END
    from ui.templates import reg_complete_student
    await query.edit_message_text(
        reg_complete_student(result["full_name"], result["user_id"]),
        parse_mode=ParseMode.MARKDOWN)
    bot = query.message.get_bot()
    from config.config import ADMIN_GROUP_CHAT_ID
    if ADMIN_GROUP_CHAT_ID:
        try:
            await bot.send_message(chat_id=ADMIN_GROUP_CHAT_ID,
                text=f"🎓 *New Student*\n\nName: {result['full_name']}\n"
                     f"ID: `{result['user_id']}`\nGrade: {d.get('grade')}\n"
                     f"Subjects: {d.get('subjects')}",
                parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
    context.user_data.clear()
    from handlers.dashboards import show_student_dashboard
    await show_student_dashboard(update, context)
    return ConversationHandler.END


# ── Tutor Registration ────────────────────────────────────────────────────────

async def tutor_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _pre_registration_checks(update, context, "tutor"):
        return ConversationHandler.END
    context.user_data.clear()
    await reply(update,
        f"👨‍🏫 *Tutor Registration*\n\n`○○○○○○○○○○○`  Step 1 of 11\n\n{'─'*26}\n\n"
        f"📜 *Terms & Conditions*\n\n{TERMS_TEXT}\n\n{'─'*26}\n\n"
        f"Do you agree to these terms?",
        reply_markup=_kb([
            [InlineKeyboardButton("✅ I Agree", callback_data="tut_terms_agree"),
             InlineKeyboardButton("❌ I Disagree", callback_data="tut_terms_disagree")],
        ]))
    return TUT_TERMS


async def tut_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if "disagree" in query.data:
        await query.edit_message_text("❌ You must agree to the Terms to register.",
            parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data["agreed_terms"] = True
    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●○○○○○○○○○○`  Step 2 of 11\n\n{'─'*26}\n\n"
        f"📋 *Tutor Rules & Regulations*\n\n{TUTOR_RULES_TEXT}\n\n{'─'*26}\n\n"
        f"Do you agree to these rules?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([
            [InlineKeyboardButton("✅ I Agree", callback_data="tut_rules_agree"),
             InlineKeyboardButton("❌ I Disagree", callback_data="tut_rules_disagree")],
        ]))
    return TUT_RULES


async def tut_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if "disagree" in query.data:
        await query.edit_message_text("❌ You must agree to the Tutor Rules to register.",
            parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data["agreed_rules"] = True
    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●○○○○○○○○○`  Step 3 of 11\n\n{'─'*26}\n\n"
        f"Please enter your *full name*:\n\n💡 _e.g. Bereket Alemu_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
    return TUT_NAME


async def tut_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    valid, err = validate_name(name)
    if not valid:
        await update.message.reply_text(f"❌ {err}", parse_mode=ParseMode.MARKDOWN,
            reply_markup=_back_cancel())
        return TUT_NAME
    context.user_data["full_name"] = name
    await update.message.reply_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●○○○○○○○○`  Step 4 of 11\n\n{'─'*26}\n\n"
        f"Please enter your *phone number*:\n\n💡 _e.g. 0911234567_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
    return TUT_PHONE


async def tut_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    valid, err = validate_phone(phone)
    if not valid:
        await update.message.reply_text(f"❌ {err}", parse_mode=ParseMode.MARKDOWN,
            reply_markup=_back_cancel())
        return TUT_PHONE
    context.user_data["phone"] = phone
    context.user_data["primary_subjects"] = []
    await update.message.reply_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●○○○○○○○`  Step 5 of 11\n\n{'─'*26}\n\n"
        f"📚 *Select PRIMARY subjects to teach*\n\n"
        f"_These are subjects you are most confident teaching_\n\n"
        f"_Tap subjects to select, then tap Done_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=tutor_subject_picker_keyboard([], done_cb="tut_primary_done", back_cb="back"))
    return TUT_PRIMARY_SUBJECTS


async def tut_primary_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subj = query.data.replace("subj_toggle_", "").replace("_", " ")
    selected = context.user_data.get("primary_subjects", [])
    if subj in selected:
        selected.remove(subj)
    else:
        selected.append(subj)
    context.user_data["primary_subjects"] = selected
    sel_text = "✅ " + ", ".join(selected) if selected else "_Tap subjects to select_"
    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●○○○○○○○`  Step 5 of 11\n\n"
        f"📚 *PRIMARY subjects*\n\n{sel_text}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=tutor_subject_picker_keyboard(selected, done_cb="tut_primary_done", back_cb="back"))
    return TUT_PRIMARY_SUBJECTS


async def tut_primary_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not context.user_data.get("primary_subjects"):
        await query.answer("Please select at least one primary subject.", show_alert=True)
        return TUT_PRIMARY_SUBJECTS
    context.user_data["secondary_subjects"] = []
    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●●○○○○○○`  Step 6 of 11\n\n{'─'*26}\n\n"
        f"📚 *Select SECONDARY subjects* _(optional)_\n\n"
        f"_Tap Done to skip_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=tutor_subject_picker_keyboard([], done_cb="tut_secondary_done", back_cb="back"))
    return TUT_SECONDARY_SUBJECTS


async def tut_secondary_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subj = query.data.replace("subj_toggle_", "").replace("_", " ")
    primary = context.user_data.get("primary_subjects", [])
    if subj in primary:
        await query.answer(f"{subj} is already a primary subject.", show_alert=True)
        return TUT_SECONDARY_SUBJECTS
    selected = context.user_data.get("secondary_subjects", [])
    if subj in selected:
        selected.remove(subj)
    else:
        selected.append(subj)
    context.user_data["secondary_subjects"] = selected
    sel_text = "✅ " + ", ".join(selected) if selected else "_None selected_"
    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●●○○○○○○`  Step 6 of 11\n\n"
        f"📚 *SECONDARY subjects*\n\n{sel_text}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=tutor_subject_picker_keyboard(selected, done_cb="tut_secondary_done", back_cb="back"))
    return TUT_SECONDARY_SUBJECTS


async def tut_secondary_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●●●○○○○○`  Step 7 of 11\n\n{'─'*26}\n\n"
        f"How many *hours per week* can you teach?\n\n"
f"_Each session is 1 hour. You can teach multiple students per day._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=tutor_hours_per_week_keyboard())
    return TUT_MAX_DAYS


async def tut_max_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hours = int(query.data.replace("tut_maxhours_", ""))
    context.user_data["max_teaching_hours"] = hours
    context.user_data["selected_payment_methods"] = []

    rows = []
    row = []
    for method in PAYMENT_METHODS:
        row.append(InlineKeyboardButton(method, callback_data=f"paymethod_{method.replace(' ', '_')}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✅ Done", callback_data="tut_paymethods_done")])
    rows.append([InlineKeyboardButton("‹ Back", callback_data="back"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel_registration")])

    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●●●●○○○○`  Step 8 of 11\n\n{'─'*26}\n\n"
        f"💳 *Select your preferred payment accounts*\n\n_Select one or more_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(rows))
    return TUT_PAYMENT_METHODS


async def tut_payment_method_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("paymethod_", "").replace("_", " ")
    selected = context.user_data.get("selected_payment_methods", [])
    if method in selected:
        selected.remove(method)
    else:
        selected.append(method)
    context.user_data["selected_payment_methods"] = selected

    rows = []
    row = []
    for m in PAYMENT_METHODS:
        prefix = "✅ " if m in selected else ""
        row.append(InlineKeyboardButton(f"{prefix}{m}",
            callback_data=f"paymethod_{m.replace(' ', '_')}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    count = len(selected)
    rows.append([InlineKeyboardButton(
        f"✅ Done ({count})" if count else "✅ Done",
        callback_data="tut_paymethods_done")])
    rows.append([InlineKeyboardButton("‹ Back", callback_data="back"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel_registration")])

    sel_text = "✅ " + ", ".join(selected) if selected else "_Tap to select_"
    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●●●●○○○○`  Step 8 of 11\n\n"
        f"💳 *Payment accounts*\n\n{sel_text}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(rows))
    return TUT_PAYMENT_METHODS


async def tut_paymethods_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected = context.user_data.get("selected_payment_methods", [])
    if not selected:
        await query.answer("Please select at least one payment method.", show_alert=True)
        return TUT_PAYMENT_METHODS
    context.user_data["payment_accounts_filled"] = {}
    context.user_data["payment_account_queue"] = list(selected)
    first = selected[0]
    await query.edit_message_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●●●●●○○○`  Step 9 of 11\n\n{'─'*26}\n\n"
        f"💳 Enter your *{first}* account number:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
    return TUT_PAYMENT_ACCOUNTS


async def tut_payment_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.validators import validate_account_number
    number = update.message.text.strip()
    valid, err = validate_account_number(number)
    queue = context.user_data.get("payment_account_queue", [])
    if not valid:
        current = queue[0] if queue else "account"
        await update.message.reply_text(f"❌ {err}\n\nEnter your {current} account number:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
        return TUT_PAYMENT_ACCOUNTS
    filled = context.user_data.get("payment_accounts_filled", {})
    current = queue.pop(0)
    filled[current] = number
    context.user_data["payment_account_queue"] = queue
    context.user_data["payment_accounts_filled"] = filled
    if queue:
        await update.message.reply_text(
            f"✅ {current} saved.\n\nEnter your *{queue[0]}* account number:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
        return TUT_PAYMENT_ACCOUNTS
    context.user_data["payment_accounts"] = json.dumps(filled)
    await update.message.reply_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●●●●●●○○`  Step 10 of 11\n\n{'─'*26}\n\n"
        f"📝 Briefly describe your *teaching experience*:\n\n"
        f"💡 _e.g. BSc Mathematics, 3 years experience_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=_back_cancel())
    return TUT_EXPERIENCE


async def tut_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["experience"] = update.message.text.strip()
    context.user_data["doc_file_ids"] = []
    await update.message.reply_text(
        f"👨‍🏫 *Tutor Registration*\n\n`●●●●●●●●●●○`  Step 11 of 11\n\n{'─'*26}\n\n"
        f"📄 *Upload your documents*\n\n"
        f"Send the following as PDF files or photos:\n"
        f"  • CV / Resume\n"
        f"  • Academic Transcripts\n"
        f"  • Entrance exam results _(if applicable)_\n"
        f"  • National ID photo\n\n"
        f"_Send files one by one, then tap Done._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([
            [InlineKeyboardButton("✅ Done — Submit Application", callback_data="tut_docs_done")],
            [InlineKeyboardButton("‹ Back", callback_data="back"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel_registration")],
        ]))
    return TUT_DOCUMENTS


async def tut_document_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_ids = context.user_data.get("doc_file_ids", [])
    if update.message.document:
        file_ids.append(("document", update.message.document.file_id,
                         update.message.document.file_name or "document"))
    elif update.message.photo:
        file_ids.append(("photo", update.message.photo[-1].file_id, "ID photo"))
    context.user_data["doc_file_ids"] = file_ids
    await update.message.reply_text(
        f"✅ *File {len(file_ids)} received.*\n\nSend more or tap Done.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([
            [InlineKeyboardButton("✅ Done — Submit Application", callback_data="tut_docs_done")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_registration")],
        ]))
    return TUT_DOCUMENTS


async def tut_docs_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    file_ids = context.user_data.get("doc_file_ids", [])
    if not file_ids:
        await query.answer("Please upload at least one document first.", show_alert=True)
        return TUT_DOCUMENTS
    d = context.user_data
    primary = d.get("primary_subjects", [])
    secondary = d.get("secondary_subjects", [])
    with next(get_db()) as db:
        result = RegistrationService(db).register_tutor(
            telegram_id=update.effective_user.id,
            full_name=d["full_name"], phone=d["phone"],
            primary_subjects=", ".join(primary),
            secondary_subjects=", ".join(secondary),
            experience=d.get("experience", ""),
            max_teaching_hours=d.get("max_teaching_hours", 3),
            payment_accounts=d.get("payment_accounts", "{}"),
            doc_file_ids=json.dumps(file_ids),
        )
    if not result["success"]:
        await query.edit_message_text(f"❌ {result['message']}")
        return ConversationHandler.END
    from ui.templates import reg_complete_tutor
    await query.edit_message_text(
        reg_complete_tutor(result["full_name"], result["user_id"]),
        parse_mode=ParseMode.MARKDOWN)
    bot = query.message.get_bot()
    from config.config import ADMIN_GROUP_CHAT_ID
    if ADMIN_GROUP_CHAT_ID:
        try:
            claim_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "📋 Review Application",
                    callback_data=f"tut_detail_{result['user_id']}")
            ]])
            await bot.send_message(chat_id=ADMIN_GROUP_CHAT_ID,
                text=f"👨‍🏫 *New Tutor Application*\n\n"
                     f"Name: *{result['full_name']}*\nID: `{result['user_id']}`\n"
                     f"Primary: {', '.join(primary)}\n"
                     f"Secondary: {', '.join(secondary) or 'None'}\n"
                     f"Max hours/week: {d.get('max_teaching_hours', 3)}\n\n"
                     f"Documents below ↓ — Review and tap Claim to approve or reject.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=claim_kb)
            for ftype, fid, fname in file_ids:
                try:
                    if ftype == "document":
                        await bot.send_document(chat_id=ADMIN_GROUP_CHAT_ID, document=fid,
                            caption=f"{fname} — {result['full_name']}")
                    else:
                        await bot.send_photo(chat_id=ADMIN_GROUP_CHAT_ID, photo=fid,
                            caption=f"ID Photo — {result['full_name']}")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to notify admin group: {e}")
    context.user_data.clear()
    return ConversationHandler.END


async def _timeout_callback(update, context):
    context.user_data.clear()
    try:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="⏱ *Registration timed out.*\n\nUse /start to try again.",
            parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


def student_conv_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("register_student", student_start),
            CallbackQueryHandler(student_start, pattern="^register_student$"),
        ],
        states={
            STU_TERMS: [CallbackQueryHandler(stu_terms, pattern="^stu_terms_")],
            STU_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, stu_name)],
            STU_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, stu_phone)],
            STU_GRADE: [CallbackQueryHandler(stu_grade, pattern="^grade_pick_")],
            STU_SUBJECTS: [
                CallbackQueryHandler(stu_subject_toggle, pattern="^subj_toggle_"),
                CallbackQueryHandler(stu_subjects_done, pattern="^stu_subjects_done$"),
            ],
            STU_DAYS: [CallbackQueryHandler(stu_days, pattern="^stu_days_")],
            STU_PARENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, stu_parent)],
            STU_CONFIRM: [CallbackQueryHandler(stu_confirm, pattern="^stu_confirm$")],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, _timeout_callback),
                CallbackQueryHandler(_timeout_callback),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern="^back$"),
            CallbackQueryHandler(_cancel, pattern="^cancel_registration$"),
        ],
        name="student_registration",
        per_message=False, persistent=False, conversation_timeout=300,
    )


def tutor_conv_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("register_tutor", tutor_start),
            CallbackQueryHandler(tutor_start, pattern="^register_tutor$"),
        ],
        states={
            TUT_TERMS: [CallbackQueryHandler(tut_terms, pattern="^tut_terms_")],
            TUT_RULES: [CallbackQueryHandler(tut_rules, pattern="^tut_rules_")],
            TUT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, tut_name)],
            TUT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tut_phone)],
            TUT_PRIMARY_SUBJECTS: [
                CallbackQueryHandler(tut_primary_toggle, pattern="^subj_toggle_"),
                CallbackQueryHandler(tut_primary_done, pattern="^tut_primary_done$"),
            ],
            TUT_SECONDARY_SUBJECTS: [
                CallbackQueryHandler(tut_secondary_toggle, pattern="^subj_toggle_"),
                CallbackQueryHandler(tut_secondary_done, pattern="^tut_secondary_done$"),
            ],
            TUT_MAX_DAYS: [CallbackQueryHandler(tut_max_days, pattern="^tut_maxhours_")],
            TUT_PAYMENT_METHODS: [
                CallbackQueryHandler(tut_payment_method_toggle, pattern="^paymethod_"),
                CallbackQueryHandler(tut_paymethods_done, pattern="^tut_paymethods_done$"),
            ],
            TUT_PAYMENT_ACCOUNTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tut_payment_account)],
            TUT_EXPERIENCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tut_experience)],
            TUT_DOCUMENTS: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, tut_document_received),
                CallbackQueryHandler(tut_docs_done, pattern="^tut_docs_done$"),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, _timeout_callback),
                CallbackQueryHandler(_timeout_callback),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern="^back$"),
            CallbackQueryHandler(_cancel, pattern="^cancel_registration$"),
        ],
        name="tutor_registration",
        per_message=False, persistent=False, conversation_timeout=600,
    )
