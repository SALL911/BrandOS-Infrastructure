"""Unit tests for geo_audit.analyze_mention.

Regression coverage for 2026-04-28 bug：當 text="" 且 domain="" 時，
mentioned 因 Python `or` 短路語意變成空字串 "" 而非 False，
導致 reports/geo-audit/*.json 的 `mentioned` 欄位型別漂浮。
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

# Bypass top-level execution if any (geo_audit.py 沒有 top-level side effect，
# 但保險起見用 importlib 而非 from import)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "geo_audit",
    pathlib.Path(__file__).parent.parent / "scripts" / "geo_audit.py",
)
geo_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo_audit)


def test_mentioned_is_bool_when_brand_present():
    r = geo_audit.analyze_mention("Symcio is great", "Symcio", "")
    assert r["mentioned"] is True
    assert isinstance(r["mentioned"], bool)


def test_mentioned_is_bool_when_brand_absent():
    r = geo_audit.analyze_mention("Acme is great", "Symcio", "")
    assert r["mentioned"] is False
    assert isinstance(r["mentioned"], bool)


def test_mentioned_is_bool_with_empty_text_and_no_domain():
    """REGRESSION: 此 case 原本因 `False or ""` → "" 而漏 bool。"""
    r = geo_audit.analyze_mention("", "Symcio", "")
    assert r["mentioned"] is False
    assert isinstance(r["mentioned"], bool), (
        f"mentioned must be bool, got {type(r['mentioned']).__name__} "
        f"with value {r['mentioned']!r}"
    )


def test_mentioned_is_bool_with_empty_text_and_domain():
    r = geo_audit.analyze_mention("", "Symcio", "symcio.tw")
    assert r["mentioned"] is False
    assert isinstance(r["mentioned"], bool)


def test_mentioned_via_domain_match():
    r = geo_audit.analyze_mention("Visit symcio.tw for details.", "Symcio", "symcio.tw")
    assert r["mentioned"] is True
    assert isinstance(r["mentioned"], bool)


def test_score_zero_when_no_mention():
    r = geo_audit.analyze_mention("", "Symcio", "")
    assert r["score"] == 0.0


def test_rank_extraction_returns_some_rank():
    """Rank logic 已知粗略：抓第一個 'n.' 標記後 200 字內若含品牌就回傳 n。
    這個行為不一定精準（多品牌列表會偏向 rank=1），不是這次 PR 範圍。
    本測試僅確保在有編號列表時 rank_position 不為 None 且為 1-20 整數。"""
    r = geo_audit.analyze_mention(
        "Top providers: 1. Acme 2. Symcio 3. Beta", "Symcio", ""
    )
    assert r["mentioned"] is True
    assert r["rank_position"] is not None
    assert 1 <= r["rank_position"] <= 20


if __name__ == "__main__":
    import unittest
    # Run via unittest's discover-style for simplicity; failures exit nonzero.
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            suite.addTest(unittest.FunctionTestCase(fn))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
