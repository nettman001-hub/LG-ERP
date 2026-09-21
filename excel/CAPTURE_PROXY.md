# 캡처 프록시 사용 안내

이 문서는 `newbest.lge.com` 트래픽을 분석하기 위해 만든 전용 캡처 프록시의 사용 방법을 정리한 문서입니다.

이 프록시는 HTTPS 요청과 응답을 로컬에서 가로채서 JSONL 로그 파일로 저장합니다.

주 용도는 아래와 같습니다.

1. 브라우저에서 성공하는 요청과 코드 요청 비교
2. ERP 로그인 흐름 분석
3. B2B 세션 초기화 문제 분석
4. Nexacro SSV 요청 형식 비교

## 관련 파일

프로젝트 루트 기준 관련 파일은 아래와 같습니다.

1. `lg_capture_proxy/`
2. `capture_proxy_build.ps1`
3. `capture_proxy_install_cert.ps1`
4. `capture_proxy_enable_proxy.ps1`
5. `capture_proxy_disable_proxy.ps1`

각 파일 역할:

1. `lg_capture_proxy/`
2. .NET 8 기반 캡처 프록시 본체
3. `capture_proxy_build.ps1`
4. 프록시 빌드
5. `capture_proxy_install_cert.ps1`
6. HTTPS 복호화를 위한 인증서 생성 및 설치
7. `capture_proxy_enable_proxy.ps1`
8. Windows 프록시 활성화
9. `capture_proxy_disable_proxy.ps1`
10. Windows 프록시 비활성화

## 준비 조건

사용 전 아래가 준비되어 있어야 합니다.

1. `dotnet` 실행 가능
2. PowerShell 실행 가능
3. 현재 프로젝트 루트에서 작업 중일 것

프로젝트 루트 예시:

`d:\OneDrive\Documents\프로젝트_LG가이드준비\excel`

## 가장 권장하는 사용 순서

아래 순서대로 진행하면 됩니다.

### 1. 프록시 빌드

```powershell
.\capture_proxy_build.ps1
```

PowerShell 실행 정책 오류가 나면 아래처럼 현재 세션만 우회할 수 있습니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

그 후 다시:

```powershell
.\capture_proxy_build.ps1
```

### 2. 인증서 설치

```powershell
.\capture_proxy_install_cert.ps1
```

이 단계는 HTTPS 복호화를 위해 필요합니다.

설치 후에는 브라우저를 완전히 종료했다가 다시 실행하는 것이 안전합니다.

### 3. 프록시 실행

```powershell
dotnet run --project .\lg_capture_proxy\LgCaptureProxy.csproj -c Release
```

이 창은 프록시 실행 상태로 유지해야 합니다.

### 4. Windows 프록시 활성화

다른 PowerShell 창을 새로 열어서 아래를 실행합니다.

```powershell
.\capture_proxy_enable_proxy.ps1
```

정상이라면 Windows 프록시가 `127.0.0.1:8877`로 설정됩니다.

### 5. 실제 브라우저 동작 수행

이제 IE 모드 또는 실제 사용하는 브라우저에서 아래 작업을 수행합니다.

1. `newbest.lge.com` 접속
2. 로그인
3. ERP 관련 화면 진입
4. 모델 조회 또는 재고 조회 또는 생산계획 조회 수행

### 6. 프록시 비활성화

캡처가 끝나면 아래 명령으로 Windows 프록시를 반드시 해제합니다.

```powershell
.\capture_proxy_disable_proxy.ps1
```

필요하면 프록시 실행 중이던 창도 종료합니다.

## 로그 파일 위치

기본 로그 파일은 아래 경로에 저장됩니다.

`lg_capture_proxy\bin\Release\net8.0\runtime_data\logs\capture-YYYYMMDD-HHMMSS.jsonl`

예:

`lg_capture_proxy\bin\Release\net8.0\runtime_data\logs\capture-20260316-004614.jsonl`

## 로그 내용

로그에는 일반적으로 아래 정보가 포함됩니다.

1. 요청 URL
2. 요청 헤더
3. 요청 본문
4. 응답 상태 코드
5. 응답 헤더
6. 응답 본문

이 정보로 아래 비교가 가능합니다.

1. 브라우저는 성공하는데 코드가 실패하는 요청 비교
2. 쿠키 차이 확인
3. SSV body 형식 차이 확인
4. 실제 호출되는 서비스 URL 확인

## 이 프록시로 실제로 해결했던 문제

이 프록시는 아래 문제를 해결하는 데 사용되었습니다.

1. `SessionNotFound`
2. B2B 세션 초기화 실패
3. `/b2b/cm/nexacro/login.do` 요청 형식 불일치
4. 내부 ERP `USER_ID` 확인
5. 재고 조회와 생산계획 조회 요청 파라미터 확인

즉, 브라우저 성공 요청과 코드 요청을 비교하는 데 핵심 역할을 했습니다.

## 주의사항

아래 내용은 꼭 알고 사용해야 합니다.

1. 이 프록시는 `newbest.lge.com` 트래픽 분석을 목표로 만들어졌습니다.
2. 로그인 정보, 쿠키, 응답 본문이 로그에 저장될 수 있습니다.
3. 로그 파일에는 민감한 정보가 포함될 수 있으므로 외부 공유 전에 반드시 확인해야 합니다.
4. 인증서 설치 후 브라우저를 재시작하지 않으면 HTTPS 복호화가 제대로 안 될 수 있습니다.
5. 작업이 끝난 뒤에는 프록시를 반드시 꺼야 합니다.

## 문제 발생 시 점검 순서

### 스크립트가 실행되지 않을 때

현재 세션에 한해서 실행 정책을 우회합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 스크립트가 없다고 나올 때

현재 폴더가 프로젝트 루트인지 확인합니다.

예:

```powershell
cd d:\OneDrive\Documents\프로젝트_LG가이드준비\excel
```

### HTTPS 캡처가 되지 않을 때

아래를 순서대로 확인합니다.

1. 인증서 설치 여부
2. 브라우저 완전 재시작 여부
3. 프록시 실행 중인지 여부
4. Windows 프록시가 활성화되었는지 여부

### 작업 후 인터넷이 이상할 때

Windows 프록시가 아직 켜져 있을 수 있습니다.

아래를 실행합니다.

```powershell
.\capture_proxy_disable_proxy.ps1
```

## 새 컴퓨터에서 사용할 때 권장 절차

다른 컴퓨터로 이동한 뒤에는 아래 순서를 권장합니다.

1. 프로젝트 루트 열기
2. 이 문서 읽기
3. `.\capture_proxy_build.ps1` 실행
4. `.\capture_proxy_install_cert.ps1` 실행
5. 프록시 실행
6. Windows 프록시 활성화
7. 브라우저에서 실제 ERP 동작 수행
8. 로그 파일 생성 확인
9. 작업 후 Windows 프록시 비활성화

## 한 줄 요약

이 프록시는 브라우저에서 성공하는 `newbest.lge.com` 요청을 잡아서, 코드와 비교 분석하기 위한 전용 도구입니다.
