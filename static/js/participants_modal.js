function openParticipantsModal(index) {
  const modal = document.getElementById("modal-" + index);
  modal.classList.add("show");
  loadParticipantPage(index, 1);
}

function closeParticipantsModal(index) {
  document.getElementById("modal-" + index).classList.remove("show");
}

function loadParticipantPage(index, page) {
  const container = document.getElementById("participant-list-" + index);
  const searchValue = document.getElementById("search-input-" + index).value.toLowerCase();
  const allRows = Array.from(container.querySelectorAll(".participant-row"));
  const perPage = 12;

  let filtered = allRows.filter(row =>
    row.dataset.name.toLowerCase().includes(searchValue)
  );

  filtered.sort((a, b) => parseInt(b.dataset.entries) - parseInt(a.dataset.entries));

  allRows.forEach(row => row.style.display = "none");

  const totalPages = Math.ceil(filtered.length / perPage);
  const start = (page - 1) * perPage;
  const end = start + perPage;
  filtered.slice(start, end).forEach(row => row.style.display = "flex");

  const pagination = document.getElementById("pagination-" + index);
  pagination.innerHTML = "";

  if (page > 1) {
    const prev = document.createElement("button");
    prev.textContent = "⬅ Prev";
    prev.onclick = () => loadParticipantPage(index, page - 1);
    pagination.appendChild(prev);
  }

  pagination.appendChild(document.createTextNode(" Page " + page + " of " + totalPages + " "));

  if (page < totalPages) {
    const next = document.createElement("button");
    next.textContent = "Next ➡";
    next.onclick = () => loadParticipantPage(index, page + 1);
    pagination.appendChild(next);
  }
}

document.addEventListener("keydown", function(event) {
  if (event.key === "Escape") {
    document.querySelectorAll(".participants-modal.show").forEach(modal => {
      modal.classList.remove("show");
    });
  }
});