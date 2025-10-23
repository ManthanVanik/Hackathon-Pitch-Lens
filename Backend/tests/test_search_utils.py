import os

import asyncio
import pytest

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCS_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
os.environ.setdefault("GOOGLE_SEARCH_ENGINE_ID", "dummy")

from utils.search_utils import PublicDataGatherer


class _DummySearchService:
    def cse(self):
        return self

    def list(self, **kwargs):
        return self

    def execute(self):
        return {"items": []}


class _DummySummarizer:
    def generate_text(self, prompt: str) -> str:
        return ""


def test_clean_company_title_normalizes_variations():
    assert PublicDataGatherer._clean_company_title("Airbnb - Official Site") == "Airbnb"
    assert PublicDataGatherer._clean_company_title("Stripe | Home Page") == "Stripe"
    assert PublicDataGatherer._clean_company_title("") == ""


def test_build_logo_entry_uses_snippet_for_company_name():
    entry = PublicDataGatherer._build_logo_entry(
        "B&",
        [
            {
                "title": "B& Logo PNG",
                "snippet": "Logo of Bain & Company management consulting firm.",
                "link": "https://example.com/bain",
            }
        ],
    )

    assert entry is not None
    assert entry["company_name"] == "Bain & Company"
    assert entry["source"] == "https://example.com/bain"


def test_build_logo_entry_skips_unresolved_short_matches():
    entry = PublicDataGatherer._build_logo_entry("B&", [])
    assert entry is None


def test_resolve_logo_companies_returns_structured_matches(monkeypatch):
    gatherer = PublicDataGatherer(search_service=_DummySearchService(), summarizer=_DummySummarizer())

    async def fake_search(query: str, num_results: int = 5, timeout: int = 30):
        if "Airbnb" in query:
            return [
                {
                    "title": "Airbnb - Official Site",
                    "snippet": "",
                    "link": "https://www.airbnb.com",
                }
            ]
        return []

    monkeypatch.setattr(gatherer, "_perform_search", fake_search)

    results = asyncio.run(gatherer._resolve_logo_companies(["Airbnb", "UnknownCo"]))

    assert {
        "logo_text": "Airbnb",
        "company_name": "Airbnb",
        "source": "https://www.airbnb.com",
    } in results
    assert any(entry["company_name"] == "UnknownCo" for entry in results)


def test_gather_data_includes_logo_matches(monkeypatch):
    gatherer = PublicDataGatherer(search_service=_DummySearchService(), summarizer=_DummySummarizer())

    async def fake_founder(names):
        return {
            "summary": "Founder background",
            "contacts": {
                "emails": ["ceo@example.com"],
                "sources": ["https://example.com/profile"],
            },
            "results": [],
        }

    async def fake_competitors(company, sector):
        return ["Competitor"]

    async def fake_market(sector):
        return {"TAM": "1B"}

    async def fake_news(company, founders):
        return ["News item"]

    async def fake_logos(logos):
        return [
            {
                "logo_text": logos[0],
                "company_name": "ResolvedCo",
                "source": "https://example.com",
            }
        ]

    monkeypatch.setattr(gatherer, "_search_founder_profile", fake_founder)
    monkeypatch.setattr(gatherer, "_search_competitors", fake_competitors)
    monkeypatch.setattr(gatherer, "_search_market_data", fake_market)
    monkeypatch.setattr(gatherer, "_search_news", fake_news)
    monkeypatch.setattr(gatherer, "_resolve_logo_companies", fake_logos)

    data = asyncio.run(gatherer.gather_data("Company", ["Alice"], "Fintech", logos=["LogoText"]))

    assert data["logo_companies"][0]["company_name"] == "ResolvedCo"
    assert data["founder_profile"] == "Founder background"
    assert data["founder_contacts"]["emails"] == ["ceo@example.com"]
