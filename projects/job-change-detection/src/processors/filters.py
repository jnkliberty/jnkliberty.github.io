"""
Filters for skipping contacts that shouldn't be processed.
"""

import re
from typing import Tuple, Optional


# Generic team/department account patterns
GENERIC_NAME_PATTERNS = [
    r"(?i)^(BI|IT|HR|Sales|Marketing|Finance|Legal|Support|Admin|Operations)\s+(Team|Department|Group)$",
    r"(?i)^Team\s+\w+$",
    r"(?i)^\w+\s+Team$",
    r"(?i)^(Office|Executive|Administrative)\s+Assistant$",
    r"(?i)^(Company|Corporate|Business)\s+Account$",
    r"(?i)^Application\s+Integrations?$",
    r"(?i)^(General|Main)\s+Contact$",
]

# Generic email patterns (skip these entirely)
GENERIC_EMAIL_PATTERNS = [
    r"(?i)^(info|contact|hello|support|admin|sales|marketing|team|general|noreply|no-reply)@",
    r"(?i)^(billing|accounts|hr|legal|press|media|partnerships)@",
    r"(?i)^(office|reception|inquiry|enquiry|feedback)@",
    r"(?i)^invitation@",
    r"(?i)^biteam@",
    r"(?i)^appintegrations@",
]

# Internal company domains to skip
INTERNAL_DOMAINS = [
    "your-company.com",
]


def should_skip_contact(
    email: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    company: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Determine if a contact should be skipped from processing.

    Returns:
        Tuple of (should_skip: bool, reason: str)
    """
    # Check for empty or missing data
    if not email:
        return True, "Missing Email"

    email_lower = email.lower().strip()

    # Check internal domains
    for domain in INTERNAL_DOMAINS:
        if email_lower.endswith(f"@{domain}"):
            return True, f"Skip - Internal ({domain})"

    # Check generic email patterns
    for pattern in GENERIC_EMAIL_PATTERNS:
        if re.match(pattern, email_lower):
            return True, "Skip - Generic Email Account"

    # Check name patterns
    full_name = f"{first_name or ''} {last_name or ''}".strip()
    if full_name:
        for pattern in GENERIC_NAME_PATTERNS:
            if re.match(pattern, full_name):
                return True, "Skip - Generic Team Account"

    # Check for obviously non-personal names
    if first_name and not last_name:
        # Single word that looks like a team name
        single_names_to_skip = ["BI", "IT", "HR", "Sales", "Marketing", "Team", "Admin", "Support"]
        if first_name.strip() in single_names_to_skip:
            return True, "Skip - Generic Team Account"

    return False, ""


def is_valid_linkedin_url(url: Optional[str]) -> bool:
    """Check if a URL is a valid LinkedIn profile URL.

    Handles:
    - Standard URLs: linkedin.com/in/username
    - Country-specific: no.linkedin.com/in/username, za.linkedin.com/in/username
    - URL-encoded characters: %20, etc.
    - With or without www
    - With or without trailing slash
    - With query parameters or extra path segments
    """
    if not url:
        return False

    url = url.strip().lower()

    # Check for LinkedIn profile patterns - more permissive to handle edge cases
    patterns = [
        # Standard URLs
        r"^https?://(www\.)?linkedin\.com/in/[\w%-]+",
        # Country-specific domains (e.g., no.linkedin.com, za.linkedin.com)
        r"^https?://[a-z]{2}\.linkedin\.com/in/[\w%-]+",
        # Without protocol (some inputs might be missing it)
        r"^(www\.)?linkedin\.com/in/[\w%-]+",
        r"^[a-z]{2}\.linkedin\.com/in/[\w%-]+",
    ]

    for pattern in patterns:
        if re.match(pattern, url):
            return True

    return False


def normalize_linkedin_url(url: str) -> str:
    """
    Normalize a LinkedIn URL to a consistent format for matching.

    Handles variations like:
    - http vs https
    - www vs non-www
    - country-specific domains (no.linkedin.com, za.linkedin.com, etc.)
    - trailing slashes
    - case differences
    """
    if not url:
        return ""

    url = url.lower().strip()

    # Remove protocol
    url = url.replace("https://", "").replace("http://", "")

    # Remove www
    url = url.replace("www.", "")

    # Normalize country-specific LinkedIn domains to standard domain
    # e.g., no.linkedin.com, za.linkedin.com, nl.linkedin.com -> linkedin.com
    url = re.sub(r'^[a-z]{2}\.linkedin\.com', 'linkedin.com', url)

    # Remove trailing slash
    url = url.rstrip("/")

    return url


def extract_linkedin_username(url: str) -> Optional[str]:
    """Extract the username from a LinkedIn profile URL."""
    if not url:
        return None

    match = re.search(r"linkedin\.com/in/([\w%-]+)", url, re.IGNORECASE)
    if match:
        return match.group(1)

    return None
