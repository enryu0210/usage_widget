"""Gemini 및 Argon(Gemini 4 Argon) 잔여 사용량 조회 모듈.

로컬에 저장된 Google OAuth 토큰(위젯 전용 저장소, Windows 자격 증명 관리자, Antigravity IDE DB)을
순서대로 탐색하고, 단일 API 호출로 일반 Gemini 모델과 Argon 주간 쿼터를 분리 조회한다.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import sqlite3
import urllib.error
import urllib.parse

from .base import WIDGET_CONFIG_DIR, ProviderStatus, QuotaMetric, format_reset, http_json


def get_gemini_oauth_client() -> tuple[str, str]:
    """로컬에 설치된 Antigravity 바이너리 또는 캐시 파일에서 OAuth 클라이언트 정보를 동적으로 읽는다.

    코드 저장소에 OAuth 클라이언트 식별자를 하드코딩하면 GitHub Push Protection에 차단되므로,
    현재 기기의 설치본에서 최초 1회 추출하여 ~/.usage_widget/gemini_client.json 에 캐싱한다.
    """
    cache_file = WIDGET_CONFIG_DIR / "gemini_client.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("client_id") and data.get("client_secret"):
                return str(data["client_id"]), str(data["client_secret"])
        except Exception:
            pass

    local_app = os.environ.get("LOCALAPPDATA", "")
    exe_path = pathlib.Path(local_app) / "agy" / "bin" / "agy.exe"
    if exe_path.exists():
        raw = exe_path.read_bytes()
        ids = re.findall(b"107[0-9]{10}-[a-z0-9]{32}\\.apps\\.googleusercontent\\.com", raw)
        secrets = re.findall(b"GOCSPX-[A-Za-z0-9_\\-]{28}", raw)
        if ids and secrets:
            cid = ids[0].decode("ascii")
            csec = secrets[0].decode("ascii")
            WIDGET_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps({"client_id": cid, "client_secret": csec}, indent=2),
                encoding="utf-8",
            )
            return cid, csec

    raise RuntimeError("로컬 Antigravity 설치본에서 OAuth 클라이언트 정보를 찾을 수 없습니다.")


def _extract_credman_refresh_token() -> str | None:
    """Windows 자격 증명 관리자(gemini:antigravity)에서 refresh_token을 추출한다.

    agy CLI만 설치·로그인된 환경에서도 별도 로그인 없이 즉시 연동되도록 지원한다.
    """
    try:
        import ctypes
        import ctypes.wintypes

        class _CREDENTIALW(ctypes.Structure):
            _fields_ = [
                ("Flags", ctypes.wintypes.DWORD),
                ("Type", ctypes.wintypes.DWORD),
                ("TargetName", ctypes.wintypes.LPWSTR),
                ("Comment", ctypes.wintypes.LPWSTR),
                ("LastWritten", ctypes.wintypes.FILETIME),
                ("CredentialBlobSize", ctypes.wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
                ("Persist", ctypes.wintypes.DWORD),
                ("AttributeCount", ctypes.wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.wintypes.LPWSTR),
                ("UserName", ctypes.wintypes.LPWSTR),
            ]

        advapi32 = ctypes.WinDLL("advapi32.dll")
        pcred = ctypes.POINTER(_CREDENTIALW)()
        if not advapi32.CredReadW("gemini:antigravity", 1, 0, ctypes.byref(pcred)):
            return None
        try:
            blob = ctypes.string_at(
                pcred.contents.CredentialBlob, pcred.contents.CredentialBlobSize
            ).decode("utf-8", "ignore")
        finally:
            advapi32.CredFree(pcred)
        raw = json.loads(blob)
        tok_obj = raw.get("token") if isinstance(raw.get("token"), dict) else raw
        rt = tok_obj.get("refresh_token")
        return str(rt) if rt else None
    except Exception:
        return None


def _extract_antigravity_refresh_token() -> str | None:
    """Antigravity IDE의 로컬 SQLite(state.vscdb)에서 Google OAuth refresh_token을 추출한다."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    db_path = pathlib.Path(appdata) / "Antigravity" / "User" / "globalStorage" / "state.vscdb"
    if not db_path.exists():
        return None
    try:
        # IDE가 실행 중일 때도 락 충돌이 나지 않도록 읽기 전용 URI 모드로 연다.
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        try:
            row = conn.execute(
                "SELECT value FROM ItemTable WHERE key = 'antigravityUnifiedStateSync.oauthToken'"
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return None
        outer = base64.b64decode(row[0])
        for chunk in re.findall(b"[A-Za-z0-9_\\-\\./:=+]{16,}", outer):
            try:
                inner = base64.b64decode(chunk.decode("ascii", "ignore"))
                matches = re.findall(b"1//[A-Za-z0-9_\\-]+", inner)
                if matches:
                    return matches[0].decode("ascii")
            except Exception:
                continue
    except Exception:
        return None
    return None


def get_gemini_refresh_token() -> str | None:
    """위젯 전용 저장소 -> Windows 자격 증명 관리자 -> Antigravity IDE 순서로 토큰을 찾는다."""
    saved = WIDGET_CONFIG_DIR / "gemini_oauth.json"
    if saved.exists():
        try:
            tok = json.loads(saved.read_text(encoding="utf-8")).get("refresh_token")
            if tok:
                return str(tok)
        except Exception:
            pass
    return _extract_credman_refresh_token() or _extract_antigravity_refresh_token()


def fetch_gemini_and_argon() -> tuple[ProviderStatus, ProviderStatus]:
    """Google Code Assist (Antigravity) API에서 Gemini 일반 모델과 Gemini 4 Argon 잔여량을 분리 조회한다.

    단일 API 호출(retrieveUserQuotaSummary)로 두 그룹 데이터를 모두 받아와
    불필요한 중복 네트워크 왕복을 방지하고 UI에는 별도 카드로 분리해 제공한다.
    """
    refresh_token = get_gemini_refresh_token()
    if not refresh_token:
        return (
            ProviderStatus("Gemini", False, error="계정 미연동 ([계정 연동] 클릭)"),
            ProviderStatus("Argon", False, error="Gemini 계정 연동 시 함께 표시됨"),
        )

    try:
        client_id, client_secret = get_gemini_oauth_client()
        tok_form = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        tok_res = http_json("https://oauth2.googleapis.com/token", method="POST", data=tok_form)
        access_token = tok_res["access_token"]

        ca_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            # 서버가 Gemini Models 및 Gemini 4 Argon 버킷을 모두 내려주려면
            # Antigravity CLI 형식의 User-Agent와 최신 빌드 CL 번호가 포함되어야 한다.
            "User-Agent": (
                "antigravity/cli/1.4.2 "
                "(aidev_client; os_type=windows; arch=amd64; cl=1001597273; auth_method=consumer)"
            ),
        }

        load_res = http_json(
            "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
            method="POST",
            headers=ca_headers,
            data=json.dumps(
                {
                    "metadata": {
                        "ideType": "ANTIGRAVITY",
                        "platform": "WINDOWS_AMD64",
                        "pluginType": "GEMINI",
                    }
                }
            ).encode("utf-8"),
        )

        paid_tier = load_res.get("paidTier") or {}
        current_tier = load_res.get("currentTier") or {}
        plan = str(paid_tier.get("name") or current_tier.get("name") or "Gemini").upper()
        project = load_res.get("cloudaicompanionProject") or "aicode-consumers"

        summary_res = http_json(
            "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary",
            method="POST",
            headers=ca_headers,
            data=json.dumps({"project": project}).encode("utf-8"),
        )

        gemini_metrics: list[QuotaMetric] = []
        argon_metrics: list[QuotaMetric] = []

        # 5시간 한도를 위쪽에, 주간 한도를 아래쪽에 일관되게 배치한다.
        window_labels = {"5h": "5시간 한도 잔여", "weekly": "7일 주간 잔여"}
        window_order = {"5h": 0, "weekly": 1}

        for grp in summary_res.get("groups") or []:
            gname = str(grp.get("displayName") or "")
            buckets = sorted(
                grp.get("buckets") or [],
                key=lambda b: window_order.get(str(b.get("window") or ""), 99),
            )
            for b in buckets:
                if b.get("remainingFraction") is None:
                    continue
                rem = max(0.0, min(100.0, float(b["remainingFraction"]) * 100.0))
                win = str(b.get("window") or "")
                label = window_labels.get(win, str(b.get("displayName") or "쿼터 잔여"))
                metric = QuotaMetric(label, rem, format_reset(b.get("resetTime")))

                if "Argon" in gname or "argon" in str(b.get("bucketId") or ""):
                    argon_metrics.append(metric)
                elif "Gemini" in gname or str(b.get("bucketId") or "").startswith("gemini-"):
                    gemini_metrics.append(metric)

        gemini_status = ProviderStatus("Gemini", True, plan=plan, metrics=gemini_metrics)
        if argon_metrics:
            argon_status = ProviderStatus("Argon", True, plan="GEMINI 4", metrics=argon_metrics)
        else:
            argon_status = ProviderStatus(
                "Argon", False, plan="GEMINI 4", error="Argon 별도 쿼터 대상 요금제가 아님"
            )
        return gemini_status, argon_status
    except urllib.error.HTTPError as e:
        err_msg = f"API 오류 ({e.code}) - 재연동 필요"
        return (
            ProviderStatus("Gemini", False, error=err_msg),
            ProviderStatus("Argon", False, error=err_msg),
        )
    except Exception as e:
        err_msg = f"조회 실패: {e}"
        return (
            ProviderStatus("Gemini", False, error=err_msg),
            ProviderStatus("Argon", False, error=err_msg),
        )
