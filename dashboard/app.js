"use strict";

/* ====================================================================== Utilitaires */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Petite mise en forme des textes des IA (gras, listes, retours à la ligne), après échappement.
const md = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|\n)[ \t]*[-*•] +/g, "$1• ").replace(/\n/g, "<br>");
const plain = (t) => String(t ?? "").replace(/\*\*|#+ /g, "").replace(/\s*\n\s*/g, " ");
const num = (v) => (v === null || v === undefined || v === "" || isNaN(+v) ? null : +v);
const money = (v, d = 0) => num(v) === null ? "—" : `${new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: d, maximumFractionDigits: d }).format(v)} $`;
const pct = (v, d = 2) => num(v) === null ? "—" : `${v > 0 ? "+" : ""}${(+v).toFixed(d).replace(".", ",")} %`;
const nb = (v, d = 1) => num(v) === null ? "—" : (+v).toLocaleString("fr-FR", { maximumFractionDigits: d });
const tone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "muted");
const fmtDate = (d, opt) => new Date(d).toLocaleString("fr-FR", { timeZone: "Europe/Paris", ...opt });
const hm = (d) => fmtDate(d, { hour: "2-digit", minute: "2-digit" });
const dayHm = (d) => fmtDate(d, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const tryJSON = (s) => { try { return JSON.parse(s); } catch { return null; } };

// En ligne (GitHub Pages), pas de serveur : on lit les fichiers générés par build_site.py.
const STATIC = !!window.STATIC_SITE;
function staticPath(p) {
  const u = new URL(p, location.href);
  if (u.pathname.endsWith("/api/session")) return `data/sessions/${encodeURIComponent(u.searchParams.get("nom"))}.json`;
  return `data/${u.pathname.split("/").pop()}.json`;
}
const api = (p, opt) => fetch(STATIC ? `${staticPath(p)}?v=${Date.now()}` : p, opt).then((r) => r.json());

/* ====================================================================== Icônes Flow (trait 1,6 px) */
const P = {
  home: '<path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z"/>',
  users: '<circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.6-3 2.8-4.6 5.5-4.6s4.9 1.6 5.5 4.6"/><path d="M15.5 5.6a3 3 0 0 1 0 5.8M17.5 14.6c1.6.6 2.7 2 3 4.4"/>',
  list: '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><circle cx="4.8" cy="6.5" r=".9"/><circle cx="4.8" cy="12" r=".9"/><circle cx="4.8" cy="17.5" r=".9"/>',
  desktop: '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20h6M12 16.5V20"/>',
  briefcase: '<rect x="3.5" y="7" width="17" height="12.5" rx="2"/><path d="M8.5 7V5.5a1.5 1.5 0 0 1 1.5-1.5h4a1.5 1.5 0 0 1 1.5 1.5V7M3.5 12.5h17"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  chart: '<path d="M4 4v16h16"/><path d="m7.5 14.5 3.5-3.5 3 3 5-5.5"/>',
  spark: '<path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3M6 6l2.1 2.1M15.9 15.9 18 18M6 18l2.1-2.1M15.9 8.1 18 6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M5.5 18.5l1.4-1.4M17.1 6.9l1.4-1.4"/>',
  moon: '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  minus: '<path d="M6 12h12"/>',
  square: '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  down: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
  alert: '<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5M12 17h.01"/>',
  key: '<circle cx="8" cy="15" r="3.5"/><path d="m10.5 12.5 8-8M15.5 7.5l2.5 2.5"/>',
  filter: '<path d="M4 5h16l-6 7.5V19l-4-2v-4.5z"/>',
  news: '<rect x="3.5" y="5" width="13" height="14.5" rx="1.5"/><path d="M16.5 9h3v8.5a2 2 0 0 1-4 0M7 9h6M7 12.5h6M7 16h3.5"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/>',
  doc: '<path d="M6.5 3.5h7l4 4v13h-11z"/><path d="M13.5 3.5v4h4M9 12h6M9 15.5h6"/>',
  edit: '<path d="M14.5 5.5l4 4L9 19H5v-4z"/><path d="M12.5 7.5l4 4"/>',
  book: '<path d="M4.5 5.5c2.5-1 5-1 7.5.5v13c-2.5-1.5-5-1.5-7.5-.5zM19.5 5.5c-2.5-1-5-1-7.5.5v13c2.5-1.5 5-1.5 7.5-.5z"/>',
  wallet: '<rect x="3.5" y="6" width="17" height="13" rx="2"/><path d="M3.5 9.5h17M16 14h1.5"/>',
  chat: '<path d="M4.5 6.5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H10l-4 3.5v-3.5h0.5a2 2 0 0 1-2-2z"/>',
  shield: '<path d="M12 3.5 5 6v5.5c0 4.5 3 7.7 7 9 4-1.3 7-4.5 7-9V6z"/>',
  send: '<path d="M20 4 3.5 11l6.5 2.5L12.5 20z"/><path d="m10 13.5 4-4"/>',
  note: '<path d="M5 4.5h14v10l-5 5H5z"/><path d="M14 19.5v-5h5M8.5 9h7M8.5 12h4"/>',
  bell: '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 3.5 5.4 3.5 8.5s-1 5.9-3.5 8.5c-2.5-2.6-3.5-5.4-3.5-8.5s1-5.9 3.5-8.5z"/>',
  // Les IA
  qualite: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4M8.5 11h5M11 8.5v5"/>',
  equilibre: '<path d="M12 4v16M7 20h10M5 7.5h14"/><path d="m5 7.5-2.5 6a2.5 2.5 0 0 0 5 0zM19 7.5l-2.5 6a2.5 2.5 0 0 0 5 0z"/>',
  sentiment: '<path d="M12 21c3.9 0 6.5-2.8 6.5-6.5 0-2.8-1.9-5-3.3-6.4-.3 1.8-1.3 2.8-2.3 2.8 0-2.8-1.4-5.6-3.6-7.4.1 3.8-3.8 6-3.8 11 0 3.7 2.6 6.5 6.5 6.5z"/>',
  contrarien: '<path d="M4.5 8h13l-3-3M19.5 16h-13l3 3"/>',
  critique: '<path d="M12 3.5 5 6v5.5c0 4.5 3 7.7 7 9 4-1.3 7-4.5 7-9V6z"/><path d="m9 12 2 2 4-4"/>',
  gerant: '<path d="m3.5 8.5 4 3 4.5-6 4.5 6 4-3-2 10h-13z"/><path d="M5.5 20.5h13"/>',
};
const icon = (name, cls = "ic") =>
  `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || P.spark}</svg>`;

const META = {
  qualite: { color: "var(--sky)", tag: "Analyste · qualité et chiffres",
    desc: "Épluche les chiffres (croissance, marges, dette, valorisation) et propose des entreprises solides à prix raisonnable. Comme « Claude » chez Aywen." },
  equilibre: { color: "var(--sage)", tag: "Analyste · diversification",
    desc: "Cherche des idées dans des secteurs variés pour équilibrer le compte et limiter le risque. Comme « ChatGPT » chez Aywen." },
  sentiment: { color: "var(--peach)", tag: "Analyste · sentiment et risque",
    desc: "Suit l'humeur des réseaux et l'actualité chaude : tendances Reddit, actions en forte dynamique. Comme « Grok », le gagnant de la vidéo." },
  contrarien: { color: "var(--plum)", tag: "Analyste · contrarien, préférence Europe",
    desc: "Cherche les actions qui ont beaucoup chuté, de préférence européennes cotées à New York, à condition de prouver que le marché s'est trompé. Comme « Mistral » chez Aywen." },
  critique: { color: "var(--ink-3)", tag: "Critique · avocat du diable",
    desc: "Contrôle chaque proposition avec les outils : faits datés, catalyseur dans l'horizon, stop hors du bruit, paris corrélés. Verdict : ok, réserve ou rejet." },
  gerant: { color: "var(--coral)", tag: "Gérant · stratégie Qualité",
    desc: "Reçoit les propositions et les avis, vérifie avec les outils, décide et passe les ordres sur le compte. Ses notes sont le journal de bord de l'équipe." },
};
const ROLE = { analyste: "Analyste", critique: "Critique", gerant: "Gérant" };
const MODE = { preparation: ["Préparation", "pill-coral"], ouverture: ["Ouverture", "pill-sky"], suivi: ["Suivi", "pill-plum"] };
const STATUT = { en_attente: ["En attente", "pill-peach"], execute: ["Exécuté", "pill-sage"], annule: ["Annulé", ""],
  rejete: ["Refusé", "pill-danger"], erreur: ["Erreur", "pill-danger"] };
const VERDICT = { ok: ["ok", "pill-sage"], reserve: ["réserve", "pill-peach"], rejet: ["rejet", "pill-danger"] };

const S = {
  ov: null, sessions: [], notes: {}, live: null, wasRunning: false, page: "accueil",
  sel: null, cache: {}, iaSel: "gerant", jAgent: "tous", jType: "tout",
  deskScope: "last", deskData: [], wins: {}, z: 20,
};

function toast(msg, ic = "info") {
  const t = $("#toast");
  t.innerHTML = `${icon(ic)}<span>${esc(msg)}</span>`;
  t.classList.add("show");
  clearTimeout(toast.h);
  toast.h = setTimeout(() => t.classList.remove("show"), 3200);
}
const empty = (ic, title, sub) =>
  `<div class="empty"><span class="ic-box">${icon(ic)}</span><b>${esc(title)}</b><span class="small">${esc(sub)}</span></div>`;
const agentOf = (id) => S.ov?.agents.find((a) => a.id === id) || { id, nom: id, provider: "", cle: "", role: "" };
const shortName = (id) => agentOf(id).nom.replace("Analyste ", "");
const avatar = (id, small) => `<span class="avatar${small ? " sm" : ""}" style="--c:${META[id]?.color || "var(--coral)"}" title="${esc(agentOf(id).nom)}">${icon(id)}</span>`;
const providerPill = (a) => `<span class="pill ${a.provider === "gemini" ? "pill-sky" : "pill-peach"}">${a.provider === "gemini" ? "Gemini" : "Groq"} · clé ${a.cle}</span>`;
const modelName = (m) => String(m || "").replace(/^(gemini|groq)#\d:/, "").replace("openai/", "").replace("qwen/", "");
const verdictPill = (v) => v ? `<span class="pill ${VERDICT[v.verdict]?.[1] || ""}">critique : ${esc(VERDICT[v.verdict]?.[0] || v.verdict)}</span>` : '<span class="pill">pas d\'avis</span>';
const modePill = (m) => `<span class="pill ${MODE[m]?.[1] || ""}">${esc(MODE[m]?.[0] || m || "Séance")}</span>`;
const sessLabel = (s) => `${MODE[s.mode]?.[0] || "Séance"} du ${s.quand || s.nom}${s.simulation ? " (simulation)" : ""}`;

function actionPill(action) {
  const a = String(action || "").toLowerCase();
  const cls = a.startsWith("vend") || a.startsWith("all") ? "pill-danger" : a === "ajuster_stop" ? "pill-sky" : "pill-sage";
  return `<span class="pill ${cls}">${esc(String(action || "").replace("_", " "))}</span>`;
}

/* ====================================================================== Thème */
function applyThemeButton() {
  const dark = document.documentElement.dataset.theme === "dark";
  $("#theme-btn").innerHTML = icon(dark ? "sun" : "moon");
  $("#theme-btn").setAttribute("aria-label", dark ? "Passer en thème clair" : "Passer en thème sombre");
}
$("#theme-btn").onclick = () => {
  const dark = document.documentElement.dataset.theme !== "dark";
  if (dark) document.documentElement.dataset.theme = "dark";
  else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch (e) { /* stockage indisponible */ }
  applyThemeButton();
};

/* ====================================================================== Navigation entre les 4 pages */
const PAGES = ["accueil", "ia", "journal", "bureau"];
function route() {
  const p = location.hash.slice(1).split("?")[0];
  S.page = PAGES.includes(p) ? p : "accueil";
  $$(".page").forEach((s) => (s.hidden = s.dataset.page !== S.page));
  $$(".nav-item, .tabbar a").forEach((a) => a.classList.toggle("active", a.dataset.p === S.page));
  document.body.classList.toggle("on-desk", S.page === "bureau");
  window.scrollTo(0, 0);
  renderPage();
}
function go(page) { if (location.hash !== `#${page}`) location.hash = page; else route(); }
window.addEventListener("hashchange", route);

function renderPage() {
  if (!S.ov) return;
  if (S.page === "accueil") {
    renderBand(S.ov); renderChart(S.ov); renderDay(); renderPositions(S.ov); renderPlan(S.ov); renderRepartition(S.ov);
    renderBilan(S.ov); renderStats(S.ov); renderLecons(S.ov); renderRappelsCard(S.ov); renderSysteme(S.ov);
  }
  if (S.page === "ia") { renderIAList(); renderIAPanel(); renderRanking(S.ov); }
  if (S.page === "journal") renderJournal();
  if (S.page === "bureau") renderDesktop();
}

/* ====================================================================== En-tête */
function relTime(iso) {
  const ms = new Date(iso) - Date.now();
  if (isNaN(ms)) return "";
  const h = Math.floor(ms / 3.6e6), m = Math.round((ms % 3.6e6) / 6e4);
  return h >= 20 ? fmtDate(iso, { weekday: "long", hour: "2-digit", minute: "2-digit" })
    : h > 0 ? `dans ${h} h ${String(m).padStart(2, "0")}` : `dans ${m} min`;
}

function renderHeader(o) {
  const [cls, label] = o.demo ? ["pill-peach", "Démo"] : o.paper ? ["pill-sky", "Paper trading"] : ["pill-danger", "Argent réel"];
  $$(".js-mode").forEach((b) => { b.className = `js-mode pill ${cls}`; b.textContent = label; });
  const h = o.horloge || {};
  $$(".js-market").forEach((m) => {
    m.innerHTML = `<i class="dot ${h.is_open ? "on" : ""}"></i><span>${h.is_open
      ? `Bourse de New York ouverte · ferme ${esc(relTime(h.next_close))}`
      : `Bourse fermée · ouvre ${esc(relTime(h.next_open))}`}</span>`;
  });
  $("#btn-sim span").textContent = STATIC ? "Forcer le lancement" : o.demo ? "Lancer une démo" : "Lancer une simulation";
  $("#btn-sim").hidden = STATIC && !o.depot;
  $$(".js-depot").forEach((el) => (el.textContent = o.depot || "bot-ia-trading"));
  $("#btn-real").hidden = !!o.demo || STATIC;

  const ban = $("#banner");
  const show = (kind, ic, html) => { ban.className = `banner ${kind}`; ban.innerHTML = `${icon(ic)}<span>${html}</span>`; ban.hidden = false; };
  const missed = STATIC ? missedSession(o) : "";
  if (o.erreur) show("err", "alert", `Alpaca ne répond pas : ${esc(o.erreur)}`);
  else if (missed) {
    const prep = missed.startsWith("la préparation");
    show("warn", "alert", `<b>Séance manquée</b> : ${esc(missed)} GitHub saute parfois ses horaires. ${prep ? "Avant 15 h 30, la préparation lancée maintenant exécutera elle-même son plan à l'ouverture." : ""}
      <button class="btn" id="missed-run" style="margin-left:8px">${icon("send")}${prep ? "Lancer la préparation" : "Lancer une séance"}</button>`);
    $("#missed-run").onclick = () => {
      openForce();
      $("#force-mode").value = prep ? "preparation" : "auto";
      $("#force-sim").checked = false;
    };
  }
  else if (STATIC) show("info", "info", `Version en ligne, mise à jour après chaque séance. Dernière mise à jour : ${esc(fmtDate(o.genere_le, { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }))}.`);
  else if (o.demo) show("warn", "info", "Mode démo : aucune clé Alpaca dans le fichier .env, les chiffres affichés sont factices.");
  else ban.hidden = true;

  const k = o.cles || {}, L = o.limites || {};
  $("#nav-foot").innerHTML = `
    <div class="row"><span>Clés Gemini</span><span class="pill ${k.gemini >= 3 || o.demo ? "pill-sage" : "pill-peach"}">${o.demo ? "démo" : `${k.gemini}/3`}</span></div>
    <div class="row"><span>Clés Groq</span><span class="pill ${k.groq >= 3 || o.demo ? "pill-sage" : "pill-peach"}">${o.demo ? "démo" : `${k.groq}/3`}</span></div>
    <div class="row"><span>Max par titre</span><span>${esc(L.max_position_pct)} %</span></div>
    <div class="row"><span>Écart max à l'ouverture</span><span>${esc(L.max_gap_pct)} %</span></div>`;
}

// Calculé par le navigateur à l'heure où l'on regarde le site : si plus rien ne tourne sur GitHub,
// le site n'est plus republié, mais l'alerte apparaît quand même.
function missedSession(o) {
  const now = new Date();
  const nyToday = now.toLocaleDateString("sv-SE", { timeZone: "America/New_York" });
  const parisH = +now.toLocaleString("en-GB", { timeZone: "Europe/Paris", hour: "2-digit", hour12: false });
  const days = o.jours_bourse || [];
  const nyDay = new Date(`${nyToday}T12:00:00Z`).getUTCDay();
  const trading = days.length ? days.includes(nyToday) : nyDay > 0 && nyDay < 6;
  const planDate = "plan_reel" in o ? o.plan_reel : o.plan?.date;
  if (trading && parisH >= 12 && planDate !== nyToday) return "la préparation de ce matin n'a pas eu lieu (aucun plan pour aujourd'hui).";
  const last = o.alertes?.ts ? new Date(o.alertes.ts) : null;
  const before = days.filter((d) => d < nyToday);
  if (last && before.length >= 2 && last.toLocaleDateString("sv-SE", { timeZone: "America/New_York" }) < before[before.length - 2])
    return `aucune séance depuis le ${dayHm(last)}.`;
  return "";
}

/* ====================================================================== Page 1 : Accueil */
function renderBand(o) {
  const a = o.compte;
  if (!a) return;
  $$(".band .skeleton").forEach((e) => e.classList.remove("skeleton"));
  const day = a.equity - a.last_equity;
  $("#k-equity").textContent = money(a.equity, 2);
  $("#k-day").innerHTML = `<span class="${tone(day)}" style="display:inline-flex;align-items:center;gap:4px">${icon(day >= 0 ? "up" : "down")}${esc(money(Math.abs(day), 2))} (${esc(pct(a.last_equity ? (day / a.last_equity) * 100 : 0))})</span> aujourd'hui`;
  const h = o.historique || [];
  const first = h.find((p) => p.v > 0);
  const perf = first ? (a.equity / first.v - 1) * 100 : 0;
  $("#k-perf").innerHTML = `<span class="${tone(perf)}">${esc(pct(perf))}</span>`;
  const spy = spyPerf(o, first);
  $("#k-perf-sub").innerHTML = first
    ? `${esc(money(a.equity - first.v, 0))} depuis le ${esc(fmtDate(first.t * 1000, { day: "numeric", month: "short" }))}${spy !== null ? ` · S&amp;P 500 : <span class="${tone(spy)}">${esc(pct(spy, 1))}</span>` : ""}`
    : "";
  const e = o.equipe || {};
  const cash = e.cash ?? a.cash, total = e.valeur || a.equity || 1;
  $("#k-cash").textContent = money(cash, 0);
  $("#k-cash-bar").style.width = `${Math.max(0, Math.min(100, (cash / total) * 100))}%`;
  const pos = o.positions || [];
  const pl = pos.reduce((s, p) => s + (p.pl || 0), 0);
  $("#k-pos").textContent = `${pos.length}`;
  $("#k-pos-sub").innerHTML = pos.length ? `Latent : <span class="${tone(pl)}">${esc(money(pl, 0))}</span> · max ${esc(o.limites.max_positions)}`
    : `${((cash / total) * 100).toFixed(0)} % en liquidités`;
}

function smoothPath(pts) {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`;
  }
  return d;
}

// Performance du S&P 500 (fonds SPY) depuis la même date que le compte.
function spyPerf(o, first) {
  const s = (o.spy || []).filter((b) => b.t && b.c);
  if (!first || s.length < 2) return null;
  const d0 = new Date(first.t * 1000).toISOString().slice(0, 10);
  const start = s.find((b) => b.t >= d0) || s[0];
  return (s[s.length - 1].c / start.c - 1) * 100;
}

function renderChart(o) {
  const box = $("#chart");
  let pts = (o.historique || []).map((p) => ({ t: p.t * 1000, v: p.v }));
  if (pts.length < 2) pts = (o.historique_ia || []).map((r) => ({ t: new Date(r.date).getTime(), v: r.valeur }));
  if (pts.length < 2) {
    box.innerHTML = empty("chart", "Pas encore d'historique", "La courbe apparaîtra après les premières séances.");
    return;
  }
  // Le S&P 500 ramené à la même valeur de départ que le compte, pour comparer les deux courbes.
  const d0 = new Date(pts[0].t).toISOString().slice(0, 10);  // même date de départ que spyPerf()
  const spyRaw = (o.spy || []).filter((b) => b.t && b.c && b.t >= d0)
    .map((b) => ({ t: new Date(`${b.t}T21:00:00Z`).getTime(), c: b.c }));
  const spyPts = spyRaw.length >= 2 ? spyRaw.map((b) => ({ t: b.t, v: (pts[0].v * b.c) / spyRaw[0].c })) : [];
  $("#chart-legend").innerHTML = spyPts.length
    ? `<span class="legend"><i style="background:var(--coral)"></i>Compte</span><span class="legend"><i style="background:var(--sky)"></i>S&amp;P 500</span>`
    : "30 derniers jours";
  const W = box.clientWidth || 700, H = box.clientHeight || 260, L = 70, R = 12, T = 12, B = 28;
  const allT = [...pts, ...spyPts].map((p) => p.t);
  const t0 = Math.min(...allT), t1 = Math.max(...allT);
  const allV = [...pts, ...spyPts].map((p) => p.v);
  let lo = Math.min(...allV), hi = Math.max(...allV);
  const pad = (hi - lo) * 0.15 || hi * 0.01 || 1;
  lo -= pad; hi += pad;
  const x = (t) => L + ((t - t0) / ((t1 - t0) || 1)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  let grid = "";
  for (let k = 0; k <= 4; k++) {
    const v = lo + ((hi - lo) * k) / 4;
    grid += `<line class="c-grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="c-label" x="${L - 10}" y="${y(v) + 4}" text-anchor="end">${esc(money(v, 0))}</text>`;
  }
  for (let k = 0; k < 4; k++) {
    const t = t0 + ((t1 - t0) * k) / 3;
    grid += `<text class="c-label" x="${x(t)}" y="${H - 6}" text-anchor="${k === 0 ? "start" : k === 3 ? "end" : "middle"}">${esc(fmtDate(t, { day: "numeric", month: "short" }))}</text>`;
  }
  const xy = pts.map((p) => [x(p.t), y(p.v)]);
  const last = xy[xy.length - 1];
  const spyXY = spyPts.map((p) => [x(p.t), y(p.v)]);
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Évolution de la valeur du compte comparée au S&P 500">
    <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="c-stop-a"/><stop offset="1" class="c-stop-b"/></linearGradient></defs>
    ${grid}<path d="${smoothPath(xy)} L${last[0]},${H - B} L${xy[0][0]},${H - B} Z" fill="url(#area)"/>
    ${spyXY.length ? `<path class="c-spy" d="${smoothPath(spyXY)}"/>` : ""}
    <path class="c-line" d="${smoothPath(xy)}"/><circle class="c-dot" cx="${last[0]}" cy="${last[1]}" r="4.5"/></svg>`;
}

/* ---------- Accueil : bilan, rappels, état du système ---------- */
function renderBilan(o) {
  const b = o.bilan || {};
  $("#bilan-card").hidden = !b.texte;
  if (!b.texte) return;
  $("#bilan-date").textContent = `vendredi ${fmtDate(`${b.date}T12:00:00Z`, { day: "numeric", month: "long" })}`;
  $("#bilan-text").innerHTML = md(b.texte);
}

const kvBox = (rows) => `<div class="kv">${rows.map(([k, v, cls]) => `<div><span>${esc(k)}</span><b class="${cls || ""}">${esc(v)}</b></div>`).join("")}</div>`;

function renderStats(o) {
  const s = o.stats || {};
  $("#stats-sub").textContent = s.debut ? `depuis le ${fmtDate(`${s.debut}T12:00:00Z`, { day: "numeric", month: "long" })}` : "";
  if (!s.debut && !s.ventes) {
    $("#stats-card").innerHTML = empty("chart", "Pas encore de statistiques", "Elles apparaîtront après les premières séances.");
    return;
  }
  const ecart = num(s.perf_pct) !== null && num(s.spy_pct) !== null ? s.perf_pct - s.spy_pct : null;
  $("#stats-card").innerHTML = kvBox([
    ["Performance du compte", pct(s.perf_pct), tone(s.perf_pct)],
    ["S&P 500 sur la période", pct(s.spy_pct), tone(s.spy_pct)],
    ["Écart avec le marché", ecart === null ? "—" : pct(ecart), tone(ecart)],
    ["Plus forte baisse", pct(s.drawdown_max_pct), s.drawdown_max_pct < 0 ? "down" : ""],
    ["Ventes clôturées", nb(s.ventes, 0)],
    ["Ventes gagnantes", s.reussite_pct === null || s.reussite_pct === undefined ? "—" : `${s.gagnantes} (${s.reussite_pct} %)`],
    ["Gain moyen", money(s.gain_moyen, 0), tone(s.gain_moyen)],
    ["Perte moyenne", money(s.perte_moyenne, 0), tone(s.perte_moyenne)],
    ["Plus-values réalisées", money(s.realise, 0), tone(s.realise)],
  ]) + '<p class="small muted" style="margin:10px 0 0">La plus forte baisse mesure la chute maximale du compte depuis son plus haut.</p>';
}

function renderLecons(o) {
  const l = (o.lecons || []).slice().reverse();
  $("#lecons-sub").textContent = l.length ? `${l.length} leçon${l.length > 1 ? "s" : ""}` : "";
  $("#lecons-card").innerHTML = l.length
    ? `<div class="list">${l.slice(0, 8).map((x) => `<div class="order">${x.auteur === "bilan" ? '<span class="pill">bilan</span>' : avatar(x.auteur, true)}<span class="small muted">${esc(fmtDate(`${x.date}T12:00:00Z`, { day: "numeric", month: "short" }))}</span><div class="why">${esc(x.texte)}</div></div>`).join("")}</div>`
    : empty("book", "Aucune leçon pour l'instant", "Les IA notent ici les règles tirées de leurs erreurs et de leurs réussites. Elles les relisent à chaque séance.");
}

function renderRanking(o) {
  const c = o.classement || {};
  const rows = (c.analystes || []).filter((r) => r.propositions);
  $("#rank-sub").textContent = c.propositions ? `${c.propositions} idée${c.propositions > 1 ? "s" : ""} d'achat depuis le ${fmtDate(`${c.depuis}T12:00:00Z`, { day: "numeric", month: "short" })}` : "";
  if (!rows.length) {
    $("#rank-card").innerHTML = empty("spark", "Pas encore de classement", "Après les premières séances réelles, on mesure ce qu'aurait rapporté chaque idée des analystes depuis qu'elle a été proposée, achetée ou non.");
    return;
  }
  const cell = (v) => `<span class="${tone(v)}">${esc(pct(v, 1))}</span>`;
  const crit = c.critique || {};
  $("#rank-card").innerHTML = `<div class="table-wrap"><table class="tbl-tight"><thead><tr><th>Analyste</th><th>Idées</th><th>Achetées</th><th>Rendement moyen</th><th>Gagnantes</th><th>Moy. achetées</th><th>Moy. écartées</th><th>Meilleure · pire</th></tr></thead><tbody>
    ${rows.map((r, i) => `<tr><td><span style="display:inline-flex;align-items:center;gap:8px">${avatar(r.id, true)}<b>${i + 1}. ${esc(shortName(r.id))}</b></span></td><td>${r.propositions}</td><td>${r.retenues}</td><td>${cell(r.rendement_moyen)}</td><td>${r.reussite_pct ?? "—"} %</td><td>${cell(r.moyenne_retenues)}</td><td>${cell(r.moyenne_ecartees)}</td>
      <td class="mono" style="white-space:nowrap">${r.meilleure ? `${esc(r.meilleure.symbole)} ${cell(r.meilleure.rendement)}` : "—"}${r.pire && r.pire.symbole !== r.meilleure?.symbole ? ` · ${esc(r.pire.symbole)} ${cell(r.pire.rendement)}` : ""}</td></tr>`).join("")}
    </tbody></table></div>
    <p class="small muted" style="margin:10px 0 0">Rendement mesuré depuis le prix du jour de la proposition, jusqu'au dernier cours.${crit.avis ? ` Avis du critique confirmés par la suite : ${crit.justes_pct} % (${crit.avis} avis « ok » ou « rejet »).` : ""}</p>`;
}

function rappelRow(r) {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "America/New_York" });
  const st = r.statut !== "actif" ? [r.statut === "fait" ? "traité" : "expiré", r.statut === "fait" ? "pill-sage" : ""]
    : r.date <= today ? ["aujourd'hui", "pill-coral"] : [fmtDate(`${r.date}T12:00:00Z`, { day: "numeric", month: "short" }), "pill-peach"];
  const who = r.cree_par === "systeme" ? '<span class="pill">automatique</span>' : avatar(r.cree_par, true);
  return `<div class="order">${who}<span class="pill ${st[1]}">${esc(st[0])}</span>${r.symbole ? `<span class="mono"><b>${esc(r.symbole)}</b></span>` : ""}<b>${esc(r.titre)}</b>
    ${r.details ? `<div class="why">${md(r.details)}</div>` : ""}${r.note ? `<div class="why"><b>Traité :</b> ${esc(r.note)}</div>` : ""}</div>`;
}

