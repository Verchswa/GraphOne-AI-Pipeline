import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional,Tuple
import aiohttp
from dateutil import parser as date_parser
import feedparser
from src.resolution import EntityResolver
from src.schemas import JobContent, JobRecord
from src.storage import AsyncPipelineStorage

logger = logging.getLogger("JobsCrawler")


class FreshJobsCrawler:

    def __init__(
        self,
        resolver: EntityResolver,
        storage: AsyncPipelineStorage,
        hours_freshness: int = 24,
    ):
        self.resolver = resolver
        self.storage = storage
        self.cutoff_time = datetime.now(timezone.utc) - timedelta(
            hours=hours_freshness
        )

    def _parse_and_verify_date(
        self, raw_date: Optional[str]
    ) -> Optional[Tuple[str, datetime]]:
        if not raw_date:
            return None
        try:
            dt = date_parser.parse(raw_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)

            if dt >= self.cutoff_time:
                return (dt.isoformat(), dt)
        except Exception:
            pass
        return None

    async def _fetch_remotive(
        self, session: aiohttp.ClientSession
    ) -> List[JobRecord]:
        jobs: List[JobRecord] = []
        url = "https://remotive.com/api/remote-jobs?category=software-dev&search=AI"
        try:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data.get("jobs", []):
                        date_res = self._parse_and_verify_date(
                            item.get("publication_date")
                        )
                        if not date_res:
                            continue

                        iso_date, _ = date_res
                        raw_company = item.get("company_name", "Unknown")
                        canonical, m, conf = self.resolver.resolve(raw_company)
                        await self.storage.log_entity_resolution(
                            raw_company, canonical, m, conf
                        )

                        jobs.append(
                            JobRecord(
                                content=JobContent(
                                    company=canonical,
                                    date=iso_date,
                                    is_remote=True,
                                    role_family="Engineering",
                                ),
                                source_url=item.get(
                                    "url", "https://remotive.com"
                                ),
                            )
                        )
        except Exception as e:
            logger.error(f"Remotive fetch failed: {e}")
        return jobs

    async def _fetch_arbeitnow(
        self, session: aiohttp.ClientSession
    ) -> List[JobRecord]:
        jobs: List[JobRecord] = []
        url = "https://www.arbeitnow.com/api/job-board-api"
        try:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data.get("data", []):
                        title = item.get("title", "").lower()
                        tags = [t.lower() for t in item.get("tags", [])]
                        if not any(
                            k in title or k in tags
                            for k in [
                                "ai",
                                "machine learning",
                                "data",
                                "python",
                                "llm",
                            ]
                        ):
                            continue

                        # Arbeitnow provides epoch created_at
                        epoch = item.get("created_at")
                        if not epoch:
                            continue
                        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
                        if dt < self.cutoff_time:
                            continue

                        raw_company = item.get("company_name", "Unknown")
                        canonical, m, conf = self.resolver.resolve(raw_company)
                        await self.storage.log_entity_resolution(
                            raw_company, canonical, m, conf
                        )

                        jobs.append(
                            JobRecord(
                                content=JobContent(
                                    company=canonical,
                                    date=dt.isoformat(),
                                    is_remote=item.get("remote", False),
                                    role_family="Engineering",
                                ),
                                source_url=item.get(
                                    "url", "https://arbeitnow.com"
                                ),
                            )
                        )
        except Exception as e:
            logger.error(f"Arbeitnow fetch failed: {e}")
        return jobs

    async def _fetch_jobicy(
        self, session: aiohttp.ClientSession
    ) -> List[JobRecord]:
        jobs: List[JobRecord] = []
        url = (
            "https://jobicy.com/api/v2/remote-jobs?count=50&industry=engineering"
        )
        try:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data.get("jobs", []):
                        title = item.get("jobTitle", "").lower()
                        if not any(
                            k in title
                            for k in ["ai", "machine learning", "data", "ml"]
                        ):
                            continue

                        date_res = self._parse_and_verify_date(
                            item.get("pubDate")
                        )
                        if not date_res:
                            continue

                        iso_date, _ = date_res
                        raw_company = item.get("companyName", "Unknown")
                        canonical, m, conf = self.resolver.resolve(raw_company)
                        await self.storage.log_entity_resolution(
                            raw_company, canonical, m, conf
                        )

                        jobs.append(
                            JobRecord(
                                content=JobContent(
                                    company=canonical,
                                    date=iso_date,
                                    is_remote=True,
                                    role_family="Engineering",
                                ),
                                source_url=item.get("url", "https://jobicy.com"),
                            )
                        )
        except Exception as e:
            logger.error(f"Jobicy fetch failed: {e}")
        return jobs

    async def _fetch_wwr_feed(
        self, session: aiohttp.ClientSession
    ) -> List[JobRecord]:
        jobs: List[JobRecord] = []
        url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
        try:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    feed = feedparser.parse(content)
                    for entry in feed.entries:
                        title = entry.get("title", "")
                        if not any(
                            k in title.lower()
                            for k in [
                                "ai",
                                "machine learning",
                                "ml",
                                "data",
                                "python",
                            ]
                        ):
                            continue

                        date_res = self._parse_and_verify_date(
                            entry.get("published")
                        )
                        if not date_res:
                            continue

                        iso_date, _ = date_res
                        # Format often: "Company: Job Title"
                        raw_company = (
                            title.split(":")[0].strip()
                            if ":" in title
                            else "Unknown"
                        )
                        canonical, m, conf = self.resolver.resolve(raw_company)
                        await self.storage.log_entity_resolution(
                            raw_company, canonical, m, conf
                        )

                        jobs.append(
                            JobRecord(
                                content=JobContent(
                                    company=canonical,
                                    date=iso_date,
                                    is_remote=True,
                                    role_family="Engineering",
                                ),
                                source_url=entry.get(
                                    "link", "https://weworkremotely.com"
                                ),
                            )
                        )
        except Exception as e:
            logger.error(f"WeWorkRemotely fetch failed: {e}")
        return jobs

    async def collect(self) -> List[JobRecord]:
        logger.info("Initiating ingestion of fresh AI jobs (<=24 hours)...")
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                self._fetch_remotive(session),
                self._fetch_arbeitnow(session),
                self._fetch_jobicy(session),
                self._fetch_wwr_feed(session),
                return_exceptions=True,
            )

        all_jobs: List[JobRecord] = []
        for r in results:
            if isinstance(r, list):
                all_jobs.extend(r)

        logger.info(f"Collected {len(all_jobs)} verified fresh AI job postings.")
        return all_jobs