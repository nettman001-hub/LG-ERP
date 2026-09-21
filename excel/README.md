# 엑셀 가격표 할인율 조정기

윈도우에서 실행되는 간단한 GUI 프로그램입니다.

## 기능
- 엑셀 파일(`.xlsx`) 업로드
- **첫 번째 시트**에서 "가격표 테이블"을 자동으로 찾아 테이블별 할인율을 조정
- 할인율 변경 시 **공급가 자동 재계산** (공급가는 **10원 단위 버림**)
- 원하는 파일명으로 저장

## 실행(개발용)

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

## 배포(윈도우 exe)

```bash
python -m pip install pyinstaller
python -m PyInstaller --noconsole --onefile --name PriceTableEditor main.py
```

생성된 exe는 `dist\PriceTableEditor.exe` 입니다.

또는 PowerShell에서:

```powershell
.\build_exe.ps1
```

### 주의
- `.xlsx`만 지원합니다. (`.xls`는 변환 후 사용)
- 원본 파일은 그대로 두고, 저장 파일명으로 새 파일을 생성하는 방식입니다.

## 테이블 인식 규칙(현재)
- 첫 번째 시트에서 행을 훑으면서 헤더에 다음 컬럼명이 포함된 블록을 테이블로 인식합니다.
  - `모델명`, `출하가`, `공급가`, `할인율`
- 헤더 아래로 **빈 행이 나오기 전까지**를 해당 테이블의 데이터 범위로 봅니다.

> 실제 엑셀 양식에 따라 약간의 조정이 필요할 수 있습니다. (예: 헤더 명칭이 다르거나 병합셀/서식만 있는 빈 행 처리 등)

