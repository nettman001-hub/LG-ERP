# OTP 중계 연동 메모

이 문서는 ERP SMS OTP를 Android 알림 앱과 HTTP 중계 서버를 통해 `main.py`에서 자동 수신하는 기능의 현재 기준 메모입니다.

## 현재 반영된 코드

다음 파일이 이미 반영되었습니다.

1. `main.py`
2. `otp_bridge_client.py`

현재 `ERPLoginDialog`에는 아래 기능이 추가되었습니다.

1. 자동 OTP 수신 사용 체크박스
2. 중계 URL 입력란
3. 상태 표시 라벨
4. SMS 발송 성공 후 중계 서버 polling
5. OTP 수신 시 자동 입력 후 자동 검증
6. 실패 시 수동 입력 fallback 유지

## 중계 서버 API 규칙

`main.py`는 아래 두 엔드포인트를 기대합니다.

### 1. GET `otp_latest.php`

정상 OTP가 있으면:

```json
{
  "ok": true,
  "code": "123456",
  "created_at": "2026-03-16T10:20:30"
}
```

OTP가 없으면:

```json
{
  "ok": false
}
```

### 2. POST `otp_delete.php`

응답 형식은 자유지만 HTTP 200이면 삭제 성공으로 취급합니다.

예:

```json
{
  "ok": true
}
```

## `main.py` 동작 방식

1. 사용자가 아이디/비밀번호 입력
2. `문자 인증번호 받기` 클릭
3. SMS 발송 성공
4. 자동 OTP 사용이 켜져 있고 URL이 있으면 polling 시작
5. 2초 간격으로 `otp_latest.php` 조회
6. OTP를 받으면 입력칸에 채움
7. `login_step2_verify_sms()` 자동 호출
8. OTP는 바로 `otp_delete.php`로 삭제 시도

제한:

1. polling 최대 60회
2. 총 대기시간은 약 120초

## 환경변수

중계 URL은 앱 실행 전 환경변수로 기본값을 넣을 수 있습니다.

PowerShell 예:

```powershell
$env:OTP_BRIDGE_BASE_URL="http://example.com/otp"
py main.py
```

이 값을 주면 로그인 창의 중계 URL 입력란 기본값으로 채워집니다.

## 아직 안 만든 것

아래는 아직 구현하지 않았습니다.

1. Android 알림 읽기 앱
2. OTP TTL 강제 검증 로직
3. 중복 로그인 구분용 request id

PHP 중계 서버 파일은 초안 작성 및 서버 업로드 확인 완료:

1. `otp_upload.php`
2. `otp_latest.php`
3. `otp_delete.php`

## 다음 구현 권장 순서

1. `otp_upload.php`
2. `otp_latest.php`
3. `otp_delete.php`
4. Android 앱에서 OTP 업로드 테스트
5. `main.py` 실제 연동 테스트

Android 앱 명세는 `ANDROID_OTP_APP_SPEC.md` 참고
