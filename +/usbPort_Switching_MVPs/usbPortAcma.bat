@echo off
:: Yönetici yetkisi kontrolü
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Bu scripti YONETICI OLARAK calistirmalisin.
    pause
    exit /b
)

echo [1/4] Bilgisayar Yapilandirmasi (HKLM) USB ilkeleri sifirlaniyor...
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices" /f >nul 2>&1

echo [2/4] Kullanici Yapilandirmasi (HKCU) USB ilkeleri sifirlaniyor...
reg delete "HKCU\Software\Policies\Microsoft\Windows\RemovableStorageDevices" /f >nul 2>&1

echo [3/4] USBSTOR surucu servisi aktif ediliyor (Start = 3)...
reg add "HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR" /v "Start" /t REG_DWORD /d 3 /f >nul 2>&1

echo [4/4] Ilkeler guncelleniyor...
gpupdate /force

echo.
echo Islem tamamlandi. USB portlari basariyla erisime acildi.
pause