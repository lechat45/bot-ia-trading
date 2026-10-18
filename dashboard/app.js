"use strict";

/* ---------- Utilitaires ---------- */
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v) => (v === null || v === undefined || v === "" || isNaN(+v) ? null : +v);
const money = (v, d = 0) => num(v) === null ? "—" : `${new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: d, maximumFractionDigits: d }).format(v)} $`;
const pct = (v, d = 2) => num(v) === null ? "—" : `${v > 0 ? "+" : ""}${(+v).toFixed(d).replace(".", ",")} %`;
const tone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "muted");
// En ligne (GitHub Pages / Cloudflare), pas de serveur : on lit les fichiers générés par build_site.py.
const STATIC = !!window.STATIC_SITE;
function staticPath(p) {
  const u = new URL(p, location.href);
  if (u.pathname.endsWith("/api/session")) return `data/sessions/${encodeURIComponent(u.searchParams.get("nom"))}.json`;
  return `data/${u.pathname.split("/").pop()}.json`;
}
const api = (p, opt) => fetch(STATIC ? `${staticPath(p)}?v=${Date.now()}` : p, opt).then((r) => r.json());

const svg = (d, extra = "") =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ${extra}>${d}</svg>`;
const ICONS = {
  qualite: svg('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/><path d="M8 11h6M11 8v6"/>'),
  equilibre: svg('<path d="M12 3v18M5 21h14"/><path d="m5 8-3 6a3 3 0 0 0 6 0zM19 8l-3 6a3 3 0 0 0 6 0z"/><path d="M5 8h14"/>'),
  sentiment: svg('<path d="M12 22c4 0 7-3 7-7 0-3-2-5.5-3.5-7-.4 2-1.5 3-2.5 3 0-3-1.5-6-4-8 0 4-4 6.5-4 12 0 4 3 7 7 7z"/>'),
  contrarien: svg('<path d="M7 7h11l-3-3M17 17H6l3 3"/>'),
  critique: svg('<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>'),
  gerant: svg('<path d="m3 8 4 3 5-6 5 6 4-3-2 11H5z"/><path d="M5 19h14"/>'),
};
const META = {
  qualite: { c: "#34d399", tag: "Qualité · chiffres & patience",
    desc: "Épluche les chiffres (croissance, marges, dette, valorisation). Cherche des entreprises solides à prix raisonnable, ne panique pas quand le prix baisse tant que la thèse tient. Inspiré de l'agent « Claude » d'Aywen." },
  equilibre: { c: "#60a5fa", tag: "Équilibre · diversification",
    desc: "Construit un portefeuille diversifié sur des secteurs variés pour limiter le risque, en évitant de tout analyser sans jamais agir. Inspiré de l'agent « ChatGPT » d'Aywen." },
  sentiment: { c: "#fbbf24", tag: "Sentiment · momentum",
    desc: "Mise sur l'humeur du marché : actualité chaude, tendances Reddit, actions en forte dynamique. Accepte plus de risque, dans les limites du code. Inspiré de l'agent « Grok », vainqueur de l'expérience d'Aywen." },
  contrarien: { c: "#fb7185", tag: "Contrarien · rebonds",
    desc: "Cherche les actions qui ont beaucoup chuté, à condition de prouver que le marché a surréagi, avec un catalyseur daté. A retenu les leçons des erreurs de l'agent « Mistral »." },
  critique: { c: "#a78bfa", tag: "Avocat du diable",
    desc: "Contrôle chaque proposition : faits datés, catalyseur dans l'horizon, stop hors du bruit, paris corrélés, comportements interdits. Verdict : ok, réserve ou rejet." },
  gerant: { c: "#22d3ee", tag: "Décision finale",
    desc: "Synthétise les 4 analystes et l'avis du critique, vérifie avec Google Search, surveille l'ensemble du portefeuille et décide des ordres. Ses notes sont le journal de bord de l'équipe." },
};
const STEPS = [
  ["portefeuille", "Lecture du portefeuille"], ["marche", "Screener & actualités"],
  ["selection", "Sélection des titres"], ["donnees", "Collecte des données"],
  ["theses", "Rédaction des thèses"], ["critique", "Contrôle du critique"],
  ["gerant", "Décision du gérant"], ["ordres", "Garde-fous & ordres"],
];
const STAGE_LABEL = { selection: "sélectionne ses titres", theses: "rédige ses thèses", critique: "contrôle les propositions", gerant: "prend la décision" };

const S = { ov: null, sessions: [], latest: null, current: null, notes: {}, live: null, wasRunning: false, tab: "qualite" };

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast.h);
  toast.h = setTimeout(() => t.classList.remove("show"), 3200);
}

/* ---------- En-tête ---------- */
function relTime(iso) {
  const ms = new Date(iso) - Date.now();
  if (isNaN(ms)) return "";
  const h = Math.floor(ms / 3.6e6), m = Math.round((ms % 3.6e6) / 6e4);
  return h >= 24 ? new Date(iso).toLocaleString("fr-FR", { weekday: "short", hour: "2-digit", minute: "2-digit" })
    : h > 0 ? `dans ${h} h ${String(m).padStart(2, "0")}` : `dans ${m} min`;
}

function renderHeader(o) {
  const b = $("#mode-badge");
  if (o.demo) { b.className = "badge demo"; b.textContent = "● Démo"; }
  else if (o.paper) { b.className = "badge paper"; b.textContent = "● Paper trading"; }
  else { b.className = "badge live"; b.textContent = "● Argent réel"; }
  const h = o.horloge || {};
  const open = !!h.is_open;
  $("#market").innerHTML = `<i class="dot ${open ? "on" : ""}"></i><span>${open
    ? `Bourse de New York ouverte · ferme ${esc(relTime(h.next_close))}`
    : `Bourse fermée · ouvre ${esc(relTime(h.next_open))}`}</span>`;
  $("#btn-sim span").textContent = STATIC ? "Lancer sur GitHub" : o.demo ? "Lancer une démo" : "Lancer une simulation";
  $("#btn-sim").hidden = STATIC && !o.actions_url;
  $("#btn-real").hidden = !!o.demo || STATIC;
  const ban = $("#banner");
  if (STATIC && !o.erreur) {
    ban.className = "banner"; ban.hidden = false;
    ban.style.borderColor = "rgba(34,211,238,.3)"; ban.style.background = "rgba(34,211,238,.06)"; ban.style.color = "#a5f3fc";
    ban.textContent = `Version en ligne : mise à jour automatiquement après chaque session (dernière mise à jour ${new Date(o.genere_le).toLocaleString("fr-FR", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}).`;
  } else if (o.erreur) {
    ban.className = "banner err"; ban.hidden = false;
    ban.textContent = `Alpaca ne répond pas : ${o.erreur}`;
  } else if (o.demo) {
    ban.className = "banner"; ban.hidden = false;
    ban.textContent = "Mode démo : aucune clé Alpaca dans le fichier .env, les chiffres affichés sont factices. Remplis .env puis relance « python dashboard.py ».";
  } else ban.hidden = true;
}

/* ---------- KPI ---------- */
function renderKpis(o) {
  const a = o.compte;
  if (!a) return;
  document.querySelectorAll(".kpi .skeleton").forEach((e) => e.classList.remove("skeleton"));
  const day = a.equity - a.last_equity;
  $("#k-equity").textContent = money(a.equity, 2);
  $("#k-day").innerHTML = `<span class="${tone(day)}">${day >= 0 ? "▲" : "▼"} ${money(Math.abs(day), 2)} (${pct(a.last_equity ? (day / a.last_equity) * 100 : 0)})</span> <span class="muted">aujourd'hui</span>`;
  const h = o.historique || [];
  const first = h.find((p) => p.v > 0);
  const perf = first ? (a.equity / first.v - 1) * 100 : 0;
  $("#k-perf").innerHTML = `<span class="${tone(perf)}">${pct(perf)}</span>`;
  $("#k-perf-sub").textContent = first ? `${money(a.equity - first.v, 0)} depuis le ${new Date(first.t * 1000).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}` : "";
  const cashPct = a.equity ? (a.cash / a.equity) * 100 : 0;
  $("#k-cash").textContent = money(a.cash, 0);
  $("#k-cash-bar").style.width = `${Math.max(0, Math.min(100, cashPct))}%`;
  const pos = o.positions || [];
  const pl = pos.reduce((s, p) => s + p.pl, 0);
  $("#k-pos").textContent = `${pos.length}`;
  $("#k-pos-sub").innerHTML = pos.length ? `Latent : <span class="${tone(pl)}">${money(pl, 0)}</span> · max ${o.limites.max_positions}` : `max ${o.limites.max_positions} · ${cashPct.toFixed(0)} % en cash`;
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
    box.innerHTML = `<div class="empty">${svg('<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/>')}<div>Pas encore d'historique</div><div class="muted" style="font-size:12px">La courbe apparaîtra après quelques jours de trading.</div></div>`;
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
  const up = vs[vs.length - 1] >= vs[0];
  const col = up ? "#34d399" : "#fb7185";
  let grid = "";
  for (let k = 0; k <= 4; k++) {
    const v = lo + ((hi - lo) * k) / 4, yy = y(v);
    grid += `<line x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}" stroke="rgba(255,255,255,.06)"/>
      <text x="${L - 10}" y="${yy + 4}" text-anchor="end" fill="#5b6178" font-size="11">${esc(money(v, 0))}</text>`;
  }
  const n = Math.min(5, points.length);
  for (let k = 0; k < n; k++) {
    const i = Math.round((k * (points.length - 1)) / (n - 1 || 1));
    const d = new Date(points[i].t * 1000).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
    grid += `<text x="${x(i)}" y="${H - 6}" text-anchor="${k === 0 ? "start" : k === n - 1 ? "end" : "middle"}" fill="#5b6178" font-size="11">${esc(d)}</text>`;
  }
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <defs>
      <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${col}" stop-opacity=".32"/><stop offset="1" stop-color="${col}" stop-opacity="0"/>
      </linearGradient>
      <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="${col}"/>
      </linearGradient>
      <filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    </defs>
    ${grid}
    <path d="${line} L${pts[pts.length - 1][0]},${H - B} L${pts[0][0]},${H - B} Z" fill="url(#area)"/>
    <path d="${line}" fill="none" stroke="url(#stroke)" stroke-width="2.5" filter="url(#glow)"/>
    <circle cx="${pts[pts.length - 1][0]}" cy="${pts[pts.length - 1][1]}" r="4.5" fill="${col}" stroke="#06070c" stroke-width="2"/>
    <g id="hover" opacity="0"><line id="hl" y1="${T}" y2="${H - B}" stroke="rgba(255,255,255,.25)" stroke-dasharray="3 4"/>
      <circle id="hc" r="5" fill="#fff" stroke="${col}" stroke-width="3"/></g>
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
    tip.innerHTML = `<b>${esc(money(points[i].v, 2))}</b> <span class="${tone(chg)}">${esc(pct(chg))}</span><br><span class="muted">${esc(new Date(points[i].t * 1000).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }))}</span>`;
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

function renderAgents() {
  const o = S.ov;
  if (!o) return;
  const etat = S.live?.etat || {}, running = S.live?.runner?.running || etat.running;
  $("#agents").innerHTML = o.agents.map((a) => {
    const m = META[a.id] || { c: "#8b5cf6", tag: "" };
    const last = agentLast(a.id);
    const thinking = running && etat.agent === a.id;
    const status = thinking
      ? `<span class="typing"><i></i><i></i><i></i></span><span style="color:${m.c}">${esc(a.nom.split(" ").pop())} ${esc(STAGE_LABEL[etat.etape] || "réfléchit")}…</span>`
      : !a.cle_configuree ? `<span class="down">● Clé ${esc(a.provider)} n°${a.cle} manquante (relais par une autre clé)</span>`
      : `<i class="dot"></i> En veille`;
    const tickers = (last.tickers || []).map((t) => `<span class="chip tk">${esc(t)}</span>`).join("");
    const nProps = (last.props || []).length;
    const extra = a.id === "critique" && last.avis?.length
      ? `<span class="chip">${last.avis.length} avis</span>`
      : nProps ? `<span class="chip">${nProps} ${a.id === "gerant" ? "ordre" : "proposition"}${nProps > 1 ? "s" : ""}</span>` : "";
    return `<article class="card agent ${thinking ? "thinking" : ""}" style="--c:${m.c}" data-id="${esc(a.id)}" tabindex="0">
      <div class="agent-top">
        <div class="avatar">${ICONS[a.id] || ""}</div>
        <div><h3>${esc(a.nom)}</h3><div class="tag">${esc(m.tag)}</div></div>
      </div>
      <div class="chips">
        <span class="chip ${esc(a.provider)}">${a.provider === "gemini" ? "Gemini" : "Groq"} · clé ${a.cle}</span>
        ${tickers}${extra}
      </div>
      <div class="excerpt">${esc(last.texte || "Pas encore de session : lance une simulation pour voir son raisonnement.")}</div>
      <div class="agent-status">${status}</div>
    </article>`;
  }).join("");
  document.querySelectorAll(".agent").forEach((el) => {
    el.onclick = () => openDrawer(el.dataset.id);
    el.onkeydown = (e) => { if (e.key === "Enter") openDrawer(el.dataset.id); };
  });
}

function propCard(p) {
  const act = String(p.action || "").toLowerCase();
  const c = act.startsWith("vend") || act.startsWith("all") ? "down" : act === "ajuster_stop" ? "muted" : "up";
  const conf = p.confiance ? `<span class="chip">confiance ${esc(p.confiance)}</span>` : "";
  const rows = [
    ["Poids", p.poids_pct != null ? `${p.poids_pct} %` : null], ["Stop loss", p.stop_loss], ["Objectif", p.take_profit],
    ["Horizon", p.horizon_jours ? `${p.horizon_jours} jours` : null], ["Arguments", p.arguments || p.justification],
    ["Risques", p.risques], ["Invalidation", p.invalidation], ["Source", p.source],
  ].filter(([, v]) => v !== null && v !== undefined && v !== "");
  return `<div class="prop"><div class="prop-h"><span class="pill ${c}">${esc(p.action)}</span><span class="s">${esc(p.symbole)}</span>${conf}</div>
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>`;
}

function openDrawer(id) {
  const a = S.ov.agents.find((x) => x.id === id);
  const m = META[id] || {};
  const last = agentLast(id);
  const notes = S.notes[id];
  const avis = (last.avis || []).map((v) => `<div class="verdict"><b class="v-${esc(v.verdict)}">${esc(v.verdict)}</b><span class="mono muted">${esc(v.id)}</span><span>${esc(v.raison)}</span></div>`).join("");
  $("#drawer").innerHTML = `<div class="drawer-head" style="--c:${m.c}">
      <div class="avatar">${ICONS[id] || ""}</div>
      <div><h3>${esc(a.nom)}</h3><div class="chips" style="margin-top:6px"><span class="chip ${esc(a.provider)}">${a.provider === "gemini" ? "Gemini" : "Groq"} · clé ${a.cle}</span>${last.modele ? `<span class="chip">${esc(last.modele)}</span>` : ""}</div></div>
      <button class="btn x" id="drawer-x" aria-label="Fermer">✕</button>
    </div>
    <div class="drawer-body">
      <div><div class="sub-h">Stratégie</div><p class="strategy">${esc(m.desc)}</p></div>
      ${last.tickers?.length ? `<div><div class="sub-h">Titres choisis</div><div class="chips">${last.tickers.map((t) => `<span class="chip tk">${esc(t)}</span>`).join("")}</div>${last.raison ? `<p class="muted">${esc(last.raison)}</p>` : ""}</div>` : ""}
      <div><div class="sub-h">Dernière réflexion</div><p class="strategy">${esc(last.texte || "—")}</p></div>
      ${avis ? `<div><div class="sub-h">Verdicts</div>${avis}</div>` : ""}
      ${(last.props || []).length ? `<div class="panel"><div class="sub-h">${id === "gerant" ? "Ordres décidés" : "Propositions"}</div>${last.props.map(propCard).join("")}</div>` : ""}
      <div><div class="sub-h">Notes (sa mémoire entre deux sessions)</div><div class="notes">${esc(notes || "Aucune note pour l'instant. Les notes sont écrites après une session réelle (pas en simulation).")}</div></div>
    </div>`;
  $("#drawer").classList.add("open");
  $("#scrim").classList.add("open");
  $("#drawer-x").onclick = closeDrawer;
}
function closeDrawer() { $("#drawer").classList.remove("open"); $("#scrim").classList.remove("open"); }

/* ---------- Positions ---------- */
function renderPositions(o) {
  const pos = o.positions || [];
  if (!pos.length) {
    $("#positions").innerHTML = `<div class="empty">${svg('<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>')}<div>Aucune position</div><div class="muted" style="font-size:12px">Le portefeuille est 100 % en liquidités.</div></div>`;
    return;
  }
  const eq = o.compte?.equity || 1;
  $("#positions").innerHTML = `<table><thead><tr><th>Titre</th><th>Quantité</th><th>Prix d'achat</th><th>Prix</th><th>Valeur</th><th>Poids</th><th>Plus/moins-value</th><th>Stop ← prix → objectif</th></tr></thead><tbody>
    ${pos.map((p) => {
      let range = '<span class="muted">pas de sortie programmée</span>';
      if (p.stop && p.tp && p.tp > p.stop) {
        const f = (v) => Math.max(0, Math.min(100, ((v - p.stop) / (p.tp - p.stop)) * 100));
        range = `<div class="range"><i class="en" style="left:${f(p.prix_achat)}%"></i><i class="mk" style="left:${f(p.prix)}%"></i></div>
          <div class="range-labels"><span>${esc(money(p.stop, 2))}</span><span>${esc(money(p.tp, 2))}</span></div>`;
      } else if (p.stop) range = `<span class="muted">stop ${esc(money(p.stop, 2))}</span>`;
      return `<tr><td><div class="sym"><span class="logo-s">${esc(p.symbole.slice(0, 4))}</span>${esc(p.symbole)}</div></td>
        <td>${esc(p.qty)}</td><td>${esc(money(p.prix_achat, 2))}</td><td>${esc(money(p.prix, 2))}</td>
        <td>${esc(money(p.valeur, 0))}</td><td>${((p.valeur / eq) * 100).toFixed(1).replace(".", ",")} %</td>
        <td><span class="pill ${tone(p.pl)}">${esc(money(p.pl, 0))} · ${esc(pct(p.pl_pct, 1))}</span></td><td>${range}</td></tr>`;
    }).join("")}</tbody></table>`;
}

/* ---------- Direct ---------- */
function renderLive() {
  const L = S.live;
  if (!L) return;
  const r = L.runner, etat = L.etat || {};
  const running = r.running || (etat.running && Date.now() - new Date(etat.maj) < 10 * 60e3);
  const idx = STEPS.findIndex(([k]) => k === etat.etape);
  const finished = etat.etape === "termine";
  $("#stepper").innerHTML = STEPS.map(([k, label], i) => {
    let c = "", ic = i + 1;
    if (running && i < idx) { c = "done"; ic = "✓"; }
    else if (running && i === idx) { c = "active"; ic = ""; }
    else if (!running && finished && (r.code === 0 || STATIC)) { c = "done"; ic = "✓"; }
    const who = running && i === idx && etat.agent ? `<span class="who">${esc(S.ov?.agents.find((a) => a.id === etat.agent)?.nom || etat.agent)}</span>` : "";
    return `<li class="step ${c}"><span class="ic">${ic}</span>${esc(label)}${who}</li>`;
  }).join("");
  if (STATIC) {
    $("#console").textContent = "Les sessions tournent automatiquement sur GitHub Actions, du lundi au vendredi vers 17 h 05 et 20 h 35 (heure de Paris). Le détail de chaque session est dans l'historique ci-dessous.";
    $("#live-status").textContent = etat.maj ? `Dernière : ${new Date(etat.maj).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}` : "En veille";
    return renderAgents();
  }
  const st = $("#live-status");
  st.innerHTML = running ? `<i class="dot run"></i> ${r.mode === "reel" ? "Session réelle" : r.mode === "demo" ? "Démo" : "Simulation"} en cours`
    : r.code === 0 ? "Terminée ✓" : r.code ? `Erreur (code ${r.code})` : "En veille";
  if (r.logs.length) {
    const con = $("#console");
    const stick = con.scrollTop + con.clientHeight >= con.scrollHeight - 30;
    con.innerHTML = r.logs.map((l) => {
      const c = /erreur|error|échec|traceback/i.test(l) ? "err" : /terminé|simulé|envoyé|✓/i.test(l) ? "ok" : "";
      return `<span class="${c}">${esc(l)}</span>`;
    }).join("\n");
    if (stick) con.scrollTop = con.scrollHeight;
  }
  $("#btn-sim").disabled = running;
  $("#btn-real").disabled = running;
  if (S.wasRunning && !running) {
    toast(r.code === 0 ? "Session terminée ✓" : "La session s'est arrêtée avec une erreur");
    refreshAll(true);
  }
  S.wasRunning = running;
  renderAgents();
}

/* ---------- Historique ---------- */
function renderSessions() {
  const list = S.sessions;
  $("#sess-count").textContent = list.length ? `${list.length} session${list.length > 1 ? "s" : ""}` : "";
  if (!list.length) {
    $("#sess-list").innerHTML = "";
    $("#detail").innerHTML = `<div class="empty">${svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>')}<div>Aucune session pour l'instant</div><div class="muted" style="font-size:12px">Lance une simulation : chaque session apparaîtra ici avec le raisonnement complet des 6 agents.</div></div>`;
    return;
  }
  $("#sess-list").innerHTML = list.map((s) => `<button class="sess ${S.current?.nom === s.nom ? "sel" : ""}" data-n="${esc(s.nom)}">
      <div class="t"><span>${esc(s.quand || s.nom)}</span>${s.simulation ? '<span class="st sim">simulation</span>' : '<span class="st ok">réelle</span>'}</div>
      <div class="s">${esc(s.synthese || "Pas de décision.")}</div>
      <div class="m"><span class="chip">${s.propositions} prop.</span><span class="chip">${s.ordres} ordre${s.ordres > 1 ? "s" : ""}</span>${s.rejets ? `<span class="chip off">${s.rejets} rejeté${s.rejets > 1 ? "s" : ""}</span>` : ""}</div>
    </button>`).join("");
  document.querySelectorAll(".sess").forEach((b) => (b.onclick = () => loadSession(b.dataset.n)));
}

async function loadSession(nom) {
  const d = await api(`/api/session?nom=${encodeURIComponent(nom)}`);
  if (d.erreur) return toast(d.erreur);
  S.current = d;
  renderSessions();
  renderDetail();
}

function renderDetail() {
  const d = S.current;
  if (!d) return;
  const pv = d.portefeuille || {};
  const order = (o, ok) => {
    const st = !ok ? ["ko", "rejeté"] : o.statut === "simulé" ? ["sim", "simulé"] : o.statut === "erreur" ? ["ko", "erreur"] : ["ok", "envoyé"];
    const det = [o.qty ? `${o.qty} actions` : null, o.montant ? money(o.montant, 0) : null,
      o.stop_loss ? `stop ${money(o.stop_loss, 2)}` : null, o.take_profit ? `objectif ${money(o.take_profit, 2)}` : null].filter(Boolean).join(" · ");
    const why = !ok ? o.raison_rejet : o.erreur || o.justification;
    return `<div class="order"><span class="act">${esc(String(o.action || "").replace("_", " "))}</span><span class="mono"><b>${esc(o.symbole)}</b></span><span class="muted">${esc(det)}</span><span class="st ${st[0]}">${st[1]}</span>${why ? `<div class="why">${esc(why)}</div>` : ""}</div>`;
  };
  const orders = (d.ordres || []).map((o) => order(o, true)).concat((d.rejets || []).map((o) => order(o, false))).join("")
    || '<div class="muted">Aucun ordre : l\'équipe a choisi de ne rien faire.</div>';
  const tabs = ["qualite", "equilibre", "sentiment", "contrarien", "critique"];
  if (!tabs.includes(S.tab)) S.tab = "qualite";
  const nameOf = (id) => S.ov?.agents.find((a) => a.id === id)?.nom || id;
  const tok = Object.entries(d.tokens || {}).sort();
  const maxTok = Math.max(1, ...tok.map(([, v]) => v));
  $("#detail").innerHTML = `
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <h3 style="font-size:16px">Session du ${esc(d.quand)}</h3>
      ${d.simulation ? '<span class="st sim inline">simulation</span>' : '<span class="st ok inline">réelle</span>'}
      <span class="muted" style="margin-left:auto">Valeur ${esc(money(pv.valeur_totale, 0))} · cash ${esc(pv.cash_pct)} %</span>
    </div>
    <div class="synth"><div class="who">${ICONS.gerant.replace("<svg", '<svg width="15" height="15"')} Décision du gérant ${d.modeles?.["gerant:gerant"] ? `· <span class="mono" style="font-weight:400">${esc(d.modeles["gerant:gerant"])}</span>` : ""}</div>
      <p>${esc(d.decision?.synthese || "—")}</p></div>
    <div><div class="sub-h">Ordres</div><div class="orders">${orders}</div></div>
    <div>
      <div class="tabs">${tabs.map((t) => `<button class="tab ${S.tab === t ? "on" : ""}" data-t="${t}" style="--c:${META[t].c}"><span class="d"></span>${esc(nameOf(t).replace("Analyste ", ""))}</button>`).join("")}</div>
      <div class="panel" style="margin-top:14px" id="tab-panel"></div>
    </div>
    ${tok.length ? `<div><div class="sub-h">Consommation des clés (gratuite)</div><div class="tokens">${tok.map(([k, v]) => `<div class="tok"><span class="mono">${esc(k)}</span><div class="bar"><i style="width:${(v / maxTok) * 100}%;background:${k.startsWith("gemini") ? "var(--gemini)" : "var(--groq)"}"></i></div><span class="muted">${v.toLocaleString("fr-FR")} tokens · ${d.appels?.[k] || 0} appels</span></div>`).join("")}</div></div>` : ""}`;
  document.querySelectorAll(".tab").forEach((b) => (b.onclick = () => { S.tab = b.dataset.t; renderDetail(); }));
  const last = agentLast(S.tab, d);
  const panel = $("#tab-panel");
  if (S.tab === "critique") {
    panel.innerHTML = (last.avis || []).length
      ? `<div>${last.avis.map((v) => `<div class="verdict"><b class="v-${esc(v.verdict)}">${esc(v.verdict)}</b><span class="mono muted">${esc(v.id)}</span><span>${esc(v.raison)}</span></div>`).join("")}</div>
         ${last.texte ? `<p class="analysis"><b>Risques du portefeuille :</b> ${esc(last.texte)}</p>` : ""}`
      : '<div class="muted">Le critique n\'a pas été sollicité (aucune proposition).</div>';
  } else {
    panel.innerHTML = `
      ${last.tickers?.length ? `<div class="chips" style="margin:0">${last.tickers.map((t) => `<span class="chip tk">${esc(t)}</span>`).join("")}<span class="muted" style="font-size:12px;align-self:center">${esc(last.raison || "")}</span></div>` : ""}
      <p class="analysis">${esc(last.texte || "Pas de réponse pour cet agent.")}</p>
      ${(last.props || []).map(propCard).join("") || '<div class="muted">Aucune proposition : rien ne méritait d\'agir selon sa stratégie.</div>'}
      ${last.modele ? `<div class="muted mono" style="font-size:11.5px">${esc(last.modele)}</div>` : ""}`;
  }
}

/* ---------- Boucles ---------- */
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
    toast("Impossible de joindre le serveur du tableau de bord");
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
  if (!r.ok) return toast(r.erreur || "Lancement impossible");
  toast(mode === "reel" ? "Session réelle lancée" : "Simulation lancée : l'équipe se met au travail");
  S.wasRunning = true;
  $("#console").textContent = "Démarrage…";
}

$("#btn-sim").onclick = () => {
  if (STATIC) return S.ov?.actions_url && window.open(S.ov.actions_url, "_blank", "noopener");
  run("simulation");
};
$("#btn-real").onclick = () => {
  const paper = S.ov?.paper;
  $("#modal-text").textContent = paper
    ? "Les agents vont envoyer de vrais ordres sur ton compte Alpaca PAPER (argent virtuel). La session ne tourne que si la bourse de New York est ouverte."
    : "ATTENTION : compte en ARGENT RÉEL. Les agents vont envoyer de vrais ordres avec ton argent.";
  $("#modal").classList.add("open");
};
$("#modal-no").onclick = () => $("#modal").classList.remove("open");
$("#modal-yes").onclick = () => { $("#modal").classList.remove("open"); run("reel"); };
$("#scrim").onclick = closeDrawer;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeDrawer(); $("#modal").classList.remove("open"); } });
let rz;
window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => S.ov && renderChart(S.ov.historique), 150); });

refreshAll();
pollLive();
setInterval(() => { if (!S.wasRunning) refreshAll(); }, STATIC ? 120000 : 30000);
