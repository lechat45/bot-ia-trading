"use strict";

/* ---------- Utilitaires ---------- */
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
const tone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "muted");
const fmtDate = (d, opt) => new Date(d).toLocaleString("fr-FR", { timeZone: "Europe/Paris", ...opt });
const hm = (d) => fmtDate(d, { hour: "2-digit", minute: "2-digit" });

// En ligne (GitHub Pages), pas de serveur : on lit les fichiers générés par build_site.py.
const STATIC = !!window.STATIC_SITE;
function staticPath(p) {
  const u = new URL(p, location.href);
  if (u.pathname.endsWith("/api/session")) return `data/sessions/${encodeURIComponent(u.searchParams.get("nom"))}.json`;
  return `data/${u.pathname.split("/").pop()}.json`;
}
const api = (p, opt) => fetch(STATIC ? `${staticPath(p)}?v=${Date.now()}` : p, opt).then((r) => r.json());

/* ---------- Icônes Flow : grille 24 px, trait 1,6 px, bouts arrondis ---------- */
const P = {
  home: '<path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z"/>',
  users: '<circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.6-3 2.8-4.6 5.5-4.6s4.9 1.6 5.5 4.6"/><path d="M15.5 5.6a3 3 0 0 1 0 5.8M17.5 14.6c1.6.6 2.7 2 3 4.4"/>',
  briefcase: '<rect x="3.5" y="7" width="17" height="12.5" rx="2"/><path d="M8.5 7V5.5a1.5 1.5 0 0 1 1.5-1.5h4a1.5 1.5 0 0 1 1.5 1.5V7M3.5 12.5h17"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  chart: '<path d="M4 4v16h16"/><path d="m7.5 14.5 3.5-3.5 3 3 5-5.5"/>',
  spark: '<path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3M6 6l2.1 2.1M15.9 15.9 18 18M6 18l2.1-2.1M15.9 8.1 18 6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M5.5 18.5l1.4-1.4M17.1 6.9l1.4-1.4"/>',
  moon: '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
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

const S = { ov: null, sessions: [], brain: null, current: null, notes: {}, live: null, wasRunning: false, tab: null };

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
const avatar = (id, small) => `<span class="avatar${small ? " sm" : ""}" style="--c:${META[id]?.color || "var(--coral)"}">${icon(id)}</span>`;
const providerPill = (a) => `<span class="pill ${a.provider === "gemini" ? "pill-sky" : "pill-peach"}">${a.provider === "gemini" ? "Gemini" : "Groq"} · clé ${a.cle}</span>`;
const modelName = (m) => String(m || "").replace(/^(gemini|groq)#\d:/, "").replace("openai/", "").replace("qwen/", "");
const verdictPill = (v) => v ? `<span class="pill ${VERDICT[v.verdict]?.[1] || ""}">critique : ${esc(VERDICT[v.verdict]?.[0] || v.verdict)}</span>` : '<span class="pill">pas d\'avis</span>';

/* ---------- Thème ---------- */
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

/* ---------- En-tête ---------- */
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
  $("#btn-sim span").textContent = STATIC ? "Lancer sur GitHub" : o.demo ? "Lancer une démo" : "Lancer une simulation";
  $("#btn-sim").hidden = STATIC && !o.actions_url;
  $("#btn-real").hidden = !!o.demo || STATIC;

  const ban = $("#banner");
  const show = (kind, ic, html) => { ban.className = `banner ${kind}`; ban.innerHTML = `${icon(ic)}<span>${html}</span>`; ban.hidden = false; };
  if (o.erreur) show("err", "alert", `Alpaca ne répond pas : ${esc(o.erreur)}`);
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

/* ---------- Bandeau ---------- */
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
  $("#k-perf-sub").textContent = first ? `${money(a.equity - first.v, 0)} depuis le ${fmtDate(first.t * 1000, { day: "numeric", month: "short" })}` : "";
  const e = o.equipe || {};
  const cash = e.cash ?? a.cash, total = e.valeur || a.equity || 1;
  $("#k-cash").textContent = money(cash, 0);
  $("#k-cash-bar").style.width = `${Math.max(0, Math.min(100, (cash / total) * 100))}%`;
  const pos = o.positions || [];
  const pl = pos.reduce((s, p) => s + (p.pl || 0), 0);
  $("#k-pos").textContent = `${pos.length}`;
  $("#k-pos-sub").innerHTML = pos.length ? `Latent : <span class="${tone(pl)}">${esc(money(pl, 0))}</span> · max ${esc(o.limites.max_positions)}`
    : `${((cash / total) * 100).toFixed(0)} % en liquidités`;
  $("#nav-pos").textContent = pos.length || "";
}

/* ---------- Dernière décision de l'équipe ---------- */
function proposalRow(p) {
  const det = p.action === "acheter"
    ? `${money(p.montant, 0)} · stop -${p.stop_loss_pct} % · objectif +${p.take_profit_pct} %`
    : `${p.pourcentage ?? 100} % de la position`;
  return `<div class="order">${avatar(p.auteur, true)}${actionPill(p.action)}<span class="mono"><b>${esc(p.symbole)}</b></span><span class="small muted">${esc(det)}</span>
    ${verdictPill(p.avis)}${p.retenue ? `<span class="pill pill-coral">${icon("check")}retenue</span>` : ""}
    <details class="why"><summary>Thèse de ${esc(shortName(p.auteur))}${p.confiance ? ` · confiance ${esc(p.confiance)}` : ""}</summary>${md(p.these)}${p.avis?.raison ? `<br><br><b>Critique :</b> ${md(p.avis.raison)}` : ""}</details></div>`;
}

function renderDecision() {
  const d = S.brain;
  if (!d) {
    $("#decision").innerHTML = empty("gerant", "Pas encore de séance", "Lancez une simulation pour voir l'équipe proposer, contrôler et décider.");
    $("#decision-when").textContent = "";
    return;
  }
  $("#decision-when").innerHTML = `${MODE[d.mode] ? `<span class="pill ${MODE[d.mode][1]}">${esc(MODE[d.mode][0])}</span>` : ""}${d.simulation ? '<span class="pill">Simulation</span>' : ""}${esc(fmtDate(d.ts, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))}`;
  const props = d.propositions || [];
  $("#decision").innerHTML = `
    <div class="synth"><div class="who">${icon("gerant")}Le gérant</div><p class="clamp">${md(d.decision || "—")}</p></div>
    <div class="sub-h overline" style="margin-top:16px">Propositions des analystes (${props.length})</div>
    ${props.length ? `<div class="list">${props.map(proposalRow).join("")}</div>` : '<p class="muted small">Aucune proposition à cette séance.</p>'}`;
}

/* ---------- Journée de bourse ---------- */
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
  const st = $("#live-status");
  st.innerHTML = running ? `<span class="pill pill-coral"><i class="dot run"></i>${esc(MODE[etat.mode]?.[0] || "Séance")}${etat.simulation ? " (simulation)" : ""} en cours</span>`
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
  renderDay();
  renderAgents();
}

