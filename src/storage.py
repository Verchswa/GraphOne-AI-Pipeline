import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
import aiosqlite

logger = logging.getLogger("StorageEngine")


class AsyncPipelineStorage:

    def __init__(self, db_path: str = "pipeline_intelligence.db"):
        self.db_path = db_path

    async def init_db(self):
        """Initializes canonical relational tables and deduplication indices."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS startups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_key TEXT UNIQUE,
                entity_name TEXT,
                employee_count INTEGER,
                source_name TEXT,
                source_url TEXT,
                collected_at TEXT,
                raw_payload TEXT
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_key TEXT UNIQUE,
                startup_name TEXT,
                pricing_model TEXT,
                source_name TEXT,
                source_url TEXT,
                collected_at TEXT,
                raw_payload TEXT
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS research_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_key TEXT UNIQUE,
                title TEXT,
                authors TEXT,
                paper_url TEXT,
                github_url TEXT,
                github_stars INTEGER,
                published_date TEXT,
                raw_payload TEXT
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_key TEXT UNIQUE,
                company TEXT,
                date TEXT,
                is_remote BOOLEAN,
                role_family TEXT,
                source_url TEXT,
                raw_payload TEXT
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_key TEXT UNIQUE,
                title TEXT,
                full_text TEXT,
                source_name TEXT,
                source_url TEXT,
                published_date TEXT,
                collected_at TEXT,
                raw_payload TEXT
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS entity_mapping_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_name TEXT,
                canonical_name TEXT,
                method TEXT,
                confidence REAL,
                resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            await db.commit()

    @staticmethod
    def compute_hash(key_material: str) -> str:
        return hashlib.sha256(key_material.strip().lower().encode()).hexdigest()

    async def insert_startup(self, record: Dict[str, Any]) -> bool:
        h = self.compute_hash(
            f"{record['content']['entityName']}_{record['source']['url']}"
        )
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO startups (hash_key, entity_name, employee_count, source_name, source_url, collected_at, raw_payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        h,
                        record["content"]["entityName"],
                        record["content"]["data"]["employeeCount"],
                        record["source"]["name"],
                        record["source"]["url"],
                        record["collectedAt"],
                        json.dumps(record),
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting startup: {e}")
            return False

    async def insert_product(self, record: Dict[str, Any]) -> bool:
        h = self.compute_hash(
            f"{record['content']['startupName']}_{record['source']['url']}"
        )
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO products (hash_key, startup_name, pricing_model, source_name, source_url, collected_at, raw_payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        h,
                        record["content"]["startupName"],
                        record["content"]["pricingModel"],
                        record["source"]["name"],
                        record["source"]["url"],
                        record["collectedAt"],
                        json.dumps(record),
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting product: {e}")
            return False

    async def insert_paper(self, record: Dict[str, Any]) -> bool:
        h = self.compute_hash(record["content"]["paper_url"])
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO research_papers (hash_key, title, authors, paper_url, github_url, github_stars, published_date, raw_payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        h,
                        record["content"]["title"],
                        json.dumps(record["content"]["authors"]),
                        record["content"]["paper_url"],
                        record["content"]["github_url"],
                        record["content"]["github_stars"],
                        record["content"]["published_date"],
                        json.dumps(record),
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting research paper: {e}")
            return False

    async def insert_job(self, record: Dict[str, Any]) -> bool:
        h = self.compute_hash(
            f"{record['content']['company']}_{record['source_url']}"
        )
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO jobs (hash_key, company, date, is_remote, role_family, source_url, raw_payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        h,
                        record["content"]["company"],
                        record["content"]["date"],
                        record["content"]["is_remote"],
                        record["content"]["role_family"],
                        record["source_url"],
                        json.dumps(record),
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting job: {e}")
            return False

    async def insert_news(self, record: Dict[str, Any]) -> bool:
        h = self.compute_hash(record["source"]["url"])
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO news (hash_key, title, full_text, source_name, source_url, published_date, collected_at, raw_payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        h,
                        record["content"]["title"],
                        record["content"]["text"],
                        record["source"]["name"],
                        record["source"]["url"],
                        record["content"]["published_date"],
                        record["collectedAt"],
                        json.dumps(record),
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting news: {e}")
            return False

    async def log_entity_resolution(
        self,
        raw_name: str,
        canonical_name: str,
        method: str,
        confidence: float,
    ):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO entity_mapping_logs (raw_name, canonical_name, method, confidence)
                    VALUES (?, ?, ?, ?)
                """,
                    (raw_name, canonical_name, method, confidence),
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Error logging entity resolution: {e}")

    async def get_counts(self) -> Dict[str, int]:
        counts = {}
        async with aiosqlite.connect(self.db_path) as db:
            for table in [
                "startups",
                "products",
                "research_papers",
                "jobs",
                "news",
                "entity_mapping_logs",
            ]:
                async with db.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ) as cursor:
                    row = await cursor.fetchone()
                    counts[table] = row[0] if row else 0
        return counts