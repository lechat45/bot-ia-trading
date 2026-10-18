"use strict";

/* ---------- Utilitaires ---------- */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v) => (v === null || v === undefined || v === "" || isNaN(+v) ? null : +v);
const money = (v, d = 0) => num(v) === null ? "—" : `${new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: d, maximumFractionDigits: d }).format(v)} $`;
const pct = (v, d = 2) => num(v) === null ? "—" : `${v > 0 ? "+" : ""}${(+v).toFixed(d).replace(".", ",")} %`;
const tone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "muted");
const fmtDate = (d, opt) => new Date(d).toLocaleString("fr-FR", opt);

// En ligne (GitHub Pages / Cloudflare), pas de serveur : on lit les fichiers générés par build_site.py.
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
  bell: '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  key: '<circle cx="8" cy="15" r="3.5"/><path d="m10.5 12.5 8-8M15.5 7.5l2.5 2.5"/>',
  shield: '<path d="M12 3.5 5 6v5.5c0 4.5 3 7.7 7 9 4-1.3 7-4.5 7-9V6z"/>',
  wallet: '<rect x="3.5" y="6" width="17" height="13" rx="2"/><path d="M3.5 9.5h17M16 14h1.5"/>',
  // Agents
  qualite: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4M8.5 11h5M11 8.5v5"/>',
  equilibre: '<path d="M12 4v16M7 20h10M5 7.5h14"/><path d="m5 7.5-2.5 6a2.5 2.5 0 0 0 5 0zM19 7.5l-2.5 6a2.5 2.5 0 0 0 5 0z"/>',
  sentiment: '<path d="M12 21c3.9 0 6.5-2.8 6.5-6.5 0-2.8-1.9-5-3.3-6.4-.3 1.8-1.3 2.8-2.3 2.8 0-2.8-1.4-5.6-3.6-7.4.1 3.8-3.8 6-3.8 11 0 3.7 2.6 6.5 6.5 6.5z"/>',
  contrarien: '<path d="M4.5 8h13l-3-3M19.5 16h-13l3 3"/>',
  critique: '<path d="M12 3.5 5 6v5.5c0 4.5 3 7.7 7 9 4-1.3 7-4.5 7-9V6z"/><path d="m9 12 2 2 4-4"/>',
  gerant: '<path d="m3.5 8.5 4 3 4.5-6 4.5 6 4-3-2 10h-13z"/><path d="M5.5 20.5h13"/>',
};
const icon = (name, cls = "ic") =>
  `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || ""}</svg>`;

const META = {
  qualite: { tag: "Qualité · chiffres et patience",
    desc: "Épluche les chiffres (croissance, marges, dette, valorisation). Cherche des entreprises solides à prix raisonnable et ne panique pas quand le prix baisse tant que la thèse tient. Inspiré de l'agent « Claude » d'Aywen." },
  equilibre: { tag: "Équilibre · diversification",
    desc: "Construit un portefeuille diversifié sur des secteurs variés pour limiter le risque, sans tout analyser pour ne jamais agir. Inspiré de l'agent « ChatGPT » d'Aywen." },
  sentiment: { tag: "Sentiment · momentum",
    desc: "Mise sur l'humeur du marché : actualité chaude, tendances Reddit, actions en forte dynamique. Accepte plus de risque, dans les limites du code. Inspiré de l'agent « Grok », vainqueur de l'expérience d'Aywen." },
  contrarien: { tag: "Contrarien · rebonds",
    desc: "Cherche les actions qui ont beaucoup chuté, à condition de prouver que le marché a surréagi, avec un catalyseur daté. A retenu les leçons des erreurs de l'agent « Mistral »." },
  critique: { tag: "Avocat du diable",
    desc: "Contrôle chaque proposition : faits datés, catalyseur dans l'horizon, stop hors du bruit, paris corrélés, comportements interdits. Verdict : ok, réserve ou rejet." },
  gerant: { tag: "Décision finale",
    desc: "Synthétise les 4 analystes et l'avis du critique, vérifie avec Google Search, surveille l'ensemble du portefeuille et décide des ordres. Ses notes sont le journal de bord de l'équipe." },
};
const STEPS = [
  ["portefeuille", "Lecture du portefeuille"], ["marche", "Screener et actualités"],
  ["selection", "Sélection des titres"], ["donnees", "Collecte des données"],
  ["theses", "Rédaction des thèses"], ["critique", "Contrôle du critique"],
  ["gerant", "Décision du gérant"], ["ordres", "Garde-fous et ordres"],
];
const STAGE_LABEL = { selection: "sélectionne ses titres", theses: "rédige ses thèses", critique: "contrôle les propositions", gerant: "prend la décision" };
const VERDICT = { ok: "pill-sage", reserve: "pill-peach", rejet: "pill-danger" };

