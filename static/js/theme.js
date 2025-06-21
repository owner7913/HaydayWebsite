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
document.addEventListener("DOMContentLoaded", () => {
  const winglet = document.getElementById("discord-winglet");

  if (winglet) {
    const LAST_SHOWN_KEY = "wingletLastShown";
    const now = Date.now();
    const cooldown = 10 * 60 * 1000; // 10 minutes

    const lastShown = parseInt(sessionStorage.getItem(LAST_SHOWN_KEY), 10);

    // Only show if it's been more than 10 minutes
    if (!lastShown || (now - lastShown > cooldown)) {
      function toggleWinglet() {
        winglet.classList.add("show");
        setTimeout(() => winglet.classList.remove("show"), 12000); // visible 12s
        sessionStorage.setItem(LAST_SHOWN_KEY, Date.now().toString());
      }

      setTimeout(toggleWinglet, 20000); // show after 20s
    }
  }
});



