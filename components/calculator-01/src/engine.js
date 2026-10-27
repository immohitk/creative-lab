
"use strict";

function tokenize(input) {
  const tokens = [];
  const pattern = /\s*(\d+(?:\.\d*)?|\.\d+|[+\-*/])\s*/g;
  let position = 0;
  let match;

  while (position < input.length) {
    pattern.lastIndex = position;
    match = pattern.exec(input);

    if (!match || match.index !== position) {
      throw new Error("Invalid expression.");
    }

    tokens.push(match[1]);
    position = pattern.lastIndex;
  }

  if (tokens.length === 0) {
    throw new Error("Enter a calculation.");
  }

  return tokens;
}

function evaluateExpression(input) {
  const tokens = tokenize(input);
  let index = 0;

  function parseNumber() {
    let sign = 1;

    if (tokens[index] === "+" || tokens[index] === "-") {
      if (tokens[index] === "-") sign = -1;
      index++;
    }

    const token = tokens[index];

    if (token === undefined || !/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(token)) {
      throw new Error("Expected a number.");
    }

    index++;
    return sign * Number(token);
  }

  function parseTerm() {
    let value = parseNumber();

    while (tokens[index] === "*" || tokens[index] === "/") {
      const operator = tokens[index++];
      const right = parseNumber();

      if (operator === "/" && right === 0) {
        throw new Error("Cannot divide by zero.");
      }

      value = operator === "*" ? value * right : value / right;

      if (!Number.isFinite(value)) {
        throw new Error("Result is outside the supported range.");
      }
    }

    return value;
  }

  function parseExpression() {
    let value = parseTerm();

    while (tokens[index] === "+" || tokens[index] === "-") {
      const operator = tokens[index++];
      const right = parseTerm();

      value = operator === "+" ? value + right : value - right;

      if (!Number.isFinite(value)) {
        throw new Error("Result is outside the supported range.");
      }
    }

    return value;
  }

  const result = parseExpression();

  if (index !== tokens.length) {
    throw new Error("Invalid expression.");
  }

  return Object.is(result, -0) ? 0 : Number(result.toPrecision(12));
}

if (typeof module !== "undefined") {
  module.exports = { evaluateExpression };
}

if (typeof window !== "undefined") {
  window.CalculatorEngine = { evaluateExpression };
}