function allRappels(o) {
  const map = new Map((o.rappels || []).map((r) => [r.id, r]));
  (S.sel?.rappels || []).forEach((r) => { if (!map.has(r.id)) map.set(r.id, { ...r, simulation: S.sel.simulation }); });
  return [...map.values()];
}

function renderRappelsCard(o) {
  const actifs = allRappels(o).filter((r) => r.statut === "actif").sort((a, b) => a.date.localeCompare(b.date));
  $("#rappels-sub").textContent = actifs.length ? `${actifs.length} actif${actifs.length > 1 ? "s" : ""}` : "";
  $("#rappels-card").innerHTML = actifs.length ? `<div class="list">${actifs.slice(0, 6).map(rappelRow).join("")}</div>`
    : empty("bell", "Aucun rappel", "Les IA créent des rappels pour les événements datés (résultats, annonces…) ; ceux des actions détenues sont ajoutés automatiquement.");
}

function renderSysteme(o) {
  const v = o.installation || {};
  if (!v.date) {
    $("#systeme-sub").textContent = "";
    $("#systeme-card").innerHTML = empty("shield", "Pas encore vérifié", "La vérification complète se lance toute seule avant la première séance (ou avec python main.py --verifier).");
    return;
  }
  $("#systeme-sub").innerHTML = `<span class="pill ${v.ok ? "pill-sage" : "pill-danger"}">${v.ok ? "prêt à trader" : "problème critique"}</span>`;
  const bad = (v.checks || []).filter((c) => !c.ok);
  const al = o.alertes || {};
  const alerts = (al.frein ? `<div class="banner err" style="margin:0 0 10px">${icon("alert")}<span><b>Frein d'urgence</b> à la séance du ${esc(al.quand)} : ${esc(al.frein)}. Aucun achat tant que la perte dépasse le seuil.</span></div>` : "")
    + ((al.ecarts || []).length ? `<div class="banner warn" style="margin:0 0 10px">${icon("alert")}<span><b>Écart avec Alpaca</b> : ${esc(al.ecarts.join(" ; "))}. Vérifiez les positions sur le site d'Alpaca.</span></div>` : "");
  $("#systeme-card").innerHTML = alerts + `<p class="small muted" style="margin:0 0 10px">Vérifié le ${esc(dayHm(v.date))} : ${esc(v.reussis)}/${esc(v.total)} tests réussis.</p>
    <div class="list">${(bad.length ? bad : (v.checks || []).slice(0, 5)).map((c) => `<div class="order"><span class="pill ${c.ok ? "pill-sage" : c.niveau === "critique" ? "pill-danger" : "pill-peach"}">${c.ok ? "ok" : c.niveau === "critique" ? "échec" : "attention"}</span><b>${esc(c.nom)}</b><div class="why">${esc(c.detail)}</div></div>`).join("")}</div>
    ${bad.length ? "" : '<p class="small muted" style="margin:10px 0 0">Tout fonctionne : clés, broker, données, IA et garde-fous.</p>'}`;
}

