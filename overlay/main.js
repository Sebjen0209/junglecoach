const { app, BrowserWindow, ipcMain, screen, safeStorage } = require('electron');
const path = require('path');
const fs = require('fs');

const WINDOW_WIDTH = 290;
const WINDOW_HEIGHT_INITIAL = 160;

let mainWindow = null;

function getTokenPath() {
  return path.join(app.getPath('userData'), 'session.enc');
}

function createWindow() {
  const { width } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT_INITIAL,
    x: width - WINDOW_WIDTH - 20,
    y: 20,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: false,
    minimizable: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Stay on top even over fullscreen LoL window
  mainWindow.setAlwaysOnTop(true, 'screen-saver');
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  if (process.argv.includes('--dev-tools')) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});

app.on('activate', () => {
  if (mainWindow === null) createWindow();
});

// ── IPC handlers ────────────────────────────────────────────

ipcMain.on('close-window', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.on('minimize-window', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('set-height', (_event, height) => {
  if (mainWindow) {
    const clamped = Math.max(80, Math.min(600, height));
    mainWindow.setSize(WINDOW_WIDTH, clamped);
  }
});

// ── Token storage (encrypted via OS keychain) ────────────────

ipcMain.handle('get-token', () => {
  try {
    const tokenPath = getTokenPath();
    if (!fs.existsSync(tokenPath)) return null;
    const encrypted = fs.readFileSync(tokenPath);
    return safeStorage.decryptString(encrypted);
  } catch {
    return null;
  }
});

ipcMain.handle('save-token', (_event, token) => {
  try {
    const encrypted = safeStorage.encryptString(token);
    fs.writeFileSync(getTokenPath(), encrypted);
    return true;
  } catch {
    return false;
  }
});

ipcMain.handle('clear-token', () => {
  try {
    const tokenPath = getTokenPath();
    if (fs.existsSync(tokenPath)) fs.unlinkSync(tokenPath);
    return true;
  } catch {
    return false;
  }
});