/* ---------- Graphique ---------- */
function smoothPath(pts) {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`;
  }
  return d;
}

function renderChart(o) {
  const box = $("#chart");
  let pts = (o.historique || []).map((p) => ({ t: p.t * 1000, v: p.v }));
  if (pts.length < 2) pts = (o.historique_ia || []).map((r) => ({ t: new Date(r.date).getTime(), v: r.valeur }));
  $("#chart-legend").textContent = "30 derniers jours";
  if (pts.length < 2) {
    box.innerHTML = empty("chart", "Pas encore d'historique", "La courbe apparaîtra après les premières séances.");
    return;
  }
  const W = box.clientWidth || 700, H = box.clientHeight || 260, L = 70, R = 12, T = 12, B = 28;
  const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  let lo = Math.min(...pts.map((p) => p.v)), hi = Math.max(...pts.map((p) => p.v));
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
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Évolution de la valeur du compte">
    <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="c-stop-a"/><stop offset="1" class="c-stop-b"/></linearGradient></defs>
    ${grid}<path d="${smoothPath(xy)} L${last[0]},${H - B} L${xy[0][0]},${H - B} Z" fill="url(#area)"/>
    <path class="c-line" d="${smoothPath(xy)}"/><circle class="c-dot" cx="${last[0]}" cy="${last[1]}" r="4.5"/></svg>`;
}

