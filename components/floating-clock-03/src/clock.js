const clockElement = document.getElementById('clock');
const dateElement = document.getElementById('date');
const widget = document.getElementById('clockWidget');
const wallpaperVideo = document.getElementById('wallpaperVideo');
let use24Hour = false;
let prefs = {};
let dragPointerId = null;
let dragOrigin = null;
let dragStarted = false;

function renderClock() {
  const now = new Date();
  clockElement.textContent = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: !use24Hour
  }).format(now);
  dateElement.textContent = new Intl.DateTimeFormat(undefined, {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
  }).format(now);
}

function applyPreferences(next) {
  prefs = { ...prefs, ...next };
  use24Hour = prefs.format === '24';
  widget.dataset.background = prefs.background || 'glass';
  widget.dataset.shape = prefs.shape || 'rounded';
  widget.dataset.gradient = prefs.gradientPreset || 'aurora';
  widget.dataset.panelDepth = prefs.panelDepth || 'floating';
  widget.dataset.clockSurface = prefs.clockSurface || 'glass';
  widget.dataset.dateSurface = prefs.dateSurface || 'none';
  widget.dataset.clockTextEffect = prefs.clockTextEffect || 'embossed';
  widget.dataset.dateTextEffect = prefs.dateTextEffect || 'soft';

  const wallpaperUrl = prefs.wallpaperUrl;
  const extension = (prefs.wallpaperPath || '').split('.').pop().toLowerCase();
  const isVideo = ['mp4', 'webm', 'mov', 'm4v'].includes(extension);
  widget.dataset.wallpaperType = isVideo ? 'video' : (extension === 'gif' ? 'gif' : 'image');
  widget.style.setProperty('--wallpaper-image', wallpaperUrl && !isVideo ? `url("${wallpaperUrl}")` : 'none');
  if (wallpaperVideo) {
    if (isVideo && wallpaperUrl) {
      if (wallpaperVideo.src !== wallpaperUrl) wallpaperVideo.src = wallpaperUrl;
      wallpaperVideo.style.display = 'block';
      wallpaperVideo.play().catch(() => {});
    } else {
      wallpaperVideo.pause();
      wallpaperVideo.removeAttribute('src');
      wallpaperVideo.load();
      wallpaperVideo.style.display = 'none';
    }
  }

  const root = document.documentElement.style;
  const masterScale = Math.max(0.40, Math.min(2, Number(prefs.masterScale) || 1));
  root.setProperty('--master-scale', String(masterScale));
  root.setProperty('--clock-size', `${(prefs.clockSize ?? 46) * masterScale}px`);
  root.setProperty('--date-size', `${(prefs.dateSize ?? 14) * masterScale}px`);
  root.setProperty('--time-date-gap', `${(prefs.timeDateGap ?? 12) * masterScale}px`);
  root.setProperty('--clock-color', prefs.clockColor || '#F5FFF9');
  root.setProperty('--date-color', prefs.dateColor || '#C9D4DE');
  root.setProperty('--clock-font', `'${prefs.clockFont || 'Segoe UI'}', sans-serif`);
  root.setProperty('--date-font', `'${prefs.dateFont || 'Segoe UI'}', sans-serif`);
  root.setProperty('--clock-outline-color', prefs.clockOutlineColor || '#17212B');
  root.setProperty('--date-outline-color', prefs.dateOutlineColor || '#17212B');
  root.setProperty('--clock-outline-width', prefs.clockOutlineEnabled ? `${(prefs.clockOutlineWidth ?? 1) * masterScale}px` : '0px');
  root.setProperty('--date-outline-width', prefs.dateOutlineEnabled ? `${(prefs.dateOutlineWidth ?? 1) * masterScale}px` : '0px');
  root.setProperty('--panel-opacity', String(prefs.opacity ?? 1));
  root.setProperty('--solid-color', prefs.solidColor || '#17212B');
  root.setProperty('--clock-surface-color', prefs.clockSurfaceColor || '#142235');
  root.setProperty('--date-surface-color', prefs.dateSurfaceColor || '#142235');
  renderClock();
}

// Movement is provided by Electron's native draggable region in styles.css.
// No pointer handlers are registered: dragging can never change the BrowserWindow size.

window.floatingClock.onPreferencesUpdated(applyPreferences);
(async () => {
  applyPreferences(await window.floatingClock.getPreferences());
  setInterval(renderClock, 1000);
})();
