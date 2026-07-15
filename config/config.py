import os
from dotenv import load_dotenv

load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_IDS = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()]
ADMIN_GROUP_CHAT_ID = int(os.getenv("ADMIN_GROUP_CHAT_ID", "0")) or None
DATABASE_URL = os.getenv("DATABASE_URL")
PLATFORM_COMMISSION_ETB = float(os.getenv("PLATFORM_COMMISSION_ETB", "100"))
TUTOR_NET_RATE_ETB = float(os.getenv("TUTOR_NET_RATE_ETB", "200"))
DEFAULT_SESSION_RATE_ETB = float(os.getenv("SESSION_RATE_ETB", "300"))
TIMEZONE = os.getenv("TIMEZONE", "Africa/Addis_Ababa")
RECORDINGS_PATH = os.getenv("RECORDINGS_PATH", "./recordings")
MAX_RECORDING_AGE_DAYS = int(os.getenv("MAX_RECORDING_AGE_DAYS", "30"))
MAX_RECORDING_SIZE_MB = int(os.getenv("MAX_RECORDING_SIZE_MB", "2000"))
MAX_RECORDING_SIZE_BYTES = MAX_RECORDING_SIZE_MB * 1024 * 1024
ALLOWED_VIDEO_EXTENSIONS = os.getenv("ALLOWED_VIDEO_EXTENSIONS", ".mp4,.mkv,.avi").split(",")
ZOOM_LINK_REQUEST_HOURS = 24
ZOOM_LINK_DEADLINE_HOURS = 1
SESSION_REMINDER_HOURS = 1
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@AkewTutor")
PAYMENT_TEST_MODE = os.getenv("PAYMENT_TEST_MODE", "false").lower() == "true"

os.makedirs(RECORDINGS_PATH, exist_ok=True)
os.makedirs("./logs", exist_ok=True)
os.makedirs("./backups", exist_ok=True)
