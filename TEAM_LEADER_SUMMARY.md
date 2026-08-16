# YÖNETİCİ ÖZETİ: OPENAGENT

**Hava Boşluklu (Air-Gapped) Windows Ortamları İçin Güvenli ve Denetlenebilir Runbook Otomasyon Ajanı**

---

**1. Problem ve Çözüm Dengesi**

* **Mevcut Durum:** Ar-Ge, aviyonik ve simülasyon ekiplerinin ihtiyaç duyduğu karmaşık, çok adımlı geliştirme ortamları (SDK, derleyiciler, özel konfigürasyonlar) değişken README/Runbook dokümanlarına dayanır. Bu süreçler BT Teknik Destek ekibine ciddi bir çağrı (ticket) yükü bindirmekte ve manuel müdahale hatalarına zemin hazırlamaktadır.
* **Çözüm (OpenAgent):** İnternete kapalı yerel ağda (Air-Gap) çalışan, verilen teknik yönergeyi analiz ederek adım adım PowerShell komutlarına dönüştüren, her adımı operatör onayına (`Human-in-the-Loop`) sunan ve tam denetim izi (Audit Trail) bırakan hafif bir istemci otomasyonudur.

---

**2. Sistem Mimarisi (Zero-Dependency Client)**

```
[ Merkezi Yerel Sunucu (LAN) ] ── (HTTP / JSON) ──► [ Hedef Kullanıcı Bilgisayarı ]
 • Ollama (qwen2.5-coder)                            • Sadece OpenAgent.exe (~15 MB)
 • Dış API / İnternet: %0                            • Python / Ollama / Paket Kurulumu: YOK

```

* **Hedef Sistem Hijyeni:** Kullanıcı veya test istasyonlarına Python, pip bağımlılıkları veya yerel model dosyaları yüklenmez. Tek bir derlenmiş `.exe` çalıştırılır ve işlem sonrası iz bırakmaz.
* **Merkezi Zekâ:** Model, kurum içi LAN sunucusunda izole barındırılır; veriler kurum dışına kesinlikle çıkmaz.

---

**3. Güvenlik ve Kurumsal Uyum Katmanları**

| Güvenlik Katmanı | Uygulanan Mekanizma | Sağlanan Kurumsal Güvence |
| --- | --- | --- |
| **Human-in-the-Loop** | Her komut öncesi `[E/H]` operatör onayı | Modelin kontrolsüz veya özerk aksiyon alması engellenir. |
| **Komut Kara Listesi** | Regex tabanlı filtreleme (`format`, `bcdedit`, `rmdir C:\`) | Yıkıcı ve tehlikeli sistem komutları çalışma anında bloke edilir. |
| **Denetim İzi (Audit)** | Zaman damgalı JSON loglama | Çalıştırılan her komut, operatör onayı ve çıktı SIEM uyumlu kaydedilir. |
| **Port Yönetimi** | `USBSTOR` ve GPO Registry manipülasyonu | Kurulum süresince kontrollü USB açma, işlem bitiminde otomatik kilitleme. |

---

**4. Operasyonel Kazanımlar**

* **Hata Düzeltme (Self-Healing):** Komut yürütme sırasında alınan `stderr` ve dönüş kodları modele geri beslenir. Model eksik ara adımları (klasör oluşturma, parametre düzeltme vb.) analiz edip akışı kendi kurtarır.
* **Zaman ve İş Gücü Tasarrufu:** 15–20 dakika süren manuel ortam hazırlıkları 1–2 dakikalık standart ve tekrarlanabilir bir sürece indirgenir.
* **Standartlaşma:** Farklı mühendislerin aynı ortamı kurarken yaşayacağı konfigürasyon sapmaları sıfırlanır.

---

**5. Mevcut Aşama ve Pilot Önerisi**

Projenin PoC (Kavram Kanıtı) aşaması izole sanal makinelerde başarıyla tamamlanmıştır. Sistem; **2 dakikalık canlı simülasyon ortamı kurulumu ve hata kurtarma demosu** ile test edilmeye hazırdır.