/* ---------- L'équipe ---------- */
function brainOf(id) { return S.brain?.agents?.[id] || null; }

function stats(b) {
  if (!b) return "";
  const out = [];
  if (b.propositions?.length) out.push(`${b.propositions.length} proposition${b.propositions.length > 1 ? "s" : ""}`);
  if (b.avis?.length) out.push(`${b.avis.length} avis`);
  if (b.ordres?.length) out.push(`${b.ordres.length} ordre${b.ordres.length > 1 ? "s" : ""}`);
  return out.map((s) => `<span class="pill pill-coral">${esc(s)}</span>`).join("");
}

function renderAgents() {
  const o = S.ov;
  if (!o) return;
  const etat = S.live?.etat || {}, running = S.live?.runner?.running || etat.running;
  $("#agents").innerHTML = o.agents.map((a) => {
    const m = META[a.id] || {}, b = brainOf(a.id);
    const st = etat.agents?.[a.id] || {};
    const thinking = running && ["reflechit", "outil"].includes(st.statut);
    const status = thinking
      ? `<span class="typing"><i></i><i></i><i></i></span><span style="color:var(--coral-soft);font-weight:600">${esc(st.statut === "outil" ? st.action : "réfléchit…")}</span>`
      : !a.cle_configuree ? `<span class="pill pill-peach">${icon("key")}Clé manquante, relais par une autre</span>`
      : `<i class="dot"></i>${b ? `Dernière séance : ${esc(MODE[S.brain.mode]?.[0] || "")} du ${esc(fmtDate(S.brain.ts, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))}` : "En veille"}`;
    return `<article class="card agent ${thinking ? "thinking" : ""}" data-id="${esc(a.id)}" tabindex="0" role="button" aria-label="Voir le cerveau de ${esc(a.nom)}">
      <div class="agent-top">${avatar(a.id)}<div><h3>${esc(a.nom)}</h3><div class="tag">${esc(m.tag)}</div></div></div>
      <div class="chips">${providerPill(a)}<span class="pill mono">${esc(modelName(b?.modele || a.modele))}</span>${stats(b)}</div>
      <p class="excerpt">${esc(plain(b?.compte_rendu) || "Pas encore de séance : lancez une simulation pour voir son raisonnement.")}</p>
      <div class="agent-status">${status}</div>
    </article>`;
  }).join("");
  $$(".agent").forEach((el) => {
    el.onclick = () => openDrawer(el.dataset.id);
    el.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDrawer(el.dataset.id); } };
  });
}

/* ---------- Le « cerveau » : chaque réflexion et chaque outil ---------- */
function toolLabel(st) {
  const a = st.args || {};
  const L = {
    consulter_portefeuille: ["briefcase", "Consulte le portefeuille"],
    screener: ["filter", `Screener : ${String(a.critere || "").replaceAll("_", " ")}`],
    historique_prix: ["chart", `Historique du cours : ${a.symbole || ""}`],
    donnees_financieres: ["doc", `Données financières : ${a.symbole || ""}`],
    actualites: ["news", `Actualités : ${a.symbole || "marché"}`],
    recherche_web: ["search", `Recherche web : « ${a.question || ""} »`],
    sentiment_reseaux: ["users", `Sentiment des réseaux : ${a.symbole || ""}`],
    ecrire_notes: ["edit", "Met à jour ses notes"],
    proposer_ordre: ["send", `Propose : ${a.action || ""} ${a.symbole || ""}${a.montant_usd ? ` pour ${money(a.montant_usd, 0)}` : ""}`],
    donner_avis: ["shield", `Avis sur ${a.id || ""} : ${a.verdict || ""}`],
    passer_ordre: ["wallet", `Ordre : ${a.action || ""} ${a.symbole || ""}${a.montant_usd ? ` pour ${money(a.montant_usd, 0)}` : ""}${a.stop_loss_pct ? ` · stop -${a.stop_loss_pct} % · objectif +${a.take_profit_pct} %` : ""}`],
    annuler_ordre: ["x", `Annule l'ordre planifié sur ${a.symbole || ""}`],
    ajuster_stop: ["shield", `Remonte le stop de ${a.symbole || ""} à ${money(a.nouveau_stop, 2)}`],
    lire_skill: ["book", `Lit le skill « ${a.nom || ""} »`],
    terminer_session: ["check", "Termine la séance"],
  };
  return L[st.nom] || ["spark", st.nom];
}

