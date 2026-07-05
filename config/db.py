from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,  # recycle connections after 30 min; avoids using a
                        # connection the pooler silently dropped while idle
    connect_args={
        # Without these, a hung TCP handshake or a stuck query blocks
        # forever — and since DB calls here are synchronous, that freezes
        # the ENTIRE asyncio event loop (Telegram polling, scheduler, and
        # the watchdog job all run on it). These caps mean the worst case
        # is a clear error after a few seconds, not a silent permanent hang.
        "connect_timeout": 10,               # max seconds to establish a connection
        "options": "-c statement_timeout=15000",  # max 15s for any single query
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import user, schedule, payment, emergency, messaging  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialised")