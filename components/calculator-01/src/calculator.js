"use strict";

const display = document.querySelector("#display");
const expressionInput = document.querySelector("#expression");
const preview = document.querySelector("#preview");
const errorDisplay = document.querySelector("#error");
const keypad = document.querySelector(".calculator__keypad");
const historyList = document.querySelector("#history-list");
const historyEmpty = document.querySelector("#history-empty");
const clearHistoryButton = document.querySelector("#clear-history");
const historyDrawer = document.querySelector("#history-drawer");
const historyToggle = document.querySelector("#history-toggle");

const HISTORY_KEY = "creative-lab-calculator-history";
const MAX_HISTORY_ITEMS = 20;
let history = loadHistory();
let justCalculated = false;
let lastCalculation = "";
function loadHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(saved) ? saved.slice(0, MAX_HISTORY_ITEMS) : [];
  } catch {
    return [];
  }
}
function saveHistory() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch {
    showError("Unable to save calculation history.");
  }
}
function renderHistory() {
  historyList.replaceChildren();
  historyEmpty.hidden = history.length > 0;
  history.forEach((item) => {
    const li = document.createElement("li");
    li.className = "history__item";

    const expression = document.createElement("span");
    expression.className = "history__expression";
    expression.textContent = item.expression.replace(/\*/g, "×").replace(/\//g, "÷");

    const result = document.createElement("span");
    result.className = "history__result";
    result.textContent = `= ${item.result}`;

    li.append(expression, result);
    historyList.append(li);
  });
}
function addHistory(expression, result) {
  history.unshift({ expression, result });
  history = history.slice(0, MAX_HISTORY_ITEMS);
  saveHistory();
  renderHistory();
}
function showError(message = "") {
  errorDisplay.textContent = message;
}
function formatExpression(value) {
  return value.replace(/\*/g, "×").replace(/\//g, "÷");
}
function normalizedExpression(value) {
  return value.replace(/[×]/g, "*").replace(/[÷]/g, "/").replace(/[−]/g, "-");
}
function normalizeOperatorRuns(value) {
  // Keep only one binary operator in a run. A leading minus may start a
  // negative number; spaces are never added by the calculator.
  return value.replace(/[+*/×÷^−-]{2,}/g, (run, offset) => {
    if (offset === 0 && run.startsWith("-")) return "-";
    return run.slice(-1);
  });
}
function isCompleteExpression(raw) {
  const value = normalizedExpression(raw).trim();
  if (!value || /[+\-*/^.]$/.test(value)) return false;
  if (/[+*/^]\s*[+*/^]/.test(value)) return false;
  if (!/^[0-9+\-*/^().\s]+$/.test(value)) return false;
  if (!/[0-9)]$/.test(value)) return false;
  return true;
}
function evaluate(raw) {
  const source = normalizedExpression(raw).replace(/\s+/g, "");
  if (!isCompleteExpression(source)) throw new Error("Incomplete expression.");
  let index = 0;

  function parseExpression() {
    let value = parseTerm();
    while (source[index] === "+" || source[index] === "-") {
      const op = source[index++];
      const right = parseTerm();
      value = op === "+" ? value + right : value - right;
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
    }
    return value;
  }
  function parseUnary() {
    if (source[index] === "+") { index++; return parseUnary(); }
    if (source[index] === "-") { index++; return -parseUnary(); }
    return parsePower();
  }
  function parsePower() {
    const base = parsePrimary();
    if (source[index] === "^") {
      index++;
      const exponentText = source.slice(index).match(/^\d+/)?.[0];
      if (!exponentText) throw new Error("Enter an exponent from 1 to 99.");
      const exponent = Number(exponentText);
      if (exponent < 1 || exponent > 99) throw new Error("Too large");
      if (!Number.isInteger(base) || base < 0) throw new Error("Power base must be a non-negative whole number.");
      index += exponentText.length;
      const powered = Math.pow(base, exponent);
      if (!Number.isFinite(powered) || powered > 999999999999) throw new Error("Too large");
      return powered;
    }
    return base;
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
  const result = parseExpression();
  if (index !== source.length) throw new Error("Invalid expression.");
  if (!Number.isFinite(result) || Math.abs(result) > 999999999999) throw new Error("Too large");
  return Number.isInteger(result) ? result : Number(result.toPrecision(12));
}
function updatePreview() {
  const raw = expressionInput.value;
  preview.textContent = "";
  showError();
  if (!raw.trim()) return;
  display.textContent = "0";
  // A trailing operator is pending, not final; preview the valid prefix only.
  const previewExpression = raw.replace(/[+*/×÷^ −-]\s*$/, "").trim();
  if (!previewExpression || !isCompleteExpression(previewExpression)) return;
  try {
    const result = evaluate(previewExpression);
    if (Number.isFinite(Number(result))) preview.textContent = `≈ ${result}`;
  } catch (error) {
    if (error.message === "Too large") preview.textContent = "Too large";
    // Invalid or unfinished expressions should not show a misleading result.
  }
}
function clearAll() {
  expressionInput.value = "";
  display.textContent = "0";
  preview.textContent = "";
  justCalculated = false;
  lastCalculation = "";
  showError();
}
function insertAtSelection(text) {
  const input = expressionInput;
  const before = input.value;
  const isOperator = ["+", "-", "*", "/", "×", "÷", "−", "^"].includes(text);
  const last = before.trimEnd().slice(-1);

  if (isOperator) {
    if (!before.trim()) {
      if (text !== "-") return; // Only minus may start a negative number.
    } else if (["+", "*", "/", "×", "÷", "−", "^"].includes(last) || last === "-") {
      // Replace the pending operator. Never add whitespace or stack operators.
      if (before.length === 1 && last === "-") {
        input.value = text === "-" ? "-" : "";
      } else {
        input.value = before.slice(0, -1) + text;
      }
      input.setSelectionRange(input.value.length, input.value.length);
      justCalculated = false;
      display.textContent = "0";
      updatePreview();
      return;
    } else if (!/[0-9.)]$/.test(last)) {
      return;
    }
  }

  if (text === ".") {
    const currentNumber = before.split(/[+*/×÷()\s−-]/).pop() || "";
    if (currentNumber.includes(".")) return;
    if (!currentNumber) text = "0.";
  }

  input.value = before + text;
  input.setSelectionRange(input.value.length, input.value.length);
  justCalculated = false;
  display.textContent = "0";
  updatePreview();
}
function enterDigit(digit) {
  if (justCalculated) {
    expressionInput.value = "";
    justCalculated = false;
  }
  insertAtSelection(digit);
}
function enterOperator(operator) {
  // Display calculator symbols to the user; normalizedExpression converts them internally for evaluation.
  operator = ({ "*": "×", "/": "÷", "-": "−" })[operator] || operator;
  if (justCalculated) {
    expressionInput.value = display.textContent;
    expressionInput.setSelectionRange(expressionInput.value.length, expressionInput.value.length);
    justCalculated = false;
  }
  insertAtSelection(operator);
}
function enterDecimal() {
  const input = expressionInput;
  const left = input.value;
  const currentNumber = left.trimEnd().split(/[+\-*/×÷()\s−]/).pop() || "";
  if (currentNumber.includes(".")) return;
  insertAtSelection(currentNumber ? "." : "0.");
}
function backspace() {
  const input = expressionInput;
  const keypadTriggered = document.activeElement !== input;
  const value = input.value;
  if (!value) {
    showError();
    preview.textContent = "";
    return;
  }

  let start;
  let end;
  if (keypadTriggered) {
    // Clicking the keypad moves focus away from the input; ignore its stale caret
    // and consistently remove the rightmost character.
    end = value.length;
    start = end - 1;
  } else {
    start = input.selectionStart ?? value.length;
    end = input.selectionEnd ?? start;
    if (start === end) {
      if (start === 0) return;
      start -= 1;
    }
  }

  input.value = value.slice(0, start) + value.slice(end);
  input.focus();
  const caret = start;
  input.setSelectionRange(caret, caret);
  justCalculated = false;
  showError();
  if (input.value.trim()) display.textContent = "0";
  else display.textContent = "0";
  updatePreview();
}
function enterPower() {
  const input = expressionInput;
  if (justCalculated) {
    const result = display.textContent;
    if (!/^\d+$/.test(result)) {
      showError("Power base must be a non-negative whole number.");
      return;
    }
    input.value = result + "^";
    justCalculated = false;
    display.textContent = "0";
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    updatePreview();
    return;
  }
  const match = input.value.match(/(\d+)$/);
  if (!match) return;
  const base = Number(match[1]);
  if (!Number.isInteger(base) || base < 0) {
    showError("Power base must be a non-negative whole number.");
    return;
  }
  input.value += "^";
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
  showError();
  display.textContent = "0";
  updatePreview();
}
function calculateResult() {
  const raw = expressionInput.value.trim();
  // After a successful calculation the expression field is intentionally blank.
  // Pressing equals again should do nothing until the user starts a new operation.
  if (!raw) return;
  if (!isCompleteExpression(raw)) {
    showError("Complete the expression before pressing =.");
    return;
  }
  try {
    const result = String(evaluate(raw));
    display.textContent = result;
    preview.textContent = "";
    addHistory(raw, result);
    expressionInput.value = "";
    lastCalculation = raw;
    justCalculated = true;
    showError();
  } catch (error) {
    showError(error.message || "Unable to calculate.");
  }
}

expressionInput.addEventListener("input", () => {
  const input = expressionInput;
  const caret = input.selectionStart ?? input.value.length;
  const allowed = input.value
    .replace(/\s+/g, "")
    .replace(/[^0-9+*/×÷^ .−-]/g, "")
    .replace(/[()]/g, "");
  const cleaned = normalizeOperatorRuns(allowed);
  if (cleaned !== input.value) {
    const prefix = normalizeOperatorRuns(allowed.slice(0, caret));
    input.value = cleaned;
    const safeCaret = Math.min(prefix.length, input.value.length);
    input.setSelectionRange(safeCaret, safeCaret);
  }
  justCalculated = false;
  if (input.value.trim()) display.textContent = "0";
  updatePreview();
});
expressionInput.addEventListener("keydown", (event) => {
  if (event.key === "(" || event.key === ")") {
    event.preventDefault();
    return;
  }
  if (["+", "-", "*", "/", "^", "×", "÷", "−"].includes(event.key)) {
    event.preventDefault();
    enterOperator(event.key);
  } else if (event.key === "Backspace") {
    event.preventDefault();
    backspace();
  } else if (event.key === "Enter" || event.key === "=") {
    event.preventDefault();
    calculateResult();
  } else if (event.key === "Escape") {
    event.preventDefault();
    clearAll();
  }
});
keypad.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.digit !== undefined) enterDigit(button.dataset.digit);
  else if (button.dataset.operator) enterOperator(button.dataset.operator);
  else {
    switch (button.dataset.action) {
      case "clear": clearAll(); break;
      case "backspace": backspace(); break;
      case "decimal": enterDecimal(); break;
      case "sign": enterPower(); break;
      case "equals": calculateResult(); break;
    }
  }
});
clearHistoryButton.addEventListener("click", () => {
  history = [];
  saveHistory();
  renderHistory();
});

