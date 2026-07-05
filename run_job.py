"""Manual job trigger for testing."""
import asyncio
import sys
from telegram import Bot
from config.config import BOT_TOKEN

async def main(job_name: str):
    bot = Bot(token=BOT_TOKEN)

    if job_name == "reminders":
        from services.notification_service import job_payment_reminders
        await job_payment_reminders(bot)
        print("✅ Payment reminders job ran")
    elif job_name == "sessions":
        from services.notification_service import job_generate_sessions
        await job_generate_sessions()
        print("✅ Session generation job ran")
    elif job_name == "zoom":
        from services.notification_service import job_request_zoom_links
        await job_request_zoom_links(bot)
        print("✅ Zoom link request job ran")
    elif job_name == "missed":
        from services.notification_service import job_mark_missed_sessions
        await job_mark_missed_sessions()
        print("✅ Missed sessions job ran")
    elif job_name == "zoom_deadline":
        from services.notification_service import job_zoom_deadline_check
        await job_zoom_deadline_check(bot)
        print("✅ Zoom deadline check job ran")
    elif job_name == "start_confirm":
        from services.notification_service import job_session_start_confirmation
        await job_session_start_confirmation(bot)
        print("✅ Session start confirmation job ran")
    elif job_name == "tutor_response":
        from services.notification_service import job_check_tutor_start_response
        await job_check_tutor_start_response(bot)
        print("✅ Tutor start response check job ran")
    elif job_name == "end_confirm":
        from services.notification_service import job_session_end_confirmation
        await job_session_end_confirmation(bot)
        print("✅ Session end confirmation job ran")
    elif job_name == "recording_reminder":
        from services.notification_service import job_recording_reminder
        await job_recording_reminder(bot)
        print("✅ Recording reminder job ran")
    else:
        print(f"Unknown job: {job_name}")
        print("Available: reminders, sessions, zoom, missed, zoom_deadline, start_confirm, tutor_response, end_confirm, recording_reminder")

asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "reminders"))