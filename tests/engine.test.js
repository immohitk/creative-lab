
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { evaluateExpression } = require("../components/calculator-01/src/engine.js");

test("basic arithmetic", () => {
  assert.equal(evaluateExpression("12+8"), 20);
  assert.equal(evaluateExpression("15-7"), 8);
  assert.equal(evaluateExpression("6*4"), 24);
  assert.equal(evaluateExpression("20/5"), 4);
});

test("decimals and negative numbers", () => {
  assert.equal(evaluateExpression("0.5+0.25"), 0.75);
  assert.equal(evaluateExpression("-5+2"), -3);
});

test("multiplication takes precedence over addition", () => {
  assert.equal(evaluateExpression("2+3*4"), 14);
});

test("division by zero is rejected", () => {
  assert.throws(() => evaluateExpression("20/0"), /divide by zero/i);
});

test("invalid and incomplete expressions are rejected", () => {
  assert.throws(() => evaluateExpression("2+"));
  assert.throws(() => evaluateExpression("2+a"));
});
