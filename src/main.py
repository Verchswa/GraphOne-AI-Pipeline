import asyncio
import logging
import sys
from src.crawlers.jobs import FreshJobsCrawler
from src.crawlers.news import FreshNewsCrawler
from src.crawlers.papers import ArxivPapersCrawler
from src.crawlers.startups_products import StartupsAndProductsCrawler
from src.resolution import EntityResolver
from src.storage import AsyncPipelineStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("PipelineOrchestrator")


async def run_pipeline():
    logger.info("==================================================")
    logger.info("GraphOne / FrontierAtlas Intelligence Ingestion")
    logger.info("==================================================")

    # 1. Initialize Storage & Resolvers
    storage = AsyncPipelineStorage("pipeline_intelligence.db")
    await storage.init_db()
    resolver = EntityResolver()

    # 2. Instantiate Crawlers
    papers_crawler = ArxivPapersCrawler(target_count=1050)
    entities_crawler = StartupsAndProductsCrawler(
        resolver=resolver, storage=storage, target_count=1050
    )
    news_crawler = FreshNewsCrawler(hours_freshness=24)
    jobs_crawler = FreshJobsCrawler(
        resolver=resolver, storage=storage, hours_freshness=24
    )

    logger.info("Phase 1 & 2: Executing concurrent ingestion tasks...")
    papers_task = asyncio.create_task(papers_crawler.collect())
    entities_task = asyncio.create_task(entities_crawler.collect())
    news_task = asyncio.create_task(news_crawler.collect())
    jobs_task = asyncio.create_task(jobs_crawler.collect())

    # Wait for completion
    papers = await papers_task
    startups, products = await entities_task
    news_items = await news_task
    jobs = await jobs_task

    # 3. Store Records into SQLite with SHA-256 Deduplication
    logger.info("Persisting validated canonical records into storage...")
    for p in papers:
        await storage.insert_paper(p.model_dump())
    for s in startups:
        await storage.insert_startup(s.model_dump())
    for prod in products:
        await storage.insert_product(prod.model_dump())
    for n in news_items:
        await storage.insert_news(n.model_dump())
    for j in jobs:
        await storage.insert_job(j.model_dump())

    # 4. Print Summary Verification
    counts = await storage.get_counts()
    logger.info("==================================================")
    logger.info("INGESTION PIPELINE EXECUTION AUDIT SUMMARY")
    logger.info("==================================================")
    for table, count in counts.items():
        logger.info(f"• {table.replace('_', ' ').title()}: {count} rows")
    logger.info("==================================================")


if __name__ == "__main__":
    asyncio.run(run_pipeline())