const S = { ov: null, sessions: [], latest: null, current: null, notes: {}, live: null, wasRunning: false, tab: "qualite" };

function toast(msg, ic = "info") {
  const t = $("#toast");
  t.innerHTML = `${icon(ic)}<span>${esc(msg)}</span>`;
  t.classList.add("show");
  clearTimeout(toast.h);
  toast.h = setTimeout(() => t.classList.remove("show"), 3200);
}
const empty = (ic, title, sub) =>
  `<div class="empty"><span class="ic-box">${icon(ic)}</span><b>${esc(title)}</b><span class="small">${esc(sub)}</span></div>`;

/* ---------- Thème clair / sombre ---------- */
function applyThemeButton() {
  const dark = document.documentElement.dataset.theme === "dark";
  const b = $("#theme-btn");
  b.innerHTML = icon(dark ? "sun" : "moon");
  b.setAttribute("aria-label", dark ? "Passer en thème clair" : "Passer en thème sombre");
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
  return h >= 24 ? fmtDate(iso, { weekday: "short", hour: "2-digit", minute: "2-digit" })
    : h > 0 ? `dans ${h} h ${String(m).padStart(2, "0")}` : `dans ${m} min`;
}

function renderHeader(o) {
  const [cls, label] = o.demo ? ["pill-peach", "Démo"] : o.paper ? ["pill-sky", "Paper trading"] : ["pill-danger", "Argent réel"];
  $$(".js-mode").forEach((b) => { b.className = `js-mode pill ${cls}`; b.textContent = label; });
  const h = o.horloge || {};
  const open = !!h.is_open;
  $$(".js-market").forEach((m) => {
    m.innerHTML = `<i class="dot ${open ? "on" : ""}"></i><span>${open
      ? `Bourse de New York ouverte · ferme ${esc(relTime(h.next_close))}`
      : `Bourse fermée · ouvre ${esc(relTime(h.next_open))}`}</span>`;
  });
  $("#btn-sim span").textContent = STATIC ? "Lancer sur GitHub" : o.demo ? "Lancer une démo" : "Lancer une simulation";
  $("#btn-sim").hidden = STATIC && !o.actions_url;
  $("#btn-real").hidden = !!o.demo || STATIC;

  const ban = $("#banner");
  const show = (kind, ic, html) => { ban.className = `banner ${kind}`; ban.innerHTML = `${icon(ic)}<span>${html}</span>`; ban.hidden = false; };
  if (o.erreur) show("err", "alert", `Alpaca ne répond pas : ${esc(o.erreur)}`);
  else if (STATIC) show("info", "info", `Version en ligne, mise à jour automatiquement après chaque session. Dernière mise à jour : ${esc(fmtDate(o.genere_le, { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }))}.`);
  else if (o.demo) show("warn", "info", "Mode démo : aucune clé Alpaca dans le fichier .env, les chiffres affichés sont factices. Remplissez .env puis relancez « python dashboard.py ».");
  else ban.hidden = true;

  const k = o.cles || {};
  $("#nav-foot").innerHTML = `
    <div class="row"><span>Clés Gemini</span><span class="pill ${k.gemini >= 3 || o.demo ? "pill-sage" : "pill-peach"}">${o.demo ? "démo" : `${k.gemini}/3`}</span></div>
    <div class="row"><span>Clés Groq</span><span class="pill ${k.groq >= 3 || o.demo ? "pill-sage" : "pill-peach"}">${o.demo ? "démo" : `${k.groq}/3`}</span></div>
    <div class="row"><span>Max par titre</span><span>${esc(o.limites.max_position_pct)} %</span></div>
    <div class="row"><span>Cash minimum</span><span>${esc(o.limites.min_cash_pct)} %</span></div>`;
}

