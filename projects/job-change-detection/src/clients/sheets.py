"""
Google Sheets client using gspread with OAuth authentication.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

import gspread
from gspread.exceptions import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import api_config, sheet_columns

logger = logging.getLogger(__name__)


class SheetsClient:
    """Google Sheets client for reading and writing contact data."""

    def __init__(self, spreadsheet_id: str = None):
        self.spreadsheet_id = spreadsheet_id or api_config.spreadsheet_id
        self._gc: Optional[gspread.Client] = None
        self._sheet: Optional[gspread.Worksheet] = None

    def connect(self) -> None:
        """
        Connect to Google Sheets using OAuth.

        On first run, this will open a browser for authentication.
        Credentials are cached in ~/.config/gspread/authorized_user.json
        """
        logger.info("Connecting to Google Sheets...")
        self._gc = gspread.oauth()
        spreadsheet = self._gc.open_by_key(self.spreadsheet_id)
        self._sheet = spreadsheet.sheet1
        logger.info(f"Connected to spreadsheet: {spreadsheet.title}")

    def get_all_contacts(self, start_row: int = 3, end_row: int = None) -> List[Dict[str, Any]]:
        """
        Get all contacts from the spreadsheet.

        Args:
            start_row: First data row (1-indexed, default 3 since row 2 is header)
            end_row: Last data row (inclusive, None for all)

        Returns:
            List of contact dictionaries
        """
        if not self._sheet:
            self.connect()

        logger.info(f"Fetching contacts from row {start_row} to {end_row or 'end'}")

        # Get all values
        all_values = self._sheet.get_all_values()

        # Convert to list of dicts
        contacts = []
        cols = sheet_columns

        for i, row in enumerate(all_values[start_row - 1:end_row], start=start_row):
            # Pad row to expected length
            while len(row) < 21:
                row.append("")

            contact = {
                "row": i,
                "email": row[cols.email] if len(row) > cols.email else "",
                "first_name": row[cols.first_name] if len(row) > cols.first_name else "",
                "last_name": row[cols.last_name] if len(row) > cols.last_name else "",
                "company_name": row[cols.company_name] if len(row) > cols.company_name else "",
                "job_title": row[cols.job_title] if len(row) > cols.job_title else "",
                "paid_seat": row[cols.paid_seat] if len(row) > cols.paid_seat else "",
                "linkedin_url": row[cols.linkedin_url] if len(row) > cols.linkedin_url else "",
                "phone_number": row[cols.phone_number] if len(row) > cols.phone_number else "",
                "confirmed_linkedin": row[cols.confirmed_linkedin] if len(row) > cols.confirmed_linkedin else "",
                "job_changed": row[cols.job_changed] if len(row) > cols.job_changed else "",
                "new_company": row[cols.new_company] if len(row) > cols.new_company else "",
                "new_job_title": row[cols.new_job_title] if len(row) > cols.new_job_title else "",
                "last_processed_date": row[cols.last_processed_date] if len(row) > cols.last_processed_date else "",
                "new_email": row[cols.new_email] if len(row) > cols.new_email else "",
                "new_phone": row[cols.new_phone] if len(row) > cols.new_phone else "",
                "enrichment_status": row[cols.enrichment_status] if len(row) > cols.enrichment_status else "",
                "linkedin_validation_date": row[cols.linkedin_validation_date] if len(row) > cols.linkedin_validation_date else "",
                "ready_for_outreach": row[cols.ready_for_outreach] if len(row) > cols.ready_for_outreach else "",
            }
            contacts.append(contact)

        logger.info(f"Fetched {len(contacts)} contacts")
        return contacts

    def get_contact_batch(self, start_row: int, batch_size: int) -> List[Dict[str, Any]]:
        """Get a batch of contacts starting from a specific row."""
        return self.get_all_contacts(start_row=start_row, end_row=start_row + batch_size - 1)

    def update_contact(self, row: int, updates: Dict[str, Any]) -> None:
        """
        Update a single contact row with new data.

        Args:
            row: Row number (1-indexed)
            updates: Dictionary of column names to values
        """
        if not self._sheet:
            self.connect()

        cols = sheet_columns
        today = datetime.now().strftime("%Y-%m-%d")

        # Build list of cell updates
        cell_updates = []

        # Map update keys to column indices
        column_map = {
            "confirmed_linkedin": cols.confirmed_linkedin,
            "job_changed": cols.job_changed,
            "new_company": cols.new_company,
            "new_job_title": cols.new_job_title,
            "last_processed_date": cols.last_processed_date,
            "new_email": cols.new_email,
            "new_phone": cols.new_phone,
            "enrichment_status": cols.enrichment_status,
            "linkedin_validation_date": cols.linkedin_validation_date,
            "linkedin_url": cols.linkedin_url,  # For discovered LinkedIn URLs
            "ready_for_outreach": cols.ready_for_outreach,
        }

        for key, value in updates.items():
            if key in column_map:
                col_idx = column_map[key]
                # gspread uses 1-indexed columns
                cell_updates.append({
                    "range": f"{chr(65 + col_idx)}{row}",
                    "values": [[str(value) if value is not None else ""]]
                })

        if cell_updates:
            try:
                self._sheet.batch_update(cell_updates)
                logger.debug(f"Updated row {row}: {list(updates.keys())}")
            except APIError as e:
                logger.error(f"Failed to update row {row}: {e}")
                raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((APIError, ConnectionError, OSError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Sheets write failed, retrying in {retry_state.next_action.sleep} seconds... "
            f"(attempt {retry_state.attempt_number}/3)"
        )
    )
    def _write_batch_with_retry(self, batch: List[Dict]) -> None:
        """Write a batch of cell updates with retry logic."""
        self._sheet.batch_update(batch)

    def batch_update_contacts(self, updates: List[Dict[str, Any]]) -> None:
        """
        Update multiple contacts in a single batch request.

        Args:
            updates: List of dicts with 'row' and other column updates

        Includes retry logic with exponential backoff for connection failures.
        If all retries fail, saves the batch data to a local file for recovery.
        """
        if not self._sheet:
            self.connect()

        if not updates:
            return

        cols = sheet_columns
        column_map = {
            "confirmed_linkedin": cols.confirmed_linkedin,
            "job_changed": cols.job_changed,
            "new_company": cols.new_company,
            "new_job_title": cols.new_job_title,
            "last_processed_date": cols.last_processed_date,
            "new_email": cols.new_email,
            "new_phone": cols.new_phone,
            "enrichment_status": cols.enrichment_status,
            "linkedin_validation_date": cols.linkedin_validation_date,
            "linkedin_url": cols.linkedin_url,
            "ready_for_outreach": cols.ready_for_outreach,
        }

        cell_updates = []

        for update in updates:
            row = update.get("row")
            if not row:
                continue

            for key, value in update.items():
                if key == "row":
                    continue
                if key in column_map:
                    col_idx = column_map[key]
                    cell_updates.append({
                        "range": f"{chr(65 + col_idx)}{row}",
                        "values": [[str(value) if value is not None else ""]]
                    })

        if cell_updates:
            # Split into batches of 1000 (gspread limit)
            for i in range(0, len(cell_updates), 1000):
                batch = cell_updates[i:i + 1000]
                try:
                    self._write_batch_with_retry(batch)
                    logger.info(f"Batch updated {len(batch)} cells")
                except Exception as e:
                    # All retries failed - save to recovery file
                    logger.error(f"Batch update failed after all retries: {e}")
                    self._save_failed_batch(updates, e)
                    raise

    def _save_failed_batch(self, updates: List[Dict[str, Any]], error: Exception) -> None:
        """Save failed batch data to a local file for recovery."""
        import json
        from pathlib import Path

        recovery_dir = Path(__file__).parent.parent / "recovery"
        recovery_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recovery_file = recovery_dir / f"failed_batch_{timestamp}.json"

        # Extract row numbers for easy identification
        rows = [u.get("row") for u in updates if u.get("row")]

        recovery_data = {
            "timestamp": timestamp,
            "error": str(error),
            "rows": rows,
            "updates": updates,
        }

        with open(recovery_file, "w") as f:
            json.dump(recovery_data, f, indent=2, default=str)

        logger.error(f"Failed batch saved to {recovery_file}")
        logger.error(f"Affected rows: {min(rows) if rows else 'unknown'}-{max(rows) if rows else 'unknown'}")

    def get_total_rows(self) -> int:
        """Get total number of rows in the sheet."""
        if not self._sheet:
            self.connect()
        return self._sheet.row_count

    def get_row_count_with_data(self) -> int:
        """Get count of rows that have data."""
        if not self._sheet:
            self.connect()
        # Get column A values and count non-empty
        col_a = self._sheet.col_values(1)
        return len([v for v in col_a if v.strip()])
