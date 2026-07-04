let sessionId = null;
let snapshot = null;
let lastEventId = 0;
let logLevel = "basic";
let renderedDecisionId = null;
let renderedLogKey = "";
let pollInFlight = false;
let pollTimer = null;
let lastPollStartedAt = 0;
let worstFrameMs = 0;
const logs = { basic: [], full: [] };
const debugMode = new URLSearchParams(window.location.search).has("debug");
const perfSamples = [];
const playerRenderKeys = new Map();
const handledFxEventIds = new Set();
const recentItemFxKeys = new Map();
const botThinking = new Map();
let thinkingRevision = 0;
const renderKeys = {
  status: "",
  card: "",
  dungeon: "",
  decision: "",
  draft: "",
  players: "",
};
const TEACHER_MARK = "\u{1F9D1}\u200D\u{1F3EB}";
const ACTIVE_MARK = "\u26A1";
const STATIC_ASSETS = "/static/assets";
const ITEM_FX_LANES = [
  { x: 118, y: 0 },
  { x: 250, y: 18 },
  { x: -118, y: 18 },
  { x: 382, y: 38 },
  { x: -250, y: 38 },
];
const AUDIO_FILES = {
  draw: `${STATIC_ASSETS}/sounds/draw.wav`,
  execute: `${STATIC_ASSETS}/sounds/execute.mp3`,
  playcard: `${STATIC_ASSETS}/sounds/playcard.wav`,
  rolldie: `${STATIC_ASSETS}/sounds/rolldie.wav`,
  shuffle: `${STATIC_ASSETS}/sounds/shuffle.wav`,
};
const audioBank = {};
let audioReady = false;
let itemFxLane = 0;

const $ = (id) => document.getElementById(id);

function trackFrame(now) {
  if (trackFrame.last) {
    worstFrameMs = Math.max(worstFrameMs, now - trackFrame.last);
  }
  trackFrame.last = now;
  window.requestAnimationFrame(trackFrame);
}
window.requestAnimationFrame(trackFrame);

