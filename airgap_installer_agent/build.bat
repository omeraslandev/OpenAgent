@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo  OpenAgent — PyInstaller derleme
echo  Cikti: dist\OpenAgent.exe
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python PATH uzerinde bulunamadi.
    echo        Derleme makinesinde Python 3.10+ kurulu olmali.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [*] Sanal ortam olusturuluyor...
    python -m venv .venv
    if errorlevel 1 (
        echo [HATA] venv olusturulamadi.
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [HATA] Sanal ortam etkinlestirilemedi.
    exit /b 1
)

echo [*] Bagimliliklar yukleniyor...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install "pyinstaller>=6.0"

if errorlevel 1 (
    echo [HATA] pip install basarisiz.
    exit /b 1
)

echo [*] Onceki build artiklari temizleniyor...
if exist "build" rmdir /s /q "build"
if exist "dist\OpenAgent.exe" del /f /q "dist\OpenAgent.exe"

echo [*] PyInstaller calisiyor (onefile + console + uac-admin)...
pyinstaller --noconfirm --clean OpenAgent.spec

if errorlevel 1 (
    echo.
    echo [HATA] PyInstaller derlemesi basarisiz.
    exit /b 1
)

if not exist "dist\OpenAgent.exe" (
    echo [HATA] dist\OpenAgent.exe olusmadi.
    exit /b 1
)

echo.
echo [OK] Derleme tamamlandi:
echo      %cd%\dist\OpenAgent.exe
echo.
echo Ornek kullanim:
echo   dist\OpenAgent.exe run --readme C:\TestKurulum\README.txt --server http://192.168.1.50:11434
echo   dist\OpenAgent.exe usb --action status
echo   dist\OpenAgent.exe audit --list
echo.
endlocal
exit /b 0
