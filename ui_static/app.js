let sessionId = null;
let snapshot = null;
let lastEventId = 0;
let logLevel = "basic";
let renderedDecisionId = null;
let renderedLogKey = "";
const logs = { basic: [], full: [] };

const $ = (id) => document.getElementById(id);

function cleanText(value) {
  return String(value ?? "")
    .replaceAll("<b>", "")
    .replaceAll("</b>", "")
    .replace(/\s+/g, " ")
    .trim();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/\n/g, "&#10;");
}

function cleanOptionDescription(value) {
  return cleanText(value)
    .split("|")
    .map((part) => part.trim())
    .filter((part) => !/^PV\s*\+?0\b/i.test(part))
    .join(" | ");
}

function itemColorCode(item) {
  const code = Number(item?.colorCode || 0);
  return Number.isFinite(code) ? code : 0;
}

function itemColorStyle(item) {
  const color = String(item?.color || "").trim();
  return /^#[0-9a-f]{6}$/i.test(color) ? ` style="background-color: ${escapeAttr(color)}"` : "";
}

function itemColorSwatch(item, extraClass = "") {
  const code = itemColorCode(item);
  const colorClass = code ? " has-color" : "";
  return `<span class="item-color ${extraClass}${colorClass}" data-color="${code}"${itemColorStyle(item)} aria-label="${escapeAttr(item?.colorName || "No color")}"></span>`;
}

function statusFor(player) {
  if (!player.alive) return ["dead", "status-dead"];
  if (player.fled) return ["fled", "status-fled"];
  if (player.inDungeon) return ["in dungeon", "status-active"];
  return ["safe", "status-active"];
}

function chip(label) {
  return `<span class="chip">${escapeHtml(label)}</span>`;
}

function cardChips(card) {
  const stats = [];
  if (card.event) stats.push(chip("event"));
  if (card.power !== null && card.power !== undefined) stats.push(chip(`power ${card.power}`));
  if (Number(card.damage || 0) > 0) stats.push(chip(`damage ${card.damage}`));
  for (const type of card.types || []) stats.push(chip(type));
  return stats.join("");
}

function assetImage(entity, className, altText, titleText = "") {
  const src = String(entity?.image || "").trim();
  if (!src) return "";
  const alt = altText || entity?.title || entity?.name || "card";
  const title = cleanText(titleText || "");
  const titleAttr = title ? ` title="${escapeAttr(title)}"` : "";
  return `<img class="${className}" src="${escapeAttr(src)}" alt="${escapeAttr(alt)}"${titleAttr} loading="lazy">`;
}

function renderCard(card) {
  if (!card) {
    $("currentCard").innerHTML = `<div class="empty">No current card.</div>`;
    return;
  }
  $("currentCard").innerHTML = `
    <div class="card-detail">
      ${assetImage(card, "card-art", card.title)}
      <div class="card-copy">
        <div class="card-name">${escapeHtml(card.title || "Card")}</div>
        <div class="stats">${cardChips(card)}</div>
        <div class="muted">${escapeHtml(cleanText(card.description || card.effect || ""))}</div>
      </div>
    </div>
  `;
}

function renderPileCard(card, index = null) {
  const description = cleanText(card.description || card.effect || "");
  const tooltip = description ? ` title="${escapeAttr(description)}"` : "";
  const count = Number(card.count || 1);
  const countLabel = count > 1 ? `<span class="pile-count">x${count}</span>` : "";
  const indexLabel = index === null ? "" : `<span class="pile-index">${index}</span>`;
  return `
    <article class="pile-card ${card.event ? "event-card" : "monster-card"}"${tooltip}>
      ${assetImage(card, "pile-art", card.title)}
      <div class="pile-card-head">
        ${indexLabel}
        <span class="pile-card-name">${escapeHtml(card.title || "Card")}</span>
        ${countLabel}
      </div>
      <div class="stats">${cardChips(card)}</div>
    </article>
  `;
}

function renderDungeon(dungeon) {
  const state = dungeon || {};
  const remaining = state.remainingSummary || [];
  const discard = state.discard || [];
  const knownGroups = state.knownCards || [];
  const knownCards = knownGroups.flatMap((group) =>
    (group.cards || []).map((card) => ({ ...card, player: group.player }))
  );
  $("pilesMeta").textContent = "dungeon grouped | discard top first";
  $("dungeonCount").textContent = `${state.remainingCount || 0} left`;
  $("discardCount").textContent = `${state.discardCount || 0} cards`;
  $("dungeonRemaining").innerHTML = remaining.length
    ? remaining.map((card) => renderPileCard(card)).join("")
    : `<div class="empty">No remaining dungeon cards.</div>`;
  $("discardCards").innerHTML = discard.length
    ? discard.map((card, index) => renderPileCard(card, index + 1)).join("")
    : `<div class="empty">No discarded cards yet.</div>`;
  $("knownCardsPanel").hidden = knownCards.length === 0;
  $("knownCards").innerHTML = knownCards.length
    ? knownCards.map((card) => renderPileCard(card, card.position)).join("")
    : "";
}

