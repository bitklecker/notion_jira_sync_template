# main.py
import os
import json
import argparse
import logging
import traceback
from datetime import datetime
import pytz

from utils.jira import fetch_filtered_jira_issues
from utils.notion import (
    get_existing_ticket_ids,
    add_or_update_ticket,
    delete_orphaned_tickets,
    update_last_synced
)
from utils.emailer import send_summary_email, send_error_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
)

REQUIRED_ENV = [
    "NOTION_API_KEY",
    "NOTION_DATABASE_ID",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_DOMAIN",
    "EMAIL_SENDER",
    "EMAIL_RECEIVER",
    "EMAIL_APP_PASSWORD",
]

def validate_env():
    missing = [key for key in REQUIRED_ENV if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {missing}")

def get_email_hours():
    return [9, 17]

def is_email_hour():
    est = pytz.timezone("America/New_York")
    return datetime.now(est).hour in get_email_hours()

def main(dry_run=False):
    try:
        validate_env()
        logging.info("🚀 Starting Jira → Notion sync...")

        issues = fetch_filtered_jira_issues()
        logging.info(f"🔍 Jira issues found: {len(issues)}")

        existing_ids, page_map = get_existing_ticket_ids()
        logging.info(f"📚 Existing Notion tickets: {len(existing_ids)}")

        created, updated = {}, {}

        seen_ticket_ids = set()

        for issue in issues:
            ticket_id, changes = add_or_update_ticket(issue, existing_ids, dry_run=dry_run)
            seen_ticket_ids.add(ticket_id)
            if changes.get("created"):
                created[ticket_id] = changes
            elif changes.get("updated"):
                updated[ticket_id] = changes

        # Delete tickets no longer matching the JIRA_DISPLAY_NAME
        delete_orphaned_tickets(page_map, seen_ticket_ids, dry_run=dry_run)

        logging.info(f"📦 Created={len(created)}, Updated={len(updated)}")

        if dry_run:
            logging.info("🧪 Dry run enabled — skipping email and Notion updates.")
            return

        if (created or updated) and is_email_hour():
            send_summary_email(created, updated)
            logging.info("📧 Summary email sent.")
        else:
            logging.info("🕒 Not an email hour or no changes — skipping email.")

        update_last_synced()

    except Exception as e:
        err = traceback.format_exc()
        logging.error(f"💥 Sync failed: {e}\n{err}")
        try:
            send_error_email("Jira-to-Notion sync failed", err)
        except Exception as mail_err:
            logging.error(f"❌ Failed to send error email: {mail_err}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without updating Notion or sending email")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
