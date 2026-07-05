from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, Numeric, Text
from sqlalchemy.sql import func
from config.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(20), unique=True, nullable=False)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    role = Column(String(10), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_master_admin = Column(Boolean, default=False)
    agreed_terms_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Student(Base):
    __tablename__ = "students"

    user_id = Column(String(20), primary_key=True)
    grade = Column(String(40))
    parent_phone = Column(String(20))
    hourly_rate_etb = Column(Numeric(10, 2), nullable=True)
    subjects = Column(Text)
    stream = Column(String(10), nullable=True)   # "Natural" | "Social" | None — only used for Grade 11/12
    days_per_week = Column(Integer, default=3)
    next_payment_due = Column(DateTime, nullable=True)
    payment_notified_days = Column(Integer, default=0)
    notes = Column(Text)


class Tutor(Base):
    __tablename__ = "tutors"

    user_id = Column(String(20), primary_key=True)
    primary_subjects = Column(Text)
    secondary_subjects = Column(Text)
    experience = Column(Text)
    # Documents
    cv_file_ids = Column(Text)           # JSON list of file_ids
    id_photo_file_id = Column(String(200))
    video_file_id = Column(String(200))
    # Approval
    # pending_documents | pending_video | approved | rejected | blacklisted
    approval_status = Column(String(30), default="pending_documents")
    rejection_reason = Column(Text)
    id_verified = Column(Boolean, default=False)
    # Capacity
    max_teaching_hours = Column(Integer, default=3)  # hours per week
    # Payment accounts: JSON {"Telebirr": "0912...", "CBE": "1000..."}
    payment_accounts = Column(Text)
    is_blacklisted = Column(Boolean, default=False)
    total_sessions = Column(Integer, default=0)


class Blacklist(Base):
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    reason = Column(Text)
    blacklisted_at = Column(DateTime, server_default=func.now())
