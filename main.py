"""Entry point."""
import threading
import http.server
import socketserver
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from config.config import BOT_TOKEN
from config.db import init_db
import os
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    format="%(asctime)s · %(name)s · %(levelname)s · %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.registration import check_channel_membership, channel_join_keyboard
    from utils.helpers import reply
    joined = await check_channel_membership(context.bot, update.effective_user.id)
    if not joined:
        await reply(update,
            "📢 *Join Our Channel First*\n\n"
            "You must join our official channel to use EduConnect.",
            reply_markup=channel_join_keyboard())
        return
    from handlers.dashboards import route_to_dashboard
    await route_to_dashboard(update, context)


# ── /myid ─────────────────────────────────────────────────────────────────────

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config.db import get_db
    from repositories.user import UserRepository
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
    tid = update.effective_user.id
    if user:
        await update.message.reply_text(
            f"Your Platform ID: `{user.user_id}`\n"
            f"Your Telegram ID: `{tid}`",
            parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"Your Telegram ID: `{tid}`\n_Not registered yet._",
            parse_mode="Markdown")


# ── Channel join check ────────────────────────────────────────────────────────

async def check_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from handlers.registration import check_channel_membership, channel_join_keyboard
    joined = await check_channel_membership(context.bot, update.effective_user.id)
    if joined:
        from handlers.dashboards import route_to_dashboard
        await route_to_dashboard(update, context)
    else:
        await query.edit_message_text(
            "❌ *Not joined yet.*\n\nPlease join the channel first.",
            parse_mode="Markdown",
            reply_markup=channel_join_keyboard())


# ── Reply keyboard router ─────────────────────────────────────────────────────

async def handle_reply_keyboard(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE) -> bool:
    text = update.message.text

    async def _sessions_student(u, c):
        from handlers.student import student_sessions
        await student_sessions(u, c)

    async def _schedule_student(u, c):
        from handlers.student import student_schedule
        await student_schedule(u, c)

    async def _payments(u, c):
        from handlers.student import student_payments
        await student_payments(u, c)

    async def _profile(u, c):
        from config.db import get_db
        from repositories.user import UserRepository
        with next(get_db()) as db:
            usr = UserRepository(db).get_by_telegram_id(u.effective_user.id)
        if usr and usr.role == "tutor":
            from handlers.tutor import tutor_profile
            await tutor_profile(u, c)
        else:
            from handlers.student import my_profile
            await my_profile(u, c)

    async def _earnings(u, c):
        from handlers.tutor import tutor_earnings
        await tutor_earnings(u, c)

    async def _sessions_tutor(u, c):
        from handlers.tutor import tutor_sessions
        await tutor_sessions(u, c)

    async def _schedule_tutor(u, c):
        from handlers.tutor import tutor_schedule
        await tutor_schedule(u, c)

    async def _recording(u, c):
        from handlers.tutor import upload_start
        await upload_start(u, c)

    async def _confirm(u, c):
        from handlers.confirm_flow import confirm_start
        await confirm_start(u, c)

    async def _report(u, c):
        from handlers.student import report_start
        await report_start(u, c)

    async def _emergency(u, c):
        from handlers.student import emergency_start
        await emergency_start(u, c)

    async def _help(u, c):
        from handlers.callbacks import _show_help
        from config.db import get_db
        from repositories.user import UserRepository
        with next(get_db()) as db:
            usr = UserRepository(db).get_by_telegram_id(u.effective_user.id)
        await _show_help(u, c, usr.role if usr else None)

    async def _overview(u, c):
        from handlers.admin_panel import admin_overview
        await admin_overview(u, c)

    async def _users(u, c):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await u.message.reply_text("👥 *User Management*\n\nChoose a category:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Students", callback_data="students_filter_all"),
                 InlineKeyboardButton("👨‍🏫 Tutors", callback_data="tutors_filter_all")],
                [InlineKeyboardButton("👑 Admins", callback_data="admins_filter_all")],
                [InlineKeyboardButton("‹ Back", callback_data="admin_home")],
            ]))

    async def _finance(u, c):
        from ui.keyboards import admin_finance_menu
        await u.message.reply_text("💰 *Finance*\n\nChoose an action:",
            parse_mode="Markdown", reply_markup=admin_finance_menu())

    async def _emergencies(u, c):
        from handlers.admin_panel import show_emergencies
        await show_emergencies(u, c)

    async def _issues(u, c):
        from handlers.admin_panel import show_issues
        await show_issues(u, c)

    routes = {
        # Student
        "📅 Sessions": _sessions_student,
        "📆 Schedule": _schedule_student,
        "💳 Payments": _payments,
        "👤 Profile": _profile,
        "📝 Report": _report,
        "🚨 Emergency": _emergency,
        # Tutor
        "💰 Earnings": _earnings,
        "📹 Recording": _recording,
        "✅ Confirm": _confirm,
        # Admin
        "📊 Overview": _overview,
        "👥 Students": _users,
        "👨‍🏫 Tutors": _users,
        "👑 Admins": _users,
        "💰 Finance": _finance,
        "🚨 Emergencies": _emergencies,
        "⚠️ Issues": _issues,
        # Shared
        "❓ Help": _help,
    }

    handler = routes.get(text)
    if handler is None:
        return False
    await handler(update, context)
    return True


# ── Smart message handler ─────────────────────────────────────────────────────

async def smart_message_handler(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    # 1. Reply keyboard buttons
    if update.message and update.message.text:
        handled = await handle_reply_keyboard(update, context)
        if handled:
            return

    # 2. Zoom link text
    if update.message and update.message.text:
        from handlers.zoom import handle_zoom_link_text
        handled = await handle_zoom_link_text(update, context)
        if handled:
            return

    # 3. Payment screenshot
    if update.message and update.message.photo:
        from handlers.callbacks import handle_payment_screenshot
        handled = await handle_payment_screenshot(update, context)
        if handled:
            return

    # 4. Tutor video upload (pending_video) — must come before file upload response.
    #    Videos sent as files arrive as update.message.document with a video mime type,
    #    so we must intercept documents here before handle_file_upload_response does.
    if update.message and (update.message.video or update.message.document):
        from config.db import get_db
        from repositories.user import UserRepository, TutorRepository
        _handled_as_tutor_video = False
        with next(get_db()) as db:
            _tvu_user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
            if _tvu_user and _tvu_user.role == "tutor":
                _tvu_tut = TutorRepository(db).get(_tvu_user.user_id)
                if _tvu_tut and _tvu_tut.approval_status == "pending_video":
                    _handled_as_tutor_video = True
                    # Resolve file_id — accept native video or video-sent-as-document
                    _tvu_msg = update.message
                    _tvu_file_id = None
                    if _tvu_msg.video:
                        _tvu_file_id = _tvu_msg.video.file_id
                    elif _tvu_msg.document:
                        _tvu_mime = _tvu_msg.document.mime_type or ""
                        if _tvu_mime.startswith("video/"):
                            _tvu_file_id = _tvu_msg.document.file_id

                    if not _tvu_file_id:
                        # Non-video file sent while awaiting video — guide them
                        await update.message.reply_text(
                            "⚠️ *Please send a video file.*\n\n"
                            "We need a teaching video (30–50 min) of you tutoring.\n\n"
                            "Send it here as a video or as a file. "
                            "To cancel your application, contact an admin.",
                            parse_mode="Markdown")
                        return

                    # Save the video (re-sending replaces the previous one)
                    _tvu_tut.video_file_id = _tvu_file_id
                    db.commit()
                    _tvu_name = _tvu_user.full_name
                    _tvu_uid = _tvu_user.user_id

        if _handled_as_tutor_video and _tvu_file_id:
            from config.config import ADMIN_GROUP_CHAT_ID
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            review_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Approve",
                    callback_data=f"approve_video_{_tvu_uid}"),
                InlineKeyboardButton("❌ Reject & Blacklist",
                    callback_data=f"reject_video_{_tvu_uid}"),
            ]])
            await update.message.reply_text(
                "✅ *Video received!*\n\n"
                "An admin will review it and notify you soon.\n\n"
                "_Sent the wrong video? Just send the correct one — "
                "it will replace the previous one._",
                parse_mode="Markdown")
            if ADMIN_GROUP_CHAT_ID:
                try:
                    await context.bot.send_video(
                        chat_id=ADMIN_GROUP_CHAT_ID, video=_tvu_file_id,
                        caption=f"📹 *Teaching Video*\n\n"
                                f"Tutor: *{_tvu_name}*\n"
                                f"ID: `{_tvu_uid}`",
                        parse_mode="Markdown",
                        reply_markup=review_kb)
                except Exception as e:
                    logger.error(f"Failed to send tutor video to admin group: {e}")
            return

    # 5. File upload response (admin messaging)
    if update.message and (update.message.photo or update.message.document):
        from handlers.messaging import handle_file_upload_response
        handled = await handle_file_upload_response(update, context)
        if handled:
            return

    # 6. Rate input
    if update.message and update.message.text:
        if context.user_data.get("awaiting_rate_input"):
            student_id = context.user_data.pop("setting_rate_for", None)
            context.user_data.pop("awaiting_rate_input", None)
            try:
                rate = float(update.message.text.strip())
                from services.payment_service import PaymentService
                from config.db import get_db
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                with next(get_db()) as db:
                    result = PaymentService(db).set_student_rate(
                        update.effective_user.id, student_id, rate)
                await update.message.reply_text(
                    f"{'✅' if result['success'] else '❌'} {result['message']}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("‹ Back",
                            callback_data=f"stu_detail_{student_id}")]]))
            except ValueError:
                await update.message.reply_text("❌ Please enter a valid number.")
            return

    # 7. Admin text responses (resolve, reject)
    if update.message and update.message.text:
        from handlers.callbacks import handle_text_in_context
        await handle_text_in_context(update, context)


