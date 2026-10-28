"use strict";

function evaluateExpression(input) {
  const source = String(input).replace(/[×]/g, "*").replace(/[÷]/g, "/").replace(/[−]/g, "-").replace(/\s+/g, "");
  if (!source) throw new Error("Enter a calculation.");

  let index = 0;

  function parseExpression() {
    let value = parseTerm();
    while (source[index] === "+" || source[index] === "-") {
      const op = source[index++];
      const right = parseTerm();
      value = op === "+" ? value + right : value - right;
      assertFinite(value);
    }
    return value;
  }

  function parseTerm() {
    let value = parseUnary();
    while (source[index] === "*" || source[index] === "/") {
      const op = source[index++];
      const right = parseUnary();
      if (op === "/" && right === 0) throw new Error("Cannot divide by zero.");
      value = op === "*" ? value * right : value / right;
      assertFinite(value);
    }
    return value;
  }

  function parseUnary() {
    if (source[index] === "+") {
      index++;
      return parseUnary();
    }
    if (source[index] === "-") {
      index++;
      return -parseUnary();
    }
    return parsePower();
  }

  function parsePower() {
    const base = parsePrimary();
    if (source[index] !== "^") return base;

    index++;
    const match = source.slice(index).match(/^\d+/);
    if (!match) throw new Error("Enter an exponent from 1 to 99.");

    const exponent = Number(match[0]);
    if (exponent < 1 || exponent > 99) throw new Error("Exponent must be between 1 and 99.");
    if (!Number.isInteger(base) || base < 0) throw new Error("Power base must be a non-negative whole number.");

    index += match[0].length;
    const result = Math.pow(base, exponent);
    assertFinite(result);
    return result;
  }

  function parsePrimary() {
    if (source[index] === "(") {
      index++;
      const value = parseExpression();
      if (source[index] !== ")") throw new Error("Missing closing bracket.");
      index++;
      return value;
    }

    const match = source.slice(index).match(/^(?:\d+\.?\d*|\.\d+)/);
    if (!match) throw new Error("Invalid expression.");
    index += match[0].length;
    return Number(match[0]);
  }

  function assertFinite(value) {
    if (!Number.isFinite(value) || Math.abs(value) > 999999999999) {
      throw new Error("Result is outside the supported range.");
    }
  }

  const result = parseExpression();
  if (index !== source.length) throw new Error("Invalid expression.");
  assertFinite(result);
  return Object.is(result, -0) ? 0 : Number(result.toPrecision(12));
}

if (typeof module !== "undefined") {
  module.exports = { evaluateExpression };
}

if (typeof window !== "undefined") {
  window.CalculatorEngine = { evaluateExpression };
}
