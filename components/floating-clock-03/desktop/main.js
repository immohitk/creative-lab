const {
  app,
  BrowserWindow,
  ipcMain,
  screen,
  Menu,
  Tray,
  nativeImage,
  dialog,
} = require("electron");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

let clockWindow = null;
let tray = null;
let dragState = null;

const DEFAULT_BOUNDS = { width: 260, height: 90, x: 40, y: 40 };

function getPreferences() {
  const defaults = {
    x: DEFAULT_BOUNDS.x,
    y: DEFAULT_BOUNDS.y,
  };

  try {
    const fs = require("node:fs");
    const file = path.join(app.getPath("userData"), "preferences.json");

    if (fs.existsSync(file)) {
      return { ...defaults, ...JSON.parse(fs.readFileSync(file, "utf8")) };
    }
  } catch {
    // Use safe defaults if preferences are invalid.
  }

  return defaults;
}

ipcMain.handle("clock:get-preferences", () => {
  const prefs = getPreferences();

  return {
    ...prefs,
    wallpaperUrl: prefs.wallpaperPath
      ? pathToFileURL(prefs.wallpaperPath).href
      : null,
  };
});

ipcMain.handle("clock:save-preference", (_event, key, value) => {
  const allowedKeys = [
    "format",
    "theme",
    "background",
    "shape",
    "clockSize",
    "dateSize",
    "opacity",
    "wallpaperPath",
  ];

  if (!allowedKeys.includes(key)) return false;

  if (key === "format" && !["12", "24"].includes(value)) return false;
  if (key === "theme" && !["midnight", "light", "forest"].includes(value)) return false;
  if (key === "background" && !["glass", "wallpaper", "transparent"].includes(value)) return false;
  if (key === "shape" && !["rounded", "pill", "square"].includes(value)) return false;
  if (key === "wallpaperPath" && typeof value !== "string") return false;

  if (key === "clockSize" && (!Number.isFinite(value) || value < 20 || value > 120)) return false;
  if (key === "dateSize" && (!Number.isFinite(value) || value < 8 || value > 32)) return false;
  if (key === "opacity" && (!Number.isFinite(value) || value < 0.2 || value > 1)) return false;

  savePreferences({ [key]: value });
  clockWindow?.webContents.send("clock:preferences-updated", {
    ...getPreferences(),
    wallpaperUrl: getPreferences().wallpaperPath
      ? pathToFileURL(getPreferences().wallpaperPath).href
      : null,
  });

  return true;
});

ipcMain.handle("clock:select-wallpaper", async () => {
  if (!clockWindow || clockWindow.isDestroyed()) return null;

  const result = await dialog.showOpenDialog(clockWindow, {
    title: "Choose Clock Wallpaper",
    properties: ["openFile"],
    filters: [
      {
        name: "Images",
        extensions: ["png", "jpg", "jpeg", "webp", "bmp"],
      },
    ],
  });

  if (result.canceled || !result.filePaths.length) return null;

  const wallpaperPath = result.filePaths[0];
  const wallpaperUrl = pathToFileURL(wallpaperPath).href;

  savePreferences({ wallpaperPath });

  const preferences = {
    ...getPreferences(),
    wallpaperUrl,
  };

  clockWindow.webContents.send("clock:preferences-updated", preferences);

  return { wallpaperPath, wallpaperUrl };
});

function savePreferences(patch) {
  try {
    const fs = require("node:fs");
    const file = path.join(app.getPath("userData"), "preferences.json");
    const current = getPreferences();
    fs.writeFileSync(file, JSON.stringify({ ...current, ...patch }, null, 2));
  } catch (error) {
    console.error("Could not save preferences:", error);
  }
}

function getSafePosition(x, y, width, height) {
  const displays = screen.getAllDisplays();

  const isVisible = displays.some(({ workArea }) =>
    x + width > workArea.x &&
    x < workArea.x + workArea.width &&
    y + height > workArea.y &&
    y < workArea.y + workArea.height
  );

  if (isVisible) return { x, y };

  const { workArea } = screen.getPrimaryDisplay();

  return {
    x: workArea.x + 20,
    y: workArea.y + 20,
  };
}