/* ---------- Bandeau : chiffres clés ---------- */
function renderKpis(o) {
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
  const cashPct = a.equity ? (a.cash / a.equity) * 100 : 0;
  $("#k-cash").textContent = money(a.cash, 0);
  $("#k-cash-bar").style.width = `${Math.max(0, Math.min(100, cashPct))}%`;
  const pos = o.positions || [];
  const pl = pos.reduce((s, p) => s + p.pl, 0);
  $("#k-pos").textContent = `${pos.length}`;
  $("#k-pos-sub").innerHTML = pos.length
    ? `Latent : <span class="${tone(pl)}">${esc(money(pl, 0))}</span> · max ${esc(o.limites.max_positions)}`
    : `max ${esc(o.limites.max_positions)} · ${cashPct.toFixed(0)} % en cash`;
  $("#nav-pos").textContent = pos.length || "";
}

/* ---------- Graphique ---------- */
function smoothPath(pts) {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${c1[0]},${c1[1]} ${c2[0]},${c2[1]} ${p2[0]},${p2[1]}`;
  }
  return d;
}

function renderChart(points) {
  const box = $("#chart");
  if (!points || points.length < 2) {
    box.innerHTML = empty("chart", "Pas encore d'historique", "La courbe apparaîtra après quelques jours de trading.");
    return;
  }
  const W = box.clientWidth || 700, H = box.clientHeight || 260, L = 64, R = 12, T = 12, B = 28;
  const vs = points.map((p) => p.v);
  let lo = Math.min(...vs), hi = Math.max(...vs);
  const pad = (hi - lo) * 0.15 || hi * 0.01 || 1;
  lo -= pad; hi += pad;
  const x = (i) => L + (i / (points.length - 1)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const pts = points.map((p, i) => [x(i), y(p.v)]);
  const line = smoothPath(pts);
  let grid = "";
  for (let k = 0; k <= 4; k++) {
    const v = lo + ((hi - lo) * k) / 4, yy = y(v);
    grid += `<line class="c-grid" x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}"/>
      <text class="c-label" x="${L - 10}" y="${yy + 4}" text-anchor="end">${esc(money(v, 0))}</text>`;
  }
  const n = Math.min(5, points.length);
  for (let k = 0; k < n; k++) {
    const i = Math.round((k * (points.length - 1)) / (n - 1 || 1));
    grid += `<text class="c-label" x="${x(i)}" y="${H - 6}" text-anchor="${k === 0 ? "start" : k === n - 1 ? "end" : "middle"}">${esc(fmtDate(points[i].t * 1000, { day: "numeric", month: "short" }))}</text>`;
  }
  const last = pts[pts.length - 1];
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Évolution de la valeur du portefeuille">
    <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="c-stop-a"/><stop offset="1" class="c-stop-b"/></linearGradient></defs>
    ${grid}
    <path d="${line} L${last[0]},${H - B} L${pts[0][0]},${H - B} Z" fill="url(#area)"/>
    <path class="c-line" d="${line}"/>
    <circle class="c-dot" cx="${last[0]}" cy="${last[1]}" r="4.5"/>
    <g id="hover" opacity="0"><line class="c-hover-line" id="hl" y1="${T}" y2="${H - B}"/><circle class="c-hover-dot" id="hc" r="5"/></g>
    <rect x="${L}" y="0" width="${W - L - R}" height="${H}" fill="transparent" id="hit"/>
  </svg><div class="chart-tip" id="tip"></div>`;
  const hit = $("#hit", box), g = $("#hover", box), tip = $("#tip", box);
  hit.addEventListener("mousemove", (e) => {
    const r = box.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(points.length - 1, Math.round(((mx - L) / (W - L - R)) * (points.length - 1))));
    const [px, py] = pts[i];
    g.setAttribute("opacity", "1");
    $("#hl", box).setAttribute("x1", px); $("#hl", box).setAttribute("x2", px);
    $("#hc", box).setAttribute("cx", px); $("#hc", box).setAttribute("cy", py);
    const chg = (points[i].v / points[0].v - 1) * 100;
    tip.innerHTML = `<b>${esc(money(points[i].v, 2))}</b> <span class="${tone(chg)}">${esc(pct(chg))}</span><br><span class="muted">${esc(fmtDate(points[i].t * 1000, { weekday: "long", day: "numeric", month: "long" }))}</span>`;
    tip.style.left = `${(px / W) * 100}%`; tip.style.top = `${(py / H) * r.height}px`; tip.style.opacity = "1";
  });
  hit.addEventListener("mouseleave", () => { g.setAttribute("opacity", "0"); tip.style.opacity = "0"; });
}

