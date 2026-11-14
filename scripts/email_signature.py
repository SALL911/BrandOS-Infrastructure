"""Symcio Email 署名（Python 單一來源，與 web/landing/lib/email/signature.ts 同步）。

公開欄位寫在程式碼；電話、LINE、個人信箱只讀環境變數，未設定時自動省略：
  EMAIL_SIG_PHONE / EMAIL_SIG_LINE / EMAIL_SIG_ALT_EMAIL
"""
from __future__ import annotations

import html
import os

NAME = "黃智詮 Sall Huang"
TITLE = "Symcio 創辦人"
ORG = "Symcio（籌備中）"
TAGLINE = "讓 AI 正確介紹你的品牌：數據可查・AI 可見・品牌可估"
PAPER_LABEL = "BCI 品牌資本指數 方法論論文"
PAPER_URL = "https://doi.org/10.5281/zenodo.20419081"
SITE = "symcio.tw"
SITE_URL = "https://symcio.tw"
EMAIL = "sall@symcio.tw"


def _env(key: str) -> str | None:
    v = os.environ.get(key, "").strip()
    return v or None


def signature_text() -> str:
    alt, line, phone = _env("EMAIL_SIG_ALT_EMAIL"), _env("EMAIL_SIG_LINE"), _env("EMAIL_SIG_PHONE")
    emails = " ".join(e for e in (EMAIL, alt) if e)
    tail = "｜".join(x for x in (SITE, emails, f"LINE：{line}" if line else None, phone) if x)
    return "\n".join([
        "================================",
        f"{NAME}｜{TITLE}",
        f"{ORG}｜{TAGLINE}",
        f"{PAPER_LABEL}：{PAPER_URL}",
        tail,
    ])


def signature_html(color: str = "#6B7280") -> str:
    alt, line, phone = _env("EMAIL_SIG_ALT_EMAIL"), _env("EMAIL_SIG_LINE"), _env("EMAIL_SIG_PHONE")
    e = html.escape

    def a(href: str, text: str) -> str:
        return f'<a href="{e(href)}" style="color:{color};">{e(text)}</a>'

    emails = " ".join(x for x in (a(f"mailto:{EMAIL}", EMAIL), a(f"mailto:{alt}", alt) if alt else "") if x)
    tail = "｜".join(x for x in (a(SITE_URL, SITE), emails, f"LINE：{e(line)}" if line else "", e(phone) if phone else "") if x)
    return (
        f'<strong style="color:{color};">{e(NAME)}</strong>｜{e(TITLE)}<br>\n'
        f"{e(ORG)}｜{e(TAGLINE)}<br>\n"
        f"{e(PAPER_LABEL)}：{a(PAPER_URL, PAPER_URL)}<br>\n"
        f"{tail}"
    )


if __name__ == "__main__":
    print(signature_text())
