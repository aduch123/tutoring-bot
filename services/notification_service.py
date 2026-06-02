"""All automated notifications and scheduler jobs."""
import logging
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from config.db import SessionLocal
from config.config import ADMIN_GROUP_CHAT_ID

logger = logging.getLogger(__name__)


def _kb(rows): return InlineKeyboardMarkup(rows)


async def _safe_send(bot, chat_id, text, reply_markup=None):
    from utils.retry import safe_send
    await safe_send(bot, chat_id, text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True)


async def _notify_admin_group(bot, text, reply_markup=None):
    if ADMIN_GROUP_CHAT_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_GROUP_CHAT_ID, text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
                disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Admin group notify failed: {e}")


# ── Session generation ────────────────────────────────────────────────────────

_last_session_generation_date = None

async def job_generate_sessions():
    """Daily: generate session rows for next 7 days (paid students only).
    Guard against duplicate runs on the same calendar day (e.g. on bot restart).
    """
    global _last_session_generation_date
    today = datetime.now().date()
    if _last_session_generation_date == today:
        logger.info("[Scheduler] job_generate_sessions: already ran today, skipping.")
        return
    _last_session_generation_date = today

    from services.schedule_service import ScheduleService
    from services.payment_service import PaymentService
    with SessionLocal() as db:
        pay_svc = PaymentService(db)
        svc = ScheduleService(db)
        # Only generate for students who have paid
        from models.user import User
        students = db.query(User).filter(User.role == "student", User.is_active == True).all()
        paid_student_ids = set()
        for s in students:
            if pay_svc.is_student_unlocked(s.user_id):
                paid_student_ids.add(s.user_id)
        count = svc.generate_sessions_for_window(days_ahead=7,
                                                   allowed_student_ids=paid_student_ids)
        logger.info(f"[Scheduler] Generated {count} new sessions")


# ── Zoom link requests ────────────────────────────────────────────────────────

async def job_request_zoom_links(bot: Bot):
    """Hourly: request Zoom links from tutors 24hrs before session."""
    from models.schedule import Session as SM
    from repositories.user import UserRepository
    with SessionLocal() as db:
        now = datetime.now()
        window_start = now + timedelta(hours=23.5)
        window_end = now + timedelta(hours=24.5)
        sessions = db.query(SM).filter(
            SM.scheduled_start >= window_start,
            SM.scheduled_start <= window_end,
            SM.status == "scheduled",
            SM.zoom_link == None,
        ).all()
        repo = UserRepository(db)
        for s in sessions:
            tutor = repo.get_by_user_id(s.tutor_id)
            if tutor:
                try:
                    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                    zoom_kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔗 Submit Zoom Link",
                            callback_data=f"zoom_request_{s.session_id}")
                    ]])
                    await _safe_send(bot, tutor.telegram_id,
                        f"📋 *Zoom Link Required*\n\n"
                        f"You have a session tomorrow:\n\n"
                        f"📚 {s.subject}\n"
                        f"🕐 {s.scheduled_start.strftime('%a %d %b · %H:%M')} – "
                        f"{s.scheduled_end.strftime('%H:%M')}\n\n"
                        f"Tap the button below to submit your Zoom link.",
                        reply_markup=zoom_kb)
                    s.status = "zoom_pending"
                    s.zoom_requested_at = now
                except Exception as e:
                    logger.error(f"Zoom request failed for tutor {tutor.telegram_id}: {e}")
        db.commit()


# ── Zoom deadline check ───────────────────────────────────────────────────────

