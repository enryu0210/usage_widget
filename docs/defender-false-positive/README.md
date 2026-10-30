# v1.0.4 Windows Defender 오탐 (2026-10-30)

- 상태: 원인 확인, v1.0.5 재빌드로 해결 (릴리스는 사용자 확인 후)

## 1. 증상
GitHub 릴리스 v1.0.4 의 `AIUsageWidget.exe` 를 내려받자 Defender 가 격리.
- 탐지명: `Trojan:Win32/Sabsik.TE.A!ml` (`!ml` = 클라우드 머신러닝 휴리스틱, 시그니처가 아님)
- 릴리스 sha256: `0bc8a7b712e10bf0b6440b2475a5d0260ed798d9988a77f37c38fb7776408a39`

## 2. 원인
**코드 문제가 아니라, 그 빌드 결과물 하나가 ML 판정에 걸린 것.**
PyInstaller onefile exe 는 빌드할 때마다 바이트가 달라지고, Defender ML 은 미서명 PyInstaller exe 에
경계선 점수를 주는 일이 잦아 어떤 빌드는 걸리고 어떤 빌드는 안 걸린다.

`MpCmdRun -Scan -ScanType 3 -DisableRemediation` 으로 확인한 근거:

| 대상 | 결과 |
|---|---|
| 릴리스 v1.0.3 exe | 통과 |
| 릴리스 v1.0.4 와 같은 로컬 빌드 (`dist`, 14:59) | **탐지** (Sabsik.TE.A!ml) |
| 같은 HEAD 소스를 다시 빌드 (2회) | 둘 다 통과, 해시도 서로 다름 |
| 업데이터 제거 / relaunch 제거 / 교체 로직 제거 / 환경변수 제거 빌드 | 모두 통과 |
| 다시 빌드한 exe 에 인터넷 다운로드 표시(Zone.Identifier ZoneId=3) 부착 | 통과 |

→ 특정 코드(자동 업데이터)를 빼야 하는 문제가 아니다. 같은 소스로 다시 빌드하면 통과한다.

## 3. 조치
1. `APP_VERSION` 1.0.5 로 올려 재빌드 → Defender 통과 확인 (sha256 `1340f1d4…8b38`).
   같은 v1.0.4 에 파일만 바꾸지 않은 이유: 이미 받은 사람·캐시와 섞이지 않게 새 번호로 낸다.
2. `build.bat` 마지막에 Defender 검사 추가 — 걸리면 exit 1 로 멈춘다(탐지 시 MpCmdRun 종료 코드 2 확인).
   자동 업데이트가 있어서 걸린 exe 를 한 번 올리면 친구 PC 전부에 퍼지므로, 올리기 전에 막는다.
3. (사용자) 걸린 v1.0.4 파일을 Microsoft 에 오탐 신고: https://www.microsoft.com/en-us/wdsi/filesubmission
   (Software developer → Incorrectly detected). 로그인이 필요해 자동화하지 않았다.

## 4. 한계
- 로컬 검사를 통과해도, 업로드 후 다른 PC 에서 처음 다운로드될 때 클라우드 ML 이 다시 판정할 수 있다.
  완전히 막으려면 **코드 서명**(Azure Trusted Signing 등, 유료)이 필요하다. 오탐이 반복되면 그때 검토.
