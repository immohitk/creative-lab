
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("floatingClock", {
  startDrag: (pointer) => ipcRenderer.send("clock:drag-start", pointer),
  moveDrag: (pointer) => ipcRenderer.send("clock:drag-move", pointer),
  endDrag: () => ipcRenderer.send("clock:drag-end"),

  getPreferences: () => ipcRenderer.invoke("clock:get-preferences"),
  savePreference: (key, value) =>
    ipcRenderer.invoke("clock:save-preference", key, value),

  selectWallpaper: () => ipcRenderer.invoke("clock:select-wallpaper"),
  showSettingsMenu: () => ipcRenderer.invoke("clock:show-settings-menu"),

  onOpenWallpaperPicker: (callback) => {
    ipcRenderer.on("clock:open-wallpaper-picker", () => {
      callback();
    });
  },

  onPreferencesUpdated: (callback) => {
    ipcRenderer.on("clock:preferences-updated", (_event, prefs) => {
      callback(prefs);
    });
  },
});
