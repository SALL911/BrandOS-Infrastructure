"""Perplexity 結構化引用網址保留測試。

sonar 的回覆內文只有 [1][2] 編號，網址放在 search_results / citations 欄位；
過去 adapter 只取內文，aivi_mentions.cited_urls 對 Perplexity 永遠是空陣列。
"""
import json
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

import geo_audit  # noqa: E402
import aivi_tracker  # noqa: E402


def _fake_post(resp):
    return lambda *a, **kw: resp


def test_query_perplexity_keeps_search_results(monkeypatch):
    monkeypatch.setattr(geo_audit, "_post", _fake_post({
        "choices": [{"message": {"content": "Symcio 是 AVI 平台 [1][2]"}}],
        "search_results": [
            {"title": "a", "url": "https://symcio.tw/"},
            {"title": "b", "url": "https://example.com/x"},
        ],
        "citations": ["https://symcio.tw/", "https://legacy.example/y"],
    }))
    text = geo_audit.query_perplexity("q", "key")
    assert text == "Symcio 是 AVI 平台 [1][2]"
    assert text.citations == [
        "https://symcio.tw/", "https://example.com/x", "https://legacy.example/y",
    ]


def test_query_perplexity_without_citations(monkeypatch):
    monkeypatch.setattr(geo_audit, "_post", _fake_post(
        {"choices": [{"message": {"content": "no sources"}}]}))
    assert geo_audit.query_perplexity("q", "key").citations == []


def test_extract_urls_merges_structured_and_inline():
    text = geo_audit.EngineText(
        "見 https://example.com/x 與 https://inline.example/z.",
        ["https://symcio.tw/", "https://example.com/x"],
    )
    assert aivi_tracker.extract_urls(text) == [
        "https://symcio.tw/", "https://example.com/x", "https://inline.example/z",
    ]


def test_extract_urls_plain_str_unchanged():
    assert aivi_tracker.extract_urls("see https://a.example/b.") == ["https://a.example/b"]
    assert aivi_tracker.extract_urls("") == []


def test_engine_text_serializes_as_plain_string():
    assert json.dumps(geo_audit.EngineText("x", ["https://a"])) == '"x"'
