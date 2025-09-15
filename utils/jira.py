import os
import requests
import logging

# Maps roles to known user field IDs (excluding Head of Brand Design Review)
ROLE_FIELD_MAP = {
    "designer": "cf[13403]",
    "copywriter": "cf[13402]",
    "brand_lead": "cf[13902]",
    "project_lead": "cf[13400]",
    "print_producer": "cf[15530]",
    "social_media": "cf[14200]",
    "illustration": "cf[14110]",
    "production": "cf[14109]",
    "assignee": "assignee",
}

# Only the fields we actually use in notion.py (plus a few basics)
# If you add/remove Notion mappings, update this list to match.
ENHANCED_FIELDS = [
    "summary", "status", "assignee", "duedate",
    "customfield_13403",  # Designer
    "customfield_13406",  # Copy due date
    "customfield_15039",  # CR3
    "customfield_13607",  # Ideal go-live date (and maybe Design due date in your map)
    "customfield_13902",  # Brand lead
    "customfield_15011",  # Brief date
    "customfield_13408",  # Due date (often design due in some projects)
    "customfield_13402",  # Copywriter
    "customfield_15159",  # Sizing (brand)
    "customfield_13407",  # Illustration due date
    "customfield_13400",  # Project lead
    "customfield_14610",  # Head of Brand Design Review
    "customfield_15100",  # Video due date
    "customfield_14110",  # Illustration
    "customfield_14112",  # CR2
    "customfield_14111",  # CR1
    "customfield_14201",  # Social media due date
    "customfield_15530",  # Print producer
    "customfield_14200",  # Social media
    "customfield_14109",  # Production
]

def _build_jql():
    """
    JQL precedence:
      1) Use JIRA_JQL if provided.
      2) Else require JIRA_DISPLAY_NAME + JIRA_ROLE and build a scoped JQL.
    """
    jql = os.getenv("JIRA_JQL")
    if jql:
        return jql.strip()

    display_name = os.getenv("JIRA_DISPLAY_NAME")
    role = (os.getenv("JIRA_ROLE") or "").lower().strip()

    if not display_name or not role:
        raise RuntimeError("Either JIRA_JQL must be provided, or both JIRA_DISPLAY_NAME and JIRA_ROLE must be set")

    field = ROLE_FIELD_MAP.get(role)
    if not field:
        raise RuntimeError(f"Unsupported JIRA_ROLE: {role}")

    safe_name = display_name.replace('"', '\\"')
    return (
        f'project = CFM AND status != Resolved AND created >= "2024-01-01" AND {field} = "{safe_name}" '
        'ORDER BY updated DESC'
    )

def _auth_tuple():
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    if not email or not token:
        raise RuntimeError("Missing Jira credentials: JIRA_EMAIL, JIRA_API_TOKEN")
    return (email, token)

def _domain():
    domain = os.getenv("JIRA_DOMAIN")
    if not domain:
        raise RuntimeError("Missing required env: JIRA_DOMAIN")
    return domain

def fetch_filtered_jira_issues():
    """
    Enhanced JQL only:
      POST https://{domain}/rest/api/3/search/jql
      Body: { jql, fields: [..], maxResults, nextPageToken? }
      Response: { issues: [...], isLast: bool, nextPageToken?: str }
    Docs: developer.atlassian.com (Issue search » enhanced search). 
    """
    domain = _domain()
    auth = _auth_tuple()
    jql = _build_jql()

    url = f"https://{domain}/rest/api/3/search/jql"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    logging.info(f"🧠 JQL used: {jql}")
    logging.info("📡 Using ENHANCED endpoint: POST /rest/api/3/search/jql")

    issues = []
    next_token = None
    page_size = 100

    while True:
        body = {
            "jql": jql,
            "fields": ENHANCED_FIELDS,
            "maxResults": page_size,
        }
        if next_token:
            body["nextPageToken"] = next_token

        resp = requests.post(url, headers=headers, json=body, auth=auth, timeout=30)
        if resp.status_code != 200:
            # Surface the actual error so it's obvious if someone reintroduces legacy paths
            raise Exception(f"Enhanced JQL failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        batch = data.get("issues", []) or []
        issues.extend(batch)
        logging.info(f"🔍 (enhanced) fetched {len(batch)} issues (total so far={len(issues)})")

        if data.get("isLast", False):
            break

        next_token = data.get("nextPageToken")
        if not next_token:
            logging.warning("⚠️ Enhanced JQL: missing nextPageToken while isLast == False — stopping early.")
            break

    return issues
