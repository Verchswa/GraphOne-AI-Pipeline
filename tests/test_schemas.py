import pytest
from src.schemas import (
    JobContent,
    JobRecord,
    PricingModelEnum,
    ProductContent,
    ProductRecord,
    ResearchPaperContent,
    ResearchPaperRecord,
    SourceMeta,
    StartupContent,
    StartupData,
    StartupRecord,
)


def test_startup_schema():
    rec = StartupRecord(
        source=SourceMeta(
            name="YC", url="https://ycombinator.com/companies/stripe"
        ),
        content=StartupContent(
            entityName="Stripe", data=StartupData(employeeCount=7000)
        ),
    )
    assert rec.recordType == "STARTUP"
    assert rec.content.entityName == "Stripe"
    assert rec.content.data.employeeCount == 7000


def test_product_schema():
    rec = ProductRecord(
        source=SourceMeta(name="HF", url="https://huggingface.co/spaces/test"),
        content=ProductContent(
            startupName="Mistral AI", pricingModel=PricingModelEnum.PAID
        ),
    )
    assert rec.recordType == "PRODUCT"
    assert rec.content.pricingModel == "PAID"


def test_research_paper_schema():
    rec = ResearchPaperRecord(
        content=ResearchPaperContent(
            title="Attention Is All You Need",
            authors=["Vaswani et al."],
            paper_url="https://arxiv.org/abs/1706.03762",
            github_url="https://github.com/tensorflow/tensor2tensor",
            github_stars=14500,
            published_date="2017-06-12T00:00:00Z",
        )
    )
    assert rec.content.github_stars == 14500
    assert rec.content.authors == ["Vaswani et al."]


def test_job_schema():
    rec = JobRecord(
        content=JobContent(
            company="Anthropic",
            date="2026-09-10T12:00:00Z",
            is_remote=True,
            role_family="Engineering",
        ),
        source_url="https://anthropic.com/jobs/1",
    )
    assert rec.content.is_remote is True
    assert rec.content.company == "Anthropic"