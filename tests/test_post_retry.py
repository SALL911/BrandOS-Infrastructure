"""_post 重試測試：429／5xx／逾時要重試，4xx 不重試，Supabase 空 body 視為成功。

背景：gemini-3.8-flash 在尖峰時段頻繁回 503／429 或逾時，
未重試時 geo-audit.yml 單次執行 20 題可能全數失敗。
"""
import io
import sys, pathlib
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))

import geo_audit  # noqa: E402


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return HTTPError("https://x", code, "err", headers, io.BytesIO(b"busy"))


def _install(monkeypatch, outcomes):
    calls, sleeps = [], []

    def fake_urlopen(req, timeout):
        calls.append(timeout)
        out = outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return _Resp(out)

    monkeypatch.setattr(geo_audit.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(geo_audit.time, "sleep", sleeps.append)
    return calls, sleeps


def test_retries_503_then_succeeds(monkeypatch):
    calls, sleeps = _install(monkeypatch, [_http_error(503), b'{"ok": 1}'])
    assert geo_audit._post("https://x", {}, {}) == {"ok": 1}
    assert len(calls) == 2
    assert sleeps == [geo_audit.RETRY_BASE_DELAY]


def test_retries_timeout_then_succeeds(monkeypatch):
    calls, _ = _install(monkeypatch, [TimeoutError("The read operation timed out"), b"{}"])
    assert geo_audit._post("https://x", {}, {}) == {}
    assert len(calls) == 2


def test_honors_retry_after_on_429(monkeypatch):
    _, sleeps = _install(monkeypatch, [_http_error(429, "7"), b"{}"])
    geo_audit._post("https://x", {}, {})
    assert sleeps == [7.0]


def test_gives_up_after_retries(monkeypatch):
    n = geo_audit.HTTP_RETRIES + 1
    calls, sleeps = _install(monkeypatch, [_http_error(503) for _ in range(n)])
    resp = geo_audit._post("https://x", {}, {})
    assert resp["_error"] == "HTTP 503"
    assert len(calls) == n
    assert len(sleeps) == n - 1


def test_does_not_retry_client_error(monkeypatch):
    calls, sleeps = _install(monkeypatch, [_http_error(400)])
    assert geo_audit._post("https://x", {}, {})["_error"] == "HTTP 400"
    assert len(calls) == 1 and sleeps == []


def test_empty_success_body_is_not_an_error(monkeypatch):
    _install(monkeypatch, [b""])
    assert geo_audit._post("https://x", {}, {}) == {}
