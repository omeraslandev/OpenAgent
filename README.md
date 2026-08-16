# OpenAgent

Hava boşluklu Windows istemcileri için **Merkezi LLM (Ollama) + tek `.exe` istemci** kurulum otomasyonu.

## Şimdi nasıl çalıştırıyoruz?

### 1) Merkezi sunucuda (bir kez)

```powershell
ollama pull qwen2.5-coder:7b
ollama serve
# Uzak erişim için OLLAMA_HOST=0.0.0.0:11434 ve firewall TCP 11434
```

### 2) Exe üret (geliştirme PC)

```powershell
cd airgap_installer_agent
.\build.bat
# → dist\OpenAgent.exe
```

### 3) Hedef PC’de (Python/Ollama yok)

```powershell
.\OpenAgent.exe run --readme "C:\TestKurulum\README.txt" --dir "C:\TestKurulum" --server http://192.168.1.50:11434
```

Diğer komutlar:

```powershell
.\OpenAgent.exe usb --action unlock|lock|status
.\OpenAgent.exe audit --list
```

**Detaylı kılavuz:** [`airgap_installer_agent/README.md`](airgap_installer_agent/README.md)
