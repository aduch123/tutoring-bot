from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Time
from sqlalchemy.sql import func
from config.db import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True)
    schedule_id = Column(String(20), unique=True, nullable=False)
    student_id = Column(String(20), nullable=False)
    tutor_id = Column(String(20), nullable=False)
    subject = Column(String(80), nullable=False)
    days_of_week = Column(String(20), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())
    notes = Column(Text)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(20), unique=True, nullable=False)
    schedule_id = Column(String(20), nullable=False)
    student_id = Column(String(20), nullable=False)
    tutor_id = Column(String(20), nullable=False)
    subject = Column(String(80), nullable=False)
    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=False)
    zoom_link = Column(Text)
    zoom_requested_at = Column(DateTime)
    zoom_submitted_at = Column(DateTime)
    # scheduled | zoom_pending | zoom_ready | in_progress | completed
    # cancelled | disputed | missed | tutor_absent | student_absent
    status = Column(String(20), default="scheduled")
    # Start confirmations
    tutor_start_confirmed = Column(Boolean, default=False)
    student_start_confirmed = Column(Boolean, default=False)
    start_confirmed_at = Column(DateTime)
    # End confirmations
    tutor_confirmed = Column(Boolean, default=False)
    student_confirmed = Column(Boolean, default=False)
    end_confirmed_at = Column(DateTime)
    # Recording
    recording_path = Column(Text)
    recording_uploaded_at = Column(DateTime)
    recording_approved = Column(Boolean, default=False)
    recording_approved_by = Column(String(20))
    # Replacement
    replacement_tutor_id = Column(String(20))
    admin_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
