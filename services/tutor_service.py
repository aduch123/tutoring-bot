"""Tutor capacity, availability, and assignment logic."""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from models.schedule import Schedule
from repositories.user import UserRepository, TutorRepository
from repositories.schedule import ScheduleRepository

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TutorService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.tutors = TutorRepository(db)
        self.schedules = ScheduleRepository(db)

    def get_weekly_assigned_hours(self, tutor_id: str) -> int:
        """Count total assigned hours per week (each session = 1 hour)."""
        active_scheds = self.schedules.get_by_tutor(tutor_id, active_only=True)
        total_hours = 0
        for s in active_scheds:
            # Count number of days in schedule = number of sessions per week
            days = [d for d in s.days_of_week.split(",") if d.strip().isdigit()]
            total_hours += len(days)
        return total_hours

    def get_weekly_assigned_days(self, tutor_id: str) -> int:
        """Legacy — returns hours now."""
        return self.get_weekly_assigned_hours(tutor_id)

    def is_tutor_full(self, tutor_id: str) -> bool:
        """True if tutor's assigned hours >= their max_teaching_hours."""
        tut = self.tutors.get(tutor_id)
        if not tut:
            return False
        max_hours = tut.max_teaching_hours or 3
        assigned = self.get_weekly_assigned_hours(tutor_id)
        return assigned >= max_hours

    def get_tutor_status(self, tutor_id: str) -> str:
        """Returns: available | full | suspended | pending | blacklisted"""
        tut = self.tutors.get(tutor_id)
        user = self.users.get_by_user_id(tutor_id)
        if not tut or not user:
            return "unknown"
        if tut.is_blacklisted:
            return "blacklisted"
        if not user.is_active:
            return "suspended"
        if tut.approval_status != "approved":
            return "pending"
        if self.is_tutor_full(tutor_id):
            return "full"
        return "available"

    def get_available_tutors_for_subject(self, subject: str, include_full: bool = False,
                                      exclude_tutor_id: str = None) -> list:
        """
        Returns tutors who can teach the given subject.
        Marks each as primary/secondary match and available/full.
        """
        from models.user import User, Tutor
        tutors = (
            self.db.query(Tutor)
            .join(User, Tutor.user_id == User.user_id)
            .filter(
                User.is_active == True,
                User.is_verified == True,
                Tutor.approval_status == "approved",
                Tutor.is_blacklisted == False,
            )
            .all()
        )

        result = []
        subj_lower = subject.lower()

        for tut in tutors:
            if exclude_tutor_id and tut.user_id == exclude_tutor_id:
                continue
            user = self.users.get_by_user_id(tut.user_id)
            primary = [s.strip() for s in (tut.primary_subjects or "").split(",") if s.strip()]
            secondary = [s.strip() for s in (tut.secondary_subjects or "").split(",") if s.strip()]

            primary_lower = [s.lower() for s in primary]
            secondary_lower = [s.lower() for s in secondary]

            match_type = None
            if any(subj_lower in p or p in subj_lower for p in primary_lower):
                match_type = "primary"
            elif any(subj_lower in s or s in subj_lower for s in secondary_lower):
                match_type = "secondary"

            if not match_type:
                continue

            status = self.get_tutor_status(tut.user_id)
            assigned_days = self.get_weekly_assigned_days(tut.user_id)
            max_days = tut.max_teaching_hours or 3

            if status == "full" and not include_full:
                continue

            # Get students already assigned to this tutor
            assigned_scheds = self.schedules.get_by_tutor(tut.user_id, active_only=True)
            assigned_student_ids = list(set(s.student_id for s in assigned_scheds))

            result.append({
                "user_id": tut.user_id,
                "full_name": user.full_name if user else tut.user_id,
                "phone": user.phone if user else "—",
                "primary_subjects": primary,
                "secondary_subjects": secondary,
                "match_type": match_type,
                "status": status,
                "assigned_hours": assigned_days,
                "max_hours": max_days,
                "load": f"{assigned_days}/{max_days}h/week",
                "assigned_students": len(assigned_student_ids),
                "assigned_hours": self.db.query(Schedule).filter(
                    Schedule.tutor_id == tut.user_id,
                    Schedule.is_active == True
                ).count(),
            })

        # Sort: primary matches first, then by load (least assigned first)
        result.sort(key=lambda x: (
            0 if x["match_type"] == "primary" else 1,
            x["assigned_hours"]
        ))
        return result

    def is_tutor_assigned_to_student(self, tutor_id: str, student_id: str) -> bool:
        """Check if this tutor already has an active schedule with this student."""
        scheds = self.schedules.get_by_tutor(tutor_id, active_only=True)
        return any(s.student_id == student_id for s in scheds)

    def get_student_tutor_for_subject(self, student_id: str, subject: str):
        """Get the tutor assigned to teach a specific subject to this student."""
        scheds = self.schedules.get_by_student(student_id, active_only=True)
        subj_lower = subject.lower()
        for s in scheds:
            if subj_lower in s.subject.lower() or s.subject.lower() in subj_lower:
                return s.tutor_id
        return None

    def blacklist_tutor(self, tutor_id: str, reason: str):
        """Permanently blacklist a tutor."""
        from models.user import Blacklist
        tut = self.tutors.get(tutor_id)
        user = self.users.get_by_user_id(tutor_id)
        if tut:
            tut.is_blacklisted = True
            tut.approval_status = "blacklisted"
            tut.rejection_reason = reason
        if user:
            user.is_active = False
            user.is_verified = False
            # Add to blacklist table
            existing = self.db.query(Blacklist).filter(
                Blacklist.telegram_id == user.telegram_id).first()
            if not existing:
                bl = Blacklist(telegram_id=user.telegram_id, reason=reason)
                self.db.add(bl)
        self.db.commit()

    def unblacklist_tutor(self, tutor_id: str):
        """Reverse a blacklist — tutor must go through document review again."""
        tut = self.tutors.get(tutor_id)
        user = self.users.get_by_user_id(tutor_id)
        if tut:
            tut.is_blacklisted = False
            tut.approval_status = "pending_documents"
            tut.rejection_reason = None
        if user:
            user.is_active = True
            user.is_verified = False
        self.db.commit()
        # Deliberately NOT touching the Blacklist table — the tombstone stays
        # as a historical record and only matters again if this account is
        # later deleted and someone tries to re-register with the same telegram_id.

    def is_telegram_id_blacklisted(self, telegram_id: int) -> bool:
        """Check if a Telegram ID is permanently blacklisted."""
        from models.user import Blacklist
        return self.db.query(Blacklist).filter(
            Blacklist.telegram_id == telegram_id).first() is not None