/* ---------- Agents ---------- */
function agentLast(id, d = S.latest) {
  if (!d) return {};
  const so = d.sorties || {};
  if (id === "gerant") return { texte: d.decision?.synthese, modele: d.modeles?.["gerant:gerant"], props: d.decision?.ordres || [] };
  if (id === "critique") return { texte: so.critique?.risques_portefeuille, modele: d.modeles?.["critique:critique"], avis: so.critique?.avis || [] };
  const sel = so[`selection:${id}`] || {}, th = so[`theses:${id}`] || {};
  return { tickers: sel.tickers || [], raison: sel.raison, texte: th.analyse || sel.raison,
    modele: d.modeles?.[`theses:${id}`] || d.modeles?.[`selection:${id}`], props: th.propositions || [] };
}
const providerPill = (a) => `<span class="pill ${a.provider === "gemini" ? "pill-sky" : "pill-peach"}">${a.provider === "gemini" ? "Gemini" : "Groq"} · clé ${a.cle}</span>`;

function renderAgents() {
  const o = S.ov;
  if (!o) return;
  const etat = S.live?.etat || {}, running = S.live?.runner?.running || etat.running;
  $("#agents").innerHTML = o.agents.map((a) => {
    const m = META[a.id] || {};
    const last = agentLast(a.id);
    const thinking = running && etat.agent === a.id;
    const status = thinking
      ? `<span class="typing"><i></i><i></i><i></i></span><span style="color:var(--coral-soft);font-weight:600">${esc(STAGE_LABEL[etat.etape] || "réfléchit")}…</span>`
      : !a.cle_configuree ? `<span class="pill pill-peach">${icon("key")}Clé manquante, relais par une autre clé</span>`
      : `<i class="dot"></i>En veille`;
    const tickers = (last.tickers || []).map((t) => `<span class="pill tk">${esc(t)}</span>`).join("");
    const n = (last.props || []).length;
    const extra = a.id === "critique" && last.avis?.length ? `<span class="pill">${last.avis.length} avis</span>`
      : n ? `<span class="pill pill-coral">${n} ${a.id === "gerant" ? "ordre" : "proposition"}${n > 1 ? "s" : ""}</span>` : "";
    return `<article class="card agent ${thinking ? "thinking" : ""}" data-id="${esc(a.id)}" tabindex="0" role="button" aria-label="Voir le détail de ${esc(a.nom)}">
      <div class="agent-top">
        <span class="avatar">${icon(a.id)}</span>
        <div><h3>${esc(a.nom)}</h3><div class="tag">${esc(m.tag)}</div></div>
      </div>
      <div class="chips">${providerPill(a)}${tickers}${extra}</div>
      <p class="excerpt">${esc(last.texte || "Pas encore de session : lancez une simulation pour voir son raisonnement.")}</p>
      <div class="agent-status">${status}</div>
    </article>`;
  }).join("");
  $$(".agent").forEach((el) => {
    el.onclick = () => openDrawer(el.dataset.id);
    el.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDrawer(el.dataset.id); } };
  });
}

