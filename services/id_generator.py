"""Thread-safe sequential ID generation."""
import threading

_lock = threading.Lock()


class IDGenerator:
    @staticmethod
    def _next(prefix: str, model_class, id_field: str, db) -> str:
        with _lock:
            last = (
                db.query(model_class)
                .order_by(getattr(model_class, id_field).desc())
                .first()
            )
            if last:
                try:
                    num = int(getattr(last, id_field).split("-")[1]) + 1
                except Exception:
                    num = 1
            else:
                num = 1
            return f"{prefix}-{num:04d}"

    @staticmethod
    def user_id(role: str, db) -> str:
        from models.user import User
        prefix = {"student": "STU", "tutor": "TUT", "admin": "ADM"}.get(role, "USR")
        return IDGenerator._next(prefix, User, "user_id", db)

    @staticmethod
    def schedule_id(db) -> str:
        from models.schedule import Schedule
        return IDGenerator._next("SCH", Schedule, "schedule_id", db)

    @staticmethod
    def session_id(db) -> str:
        from models.schedule import Session
        return IDGenerator._next("SES", Session, "session_id", db)

    @staticmethod
    def emergency_id(db) -> str:
        from models.emergency import Emergency
        return IDGenerator._next("EMG", Emergency, "emergency_id", db)

    @staticmethod
    def transaction_id(db) -> str:
        from models.payment import Payment
        import random
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        rnd = random.randint(1000, 9999)
        return f"TXN-{ts}-{rnd}"
