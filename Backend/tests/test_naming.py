import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.naming import build_company_display_name


def test_build_company_display_name_with_distinct_product():
    assert (
        build_company_display_name("Acme Corp", "Acme Insight Platform")
        == "Acme Corp (Product: Acme Insight Platform)"
    )


def test_build_company_display_name_same_names():
    assert build_company_display_name("Acme", "Acme") == "Acme"


def test_build_company_display_name_product_subset():
    assert build_company_display_name("Acme Analytics", "Acme") == "Acme Analytics (Product: Acme)"


def test_build_company_display_name_missing_company():
    assert build_company_display_name(None, "Acme Widget") == "Acme Widget"


def test_build_company_display_name_missing_product():
    assert build_company_display_name("Acme", None) == "Acme"
