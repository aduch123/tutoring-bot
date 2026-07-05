from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from repositories.user import UserRepository, StudentRepository
from repositories.payment import PaymentRepository, PayoutRepository
from repositories.schedule import SessionRepository
from services.id_generator import IDGenerator
from services.admin_service import AdminService
from config.config import PLATFORM_COMMISSION_ETB, TUTOR_NET_RATE_ETB, DEFAULT_SESSION_RATE_ETB


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.students = StudentRepository(db)
        self.payments = PaymentRepository(db)
        self.payouts = PayoutRepository(db)
        self.sessions = SessionRepository(db)

    # ── Student payment status ────────────────────────────────────────────────

    def get_student_payment_status(self, student_id: str) -> dict:
        """
        Returns the current payment status for a student.
        Statuses: unpaid | screenshot_uploaded | paid
        """
        now = datetime.now()
        current_month = now.date().replace(day=1)

        # Check current month invoice
        payment = self.payments.get_by_student_month(student_id, current_month)

        if not payment:
            return {"status": "unpaid", "payment": None}

        if payment.status == "completed":
            return {"status": "paid", "payment": payment}
        if payment.status == "screenshot_uploaded":
            return {"status": "screenshot_uploaded", "payment": payment}
        return {"status": "unpaid", "payment": payment}

    def is_student_unlocked(self, student_id: str) -> bool:
        """True if student has at least one confirmed payment."""
        all_payments = self.payments.get_by_student(student_id)
        return any(p.status == "completed" for p in all_payments)
    
    def is_student_unlocked_this_month(self, student_id: str) -> bool:
        """
        True if the student has a confirmed payment for the current calendar month
        OR if their rolling subscription deadline is still active in the future.
        """
        from models.user import Student
        from datetime import datetime

        # 1. Primary Gate: If their rolling deadline is in the future, they are explicitly unlocked
        student = self.db.query(Student).filter(Student.user_id == student_id).first()
        if student and student.next_payment_due and student.next_payment_due > datetime.now():
            return True

        # 2. Calendar Month Gate: If overdue, check if an approved payment exists for this month
        current_month = datetime.now().date().replace(day=1)
        current_payment = self.payments.get_by_student_month(student_id, current_month)

        if current_payment and current_payment.status == "completed":
            return True

        return False

    # ── Screenshot upload ─────────────────────────────────────────────────────

    def submit_payment_screenshot(self, student_telegram_id: int,
                                   file_id: str) -> dict:
        """Student uploads payment proof screenshot."""
        user = self.users.get_by_telegram_id(student_telegram_id)
        if not user or user.role != "student":
            return {"success": False, "message": "Student not found."}

        now = datetime.now()
        current_month = now.date().replace(day=1)

        # Get or create invoice for current month
        payment = self.payments.get_by_student_month(user.user_id, current_month)
        if not payment:
            # Auto-create invoice at student's rate
            rate = self.get_student_rate(user.user_id)
            txn = IDGenerator.transaction_id(self.db)
            payment = self.payments.create({
                "transaction_id": txn,
                "student_id": user.user_id,
                "amount": Decimal(str(rate)),
                "month": current_month,
                "status": "pending",
            })

        if payment.status == "completed":
            return {"success": False, "message": "Your payment for this month is already confirmed."}

        was_already_uploaded = payment.status == "screenshot_uploaded"
        existing_claimer = payment.claimed_by_telegram_id

        payment.screenshot_file_id = file_id
        payment.screenshot_uploaded_at = now
        payment.status = "screenshot_uploaded"
        self.db.commit()

        return {
            "success": True,
            "is_reupload": was_already_uploaded,
            "claimed_by_telegram_id": existing_claimer,
            "transaction_id": payment.transaction_id,
            "student_name": user.full_name,
            "student_id": user.user_id,
            "amount": float(payment.amount),
            "month": payment.month.strftime("%B %Y"),
        }

    # ── Claiming system ───────────────────────────────────────────────────────

    def claim_payment_review(self, admin_telegram_id: int,
                              transaction_id: str) -> dict:
        """Admin claims a payment review from the group chat."""
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}

        payment = self.payments.get_by_transaction(transaction_id)
        if not payment:
            return {"success": False, "message": "Payment not found."}

        if payment.claimed_by_telegram_id and payment.claimed_by_telegram_id != admin_telegram_id:
            # Already claimed by someone else
            admin = self.users.get_by_telegram_id(payment.claimed_by_telegram_id)
            name = admin.full_name if admin else "Another admin"
            return {"success": False, "already_claimed": True,
                    "message": f"Already being handled by *{name}*."}

        # Claim it
        admin = self.users.get_by_telegram_id(admin_telegram_id)
        payment.claimed_by_telegram_id = admin_telegram_id
        payment.claimed_by_user_id = admin.user_id if admin else None
        payment.claimed_at = datetime.now()
        self.db.commit()

        student = self.users.get_by_user_id(payment.student_id)
        return {
            "success": True,
            "transaction_id": transaction_id,
            "student_name": student.full_name if student else payment.student_id,
            "student_id": payment.student_id,
            "student_telegram_id": student.telegram_id if student else None,
            "amount": float(payment.amount),
            "month": payment.month.strftime("%B %Y"),
            "screenshot_file_id": payment.screenshot_file_id,
        }

    def confirm_payment(self, admin_telegram_id: int,
                         transaction_id: str) -> dict:
        """Admin confirms payment after reviewing screenshot."""
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}

        payment = self.payments.get_by_transaction(transaction_id)
        if not payment:
            return {"success": False, "message": f"Transaction {transaction_id} not found."}
        if payment.status == "completed":
            return {"success": False, "message": "Already confirmed."}

        payment.status = "completed"
        payment.paid_at = datetime.now()
        # Push the rolling deadline forward by 30 days from today
        student_record = self.students.get(payment.student_id)
        if student_record:
            student_record.next_payment_due = datetime.now() + timedelta(days=30)
        self.db.commit()

        student = self.users.get_by_user_id(payment.student_id)
        return {
            "success": True,
            "student_name": student.full_name if student else payment.student_id,
            "student_telegram_id": student.telegram_id if student else None,
            "month": payment.month.strftime("%B %Y"),
            "amount": float(payment.amount),
        }

    def reject_payment(self, admin_telegram_id: int,
                        transaction_id: str, reason: str) -> dict:
        """Admin rejects a payment screenshot."""
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}

        payment = self.payments.get_by_transaction(transaction_id)
        if not payment:
            return {"success": False, "message": "Payment not found."}

        payment.status = "pending"
        payment.screenshot_file_id = None
        payment.claimed_by_telegram_id = None
        payment.claimed_by_user_id = None
        payment.claimed_at = None
        self.db.commit()

        student = self.users.get_by_user_id(payment.student_id)
        return {
            "success": True,
            "student_name": student.full_name if student else payment.student_id,
            "student_telegram_id": student.telegram_id if student else None,
            "reason": reason,
        }

    # ── Rate management ───────────────────────────────────────────────────────

    def get_student_rate(self, student_id: str) -> float:
        s = self.students.get(student_id)
        if s and s.hourly_rate_etb:
            return float(s.hourly_rate_etb)
        return DEFAULT_SESSION_RATE_ETB

    def set_student_rate(self, admin_telegram_id: int,
                          student_id: str, rate: float) -> dict:
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        student = self.users.get_by_user_id(student_id)
        if not student or student.role != "student":
            return {"success": False, "message": f"Student {student_id} not found."}
        self.students.set_rate(student_id, rate)
        return {"success": True,
                "message": f"Rate for {student.full_name} set to {rate:.0f} ETB/hr."}

    # ── Invoice & payout ──────────────────────────────────────────────────────

    def create_invoice(self, admin_telegram_id: int, student_id: str,
                        month: date, amount: Decimal) -> dict:
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        student = self.users.get_by_user_id(student_id)
        if not student or student.role != "student":
            return {"success": False, "message": f"Student {student_id} not found."}
        if self.payments.get_by_student_month(student_id, month):
            return {"success": False,
                    "message": f"Invoice for {month.strftime('%B %Y')} already exists."}
        txn = IDGenerator.transaction_id(self.db)
        self.payments.create({
            "transaction_id": txn, "student_id": student_id,
            "amount": amount, "month": month, "status": "pending",
        })
        return {"success": True, "transaction_id": txn,
                "student_name": student.full_name,
                "amount": float(amount), "month": month.strftime("%B %Y")}

    def get_student_payments(self, telegram_id: int) -> dict:
        user = self.users.get_by_telegram_id(telegram_id)
        if not user or user.role != "student":
            return {"success": False, "message": "Student not found."}
        payments = self.payments.get_by_student(user.user_id)
        rate = self.get_student_rate(user.user_id)
        return {
            "success": True, "rate": rate,
            "payments": [
                {"transaction_id": p.transaction_id, "amount": float(p.amount),
                 "month": p.month.strftime("%B %Y"), "status": p.status}
                for p in payments
            ],
        }

    def generate_monthly_payouts(self, admin_telegram_id: int,
                                   month: date) -> dict:
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        from models.user import User
        from models.schedule import Session as SM
        tutors = self.db.query(User).filter(
            User.role == "tutor", User.is_verified == True).all()
        start = datetime.combine(month.replace(day=1), datetime.min.time())
        if month.month == 12:
            end = datetime.combine(
                month.replace(year=month.year + 1, month=1, day=1), datetime.min.time())
        else:
            end = datetime.combine(
                month.replace(month=month.month + 1, day=1), datetime.min.time())

        created = []
        for tutor in tutors:
            if self.payouts.get_by_tutor_month(tutor.user_id, month):
                continue
            count = self.db.query(SM).filter(
                SM.tutor_id == tutor.user_id, SM.status == "completed",
                SM.recording_approved == True,
                SM.scheduled_start >= start, SM.scheduled_start < end,
            ).count()
            if count == 0:
                continue
            rate = DEFAULT_SESSION_RATE_ETB
            total = Decimal(str(count * rate))
            commission = Decimal(str(PLATFORM_COMMISSION_ETB)) * count
            net = Decimal(str(TUTOR_NET_RATE_ETB)) * count
            self.payouts.create({
                "tutor_id": tutor.user_id, "month": month,
                "sessions_completed": count, "total_amount": total,
                "platform_commission": commission, "net_amount": net,
                "status": "pending",
            })
            created.append({"tutor": tutor.full_name, "sessions": count,
                             "net": float(net)})
        return {"success": True, "created": len(created),
                "payouts": created, "month": month.strftime("%B %Y")}

    def mark_payout_paid(self, admin_telegram_id: int,
                          tutor_id: str, month: date) -> dict:
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        p = self.payouts.get_by_tutor_month(tutor_id, month)
        if not p:
            return {"success": False, "message": "Payout not found."}
        p.status = "paid"
        p.paid_at = datetime.now()
        self.db.commit()
        tutor = self.users.get_by_user_id(tutor_id)
        return {"success": True,
                "tutor_name": tutor.full_name if tutor else tutor_id,
                "tutor_telegram_id": tutor.telegram_id if tutor else None,
                "net": float(p.net_amount), "month": month.strftime("%B %Y")}

    def get_tutor_earnings(self, telegram_id: int) -> dict:
        user = self.users.get_by_telegram_id(telegram_id)
        if not user or user.role != "tutor":
            return {"success": False, "message": "Tutor not found."}
        payouts = self.payouts.get_by_tutor(user.user_id)
        total_earned = sum(float(p.net_amount) for p in payouts if p.status == "paid")
        return {
            "success": True, "total_earned": total_earned,
            "payouts": [
                {"month": p.month.strftime("%B %Y"), "sessions": p.sessions_completed,
                 "gross": float(p.total_amount), "commission": float(p.platform_commission),
                 "net": float(p.net_amount), "status": p.status}
                for p in payouts
            ],
        }
