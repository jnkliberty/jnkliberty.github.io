"""
Checkpoint management for resumable processing.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Statistics for the current processing run."""
    total_contacts: int = 0
    processed: int = 0
    skipped: int = 0
    job_changers: int = 0
    phones_enriched: int = 0
    emails_enriched: int = 0
    errors: int = 0
    linkedin_validated: int = 0
    linkedin_private: int = 0
    linkedin_not_found: int = 0
    linkedin_discovered: int = 0  # URLs discovered via search

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "ProcessingStats":
        return cls(**data)


@dataclass
class Checkpoint:
    """Checkpoint state for resumable processing."""
    last_processed_row: int
    stage: str  # "linkedin", "phone", "email", "complete"
    started_at: str
    updated_at: str
    stats: ProcessingStats = field(default_factory=ProcessingStats)
    failed_rows: List[int] = field(default_factory=list)
    pending_retries: Dict[int, int] = field(default_factory=dict)  # row -> retry_count
    known_total_rows: int = 0  # Track spreadsheet size to detect new rows
    processed_row_ids: List[str] = field(default_factory=list)  # Contact IDs of processed rows (optional)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_processed_row": self.last_processed_row,
            "stage": self.stage,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "stats": self.stats.to_dict(),
            "failed_rows": self.failed_rows,
            "pending_retries": self.pending_retries,
            "known_total_rows": self.known_total_rows,
            "processed_row_ids": self.processed_row_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        stats = ProcessingStats.from_dict(data.get("stats", {}))
        return cls(
            last_processed_row=data["last_processed_row"],
            stage=data["stage"],
            started_at=data["started_at"],
            updated_at=data["updated_at"],
            stats=stats,
            failed_rows=data.get("failed_rows", []),
            pending_retries=data.get("pending_retries", {}),
            known_total_rows=data.get("known_total_rows", 0),
            processed_row_ids=data.get("processed_row_ids", []),
        )