async def job_zoom_deadline_check(bot: Bot):
    """Every 15 mins: urgent alert if no zoom link 1hr before session."""
    from models.schedule import Session as SM
    from repositories.user import UserRepository
    from ui.keyboards import claim_emergency_button
    with SessionLocal() as db:
        now = datetime.now()
        window_start = now + timedelta(minutes=45)
        window_end = now + timedelta(minutes=75)
        sessions = db.query(SM).filter(
            SM.scheduled_start >= window_start,
            SM.scheduled_start <= window_end,
            SM.zoom_link == None,
            SM.status.in_(["scheduled", "zoom_pending"]),
        ).all()
        repo = UserRepository(db)
        for s in sessions:
            tutor = repo.get_by_user_id(s.tutor_id)
            student = repo.get_by_user_id(s.student_id)
            if tutor:
                await _safe_send(bot, tutor.telegram_id,
                    f"🚨 *URGENT — No Zoom Link*\n\n"
                    f"Session starts in ~1 hour!\n\n"
                    f"📚 {s.subject} with {student.full_name if student else 'student'}\n"
                    f"🕐 {s.scheduled_start.strftime('%H:%M')}\n\n"
                    f"Tap below to submit your link immediately!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔗 Submit Zoom Link NOW",
                            callback_data=f"zoom_request_{s.session_id}")
                    ]]))
            await _notify_admin_group(bot,
                f"⚠️ *No Zoom Link — Session in 1 Hour*\n\n"
                f"Session: `{s.session_id}`\n"
                f"Tutor: {tutor.full_name if tutor else s.tutor_id}\n"
                f"Student: {student.full_name if student else s.student_id}\n"
                f"Time: {s.scheduled_start.strftime('%H:%M')}")


# ── Session start confirmation (5 mins before) ───────────────────────────────

async def job_session_start_confirmation(bot: Bot):
    """Every 5 mins: send start confirmation 5 mins before session."""
    from models.schedule import Session as SM
    from repositories.user import UserRepository
    with SessionLocal() as db:
        now = datetime.now()
        window_start = now + timedelta(minutes=3)
        window_end = now + timedelta(minutes=7)
        sessions = db.query(SM).filter(
            SM.scheduled_start >= window_start,
            SM.scheduled_start <= window_end,
            SM.status == "zoom_ready",
            SM.tutor_start_confirmed == False,
        ).all()
        repo = UserRepository(db)
        for s in sessions:
            tutor = repo.get_by_user_id(s.tutor_id)
            student = repo.get_by_user_id(s.student_id)
            confirm_kb = _kb([[
                InlineKeyboardButton("✅ I'm in the session",
                                     callback_data=f"start_confirm_{s.session_id}"),
                InlineKeyboardButton("❌ I can't attend",
                                     callback_data=f"start_decline_{s.session_id}"),
            ]])
            if tutor:
                await _safe_send(bot, tutor.telegram_id,
                    f"⏰ *Session starts in 5 minutes!*\n\n"
                    f"📚 {s.subject}\n"
                    f"👤 Student: {student.full_name if student else 'your student'}\n"
                    f"🕐 {s.scheduled_start.strftime('%H:%M')}\n\n"
                    f"Are you ready?",
                    reply_markup=confirm_kb)
            if student:
                await _safe_send(bot, student.telegram_id,
                    f"⏰ *Session starts in 5 minutes!*\n\n"
                    f"📚 {s.subject}\n"
                    f"👨‍🏫 Tutor: {tutor.full_name if tutor else 'your tutor'}\n"
                    f"🕐 {s.scheduled_start.strftime('%H:%M')}\n"
                    + (f"🔗 [Join Zoom]({s.zoom_link})" if s.zoom_link else ""),
                    reply_markup=_kb([[
                        InlineKeyboardButton("✅ I'm in the session",
                                             callback_data=f"start_confirm_stu_{s.session_id}"),
                        InlineKeyboardButton("❌ I can't attend",
                                             callback_data=f"start_decline_stu_{s.session_id}"),
                    ]]))


# ── Check tutor start no-response ────────────────────────────────────────────

async def job_check_tutor_start_response(bot: Bot):
    """Every 15 mins: flag sessions where tutor didn't confirm start."""
    from models.schedule import Session as SM
    from repositories.user import UserRepository
    from ui.keyboards import claim_emergency_button
    with SessionLocal() as db:
        now = datetime.now()
        # Sessions that started 10+ mins ago and tutor hasn't confirmed
        cutoff = now - timedelta(minutes=10)
        sessions = db.query(SM).filter(
            SM.scheduled_start <= cutoff,
            SM.scheduled_start >= now - timedelta(hours=2),
            SM.status == "zoom_ready",
            SM.tutor_start_confirmed == False,
        ).all()
        repo = UserRepository(db)
        for s in sessions:
            s.status = "tutor_absent"
            tutor = repo.get_by_user_id(s.tutor_id)
            student = repo.get_by_user_id(s.student_id)
            if student:
                await _safe_send(bot, student.telegram_id,
                    f"⚠️ *Session Issue*\n\n"
                    f"Your tutor hasn't confirmed attendance for the {s.subject} session.\n"
                    f"An admin has been notified and is working on a solution.")
            await _notify_admin_group(bot,
                f"🚨 *Tutor Did Not Confirm Session Start*\n\n"
                f"Session: `{s.session_id}`\n"
                f"Subject: {s.subject}\n"
                f"Tutor: {tutor.full_name if tutor else s.tutor_id}\n"
                f"Student: {student.full_name if student else s.student_id}\n"
                f"Time: {s.scheduled_start.strftime('%H:%M')}\n\n"
                f"Please assign a replacement tutor or contact the tutor.",
                reply_markup=_kb([[
                    InlineKeyboardButton("🔄 Assign Replacement",
                                         callback_data=f"assign_replacement_{s.session_id}")
                ]]))
        db.commit()


# ── Session end confirmation ──────────────────────────────────────────────────

async def job_session_end_confirmation(bot: Bot):
    """Every 5 mins: send end confirmation at session end time."""
    from models.schedule import Session as SM
    from repositories.user import UserRepository
    with SessionLocal() as db:
        now = datetime.now()
        window_start = now - timedelta(minutes=5)
        window_end = now + timedelta(minutes=5)
        sessions = db.query(SM).filter(
            SM.scheduled_end >= window_start,
            SM.scheduled_end <= window_end,
            SM.status == "in_progress",
            SM.tutor_confirmed == False,
        ).all()
        repo = UserRepository(db)
        for s in sessions:
            tutor = repo.get_by_user_id(s.tutor_id)
            student = repo.get_by_user_id(s.student_id)
            if tutor:
                await _safe_send(bot, tutor.telegram_id,
                    f"✅ *Session Ended*\n\n"
                    f"Did you complete the {s.subject} session?\n\n"
                    f"After confirming, please upload the recording within 24 hours.",
                    reply_markup=_kb([[
                        InlineKeyboardButton("✅ Yes, completed",
                                             callback_data=f"end_confirm_tut_{s.session_id}"),
                        InlineKeyboardButton("❌ Issue occurred",
                                             callback_data=f"end_issue_{s.session_id}"),
                    ]]))
            if student:
                await _safe_send(bot, student.telegram_id,
                    f"✅ *Session Ended*\n\n"
                    f"Did your {s.subject} session complete successfully?",
                    reply_markup=_kb([[
                        InlineKeyboardButton("✅ Yes, completed",
                                             callback_data=f"end_confirm_stu_{s.session_id}"),
                        InlineKeyboardButton("❌ There was an issue",
                                             callback_data=f"end_issue_stu_{s.session_id}"),
                    ]]))


# ── Recording upload reminder ─────────────────────────────────────────────────

