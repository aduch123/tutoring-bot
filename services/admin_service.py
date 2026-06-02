"""Central admin authorization — checks DB so dynamic admins work."""
from config.config import ADMIN_TELEGRAM_IDS


class AdminService:

    @staticmethod
    def is_admin(telegram_id: int, db=None) -> bool:
        if telegram_id in ADMIN_TELEGRAM_IDS:
            return True
        if db is not None:
            from models.user import User
            u = db.query(User).filter(
                User.telegram_id == telegram_id,
                User.role == "admin",
                User.is_active == True,
            ).first()
            return u is not None
        return False

    @staticmethod
    def is_master_admin(telegram_id: int, db=None) -> bool:
        if db is not None:
            from models.user import User
            u = db.query(User).filter(User.telegram_id == telegram_id).first()
            if u and u.is_master_admin:
                return True
        # Fallback: first ID in list is master
        return bool(ADMIN_TELEGRAM_IDS) and telegram_id == ADMIN_TELEGRAM_IDS[0]
