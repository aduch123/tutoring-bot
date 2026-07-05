"""Registration service — updated for new fields."""
from datetime import datetime
from sqlalchemy.orm import Session
from repositories.user import UserRepository, StudentRepository, TutorRepository
from services.id_generator import IDGenerator
from services.admin_service import AdminService
from config.config import DEFAULT_SESSION_RATE_ETB
from data.rates import get_rate_for_grade


class RegistrationService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.students = StudentRepository(db)
        self.tutors = TutorRepository(db)

    def register_student(self, telegram_id, full_name, phone,
                         grade=None, parent_phone=None,
                         subjects=None, days_per_week=3, **kwargs):
        if self.users.get_by_telegram_id(telegram_id):
            return {"success": False, "message": "You are already registered."}
        uid = IDGenerator.user_id("student", self.db)
        self.users.create_user({
            "user_id": uid, "telegram_id": telegram_id, "role": "student",
            "full_name": full_name, "phone": phone,
            "is_verified": True, "is_active": True,
            "agreed_terms_at": datetime.now(),
        })
        rate = get_rate_for_grade(grade or "Other")
        from datetime import timedelta
        next_due = datetime.now()
        self.students.create({
            "user_id": uid, "grade": grade, "parent_phone": parent_phone,
            "subjects": subjects, "days_per_week": days_per_week,
            "hourly_rate_etb": rate,
            "next_payment_due": next_due,
        })
        return {"success": True, "user_id": uid, "full_name": full_name}

    def register_tutor(self, telegram_id, full_name, phone,
                       primary_subjects="", secondary_subjects="",
                       experience="", max_teaching_hours=3,
                       payment_accounts="{}", doc_file_ids="[]", **kwargs):
        if self.users.get_by_telegram_id(telegram_id):
            return {"success": False, "message": "You are already registered."}
        uid = IDGenerator.user_id("tutor", self.db)
        self.users.create_user({
            "user_id": uid, "telegram_id": telegram_id, "role": "tutor",
            "full_name": full_name, "phone": phone,
            "is_verified": False, "is_active": True,
            "agreed_terms_at": datetime.now(),
        })
        self.tutors.create({
            "user_id": uid,
            "primary_subjects": primary_subjects,
            "secondary_subjects": secondary_subjects,
            "experience": experience,
            "max_teaching_hours": max_teaching_hours,
            "payment_accounts": payment_accounts,
            "cv_file_ids": doc_file_ids,
            "approval_status": "pending_documents",
        })
        return {"success": True, "user_id": uid, "full_name": full_name}

    def approve_tutor_documents(self, tutor_user_id: str, admin_telegram_id: int):
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        user = self.users.get_by_user_id(tutor_user_id)
        if not user or user.role != "tutor":
            return {"success": False, "message": "Tutor not found."}
        tut = self.tutors.get(tutor_user_id)
        if not tut:
            return {"success": False, "message": "Tutor record not found."}
        if tut.approval_status != "pending_documents":
            return {"success": False, "message": f"Status is already: {tut.approval_status}"}
        tut.approval_status = "pending_video"
        self.db.commit()
        return {"success": True, "telegram_id": user.telegram_id, "full_name": user.full_name}

    def reject_tutor_documents(self, tutor_user_id: str, admin_telegram_id: int, reason: str):
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        user = self.users.get_by_user_id(tutor_user_id)
        tut = self.tutors.get(tutor_user_id)
        if not user or not tut:
            return {"success": False, "message": "Tutor not found."}
        tut.rejection_reason = reason
        # Keep status as pending_documents so they can re-upload
        self.db.commit()
        return {"success": True, "telegram_id": user.telegram_id, "full_name": user.full_name}

    def approve_tutor_video(self, tutor_user_id: str, admin_telegram_id: int):
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        user = self.users.get_by_user_id(tutor_user_id)
        tut = self.tutors.get(tutor_user_id)
        if not user or not tut:
            return {"success": False, "message": "Tutor not found."}
        tut.approval_status = "approved"
        tut.id_verified = True
        user.is_verified = True
        self.db.commit()
        return {"success": True, "telegram_id": user.telegram_id, "full_name": user.full_name, "message": f"Tutor {user.full_name} has been approved successfully!\n\nTutor ID: {tutor_user_id}"}

    def reject_tutor_video(self, tutor_user_id: str, admin_telegram_id: int, reason: str):
        """Final rejection — permanently blacklist the tutor."""
        if not AdminService.is_admin(admin_telegram_id, self.db):
            return {"success": False, "message": "Unauthorised."}
        user = self.users.get_by_user_id(tutor_user_id)
        if not user:
            return {"success": False, "message": "Tutor not found."}
        from services.tutor_service import TutorService
        TutorService(self.db).blacklist_tutor(tutor_user_id, reason)
        return {"success": True, "telegram_id": user.telegram_id, "full_name": user.full_name}

    def approve_tutor(self, tutor_user_id: str, admin_telegram_id: int):
        """Legacy single-step approval — kept for compatibility."""
        return self.approve_tutor_video(tutor_user_id, admin_telegram_id)

    def register_admin(self, telegram_id, full_name, phone, is_master=False):
        if self.users.get_by_telegram_id(telegram_id):
            return {"success": False, "message": "Already registered."}
        uid = IDGenerator.user_id("admin", self.db)
        self.users.create_user({
            "user_id": uid, "telegram_id": telegram_id, "role": "admin",
            "full_name": full_name, "phone": phone,
            "is_verified": True, "is_active": True, "is_master_admin": is_master,
        })
        return {"success": True, "user_id": uid}
