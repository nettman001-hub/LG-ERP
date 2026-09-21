# 🏛️ 삼성 인가 PC 기반 독립 B2B 자동화 시스템 구축 기획서

> **문서 상태**: 2026-09-22 기획 확정판  
> **핵심 원칙**: LG 프로그램(`excel/`) 100% 완전 분리 & 삼성 정식 인가 PC 전용 독립 시스템 구축  
> **시각화 HTML**: [`삼성_인가PC_독립_B2B_시스템_구현계획.html`](./삼성_인가PC_독립_B2B_시스템_구현계획.html)

---

## 💡 1. 핵심 전제 조건: "왜 삼성 인가 PC 분리 구동이 최선의 선택인가?"

삼성전자 대리점 전산망은 금융권 수준의 **제로 트러스트(Zero Trust)** 보안 모델이 적용되어 있습니다.
- **백엔드**: 차세대 SAP S/4HANA (N-ERP)
- **보안 통제**: 단말기 MAC/UUID 인가 승인 + SingleID CIAM + nProtect/ASTx 보안 데몬 + WAF 봇 탐지

비인가 PC에서 헤드리스 브라우저(Selenium/Playwright)나 억지스러운 봇 접속을 시도하면 즉시 WAF와 보안 데몬에 의해 감지되어 대리점 계정 정지 위험이 발생합니다.

반면, 사용자님의 **"이미 본사의 정식 인가를 받은 다른 업무용 PC에서 LG와 분리하여 독립 구동한다"**는 결정은:
1. 단말기 인증(MAC/UUID)을 우회할 필요 없이 합법적·정상적으로 통과된 상태를 활용
2. 보안 프로그램과 마찰 없이 **공식 브라우저 세션과 본사 공식 대량 발주 엑셀 양식을 100% 활용**
3. 계정 정지 및 봇 차단 리스크를 원천 배제하는 가장 안전하고 스마트한 전략입니다.

---

## 🏛️ 2. 시스템 아키텍처 및 3대 전략 비교

```mermaid
flowchart TB
    subgraph TargetPC["삼성 인가 전용 PC (업무용 독립 PC)"]
        subgraph OfficialBrowser["정식 브라우저 (Edge / Chrome)"]
            Edge["공식 로그인<br/>• SingleID CIAM 로그인<br/>• 보안 프로그램(nProtect/ASTx) 정상 통과<br/>• WAF 단말 핑거프린팅 통과"]
        end

        subgraph SamsungApp["삼성 전용 독립 프로그램 (SamsungPriceEditor)"]
            direction TB
            UI["삼성 딥블루 테마 데스크톱 GUI"]
            PriceEngine["삼성 가이드 엑셀 가격표 & 할인율 계산기"]
            Danawa["다나와 최저가 실시간 비교"]
            BatchGenerator["삼성 B2B 공식 규격 대량 발주 엑셀 생성기"]
            SessionBridge["CDP 브라우저 세션 브리지 (옵션)"]
        end

        Edge <-->|세션 공유 (디버깅 포트)| SessionBridge
        UI --- PriceEngine & Danawa & BatchGenerator & SessionBridge
    end

    subgraph SamsungCloud["삼성전자 B2B 클라우드 (G-Net / N-ERP)"]
        Portal["삼성 B2B 파트너 포털"]
        SAP["SAP S/4HANA (ATP 실시간 재고)"]
        Portal <--> SAP
    end

    subgraph MobileWebhook["2차 인증(MFA) 파이프라인"]
        Phone["담당자 스마트폰 (SMS 수신)"]
        SmsApp["SmsWebhook 앱 (기존 자산 활용)"]
        Server["unione24.co.kr 중계 서버"]
        Phone --> SmsApp --> Server -.-> UI
    end

    BatchGenerator -.->|발주 엑셀 공식 업로드| Portal
```

### 📊 3대 연동 전략 심층 비교

| 구분 | [방안 A] 브라우저 세션 쉐어링 (CDP) | [방안 B] 엑셀 배치 업로드 (실무 최강 ⭐) | [방안 C] 완전 자동 GUI 매크로 |
| :--- | :--- | :--- | :--- |
| **작동 메커니즘** | 인가 PC 브라우저의 인증 토큰을 읽어 백그라운드 OData/REST API 직접 호출 | 가격표 할인율 조정 후 **삼성 B2B 포털 공식 대량 발주 엑셀** 자동 생성 | 마우스 클릭 및 가상 키보드 입력 자동화로 화면을 직접 조작 |
| **보안 안전성** | 매우 안전 (정식 세션 재사용) | **100% 안전 (본사 공식 기능 활용)** | 위험 (보안 데몬이 매크로로 감지) |
| **계정 정지 위험** | 없음 (정식 인가 단말기 트래픽) | **전혀 없음 (본사 권장 정식 프로세스)** | 있음 (비정상 입력 패턴 탐지 가능) |
| **실무 도입 난이도**| 중간 (포털 API 패킷 조사 필요) | **매우 쉬움 (양식 규격 매핑 즉시 사용)** | 어려움 (해상도 및 UI 변경 시 오류) |
| **최종 권장 결론** | **권장 (실시간 ATP 재고 조회용)** | **적극 권장 (주문/발주 실무 핵심 파이프라인)**| **비권장 (차단 리스크 원천 배제)** |