function actionPill(action) {
  const a = String(action || "").toLowerCase();
  const cls = a.startsWith("vend") || a.startsWith("all") ? "pill-danger" : a === "ajuster_stop" ? "pill-sky" : "pill-sage";
  return `<span class="pill ${cls}">${esc(String(action || "").replace("_", " "))}</span>`;
}

function propCard(p) {
  const rows = [
    ["Poids", p.poids_pct != null ? `${p.poids_pct} %` : null], ["Stop loss", p.stop_loss], ["Objectif", p.take_profit],
    ["Horizon", p.horizon_jours ? `${p.horizon_jours} jours` : null], ["Arguments", p.arguments || p.justification],
    ["Risques", p.risques], ["Invalidation", p.invalidation], ["Source", p.source],
  ].filter(([, v]) => v !== null && v !== undefined && v !== "");
  return `<div class="prop"><div class="prop-h">${actionPill(p.action)}<span class="s">${esc(p.symbole)}</span>${p.confiance ? `<span class="pill">confiance ${esc(p.confiance)}</span>` : ""}</div>
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>`;
}
const verdictRow = (v) => `<div class="verdict"><span class="pill ${VERDICT[v.verdict] || ""}">${esc(v.verdict)}</span><span class="mono muted small">${esc(v.id)}</span><span>${esc(v.raison)}</span></div>`;

