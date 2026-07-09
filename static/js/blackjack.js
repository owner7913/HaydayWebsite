(function () {
  const app = document.getElementById("blackjack-app");
  if (!app) return;

  const viewerId = Number(app.dataset.viewerId || 0);
  const lobbyList = document.getElementById("blackjack-table-list");
  const liveRoot = document.getElementById("blackjack-live");
  const balanceNode = document.getElementById("blackjack-balance");
  const activeTitle = document.getElementById("blackjack-active-title");
  const activeCopy = document.getElementById("blackjack-active-copy");
  const leaveBtn = document.getElementById("blackjack-leave-btn");
  const createForm = document.getElementById("blackjack-create-form");
  const refreshLobbyBtn = document.getElementById("blackjack-refresh-lobby");
  const sidebarToggleBtn = document.getElementById("blackjack-sidebar-toggle");
  const disclaimerOverlay = document.getElementById("blackjack-disclaimer");
  const disclaimerAcceptBtn = document.getElementById("blackjack-disclaimer-accept");
  const reportBtn = document.getElementById("blackjack-report-btn");
  const reportOverlay = document.getElementById("blackjack-report-overlay");
  const reportReasonInput = document.getElementById("blackjack-report-reason");
  const reportSubmitBtn = document.getElementById("blackjack-report-submit");
  const reportCancelBtn = document.getElementById("blackjack-report-cancel");
  const rulesOverlay = document.getElementById("blackjack-rules-overlay");
  const rulesCloseBtn = document.getElementById("blackjack-rules-close");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const isAdmin = app.dataset.isAdmin === "true";
  const disclaimerKey = "blackjack-disclaimer-v1";

  const suitCodes = {
    spades: "S",
    hearts: "H",
    diamonds: "D",
    clubs: "C",
  };

  let activeTableId = app.dataset.activeTableId || "";
  let tableTimer = null;
  const renderedCardKeys = new Set();
  let countdownTimer = null;
  let chatCollapsed = window.matchMedia("(max-width: 980px)").matches;
  let unreadChatCount = 0;
  const seenChatIds = new Set();
  let lastRenderedTable = null;
  let sidebarCollapsed = window.matchMedia("(max-width: 980px)").matches;

  function formatNumber(value) {
    return new Intl.NumberFormat().format(Number(value || 0));
  }

  function setBalance(value) {
    document.querySelectorAll("[data-blackjack-balance]").forEach((node) => {
      node.textContent = formatNumber(value);
    });
  }

  function formatSignedNumber(value) {
    const amount = Number(value || 0);
    const sign = amount > 0 ? "+" : amount < 0 ? "-" : "";
    return `${sign}${formatNumber(Math.abs(amount))}`;
  }

  function sessionPnlClass(value) {
    const amount = Number(value || 0);
    if (amount > 0) return "win";
    if (amount < 0) return "loss";
    return "even";
  }

  function setSidebarCollapsed(value) {
    sidebarCollapsed = Boolean(value);
    app.classList.toggle("sidebar-collapsed", sidebarCollapsed);
    if (sidebarToggleBtn) {
      sidebarToggleBtn.textContent = sidebarCollapsed ? "Show setup" : "Hide setup";
    }
  }

  function hasAcceptedDisclaimer() {
    try {
      return window.localStorage.getItem(disclaimerKey) === "accepted";
    } catch (error) {
      return false;
    }
  }

  function setDisclaimerAccepted() {
    try {
      window.localStorage.setItem(disclaimerKey, "accepted");
    } catch (error) {
      // ignore storage failures
    }
    disclaimerOverlay?.classList.add("hidden");
    document.body.classList.remove("no-scroll");
  }

  function setReportModalOpen(value) {
    const isOpen = Boolean(value);
    reportOverlay?.classList.toggle("hidden", !isOpen);
    if (isOpen) {
      document.body.classList.add("no-scroll");
      setTimeout(() => reportReasonInput?.focus(), 0);
    } else if (hasAcceptedDisclaimer()) {
      document.body.classList.remove("no-scroll");
    }
  }

  function setRulesModalOpen(value) {
    const isOpen = Boolean(value);
    rulesOverlay?.classList.toggle("hidden", !isOpen);
    if (isOpen) {
      document.body.classList.add("no-scroll");
    } else if (hasAcceptedDisclaimer() && reportOverlay?.classList.contains("hidden")) {
      document.body.classList.remove("no-scroll");
    }
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds || 0)));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return mins ? `${mins}:${String(secs).padStart(2, "0")}` : `${secs}s`;
  }

  function secondsUntil(isoString) {
    if (!isoString) return null;
    const target = new Date(isoString).getTime();
    if (!Number.isFinite(target)) return null;
    return Math.max(0, Math.ceil((target - Date.now()) / 1000));
  }

  async function api(url, options) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Request failed");
    }
    return data;
  }

  function updateUrl() {
    const url = new URL(window.location.href);
    if (activeTableId) {
      url.searchParams.set("table", activeTableId);
    } else {
      url.searchParams.delete("table");
    }
    window.history.replaceState({}, "", url);
  }

  function suitClass(card) {
    if (!card || !card.suit) return "";
    return String(card.suit);
  }

  function toCardMeisterCid(card) {
    if (!card || card.label === "??" || card.suit === "hidden") return null;
    const rank = String(card.rank || "").toUpperCase();
    const suitCode = suitCodes[String(card.suit || "")];
    if (!rank || !suitCode) return null;
    return `${rank}${suitCode}`;
  }

  function cardAnimationClass(cardKey, card, revealedFromHidden) {
    if (!renderedCardKeys.has(cardKey)) {
      renderedCardKeys.add(cardKey);
      if (revealedFromHidden) return "flip";
      return card?.suit === "hidden" ? "deal flip" : "deal";
    }
    return "";
  }

  function renderCards(areaKey, cards, options = {}) {
    if (!cards || !cards.length) return '<div class="blackjack-copy">No cards yet.</div>';
    const isFan = Boolean(options.fan);
    const midpoint = (cards.length - 1) / 2;
    const isCompactFan = Boolean(options.compactFan);
    const fanSpread = isFan ? (isCompactFan ? Math.min(6.5, 3.5 + cards.length * 0.6) : Math.min(14, 8 + cards.length * 1.5)) : 0;
    const fanLiftScale = isFan ? (isCompactFan ? Math.min(4.5, 2 + cards.length * 0.45) : Math.min(11, 5 + cards.length)) : 0;
    return `<div class="blackjack-card-row ${isFan ? "fan" : ""}">${cards.map((card, index) => {
      const cardKey = `${areaKey}:${index}:${card.label || "??"}`;
      const hiddenKey = `${areaKey}:${index}:??`;
      const revealedFromHidden = card.label !== "??" && renderedCardKeys.has(hiddenKey);
      const animationClass = cardAnimationClass(cardKey, card, revealedFromHidden);
      const cid = toCardMeisterCid(card);
      const angle = isFan ? (index - midpoint) * fanSpread : 0;
      const lift = isFan ? Math.abs(index - midpoint) * fanLiftScale : 0;
      const fanClass = isFan ? `fan-slot ${isCompactFan ? "compact" : ""}` : "";
      const fanStyle = isFan ? `style="--fan-angle:${angle}deg; --fan-lift:${lift}px; z-index:${index + 1};"` : "";
      return `
        <div class="blackjack-card ${suitClass(card)} ${card.suit === "hidden" ? "hidden" : ""} ${animationClass} ${fanClass}" ${fanStyle}>
          <div class="blackjack-card-inner">
            <div class="blackjack-card-face">
              ${cid ? `<playing-card cid="${cid}"></playing-card>` : ""}
            </div>
            <div class="blackjack-card-back"></div>
          </div>
        </div>
      `;
    }).join("")}</div>`;
  }

  function resultLabel(result) {
    const map = {
      win: "Win",
      loss: "Loss",
      push: "Push",
      blackjack: "Blackjack",
      dealer_blackjack: "Dealer Blackjack",
    };
    return map[result] || "";
  }

  function renderResultBanner(hand) {
    if (!hand?.result) return "";
    const payout = Number(hand.payout || 0);
    const betAmount = Number(hand.bet_amount || 0);
    const net = payout - betAmount;
    if (hand.result === "win" || hand.result === "blackjack") {
      return `<div class="blackjack-result-banner win">Win +${formatNumber(net)}</div>`;
    }
    if (hand.result === "push") {
      return `<div class="blackjack-result-banner push">Push 0</div>`;
    }
    return `<div class="blackjack-result-banner loss">Loss -${formatNumber(betAmount)}</div>`;
  }

  function statusLabel(status) {
    const map = {
      waiting: "waiting",
      waiting_next_hand: "waiting next hand",
      playing: "playing",
      done: "done",
      timed_out: "timed out",
      insufficient_funds: "insufficient funds",
    };
    return map[status] || String(status || "waiting").replaceAll("_", " ");
  }

  function formatClock(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function captureDraftState() {
    const active = document.activeElement;
    const activeId = active?.id || "";
    return {
      activeId,
      seatBetValue: document.getElementById("blackjack-seat-bet-input")?.value ?? "",
      autoBetValue: document.getElementById("blackjack-auto-bet-amount")?.value ?? "",
      autoBetEnabled: document.getElementById("blackjack-auto-bet-enabled")?.checked ?? false,
      chatValue: document.getElementById("blackjack-chat-input")?.value ?? "",
      selectionStart: typeof active?.selectionStart === "number" ? active.selectionStart : null,
      selectionEnd: typeof active?.selectionEnd === "number" ? active.selectionEnd : null,
    };
  }

  function restoreDraftState(state) {
    if (!state) return;
    const seatBetInput = document.getElementById("blackjack-seat-bet-input");
    const autoBetInput = document.getElementById("blackjack-auto-bet-amount");
    const autoBetToggle = document.getElementById("blackjack-auto-bet-enabled");
    const chatInput = document.getElementById("blackjack-chat-input");
    if (seatBetInput && state.seatBetValue !== "") seatBetInput.value = state.seatBetValue;
    if (autoBetInput && state.autoBetValue !== "") autoBetInput.value = state.autoBetValue;
    if (autoBetToggle) autoBetToggle.checked = Boolean(state.autoBetEnabled);
    if (chatInput && state.chatValue !== "") chatInput.value = state.chatValue;
    const active = state.activeId ? document.getElementById(state.activeId) : null;
    if (active) {
      active.focus({ preventScroll: true });
      if (typeof state.selectionStart === "number" && typeof active.setSelectionRange === "function") {
        active.setSelectionRange(state.selectionStart, state.selectionEnd ?? state.selectionStart);
      }
    }
  }

  function trackChat(table) {
    let incoming = 0;
    for (const message of orderedChatMessages(table.chat || [])) {
      if (!message?.id || seenChatIds.has(message.id)) continue;
      seenChatIds.add(message.id);
      if (chatCollapsed && message.kind !== "system" && Number(message.user_id || 0) !== viewerId) {
        incoming += 1;
      }
    }
    if (incoming) unreadChatCount += incoming;
    if (!chatCollapsed) unreadChatCount = 0;
  }

  function orderedChatMessages(messages) {
    return [...(messages || [])].sort((a, b) => {
      const aTime = a?.ts ? new Date(a.ts).getTime() : 0;
      const bTime = b?.ts ? new Date(b.ts).getTime() : 0;
      if (aTime !== bTime) return aTime - bTime;
      return String(a?.id || "").localeCompare(String(b?.id || ""));
    });
  }

  function renderChat(table) {
    const messages = orderedChatMessages(table.chat || []);
    return `
      <aside class="blackjack-chat-panel ${chatCollapsed ? "collapsed" : ""}">
        <div class="blackjack-chat-head">
          <div class="blackjack-chat-title">
            <strong>${chatCollapsed ? "Chat" : "Table chat"}</strong>
            <span class="blackjack-unread-badge ${unreadChatCount ? "" : "hidden"}">${unreadChatCount}</span>
          </div>
          <span class="blackjack-copy">${table.players.length}/${table.max_players} seated</span>
          <button class="blackjack-button alt blackjack-chat-toggle" id="blackjack-chat-toggle" type="button">${chatCollapsed ? "Open" : "Hide"}</button>
        </div>
        <div class="blackjack-chat-log" id="blackjack-chat-log">
          ${messages.length ? messages.map((message) => `
            <div class="blackjack-chat-msg ${message.kind === "system" ? "system" : ""}">
              ${message.kind === "system" ? "" : `<img class="blackjack-chat-avatar" src="${message.avatar_url || "https://cdn.discordapp.com/embed/avatars/0.png"}" alt="">`}
              <div class="blackjack-chat-bubble">
                <p class="blackjack-chat-name">${message.kind === "system" ? "Table" : `${message.username || "Player"} · ${formatClock(message.ts)}`}</p>
                <p class="blackjack-chat-text">${message.text || ""}</p>
              </div>
            </div>
          `).join("") : '<div class="blackjack-empty">No chat yet.</div>'}
        </div>
        <form class="blackjack-chat-form" id="blackjack-chat-form">
          <input class="blackjack-input" id="blackjack-chat-input" maxlength="300" placeholder="Message the table">
          <button class="blackjack-button" type="submit">Send</button>
        </form>
      </aside>
    `;
  }

  function renderViewerControls(table) {
    const player = table.viewer_player;
    if (!player) {
      if (table.viewer_role === "observer") {
        return `
          <div class="blackjack-empty">You are watching this table.</div>
          <div class="blackjack-actions">
            <button class="blackjack-button" id="blackjack-join-seat" type="button">Join table</button>
          </div>
        `;
      }
      return `
        <div class="blackjack-empty">Watch the table or take a seat to join the next betting window.</div>
        <div class="blackjack-actions">
          <button class="blackjack-button alt" id="blackjack-watch-table" type="button">Watch table</button>
          <button class="blackjack-button" id="blackjack-join-seat" type="button">Join table</button>
        </div>
      `;
    }
    return "";
  }

  function renderViewerHand(table) {
    return "";
  }

  function tableTimerText(table) {
    const turnRemaining = secondsUntil(table.turn_deadline_at);
    if (turnRemaining !== null) return `Turn ${formatDuration(turnRemaining)}`;
    const nextHandRemaining = secondsUntil(table.auto_redeal_at);
    if (nextHandRemaining !== null) return `Next hand ${formatDuration(nextHandRemaining)}`;
    const autoStartRemaining = secondsUntil(table.auto_start_at);
    if (autoStartRemaining !== null) return `Hand starts ${formatDuration(autoStartRemaining)}`;
    return `Turn time ${formatDuration(table.turn_time_seconds)}`;
  }

  function renderSeatBetControls(player, table) {
    if (Number(player.user_id) !== viewerId) return "";
    if (table.phase !== "betting") return "";
    const isLiveRound = Number(player.reserved_bet || 0) > 0;
    const stagedBet = isLiveRound ? Number(player.next_bet || 0) : Number(player.bet || 0);
    const currentBetPlaced = !isLiveRound && table.phase === "betting" && stagedBet > 0;
    const quickBets = [25, 100, 250, 500];
    if (currentBetPlaced) {
      return `
        <div class="blackjack-seat-bet-controls compact">
          <div class="blackjack-bet-note">
            Bet placed: ${formatNumber(stagedBet)}. Waiting for the rest of the table.
          </div>
        </div>
      `;
    }
    return `
      <div class="blackjack-seat-bet-controls">
        <div class="blackjack-chip-row">
          ${quickBets.map((amount) => `
            <button class="blackjack-chip-button ${stagedBet === amount ? "active" : ""}" type="button" data-chip-bet="${amount}">
              <span>${formatNumber(amount)}</span>
            </button>
          `).join("")}
        </div>
        <div class="blackjack-seat-bet-custom">
          <input class="blackjack-input" id="blackjack-seat-bet-input" type="number" min="${table.min_bet}" step="1" placeholder="Custom amount" value="${stagedBet || ""}">
          <button class="blackjack-button alt" id="blackjack-seat-bet-save" type="button">${isLiveRound ? "Save next" : "Bet"}</button>
        </div>
        <div class="blackjack-bet-note">
          ${isLiveRound
            ? `Current hand is locked at ${formatNumber(player.reserved_bet)}. Set the next one here.`
            : `Place your bet here before the next hand starts. Minimum ${formatNumber(table.min_bet)}.`}
        </div>
      </div>
    `;
  }

  function renderSeatAutoBetToggle(player, table) {
    if (Number(player.user_id) !== viewerId) return "";
    const rememberedBet = Number(player.next_bet || player.bet || player.auto_bet_amount || table.min_bet || 0);
    return `
      <label class="blackjack-seat-auto-toggle" title="Auto bet your selected amount each round">
        <input id="blackjack-auto-bet-enabled" type="checkbox" ${player.auto_bet_enabled ? "checked" : ""}>
        <span>Auto</span>
        <strong>${formatNumber(rememberedBet)}</strong>
      </label>
    `;
  }

  function renderInsuranceMarker(player, table) {
    const state = String(player.insurance_state || "unavailable");
    if (state === "unavailable") return "";
    const labels = {
      pending: "Ins ?",
      taken: "Ins ✓",
      declined: "Ins -",
      won: "Ins +",
      lost: "Ins x",
    };
    const markerClass = {
      pending: "pending",
      taken: "taken",
      declined: "declined",
      won: "won",
      lost: "lost",
    }[state] || "pending";
    if (table.phase !== "insurance" && !["taken", "declined", "won", "lost"].includes(state)) return "";
    return `<div class="blackjack-insurance-marker ${markerClass}">${labels[state] || "Ins"}</div>`;
  }

  function renderSeatActionControls(player, table) {
    if (Number(player.user_id) !== viewerId) return "";
    const isTurn = table.current_turn_user_id === viewerId;
    const activeHand = player.hands?.[player.active_hand_index || 0];
    const canDouble = Boolean(
      isTurn &&
      table.phase === "player_turns" &&
      activeHand &&
      activeHand.cards?.length === 2 &&
      !activeHand.doubled &&
      !activeHand.stood
    );
    const canSplit = Boolean(
      isTurn &&
      table.phase === "player_turns" &&
      activeHand &&
      activeHand.cards?.length === 2 &&
      String(activeHand.cards?.[0]?.rank || "") === String(activeHand.cards?.[1]?.rank || "")
    );
    const canInsurance = Boolean(
      isTurn &&
      table.phase === "insurance" &&
      Math.floor(Number(activeHand?.bet_amount || 0) / 2) > 0 &&
      player.insurance_state === "pending"
    );
    if (!isTurn) return renderSeatAutoBetToggle(player, table);
    return `
      <div class="blackjack-seat-action-row">
        ${table.phase === "insurance" ? `
          ${canInsurance ? '<button class="blackjack-seat-action" id="blackjack-insurance" type="button">Ins</button>' : ""}
          <button class="blackjack-seat-action alt" id="blackjack-no-insurance" type="button">No</button>
        ` : ""}
        ${table.phase === "player_turns" ? `
          <button class="blackjack-seat-action" id="blackjack-hit" type="button">H</button>
          <button class="blackjack-seat-action alt" id="blackjack-stand" type="button">S</button>
          ${canDouble ? '<button class="blackjack-seat-action" id="blackjack-double" type="button">DD</button>' : ""}
          ${canSplit ? '<button class="blackjack-seat-action alt" id="blackjack-split" type="button">Sp</button>' : ""}
        ` : ""}
        ${renderSeatAutoBetToggle(player, table)}
      </div>
    `;
  }

  function renderObservers(table) {
    if (!table.observers?.length) {
      return '<div class="blackjack-copy">No observers yet.</div>';
    }
    return `
      <div class="blackjack-observer-list">
        ${table.observers.map((observer) => `
          <div class="blackjack-observer-pill">
            <img class="blackjack-avatar" src="${observer.avatar_url}" alt="">
            <span>${observer.username}${observer.is_owner ? " (host)" : ""}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderPlayers(table) {
    if (!table.players.length) {
      return '<div class="blackjack-empty">No players at this table yet.</div>';
    }

    const compactLayout = window.innerWidth <= 980;
    if (compactLayout) {
      const orderedPlayers = [...table.players].sort((a, b) => {
        const aViewer = Number(a.user_id === viewerId);
        const bViewer = Number(b.user_id === viewerId);
        if (aViewer !== bViewer) return bViewer - aViewer;
        const aTurn = Number(table.current_turn_user_id === a.user_id);
        const bTurn = Number(table.current_turn_user_id === b.user_id);
        return bTurn - aTurn;
      });

      return `<div class="blackjack-mobile-seat-grid">${orderedPlayers.map((player) => `
        <div class="blackjack-mobile-seat ${table.current_turn_user_id === player.user_id ? "turn" : ""} ${player.user_id === viewerId ? "viewer" : ""}">
          <div class="blackjack-mobile-seat-head">
            <img class="blackjack-avatar ${table.current_turn_user_id === player.user_id ? "turn" : ""}" src="${player.avatar_url}" alt="">
            <div class="blackjack-mobile-seat-name">${player.username}</div>
            ${renderInsuranceMarker(player, table)}
          </div>
          ${renderSeatActionControls(player, table)}
          ${player.hands?.length ? `
            <div class="blackjack-hand-stack ${player.hands.length > 1 ? "multi-hand" : ""}">
              ${player.hands.map((seatHand, handIndex) => `
                <div class="blackjack-seat-hand ${player.hands.length > 1 ? "split-layout" : ""}">
                  ${renderResultBanner(seatHand)}
                  <div class="blackjack-seat-cards ${handIndex === (player.active_hand_index || 0) && table.current_turn_user_id === player.user_id ? "active" : ""}">
                    ${renderCards(`player-${player.user_id}-hand-${handIndex}`, seatHand.cards, { fan: true, compactFan: true })}
                  </div>
                  <div class="blackjack-player-meta">
                    <span>Bet ${formatNumber(seatHand.bet_amount || player.bet || 0)}</span>
                    <span>Total ${seatHand.total}</span>
                  </div>
                </div>
              `).join("")}
            </div>
          ` : '<div class="blackjack-copy">Waiting for the next hand.</div>'}
          ${renderSeatBetControls(player, table)}
        </div>
      `).join("")}</div>`;
    }

    const seatOffsets = {
      1: [{ x: 0, y: 0 }],
      2: [{ x: -156, y: 24 }, { x: 156, y: 24 }],
      3: [{ x: -220, y: 68 }, { x: 0, y: 8 }, { x: 220, y: 68 }],
      4: [{ x: -286, y: 118 }, { x: -104, y: 46 }, { x: 104, y: 46 }, { x: 286, y: 118 }],
      5: [{ x: -314, y: 138 }, { x: -168, y: 72 }, { x: 0, y: 18 }, { x: 168, y: 72 }, { x: 314, y: 138 }],
      6: [{ x: -334, y: 150 }, { x: -220, y: 96 }, { x: -72, y: 32 }, { x: 72, y: 32 }, { x: 220, y: 96 }, { x: 334, y: 150 }],
    };

    const playerCount = Math.min(table.players.length, 6);
    const layout = seatOffsets[playerCount] || seatOffsets[6];
    const seatPhaseOffset = table.phase === "betting" || table.phase === "settled" ? 42 : 0;

    const seatScaleByCount = {
      1: 1,
      2: 0.97,
      3: 0.9,
      4: 0.81,
      5: 0.71,
      6: 0.62,
    };

    const mobileGridScaleByCount = {
      1: 0.62,
      2: 0.58,
      3: 0.5,
      4: 0.44,
      5: 0.39,
      6: 0.34,
    };

    const seatScale = seatScaleByCount[playerCount] || 0.62;
    const mobileGridScale = mobileGridScaleByCount[playerCount] || 0.34;

    return `<div class="blackjack-player-grid seats-${playerCount}" style="--grid-scale-mobile:${mobileGridScale};">${table.players.map((player, index) => {
      const seat = layout[Math.min(layout.length - 1, index)] || { x: 0, y: 0 };

      const scaledX = Math.round(seat.x * seatScale);
      const scaledY = Math.round((seat.y + seatPhaseOffset) * seatScale);

      const seatStyle = `
        transform:
          translateX(calc(-50% + ${scaledX}px))
          translateY(${scaledY}px)
          scale(${seatScale});
        transform-origin: center bottom;
      `;

      return `
        <div class="blackjack-player ${table.current_turn_user_id === player.user_id ? "turn" : ""} ${table.phase === "betting" || table.phase === "settled" ? "betting-layout" : ""}" style="${seatStyle}">
          ${player.hands?.length ? `
            <div class="blackjack-hand-stack">
              ${player.hands.map((seatHand, handIndex) => `
                <div class="blackjack-seat-hand">
                  ${renderResultBanner(seatHand)}
                  <div class="blackjack-seat-cards ${handIndex === (player.active_hand_index || 0) && table.current_turn_user_id === player.user_id ? "active" : ""}">
                    ${renderCards(`player-${player.user_id}-hand-${handIndex}`, seatHand.cards, { fan: true, compactFan: true })}
                  </div>
                  <div class="blackjack-player-meta">
                    <span>Bet ${formatNumber(seatHand.bet_amount || player.bet || 0)}</span>
                    <span>Total ${seatHand.total}</span>
                  </div>
                </div>
              `).join("")}
            </div>
            <div class="blackjack-player-avatar-row">
              <img class="blackjack-avatar ${table.current_turn_user_id === player.user_id ? "turn" : ""}" src="${player.avatar_url}" alt="">
              <div class="blackjack-player-name">${player.username}</div>
              ${renderInsuranceMarker(player, table)}
            </div>
            ${renderSeatActionControls(player, table)}
          ` : '<div class="blackjack-copy">Waiting for the next hand.</div>'}
          ${renderSeatBetControls(player, table)}
        </div>
      `;
    }).join("")}</div>`;
  }

  function renderTable(table) {
    const draftState = captureDraftState();
    trackChat(table);
    lastRenderedTable = table;
    const compactLayout = window.innerWidth <= 980;
    const turnRemaining = secondsUntil(table.turn_deadline_at);
    const nextHandRemaining = secondsUntil(table.auto_redeal_at);
    const autoStartRemaining = secondsUntil(table.auto_start_at);
    activeTitle.textContent = table.name;
    activeCopy.textContent = `${table.owner_name} owns this table. Minimum bet ${formatNumber(table.min_bet)}. Turn time ${formatDuration(table.turn_time_seconds)}. Fresh bets are required unless auto bet is on.`;
    leaveBtn.hidden = false;
    if (reportBtn) reportBtn.hidden = false;

    liveRoot.innerHTML = `
      <div class="blackjack-live-layout ${chatCollapsed ? "chat-collapsed" : ""}">
        <div>
          <div class="blackjack-table-board">
        <div class="blackjack-row">
          <div class="blackjack-status ${table.status}">${table.phase}</div>
          <div class="blackjack-row" style="justify-content:flex-end;">
            <div class="blackjack-balance blackjack-balance-inline">Balance <strong data-blackjack-balance>${balanceNode?.textContent || "0"}</strong></div>
            <div class="blackjack-pnl-chip ${sessionPnlClass(table.viewer_player?.session_pnl)}">Table P/L <strong>${formatSignedNumber(table.viewer_player?.session_pnl || 0)}</strong></div>
            <button class="blackjack-info-button" id="blackjack-rules-btn" type="button" aria-label="Open blackjack rules">i</button>
            <div class="blackjack-copy">Code ${table.table_code}</div>
          </div>
        </div>
        <p class="blackjack-message">${table.message || "Waiting on the next move."}</p>
        <div class="blackjack-meta">
          <div class="blackjack-stat"><strong>Seats</strong><div>${table.players.length} / ${table.max_players}</div></div>
          <div class="blackjack-stat"><strong>Observers</strong><div>${table.observers?.length || 0}</div></div>
          <div class="blackjack-stat"><strong>Shoe</strong><div>${table.shoe_count} decks</div></div>
          <div class="blackjack-stat"><strong>Turn</strong><div>${table.phase === "betting" ? "Betting window" : table.current_turn_user_id ? "Player action" : "No active turn"}</div></div>
          <div class="blackjack-stat"><strong>Timer</strong><div id="blackjack-turn-timer" data-deadline="${table.turn_deadline_at || ""}" data-redeal="${table.auto_redeal_at || ""}" data-start="${table.auto_start_at || ""}">${turnRemaining !== null ? formatDuration(turnRemaining) : nextHandRemaining !== null ? formatDuration(nextHandRemaining) : autoStartRemaining !== null ? formatDuration(autoStartRemaining) : formatDuration(table.turn_time_seconds)}</div></div>
        </div>
        <div class="blackjack-table-stage ${compactLayout ? "mobile-layout" : ""}">
          <div class="blackjack-dealer-zone">
            <div class="blackjack-dealer-head">
              <img class="blackjack-dealer-avatar" src="${table.dealer_profile.avatar_url}" alt="">
              <div>
                <p class="blackjack-dealer-title">Dealer</p>
                <p class="blackjack-dealer-name">${table.dealer_profile.username}</p>
              </div>
            </div>
            <div class="blackjack-hand-area blackjack-dealer-cards">
              ${renderCards("dealer", table.dealer.cards)}
            </div>
            <p class="blackjack-dealer-total">${table.dealer.hole_hidden ? "One card hidden" : `Dealer total ${table.dealer.total}`}</p>
          </div>
          ${renderPlayers(table)}
        </div>
          </div>
          <div class="blackjack-controls-panel">
            <div class="blackjack-seat-meta">
              <div>
                <p class="blackjack-seat-kicker">${table.viewer_role === "player" ? "Your seat" : table.viewer_role === "observer" ? "Observing" : "Table access"}</p>
                <p class="blackjack-seat-name">${table.viewer_player ? table.viewer_player.username : table.viewer_observer ? table.viewer_observer.username : "Not seated"}</p>
              </div>
              <div class="blackjack-timer-pill" data-deadline="${table.turn_deadline_at || ""}" data-redeal="${table.auto_redeal_at || ""}" data-start="${table.auto_start_at || ""}">${tableTimerText(table)}</div>
            </div>
            <div>
              <p class="blackjack-seat-kicker">Observers</p>
              ${renderObservers(table)}
            </div>
            ${renderViewerHand(table)}
            ${renderViewerControls(table)}
          </div>
        </div>
        ${renderChat(table)}
      </div>
    `;

    async function saveSeatBet(amountOverride = null) {
      const bet = Number(amountOverride ?? (document.getElementById("blackjack-seat-bet-input")?.value || 0));
      try {
        await api("/api/blackjack/bet", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, bet }),
        });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    }

    document.getElementById("blackjack-seat-bet-save")?.addEventListener("click", function () {
      saveSeatBet();
    });

    document.querySelectorAll("[data-chip-bet]").forEach((button) => {
      button.addEventListener("click", function () {
        const amount = Number(this.getAttribute("data-chip-bet") || 0);
        const input = document.getElementById("blackjack-seat-bet-input");
        if (input) input.value = String(amount);
        saveSeatBet(amount);
      });
    });

    document.getElementById("blackjack-auto-bet-enabled")?.addEventListener("change", async function () {
      const enabled = Boolean(this.checked);
      try {
        await api("/api/blackjack/auto-bet", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, enabled }),
        });
        await refreshTable();
      } catch (error) {
        this.checked = !enabled;
        alert(error.message);
      }
    });

    document.getElementById("blackjack-watch-table")?.addEventListener("click", async function () {
      try {
        await api("/api/blackjack/observe", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId }),
        });
        await refreshTable();
        await refreshLobby();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-join-seat")?.addEventListener("click", async function () {
      try {
        await api("/api/blackjack/join", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId }),
        });
        await refreshTable();
        await refreshLobby();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-hit")?.addEventListener("click", async function () {
      try {
        await api("/api/blackjack/action", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, action: "hit" }),
        });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-stand")?.addEventListener("click", async function () {
      try {
        await api("/api/blackjack/action", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, action: "stand" }),
        });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-double")?.addEventListener("click", async function () {
      try {
        await api("/api/blackjack/action", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, action: "double" }),
        });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-split")?.addEventListener("click", async function () {
      try {
        await api("/api/blackjack/action", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, action: "split" }),
        });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-insurance")?.addEventListener("click", async function () {
      try {
        await api("/api/blackjack/action", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, action: "insurance" }),
        });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-no-insurance")?.addEventListener("click", async function () {
      try {
        await api("/api/blackjack/action", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, action: "insurance_decline" }),
        });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-chat-form")?.addEventListener("submit", async function (event) {
      event.preventDefault();
      const input = document.getElementById("blackjack-chat-input");
      const message = (input?.value || "").trim();
      if (!message) return;
      try {
        await api("/api/blackjack/chat", {
          method: "POST",
          body: JSON.stringify({ table_id: activeTableId, message }),
        });
        if (input) input.value = "";
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.getElementById("blackjack-chat-toggle")?.addEventListener("click", function () {
      chatCollapsed = !chatCollapsed;
      if (!chatCollapsed) unreadChatCount = 0;
      renderTable(table);
    });

    document.getElementById("blackjack-rules-btn")?.addEventListener("click", function () {
      setRulesModalOpen(true);
    });

    const chatLog = document.getElementById("blackjack-chat-log");
    if (chatLog && !chatCollapsed) chatLog.scrollTop = chatLog.scrollHeight;
    restoreDraftState(draftState);
  }

  function renderEmptyState() {
    activeTitle.textContent = "Choose a table";
    activeCopy.textContent = "Join a table to play. Every hand needs fresh bets unless auto bet is turned on.";
    leaveBtn.hidden = true;
    if (reportBtn) reportBtn.hidden = true;
    setReportModalOpen(false);
    setRulesModalOpen(false);
    liveRoot.innerHTML = '<div class="blackjack-empty">Create a table or join one from the lobby.</div>';
  }

  async function refreshLobby() {
    try {
      const data = await api("/api/blackjack/lobby", { method: "GET" });
      setBalance(data.balance);
      if (!data.tables.length) {
        lobbyList.innerHTML = '<div class="blackjack-empty">No tables open yet.</div>';
      } else {
        lobbyList.innerHTML = data.tables.map((table) => `
          <div class="blackjack-table-item">
            <div class="blackjack-table-card-head">
              <div class="blackjack-table-card-title">
                <strong>${table.name}</strong>
                <p class="blackjack-table-host">Host: ${table.owner_name}</p>
              </div>
              <span class="blackjack-status ${table.status}">${table.status}</span>
            </div>
            <div class="blackjack-table-stats">
              <div class="blackjack-table-stat">
                <span class="blackjack-table-stat-label">Seats</span>
                <span class="blackjack-table-stat-value">${table.player_count}/${table.max_players}</span>
              </div>
              <div class="blackjack-table-stat">
                <span class="blackjack-table-stat-label">Observers</span>
                <span class="blackjack-table-stat-value">${table.observer_count || 0}</span>
              </div>
              <div class="blackjack-table-stat">
                <span class="blackjack-table-stat-label">Minimum Bet</span>
                <span class="blackjack-table-stat-value">${formatNumber(table.min_bet)}</span>
              </div>
              <div class="blackjack-table-stat">
                <span class="blackjack-table-stat-label">Turn Time</span>
                <span class="blackjack-table-stat-value">${formatDuration(table.turn_time_seconds)}</span>
              </div>
              <div class="blackjack-table-stat">
                <span class="blackjack-table-stat-label">Starts</span>
                <span class="blackjack-table-stat-value">${table.auto_start_at ? formatDuration(secondsUntil(table.auto_start_at)) : (table.status === "playing" ? "Live" : "Ready")}</span>
              </div>
            </div>
            <div class="blackjack-actions">
              <button class="blackjack-button alt" data-open-table="${table.id}" type="button">${table.viewer_joined || table.viewer_observing ? "Open" : "Watch"}</button>
              ${table.viewer_joined ? "" : `<button class="blackjack-button" data-join-table="${table.id}" type="button">Join table</button>`}
              ${isAdmin ? `<button class="blackjack-button" data-delete-table="${table.id}" type="button">Delete</button>` : ""}
            </div>
          </div>
        `).join("");
      }

      lobbyList.querySelectorAll("[data-open-table]").forEach((button) => {
        button.addEventListener("click", async function () {
          const tableId = this.getAttribute("data-open-table");
          try {
            activeTableId = tableId;
            updateUrl();
            await refreshTable();
            await refreshLobby();
          } catch (error) {
            alert(error.message);
          }
        });
      });

      lobbyList.querySelectorAll("[data-join-table]").forEach((button) => {
        button.addEventListener("click", async function () {
          const tableId = this.getAttribute("data-join-table");
          try {
            await api("/api/blackjack/join", {
              method: "POST",
              body: JSON.stringify({ table_id: tableId }),
            });
            activeTableId = tableId;
            updateUrl();
            await refreshTable();
            await refreshLobby();
          } catch (error) {
            alert(error.message);
          }
        });
      });

      lobbyList.querySelectorAll("[data-delete-table]").forEach((button) => {
        button.addEventListener("click", async function () {
          const tableId = this.getAttribute("data-delete-table");
          try {
            await api("/api/blackjack/delete", {
              method: "POST",
              body: JSON.stringify({ table_id: tableId }),
            });
            if (activeTableId === tableId) {
              activeTableId = "";
              updateUrl();
              renderEmptyState();
            }
            await refreshLobby();
          } catch (error) {
            alert(error.message);
          }
        });
      });
    } catch (error) {
      lobbyList.innerHTML = `<div class="blackjack-empty">${error.message}</div>`;
    }
  }

  async function refreshTable() {
    clearTimeout(tableTimer);
    if (!activeTableId) {
      renderEmptyState();
      return;
    }

    try {
      const data = await api(`/api/blackjack/table/${activeTableId}`, { method: "GET" });
      setBalance(data.balance);
      renderTable(data.table);
      tableTimer = setTimeout(refreshTable, Math.max(900, (data.table.poll_seconds || 1) * 1000));
    } catch (error) {
      activeTableId = "";
      updateUrl();
      renderEmptyState();
    }
  }

  createForm?.addEventListener("submit", async function (event) {
    event.preventDefault();
    const formData = new FormData(createForm);
    try {
      const data = await api("/api/blackjack/create", {
        method: "POST",
        body: JSON.stringify({
          name: formData.get("name"),
          min_bet: Number(formData.get("min_bet") || 1),
          max_players: Number(formData.get("max_players") || 4),
          turn_time_seconds: Number(formData.get("turn_time_seconds") || 60),
        }),
      });
      activeTableId = data.table_id;
      updateUrl();
      await refreshLobby();
      await refreshTable();
    } catch (error) {
      alert(error.message);
    }
  });

  refreshLobbyBtn?.addEventListener("click", function () {
    refreshLobby();
  });

  sidebarToggleBtn?.addEventListener("click", function () {
    setSidebarCollapsed(!sidebarCollapsed);
  });

  reportBtn?.addEventListener("click", function () {
    if (!activeTableId) return;
    setReportModalOpen(true);
  });

  reportCancelBtn?.addEventListener("click", function () {
    setReportModalOpen(false);
  });

  reportOverlay?.addEventListener("click", function (event) {
    if (event.target === reportOverlay) setReportModalOpen(false);
  });

  rulesCloseBtn?.addEventListener("click", function () {
    setRulesModalOpen(false);
  });

  rulesOverlay?.addEventListener("click", function (event) {
    if (event.target === rulesOverlay) setRulesModalOpen(false);
  });

  reportSubmitBtn?.addEventListener("click", async function () {
    const reason = String(reportReasonInput?.value || "").trim();
    if (reason.length < 10) {
      alert("Please describe the issue before sending the report.");
      reportReasonInput?.focus();
      return;
    }
    try {
      await api("/api/blackjack/report", {
        method: "POST",
        body: JSON.stringify({ table_id: activeTableId, reason }),
      });
      if (reportReasonInput) reportReasonInput.value = "";
      setReportModalOpen(false);
      alert("Report sent to the admin dashboard.");
    } catch (error) {
      alert(error.message);
    }
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth <= 980 && !sidebarCollapsed) {
      setSidebarCollapsed(true);
    }
  });

  leaveBtn?.addEventListener("click", async function () {
    if (!activeTableId) return;
    try {
      await api("/api/blackjack/leave", {
        method: "POST",
        body: JSON.stringify({ table_id: activeTableId }),
      });
      activeTableId = "";
      updateUrl();
      renderEmptyState();
      await refreshLobby();
    } catch (error) {
      alert(error.message);
    }
  });

  disclaimerAcceptBtn?.addEventListener("click", function () {
    setDisclaimerAccepted();
  });

  renderEmptyState();
  setSidebarCollapsed(sidebarCollapsed);
  if (hasAcceptedDisclaimer()) {
    disclaimerOverlay?.classList.add("hidden");
  } else {
    document.body.classList.add("no-scroll");
  }
  refreshLobby();
  refreshTable();
  setInterval(refreshLobby, 5000);
  clearInterval(countdownTimer);
  countdownTimer = setInterval(function () {
    const turnTimer = document.getElementById("blackjack-turn-timer");
    const nextTimer = document.querySelector(".blackjack-timer-pill");
    if (turnTimer) {
      const tableDeadline = turnTimer.dataset.deadline;
      const tableRedeal = turnTimer.dataset.redeal;
      const tableStart = turnTimer.dataset.start;
      const turnRemaining = secondsUntil(tableDeadline);
      const redealRemaining = secondsUntil(tableRedeal);
      const startRemaining = secondsUntil(tableStart);
      if (turnRemaining !== null) {
        turnTimer.textContent = formatDuration(turnRemaining);
      } else if (redealRemaining !== null) {
        turnTimer.textContent = formatDuration(redealRemaining);
      } else if (startRemaining !== null) {
        turnTimer.textContent = formatDuration(startRemaining);
      }
    }
    if (nextTimer) {
      const turnRemaining = secondsUntil(nextTimer.dataset.deadline);
      const redealRemaining = secondsUntil(nextTimer.dataset.redeal);
      const startRemaining = secondsUntil(nextTimer.dataset.start);
      if (turnRemaining !== null) {
        nextTimer.textContent = `Turn ${formatDuration(turnRemaining)}`;
      } else if (redealRemaining !== null) {
        nextTimer.textContent = `Next hand ${formatDuration(redealRemaining)}`;
      } else if (startRemaining !== null) {
        nextTimer.textContent = `Hand starts ${formatDuration(startRemaining)}`;
      }
    }
  }, 1000);
})();


