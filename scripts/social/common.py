"""社群發布共用工具：HTTP、UTM、品牌用語檢查、OAuth 1.0a 簽章、Bluesky facets。

只用標準函式庫，CI 不需額外安裝套件。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

USER_AGENT = "symcio-social-automation/1.0"

# CLAUDE.md §六 禁用詞 + 品牌使用規範（不得主張授權／合作關係）
BANNED_TERMS = ("創新", "顛覆", "賦能", "授權代表", "official partner", "官方合作夥伴")
URL_RE = re.compile(r"https?://[^\s<>\"'）)】」]+")


class ChannelError(RuntimeError):
    """通路 API 回傳錯誤；訊息已截斷且不含憑證。"""


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: object | None = None,
    form: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict:
    data = None
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            out = json.loads(raw) if raw.strip() else {}
            if isinstance(out, dict):
                # LinkedIn 以回應標頭回傳新貼文 ID
                rid = resp.headers.get("x-restli-id")
                if rid:
                    out.setdefault("_restli_id", rid)
                return out
            return {"data": out}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        # 網址可能帶 access_token，只回報主機與路徑
        safe = urllib.parse.urlsplit(url)
        raise ChannelError(f"HTTP {e.code} {safe.netloc}{safe.path}: {body}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        safe = urllib.parse.urlsplit(url)
        raise ChannelError(f"{type(e).__name__} {safe.netloc}{safe.path}: {e}") from None


def with_utm(url: str | None, channel: str, campaign: str | None = None) -> str | None:
    """只對 symcio.tw 的連結加 UTM，外部連結維持原樣。"""
    if not url:
        return url
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if host != "symcio.tw" and not host.endswith(".symcio.tw"):
        return url
    query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("utm_source", channel)
    query.setdefault("utm_medium", "social")
    query.setdefault(
        "utm_campaign", campaign or "social_" + datetime.now(timezone.utc).strftime("%Y%m%d")
    )
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def lint_copy(text: str) -> list[str]:
    """回傳違反品牌語氣規範的項目；空 list 代表通過。"""
    problems = [f"禁用詞：{t}" for t in BANNED_TERMS if t.lower() in text.lower()]
    if "!" in text or "！" in text:
        problems.append("不使用感嘆號")
    return problems


def compose(body: str, link: str | None, tags: list[str], limit: int) -> str:
    """組出單則貼文：內文 + 連結 + hashtags，超過 limit 時先丟 hashtag 再截內文。"""
    hashtags = " ".join("#" + re.sub(r"[^\w]", "", t) for t in tags if re.sub(r"[^\w]", "", t))
    tail = "\n\n" + link if link else ""

    def build(b: str, h: str) -> str:
        return b + tail + ("\n\n" + h if h else "")

    text = build(body, hashtags)
    if len(text) <= limit:
        return text
    text = build(body, "")
    if len(text) <= limit:
        return text
    room = limit - len(tail) - 1
    if room < 20:
        raise ChannelError(f"連結過長，無法在 {limit} 字元內組出貼文")
    return body[:room].rstrip() + "…" + tail


# ---------- OAuth 1.0a（X API 使用者授權）----------

def _pct(s: str) -> str:
    return urllib.parse.quote(str(s), safe="-._~")


def oauth1_signature(
    method: str,
    url: str,
    params: dict[str, str],
    consumer_secret: str,
    token_secret: str,
) -> str:
    normalized = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in sorted(params.items()))
    base = "&".join([method.upper(), _pct(url), _pct(normalized)])
    key = f"{_pct(consumer_secret)}&{_pct(token_secret)}".encode()
    return base64.b64encode(hmac.new(key, base.encode(), hashlib.sha1).digest()).decode()


def oauth1_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    token: str,
    token_secret: str,
) -> str:
    """JSON body 的請求（如 POST /2/tweets）簽章只涵蓋 oauth_* 參數。"""
    oauth = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    oauth["oauth_signature"] = oauth1_signature(method, url, oauth, consumer_secret, token_secret)
    return "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))


# ---------- Bluesky rich text ----------

def bluesky_link_facets(text: str) -> list[dict]:
    """Bluesky 不會自動把網址轉成連結，需以 UTF-8 byte offset 標註。"""
    facets = []
    for m in URL_RE.finditer(text):
        start = len(text[: m.start()].encode("utf-8"))
        end = start + len(m.group(0).encode("utf-8"))
        facets.append(
            {
                "index": {"byteStart": start, "byteEnd": end},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group(0)}],
            }
        )
    return facets
