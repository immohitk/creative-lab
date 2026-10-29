
const clock = document.getElementById("clock");
const date = document.getElementById("date");
const button12 = document.getElementById("format12");
const button24 = document.getElementById("format24");
const themeSelect = document.getElementById("themeSelect");

const validThemes = ["midnight", "light", "forest"];

let use24Hour = localStorage.getItem("clock-format") === "24";
let currentTime = new Date();

function updateFormatButtons() {
  button12.classList.toggle("active", !use24Hour);
  button24.classList.toggle("active", use24Hour);

  button12.setAttribute("aria-pressed", String(!use24Hour));
  button24.setAttribute("aria-pressed", String(use24Hour));

  clock.setAttribute(
    "aria-label",
    `Current time. ${use24Hour ? "24-hour" : "12-hour"} format. Click to switch format.`
  );
}

function applyTheme(theme) {
  const selectedTheme = validThemes.includes(theme) ? theme : "midnight";

  document.documentElement.dataset.theme = selectedTheme;
  themeSelect.value = selectedTheme;
  localStorage.setItem("clock-theme", selectedTheme);
}

function renderClock(now) {
  if (window.ClockEngine) {
    clock.textContent = window.ClockEngine.formatTime(now, use24Hour);
    date.textContent = window.ClockEngine.formatDate(now);
  } else {
    clock.textContent = now.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: !use24Hour,
    });

    date.textContent = now.toLocaleDateString(undefined, {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }
}

function updateClock() {
  currentTime = new Date();
  renderClock(currentTime);
}

function setFormat(value) {
  if (use24Hour === value) return;

  use24Hour = value;
  localStorage.setItem("clock-format", use24Hour ? "24" : "12");

  updateFormatButtons();
  renderClock(currentTime);
}

button12.addEventListener("click", () => setFormat(false));
button24.addEventListener("click", () => setFormat(true));
clock.addEventListener("click", () => setFormat(!use24Hour));

themeSelect.addEventListener("change", () => {
  applyTheme(themeSelect.value);
});

applyTheme(localStorage.getItem("clock-theme") || "midnight");
updateFormatButtons();
updateClock();

setInterval(updateClock, 1000);