async def job_recording_reminder(bot: Bot):
    """Every 6 hrs: remind tutors to upload recording."""
    from models.schedule import Session as SM
    from repositories.user import UserRepository
    with SessionLocal() as db:
        now = datetime.now()
        cutoff = now - timedelta(hours=6)
        sessions = db.query(SM).filter(
            SM.status == "in_progress",
            SM.tutor_confirmed == True,
            SM.student_confirmed == True,
            SM.recording_path == None,
            SM.scheduled_end <= cutoff,
        ).all()
        repo = UserRepository(db)
        for s in sessions:
            tutor = repo.get_by_user_id(s.tutor_id)
            hours_since = (now - s.scheduled_end).seconds // 3600
            if tutor:
                await _safe_send(bot, tutor.telegram_id,
                    f"⚠️ *Recording Not Uploaded*\n\n"
                    f"Session `{s.session_id}` ended {hours_since}h ago.\n"
                    f"Please upload the recording:\n"
                    f"Tap 📹 Upload Recording on your dashboard.")
            # After 24hrs notify admin
            if hours_since >= 24:
                await _notify_admin_group(bot,
                    f"⚠️ *Tutor Hasn't Uploaded Recording*\n\n"
                    f"Session: `{s.session_id}` — {s.subject}\n"
                    f"Tutor: {tutor.full_name if tutor else s.tutor_id}\n"
                    f"Ended: {s.scheduled_end.strftime('%d %b %H:%M')}")


# ── Payment reminders ─────────────────────────────────────────────────────────

async def job_payment_reminders(bot: Bot):
    """Daily: notify students approaching payment due date."""
    from models.user import User, Student
    from services.payment_service import PaymentService
    with SessionLocal() as db:
        now = datetime.now()
        students = db.query(Student).all()
        pay_svc = PaymentService(db)
        for stu in students:
            if not stu.next_payment_due:
                continue
            days_until = (stu.next_payment_due - now).days
            user = db.query(User).filter(User.user_id == stu.user_id).first()
            if not user or not user.is_active:
                continue
            if days_until in (5, 3, 1):
                rate = pay_svc.get_student_rate(stu.user_id)
                monthly = (stu.days_per_week or 3) * 4 * rate
                await _safe_send(bot, user.telegram_id,
                    f"💳 *Payment Reminder*\n\n"
                    f"Your monthly payment of *{monthly:.0f} ETB* is due in "
                    f"*{days_until} day{'s' if days_until > 1 else ''}*.\n\n"
                    f"Please pay on time to keep your sessions active.\n"
                    f"Tap 💳 Payments to upload your proof.")
            elif days_until == 0:
                await _safe_send(bot, user.telegram_id,
                    f"💳 *Payment Due Today*\n\n"
                    f"Your payment is due today.\n"
                    f"Please complete payment to avoid session suspension.")
            elif days_until < 0 and not pay_svc.is_student_unlocked(stu.user_id):
                # Lock dashboard and cancel sessions
                await _handle_overdue_student(bot, db, stu, user, pay_svc)


async def _handle_overdue_student(bot, db, stu, user, pay_svc):
    """Cancel future sessions for overdue student."""
    from models.schedule import Session as SM, Schedule
    if pay_svc.is_student_unlocked(stu.user_id):
        return
    future_sessions = db.query(SM).filter(
        SM.student_id == stu.user_id,
        SM.status.in_(["scheduled", "zoom_pending", "zoom_ready"]),
        SM.scheduled_start > datetime.now(),
    ).all()
    for s in future_sessions:
        s.status = "cancelled"
    db.commit()
    if future_sessions:
        await _safe_send(bot, user.telegram_id,
            f"🔒 *Sessions Suspended*\n\n"
            f"Your payment is overdue. Your upcoming sessions have been paused.\n\n"
            f"Please complete your payment to resume sessions.\n"
            f"Tap 💳 Payments on your dashboard.")


# ── Mark missed sessions ──────────────────────────────────────────────────────

async def job_mark_missed_sessions():
    """Hourly: mark past sessions that were never started."""
    from models.schedule import Session as SM
    with SessionLocal() as db:
        now = datetime.now()
        missed = db.query(SM).filter(
            SM.scheduled_end < now,
            SM.status.in_(["scheduled", "zoom_pending"]),
        ).all()
        for s in missed:
            s.status = "missed"
        db.commit()
        if missed:
            logger.info(f"[Scheduler] Marked {len(missed)} sessions as missed")


async def notify_admin_group(bot: Bot, text: str, reply_markup=None):
    await _notify_admin_group(bot, text, reply_markup)
