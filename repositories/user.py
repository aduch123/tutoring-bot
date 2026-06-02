from sqlalchemy.orm import Session
from models.user import User, Student, Tutor
from typing import Optional, List


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, data: dict) -> User:
        user = User(**data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.telegram_id == telegram_id).first()

    def get_by_user_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.user_id == user_id).first()

    def get_all_by_role(self, role: str) -> List[User]:
        return self.db.query(User).filter(User.role == role).all()

    def set_verified(self, user_id: str, value: bool):
        u = self.get_by_user_id(user_id)
        if u:
            u.is_verified = value
            self.db.commit()

    def set_active(self, user_id: str, value: bool):
        u = self.get_by_user_id(user_id)
        if u:
            u.is_active = value
            self.db.commit()


class StudentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Student:
        s = Student(**data)
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def get(self, user_id: str) -> Optional[Student]:
        return self.db.query(Student).filter(Student.user_id == user_id).first()

    def set_rate(self, user_id: str, rate: float):
        s = self.get(user_id)
        if s:
            s.hourly_rate_etb = rate
            self.db.commit()


class TutorRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Tutor:
        t = Tutor(**data)
        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        return t

    def get(self, user_id: str) -> Optional[Tutor]:
        return self.db.query(Tutor).filter(Tutor.user_id == user_id).first()

    def get_all_verified(self) -> List[Tutor]:
        return (
            self.db.query(Tutor)
            .join(User, Tutor.user_id == User.user_id)
            .filter(User.is_verified == True)
            .all()
        )

    def update_docs(self, user_id: str, cv=None, transcript=None, id_photo=None):
        t = self.get(user_id)
        if t:
            if cv:
                t.cv_file_id = cv
            if transcript:
                t.transcript_file_id = transcript
            if id_photo:
                t.id_photo_file_id = id_photo
            self.db.commit()