function createWindow() {
  if (clockWindow && !clockWindow.isDestroyed()) {
    clockWindow.show();
    return clockWindow;
  }

  const prefs = getPreferences();
  const validThemes = ["midnight", "light", "forest"];
  const format = prefs.format === "24" ? "24" : "12";
  const theme = validThemes.includes(prefs.theme) ? prefs.theme : "midnight";
  const position = getSafePosition(
    Number.isFinite(prefs.x) ? prefs.x : DEFAULT_BOUNDS.x,
    Number.isFinite(prefs.y) ? prefs.y : DEFAULT_BOUNDS.y,
    DEFAULT_BOUNDS.width,
    DEFAULT_BOUNDS.height
  );

  clockWindow = new BrowserWindow({
    ...DEFAULT_BOUNDS,
    ...position,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    alwaysOnTop: true,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    show: false,
    title: "Creative Lab Floating Clock",
    icon: path.join(process.resourcesPath, "creative-lab-clock.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  clockWindow.setAlwaysOnTop(true);
  clockWindow.loadFile(path.join(__dirname, "../src/index.html"));

  clockWindow.once("ready-to-show", () => {
    if (clockWindow && !clockWindow.isDestroyed()) clockWindow.show();
  });

  clockWindow.on("moved", () => {
    if (!clockWindow || clockWindow.isDestroyed()) return;
    const [x, y] = clockWindow.getPosition();
    savePreferences({ x, y });
  });

  clockWindow.on("closed", () => {
    clockWindow = null;
    dragState = null;
  });

  return clockWindow;
}

ipcMain.on("clock:drag-start", (event, pointer) => {
  if (!clockWindow || event.sender !== clockWindow.webContents) return;
  if (!pointer || !Number.isFinite(pointer.screenX) || !Number.isFinite(pointer.screenY)) return;

  const [x, y] = clockWindow.getPosition();

  dragState = {
    pointerX: pointer.screenX,
    pointerY: pointer.screenY,
    windowX: x,
    windowY: y,
  };
});

ipcMain.on("clock:drag-move", (event, pointer) => {
  if (!clockWindow || event.sender !== clockWindow.webContents || !dragState) return;
  if (!pointer || !Number.isFinite(pointer.screenX) || !Number.isFinite(pointer.screenY)) return;

  clockWindow.setPosition(
    Math.round(dragState.windowX + pointer.screenX - dragState.pointerX),
    Math.round(dragState.windowY + pointer.screenY - dragState.pointerY)
  );
});

ipcMain.on("clock:drag-end", (event) => {
  if (clockWindow && event.sender === clockWindow.webContents) dragState = null;
});

ipcMain.handle("clock:show-settings-menu", async () => {
  if (!clockWindow || clockWindow.isDestroyed()) return;

  const menu = Menu.buildFromTemplate([
    {
      label: "Choose Wallpaper",
      click: () => clockWindow?.webContents.send("clock:open-wallpaper-picker"),
    },
    {
      label: "Glass Background",
      click: () => {
        savePreferences({ background: "glass" });
        clockWindow?.webContents.send("clock:preferences-updated", {
          ...getPreferences(),
          wallpaperUrl: getPreferences().wallpaperPath
            ? pathToFileURL(getPreferences().wallpaperPath).href
            : null,
        });
      },
    },
    {
      label: "Transparent Background",
      click: () => {
        savePreferences({ background: "transparent" });
        clockWindow?.webContents.send("clock:preferences-updated", {
          ...getPreferences(),
          wallpaperUrl: getPreferences().wallpaperPath
            ? pathToFileURL(getPreferences().wallpaperPath).href
            : null,
        });
      },
    },
    { type: "separator" },
    {
      label: "Toggle 12/24-hour Format",
      click: () => {
        const format = getPreferences().format === "24" ? "12" : "24";
        savePreferences({ format });
        clockWindow?.webContents.send("clock:preferences-updated", {
          ...getPreferences(),
          wallpaperUrl: getPreferences().wallpaperPath
            ? pathToFileURL(getPreferences().wallpaperPath).href
            : null,
        });
      },
    },
  ]);

  menu.popup({ window: clockWindow });
});

function createTray() {
  if (tray) return;

  const iconPath = path.join(__dirname, "../assets/creative-lab-clock.ico");
  const icon = nativeImage.createFromPath(iconPath);

  tray = new Tray(icon);
  tray.setToolTip("Creative Lab Floating Clock");

  const menu = Menu.buildFromTemplate([
    {
      label: "Show Clock",
      click: () => clockWindow?.show(),
    },
    {
        label: "Time Format",
        submenu: [
            {
            label: "12-hour",
            type: "radio",
            checked: getPreferences().format !== "24",
            click: () => {
                savePreferences({ format: "12" });
                clockWindow?.webContents.send(
                "clock:preferences-updated",
                getPreferences()
                );
            },
            },
            {
            label: "24-hour",
            type: "radio",
            checked: getPreferences().format === "24",
            click: () => {
                savePreferences({ format: "24" });
                clockWindow?.webContents.send(
                "clock:preferences-updated",
                getPreferences()
                );
            },
            },
        ],
        },
        { type: "separator" },
        {
        label: "Theme",
        submenu: ["midnight", "light", "forest"].map((theme) => ({
            label: theme.charAt(0).toUpperCase() + theme.slice(1),
            type: "radio",
            checked: getPreferences().theme === theme,
            click: () => {
            savePreferences({ theme });
            clockWindow?.webContents.send(
                "clock:preferences-updated",
                getPreferences()
            );
            },
        })),
    },
    {
      label: "Hide Clock",
      click: () => clockWindow?.hide(),
    },
    { type: "separator" },
    {
      label: "Exit",
      click: () => app.quit(),
    },
  ]);

  tray.setContextMenu(menu);
}

app.whenReady().then(() => {
  createWindow();
  createTray();

  app.on("activate", () => {
    if (!clockWindow || clockWindow.isDestroyed()) createWindow();
    else clockWindow.show();
  });
});

app.on("before-quit", () => {
  if (tray) {
    tray.destroy();
    tray = null;
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
