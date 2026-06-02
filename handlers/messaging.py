"""Admin-to-user messaging — 5 response types."""
import json
import logging
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

(
    MSG_COMPOSE, MSG_RESPONSE_TYPE, MSG_OPTIONS, MSG_PREVIEW, MSG_AWAIT_RESPONSE,
) = range(5)

RESPONSE_TYPES = {
    "text": "📝 Text Reply",
    "approve_disapprove": "✅❌ Approve / Disapprove",
    "acknowledge": "👍 Acknowledge",
    "choose_options": "🔘 Choose from Options",
    "file_upload": "📎 File Upload",
}


def _kb(rows): return InlineKeyboardMarkup(rows)
def _back(cb="back"): return _kb([[InlineKeyboardButton("‹ Back", callback_data=cb)]])


async def _cancel(update, context):
    context.user_data.clear()
    await reply(update, "❌ Cancelled.")
    return ConversationHandler.END


# ── Start messaging flow ──────────────────────────────────────────────────────

async def start_message_flow(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              to_user_id: str):
    """Entry: admin taps Send Message on a user detail screen."""
    with next(get_db()) as db:
        from repositories.user import UserRepository
        user = UserRepository(db).get_by_user_id(to_user_id)
        if not user:
            await reply(update, "❌ User not found.")
            return ConversationHandler.END

    context.user_data["msg_to_user_id"] = to_user_id
    context.user_data["msg_to_name"] = user.full_name
    context.user_data["msg_to_telegram_id"] = user.telegram_id

    await reply(update,
        f"✉️ *Send Message*\n\n"
        f"To: *{user.full_name}* (`{to_user_id}`)\n\n"
        f"{'─'*26}\n\n"
        f"Type the message you want to send:",
        reply_markup=_back(f"msg_back_{to_user_id}"))
    return MSG_COMPOSE


