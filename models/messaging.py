from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from config.db import Base


class MessageLog(Base):
    __tablename__ = "message_log"

    id = Column(Integer, primary_key=True)
    message_id = Column(String(20), unique=True, nullable=False)
    from_admin_id = Column(String(20), nullable=False)
    to_user_id = Column(String(20), nullable=False)
    message_text = Column(Text, nullable=False)
    # text | approve_disapprove | acknowledge | choose_options | file_upload
    response_type = Column(String(30), nullable=False)
    response_options = Column(Text)       # JSON for choose_options type
    user_response = Column(Text)
    responded_at = Column(DateTime)
    sent_at = Column(DateTime, server_default=func.now())
