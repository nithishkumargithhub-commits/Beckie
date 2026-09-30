"""
BECKIE - 1-Time Google Calendar & Google Tasks OAuth Authorization Script.

Uses official Google OAuth run_local_server to guarantee state consistency,
prevent CSRF state mismatch, open the browser automatically, and persist token.json.
"""

import os
import sys

# Ensure unbuffered output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from google_auth_oauthlib.flow import InstalledAppFlow
from actions.google_services import (
    CALENDAR_TASKS_SCOPES,
    CREDENTIALS_PATH,
    TOKEN_PATH,
    list_google_tasks,
    list_calendar_events,
)

PORT = 8090

def main():
    print("=" * 64, flush=True)
    print("      BECKIE // GOOGLE CALENDAR & TASKS AUTHENTICATION", flush=True)
    print("=" * 64, flush=True)

    if not os.path.exists(CREDENTIALS_PATH):
        print(f"\n[ERROR] credentials.json not found at: {CREDENTIALS_PATH}", flush=True)
        sys.exit(1)

    print(f"\n[1/3] Found credentials.json (Project beckie-510016)", flush=True)
    print("[2/3] Starting local server & launching browser...", flush=True)

    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_PATH,
        CALENDAR_TASKS_SCOPES,
    )

    prompt_msg = (
        "\n" + "-" * 64 + "\n"
        "Please visit this URL if browser did not open automatically:\n{url}\n"
        + "-" * 64 + "\n"
    )

    try:
        # run_local_server handles authorization_url generation, state validation,
        # browser opening, and code exchange in a single atomic flow.
        creds = flow.run_local_server(
            host="localhost",
            port=PORT,
            open_browser=True,
            authorization_prompt_message=prompt_msg,
            success_message="Authentication successful! BECKIE has been authorized. You can close this tab.",
            prompt="consent",
            access_type="offline"
        )

        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        print(f"\n[SUCCESS] OAuth token generated and saved to: {TOKEN_PATH}", flush=True)
    except Exception as e:
        print(f"\n[ERROR] Authentication failed: {e}", flush=True)
        sys.exit(1)

    print("\n[3/3] Testing live connections...", flush=True)
    
    print("\n--- Testing Google Tasks ---", flush=True)
    ok_tasks, tasks_msg = list_google_tasks(max_results=3)
    if ok_tasks:
        print(f"[OK] Tasks Connected:\n{tasks_msg}", flush=True)
    else:
        print(f"[WARNING] Tasks Error: {tasks_msg}", flush=True)

    print("\n--- Testing Google Calendar ---", flush=True)
    ok_cal, cal_msg = list_calendar_events(max_results=3)
    if ok_cal:
        print(f"[OK] Calendar Connected:\n{cal_msg}", flush=True)
    else:
        print(f"[WARNING] Calendar Error: {cal_msg}", flush=True)

    print("\n" + "=" * 64, flush=True)
    print("  AUTHENTICATION COMPLETE! BECKIE CAN NOW SYNC CALENDAR & TASKS.", flush=True)
    print("=" * 64, flush=True)

if __name__ == "__main__":
    main()
