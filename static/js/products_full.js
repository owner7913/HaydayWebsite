let products = [];

async function loadProducts() {
  try {
    const res = await fetch("/api/production-data");
    products = await res.json();

    // Populate machine dropdown
    const machineSet = new Set(products.map(p => p.machine).filter(Boolean));
    const machineFilter = document.getElementById("machineFilter");
    machineFilter.innerHTML = '<option value="all">All Machines</option>';
    Array.from(machineSet).sort().forEach(machine => {
      const opt = document.createElement("option");
      opt.value = machine.toLowerCase();
      opt.textContent = machine;
      machineFilter.appendChild(opt);
    });

    // Auto-generate on load
    generateSuggestions();
  } catch (err) {
    console.error("❌ Failed to load products:", err);
  }
}

window.addEventListener("DOMContentLoaded", loadProducts);