function renderDecision(decision) {
  if (!decision) {
    renderedDecisionId = null;
    $("decisionBox").innerHTML = `<div class="empty">Waiting for the next human decision.</div>`;
    return;
  }
  if (decision.id === renderedDecisionId) {
    return;
  }
  renderedDecisionId = decision.id;
  const contextRows = Object.entries(decision.context || {})
    .filter(([, value]) => value !== null && value !== "" && value !== undefined)
    .slice(0, 8)
    .map(([key, value]) => chip(`${key}: ${Array.isArray(value) ? value.join(", ") : value}`))
    .join("");
  const buttons = decision.options
    .map((option) => {
      const cls = option.id === decision.defaultId ? "default" : "secondary";
      const desc = cleanOptionDescription(option.description || "");
      const optionColor = itemColorCode(option) || option.color ? itemColorSwatch(option, "decision-color") : "";
      return `<button class="${cls}" data-decision="${decision.id}" data-option="${option.id}" type="button">
        <span class="button-main">${optionColor}<span>${escapeHtml(option.label)}</span></span>${desc ? `<span class="button-desc">${escapeHtml(desc)}</span>` : ""}
      </button>`;
    })
    .join("");
  $("decisionBox").innerHTML = `
    <div class="decision-content">
      <div class="muted">${escapeHtml(decision.player)}</div>
      <div class="card-name">${escapeHtml(decision.prompt)}</div>
      <div class="stats">${contextRows}</div>
      <div class="decision-actions">${buttons}</div>
    </div>
  `;
  document.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      await submitDecision(button.dataset.decision, button.dataset.option);
    });
  });
}

function renderDraft(draft) {
  const panel = $("draftPanel");
  if (!draft) {
    panel.hidden = true;
    $("draftPickedWrap").hidden = true;
    $("draftPicked").innerHTML = "";
    $("draftHand").innerHTML = "";
    return;
  }
  panel.hidden = false;
  $("draftMeta").textContent = `${draft.player || ""} round ${draft.round || ""} pick ${draft.pick || ""}`;
  const picked = draft.yourPicked || draft.picked || [];
  $("draftPickedWrap").hidden = picked.length === 0;
  $("draftPicked").innerHTML = picked.map(renderItem).join("");
  $("draftHand").innerHTML = (draft.hand || []).map(renderItem).join("");
}

function renderItem(item) {
  const status = item.intact === false ? "broken" : "";
  const description = cleanText(item.description || item.effect || "");
  const tooltip = description ? ` title="${escapeAttr(description)}"` : "";
  const pv = Number(item.pv || 0);
  const flee = Number(item.flee || 0);
  const meta = [
    pv !== 0 ? `PV ${pv > 0 ? "+" : ""}${pv}` : "",
    flee ? `flee ${flee > 0 ? "+" : ""}${flee}` : "",
    item.active ? "⚡" : "",
  ].filter(Boolean).join(" | ");
  const tags = [
    ...(item.types || []),
    ...(item.powers || []).map((p) => `power ${p}`),
  ].join(", ");
  return `
    <div class="item-card ${status}"${tooltip}>
      <div class="item-name">
        ${assetImage(item, "item-art", item.name, description)}
        ${itemColorSwatch(item)}
        <span>${escapeHtml(item.name)}</span>
      </div>
      ${meta ? `<div class="item-meta">${escapeHtml(meta)}</div>` : ""}
      ${tags ? `<div class="item-meta">${escapeHtml(tags)}</div>` : ""}
      ${item.effect ? `<div class="item-effect">${escapeHtml(cleanText(item.effect))}</div>` : ""}
    </div>
  `;
}

function renderMonsterStack(monsters) {
  const cards = monsters || [];
  if (!cards.length) {
    return `<div class="monster-stack empty-stack">none</div>`;
  }
  return `
    <div class="monster-stack">
      ${cards.map((monster, index) => {
        const title = monster.title || "Monster";
        const detail = cleanText(monster.description || monster.effect || title);
        const image = assetImage(monster, "monster-art", title, detail);
        const fallback = `<span class="monster-fallback" title="${escapeAttr(detail)}">${escapeHtml(title)}</span>`;
        return `<span class="monster-token" aria-label="${escapeAttr(`${index + 1}. ${title}`)}">${image || fallback}</span>`;
      }).join("")}
    </div>
  `;
}

function renderPlayers(players) {
  $("players").innerHTML = (players || []).map((player) => {
    const [status, statusClass] = statusFor(player);
    const itemList = (player.items || []).map(renderItem).join("");
    const monsterStack = renderMonsterStack(player.monsters || []);
    const strategyText = player.strategy ? ` | ${player.strategy}` : "";
    return `
      <article class="player ${player.control === "human" ? "human" : ""} ${player.alive ? "" : "dead"}">
        <div class="player-head">
          <div>
            <div class="player-name">${escapeHtml(player.name)}</div>
            <div class="muted">${escapeHtml(`${player.control}${strategyText}`)}</div>
          </div>
          <div class="${statusClass}">${status}</div>
        </div>
        <div class="player-body">
          <div class="hero-line">
            ${assetImage(player.hero, "hero-art", player.hero?.name)}
            <span>${escapeHtml(player.hero ? player.hero.name : "No hero")}</span>
          </div>
          <div class="stats">
            ${chip(`PV ${player.pv}`)}
            ${chip(`score ${player.currentScore}`)}
            ${chip(`final ${player.score}`)}
            ${chip(`medals ${player.medals}`)}
            ${chip(`turn ${player.turn}`)}
          </div>
          <div class="monster-row">${monsterStack}</div>
          <div class="mini-list">${itemList}</div>
        </div>
      </article>
    `;
  }).join("");
}