let lastFocus = null;
function openDrawer(id) {
  const a = S.ov.agents.find((x) => x.id === id);
  const m = META[id] || {};
  const last = agentLast(id);
  lastFocus = document.activeElement;
  $("#drawer").innerHTML = `<div class="drawer-head">
      <span class="avatar">${icon(id)}</span>
      <div><h3>${esc(a.nom)}</h3><div class="chips" style="margin-top:6px">${providerPill(a)}${last.modele ? `<span class="pill mono">${esc(last.modele)}</span>` : ""}</div></div>
      <button class="icon-btn" id="drawer-x" aria-label="Fermer">${icon("x")}</button>
    </div>
    <div class="drawer-body">
      <div><div class="overline sub-h">Stratégie</div><p>${esc(m.desc)}</p></div>
      ${last.tickers?.length ? `<div><div class="overline sub-h">Titres choisis</div><div class="chips" style="margin-top:0">${last.tickers.map((t) => `<span class="pill tk">${esc(t)}</span>`).join("")}</div>${last.raison ? `<p class="small muted" style="margin-top:8px">${esc(last.raison)}</p>` : ""}</div>` : ""}
      <div><div class="overline sub-h">Dernière réflexion</div><p>${esc(last.texte || "—")}</p></div>
      ${(last.avis || []).length ? `<div><div class="overline sub-h">Verdicts</div>${last.avis.map(verdictRow).join("")}</div>` : ""}
      ${(last.props || []).length ? `<div class="panel" style="margin-top:0"><div class="overline">${id === "gerant" ? "Ordres décidés" : "Propositions"}</div>${last.props.map(propCard).join("")}</div>` : ""}
      <div><div class="overline sub-h">Notes (sa mémoire entre deux sessions)</div><div class="notes">${esc(S.notes[id] || "Aucune note pour l'instant. Les notes sont écrites après une session réelle, pas en simulation.")}</div></div>
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

/* ---------- Positions ---------- */
function renderPositions(o) {
  const pos = o.positions || [];
  const box = $("#positions-table");
  if (!pos.length) {
    box.style.margin = "0";
    box.innerHTML = empty("briefcase", "Aucune position", "Le portefeuille est entièrement en liquidités.");
    return;
  }
  box.style.margin = "";
  const eq = o.compte?.equity || 1;
  box.innerHTML = `<table><thead><tr><th>Titre</th><th>Quantité</th><th>Prix d'achat</th><th>Prix</th><th>Valeur</th><th>Poids</th><th>Plus ou moins-value</th><th>Stop, prix, objectif</th></tr></thead><tbody>
    ${pos.map((p) => {
      let range = '<span class="muted small">Pas de sortie programmée</span>';
      if (p.stop && p.tp && p.tp > p.stop) {
        const f = (v) => Math.max(0, Math.min(100, ((v - p.stop) / (p.tp - p.stop)) * 100));
        range = `<div class="range"><i class="en" style="left:${f(p.prix_achat)}%"></i><i class="mk" style="left:${f(p.prix)}%"></i></div>
          <div class="range-labels"><span>${esc(money(p.stop, 2))}</span><span>${esc(money(p.tp, 2))}</span></div>`;
      } else if (p.stop) range = `<span class="muted small">Stop ${esc(money(p.stop, 2))}</span>`;
      return `<tr><td><div class="sym"><span class="logo-s">${esc(p.symbole.slice(0, 4))}</span>${esc(p.symbole)}</div></td>
        <td>${esc(p.qty)}</td><td>${esc(money(p.prix_achat, 2))}</td><td>${esc(money(p.prix, 2))}</td>
        <td>${esc(money(p.valeur, 0))}</td><td>${((p.valeur / eq) * 100).toFixed(1).replace(".", ",")} %</td>
        <td><span class="pill ${p.pl >= 0 ? "pill-sage" : "pill-danger"}">${esc(money(p.pl, 0))} · ${esc(pct(p.pl_pct, 1))}</span></td><td>${range}</td></tr>`;
    }).join("")}</tbody></table>`;
}

/* ---------- Session en direct ---------- */
function renderLive() {
  const L = S.live;
  if (!L) return;
  const r = L.runner, etat = L.etat || {};
  const running = r.running || (etat.running && Date.now() - new Date(etat.maj) < 10 * 60e3);
  const idx = STEPS.findIndex(([k]) => k === etat.etape);
  const finished = etat.etape === "termine";
  $("#stepper").innerHTML = STEPS.map(([k, label], i) => {
    let c = "", ic = `${i + 1}`;
    if ((running && i < idx) || (!running && finished && (r.code === 0 || STATIC))) { c = "done"; ic = icon("check", ""); }
    else if (running && i === idx) { c = "active"; ic = ""; }
    const who = running && i === idx && etat.agent ? `<span class="who">${esc(S.ov?.agents.find((a) => a.id === etat.agent)?.nom || etat.agent)}</span>` : "";
    return `<li class="step ${c}"><span class="ic">${ic}</span>${esc(label)}${who}</li>`;
  }).join("");
  if (STATIC) {
    $("#console").textContent = "Les sessions tournent automatiquement sur GitHub Actions, du lundi au vendredi vers 17 h 05 et 20 h 35 (heure de Paris). Le détail de chaque session est dans l'historique.";
    $("#live-status").innerHTML = etat.maj ? `Dernière : ${esc(fmtDate(etat.maj, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))}` : "En veille";
    return renderAgents();
  }
  $("#live-status").innerHTML = running
    ? `<span class="pill pill-coral"><i class="dot run"></i>${r.mode === "reel" ? "Session réelle" : r.mode === "demo" ? "Démo" : "Simulation"} en cours</span>`
    : r.code === 0 ? `<span class="pill pill-sage">${icon("check")}Terminée</span>`
    : r.code ? `<span class="pill pill-danger">Erreur (code ${esc(r.code)})</span>` : "En veille";
  if (r.logs.length) {
    const con = $("#console");
    const stick = con.scrollTop + con.clientHeight >= con.scrollHeight - 30;
    con.innerHTML = r.logs.map((l) => {
      const c = /erreur|error|échec|traceback/i.test(l) ? "err" : /terminé|simulé|envoyé/i.test(l) ? "ok" : "";
      return `<span class="${c}">${esc(l)}</span>`;
    }).join("\n");
    if (stick) con.scrollTop = con.scrollHeight;
  }
  $("#btn-sim").disabled = running;
  $("#btn-real").disabled = running;
  if (S.wasRunning && !running) {
    toast(r.code === 0 ? "Session terminée" : "La session s'est arrêtée avec une erreur", r.code === 0 ? "check" : "alert");
    refreshAll(true);
  }
  S.wasRunning = running;
  renderAgents();
}

/* ---------- Historique ---------- */
const simPill = (sim) => sim ? '<span class="pill pill-sky">Simulation</span>' : '<span class="pill pill-sage">Réelle</span>';

function renderSessions() {
  const list = S.sessions;
  $("#sess-count").textContent = list.length ? `${list.length} session${list.length > 1 ? "s" : ""}` : "";
  $("#nav-sess").textContent = list.length || "";
  if (!list.length) {
    $("#sess-list").innerHTML = "";
    $("#detail").innerHTML = empty("clock", "Aucune session pour l'instant", "Lancez une simulation : chaque session apparaîtra ici avec le raisonnement complet des 6 agents.");
    return;
  }
  $("#sess-list").innerHTML = list.map((s) => `<button class="sess ${S.current?.nom === s.nom ? "sel" : ""}" data-n="${esc(s.nom)}">
      <div class="t"><span>${esc(s.quand || s.nom)}</span>${simPill(s.simulation)}</div>
      <div class="s">${esc(s.synthese || "Pas de décision.")}</div>
      <div class="m"><span class="pill">${s.propositions} prop.</span><span class="pill">${s.ordres} ordre${s.ordres > 1 ? "s" : ""}</span>${s.rejets ? `<span class="pill pill-danger">${s.rejets} rejeté${s.rejets > 1 ? "s" : ""}</span>` : ""}</div>
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
  const pv = d.portefeuille || {};
  const order = (o, ok) => {
    const st = !ok ? ["pill-danger", "Rejeté"] : o.statut === "simulé" ? ["pill-sky", "Simulé"] : o.statut === "erreur" ? ["pill-danger", "Erreur"] : ["pill-sage", "Envoyé"];
    const det = [o.qty ? `${o.qty} actions` : null, o.montant ? money(o.montant, 0) : null,
      o.stop_loss ? `stop ${money(o.stop_loss, 2)}` : null, o.take_profit ? `objectif ${money(o.take_profit, 2)}` : null].filter(Boolean).join(" · ");
    const why = !ok ? o.raison_rejet : o.erreur || o.justification;
    return `<div class="order">${actionPill(o.action)}<span class="mono"><b>${esc(o.symbole)}</b></span><span class="muted small">${esc(det)}</span><span class="pill ${st[0]}">${st[1]}</span>${why ? `<div class="why">${esc(why)}</div>` : ""}</div>`;
  };
  const orders = (d.ordres || []).map((o) => order(o, true)).concat((d.rejets || []).map((o) => order(o, false))).join("")
    || `<div class="empty-line">Aucun ordre : l'équipe a choisi de ne rien faire.</div>`;
  const tabs = ["qualite", "equilibre", "sentiment", "contrarien", "critique"];
  if (!tabs.includes(S.tab)) S.tab = "qualite";
  const nameOf = (id) => S.ov?.agents.find((a) => a.id === id)?.nom || id;
  const tok = Object.entries(d.tokens || {}).sort();
  const maxTok = Math.max(1, ...tok.map(([, v]) => v));
  $("#detail").innerHTML = `
    <div class="detail-head"><h3>Session du ${esc(d.quand)}</h3>${simPill(d.simulation)}
      <span class="right">Valeur ${esc(money(pv.valeur_totale, 0))} · cash ${esc(pv.cash_pct)} %</span></div>
    <div class="synth"><div class="who">${icon("gerant")}Décision du gérant${d.modeles?.["gerant:gerant"] ? `<span class="mono muted" style="font-weight:400">${esc(d.modeles["gerant:gerant"])}</span>` : ""}</div>
      <p>${esc(d.decision?.synthese || "—")}</p></div>
    <div><div class="overline sub-h">Ordres</div><div class="list">${orders}</div></div>
    <div>
      <div class="tabs" role="tablist">${tabs.map((t) => `<button class="tab ${S.tab === t ? "on" : ""}" role="tab" aria-selected="${S.tab === t}" data-t="${t}">${esc(nameOf(t).replace("Analyste ", ""))}</button>`).join("")}</div>
      <div class="panel" id="tab-panel"></div>
    </div>
    ${tok.length ? `<div><div class="overline sub-h">Consommation des clés (gratuite)</div><div class="tokens">${tok.map(([k, v]) => `<div class="tok"><span class="mono">${esc(k)}</span><div class="bar"><i class="${k.startsWith("gemini") ? "gemini" : "groq"}" style="width:${(v / maxTok) * 100}%"></i></div><span class="muted">${v.toLocaleString("fr-FR")} tokens · ${d.appels?.[k] || 0} appels</span></div>`).join("")}</div></div>` : ""}`;
  $$(".tab").forEach((b) => (b.onclick = () => { S.tab = b.dataset.t; renderDetail(); }));
  const last = agentLast(S.tab, d);
  const panel = $("#tab-panel");
  if (S.tab === "critique") {
    panel.innerHTML = (last.avis || []).length
      ? `<div>${last.avis.map(verdictRow).join("")}</div>${last.texte ? `<p class="analysis"><b>Risques du portefeuille :</b> ${esc(last.texte)}</p>` : ""}`
      : '<p class="analysis muted">Le critique n\'a pas été sollicité (aucune proposition).</p>';
  } else {
    panel.innerHTML = `
      ${last.tickers?.length ? `<div class="chips" style="margin-top:0">${last.tickers.map((t) => `<span class="pill tk">${esc(t)}</span>`).join("")}</div>${last.raison ? `<p class="small muted" style="margin:0">${esc(last.raison)}</p>` : ""}` : ""}
      <p class="analysis">${esc(last.texte || "Pas de réponse pour cet agent.")}</p>
      ${(last.props || []).map(propCard).join("") || '<p class="analysis muted">Aucune proposition : rien ne méritait d\'agir selon sa stratégie.</p>'}
      ${last.modele ? `<div class="mono muted small">${esc(last.modele)}</div>` : ""}`;
  }
}

