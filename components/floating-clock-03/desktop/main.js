const { app, BrowserWindow, ipcMain, Menu, Tray, nativeImage, dialog, screen } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const { execFile } = require('node:child_process');
const { mergePreferences, recoverBounds } = require('./state-utils');

const DEFAULT_BOUNDS = { width: 320, height: 112, x: 40, y: 40 };
const MIN_MASTER_SCALE = 0.40;
const MAX_MASTER_SCALE = 2;
const DEFAULTS = {
  format: '12', background: 'glass', shape: 'rounded', opacity: 1,
  clockSize: 46, dateSize: 14,
  clockColor: '#F5FFF9', dateColor: '#C9D4DE',
  clockFont: 'Segoe UI', dateFont: 'Segoe UI',
  clockOutlineEnabled: true, clockOutlineColor: '#17212B', clockOutlineWidth: 1,
  dateOutlineEnabled: true, dateOutlineColor: '#17212B', dateOutlineWidth: 1,
  solidColor: '#17212B', gradientPreset: 'aurora',
  clockSurface: 'glass', dateSurface: 'none',
  clockSurfaceColor: '#142235', dateSurfaceColor: '#142235',
  clockTextEffect: 'embossed', dateTextEffect: 'soft', panelDepth: 'floating',
  wallpaperPath: null,
  masterScale: 1, timeDateGap: 12,
  windowWidth: DEFAULT_BOUNDS.width, windowHeight: DEFAULT_BOUNDS.height,
  x: DEFAULT_BOUNDS.x, y: DEFAULT_BOUNDS.y
};

let clockWindow = null;
let settingsWindow = null;
let tray = null;
let dragState = null;
let positionSaveTimer = null;
let expectedClockSize = { width: DEFAULT_BOUNDS.width, height: DEFAULT_BOUNDS.height };
let applyingMasterSize = false;

function preferenceFile() { return path.join(app.getPath('userData'), 'preferences.json'); }
function getPreferences() {
  try {
    if (fs.existsSync(preferenceFile())) {
      const stored = JSON.parse(fs.readFileSync(preferenceFile(), 'utf8'));
      return mergePreferences(DEFAULTS, stored);
    }
  } catch (error) { console.error('Could not read preferences:', error); }
  return { ...DEFAULTS };
}
function savePreferences(patch) {
  const next = { ...getPreferences(), ...patch };
  try {
    fs.mkdirSync(path.dirname(preferenceFile()), { recursive: true });
    fs.writeFileSync(preferenceFile(), JSON.stringify(next, null, 2));
  } catch (error) { console.error('Could not save preferences:', error); }
  return next;
}
function withWallpaperUrl(prefs = getPreferences()) {
  return {
    ...prefs,
    wallpaperUrl: prefs.wallpaperPath && fs.existsSync(prefs.wallpaperPath)
      ? pathToFileURL(prefs.wallpaperPath).href : null
  };
}
function broadcastPreferences() {
  const prefs = withWallpaperUrl();
  if (clockWindow && !clockWindow.isDestroyed()) clockWindow.webContents.send('clock:preferences-updated', prefs);
  if (settingsWindow && !settingsWindow.isDestroyed()) settingsWindow.webContents.send('settings:preferences-updated', prefs);
}
function refreshTrayMenu() {
  if (tray && !tray.isDestroyed()) tray.setContextMenu(buildTrayMenu());
}
function validatePreference(key, value) {
  const enums = {
    format: ['12', '24'],
    background: ['glass', 'wallpaper', 'wallpaper-glass', 'solid', 'gradient', 'aurora', 'carbon', 'metal', 'transparent'],
    shape: ['rounded', 'pill', 'square'],
    gradientPreset: ['aurora', 'sunset', 'ocean', 'graphite', 'nebula', 'emerald'],
    clockSurface: ['none', 'glass', 'raised', 'neon', 'inset'],
    dateSurface: ['none', 'glass', 'raised', 'neon', 'inset'],
    clockTextEffect: ['clean', 'soft', 'embossed', 'extruded', 'neon'],
    dateTextEffect: ['clean', 'soft', 'embossed', 'extruded', 'neon'],
    panelDepth: ['flat', 'floating', 'bevel', 'chrome'],
    clockFont: ['Segoe UI Variable', 'Segoe UI', 'Arial', 'Georgia', 'Verdana', 'Trebuchet MS', 'Courier New', 'Tahoma', 'Times New Roman', 'Consolas', 'Cambria', 'Bahnschrift'],
    dateFont: ['Segoe UI Variable', 'Segoe UI', 'Arial', 'Georgia', 'Verdana', 'Trebuchet MS', 'Courier New', 'Tahoma', 'Times New Roman', 'Consolas', 'Cambria', 'Bahnschrift']
  };
  if (enums[key]) return enums[key].includes(value);
  if (['clockColor', 'dateColor', 'clockOutlineColor', 'dateOutlineColor', 'solidColor', 'clockSurfaceColor', 'dateSurfaceColor'].includes(key)) {
    return typeof value === 'string' && /^#[0-9a-fA-F]{6}$/.test(value);
  }
  if (['clockOutlineEnabled', 'dateOutlineEnabled'].includes(key)) return typeof value === 'boolean';
  if (key === 'clockSize') return Number.isFinite(value) && value >= 20 && value <= 120;
  if (key === 'dateSize') return Number.isFinite(value) && value >= 8 && value <= 32;
  if (['clockOutlineWidth', 'dateOutlineWidth'].includes(key)) return Number.isFinite(value) && value >= 0 && value <= 5;
  if (key === 'opacity') return Number.isFinite(value) && value >= 0.2 && value <= 1;
  if (key === 'masterScale') return Number.isFinite(value) && value >= MIN_MASTER_SCALE && value <= MAX_MASTER_SCALE;
  if (key === 'timeDateGap') return Number.isFinite(value) && value >= 0 && value <= 32;
  return false;
}

ipcMain.handle('clock:get-preferences', () => withWallpaperUrl());
ipcMain.handle('settings:get-preferences', () => withWallpaperUrl());
ipcMain.handle('preferences:save', (_event, key, value) => {
  if (!validatePreference(key, value)) return false;
  savePreferences({ [key]: value });
  broadcastPreferences();
  return true;
});
ipcMain.handle('preferences:reset', () => {
  savePreferences({ ...DEFAULTS });
  if (clockWindow && !clockWindow.isDestroyed()) {
    expectedClockSize = { width: DEFAULT_BOUNDS.width, height: DEFAULT_BOUNDS.height };
    clockWindow.setPosition(DEFAULT_BOUNDS.x, DEFAULT_BOUNDS.y, false);
    clockWindow.setSize(expectedClockSize.width, expectedClockSize.height, false);
  }
  broadcastPreferences();
  return withWallpaperUrl();
});
ipcMain.handle('wallpaper:choose', async () => {
  const result = await dialog.showOpenDialog(settingsWindow || undefined, {
    title: 'Choose Clock Wallpaper', properties: ['openFile'],
    filters: [{ name: 'Wallpaper media', extensions: ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'mp4', 'webm', 'mov', 'm4v'] }]
  });
  if (result.canceled || !result.filePaths.length) return null;
  savePreferences({ wallpaperPath: result.filePaths[0], background: 'wallpaper' });
  broadcastPreferences();
  return true;
});
ipcMain.handle('clock:set-master-size', (_event, requestedScale) => {
  if (!clockWindow || clockWindow.isDestroyed() || !Number.isFinite(requestedScale)) return false;
  const scale = Math.max(MIN_MASTER_SCALE, Math.min(MAX_MASTER_SCALE, requestedScale));
  const width = Math.round(DEFAULT_BOUNDS.width * scale);
  const height = Math.round(DEFAULT_BOUNDS.height * scale);
  expectedClockSize = { width, height };
  // Programmatic resize is allowed even though native user resizing is disabled.
  clockWindow.setBounds({ ...clockWindow.getBounds(), width, height }, false);
  savePreferences({ masterScale: scale, windowWidth: width, windowHeight: height });
  broadcastPreferences();
  return { masterScale: scale, windowWidth: width, windowHeight: height };
});

function createSettingsWindow() {
  if (settingsWindow && !settingsWindow.isDestroyed()) {
    if (!settingsWindow.isVisible()) settingsWindow.show();
    settingsWindow.focus();
    return;
  }
  settingsWindow = new BrowserWindow({
    width: 820, height: 760, minWidth: 720, minHeight: 640,
    title: 'Creative Lab · Floating Clock Settings',
    icon: path.join(__dirname, '../assets/floating-clock-app.ico'),
    show: false, resizable: true, autoHideMenuBar: true,
    backgroundColor: '#0d1420',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false, sandbox: true
    }
  });
  settingsWindow.loadFile(path.join(__dirname, '../src/settings.html'));
  settingsWindow.once('ready-to-show', () => settingsWindow && !settingsWindow.isDestroyed() && settingsWindow.show());
  settingsWindow.on('closed', () => { settingsWindow = null; });
}
ipcMain.handle('settings:open', () => createSettingsWindow());

function lowerClockBehindWindows() {
  if (process.platform !== 'win32' || !clockWindow || clockWindow.isDestroyed()) return;
  const handle = clockWindow.getNativeWindowHandle();
  const hwnd = handle.length >= 8 ? handle.readBigUInt64LE(0).toString() : String(handle.readUInt32LE(0));
  const script = `$sig='[DllImport("user32.dll", SetLastError=true)] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);'; Add-Type -MemberDefinition $sig -Name Native -Namespace Win32; [Win32.Native]::SetWindowPos([IntPtr]::new([Int64]${hwnd}), [IntPtr]::new(1), 0, 0, 0, 0, 0x0001 -bor 0x0002 -bor 0x0010) | Out-Null`;
  execFile('powershell.exe', ['-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', script], { windowsHide: true }, (error) => {
    if (error) console.warn('Could not lower clock behind other windows:', error.message);
  });
}

