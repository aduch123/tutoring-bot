from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def kb(rows): return InlineKeyboardMarkup(rows)
def back(cb="back"): return kb([[InlineKeyboardButton("‹ Back", callback_data=cb)]])
def back_row(cb="back"): return [InlineKeyboardButton("‹ Back", callback_data=cb)]
def back_cancel(back_cb="back"):
    return kb([[InlineKeyboardButton("‹ Back", callback_data=back_cb),
                InlineKeyboardButton("✕ Cancel", callback_data="cancel_registration")]])

# ── Unregistered ──────────────────────────────────────────────────────────────

def unregistered_menu():
    return kb([
        [InlineKeyboardButton("📚 Student", callback_data="register_student"),
         InlineKeyboardButton("👨‍🏫 Tutor", callback_data="register_tutor")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

# ── Reply keyboards ───────────────────────────────────────────────────────────

def student_reply_keyboard():
    return ReplyKeyboardMarkup([
        ["📅 Sessions", "📆 Schedule"],
        ["💳 Payments", "👤 Profile"],
        ["📝 Report", "🚨 Emergency"],
        ["❓ Help"],
    ], resize_keyboard=True, is_persistent=True)


def tutor_reply_keyboard():
    return ReplyKeyboardMarkup([
        ["📅 Sessions", "📆 Schedule"],
        ["💰 Earnings", "👤 Profile"],
        ["📹 Recording", "✅ Confirm"],
        ["📝 Report", "🚨 Emergency"],
        ["❓ Help"],
    ], resize_keyboard=True, is_persistent=True)


def admin_reply_keyboard():
    return ReplyKeyboardMarkup([
        ["👥 Students", "👨‍🏫 Tutors"],
        ["👑 Admins", "💰 Finance"],
        ["🚨 Emergencies", "⚠️ Issues"],
        ["📊 Overview", "❓ Help"],
    ], resize_keyboard=True, is_persistent=True)


def remove_reply_keyboard():
    return ReplyKeyboardRemove()

# ── Student locked ────────────────────────────────────────────────────────────

def student_locked_menu():
    return kb([
        [InlineKeyboardButton("💳 Pay Now", callback_data="show_payment_page")],
        [InlineKeyboardButton("📸 Upload Screenshot", callback_data="upload_payment_proof")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

# ── Admin — users ─────────────────────────────────────────────────────────────

def admin_students_filter():
    return kb([
        [InlineKeyboardButton("All", callback_data="students_filter_all"),
         InlineKeyboardButton("Unpaid", callback_data="students_filter_unpaid"),
         InlineKeyboardButton("No Tutor", callback_data="students_filter_no_tutor")],
        back_row("admin_home"),
    ])


def admin_tutors_filter():
    return kb([
        [InlineKeyboardButton("All", callback_data="tutors_filter_all"),
         InlineKeyboardButton("Pending", callback_data="tutors_filter_pending"),
         InlineKeyboardButton("Suspended", callback_data="tutors_filter_suspended")],
        back_row("admin_home"),
    ])


def admin_admins_menu():
    return kb([
        [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin_flow")],
        [InlineKeyboardButton("📋 View All", callback_data="admins_filter_all")],
        back_row("admin_home"),
    ])

# ── Admin — finance ───────────────────────────────────────────────────────────

def admin_finance_menu():
    return kb([
        [InlineKeyboardButton("🧾 Invoices", callback_data="finance_invoices"),
         InlineKeyboardButton("💸 Payouts", callback_data="finance_payouts")],
        [InlineKeyboardButton("📊 Set Rate", callback_data="set_student_rate")],
        back_row("admin_home"),
    ])


def admin_invoices_filter():
    return kb([
        [InlineKeyboardButton("All", callback_data="invoices_filter_all"),
         InlineKeyboardButton("Unpaid", callback_data="invoices_filter_unpaid"),
         InlineKeyboardButton("Review", callback_data="invoices_filter_screenshot"),
         InlineKeyboardButton("Paid", callback_data="invoices_filter_paid")],
        back_row("admin_finance"),
    ])


def admin_payouts_filter():
    return kb([
        [InlineKeyboardButton("All", callback_data="payouts_filter_all"),
         InlineKeyboardButton("Pending", callback_data="payouts_filter_pending"),
         InlineKeyboardButton("Paid", callback_data="payouts_filter_paid")],
        [InlineKeyboardButton("💸 Generate Month", callback_data="generate_payouts_now")],
        back_row("admin_finance"),
    ])


def invoice_actions(transaction_id: str):
    return kb([
        [InlineKeyboardButton("✅ Confirm", callback_data=f"approve_payment_{transaction_id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"reject_payment_{transaction_id}")],
        [InlineKeyboardButton("🗑 Delete", callback_data=f"delete_invoice_{transaction_id}")],
        back_row("finance_invoices"),
    ])


def payout_actions(tutor_id: str, month_str: str):
    return kb([
        [InlineKeyboardButton("✅ Mark Paid",
                               callback_data=f"mark_payout_{tutor_id}_{month_str}")],
        back_row("finance_payouts"),
    ])

# ── Claim buttons ─────────────────────────────────────────────────────────────

def claim_payment_button(transaction_id: str):
    return kb([[InlineKeyboardButton(
        "✅ Claim & Review", callback_data=f"claim_payment_{transaction_id}")]])


def claim_emergency_button(emergency_id: str):
    return kb([[InlineKeyboardButton(
        "🚨 Claim & Handle", callback_data=f"claim_emergency_{emergency_id}")]])


def claim_report_button(emergency_id: str):
    return kb([[InlineKeyboardButton(
        "📝 Claim & Handle", callback_data=f"claim_emergency_{emergency_id}")]])

# ── Emergency type ────────────────────────────────────────────────────────────

def emergency_type_menu():
    return kb([
        [InlineKeyboardButton("🌐 Connection", callback_data="emg_internet"),
         InlineKeyboardButton("🚫 No-Show", callback_data="emg_no_show")],
        [InlineKeyboardButton("💻 Technical", callback_data="emg_technical"),
         InlineKeyboardButton("💰 Payment", callback_data="emg_payment")],
        [InlineKeyboardButton("⚠️ Behaviour", callback_data="emg_behaviour"),
         InlineKeyboardButton("❓ Other", callback_data="emg_other")],
        back_row(),
    ])

# ── Confirm session inline ────────────────────────────────────────────────────

def confirm_session_inline(session_id: str):
    return kb([
        [InlineKeyboardButton(f"✅ Confirm", callback_data=f"do_confirm_{session_id}")],
        back_row(),
    ])

# ── Tutor hours per week ──────────────────────────────────────────────────────

def tutor_hours_per_week_keyboard():
    """Hour options for tutor weekly capacity."""
    hours = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    rows = []
    row = []
    for h in hours:
        row.append(InlineKeyboardButton(f"{h}h", callback_data=f"tut_maxhours_{h}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("‹ Back", callback_data="back"),
                 InlineKeyboardButton("✕ Cancel", callback_data="cancel_registration")])
    return kb(rows)

# ── Zoom link flow ────────────────────────────────────────────────────────────

def zoom_submitted_actions(session_id: str):
    return kb([
        [InlineKeyboardButton("✅ Submit This Link", callback_data=f"zoom_confirm_{session_id}"),
         InlineKeyboardButton("✏️ Re-enter", callback_data=f"zoom_retry_{session_id}")],
    ])