function todayParis(d) { return fmtDate(d, { year: "numeric", month: "2-digit", day: "2-digit" }); }

function renderDay() {
  const o = S.ov;
  if (!o) return;
  const now = new Date();
  const plan = o.plan || {};
  const h = o.horloge || {};
  const prepH = o.limites?.preparation_heure ?? 9;
  const openAt = h.next_open && todayParis(h.next_open) === todayParis(now) ? hm(h.next_open) : "15:30";
  const suiviAt = hm(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 17, 30)));
  const planToday = plan.cree_le && todayParis(plan.cree_le) === todayParis(now) && !plan.simulation;
  const nPlan = (plan.ordres || []).length;
  const isoParis = now.toLocaleDateString("sv-SE", { timeZone: "Europe/Paris" });
  const suiviDone = S.sessions.some((s) => s.mode === "suivi" && !s.simulation && s.nom.startsWith(isoParis));
  const live = S.live?.etat || {};
  const running = S.live?.runner?.running || live.running;
  const steps = [
    ["preparation", `${String(prepH).padStart(2, "0")}:00`, "Préparation", "L'équipe décide quoi acheter à l'ouverture",
      planToday ? `${nPlan} ordre${nPlan > 1 ? "s" : ""} planifié${nPlan > 1 ? "s" : ""}` : null],
    ["ouverture", openAt, "Ouverture de New York", "Exécution automatique des ordres planifiés",
      planToday && plan.execute_le ? `exécuté à ${hm(plan.execute_le)}` : null],
    ["suivi", suiviAt, "Suivi", "L'équipe fait le point et agit en direct", suiviDone ? "fait" : null],
  ];
  $("#day").innerHTML = steps.map(([k, t, title, sub, done]) => {
    const active = running && live.mode === k;
    return `<li class="day-step ${done ? "done" : ""} ${active ? "active" : ""}">
      <span class="day-t mono">${esc(t)}</span><span class="day-dot">${done ? icon("check", "") : ""}</span>
      <span class="day-body"><b>${esc(title)}</b><span class="small muted">${esc(active ? "en cours…" : done || sub)}</span></span></li>`;
  }).join("");
}

function renderPositions(o) {
  const pos = o.positions || [];
  const box = $("#positions-table");
  if (!pos.length) {
    box.style.margin = "0";
    box.innerHTML = empty("briefcase", "Aucune position", "Le compte est entièrement en liquidités.");
    return;
  }
  box.style.margin = "";
  const eq = o.equipe?.valeur || o.compte?.equity || 1;
  box.innerHTML = `<table><thead><tr><th>Titre</th><th>Quantité</th><th>Prix d'achat</th><th>Prix</th><th>Valeur</th><th>Poids</th><th>Plus ou moins-value</th><th>Stop, prix, objectif</th></tr></thead><tbody>
    ${pos.map((p) => {
      let range = '<span class="muted small">—</span>';
      if (p.stop && p.tp && p.tp > p.stop) {
        const f = (v) => Math.max(0, Math.min(100, ((v - p.stop) / (p.tp - p.stop)) * 100));
        range = `<div class="range"><i class="en" style="left:${f(p.prix_achat)}%"></i><i class="mk" style="left:${f(p.prix)}%"></i></div>
          <div class="range-labels"><span>${esc(money(p.stop, 2))}</span><span>${esc(money(p.tp, 2))}</span></div>`;
      }
      return `<tr><td><div class="sym"><span class="logo-s">${esc(p.symbole.slice(0, 4))}</span>${esc(p.symbole)}${p.en_attente ? ' <span class="pill pill-peach">en attente</span>' : ""}</div></td>
        <td>${esc(p.qty)}</td><td>${esc(money(p.prix_achat, 2))}</td><td>${esc(money(p.prix, 2))}</td><td>${esc(money(p.valeur, 0))}</td>
        <td>${((p.valeur / eq) * 100).toFixed(1).replace(".", ",")} %</td>
        <td><span class="pill ${p.pl >= 0 ? "pill-sage" : "pill-danger"}">${esc(money(p.pl, 0))} · ${esc(pct(p.pl_pct, 1))}</span></td><td>${range}</td></tr>`;
    }).join("")}</tbody></table>`;
}

