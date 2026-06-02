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
               temp_path: str, file_size: int, file_ext: str) -> dict:
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

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{ts}{file_ext}"
        dest = os.path.join(RECORDINGS_PATH, filename)
        try:
            shutil.move(temp_path, dest)
        except Exception as e:
            return {"success": False, "message": f"Failed to save file: {e}"}

        ses.recording_path = dest
        ses.recording_uploaded_at = datetime.now()
        self.db.commit()
        return {"success": True, "filename": filename, "session_id": session_id}
