import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional,Tuple
import aiohttp
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import feedparser
from src.schemas import NewsContent, NewsRecord, SourceMeta

logger = logging.getLogger("NewsCrawler")

AI_NEWS_SOURCES = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
    },
    {
        "name": "Ars Technica Tech",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    },
    {
        "name": "MIT Tech Review",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    },
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/artificial-intelligence/index.xml",
    },
]


class FreshNewsCrawler:

    def __init__(self, hours_freshness: int = 24):
        self.cutoff_time = datetime.now(timezone.utc) - timedelta(
            hours=hours_freshness
        )

    def _parse_and_verify_date(
        self, entry: dict
    ) -> Optional[Tuple[str, datetime]]:
        """Extracts and verifies publication date against the strict 24-hour cutoff."""
        raw_date = (
            entry.get("published")
            or entry.get("pubDate")
            or entry.get("updated")
        )
        if not raw_date and hasattr(entry, "published_parsed"):
            try:
                dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if dt >= self.cutoff_time:
                    return (dt.isoformat(), dt)
                return None
            except Exception:
                pass

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
        except Exception as e:
            logger.debug(f"Failed to parse date '{raw_date}': {e}")

        return None

    async def _fetch_full_text(
        self, session: aiohttp.ClientSession, url: str
    ) -> str:
        """Retrieves and cleans full-text body paragraphs from destination page."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0"
                    " Safari/537.36"
                )
            }
            async with session.get(url, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    for s in soup(["script", "style", "nav", "footer", "aside"]):
                        s.decompose()
                    paragraphs = [
                        p.get_text().strip()
                        for p in soup.find_all("p")
                        if len(p.get_text().strip()) > 30
                    ]
                    if paragraphs:
                        return "\n\n".join(paragraphs)
        except Exception as e:
            logger.debug(f"Could not extract body for {url}: {e}")
        return ""

    async def collect(self) -> List[NewsRecord]:
        logger.info("Initiating ingestion of fresh AI news (<=24 hours)...")
        verified_news: List[NewsRecord] = []

        async with aiohttp.ClientSession() as session:
            for src in AI_NEWS_SOURCES:
                logger.info(f"Checking feed: {src['name']}...")
                try:
                    async with session.get(
                        src["url"],
                        headers={"User-Agent": "AIEngineerNewsBot/1.0"},
                        timeout=15,
                    ) as resp:
                        if resp.status != 200:
                            logger.warning(
                                f"Failed to fetch feed {src['name']}: HTTP {resp.status}"
                            )
                            continue
                        feed_content = await resp.text()

                    feed = feedparser.parse(feed_content)
                    for entry in feed.entries:
                        date_res = self._parse_and_verify_date(entry)
                        if not date_res:
                            # Strict rejection of non-verified or stale articles
                            continue

                        iso_date, _ = date_res
                        link = entry.get("link", "")
                        title = entry.get("title", "Untitled")

                        full_text = await self._fetch_full_text(session, link)
                        if not full_text:
                            full_text = entry.get("summary", "")

                        record = NewsRecord(
                            source=SourceMeta(name=src["name"], url=link),
                            content=NewsContent(
                                title=title,
                                text=full_text,
                                published_date=iso_date,
                            ),
                        )
                        verified_news.append(record)
                except Exception as e:
                    logger.error(f"Error reading feed {src['name']}: {e}")

        logger.info(
            f"Collected {len(verified_news)} verified fresh news records."
        )
        return verified_news