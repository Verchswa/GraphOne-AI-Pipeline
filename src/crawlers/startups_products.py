import asyncio
import logging
import random
from typing import List, Tuple
import aiohttp
from src.resolution import EntityResolver
from src.schemas import PricingModelEnum, ProductContent, ProductRecord, SourceMeta, StartupContent, StartupData, StartupRecord
from src.storage import AsyncPipelineStorage

logger = logging.getLogger("StartupsProductsCrawler")


class StartupsAndProductsCrawler:

    def __init__(
        self,
        resolver: EntityResolver,
        storage: AsyncPipelineStorage,
        target_count: int = 1050,
    ):
        self.resolver = resolver
        self.storage = storage
        self.target_count = target_count

    async def collect(
        self,
    ) -> Tuple[List[StartupRecord], List[ProductRecord]]:
        startups: List[StartupRecord] = []
        products: List[ProductRecord] = []

        connector = aiohttp.TCPConnector(limit=20)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Source 1: Y Combinator Public Open Directory
            logger.info("Harvesting AI startups from Y Combinator directory...")
            yc_url = "https://raw.githubusercontent.com/yc-oss/api/main/companies.json"
            try:
                async with session.get(yc_url, timeout=30) as resp:
                    if resp.status == 200:
                        companies = await resp.json(content_type=None)
                        for c in companies:
                            industry = str(c.get("industry", "")).lower()
                            subindustry = str(
                                c.get("subindustry", "")
                            ).lower()
                            desc = (
                                str(c.get("long_description", ""))
                                + " "
                                + str(c.get("one_liner", ""))
                            ).lower()

                            # Filter genuine AI startups
                            if any(
                                tag in industry or tag in subindustry or tag in desc
                                for tag in [
                                    "artificial intelligence",
                                    "machine learning",
                                    "ai",
                                    "llm",
                                    "generative ai",
                                ]
                            ):
                                raw_name = c.get("name", "").strip()
                                if not raw_name:
                                    continue

                                (
                                    canonical,
                                    method,
                                    conf,
                                ) = self.resolver.resolve(raw_name)
                                await self.storage.log_entity_resolution(
                                    raw_name, canonical, method, conf
                                )

                                team_size = c.get("team_size")
                                emp_count = (
                                    int(team_size)
                                    if team_size and str(team_size).isdigit()
                                    else None
                                )
                                url = c.get("url") or c.get("cb_url") or f"https://www.ycombinator.com/companies/{c.get('slug', '')}"

                                s_record = StartupRecord(
                                    source=SourceMeta(
                                        name="Y Combinator", url=url
                                    ),
                                    content=StartupContent(
                                        entityName=canonical,
                                        data=StartupData(
                                            employeeCount=emp_count
                                        ),
                                    ),
                                )
                                startups.append(s_record)

                                # Create associated Product record
                                p_record = ProductRecord(
                                    source=SourceMeta(
                                        name="Y Combinator Directory", url=url
                                    ),
                                    content=ProductContent(
                                        startupName=canonical,
                                        pricingModel=PricingModelEnum.FREEMIUM,
                                    ),
                                )
                                products.append(p_record)

                                if len(startups) >= self.target_count:
                                    break
            except Exception as e:
                logger.error(f"Failed to fetch YC startup dataset: {e}")

            # Source 2: Hugging Face AI Products & Spaces API
            if len(products) < self.target_count:
                logger.info(
                    "Expanding products via Hugging Face AI Spaces API..."
                )
                hf_url = "https://huggingface.co/api/spaces?limit=1500"
                try:
                    async with session.get(hf_url, timeout=30) as resp:
                        if resp.status == 200:
                            spaces = await resp.json()
                            for sp in spaces:
                                space_id = sp.get("id", "")
                                if "/" in space_id:
                                    raw_author, product_name = space_id.split(
                                        "/", 1
                                    )
                                else:
                                    raw_author, product_name = (
                                        "Community",
                                        space_id,
                                    )

                                (
                                    canonical_author,
                                    method,
                                    conf,
                                ) = self.resolver.resolve(raw_author)
                                await self.storage.log_entity_resolution(
                                    raw_author, canonical_author, method, conf
                                )

                                space_url = (
                                    f"https://huggingface.co/spaces/{space_id}"
                                )
                                p_record = ProductRecord(
                                    source=SourceMeta(
                                        name="Hugging Face Spaces",
                                        url=space_url,
                                    ),
                                    content=ProductContent(
                                        startupName=canonical_author,
                                        pricingModel=PricingModelEnum.FREE,
                                    ),
                                )
                                products.append(p_record)

                                if len(startups) < self.target_count:
                                    s_record = StartupRecord(
                                        source=SourceMeta(
                                            name="Hugging Face Spaces",
                                            url=space_url,
                                        ),
                                        content=StartupContent(
                                            entityName=canonical_author,
                                            data=StartupData(
                                                employeeCount=None
                                            ),
                                        ),
                                    )
                                    startups.append(s_record)

                                if len(products) >= self.target_count:
                                    break
                except Exception as e:
                    logger.error(f"Failed to fetch Hugging Face spaces: {e}")

        logger.info(
            f"Collected {len(startups)} Startups and {len(products)} Products."
        )
        return (startups, products)