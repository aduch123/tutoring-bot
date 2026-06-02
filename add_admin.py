#!/usr/bin/env python
"""
Bootstrap script — run once from terminal to create the first master admin.

Usage:
    python add_admin.py <telegram_id> <full_name> <phone>

Example:
    python add_admin.py 123456789 "Adonay Tesfaye" "0912345678"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.db import init_db, SessionLocal
from services.registration import RegistrationService


def main():
    if len(sys.argv) < 4:
        print("Usage: python add_admin.py <telegram_id> <full_name> <phone>")
        print('Example: python add_admin.py 123456789 "Adonay Tesfaye" "0912345678"')
        sys.exit(1)

    telegram_id = int(sys.argv[1])
    full_name = sys.argv[2]
    phone = sys.argv[3]

    print("Initialising database...")
    init_db()

    with SessionLocal() as db:
        svc = RegistrationService(db)
        result = svc.register_admin(
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            is_master=True,
        )

    if result["success"]:
        print(f"\n✅ Master admin created!")
        print(f"   Name    : {full_name}")
        print(f"   ID      : {result['user_id']}")
        print(f"   Telegram: {telegram_id}")
        print(f"\nAlso add this Telegram ID to ADMIN_TELEGRAM_IDS in your .env file.")
    else:
        print(f"\n❌ {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
