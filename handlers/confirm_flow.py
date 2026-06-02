"""
Session confirmation flow — fully button driven.
No /confirm command needed.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters,
)
from telegram.constants import ParseMode
from config.db import get_db
from utils.helpers import reply

logger = logging.getLogger(__name__)

ASK_SESSION_ID = 0


async def confirm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: user taps Confirm Session button."""
    from repositories.user import UserRepository
    from models.schedule import Session as SM
    from datetime import datetime

    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        if not user:
            await reply(update, "❌ User not found.")
            return ConversationHandler.END

        # Show sessions that need confirmation
        now = datetime.now()
        rows = (
            db.query(SM)
            .filter(
                (SM.tutor_id == user.user_id) | (SM.student_id == user.user_id),
                SM.status.in_(["in_progress", "zoom_ready", "scheduled"]),
                SM.scheduled_start <= now,
            )
            .order_by(SM.scheduled_start.desc())
            .limit(5)
            .all()
        )

        if not rows:
            await reply(update,
                "✅ *No sessions pending confirmation.*\n\n"
                "Sessions appear here after they start.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("‹ Back", callback_data="back")
                ]]))
            return ConversationHandler.END

        kb_rows = []
        for s in rows:
            already = (s.tutor_confirmed if user.user_id == s.tutor_id
                       else s.student_confirmed)
            if not already:
                label = f"✅ {s.subject} · {s.scheduled_start.strftime('%d %b %H:%M')}"
                kb_rows.append([InlineKeyboardButton(
                    label, callback_data=f"do_confirm_{s.session_id}")])

        if not kb_rows:
            await reply(update,
                "✅ *All sessions already confirmed.*",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("‹ Back", callback_data="back")
                ]]))
            return ConversationHandler.END

        kb_rows.append([InlineKeyboardButton("‹ Back", callback_data="back")])
        await reply(update,
            "✅ *Confirm Session Attendance*\n\n"
            "Select the session to confirm:",
            reply_markup=InlineKeyboardMarkup(kb_rows))

    return ConversationHandler.END


def confirm_conv_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(confirm_start, pattern="^confirm_session$"),
        ],
        states={},
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern="^back$"),
        ],
        name="confirm_session",
        per_message=False, persistent=False,
    )
