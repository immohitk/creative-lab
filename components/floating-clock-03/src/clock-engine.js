function formatTime(date, use24Hour = false) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: !use24Hour
  }).format(date);
}
function formatDate(date) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long", year: "numeric", month: "long", day: "numeric"
  }).format(date);
}
if (typeof module !== "undefined" && module.exports) module.exports = { formatTime, formatDate };
if (typeof window !== "undefined") window.ClockEngine = { formatTime, formatDate };
