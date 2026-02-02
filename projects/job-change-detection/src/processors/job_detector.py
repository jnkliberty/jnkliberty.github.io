"""
Job change detection with fuzzy company name matching.
"""

import re
from dataclasses import dataclass
from typing import Optional
from difflib import SequenceMatcher


@dataclass
class JobChangeResult:
    """Result of job change detection."""
    is_job_changer: bool
    confidence: float  # 0.0 - 1.0
    linkedin_company: str
    original_company: str
    linkedin_title: Optional[str] = None
    reason: str = ""


# Common company suffixes to strip for comparison
COMPANY_SUFFIXES = [
    r",?\s+inc\.?$",
    r",?\s+llc\.?$",
    r",?\s+ltd\.?$",
    r",?\s+corp\.?$",
    r",?\s+corporation$",
    r",?\s+co\.?$",
    r",?\s+company$",
    r",?\s+limited$",
    r",?\s+gmbh$",
    r",?\s+ag$",
    r",?\s+sa$",
    r",?\s+plc$",
    r",?\s+pvt\.?\s+ltd\.?$",
    r",?\s+private\s+limited$",
    r",?\s+technologies?$",
    r",?\s+solutions?$",
    r",?\s+software$",
    r",?\s+group$",
    r",?\s+holdings?$",
    r"\s+\(.*?\)$",  # Remove parenthetical notes
]

# Known company aliases (linkedin_name -> [possible_names])
COMPANY_ALIASES = {
    "meta": ["facebook", "meta platforms"],
    "alphabet": ["google", "alphabet inc"],
    "x": ["twitter", "x corp"],
}


def normalize_company_name(name: Optional[str]) -> str:
    """Normalize company name for comparison."""
    if not name:
        return ""

    # Convert to lowercase
    normalized = name.lower().strip()

    # Remove common suffixes
    for suffix_pattern in COMPANY_SUFFIXES:
        normalized = re.sub(suffix_pattern, "", normalized, flags=re.IGNORECASE)

    # Remove extra whitespace
    normalized = " ".join(normalized.split())

    return normalized.strip()


def are_companies_same(company1: str, company2: str, threshold: float = 0.85) -> tuple[bool, float]:
    """
    Check if two company names refer to the same company.

    Returns:
        Tuple of (are_same: bool, similarity_score: float)
    """
    if not company1 or not company2:
        return False, 0.0

    norm1 = normalize_company_name(company1)
    norm2 = normalize_company_name(company2)

    # Exact match after normalization
    if norm1 == norm2:
        return True, 1.0

    # Check if one contains the other
    if norm1 in norm2 or norm2 in norm1:
        return True, 0.95

    # Check known aliases
    for alias_key, alias_values in COMPANY_ALIASES.items():
        all_aliases = [alias_key] + alias_values
        if norm1 in all_aliases and norm2 in all_aliases:
            return True, 0.98

    # Fuzzy match using SequenceMatcher
    similarity = SequenceMatcher(None, norm1, norm2).ratio()

    return similarity >= threshold, similarity


def detect_job_change(
    linkedin_company: Optional[str],
    spreadsheet_company: Optional[str],
    linkedin_title: Optional[str] = None,
    spreadsheet_title: Optional[str] = None
) -> JobChangeResult:
    """
    Detect if a person has changed jobs based on company comparison.

    Args:
        linkedin_company: Current company from LinkedIn profile
        spreadsheet_company: Company name from our records
        linkedin_title: Current title from LinkedIn (optional)
        spreadsheet_title: Title from our records (optional)

    Returns:
        JobChangeResult with detection details
    """
    # Handle missing data
    if not linkedin_company:
        return JobChangeResult(
            is_job_changer=False,
            confidence=0.0,
            linkedin_company="",
            original_company=spreadsheet_company or "",
            linkedin_title=linkedin_title,
            reason="LinkedIn company not available"
        )

    if not spreadsheet_company:
        return JobChangeResult(
            is_job_changer=False,
            confidence=0.0,
            linkedin_company=linkedin_company,
            original_company="",
            linkedin_title=linkedin_title,
            reason="Original company not in records"
        )

    # Compare companies
    are_same, similarity = are_companies_same(linkedin_company, spreadsheet_company)

    if are_same:
        return JobChangeResult(
            is_job_changer=False,
            confidence=similarity,
            linkedin_company=linkedin_company,
            original_company=spreadsheet_company,
            linkedin_title=linkedin_title,
            reason=f"Same company (similarity: {similarity:.2%})"
        )

    # Different company detected
    # Calculate confidence based on how different the companies are
    confidence = 1.0 - similarity  # Higher confidence when more different

    return JobChangeResult(
        is_job_changer=True,
        confidence=confidence,
        linkedin_company=linkedin_company,
        original_company=spreadsheet_company,
        linkedin_title=linkedin_title,
        reason=f"Company changed (similarity: {similarity:.2%})"
    )


def is_side_venture(
    linkedin_company: str,
    spreadsheet_company: str,
    linkedin_experiences: list[dict] = None
) -> bool:
    """
    Check if the LinkedIn company is a side venture while person is still at original company.

    This checks if the person's LinkedIn shows multiple current positions,
    one of which matches the spreadsheet company.

    Args:
        linkedin_company: Primary/current company from LinkedIn
        spreadsheet_company: Company from our records
        linkedin_experiences: List of experience dicts from LinkedIn profile

    Returns:
        True if person appears to have a side venture but is still at original company
    """
    if not linkedin_experiences:
        return False

    # Check if any current experience matches the spreadsheet company
    for exp in linkedin_experiences:
        if not exp.get("is_current", False):
            continue

        exp_company = exp.get("company_name", "")
        is_same, _ = are_companies_same(exp_company, spreadsheet_company)

        if is_same:
            # They have a current role at the original company
            return True

    return False