# ── Scheduler ─────────────────────────────────────────────────────────────────

def setup_scheduler(app: Application) -> AsyncIOScheduler:
    from services.notification_service import (
        job_generate_sessions, job_request_zoom_links,
        job_zoom_deadline_check,
        job_mark_missed_sessions, job_payment_reminders,
        job_session_start_confirmation, job_check_tutor_start_response,
        job_session_end_confirmation, job_recording_reminder,
    )
    bot = app.bot
    # Capture the running event loop now (we are inside main_async, so it exists).
    # APScheduler runs lambdas in a thread pool where asyncio.get_event_loop()
    # raises RuntimeError, so we must close over the loop here.
    loop = asyncio.get_event_loop()
    scheduler = AsyncIOScheduler(timezone="Africa/Addis_Ababa")
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_generate_sessions(), loop),
        CronTrigger(hour=0, minute=5))
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_request_zoom_links(bot), loop),
        IntervalTrigger(hours=1))
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_zoom_deadline_check(bot), loop),
        IntervalTrigger(minutes=15))
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_session_start_confirmation(bot), loop),
        IntervalTrigger(minutes=5))
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_check_tutor_start_response(bot), loop),
        IntervalTrigger(minutes=15))
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_session_end_confirmation(bot), loop),
        IntervalTrigger(minutes=5))
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_recording_reminder(bot), loop),
        IntervalTrigger(hours=6))
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_mark_missed_sessions(), loop),
        IntervalTrigger(hours=1))
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(job_payment_reminders(bot), loop),
        CronTrigger(hour=8, minute=0))
    return scheduler


# ── Handler registration ──────────────────────────────────────────────────────

def register_handlers(app: Application):
    from handlers.registration import student_conv_handler, tutor_conv_handler
    from handlers.tutor import upload_conv_handler
    from handlers.confirm_flow import confirm_conv_handler
    from handlers.student import report_conv_handler, emergency_conv_handler
    from handlers.admin_panel import (
        assign_tutor_conv_handler, edit_student_conv_handler,
        edit_tutor_conv_handler, edit_admin_conv_handler,
        add_admin_conv_handler,
    )
    from handlers.messaging import (
        messaging_conv_handler, handle_user_message_response)
    from handlers.callbacks import callback_router
    from handlers.zoom import (
        handle_zoom_confirm, handle_zoom_retry, handle_zoom_cancel)
    from handlers.session_confirmations import (
        handle_start_confirm, handle_start_decline,
        handle_end_confirm_tutor, handle_end_confirm_student,
        handle_end_issue, handle_recording_approve, handle_recording_reject,
        assign_replacement_start, do_assign_replacement,
    )

    # ConversationHandlers (highest priority)
    app.add_handler(student_conv_handler())
    app.add_handler(tutor_conv_handler())
    app.add_handler(upload_conv_handler())
    app.add_handler(confirm_conv_handler())
    app.add_handler(report_conv_handler())
    app.add_handler(emergency_conv_handler())
    app.add_handler(assign_tutor_conv_handler())
    app.add_handler(edit_student_conv_handler())
    app.add_handler(edit_tutor_conv_handler())
    app.add_handler(edit_admin_conv_handler())
    app.add_handler(add_admin_conv_handler())
    app.add_handler(messaging_conv_handler())

    # Core commands (only /start, /myid, /cancel remain)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))

    # Session lifecycle callbacks
    app.add_handler(CallbackQueryHandler(
        handle_start_confirm, pattern=r"^start_confirm_"))
    app.add_handler(CallbackQueryHandler(
        handle_start_decline, pattern=r"^start_decline_"))
    app.add_handler(CallbackQueryHandler(
        handle_end_confirm_tutor, pattern=r"^end_confirm_tut_"))
    app.add_handler(CallbackQueryHandler(
        handle_end_confirm_student, pattern=r"^end_confirm_stu_"))
    app.add_handler(CallbackQueryHandler(
        handle_end_issue, pattern=r"^end_issue"))
    app.add_handler(CallbackQueryHandler(
        handle_recording_approve, pattern=r"^approve_recording_"))
    app.add_handler(CallbackQueryHandler(
        handle_recording_reject, pattern=r"^reject_recording_"))
    app.add_handler(CallbackQueryHandler(
        assign_replacement_start, pattern=r"^assign_replacement_"))
    app.add_handler(CallbackQueryHandler(
        do_assign_replacement, pattern=r"^do_replace_"))

    # Zoom flow callbacks
    app.add_handler(CallbackQueryHandler(
        handle_zoom_confirm, pattern=r"^zoom_confirm_"))
    app.add_handler(CallbackQueryHandler(
        handle_zoom_retry, pattern=r"^zoom_retry_"))
    app.add_handler(CallbackQueryHandler(
        handle_zoom_cancel, pattern=r"^cancel_zoom$"))

    # Channel join
    app.add_handler(CallbackQueryHandler(
        check_channel_join, pattern="^check_channel_join$"))

    # Zoom link request button
    app.add_handler(CallbackQueryHandler(
        _handle_zoom_request, pattern=r"^zoom_request_"))

    # User message responses
    app.add_handler(CallbackQueryHandler(
        handle_user_message_response, pattern=r"^msg_resp_"))

    # Upload session selection
    app.add_handler(CallbackQueryHandler(
        _handle_upload_select, pattern=r"^upload_select_"))

    # Central callback router (catch-all)
    app.add_handler(CallbackQueryHandler(callback_router))

    # Smart message handler
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO |
         filters.Document.ALL | filters.VIDEO) & ~filters.COMMAND,
        smart_message_handler
    ))


