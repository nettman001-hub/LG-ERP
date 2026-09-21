# 다음 에이전트 인수인계 문서

이 문서는 다른 컴퓨터에서 이 프로젝트를 이어받는 에이전트를 위한 최신 기준 문서입니다.

**최근 업데이트 (2026-04-01):** 사용자가 직접 터미널 환경에서 ERP 로그인, 재고 단건 조회, 생산계획 단건 조회의 정상 작동을 완료했습니다. 사용자께서 "수정할것이 있다. 8"이라고 메모를 남기셨으니 해당 내용파악부터 시작하여 엑셀 시트 자동 추가 및 일괄 작업 작업을 속행하시면 됩니다. 자세한 내역은 `SESSION_HANDOFF_2026-04-01.md`를 참고하세요.

현재 코드 상태, ERP 연동 방식, 남은 작업 순서를 한 번에 이해할 수 있도록 정리했습니다.

## 읽는 순서

프로젝트를 새로 이어받는 경우 아래 순서로 읽는 것이 가장 안전합니다.

1. `NEXT_AGENT_HANDOFF.md`
2. `DEV_HANDOFF.md`
3. `implementation_plan.md`
4. `erp_client.py`
5. `main.py`
6. 보류 기능 확인 필요 시 `KAKAO_BOT_IDEA.md`

## 프로젝트 목적

이 프로젝트는 엑셀 가격표 편집기이며, 현재 아래 기능을 포함합니다.

1. 엑셀 가격표 열기 및 수정
2. 다나와 가격 비교
3. LG B2B ERP 로그인
4. ERP 모델 검색
5. ERP 재고 조회
6. ERP 생산계획 조회

## 실제 동작 확인 상태

이전 작업 세션에서 아래 동작은 실제로 확인되었습니다.

1. `python main.py` 실행 가능
2. ERP SMS OTP 로그인 가능
3. ERP 모델 조회 가능
4. ERP 재고 조회 가능
5. ERP 생산계획 조회 가능

사용자 확인 기준으로도 아래가 확인되었습니다.

1. 재고 값 정상 조회
2. 생산계획 값 정상 조회
3. `main.py`의 다나와 최저가 크롤링은 정상 동작
4. 테이블 내용 미리보기 창에서 공급가/차액 표시 정상 동작
5. 카카오 챗봇 결과의 공급가는 열려 있는 엑셀 가격표의 공급가 기준으로 정상 동작

## 2026-03-20 추가 주의사항

이번 세션에서 확인된 중요한 사실:

1. `main.py`의 다나와 가격비교는 원래 잘 동작하고 있었다.
2. 미리보기 창의 공급가/차액 표시도 원래 잘 동작하고 있었다.
3. 카카오 챗봇의 공급가도 엑셀 가격표 공급가 기준으로 이미 맞춰져 있었다.
4. 따라서 다나와 크롤링, 미리보기, 카카오 공급가 로직은 증거 없이 추정으로 수정하지 말 것.
5. 실제 오류가 재현되기 전에는 `price_compare.py`, `main.py`, `inventory_queue.py`의 해당 경로를 손대지 말 것.

이번 세션에서 잠깐 들어갔던 추정성 수정은 모두 원복했다.

원복 완료 기준:

1. `price_compare.py`는 원래 방식대로 `bs4`를 직접 import한다.
2. `requirements.txt`에는 `PySide6`, `openpyxl`, `requests`만 남아 있다.
3. `main.spec`, `PriceTableEditor.spec`, `build_exe.ps1`에는 추가 hidden import 수정이 없다.

현재 GUI 동작은 아래와 같습니다.

1. 사용자 ERP 로그인
2. 시트에서 한 행 선택
3. 선택 행 ERP 단건 조회 실행
4. 앱이 full model 검색
5. 재고 조회 수행
6. 생산계획 조회 수행
7. 팝업에 결과 표시

현재 팝업에는 아래 값이 표시됩니다.

1. full model 명
2. 총 가용재고
3. 생산계획 주간 합계 `D00~D07`
4. 생산계획 전체 합계 `D00~D30`

