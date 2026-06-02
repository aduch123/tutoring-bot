from telegram import Update
from telegram.constants import ParseMode


async def reply(update: Update, text: str, reply_markup=None):
    """Smart reply — works for both messages and callback queries.

    When responding to a callback query on a media message (photo, video,
    document), Telegram does not allow edit_message_text — only
    edit_message_caption. We detect that and fall back to sending a new
    message so the admin always gets a response.
    """
    if update.callback_query:
        msg = update.callback_query.message
        has_media = bool(
            msg and (msg.photo or msg.video or msg.document
                     or msg.audio or msg.animation or msg.sticker)
        )
        if has_media:
            # Can't edit text on a media message — answer the query silently
            # and send a fresh message instead.
            await update.callback_query.answer()
            await msg.reply_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup, disable_web_page_preview=True,
            )
        else:
            await update.callback_query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup, disable_web_page_preview=True,
            )
    elif update.message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup, disable_web_page_preview=True,
        )


async def send(bot, chat_id: int, text: str, reply_markup=None):
    await bot.send_message(
        chat_id=chat_id, text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )