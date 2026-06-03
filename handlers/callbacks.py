"""Central callback query router."""
import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from config.db import get_db
from utils.helpers import reply, send
from utils.error_handler import handle_errors

logger = logging.getLogger(__name__)


@handle_errors
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    from repositories.user import UserRepository
    with next(get_db()) as db:
        user = UserRepository(db).get_by_telegram_id(update.effective_user.id)
    role = user.role if user else None

    # ── Navigation ────────────────────────────────────────────────────────────
    if data in ("back", "admin_home"):
        from handlers.dashboards import route_to_dashboard
        await route_to_dashboard(update, context)

    elif data == "noop":
        pass

    # ── Unregistered ──────────────────────────────────────────────────────────
    elif data == "about":
        from ui.templates import about_message
        from ui.keyboards import unregistered_menu
        await reply(update, about_message(), reply_markup=unregistered_menu())

    elif data == "help":
        await _show_help(update, context, role)

    # ── Payment locked ────────────────────────────────────────────────────────
    elif data == "show_payment_page":
        from ui.payment_page import payment_page
        from ui.keyboards import student_locked_menu
        from services.payment_service import PaymentService
        with next(get_db()) as db:
            u = user
            rate = PaymentService(db).get_student_rate(u.user_id) if u else 400
        month = datetime.now().strftime("%B %Y")
        await reply(update, payment_page(rate, month, u.full_name if u else "Student"),
                    reply_markup=_locked_menu())

    elif data == "upload_payment_proof":
        from ui.keyboards import back
        await reply(update,
            "📸 *Upload Payment Screenshot*\n\n"
            "Send a clear screenshot of your payment confirmation.\n\n"
            "_Make sure the amount is visible._",
            reply_markup=back())
        context.user_data["awaiting_payment_screenshot"] = True

    # ── Student ───────────────────────────────────────────────────────────────
    elif data == "student_sessions":
        from handlers.student import student_sessions
        await student_sessions(update, context)

    elif data == "student_schedule":
        from handlers.student import student_schedule
        await student_schedule(update, context)

    elif data == "student_payments":
        from handlers.student import student_payments
        await student_payments(update, context)

    elif data == "my_profile":
        if role == "student":
            from handlers.student import my_profile
            await my_profile(update, context)
        elif role == "tutor":
            from handlers.tutor import tutor_profile
            await tutor_profile(update, context)
        else:
            await _myid(update, user)

    # ── Tutor ─────────────────────────────────────────────────────────────────
    elif data == "tutor_sessions":
        from handlers.tutor import tutor_sessions
        await tutor_sessions(update, context)

    elif data == "tutor_schedule":
        from handlers.tutor import tutor_schedule
        await tutor_schedule(update, context)

    elif data == "tutor_earnings":
        from handlers.tutor import tutor_earnings
        await tutor_earnings(update, context)
        
    elif data.startswith("reupload_docs_done_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        import json
        parts = data.replace("reupload_docs_done_", "").rsplit("_", 1)
        tutor_id = parts[0]
        admin_id = int(parts[1])
        file_ids = context.user_data.get("reupload_file_ids", [])
        if not file_ids:
            await query.answer("Please send at least one file first.", show_alert=True)
            return
        with next(get_db()) as db:
            from repositories.user import UserRepository, TutorRepository
            tut = TutorRepository(db).get(tutor_id)
            user = UserRepository(db).get_by_user_id(tutor_id)
            if tut:
                tut.cv_file_ids = json.dumps(file_ids)
                db.commit()
            full_name = user.full_name if user else tutor_id

        context.user_data.pop("awaiting_doc_reupload", None)
        context.user_data.pop("reupload_file_ids", None)
        context.user_data.pop("reupload_tutor_id", None)
        context.user_data.pop("reupload_admin_id", None)

        await reply(update,
            "✅ *Documents Re-submitted*\n\n"
            "Your documents have been sent to the reviewer. "
            "You will be notified once they are reviewed.")

        await send(context.bot, admin_id,
            f"📄 *Re-uploaded Documents*\n\n"
            f"Tutor *{full_name}* (`{tutor_id}`) has re-uploaded their documents.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "📄 Show Documents",
                    callback_data=f"show_docs_tut_{tutor_id}_{admin_id}")
            ]]))
        
    elif data.startswith("reupload_docs_"):
        parts = data.replace("reupload_docs_", "").rsplit("_", 1)
        tutor_id = parts[0]
        admin_id = parts[1]
        context.user_data["awaiting_doc_reupload"] = True
        context.user_data["reupload_tutor_id"] = tutor_id
        context.user_data["reupload_admin_id"] = admin_id
        context.user_data["reupload_file_ids"] = []
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await reply(update,
            "📤 *Re-upload Documents*\n\n"
            "Send your files one by one (PDFs or photos).\n"
            "When you're done tap the Submit button.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "✅ Submit Documents",
                    callback_data=f"reupload_docs_done_{tutor_id}_{admin_id}")
            ]]))

    # ── Admin — top level ─────────────────────────────────────────────────────
    elif data == "admin_overview":
        from handlers.admin_panel import admin_overview
        await admin_overview(update, context)

    elif data == "admin_finance":
        from ui.keyboards import admin_finance_menu
        await reply(update, "💰 *Finance*\n\nChoose an action:",
                    reply_markup=admin_finance_menu())

    elif data == "finance_invoices":
        from handlers.admin_panel import show_invoices
        await show_invoices(update, context, "all")

    elif data == "finance_payouts":
        from handlers.admin_panel import show_payouts
        await show_payouts(update, context, "all")

    elif data == "generate_payouts_now":
        from services.payment_service import PaymentService
        month = datetime.now().date().replace(day=1)
        with next(get_db()) as db:
            result = PaymentService(db).generate_monthly_payouts(
                update.effective_user.id, month)
        from ui.keyboards import back
        if not result["success"]:
            await reply(update, f"❌ {result['message']}", reply_markup=back("finance_payouts"))
        else:
            lines = [f"💸 *Payouts Generated — {result['month']}*\n\nTotal: {result['created']} tutors\n"]
            for p in result["payouts"]:
                lines.append(f"• {p['tutor']} — {p['sessions']} sessions — *{p['net']:.0f} ETB*")
            await reply(update, "\n".join(lines), reply_markup=back("finance_payouts"))

    elif data.startswith("invoices_filter_"):
        from handlers.admin_panel import show_invoices
        ft = data.replace("invoices_filter_", "")
        await show_invoices(update, context, ft)

    elif data.startswith("payouts_filter_"):
        from handlers.admin_panel import show_payouts
        ft = data.replace("payouts_filter_", "")
        await show_payouts(update, context, ft)

    elif data.startswith("invoice_detail_"):
        from handlers.admin_panel import invoice_detail
        await invoice_detail(update, context, data.replace("invoice_detail_", ""))

    elif data.startswith("payout_detail_"):
        parts = data.replace("payout_detail_", "").rsplit("_", 1)
        from handlers.admin_panel import payout_detail
        await payout_detail(update, context, parts[0], parts[1])

    elif data.startswith("mark_payout_"):
        parts = data.replace("mark_payout_", "").rsplit("_", 1)
        tutor_id, month_str = parts[0], parts[1]
        from services.payment_service import PaymentService
        from ui.keyboards import back
        month = datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
        with next(get_db()) as db:
            result = PaymentService(db).mark_payout_paid(
                update.effective_user.id, tutor_id, month)
        if result["success"] and result.get("tutor_telegram_id"):
            from ui.templates import payout_paid_tutor
            await send(context.bot, result["tutor_telegram_id"],
                payout_paid_tutor(result["tutor_name"], result["month"], result["net"]))
        msg = f"{'✅' if result['success'] else '❌'} {result.get('message', 'Done.')}"
        await reply(update, msg, reply_markup=back("finance_payouts"))

    elif data == "set_student_rate":
        from ui.keyboards import back
        context.user_data["awaiting_rate_input"] = True
        context.user_data["setting_rate_for"] = None
        from ui.keyboards import back
        await reply(update,
            "📊 *Set Student Rate*\n\n"
            "Please go to Students → Student Detail → Set Rate\n"
            "to set a rate for a specific student.",
            reply_markup=back("admin_finance"))

    # ── Admin — users ─────────────────────────────────────────────────────────
    elif data == "admin_users":
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton as IKB
        await reply(update, "👥 *User Management*\n\nChoose a category:",
                    reply_markup=InlineKeyboardMarkup([
                        [IKB("📚 Students", callback_data="students_filter_all"),
                         IKB("👨‍🏫 Tutors", callback_data="tutors_filter_all")],
                        [IKB("👑 Admins", callback_data="admins_filter_all")],
                        [IKB("‹ Back", callback_data="admin_home")],
                    ]))

    elif data.startswith("students_filter_"):
        rest = data.replace("students_filter_", "")
        if "_page_" in rest:
            parts = rest.split("_page_")
            ft, page = parts[0], int(parts[1])
        else:
            ft, page = rest, 0
        from handlers.admin_panel import show_students_list
        await show_students_list(update, context, ft, page)

    elif data.startswith("tutors_filter_"):
        rest = data.replace("tutors_filter_", "")
        if "_page_" in rest:
            parts = rest.split("_page_")
            ft, page = parts[0], int(parts[1])
        else:
            ft, page = rest, 0
        from handlers.admin_panel import show_tutors_list
        await show_tutors_list(update, context, ft, page)

    elif data.startswith("admins_filter_") or data.startswith("admins_page_"):
        page = 0
        if data.startswith("admins_page_"):
            page = int(data.replace("admins_page_", ""))
        from handlers.admin_panel import show_admins_list
        await show_admins_list(update, context, page)

    elif data.startswith("stu_detail_"):
        from handlers.admin_panel import student_detail
        await student_detail(update, context, data.replace("stu_detail_", ""))

    elif data.startswith("tut_detail_"):
        from handlers.admin_panel import tutor_detail
        await tutor_detail(update, context, data.replace("tut_detail_", ""))

    elif data.startswith("adm_detail_"):
        from handlers.admin_panel import admin_detail
        await admin_detail(update, context, data.replace("adm_detail_", ""))

    elif data.startswith("assign_tutor_"):
        from handlers.admin_panel import show_compatible_tutors
        await show_compatible_tutors(update, context, data.replace("assign_tutor_", ""))

    elif data.startswith("assign_filter_"):
        # assign_filter_all_STU-0001 / assign_filter_primary_STU-0001
        parts = data.replace("assign_filter_", "").split("_", 1)
        filter_type = parts[0]
        student_id = parts[1] if len(parts) > 1 else ""
        from handlers.admin_panel import show_compatible_tutors
        await show_compatible_tutors(update, context, student_id, filter_type)

    elif data.startswith("tutor_briefing_"):
        tutor_id = data.replace("tutor_briefing_", "")
        from handlers.admin_panel import show_tutor_briefing
        await show_tutor_briefing(update, context, tutor_id)

    elif data.startswith("edit_student_"):
        from handlers.admin_panel import edit_student_start
        await edit_student_start(update, context, data.replace("edit_student_", ""))

    elif data.startswith("edit_tutor_"):
        from handlers.admin_panel import edit_tutor_start
        await edit_tutor_start(update, context, data.replace("edit_tutor_", ""))

    elif data.startswith("edit_schedule_stu_"):
        uid = data.replace("edit_schedule_stu_", "")
        from handlers.admin_panel import edit_schedule_list
        await edit_schedule_list(update, context, uid, f"stu_detail_{uid}")

    elif data.startswith("edit_schedule_tut_"):
        uid = data.replace("edit_schedule_tut_", "")
        from handlers.admin_panel import edit_schedule_list
        await edit_schedule_list(update, context, uid, f"tut_detail_{uid}")

    elif data.startswith("deactivate_sch_"):
        parts = data.replace("deactivate_sch_", "").split("_", 1)
        sch_id = parts[0]
        back_cb = parts[1] if len(parts) > 1 else "back"
        from services.schedule_service import ScheduleService
        from ui.keyboards import back
        with next(get_db()) as db:
            result = ScheduleService(db).deactivate_schedule(
                update.effective_user.id, sch_id)
        await reply(update, f"{'✅' if result['success'] else '❌'} {result['message']}",
                    reply_markup=back(back_cb))

    elif data.startswith("setrate_stu_"):
        student_id = data.replace("setrate_stu_", "")
        context.user_data["setting_rate_for"] = student_id
        context.user_data["awaiting_rate_input"] = True
        from ui.keyboards import back
        await reply(update, "💵 *Set Student Rate*\n\nEnter the new hourly rate in ETB:",
                    reply_markup=back(f"stu_detail_{student_id}"))

    elif data.startswith("toggle_active_stu_"):
        from handlers.admin_panel import toggle_active_student
        await toggle_active_student(update, context, data.replace("toggle_active_stu_", ""))

    elif data.startswith("toggle_active_tut_"):
        from handlers.admin_panel import toggle_active_tutor
        await toggle_active_tutor(update, context, data.replace("toggle_active_tut_", ""))

    elif data.startswith("confirm_delete_stu_"):
        from handlers.admin_panel import confirm_delete
        await confirm_delete(update, context, "stu", data.replace("confirm_delete_stu_", ""))

    elif data.startswith("confirm_delete_tut_"):
        from handlers.admin_panel import confirm_delete
        await confirm_delete(update, context, "tut", data.replace("confirm_delete_tut_", ""))

    elif data.startswith("confirm_delete_adm_"):
        from handlers.admin_panel import confirm_delete
        await confirm_delete(update, context, "adm", data.replace("confirm_delete_adm_", ""))

    elif data.startswith("do_delete_stu_"):
        from handlers.admin_panel import do_delete_student
        await do_delete_student(update, context, data.replace("do_delete_stu_", ""))

    elif data.startswith("do_delete_tut_"):
        from handlers.admin_panel import do_delete_tutor
        await do_delete_tutor(update, context, data.replace("do_delete_tut_", ""))

    elif data.startswith("do_delete_adm_"):
        from handlers.admin_panel import do_delete_admin
        await do_delete_admin(update, context, data.replace("do_delete_adm_", ""))

    elif data.startswith("approve_tut_"):
        tutor_id = data.replace("approve_tut_", "")
        from services.registration import RegistrationService
        from ui.keyboards import back
        with next(get_db()) as db:
            result = RegistrationService(db).approve_tutor(tutor_id, update.effective_user.id)
        await reply(update, f"{'✅' if result['success'] else '❌'} {result['message']}",
                    reply_markup=back(f"tut_detail_{tutor_id}"))
        if result.get("telegram_id"):
            await send(context.bot, result["telegram_id"],
                "🎉 *Your tutor application has been approved!*\n\n"
                "Welcome to EduConnect. Use /start to access your dashboard.")
            
    elif data.startswith("claim_review_tut_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        from repositories.user import UserRepository, TutorRepository
        import json
        tutor_id = data.replace("claim_review_tut_", "")
        with next(get_db()) as db:
            user = UserRepository(db).get_by_user_id(tutor_id)
            tut = TutorRepository(db).get(tutor_id)
            if not user or not tut:
                await reply(update, "❌ Tutor not found.")
                return
            full_name = user.full_name
            phone = user.phone
            primary = tut.primary_subjects or "—"
            secondary = tut.secondary_subjects or "—"
            experience = tut.experience or "—"
            max_hours = tut.max_teaching_hours or 3

        admin_user = update.effective_user
        try:
            await query.edit_message_text(
                f"👨‍🏫 *New Tutor Application*\n\n"
                f"Name: *{full_name}*\n"
                f"ID: `{tutor_id}`\n\n"
                f"🔒 Claimed by {admin_user.full_name or admin_user.first_name}",
                parse_mode="Markdown")
        except Exception:
            pass

        await send(context.bot, admin_user.id,
            f"📋 *Tutor Application Review*\n\n"
            f"👨‍🏫 *{full_name}*\n"
            f"{'─'*26}\n"
            f"🆔  `{tutor_id}`\n"
            f"📱  {phone}\n"
            f"★  Primary: {primary}\n"
            f"○  Secondary: {secondary}\n"
            f"🎓  Experience: {experience}\n"
            f"⏱  Max hours/week: {max_hours}\n\n"
            f"Tap below to view the submitted documents.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "📄 Show Documents",
                    callback_data=f"show_docs_tut_{tutor_id}_{admin_user.id}")
            ]]))
        
    elif data.startswith("show_docs_tut_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        from repositories.user import UserRepository, TutorRepository
        import json
        parts = data.replace("show_docs_tut_", "").rsplit("_", 1)
        tutor_id, admin_id = parts[0], parts[1]
        with next(get_db()) as db:
            tut = TutorRepository(db).get(tutor_id)
            doc_file_ids = json.loads(tut.cv_file_ids or "[]") if tut else []

        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        if not doc_file_ids:
            await reply(update, "⚠️ No documents found for this tutor.")
        else:
            for item in doc_file_ids:
                try:
                    ftype, fid, fname = item
                    if ftype == "document":
                        await context.bot.send_document(
                            chat_id=update.effective_user.id,
                            document=fid, caption=fname)
                    else:
                        await context.bot.send_photo(
                            chat_id=update.effective_user.id,
                            photo=fid, caption=f"ID Photo")
                except Exception:
                    pass

        await send(context.bot, update.effective_user.id,
            "📋 *Review Decision*\n\nAll documents sent above. What is your decision?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "✅ Approve Docs",
                    callback_data=f"approve_docs_{tutor_id}")],
                [InlineKeyboardButton(
                    "🔄 Request Re-upload",
                    callback_data=f"reject_docs_{tutor_id}_{admin_id}"),
                 InlineKeyboardButton(
                    "🚫 Reject & Blacklist",
                    callback_data=f"blacklist_docs_{tutor_id}")],
            ]))

    elif data.startswith("approve_docs_"):
        tutor_id = data.replace("approve_docs_", "")
        from services.registration import RegistrationService
        from ui.keyboards import back
        with next(get_db()) as db:
            result = RegistrationService(db).approve_tutor_documents(
                tutor_id, update.effective_user.id)
        await reply(update,
            f"{'✅' if result['success'] else '❌'} "
            f"{result.get('message', 'Documents approved.')}",
            reply_markup=back(f"tut_detail_{tutor_id}"))
        if result.get("telegram_id"):
            await send(context.bot, result["telegram_id"],
                "✅ *Documents Approved!*\n\n"
                "Your CV, transcripts and ID have been verified.\n\n"
                "📹 *Next step:* Please upload a teaching video (30–50 minutes) "
                "of yourself tutoring a subject.\n\n"
                "Send the video file directly in this chat — as a video or as a file attachment.\n\n"
                "_Sent the wrong one? Just send it again — the new one will replace it._\n\n"
                "Use /start any time to see your current status.")

    elif data.startswith("reject_docs_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        parts = data.replace("reject_docs_", "").rsplit("_", 1)
        tutor_id = parts[0]
        admin_id = parts[1] if len(parts) > 1 else str(update.effective_user.id)
        context.user_data["rejecting_docs_tutor"] = tutor_id
        context.user_data["rejecting_docs_admin_id"] = admin_id
        from ui.keyboards import back
        await reply(update,
            "❌ *Reject Documents*\n\n"
            "Type your rejection reason below.\n"
            "Be specific about what documents need to be re-uploaded:",
            reply_markup=back(f"tut_detail_{tutor_id}"))
    
    elif data.startswith("blacklist_docs_"):
        tutor_id = data.replace("blacklist_docs_", "")
        context.user_data["blacklisting_docs_tutor"] = tutor_id
        from ui.keyboards import back
        await reply(update,
            "🚫 *Reject & Blacklist*\n\n"
            "⚠️ This will PERMANENTLY blacklist this tutor.\n"
            "They will never be able to register again.\n\n"
            "State the reason:",
            reply_markup=back(f"tut_detail_{tutor_id}"))
        
    elif data.startswith("request_video_reupload_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        parts = data.replace("request_video_reupload_", "").rsplit("_", 1)
        tutor_id = parts[0]
        admin_id = parts[1] if parts[1] != "0" else str(update.effective_user.id)
        context.user_data["requesting_video_reupload_tutor"] = tutor_id
        context.user_data["requesting_video_reupload_admin_id"] = admin_id
        from ui.keyboards import back
        await reply(update,
            "🔄 *Request Video Re-upload*\n\n"
            "State what is wrong with the video and what needs to be corrected:",
            reply_markup=back(f"tut_detail_{tutor_id}"))

    elif data.startswith("approve_video_"):
        tutor_id = data.replace("approve_video_", "")
        from services.registration import RegistrationService
        from ui.keyboards import back
        with next(get_db()) as db:
            result = RegistrationService(db).approve_tutor_video(
                tutor_id, update.effective_user.id)
        await reply(update,
            f"{'✅' if result['success'] else '❌'} "
            f"{result.get('message', 'Video approved.')}",
            reply_markup=back(f"tut_detail_{tutor_id}"))
        if result.get("telegram_id"):
            await send(context.bot, result["telegram_id"],
                "🎉 *You are fully approved as a tutor!*\n\n"
                "Welcome to EduConnect. An admin will assign students to you.\n"
                "Use /start to access your dashboard.")

    elif data.startswith("claim_review_video_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        from repositories.user import UserRepository, TutorRepository
        tutor_id = data.replace("claim_review_video_", "")
        with next(get_db()) as db:
            user = UserRepository(db).get_by_user_id(tutor_id)
            tut = TutorRepository(db).get(tutor_id)
            if not user or not tut:
                await reply(update, "❌ Tutor not found.")
                return
            full_name = user.full_name
            video_file_id = tut.video_file_id

        admin_user = update.effective_user
        try:
            await query.edit_message_text(
                f"📹 *New Teaching Video Submitted*\n\n"
                f"Tutor: *{full_name}*\n"
                f"ID: `{tutor_id}`\n\n"
                f"🔒 Claimed by {admin_user.full_name or admin_user.first_name}",
                parse_mode="Markdown")
        except Exception:
            pass

        await send(context.bot, admin_user.id,
            f"🎬 *Video Review*\n\n"
            f"Tutor: *{full_name}* (`{tutor_id}`)\n\n"
            f"Tap below to watch the submitted teaching video.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🎬 Show Video",
                    callback_data=f"show_video_tut_{tutor_id}_{admin_user.id}")
            ]]))

    elif data.startswith("show_video_tut_"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        from repositories.user import TutorRepository
        parts = data.replace("show_video_tut_", "").rsplit("_", 1)
        tutor_id = parts[0]
        admin_id = parts[1]

        with next(get_db()) as db:
            tut = TutorRepository(db).get(tutor_id)
            video_file_id = tut.video_file_id if tut else None

        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        if video_file_id:
            try:
                await context.bot.send_video(
                    chat_id=update.effective_user.id,
                    video=video_file_id,
                    caption="📹 Teaching video")
            except Exception:
                await send(context.bot, update.effective_user.id,
                    "⚠️ Could not send the video. It may have expired.")
        else:
            await send(context.bot, update.effective_user.id,
                "⚠️ No video found for this tutor.")

        await send(context.bot, update.effective_user.id,
            "📋 *Review Decision*\n\nVideo sent above. What is your decision?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"approve_video_{tutor_id}")],
                [InlineKeyboardButton(
                    "🔄 Request Re-upload",
                    callback_data=f"request_video_reupload_{tutor_id}_{admin_id}"),
                 InlineKeyboardButton(
                    "🚫 Reject & Blacklist",
                    callback_data=f"reject_video_{tutor_id}")],
            ]))

    elif data.startswith("reject_video_"):
        tutor_id = data.replace("reject_video_", "")
        context.user_data["rejecting_video_tutor"] = tutor_id
        from ui.keyboards import back
        await reply(update,
            "🚫 *Reject Video & Blacklist*\n\n"
            "⚠️ This will PERMANENTLY blacklist this tutor.\n"
            "They will never be able to register again.\n\n"
            "State the reason for rejection:",
            reply_markup=back(f"tut_detail_{tutor_id}"))
        
    elif data.startswith("ack_video_reupload_"):
        parts = data.replace("ack_video_reupload_", "").rsplit("_", 1)
        tutor_id = parts[0]
        admin_id = parts[1]
        context.user_data["video_reupload_admin_id"] = admin_id
        await reply(update,
            "📹 *Send Your New Video*\n\n"
            "Send your new teaching video (30–50 min) directly here as a video or file.\n"
            "It will replace your previous submission.")

    # ── Admin — emergencies / issues ──────────────────────────────────────────
    elif data == "admin_emergencies":
        from handlers.admin_panel import show_emergencies
        await show_emergencies(update, context)

    elif data == "admin_issues":
        from handlers.admin_panel import show_issues
        await show_issues(update, context)

    # ── Claiming: payment ─────────────────────────────────────────────────────
    elif data.startswith("claim_payment_"):
        await _handle_claim_payment(update, context, data.replace("claim_payment_", ""))

    # ── Claiming: emergency/issue ─────────────────────────────────────────────
    elif data.startswith("claim_emergency_"):
        await _handle_claim_emergency(update, context, data.replace("claim_emergency_", ""))

    # ── Payment approval ──────────────────────────────────────────────────────
    elif data.startswith("approve_payment_"):
        await _handle_approve_payment(update, context, data.replace("approve_payment_", ""))

    elif data.startswith("reject_payment_"):
        context.user_data["rejecting_payment"] = data.replace("reject_payment_", "")
        from ui.keyboards import back
        await reply(update, "❌ *Reject Payment*\n\nPlease state the reason:", reply_markup=back())

    elif data.startswith("delete_invoice_"):
        txn_id = data.replace("delete_invoice_", "")
        from repositories.payment import PaymentRepository
        from ui.keyboards import back
        with next(get_db()) as db:
            p = PaymentRepository(db).get_by_transaction(txn_id)
            if p:
                db.delete(p)
                db.commit()
                await reply(update, "🗑️ Invoice deleted.", reply_markup=back("finance_invoices"))
            else:
                await reply(update, "❌ Invoice not found.", reply_markup=back("finance_invoices"))

    # ── Emergency resolve ─────────────────────────────────────────────────────
    elif data.startswith("resolve_emg_"):
        context.user_data["resolving_emergency"] = data.replace("resolve_emg_", "")
        from ui.keyboards import back
        await reply(update,
            f"✅ *Resolve Issue*\n\nDescribe how you resolved it:",
            reply_markup=back())

    # ── Session confirm ────────────────────────────────────────────────────────
    elif data.startswith("do_confirm_"):
        session_id = data.replace("do_confirm_", "")
        from services.confirmation_service import ConfirmationService
        from ui.keyboards import back
        with next(get_db()) as db:
            result = ConfirmationService(db).confirm(update.effective_user.id, session_id)
        if result["success"] and result["completed"]:
            await reply(update, f"✅ *Session {session_id} complete!* 🎉", reply_markup=back())
        elif result["success"]:
            await reply(update,
                f"✅ Confirmed. Waiting for: _{', '.join(result['missing'])}_",
                reply_markup=back())
        else:
            await reply(update, f"❌ {result['message']}", reply_markup=back())

    # ── Emergency type ────────────────────────────────────────────────────────
    elif data == "emergency":
        from ui.keyboards import emergency_type_menu
        await reply(update, "🚨 *Emergency Report*\n\nWhat type of issue is this?",
                    reply_markup=emergency_type_menu())

    elif data.startswith("emg_"):
        from handlers.student import emergency_type_chosen
        await emergency_type_chosen(update, context)

    else:
        logger.warning(f"Unhandled callback: {data}")
        from ui.keyboards import back
        await reply(update, "⚠️ Unknown action. Use /start to return to your dashboard.",
                    reply_markup=back())


# ── Claim handlers ────────────────────────────────────────────────────────────

async def _handle_claim_payment(update, context, transaction_id):
    from services.payment_service import PaymentService
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    with next(get_db()) as db:
        result = PaymentService(db).claim_payment_review(
            update.effective_user.id, transaction_id)
    if not result["success"]:
        await update.callback_query.answer(
            result["message"].replace("*", ""), show_alert=True)
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Payment",
                               callback_data=f"approve_payment_{transaction_id}"),
         InlineKeyboardButton("❌ Reject",
                               callback_data=f"reject_payment_{transaction_id}")],
        [InlineKeyboardButton("🗑️ Delete Invoice",
                               callback_data=f"delete_invoice_{transaction_id}")],
    ])
    try:
        if result.get("screenshot_file_id"):
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=result["screenshot_file_id"],
                caption=f"Payment proof — {result['student_name']}")
        await send(context.bot, update.effective_user.id,
            f"💳 *Payment Review*\n\n"
            f"Student: *{result['student_name']}* (`{result['student_id']}`)\n"
            f"Month: {result['month']}\n"
            f"Amount: {result['amount']:.0f} ETB\n"
            f"TXN: `{result['transaction_id']}`\n\n"
            f"Confirm or reject:",
            reply_markup=keyboard)
        await update.callback_query.answer("Claimed! Check your DM.")
    except Exception as e:
        logger.error(f"Failed to DM admin: {e}")
        await update.callback_query.answer(
            "Couldn't send DM. Start the bot privately first.", show_alert=True)


async def _handle_claim_emergency(update, context, emergency_id):
    from services.emergency_service import EmergencyService
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    with next(get_db()) as db:
        result = EmergencyService(db).claim(update.effective_user.id, emergency_id)
    if not result["success"]:
        await update.callback_query.answer(
            result["message"].replace("*", ""), show_alert=True)
        return
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Mark Resolved",
                              callback_data=f"resolve_emg_{emergency_id}")]])
    try:
        await send(context.bot, update.effective_user.id,
            f"🚨 *Claimed: {emergency_id}*\n\n"
            f"Type: {result['issue_type']}\n"
            f"From: *{result['reporter_name']}*\n"
            f"Session: {result['session_id'] or 'N/A'}\n\n"
            f"*Details:*\n{result['description']}\n\n"
            f"Tap below when resolved:",
            reply_markup=keyboard)
        await update.callback_query.answer("Claimed! Check your DM.")
    except Exception as e:
        logger.error(f"Failed to DM admin: {e}")
        await update.callback_query.answer(
            "Couldn't send DM. Start the bot privately first.", show_alert=True)


async def _handle_approve_payment(update, context, transaction_id):
    from services.payment_service import PaymentService
    with next(get_db()) as db:
        result = PaymentService(db).confirm_payment(update.effective_user.id, transaction_id)
    if not result["success"]:
        from ui.keyboards import back
        await reply(update, f"❌ {result['message']}", reply_markup=back())
        return
    from ui.keyboards import back
    await reply(update,
        f"✅ *Payment Confirmed*\n\n"
        f"Student: {result['student_name']}\n"
        f"Month: {result['month']}\n"
        f"Amount: {result['amount']:.0f} ETB",
        reply_markup=back("finance_invoices"))
    if result.get("student_telegram_id"):
        await send(context.bot, result["student_telegram_id"],
            f"✅ *Payment Confirmed!*\n\n"
            f"Your payment of *{result['amount']:.0f} ETB* for *{result['month']}* "
            f"has been verified.\n\nYour dashboard is now unlocked.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎓 Go to Dashboard", callback_data="back")
        ]]))


# ── Text/photo handlers (outside conversations) ───────────────────────────────

async def handle_payment_screenshot(update, context) -> bool:
    if not context.user_data.get("awaiting_payment_screenshot"):
        return False
    photo = update.message.photo
    if not photo:
        await update.message.reply_text("⚠️ Please send a *photo* screenshot.",
                                         parse_mode="Markdown")
        return True
    file_id = photo[-1].file_id
    context.user_data.pop("awaiting_payment_screenshot", None)
    from services.payment_service import PaymentService
    from config.config import ADMIN_GROUP_CHAT_ID
    from ui.keyboards import claim_payment_button
    with next(get_db()) as db:
        result = PaymentService(db).submit_payment_screenshot(
            update.effective_user.id, file_id)
    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}")
        return True
    from ui.keyboards import back
    await update.message.reply_text(
        "✅ *Screenshot Received!*\n\n"
        "An admin will verify it shortly. You'll be notified once confirmed. 🙏",
        parse_mode="Markdown", reply_markup=back())
    if ADMIN_GROUP_CHAT_ID:
        try:
            await context.bot.send_photo(
                chat_id=ADMIN_GROUP_CHAT_ID, photo=file_id,
                caption=(
                    f"💳 *New Payment Screenshot*\n\n"
                    f"Student: *{result['student_name']}* (`{result['student_id']}`)\n"
                    f"Month: {result['month']}\n"
                    f"Amount: {result['amount']:.0f} ETB\n"
                    f"TXN: `{result['transaction_id']}`"),
                parse_mode="Markdown",
                reply_markup=claim_payment_button(result["transaction_id"]))
        except Exception as e:
            logger.error(f"Failed to send to admin group: {e}")
    return True


async def handle_text_in_context(update, context):
    text = update.message.text.strip()
    if context.user_data.get("resolving_emergency"):
        emergency_id = context.user_data.pop("resolving_emergency")
        from services.emergency_service import EmergencyService
        with next(get_db()) as db:
            result = EmergencyService(db).resolve(update.effective_user.id, emergency_id, text)
        from ui.keyboards import back
        if not result["success"]:
            await update.message.reply_text(f"❌ {result['message']}", reply_markup=back())
            return
        await update.message.reply_text(
            f"✅ *Emergency `{emergency_id}` resolved.*",
            parse_mode="Markdown", reply_markup=back("admin_home"))
        if result.get("reporter_telegram_id"):
            await send(context.bot, result["reporter_telegram_id"],
                f"✅ *Your issue has been resolved*\n\nTicket: `{emergency_id}`\nResolution: {text}")

    elif context.user_data.get("rejecting_docs_tutor"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        tutor_id = context.user_data.pop("rejecting_docs_tutor")
        admin_id = context.user_data.pop("rejecting_docs_admin_id", str(update.effective_user.id))
        from services.registration import RegistrationService
        from ui.keyboards import back
        with next(get_db()) as db:
            result = RegistrationService(db).reject_tutor_documents(
                tutor_id, update.effective_user.id, text)
        await update.message.reply_text(
            "❌ Documents not approved. Tutor has been notified.",
            reply_markup=back(f"tut_detail_{tutor_id}"))
        if result.get("telegram_id"):
            await send(context.bot, result["telegram_id"],
                f"❌ *Documents Not Approved*\n\n"
                f"*Reason from reviewer:*\n{text}\n\n"
                f"Please re-upload the required documents by tapping the button below.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "📤 Re-upload Documents",
                        callback_data=f"reupload_docs_{tutor_id}_{admin_id}")
                ]]))
            
    elif context.user_data.get("blacklisting_docs_tutor"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        tutor_id = context.user_data.pop("blacklisting_docs_tutor")
        from services.registration import RegistrationService
        from ui.keyboards import back
        with next(get_db()) as db:
            result = RegistrationService(db).reject_tutor_documents(
                tutor_id, update.effective_user.id, text)
            from services.tutor_service import TutorService
            TutorService(db).blacklist_tutor(tutor_id, text)
        await update.message.reply_text(
            "🚫 Tutor rejected and permanently blacklisted.",
            reply_markup=back("tutors_filter_all"))
        if result.get("telegram_id"):
            await send(context.bot, result["telegram_id"],
                f"🚫 *Application Rejected*\n\n"
                f"Reason: {text}\n\n"
                f"Unfortunately your application has been permanently rejected. "
                f"You are not able to re-register on this platform.")

    elif context.user_data.get("rejecting_video_tutor"):
        tutor_id = context.user_data.pop("rejecting_video_tutor")
        from services.registration import RegistrationService
        from ui.keyboards import back
        with next(get_db()) as db:
            result = RegistrationService(db).reject_tutor_video(
                tutor_id, update.effective_user.id, text)
        await update.message.reply_text(
            "🚫 Tutor rejected and permanently blacklisted.",
            reply_markup=back("tutors_filter_all"))
        if result.get("telegram_id"):
            await send(context.bot, result["telegram_id"],
                f"🚫 *Application Rejected*\n\n"
                f"Reason: {text}\n\n"
                f"Unfortunately your application has been permanently rejected. "
                f"You are not able to re-register on this platform.")
            
    elif context.user_data.get("requesting_video_reupload_tutor"):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        tutor_id = context.user_data.pop("requesting_video_reupload_tutor")
        admin_id = context.user_data.pop("requesting_video_reupload_admin_id", str(update.effective_user.id))
        from repositories.user import UserRepository, TutorRepository
        with next(get_db()) as db:
            user = UserRepository(db).get_by_user_id(tutor_id)
            telegram_id = user.telegram_id if user else None
        from ui.keyboards import back
        await update.message.reply_text(
            "🔄 Tutor notified to re-upload their video.",
            reply_markup=back(f"tut_detail_{tutor_id}"))
        if telegram_id:
            await send(context.bot, telegram_id,
                f"🔄 *Video Re-upload Required*\n\n"
                f"*Feedback from reviewer:*\n{text}\n\n"
                f"Please send a new teaching video (30–50 minutes) directly in this chat.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "📹 I understand, let me re-upload",
                        callback_data=f"ack_video_reupload_{tutor_id}_{admin_id}")
                ]]))

    elif context.user_data.get("rejecting_payment"):
        transaction_id = context.user_data.pop("rejecting_payment")
        from services.payment_service import PaymentService
        with next(get_db()) as db:
            result = PaymentService(db).reject_payment(
                update.effective_user.id, transaction_id, text)
        from ui.keyboards import back
        await update.message.reply_text(
            "❌ Payment rejected. Student has been notified.",
            reply_markup=back("finance_invoices"))
        if result.get("student_telegram_id"):
            await send(context.bot, result["student_telegram_id"],
                f"❌ *Payment Not Confirmed*\n\nReason: {text}\n\n"
                f"Please re-upload a clear screenshot or contact an admin.")


# ── Help ──────────────────────────────────────────────────────────────────────

async def _show_help(update, context, role):
    from ui.keyboards import back
    if role == "student":
        text = (
            "❓ *Student Help*\n\n"
            "📅 *My Sessions* — View upcoming & past sessions\n"
            "📆 *My Schedule* — Your weekly recurring schedule\n"
            "💳 *Payments* — Invoices and payment status\n"
            "📝 *Report Issue* — Report a problem\n"
            "🚨 *Emergency* — Urgent issues\n\n"
            "After each session:\n"
            "Use ✅ *Confirm* button on your dashboard"
        )
    elif role == "tutor":
        text = (
            "❓ *Tutor Help*\n\n"
            "📅 *My Sessions* — View upcoming & past sessions\n"
            "📆 *My Schedule* — Your teaching schedule\n"
            "💰 *Earnings* — Payouts and earnings history\n"
            "📹 *Upload Recording* — Upload session recording\n"
            "✅ *Confirm Session* — Confirm you taught a session\n\n"
            "When prompted, tap 🔗 *Submit Zoom Link* to send your link\n"
            "Use ✅ *Confirm* button to confirm sessions"
        )
    elif role == "admin":
        text = (
            "❓ *Admin Help*\n\n"
            "👥 *Students* — View, edit, assign tutors, manage payments\n"
            "👨‍🏫 *Tutors* — View, edit, approve, manage schedules\n"
            "👑 *Admins* — Add/remove admins\n"
            "💰 *Finance* — Invoices, payouts\n"
            "🚨 *Emergencies* — Urgent issues\n"
            "⚠️ *Issues* — Non-urgent reports\n"
            "📊 *Overview* — System stats\n\n"
            "Useful commands:\n"
            "All actions available through dashboard buttons\n"
            "Use ⚠️ Issues / 🚨 Emergencies to handle reports"
        )
    else:
        text = (
            "❓ *Help*\n\n"
            "Register as a *Student* or *Tutor* using the buttons below.\n\n"
            "Already registered? Use /start."
        )
    await reply(update, text, reply_markup=back())


async def _myid(update, user):
    from ui.keyboards import back
    if user:
        await reply(update,
            f"🆔 Platform ID: `{user.user_id}`\n📱 Telegram ID: `{user.telegram_id}`",
            reply_markup=back())
    else:
        await reply(update,
            f"📱 Telegram ID: `{update.effective_user.id}`",
            reply_markup=back())


def _locked_menu():
    from ui.keyboards import student_locked_menu
    return student_locked_menu()