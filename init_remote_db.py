import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

os.environ["DATABASE_URL"] = DATABASE_URL

from config.db import init_db
init_db()
print("✅ Database initialized!")