function planRow(o) {
  const [lab, cls] = STATUT[o.statut] || [o.statut, ""];
  const det = o.action === "acheter"
    ? `${money(o.montant_usd, 0)} · ~${o.qty_estimee} à ${money(o.prix_reference, 2)} · stop -${o.stop_loss_pct} % · objectif +${o.take_profit_pct} %`
    : `${o.pourcentage ?? 100} % de la position`;
  return `<div class="order">${avatar(o.agent || "gerant", true)}${actionPill(o.action)}<span class="mono"><b>${esc(o.symbole)}</b></span><span class="small muted">${esc(det)}</span>${o.source ? `<span class="pill mono">${esc(o.source)}</span>` : ""}<span class="pill ${cls}">${esc(lab)}</span>
    ${o.resultat && o.statut !== "en_attente" ? `<div class="why">${esc(o.resultat)}</div>` : ""}${o.these ? `<details class="why"><summary>Thèse</summary>${md(o.these)}</details>` : ""}</div>`;
}

function renderPlan(o) {
  const plan = o.plan || {};
  const orders = plan.ordres || [];
  $("#plan-sub").textContent = plan.date
    ? `${plan.simulation ? "Simulation · " : ""}préparé le ${dayHm(plan.cree_le)} · ${plan.execute_le ? `exécuté à ${hm(plan.execute_le)}` : plan.simulation ? "non exécuté" : "en attente de l'ouverture"}`
    : "";
  $("#plan-card").innerHTML = orders.length ? `<div class="list">${orders.map(planRow).join("")}</div>`
    : empty("calendar", "Aucun ordre planifié", `Chaque jour de bourse à ${o.limites?.preparation_heure ?? 9} h, l'équipe prépare les ordres de l'ouverture.`);
}

/* ---------- Accueil : répartition du compte par secteur (anneau) ----------
   Les 3 plus gros secteurs en couleur (seules 3 teintes restent distinguables entre elles quand n'importe
   quelles parts se touchent, daltoniens compris), les suivants regroupés en « Autres secteurs », les
   liquidités en gris clair. La légende donne nom, %, montant et titres : rien ne repose sur la couleur seule. */
function renderRepartition(o) {
  const box = $("#repart-card");
  const r = o.repartition;
  if (!r || !r.total) {
    box.innerHTML = empty("wallet", "Pas encore de données", "La répartition apparaîtra avec les données du compte.");
    return;
  }
  const secs = r.secteurs || [];
  const top = secs.slice(0, 3), rest = secs.slice(3);
  const parts = top.map((s, i) => ({ nom: s.secteur, valeur: s.valeur, pct: s.pct, titres: s.symboles, fill: `var(--viz-${i + 1})` }));
  if (rest.length) {
    parts.push({ nom: "Autres secteurs", valeur: rest.reduce((a, s) => a + s.valeur, 0), pct: rest.reduce((a, s) => a + s.pct, 0),
      titres: rest.flatMap((s) => s.symboles), detail: rest.map((s) => s.secteur).join(", "), fill: "var(--viz-autres)" });
  }
  if (r.liquidites > 0) parts.push({ nom: "Liquidités", valeur: r.liquidites, pct: r.liquidites_pct, titres: [], fill: "var(--viz-cash)" });

  const S0 = 168, C = S0 / 2, R1 = 78, R0 = 54, gap = parts.length > 1 ? 2 / ((R0 + R1) / 2) : 0;  // 2 px d'écart entre les parts
  const pt = (rad, a) => `${(C + rad * Math.sin(a)).toFixed(2)},${(C - rad * Math.cos(a)).toFixed(2)}`;
  const arc = (a0, a1) => {
    if (a1 - a0 >= Math.PI * 2 - 1e-6) {  // une seule part : l'anneau entier
      return `M${pt(R1, 0)} A${R1},${R1} 0 1 1 ${pt(R1, Math.PI)} A${R1},${R1} 0 1 1 ${pt(R1, 0)} M${pt(R0, 0)} A${R0},${R0} 0 1 0 ${pt(R0, Math.PI)} A${R0},${R0} 0 1 0 ${pt(R0, 0)} Z`;
    }
    const big = a1 - a0 > Math.PI ? 1 : 0;
    return `M${pt(R1, a0)} A${R1},${R1} 0 ${big} 1 ${pt(R1, a1)} L${pt(R0, a1)} A${R0},${R0} 0 ${big} 0 ${pt(R0, a0)} Z`;
  };
  const sum = parts.reduce((a, p) => a + p.valeur, 0) || 1;
  let a = 0;
  const paths = parts.map((p, i) => {
    const span = (p.valeur / sum) * Math.PI * 2;
    const a0 = a + (span > gap ? gap / 2 : 0), a1 = a + span - (span > gap ? gap / 2 : 0);
    a += span;
    return `<path class="viz-seg" data-i="${i}" d="${arc(a0, a1)}" fill="${p.fill}" fill-rule="evenodd"></path>`;
  }).join("");
  const investi = 100 - (r.liquidites_pct || 0);
  const label = parts.map((p) => `${p.nom} ${nb(p.pct, 1)} %`).join(", ");
  box.innerHTML = `<div class="viz-donut">
      <div class="viz-ring">
        <svg viewBox="0 0 ${S0} ${S0}" role="img" aria-label="Répartition du compte : ${esc(label)}">${paths}</svg>
        <div class="viz-center"><b>${esc(nb(investi, 0))} %</b><span>investi</span></div>
        <div class="viz-tip" hidden></div>
      </div>
      <ul class="viz-legend">${parts.map((p, i) => `<li data-i="${i}"><i style="background:${p.fill}"></i>
        <span class="viz-name">${esc(p.nom)}<small>${esc(p.titres.length ? p.titres.join(", ") : p.nom === "Liquidités" ? "non investies" : "")}</small></span>
        <span class="viz-val"><b>${esc(nb(p.pct, 1))} %</b><small>${esc(money(p.valeur, 0))}</small></span></li>`).join("")}</ul>
    </div>`;
  const tip = $(".viz-tip", box), segs = $$(".viz-seg", box), rows = $$(".viz-legend li", box);
  const focus = (i) => {
    segs.forEach((s) => s.classList.toggle("dim", i !== null && +s.dataset.i !== i));
    rows.forEach((li) => li.classList.toggle("on", +li.dataset.i === i));
    if (i === null) { tip.hidden = true; return; }
    const p = parts[i];
    tip.innerHTML = `<b>${esc(p.nom)}</b><span>${esc(nb(p.pct, 1))} % du compte · ${esc(money(p.valeur, 0))}</span>${p.titres.length ? `<span>${esc(p.titres.join(", "))}</span>` : ""}${p.detail ? `<span>${esc(p.detail)}</span>` : ""}`;
    tip.hidden = false;
  };
  [...segs, ...rows].forEach((el) => {
    el.addEventListener("mouseenter", () => focus(+el.dataset.i));
    el.addEventListener("mouseleave", () => focus(null));
  });
}

/* ====================================================================== Direct (séance en cours) */
function renderLive() {
  const L = S.live;
  if (!L) return;
  const r = L.runner || {}, etat = L.etat || {};
  const running = r.running || (etat.running && Date.now() - new Date(etat.maj) < 10 * 60e3);
  const agents = etat.agents || {};
  $("#live").innerHTML = running ? Object.entries(agents).map(([id, st]) => {
    const label = st.statut === "reflechit" ? `<span class="typing"><i></i><i></i><i></i></span>réfléchit…`
      : st.statut === "outil" ? esc(st.action) : st.statut === "termine" ? `${icon("check")}${esc(st.action || "terminé")}`
      : st.statut === "erreur" ? `<span class="down">erreur</span>` : "attend son tour";
    return `<div class="live-row">${avatar(id, true)}<b>${esc(shortName(id))}</b><span class="live-act">${label}</span><span class="small muted">${st.etapes || 0} outils</span></div>`;
  }).join("") : "";
  $("#live-status").innerHTML = running ? `<span class="pill pill-coral"><i class="dot run"></i>${esc(MODE[etat.mode]?.[0] || "Séance")}${etat.simulation ? " (simulation)" : ""} en cours</span>`
    : r.code === 0 ? `<span class="pill pill-sage">${icon("check")}Terminée</span>`
    : r.code ? `<span class="pill pill-danger">Erreur (code ${esc(r.code)})</span>` : "En veille";
  const con = $("#console");
  if (!STATIC && (r.logs || []).length) {
    con.hidden = false;
    const stick = con.scrollTop + con.clientHeight >= con.scrollHeight - 30;
    con.innerHTML = r.logs.map((l) => `<span class="${/erreur|error|échec|traceback/i.test(l) ? "err" : /exécuté|terminée|planifié/i.test(l) ? "ok" : ""}">${esc(l)}</span>`).join("\n");
    if (stick) con.scrollTop = con.scrollHeight;
  }
  $("#btn-sim").disabled = !STATIC && running;
  $("#btn-real").disabled = running;
  if (S.wasRunning && !running) {
    toast(r.code === 0 || r.code == null ? "Séance terminée" : "La séance s'est arrêtée avec une erreur", r.code ? "alert" : "check");
    refreshAll(true);
  }
  S.wasRunning = running;
  if (S.page === "accueil") renderDay();
  if (S.page === "ia") renderIAList();
}

/* ====================================================================== Séances (partagées par les pages 2, 3 et 4) */
const brainSessions = () => S.sessions.filter((s) => s.mode !== "ouverture");

async function getSession(nom) {
  if (!S.cache[nom]) S.cache[nom] = await api(`/api/session?nom=${encodeURIComponent(nom)}`);
  return S.cache[nom];
}

function fillSessionSelects() {
  const list = brainSessions();
  const opts = list.map((s) => `<option value="${esc(s.nom)}">${esc(sessLabel(s))}</option>`).join("")
    || '<option value="">Aucune séance</option>';
  $$(".js-session").forEach((sel) => { sel.innerHTML = opts; if (S.sel) sel.value = S.sel.nom; });
  const scope = $("#desk-scope");
  scope.innerHTML = `<option value="last">Dernière séance</option><option value="last5">5 dernières séances</option>`
    + list.map((s) => `<option value="${esc(s.nom)}">${esc(sessLabel(s))}</option>`).join("");
  scope.value = S.deskScope;
}

$$(".js-session").forEach((sel) => sel.addEventListener("change", async () => {
  if (!sel.value) return;
  S.sel = await getSession(sel.value);
  $$(".js-session").forEach((x) => (x.value = sel.value));
  renderPage();
}));

/* ====================================================================== Le « cerveau » : réflexions et outils */
function toolLabel(st) {
  const a = st.args || {};
  const L = {
    consulter_portefeuille: ["briefcase", "Consulte le portefeuille"],
    screener: ["filter", `Screener : ${String(a.critere || "").replaceAll("_", " ")}`],
    historique_prix: ["chart", `Historique du cours : ${a.symbole || ""}`],
    donnees_financieres: ["doc", `Données financières : ${a.symbole || ""}`],
    actualites: ["news", `Actualités : ${a.symbole || "marché"}`],
    recherche_web: ["search", `Recherche web : « ${a.question || ""} »`],
    sentiment_reseaux: ["chat", `Sentiment des réseaux : ${a.symbole || ""}`],
    ecrire_notes: ["edit", "Met à jour ses notes"],
    proposer_ordre: ["send", `Propose : ${a.action || ""} ${a.symbole || ""}${a.montant_usd ? ` pour ${money(a.montant_usd, 0)}` : ""}`],
    donner_avis: ["shield", `Avis sur ${a.id || ""} : ${a.verdict || ""}`],
    passer_ordre: ["wallet", `Ordre : ${a.action || ""} ${a.symbole || ""}${a.montant_usd ? ` pour ${money(a.montant_usd, 0)}` : ""}${a.stop_loss_pct ? ` · stop -${a.stop_loss_pct} % · objectif +${a.take_profit_pct} %` : ""}`],
    annuler_ordre: ["x", `Annule l'ordre planifié sur ${a.symbole || ""}`],
    ajuster_stop: ["shield", `Remonte le stop de ${a.symbole || ""} à ${money(a.nouveau_stop, 2)}`],
    lire_skill: ["book", `Lit le skill « ${a.nom || ""} »`],
    lire_page: ["globe", `Ouvre la page ${String(a.url || "").replace(/^https?:\/\//, "").slice(0, 60)}`],
    creer_rappel: ["bell", `Crée un rappel le ${a.date || ""} : ${a.titre || ""}`],
    voir_rappels: ["bell", "Consulte les rappels"],
    terminer_rappel: ["check", `Rappel ${a.id || ""} traité`],
    terminer_session: ["check", "Termine la séance"],
  };
  return L[st.nom] || ["spark", st.nom];
}

function stepKind(st) {
  if (st.type === "pensee") return "think";
  if (st.type === "refus") return "refus";
  if (["passer_ordre", "proposer_ordre", "donner_avis", "ajuster_stop", "annuler_ordre"].includes(st.nom)) return "order";
  return "tool";
}

function brainItem(st, who) {
  let ic, title, body = "", details = "";
  if (st.type === "pensee") { ic = "chat"; title = "Réflexion"; body = st.texte; }
  else if (st.type === "notes") { ic = "book"; title = "Relit ses notes"; body = st.texte; }
  else if (st.type === "refus") { ic = "alert"; title = `Refusé par les garde-fous (${st.symbole || ""})`; body = st.raison; }
  else {
    [ic, title] = toolLabel(st);
    const a = st.args || {};
    body = { passer_ordre: a.these, proposer_ordre: a.these, donner_avis: a.raison, ecrire_notes: a.contenu,
      terminer_session: a.compte_rendu }[st.nom] || "";
    if (st.resultat && !["ecrire_notes", "terminer_session", "lire_skill", "donner_avis"].includes(st.nom)) {
      const full = st.donnees ? JSON.stringify(st.donnees, null, 1) : st.resultat;
      details = `<details><summary>Résultat de l'outil</summary><pre>${esc(full)}</pre></details>`;
    }
  }
  return `<li class="b-step b-${stepKind(st)}"><span class="b-ic">${icon(ic)}</span><div class="b-body"><div class="b-title"><span>${who ? `${avatar(who, true)}<span class="b-who">${esc(shortName(who))}</span>` : ""}${esc(title)}</span><span class="b-time">${esc(hm(st.t))}</span></div>${body ? `<div class="b-text">${md(body)}</div>` : ""}${details}</div></li>`;
}

/* ====================================================================== Page 2 : les IA */
function stats(b) {
  if (!b) return "";
  const out = [];
  if (b.propositions?.length) out.push(`${b.propositions.length} proposition${b.propositions.length > 1 ? "s" : ""}`);
  if (b.avis?.length) out.push(`${b.avis.length} avis`);
  if (b.ordres?.length) out.push(`${b.ordres.length} ordre${b.ordres.length > 1 ? "s" : ""}`);
  return out.map((s) => `<span class="pill pill-coral">${esc(s)}</span>`).join("");
}

function renderIAList() {
  const o = S.ov;
  if (!o) return;
  const etat = S.live?.etat || {}, running = S.live?.runner?.running || etat.running;
  $("#ia-list").innerHTML = o.agents.map((a) => {
    const b = S.sel?.agents?.[a.id];
    const st = etat.agents?.[a.id] || {};
    const thinking = running && ["reflechit", "outil"].includes(st.statut);
    const status = thinking
      ? `<span class="typing"><i></i><i></i><i></i></span><span class="live-txt">${esc(st.statut === "outil" ? st.action : "réfléchit…")}</span>`
      : !a.cle_configuree ? `<span class="pill pill-peach">${icon("key")}clé manquante</span>`
      : b ? `${b.outils || 0} outils · ${Math.max(1, Math.round((b.duree_s || 0) / 60))} min` : "pas dans cette séance";
    return `<button class="ia-item ${S.iaSel === a.id ? "sel" : ""} ${thinking ? "thinking" : ""}" data-id="${esc(a.id)}">
      ${avatar(a.id)}<span class="ia-item-body"><b>${esc(a.nom)}</b><span class="small muted">${esc(ROLE[a.role] || "")} · ${esc(modelName(b?.modele || a.modele))}</span>
      <span class="ia-item-status small">${status}</span><span class="chips">${stats(b)}</span></span></button>`;
  }).join("");
  $$(".ia-item").forEach((el) => (el.onclick = () => { S.iaSel = el.dataset.id; renderIAList(); renderIAPanel(); }));
  $(".ia-item.sel")?.scrollIntoView({ block: "nearest", inline: "nearest" });
}

function proposalRow(p) {
  const det = p.action === "acheter"
    ? `${money(p.montant, 0)} · stop -${p.stop_loss_pct} % · objectif +${p.take_profit_pct} %`
    : `${p.pourcentage ?? 100} % de la position`;
  return `<div class="order">${avatar(p.auteur, true)}${actionPill(p.action)}<span class="mono"><b>${esc(p.symbole)}</b></span><span class="small muted">${esc(det)}</span>
    ${verdictPill(p.avis)}${p.retenue ? `<span class="pill pill-coral">${icon("check")}achetée</span>` : ""}
    <details class="why"><summary>Thèse de ${esc(shortName(p.auteur))}${p.confiance ? ` · confiance ${esc(p.confiance)}` : ""}</summary>${md(p.these)}${p.avis?.raison ? `<br><br><b>Critique :</b> ${md(p.avis.raison)}` : ""}</details></div>`;
}

function orderRow(o) {
  const ok = o.ok !== false;
  return `<div class="order">${actionPill(o.action)}<span class="mono"><b>${esc(o.symbole)}</b></span>${o.source ? `<span class="pill mono">${esc(o.source)}</span>` : ""}<span class="pill ${ok ? "pill-sage" : "pill-danger"}">${esc(o.resultat && o.resultat.startsWith("planifié") ? "planifié" : ok ? "exécuté" : "échec")}</span><div class="why">${esc(o.resultat || "")}</div>${o.these ? `<details class="why"><summary>Thèse</summary>${md(o.these)}</details>` : ""}</div>`;
}

