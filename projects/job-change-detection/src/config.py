"""
Configuration settings for LinkedIn Job Change Processor.
Load API keys from environment variables or .env file.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv(Path(__file__).parent / ".env")


@dataclass
class APIConfig:
    """API configuration and rate limits."""

    # Bright Data LinkedIn API
    bright_data_api_key: str = os.getenv("BRIGHT_DATA_API_KEY", "")
    bright_data_dataset_id: str = os.getenv("BRIGHT_DATA_DATASET_ID", "your-dataset-id")
    bright_data_batch_size: int = 20  # Max URLs per request
    bright_data_concurrent_batches: int = 5
    bright_data_poll_interval: int = 45  # seconds
    bright_data_max_poll_attempts: int = 40  # ~30 minutes max wait

    # LeadsMagic Phone API
    leadsmagic_api_key: str = os.getenv("LEADSMAGIC_API_KEY", "")
    leadsmagic_rate_limit: int = 300  # requests per minute
    leadsmagic_concurrent: int = 5
    leadsmagic_credits_per_lookup: int = 5

    # Better Contact API
    better_contact_api_key: str = os.getenv("BETTER_CONTACT_API_KEY", "")
    better_contact_batch_size: int = 50
    better_contact_concurrent: int = 2
    better_contact_poll_interval: int = 30  # seconds
    better_contact_phone_credits: int = 10
    better_contact_email_credits: int = 1

    # Google Sheets
    spreadsheet_id: str = os.getenv("SPREADSHEET_ID", "")


@dataclass
class ProcessingConfig:
    """Processing settings."""

    # Row ranges (1-indexed, row 2 is header)
    header_row: int = 2
    data_start_row: int = 3

    # Checkpoint settings
    checkpoint_dir: Path = Path(__file__).parent / "checkpoints"
    checkpoint_frequency: int = 20  # Save every N contacts

    # Logging
    log_dir: Path = Path(__file__).parent / "logs"
    log_level: str = "INFO"

    # Retry settings
    max_retries: int = 3
    initial_retry_delay: int = 5  # seconds
    max_retry_delay: int = 300  # seconds


@dataclass
class SheetColumns:
    """Google Sheets column mapping (0-indexed)."""

    # Input columns
    contact_id: int = 0               # A
    email: int = 1                    # B
    first_name: int = 2               # C
    last_name: int = 3                # D
    company_name: int = 4             # E
    job_title: int = 5                # F
    number_of_imports: int = 6        # G
    connected_data_sources: int = 7   # H
    paid_seat: int = 8                # I
    linkedin_url: int = 9             # J
    phone_number: int = 10            # K

    # Output columns
    confirmed_linkedin: int = 11      # L
    job_changed: int = 12             # M
    new_company: int = 13             # N
    new_job_title: int = 14           # O
    last_processed_date: int = 15     # P
    new_email: int = 16               # Q
    new_phone: int = 17               # R
    enrichment_status: int = 18       # S
    linkedin_validation_date: int = 19 # T
    ready_for_outreach: int = 20      # U


# Global config instances
api_config = APIConfig()
processing_config = ProcessingConfig()
sheet_columns = SheetColumns()

# Ensure directories exist
processing_config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
processing_config.log_dir.mkdir(parents=True, exist_ok=True)


def validate_api_keys() -> list[str]:
    """
    Validate that required API keys are configured.

    Returns:
        List of error messages for missing keys (empty if all valid)
    """
    errors = []

    if not api_config.bright_data_api_key:
        errors.append("BRIGHT_DATA_API_KEY is not set")

    if not api_config.leadsmagic_api_key:
        errors.append("LEADSMAGIC_API_KEY is not set")

    if not api_config.better_contact_api_key:
        errors.append("BETTER_CONTACT_API_KEY is not set")

    if not api_config.spreadsheet_id:
        errors.append("SPREADSHEET_ID is not set")

    return errors
