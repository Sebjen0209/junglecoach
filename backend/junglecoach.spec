# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the JungleCoach local backend.
#
# Build from the backend/ directory:
#   cd backend
#   pyinstaller junglecoach.spec
#
# Output: backend/dist/junglecoach-backend/
# The entire dist/junglecoach-backend/ folder is then bundled into the
# Electron installer via electron-builder's extraResources config.

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Static data files needed at runtime.
        # junglecoach.db is NOT bundled — it is downloaded from the cloud API
        # on first launch by data/updater.py.
        ("data/champions.json",   "data"),
        ("data/power_spikes.json", "data"),
    ],
    hiddenimports=[
        # uvicorn resolves these dynamically — PyInstaller misses them.
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # FastAPI / Starlette internals
        "starlette.routing",
        "starlette.middleware.cors",
        # pydantic-settings reads .env files via a plugin
        "pydantic_settings",
        # anyio backend
        "anyio",
        "anyio._backends._asyncio",
        # httpx (Riot Live Client API + cloud API call)
        "httpx",
        # Riot API wrapper
        "riotwatcher",
        # Process detection (lol_phase.py)
        "psutil",
        # python-dotenv
        "dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy packages that aren't used in production.
    excludes=[
        "anthropic",   # moved to Railway — not needed locally
        "winocr",      # legacy OCR path — not used
        "PIL",         # same
        "pytest",
        "black",
        "ruff",
        "tkinter",
        "matplotlib",
        "numpy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="junglecoach-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # No console window — runs silently in the background.
    # Logs go to the file configured in main.py.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Set to "assets/icon.ico" once the icon exists
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="junglecoach-backend",
)
