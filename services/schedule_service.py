"""
Manages recurring schedules and generates concrete Sessions from them.
"""
from datetime import datetime, timedelta, date, time
from sqlalchemy.orm import Session as DBSession
from repositories.schedule import ScheduleRepository, SessionRepository
from repositories.user import UserRepository
from services.id_generator import IDGenerator
from services.admin_service import AdminService

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _parse_days(days_str: str):
    """'0,1,4' → [0, 1, 4]"""
    return [int(d.strip()) for d in days_str.split(",") if d.strip().isdigit()]


def _day_label(days_str: str) -> str:
    days = _parse_days(days_str)
    return ", ".join(DAY_NAMES[d] for d in days)


class ScheduleService:
    def __init__(self, db: DBSession):
        self.db = db
        self.schedules = ScheduleRepository(db)
        self.sessions = SessionRepository(db)
        self.users = UserRepository(db)

    # ── Admin: create schedule ──────────────────────────────────────────────

    def create_schedule(self, admin_telegram_id: int, student_id: str, tutor_id: str,
                        subject: str, days_str: str, start_time: time, end_time: time,
                        notes: str = None) -> dict:
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}

        student = self.users.get_by_user_id(student_id)
        if not student or student.role != "student":
            return {"success": False, "message": f"Student {student_id} not found."}

        tutor = self.users.get_by_user_id(tutor_id)
        if not tutor or tutor.role != "tutor" or not tutor.is_verified:
            return {"success": False, "message": f"Tutor {tutor_id} not found or not verified."}

        admin = self.users.get_by_telegram_id(admin_telegram_id)
        sch_id = IDGenerator.schedule_id(self.db)

        schedule = self.schedules.create({
            "schedule_id": sch_id,
            "student_id": student_id,
            "tutor_id": tutor_id,
            "subject": subject,
            "days_of_week": days_str,
            "start_time": start_time,
            "end_time": end_time,
            "is_active": True,
            "created_by": admin.user_id if admin else "system",
            "notes": notes,
        })

        return {
            "success": True,
            "schedule_id": sch_id,
            "student": student.full_name,
            "tutor": tutor.full_name,
            "subject": subject,
            "days": _day_label(days_str),
            "time": f"{start_time.strftime('%H:%M')} – {end_time.strftime('%H:%M')}",
        }

    def deactivate_schedule(self, admin_telegram_id: int, schedule_id: str) -> dict:
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        sch = self.schedules.get(schedule_id)
        if not sch:
            return {"success": False, "message": f"Schedule {schedule_id} not found."}
        self.schedules.deactivate(schedule_id)
        # Cancel future sessions
        from models.schedule import Session as SM
        future = (
            self.db.query(SM)
            .filter(SM.schedule_id == schedule_id,
                    SM.status.in_(["scheduled", "zoom_pending", "zoom_ready"]),
                    SM.scheduled_start > datetime.now())
            .all()
        )
        for s in future:
            s.status = "cancelled"
        self.db.commit()
        return {"success": True, "message": f"Schedule {schedule_id} deactivated."}

    # ── Session generation (called by scheduler daily) ──────────────────────

    def generate_sessions_for_window(self, days_ahead: int = 7, allowed_student_ids: set = None) -> int:
        """
        For every active schedule, generate Session rows for occurrences
        within the next `days_ahead` days that don't already exist.
        Returns count of new sessions created.
        """
        from models.schedule import Session as SM
        now = datetime.now()
        window_end = now + timedelta(days=days_ahead)
        created = 0

        for sch in self.schedules.get_all_active():
            if allowed_student_ids is not None and sch.student_id not in allowed_student_ids:
                continue
            days = _parse_days(sch.days_of_week)
            # Walk through each day in the window
            cursor = now.date()
            while cursor <= window_end.date():
                if cursor.weekday() in days:
                    start_dt = datetime.combine(cursor, sch.start_time)
                    end_dt = datetime.combine(cursor, sch.end_time)
                    if start_dt > now:
                        # Check if session already exists
                        exists = self.db.query(SM).filter(
                            SM.schedule_id == sch.schedule_id,
                            SM.scheduled_start == start_dt,
                        ).first()
                        if not exists:
                            ses_id = IDGenerator.session_id(self.db)
                            self.sessions.create({
                                "session_id": ses_id,
                                "schedule_id": sch.schedule_id,
                                "student_id": sch.student_id,
                                "tutor_id": sch.tutor_id,
                                "subject": sch.subject,
                                "scheduled_start": start_dt,
                                "scheduled_end": end_dt,
                                "status": "scheduled",
                            })
                            created += 1
                cursor += timedelta(days=1)

        return created

    # ── Getters ─────────────────────────────────────────────────────────────

    def get_student_schedules(self, student_id: str) -> list:
        scheds = self.schedules.get_by_student(student_id)
        result = []
        for s in scheds:
            tutor = self.users.get_by_user_id(s.tutor_id)
            result.append({
                "schedule_id": s.schedule_id,
                "subject": s.subject,
                "tutor_name": tutor.full_name if tutor else s.tutor_id,
                "days": _day_label(s.days_of_week),
                "time": f"{s.start_time.strftime('%H:%M')} – {s.end_time.strftime('%H:%M')}",
                "is_active": s.is_active,
            })
        return result

    def get_tutor_schedules(self, tutor_id: str) -> list:
        scheds = self.schedules.get_by_tutor(tutor_id)
        result = []
        for s in scheds:
            student = self.users.get_by_user_id(s.student_id)
            result.append({
                "schedule_id": s.schedule_id,
                "subject": s.subject,
                "student_name": student.full_name if student else s.student_id,
                "days": _day_label(s.days_of_week),
                "time": f"{s.start_time.strftime('%H:%M')} – {s.end_time.strftime('%H:%M')}",
                "is_active": s.is_active,
            })
        return result

    def _week_end(self) -> datetime:
        """Get end of current week (Sunday 23:59)."""
        now = datetime.now()
        days_until_sunday = 6 - now.weekday()
        return (now + timedelta(days=days_until_sunday)).replace(
            hour=23, minute=59, second=59)

    def get_student_upcoming_sessions(self, student_id: str,
                                       limit: int = 5,
                                       this_week_only: bool = True) -> list:
        from models.schedule import Session as SM
        now = datetime.now()
        week_end = self._week_end() if this_week_only else now + timedelta(days=365)
        rows = (
            self.db.query(SM)
            .filter(SM.student_id == student_id,
                    SM.scheduled_start >= now,
                    SM.scheduled_start <= week_end,
                    SM.status.in_(["scheduled", "zoom_pending", "zoom_ready", "in_progress"]))
            .order_by(SM.scheduled_start)
            .limit(limit)
            .all()
        )
        result = []
        for s in rows:
            tutor = self.users.get_by_user_id(s.tutor_id)
            result.append({
                "session_id": s.session_id,
                "subject": s.subject,
                "tutor_name": tutor.full_name if tutor else s.tutor_id,
                "start": s.scheduled_start.strftime("%a %d %b · %H:%M"),
                "end": s.scheduled_end.strftime("%H:%M"),
                "status": s.status,
                "zoom_link": s.zoom_link,
            })
        return result

    def get_student_all_upcoming_sessions(self, student_id: str, limit: int = 20) -> list:
        """Extended view — next 2 weeks, used in My Sessions screen."""
        return self.get_student_upcoming_sessions(
            student_id, limit=limit, this_week_only=False)

    def get_tutor_upcoming_sessions(self, tutor_id: str,
                                     limit: int = 10,
                                     this_week_only: bool = True) -> list:
        from models.schedule import Session as SM
        now = datetime.now()
        week_end = self._week_end() if this_week_only else now + timedelta(days=365)
        rows = (
            self.db.query(SM)
            .filter(SM.tutor_id == tutor_id,
                    SM.scheduled_start >= now,
                    SM.scheduled_start <= week_end,
                    SM.status.in_(["scheduled", "zoom_pending", "zoom_ready", "in_progress"]))
            .order_by(SM.scheduled_start)
            .limit(limit)
            .all()
        )
        result = []
        for s in rows:
            student = self.users.get_by_user_id(s.student_id)
            result.append({
                "session_id": s.session_id,
                "subject": s.subject,
                "student_name": student.full_name if student else s.student_id,
                "start": s.scheduled_start.strftime("%a %d %b · %H:%M"),
                "end": s.scheduled_end.strftime("%H:%M"),
                "status": s.status,
                "zoom_link": s.zoom_link,
            })
        return result

    def get_tutor_all_upcoming_sessions(self, tutor_id: str, limit: int = 20) -> list:
        """Extended view — next 2 weeks."""
        return self.get_tutor_upcoming_sessions(
            tutor_id, limit=limit, this_week_only=False)

    def submit_zoom_link(self, tutor_telegram_id: int, session_id: str, link: str) -> dict:
        ses = self.sessions.get(session_id)
        if not ses:
            return {"success": False, "message": f"Session {session_id} not found."}
        tutor = self.users.get_by_telegram_id(tutor_telegram_id)
        if not tutor or tutor.user_id != ses.tutor_id:
            return {"success": False, "message": "You are not the assigned tutor."}
        if not link.startswith("http"):
            return {"success": False, "message": "Please send a valid Zoom link (must start with http)."}
        self.sessions.set_zoom_link(session_id, link)
        student = self.users.get_by_user_id(ses.student_id)
        return {
            "success": True,
            "session_id": session_id,
            "student_telegram_id": student.telegram_id if student else None,
            "student_name": student.full_name if student else "Student",
            "subject": ses.subject,
            "start": ses.scheduled_start.strftime("%a %d %b · %H:%M"),
            "zoom_link": link,
        }
