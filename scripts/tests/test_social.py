"""Unit tests for scripts/social/ 與 social_publisher 的純函式（不連網、不連 DB）。

Run:
    python -m unittest scripts.tests.test_social
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from social.channels import PUBLISHERS, REQUIRED_ENV, is_configured  # noqa: E402
from social.common import (  # noqa: E402
    ChannelError,
    bluesky_link_facets,
    compose,
    lint_copy,
    oauth1_signature,
    with_utm,
)
from social_publisher import MAX_ATTEMPTS, plan_channels  # noqa: E402


class UtmTest(unittest.TestCase):
    def test_adds_utm_to_symcio_links_only(self):
        out = with_utm("https://symcio.tw/news/a?x=1", "threads", "c1")
        self.assertIn("x=1", out)
        self.assertIn("utm_source=threads", out)
        self.assertIn("utm_medium=social", out)
        self.assertIn("utm_campaign=c1", out)
        self.assertIn("utm_source=x", with_utm("https://www.symcio.tw/", "x"))
        self.assertEqual(with_utm("https://doi.org/10.5281/zenodo.20419081", "x"), "https://doi.org/10.5281/zenodo.20419081")
        # 不可被相似網域騙過
        self.assertEqual(with_utm("https://evilsymcio.tw/", "x"), "https://evilsymcio.tw/")
        self.assertIsNone(with_utm(None, "x"))

    def test_keeps_existing_utm(self):
        self.assertIn("utm_source=newsletter", with_utm("https://symcio.tw/?utm_source=newsletter", "x"))


class LintTest(unittest.TestCase):
    def test_flags_banned_terms_and_exclamation(self):
        self.assertEqual(lint_copy("BCI 把 AI 可見度與 ESG 整合成可查證的數據。"), [])
        self.assertTrue(lint_copy("顛覆產業的平台"))
        self.assertTrue(lint_copy("立即體驗！"))
        self.assertTrue(lint_copy("Bloomberg Official Partner"))


class ComposeTest(unittest.TestCase):
    def test_fits_without_truncation(self):
        self.assertEqual(compose("內文", "https://symcio.tw/", ["AVI", "B C"], 280), "內文\n\nhttps://symcio.tw/\n\n#AVI #BC")

    def test_drops_tags_then_truncates_body_but_keeps_link(self):
        link = "https://symcio.tw/news/x"
        out = compose("字" * 400, link, ["AVI"], 280)
        self.assertLessEqual(len(out), 280)
        self.assertTrue(out.endswith(link))
        self.assertNotIn("#AVI", out)
        self.assertIn("…", out)

    def test_rejects_link_that_cannot_fit(self):
        with self.assertRaises(ChannelError):
            compose("內文", "https://symcio.tw/" + "a" * 300, [], 280)


class OAuthTest(unittest.TestCase):
    def test_signature_matches_published_reference_vector(self):
        # X 開發者文件「Creating a signature」的範例
        params = {
            "status": "Hello Ladies + Gentlemen, a signed OAuth request!",
            "include_entities": "true",
            "oauth_consumer_key": "xvz1evFS4wEEPTGEFPHBog",
            "oauth_nonce": "kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg",
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": "1318622958",
            "oauth_token": "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb",
            "oauth_version": "1.0",
        }
        sig = oauth1_signature(
            "POST", "https://api.twitter.com/1.1/statuses/update.json", params,
            "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw", "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
        )
        self.assertEqual(sig, "hCtSmYh+iHYCEqBWrE7C7hYmtUk=")


class BlueskyFacetTest(unittest.TestCase):
    def test_byte_offsets_account_for_cjk(self):
        text = "品牌 https://symcio.tw/a 結尾"
        (facet,) = bluesky_link_facets(text)
        raw = text.encode("utf-8")
        span = raw[facet["index"]["byteStart"] : facet["index"]["byteEnd"]].decode("utf-8")
        self.assertEqual(span, "https://symcio.tw/a")
        self.assertEqual(facet["features"][0]["uri"], "https://symcio.tw/a")


class PlanTest(unittest.TestCase):
    ENV = {"BLUESKY_HANDLE": "h", "BLUESKY_APP_PASSWORD": "p", "FB_PAGE_ID": "1", "FB_PAGE_ACCESS_TOKEN": "t", "IG_USER_ID": "2"}

    def test_every_channel_has_publisher_and_env_spec(self):
        self.assertEqual(set(PUBLISHERS), set(REQUIRED_ENV))

    def test_line_needs_explicit_opt_in(self):
        self.assertFalse(is_configured("line", {"LINE_CHANNEL_ACCESS_TOKEN": "t"}))
        self.assertFalse(is_configured("line", {"LINE_CHANNEL_ACCESS_TOKEN": "t", "LINE_BROADCAST_ENABLED": "false"}))
        self.assertTrue(is_configured("line", {"LINE_CHANNEL_ACCESS_TOKEN": "t", "LINE_BROADCAST_ENABLED": "true"}))

    def test_plan_skips_done_unconfigured_and_exhausted(self):
        post = {"channels": ["bluesky", "facebook", "instagram", "x", "threads"], "image_url": None}
        todo, skipped, given_up = plan_channels(post, {"threads"}, {"facebook": MAX_ATTEMPTS}, self.ENV)
        self.assertEqual(todo, ["bluesky"])
        self.assertEqual(given_up, ["facebook"])
        self.assertEqual([s[0] for s in skipped], ["instagram", "x"])
        self.assertIn("image_url", skipped[0][1])
        self.assertIn("X_API_KEY", skipped[1][1])


if __name__ == "__main__":
    unittest.main()
