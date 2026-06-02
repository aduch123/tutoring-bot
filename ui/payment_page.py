"""Payment page UI — account numbers and instructions."""

# ── Placeholder account numbers ───────────────────────────────────────────────
# Replace these with your real account details before going live

PAYMENT_ACCOUNTS = {
    "telebirr": {
        "name": "Telebirr",
        "emoji": "📱",
        "number": "0912 345 678",
        "account_name": "EduConnect Tutoring",
    },
    "cbe_birr": {
        "name": "CBE Birr",
        "emoji": "🏦",
        "number": "1000123456789",
        "account_name": "EduConnect Tutoring",
    },
    "cbe_bank": {
        "name": "Commercial Bank of Ethiopia",
        "emoji": "🏛️",
        "number": "1000456789012",
        "account_name": "EduConnect Tutoring PLC",
    },
    "awash_bank": {
        "name": "Awash Bank",
        "emoji": "🏦",
        "number": "01320123456789",
        "account_name": "EduConnect Tutoring PLC",
    },
    "abyssinia_bank": {
        "name": "Bank of Abyssinia",
        "emoji": "🏦",
        "number": "68901234567",
        "account_name": "EduConnect Tutoring PLC",
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


def locked_dashboard(student_name: str, has_pending_screenshot: bool) -> str:
    if has_pending_screenshot:
        return (
            f"⏳ *Payment Under Review*\n\n"
            f"Hi {student_name.split()[0]}, your payment screenshot has been received.\n\n"
            f"An admin is reviewing it. You'll be notified once confirmed.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"If you haven't paid yet, tap *Pay Now* to see payment details."
        )
    return (
        f"🔒 *Account Not Yet Active*\n\n"
        f"Hi {student_name.split()[0]}, welcome to EduConnect!\n\n"
        f"To access tutoring sessions, please complete your first payment.\n\n"
        f"Tap *💳 Pay Now* below to see payment instructions."
    )
