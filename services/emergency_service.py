from datetime import datetime
from sqlalchemy.orm import Session
from repositories.user import UserRepository
from repositories.emergency import EmergencyRepository
from repositories.schedule import SessionRepository
from services.id_generator import IDGenerator
from services.admin_service import AdminService

ISSUE_TYPES = {
    "internet": "🌐 Internet / Connection Issue",
    "no_show": "🚫 Tutor / Student No-Show",
    "technical": "💻 Technical Problem",
    "payment": "💰 Payment Dispute",
    "behaviour": "⚠️ Behaviour Concern",
    "other": "❓ Other",
}


class EmergencyService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.emergencies = EmergencyRepository(db)
        self.sessions = SessionRepository(db)

    def create(self, reporter_telegram_id: int, issue_type: str,
               description: str, session_id: str = None) -> dict:
        user = self.users.get_by_telegram_id(reporter_telegram_id)
        if not user:
            return {"success": False, "message": "You are not registered."}
        if session_id:
            ses = self.sessions.get(session_id)
            if not ses:
                return {"success": False, "message": f"Session {session_id} not found."}
            if user.user_id not in (ses.student_id, ses.tutor_id):
                return {"success": False, "message": "You are not part of that session."}
            ses.status = "disputed"
            self.db.commit()

        emg_id = IDGenerator.emergency_id(self.db)
        self.emergencies.create({
            "emergency_id": emg_id,
            "reported_by": user.user_id,
            "session_id": session_id,
            "issue_type": issue_type,
            "description": description,
            "status": "open",
        })
        return {
            "success": True,
            "emergency_id": emg_id,
            "reporter_name": user.full_name,
            "reporter_id": user.user_id,
            "issue_type": ISSUE_TYPES.get(issue_type, issue_type),
            "description": description,
            "session_id": session_id,
        }

    def claim(self, admin_telegram_id: int, emergency_id: str) -> dict:
        """Admin claims an emergency from the group chat."""
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}

        emg = self.emergencies.get(emergency_id)
        if not emg:
            return {"success": False, "message": f"Emergency {emergency_id} not found."}
        if emg.status == "resolved":
            return {"success": False, "already_resolved": True,
                    "message": "This emergency has already been resolved."}

        # Already claimed by someone else?
        if emg.claimed_by_telegram_id and emg.claimed_by_telegram_id != admin_telegram_id:
            claimer = self.users.get_by_telegram_id(emg.claimed_by_telegram_id)
            name = claimer.full_name if claimer else "Another admin"
            return {"success": False, "already_claimed": True,
                    "message": f"Already being handled by *{name}*."}

        admin = self.users.get_by_telegram_id(admin_telegram_id)
        emg.claimed_by_telegram_id = admin_telegram_id
        emg.claimed_by_user_id = admin.user_id if admin else None
        emg.claimed_at = datetime.now()
        emg.status = "claimed"
        self.db.commit()

        reporter = self.users.get_by_user_id(emg.reported_by)
        return {
            "success": True,
            "emergency_id": emergency_id,
            "issue_type": ISSUE_TYPES.get(emg.issue_type, emg.issue_type),
            "description": emg.description,
            "reporter_name": reporter.full_name if reporter else emg.reported_by,
            "reporter_id": emg.reported_by,
            "reporter_telegram_id": reporter.telegram_id if reporter else None,
            "session_id": emg.session_id,
        }

    def resolve(self, admin_telegram_id: int, emergency_id: str,
                notes: str) -> dict:
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        admin = self.users.get_by_telegram_id(admin_telegram_id)
        emg = self.emergencies.get(emergency_id)
        if not emg:
            return {"success": False, "message": f"Emergency {emergency_id} not found."}
        if emg.status == "resolved":
            return {"success": False, "message": "Already resolved."}
        self.emergencies.resolve(
            emergency_id, admin.user_id if admin else "admin", notes)
        reporter = self.users.get_by_user_id(emg.reported_by)
        return {
            "success": True,
            "emergency_id": emergency_id,
            "reporter_telegram_id": reporter.telegram_id if reporter else None,
            "reporter_name": reporter.full_name if reporter else emg.reported_by,
        }

    def get_open(self) -> list:
        items = self.emergencies.get_open()
        result = []
        for e in items:
            reporter = self.users.get_by_user_id(e.reported_by)
            claimer_name = None
            if e.claimed_by_telegram_id:
                claimer = self.users.get_by_telegram_id(e.claimed_by_telegram_id)
                claimer_name = claimer.full_name if claimer else "Admin"
            result.append({
                "emergency_id": e.emergency_id,
                "reporter": reporter.full_name if reporter else e.reported_by,
                "reporter_id": e.reported_by,
                "issue_type": ISSUE_TYPES.get(e.issue_type, e.issue_type),
                "description": e.description[:120],
                "session_id": e.session_id,
                "created_at": e.created_at.strftime("%d %b %H:%M"),
                "status": e.status,
                "claimed_by": claimer_name,
            })
        return result
