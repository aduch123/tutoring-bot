"""Payment page UI — account numbers and instructions."""

# ── Placeholder account numbers ───────────────────────────────────────────────
# Replace these with your real account details before going live

PAYMENT_ACCOUNTS = {
    "telebirr": {
        "name": "Telebirr",
        "emoji": "📱",
        "number": "0968884489",
        "account_name": "Yeabneh Tagesse",
    },
    "cbe_bank": {
        "name": "Commercial Bank of Ethiopia",
        "emoji": "🏛️",
        "number": "1000776720899",
        "account_name": "Yeabneh Tagesse",
    },
    "awash_bank": {
        "name": "Awash Bank",
        "emoji": "🏦",
        "number": "013201300940300",
        "account_name": "Yeabneh Tagesse",
    },
}

def payment_page(amount: float, month: str, student_name: str) -> str:
    lines = [
        f"💳 *Payment Required*\n",
        f"Hello *{student_name.split()[0]}*, please complete your payment to access tutoring.\n",
        f"━━━━━━━━━━━━━━━━━━━━━━\n",
        f"💵 *Amount:* {amount:.0f} ETB\n"
        f"📅 *For:* {month}\n",
        f"━━━━━━━━━━━━━━━━━━━━━━\n",
        f"*Payment Options:*\n",
    ]
    for acc in PAYMENT_ACCOUNTS.values():
        lines.append(
            f"\n{acc['emoji']} *{acc['name']}*\n"
            f"  Number: `{acc['number']}`\n"
            f"  Name: {acc['account_name']}"
        )
    lines.append(
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📸 *After paying:*\n"
        f"Take a screenshot of your payment confirmation and send it here.\n\n"
        f"⏳ An admin will verify and activate your account within a few hours."
    )
    return "\n".join(lines)

def locked_dashboard(student_name: str, has_pending_screenshot: bool,
                     is_first_payment: bool = False) -> str:
    first_name = student_name.split()[0]
    if has_pending_screenshot:
        return (
            f"⏳ *Payment Under Review*\n\n"
            f"Hi {first_name}, your payment screenshot has been received.\n\n"
            f"An admin is reviewing it. You'll be notified once confirmed.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"If you haven't paid yet, tap *Pay Now* to see payment details."
        )
    if is_first_payment:
        return (
            f"🔒 *Account Not Yet Active*\n\n"
            f"Hi {first_name}, welcome to Akew Tutor!\n\n"
            f"To access tutoring sessions, please complete your first payment.\n\n"
            f"Tap *💳 Pay Now* below to see payment instructions."
        )
    return (
        f"🔒 *Account Suspended*\n\n"
        f"Hi {first_name}, your monthly payment is overdue.\n\n"
        f"Your sessions have been paused until payment is confirmed.\n\n"
        f"Tap *💳 Pay Now* below to complete your payment and resume sessions."
    )
