"""
Zoom link submission flow — fully button/text driven, no commands.
When bot requests a zoom link from tutor, it sets context.
Tutor pastes link as plain text → bot validates → sends to student.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config.db import get_db
from utils.helpers import reply, send
from utils.validators import validate_zoom_link

logger = logging.getLogger(__name__)


async def handle_zoom_link_text(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Called from smart_message_handler.
    Returns True if message was a zoom link submission, False otherwise.
    """
    if not context.user_data.get("awaiting_zoom_link"):
        return False

    session_id = context.user_data.get("zoom_session_id")
    if not session_id:
        return False

    link = update.message.text.strip()
    valid, err = validate_zoom_link(link)

    if not valid:
        await update.message.reply_text(
            f"❌ {err}\n\nPlease paste your Zoom link:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✕ Cancel", callback_data="cancel_zoom")
            ]]))
        return True

    # Show preview and ask for confirmation
    context.user_data["zoom_link_pending"] = link
    await update.message.reply_text(
        f"🔗 *Zoom Link Preview*\n\n"
        f"Session: `{session_id}`\n"
        f"Link: {link}\n\n"
        f"Submit this link?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Submit",
                                   callback_data=f"zoom_confirm_{session_id}"),
             InlineKeyboardButton("✏️ Re-enter",
                                   callback_data=f"zoom_retry_{session_id}")],
        ]))
    return True


async def handle_zoom_confirm(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Admin confirms zoom link — saves and sends to student."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("zoom_confirm_", "")
    link = context.user_data.get("zoom_link_pending")

    if not link:
        await query.edit_message_text("❌ No link found. Please try again.")
        context.user_data.pop("awaiting_zoom_link", None)
        context.user_data.pop("zoom_session_id", None)
        return

    with next(get_db()) as db:
        from services.schedule_service import ScheduleService
        result = ScheduleService(db).submit_zoom_link(
            tutor_telegram_id=update.effective_user.id,
            session_id=session_id,
            link=link,
        )

    if not result["success"]:
        await query.edit_message_text(f"❌ {result['message']}")
        return

    await query.edit_message_text(
        f"✅ *Zoom link submitted!*\n\n"
        f"Session: `{session_id}`\n"
        f"The student has been notified with the link.",
        parse_mode=ParseMode.MARKDOWN)

    # Notify student
    if result.get("student_telegram_id"):
        await send(
            query.message.get_bot(),
            result["student_telegram_id"],
            f"🔗 *Zoom Link Ready*\n\n"
            f"Your session is confirmed!\n\n"
            f"📚 Subject: {result['subject']}\n"
            f"🕐 Time: {result['start']}\n"
            f"🔗 [Join Zoom]({link})\n\n"
            f"See you there! 🎓")

    # Clear context
    context.user_data.pop("awaiting_zoom_link", None)
    context.user_data.pop("zoom_session_id", None)
    context.user_data.pop("zoom_link_pending", None)


async def handle_zoom_retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tutor wants to re-enter the zoom link."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("zoom_retry_", "")
    context.user_data["zoom_link_pending"] = None
    context.user_data["awaiting_zoom_link"] = True
    context.user_data["zoom_session_id"] = session_id
    await query.edit_message_text(
        f"🔗 *Submit Zoom Link*\n\n"
        f"Session: `{session_id}`\n\n"
        f"Please paste your Zoom meeting link:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✕ Cancel", callback_data="cancel_zoom")
        ]]))


async def handle_zoom_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel zoom link submission."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("awaiting_zoom_link", None)
    context.user_data.pop("zoom_session_id", None)
    context.user_data.pop("zoom_link_pending", None)
    await query.edit_message_text(
        "❌ Zoom link submission cancelled.\n\n"
        "You can submit it later from your Sessions screen.")