async def _handle_zoom_request(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Tutor taps 'Submit Zoom Link' button — sets context and prompts."""
    query = update.callback_query
    await query.answer()
    session_id = query.data.replace("zoom_request_", "")
    context.user_data["awaiting_zoom_link"] = True
    context.user_data["zoom_session_id"] = session_id
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    await query.edit_message_text(
        f"🔗 *Submit Zoom Link*\n\n"
        f"Session: `{session_id}`\n\n"
        f"Please paste your Zoom meeting link below:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✕ Cancel", callback_data="cancel_zoom")
        ]]))


async def _handle_upload_select(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    from handlers.tutor import upload_session_selected
    await upload_session_selected(update, context)

def run_dummy_server():
    # Render provides the PORT variable; default to 8080 if local
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    
    # Allow reuse of the port to prevent address-already-in-use errors
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Dummy server listening on port {port} to satisfy Render.")
        httpd.serve_forever()

# ── Main ──────────────────────────────────────────────────────────────────────

async def main_async():
    print("=" * 52)
    print("   EDUCONNECT TUTORING BOT")
    print("=" * 52)

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN missing in .env")
        return

    from config.config import ADMIN_GROUP_CHAT_ID
    if not ADMIN_GROUP_CHAT_ID:
        print("WARNING: ADMIN_GROUP_CHAT_ID not set — admin notifications will be silently dropped!")
        logger.warning("ADMIN_GROUP_CHAT_ID not set in .env — all admin group notifications disabled.")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()
    register_handlers(app)

    # Register global error handler so any undecorated handler failure is caught
    async def _global_error_handler(update, context):
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Unhandled exception:\n{tb}")
        if ADMIN_GROUP_CHAT_ID:
            try:
                func_name = context.error.__traceback__.tb_frame.f_code.co_name if context.error else "unknown"
                await context.bot.send_message(
                    chat_id=ADMIN_GROUP_CHAT_ID,
                    text=f"🤖 *Unhandled Bot Error*\n\n`{func_name}`\n`{str(context.error)[:300]}`",
                    parse_mode="Markdown")
            except Exception:
                pass
    app.add_error_handler(_global_error_handler)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    # Start scheduler AFTER the app is fully running so the bot object is ready
    scheduler = setup_scheduler(app)
    scheduler.start()

    from services.notification_service import job_generate_sessions
    await job_generate_sessions()

    print("Bot is running. Press Ctrl+C to stop.")
    print("=" * 52)

    try:
        await asyncio.get_event_loop().create_future()
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down...")
    finally:
        scheduler.shutdown(wait=False)
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def main():
    # Start a fake web server in a separate background thread
    threading.Thread(target=run_dummy_server, daemon=True).start()

    asyncio.run(main_async())


if __name__ == "__main__":
    main()