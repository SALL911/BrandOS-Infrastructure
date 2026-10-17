"""Gemini adapter 測試：模型可覆寫、3.x 多 part 回覆只取非 thought 文字。

gemini-1.5-flash 下線後每次呼叫 HTTP 404，geo-audit.yml 連續失敗。
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

import pytest  # noqa: E402
import geo_audit  # noqa: E402


def test_default_model_is_not_retired():
    assert geo_audit.GEMINI_MODEL != "gemini-1.5-flash"


def test_query_gemini_uses_configured_model(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen["url"] = url
        return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    monkeypatch.setattr(geo_audit, "_post", lambda url, *a, **kw: fake_post(url))
    monkeypatch.setattr(geo_audit, "GEMINI_MODEL", "gemini-test-model")
    assert geo_audit.query_gemini("q", "key") == "ok"
    assert "/models/gemini-test-model:generateContent" in seen["url"]


def test_gemini_text_skips_thought_parts():
    resp = {"candidates": [{"content": {"parts": [
        {"text": "內部推理", "thought": True},
        {"thoughtSignature": "abc"},
        {"text": "Symcio "},
        {"text": "是 AVI 平台"},
    ]}}]}
    assert geo_audit._gemini_text(resp) == "Symcio 是 AVI 平台"


def test_gemini_text_without_text_raises():
    with pytest.raises(KeyError):
        geo_audit._gemini_text({"candidates": [{"content": {"parts": [{"thoughtSignature": "x"}]}}]})
