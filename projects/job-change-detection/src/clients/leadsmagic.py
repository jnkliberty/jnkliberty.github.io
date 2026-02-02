"""
LeadsMagic API client for phone and email enrichment.
"""

import asyncio
import logging
import ssl
import certifi
from dataclasses import dataclass
from typing import Optional, List

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import api_config

logger = logging.getLogger(__name__)


@dataclass
class PhoneResult:
    """Result of phone enrichment."""
    linkedin_url: str
    phone: Optional[str] = None
    phone_type: Optional[str] = None  # mobile, work, etc.
    success: bool = False
    error: Optional[str] = None
    source: str = "LeadsMagic"


@dataclass
class EmailResult:
    """Result of email enrichment."""
    linkedin_url: str
    email: Optional[str] = None
    email_status: Optional[str] = None  # valid, valid_catch_all, catch_all, not_found
    success: bool = False
    error: Optional[str] = None
    source: str = "LeadsMagic"


class LeadsMagicClient:
    """Client for LeadsMagic mobile finder API."""

    BASE_URL = "https://api.leadmagic.io/v1"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or api_config.leadsmagic_api_key
        self.rate_limit = api_config.leadsmagic_rate_limit
        self.concurrent = api_config.leadsmagic_concurrent
        self._request_count = 0
        self._last_reset = None

    def _get_headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _find_mobile(
        self,
        session: aiohttp.ClientSession,
        linkedin_url: str,
        work_email: Optional[str] = None
    ) -> PhoneResult:
        """
        Find mobile number for a LinkedIn profile.

        Args:
            linkedin_url: LinkedIn profile URL
            work_email: Optional work email to improve match rate

        Returns:
            PhoneResult with phone number if found
        """
        endpoint = f"{self.BASE_URL}/people/mobile-finder"

        payload = {"profile_url": linkedin_url}
        if work_email:
            payload["work_email"] = work_email

        try:
            async with session.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 429:
                    # Rate limited
                    logger.warning("LeadsMagic rate limit hit, waiting...")
                    await asyncio.sleep(60)
                    raise aiohttp.ClientError("Rate limited")

                if resp.status == 404:
                    return PhoneResult(
                        linkedin_url=linkedin_url,
                        success=False,
                        error="Phone not found"
                    )

                if resp.status != 200:
                    error_text = await resp.text()
                    return PhoneResult(
                        linkedin_url=linkedin_url,
                        success=False,
                        error=f"API error {resp.status}: {error_text}"
                    )

                data = await resp.json()

                # Extract phone from response
                phone = data.get("mobile") or data.get("phone") or data.get("mobile_phone")

                if phone:
                    return PhoneResult(
                        linkedin_url=linkedin_url,
                        phone=phone,
                        phone_type=data.get("phone_type", "mobile"),
                        success=True,
                    )
                else:
                    return PhoneResult(
                        linkedin_url=linkedin_url,
                        success=False,
                        error="No phone in response"
                    )

        except asyncio.TimeoutError:
            return PhoneResult(
                linkedin_url=linkedin_url,
                success=False,
                error="Request timeout"
            )
        except aiohttp.ClientError as e:
            return PhoneResult(
                linkedin_url=linkedin_url,
                success=False,
                error=str(e)
            )

    async def find_phone(
        self,
        linkedin_url: str,
        work_email: Optional[str] = None
    ) -> PhoneResult:
        """
        Find phone for a single LinkedIn profile.

        Args:
            linkedin_url: LinkedIn profile URL
            work_email: Optional work email

        Returns:
            PhoneResult
        """
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            return await self._find_mobile(session, linkedin_url, work_email)

    async def find_phones_batch(
        self,
        contacts: List[dict],
        max_concurrent: int = None
    ) -> List[PhoneResult]:
        """
        Find phones for multiple contacts with rate limiting.

        Args:
            contacts: List of dicts with 'linkedin_url' and optionally 'email'
            max_concurrent: Max concurrent requests

        Returns:
            List of PhoneResult objects
        """
        max_concurrent = max_concurrent or self.concurrent
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def process_contact(contact: dict) -> PhoneResult:
            async with semaphore:
                # Rate limiting: stay well under 300/min
                await asyncio.sleep(0.2)  # 5 requests per second = 300/min
                ssl_ctx = ssl.create_default_context(cafile=certifi.where())
                conn = aiohttp.TCPConnector(ssl=ssl_ctx)
                async with aiohttp.ClientSession(connector=conn) as session:
                    return await self._find_mobile(
                        session,
                        contact.get("linkedin_url", ""),
                        contact.get("email")
                    )

        logger.info(f"Processing {len(contacts)} contacts for phone enrichment")

        # Process with concurrency limit
        tasks = [process_contact(c) for c in contacts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to PhoneResult
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(PhoneResult(
                    linkedin_url=contacts[i].get("linkedin_url", ""),
                    success=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)

        success_count = sum(1 for r in final_results if r.success)
        logger.info(f"Phone enrichment complete: {success_count}/{len(final_results)} found")

        return final_results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _find_email(
        self,
        session: aiohttp.ClientSession,
        first_name: str,
        last_name: str,
        company: str,
        linkedin_url: str = ""
    ) -> EmailResult:
        """
        Find email for a person using LeadsMagic email-finder.

        Args:
            first_name: Person's first name
            last_name: Person's last name
            company: Company name (used as company_name parameter)
            linkedin_url: LinkedIn URL (for tracking purposes)

        Returns:
            EmailResult with email if found
        """
        endpoint = f"{self.BASE_URL}/people/email-finder"

        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company,
        }

        try:
            async with session.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 429:
                    logger.warning("LeadsMagic rate limit hit, waiting...")
                    await asyncio.sleep(60)
                    raise aiohttp.ClientError("Rate limited")

                if resp.status == 404:
                    return EmailResult(
                        linkedin_url=linkedin_url,
                        success=False,
                        error="Email not found"
                    )

                if resp.status != 200:
                    error_text = await resp.text()
                    return EmailResult(
                        linkedin_url=linkedin_url,
                        success=False,
                        error=f"API error {resp.status}: {error_text}"
                    )

                data = await resp.json()

                # Extract email from response
                email = data.get("email")
                status = data.get("status", "").lower()

                # Check if email is valid (not just catch-all or not found)
                if email and status in ["valid", "valid_catch_all"]:
                    return EmailResult(
                        linkedin_url=linkedin_url,
                        email=email,
                        email_status=status,
                        success=True,
                    )
                else:
                    return EmailResult(
                        linkedin_url=linkedin_url,
                        email_status=status,
                        success=False,
                        error=data.get("message", "No valid email found")
                    )

        except asyncio.TimeoutError:
            return EmailResult(
                linkedin_url=linkedin_url,
                success=False,
                error="Request timeout"
            )
        except aiohttp.ClientError as e:
            return EmailResult(
                linkedin_url=linkedin_url,
                success=False,
                error=str(e)
            )

    async def find_email(
        self,
        first_name: str,
        last_name: str,
        company: str,
        linkedin_url: str = ""
    ) -> EmailResult:
        """
        Find email for a single person.

        Args:
            first_name: Person's first name
            last_name: Person's last name
            company: Company name
            linkedin_url: LinkedIn URL (for tracking)

        Returns:
            EmailResult
        """
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            return await self._find_email(session, first_name, last_name, company, linkedin_url)

    async def find_emails_batch(
        self,
        contacts: List[dict],
        max_concurrent: int = None
    ) -> List[EmailResult]:
        """
        Find emails for multiple contacts with rate limiting.

        Args:
            contacts: List of dicts with 'first_name', 'last_name', 'company', 'linkedin_url'
            max_concurrent: Max concurrent requests

        Returns:
            List of EmailResult objects
        """
        max_concurrent = max_concurrent or self.concurrent
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def process_contact(contact: dict) -> EmailResult:
            async with semaphore:
                # Rate limiting: stay well under 400/min limit
                await asyncio.sleep(0.2)  # 5 requests per second = 300/min
                ssl_ctx = ssl.create_default_context(cafile=certifi.where())
                conn = aiohttp.TCPConnector(ssl=ssl_ctx)
                async with aiohttp.ClientSession(connector=conn) as session:
                    return await self._find_email(
                        session,
                        contact.get("first_name", ""),
                        contact.get("last_name", ""),
                        contact.get("company", ""),
                        contact.get("linkedin_url", "")
                    )

        logger.info(f"Processing {len(contacts)} contacts for email enrichment via LeadsMagic")

        # Process with concurrency limit
        tasks = [process_contact(c) for c in contacts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to EmailResult
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(EmailResult(
                    linkedin_url=contacts[i].get("linkedin_url", ""),
                    success=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)

        success_count = sum(1 for r in final_results if r.success)
        logger.info(f"LeadsMagic email enrichment complete: {success_count}/{len(final_results)} found")

        return final_results
