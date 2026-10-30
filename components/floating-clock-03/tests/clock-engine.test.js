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