function renderIAPanel() {
  const box = $("#ia-panel");
  const id = S.iaSel, a = agentOf(id), m = META[id] || {};
  const d = S.sel, b = d?.agents?.[id];
  const head = `<div class="ia-panel-head">${avatar(id)}<div><h2>${esc(a.nom)}</h2><div class="chips" style="margin-top:6px"><span class="pill">${esc(ROLE[a.role] || "")}</span>${providerPill(a)}<span class="pill mono">${esc(modelName(b?.modele || a.modele))}</span></div></div></div>
    <p class="muted small" style="margin:12px 0 0">${esc(m.desc)}</p>`;
  if (!d || !b) {
    box.innerHTML = head + empty(id, "Pas de réflexion pour cette séance", !d ? "Lancez une simulation pour voir l'équipe au travail."
      : d.allegee ? `Séance de suivi allégée (${d.allegee}) : seul le gérant a vérifié les positions, pour économiser les quotas des IA.`
      : "Cette IA n'a pas été sollicitée (par exemple, le critique n'intervient que s'il y a des propositions).");
    return;
  }
  let actions = "";
  if (a.role === "gerant") {
    actions = `<div><div class="overline sub-h">Actions achetées ou vendues (${(b.ordres || []).length})</div>${(b.ordres || []).length ? `<div class="list">${b.ordres.map(orderRow).join("")}</div>` : '<p class="muted small">Aucun ordre à cette séance : le gérant a choisi de ne rien faire.</p>'}</div>
      <div><div class="overline sub-h">Propositions examinées (${(d.propositions || []).length})</div>${(d.propositions || []).length ? `<div class="list">${d.propositions.map(proposalRow).join("")}</div>` : '<p class="muted small">Aucune proposition.</p>'}</div>`;
  } else if (a.role === "analyste") {
    const mine = (d.propositions || []).filter((p) => p.auteur === id);
    actions = `<div><div class="overline sub-h">Ses propositions d'achat ou de vente (${mine.length})</div>${mine.length ? `<div class="list">${mine.map(proposalRow).join("")}</div>` : '<p class="muted small">Aucune proposition : rien ne méritait d\'agir selon sa stratégie.</p>'}</div>`;
  } else {
    actions = `<div><div class="overline sub-h">Ses avis (${(b.avis || []).length})</div>${(b.avis || []).length ? `<div class="list">${b.avis.map((v) => `<div class="order"><span class="pill ${VERDICT[v.verdict]?.[1] || ""}">${esc(VERDICT[v.verdict]?.[0] || v.verdict)}</span><span class="mono small">${esc(v.id)}</span><div class="why">${md(v.raison)}</div></div>`).join("")}</div>` : '<p class="muted small">Aucun avis.</p>'}</div>`;
  }
  box.innerHTML = `${head}
    <div class="ia-meta small muted">${esc(sessLabel(d))} · ${b.outils || 0} appels d'outils · ${Math.max(1, Math.round((b.duree_s || 0) / 60))} min · ${(b.tokens || 0).toLocaleString("fr-FR")} tokens</div>
    ${b.erreur ? `<div class="banner err">${icon("alert")}<span>${esc(b.erreur)}</span></div>` : ""}
    <div class="synth"><div class="who">${icon(id)}Résumé de sa réflexion</div><p>${md(b.compte_rendu || "—")}</p></div>
    ${d.allegee && a.role === "gerant" ? `<div class="banner info">${icon("info")}<span>Séance de suivi allégée : ${esc(d.allegee)}. Les analystes et le critique n'ont pas été sollicités.</span></div>` : ""}
    ${actions}
    ${d.resume_marche ? `<details class="why"><summary>Résumé du marché reçu par les IA au début de la séance</summary><div class="notes" style="margin-top:8px">${esc(d.resume_marche.trim())}</div></details>` : ""}
    <div class="row-btns">
      <button class="btn" id="ia-to-journal">${icon("list")}Voir son journal détaillé</button>
      <button class="btn" id="ia-to-notes">${icon("note")}Ouvrir ses notes</button>
    </div>`;
  $("#ia-to-journal").onclick = () => { S.jAgent = id; go("journal"); };
  $("#ia-to-notes").onclick = () => { go("bureau"); setTimeout(() => openApp("notes", { agent: id }), 60); };
}

/* ====================================================================== Page 3 : le journal */
const TYPES = [["tout", "Tout"], ["think", "Réflexions"], ["tool", "Outils"], ["order", "Ordres et avis"], ["refus", "Refus"]];

function renderJournal() {
  const d = S.sel;
  const ids = d ? Object.keys(d.agents || {}) : [];
  if (S.jAgent !== "tous" && !ids.includes(S.jAgent)) S.jAgent = "tous";
  $("#j-agents").innerHTML = `<span class="overline">IA</span>` + [["tous", "Toutes"], ...ids.map((i) => [i, shortName(i)])].map(([k, l]) =>
    `<button class="chip-btn ${S.jAgent === k ? "on" : ""}" data-a="${esc(k)}">${k !== "tous" ? avatar(k, true) : ""}${esc(l)}</button>`).join("");
  $("#j-types").innerHTML = `<span class="overline">Type</span>` + TYPES.map(([k, l]) =>
    `<button class="chip-btn ${S.jType === k ? "on" : ""}" data-t="${k}">${esc(l)}</button>`).join("");
  $$("#j-agents .chip-btn").forEach((b) => (b.onclick = () => { S.jAgent = b.dataset.a; renderJournal(); }));
  $$("#j-types .chip-btn").forEach((b) => (b.onclick = () => { S.jType = b.dataset.t; renderJournal(); }));
  if (!d) {
    $("#j-usage").innerHTML = "";
    $("#j-timeline").innerHTML = empty("list", "Aucune séance", "Lancez une simulation pour remplir le journal.");
    return;
  }
  const agents = S.jAgent === "tous" ? ids : [S.jAgent];
  // Outils utilisés par chaque IA
  $("#j-usage").innerHTML = agents.map((aid) => {
    const count = {};
    (d.agents[aid].etapes || []).filter((s) => s.type === "outil").forEach((s) => (count[s.nom] = (count[s.nom] || 0) + 1));
    const chips = Object.entries(count).sort((x, y) => y[1] - x[1]).map(([n, c]) =>
      `<span class="pill">${icon(toolLabel({ nom: n })[0])}${esc(n.replaceAll("_", " "))} × ${c}</span>`).join("");
    return `<div class="usage-row">${avatar(aid, true)}<b>${esc(shortName(aid))}</b><span class="chips" style="margin:0">${chips || '<span class="muted small">aucun outil</span>'}</span></div>`;
  }).join("");
  const steps = agents.flatMap((aid) => (d.agents[aid].etapes || []).map((s) => ({ ...s, _a: aid })))
    .filter((s) => S.jType === "tout" || stepKind(s) === S.jType)
    .sort((x, y) => String(x.t).localeCompare(String(y.t)));
  $("#j-timeline").innerHTML = steps.length
    ? `<ol class="brain">${steps.map((s) => brainItem(s, S.jAgent === "tous" ? s._a : null)).join("")}</ol>`
    : empty("list", "Rien à afficher", "Aucune étape de ce type pour cette sélection.");
}

/* ====================================================================== Page 4 : le bureau façon Windows */
const APPS = [
  { id: "notes", nom: "Notes", ic: "note", color: "var(--peach)", sub: "Les notes de chaque IA" },
  { id: "recherches", nom: "Recherches web", ic: "search", color: "var(--sky)", sub: "Ses recherches Google" },
  { id: "actualites", nom: "Actualités", ic: "news", color: "var(--coral)", sub: "Les articles qu'elle a lus" },
  { id: "bourse", nom: "Bourse", ic: "chart", color: "var(--sage)", sub: "Les cours et chiffres consultés" },
  { id: "screener", nom: "Screener", ic: "filter", color: "var(--plum)", sub: "Ses filtres d'actions" },
  { id: "reddit", nom: "Reddit", ic: "chat", color: "var(--coral-deep)", sub: "L'humeur des réseaux vue" },
  { id: "ordres", nom: "Ordres", ic: "wallet", color: "var(--sage)", sub: "Tous les achats et ventes" },
  { id: "rappels", nom: "Rappels", ic: "bell", color: "var(--peach)", sub: "Les événements à ne pas oublier" },
];
const appOf = (id) => APPS.find((a) => a.id === id);

async function loadDeskData() {
  const list = brainSessions();
  let names = [];
  if (S.deskScope === "last") names = list.slice(0, 1).map((s) => s.nom);
  else if (S.deskScope === "last5") names = list.slice(0, 5).map((s) => s.nom);
  else names = [S.deskScope];
  const sessions = await Promise.all(names.map(getSession));
  S.deskData = sessions.flatMap((d) => Object.entries(d.agents || {}).flatMap(([aid, r]) =>
    (r.etapes || []).filter((s) => s.type === "outil").map((s) => ({
      sess: d.quand, ts: s.t, agent: aid, nom: s.nom, args: s.args || {}, d: s.donnees ?? tryJSON(s.resultat), raw: s.resultat,
    }))));
  S.deskSessions = sessions;
}

function renderDesktop() {
  fillSessionSelects();
  $("#desk-icons").innerHTML = APPS.map((a) => `<button class="desk-icon" data-app="${a.id}" title="${esc(a.sub)}">
    <span class="desk-tile" style="--c:${a.color}">${icon(a.ic)}</span><span class="desk-label">${esc(a.nom)}</span></button>`).join("");
  $$(".desk-icon").forEach((b) => (b.onclick = () => openApp(b.dataset.app)));
  renderTaskbar();
  tickClock();
  loadDeskData().then(() => Object.keys(S.wins).forEach(renderWin));
}

$("#desk-scope").addEventListener("change", async (e) => {
  S.deskScope = e.target.value;
  await loadDeskData();
  Object.keys(S.wins).forEach(renderWin);
});

function tickClock() {
  const el = $("#tb-clock");
  if (el) el.innerHTML = `<b>${esc(hm(new Date()))}</b><span>${esc(fmtDate(new Date(), { day: "2-digit", month: "2-digit", year: "numeric" }))}</span>`;
}
setInterval(tickClock, 30000);

function renderTaskbar() {
  $("#tb-apps").innerHTML = APPS.map((a) => {
    const w = S.wins[a.id];
    return `<button class="tb-app ${w ? "open" : ""} ${w && !w.min && w.el.classList.contains("focus") ? "active" : ""}" data-app="${a.id}" title="${esc(a.nom)}" aria-label="${esc(a.nom)}"><span style="color:${a.color}">${icon(a.ic)}</span></button>`;
  }).join("");
  $$(".tb-app").forEach((b) => (b.onclick = () => {
    const w = S.wins[b.dataset.app];
    if (!w) return openApp(b.dataset.app);
    if (w.min || !w.el.classList.contains("focus")) { w.min = false; w.el.classList.remove("min"); focusWin(b.dataset.app); }
    else { w.min = true; w.el.classList.add("min"); w.el.classList.remove("focus"); renderTaskbar(); }
  }));
  $("#desk-hint").hidden = Object.keys(S.wins).length > 0;
}

function focusWin(id) {
  Object.values(S.wins).forEach((w) => w.el.classList.remove("focus"));
  const w = S.wins[id];
  w.el.style.zIndex = ++S.z;
  w.el.classList.add("focus");
  renderTaskbar();
}

function openApp(id, opts = {}) {
  const app = appOf(id);
  if (!app) return;
  if (S.wins[id]) {
    const w = S.wins[id];
    Object.assign(w.state, opts);
    w.min = false;
    w.el.classList.remove("min");
    focusWin(id);
    renderWin(id);
    return;
  }
  const desk = $("#desktop");
  const n = Object.keys(S.wins).length;
  const el = document.createElement("div");
  el.className = "win";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-label", app.nom);
  const dw = desk.clientWidth || 900, dh = desk.clientHeight || 600;
  const W = Math.max(340, Math.min(720, dw - 40)), H = Math.max(260, Math.min(480, dh - 90));
  el.style.width = `${W}px`;
  el.style.height = `${H}px`;
  el.style.left = `${Math.min(130 + n * 28, Math.max(0, dw - W - 10))}px`;
  el.style.top = `${Math.min(24 + n * 28, Math.max(0, dh - H - 60))}px`;
  el.innerHTML = `<div class="win-title"><span class="win-ic" style="color:${app.color}">${icon(app.ic)}</span><span class="win-name">${esc(app.nom)}</span>
    <span class="win-ctrls"><button class="win-btn" data-act="min" aria-label="Réduire">${icon("minus")}</button><button class="win-btn" data-act="max" aria-label="Agrandir">${icon("square")}</button><button class="win-btn close" data-act="close" aria-label="Fermer">${icon("x")}</button></span></div>
    <div class="win-tools"></div><div class="win-body"></div>`;
  $("#desk-windows").appendChild(el);
  S.wins[id] = { el, state: { agent: "tous", q: "", ...opts }, min: false };
  el.addEventListener("pointerdown", () => focusWin(id));
  $$(".win-btn", el).forEach((b) => (b.onclick = (e) => {
    e.stopPropagation();
    const act = b.dataset.act;
    if (act === "close") { el.remove(); delete S.wins[id]; renderTaskbar(); }
    if (act === "min") { S.wins[id].min = true; el.classList.add("min"); el.classList.remove("focus"); renderTaskbar(); }
    if (act === "max") el.classList.toggle("max");
  }));
  dragWin(el, $(".win-title", el));
  $(".win-title", el).addEventListener("dblclick", () => el.classList.toggle("max"));
  renderWinTools(id);
  focusWin(id);
  renderWin(id);
}

function dragWin(el, handle) {
  handle.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".win-btn") || el.classList.contains("max") || window.innerWidth < 900) return;
    const desk = $("#desktop").getBoundingClientRect();
    const sx = e.clientX, sy = e.clientY, ox = el.offsetLeft, oy = el.offsetTop;
    handle.setPointerCapture(e.pointerId);
    const move = (ev) => {
      el.style.left = `${Math.max(-el.offsetWidth + 120, Math.min(desk.width - 120, ox + ev.clientX - sx))}px`;
      el.style.top = `${Math.max(0, Math.min(desk.height - 90, oy + ev.clientY - sy))}px`;
    };
    const up = () => { handle.removeEventListener("pointermove", move); handle.removeEventListener("pointerup", up); };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
  });
}

function renderWinTools(id) {
  const w = S.wins[id];
  const ids = S.ov?.agents.map((a) => a.id) || [];
  const tools = $(".win-tools", w.el);
  tools.innerHTML = `<label class="win-search">${icon("search")}<input type="search" placeholder="Rechercher (symbole, mot…)" value="${esc(w.state.q)}" aria-label="Rechercher"></label>
    <select class="select" aria-label="IA"><option value="tous">Toutes les IA</option>${ids.map((a) => `<option value="${a}">${esc(agentOf(a).nom)}</option>`).join("")}</select>`;
  const sel = $("select", tools);
  sel.value = w.state.agent;
  sel.onchange = () => { w.state.agent = sel.value; renderWin(id); };
  $("input", tools).oninput = (e) => { w.state.q = e.target.value; renderWin(id); };
}

function renderWin(id) {
  const w = S.wins[id];
  if (!w) return;
  const sel = $(".win-tools select", w.el);
  if (sel) sel.value = w.state.agent;
  const items = S.deskData.filter((x) => w.state.agent === "tous" || x.agent === w.state.agent);
  const q = w.state.q.trim().toLowerCase();
  const body = $(".win-body", w.el);
  body.innerHTML = (APP_RENDER[id] || (() => ""))(items, q, w);
  $$("[data-pick]", body).forEach((b) => (b.onclick = () => { w.state.pick = b.dataset.pick; renderWin(id); }));
}

const match = (q, ...txt) => !q || txt.some((t) => String(t ?? "").toLowerCase().includes(q));
const readers = (set) => [...set].map((a) => avatar(a, true)).join("");

function sparkline(vals) {
  const v = (vals || []).filter((x) => num(x) !== null);
  if (v.length < 2) return "";
  const W = 260, H = 56, lo = Math.min(...v), hi = Math.max(...v) || 1;
  const pts = v.map((y, i) => [(i / (v.length - 1)) * W, H - 4 - ((y - lo) / ((hi - lo) || 1)) * (H - 8)]);
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><path class="c-line" d="${smoothPath(pts)}"/></svg>`;
}

// Résultats d'une recherche web sans réponse rédigée : articles de Tavily, de Google Actualités et de Wikipédia.
function searchList(d) {
  if (!d) return "";
  const line = (t, meta, extra) => `<div class="search-row"><b>${esc(t)}</b>${meta ? `<span class="small muted">${esc(meta)}</span>` : ""}${extra ? `<div class="small muted">${esc(extra)}</div>` : ""}</div>`;
  const rows = [
    ...(d.resultats || []).map((r) => line(r.titre, r.url, r.extrait)),
    ...(d.actualites_google || []).map((n) => line(n.titre, [n.source, n.date && dayHm(n.date.replace(" ", "T") + "Z")].filter(Boolean).join(" · "))),
    ...(d.wikipedia || []).map((w) => line(`Wikipédia : ${w.titre}`, "", w.extrait)),
  ];
  return rows.length ? `<div class="search-list">${rows.slice(0, 10).join("")}</div>` : "";
}