function renderLogs(force = false) {
  const list = $("logList");
  const active = logs[logLevel];
  const lastId = active.length ? active[active.length - 1].id : 0;
  const renderKey = `${logLevel}:${active.length}:${lastId}`;
  if (!force && renderKey === renderedLogKey) {
    return;
  }
  const distanceFromBottom = list.scrollHeight - list.scrollTop - list.clientHeight;
  const wasAtBottom = distanceFromBottom < 12;
  const previousTop = list.scrollTop;
  list.innerHTML = active.map((event) => `<li>${escapeHtml(event.text)}</li>`).join("");
  if (wasAtBottom) {
    list.scrollTop = list.scrollHeight;
  } else {
    list.scrollTop = Math.min(previousTop, Math.max(0, list.scrollHeight - list.clientHeight));
  }
  renderedLogKey = renderKey;
}

function render() {
  if (!snapshot) return;
  $("statusLine").textContent = `${snapshot.status} | ${snapshot.mode} | ${snapshot.phase}`;
  $("phaseBadge").textContent = snapshot.phase || "setup";
  $("roundLabel").textContent = snapshot.round || "";
  renderCard(snapshot.currentCard);
  renderDungeon(snapshot.dungeon);
  renderDecision(snapshot.pendingDecision);
  renderDraft(snapshot.draft);
  renderPlayers(snapshot.players);
}

function collapsePiles() {
  for (const id of ["dungeonDetails", "discardDetails"]) {
    $(id)?.removeAttribute("open");
  }
}

function botStrategiesForGame() {
  const count = Math.max(0, Number($("playerCount").value || 0) - 1);
  return Array.from({ length: count }, (_, idx) => $(`botStrategy${idx + 1}`).value);
}

function updateBotStrategyControls() {
  const count = Math.max(0, Number($("playerCount").value || 0) - 1);
  document.querySelectorAll(".bot-ai-control").forEach((control) => {
    const slot = Number(control.dataset.botSlot || 0);
    const visible = slot <= count;
    control.hidden = !visible;
    const select = control.querySelector("select");
    if (select) select.disabled = !visible;
  });
}

async function createGame(event) {
  event.preventDefault();
  lastEventId = 0;
  renderedDecisionId = null;
  renderedLogKey = "";
  collapsePiles();
  logs.basic = [];
  logs.full = [];
  const seedValue = $("seed").value.trim();
  const payload = {
    mode: $("mode").value,
    playerName: $("playerName").value.trim() || "Human",
    playerCount: Number($("playerCount").value),
    seed: seedValue ? Number(seedValue) : null,
    botDelayMs: Number($("botDelay").value || 0),
    botStrategies: botStrategiesForGame(),
  };
  const response = await fetch("/api/games", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  snapshot = await response.json();
  sessionId = snapshot.id;
  render();
  renderLogs(true);
}

async function submitDecision(decisionId, optionId) {
  if (!sessionId) return;
  const response = await fetch(`/api/games/${sessionId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decisionId, optionId }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    alert(body.detail || "Decision rejected.");
  }
  await poll();
}

async function poll() {
  if (!sessionId) return;
  const [snapResponse, basicResponse, fullResponse] = await Promise.all([
    fetch(`/api/games/${sessionId}`),
    fetch(`/api/games/${sessionId}/events?after=${lastEventId}&level=basic`),
    fetch(`/api/games/${sessionId}/events?after=${lastEventId}&level=full`),
  ]);
  if (!snapResponse.ok) return;
  snapshot = await snapResponse.json();
  const fullBody = await fullResponse.json();
  const basicBody = await basicResponse.json();
  const fullEvents = fullBody.events || [];
  const basicEvents = basicBody.events || [];
  if (fullEvents.length) {
    lastEventId = Math.max(lastEventId, ...fullEvents.map((e) => e.id));
    logs.full.push(...fullEvents);
    logs.full = logs.full.slice(-600);
  }
  if (basicEvents.length) {
    logs.basic.push(...basicEvents);
    logs.basic = logs.basic.slice(-400);
  }
  render();
  renderLogs();
}

function setLogLevel(level) {
  logLevel = level;
  $("basicTab").classList.toggle("active", level === "basic");
  $("fullTab").classList.toggle("active", level === "full");
  renderLogs(true);
}

$("newGameForm").addEventListener("submit", createGame);
$("playerCount").addEventListener("change", updateBotStrategyControls);
$("basicTab").addEventListener("click", () => setLogLevel("basic"));
$("fullTab").addEventListener("click", () => setLogLevel("full"));
updateBotStrategyControls();
setInterval(poll, 700);
