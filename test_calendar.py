"""
Test script for Google Calendar API Integration in Jarvis.
Run this script to verify credentials.json, test Google OAuth flow,
create a sample reminder event, and list upcoming calendar events.
"""

import os
import sys
import logging

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

from actions.reminders import (
    get_calendar_service,
    create_calendar_reminder,
    list_calendar_reminders,
    CREDENTIALS_PATH,
    TOKEN_PATH
)

def run_calendar_test():
    print("=" * 60)
    print("JARVIS - GOOGLE CALENDAR API INTEGRATION TEST")
    print("=" * 60)

    print(f"\n1. Checking Credentials File:")
    print(f"   Credentials Path: {CREDENTIALS_PATH}")
    if os.path.exists(CREDENTIALS_PATH):
        print("   [OK] credentials.json found!")
    else:
        print("   [INFO] credentials.json NOT found in project root.")
        print("   -> Reminders will save locally to SQLite database (jarvis.db).")
        print("   -> To enable Google Calendar sync, download OAuth Client credentials from Google Cloud Console, save as credentials.json in root folder.")

    print(f"\n2. Checking Saved Token File:")
    print(f"   Token Path: {TOKEN_PATH}")
    if os.path.exists(TOKEN_PATH):
        print("   [OK] token.json found (previously authorized).")
    else:
        print("   [INFO] token.json not found yet (will be created upon first OAuth login).")

    print(f"\n3. Testing Google Calendar Service Authentication:")
    service, error_msg = get_calendar_service()
    if service:
        print("   [SUCCESS] Google Calendar API Service authenticated successfully!")
    else:
        print(f"   [NOTICE] Google Calendar Service offline/not connected: {error_msg}")

    print(f"\n4. Testing Reminder Creation Function:")
    success, msg = create_calendar_reminder("Test Jarvis Calendar Reminder", "in 30 minutes")
    print(f"   Result: {msg}")

    print(f"\n5. Testing List Reminders Function:")
    success, list_msg = list_calendar_reminders()
    print(f"   Result:\n{list_msg}")

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    run_calendar_test()
