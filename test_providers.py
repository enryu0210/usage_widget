"""토큰 갱신·연동 로직 오프라인 검증 (python test_providers.py).

실제 계정 토큰을 건드리지 않도록 네트워크 호출(http_json)을 가짜로 바꾸고 임시 폴더에서만 실행한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

from providers import ProviderStatus, QuotaMetric, auth, base, claude, codex, gemini
from ui import updater
from ui.app import UsageWidgetApp
from ui.settings import DisplaySettings


def check_claude_refreshes_expired_token(tmp: pathlib.Path) -> None:
    """재부팅 후처럼 access token 이 만료돼 있으면 갱신하고, 새 토큰을 파일에 되써 넣어야 한다."""
    cred = tmp / ".credentials.json"
    expired_ms = int((time.time() - 3600) * 1000)
    cred.write_text(json.dumps({"claudeAiOauth": {
        "accessToken": "old-at", "refreshToken": "old-rt", "expiresAt": expired_ms,
        "subscriptionType": "max", "scopes": ["user:inference"],
    }}), encoding="utf-8")

    calls: list[str] = []

    def fake_http_json(url, **kw):
        calls.append(url)
        if url.endswith("/oauth/token"):
            assert json.loads(kw["data"])["refresh_token"] == "old-rt"
            return {"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 28800}
        assert kw["headers"]["Authorization"] == "Bearer new-at"
        return {"five_hour": {"utilization": 30, "resets_at": None}}

    with mock.patch.object(claude, "http_json", fake_http_json):
        st = claude.fetch_claude(cred)

    assert st.connected and st.metrics[0].remaining_percent == 70.0, st
    saved = json.loads(cred.read_text(encoding="utf-8"))["claudeAiOauth"]
    assert saved["accessToken"] == "new-at" and saved["refreshToken"] == "new-rt"
    assert saved["expiresAt"] > time.time() * 1000
    assert saved["scopes"] == ["user:inference"], "다른 필드는 보존돼야 한다"

    # 유효한 토큰이면 갱신 호출 없이 사용량 API 만 불러야 한다.
    calls.clear()
    with mock.patch.object(claude, "http_json", fake_http_json):
        claude.fetch_claude(cred)
    assert not any(u.endswith("/oauth/token") for u in calls), calls


def check_gemini_picks_matching_secret(tmp: pathlib.Path) -> None:
    """agy.exe 안의 첫 번째 secret 이 짝이 아니어도 검증을 통과한 secret 을 골라야 한다."""
    cid = "107" + "1" * 10 + "-" + "a" * 32 + ".apps.googleusercontent.com"
    # Push Protection 오탐을 피하려고 secret 형태 문자열을 실행 시점에 조립한다.
    wrong, right = "GOCSPX" + "-" + "W" * 28, "GOCSPX" + "-" + "R" * 28
    exe = tmp / "agy" / "bin" / "agy.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(f"xx{wrong}yy{cid}zz{wrong}{right}".encode())
    conf = tmp / "conf"
    # 옛 버전이 잘못 캐싱한(검증 표시 없는) 짝은 무시하고 다시 골라야 한다.
    conf.mkdir()
    (conf / "gemini_client.json").write_text(json.dumps({"client_id": cid, "client_secret": wrong}))

    with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(tmp)}), \
         mock.patch.object(gemini, "WIDGET_CONFIG_DIR", conf), \
         mock.patch.object(gemini, "_is_valid_client_pair", lambda c, s: s == right):
        assert gemini.get_gemini_oauth_client() == (cid, right)
    cached = json.loads((conf / "gemini_client.json").read_text())
    assert cached["client_secret"] == right and cached["verified"]


def check_agy_found_on_path(tmp: pathlib.Path) -> None:
    """기본 경로에 agy 가 없어도 PATH 에 있는 agy.exe 를 찾아야 하고, .cmd 래퍼는 거절해야 한다."""
    exe = tmp / "elsewhere" / "agy.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(tmp)}):
        with mock.patch.object(gemini.shutil, "which", lambda name: str(exe)):
            assert gemini._find_agy_exe() == exe
        with mock.patch.object(gemini.shutil, "which", lambda name: str(tmp / "agy.cmd")):
            try:
                gemini._find_agy_exe()
                raise AssertionError(".cmd 래퍼를 agy 바이너리로 받아들였다")
            except RuntimeError as e:
                assert "agy.cmd" in str(e)  # 오류 문구에 찾은 경로가 남아야 다음 진단이 쉽다


def check_login_ignores_stray_requests(tmp: pathlib.Path) -> None:
    """콜백 전에 favicon 같은 요청이 먼저 와도 서버가 닫히지 않고 진짜 code 를 받아야 한다."""

    def fake_browser(url: str) -> None:
        redirect_uri = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["redirect_uri"][0]
        port = redirect_uri.rsplit(":", 1)[1]

        def _hit() -> None:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/favicon.ico").read()
            urllib.request.urlopen(f"http://127.0.0.1:{port}/?code=abc").read()

        threading.Thread(target=_hit, daemon=True).start()

    def fake_http_json(url, **kw):
        assert b"code=abc" in kw["data"]
        return {"refresh_token": "rt-1"}

    with mock.patch.object(auth, "get_gemini_oauth_client", lambda: ("cid", "sec")), \
         mock.patch.object(auth.webbrowser, "open", fake_browser), \
         mock.patch.object(auth, "http_json", fake_http_json), \
         mock.patch.object(auth, "WIDGET_CONFIG_DIR", tmp):
        assert auth.link_gemini_oauth(timeout_sec=10) is True
    assert json.loads((tmp / "gemini_oauth.json").read_text())["refresh_token"] == "rt-1"


def check_gemini_falls_back_to_bundled_client(tmp: pathlib.Path) -> None:
    """Antigravity 가 없는 PC 에서도 exe 에 동봉된 검증된 클라이언트로 연동할 수 있어야 한다."""
    conf = tmp / "conf"  # 캐시 없음
    meipass = tmp / "meipass"
    (meipass / "bundled").mkdir(parents=True)
    bundled = meipass / "bundled" / "gemini_client.json"
    bundled.write_text(json.dumps({"client_id": "cid", "client_secret": "sec", "verified": True}))

    with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(tmp)}),          mock.patch.object(gemini.shutil, "which", lambda name: None),          mock.patch.object(gemini, "WIDGET_CONFIG_DIR", conf):
        with mock.patch.object(gemini.sys, "_MEIPASS", str(meipass), create=True):
            assert gemini.get_gemini_oauth_client() == ("cid", "sec")
        # 검증 표시가 없는 동봉본은 짝이 틀렸을 수 있으니 쓰지 않고 원래 오류를 보여줘야 한다.
        bundled.write_text(json.dumps({"client_id": "cid", "client_secret": "sec"}))
        with mock.patch.object(gemini.sys, "_MEIPASS", str(meipass), create=True):
            try:
                gemini.get_gemini_oauth_client()
                raise AssertionError("검증 안 된 동봉본을 사용했다")
            except RuntimeError as e:
                assert "agy" in str(e)


def check_gemini_keeps_other_groups_as_detail(tmp: pathlib.Path) -> None:
    """Gemini/Argon 이 아닌 모델 그룹도 버리지 말고 Gemini 카드의 세부(기본 숨김) 행으로 둬야 한다."""
    summary = {"groups": [
        {"displayName": "Gemini Models", "buckets": [
            {"bucketId": "gemini-weekly", "window": "weekly", "remainingFraction": 0.5},
            {"bucketId": "gemini-5h", "window": "5h", "remainingFraction": 0.9},
        ]},
        {"displayName": "Gemini 4 Argon", "buckets": [
            {"bucketId": "argon-weekly", "window": "weekly", "remainingFraction": 0.3},
        ]},
        {"displayName": "Claude Models", "buckets": [
            {"bucketId": "claude-5h", "window": "5h", "remainingFraction": 0.7},
        ]},
    ]}

    def fake_http_json(url, **kw):
        if url.endswith("/token"):
            return {"access_token": "at"}
        if url.endswith(":loadCodeAssist"):
            return {"currentTier": {"name": "pro"}}
        return summary

    with mock.patch.object(gemini, "get_gemini_refresh_token", lambda: "rt"),          mock.patch.object(gemini, "get_gemini_oauth_client", lambda: ("cid", "sec")),          mock.patch.object(gemini, "http_json", fake_http_json):
        gem, argon = gemini.fetch_gemini_and_argon()

    assert [(m.label, m.detail) for m in gem.metrics] == [
        ("5시간 한도 잔여", False), ("7일 주간 잔여", False), ("Claude Models · 5시간 한도 잔여", True),
    ], gem.metrics
    assert len({m.key for m in gem.metrics}) == 3, "행마다 고유 키가 있어야 표시 설정이 섞이지 않는다"
    assert argon.connected and argon.metrics[0].key == "argon.argon-weekly"


def check_codex_additional_limits_are_detail(tmp: pathlib.Path) -> None:
    """Codex 모델별 추가 한도는 이름을 붙인 세부 행으로 나와야 한다."""
    (tmp / ".codex").mkdir()
    (tmp / ".codex" / "auth.json").write_text(json.dumps({"tokens": {"access_token": "at"}}))
    usage = {
        "plan_type": "plus",
        "rate_limit": {"primary_window": {"used_percent": 20, "limit_window_seconds": 18000}},
        "additional_rate_limits": [{
            "limit_name": "codex-mini",
            "rate_limit": {"secondary_window": {"used_percent": 60, "limit_window_seconds": 604800}},
        }],
    }
    with mock.patch.object(codex.pathlib.Path, "home", lambda: tmp),          mock.patch.object(codex, "http_json", lambda url, **kw: usage):
        st = codex.fetch_codex()
    assert [(m.label, m.remaining_percent, m.detail) for m in st.metrics] == [
        ("5시간 한도 잔여", 80.0, False), ("codex-mini · 7일 주간 잔여", 40.0, True),
    ], st


def check_codex_model_usage_shows_status(tmp: pathlib.Path) -> None:
    """model_usage(예: gpt-6-astra)는 % 대신 사용 가능/한도 도달 상태 행으로 나와야 한다."""
    (tmp / ".codex").mkdir()
    (tmp / ".codex" / "auth.json").write_text(json.dumps({"tokens": {"access_token": "at"}}))
    reset_at = int(time.time()) + 3 * 3600 + 120
    usage = {
        "plan_type": "pro",
        "rate_limit": {"primary_window": {"used_percent": 7, "limit_window_seconds": 604800}},
        "model_usage": {
            "gpt-6-astra": {"available": True, "available_at": None},
            "gpt-7-nova": {"available": False, "available_at": reset_at},
            "broken": None,
        },
    }
    with mock.patch.object(codex.pathlib.Path, "home", lambda: tmp),          mock.patch.object(codex, "http_json", lambda url, **kw: usage):
        st = codex.fetch_codex()
    rows = [(m.label, m.status_text, m.remaining_percent, m.detail, m.key) for m in st.metrics[1:]]
    assert rows == [
        ("GPT-6 Astra", "사용 가능", 100.0, False, "codex.model.gpt-6-astra"),
        ("GPT-7 Nova", "한도 도달", 0.0, False, "codex.model.gpt-7-nova"),
    ], rows
    assert st.metrics[2].reset_text.startswith("3시간"), st.metrics[2].reset_text


def check_display_settings_persist(tmp: pathlib.Path) -> None:
    """기본은 '기본 행 보임·세부 행 숨김'이고, 바꾼 값은 재시작 후에도 유지돼야 한다."""
    path = tmp / "display.json"
    base = QuotaMetric("5시간", 50.0, key="claude.five_hour")
    detail = QuotaMetric("Opus", 50.0, key="claude.seven_day_opus", detail=True)

    s = DisplaySettings(path)
    assert s.card_visible("Codex") and s.metric_visible(base) and not s.metric_visible(detail)
    s.set_card("Codex", False)
    s.set_metric(detail, True)
    s.set_metric(base, False)

    s = DisplaySettings(path)
    assert not s.card_visible("Codex") and s.metric_visible(detail) and not s.metric_visible(base)

    path.write_text("{깨진 json")  # 파일이 깨져도 위젯은 기본값으로 떠야 한다
    s = DisplaySettings(path)
    assert s.card_visible("Codex") and not s.metric_visible(detail)


def check_timeout_retries_and_keeps_previous(tmp: pathlib.Path) -> None:
    """시간 초과는 1회 재시도하고, 그래도 실패하면 카드가 직전 값을 유지해야 한다(인증 실패는 그대로 노출)."""
    calls = []

    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b'{"ok": 1}'

    def flaky_urlopen(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError(TimeoutError("timed out"))
        return FakeResp()

    with mock.patch.object(base.urllib.request, "urlopen", flaky_urlopen),          mock.patch.object(base.time, "sleep", lambda s: None):
        assert base.http_json("https://x") == {"ok": 1} and len(calls) == 2
        calls.clear()
        try:  # retries=0 (일회용 토큰 호출)은 재전송하면 안 된다
            base.http_json("https://x", retries=0)
            raise AssertionError("재시도하면 안 됨")
        except urllib.error.URLError:
            assert len(calls) == 1

    assert base.is_transient(urllib.error.HTTPError("u", 429, "", {}, None))
    assert not base.is_transient(urllib.error.HTTPError("u", 401, "", {}, None))

    good = ProviderStatus("Claude", True, metrics=[QuotaMetric("5시간", 40.0)])
    app = mock.Mock(_last_statuses=[good, ProviderStatus("Codex", True)])
    merged = UsageWidgetApp._keep_previous_on_transient(app, [
        ProviderStatus("Claude", False, error="조회 실패: timed out", transient=True),
        ProviderStatus("Codex", False, error="API 오류 (401)"),
    ])
    assert merged[0].connected and merged[0].metrics == good.metrics and "이전 값" in merged[0].error
    assert not merged[1].connected  # 인증 실패는 덮지 않는다


def check_claude_shows_new_model_windows(tmp: pathlib.Path) -> None:
    """목록에 없는 새 모델 한도(seven_day_xxx)도 세부 행으로 나오고, 관계없는 키는 무시해야 한다."""
    cred = tmp / ".credentials.json"
    cred.write_text(json.dumps({"claudeAiOauth": {"accessToken": "at"}}), encoding="utf-8")
    usage = {
        "five_hour": {"utilization": 10, "resets_at": None},
        "seven_day_new_model": {"utilization": 25, "resets_at": None},
        "five_hour_new_model": None,  # 요금제가 안 주면 null — 행을 만들지 않는다
        "extra_usage": {"utilization": 50},  # 한도 창이 아닌 키
    }
    with mock.patch.object(claude, "http_json", lambda url, **kw: usage):
        st = claude.fetch_claude(cred)
    rows = {m.key: m for m in st.metrics}
    assert set(rows) == {"claude.five_hour", "claude.seven_day_new_model"}, rows
    new_row = rows["claude.seven_day_new_model"]
    assert new_row.label == "7일 New Model 잔여" and new_row.detail and new_row.remaining_percent == 75.0


def check_updater_finds_and_installs(tmp: pathlib.Path) -> None:
    """새 버전만 받고, 해시가 맞을 때만 exe 를 바꿔치기해야 한다."""
    exe = tmp / "AIUsageWidget.exe"
    exe.write_bytes(b"old build")
    new_bytes = b"new build"
    new_hash = hashlib.sha256(new_bytes).hexdigest()

    def release(tag, digest):
        return {"tag_name": tag, "assets": [{
            "name": "AIUsageWidget.exe", "browser_download_url": "https://example/exe",
            "digest": f"sha256:{digest}" if digest else None,
        }]}

    def find(rel):
        with mock.patch.object(updater, "http_json", lambda url, **kw: rel):
            return updater.find_update(exe)

    assert updater.parse_version("v1.10.0") > updater.parse_version("1.9.9")
    assert find(release("v99.0.0", new_hash)) == ("https://example/exe", new_hash)
    assert find(release(f"v{updater.APP_VERSION}", new_hash)) is None, "같은 버전은 받지 않는다"
    assert find(release("v99.0.0", None)) is None, "해시 없는 파일은 설치하지 않는다"
    # APP_VERSION 을 안 올린 채 릴리스해도, 이미 같은 파일이면 무한 재설치하지 않는다.
    assert find(release("v99.0.0", hashlib.sha256(b"old build").hexdigest())) is None

    def fake_urlopen(body):
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.side_effect = [body, b""]
        return lambda req, timeout: resp

    # 다운로드가 손상됐으면 원래 exe 를 그대로 둔다.
    with mock.patch.object(updater.urllib.request, "urlopen", fake_urlopen(b"tampered")):
        assert not updater.install(exe, "https://example/exe", new_hash)
    assert exe.read_bytes() == b"old build" and not (tmp / "AIUsageWidget.exe.new").exists()

    with mock.patch.object(updater.urllib.request, "urlopen", fake_urlopen(new_bytes)):
        assert updater.install(exe, "https://example/exe", new_hash)
    assert exe.read_bytes() == new_bytes
    assert (tmp / "AIUsageWidget.exe.old").read_bytes() == b"old build"

    # 오프라인이어도 예외가 새어 나와 위젯을 죽이지 않아야 한다.
    quit_calls = []
    def offline(url, **kw):
        raise urllib.error.URLError("offline")
    with mock.patch.object(updater, "http_json", offline):
        updater.check_and_update(exe, lambda: quit_calls.append(1))
    assert not quit_calls


if __name__ == "__main__":
    for check in (check_claude_refreshes_expired_token, check_gemini_picks_matching_secret,
                  check_agy_found_on_path, check_login_ignores_stray_requests,
                  check_gemini_falls_back_to_bundled_client, check_gemini_keeps_other_groups_as_detail,
                  check_codex_additional_limits_are_detail, check_display_settings_persist,
                  check_timeout_retries_and_keeps_previous, check_claude_shows_new_model_windows,
                  check_updater_finds_and_installs, check_codex_model_usage_shows_status):
        with tempfile.TemporaryDirectory() as d:
            check(pathlib.Path(d))
        print("OK", check.__name__)
