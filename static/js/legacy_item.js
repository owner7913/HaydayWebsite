/* legacy_item.js
   Minimal, UI-agnostic utilities + Item model (ported from the old repo)
   Requires: math.js (load BEFORE this file)
*/
(function (global) {
  // ---------- helpers ----------
  function normalizeName(name) {
    return (name || "")
      .replace(/[\u200B-\u200D\uFEFF]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }
  function convertToTitleSnakeCase(str) {
    // "brown sugar" -> "Brown_Sugar"
    const s = normalizeName(str).toLowerCase();
    return s
      .split(" ")
      .filter(Boolean)
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join("_");
  }

  // ---------- name formatting (keep these globals similar to old repo) ----------
  // 1) Abbreviations from your old repo.
  //    If you have a big mapping in Item.js, paste it here.
  //    You can add entries over time, e.g. ["bs","Brown Sugar"]
  const abbreviationMapping = new Map([
    // ["bs", "Brown Sugar"],
    // ["cpc", "Carrot Pie"],
  ]);

  // 2) Names with special casing (copy any odd cases from the old file).
  const specialNameMapping = new Map([
    ["Tnt_Barrel", "TNT_Barrel"],
    ["Blt_Salad", "BLT_Salad"],
    ["Bacon_And_Eggs", "Bacon_and_Eggs"],
    ["Fish_And_Chips", "Fish_and_Chips"],
    ["Peanut_Butter_And_Jelly_Sandwich", "Peanut_Butter_and_Jelly_Sandwich"],
    ["Frutti_Di_Mare_Pizza", "Frutti_di_Mare_Pizza"],
  ]);

  const customItemNames = new Set(["BEM Set", "SEM Set", "TEM Set", "LEM Set"]);
  function setUpCustomItems() {
    for (const name of customItemNames) {
      specialNameMapping.set(convertToTitleSnakeCase(name), name);
    }
  }

  function handleAbbreviations(name) {
    return abbreviationMapping.get(name.toLowerCase()) ?? name;
  }
  function handleSpecialNames(titleSnake) {
    return specialNameMapping.get(titleSnake) ?? titleSnake;
  }
  function formatItemName(input) {
    const trimmed = normalizeName(input);
    if (!trimmed) return trimmed;
    const unabbrev = handleAbbreviations(trimmed);
    const titleSnake = convertToTitleSnakeCase(unabbrev);
    return handleSpecialNames(titleSnake);
  }

  // ---------- Item model (price math & pretty name) ----------
  // Constructor mirrors your old Item(name, quantity, url, priceOrMultiplier, maxPrice)
  class Item {
    static fieldsToOmitFromLocalStorage = new Set([
      "customQuantity",
      "customPriceOrMultiplier",
      "isSelected",
    ]);

    constructor(name, quantity, url, priceOrMultiplier, maxPrice) {
      this.name = name;                // Title_Snake_Case or snake_case
      this.quantity = quantity;        // default qty
      this.url = url || "";
      this.priceOrMultiplier = (priceOrMultiplier ?? "1x").toString();
      this.maxPrice = Number(maxPrice) || 0;

      // session-only fields
      this.customQuantity = undefined;
      this.customPriceOrMultiplier = undefined;
      this.isSelected = false;
    }

    getHumanReadableName() {
      return (this.name || "").replaceAll("_", " ");
    }

    // Returns [totalPriceNumber, equationString, errorMessageOrNull, warningMessageOrNull]
    calculateTotalPrice(shouldIgnoreCustomValues = false) {
      let quantity = this.customQuantity ?? this.quantity;
      let priceOrMult = this.customPriceOrMultiplier ?? this.priceOrMultiplier;
      const maxPrice = this.maxPrice;

      if (shouldIgnoreCustomValues) {
        quantity = this.quantity;
        priceOrMult = this.priceOrMultiplier;
      }

      // Guard rails
      if (!Number.isFinite(maxPrice) || maxPrice <= 0) {
        return [NaN, "NaN", `${this.getHumanReadableName()} doesn't have a valid maximum price (${maxPrice}).`];
      }

      // normalize inputs
      priceOrMult = String(priceOrMult || "").trim();
      let warning;

      // interpret priceOrMult
      let unitPriceExpr; // string expression for math.js
      if (!priceOrMult.length) {
        unitPriceExpr = `${maxPrice}*(1)`; // default to 1x
        warning = `The price/multiplier for ${this.getHumanReadableName()} was empty, so it was defaulted to 1x.`;
      } else if (priceOrMult.endsWith("x")) {
        // multiplier mode -> maxPrice * mult
        const mult = priceOrMult.slice(0, -1); // "1.5x" -> "1.5"
        if (!mult.trim().length) {
          return [NaN, "NaN", `Invalid multiplier for ${this.getHumanReadableName()}.`];
        }
        unitPriceExpr = `${maxPrice}*(${mult})`;
      } else {
        // direct price mode, supports "2k", "1.2m" and full expressions
        let p = priceOrMult;
        if (/k$/i.test(p)) p = `(${p.slice(0, -1)})*10^3`;
        else if (/m$/i.test(p)) p = `(${p.slice(0, -1)})*10^6`;
        unitPriceExpr = p;
      }

      // Coerce quantity; allow expressions like "+5" to adjust
      let qtyExpr = String(quantity ?? 0);
      // sanitize quantity: if looks like an expression, evaluate; else number
      let qty;
      try {
        qty = Math.floor(global.math ? global.math.evaluate(qtyExpr) : Number(qtyExpr));
      } catch {
        qty = Math.floor(Number(qtyExpr));
      }
      if (!Number.isFinite(qty) || qty < 0) qty = 0;

      // Final evaluation
      let unitPrice, total;
      try {
        unitPrice = global.math ? global.math.evaluate(unitPriceExpr) : Number(unitPriceExpr);
      } catch (e) {
        return [NaN, "NaN", `Invalid price expression "${priceOrMult}" for ${this.getHumanReadableName()}.`];
      }

      if (!Number.isFinite(unitPrice) || unitPrice < 0) {
        return [NaN, "NaN", `Invalid unit price for ${this.getHumanReadableName()}.`];
      }

      total = Math.floor(qty * unitPrice);
      const equation = `${qty} * (${unitPriceExpr})`;

      return [total, equation, null, warning];
    }
  }

  // expose to window
  global.normalizeItemName = normalizeName;
  global.convertToTitleSnakeCase = convertToTitleSnakeCase;
  global.formatItemName = formatItemName;
  global.handleAbbreviations = handleAbbreviations;
  global.handleSpecialNames = handleSpecialNames;
  global.setUpCustomItems = setUpCustomItems;
  global.Item = Item;
})(window);
