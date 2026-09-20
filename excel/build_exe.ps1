$ErrorActionPreference = "Stop"

Write-Host "부트스트랩: 필요한 패키지 설치 중..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller Pillow

Write-Host "아이콘 변환 중..."
python convert_icon.py

Write-Host "실행 파일 빌드 중 (Splash Screen 포함)..."
python -m PyInstaller --clean main.spec

Write-Host ""
Write-Host "완료: dist\PriceTableEditor.exe"
