// theme.js
function toggleDarkMode() {
  const body = document.body;
  const label = document.getElementById("darkmode-label");
  const isDark = body.classList.toggle("dark");
  localStorage.setItem("theme", isDark ? "dark" : "light");
  if (label) label.textContent = isDark ? "Light Mode" : "Dark Mode";
}

// Apply saved theme BEFORE DOM paints
(function () {
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme === "dark") {
    document.documentElement.classList.add("dark");
    document.body.classList.add("dark");
  }
})();

// Apply label update AFTER DOM loads
document.addEventListener("DOMContentLoaded", () => {
  const isDark = document.body.classList.contains("dark");
  const label = document.getElementById("darkmode-label");
  if (label) label.textContent = isDark ? "Light Mode" : "Dark Mode";
});
