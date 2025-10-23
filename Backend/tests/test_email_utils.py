from utils.email_utils import extract_emails


def test_extract_emails_handles_nested_structures():
    payload = {
        "page_1": "Reach us at founders@alpha.io or ceo@alpha.io",
        "page_2": [
            "Contact: jane.doe@alpha.io",
            {"notes": "Backup info@alpha.io for support"},
        ],
    }

    extras = ["CEO Email: CEO@alpha.io", "operations@alpha.io"]

    assert extract_emails(payload, extras) == [
        "founders@alpha.io",
        "ceo@alpha.io",
        "jane.doe@alpha.io",
        "info@alpha.io",
        "operations@alpha.io",
    ]


def test_extract_emails_skips_empty_sources():
    assert extract_emails(None, "", [], {}) == []


def test_extract_emails_preserves_first_seen_casing():
    sources = ["Investor: Growth@Beta.com", "growth@beta.com"]
    assert extract_emails(sources) == ["Growth@Beta.com"]
