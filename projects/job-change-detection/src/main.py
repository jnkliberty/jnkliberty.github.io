#!/usr/bin/env python3
"""
LinkedIn Job Change Detection Pipeline

Process contacts from Google Sheets to detect job changes and enrich data.

Usage:
    python main.py --start-row 34 --end-row 6453
    python main.py --resume
    python main.py --start-row 34 --end-row 100 --dry-run
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import api_config, processing_config, sheet_columns, validate_api_keys
from clients.sheets import SheetsClient
from clients.bright_data import BrightDataClient, LinkedInProfile, LinkedInSearchClient
from clients.leadsmagic import LeadsMagicClient, PhoneResult, EmailResult
from clients.better_contact import BetterContactClient, EnrichmentResult
from processors.filters import should_skip_contact, is_valid_linkedin_url, normalize_linkedin_url
from processors.job_detector import detect_job_change, JobChangeResult
from utils.checkpoint import CheckpointManager, ProcessingStats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(processing_config.log_dir / f"processing_{datetime.now():%Y%m%d_%H%M%S}.log"),
    ]
)
logger = logging.getLogger(__name__)


class JobChangeProcessor:
    """Main orchestrator for job change detection pipeline."""

    def __init__(
        self,
        start_row: int = 34,
        end_row: int = None,
        dry_run: bool = False,
        batch_size: int = 20,
        reverse: bool = False,
    ):
        self.start_row = start_row
        self.end_row = end_row
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.reverse = reverse

        # Initialize clients
        self.sheets = SheetsClient()
        self.bright_data = BrightDataClient()
        self.linkedin_search = LinkedInSearchClient()
        self.leadsmagic = LeadsMagicClient()
        self.better_contact = BetterContactClient()

        # Initialize checkpoint manager (separate file for reverse processing)
        checkpoint_dir = processing_config.checkpoint_dir
        checkpoint_name = "progress_reverse" if reverse else "progress"
        self.checkpoint = CheckpointManager(checkpoint_dir, checkpoint_name=checkpoint_name)

        # Processing state
        self.contacts: List[Dict[str, Any]] = []
        self.pending_updates: List[Dict[str, Any]] = []
        self.current_total_rows: int = 0

    def load_contacts(self) -> None:
        """Load contacts from Google Sheets."""
        direction = "bottom-up (reverse)" if self.reverse else "top-down"
        logger.info(f"Loading contacts from row {self.start_row} to {self.end_row or 'end'} ({direction})")
        self.sheets.connect()

        # Get current total row count for new row detection
        self.current_total_rows = self.sheets.get_row_count_with_data()
        logger.info(f"Current spreadsheet has {self.current_total_rows} rows with data")

        self.contacts = self.sheets.get_all_contacts(
            start_row=self.start_row,
            end_row=self.end_row
        )

        # Reverse order if processing from bottom up
        if self.reverse:
            self.contacts = list(reversed(self.contacts))

        logger.info(f"Loaded {len(self.contacts)} contacts")

    def filter_contacts(self) -> tuple[List[Dict], List[Dict]]:
        """
        Filter contacts into processable and skipped.

        Returns:
            Tuple of (to_process, skipped)
        """
        to_process = []
        skipped = []

        for contact in self.contacts:
            should_skip, reason = should_skip_contact(
                contact.get("email"),
                contact.get("first_name"),
                contact.get("last_name"),
                contact.get("company_name")
            )

            if should_skip:
                contact["skip_reason"] = reason
                skipped.append(contact)
                self.checkpoint.update(increment_skipped=True)
            else:
                to_process.append(contact)

        logger.info(f"Filtered: {len(to_process)} to process, {len(skipped)} skipped")
        return to_process, skipped

    async def discover_linkedin_urls(
        self,
        contacts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Discover LinkedIn URLs for contacts missing them.

        Searches using name + company + title data from the spreadsheet.
        Updates the spreadsheet with discovered URLs.

        Args:
            contacts: List of contacts to process

        Returns:
            Updated list of contacts with discovered URLs filled in
        """
        # Find contacts missing LinkedIn URLs
        missing_urls = [
            c for c in contacts
            if not is_valid_linkedin_url(c.get("linkedin_url"))
        ]

        if not missing_urls:
            logger.debug("All contacts have LinkedIn URLs")
            return contacts

        logger.info(f"Discovering LinkedIn URLs for {len(missing_urls)} contacts")

        # Search for each contact's LinkedIn profile
        discovered = 0
        url_updates = []

        for contact in missing_urls:
            first_name = contact.get("first_name", "")
            last_name = contact.get("last_name", "")
            company = contact.get("company_name", "")
            title = contact.get("job_title", "")

            # Skip if missing name data
            if not first_name or not last_name:
                logger.warning(f"Row {contact.get('row')}: Missing name, cannot search")
                continue

            # Search for LinkedIn profile
            url = await self.linkedin_search.search_via_google(
                first_name, last_name, company, title
            )

            if url:
                discovered += 1
                contact["linkedin_url"] = url
                contact["linkedin_discovered"] = True
                logger.info(f"DISCOVERED: {first_name} {last_name} -> {url}")

                # Prepare update for spreadsheet
                url_updates.append({
                    "row": contact["row"],
                    "linkedin_url": url,
                })
            else:
                logger.debug(f"No LinkedIn found for {first_name} {last_name} at {company}")

        # Update spreadsheet with discovered URLs
        if url_updates and not self.dry_run:
            self.sheets.batch_update_contacts(url_updates)
            logger.info(f"Updated {len(url_updates)} discovered LinkedIn URLs in spreadsheet")

        logger.info(f"LinkedIn URL discovery: {discovered}/{len(missing_urls)} found")
        self.checkpoint.update(increment_linkedin_discovered=discovered)

        return contacts

    async def process_linkedin_batch(
        self,
        contacts: List[Dict[str, Any]]
    ) -> List[tuple[Dict, LinkedInProfile]]:
        """
        Process a batch of contacts through LinkedIn validation.

        Returns:
            List of (contact, profile) tuples
        """
        # Filter to contacts with LinkedIn URLs
        contacts_with_linkedin = [
            c for c in contacts
            if is_valid_linkedin_url(c.get("linkedin_url"))
        ]

        if not contacts_with_linkedin:
            return [(c, LinkedInProfile(url="", error="No LinkedIn URL")) for c in contacts]

        # Prepare URLs for Bright Data (keep https:// prefix)
        def prepare_url_for_api(url: str) -> str:
            """Prepare URL for Bright Data API (needs https:// prefix)."""
            url = url.strip()
            if url.startswith("http://"):
                url = url.replace("http://", "https://", 1)
            if not url.startswith("https://"):
                url = "https://" + url
            url = url.replace("www.", "")
            return url.rstrip("/")

        urls = [prepare_url_for_api(c["linkedin_url"]) for c in contacts_with_linkedin]

        logger.info(f"Fetching {len(urls)} LinkedIn profiles")
        profiles = await self.bright_data.fetch_profiles(urls)

        # Match profiles back to contacts
        results = []
        profile_map = {normalize_linkedin_url(p.url): p for p in profiles}

        for contact in contacts:
            original_url = contact.get("linkedin_url", "")
            url = normalize_linkedin_url(original_url)

            if url and url in profile_map:
                results.append((contact, profile_map[url]))
            elif not original_url or not url:
                # Contact has no LinkedIn URL
                results.append((
                    contact,
                    LinkedInProfile(url="", error="No LinkedIn URL")
                ))
            else:
                # Contact has LinkedIn URL but profile wasn't returned (URL mismatch)
                logger.warning(f"Row {contact.get('row')}: Profile not returned for URL: {original_url}")
                results.append((
                    contact,
                    LinkedInProfile(url=original_url, error="Profile not returned")
                ))

        return results

    def detect_job_changes(
        self,
        contact_profiles: List[tuple[Dict, LinkedInProfile]]
    ) -> List[tuple[Dict, LinkedInProfile, JobChangeResult]]:
        """
        Detect job changes for validated contacts.

        Returns:
            List of (contact, profile, job_change_result) tuples
        """
        results = []

        for contact, profile in contact_profiles:
            if profile.error or profile.is_private:
                # Can't detect job change
                job_result = JobChangeResult(
                    is_job_changer=False,
                    confidence=0.0,
                    linkedin_company="",
                    original_company=contact.get("company_name", ""),
                    reason=profile.error or "Profile Private"
                )
            else:
                job_result = detect_job_change(
                    linkedin_company=profile.current_company,
                    spreadsheet_company=contact.get("company_name"),
                    linkedin_title=profile.current_title,
                    spreadsheet_title=contact.get("job_title")
                )
                if job_result.is_job_changer:
                    logger.info(f"JOB CHANGE: {contact.get('first_name')} {contact.get('last_name')} - {job_result.original_company} -> {job_result.linkedin_company}")
                    if job_result.linkedin_title:
                        logger.info(f"  New Title: {job_result.linkedin_title}")

            results.append((contact, profile, job_result))

            # Update checkpoint stats
            if job_result.is_job_changer:
                self.checkpoint.update(increment_job_changers=True)
            if profile.is_private:
                self.checkpoint.update(increment_linkedin_private=True)
            elif profile.error:
                self.checkpoint.update(increment_linkedin_not_found=True)
            else:
                self.checkpoint.update(increment_linkedin_validated=True)

        return results

    async def enrich_phones(
        self,
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, PhoneResult]:
        """
        Enrich phones for contacts missing phone numbers using dual-API fallback.

        Step 1: Try LeadsMagic Mobile Finder (personal cell phones)
        Step 2: Fall back to Better Contact (B2B work numbers) if LeadsMagic fails

        Returns:
            Dict mapping linkedin_url to PhoneResult
        """
        # Filter to contacts needing phones
        need_phones = [
            c for c in contacts
            if not c.get("phone_number") and is_valid_linkedin_url(c.get("linkedin_url"))
        ]

        if not need_phones:
            return {}

        logger.info(f"Enriching phones for {len(need_phones)} contacts")

        # Step 1: Try LeadsMagic Mobile Finder (personal cell phones)
        logger.info("Step 1: Trying LeadsMagic for personal mobile phones")
        leadsmagic_results = await self.leadsmagic.find_phones_batch([
            {"linkedin_url": c["linkedin_url"], "email": c.get("email")}
            for c in need_phones
        ])

        results = {}
        need_fallback = []

        for i, result in enumerate(leadsmagic_results):
            contact = need_phones[i]
            normalized_url = normalize_linkedin_url(contact["linkedin_url"])
            if result.success:
                results[normalized_url] = result
                self.checkpoint.update(increment_phones=True)
                logger.info(f"LeadsMagic found personal mobile for {contact.get('first_name', '')} {contact.get('last_name', '')}: {result.phone}")
            else:
                need_fallback.append((contact, normalized_url))

        # Step 2: Try Better Contact for failures (B2B work numbers)
        if need_fallback:
            logger.info(f"Step 2: Trying Better Contact for {len(need_fallback)} contacts without phones")
            bc_results = await self.better_contact.enrich_phones([
                {
                    "linkedin_url": c["linkedin_url"],
                    "first_name": c.get("first_name", ""),
                    "last_name": c.get("last_name", ""),
                    "company": c.get("company_name", ""),
                }
                for c, _ in need_fallback
            ])

            for i, result in enumerate(bc_results):
                contact, normalized_url = need_fallback[i]
                if result.phone_found:
                    results[normalized_url] = PhoneResult(
                        linkedin_url=contact["linkedin_url"],
                        phone=result.phone,
                        phone_type="work",
                        success=True,
                        source="BetterContact"
                    )
                    self.checkpoint.update(increment_phones=True)
                    logger.info(f"Better Contact found work phone for {contact.get('first_name', '')} {contact.get('last_name', '')}: {result.phone}")

        logger.info(f"Phone enrichment complete: {len(results)}/{len(need_phones)} found")
        return results

    async def enrich_emails_for_job_changers(
        self,
        job_changers: List[tuple[Dict, LinkedInProfile, JobChangeResult]]
    ) -> Dict[str, str]:
        """
        Enrich emails for job changers using their NEW company.

        Uses dual-API fallback: Better Contact first, LeadsMagic as fallback.

        Returns:
            Dict mapping linkedin_url to new email
        """
        if not job_changers:
            return {}

        logger.info(f"Enriching emails for {len(job_changers)} job changers")

        # Prepare contacts with NEW company
        contacts_for_enrichment = [
            {
                "linkedin_url": profile.url,
                "first_name": contact.get("first_name", ""),
                "last_name": contact.get("last_name", ""),
                "company": job_result.linkedin_company,  # Use NEW company!
            }
            for contact, profile, job_result in job_changers
        ]

        # Step 1: Try Better Contact first
        logger.info("Step 1: Trying Better Contact for email enrichment")
        bc_results = await self.better_contact.enrich_emails(contacts_for_enrichment)

        emails = {}
        need_fallback = []

        for i, result in enumerate(bc_results):
            contact = contacts_for_enrichment[i]
            # Normalize URL for consistent lookup later
            normalized_url = normalize_linkedin_url(contact["linkedin_url"])
            if result.email_found:
                emails[normalized_url] = result.email
                self.checkpoint.update(increment_emails=True)
                logger.info(f"Better Contact found email for {contact['first_name']} {contact['last_name']}: {result.email}")
            else:
                need_fallback.append((contact, normalized_url))

        # Step 2: Try LeadsMagic for failures
        if need_fallback:
            logger.info(f"Step 2: Trying LeadsMagic for {len(need_fallback)} contacts without emails")
            lm_results = await self.leadsmagic.find_emails_batch([c for c, _ in need_fallback])

            for i, result in enumerate(lm_results):
                contact, normalized_url = need_fallback[i]
                if result.success and result.email:
                    emails[normalized_url] = result.email
                    self.checkpoint.update(increment_emails=True)
                    logger.info(f"LeadsMagic found email for {contact['first_name']} {contact['last_name']}: {result.email}")

        logger.info(f"Email enrichment complete: {len(emails)}/{len(job_changers)} found")
        return emails

    async def enrich_phones_for_job_changers(
        self,
        job_changers: List[tuple[Dict, LinkedInProfile, JobChangeResult]]
    ) -> Dict[str, PhoneResult]:
        """
        Enrich phones for job changers using dual-API fallback.

        Step 1: Try LeadsMagic Mobile Finder (personal cell phones)
        Step 2: Fall back to Better Contact (B2B work numbers) if LeadsMagic fails

        Returns:
            Dict mapping linkedin_url to PhoneResult
        """
        if not job_changers:
            return {}

        logger.info(f"Enriching phones for {len(job_changers)} job changers")

        # Prepare contacts for enrichment
        contacts_for_enrichment = []
        for contact, profile, job_result in job_changers:
            contacts_for_enrichment.append({
                "linkedin_url": profile.url,
                "email": contact.get("email"),
                "first_name": contact.get("first_name", ""),
                "last_name": contact.get("last_name", ""),
                "company": job_result.linkedin_company,  # Use NEW company for Better Contact
            })

        # Step 1: Try LeadsMagic Mobile Finder (personal cell phones)
        logger.info("Step 1: Trying LeadsMagic for personal mobile phones")
        lm_results = await self.leadsmagic.find_phones_batch([
            {"linkedin_url": c["linkedin_url"], "email": c.get("email")}
            for c in contacts_for_enrichment
        ])

        phones = {}
        need_fallback = []

        for i, result in enumerate(lm_results):
            contact = contacts_for_enrichment[i]
            normalized_url = normalize_linkedin_url(contact["linkedin_url"])
            if result.success:
                phones[normalized_url] = result
                self.checkpoint.update(increment_phones=True)
                logger.info(f"LeadsMagic found personal mobile for {contact['first_name']} {contact['last_name']}: {result.phone}")
            else:
                need_fallback.append((contact, normalized_url))

        # Step 2: Try Better Contact for failures (B2B work numbers)
        if need_fallback:
            logger.info(f"Step 2: Trying Better Contact for {len(need_fallback)} contacts without phones")
            bc_results = await self.better_contact.enrich_phones([
                {
                    "linkedin_url": c["linkedin_url"],
                    "first_name": c["first_name"],
                    "last_name": c["last_name"],
                    "company": c["company"],
                }
                for c, _ in need_fallback
            ])

            for i, result in enumerate(bc_results):
                contact, normalized_url = need_fallback[i]
                if result.phone_found:
                    # Create a PhoneResult-like object for consistency
                    phones[normalized_url] = PhoneResult(
                        linkedin_url=contact["linkedin_url"],
                        phone=result.phone,
                        phone_type="work",
                        success=True,
                        source="BetterContact"
                    )
                    self.checkpoint.update(increment_phones=True)
                    logger.info(f"Better Contact found work phone for {contact['first_name']} {contact['last_name']}: {result.phone}")

        logger.info(f"Phone enrichment complete: {len(phones)}/{len(job_changers)} found")
        return phones

    def prepare_updates(
        self,
        contact: Dict,
        profile: LinkedInProfile,
        job_result: JobChangeResult,
        phone: Optional[str] = None,
        phone_source: Optional[str] = None,
        new_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prepare update dict for a single contact."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Check if contact has a valid LinkedIn URL (used for multiple validations)
        original_url = contact.get("linkedin_url", "")
        has_valid_url = bool(original_url) and is_valid_linkedin_url(original_url)

        update = {
            "row": contact["row"],
            "last_processed_date": today,
            "linkedin_validation_date": today,
        }

        # LinkedIn validation results
        if profile.is_private:
            update["enrichment_status"] = "Profile Private"
            logger.debug(f"Row {contact['row']}: Profile is private")
        elif profile.error:
            if "not found" in profile.error.lower():
                update["enrichment_status"] = "LinkedIn Not Found"
            elif "retry" in profile.error.lower():
                update["enrichment_status"] = "Profile Data Incomplete - Retry"
            else:
                update["enrichment_status"] = f"Error: {profile.error[:50]}"
            logger.debug(f"Row {contact['row']}: Profile has error: {profile.error}")
        else:
            # Profile successfully validated - but only confirm if contact actually has a LinkedIn URL
            if has_valid_url:
                update["confirmed_linkedin"] = "Yes"
                update["enrichment_status"] = "LinkedIn Validated"  # Clear any previous error status
                logger.debug(f"Row {contact['row']}: LinkedIn confirmed (company: {profile.current_company})")
            else:
                # No LinkedIn URL - should not reach here, but safety check
                update["confirmed_linkedin"] = "No"
                update["enrichment_status"] = "No LinkedIn URL"
                logger.warning(f"Row {contact['row']}: Profile returned but no valid LinkedIn URL - data integrity issue")

        # Job change results - only if contact has valid LinkedIn URL

        if job_result.is_job_changer and has_valid_url:
            update["job_changed"] = "Yes"
            update["new_company"] = job_result.linkedin_company
            update["new_job_title"] = job_result.linkedin_title or ""
        else:
            update["job_changed"] = "No"
            if job_result.is_job_changer and not has_valid_url:
                logger.warning(f"Row {contact['row']}: Job change detected but no valid LinkedIn URL - ignoring")

        # Phone enrichment
        if phone:
            update["new_phone"] = phone
            if phone_source:
                update["enrichment_status"] = f"Phone Found ({phone_source})"

        # Email enrichment (job changers only)
        if new_email:
            update["new_email"] = new_email
            update["enrichment_status"] = "Email Found"
        elif job_result.is_job_changer and not new_email:
            if update.get("enrichment_status", "").startswith("Phone"):
                pass  # Keep phone status
            else:
                update["enrichment_status"] = "Email Not Found"

        return update

    async def process_batch(
        self,
        batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process a single batch through the full pipeline.

        Returns:
            List of update dicts for Google Sheets
        """
        # NOTE: LinkedIn URL discovery removed - not scalable via API
        # Contacts without LinkedIn URLs will be marked as errors

        # Step 1: LinkedIn validation
        contact_profiles = await self.process_linkedin_batch(batch)

        # Step 2: Job change detection
        with_job_results = self.detect_job_changes(contact_profiles)

        # Step 3: Phone enrichment (all contacts missing phones)
        phone_results = await self.enrich_phones(batch)

        # Step 4: Email AND Phone enrichment for job changers (run in parallel)
        job_changers = [
            (c, p, j) for c, p, j in with_job_results
            if j.is_job_changer
        ]

        # Run email and phone enrichment for job changers concurrently
        email_task = self.enrich_emails_for_job_changers(job_changers)
        phone_task = self.enrich_phones_for_job_changers(job_changers)
        email_results, job_changer_phone_results = await asyncio.gather(email_task, phone_task)

        # Merge job changer phone results with general phone results
        # Job changer phones take priority (they're enriched with NEW company info)
        phone_results.update(job_changer_phone_results)

        # Prepare updates
        updates = []
        for contact, profile, job_result in with_job_results:
            url = normalize_linkedin_url(contact.get("linkedin_url", ""))

            # Get phone if enriched
            phone = None
            phone_source = None
            if url in phone_results:
                pr = phone_results[url]
                if pr.success:
                    phone = pr.phone
                    phone_source = pr.source

            # Get email if job changer
            new_email = email_results.get(url)

            update = self.prepare_updates(
                contact, profile, job_result,
                phone=phone,
                phone_source=phone_source,
                new_email=new_email
            )
            updates.append(update)

        return updates

    async def reenrich_existing_job_changers(self, start_row: int, end_row: int) -> None:
        """
        Re-enrich existing job changers who are missing emails or phones.

        This runs as a separate step before processing new contacts.
        It finds job changers in the specified range and fills in missing data.
        """
        logger.info("=" * 60)
        logger.info("RE-ENRICHING EXISTING JOB CHANGERS")
        logger.info("=" * 60)

        # Load all contacts in range
        self.sheets.connect()
        contacts = self.sheets.get_all_contacts(start_row=start_row, end_row=end_row)

        # Find job changers missing emails or phones
        job_changers_need_email = []
        contacts_need_phone = []

        for contact in contacts:
            job_changed = contact.get("job_changed", "").lower() == "yes"
            has_email = bool(contact.get("new_email"))
            has_phone = bool(contact.get("phone_number")) or bool(contact.get("new_phone"))
            has_linkedin = is_valid_linkedin_url(contact.get("linkedin_url"))

            if job_changed and not has_email and has_linkedin:
                job_changers_need_email.append(contact)

            if not has_phone and has_linkedin:
                contacts_need_phone.append(contact)

        logger.info(f"Found {len(job_changers_need_email)} job changers missing emails")
        logger.info(f"Found {len(contacts_need_phone)} contacts missing phones")

        if not job_changers_need_email and not contacts_need_phone:
            logger.info("No re-enrichment needed")
            return

        # Re-enrich emails for job changers
        if job_changers_need_email:
            logger.info("\n--- Re-enriching Emails for Job Changers ---")

            # Prepare data for email enrichment
            enrichment_data = []
            for contact in job_changers_need_email:
                enrichment_data.append({
                    "linkedin_url": contact["linkedin_url"],
                    "first_name": contact.get("first_name", ""),
                    "last_name": contact.get("last_name", ""),
                    "company": contact.get("new_company", ""),  # Use NEW company
                })

            # Try Better Contact first
            logger.info(f"Trying Better Contact for {len(enrichment_data)} contacts...")
            bc_results = await self.better_contact.enrich_emails(enrichment_data)

            email_updates = []
            need_leadsmagic = []

            for i, result in enumerate(bc_results):
                contact = job_changers_need_email[i]
                if result.email_found:
                    email_updates.append({
                        "row": contact["row"],
                        "new_email": result.email,
                        "enrichment_status": "Email Found (BetterContact)",
                    })
                    logger.info(f"  Row {contact['row']}: Found email via Better Contact: {result.email}")
                else:
                    need_leadsmagic.append((contact, enrichment_data[i]))

            # Try LeadsMagic for failures
            if need_leadsmagic:
                logger.info(f"Trying LeadsMagic for {len(need_leadsmagic)} remaining contacts...")
                lm_results = await self.leadsmagic.find_emails_batch([c for _, c in need_leadsmagic])

                for i, result in enumerate(lm_results):
                    contact, _ = need_leadsmagic[i]
                    if result.success and result.email:
                        email_updates.append({
                            "row": contact["row"],
                            "new_email": result.email,
                            "enrichment_status": "Email Found (LeadsMagic)",
                        })
                        logger.info(f"  Row {contact['row']}: Found email via LeadsMagic: {result.email}")

            # Write email updates
            if email_updates and not self.dry_run:
                self.sheets.batch_update_contacts(email_updates)
                logger.info(f"Updated {len(email_updates)} emails in spreadsheet")
            elif email_updates:
                logger.info(f"[DRY RUN] Would update {len(email_updates)} emails")

        # Re-enrich phones
        if contacts_need_phone:
            logger.info("\n--- Re-enriching Phones ---")

            # Try LeadsMagic first
            logger.info(f"Trying LeadsMagic for {len(contacts_need_phone)} contacts...")
            lm_phone_results = await self.leadsmagic.find_phones_batch([
                {"linkedin_url": c["linkedin_url"], "email": c.get("email")}
                for c in contacts_need_phone
            ])

            phone_updates = []
            need_bc_phone = []

            for i, result in enumerate(lm_phone_results):
                contact = contacts_need_phone[i]
                if result.success:
                    phone_updates.append({
                        "row": contact["row"],
                        "new_phone": result.phone,
                        "enrichment_status": "Phone Found (LeadsMagic)",
                    })
                    logger.info(f"  Row {contact['row']}: Found phone via LeadsMagic: {result.phone}")
                else:
                    need_bc_phone.append(contact)

            # Try Better Contact for failures
            if need_bc_phone:
                logger.info(f"Trying Better Contact for {len(need_bc_phone)} remaining contacts...")
                bc_phone_results = await self.better_contact.enrich_phones([
                    {
                        "linkedin_url": c["linkedin_url"],
                        "first_name": c.get("first_name", ""),
                        "last_name": c.get("last_name", ""),
                        "company": c.get("company_name", ""),
                    }
                    for c in need_bc_phone
                ])

                for i, result in enumerate(bc_phone_results):
                    contact = need_bc_phone[i]
                    if result.phone_found:
                        phone_updates.append({
                            "row": contact["row"],
                            "new_phone": result.phone,
                            "enrichment_status": "Phone Found (BetterContact)",
                        })
                        logger.info(f"  Row {contact['row']}: Found phone via Better Contact: {result.phone}")

            # Write phone updates
            if phone_updates and not self.dry_run:
                self.sheets.batch_update_contacts(phone_updates)
                logger.info(f"Updated {len(phone_updates)} phones in spreadsheet")
            elif phone_updates:
                logger.info(f"[DRY RUN] Would update {len(phone_updates)} phones")

        logger.info("\n--- Re-enrichment Complete ---")
        if job_changers_need_email:
            logger.info(f"Emails: {len([u for u in email_updates if 'new_email' in u])}/{len(job_changers_need_email)} enriched")
        if contacts_need_phone:
            logger.info(f"Phones: {len([u for u in phone_updates if 'new_phone' in u])}/{len(contacts_need_phone)} enriched")

    def check_for_new_rows(self) -> tuple[int, int]:
        """
        Check if new rows have been added to the spreadsheet since last run.

        Returns:
            Tuple of (new_row_count, new_end_row)
            new_row_count: Number of new rows detected
            new_end_row: The new end row number (for setting end_row dynamically)
        """
        existing = self.checkpoint.load()
        if not existing:
            return 0, 0

        new_row_count = self.checkpoint.detect_new_rows(self.current_total_rows)
        if new_row_count > 0:
            # Calculate the range of new rows
            known = self.checkpoint.get_known_total_rows()
            # New rows start at known+1 and go to current_total_rows
            logger.info(f"NEW ROWS DETECTED: {new_row_count} new rows (rows {known+1} to {self.current_total_rows})")
            return new_row_count, self.current_total_rows

        return 0, 0

    async def run(self, reenrich: bool = False, reenrich_end_row: int = None) -> None:
        """Run the full processing pipeline."""
        logger.info("=" * 60)
        logger.info("LinkedIn Job Change Detection Pipeline")
        logger.info("=" * 60)

        # Step 0: Re-enrich existing job changers if requested
        if reenrich:
            # Re-enrich from row 2 up to start_row (or specified end)
            reenrich_end = reenrich_end_row or (self.start_row - 1 if self.start_row > 2 else 286)
            await self.reenrich_existing_job_changers(start_row=2, end_row=reenrich_end)
            logger.info("")  # Blank line separator

        # Load contacts
        self.load_contacts()

        if not self.contacts:
            logger.warning("No contacts to process")
            return

        # Check for new rows added since last run
        new_row_count, _ = self.check_for_new_rows()
        if new_row_count > 0:
            logger.info(f"Will process {new_row_count} newly added rows in this run")

        # Check for existing checkpoint (unless force_reprocess is set)
        existing = self.checkpoint.load()
        if existing and not getattr(self, 'force_reprocess', False):
            if self.reverse:
                # In reverse mode: last_processed_row is the lowest row we've done
                # We want rows BELOW that (lower row numbers)
                resume_row = existing.last_processed_row - 1
                if resume_row >= self.start_row:
                    logger.info(f"Resuming reverse processing from row {resume_row} downward")
                    self.contacts = [c for c in self.contacts if c["row"] <= resume_row]
            else:
                # Forward mode: resume from rows above last processed
                resume_row = existing.last_processed_row + 1
                if resume_row > self.start_row:
                    logger.info(f"Resuming from row {resume_row}")
                    self.contacts = [c for c in self.contacts if c["row"] >= resume_row]
        elif getattr(self, 'force_reprocess', False):
            logger.info(f"Force reprocess enabled - processing rows {self.start_row} to {self.end_row or 'end'}")
        else:
            # Create checkpoint with appropriate starting row
            if self.reverse and self.contacts:
                # In reverse mode, start from highest row
                start = self.contacts[0]["row"]  # Already reversed, so first is highest
            else:
                start = self.start_row
            self.checkpoint.create(start, len(self.contacts), known_total_rows=self.current_total_rows)

        # Filter contacts
        to_process, skipped = self.filter_contacts()

        # Write skip statuses
        if not self.dry_run and skipped:
            skip_updates = [
                {
                    "row": c["row"],
                    "enrichment_status": c["skip_reason"],
                    "last_processed_date": datetime.now().strftime("%Y-%m-%d"),
                }
                for c in skipped
            ]
            self.sheets.batch_update_contacts(skip_updates)

        # Process in batches
        total_batches = (len(to_process) + self.batch_size - 1) // self.batch_size
        logger.info(f"Processing {len(to_process)} contacts in {total_batches} batches")

        for i in range(0, len(to_process), self.batch_size):
            batch = to_process[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1

            logger.info(f"\n--- Batch {batch_num}/{total_batches} (rows {batch[0]['row']}-{batch[-1]['row']}) ---")

            try:
                updates = await self.process_batch(batch)

                # Write updates to sheets
                if not self.dry_run:
                    self.sheets.batch_update_contacts(updates)
                    logger.info(f"Updated {len(updates)} rows in Google Sheets")
                else:
                    logger.info(f"[DRY RUN] Would update {len(updates)} rows")

                # Update checkpoint
                for update in updates:
                    self.checkpoint.update(
                        row=update["row"],
                        increment_processed=True
                    )
                self.checkpoint.save()

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                self.checkpoint.update(increment_errors=True)
                # Add failed rows for retry
                for contact in batch:
                    self.checkpoint.update(add_failed_row=contact["row"])
                self.checkpoint.save()
                continue

        # Update known_total_rows for next run (to detect new rows)
        self.checkpoint.update_known_total_rows(self.current_total_rows)

        # Print summary
        self.checkpoint.print_summary()
        logger.info("Processing complete!")


def main():
    """CLI entry point."""
    # Validate API keys early
    api_errors = validate_api_keys()
    if api_errors:
        print("ERROR: Missing required configuration:")
        for error in api_errors:
            print(f"  - {error}")
        print("\nPlease configure your .env file. See .env.example for reference.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="LinkedIn Job Change Detection Pipeline"
    )
    parser.add_argument(
        "--start-row",
        type=int,
        default=34,
        help="First row to process (default: 34)"
    )
    parser.add_argument(
        "--end-row",
        type=int,
        default=None,
        help="Last row to process (default: all)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Batch size for processing (default: 20)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing to Google Sheets"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show checkpoint status and exit"
    )
    parser.add_argument(
        "--reenrich",
        action="store_true",
        help="Re-enrich existing job changers missing emails/phones before processing new rows"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocess specific row range, ignoring checkpoint resume logic"
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Process from bottom to top (highest row to lowest). Uses separate checkpoint."
    )
    parser.add_argument(
        "--detect-new",
        action="store_true",
        help="Check if new rows have been added to the spreadsheet since last run"
    )

    args = parser.parse_args()

    # Show status only
    if args.status:
        checkpoint = CheckpointManager(processing_config.checkpoint_dir)
        if checkpoint.exists():
            checkpoint.load()
            checkpoint.print_summary()
        else:
            print("No checkpoint found")
        return

    # Detect new rows only
    if args.detect_new:
        print("Checking for new rows in spreadsheet...")
        sheets = SheetsClient()
        sheets.connect()
        current_rows = sheets.get_row_count_with_data()
        print(f"Current spreadsheet has {current_rows} rows with data")

        # Check forward checkpoint
        fwd_checkpoint = CheckpointManager(processing_config.checkpoint_dir, checkpoint_name="progress")
        if fwd_checkpoint.exists():
            fwd_checkpoint.load()
            known = fwd_checkpoint.get_known_total_rows()
            if known > 0:
                new_count = current_rows - known
                if new_count > 0:
                    print(f"\n>>> FORWARD: {new_count} new rows detected (was {known}, now {current_rows})")
                    print(f"    New rows are in range: {known+1} to {current_rows}")
                else:
                    print(f"\n>>> FORWARD: No new rows (last known: {known})")
            else:
                print(f"\n>>> FORWARD: Row tracking not initialized (will be set on next run)")
        else:
            print("\n>>> FORWARD: No checkpoint exists yet")

        # Check reverse checkpoint
        rev_checkpoint = CheckpointManager(processing_config.checkpoint_dir, checkpoint_name="progress_reverse")
        if rev_checkpoint.exists():
            rev_checkpoint.load()
            known = rev_checkpoint.get_known_total_rows()
            if known > 0:
                new_count = current_rows - known
                if new_count > 0:
                    print(f"\n>>> REVERSE: {new_count} new rows detected (was {known}, now {current_rows})")
                else:
                    print(f"\n>>> REVERSE: No new rows (last known: {known})")
            else:
                print(f"\n>>> REVERSE: Row tracking not initialized")
        else:
            print("\n>>> REVERSE: No checkpoint exists yet")

        return

    # Run processor
    processor = JobChangeProcessor(
        start_row=args.start_row,
        end_row=args.end_row,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        reverse=args.reverse,
    )
    processor.force_reprocess = args.force

    asyncio.run(processor.run(reenrich=args.reenrich))


if __name__ == "__main__":
    main()
