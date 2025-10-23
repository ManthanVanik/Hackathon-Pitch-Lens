import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.cache_utils import build_weight_signature, extract_cached_memo


def test_build_weight_signature_consistency():
    weight_a = {"team": 0.3, "market": 0.4, "product": 0.3}
    weight_b = {"product": 0.30, "market": 0.40, "team": 0.3000}

    assert build_weight_signature(weight_a) == build_weight_signature(weight_b)


def test_extract_cached_memo_returns_expected_entry():
    doc = {
        "memos": {
            "market:0.4|product:0.3|team:0.3": {
                "memo_json": {"foo": "bar"},
                "weightage": {"market": 0.4, "product": 0.3, "team": 0.3},
            }
        }
    }

    result = extract_cached_memo(doc, "market:0.4|product:0.3|team:0.3")
    assert result == doc["memos"]["market:0.4|product:0.3|team:0.3"]


def test_extract_cached_memo_handles_missing_entry():
    doc = {"memos": {}}
    assert extract_cached_memo(doc, "missing") is None