class CheckpointManager:
    """Manages checkpoint saving and loading for resumable processing."""

    def __init__(self, checkpoint_dir: Path, checkpoint_name: str = "progress"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_file = self.checkpoint_dir / f"{checkpoint_name}.json"
        self.backup_file = self.checkpoint_dir / f"{checkpoint_name}_backup.json"
        self._current: Optional[Checkpoint] = None

    def exists(self) -> bool:
        """Check if a checkpoint file exists."""
        return self.checkpoint_file.exists()

    def load(self) -> Optional[Checkpoint]:
        """Load checkpoint from file."""
        if not self.checkpoint_file.exists():
            logger.info("No checkpoint file found, starting fresh")
            return None

        try:
            with open(self.checkpoint_file, "r") as f:
                data = json.load(f)
            self._current = Checkpoint.from_dict(data)
            logger.info(
                f"Loaded checkpoint: row {self._current.last_processed_row}, "
                f"stage {self._current.stage}, "
                f"processed {self._current.stats.processed}"
            )
            return self._current
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load checkpoint: {e}")
            # Try backup
            if self.backup_file.exists():
                logger.info("Attempting to load backup checkpoint")
                with open(self.backup_file, "r") as f:
                    data = json.load(f)
                self._current = Checkpoint.from_dict(data)
                return self._current
            return None

    def create(self, start_row: int, total_contacts: int, known_total_rows: int = 0) -> Checkpoint:
        """Create a new checkpoint."""
        now = datetime.now().isoformat()
        self._current = Checkpoint(
            last_processed_row=start_row - 1,  # Will be incremented on first save
            stage="linkedin",
            started_at=now,
            updated_at=now,
            stats=ProcessingStats(total_contacts=total_contacts),
            known_total_rows=known_total_rows,
        )
        self.save()
        return self._current

    def save(self) -> None:
        """Save current checkpoint to file."""
        if not self._current:
            return

        self._current.updated_at = datetime.now().isoformat()

        # Backup existing checkpoint first
        if self.checkpoint_file.exists():
            import shutil
            shutil.copy2(self.checkpoint_file, self.backup_file)

        # Write new checkpoint
        with open(self.checkpoint_file, "w") as f:
            json.dump(self._current.to_dict(), f, indent=2)

        logger.debug(f"Checkpoint saved: row {self._current.last_processed_row}")

    def update(
        self,
        row: Optional[int] = None,
        stage: Optional[str] = None,
        increment_processed: bool = False,
        increment_skipped: bool = False,
        increment_job_changers: bool = False,
        increment_phones: bool = False,
        increment_emails: bool = False,
        increment_errors: bool = False,
        increment_linkedin_validated: bool = False,
        increment_linkedin_private: bool = False,
        increment_linkedin_not_found: bool = False,
        increment_linkedin_discovered: int = 0,
        add_failed_row: Optional[int] = None,
        remove_failed_row: Optional[int] = None,
    ) -> None:
        """Update checkpoint state."""
        if not self._current:
            return

        if row is not None:
            self._current.last_processed_row = row
        if stage is not None:
            self._current.stage = stage
        if increment_processed:
            self._current.stats.processed += 1
        if increment_skipped:
            self._current.stats.skipped += 1
        if increment_job_changers:
            self._current.stats.job_changers += 1
        if increment_phones:
            self._current.stats.phones_enriched += 1
        if increment_emails:
            self._current.stats.emails_enriched += 1
        if increment_errors:
            self._current.stats.errors += 1
        if increment_linkedin_validated:
            self._current.stats.linkedin_validated += 1
        if increment_linkedin_private:
            self._current.stats.linkedin_private += 1
        if increment_linkedin_not_found:
            self._current.stats.linkedin_not_found += 1
        if increment_linkedin_discovered > 0:
            self._current.stats.linkedin_discovered += increment_linkedin_discovered
        if add_failed_row is not None and add_failed_row not in self._current.failed_rows:
            self._current.failed_rows.append(add_failed_row)
        if remove_failed_row is not None and remove_failed_row in self._current.failed_rows:
            self._current.failed_rows.remove(remove_failed_row)

    def get_current(self) -> Optional[Checkpoint]:
        """Get current checkpoint state."""
        return self._current

    def get_stats(self) -> Optional[ProcessingStats]:
        """Get current processing statistics."""
        return self._current.stats if self._current else None

    def print_summary(self) -> None:
        """Print a summary of the current checkpoint state."""
        if not self._current:
            print("No checkpoint loaded")
            return

        stats = self._current.stats
        print("\n" + "=" * 50)
        print("PROCESSING SUMMARY")
        print("=" * 50)
        print(f"Last processed row: {self._current.last_processed_row}")
        print(f"Current stage: {self._current.stage}")
        print(f"Started at: {self._current.started_at}")
        print(f"Updated at: {self._current.updated_at}")
        if self._current.known_total_rows > 0:
            print(f"Known total rows: {self._current.known_total_rows}")
        print("-" * 50)
        print(f"Total contacts: {stats.total_contacts}")
        print(f"Processed: {stats.processed}")
        print(f"Skipped: {stats.skipped}")
        print(f"Job changers found: {stats.job_changers}")
        print(f"LinkedIn validated: {stats.linkedin_validated}")
        print(f"LinkedIn discovered: {stats.linkedin_discovered}")
        print(f"LinkedIn private: {stats.linkedin_private}")
        print(f"LinkedIn not found: {stats.linkedin_not_found}")
        print(f"Phones enriched: {stats.phones_enriched}")
        print(f"Emails enriched: {stats.emails_enriched}")
        print(f"Errors: {stats.errors}")
        print(f"Failed rows pending retry: {len(self._current.failed_rows)}")
        print("=" * 50 + "\n")

    def detect_new_rows(self, current_total_rows: int) -> int:
        """
        Detect if new rows have been added since last run.

        Args:
            current_total_rows: Current row count from spreadsheet

        Returns:
            Number of new rows added (0 if no new rows)
        """
        if not self._current:
            return 0

        known = self._current.known_total_rows
        if known == 0:
            # First time tracking - not a "new row" scenario
            return 0

        if current_total_rows > known:
            new_rows = current_total_rows - known
            logger.info(f"Detected {new_rows} new rows added (was {known}, now {current_total_rows})")
            return new_rows

        return 0

    def update_known_total_rows(self, total_rows: int) -> None:
        """Update the known total rows count."""
        if self._current:
            self._current.known_total_rows = total_rows
            self.save()

    def get_known_total_rows(self) -> int:
        """Get the known total rows from checkpoint."""
        if self._current:
            return self._current.known_total_rows
        return 0
