"""Admin-to-user messaging service."""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from repositories.user import UserRepository
from services.id_generator import IDGenerator


RESPONSE_TYPES = {
    "text": "📝 Text Reply",
    "approve_disapprove": "✅❌ Approve / Disapprove",
    "acknowledge": "👍 Acknowledge",
    "choose_options": "🔘 Choose from Options",
    "file_upload": "📎 File Upload",
}


class MessagingService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def create_message(self, admin_id: str, to_user_id: str,
                       message_text: str, response_type: str,
                       response_options: list = None) -> dict:
        from models.messaging import MessageLog
        from services.id_generator import IDGenerator

        user = self.users.get_by_user_id(to_user_id)
        if not user:
            return {"success": False, "message": "User not found."}

        msg_id = f"MSG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        log = MessageLog(
            message_id=msg_id,
            from_admin_id=admin_id,
            to_user_id=to_user_id,
            message_text=message_text,
            response_type=response_type,
            response_options=json.dumps(response_options) if response_options else None,
        )
        self.db.add(log)
        self.db.commit()
        return {
            "success": True,
            "message_id": msg_id,
            "to_telegram_id": user.telegram_id,
            "to_name": user.full_name,
        }

    def record_response(self, message_id: str, response: str):
        from models.messaging import MessageLog
        log = self.db.query(MessageLog).filter(
            MessageLog.message_id == message_id).first()
        if log:
            log.user_response = response
            log.responded_at = datetime.now()
            self.db.commit()

    def get_message(self, message_id: str):
        from models.messaging import MessageLog
        return self.db.query(MessageLog).filter(
            MessageLog.message_id == message_id).first()

    def get_pending_response(self, user_id: str, response_type: str = None):
        """Get a message awaiting a text or file response from this user."""
        from models.messaging import MessageLog
        query = self.db.query(MessageLog).filter(
            MessageLog.to_user_id == user_id,
            MessageLog.user_response == None,
        )
        if response_type:
            query = query.filter(MessageLog.response_type == response_type)
        else:
            query = query.filter(MessageLog.response_type.in_(["text", "file_upload"]))
        return query.order_by(MessageLog.responded_at.desc()).first()
