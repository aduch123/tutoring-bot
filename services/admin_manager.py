"""Admin promotion/demotion service."""
from sqlalchemy.orm import Session
from repositories.user import UserRepository
from services.admin_service import AdminService
from services.id_generator import IDGenerator


class AdminManagerService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def add_admin(self, caller_telegram_id: int, target_telegram_id: int) -> dict:
        if not AdminService.is_master_admin(caller_telegram_id, self.db):
            return {"success": False, "message": "Only master admins can add new admins."}
        target = self.users.get_by_telegram_id(target_telegram_id)
        if not target:
            return {"success": False, "message": f"User with Telegram ID {target_telegram_id} not found. They must register first."}
        if target.role == "admin":
            return {"success": False, "message": f"{target.full_name} is already an admin."}
        target.role = "admin"
        target.is_verified = True
        self.db.commit()
        return {"success": True, "message": f"{target.full_name} (`{target.user_id}`) is now an admin."}

    def remove_admin(self, caller_telegram_id: int, target_telegram_id: int) -> dict:
        if not AdminService.is_master_admin(caller_telegram_id, self.db):
            return {"success": False, "message": "Only master admins can remove admins."}
        if caller_telegram_id == target_telegram_id:
            return {"success": False, "message": "You cannot remove yourself."}
        target = self.users.get_by_telegram_id(target_telegram_id)
        if not target or target.role != "admin":
            return {"success": False, "message": "Admin not found."}
        if target.is_master_admin:
            return {"success": False, "message": "Cannot remove a master admin."}
        target.role = "student"
        self.db.commit()
        return {"success": True, "message": f"{target.full_name} is no longer an admin."}
