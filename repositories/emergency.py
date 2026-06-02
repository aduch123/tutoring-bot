from sqlalchemy.orm import Session
from models.emergency import Emergency
from typing import Optional, List


class EmergencyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Emergency:
        e = Emergency(**data)
        self.db.add(e)
        self.db.commit()
        self.db.refresh(e)
        return e

    def get(self, emergency_id: str) -> Optional[Emergency]:
        return self.db.query(Emergency).filter(
            Emergency.emergency_id == emergency_id).first()

    def get_open(self) -> List[Emergency]:
        return (
            self.db.query(Emergency)
            .filter(Emergency.status.in_(["open", "claimed"]))
            .order_by(Emergency.created_at.desc())
            .all()
        )

    def resolve(self, emergency_id: str, resolved_by: str, notes: str):
        from datetime import datetime
        e = self.get(emergency_id)
        if e:
            e.status = "resolved"
            e.resolved_by = resolved_by
            e.resolved_at = datetime.now()
            e.resolution_notes = notes
            self.db.commit()