const APP_RENDER = {
  notes(items, q, w) {
    const ids = S.ov?.agents.map((a) => a.id) || [];
    const pick = w.state.agent !== "tous" ? w.state.agent : w.state.pick || "gerant";
    const fromSession = [...items].reverse().find((x) => x.agent === pick && x.nom === "ecrire_notes");
    const saved = S.notes[pick];
    const text = saved || fromSession?.args?.contenu || "";
    const src = saved ? "Notes enregistrées (sa mémoire pour la prochaine séance)"
      : fromSession ? `Notes écrites pendant la séance du ${fromSession.sess} (simulation : non enregistrées)` : "";
    return `<div class="app-split"><div class="app-side">${ids.map((a) => `<button class="side-item ${a === pick ? "sel" : ""}" data-pick="${a}">${avatar(a, true)}${esc(shortName(a))}</button>`).join("")}</div>
      <div class="app-main">${text ? `<div class="small muted" style="margin-bottom:8px">${esc(src)}</div><div class="notes">${q ? esc(text).replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), (m) => `<mark>${m}</mark>`) : esc(text)}</div>`
        : empty("note", "Pas encore de notes", "Cette IA n'a pas encore écrit de notes.")}</div></div>`;
  },

  recherches(items, q) {
    const rows = items.filter((x) => (x.nom === "recherche_web" && match(q, x.args.question, x.d?.reponse,
      ...(x.d?.actualites_google || []).map((n) => n.titre), ...(x.d?.resultats || []).map((n) => n.titre)))
      || (x.nom === "lire_page" && match(q, x.args.url, x.d?.titre, x.d?.texte)));
    if (!rows.length) return empty("search", "Aucune recherche", "Les IA n'ont fait ni recherche web ni lecture de page dans cette sélection.");
    return rows.reverse().map((x) => x.nom === "lire_page"
      ? `<div class="app-card"><div class="app-card-h">${avatar(x.agent, true)}<span class="pill pill-sky">${icon("globe")}page lue</span><b>${esc(x.d?.titre || x.args.url)}</b><span class="b-time">${esc(dayHm(x.ts))}</span></div>
        <div class="small muted mono" style="overflow-wrap:anywhere">${esc(x.d?.url || x.args.url)}</div>
        <div class="b-text">${x.d?.texte ? esc(x.d.texte.slice(0, 700)) + (x.d.texte.length > 700 ? "…" : "") : esc(x.d?.erreur || "")}</div></div>`
      : `<div class="app-card"><div class="app-card-h">${avatar(x.agent, true)}<b>« ${esc(x.args.question)} »</b>${x.d?.moteur ? `<span class="pill">${esc(x.d.moteur)}</span>` : ""}<span class="b-time">${esc(dayHm(x.ts))}</span></div>
        ${x.d?.reponse || x.d?.erreur || (!x.d && x.raw) ? `<div class="b-text">${md(x.d?.reponse || x.d?.erreur || x.raw || "")}</div>` : ""}
        ${searchList(x.d)}
        ${(x.d?.sources || []).length ? `<div class="chips">${x.d.sources.map((s) => `<span class="pill">${esc(s)}</span>`).join("")}</div>` : ""}</div>`).join("");
  },

  ordres(items, q) {
    const rows = (S.ov?.ordres || []).filter((e) => match(q, e.symbole, e.action, e.source)).slice().reverse();
    if (!rows.length) return empty("wallet", "Aucun ordre pour l'instant", "Les achats et ventes réels (pas les simulations) apparaîtront ici, avec les stops et objectifs déclenchés.");
    const sells = rows.filter((e) => e.plus_value != null);
    const pl = sells.reduce((s, e) => s + e.plus_value, 0), wins = sells.filter((e) => e.plus_value > 0).length;
    const lab = { acheter: "achat", vendre: "vente", alleger: "allègement", ajuster_stop: "stop remonté" };
    return `<div class="kv"><div><span>Ordres</span><b>${rows.length}</b></div><div><span>Ventes clôturées</span><b>${sells.length}</b></div>
      <div><span>Plus-value réalisée</span><b class="${tone(pl)}">${esc(money(pl, 0))}</b></div><div><span>Ventes gagnantes</span><b>${sells.length ? `${Math.round((wins / sells.length) * 100)} %` : "—"}</b></div></div>
      <div class="table-wrap" style="margin:8px 0 0"><table><thead><tr><th>Date</th><th>Ordre</th><th>Titre</th><th>Quantité</th><th>Prix</th><th>Plus-value</th><th>Origine</th><th>Statut</th></tr></thead><tbody>
      ${rows.map((e) => `<tr><td class="small">${esc(dayHm(e.ts))}</td><td>${actionPill(lab[e.action] || e.action)}</td><td class="mono"><b>${esc(e.symbole)}</b></td>
        <td>${esc(e.qty ?? "—")}</td><td>${e.prix ? esc(money(e.prix, 2)) : "—"}</td>
        <td>${e.plus_value != null ? `<span class="${tone(e.plus_value)}">${esc(money(e.plus_value, 2))}</span>` : "—"}</td>
        <td class="small">${esc(e.source || (e.agent === "alpaca" ? "Alpaca" : "gérant"))}</td>
        <td><span class="pill ${e.statut === "exécuté" ? "pill-sage" : e.statut === "erreur" ? "pill-danger" : "pill-peach"}">${esc(e.statut)}</span></td></tr>`).join("")}</tbody></table></div>`;
  },

  rappels(items, q) {
    const all = allRappels(S.ov || {}).filter((r) => match(q, r.titre, r.symbole, r.details));
    if (!all.length) return empty("bell", "Aucun rappel", "Les rappels créés par les IA et ceux des dates de résultats apparaîtront ici.");
    const actifs = all.filter((r) => r.statut === "actif").sort((a, b) => a.date.localeCompare(b.date));
    const passes = all.filter((r) => r.statut !== "actif").sort((a, b) => b.date.localeCompare(a.date));
    return `${actifs.length ? `<div class="overline sub-h">À venir (${actifs.length})</div><div class="list">${actifs.map(rappelRow).join("")}</div>` : ""}
      ${passes.length ? `<div class="overline sub-h" style="margin-top:12px">Traités ou expirés (${passes.length})</div><div class="list">${passes.slice(0, 30).map(rappelRow).join("")}</div>` : ""}`;
  },

  actualites(items, q) {
    const map = new Map();
    items.filter((x) => x.nom === "actualites" && Array.isArray(x.d)).forEach((x) => x.d.forEach((n) => {
      const k = n.titre;
      if (!map.has(k)) map.set(k, { ...n, lecteurs: new Set() });
      map.get(k).lecteurs.add(x.agent);
    }));
    const rows = [...map.values()].filter((n) => match(q, n.titre, n.resume, (n.symboles || []).join(" ")))
      .sort((a, b) => String(b.date).localeCompare(String(a.date)));
    if (!rows.length) return empty("news", "Aucun article", "Les IA n'ont pas lu d'actualités dans cette sélection.");
    return `<div class="small muted" style="margin-bottom:8px">${rows.length} article${rows.length > 1 ? "s" : ""} lu${rows.length > 1 ? "s" : ""}</div>` + rows.map((n) => `<div class="app-card">
      <div class="app-card-h"><span class="mono small muted">${esc(n.date)}</span>${n.source ? `<span class="pill">${esc(n.source)}</span>` : ""}<span class="readers">lu par ${readers(n.lecteurs)}</span></div>
      <b>${esc(n.titre)}</b>${n.resume ? `<div class="b-text">${esc(n.resume)}</div>` : ""}
      ${(n.symboles || []).length ? `<div class="chips">${n.symboles.map((s) => `<span class="pill tk">${esc(s)}</span>`).join("")}</div>` : ""}</div>`).join("");
  },

  bourse(items, q, w) {
    const by = new Map();
    items.filter((x) => ["historique_prix", "donnees_financieres"].includes(x.nom) && x.d && !x.d.erreur).forEach((x) => {
      const s = String(x.args.symbole || "").toUpperCase();
      if (!by.has(s)) by.set(s, { s, lecteurs: new Set() });
      const e = by.get(s);
      e.lecteurs.add(x.agent);
      if (x.nom === "historique_prix") e.h = x.d; else e.f = x.d;
    });
    const list = [...by.values()].filter((e) => match(q, e.s, e.f?.nom, e.f?.secteur)).sort((a, b) => a.s.localeCompare(b.s));
    if (!list.length) return empty("chart", "Aucune donnée boursière", "Les IA n'ont pas consulté de cours dans cette sélection (ou la recherche ne trouve rien).");
    const pick = list.find((e) => e.s === w.state.pick) || list[0];
    const h = pick.h || {}, f = pick.f || {};
    const kv = (rows) => `<div class="kv">${rows.filter(([, v]) => v !== undefined && v !== null && v !== "" && v !== "—").map(([k, v]) => `<div><span>${esc(k)}</span><b>${v}</b></div>`).join("")}</div>`;
    const p = (v) => `<span class="${tone(v)}">${esc(pct(v, 1))}</span>`;
    return `<div class="app-split"><div class="app-side">${list.map((e) => `<button class="side-item ${e === pick ? "sel" : ""}" data-pick="${esc(e.s)}"><span class="mono"><b>${esc(e.s)}</b></span><span class="readers">${readers(e.lecteurs)}</span></button>`).join("")}</div>
      <div class="app-main">
        <div class="app-card-h"><h3 class="mono">${esc(pick.s)}</h3><span class="muted">${esc(f.nom || "")}</span><span class="readers">consulté par ${readers(pick.lecteurs)}</span></div>
        ${f.secteur ? `<div class="chips" style="margin-top:6px"><span class="pill">${esc(f.secteur)}</span>${f.industrie ? `<span class="pill">${esc(f.industrie)}</span>` : ""}${f.jours_avant_resultats != null ? `<span class="pill pill-peach">résultats dans ${esc(f.jours_avant_resultats)} j (${esc(f.prochains_resultats)})</span>` : ""}</div>` : ""}
        ${h.prix ? `<div class="price-line"><b>${esc(money(h.dernier_prix || h.prix, 2))}</b>${sparkline(h.cours_hebdo_1an)}</div>` : ""}
        ${h.prix ? `<div class="overline sub-h">Graphique</div>${kv([["5 jours", p(h.perf_5j_pct)], ["1 mois", p(h.perf_1m_pct)], ["3 mois", p(h.perf_3m_pct)], ["1 an", p(h.perf_1an_pct)], ["RSI 14", esc(nb(h.rsi14, 0))], ["ATR 14", esc(money(h.atr14, 2))], ["Moyenne 20 j", esc(money(h.sma20, 2))], ["Moyenne 50 j", esc(money(h.sma50, 2))], ["Moyenne 200 j", esc(money(h.sma200, 2))], ["Plus haut 52 s", esc(money(h.plus_haut_52s, 2))], ["Plus bas 52 s", esc(money(h.plus_bas_52s, 2))], ["Volume / moyenne", esc(nb(h.volume_vs_moy20))], ["Marché (SPY) 1 mois", h.marche_SPY ? p(h.marche_SPY.perf_1m_pct) : null]])}` : ""}
        ${pick.f ? `<div class="overline sub-h">Données financières</div>${kv([["Capitalisation", esc(f.capitalisation)], ["PER", esc(nb(f.per))], ["PER attendu", esc(nb(f.per_attendu))], ["Marge nette", f.marge_nette_pct != null ? esc(`${nb(f.marge_nette_pct)} %`) : null], ["Marge opérationnelle", f.marge_op_pct != null ? esc(`${nb(f.marge_op_pct)} %`) : null], ["Croissance du CA", f.croissance_ca_pct != null ? p(f.croissance_ca_pct) : null], ["Croissance des bénéfices", f.croissance_benef_pct != null ? p(f.croissance_benef_pct) : null], ["ROE", f.roe_pct != null ? esc(`${nb(f.roe_pct)} %`) : null], ["Dette / fonds propres", esc(nb(f.dette_sur_fp, 0))], ["Flux de trésorerie libre", esc(f.flux_tresorerie_libre)], ["Dividende", f.rendement_dividende_pct != null ? esc(`${nb(f.rendement_dividende_pct, 2)} %`) : null], ["Objectif des analystes", esc(money(f.objectif_analystes, 2))], ["Avis des analystes", esc(f.avis_analystes)]])}` : ""}
      </div></div>`;
  },

  screener(items, q, w) {
    const runs = items.filter((x) => x.nom === "screener" && Array.isArray(x.d));
    if (!runs.length) return empty("filter", "Aucun screener", "Les IA n'ont pas utilisé le screener dans cette sélection.");
    const key = (x, i) => `${x.ts}-${x.agent}-${i}`;
    const pick = runs.find((x, i) => key(x, i) === w.state.pick) || runs[0];
    const rows = pick.d.filter((r) => match(q, r.s, r.nom));
    const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))].filter((c) => c !== "s");
    const label = { prix: "Prix", var_pct: "Variation", perf_5j_pct: "5 jours", perf_1m_pct: "1 mois", perf_1j_pct: "1 jour", rsi14: "RSI", ecart_plus_haut_pct: "Sous le plus haut", volume_vs_moy20: "Volume / moy.", volume: "Volume", nom: "Nom", mentions_24h: "Mentions 24 h", mentions_veille: "Veille" };
    const cell = (c, v) => /pct$/.test(c) ? `<span class="${tone(v)}">${esc(pct(v, 1))}</span>` : c === "prix" ? esc(money(v, 2)) : esc(typeof v === "number" ? nb(v) : v);
    return `<div class="app-split"><div class="app-side">${runs.map((x, i) => `<button class="side-item ${x === pick ? "sel" : ""}" data-pick="${esc(key(x, i))}">${avatar(x.agent, true)}<span><b>${esc(String(x.args.critere || "").replaceAll("_", " "))}</b><span class="small muted">${esc(hm(x.ts))}</span></span></button>`).join("")}</div>
      <div class="app-main"><div class="app-card-h"><b>${esc(String(pick.args.critere || "").replaceAll("_", " "))}</b><span class="readers">par ${avatar(pick.agent, true)}</span><span class="b-time">${esc(dayHm(pick.ts))}</span></div>
      <div class="table-wrap" style="margin:8px 0 0"><table><thead><tr><th>Titre</th>${cols.map((c) => `<th>${esc(label[c] || c)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr><td class="mono"><b>${esc(r.s)}</b></td>${cols.map((c) => `<td>${cell(c, r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div></div>`;
  },

  reddit(items, q) {
    const trend = [...items].reverse().find((x) => x.nom === "screener" && x.args.critere === "tendances_reddit" && Array.isArray(x.d));
    const checked = new Map();
    items.filter((x) => x.nom === "sentiment_reseaux" && x.d).forEach((x) => {
      const s = x.d.symbole || String(x.args.symbole || "").toUpperCase();
      if (!checked.has(s)) checked.set(s, { ...x.d, lecteurs: new Set() });
      checked.get(s).lecteurs.add(x.agent);
    });
    const list = [...checked.values()].filter((c) => match(q, c.symbole));
    let html = "";
    if (trend) {
      const rows = trend.d.filter((r) => match(q, r.s, r.nom));
      html += `<div class="overline sub-h">Les plus discutées sur Reddit (vu par ${avatar(trend.agent, true)} à ${esc(hm(trend.ts))})</div>
        <div class="table-wrap" style="margin:0 0 16px"><table><thead><tr><th>Titre</th><th>Nom</th><th>Mentions 24 h</th><th>La veille</th><th>Évolution</th></tr></thead><tbody>
        ${rows.map((r) => { const dv = (r.mentions_24h || 0) - (r.mentions_veille || 0); return `<tr><td class="mono"><b>${esc(r.s)}</b></td><td>${esc(String(r.nom || "").replace(/&amp;/g, "&"))}</td><td>${esc(r.mentions_24h)}</td><td>${esc(r.mentions_veille)}</td><td class="${tone(dv)}">${dv > 0 ? "+" : ""}${esc(dv)}</td></tr>`; }).join("")}</tbody></table></div>`;
    }
    if (list.length) {
      html += `<div class="overline sub-h">Actions vérifiées par les IA</div>` + list.map((c) => {
        const r = typeof c.reddit === "object" ? c.reddit : null;
        const now = r?.mentions_24h, before = r?.mentions_veille;
        const max = Math.max(1, now || 0, before || 0);
        return `<div class="app-card"><div class="app-card-h"><b class="mono">${esc(c.symbole)}</b>${r?.rang ? `<span class="pill pill-coral">rang ${esc(r.rang)}</span>` : ""}<span class="readers">vu par ${readers(c.lecteurs)}</span></div>
          ${r && typeof now === "number" ? `<div class="bars"><span>Mentions 24 h</span><div class="bar"><i style="width:${(now / max) * 100}%"></i></div><b>${esc(now)}</b><span>La veille</span><div class="bar"><i class="old" style="width:${((before || 0) / max) * 100}%"></i></div><b>${esc(before ?? "—")}</b></div>`
            : `<div class="small muted">${esc(typeof c.reddit === "string" ? c.reddit : r?.mentions_24h || "pas de données Reddit")}</div>`}
          <div class="small muted">${r?.upvotes != null ? `${esc(r.upvotes)} votes positifs · ` : ""}${c.articles_3_derniers_jours != null ? `${esc(c.articles_3_derniers_jours)} articles sur 3 jours` : ""}</div></div>`;
      }).join("");
    }
    return html || empty("chat", "Rien sur Reddit", "Les IA n'ont pas regardé Reddit dans cette sélection.");
  },
};

/* ====================================================================== Chargement */
async function refreshAll(force = false) {
  try {
    const [ov, sessions, notes] = await Promise.all([api("/api/overview"), api("/api/sessions"), api("/api/notes")]);
    S.ov = ov; S.notes = notes; S.sessions = sessions;
    if (force) S.cache = {};
    const latest = brainSessions()[0];
    const changed = force || latest?.nom !== S.lastLatest;
    S.lastLatest = latest?.nom;
    if (latest && (changed || !S.sel)) S.sel = await getSession(latest.nom);
    renderHeader(ov);
    fillSessionSelects();
    // Les pages de lecture ne sont redessinées que s'il y a une nouvelle séance (pour ne pas refermer ce qu'on lit).
    if (S.page === "accueil" || changed) renderPage();
    if (S.page === "bureau" && force) { await loadDeskData(); Object.keys(S.wins).forEach(renderWin); }
  } catch (e) {
    console.error(e);
    toast("Impossible de charger les données du tableau de bord", "alert");
  }
}

async function pollLive() {
  try {
    S.live = await api("/api/state");
    renderLive();
  } catch { /* serveur arrêté */ }
  if (!STATIC) setTimeout(pollLive, S.wasRunning ? 1500 : 3000);
}

async function run(mode) {
  const r = await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode }) });
  if (!r.ok) return toast(r.erreur || "Lancement impossible", "alert");
  toast(mode === "reel" ? "Séance réelle lancée" : "Simulation lancée : l'équipe se met au travail", "spark");
  S.wasRunning = true;
  $("#console").hidden = false;
  $("#console").textContent = "Démarrage…";
  go("accueil");
}

