# OpenAgent — Kullanım ve Kurulum Kılavuzu

Lokal LLM destekli, **hava boşluklu (air-gapped) Windows 10/11** ortamları için güvenli kurulum otomasyon ajanı.

Hedef bilgisayarlarda **Python, pip veya Ollama kurulumu gerekmez.** Tek dosya yeterlidir: `OpenAgent.exe`.

---

## İçindekiler

1. [Ne yapar?](#1-ne-yapar)
2. [Mimari](#2-mimari)
3. [İki rol: sunucu ve istemci](#3-iki-rol-sunucu-ve-istemci)
4. [Merkezi LLM sunucusunu hazırlama](#4-merkezi-llm-sunucusunu-hazırlama)
5. [OpenAgent.exe derleme](#5-openagentexe-derleme)
6. [Hedef bilgisayarda çalıştırma](#6-hedef-bilgisayarda-çalıştırma)
7. [Komut referansı](#7-komut-referansı)
8. [Tipik iş akışı (adım adım)](#8-tipik-iş-akışı-adım-adım)
9. [Onay ekranı (Human-in-the-Loop)](#9-onay-ekranı-human-in-the-loop)
10. [USB port yönetimi](#10-usb-port-yönetimi)
11. [Denetim logları](#11-denetim-logları)
12. [Geliştirme / kaynak koddan çalıştırma](#12-geliştirme--kaynak-koddan-çalıştırma)
13. [Sık karşılaşılan sorunlar](#13-sık-karşılaşılan-sorunlar)
14. [Güvenlik notları](#14-güvenlik-notları)
15. [Dizin yapısı](#15-dizin-yapısı)

---

## 1. Ne yapar?

OpenAgent, kurulum klasöründeki bir **README / Runbook** dosyasını okur ve:

1. Merkezi Ollama sunucusundaki modele (ör. `qwen2.5-coder:7b`) sorar: “Sıradaki adım ne?”
2. Önerilen PowerShell komutunu size Rich paneliyle gösterir
3. Siz **E (evet)** derseniz komutu çalıştırır; **H (hayır)** derseniz durur
4. Komut hata verirse hatayı modele geri gönderip düzeltme denemesi yapar (en fazla 20 adım)
5. Her adımı `audit_logs/` altına JSON olarak kaydeder

Ayrıca USB depolamayı **kilitleme / açma / durum sorgulama** araçlarını içerir.

---

## 2. Mimari

```
┌─────────────────────────────────────┐
│  Merkezi sunucu (LAN içinde)        │
│  - Ollama çalışır                   │
│  - Port: 11434                      │
│  - Model: qwen2.5-coder:7b (veya 14b)│
└──────────────────▲──────────────────┘
                   │ HTTP
                   │ --server http://192.168.x.x:11434
┌──────────────────┴──────────────────┐
│  Hedef Windows PC (air-gap istemci) │
│  - Sadece OpenAgent.exe           │
│  - Python / Ollama YOK              │
│  - UAC ile Yönetici olarak çalışır  │
│  - Kurulum README + installer’lar   │
└─────────────────────────────────────┘
```

| Bileşen | Nerede | Ne gerekir? |
|---------|--------|-------------|
| Ollama + model | Merkezi sunucu | Bir kez kurulur |
| `OpenAgent.exe` | Her hedef PC | Python gerekmez |
| Kurulum paketleri + README | Hedef PC (USB/disk) | Operatör sağlar |

---

## 3. İki rol: sunucu ve istemci

### A) Merkezi LLM sunucusu

- Ollama’nın kurulu ve çalışır olduğu bir makine
- Hedef PC’lerden **ağ üzerinden erişilebilir** olmalı (aynı LAN / intranet)
- Örnek adres: `http://192.168.1.50:11434`

### B) Hedef istemci (kurulum yapılacak PC)

- Yalnızca `OpenAgent.exe` kopyalanır
- UAC penceresi çıkar → Yönetici izni verilir
- `--server` ile merkezi sunucuya bağlanır

> **Not:** Geliştirme sırasında her şeyi tek makinede de çalıştırabilirsiniz (`--server http://localhost:11434`).

---

## 4. Merkezi LLM sunucusunu hazırlama

Bu adımlar **sadece sunucu makinesinde** yapılır (bir kez).

### 4.1 Ollama kurulumu

[https://ollama.com/download](https://ollama.com/download) adresinden Windows/Linux kurulumunu yapın.

### 4.2 Modeli indirin

```powershell
ollama pull qwen2.5-coder:7b
```

Daha güçlü alternatif:

```powershell
ollama pull qwen2.5-coder:14b
```

### 4.3 Servisi başlatın / uzak erişime açın

Varsayılan olarak Ollama `11434` portunda dinler:

```powershell
ollama serve
```

Uzak istemcilerin bağlanabilmesi için (Windows örneği — kalıcı ortam değişkeni):

```powershell
# Sistem ortam değişkeni (Yönetici PowerShell)
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "Machine")
```

Ardından Ollama servisini yeniden başlatın. Güvenlik duvarında **TCP 11434** portunu LAN için açın.

### 4.4 Sunucunun ayakta olduğunu doğrulayın

Sunucuda veya başka bir PC’den:

```powershell
curl http://192.168.1.50:11434/api/tags
```

Model listesi JSON olarak dönmeli.

---

## 5. OpenAgent.exe derleme

Derleme **geliştirme bilgisayarında** (Python kurulu Windows) yapılır. Çıkan `.exe` hedef PC’lere kopyalanır.

### 5.1 Tek komut (önerilen)

```powershell
cd airgap_installer_agent
.\build.bat
```

Script şunları yapar:

1. `.venv` oluşturur
2. `requirements.txt` + PyInstaller yükler
3. `OpenAgent.spec` ile derler
4. Çıktıyı `dist\OpenAgent.exe` olarak üretir

### 5.2 Manuel derleme

```powershell
cd airgap_installer_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install "pyinstaller>=6.0"
pyinstaller --noconfirm --clean OpenAgent.spec
```

### 5.3 Derleme çıktısı

| Dosya | Açıklama |
|-------|----------|
| `dist\OpenAgent.exe` | Tek dosya istemci (onefile + konsol + UAC admin) |

Exe özellikleri:

- `--onefile` — tek çalıştırılabilir
- `--console` — komut satırı penceresi açık
- `--uac-admin` — çalışınca Windows UAC (Yönetici) ister

---

## 6. Hedef bilgisayarda çalıştırma

### 6.1 Dosyaları hazırlayın

Örnek klasör:

```
C:\TestKurulum\
├── README.txt              ← ajanın okuyacağı runbook
├── VC_redist.x64.exe       ← örnek kurulum dosyası
└── setup.msi               ← örnek kurulum dosyası
```

`OpenAgent.exe`’yi istediğiniz yere koyun (ör. masaüstü veya kurulum klasörü).

### 6.2 Temel komut (merkezi sunucu)

**PowerShell veya CMD** (çift tıklayınca UAC çıkar; argüman vermek için terminal kullanın):

```powershell
cd C:\yol\OpenAgent_klasoru

.\OpenAgent.exe run `
  --readme "C:\TestKurulum\README.txt" `
  --dir "C:\TestKurulum" `
  --server http://192.168.1.50:11434
```

Tek satır:

```powershell
.\OpenAgent.exe run --readme "C:\TestKurulum\README.txt" --dir "C:\TestKurulum" --server http://192.168.1.50:11434
```

### 6.3 Yerel Ollama ile (geliştirme / test)

Sunucu aynı makinedeyse `--server` vermeniz gerekmez (varsayılan `http://localhost:11434`):

```powershell
.\OpenAgent.exe run --readme "C:\TestKurulum\README.txt" --dir "C:\TestKurulum"
```

### 6.4 Farklı model kullanmak

```powershell
.\OpenAgent.exe run --readme "C:\TestKurulum\README.txt" --server http://192.168.1.50:11434 --model qwen2.5-coder:14b
```

### 6.5 Onaysız çalışma (dikkatli)

```powershell
.\OpenAgent.exe run --readme "C:\TestKurulum\README.txt" --server http://192.168.1.50:11434 --auto-approve
```

> Üretimde `--auto-approve` önermiyoruz; her komutu gözden geçirin.

### 6.6 Başarılı başlangıçta ne görürsünüz?

1. UAC penceresi → **Evet**
2. Konsolda mavi panel: README yolu, çalışma dizini, sunucu, model
3. Her adımda LLM kararı + komut paneli
4. `[E/H]` onayı
5. stdout/stderr çıktıları
6. Bittiğinde yeşil “Tamamlandı” paneli ve denetim log yolu

---

## 7. Komut referansı

Program üç alt komut sunar: `run`, `usb`, `audit`.

### `run` — README ile kurulum otomasyonu

```text
OpenAgent.exe run [SEÇENEKLER]
```

| Seçenek | Kısa | Zorunlu | Varsayılan | Açıklama |
|---------|------|---------|------------|----------|
| `--readme` | `-r` | Evet | — | Runbook / README dosya yolu |
| `--dir` | `-d` | Hayır | README’nin klasörü | PowerShell çalışma dizini |
| `--server` | `-s` | Hayır | `http://localhost:11434` | Merkezi Ollama adresi |
| `--model` | `-m` | Hayır | `qwen2.5-coder:7b` | Model adı |
| `--auto-approve` | — | Hayır | kapalı | Onay sorularını atla |

Örnekler:

```powershell
.\OpenAgent.exe run -r "C:\TestKurulum\README.txt" -d "C:\TestKurulum" -s http://192.168.1.50:11434
.\OpenAgent.exe run -r "D:\Paket\RUNBOOK.md" -s http://10.0.0.20:11434 -m qwen2.5-coder:14b
```

### `usb` — USB depolama kontrolü

```text
OpenAgent.exe usb --action unlock|lock|status
```

| `--action` | Anlamı |
|------------|--------|
| `unlock` | USB depolamayı aç (politika anahtarlarını temizle, USBSTOR=3, gpupdate) |
| `lock` | USB depolamayı kilitle (Deny_All=1, USBSTOR=4, gpupdate) |
| `status` | Mevcut kilit durumunu tablo olarak göster |

```powershell
.\OpenAgent.exe usb --action unlock
.\OpenAgent.exe usb --action lock
.\OpenAgent.exe usb --action status
```

### `audit` — geçmiş oturumları listele

```powershell
.\OpenAgent.exe audit --list
```

Log dosyaları, exe’nin bulunduğu klasördeki `audit_logs\` altında oluşur.

### Yardım

```powershell
.\OpenAgent.exe --help
.\OpenAgent.exe run --help
.\OpenAgent.exe usb --help
.\OpenAgent.exe audit --help
```

---

## 8. Tipik iş akışı (adım adım)

### Senaryo: Kapalı ağda yazılım kurulumu

1. **Sunucu ekibi** merkezi makinede Ollama + modeli hazırlar, `11434` portunu açar.
2. **Derleme ekibi** `build.bat` ile `OpenAgent.exe` üretir.
3. **Operatör** hedef PC’ye şunları getirir (USB / iç ağ paylaşımı):
   - `OpenAgent.exe`
   - Kurulum klasörü (`README.txt` + installer dosyaları)
4. Operatör Yönetici olarak:

```powershell
.\OpenAgent.exe run --readme "C:\TestKurulum\README.txt" --dir "C:\TestKurulum" --server http://192.168.1.50:11434
```

5. Her önerilen komutta **E** / **H** ile onay verir.
6. Kurulum bitince `audit --list` ile kaydı kontrol eder.
7. Gerekiyorsa USB’yi tekrar kilitler:

```powershell
.\OpenAgent.exe usb --action lock
```

### Örnek README.txt (runbook)

`C:\TestKurulum\README.txt`:

```text
1. VC_redist.x64.exe dosyasını /quiet /norestart parametreleriyle sessiz kur.
2. setup.msi dosyasını msiexec /i setup.msi /qn /norestart ile kur.
3. "C:\Program Files\OrnekApp\app.exe" dosyasının varlığını doğrula.
4. Kurulum tamamlandıysa işlemi bitir.
```

Ajan bu metni okuyup sessiz kurulum bayraklarıyla (`/quiet`, `/qn`, `/VERYSILENT`, `/S` …) PowerShell komutları üretir.

---

## 9. Onay ekranı (Human-in-the-Loop)

Her tehlikeli / sistem komutundan önce benzer bir panel görürsünüz:

```text
┌── Onay Gerekli — run_powershell ──┐
│ Gerekçe: MSI sessiz kurulumu...   │
│ Durum: setup.msi kuruluyor        │
│ Komut:                            │
│ msiexec /i setup.msi /qn ...      │
└───────────────────────────────────┘
Bu komutu çalıştırmak istiyor musunuz? [e/h] (h):
```

| Tuş | Anlamı |
|-----|--------|
| `E` | Komutu çalıştır |
| `H` | Reddet ve oturumu sonlandır (varsayılan) |

`--auto-approve` verilirse panel sarı “OTOMATİK ONAY” olarak gösterilir ve soru sorulmaz.

Kara listeye takılan komutlar (ör. `format`, `diskpart`, `bcdedit`, kök silme) **hiç çalıştırılmaz**.

---

## 10. USB port yönetimi

Yönetici yetkisi gerekir (exe zaten UAC ister).

| İşlem | Komut |
|-------|--------|
| Aç | `.\OpenAgent.exe usb --action unlock` |
| Kilitle | `.\OpenAgent.exe usb --action lock` |
| Durum | `.\OpenAgent.exe usb --action status` |

Teknik olarak:

- `RemovableStorageDevices` politika anahtarları (HKLM / HKCU)
- `USBSTOR` servis `Start` değeri (`3` açık, `4` kapalı)
- `gpupdate /force`

---

## 11. Denetim logları

Her `run` oturumu için bir JSON dosyası:

```text
<OpenAgent.exe'nin klasörü>\audit_logs\audit_YYYYMMDD_HHMMSS.json
```

İçerik özeti:

- Başlangıç / bitiş zamanı
- README yolu, çalışma dizini, model, sunucu URL
- Her adım: `thought`, `command`, `user_approval`, `returncode`, `stdout`, `stderr`, süre

Listelemek:

```powershell
.\OpenAgent.exe audit --list
```

---

## 12. Geliştirme / kaynak koddan çalıştırma

Exe derlemeden Python ile test etmek için (geliştirme PC):

```powershell
cd airgap_installer_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Ollama'nın çalıştığından emin olun
ollama serve

python main.py run --readme "C:\TestKurulum\README.txt" --dir "C:\TestKurulum" --server http://localhost:11434
python main.py usb --action status
python main.py audit --list
```

`python main.py` ile `OpenAgent.exe` aynı CLI arayüzünü kullanır.

---

## 13. Sık karşılaşılan sorunlar

### “Merkezi LLM sunucusuna ulaşılamadı…”

Anlamı: Ollama’ya TCP bağlantısı kurulamadı.

Kontrol listesi:

1. Sunucuda `ollama serve` / servis ayakta mı?
2. IP doğru mu? (`--server http://DOĞRU_IP:11434`)
3. Port 11434 firewall’da açık mı?
4. `OLLAMA_HOST=0.0.0.0:11434` ayarlandı mı? (yalnız localhost dinliyorsa uzak bağlanamaz)
5. Hedef PC’den: `curl http://SUNUCU_IP:11434/api/tags`

### Model bulunamadı / LLM hatası

Sunucuda modeli çekin:

```powershell
ollama pull qwen2.5-coder:7b
ollama list
```

İstemcide aynı ismi kullanın: `--model qwen2.5-coder:7b`

### UAC çıkmıyor / yetki hatası

- Derlenmiş `OpenAgent.exe` kullanın (`uac-admin` gömülü)
- Kaynak koddan çalışıyorsanız terminali **Yönetici olarak çalıştır** ile açın

### Komutlar Türkçe karakter bozuluyor

Executor `cp857` → `utf-8` fallback kullanır. Hâlâ bozuksa PowerShell çıktısını denetim logundaki `stdout`/`stderr` alanından kontrol edin.

### Exe açılıp hemen kapanıyor

Argümansız çift tıklamada yardım gösterilip çıkabilir. Her zaman terminalden komut verin:

```powershell
.\OpenAgent.exe run --help
```

---

## 14. Güvenlik notları

1. Yalnızca **güvenilir** README/Runbook dosyalarıyla çalıştırın.
2. Her komutu okuyup onaylayın; `--auto-approve` üretimde varsayılan olmasın.
3. Kara liste ek bir katmandır; nihai sorumluluk operatördedir.
4. Merkezi Ollama’yı yalnızca güvenilir LAN’a açın; internete açık bırakmayın.
5. USB unlock sonrası iş bitince tekrar `lock` yapmayı unutmayın.
6. Denetim logları hassas komut çıktısı içerebilir; erişimini kısıtlayın.

---

## 15. Dizin yapısı

```
airgap_installer_agent/
├── main.py                 # CLI giriş noktası
├── config.py               # Model, sunucu, timeout, Registry yolları
├── OpenAgent.spec        # PyInstaller: onefile + console + UAC
├── build.bat               # Windows tek tık derleme
├── requirements.txt
├── README.md               # Bu kılavuz
├── core/
│   ├── agent.py            # ReAct döngüsü + self-healing
│   ├── executor.py         # PowerShell yürütme
│   ├── llm.py              # Sunucu bağlantısı / temiz hata
│   ├── security.py         # Kara liste + [E/H] onay + admin
│   └── logger.py           # JSON denetim izi
├── tools/
│   └── usb_manager.py      # USB lock / unlock / status
├── audit_logs/             # Çalışma zamanında dolar
└── dist/
    └── OpenAgent.exe     # Derleme çıktısı (hedef PC’ye giden dosya)
```

---

## Hızlı özet (cheat sheet)

```powershell
# --- SUNUCU ---
ollama pull qwen2.5-coder:7b
ollama serve

# --- DERLEME (geliştirme PC) ---
cd airgap_installer_agent
.\build.bat

# --- HEDEF PC ---
.\OpenAgent.exe run --readme "C:\TestKurulum\README.txt" --dir "C:\TestKurulum" --server http://192.168.1.50:11434
.\OpenAgent.exe usb --action status
.\OpenAgent.exe audit --list
```

Sorun yaşarsanız önce sunucu erişimini (`curl …/api/tags`), sonra `--server` IP’sini, ardından UAC/yönetici yetkisini kontrol edin.
