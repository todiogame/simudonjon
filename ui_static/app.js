let sessionId = null;
let snapshot = null;
let lastEventId = 0;
let logLevel = "basic";
const logs = { basic: [], full: [] };

const $ = (id) => document.getElementById(id);

function cleanText(value) {
  return String(value ?? "")
    .replaceAll("<b>", "")
    .replaceAll("</b>", "")
    .replace(/\s+/g, " ")
    .trim();
}

function statusFor(player) {
  if (!player.alive) return ["dead", "status-dead"];
  if (player.fled) return ["fled", "status-fled"];
  if (player.inDungeon) return ["in dungeon", "status-active"];
  return ["safe", "status-active"];
}

function chip(label) {
  return `<span class="chip">${label}</span>`;
}

function renderCard(card) {
  if (!card) {
    $("currentCard").innerHTML = `<div class="empty">No current card.</div>`;
    return;
  }
  const stats = [];
  if (card.event) stats.push(chip("event"));
  if (card.power !== null && card.power !== undefined) stats.push(chip(`power ${card.power}`));
  if (card.damage !== null && card.damage !== undefined) stats.push(chip(`damage ${card.damage}`));
  for (const type of card.types || []) stats.push(chip(type));
  $("currentCard").innerHTML = `
    <div class="card-detail">
      <div class="card-name">${card.title || "Card"}</div>
      <div class="stats">${stats.join("")}</div>
      <div class="muted">${cleanText(card.description || card.effect || "")}</div>
    </div>
  `;
}

function renderDecision(decision) {
  if (!decision) {
    $("decisionBox").innerHTML = `<div class="empty">Waiting for the next human decision.</div>`;
    return;
  }
  const contextRows = Object.entries(decision.context || {})
    .filter(([, value]) => value !== null && value !== "" && value !== undefined)
    .slice(0, 8)
    .map(([key, value]) => chip(`${key}: ${Array.isArray(value) ? value.join(", ") : value}`))
    .join("");
  const buttons = decision.options
    .map((option) => {
      const cls = option.id === decision.defaultId ? "default" : "secondary";
      const desc = cleanText(option.description || "");
      return `<button class="${cls}" data-decision="${decision.id}" data-option="${option.id}" type="button">
        ${option.label}${desc ? `<span class="button-desc">${desc}</span>` : ""}
      </button>`;
    })
    .join("");
  $("decisionBox").innerHTML = `
    <div class="decision-content">
      <div class="muted">${decision.player}</div>
      <div class="card-name">${decision.prompt}</div>
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
    $("draftHand").innerHTML = "";
    return;
  }
  panel.hidden = false;
  $("draftMeta").textContent = `${draft.player || ""} round ${draft.round || ""} pick ${draft.pick || ""}`;
  $("draftHand").innerHTML = (draft.hand || []).map(renderItem).join("");
}

function renderItem(item) {
  const status = item.intact === false ? "broken" : "";
  const meta = [
    `PV ${item.pv >= 0 ? "+" : ""}${item.pv || 0}`,
    item.flee ? `flee ${item.flee >= 0 ? "+" : ""}${item.flee}` : "",
    item.active ? "active" : "passive",
  ].filter(Boolean).join(" | ");
  const tags = [
    ...(item.types || []),
    ...(item.powers || []).map((p) => `power ${p}`),
  ].join(", ");
  return `
    <div class="item-card ${status}">
      <div class="item-name">${item.name}</div>
      <div class="item-meta">${meta}</div>
      ${tags ? `<div class="item-meta">${tags}</div>` : ""}
      ${item.effect ? `<div class="item-effect">${cleanText(item.effect)}</div>` : ""}
    </div>
  `;
}

function renderPlayers(players) {
  $("players").innerHTML = (players || []).map((player) => {
    const [status, statusClass] = statusFor(player);
    const itemList = (player.items || []).map(renderItem).join("");
    const monsterText = (player.monsters || []).map((m) => m.title).slice(-8).join(", ");
    return `
      <article class="player ${player.control === "human" ? "human" : ""} ${player.alive ? "" : "dead"}">
        <div class="player-head">
          <div>
            <div class="player-name">${player.name}</div>
            <div class="muted">${player.control}</div>
          </div>
          <div class="${statusClass}">${status}</div>
        </div>
        <div class="player-body">
          <div class="hero-line">${player.hero ? player.hero.name : "No hero"}</div>
          <div class="stats">
            ${chip(`PV ${player.pv}`)}
            ${chip(`score ${player.currentScore}`)}
            ${chip(`final ${player.score}`)}
            ${chip(`medals ${player.medals}`)}
            ${chip(`turn ${player.turn}`)}
          </div>
          <div class="muted">Recent monsters: ${monsterText || "none"}</div>
          <div class="mini-list">${itemList}</div>
        </div>
      </article>
    `;
  }).join("");
}

function renderLogs() {
  const list = $("logList");
  const active = logs[logLevel];
  list.innerHTML = active.map((event) => `<li>${event.text}</li>`).join("");
  list.scrollTop = list.scrollHeight;
}

function render() {
  if (!snapshot) return;
  $("statusLine").textContent = `${snapshot.status} | ${snapshot.mode} | ${snapshot.phase}`;
  $("phaseBadge").textContent = snapshot.phase || "setup";
  $("roundLabel").textContent = snapshot.round || "";
  renderCard(snapshot.currentCard);
  renderDecision(snapshot.pendingDecision);
  renderDraft(snapshot.draft);
  renderPlayers(snapshot.players);
}

async function createGame(event) {
  event.preventDefault();
  lastEventId = 0;
  logs.basic = [];
  logs.full = [];
  const seedValue = $("seed").value.trim();
  const payload = {
    mode: $("mode").value,
    playerName: $("playerName").value.trim() || "Human",
    playerCount: Number($("playerCount").value),
    seed: seedValue ? Number(seedValue) : null,
    botDelayMs: Number($("botDelay").value || 0),
  };
  const response = await fetch("/api/games", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  snapshot = await response.json();
  sessionId = snapshot.id;
  render();
  renderLogs();
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
  renderLogs();
}

$("newGameForm").addEventListener("submit", createGame);
$("basicTab").addEventListener("click", () => setLogLevel("basic"));
$("fullTab").addEventListener("click", () => setLogLevel("full"));
setInterval(poll, 700);
