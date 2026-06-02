from datetime import datetime
from sqlalchemy.orm import Session
from repositories.schedule import SessionRepository
from repositories.user import UserRepository


class ConfirmationService:
    def __init__(self, db: Session):
        self.db = db
        self.sessions = SessionRepository(db)
        self.users = UserRepository(db)

    def confirm(self, telegram_id: int, session_id: str) -> dict:
        user = self.users.get_by_telegram_id(telegram_id)
        if not user:
            return {"success": False, "message": "User not found."}
        ses = self.sessions.get(session_id)
        if not ses:
            return {"success": False, "message": f"Session {session_id} not found."}

        is_tutor = user.user_id == ses.tutor_id
        is_student = user.user_id == ses.student_id
        if not is_tutor and not is_student:
            return {"success": False, "message": "You are not assigned to this session."}

        if is_tutor:
            if ses.tutor_confirmed:
                return {"success": False, "message": "You already confirmed this session."}
            ses.tutor_confirmed = True
        else:
            if ses.student_confirmed:
                return {"success": False, "message": "You already confirmed this session."}
            ses.student_confirmed = True

        # Complete if both confirmed + recording uploaded
        completed = False
        if ses.tutor_confirmed and ses.student_confirmed and ses.recording_path:
            ses.status = "completed"
            # Increment tutor session count
            from models.user import Tutor
            tutor_rec = self.db.query(Tutor).filter(Tutor.user_id == ses.tutor_id).first()
            if tutor_rec:
                tutor_rec.total_sessions = (tutor_rec.total_sessions or 0) + 1
            completed = True

        self.db.commit()

        missing = []
        if not ses.tutor_confirmed:
            missing.append("tutor confirmation")
        if not ses.student_confirmed:
            missing.append("student confirmation")
        if not ses.recording_path:
            missing.append("recording upload")

        return {
            "success": True,
            "completed": completed,
            "missing": missing,
            "role": "tutor" if is_tutor else "student",
        }
