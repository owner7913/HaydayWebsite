document.addEventListener("DOMContentLoaded", () => {
  function updateCountdown() {
    const now = Math.floor(Date.now() / 1000);
    document.querySelectorAll(".countdown").forEach(el => {
      const end = parseInt(el.dataset.end);
      const diff = end - now;
      if (diff <= 0) {
        el.textContent = "⏰ Ended";
      } else {
        const hrs = Math.floor(diff / 3600);
        const mins = Math.floor((diff % 3600) / 60);
        const secs = diff % 60;
        el.textContent = `${hrs}h ${mins}m ${secs}s`;
      }
    });
  }
  updateCountdown();
  setInterval(updateCountdown, 1000);
});