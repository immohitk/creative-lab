const test = require("node:test");
const assert = require("node:assert/strict");
const { formatTime, formatDate } = require("../src/clock-engine");

test("formatTime returns seconds", () => {
  const result = formatTime(new Date("2026-10-30T10:08:45"), true);
  assert.match(result, /10:08:45/);
});
test("formatTime supports 12-hour format", () => {
  const result = formatTime(new Date("2026-10-30T15:08:45"), false);
  assert.match(result, /03:08:45|3:08:45/);
  assert.match(result, /PM/i);
});
test("formatDate includes year", () => {
  assert.match(formatDate(new Date("2026-10-30T10:08:45")), /2026/);
});
test("formatDate returns a non-empty string", () => {
  assert.ok(formatDate(new Date()).length > 0);
});

const { mergePreferences, recoverBounds } = require('../desktop/state-utils');

test('mergePreferences safely falls back for malformed stored preference values', () => {
  const defaults = { format: '12', width: 320, windowWidth: 320, masterScale: 1 };
  assert.deepEqual(mergePreferences(defaults, null), defaults);
  assert.deepEqual(mergePreferences(defaults, ['unexpected']), defaults);
});

test('mergePreferences preserves valid saved preferences and migrates legacy width', () => {
  const defaults = { format: '12', width: 320, windowWidth: 320, masterScale: 1 };
  assert.equal(mergePreferences(defaults, { format: '24', masterScale: 1.25 }).format, '24');
  assert.equal(mergePreferences(defaults, { windowWidth: 480 }).masterScale, 1.5);
});

test('recoverBounds keeps a saved position when it is on a connected display', () => {
  const bounds = { x: 100, y: 120, width: 320, height: 112 };
  const displays = [{ workArea: { x: 0, y: 0, width: 1920, height: 1080 } }];
  assert.deepEqual(recoverBounds(bounds, displays), bounds);
});

test('recoverBounds moves a fully off-screen widget back into a visible area', () => {
  const bounds = { x: 4000, y: 3000, width: 320, height: 112 };
  const displays = [{ workArea: { x: 0, y: 0, width: 1920, height: 1080 } }];
  const recovered = recoverBounds(bounds, displays);
  assert.ok(recovered.x < 1920 && recovered.y < 1080);
  assert.ok(recovered.x + recovered.width >= 48);
  assert.ok(recovered.y + recovered.height >= 48);
});

test('recoverBounds supports displays with negative coordinates', () => {
  const bounds = { x: 2500, y: 200, width: 320, height: 112 };
  const displays = [
    { workArea: { x: -1920, y: 0, width: 1920, height: 1080 } },
    { workArea: { x: 0, y: 0, width: 1920, height: 1080 } }
  ];
  const recovered = recoverBounds(bounds, displays);
  assert.ok(recovered.x <= 1920 - 48);
  assert.ok(recovered.x + recovered.width >= 0);
});
