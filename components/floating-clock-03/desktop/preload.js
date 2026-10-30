const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('floatingClock', {
  getPreferences: () => ipcRenderer.invoke('clock:get-preferences'),
  onPreferencesUpdated: (callback) => ipcRenderer.on('clock:preferences-updated', (_event, prefs) => callback(prefs))
});

contextBridge.exposeInMainWorld('clockSettings', {
  getPreferences: () => ipcRenderer.invoke('settings:get-preferences'),
  savePreference: (key, value) => ipcRenderer.invoke('preferences:save', key, value),
  resetPreferences: () => ipcRenderer.invoke('preferences:reset'),
  chooseWallpaper: () => ipcRenderer.invoke('wallpaper:choose'),
  setMasterSize: (scale) => ipcRenderer.invoke('clock:set-master-size', scale),
  onPreferencesUpdated: (callback) => ipcRenderer.on('settings:preferences-updated', (_event, prefs) => callback(prefs))
});
