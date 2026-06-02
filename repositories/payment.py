from sqlalchemy.orm import Session
from models.payment import Payment, TutorPayout
from typing import Optional, List
from datetime import date


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Payment:
        p = Payment(**data)
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def get_by_transaction(self, txn_id: str) -> Optional[Payment]:
        return self.db.query(Payment).filter(Payment.transaction_id == txn_id).first()

    def get_by_student(self, student_id: str) -> List[Payment]:
        return (
            self.db.query(Payment)
            .filter(Payment.student_id == student_id)
            .order_by(Payment.month.desc())
            .all()
        )

    def get_by_student_month(self, student_id: str, month: date) -> Optional[Payment]:
        return self.db.query(Payment).filter(
            Payment.student_id == student_id,
            Payment.month == month
        ).first()


class PayoutRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> TutorPayout:
        p = TutorPayout(**data)
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def get_by_tutor(self, tutor_id: str) -> List[TutorPayout]:
        return (
            self.db.query(TutorPayout)
            .filter(TutorPayout.tutor_id == tutor_id)
            .order_by(TutorPayout.month.desc())
            .all()
        )

    def get_by_tutor_month(self, tutor_id: str, month: date) -> Optional[TutorPayout]:
        return self.db.query(TutorPayout).filter(
            TutorPayout.tutor_id == tutor_id,
            TutorPayout.month == month
        ).first()
