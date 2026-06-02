from sqlalchemy.orm import Session
from sqlalchemy import func
from models.user import User, Student
from models.schedule import Session as SM, Schedule
from models.payment import Payment, TutorPayout
from models.emergency import Emergency
from repositories.user import UserRepository


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def system_dashboard(self) -> dict:
        students = self.db.query(User).filter(User.role == "student", User.is_active == True).count()
        verified_tutors = self.db.query(User).filter(User.role == "tutor", User.is_verified == True).count()
        pending_tutors = self.db.query(User).filter(User.role == "tutor", User.is_verified == False).count()
        completed = self.db.query(SM).filter(SM.status == "completed").count()
        scheduled = self.db.query(SM).filter(SM.status.in_(["scheduled", "zoom_pending", "zoom_ready"])).count()
        disputed = self.db.query(SM).filter(SM.status == "disputed").count()

        # Open emergencies vs issues (issue_type != urgent treated as issue)
        open_emergencies = self.db.query(Emergency).filter(
            Emergency.status.in_(["open", "claimed"]),
            Emergency.issue_type.in_(["internet", "no_show", "technical", "behaviour", "urgent"])
        ).count()
        open_issues = self.db.query(Emergency).filter(
            Emergency.status.in_(["open", "claimed"]),
            Emergency.issue_type.in_(["other", "payment", "dispute"])
        ).count()

        revenue = self.db.query(func.sum(Payment.amount)).filter(
            Payment.status == "completed").scalar() or 0

        # Students who haven't paid this month
        from datetime import datetime
        current_month = datetime.now().date().replace(day=1)
        all_student_ids = [u.user_id for u in self.db.query(User).filter(
            User.role == "student", User.is_active == True).all()]
        paid_ids = [p.student_id for p in self.db.query(Payment).filter(
            Payment.month == current_month,
            Payment.status == "completed"
        ).all()]
        unpaid_students = len([s for s in all_student_ids if s not in paid_ids])

        # Students with no active schedule (no tutor assigned)
        students_with_schedule = self.db.query(Schedule.student_id).filter(
            Schedule.is_active == True).distinct().all()
        students_with_schedule_ids = [s[0] for s in students_with_schedule]
        students_no_tutor = len([s for s in all_student_ids if s not in students_with_schedule_ids])

        return {
            "success": True,
            "students": students,
            "verified_tutors": verified_tutors,
            "pending_tutors": pending_tutors,
            "completed_sessions": completed,
            "scheduled_sessions": scheduled,
            "disputed_sessions": disputed,
            "open_emergencies": open_emergencies,
            "open_issues": open_issues,
            "platform_revenue": float(revenue) * 0.15,
            "unpaid_students": unpaid_students,
            "students_no_tutor": students_no_tutor,
        }

    def user_audit(self, user_id: str) -> dict:
        user = self.users.get_by_user_id(user_id)
        if not user:
            return {"success": False, "message": f"User {user_id} not found."}
        sessions = self.db.query(SM).filter(
            (SM.student_id == user_id) | (SM.tutor_id == user_id)
        ).order_by(SM.scheduled_start.desc()).limit(20).all()
        emergencies = self.db.query(Emergency).filter(
            Emergency.reported_by == user_id
        ).order_by(Emergency.created_at.desc()).limit(10).all()
        return {
            "success": True,
            "user": {
                "user_id": user.user_id, "full_name": user.full_name,
                "role": user.role, "phone": user.phone,
                "is_verified": user.is_verified, "is_active": user.is_active,
                "created_at": user.created_at.strftime("%Y-%m-%d"),
            },
            "sessions": [
                {"session_id": s.session_id, "subject": s.subject,
                 "date": s.scheduled_start.strftime("%Y-%m-%d %H:%M"), "status": s.status}
                for s in sessions
            ],
            "emergencies": [
                {"emergency_id": e.emergency_id, "issue_type": e.issue_type,
                 "status": e.status, "date": e.created_at.strftime("%Y-%m-%d")}
                for e in emergencies
            ],
        }

    def get_students_filtered(self, filter_type: str = "all") -> list:
        from datetime import datetime
        current_month = datetime.now().date().replace(day=1)
        users = self.db.query(User).filter(User.role == "student").all()
        result = []
        for u in users:
            stu = self.db.query(Student).filter(Student.user_id == u.user_id).first()
            paid = self.db.query(Payment).filter(
                Payment.student_id == u.user_id,
                Payment.month == current_month,
                Payment.status == "completed"
            ).first()
            if not paid:
                paid = self.db.query(Payment).filter(
                    Payment.student_id == u.user_id,
                    Payment.status == "completed"
                ).first()
            has_schedule = self.db.query(Schedule).filter(
                Schedule.student_id == u.user_id,
                Schedule.is_active == True
            ).first()
            row = {
                "user_id": u.user_id, "full_name": u.full_name,
                "phone": u.phone, "is_active": u.is_active,
                "subjects": stu.subjects if stu else "—",
                "is_paid": bool(paid),
                "has_tutor": bool(has_schedule),
            }
            if filter_type == "all":
                result.append(row)
            elif filter_type == "unpaid" and not paid:
                result.append(row)
            elif filter_type == "no_tutor" and not has_schedule:
                result.append(row)
        return result

    def get_tutors_filtered(self, filter_type: str = "all") -> list:
        from repositories.user import TutorRepository
        users = self.db.query(User).filter(User.role == "tutor").all()
        result = []
        for u in users:
            from models.user import Tutor
            tut = self.db.query(Tutor).filter(Tutor.user_id == u.user_id).first()
            row = {
                "user_id": u.user_id, "full_name": u.full_name,
                "phone": u.phone, "is_active": u.is_active,
                "is_verified": u.is_verified,
                "subjects": (tut.primary_subjects or "") if tut else "—",
            }
            if filter_type == "all":
                result.append(row)
            elif filter_type == "pending" and not u.is_verified:
                result.append(row)
            elif filter_type == "suspended" and not u.is_active:
                result.append(row)
        return result

    def get_invoices_filtered(self, filter_type: str = "all") -> list:
        q = self.db.query(Payment)
        if filter_type == "unpaid":
            q = q.filter(Payment.status == "pending")
        elif filter_type == "screenshot":
            q = q.filter(Payment.status == "screenshot_uploaded")
        elif filter_type == "paid":
            q = q.filter(Payment.status == "completed")
        payments = q.order_by(Payment.month.desc()).limit(50).all()
        result = []
        for p in payments:
            student = self.users.get_by_user_id(p.student_id)
            result.append({
                "transaction_id": p.transaction_id,
                "student_name": student.full_name if student else p.student_id,
                "student_id": p.student_id,
                "amount": float(p.amount),
                "month": p.month.strftime("%B %Y"),
                "status": p.status,
                "screenshot_file_id": p.screenshot_file_id,
                "claimed_by_telegram_id": p.claimed_by_telegram_id,
            })
        return result

    def get_payouts_filtered(self, filter_type: str = "all") -> list:
        q = self.db.query(TutorPayout)
        if filter_type == "pending":
            q = q.filter(TutorPayout.status == "pending")
        elif filter_type == "paid":
            q = q.filter(TutorPayout.status == "paid")
        payouts = q.order_by(TutorPayout.month.desc()).limit(50).all()
        result = []
        for p in payouts:
            tutor = self.users.get_by_user_id(p.tutor_id)
            result.append({
                "tutor_id": p.tutor_id,
                "tutor_name": tutor.full_name if tutor else p.tutor_id,
                "month": p.month.strftime("%B %Y"),
                "month_raw": p.month.strftime("%Y-%m"),
                "sessions": p.sessions_completed,
                "net": float(p.net_amount),
                "status": p.status,
            })
        return result
