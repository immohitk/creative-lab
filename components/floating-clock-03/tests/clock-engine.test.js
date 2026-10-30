const test = require("node:test");
const assert = require("node:assert/strict");
const { formatTime, formatDate } = require("../src/clock-engine");

test("24-hour format displays hours from 00 to 23", () => {
  const date = new Date(2026, 0, 15, 14, 30, 45);
  const result = formatTime(date, true);

  assert.match(result, /14/);
  assert.match(result, /30/);
  assert.match(result, /45/);
});

test("12-hour format displays PM for afternoon", () => {
  const date = new Date(2026, 0, 15, 14, 30, 45);
  const result = formatTime(date, false);

  assert.match(result, /02|2/);
  assert.match(result, /30/);
  assert.match(result, /45/);
  assert.match(result, /PM/i);
});

test("formatDate includes the year", () => {
  const date = new Date(2026, 0, 15, 12, 0, 0);
  assert.match(formatDate(date), /2026/);
});

test("formatDate returns a non-empty string", () => {
  const date = new Date(2026, 0, 15, 12, 0, 0);
  assert.ok(formatDate(date).length > 0);
});