import logging, traceback
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def handle_errors(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Error in {func.__name__}: {e}\n{tb}")
            msg = (
                "⚠️ *Something went wrong.*\n\n"
                "The issue has been logged. Please try again or contact an admin."
            )
            try:
                if update.callback_query:
                    await update.callback_query.answer("An error occurred.", show_alert=True)
                    await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
                elif update.message:
                    await update.message.reply_text(msg, parse_mode="Markdown")
            except Exception:
                pass

            from config.config import ADMIN_GROUP_CHAT_ID
            if ADMIN_GROUP_CHAT_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_GROUP_CHAT_ID,
                        text=f"🤖 *Bot Error*\n\n`{func.__name__}`\n`{str(e)[:300]}`",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
    return wrapper


def admin_only(func):
    """Decorator: reject non-admins before entering handler."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from config.db import get_db
        from services.admin_service import AdminService
        telegram_id = update.effective_user.id
        with next(get_db()) as db:
            if not AdminService.is_admin(telegram_id, db):
                msg = "🚫 *Admin access required.*"
                if update.callback_query:
                    await update.callback_query.answer("Access denied.", show_alert=True)
                else:
                    await update.message.reply_text(msg, parse_mode="Markdown")
                return
        return await func(update, context, *args, **kwargs)
    return wrapper
