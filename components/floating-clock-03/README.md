# Creative Lab Floating Clock C03

## Included
- Frameless, always-on-top desktop clock with seconds.
- Native Electron drag region: hold the left mouse button and move the clock; the clock window remains non-resizable.
- No left-click or right-click actions on the clock itself.
- Tray context menu controls Show/Hide, Settings and Exit. Clicking the tray icon itself does not toggle visibility.
- Dynamic Show Clock / Hide Clock menu label based on current visibility.
- Background modes: Glass, Wallpaper, Wallpaper + Glass, Solid, Gradient, Aurora glow, Carbon fibre, Brushed metal and Transparent.
- Gradient presets: Aurora, Sunset, Ocean, Graphite, Nebula and Emerald.
- Independent time/date fonts, colours, sizes, outlines, text depth effects and backing surfaces.
- Outer panel depth styles: Flat, Floating shadow, 3D bevel and Chrome edge.
- Window dimensions can be changed in Settings; Reset to defaults restores dimensions and appearance.
- Wallpaper image files are selected locally and are not bundled with the project.

## Setup
From this folder:
```powershell
npm install
npm start
```

## Tests
```powershell
npm test
```

Preferences are stored in Electron's userData `preferences.json`.


## Master sizing and movement

- Drag the clock by holding the left mouse button and moving it. A simple click does nothing.
- Resize from Settings > Size & layout with the proportional Master clock size slider.
- The master scale proportionally scales the outer window, time, date, spacing and padding.
- Reset to defaults restores the original 320 × 112 px size and default position.
- Tray icon clicks do not toggle visibility; use the tray context menu.


## Desktop-only window behavior

- The clock is no longer always-on-top. Normal application windows appear above it.
- The clock uses a native Electron draggable region and a non-resizable BrowserWindow. Dragging moves only; it cannot alter width or height.
- It is shown inactive so it does not steal keyboard focus when launched or shown from the tray.