async def msg_compose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["msg_text"] = update.message.text.strip()

    rows = []
    for key, label in RESPONSE_TYPES.items():
        rows.append([InlineKeyboardButton(label, callback_data=f"msgtype_{key}")])
    rows.append([InlineKeyboardButton("‹ Back", callback_data="back"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel_msg")])

    await update.message.reply_text(
        f"✉️ *Send Message*\n\n"
        f"*Message:* {context.user_data['msg_text'][:100]}\n\n"
        f"{'─'*26}\n\n"
        f"What kind of response do you expect?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb(rows))
    return MSG_RESPONSE_TYPE


async def msg_response_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rtype = query.data.replace("msgtype_", "")
    context.user_data["msg_response_type"] = rtype

    if rtype == "choose_options":
        await query.edit_message_text(
            f"🔘 *Choose from Options*\n\n"
            f"Enter the options the user can choose from.\n"
            f"_(One option per line, 2-4 options)_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_back())
        return MSG_OPTIONS

    # Show preview for other types
    return await _show_preview(query, context)


async def msg_options_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    options = [o.strip() for o in update.message.text.strip().split("\n") if o.strip()]
    if len(options) < 2:
        await update.message.reply_text(
            "❌ Please enter at least 2 options, one per line:",
            reply_markup=_back())
        return MSG_OPTIONS
    if len(options) > 4:
        options = options[:4]
    context.user_data["msg_options"] = options
    return await _show_preview(None, context, update=update)


async def _show_preview(query_or_none, context, update=None):
    msg_text = context.user_data.get("msg_text", "")
    rtype = context.user_data.get("msg_response_type", "")
    to_name = context.user_data.get("msg_to_name", "User")
    options = context.user_data.get("msg_options", [])

    type_label = RESPONSE_TYPES.get(rtype, rtype)
    preview = (
        f"👁 *Message Preview*\n\n"
        f"To: *{to_name}*\n"
        f"Response type: {type_label}\n"
        + (f"Options: {', '.join(options)}\n" if options else "") +
        f"\n{'─'*26}\n\n"
        f"*Message:*\n{msg_text}\n\n"
        f"{'─'*26}\n\n"
        f"Send this message?"
    )
    kb = _kb([
        [InlineKeyboardButton("✅ Send", callback_data="msg_send"),
         InlineKeyboardButton("✏️ Edit", callback_data="msg_edit")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_msg")],
    ])

    if query_or_none:
        await query_or_none.edit_message_text(preview, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    elif update:
        await update.message.reply_text(preview, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    return MSG_PREVIEW


async def msg_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    d = context.user_data
    to_telegram_id = d.get("msg_to_telegram_id")
    to_user_id = d.get("msg_to_user_id")
    msg_text = d.get("msg_text", "")
    rtype = d.get("msg_response_type", "text")
    options = d.get("msg_options", [])

    with next(get_db()) as db:
        from services.messaging_service import MessagingService
        from repositories.user import UserRepository
        admin = UserRepository(db).get_by_telegram_id(update.effective_user.id)
        svc = MessagingService(db)
        result = svc.create_message(
            admin_id=admin.user_id if admin else "admin",
            to_user_id=to_user_id,
            message_text=msg_text,
            response_type=rtype,
            response_options=options or None,
        )

    if not result["success"]:
        await query.edit_message_text(f"❌ {result['message']}")
        return ConversationHandler.END

    msg_id = result["message_id"]

    # Build the message to send to user
    user_kb = None
    instruction = ""

    if rtype == "text":
        instruction = "\n\n_Please reply with your response in a message._"
    elif rtype == "approve_disapprove":
        user_kb = _kb([[
            InlineKeyboardButton("✅ Approve", callback_data=f"msg_resp_{msg_id}_approve"),
            InlineKeyboardButton("❌ Disapprove", callback_data=f"msg_resp_{msg_id}_disapprove"),
        ]])
    elif rtype == "acknowledge":
        user_kb = _kb([[
            InlineKeyboardButton("👍 Got it", callback_data=f"msg_resp_{msg_id}_acknowledged"),
        ]])
    elif rtype == "choose_options":
        rows = [[InlineKeyboardButton(opt, callback_data=f"msg_resp_{msg_id}_{i}")]
                for i, opt in enumerate(options)]
        user_kb = _kb(rows)
    elif rtype == "file_upload":
        instruction = "\n\n_Please reply by sending the requested file or photo._"

    full_message = (
        f"📨 *Message from Admin*\n\n"
        f"{'─'*26}\n\n"
        f"{msg_text}"
        f"{instruction}"
    )

    try:
        await query.message.get_bot().send_message(
            chat_id=to_telegram_id,
            text=full_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=user_kb)
        await query.edit_message_text(
            f"✅ *Message sent to {result['to_name']}.*",
            parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await query.edit_message_text(f"❌ Failed to send message: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def msg_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✏️ Enter the new message text:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_back())
    return MSG_COMPOSE


# ── User response handlers ────────────────────────────────────────────────────

async def handle_user_message_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button responses from users to admin messages."""
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("msg_resp_", "").split("_", 1)
    msg_id, response = parts[0], parts[1] if len(parts) > 1 else "responded"

    with next(get_db()) as db:
        from services.messaging_service import MessagingService
        from repositories.user import UserRepository
        svc = MessagingService(db)
        msg_log = svc.get_message(msg_id)
        svc.record_response(msg_id, response)
        if msg_log:
            admin_user = UserRepository(db).get_by_user_id(msg_log.from_admin_id)
            user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
            user_name = user.full_name if user else "User"

    await query.edit_message_text(
        f"✅ *Response sent.*\n\nAn admin has been notified.",
        parse_mode=ParseMode.MARKDOWN)

    # Notify admin
    if msg_log and admin_user:
        try:
            await send(query.message.get_bot(), admin_user.telegram_id,
                f"📨 *Message Response*\n\n"
                f"From: *{user_name}*\n"
                f"Message ID: `{msg_id}`\n"
                f"Response: *{response}*")
        except Exception:
            pass


async def handle_file_upload_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle file uploads as responses to admin messages."""
    if not context.user_data.get("awaiting_msg_file"):
        return False
    msg_id = context.user_data.pop("awaiting_msg_file")
    file_id = None
    if update.message.document:
        file_id = update.message.document.file_id
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
    if not file_id:
        return False

    with next(get_db()) as db:
        from services.messaging_service import MessagingService
        svc = MessagingService(db)
        svc.record_response(msg_id, f"file_uploaded:{file_id}")

    await update.message.reply_text("✅ File received. Admin has been notified.")
    return True


def messaging_conv_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                lambda u, c: start_message_flow(u, c,
                    u.callback_query.data.replace("send_message_", "")),
                pattern=r"^send_message_")
        ],
        states={
            MSG_COMPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, msg_compose)],
            MSG_RESPONSE_TYPE: [CallbackQueryHandler(msg_response_type, pattern="^msgtype_")],
            MSG_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, msg_options_received)],
            MSG_PREVIEW: [
                CallbackQueryHandler(msg_send, pattern="^msg_send$"),
                CallbackQueryHandler(msg_edit, pattern="^msg_edit$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern="^back$"),
            CallbackQueryHandler(_cancel, pattern="^cancel_msg$"),
        ],
        name="admin_messaging", per_message=False, persistent=False,
    )
