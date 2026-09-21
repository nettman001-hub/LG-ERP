# 개발 인수인계 문서

이 문서는 현재 프로젝트의 실제 상태를 기준으로 정리한 개발 인수인계 문서입니다.

예전 메모나 깨진 문서보다 이 문서를 우선해서 참고하세요.

## 프로젝트 요약

이 프로젝트는 엑셀 가격표 편집기이며, 현재 아래 기능들이 연결되어 있습니다.

1. 엑셀 가격표 열기 및 편집
2. 다나와 가격 비교
3. LG B2B ERP 로그인
4. ERP 모델 검색
5. ERP 재고 조회
6. ERP 생산계획 조회

현재 GUI에서는 다음 동작이 확인된 상태입니다.

1. ERP 로그인 가능
2. 선택한 한 행에 대해 ERP 단건 조회 가능
3. 결과 팝업에 아래 값 표시
4. 총 가용재고
5. 생산계획 주간 합계 `D00~D07`
6. 생산계획 전체 합계 `D00~D30`

## 중요한 파일

현재 기준으로 가장 중요한 파일은 아래와 같습니다.

1. `main.py`
2. `erp_client.py`
3. `test_ssv_parser.py`
4. `NEXT_AGENT_HANDOFF.md`
5. `CAPTURE_PROXY.md`

## 실제 동작 확인 상태

최신 세션 (2026-04-01)에서 사용자가 직접 아래 항목에 대해 정상 작동함을 테스트하고 확정지었습니다.

1. `python main.py` 실행 및 GUI 표시 정상
2. ERP 로그인 (OTP 포함) 정상 통과
3. 선택 엑셀 행을 기준으로 한 ERP 단건 모델 검색/재고 조회/생산계획 조회 정상 작동

사용자 확인 기준으로도 아래가 확인되었습니다.

1. 재고 값이 정상적으로 조회됨
2. 생산계획 값이 정상적으로 조회됨
3. `main.py`의 다나와 가격비교가 정상 동작함
4. 테이블 미리보기 창의 공급가/차액 표시가 정상 동작함
5. 카카오 챗봇 공급가가 엑셀 가격표 공급가 기준으로 정상 동작함

## ERP 연동 핵심 메모

가장 큰 장애물은 `SessionNotFound`였습니다.

원인은 단순히 포털 로그인만 성공한다고 해서 ERP B2B API 세션이 준비되는 것이 아니었기 때문입니다.

실제로 동작하는 요청 흐름은 아래와 같습니다.

1. `POST /cm/portal/login.do`
2. `POST /cm/portal/openMain.do`
3. `POST /b2b/NEWBEST/index.jsp`
4. `POST /b2b/cm/nexacro/login.do`
5. `POST /b2b/service/...`

중요한 포인트는 아래와 같습니다.

1. ERP 서비스 호출에는 내부 숫자형 `USER_ID`가 필요함
2. 이 값은 `OUT_COME_LOGIN_INFO.USER_ID`에서 파싱함
3. Nexacro SSV 포맷은 브라우저 요청과 거의 동일해야 함

특히 SSV 관련 핵심 규칙은 아래와 같습니다.

1. `RS = \x1E`
2. `US = \x1F`
3. dataset 헤더는 `_RowType_`
4. 타입 표기는 `STRING(256)`
5. dataset 사이에는 빈 record 하나가 들어감
6. 어떤 요청은 빈 문자열 `""`을 유지해야 함
7. 어떤 요청은 null 문자 `\x03`를 사용해야 함

## 현재 코드 구조

### `ERPSession`

주요 역할:

1. 포털 로그인
2. SMS OTP 인증
3. 포털 세션 유지
4. B2B 브리지 form 값 보관

중요 필드:

1. `b2b_bridge_form`
2. `internal_user_id`
3. `channel_code`
4. `inventory_wh_id`

### `ERPClient`

주요 역할:

1. B2B 세션 초기화
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

## GUI 상태

`main.py`에는 현재 아래 기능이 연결되어 있습니다.

1. ERP 로그인 버튼
2. 선택 행 ERP 개별 조회 버튼

선택 행 조회 흐름은 아래 순서입니다.

1. 단축 모델명으로 ERP 모델 검색
2. 후보가 여러 개면 선택 다이얼로그 표시
3. 선택된 full model 기준 재고 조회
4. 같은 model 기준 생산계획 조회
5. 결과 팝업 표시

현재 아직 끝나지 않은 부분은 아래입니다.

1. ERP 결과를 엑셀 시트에 다시 기록하는 기능
2. 시트 전체 모델 일괄 처리
3. 엑셀 테이블 결과 열 자동 추가

## 남은 TODO

우선순위가 높은 작업:

1. `write_erp_data_to_sheet()` 구현
2. 결과 열 자동 추가
3. 추천 열 이름:
4. `available_inventory`
5. `production_weekly`
6. `production_total`
7. 전체 모델 일괄 처리 흐름 GUI 연결
8. 조회 결과를 실제 시트에 기록

중간 우선순위 작업:

1. ERP 일괄 처리 진행률 표시
2. 모델별 에러 요약 개선
3. 최종 UX 정리

## 권장 다음 단계

사용자께서 로그인 연동 및 단건 검색기능까지 확실하게 검증하셨으므로, 다음 에이전트는 아래 순서로 시작하면 됩니다.

1. **(제일 먼저 여쭤보기)** 사용자께서 남기셨던 *"수정할것이 있다. 8"*의 내용의 의도나 지시사항을 여쭤보고 먼저 해결할 것!
2. `write_erp_data_to_sheet()` 본격 구현
3. 일괄 처리(여러개 검색) 버튼과 흐름 UI/로직 연동
4. 엑셀 표에 결과 열을 자동으로 생성 및 업데이트
5. 변경된 데이터를 실제 엑셀 파일 워크북으로 저장까지 완전 검증

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

## 참고 메모

1. 오래된 문서와 코드가 충돌하면 코드를 우선 신뢰하세요.
2. 인수인계 문서 기준으로는 `NEXT_AGENT_HANDOFF.md`와 이 문서를 먼저 보는 것이 좋습니다.
3. ERP 세션 관련 로직은 작은 차이에도 실패할 수 있으므로 쉽게 단순화하지 마세요.
4. 다나와 크롤링, 미리보기 차액/공급가, 카카오 챗봇 공급가 경로는 현재 정상 동작 기준선으로 간주하고 추정으로 수정하지 마세요.
