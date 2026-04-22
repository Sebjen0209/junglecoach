#!/usr/bin/env bash
# build-installer.sh — builds the JungleCoach Windows installer.
#
# Prerequisites:
#   - Python venv set up in backend/venv
#   - PyInstaller installed: pip install pyinstaller
#   - Node deps installed: cd overlay && npm install
#   - Icons exist: overlay/assets/icon.ico and overlay/assets/icon.icns
#
# Output: overlay/dist/JungleCoach-Setup-X.X.X.exe

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Step 1: Build Python backend with PyInstaller"
cd "$REPO_ROOT/backend"
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate
pip install pyinstaller --quiet
pyinstaller junglecoach.spec --clean --noconfirm
echo "    Backend built → backend/dist/junglecoach-backend/"

echo "==> Step 2: Build Electron installer with electron-builder"
cd "$REPO_ROOT/overlay"
npm install --silent
npm run build
echo "    Installer built → overlay/dist/"

echo ""
echo "Done. Installer is in overlay/dist/"
