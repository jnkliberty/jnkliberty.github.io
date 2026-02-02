"""
Bright Data API client for LinkedIn profile fetching.
"""

import asyncio
import logging
import re
import ssl
import certifi
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import api_config

logger = logging.getLogger(__name__)


def _normalize_linkedin_url(url) -> str:
    """
    Normalize LinkedIn URL for consistent matching.

    Handles variations like:
    - http vs https
    - www vs non-www
    - trailing slashes
    - case differences
    - nested dict structures from API responses
    - country-specific domains (no.linkedin.com, za.linkedin.com, etc.)
    """
    if not url:
        return ""
    # Handle case where url might be a dict (some APIs return nested structures)
    if isinstance(url, dict):
        url = url.get("url", url.get("value", url.get("href", "")))
    # Ensure we have a string
    if not isinstance(url, str):
        logger.warning(f"Unexpected URL type: {type(url)} - {url}")
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


@dataclass
class LinkedInProfile:
    """Parsed LinkedIn profile data."""
    url: str
    name: Optional[str] = None
    headline: Optional[str] = None
    current_company: Optional[str] = None
    current_title: Optional[str] = None
    location: Optional[str] = None
    experiences: List[Dict[str, Any]] = None
    is_private: bool = False
    error: Optional[str] = None

    def __post_init__(self):
        if self.experiences is None:
            self.experiences = []


