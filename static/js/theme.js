// theme.js
document.addEventListener("DOMContentLoaded", () => {
  document.body.classList.add("dark");
});
document.addEventListener("click", (event) => {
  const target = event.target.closest("button, a, input[type='submit']");

  if (!target) return;

  // Extract meaningful info
  const tag = target.tagName.toLowerCase();
  const text = target.innerText.trim().slice(0, 100); // avoid massive texts
  const href = target.getAttribute("href") || null;
  const action = `Clicked ${tag.toUpperCase()}`;

  // Log interaction
  logInteraction(action, { text, href });
});
function logInteraction(action, details = {}) {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  fetch("/log-interaction", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken
    }
    body: JSON.stringify({ action, details })
  }).catch(err => console.warn("Logging failed:", err));
}