let historyOpen = false;
function setHistoryOpen(open) {
  historyOpen = open;
  historyDrawer.classList.toggle("is-open", open);
  historyDrawer.setAttribute("aria-hidden", String(!open));
  historyToggle.setAttribute("aria-expanded", String(open));
  historyToggle.setAttribute("aria-label", open ? "Hide calculation history" : "Show calculation history");
}
historyToggle.addEventListener("click", () => setHistoryOpen(!historyOpen));

document.addEventListener("keydown", (event) => {
  if (document.activeElement === expressionInput) return;
  if (/^[0-9.]$/.test(event.key)) { event.preventDefault(); event.key === "." ? enterDecimal() : enterDigit(event.key); expressionInput.focus(); }
  else if (["+", "-", "*", "/", "^"].includes(event.key)) { event.preventDefault(); enterOperator(event.key); expressionInput.focus(); }
  else if (event.key === "Enter" || event.key === "=") { event.preventDefault(); calculateResult(); }
  else if (event.key === "Backspace") { event.preventDefault(); backspace(); expressionInput.focus(); }
  else if (event.key === "Escape") { event.preventDefault(); clearAll(); }
});

const rootButton = keypad.querySelector('[data-action="sign"]');
if (rootButton) {
  rootButton.textContent = "xʸ";
  rootButton.setAttribute("aria-label", "Power");
}
renderHistory();
clearAll();