---

## 🧩 3. 삼성 전용 독립 프로그램 4대 핵심 모듈

1. **삼성 B2B 엑셀 대량 발주 엔진**:
   - 삼성 가이드 엑셀을 로드하여 카테고리별(TV, 냉장고, 시스템에어컨, 세탁기 등) 할인율 일괄 조정
   - **삼성 포털 공식 규격 대량 발주 엑셀(.xlsx)** 1초 만에 자동 생성
2. **브라우저 세션 브리지 (CDP)**:
   - 인가 PC의 Edge 브라우저 디버깅 포트(`localhost:9222`)를 통해 인증 토큰 무충돌 추출
   - 백그라운드 Keep-Alive 핑으로 자동 로그아웃 방지
3. **실시간 ATP(가용재고) 조회기**:
   - 모델 코드별 전국 물류센터(수원, 평택, 광주 등) 실시간 가용 재고 및 최단 출하 가능일 확인
4. **2차 인증(MFA) 원격 수신 체계**:
   - 기존 안드로이드 `SmsWebhook` + `unione24.co.kr` 파이프라인을 그대로 활용하여 스마트폰에 오는 6자리 인증번호를 PC 화면에 자동 전달

---

## 🗂️ 4. 독립 프로젝트 디렉토리 구조

LG 프로그램(`excel/`)은 단 1줄도 변경하지 않고 온전히 보존하며, 삼성 프로그램은 `samsung/` 디렉토리에 독립 구축됩니다.

```
프로젝트_LG가이드준비/
├── excel/                                <-- [기존 유지] LG B2B ERP & 가격표 프로그램 (100% 독립 보존)
├── 삼성_인가PC_독립_B2B_시스템_구현계획.html <-- [신규] 고가독성 시각화 HTML 대시보드
├── 삼성_인가PC_독립_B2B_시스템_구현계획.md   <-- [신규] 본 마크다운 기획 문서
└── samsung/                              <-- [신규 예정] 삼성 인가 PC 전용 독립 패키지
    ├── samsung_main.py                   # 삼성 딥블루 테마 데스크톱 대시보드
    ├── price_tables.py                   # 삼성 가이드 엑셀 파싱 & 할인율 엔진
    ├── batch_exporter.py                 # 삼성 B2B 포털 공식 규격 엑셀 발주서 생성기
    ├── session_bridge.py                 # 인가 브라우저 CDP 세션 연동 모듈
    ├── mfa_receiver.py                   # SMS/OTP 2차 인증 자동 수신 모듈
    └── build_samsung_exe.ps1             # 삼성 전용 단일 실행파일(SamsungPriceEditor.exe) 빌드
```

---

## 📝 5. 삼성 인가 PC 현장 사전 점검 체크리스트

1. **포털 실제 접속 주소(URL)**: Edge 브라우저 즐겨찾기에 등록된 주소 (예: `partner.samsung.com`, `b2b.samsung.com` 등)
2. **대량 발주 엑셀 양식 1부 확보**: 포털 주문 메뉴의 [대량 발주 엑셀 다운로드] 빈 양식 엑셀 파일
3. **로그인 2차 인증(MFA) 수단 확인**: SMS 문자, SingleID mOTP, 모바일 푸시 중 어떤 수단인지 확인
4. **Microsoft Edge 브라우저 구동 확인**: 디버깅 포트 옵션(`--remote-debugging-port=9222`) 실행 지원 여부

---

## 🚀 6. 향후 4단계 추진 로드맵

- **Phase 1 (현재)**: 기획 확정 및 인가 PC 현장 환경 자료 수집
- **Phase 2 (승인 시 착수)**: 삼성 독립 패키지 구축 및 대량 발주 엑셀 변환기 개발
- **Phase 3**: 삼성 딥블루 UI 제작 및 브라우저 세션 브리지 결합
- **Phase 4**: 단일 EXE 실행 파일 패키징(`SamsungPriceEditor.exe`) 및 인가 PC 현장 검증
