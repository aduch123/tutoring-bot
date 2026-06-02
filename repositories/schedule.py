from sqlalchemy.orm import Session
from models.schedule import Schedule, Session as SessionModel
from typing import Optional, List
from datetime import datetime


class ScheduleRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Schedule:
        s = Schedule(**data)
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def get(self, schedule_id: str) -> Optional[Schedule]:
        return self.db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()

    def get_by_student(self, student_id: str, active_only=True) -> List[Schedule]:
        q = self.db.query(Schedule).filter(Schedule.student_id == student_id)
        if active_only:
            q = q.filter(Schedule.is_active == True)
        return q.all()

    def get_by_tutor(self, tutor_id: str, active_only=True) -> List[Schedule]:
        q = self.db.query(Schedule).filter(Schedule.tutor_id == tutor_id)
        if active_only:
            q = q.filter(Schedule.is_active == True)
        return q.all()

    def get_all_active(self) -> List[Schedule]:
        return self.db.query(Schedule).filter(Schedule.is_active == True).all()

    def deactivate(self, schedule_id: str):
        s = self.get(schedule_id)
        if s:
            s.is_active = False
            self.db.commit()


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> SessionModel:
        s = SessionModel(**data)
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def get(self, session_id: str) -> Optional[SessionModel]:
        return self.db.query(SessionModel).filter(SessionModel.session_id == session_id).first()

    def get_by_student(self, student_id: str) -> List[SessionModel]:
        return (
            self.db.query(SessionModel)
            .filter(SessionModel.student_id == student_id)
            .order_by(SessionModel.scheduled_start)
            .all()
        )

    def get_by_tutor(self, tutor_id: str) -> List[SessionModel]:
        return (
            self.db.query(SessionModel)
            .filter(SessionModel.tutor_id == tutor_id)
            .order_by(SessionModel.scheduled_start)
            .all()
        )

    def get_upcoming(self, after: datetime, before: datetime) -> List[SessionModel]:
        return (
            self.db.query(SessionModel)
            .filter(
                SessionModel.scheduled_start >= after,
                SessionModel.scheduled_start <= before,
                SessionModel.status.in_(["scheduled", "zoom_pending", "zoom_ready"]),
            )
            .all()
        )

    def update_status(self, session_id: str, status: str):
        s = self.get(session_id)
        if s:
            s.status = status
            self.db.commit()

    def set_zoom_link(self, session_id: str, link: str):
        s = self.get(session_id)
        if s:
            s.zoom_link = link
            s.zoom_submitted_at = datetime.now()
            s.status = "zoom_ready"
            self.db.commit()
