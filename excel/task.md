# ERP API 통합 작업 목록

이 문서는 현재 실제 코드 상태를 기준으로 다시 정리한 작업 체크리스트입니다.

## 1. ERP 클라이언트 기본 구조

- [x] `erp_client.py` 생성
- [x] SSV 파서 구현
- [x] SSV 요청 body 생성 로직 구현
- [x] `ERPSession` 클래스 구성
- [x] `ERPClient` 클래스 구성

## 2. ERP 로그인 및 세션 처리

- [x] 포털 로그인 구현
- [x] SMS OTP 인증 구현
- [x] 포털 세션 유지 구현
- [x] B2B 브리지 form 파싱 구현
- [x] B2B 세션 초기화 구현
- [x] `/b2b/cm/nexacro/login.do` 연동 구현
- [x] 내부 ERP `USER_ID` 파싱 구현

## 3. ERP 조회 기능

- [x] 단축 모델명 기준 full model 검색 구현
- [x] 재고 조회 구현
- [x] 생산계획 조회 구현
- [x] 생산계획 `Available Qty` 기준 합산 로직 구현
- [x] 주간 합계 `D00~D07` 계산 구현
- [x] 전체 합계 `D00~D30` 계산 구현

## 4. 테스트 및 검증

- [x] `test_ssv_parser.py` 생성
- [x] 기본 파싱 테스트 작성
- [x] 빈 문자열 및 null 문자 처리 테스트 작성
- [x] dataset 분리 형식 테스트 작성
- [x] `py_compile` 기준 문법 검증
- [x] 실제 ERP 로그인/재고/생산계획 조회 동작 확인

## 5. GUI 통합 (`main.py`)

- [x] ERP 로그인 UI 연결
- [x] 선택 행 ERP 단건 조회 버튼 연결
- [x] 모델 검색 -> 재고 조회 -> 생산계획 조회 흐름 연결
- [x] 단건 조회 결과 팝업 표시
- [x] 생산계획 팝업 한글 깨짐 수정
- [ ] 전체 모델 일괄 조회 버튼 완성
- [ ] 진행률 다이얼로그 추가
- [ ] 일괄 처리 결과 요약 표시

## 6. 엑셀 연동

- [ ] `write_erp_data_to_sheet()` 구현
- [ ] 결과 열 자동 추가
- [ ] 권장 열 이름:
- [ ] `available_inventory`
- [ ] `production_weekly`
- [ ] `production_total`
- [ ] 조회 결과를 정확한 행에 기록
- [ ] 저장 후 다시 열어서 값 검증

## 7. 문서 정리

- [x] `DEV_HANDOFF.md` 현재 상태 기준으로 갱신
- [x] `implementation_plan.md` 현재 상태 기준으로 갱신
- [x] `NEXT_AGENT_HANDOFF.md` 신규 작성 및 정리
- [ ] `CAPTURE_PROXY.md` 최종 사용 흐름 기준으로 추가 정리

## 8. 다음 우선 작업

우선순위 순서:

- [ ] 단건 조회가 새 환경에서도 동일하게 동작하는지 재확인
- [ ] `write_erp_data_to_sheet()` 구현
- [ ] 엑셀 결과 열 자동 추가 구현
- [ ] 전체 모델 일괄 처리 GUI 연결
- [ ] 실제 워크북 기준 저장까지 검증

## 9. 보류 아이디어

- [ ] 카카오톡 단체방 ERP 조회 봇 검토
- [ ] 상세 메모는 `KAKAO_BOT_IDEA.md` 참고

## 10. OTP 자동화

- [x] `otp_upload.php` 초안 작성
- [x] `otp_latest.php` 초안 작성
- [x] `otp_delete.php` 초안 작성
- [x] 서버 업로드 및 기본 응답 확인
- [ ] Android 알림 앱 구현 시작
- [ ] Android 앱에서 OTP 업로드 테스트
## 11. 세션 관리 및 유지 보완

- [x] `main.py` 15분 주기 keep-alive 타이머 구현 확인
- [x] `erp_client.py` API 호출 시 활동 시간(`touch_activity`) 자동 갱신 로직 추가
- [x] 세션 유지 실패 시 UI 경고 표시 및 카운트다운 로직 검증
- [x] 최신 로직 반영 프로그램 재빌드 완료