function brain(steps) {
  if (!steps?.length) return '<p class="muted">Aucune étape enregistrée.</p>';
  return `<ol class="brain">${steps.map((st) => {
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
        details = `<details><summary>Résultat de l'outil</summary><pre>${esc(st.resultat)}</pre></details>`;
      }
    }
    const kind = st.type === "pensee" ? "think" : st.type === "refus" ? "refus"
      : ["passer_ordre", "proposer_ordre", "donner_avis"].includes(st.nom) ? "order" : "tool";
    return `<li class="b-step b-${kind}"><span class="b-ic">${icon(ic)}</span><div class="b-body"><div class="b-title">${esc(title)}<span class="b-time">${esc(hm(st.t))}</span></div>${body ? `<div class="b-text">${md(body)}</div>` : ""}${details}</div></li>`;
  }).join("")}</ol>`;
}

function agentWork(id, b) {
  if (!b) return "";
  let html = "";
  if (b.propositions?.length) {
    const all = (S.brain?.propositions || []).filter((p) => p.auteur === id);
    html += `<div><div class="overline sub-h">Ses propositions</div><div class="list">${(all.length ? all : b.propositions).map(proposalRow).join("")}</div></div>`;
  }
  if (b.avis?.length) {
    html += `<div><div class="overline sub-h">Ses avis</div><div class="list">${b.avis.map((v) => `<div class="order"><span class="pill ${VERDICT[v.verdict]?.[1] || ""}">${esc(VERDICT[v.verdict]?.[0] || v.verdict)}</span><span class="mono small">${esc(v.id)}</span><div class="why">${md(v.raison)}</div></div>`).join("")}</div></div>`;
  }
  if (b.ordres?.length) {
    html += `<div><div class="overline sub-h">Ses ordres</div><div class="list">${b.ordres.map((o) => `<div class="order">${actionPill(o.action)}<span class="mono"><b>${esc(o.symbole)}</b></span>${o.source ? `<span class="pill mono">${esc(o.source)}</span>` : ""}<span class="small muted">${esc(o.resultat || "")}</span></div>`).join("")}</div></div>`;
  }
  return html;
}

let lastFocus = null;
function openDrawer(id) {
  const a = agentOf(id), m = META[id] || {}, b = brainOf(id);
  lastFocus = document.activeElement;
  $("#drawer").innerHTML = `<div class="drawer-head">${avatar(id)}
      <div><h3>${esc(a.nom)}</h3><div class="chips" style="margin-top:6px"><span class="pill">${esc(ROLE[a.role] || "")}</span>${providerPill(a)}<span class="pill mono">${esc(modelName(b?.modele || a.modele))}</span></div></div>
      <button class="icon-btn" id="drawer-x" aria-label="Fermer">${icon("x")}</button>
    </div>
    <div class="drawer-body">
      <div><div class="overline sub-h">Son rôle</div><p>${esc(m.desc)}</p></div>
      ${b ? `<div class="synth"><div class="who">${icon(id)}Compte rendu de la dernière séance</div><p>${md(b.compte_rendu || "—")}</p></div>` : ""}
      ${agentWork(id, b)}
      <div><div class="overline sub-h">Son cerveau pendant la dernière séance${S.brain ? ` (${esc(MODE[S.brain.mode]?.[0] || "")}, ${esc(fmtDate(S.brain.ts, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))})` : ""}</div>${b ? brain(b.etapes) : '<p class="muted">Pas encore de séance.</p>'}</div>
      <div><div class="overline sub-h">${id === "gerant" ? "Journal de bord de l'équipe" : "Ses notes"} (sa mémoire entre deux séances)</div><div class="notes">${esc(S.notes[id] || "Aucune note pour l'instant. Les notes sont enregistrées lors des séances réelles, pas en simulation.")}</div></div>
    </div>`;
  $("#drawer").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
  $("#scrim").classList.add("open");
  $("#drawer-x").onclick = closeDrawer;
  $("#drawer-x").focus();
}
function closeDrawer() {
  if (!$("#drawer").classList.contains("open")) return;
  $("#drawer").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
  $("#scrim").classList.remove("open");
  lastFocus?.focus?.();
}

/* ---------- Plan d'ouverture ---------- */
function actionPill(action) {
  const a = String(action || "").toLowerCase();
  const cls = a.startsWith("vend") || a.startsWith("all") ? "pill-danger" : a === "ajuster_stop" ? "pill-sky" : "pill-sage";
  return `<span class="pill ${cls}">${esc(String(action || "").replace("_", " "))}</span>`;
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
  $("#nav-plan").textContent = orders.filter((x) => x.statut === "en_attente").length || "";
  $("#plan-sub").textContent = plan.date
    ? `${plan.simulation ? "Simulation · " : ""}Préparé le ${fmtDate(plan.cree_le, { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })} · ${plan.execute_le ? `exécuté à ${hm(plan.execute_le)}` : plan.simulation ? "non exécuté (simulation)" : "en attente de l'ouverture de New York"}`
    : "";
  $("#plan-card").innerHTML = orders.length ? `<div class="list">${orders.map(planRow).join("")}</div>`
    : empty("calendar", "Aucun ordre planifié", `Chaque jour de bourse à ${o.limites?.preparation_heure ?? 9} h, l'équipe prépare les ordres de l'ouverture.`);
}

/* ---------- Positions ---------- */
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

/* ---------- Historique ---------- */
const modePill = (m) => `<span class="pill ${MODE[m]?.[1] || ""}">${esc(MODE[m]?.[0] || m || "Séance")}</span>`;

function renderSessions() {
  const list = S.sessions;
  $("#sess-count").textContent = list.length ? `${list.length} séance${list.length > 1 ? "s" : ""}` : "";
  $("#nav-sess").textContent = list.length || "";
  if (!list.length) {
    $("#sess-list").innerHTML = "";
    $("#detail").innerHTML = empty("clock", "Aucune séance pour l'instant", "Lancez une simulation : chaque séance apparaîtra ici avec le cerveau complet des 6 IA.");
    return;
  }
  $("#sess-list").innerHTML = list.map((s) => `<button class="sess ${S.current?.nom === s.nom ? "sel" : ""}" data-n="${esc(s.nom)}">
      <div class="t"><span>${esc(s.quand || s.nom)}</span></div>
      <div class="s">${esc(plain(s.decision) || "")}</div>
      <div class="m">${modePill(s.mode)}${s.simulation ? '<span class="pill">Simulation</span>' : ""}${s.propositions ? `<span class="pill">${s.propositions} prop.</span>` : ""}<span class="pill">${s.ordres} ordre${s.ordres > 1 ? "s" : ""}</span>${s.erreurs ? `<span class="pill pill-danger">${s.erreurs} erreur${s.erreurs > 1 ? "s" : ""}</span>` : ""}</div>
    </button>`).join("");
  $$(".sess").forEach((b) => (b.onclick = () => loadSession(b.dataset.n)));
}

async function loadSession(nom) {
  const d = await api(`/api/session?nom=${encodeURIComponent(nom)}`);
  if (d.erreur) return toast(d.erreur, "alert");
  S.current = d;
  renderSessions();
  renderDetail();
}

function renderDetail() {
  const d = S.current;
  if (!d) return;
  const head = `<div class="detail-head"><h3>Séance du ${esc(d.quand)}</h3>${modePill(d.mode)}${d.simulation ? '<span class="pill">Simulation</span>' : ""}<span class="right">valeur ${esc(money(d.valeur_avant, 0))} → ${esc(money(d.compte?.valeur, 0))}</span></div>`;
  if (d.mode === "ouverture") {
    $("#detail").innerHTML = `${head}<div><div class="overline sub-h">Ordres planifiés exécutés à l'ouverture</div>
      <div class="list">${(d.executions || []).map(planRow).join("") || '<div class="empty-line">Aucun ordre à exécuter.</div>'}</div></div>`;
    return;
  }
  const ids = Object.keys(d.agents || {});
  if (!ids.includes(S.tab)) S.tab = ids.includes("gerant") ? "gerant" : ids[0];
  const r = d.agents[S.tab] || {};
  const tok = Object.entries(d.cles || {}).sort();
  const maxTok = Math.max(1, ...tok.map(([, v]) => v.tokens || v.appels || 0));
  const props = d.propositions || [];
  $("#detail").innerHTML = `${head}
    <div class="synth"><div class="who">${icon("gerant")}Décision du gérant</div><p>${md(d.decision || "—")}</p></div>
    <div><div class="overline sub-h">Propositions des analystes (${props.length})</div>${props.length ? `<div class="list">${props.map(proposalRow).join("")}</div>` : '<p class="muted small">Aucune proposition.</p>'}</div>
    <div>
      <div class="tabs" role="tablist">${ids.map((t) => `<button class="tab ${S.tab === t ? "on" : ""}" role="tab" aria-selected="${S.tab === t}" data-t="${esc(t)}">${esc(shortName(t))}</button>`).join("")}</div>
      <div class="panel">
        <div class="small muted">${esc(ROLE[r.role] || "")} · ${esc(modelName(r.modele))} · ${r.outils || 0} appels d'outils · ${Math.round((r.duree_s || 0) / 60)} min · ${(r.tokens || 0).toLocaleString("fr-FR")} tokens</div>
        ${r.erreur ? `<div class="banner err">${icon("alert")}<span>${esc(r.erreur)}</span></div>` : ""}
        ${S.tab !== "gerant" ? `<div class="synth"><div class="who">${icon(S.tab)}Compte rendu</div><p>${md(r.compte_rendu || "—")}</p></div>` : ""}
        ${agentWork(S.tab, r)}
        <div><div class="overline sub-h">Son cerveau, étape par étape</div>${brain(r.etapes)}</div>
      </div>
    </div>
    ${tok.length ? `<div><div class="overline sub-h">Consommation des clés (gratuite)</div><div class="tokens">${tok.map(([k, v]) => `<div class="tok"><span class="mono">${esc(k)}</span><div class="bar"><i class="${k.startsWith("gemini") ? "gemini" : "groq"}" style="width:${((v.tokens || v.appels || 0) / maxTok) * 100}%"></i></div><span class="muted">${(v.tokens || 0).toLocaleString("fr-FR")} tokens · ${v.appels || 0} appels</span></div>`).join("")}</div></div>` : ""}`;
  $$(".tab").forEach((b) => (b.onclick = () => { S.tab = b.dataset.t; renderDetail(); }));
}

/* ---------- Navigation ---------- */
function setActive(id) { $$(".nav-item, .tabbar a").forEach((a) => a.classList.toggle("active", a.dataset.s === id)); }
const io = new IntersectionObserver((entries) => {
  const vis = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
  if (vis) setActive(vis.target.id);
}, { rootMargin: "-80px 0px -55% 0px" });
$$(".section").forEach((s) => io.observe(s));
$$(".js-ic").forEach((el) => (el.innerHTML = icon(el.dataset.ic)));

/* ---------- Chargement ---------- */
async function refreshAll(force = false) {
  try {
    const [ov, sessions, notes] = await Promise.all([api("/api/overview"), api("/api/sessions"), api("/api/notes")]);
    S.ov = ov; S.notes = notes; S.sessions = sessions;
    const lastBrain = sessions.find((s) => s.mode !== "ouverture");
    if (lastBrain && (force || S.brain?.nom !== lastBrain.nom)) S.brain = await api(`/api/session?nom=${encodeURIComponent(lastBrain.nom)}`);
    if (sessions.length && (force || !S.current)) S.current = await api(`/api/session?nom=${encodeURIComponent(sessions[0].nom)}`);
    renderHeader(ov); renderBand(ov); renderDecision(); renderChart(ov); renderPlan(ov); renderPositions(ov);
    renderDay(); renderAgents(); renderSessions(); renderDetail();
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
}

$("#btn-sim").onclick = () => {
  if (STATIC) return S.ov?.actions_url && window.open(S.ov.actions_url, "_blank", "noopener");
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
$("#scrim").onclick = closeDrawer;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeDrawer(); closeModal(); } });
let rz;
window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => S.ov && renderChart(S.ov), 150); });

applyThemeButton();
refreshAll();
pollLive();
setInterval(() => { if (!S.wasRunning) refreshAll(); }, STATIC ? 120000 : 30000);