function createClockWindow() {
  const prefs = getPreferences();
  const savedScale = Number.isFinite(prefs.masterScale)
    ? Math.max(MIN_MASTER_SCALE, Math.min(MAX_MASTER_SCALE, prefs.masterScale))
    : Math.max(MIN_MASTER_SCALE, Math.min(MAX_MASTER_SCALE, (Number(prefs.windowWidth) || DEFAULT_BOUNDS.width) / DEFAULT_BOUNDS.width));
  const startupWidth = Math.round(DEFAULT_BOUNDS.width * savedScale);
  const startupHeight = Math.round(DEFAULT_BOUNDS.height * savedScale);
  savePreferences({ masterScale: savedScale, windowWidth: startupWidth, windowHeight: startupHeight });
  expectedClockSize = { width: startupWidth, height: startupHeight };
  const initialBounds = recoverBounds({
    x: Number.isFinite(prefs.x) ? prefs.x : DEFAULT_BOUNDS.x,
    y: Number.isFinite(prefs.y) ? prefs.y : DEFAULT_BOUNDS.y,
    width: startupWidth,
    height: startupHeight
  }, screen.getAllDisplays());
  if (initialBounds.x !== prefs.x || initialBounds.y !== prefs.y) {
    savePreferences({ x: initialBounds.x, y: initialBounds.y });
  }
  clockWindow = new BrowserWindow({
    width: startupWidth,
    height: startupHeight,
    x: initialBounds.x,
    y: initialBounds.y,
    frame: false, transparent: true, backgroundColor: '#00000000',
    alwaysOnTop: false, resizable: false, maximizable: false, minimizable: false,
    fullscreenable: false, skipTaskbar: true, focusable: true, show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false, sandbox: true
    }
  });
  // Normal desktop z-order: regular application windows appear above the clock.
  clockWindow.setAlwaysOnTop(false);
  // Native Electron drag region moves the window without changing its dimensions.
  // resizable:false blocks edge resizing; programmatic Master Size updates still work.
  clockWindow.loadFile(path.join(__dirname, '../src/index.html'));
  clockWindow.once('ready-to-show', () => {
    if (!clockWindow || clockWindow.isDestroyed()) return;
    clockWindow.showInactive();
    lowerClockBehindWindows();
  });
  clockWindow.on('moved', () => {
    if (!clockWindow || clockWindow.isDestroyed()) return;
    clearTimeout(positionSaveTimer);
    positionSaveTimer = setTimeout(() => {
      if (!clockWindow || clockWindow.isDestroyed()) return;
      const [x, y] = clockWindow.getPosition();
      savePreferences({ x, y });
    }, 250);
  });
  clockWindow.on('show', refreshTrayMenu);
  clockWindow.on('hide', refreshTrayMenu);
  clockWindow.on('closed', () => { clockWindow = null; refreshTrayMenu(); });
}

function toggleClockVisibility() {
  if (!clockWindow || clockWindow.isDestroyed()) {
    createClockWindow();
    return;
  }
  if (clockWindow.isVisible()) clockWindow.hide();
  else { clockWindow.showInactive(); lowerClockBehindWindows(); }
  refreshTrayMenu();
}
function buildTrayMenu() {
  const visible = !!(clockWindow && !clockWindow.isDestroyed() && clockWindow.isVisible());
  return Menu.buildFromTemplate([
    { label: visible ? 'Hide Clock' : 'Show Clock', click: toggleClockVisibility },
    { label: 'Settings', click: createSettingsWindow },
    { type: 'separator' },
    { label: 'Exit', click: () => app.quit() }
  ]);
}
function createTray() {
  if (tray && !tray.isDestroyed()) return;
  const iconPath = path.join(__dirname, '../assets/floating-clock-app.ico');
  const icon = nativeImage.createFromPath(iconPath);
  tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon);
  tray.setToolTip('Creative Lab Floating Clock');
  refreshTrayMenu();
  // Deliberately no click handler: clicking the tray icon itself must not toggle the clock.
  // The user controls visibility only through the tray context-menu command.
}

// A second launch forwards to the existing process instead of creating another clock/tray.
const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!clockWindow || clockWindow.isDestroyed()) createClockWindow();
    else if (!clockWindow.isVisible()) clockWindow.showInactive();
    lowerClockBehindWindows();
    refreshTrayMenu();
  });

  app.whenReady().then(() => {
    createClockWindow();
    createTray();
    // Do not automatically re-show a user-hidden clock on OS/app activation.
    screen.on('display-removed', recoverClockPosition);
    screen.on('display-metrics-changed', recoverClockPosition);
  });
}

function recoverClockPosition() {
  if (!clockWindow || clockWindow.isDestroyed()) return;
  const current = clockWindow.getBounds();
  const next = recoverBounds(current, screen.getAllDisplays());
  if (next.x !== current.x || next.y !== current.y) {
    clockWindow.setPosition(next.x, next.y, false);
    savePreferences({ x: next.x, y: next.y });
  }
}

app.on('before-quit', () => {
  if (tray && !tray.isDestroyed()) tray.destroy();
  tray = null;
  screen.removeListener('display-removed', recoverClockPosition);
  screen.removeListener('display-metrics-changed', recoverClockPosition);
});
app.on('window-all-closed', () => { if (process.platform === 'darwin') app.quit(); });

