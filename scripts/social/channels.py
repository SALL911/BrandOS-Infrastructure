"""各社群通路的發文實作。

每個通路一個 publish_<channel>(post, env) -> (external_id, external_url)。
`REQUIRED_ENV` 列出該通路需要的 secrets；缺任一項即視為未設定，發布時標記 skipped。

API 版本與權限會異動，上線前請對照 docs/SOCIAL_AUTOMATION.md 的檢核表。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .common import (
    ChannelError,
    bluesky_link_facets,
    compose,
    http_json,
    oauth1_header,
    with_utm,
)

GRAPH = "https://graph.facebook.com/v21.0"
THREADS = "https://graph.threads.net/v1.0"

REQUIRED_ENV: dict[str, tuple[str, ...]] = {
    "bluesky": ("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"),
    "threads": ("THREADS_USER_ID", "THREADS_ACCESS_TOKEN"),
    "facebook": ("FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN"),
    "instagram": ("IG_USER_ID", "FB_PAGE_ACCESS_TOKEN"),
    "x": ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"),
    "linkedin": ("LINKEDIN_ORG_ID", "LINKEDIN_ACCESS_TOKEN"),
    # LINE 群發會消耗訊息額度（好友數 × 則數），需另外明確開啟
    "line": ("LINE_CHANNEL_ACCESS_TOKEN", "LINE_BROADCAST_ENABLED"),
}


def is_configured(channel: str, env: dict[str, str]) -> bool:
    if not all(env.get(k, "").strip() for k in REQUIRED_ENV[channel]):
        return False
    if channel == "line":
        return env.get("LINE_BROADCAST_ENABLED", "").strip().lower() == "true"
    return True


def _short(post: dict) -> str:
    return post["body_short"]


def _medium(post: dict) -> str:
    return post.get("body_medium") or post["body_short"]


def publish_bluesky(post: dict, env: dict[str, str]) -> tuple[str, str]:
    pds = env.get("BLUESKY_PDS", "https://bsky.social").rstrip("/")
    handle = env["BLUESKY_HANDLE"]
    session = http_json(
        "POST",
        f"{pds}/xrpc/com.atproto.server.createSession",
        json_body={"identifier": handle, "password": env["BLUESKY_APP_PASSWORD"]},
    )
    text = compose(_short(post), with_utm(post.get("link_url"), "bluesky"), post.get("tags") or [], 300)
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "langs": ["zh-TW"],
    }
    facets = bluesky_link_facets(text)
    if facets:
        record["facets"] = facets
    out = http_json(
        "POST",
        f"{pds}/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json_body={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
    )
    rkey = out["uri"].rsplit("/", 1)[-1]
    return out["uri"], f"https://bsky.app/profile/{handle}/post/{rkey}"


def publish_threads(post: dict, env: dict[str, str]) -> tuple[str, str]:
    uid, token = env["THREADS_USER_ID"], env["THREADS_ACCESS_TOKEN"]
    text = compose(_short(post), with_utm(post.get("link_url"), "threads"), post.get("tags") or [], 500)
    container = http_json(
        "POST", f"{THREADS}/{uid}/threads",
        form={"media_type": "TEXT", "text": text, "access_token": token},
    )
    out = http_json(
        "POST", f"{THREADS}/{uid}/threads_publish",
        form={"creation_id": container["id"], "access_token": token},
    )
    return out["id"], ""


def publish_facebook(post: dict, env: dict[str, str]) -> tuple[str, str]:
    form = {
        "message": compose(_medium(post), None, post.get("tags") or [], 5000),
        "access_token": env["FB_PAGE_ACCESS_TOKEN"],
    }
    link = with_utm(post.get("link_url"), "facebook")
    if link:
        form["link"] = link
    out = http_json("POST", f"{GRAPH}/{env['FB_PAGE_ID']}/feed", form=form)
    return out["id"], f"https://www.facebook.com/{out['id']}"


def publish_instagram(post: dict, env: dict[str, str]) -> tuple[str, str]:
    if not post.get("image_url"):
        raise ChannelError("Instagram 需要 image_url（公開可抓取的 JPEG）")
    uid, token = env["IG_USER_ID"], env["FB_PAGE_ACCESS_TOKEN"]
    # IG 內文連結不可點，仍保留網址供辨識
    caption = compose(_medium(post), post.get("link_url"), post.get("tags") or [], 2200)
    container = http_json(
        "POST", f"{GRAPH}/{uid}/media",
        form={"image_url": post["image_url"], "caption": caption, "access_token": token},
    )
    out = http_json(
        "POST", f"{GRAPH}/{uid}/media_publish",
        form={"creation_id": container["id"], "access_token": token},
    )
    return out["id"], ""


def publish_x(post: dict, env: dict[str, str]) -> tuple[str, str]:
    url = "https://api.x.com/2/tweets"
    text = compose(_short(post), with_utm(post.get("link_url"), "x"), post.get("tags") or [], 280)
    auth = oauth1_header(
        "POST", url,
        env["X_API_KEY"], env["X_API_SECRET"], env["X_ACCESS_TOKEN"], env["X_ACCESS_TOKEN_SECRET"],
    )
    out = http_json("POST", url, headers={"Authorization": auth}, json_body={"text": text})
    tid = out["data"]["id"]
    return tid, f"https://x.com/i/status/{tid}"


def _linkedin_version(env: dict[str, str]) -> str:
    # LinkedIn 版本化 API 每月一版、約支援一年；預設取兩個月前的版本，確保已釋出
    if env.get("LINKEDIN_API_VERSION"):
        return env["LINKEDIN_API_VERSION"]
    return (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y%m")


def publish_linkedin(post: dict, env: dict[str, str]) -> tuple[str, str]:
    link = with_utm(post.get("link_url"), "linkedin")
    body: dict = {
        "author": f"urn:li:organization:{env['LINKEDIN_ORG_ID']}",
        "commentary": compose(_medium(post), None, post.get("tags") or [], 3000),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if link:
        body["content"] = {"article": {"source": link, "title": post["title"]}}
    out = http_json(
        "POST", "https://api.linkedin.com/rest/posts",
        headers={
            "Authorization": f"Bearer {env['LINKEDIN_ACCESS_TOKEN']}",
            "LinkedIn-Version": _linkedin_version(env),
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json_body=body,
    )
    urn = out.get("_restli_id") or out.get("id") or ""
    return urn, f"https://www.linkedin.com/feed/update/{urn}/" if urn else ""


def publish_line(post: dict, env: dict[str, str]) -> tuple[str, str]:
    text = compose(_medium(post), with_utm(post.get("link_url"), "line"), [], 4900)
    http_json(
        "POST", "https://api.line.me/v2/bot/message/broadcast",
        headers={"Authorization": f"Bearer {env['LINE_CHANNEL_ACCESS_TOKEN']}"},
        json_body={"messages": [{"type": "text", "text": text}]},
    )
    return "broadcast", ""


PUBLISHERS = {
    "bluesky": publish_bluesky,
    "threads": publish_threads,
    "facebook": publish_facebook,
    "instagram": publish_instagram,
    "x": publish_x,
    "linkedin": publish_linkedin,
    "line": publish_line,
}
