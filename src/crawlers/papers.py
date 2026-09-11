import asyncio
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple
import aiohttp
from src.schemas import ResearchPaperContent, ResearchPaperRecord

logger = logging.getLogger("PapersCrawler")
GITHUB_REGEX = re.compile(
    r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
)


class ArxivPapersCrawler:

    def __init__(self, target_count: int = 1050):
        self.target_count = target_count
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.semaphore = asyncio.Semaphore(10)

    async def _fetch_github_stars(
        self, session: aiohttp.ClientSession, owner: str, repo: str
    ) -> int:
        """Fetches dynamic GitHub stars via GitHub API. Never hallucinates."""
        # Strip trailing characters like .git or punctuation
        repo = re.sub(r"[\.,;:!\'\"]+$", "", repo)
        if repo.endswith(".git"):
            repo = repo[:-4]

        url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {"User-Agent": "AIEngineerPipeline/1.0"}
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        try:
            async with self.semaphore:
                async with session.get(url, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return int(data.get("stargazers_count", 0))
                    elif resp.status == 404:
                        return 0
                    elif resp.status == 403:
                        logger.warning(
                            "GitHub Rate limit hit (403). Falling back to 0."
                        )
                        return 0
        except Exception as e:
            logger.debug(f"Could not retrieve GitHub stars for {owner}/{repo}: {e}")
        return 0

    async def collect(self) -> List[ResearchPaperRecord]:
        logger.info(f"Starting arXiv extraction for {self.target_count} papers...")
        results: List[ResearchPaperRecord] = []
        batch_size = 200
        start = 0

        connector = aiohttp.TCPConnector(limit=25)
        async with aiohttp.ClientSession(connector=connector) as session:
            while len(results) < self.target_count:
                url = (
                    f"http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL"
                    f"&start={start}&max_results={batch_size}&sortBy=submittedDate&sortOrder=descending"
                )
                try:
                    async with session.get(url, timeout=30) as resp:
                        if resp.status != 200:
                            logger.error(f"arXiv API error: HTTP {resp.status}")
                            break
                        xml_data = await resp.text()

                    root = ET.fromstring(xml_data)
                    atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
                    entries = root.findall("atom:entry", atom_ns)

                    if not entries:
                        logger.info("No more arXiv records returned.")
                        break

                    for entry in entries:
                        title = entry.find("atom:title", atom_ns).text.strip()
                        title = re.sub(r"\s+", " ", title)
                        summary = entry.find(
                            "atom:summary", atom_ns
                        ).text.strip()
                        published = entry.find(
                            "atom:published", atom_ns
                        ).text.strip()

                        # Author list
                        authors = [
                            a.find("atom:name", atom_ns).text.strip()
                            for a in entry.findall("atom:author", atom_ns)
                            if a.find("atom:name", atom_ns) is not None
                        ]

                        # Paper URL
                        id_elem = entry.find("atom:id", atom_ns)
                        paper_url = id_elem.text.strip() if id_elem is not None else ""

                        # Search for GitHub repo correlation in abstract/summary
                        gh_match = GITHUB_REGEX.search(summary)
                        github_url = None
                        stars = 0

                        if gh_match:
                            owner, repo = (
                                gh_match.group(1),
                                gh_match.group(2),
                            )
                            github_url = (
                                f"https://github.com/{owner}/{repo}".rstrip(".")
                            )
                            stars = await self._fetch_github_stars(
                                session, owner, repo
                            )

                        record = ResearchPaperRecord(
                            content=ResearchPaperContent(
                                title=title,
                                authors=authors,
                                paper_url=paper_url,
                                github_url=github_url,
                                github_stars=stars,
                                published_date=published,
                            )
                        )
                        results.append(record)

                        if len(results) >= self.target_count:
                            break

                    start += batch_size
                    logger.info(
                        f"Collected {len(results)}/{self.target_count} papers..."
                    )
                    await asyncio.sleep(1.0)  # Respect arXiv 3-second query advice

                except Exception as e:
                    logger.error(f"Exception during arXiv pagination: {e}")
                    await asyncio.sleep(2.0)
                    start += batch_size

        logger.info(f"Completed arXiv extraction: {len(results)} records.")
        return results