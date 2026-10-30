const MIN_VISIBLE = 48;

function mergePreferences(defaults, stored = {}) {
  const merged = { ...defaults, ...(stored && typeof stored === 'object' && !Array.isArray(stored) ? stored : {}) };
  if (!stored || !Number.isFinite(stored.masterScale)) {
    const legacyWidth = Number(stored && stored.windowWidth) || defaults.windowWidth || defaults.width;
    const baseWidth = defaults.width || 320;
    const min = 0.4;
    const max = 2;
    merged.masterScale = Math.max(min, Math.min(max, legacyWidth / baseWidth));
  }
  return merged;
}

function intersectionArea(a, b) {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  return Math.max(0, right - left) * Math.max(0, bottom - top);
}

function distanceBetweenCenters(a, b) {
  const ax = a.x + a.width / 2;
  const ay = a.y + a.height / 2;
  const bx = b.x + b.width / 2;
  const by = b.y + b.height / 2;
  return Math.hypot(ax - bx, ay - by);
}

function recoverBounds(bounds, displays, minVisible = MIN_VISIBLE) {
  if (!Array.isArray(displays) || displays.length === 0) return { ...bounds };
  const areas = displays.map((display) => ({
    display,
    area: intersectionArea(bounds, display.workArea || display.bounds)
  }));
  let selected = areas.reduce((best, item) => item.area > best.area ? item : best, areas[0]);
  if (selected.area === 0) {
    selected = displays
      .map((display) => ({ display, distance: distanceBetweenCenters(bounds, display.workArea || display.bounds) }))
      .reduce((best, item) => item.distance < best.distance ? item : best);
  }
  const area = selected.display.workArea || selected.display.bounds;
  const visibleX = Math.min(minVisible, bounds.width, area.width);
  const visibleY = Math.min(minVisible, bounds.height, area.height);
  const minX = area.x - bounds.width + visibleX;
  const maxX = area.x + area.width - visibleX;
  const minY = area.y - bounds.height + visibleY;
  const maxY = area.y + area.height - visibleY;
  return {
    ...bounds,
    x: Math.round(Math.max(minX, Math.min(maxX, bounds.x))),
    y: Math.round(Math.max(minY, Math.min(maxY, bounds.y)))
  };
}

module.exports = { mergePreferences, recoverBounds, intersectionArea };
