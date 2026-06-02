from sqlalchemy import Column, Integer, String, DateTime, Numeric, Date, Text, BigInteger
from sqlalchemy.sql import func
from config.db import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(60), unique=True, nullable=False)
    student_id = Column(String(20), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    month = Column(Date, nullable=False)
    # pending | screenshot_uploaded | completed
    status = Column(String(30), default="pending")
    payment_method = Column(String(40))
    screenshot_file_id = Column(String(200))           # Telegram file_id of payment proof
    screenshot_uploaded_at = Column(DateTime)
    # Claiming system
    claimed_by_user_id = Column(String(20))            # admin user_id who claimed review
    claimed_by_telegram_id = Column(BigInteger)
    claimed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    paid_at = Column(DateTime)


class TutorPayout(Base):
    __tablename__ = "tutor_payouts"

    id = Column(Integer, primary_key=True)
    tutor_id = Column(String(20), nullable=False)
    month = Column(Date, nullable=False)
    sessions_completed = Column(Integer, default=0)
    total_amount = Column(Numeric(10, 2), default=0)
    platform_commission = Column(Numeric(10, 2), default=0)
    net_amount = Column(Numeric(10, 2), default=0)
    status = Column(String(20), default="pending")     # pending | paid
    paid_at = Column(DateTime)
    transaction_ref = Column(String(100))