function numericHeader(response, name) {
  const value = Number(response.headers.get(name));
  return Number.isFinite(value) ? value : 0;
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatMs(value) {
  return `${Math.round(value)}ms`;
}

function renderPerfPanel(sample) {
  if (!debugMode) return;
  const panel = $("perfPanel");
  if (!panel) return;
  panel.hidden = false;
  const recent = perfSamples.slice(-20);
  const slowest = Math.max(...recent.map((entry) => entry.totalMs), 0);
  const avgTotal = average(recent.map((entry) => entry.totalMs));
  const avgRender = average(recent.map((entry) => entry.renderMs + entry.logRenderMs));
  $("perfStatus").textContent = snapshot?.status || "no game";
  $("perfPoll").textContent = `${formatMs(sample.totalMs)} avg ${formatMs(avgTotal)} max ${formatMs(slowest)}`;
  $("perfNetwork").textContent = `${formatMs(sample.fetchMs)} server ${formatMs(sample.serverMs)}`;
  $("perfRender").textContent = `${formatMs(sample.renderMs)} + logs ${formatMs(sample.logRenderMs)} avg ${formatMs(avgRender)}`;
  $("perfPayload").textContent = `${sample.snapshotBytes + sample.eventsBytes} B / ${sample.eventCount} events`;
  $("perfFrame").textContent = `${formatMs(worstFrameMs)} worst`;
  $("perfCadence").textContent = `${formatMs(sample.pollGapMs)} gap`;
}

function recordPerf(sample) {
  perfSamples.push(sample);
  if (perfSamples.length > 80) {
    perfSamples.shift();
  }
  renderPerfPanel(sample);
}

function stableRenderKey(value) {
  return JSON.stringify(value ?? null);
}

function resetRenderKeys() {
  for (const key of Object.keys(renderKeys)) {
    renderKeys[key] = "";
  }
  playerRenderKeys.clear();
  botThinking.clear();
  thinkingRevision += 1;
  handledFxEventIds.clear();
  recentItemFxKeys.clear();
  itemFxLane = 0;
  renderedDecisionId = null;
}

function updateBotThinking(events) {
  let changed = false;
  for (const event of events || []) {
    if (event.kind === "bot_thinking" || event.kind === "bot_thinking_progress") {
      const player = event.payload?.player;
      if (!player) continue;
      botThinking.set(player, {
        decision: event.payload?.decision || "",
        iterationsDone: event.payload?.iterationsCompleted || 0,
        iterationsTotal: event.payload?.iterationsRequested || event.payload?.iterations || 0,
        elapsedMs: event.payload?.elapsedMs || 0,
      });
      changed = true;
    } else if (event.kind === "bot_decision") {
      const player = event.payload?.player || event.text?.split(":")[0];
      if (player && botThinking.delete(player)) {
        changed = true;
      }
    } else if (event.kind === "finished" || event.kind === "error") {
      if (botThinking.size) {
        botThinking.clear();
        changed = true;
      }
    }
  }
  if (changed) {
    thinkingRevision += 1;
  }
}

function isLogEvent(event) {
  return event.kind !== "bot_thinking"
    && event.kind !== "bot_thinking_progress"
    && event.kind !== "bot_item_fx";
}

function renderIfChanged(key, value, callback) {
  const next = stableRenderKey(value);
  if (renderKeys[key] === next) {
    return;
  }
  renderKeys[key] = next;
  callback(value);
}

function cleanText(value) {
  return String(value ?? "")
    .replaceAll("<b>", "")
    .replaceAll("</b>", "")
    .replace(/\s+/g, " ")
    .trim();
}

function searchKey(value) {
  return cleanText(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
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

function optionForItem(decision, item) {
  if (!decision || !item?.itemId) {
    return null;
  }
  return (decision.options || []).find((option) => option.itemId === item.itemId) || null;
}

function optionForHero(decision, hero) {
  if (!decision || !hero?.heroId) {
    return null;
  }
  return (decision.options || []).find((option) => option.heroId === hero.heroId) || null;
}

function isTeacherOption(decision, option) {
  return Boolean(decision && option && option.id === decision.defaultId);
}

function assetImage(entity, className, altText, titleText = "") {
  const src = String(entity?.image || "").trim();
  if (!src) return "";
  const alt = altText || entity?.title || entity?.name || "card";
  const title = cleanText(titleText || "");
  const titleAttr = title ? ` title="${escapeAttr(title)}"` : "";
  return `<img class="${className} zoomable-art" src="${escapeAttr(src)}" alt="${escapeAttr(alt)}"${titleAttr} loading="lazy" data-zoom-src="${escapeAttr(src)}" data-zoom-title="${escapeAttr(alt)}">`;
}

function ensureAudioReady() {
  if (audioReady) return;
  for (const [key, src] of Object.entries(AUDIO_FILES)) {
    const audio = new Audio(src);
    audio.preload = "auto";
    audio.volume = key === "execute" ? 0.55 : 0.42;
    audioBank[key] = audio;
  }
  audioReady = true;
}

function playSound(key) {
  ensureAudioReady();
  const source = audioBank[key];
  if (!source) return;
  const audio = source.cloneNode();
  audio.volume = source.volume;
  audio.play().catch(() => {});
}

function flashCurrentCard() {
  const card = $("currentCard")?.querySelector(".card-detail");
  if (!card) return;
  card.classList.remove("card-flash");
  void card.offsetWidth;
  card.classList.add("card-flash");
}

function showDiceRoll(value) {
  const layer = $("fxLayer");
  if (!layer) return;
  const dice = document.createElement("div");
  dice.className = "dice-roll-fx";
  dice.textContent = value;
  layer.appendChild(dice);
  setTimeout(() => dice.remove(), 1100);
}

function showBotItemEffect(payload) {
  const layer = $("fxLayer");
  if (!layer) return;
  const item = payload?.item || payload?.hero || {};
  const name = cleanText(item.name || payload?.itemName || payload?.heroName || "Item");
  const player = cleanText(payload?.player || "");
  const broken = payload?.effect === "break";
  const heroFx = Boolean(payload?.hero);
  const fxKey = `${heroFx ? "hero" : "item"}:${searchKey(player)}:${searchKey(name)}:${broken ? "break" : "use"}`;
  const now = Date.now();
  if (recentItemFxKeys.has(fxKey) && now - recentItemFxKeys.get(fxKey) < 1200) {
    return;
  }
  recentItemFxKeys.set(fxKey, now);
  for (const [key, seenAt] of recentItemFxKeys.entries()) {
    if (now - seenAt > 3000) recentItemFxKeys.delete(key);
  }
  const fx = document.createElement("div");
  fx.className = `item-use-fx${heroFx ? " hero-use-fx" : ""}${broken ? " item-break-fx" : ""}`;
  const lane = ITEM_FX_LANES[itemFxLane % ITEM_FX_LANES.length];
  itemFxLane += 1;
  fx.style.setProperty("--item-fx-x", `${lane.x}px`);
  fx.style.setProperty("--item-fx-y", `${lane.y}px`);

  const src = String(item.image || "").trim();
  if (src) {
    const image = document.createElement("img");
    image.src = src;
    image.alt = name;
    fx.appendChild(image);
  } else {
    const fallback = document.createElement("div");
    fallback.className = "item-fx-fallback";
    fallback.textContent = (name[0] || "?").toUpperCase();
    fx.appendChild(fallback);
  }

  const label = document.createElement("div");
  label.className = "item-fx-label";
  label.textContent = heroFx ? name : (broken ? `${name} breaks` : name);
  fx.appendChild(label);

  if (player) {
    const playerLabel = document.createElement("div");
    playerLabel.className = "item-fx-player";
    playerLabel.textContent = player;
    fx.appendChild(playerLabel);
  }

  layer.appendChild(fx);
  setTimeout(() => fx.remove(), broken ? 1900 : 1700);
}

function botItemEffectFromLog(event) {
  if (event.kind !== "log" || !snapshot?.players?.length) return null;
  const textKey = searchKey(event.text || "");
  if (!textKey) return null;
  if (["nutilisepas", "nepeutpas", "impossible"].some((marker) => textKey.includes(marker))) {
    return null;
  }

  const useMarkers = ["utilise", "active", "avec", "gracea", "execute", "defausse", "remet", "repare", "vole", "absorbe"];
  const breakMarkers = ["brise", "brisee", "casse", "cassee", "detruit", "detruite"];
  const hasUseMarker = useMarkers.some((marker) => textKey.includes(marker));
  const hasBreakMarker = breakMarkers.some((marker) => textKey.includes(marker));

  for (const player of snapshot.players || []) {
    if (player.control === "human") continue;
    const playerMentioned = textKey.includes(searchKey(player.name));
    for (const item of player.items || []) {
      const itemNameKey = searchKey(item.name);
      if (!itemNameKey || !textKey.includes(itemNameKey)) continue;
      if (playerMentioned && hasUseMarker) {
        return {
          player: player.name,
          item,
          effect: item.intact === false || hasBreakMarker ? "break" : "use",
        };
      }
      if (hasBreakMarker) {
        return {
          player: player.name,
          item,
          effect: "break",
        };
      }
    }
  }
  return null;
}

function showHitEffect() {
  const layer = $("fxLayer");
  if (!layer) return;
  const hit = document.createElement("div");
  hit.className = "hit-fx";
  layer.appendChild(hit);
  let frame = 0;
  const frameMs = 1000 / 60;
  const timer = setInterval(() => {
    const x = frame % 4;
    const y = Math.floor(frame / 4);
    hit.style.backgroundPosition = `${x * 33.3333}% ${y * 33.3333}%`;
    frame += 1;
    if (frame >= 16) {
      clearInterval(timer);
      hit.remove();
    }
  }, frameMs);
}

function handleEventEffects(events) {
  for (const event of events || []) {
    if (handledFxEventIds.has(event.id)) continue;
    handledFxEventIds.add(event.id);
    const text = cleanText(event.text || "");
    const lowered = text.toLowerCase();

    if (event.kind === "setup" || event.kind === "party_round") {
      playSound("shuffle");
    } else if (event.kind === "card_drawn") {
      playSound("draw");
      flashCurrentCard();
    } else if (event.kind === "draft_pick" || event.kind === "human_decision") {
      playSound("playcard");
    } else if (event.kind === "bot_item_fx" || event.kind === "hero_fx") {
      const broken = event.payload?.effect === "break";
      playSound(broken ? "execute" : "playcard");
      showBotItemEffect(event.payload || {});
    }

    const rollMatch = text.match(/\broll un ([1-6])\b/i);
    if (rollMatch) {
      playSound("rolldie");
      showDiceRoll(rollMatch[1]);
    }

    if (event.kind === "log" && /ex[eéèÃ©]cut|execute|mort de/i.test(lowered)) {
      playSound("execute");
      showHitEffect();
    }

    const logItemFx = botItemEffectFromLog(event);
    if (logItemFx) {
      playSound(logItemFx.effect === "break" ? "execute" : "playcard");
      showBotItemEffect(logItemFx);
    }
  }
  if (handledFxEventIds.size > 800) {
    const recent = new Set(Array.from(handledFxEventIds).slice(-500));
    handledFxEventIds.clear();
    recent.forEach((id) => handledFxEventIds.add(id));
  }
}

function openCardZoom(src, title) {
  const modal = $("cardZoom");
  const image = $("cardZoomImage");
  const label = $("cardZoomTitle");
  if (!modal || !image || !src) return;
  image.src = src;
  image.alt = title || "Card";
  label.textContent = title || "";
  modal.hidden = false;
  modal.classList.add("open");
  $("cardZoomClose")?.focus();
}

function closeCardZoom() {
  const modal = $("cardZoom");
  const image = $("cardZoomImage");
  if (!modal || modal.hidden) return;
  modal.classList.remove("open");
  modal.hidden = true;
  if (image) image.removeAttribute("src");
}

function drawOptionForCurrentDecision() {
  const decision = snapshot?.pendingDecision;
  if (decision?.kind !== "next_action") return null;
  return (decision.options || []).find((option) => option.id === "draw") || null;
}

function renderDungeonStack(count, options = {}) {
  const total = Number(count || 0);
  if (!total) {
    return `<div class="empty">No remaining dungeon cards.</div>`;
  }
  const compact = Boolean(options.compact);
  const interactive = options.interactive !== false;
  const visible = Math.min(total, compact ? 12 : 24);
  const drawOption = drawOptionForCurrentDecision();
  const decisionAttrs = interactive && drawOption
    ? ` role="button" tabindex="0" data-decision="${escapeAttr(snapshot.pendingDecision.id)}" data-option="${escapeAttr(drawOption.id)}"`
    : "";
  const cards = Array.from({ length: visible }, (_, index) => {
    const offset = index * (compact ? 0.34 : 0.45);
    const angle = ((index * 7) % 13 - 6) * 0.18;
    return `<span class="dungeon-back-card" style="--dx:${offset}px; --dy:${-offset * 0.55}px; --rot:${angle}deg"></span>`;
  }).join("");
  return `
    <div class="dungeon-stack-wrap ${compact ? "is-compact" : ""}">
      <div class="dungeon-stack ${interactive && drawOption ? "is-ready" : ""}"${decisionAttrs} aria-label="Draw from dungeon">
        ${cards}
        <span class="dungeon-stack-count">${total}</span>
      </div>
    </div>
  `;
}

function renderDecisionDie() {
  return `
    <img class="decision-die-image" src="${STATIC_ASSETS}/ui/dice.png" alt="" aria-hidden="true" loading="lazy">
  `;
}

function renderDecisionActionVisual(option) {
  if (option.id === "draw") {
    return `<span class="decision-action-visual decision-stack">${renderDungeonStack(snapshot?.dungeon?.remainingCount || 0, {
      compact: true,
      interactive: false,
    })}</span>`;
  }
  if (option.id === "flee") {
    return `<span class="decision-action-visual">${renderDecisionDie()}</span>`;
  }
  return "";
}

function renderDecisionButton(decision, option) {
  const cls = option.id === decision.defaultId ? "default" : "secondary";
  const desc = cleanOptionDescription(option.description || "");
  const titleAttr = desc ? ` title="${escapeAttr(desc)}"` : "";
  const optionColor = itemColorCode(option) || option.color ? itemColorSwatch(option, "decision-color") : "";
  const visual = renderDecisionActionVisual(option);
  const actionClass = [
    cls,
    visual ? "decision-action-button" : "",
    option.id === "draw" ? "draw-decision-button" : "",
    option.id === "flee" ? "flee-decision-button" : "",
  ].filter(Boolean).join(" ");
  const buttonInner = `
    <span class="button-main">${isTeacherOption(decision, option) ? `<span class="teacher-mark">${TEACHER_MARK}</span>` : ""}${optionColor}<span>${escapeHtml(option.label)}</span></span>
  `;

  if (option.id === "draw") {
    return `
      <div class="decision-draw-control">
        ${visual}
        <button class="${actionClass}" data-decision="${decision.id}" data-option="${option.id}" type="button"${titleAttr}>
          ${buttonInner}
        </button>
      </div>
    `;
  }

  if (option.id === "flee") {
    return `
      <div class="decision-flee-control">
        ${visual}
        <button class="${actionClass}" data-decision="${decision.id}" data-option="${option.id}" type="button"${titleAttr}>
          ${buttonInner}
        </button>
      </div>
    `;
  }

  return `<button class="${actionClass}" data-decision="${decision.id}" data-option="${option.id}" type="button"${titleAttr}>
    ${buttonInner}${visual}
  </button>`;
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
  $("pilesMeta").textContent = "stacked dungeon | discard top first";
  $("dungeonCount").textContent = `${state.remainingCount || 0} left`;
  $("discardCount").textContent = `${state.discardCount || 0} cards`;
  $("dungeonRemaining").innerHTML = `
    ${renderDungeonStack(state.remainingCount || 0, { interactive: false })}
    ${remaining.length ? `<div class="dungeon-summary">${remaining.map((card) => renderPileCard(card)).join("")}</div>` : ""}
  `;
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
  const actionOptions = decision.options.filter((option) =>
    !option.heroId && (!option.itemId || (decision.kind || "").startsWith("choose_object_"))
  );
  const buttons = actionOptions
    .map((option) => renderDecisionButton(decision, option))
    .join("");
  const itemHint = decision.kind === "choose_combat_source"
    ? `<div class="combat-hint">Cliquez votre personnage ou un objet sur votre panneau pour l'utiliser.</div>`
    : decision.kind === "unstable_anvil"
      ? `<div class="combat-hint">Cliquez un objet brisé adverse pour le voler et le réparer.</div>`
      : "";
  $("decisionBox").innerHTML = `
    <div class="decision-content">
      <div class="muted">${escapeHtml(decision.player)}</div>
      <div class="card-name">${escapeHtml(decision.prompt)}</div>
      <div class="stats">${contextRows}</div>
      ${itemHint}
      <div class="decision-actions">${buttons}</div>
    </div>
  `;
  bindDecisionControls();
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
  const decision = snapshot?.pendingDecision?.kind === "draft_pick" ? snapshot.pendingDecision : null;
  $("draftHand").innerHTML = (draft.hand || []).map((item, index, hand) =>
    renderItem(item, {
      decision,
      fanIndex: index,
      fanCenter: (hand.length - 1) / 2,
    })
  ).join("");
}

function renderItem(item, options = {}) {
  const decision = options.decision || null;
  const itemOption = optionForItem(decision, item);
  const isCombatDecision = decision?.kind === "choose_combat_source";
  const isItemDecision = Boolean(decision && (decision.options || []).some((option) => option.itemId));
  const actionable = Boolean(itemOption);
  const teacher = isTeacherOption(decision, itemOption);
  const status = [
    item.intact === false ? "broken" : "",
    isItemDecision ? "combat-visible" : "",
    isCombatDecision && !actionable ? "not-legal" : "",
    actionable ? "actionable" : "",
    teacher ? "teacher-choice" : "",
    options.large ? "item-large" : "",
    options.fanIndex !== undefined ? "draft-fan-card" : "",
  ].filter(Boolean).join(" ");
  const description = cleanText(item.description || item.effect || "");
  const tooltip = description ? ` title="${escapeAttr(description)}"` : "";
  const actionAttrs = actionable
    ? ` role="button" tabindex="0" data-decision="${escapeAttr(decision.id)}" data-option="${escapeAttr(itemOption.id)}"`
    : "";
  const pv = Number(item.pv || 0);
  const flee = Number(item.flee || 0);
  const meta = [
    pv !== 0 ? `PV ${pv > 0 ? "+" : ""}${pv}` : "",
    flee ? `flee ${flee > 0 ? "+" : ""}${flee}` : "",
    item.active ? ACTIVE_MARK : "",
  ].filter(Boolean).join(" | ");
  const tags = [
    ...(item.types || []),
    ...(item.powers || []).map((p) => `power ${p}`),
  ].join(", ");
  const fanStyle = options.fanIndex !== undefined
    ? ` style="--fan-rot:${((options.fanIndex - options.fanCenter) * 1.4).toFixed(2)}deg; --fan-y:${Math.abs(options.fanIndex - options.fanCenter) * 2.5}px"`
    : "";
  return `
    <div class="item-card ${status}"${tooltip}${actionAttrs}${fanStyle}>
      <div class="item-name">
        ${assetImage(item, "item-art", item.name, description)}
        ${itemColorSwatch(item)}
        <span>${teacher ? `<span class="teacher-mark">${TEACHER_MARK}</span> ` : ""}${escapeHtml(item.name)}</span>
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

function playerStats(player) {
  return `
    ${chip(`PV ${player.pv}`)}
    ${chip(`score ${player.currentScore}`)}
    ${chip(`final ${player.score}`)}
    ${chip(`medals ${player.medals}`)}
    ${chip(`turn ${player.turn}`)}
  `;
}

function renderOpponent(player, index, decision) {
  const [status, statusClass] = statusFor(player);
  const itemList = (player.items || []).map((item) => renderItem(item, { decision })).join("");
  const monsterStack = renderMonsterStack(player.monsters || []);
  const strategyText = player.strategy ? ` | ${player.strategy}` : "";
  const thinking = botThinking.get(player.name);
  const thinkingLabel = thinking
    ? `${thinking.iterationsDone || 0}/${thinking.iterationsTotal || "?"}`
    : "";
  return `
    <article class="player opponent ${player.alive ? "" : "dead"} ${thinking ? "thinking" : ""}" data-player-index="${index}">
      <div class="player-head">
        <div>
          <div class="player-name">
            <span>${escapeHtml(player.name)}</span>
            ${thinking ? `<span class="thinking-indicator" title="ISMCTS thinking"><span class="thinking-spinner" aria-hidden="true"></span><span>${escapeHtml(thinkingLabel)}</span></span>` : ""}
          </div>
          <div class="muted">${escapeHtml(`${player.control}${strategyText}`)}</div>
        </div>
        <div class="${statusClass}">${status}</div>
      </div>
      <div class="player-body">
        <div class="hero-line">
          ${assetImage(player.hero, "hero-art", player.hero?.name)}
          <span>${escapeHtml(player.hero ? player.hero.name : "No hero")}</span>
        </div>
        <div class="stats">${playerStats(player)}</div>
        <div class="monster-row">${monsterStack}</div>
        <div class="mini-list">${itemList}</div>
      </div>
    </article>
  `;
}

function renderHumanPlayer(player, decision) {
  if (!player) {
    $("humanPanel").innerHTML = `<div class="empty">Start a game to see your hero and items.</div>`;
    return;
  }
  const [status, statusClass] = statusFor(player);
  const monsterStack = renderMonsterStack(player.monsters || []);
  const heroOption = optionForHero(decision, player.hero);
  const heroTeacher = isTeacherOption(decision, heroOption);
  const heroStatus = [
    heroOption ? "actionable hero-choice" : "",
    heroTeacher ? "teacher-choice" : "",
  ].filter(Boolean).join(" ");
  const heroAttrs = heroOption
    ? ` role="button" tabindex="0" data-decision="${escapeAttr(decision.id)}" data-option="${escapeAttr(heroOption.id)}"`
    : "";
  const itemList = (player.items || []).map((item) => renderItem(item, {
    decision,
    large: true,
  })).join("");
  $("humanPanel").innerHTML = `
    <div class="human-head">
      <div class="human-hero ${heroStatus}"${heroAttrs}>
        ${assetImage(player.hero, "human-hero-art", player.hero?.name)}
        <div>
          <div class="player-name">${escapeHtml(player.name)}</div>
          <div class="hero-title">${heroTeacher ? `<span class="teacher-mark">${TEACHER_MARK}</span>` : ""}${escapeHtml(player.hero ? player.hero.name : "No hero")}</div>
          <div class="muted">${escapeHtml(player.hero?.effect || "")}</div>
        </div>
      </div>
      <div class="${statusClass}">${status}</div>
    </div>
    <div class="human-body">
      <div class="human-summary">
        <div class="stats">${playerStats(player)}</div>
        <div class="monster-row">${monsterStack}</div>
      </div>
      <div class="human-items item-grid">${itemList || `<div class="empty">No items.</div>`}</div>
    </div>
  `;
}

function bindDecisionControls() {
  document.querySelectorAll("[data-decision]").forEach((control) => {
    if (control.dataset.bound === "1") return;
    control.dataset.bound = "1";
    control.addEventListener("click", async () => {
      if (control.dataset.busy === "1") return;
      control.dataset.busy = "1";
      if ("disabled" in control) control.disabled = true;
      await submitDecision(control.dataset.decision, control.dataset.option);
    });
    control.addEventListener("keydown", async (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      control.click();
    });
  });
}

function renderPlayers(players, decision) {
  const container = $("opponents");
  const nextPlayers = players || [];
  const human = nextPlayers.find((player) => player.control === "human") || null;
  const seen = new Set();

  renderHumanPlayer(human, decision);

  nextPlayers.forEach((player, index) => {
    if (player.control === "human") return;
    const cacheKey = String(index);
    const opponentDecision = decision?.kind === "unstable_anvil" ? decision : null;
    const renderKey = stableRenderKey({
      player,
      decision: opponentDecision,
      thinking: botThinking.get(player.name) || null,
    });
    const current = container.querySelector(`[data-player-index="${index}"]`);
    seen.add(cacheKey);

    if (current && playerRenderKeys.get(cacheKey) === renderKey) {
      return;
    }

    const html = renderOpponent(player, index, opponentDecision);
    if (current) {
      current.outerHTML = html;
    } else {
      container.insertAdjacentHTML("beforeend", html);
    }
    playerRenderKeys.set(cacheKey, renderKey);
  });

  container.querySelectorAll("[data-player-index]").forEach((playerNode) => {
    const cacheKey = playerNode.dataset.playerIndex;
    if (!seen.has(cacheKey)) {
      playerNode.remove();
      playerRenderKeys.delete(cacheKey);
    }
  });

  bindDecisionControls();
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
  renderIfChanged("status", {
    status: snapshot.status,
    mode: snapshot.mode,
    phase: snapshot.phase,
    round: snapshot.round,
  }, () => {
    $("statusLine").textContent = `${snapshot.status} | ${snapshot.mode} | ${snapshot.phase}`;
    $("phaseBadge").textContent = snapshot.phase || "setup";
    $("roundLabel").textContent = snapshot.round || "";
  });
  renderIfChanged("card", snapshot.currentCard, renderCard);
  renderIfChanged("dungeon", snapshot.dungeon, renderDungeon);
  renderIfChanged("decision", snapshot.pendingDecision, (decision) => {
    renderedDecisionId = null;
    renderDecision(decision);
  });
  renderIfChanged("draft", {
    draft: snapshot.draft,
    decision: snapshot.pendingDecision?.kind === "draft_pick" ? snapshot.pendingDecision : null,
  }, ({ draft }) => renderDraft(draft));
  renderIfChanged("players", {
    players: snapshot.players,
    decision: snapshot.pendingDecision,
    thinkingRevision,
  }, ({ players, decision }) => renderPlayers(players, decision));
  bindDecisionControls();
}

function collapsePiles() {
  $("dungeonDetails")?.removeAttribute("open");
  $("discardDetails")?.removeAttribute("open");
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
  ensureAudioReady();
  lastEventId = 0;
  lastPollStartedAt = 0;
  worstFrameMs = 0;
  perfSamples.length = 0;
  resetRenderKeys();
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
    ismctsIterations: Number($("ismctsIterations").value || 201),
    ismctsMaxSeconds: Number($("ismctsMaxSeconds").value || 20),
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
  startPolling();
}

async function submitDecision(decisionId, optionId) {
  if (!sessionId) return;
  ensureAudioReady();
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
  if (!sessionId || pollInFlight) return;
  pollInFlight = true;
  const startedAt = performance.now();
  const pollGapMs = lastPollStartedAt ? startedAt - lastPollStartedAt : 0;
  lastPollStartedAt = startedAt;
  try {
    const fetchStartedAt = performance.now();
    const [snapResponse, fullResponse] = await Promise.all([
      fetch(`/api/games/${sessionId}`),
      fetch(`/api/games/${sessionId}/events?after=${lastEventId}&level=full`),
    ]);
    const fetchMs = performance.now() - fetchStartedAt;
    if (snapResponse.status === 404 || fullResponse.status === 404) {
      stopPolling();
      sessionId = null;
      return;
    }
    if (!snapResponse.ok || !fullResponse.ok) return;
    const parseStartedAt = performance.now();
    const [snapText, fullText] = await Promise.all([
      snapResponse.text(),
      fullResponse.text(),
    ]);
    snapshot = JSON.parse(snapText);
    const fullBody = JSON.parse(fullText);
    const parseMs = performance.now() - parseStartedAt;
    const fullEvents = fullBody.events || [];
    if (fullEvents.length) {
      lastEventId = Math.max(lastEventId, ...fullEvents.map((e) => e.id));
      updateBotThinking(fullEvents);
      handleEventEffects(fullEvents);
      const logEvents = fullEvents.filter(isLogEvent);
      logs.full.push(...logEvents);
      logs.full = logs.full.slice(-600);
      logs.basic.push(...logEvents.filter((event) => event.basic));
      logs.basic = logs.basic.slice(-400);
    }
    const renderStartedAt = performance.now();
    render();
    const renderMs = performance.now() - renderStartedAt;
    const logRenderStartedAt = performance.now();
    renderLogs();
    const logRenderMs = performance.now() - logRenderStartedAt;
    recordPerf({
      totalMs: performance.now() - startedAt,
      pollGapMs,
      fetchMs,
      parseMs,
      renderMs,
      logRenderMs,
      serverMs: numericHeader(snapResponse, "x-response-time-ms")
        + numericHeader(fullResponse, "x-response-time-ms"),
      snapshotBytes: snapText.length,
      eventsBytes: fullText.length,
      eventCount: fullEvents.length,
    });
    if (snapshot?.status && snapshot.status !== "running") {
      stopPolling();
    }
  } finally {
    pollInFlight = false;
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(poll, 700);
}

function stopPolling() {
  if (!pollTimer) return;
  clearInterval(pollTimer);
  pollTimer = null;
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
$("cardZoomClose")?.addEventListener("click", closeCardZoom);
document.addEventListener("pointerdown", ensureAudioReady, { once: true });
document.addEventListener("click", (event) => {
  if (event.target.closest("#cardZoomClose")) return;
  if (event.target.id === "cardZoom") {
    closeCardZoom();
    return;
  }
  const image = event.target.closest("[data-zoom-src]");
  if (!image || image.closest("[data-decision]")) return;
  event.preventDefault();
  openCardZoom(image.dataset.zoomSrc, image.dataset.zoomTitle || image.alt);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeCardZoom();
});
updateBotStrategyControls();
startPolling();
