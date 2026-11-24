#!/usr/bin/env python3
"""
AIVI Accuracy — 「AI 有沒有把你講對」事實正確性判定
---------------------------------------------------
WHY
  提及率只回答「AI 有沒有講到你」。客戶真正的痛點是「AI 講錯你」：
  同名混淆、錯誤主張（例如把 Symcio 講成某機構的授權代表）、
  或只提到名字卻講不出任何可查證事實（缺實體錨點）。

WHAT
  對每一則「有提及品牌」的回覆，用品牌事實檔（facts）判定：
    correct  至少命中 1 項可查證事實，且無錯誤主張、無同名混淆
    partial  有提及，但講不出任何可查證事實
    wrong    出現錯誤主張（wrong_fact）或在談另一個同名實體（name_collision）
    absent   未提及（交由提及率處理，不計入正確率分母）

HOW（規則式，刻意不用 LLM 當裁判）
  - 量測要可稽核、可重現：同一份回覆 + 同一版 facts，永遠得到同一個結果。
  - 否定句處理：錯誤主張前若出現否定詞（不、非、並非、沒有、not…），不算錯。
  - 規則是啟發式，aivi_mentions.verified_by 的 10% 人工抽驗仍必須執行。

事實檔位置（依序）：
  1. 環境變數 AIVI_FACTS_JSON（JSON 字串；客戶品牌用 GitHub Secret 注入，不進 repo）
  2. prompts/<slug>/facts.json（僅限可公開的自家示範品牌）

改 facts 內容請升版（version），否則月對月正確率不可比。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

METHOD_VERSION = "acc-v1"

# 錯誤主張前方視窗內出現這些詞，視為否定句（例：「Symcio 並非 Bloomberg 授權代表」）
# 只用多字否定結構，避免「非常」「無形資產」這類詞誤觸
NEGATION_MARKERS = (
    "不是", "並非", "並不", "沒有", "並未", "未曾", "否認", "不屬於", "不具",
    "非屬", "不提供", "不採", "不做", "不收", "不會", "不得",
    "not ", "never", "isn't", "is not", "doesn't", "does not", "without", "no longer",
)
NEGATION_WINDOW = 30   # 錯誤主張前方最多幾個字元內找否定詞（遇標點即截斷）
CLAUSE_BREAKS = ("，", "。", "；", "！", "？", ",", ".", ";", "\n")
PROXIMITY = 150        # 事實／錯誤主張需落在品牌名前後幾個字元內才歸屬於本品牌


def load_facts(slug: str, prompts_dir: Path) -> dict | None:
    """讀品牌事實檔；都沒有則回 None（不做正確性判定，不影響原本採樣）。"""
    raw = os.environ.get("AIVI_FACTS_JSON", "").strip()
    if raw:
        return _validate(json.loads(raw))
    path = prompts_dir / slug / "facts.json"
    if path.exists():
        return _validate(json.loads(path.read_text(encoding="utf-8")))
    return None


def _validate(facts: dict) -> dict:
    if not facts.get("version"):
        raise ValueError("facts 檔缺 version；改內容必須升版，否則趨勢不可比")
    if not facts.get("brand_terms"):
        raise ValueError("facts 檔缺 brand_terms（品牌名＋別名＋域名），無法判斷事實歸屬")
    for key in ("facts", "wrong_claims", "confusables"):
        facts.setdefault(key, [])
    for f in facts["facts"]:
        if not f.get("id") or not f.get("any_of"):
            raise ValueError(f"facts 每項都需要 id 與 any_of：{f}")
    return facts


def method_tag(facts: dict) -> str:
    """寫進 aivi_mentions.accuracy_method，例：acc-v1/symcio-facts-v1"""
    return f"{METHOD_VERSION}/{facts['version']}"


def _is_negated(lower: str, idx: int) -> bool:
    """往前看到同一子句開頭為止（最多 NEGATION_WINDOW 字元），不跨句。"""
    window = lower[max(0, idx - NEGATION_WINDOW):idx]
    cut = max(window.rfind(ch) for ch in CLAUSE_BREAKS)
    if cut != -1:
        window = window[cut + 1:]
    return any(m in window for m in NEGATION_MARKERS)


def _positions(lower: str, needle: str) -> list[int]:
    n, out, start = needle.lower(), [], 0
    while n:
        idx = lower.find(n, start)
        if idx == -1:
            break
        out.append(idx)
        start = idx + len(n)
    return out


def _near(idx: int, anchors: list[int]) -> bool:
    return any(abs(idx - a) <= PROXIMITY for a in anchors)


def _find(lower: str, needle: str, anchors: list[int] | None, affirmed: bool) -> bool:
    """needle 出現，且（需要時）靠近品牌名、不在否定句中。"""
    for idx in _positions(lower, needle):
        if anchors is not None and not _near(idx, anchors):
            continue
        if affirmed and _is_negated(lower, idx):
            continue
        return True
    return False


def check_accuracy(text: str, mentioned: bool, facts: dict) -> dict:
    """回傳 {accuracy, error_type, facts_hit, facts_matched, conflicts_found}。"""
    if not mentioned or not text:
        return {"accuracy": "absent", "error_type": None, "facts_hit": 0,
                "facts_matched": [], "conflicts_found": []}

    lower = text.lower()
    anchors = sorted({i for t in facts["brand_terms"] for i in _positions(lower, t)})

    matched = [f["id"] for f in facts["facts"]
               if any(_find(lower, k, anchors, affirmed=False) for k in f["any_of"])]

    conflicts = [c["id"] for c in facts["wrong_claims"]
                 if any(_find(lower, k, anchors, affirmed=True) for k in c["any_of"])]

    # 同名混淆：提到易混淆實體，且講不出任何屬於本品牌的事實 → 在談別人
    collision = (not matched) and any(
        _find(lower, k, None, affirmed=True)
        for c in facts["confusables"] for k in c["any_of"])

    if conflicts:
        accuracy, error_type = "wrong", "wrong_fact"
    elif collision:
        accuracy, error_type = "wrong", "name_collision"
    elif matched:
        accuracy, error_type = "correct", None
    else:
        accuracy, error_type = "partial", "no_verifiable_fact"

    return {
        "accuracy": accuracy,
        "error_type": error_type,
        "facts_hit": len(matched),
        "facts_matched": matched,
        "conflicts_found": conflicts,
    }


def summarize(records: list[dict]) -> dict:
    """月報用：以「有提及」為分母。"""
    scored = [r for r in records if r.get("accuracy") and r["accuracy"] != "absent"]
    n = len(scored)

    def pct(k: str) -> float | None:
        return round(sum(1 for r in scored if r["accuracy"] == k) / n * 100, 1) if n else None

    errors: dict[str, int] = {}
    for r in scored:
        if r.get("error_type"):
            errors[r["error_type"]] = errors.get(r["error_type"], 0) + 1
    return {
        "method": records[0].get("accuracy_method") if records else None,
        "mentioned_scored": n,
        "correct_rate_pct": pct("correct"),
        "partial_rate_pct": pct("partial"),
        "wrong_rate_pct": pct("wrong"),
        "error_breakdown": errors,
    }
