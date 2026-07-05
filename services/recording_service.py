import os, shutil
from datetime import datetime
from sqlalchemy.orm import Session
from repositories.schedule import SessionRepository
from repositories.user import UserRepository
from config.config import RECORDINGS_PATH, MAX_RECORDING_SIZE_BYTES, ALLOWED_VIDEO_EXTENSIONS


class RecordingService:
    def __init__(self, db: Session):
        self.db = db
        self.sessions = SessionRepository(db)
        self.users = UserRepository(db)

    def upload(self, tutor_telegram_id: int, session_id: str,
           file_id: str, file_size: int, file_ext: str) -> dict:
        user = self.users.get_by_telegram_id(tutor_telegram_id)
        if not user:
            return {"success": False, "message": "User not found."}
        ses = self.sessions.get(session_id)
        if not ses:
            return {"success": False, "message": f"Session {session_id} not found."}
        if user.user_id != ses.tutor_id:
            return {"success": False, "message": "You are not the assigned tutor."}
        if ses.recording_path:
            return {"success": False, "message": "Recording already uploaded for this session."}
        if file_size > MAX_RECORDING_SIZE_BYTES:
            return {"success": False, "message": f"File too large. Max {MAX_RECORDING_SIZE_BYTES // (1024*1024)} MB."}
        if file_ext.lower() not in ALLOWED_VIDEO_EXTENSIONS:
            return {"success": False, "message": f"Invalid format. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}"}
    
        ses.recording_path = file_id          # NOTE: column now holds a Telegram file_id, not a filesystem path
        ses.recording_uploaded_at = datetime.now()
        self.db.commit()
        return {"success": True, "file_id": file_id, "session_id": session_id}

    def reject(self, session_id: str, reason: str) -> dict:
        ses = self.sessions.get(session_id)
        if not ses:
            return {"success": False, "message": "Session not found."}
        ses.recording_path = None
        ses.recording_uploaded_at = None
        self.db.commit()
        tutor = self.users.get_by_user_id(ses.tutor_id)
        return {"success": True, "session_id": session_id,
                "tutor_telegram_id": tutor.telegram_id if tutor else None}