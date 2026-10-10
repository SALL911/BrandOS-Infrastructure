#!/usr/bin/env python3
"""
建立（或重用）Gumroad Starter Kit → VIP 專人建置的 $260 Stripe Payment Link。

$299 VIP − $39 Starter Kit 全額折抵 = $260。URL 貼入 Gumroad 產品的 Receipt 文案。
冪等：以 product.metadata.symcio_sku 與 payment_link.metadata.price_id 辨識，重複執行不重複建立。

環境變數：
  STRIPE_SECRET_KEY   必填（建議 restricted key：Products / Prices / Payment Links 寫入）
  CALENDLY_URL        選填：付款完成後自動導向預約頁
  UPGRADE_AMOUNT_USD  選填，預設 260
  STRIPE_API_BASE     選填，僅測試用（預設 https://api.stripe.com/v1）

輸出：Payment Link URL（stdout；GitHub Actions 下另寫入 job summary）
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("STRIPE_API_BASE", "https://api.stripe.com/v1")
SKU = "starter-kit-vip-upgrade"


def stripe(method: str, path: str, params: list[tuple[str, str]] | None = None) -> dict:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        sys.exit("STRIPE_SECRET_KEY is not set")
    encoded = urllib.parse.urlencode(params or [])
    url = f"{API}{path}"
    data = None
    if method == "GET" and encoded:
        url += "?" + encoded
    elif method == "POST":
        data = encoded.encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.load(res)
    except urllib.error.HTTPError as err:
        sys.exit(f"Stripe {method} {path} {err.code}: {err.read().decode()}")


def get_or_create_product() -> dict:
    res = stripe("GET", "/products/search", [("query", f"metadata['symcio_sku']:'{SKU}'")])
    if res.get("data"):
        return res["data"][0]
    product = stripe("POST", "/products", [
        ("name", "VIP Concierge Full Setup — Starter Kit upgrade"),
        ("description", "1-on-1 remote setup: Vercel deploy, custom domain, HubSpot pipeline, "
                        "14-day messaging support. $39 Starter Kit purchase credited."),
        ("metadata[symcio_sku]", SKU),
    ])
    print(f"created product {product['id']}", file=sys.stderr)
    return product


def get_or_create_price(product_id: str, amount_cents: int) -> dict:
    prices = stripe("GET", "/prices", [("product", product_id), ("active", "true"), ("limit", "100")])
    for p in prices["data"]:
        if p["unit_amount"] == amount_cents and p["currency"] == "usd" and not p.get("recurring"):
            return p
    price = stripe("POST", "/prices", [
        ("product", product_id),
        ("currency", "usd"),
        ("unit_amount", str(amount_cents)),
    ])
    print(f"created price {price['id']}", file=sys.stderr)
    return price


def get_or_create_link(price_id: str, calendly: str) -> dict:
    after = None
    while True:
        params = [("active", "true"), ("limit", "100")]
        if after:
            params.append(("starting_after", after))
        links = stripe("GET", "/payment_links", params)
        for link in links["data"]:
            meta = link.get("metadata", {})
            if meta.get("price_id") == price_id and meta.get("redirect", "") == calendly:
                return link
        if not links.get("has_more"):
            break
        after = links["data"][-1]["id"]

    params = [
        ("line_items[0][price]", price_id),
        ("line_items[0][quantity]", "1"),
        ("metadata[symcio_sku]", SKU),
        ("metadata[price_id]", price_id),
        ("metadata[redirect]", calendly),
        # 以 Gumroad 購買 email 對帳折抵資格
        ("custom_fields[0][key]", "gumroad_email"),
        ("custom_fields[0][label][type]", "custom"),
        ("custom_fields[0][label][custom]", "Email used on Gumroad"),
        ("custom_fields[0][type]", "text"),
    ]
    if calendly:
        params += [
            ("after_completion[type]", "redirect"),
            ("after_completion[redirect][url]", calendly),
        ]
    link = stripe("POST", "/payment_links", params)
    print(f"created payment link {link['id']}", file=sys.stderr)
    return link


def main() -> None:
    amount_cents = int(os.environ.get("UPGRADE_AMOUNT_USD") or "260") * 100
    calendly = os.environ.get("CALENDLY_URL", "").strip()
    if calendly and not calendly.startswith("https://"):
        sys.exit("CALENDLY_URL must start with https://")

    product = get_or_create_product()
    price = get_or_create_price(product["id"], amount_cents)
    link = get_or_create_link(price["id"], calendly)

    print(link["url"])
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### ${amount_cents // 100} VIP upgrade link\n\n{link['url']}\n\n"
                     f"- product: `{product['id']}`\n- price: `{price['id']}`\n"
                     f"- after completion: {calendly or 'Stripe confirmation page'}\n\n"
                     "Paste the URL into Gumroad → product → Receipt "
                     "(see products/gumroad-starter-kit/LAUNCH.md).\n")


if __name__ == "__main__":
    main()