## 핵심 파일

현재 기준 핵심 파일은 아래와 같습니다.

1. `main.py`
2. `erp_client.py`
3. `test_ssv_parser.py`
4. `DEV_HANDOFF.md`
5. `implementation_plan.md`
6. `CAPTURE_PROXY.md`
7. `lg_capture_proxy/Program.cs`

## 어려웠던 문제와 해결 방식

### 1. ERP 세션 문제

가장 큰 장애물은 `SessionNotFound`였습니다.

단순히 포털 로그인만 성공하는 것으로는 ERP B2B API 호출이 되지 않았습니다.

실제로 동작하는 브라우저 요청 흐름을 맞춰야 했고, 현재 구현된 정상 흐름은 아래와 같습니다.

1. `POST /cm/portal/login.do`
2. `POST /cm/portal/openMain.do`
3. `POST /b2b/NEWBEST/index.jsp`
4. `POST /b2b/cm/nexacro/login.do`
5. `POST /b2b/service/...`

이 흐름이 현재 `erp_client.py`에 반영되어 있습니다.

### 2. 내부 ERP User ID

사번 `E36401`만으로는 ERP 서비스 호출이 되지 않습니다.

ERP는 내부 숫자형 `USER_ID`를 요구하며, 현재 코드는 아래 위치에서 이를 파싱합니다.

1. `OUT_COME_LOGIN_INFO.USER_ID`

이 부분을 사번 기반 추측 로직으로 되돌리면 다시 실패할 가능성이 큽니다.

### 3. Nexacro SSV 포맷

요청 body가 브라우저와 조금만 달라도 ERP가 실패했습니다.

현재 맞춰진 핵심 규칙은 아래와 같습니다.

1. `RS = \x1E`
2. `US = \x1F`
3. dataset 헤더는 `_RowType_`
4. 타입 표기는 `STRING(256)`
5. dataset 사이에는 빈 record가 들어감
6. 어떤 요청은 빈 문자열 `""` 유지
7. 어떤 요청은 null 문자 `\x03` 사용

이 부분은 매우 민감하므로 충분한 검증 없이 단순화하면 안 됩니다.

### 4. B2B Nexacro 로그인 특이사항

`/b2b/cm/nexacro/login.do`는 일반 서비스 호출과 다르게 다뤄야 했습니다.

현재 반영된 핵심 규칙:

1. SSV 변수에는 `JSESSIONID=`만 포함
2. `L-VISITOR`, `SCOUTER`, `LENA-UID`는 SSV 변수에 넣지 않음
3. 대신 HTTP `Cookie` 헤더에는 포함
4. `IN_PSET`, `RQSTDT` dataset 구조를 브라우저 요청과 맞춤

## 현재 코드 구조

### `ERPSession`

역할:

1. 포털 로그인
2. SMS OTP 인증
3. `requests.Session` 유지
4. B2B 브리지 form 값 저장

중요 필드:

1. `b2b_bridge_form`
2. `internal_user_id`
3. `channel_code`
4. `inventory_wh_id`

### `ERPClient`

역할:

1. B2B 세션 활성화
2. Nexacro 로그인
3. 모델 검색
4. 재고 조회
5. 생산계획 조회

중요 메서드:

1. `_ensure_b2b_session()`
2. `_bootstrap_b2b_login()`
3. `_call_b2b_service()`
4. `query_full_model()`
5. `query_inventory()`
6. `query_production_plan()`
7. `process_models()`

## 현재 완료된 작업

완료된 항목:

1. ERP 로그인
2. OTP 인증
3. B2B 세션 초기화
4. full model 조회
5. 재고 조회
6. 생산계획 조회
7. GUI 단건 조회 팝업 연결
8. 동작 중인 SSV 포맷 기준 테스트 정리

## 아직 남은 작업

우선순위가 높은 남은 작업:

1. `write_erp_data_to_sheet()` 구현
2. 엑셀 결과 열 자동 추가
3. GUI 일괄 ERP 처리 연결
4. ERP 결과를 워크북에 기록

