@echo off
:: Yönetici yetkisi kontrolü
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Bu scripti YONETICI OLARAK calistirmalisin.
    pause
    exit /b
)

echo [1/4] Bilgisayar Yapilandirmasi (HKLM) erisimi engelleniyor...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices" /v "Deny_All" /t REG_DWORD /d 1 /f >nul 2>&1

echo [2/4] Kullanici Yapilandirmasi (HKCU) erisimi engelleniyor...
reg add "HKCU\Software\Policies\Microsoft\Windows\RemovableStorageDevices" /v "Deny_All" /t REG_DWORD /d 1 /f >nul 2>&1

echo [3/4] USBSTOR surucu servisi kapatiliyor (Start = 4)...
reg add "HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR" /v "Start" /t REG_DWORD /d 4 /f >nul 2>&1

echo [4/4] Ilkeler guncelleniyor...
gpupdate /force

echo.
echo Islem tamamlandi. USB depolama birimleri basariyla kilitlendi.
pause