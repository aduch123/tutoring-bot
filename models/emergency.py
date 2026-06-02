from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger
from sqlalchemy.sql import func
from config.db import Base


class Emergency(Base):
    __tablename__ = "emergencies"

    id = Column(Integer, primary_key=True)
    emergency_id = Column(String(20), unique=True, nullable=False)
    reported_by = Column(String(20), nullable=False)
    session_id = Column(String(20))
    issue_type = Column(String(50))
    description = Column(Text)
    # open | claimed | resolved
    status = Column(String(20), default="open")
    # Claiming system
    claimed_by_user_id = Column(String(20))
    claimed_by_telegram_id = Column(BigInteger)
    claimed_at = Column(DateTime)
    # Resolution
    resolved_by = Column(String(20))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
