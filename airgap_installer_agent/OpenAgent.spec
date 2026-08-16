# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — OpenAgent.exe (onefile + console + UAC admin).

Derleme: build.bat  veya  pyinstaller --noconfirm OpenAgent.spec
"""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

hidden_imports = [
    # Uygulama
    "config",
    "core",
    "core.agent",
    "core.executor",
    "core.logger",
    "core.llm",
    "core.security",
    "tools",
    "tools.usb_manager",
    # Rich
    "rich",
    "rich.console",
    "rich.panel",
    "rich.prompt",
    "rich.table",
    "rich.status",
    "rich.text",
    "rich.markup",
    "rich.box",
    "rich.style",
    "rich.theme",
    "rich._win32_console",
    # Pydantic
    "pydantic",
    "pydantic.fields",
    "pydantic_core",
    "annotated_types",
    # Ollama / HTTP
    "ollama",
    "httpx",
    "httpcore",
    "anyio",
    "anyio._backends._asyncio",
    "sniffio",
    "h11",
    "certifi",
    "idna",
    # Typer / Click
    "typer",
    "typer.main",
    "click",
    "shellingham",
    "markdown_it",
    "mdurl",
    "pygments",
    "typing_extensions",
    "typing_inspection",
]

extra_datas = []
extra_binaries = []

for pkg in ("rich", "pydantic", "pydantic_core", "ollama", "httpx", "typer", "certifi"):
    try:
        datas, binaries, hidden = collect_all(pkg)
        extra_datas += datas
        extra_binaries += binaries
        hidden_imports += hidden
    except Exception:
        pass

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="OpenAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,       # konsol penceresi açık
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,     # requireAdministrator — UAC tetikler
    uac_uiaccess=False,
)
