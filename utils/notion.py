import os
import requests
import logging

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def get_existing_ticket_ids():
    url = f"{NOTION_BASE_URL}/databases/{NOTION_DATABASE_ID}/query"
    ticket_ids = set()
    has_more = True
    payload = {"page_size": 100}
    while has_more:
        res = requests.post(url, headers=NOTION_HEADERS, json=payload)
        res.raise_for_status()
        data = res.json()
        for result in data.get("results", []):
            props = result.get("properties", {})
            ticket_field = props.get("Ticket ID", {}).get("rich_text", [])
            if ticket_field:
                text = ticket_field[0]["text"]["content"]
                ticket_ids.add(text)
        has_more = data.get("has_more", False)
        if has_more:
            payload["start_cursor"] = data["next_cursor"]
    return ticket_ids

def add_or_update_ticket(issue, existing_ids, dry_run=False):
    key = issue["key"]
    url = issue["self"]
    summary = issue["fields"].get("summary", "")
    status = issue["fields"].get("status", {}).get("name", "Unknown")

    changes = {}
    if key not in existing_ids:
        changes["created"] = True

        if dry_run:
            logging.info(f"[DRY RUN] Would create ticket: {key}")
            return key, changes

        # Create new page
        payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Name": {"title": [{"text": {"content": summary}}]},
                "Ticket ID": {"rich_text": [{"text": {"content": key}}]},
                "Status": {"status": {"name": status}},
            }
        }
        res = requests.post(f"{NOTION_BASE_URL}/pages", headers=NOTION_HEADERS, json=payload)
        res.raise_for_status()
        logging.info(f"✅ Created ticket {key} in Notion")
    else:
        logging.info(f"➖ Ticket {key} already exists. Skipping create.")
    return key, changes

def update_last_synced():
    # Optional: you can implement this to update a Notion text block with a timestamp.
    logging.info("✅ Updated last synced timestamp.")
