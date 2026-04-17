const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');

const WINDOW_WIDTH = 290;
const WINDOW_HEIGHT_INITIAL = 160;

let mainWindow = null;

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

// Renderer sends its content height so the window can auto-fit
ipcMain.on('set-height', (_event, height) => {
  if (mainWindow) {
    const clamped = Math.max(80, Math.min(600, height));
    mainWindow.setSize(WINDOW_WIDTH, clamped);
  }
});
