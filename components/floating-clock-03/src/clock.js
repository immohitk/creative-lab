
const clockElement = document.getElementById("clock");
const dateElement = document.getElementById("date");
const widget = document.getElementById("clockWidget");

const THEMES = ["midnight", "light", "forest"];
const BACKGROUNDS = ["glass", "wallpaper", "transparent"];
const SHAPES = ["rounded", "pill", "square"];

let use24Hour = false;
let currentTheme = "midnight";
let currentBackground = "glass";
let currentShape = "rounded";
let pointerStart = null;
let dragged = false;
let dragStarted = false;

function renderClock() {
  const now = new Date();

  clockElement.textContent = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: !use24Hour,
  }).format(now);

  dateElement.textContent = new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(now);
}

function applyTheme(theme) {
  currentTheme = THEMES.includes(theme) ? theme : "midnight";
  document.documentElement.dataset.theme = currentTheme;
}

function applyBackground(background) {
  currentBackground = BACKGROUNDS.includes(background)
    ? background
    : "glass";

  widget.dataset.background = currentBackground;
}

function applyShape(shape) {
  currentShape = SHAPES.includes(shape) ? shape : "rounded";
  widget.dataset.shape = currentShape;
}

function applyWallpaper(wallpaperUrl) {
  const backgroundLayer = document.getElementById("backgroundLayer");

  if (!wallpaperUrl) {
    backgroundLayer.style.backgroundImage = "none";
    return;
  }

  backgroundLayer.style.backgroundImage = `url("${wallpaperUrl}")`;
  backgroundLayer.style.backgroundSize = "cover";
  backgroundLayer.style.backgroundPosition = "center";
  backgroundLayer.style.backgroundRepeat = "no-repeat";
}

async function savePreference(key, value) {
  try {
    await window.floatingClock.savePreference(key, value);
  } catch (error) {
    console.error(`Could not save ${key}:`, error);
  }
}

async function chooseWallpaper() {
  try {
    const result = await window.floatingClock.selectWallpaper();

    if (!result) return;

    applyWallpaper(result.wallpaperUrl);
    applyBackground("wallpaper");

    await savePreference("background", "wallpaper");
  } catch (error) {
    console.error("Unable to select wallpaper:", error);
  }
}

window.floatingClock.onOpenWallpaperPicker(() => {
  chooseWallpaper();
});

async function initializePreferences() {
  try {
    const prefs = await window.floatingClock.getPreferences();

    use24Hour = prefs.format === "24";
    applyTheme(prefs.theme);
    applyBackground(prefs.background);
    applyShape(prefs.shape);
    applyWallpaper(prefs.wallpaperUrl);

    renderClock();
  } catch (error) {
    console.error("Could not load preferences:", error);
    applyTheme("midnight");
    applyBackground("glass");
    applyShape("rounded");
    renderClock();
  }
}

widget.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;

  pointerStart = { x: event.screenX, y: event.screenY };
  dragged = false;
  dragStarted = false;

  window.floatingClock.startDrag({
    screenX: event.screenX,
    screenY: event.screenY,
  });
});

window.addEventListener("pointermove", (event) => {
  if (!pointerStart) return;

  const dx = event.screenX - pointerStart.x;
  const dy = event.screenY - pointerStart.y;

  if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
    dragged = true;
    dragStarted = true;
  }

  if (dragStarted) {
    window.floatingClock.moveDrag({
      screenX: event.screenX,
      screenY: event.screenY,
    });
  }
});

window.addEventListener("pointerup", async () => {
  if (!pointerStart) return;

  window.floatingClock.endDrag();

  if (!dragged) {
    use24Hour = !use24Hour;
    await savePreference("format", use24Hour ? "24" : "12");
    renderClock();
  }

  pointerStart = null;
  dragged = false;
  dragStarted = false;
});

window.addEventListener("pointercancel", () => {
  window.floatingClock.endDrag();
  pointerStart = null;
  dragged = false;
  dragStarted = false;
});

widget.addEventListener("contextmenu", (event) => {
  event.preventDefault();
  window.floatingClock.showSettingsMenu();
});

window.floatingClock.onPreferencesUpdated((prefs) => {
  use24Hour = prefs.format === "24";
  applyTheme(prefs.theme);
  applyBackground(prefs.background);
  applyShape(prefs.shape);
  applyWallpaper(prefs.wallpaperUrl);
  renderClock();
});

initializePreferences();
setInterval(renderClock, 1000);
