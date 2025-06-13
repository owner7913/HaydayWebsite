function toggleDarkMode() {
  const body = document.body;
  const toggleBtn = document.querySelector(".theme-toggle");

  if (body.classList.contains("dark")) {
    body.classList.remove("dark");
    body.classList.add("light");
    localStorage.setItem("theme", "light");
    if (toggleBtn) toggleBtn.textContent = "🌙 Toggle Dark Mode";
  } else {
    body.classList.remove("light");
    body.classList.add("dark");
    localStorage.setItem("theme", "dark");
    if (toggleBtn) toggleBtn.textContent = "☀️ Toggle Light Mode";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const savedTheme = localStorage.getItem("theme") || "light";
  document.body.classList.remove("light", "dark");
  document.body.classList.add(savedTheme);

  const btn = document.querySelector(".theme-toggle");
  if (btn) {
    const isDark = document.body.classList.contains("dark");
    btn.textContent = isDark ? "☀️ Toggle Light Mode" : "🌙 Toggle Dark Mode";
    btn.addEventListener("click", toggleDarkMode);
  }
});
