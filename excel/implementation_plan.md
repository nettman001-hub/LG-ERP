# 구현 계획서

이 문서는 현재 실제 프로젝트 상태를 기준으로 다시 정리한 구현 계획서입니다.

예전 계획이나 깨진 메모가 아니라, 지금 코드가 어디까지 구현되어 있는지를 기준으로 작성했습니다.

## 목표

LG B2B ERP 데이터를 엑셀 가격표 편집기에 연결해서 사용자가 아래 작업을 할 수 있도록 하는 것입니다.

1. ERP 로그인
2. 모델 상세 검색
3. 재고 조회
4. 생산계획 조회
5. 조회 결과를 엑셀에 기록

## 현재 완료된 작업

### 1. ERP 로그인

완료되었습니다.

`erp_client.py`에 아래가 구현되어 있습니다.

1. 포털 로그인
2. SMS OTP 인증
3. `requests.Session` 기반 세션 유지
4. B2B 브리지 form 파싱

### 2. B2B 세션 초기화

완료되었습니다.

현재 정상 동작하는 요청 흐름은 아래와 같습니다.

1. `POST /cm/portal/login.do`
2. `POST /cm/portal/openMain.do`
3. `POST /b2b/NEWBEST/index.jsp`
4. `POST /b2b/cm/nexacro/login.do`
5. `/b2b/service/...` 하위 서비스 호출

### 3. ERP 모델 검색

완료되었습니다.

메서드:

1. `ERPClient.query_full_model(short_model)`

사용 서비스:

1. `BRS_XPMMM_RetrieveEtcModelList`

### 4. ERP 재고 조회

완료되었습니다.

메서드:

1. `ERPClient.query_inventory(full_model)`

사용 서비스:

1. `BRS_XPMMM_RetrieveLgeQty`

### 5. ERP 생산계획 조회

완료되었습니다.

메서드:

1. `ERPClient.query_production_plan(full_model)`

사용 서비스:

1. `BRS_XPMMM_RetrieveLgeProdPlanHeader`
2. `BRS_XPMMM_RetrieveLgeProdPlanDtl`

적용 규칙:

1. `GUBUN == "Available Qty"` 행 사용
2. 주간 합계는 `D00~D07`
3. 전체 합계는 `D00~D30`

### 6. GUI 단건 ERP 조회

완료되었습니다.

현재 GUI 동작은 아래와 같습니다.

1. 사용자가 한 행 선택
2. 앱이 full ERP model 조회
3. 재고 조회
4. 생산계획 조회
5. 팝업으로 결과 표시

## 남은 작업

### A. 엑셀 시트 반영

아직 미완료입니다.

필요한 작업:

1. `write_erp_data_to_sheet()` 구현
2. 결과 열이 없으면 자동 생성
3. 매칭된 행에 ERP 결과 기록

권장 결과 열 이름:

1. `available_inventory`
2. `production_weekly`
3. `production_total`

### B. 전체 ERP 일괄 처리

부분적으로만 준비되어 있습니다.

`ERPClient.process_models()`는 존재하지만, 전체 GUI 흐름과 완전히 연결되지는 않았습니다.

필요한 작업:

1. 현재 시트에서 모든 모델 수집
2. 진행률 UI와 함께 순차 처리
3. 처리 결과를 다시 엑셀에 기록

### C. GUI 버튼 흐름

아직 추가 작업이 필요합니다.

1. 실제 일괄 조회 버튼 연결
2. 진행률 다이얼로그 추가
3. 최종 성공 및 실패 요약 표시

## 중요한 기술 규칙

### Nexacro SSV 포맷

브라우저 요청과 최대한 동일하게 유지해야 합니다.

중요 규칙:

1. `RS = \x1E`
2. `US = \x1F`
3. dataset 헤더는 `_RowType_`
4. 타입 표기는 `STRING(256)`
5. dataset 사이에는 빈 record가 하나 들어감

### 빈 문자열과 null 문자 구분

이 부분은 실제 동작에 영향을 줍니다.

1. 어떤 요청은 실제 빈 문자열 `""`을 요구함
2. 어떤 요청은 null 문자 `\x03`를 요구함

이 로직은 ERP 재검증 없이 단순화하면 안 됩니다.

### 내부 User ID

ERP 서비스 호출에는 내부 숫자형 `USER_ID`가 필요합니다.

출처:

1. `OUT_COME_LOGIN_INFO.USER_ID`

사번만으로 처리하려고 하면 실패할 수 있습니다.

## 다음 수정 대상 파일

다음 단계에서 가장 많이 수정할 가능성이 높은 파일은 아래와 같습니다.

1. `erp_client.py`
2. `main.py`
3. 구현 방식에 따라 `excel_price_tables.py`

## 권장 구현 순서

1. 단건 ERP 조회가 새 컴퓨터에서도 정상인지 확인
2. `write_erp_data_to_sheet()` 구현
3. GUI 일괄 처리 흐름 연결
4. 엑셀 결과 열 자동 추가
5. 저장까지 포함한 실제 워크북 검증

## 검증 방법

앱 실행:

```powershell
& "C:\Users\PC\AppData\Local\Python\pythoncore-3.14-64\python.exe" main.py
```

파서 테스트:

```powershell
& "C:\Users\PC\AppData\Local\Python\pythoncore-3.14-64\python.exe" test_ssv_parser.py
```

문법 확인:

```powershell
& "C:\Users\PC\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m py_compile main.py erp_client.py test_ssv_parser.py
```

수동 ERP 검증:

1. 앱 실행
2. ERP 로그인
3. 한 행 선택
4. 단건 ERP 조회 실행
5. 팝업에서 아래 확인
6. 재고 값
7. 생산계획 주간 합계
8. 생산계획 전체 합계

## 완료 기준

ERP 연동 작업이 최종 완료되었다고 볼 수 있는 조건은 아래와 같습니다.

1. 단건 조회 정상 동작
2. 일괄 조회 정상 동작
3. 결과 열 자동 추가
4. 정확한 행에 값 기록
5. 워크북 저장까지 정상 동작