권장 결과 열 이름:

1. `available_inventory`
2. `production_weekly`
3. `production_total`

낮은 우선순위 작업:

1. 일괄 처리 진행률 다이얼로그
2. 모델별 에러 요약
3. 장시간 작업 UX 개선

보류 메모:

1. 카카오톡 단체방에서 ERP 조회를 트리거하는 로컬 봇 아이디어가 있음
2. 아직 구현하지 않았고 상세 구상은 `KAKAO_BOT_IDEA.md`에 정리
3. 공식 API가 아니라 PC 카카오톡 UI 자동화 방식이 유력함

## 권장 다음 단계

새 컴퓨터에서 가장 안전한 진행 순서는 아래와 같습니다.

1. 단건 조회가 그대로 동작하는지 먼저 확인
2. `main.py`에서 다나와 가격비교 버튼이 실제로 값/차액/링크를 정상 반영하는지 확인
3. 테이블 미리보기 창에서 공급가/차액 표시가 유지되는지 확인
4. 카카오 큐 처리에서 공급가가 엑셀 공급가 기준으로 들어가는지 확인
5. 위 3개가 깨지지 않았을 때만 다른 기능 수정 시작
6. `write_erp_data_to_sheet()` 구현
7. 결과 열 자동 추가 기능 구현
8. 일괄 처리 GUI 흐름 연결
9. 실제 워크북으로 저장까지 검증

## 실행 명령

앱 실행:

```powershell
& "C:\Users\PC\AppData\Local\Python\pythoncore-3.14-64\python.exe" main.py
```

테스트 실행:

```powershell
& "C:\Users\PC\AppData\Local\Python\pythoncore-3.14-64\python.exe" test_ssv_parser.py
```

문법 확인:

```powershell
& "C:\Users\PC\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m py_compile main.py erp_client.py test_ssv_parser.py
```

환경에 따라 `python`이 PATH에 잡혀 있으면 `python main.py`도 동작할 수 있습니다.

## 캡처 프록시 메모

`newbest.lge.com` 트래픽 분석용 전용 HTTPS 캡처 프록시가 들어 있습니다.

관련 파일:

1. `lg_capture_proxy/Program.cs`
2. `capture_proxy_build.ps1`
3. `capture_proxy_install_cert.ps1`
4. `capture_proxy_enable_proxy.ps1`
5. `capture_proxy_disable_proxy.ps1`
6. `CAPTURE_PROXY.md`

이 도구는 브라우저 성공 요청과 코드 요청을 비교하는 데 사용되었습니다.

## 신뢰 기준

현재 기준으로 신뢰해도 되는 대상은 아래와 같습니다.

1. `NEXT_AGENT_HANDOFF.md`
2. `DEV_HANDOFF.md`
3. `implementation_plan.md`
4. `erp_client.py`
5. `main.py`의 다나와 가격비교/미리보기 경로
6. `inventory_queue.py`의 엑셀 공급가 우선 경로
5. `main.py`
6. `test_ssv_parser.py`

문서와 코드가 충돌하면 코드를 우선 신뢰하세요.

## 다음 에이전트가 가장 먼저 해야 할 일

이전 작업지시에서 요청했던 세 가지 안정성 검사 즉,
1. ERP 로그인 작동
2. 단건 재고 조회
3. 단건 생산계획 조회
위 기능들은 **사용자님께서 직접 실행하여 모두 정상 작동함을 2026-04-01 기준으로 확인**해 주셨습니다. 

따라서 다음 에이전트가 오면 **바로 아래 두 가지를 진행**해야 합니다.

1. 사용자님께 **"이전 자리에서 말씀해주셨던 '수정할것이 있다. 8'이 어떤 부분인가요?"** 라고 여쭤보고, 그 수정사항을 먼저 처리할 것.
2. 위 내용이 해결/파악되면 곧바로 `write_erp_data_to_sheet()` 구현과 엑셀 일괄 업데이트 GUI를 만드는 작업을 속행할 것.
