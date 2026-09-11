from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


class PricingModelEnum(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


class SourceMeta(BaseModel):
    name: str
    url: str


# --- STARTUP SCHEMA ---
class StartupData(BaseModel):
    employeeCount: Optional[int] = None


class StartupContent(BaseModel):
    entityName: str
    data: StartupData = Field(default_factory=StartupData)


class StartupRecord(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "STARTUP"
    source: SourceMeta
    content: StartupContent
    collectedAt: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# --- PRODUCT SCHEMA ---
class ProductContent(BaseModel):
    startupName: str
    pricingModel: PricingModelEnum = PricingModelEnum.FREEMIUM


class ProductRecord(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "PRODUCT"
    source: SourceMeta
    content: ProductContent
    collectedAt: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# --- RESEARCH PAPER SCHEMA ---
class ResearchPaperContent(BaseModel):
    title: str
    authors: List[str]
    paper_url: str
    github_url: Optional[str] = None
    github_stars: Optional[int] = 0
    published_date: str


class ResearchPaperRecord(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "RESEARCH_PAPER"
    content: ResearchPaperContent


# --- JOB SCHEMA ---
class JobContent(BaseModel):
    company: str
    date: str
    is_remote: bool = False
    role_family: str = "Engineering"


class JobRecord(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "JOB"
    content: JobContent
    source_url: str


# --- NEWS SCHEMA ---
class NewsContent(BaseModel):
    title: str
    text: str
    published_date: str


class NewsRecord(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "NEWS"
    source: SourceMeta
    content: NewsContent
    collectedAt: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# --- ENTITY RESOLUTION LOG SCHEMA ---
class EntityResolutionLog(BaseModel):
    raw_name: str
    canonical_name: str
    method: str  # EXACT, SEED_ALIAS, REGEX_NORMALIZED, FUZZY
    confidence: float