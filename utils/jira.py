import os
import requests
import logging

def fetch_filtered_jira_issues():
    domain = os.getenv("JIRA_DOMAIN")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    display_name = os.getenv("JIRA_DISPLAY_NAME")
    jql = os.getenv("JIRA_JQL")

    if not all([domain, email, token]):
        raise RuntimeError("Missing required JIRA secrets in environment")

    if not jql and display_name:
        # Only include USER fields
        user_fields = [
            "assignee",
            "cf[13403]",  # Designer
            "cf[13402]",  # Copywriter
            "cf[13902]",  # Brand Lead
            "cf[13400]",  # Project Lead
            "cf[15530]",  # Print Producer
            "cf[14200]",  # Social Media
            "cf[14110]",  # Illustration
            "cf[14610]",  # Head of Brand Design Review
        ]
        or_clause = " OR ".join(f'{field} = "{display_name}"' for field in user_fields)
        jql = (
            f'project = CFM AND resolution = Unresolved AND created >= "2024-01-01" AND ({or_clause}) '
            'ORDER BY updated DESC'
        )

    elif not jql:
        raise RuntimeError("Either JIRA_JQL must be provided, or JIRA_DISPLAY_NAME must be set")

    logging.info(f"🧠 JQL used: {jql}")

    url = f"https://{domain}/rest/api/3/search"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    auth = (email, token)
    params = {
        "jql": jql,
        "maxResults": 100,
        "fields": "*all",
    }

    issues = []
    start_at = 0

    logging.info(f"📡 Fetching Jira issues for: {display_name or 'custom JQL'}")
    while True:
        params["startAt"] = start_at
        response = requests.get(url, headers=headers, params=params, auth=auth)

        if response.status_code != 200:
            logging.error(f"⚠️ Jira API error: {response.status_code} — {response.text}")
            raise Exception(f"Failed to fetch Jira issues: {response.text}")

        data = response.json()
        issues.extend(data.get("issues", []))
        if start_at + data.get("maxResults", 0) >= data.get("total", 0):
            break
        start_at += data["maxResults"]

    return issues