/* ---------- Navigation : élément actif selon la section visible ---------- */
function setActive(id) {
  $$(".nav-item, .tabbar a").forEach((a) => a.classList.toggle("active", a.dataset.s === id));
}
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
    renderHeader(ov); renderKpis(ov); renderChart(ov.historique); renderPositions(ov);
    if (sessions.length && (force || !S.latest || S.latest.nom !== sessions[0].nom)) {
      S.latest = await api(`/api/session?nom=${encodeURIComponent(sessions[0].nom)}`);
      if (force || !S.current) S.current = S.latest;
    }
    renderAgents(); renderSessions(); renderDetail();
  } catch (e) {
    toast("Impossible de joindre le serveur du tableau de bord", "alert");
  }
}

async function pollLive() {
  try {
    S.live = await api("/api/state");
    renderLive();
  } catch { /* serveur arrêté */ }
  if (!STATIC) setTimeout(pollLive, S.wasRunning ? 1200 : 3000);
}

async function run(mode) {
  const r = await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode }) });
  if (!r.ok) return toast(r.erreur || "Lancement impossible", "alert");
  toast(mode === "reel" ? "Session réelle lancée" : "Simulation lancée : l'équipe se met au travail", "spark");
  S.wasRunning = true;
  $("#console").textContent = "Démarrage…";
}

$("#btn-sim").onclick = () => {
  if (STATIC) return S.ov?.actions_url && window.open(S.ov.actions_url, "_blank", "noopener");
  run("simulation");
};
$("#btn-real").onclick = () => {
  $("#modal-text").textContent = S.ov?.paper
    ? "Les agents vont envoyer de vrais ordres sur votre compte Alpaca paper (argent virtuel). La session ne tourne que si la bourse de New York est ouverte."
    : "Attention : compte en argent réel. Les agents vont envoyer de vrais ordres avec votre argent.";
  $("#modal").classList.add("open");
  $("#modal-no").focus();
};
const closeModal = () => $("#modal").classList.remove("open");
$("#modal-no").onclick = closeModal;
$("#modal-yes").onclick = () => { closeModal(); run("reel"); };
$("#scrim").onclick = closeDrawer;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeDrawer(); closeModal(); } });
let rz;
window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => S.ov && renderChart(S.ov.historique), 150); });

applyThemeButton();
refreshAll();
pollLive();
setInterval(() => { if (!S.wasRunning) refreshAll(); }, STATIC ? 120000 : 30000);