class BrightDataClient:
    """Client for Bright Data LinkedIn profile API."""

    BASE_URL = "https://api.brightdata.com/datasets/v3"

    def __init__(self, api_key: str = None, dataset_id: str = None):
        self.api_key = api_key or api_config.bright_data_api_key
        self.dataset_id = dataset_id or api_config.bright_data_dataset_id
        self.batch_size = api_config.bright_data_batch_size
        self.poll_interval = api_config.bright_data_poll_interval
        self.max_poll_attempts = api_config.bright_data_max_poll_attempts

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _trigger_batch(
        self,
        session: aiohttp.ClientSession,
        urls: List[str]
    ) -> str:
        """
        Trigger a batch profile fetch.

        Returns snapshot_id for polling.
        """
        trigger_url = f"{self.BASE_URL}/trigger?dataset_id={self.dataset_id}&include_errors=True&format=json"
        payload = [{"url": url} for url in urls]

        logger.debug(f"Triggering batch of {len(urls)} URLs")

        async with session.post(trigger_url, headers=self._get_headers(), json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            snapshot_id = data.get("snapshot_id")
            logger.info(f"Batch triggered, snapshot_id: {snapshot_id}")
            return snapshot_id

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _poll_snapshot(
        self,
        session: aiohttp.ClientSession,
        snapshot_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Poll for snapshot results.

        Returns None if still processing, list of results if ready.
        """
        poll_url = f"{self.BASE_URL}/snapshot/{snapshot_id}?format=json"

        async with session.get(poll_url, headers=self._get_headers()) as resp:
            if resp.status == 202:
                # Still processing
                return None
            resp.raise_for_status()
            data = await resp.json()

            # Handle {"status": "running"} response
            if isinstance(data, dict) and data.get("status") == "running":
                return None

            return data

    async def _wait_for_results(
        self,
        session: aiohttp.ClientSession,
        snapshot_id: str
    ) -> List[Dict[str, Any]]:
        """Wait for and return snapshot results."""
        for attempt in range(self.max_poll_attempts):
            results = await self._poll_snapshot(session, snapshot_id)
            if results is not None:
                logger.info(f"Got {len(results)} results after {attempt + 1} polls")
                return results

            logger.debug(f"Poll {attempt + 1}/{self.max_poll_attempts}, waiting {self.poll_interval}s")
            await asyncio.sleep(self.poll_interval)

        raise TimeoutError(f"Snapshot {snapshot_id} did not complete after {self.max_poll_attempts} polls")

    def _parse_profile(self, raw_data: Dict[str, Any], original_url: str) -> LinkedInProfile:
        """Parse raw Bright Data response into LinkedInProfile."""
        if not raw_data:
            return LinkedInProfile(url=original_url, error="No data returned")

        # Check for errors
        if raw_data.get("error") or raw_data.get("status") == "error":
            error_msg = raw_data.get("error", raw_data.get("message", "Unknown error"))
            return LinkedInProfile(url=original_url, error=error_msg)

        # Check if profile is private
        if raw_data.get("is_private") or "private" in str(raw_data.get("error", "")).lower():
            return LinkedInProfile(url=original_url, is_private=True)

        # Extract current company and title from experiences
        experiences = raw_data.get("experience", []) or []
        current_company = None
        current_title = None

        # First, find current job from experiences
        for exp in experiences:
            # Check for current position - handle various data formats
            is_current = exp.get("is_current")
            end_date = exp.get("end_date")
            # Consider current if: is_current is True, OR end_date is empty/None/Present
            is_current_job = (
                is_current is True or
                (is_current is None and not end_date) or
                (isinstance(end_date, str) and end_date.lower() == "present")
            )
            if is_current_job:
                # Handle company as either string or dict
                company_val = exp.get("company_name") or exp.get("company")
                if isinstance(company_val, dict):
                    current_company = company_val.get("name") or company_val.get("company_name")
                else:
                    current_company = company_val
                # Get title from multiple possible fields
                current_title = (
                    exp.get("title") or
                    exp.get("position") or
                    exp.get("job_title") or
                    exp.get("role")
                )
                if current_company:  # Only break if we found a company
                    break

        # Fallback to top-level fields for company
        if not current_company:
            company_field = raw_data.get("current_company") or raw_data.get("company")
            # Handle both string and dict company values
            if isinstance(company_field, dict):
                current_company = company_field.get("name") or company_field.get("company_name")
                # Also extract title from current_company dict if available
                if not current_title:
                    current_title = company_field.get("title")
            else:
                current_company = company_field
        # Also try current_company_name field
        if not current_company:
            current_company = raw_data.get("current_company_name")

        # Fallback to top-level fields for title
        if not current_title:
            current_title = (
                raw_data.get("current_company_position") or
                raw_data.get("current_position") or
                raw_data.get("position") or
                raw_data.get("title") or
                raw_data.get("job_title") or
                raw_data.get("headline")  # headline is last resort, often not a job title
            )

        # Log if we found company but not title for debugging
        if current_company and not current_title:
            logger.warning(f"Found company '{current_company}' but no title for {original_url}")
            # Log available fields to help debug
            if experiences:
                first_exp = experiences[0]
                logger.debug(f"First experience fields: {list(first_exp.keys())}")
            logger.debug(f"Top-level fields with values: {[k for k, v in raw_data.items() if v and k not in ['experience', 'education', 'skills']]}")

        return LinkedInProfile(
            url=raw_data.get("url", original_url),
            name=raw_data.get("name") or raw_data.get("full_name"),
            headline=raw_data.get("headline"),
            current_company=current_company,
            current_title=current_title,
            location=raw_data.get("location"),
            experiences=[
                {
                    "company_name": e.get("company_name") or e.get("company"),
                    "title": e.get("title") or e.get("position"),
                    "is_current": e.get("is_current", e.get("end_date") is None),
                    "start_date": e.get("start_date"),
                    "end_date": e.get("end_date"),
                }
                for e in experiences
            ],
        )

    def _is_retryable_error(self, profile: LinkedInProfile) -> bool:
        """Check if a profile error is retryable (transient)."""
        if not profile.error:
            return False
        error_lower = profile.error.lower()
        # Retryable errors: incomplete data, timeout, retry suggestions, temporary failures
        retryable_keywords = ["retry", "incomplete", "timeout", "temporary", "try again", "not returned"]
        return any(keyword in error_lower for keyword in retryable_keywords)

    async def _fetch_profiles_single_attempt(
        self,
        session: aiohttp.ClientSession,
        urls: List[str]
    ) -> List[LinkedInProfile]:
        """Single attempt to fetch profiles (internal helper)."""
        # Trigger batch
        snapshot_id = await self._trigger_batch(session, urls)

        # Wait for results
        results = await self._wait_for_results(session, snapshot_id)

        # Parse results, matching back to original URLs
        profiles = []
        url_to_result = {}

        # Map results by URL (using normalized URLs for matching)
        for result in results:
            # Try multiple possible URL field names
            result_url = (
                result.get("url") or
                result.get("input_url") or
                result.get("linkedin_url") or
                result.get("profile_url") or
                result.get("input", {}).get("url", "") if isinstance(result.get("input"), dict) else ""
            )
            if result_url:
                normalized = _normalize_linkedin_url(result_url)
                url_to_result[normalized] = result

        # Parse in original order
        for url in urls:
            normalized_url = _normalize_linkedin_url(url)
            if normalized_url in url_to_result:
                profile = self._parse_profile(url_to_result[normalized_url], url)
            else:
                profile = LinkedInProfile(url=url, error="Profile not returned")
                logger.warning(f"No profile returned for {url}")
            profiles.append(profile)

        return profiles

    async def fetch_profiles(self, urls: List[str], max_retries: int = 1) -> List[LinkedInProfile]:
        """
        Fetch LinkedIn profiles for a list of URLs with automatic retry for transient errors.

        Args:
            urls: List of LinkedIn profile URLs (max 20)
            max_retries: Number of retry attempts for profiles with transient errors (default: 1)

        Returns:
            List of LinkedInProfile objects
        """
        if not urls:
            return []

        if len(urls) > self.batch_size:
            logger.warning(f"Batch size {len(urls)} exceeds max {self.batch_size}, truncating")
            urls = urls[:self.batch_size]

        # Create SSL context with certifi certificates
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                # First attempt
                profiles = await self._fetch_profiles_single_attempt(session, urls)

                # Check for retryable errors and retry if needed
                for retry_num in range(max_retries):
                    # Find profiles with retryable errors
                    retry_indices = []
                    retry_urls = []
                    for i, profile in enumerate(profiles):
                        if self._is_retryable_error(profile):
                            retry_indices.append(i)
                            retry_urls.append(urls[i])

                    if not retry_urls:
                        break  # No retryable errors, we're done

                    logger.info(f"Retry attempt {retry_num + 1}: {len(retry_urls)} profiles with transient errors")

                    # Wait a bit before retrying (give Bright Data time to recover)
                    await asyncio.sleep(30)

                    # Retry failed profiles
                    try:
                        retry_profiles = await self._fetch_profiles_single_attempt(session, retry_urls)

                        # Merge retry results back into main profiles list
                        for i, retry_profile in enumerate(retry_profiles):
                            original_idx = retry_indices[i]
                            # Only update if retry was successful (no error or different error)
                            if not retry_profile.error or not self._is_retryable_error(retry_profile):
                                profiles[original_idx] = retry_profile
                                if not retry_profile.error:
                                    logger.info(f"Retry successful for {retry_urls[i]}")
                    except Exception as retry_error:
                        logger.warning(f"Retry attempt {retry_num + 1} failed: {retry_error}")

                return profiles

            except Exception as e:
                logger.error(f"Failed to fetch profiles: {e}")
                # Return error profiles for all URLs
                return [LinkedInProfile(url=url, error=str(e)) for url in urls]

    async def fetch_profiles_concurrent(
        self,
        urls: List[str],
        max_concurrent: int = None
    ) -> List[LinkedInProfile]:
        """
        Fetch profiles with concurrent batches.

        Args:
            urls: List of all LinkedIn URLs to fetch
            max_concurrent: Max concurrent batch requests

        Returns:
            List of all LinkedInProfile objects
        """
        max_concurrent = max_concurrent or api_config.bright_data_concurrent_batches

        # Split into batches
        batches = [urls[i:i + self.batch_size] for i in range(0, len(urls), self.batch_size)]
        logger.info(f"Processing {len(urls)} URLs in {len(batches)} batches, {max_concurrent} concurrent")

        all_profiles = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_batch(batch_urls: List[str]) -> List[LinkedInProfile]:
            async with semaphore:
                return await self.fetch_profiles(batch_urls)

        # Process all batches with concurrency limit
        tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"Batch {i} failed: {result}")
                # Add error profiles for this batch
                all_profiles.extend([
                    LinkedInProfile(url=url, error=str(result))
                    for url in batches[i]
                ])
            else:
                all_profiles.extend(result)

        return all_profiles


class LinkedInSearchClient:
    """Client for discovering LinkedIn URLs via search APIs."""

    BRIGHT_DATA_SEARCH_URL = "https://api.brightdata.com/datasets/v3"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or api_config.bright_data_api_key

    async def search_via_google(
        self,
        first_name: str,
        last_name: str,
        company: str,
        title: str = None
    ) -> Optional[str]:
        """
        Search for LinkedIn profile URL using DuckDuckGo HTML search.

        Args:
            first_name: Person's first name
            last_name: Person's last name
            company: Company name
            title: Optional job title for more specific search

        Returns:
            LinkedIn profile URL if found, None otherwise
        """
        import urllib.parse

        # Build search query for DuckDuckGo
        query_parts = [f'site:linkedin.com/in', f'{first_name} {last_name}']
        if company:
            query_parts.append(company)

        query = " ".join(query_parts)
        encoded_query = urllib.parse.quote_plus(query)
        logger.debug(f"Searching for LinkedIn profile: {query}")

        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)

            async with aiohttp.ClientSession(connector=connector) as session:
                # Use DuckDuckGo HTML search
                search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                }

                async with session.get(search_url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.warning(f"DuckDuckGo search failed with status {resp.status}")
                        return None

                    html = await resp.text()

                    # Parse HTML for LinkedIn URLs using regex
                    import re
                    # Look for LinkedIn profile URLs in href attributes
                    linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-_]+)'
                    matches = re.findall(linkedin_pattern, html)

                    if matches:
                        # Return the first unique LinkedIn profile URL
                        username = matches[0]
                        url = f"https://linkedin.com/in/{username}"
                        logger.info(f"Found LinkedIn URL for {first_name} {last_name}: {url}")
                        return url

                    logger.debug(f"No LinkedIn profile found for {first_name} {last_name}")
                    return None

        except Exception as e:
            logger.warning(f"LinkedIn search failed for {first_name} {last_name}: {e}")
            return None

    async def search_batch(
        self,
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, Optional[str]]:
        """
        Search for LinkedIn URLs for multiple contacts.

        Args:
            contacts: List of dicts with first_name, last_name, company, title

        Returns:
            Dict mapping contact identifier to discovered URL (or None)
        """
        results = {}

        for contact in contacts:
            first_name = contact.get("first_name", "")
            last_name = contact.get("last_name", "")
            company = contact.get("company_name", contact.get("company", ""))
            title = contact.get("job_title", contact.get("title", ""))

            # Create unique key for this contact
            key = f"{first_name}_{last_name}_{company}".lower()

            url = await self.search_via_google(first_name, last_name, company, title)
            results[key] = url

            # Small delay between searches to avoid rate limiting
            await asyncio.sleep(0.5)

        found = sum(1 for v in results.values() if v)
        logger.info(f"LinkedIn URL discovery: {found}/{len(contacts)} found")

        return results


async def search_linkedin_profile(
    first_name: str,
    last_name: str,
    company: str,
    title: str = None
) -> Optional[str]:
    """
    Search for a LinkedIn profile URL using name and company.

    Uses Google search via Bright Data to find LinkedIn profiles.

    Args:
        first_name: Person's first name
        last_name: Person's last name
        company: Company name
        title: Optional job title for more specific search

    Returns:
        LinkedIn profile URL if found, None otherwise
    """
    client = LinkedInSearchClient()
    return await client.search_via_google(first_name, last_name, company, title)