/* ====================================================================== Forcer le lancement (site en ligne)
   Le site public ne contient aucune clé : le jeton GitHub (limité à ce dépôt, permission Actions)
   est saisi une fois et reste dans ce navigateur. Il sert uniquement à lancer le workflow. */
const TOKEN_KEY = "bot_ia_github_token";
const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; } };
const setToken = (t) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* stockage indisponible */ } };

function gh(path, opt = {}) {
  const tok = getToken();
  return fetch(`https://api.github.com/repos/${S.ov.depot}${path}`, {
    ...opt,
    headers: { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}), ...(opt.headers || {}) },
  });
}

function openForce() {
  const has = !!getToken();
  $("#force-token-field").hidden = has;
  $("#force-token-saved").hidden = !has;
  $("#force-error").hidden = true;
  $("#force-token").value = "";
  $("#force-modal").classList.add("open");
  $("#force-mode").focus();
}
const closeForce = () => $("#force-modal").classList.remove("open");
$("#force-no").onclick = closeForce;
$("#force-forget").onclick = (e) => { e.preventDefault(); setToken(""); openForce(); };

$("#force-yes").onclick = async () => {
  const err = (m) => { const b = $("#force-error"); b.innerHTML = `${icon("alert")}<span>${esc(m)}</span>`; b.hidden = false; };
  const typed = $("#force-token").value.trim();
  if (typed) setToken(typed);
  if (!getToken()) return err("Colle d'abord ton jeton GitHub.");
  const mode = $("#force-mode").value, sim = $("#force-sim").checked;
  $("#force-yes").disabled = true;
  try {
    const since = Date.now();
    const r = await gh("/actions/workflows/trading.yml/dispatches", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main", inputs: { mode, dry_run: String(sim) } }),
    });
    if (r.status === 401) { setToken(""); return err("Jeton refusé par GitHub (invalide ou expiré). Colle un nouveau jeton."); }
    if (r.status === 403 || r.status === 404) { setToken(""); return err("Ce jeton n'a pas le droit de lancer le workflow : donne-lui l'accès à ce dépôt avec la permission « Actions : lecture et écriture »."); }
    if (r.status !== 204) return err(`GitHub a répondu ${r.status}. Réessaie dans un instant.`);
    closeForce();
    toast(`Lancement demandé à GitHub : ${mode === "auto" ? "séance automatique" : mode}${sim ? " (simulation)" : ""}`, "spark");
    watchRun(since);
  } catch (e) {
    err("Impossible de joindre GitHub (connexion ?).");
  } finally {
    $("#force-yes").disabled = false;
  }
};

async function watchRun(since) {
  S.ghRun = { status: "queued" };
  renderGhRun();
  for (let i = 0; i < 400; i++) {  // environ 1 heure au maximum
    await new Promise((res) => setTimeout(res, 9000));
    try {
      const r = await gh("/actions/workflows/trading.yml/runs?event=workflow_dispatch&per_page=5");
      const runs = (await r.json()).workflow_runs || [];
      const run = runs.find((x) => new Date(x.created_at).getTime() >= since - 90e3);
      if (!run) continue;
      S.ghRun = { status: run.status, conclusion: run.conclusion, url: run.html_url };
      renderGhRun();
      if (run.status === "completed") {
        toast(run.conclusion === "success" ? "Séance terminée sur GitHub : le site se met à jour dans une minute" : `Séance terminée sur GitHub (${run.conclusion})`, run.conclusion === "success" ? "check" : "alert");
        setTimeout(() => refreshAll(true), 75000);
        return;
      }
    } catch { /* réseau : on réessaie */ }
  }
}

function renderGhRun() {
  const g = S.ghRun;
  if (!g || !STATIC) return;
  const label = g.status === "completed"
    ? `<span class="pill ${g.conclusion === "success" ? "pill-sage" : "pill-danger"}">${icon(g.conclusion === "success" ? "check" : "alert")}séance terminée</span>`
    : `<span class="pill pill-coral"><i class="dot run"></i>${g.status === "in_progress" ? "séance en cours sur GitHub" : "en attente sur GitHub"}</span>`;
  $("#live-status").innerHTML = g.url ? `<a href="${esc(g.url)}" target="_blank" rel="noopener" style="text-decoration:none">${label}</a>` : label;
}

$("#btn-sim").onclick = () => {
  if (STATIC) return openForce();
  run("simulation");
};
$("#btn-real").onclick = () => {
  const open = S.ov?.horloge?.is_open;
  $("#modal-text").textContent = (open
    ? "La bourse est ouverte : l'équipe va faire une séance de suivi et les ordres du gérant seront exécutés immédiatement"
    : "La bourse est fermée : l'équipe va préparer ses ordres, exécutés automatiquement à l'ouverture")
    + (S.ov?.paper ? " sur votre compte Alpaca paper (argent virtuel)." : ", AVEC VOTRE ARGENT RÉEL.");
  $("#modal").classList.add("open");
  $("#modal-no").focus();
};
const closeModal = () => $("#modal").classList.remove("open");
$("#modal-no").onclick = closeModal;
$("#modal-yes").onclick = () => { closeModal(); run("reel"); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeModal(); closeForce(); } });
let rz;
window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => S.ov && S.page === "accueil" && renderChart(S.ov), 150); });

$$(".js-ic").forEach((el) => (el.innerHTML = icon(el.dataset.ic)));
applyThemeButton();
route();
refreshAll();
pollLive();
setInterval(() => { if (!S.wasRunning) refreshAll(); }, STATIC ? 120000 : 30000);
