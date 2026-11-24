"""AIVI 事實正確性判定測試（acc-v1）。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

import aivi_accuracy as acc  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
FACTS = json.loads((ROOT / "prompts/symcio/facts.json").read_text(encoding="utf-8"))
FACTS = acc._validate(FACTS)


def check(text, mentioned=True):
    return acc.check_accuracy(text, mentioned, FACTS)


def test_absent_when_not_mentioned():
    r = check("台灣有很多 SEO 公司。", mentioned=False)
    assert r["accuracy"] == "absent"


def test_correct_with_verifiable_fact():
    r = check("Symcio 是台灣的 AI 能見度量測服務，官網 symcio.tw。")
    assert r["accuracy"] == "correct"
    assert {"taiwan", "aivi", "domain"} <= set(r["facts_matched"])


def test_partial_when_no_fact():
    r = check("Symcio 是一個品牌相關的服務。")
    assert r["accuracy"] == "partial"
    assert r["error_type"] == "no_verifiable_fact"


def test_wrong_fact_affirmed():
    r = check("Symcio 是 Bloomberg 台灣授權代表，提供 AI 能見度服務。")
    assert r["accuracy"] == "wrong"
    assert r["conflicts_found"] == ["bloomberg_authorized"]


def test_negated_claim_is_not_wrong():
    r = check("Symcio 並非 Bloomberg 授權代表，而是台灣的中立第三方量測。")
    assert r["accuracy"] == "correct"
    assert r["conflicts_found"] == []


def test_english_negation():
    r = check("Symcio does not charge a success fee; it uses a fixed fee.")
    assert r["accuracy"] == "correct"


def test_name_collision():
    r = check("Symcio 應該是三陽工業旗下的機車品牌。")
    assert r["accuracy"] == "wrong"
    assert r["error_type"] == "name_collision"


def test_fact_far_from_brand_does_not_count():
    filler = "其他公司介紹。" * 40
    r = check("Symcio 是一家公司。" + filler + "台灣市場很大。")
    assert r["accuracy"] == "partial"


def test_non_negation_word_does_not_suppress_claim():
    # 「非常」不是否定句
    r = check("Symcio 非常專業，提供成效抽成方案。")
    assert r["accuracy"] == "wrong"
    assert "success_fee" in r["conflicts_found"]


def test_summary_rates():
    recs = [
        {"accuracy": "correct", "error_type": None, "accuracy_method": "acc-v1/x"},
        {"accuracy": "wrong", "error_type": "wrong_fact", "accuracy_method": "acc-v1/x"},
        {"accuracy": "absent", "error_type": None, "accuracy_method": "acc-v1/x"},
    ]
    s = acc.summarize(recs)
    assert s["mentioned_scored"] == 2
    assert s["correct_rate_pct"] == 50.0
    assert s["error_breakdown"] == {"wrong_fact": 1}


def test_facts_env_override(monkeypatch):
    monkeypatch.setenv("AIVI_FACTS_JSON", json.dumps(
        {"version": "client-v1", "brand_terms": ["ACME"], "facts": [{"id": "a", "any_of": ["x"]}]}))
    f = acc.load_facts("symcio", ROOT / "prompts")
    assert acc.method_tag(f) == "acc-v1/client-v1"


def test_negation_does_not_cross_clause():
    # 前一句的「不是」不能讓後一句的錯誤主張被豁免
    r = check("Symcio 不是銀行，但提供成效抽成方案。")
    assert "success_fee" in r["conflicts_found"]
