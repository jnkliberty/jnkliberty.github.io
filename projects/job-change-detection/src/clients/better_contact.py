"""
Better Contact API client for email and phone enrichment.
"""

import asyncio
import logging
import ssl
import certifi
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import api_config
from processors.filters import normalize_linkedin_url

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of Better Contact enrichment."""
    linkedin_url: str
    first_name: str
    last_name: str
    company: str
    email: Optional[str] = None
    phone: Optional[str] = None
    email_found: bool = False
    phone_found: bool = False
    error: Optional[str] = None
    source: str = "BetterContact"


class BetterContactClient:
    """Client for Better Contact async enrichment API."""

    BASE_URL = "https://app.bettercontact.rocks/api/v2"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or api_config.better_contact_api_key
        self.batch_size = api_config.better_contact_batch_size
        self.poll_interval = api_config.better_contact_poll_interval

    def _get_headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _submit_batch(
        self,
        session: aiohttp.ClientSession,
        contacts: List[Dict[str, Any]],
        enrich_email: bool = True,
        enrich_phone: bool = False
    ) -> str:
        """
        Submit a batch for async enrichment.

        Returns request_id for polling.
        """
        endpoint = f"{self.BASE_URL}/async"

        # Format contacts for Better Contact API
        data = []
        for contact in contacts:
            entry = {
                "first_name": contact.get("first_name", ""),
                "last_name": contact.get("last_name", ""),
                "company": contact.get("company", ""),
            }
            if contact.get("linkedin_url"):
                entry["linkedin_url"] = contact["linkedin_url"]
            data.append(entry)

        payload = {
            "data": data,
            "enrich_email_address": enrich_email,
            "enrich_phone_number": enrich_phone,
        }

        logger.debug(f"Submitting batch of {len(data)} contacts")

        async with session.post(
            endpoint,
            headers=self._get_headers(),
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status == 429:
                logger.warning("Better Contact rate limited")
                await asyncio.sleep(60)
                raise aiohttp.ClientError("Rate limited")

            resp.raise_for_status()
            result = await resp.json()
            request_id = result.get("request_id") or result.get("id")
            logger.info(f"Batch submitted, request_id: {request_id}")
            return request_id

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _poll_results(
        self,
        session: aiohttp.ClientSession,
        request_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Poll for async results.

        Returns None if still processing, list of results if ready.
        """
        endpoint = f"{self.BASE_URL}/async/{request_id}"

        async with session.get(
            endpoint,
            headers=self._get_headers(),
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status == 202:
                # Still processing
                return None

            resp.raise_for_status()
            data = await resp.json()

            # Check if complete
            status = data.get("status", "").lower()
            # Handle all known "still processing" statuses
            if status in ["processing", "pending", "queued", "in progress", "not_started", "started"]:
                return None

            # Only return results if we actually have them
            results = data.get("results", data.get("data"))
            if results is None:
                # No results key and not a known "still processing" status
                # This might be an unknown status, treat as still processing
                logger.warning(f"Unknown response format: {data}")
                return None
            return results

    async def _wait_for_results(
        self,
        session: aiohttp.ClientSession,
        request_id: str,
        max_polls: int = 60
    ) -> List[Dict[str, Any]]:
        """Wait for and return async results."""
        for attempt in range(max_polls):
            results = await self._poll_results(session, request_id)
            if results is not None:
                logger.info(f"Got {len(results)} results after {attempt + 1} polls")
                return results

            logger.debug(f"Poll {attempt + 1}/{max_polls}, waiting {self.poll_interval}s")
            await asyncio.sleep(self.poll_interval)

        raise TimeoutError(f"Request {request_id} did not complete after {max_polls} polls")

    def _extract_url_from_result(self, raw: Dict[str, Any]) -> str:
        """Extract and normalize LinkedIn URL from API result."""
        url = raw.get("linkedin_url") or raw.get("linkedin") or ""
        return normalize_linkedin_url(url)

    def _match_results_to_contacts(
        self,
        raw_results: List[Dict[str, Any]],
        contacts: List[Dict[str, Any]]
    ) -> List[tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Match API results back to original contacts using LinkedIn URL.

        This is critical for data integrity - we cannot assume the API returns
        results in the same order as inputs. We must match by URL.

        Returns:
            List of (raw_result, original_contact) tuples in the same order as contacts
        """
        # Build a map from normalized URL to raw result
        result_map = {}
        for raw in raw_results:
            url = self._extract_url_from_result(raw)
            if url:
                result_map[url] = raw
            else:
                # Try to match by name as fallback
                name_key = f"{raw.get('first_name', '').lower()}_{raw.get('last_name', '').lower()}"
                if name_key and name_key != "_":
                    result_map[f"name:{name_key}"] = raw

        # Match each contact to its result
        matched = []
        for contact in contacts:
            url = normalize_linkedin_url(contact.get("linkedin_url", ""))
            raw = result_map.get(url)

            # Fallback: try matching by name if URL match failed
            if raw is None:
                name_key = f"name:{contact.get('first_name', '').lower()}_{contact.get('last_name', '').lower()}"
                raw = result_map.get(name_key, {})

            if raw is None:
                raw = {}
                logger.warning(f"No result found for contact: {contact.get('first_name')} {contact.get('last_name')} ({url})")

            matched.append((raw, contact))

        return matched

    def _parse_result(
        self,
        raw: Dict[str, Any],
        original: Dict[str, Any]
    ) -> EnrichmentResult:
        """Parse raw API result into EnrichmentResult."""
        # Better Contact API uses 'contact_email_address' and 'contact_phone_number'
        email = (
            raw.get("contact_email_address") or
            raw.get("email") or
            raw.get("email_address")
        )
        phone = (
            raw.get("contact_phone_number") or
            raw.get("phone") or
            raw.get("phone_number") or
            raw.get("mobile")
        )

        # Check validity
        email_valid = email and "@" in email and not email.lower().startswith("noreply")
        phone_valid = phone and len(phone.replace("+", "").replace("-", "").replace(" ", "")) >= 10

        return EnrichmentResult(
            linkedin_url=original.get("linkedin_url", ""),
            first_name=original.get("first_name", ""),
            last_name=original.get("last_name", ""),
            company=original.get("company", ""),
            email=email if email_valid else None,
            phone=phone if phone_valid else None,
            email_found=email_valid,
            phone_found=phone_valid,
            error=raw.get("error"),
        )

    async def enrich_emails(
        self,
        contacts: List[Dict[str, Any]]
    ) -> List[EnrichmentResult]:
        """
        Enrich emails for a list of contacts.

        Args:
            contacts: List of dicts with first_name, last_name, company, linkedin_url

        Returns:
            List of EnrichmentResult objects (in same order as input contacts)
        """
        if not contacts:
            return []

        # Create SSL context with certifi certificates
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                # Submit batch
                request_id = await self._submit_batch(
                    session, contacts,
                    enrich_email=True,
                    enrich_phone=False
                )

                # Wait for results
                raw_results = await self._wait_for_results(session, request_id)

                # Match results to contacts using URL-based matching (NOT index-based!)
                # This is critical for data integrity
                matched = self._match_results_to_contacts(raw_results, contacts)

                # Parse matched results
                results = []
                for raw, original in matched:
                    results.append(self._parse_result(raw, original))

                return results

            except Exception as e:
                logger.error(f"Email enrichment failed: {e}")
                return [
                    EnrichmentResult(
                        linkedin_url=c.get("linkedin_url", ""),
                        first_name=c.get("first_name", ""),
                        last_name=c.get("last_name", ""),
                        company=c.get("company", ""),
                        error=str(e)
                    )
                    for c in contacts
                ]

    async def enrich_phones(
        self,
        contacts: List[Dict[str, Any]]
    ) -> List[EnrichmentResult]:
        """
        Enrich phones for a list of contacts (fallback for LeadsMagic).

        Args:
            contacts: List of dicts with first_name, last_name, company, linkedin_url

        Returns:
            List of EnrichmentResult objects (in same order as input contacts)
        """
        if not contacts:
            return []

        # Create SSL context with certifi certificates
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                # Submit batch
                request_id = await self._submit_batch(
                    session, contacts,
                    enrich_email=False,
                    enrich_phone=True
                )

                # Wait for results
                raw_results = await self._wait_for_results(session, request_id)

                # Match results to contacts using URL-based matching (NOT index-based!)
                # This is critical for data integrity
                matched = self._match_results_to_contacts(raw_results, contacts)

                # Parse matched results
                results = []
                for raw, original in matched:
                    result = self._parse_result(raw, original)
                    result.source = "BetterContact"
                    results.append(result)

                return results

            except Exception as e:
                logger.error(f"Phone enrichment failed: {e}")
                return [
                    EnrichmentResult(
                        linkedin_url=c.get("linkedin_url", ""),
                        first_name=c.get("first_name", ""),
                        last_name=c.get("last_name", ""),
                        company=c.get("company", ""),
                        error=str(e)
                    )
                    for c in contacts
                ]

    async def enrich_batch(
        self,
        contacts: List[Dict[str, Any]],
        enrich_email: bool = True,
        enrich_phone: bool = False,
        max_concurrent: int = None
    ) -> List[EnrichmentResult]:
        """
        Enrich a large batch with automatic chunking.

        Args:
            contacts: List of contact dicts
            enrich_email: Whether to enrich emails
            enrich_phone: Whether to enrich phones
            max_concurrent: Max concurrent batch requests

        Returns:
            List of EnrichmentResult objects (in same order as input contacts)
        """
        max_concurrent = max_concurrent or api_config.better_contact_concurrent

        # Split into batches
        batches = [
            contacts[i:i + self.batch_size]
            for i in range(0, len(contacts), self.batch_size)
        ]

        logger.info(f"Processing {len(contacts)} contacts in {len(batches)} batches")

        all_results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        # Need to capture self for use in nested function
        client = self

        async def process_batch(batch: List[Dict[str, Any]]) -> List[EnrichmentResult]:
            async with semaphore:
                ssl_ctx = ssl.create_default_context(cafile=certifi.where())
                conn = aiohttp.TCPConnector(ssl=ssl_ctx)
                async with aiohttp.ClientSession(connector=conn) as session:
                    request_id = await client._submit_batch(
                        session, batch,
                        enrich_email=enrich_email,
                        enrich_phone=enrich_phone
                    )
                    raw_results = await client._wait_for_results(session, request_id)

                    # Match results to contacts using URL-based matching (NOT index-based!)
                    # This is critical for data integrity
                    matched = client._match_results_to_contacts(raw_results, batch)
                    return [
                        client._parse_result(raw, original)
                        for raw, original in matched
                    ]

        tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"Batch {i} failed: {result}")
                all_results.extend([
                    EnrichmentResult(
                        linkedin_url=c.get("linkedin_url", ""),
                        first_name=c.get("first_name", ""),
                        last_name=c.get("last_name", ""),
                        company=c.get("company", ""),
                        error=str(result)
                    )
                    for c in batches[i]
                ])
            else:
                all_results.extend(result)

        return all_results
