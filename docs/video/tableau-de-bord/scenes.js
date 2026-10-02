/* Le Sentier · étape 5 — « Tour du propriétaire » : visite guidée du tableau de bord.
 * Moteur : ../engine/engine.js. Découpage et narration : script.json.
 * Captures réelles (../shots/) du workspace fictif de Camille (mardi 29 septembre 2026).
 * Le tableau de bord est en français seulement : en EN on garde les captures, on traduit les légendes. */
"use strict";
(() => {
const STR = {
  fr: {
    k1: "00 · LANCER", h1: "Une commande.",
    opts: [["--port 9000", "autre port"], ["--no-open", "sans ouvrir le navigateur"], ["--memory", "index en mémoire"], ["--rebuild", "repart d'un index vide"]],
    chips: ["127.0.0.1 · lecture seule", "construit depuis vos fichiers Markdown", "à jour en 30 s au plus"],
    dash: "Tableau de bord (interface en français)",
    kT: "LE TOUR", hT: "Une vue, une question.", ofN: "vue",
    today: { card: ["Aujourd'hui", "Je cours, j'allège ou je me repose ?"], caps: ["Verdict et raison", "Bilan sur votre référence", "Programme et météo"] },
    week: { card: ["Semaine", "Qu'est-ce qui était prévu, qu'est-ce qui a été fait ?"], caps: ["Seuil annulé · côtes → jeudi", "Garde-fou r7"] },
    form: { cards: [["Forme & charge", "Où en est ma condition, ma fatigue, ma forme ?"], ["Trail Shape", "Ma préparation couvre-t-elle ce que la course va exiger ?"]], caps: ["Condition · fatigue · forme", "Score de forme trail"] },
    session: { card: ["Séances", "Qu'est-ce que j'ai fait, et comment ça s'est passé ?"], caps: ["Dimanche 27 : 18,2 km · 820 m D+", "Montées détectées", "Splits au kilomètre"] },
    decisions: { card: ["Décisions", "Pourquoi cette séance a-t-elle changé ?"], caps: ["Le journal des décisions", "Avant / après · données · sources"] },
    kM: "ET LE RESTE", hM: "Il y en a d'autres.",
    more: [["Santé", "Comment mon corps encaisse-t-il ?"], ["Nutrition", "Mon poids et mes apports suivent-ils ?"], ["Rapports", "Qu'est-ce que le coach en a conclu ?"], ["Performance", "Quel est mon niveau, que puis-je viser ?"], ["Calendrier", "Suis-je régulier ?"]],
    kP: "PARTOUT", hP: "Dans la poche aussi.",
    desk: "Ordinateur", ph: "Téléphone",
    flows: ["tunnel SSH ou reverse proxy + SSO", "Docker : workspace monté en lecture seule"],
  },
  en: {
    k1: "00 · LAUNCH", h1: "One command.",
    opts: [["--port 9000", "another port"], ["--no-open", "don't open the browser"], ["--memory", "in-memory index"], ["--rebuild", "start from an empty index"]],
    chips: ["127.0.0.1 · read-only", "built from your Markdown files", "up to date within 30 s"],
    dash: "Dashboard (French UI)",
    kT: "THE TOUR", hT: "One view, one question.", ofN: "view",
    today: { card: ["Today", "Do I run, ease off or rest?"], caps: ["Verdict and reason", "Check against your baseline", "Plan and weather"] },
    week: { card: ["Week", "What was planned, what was done?"], caps: ["Threshold cancelled · hills → Thursday", "Guardrail r7"] },
    form: { cards: [["Fitness & load", "Where do my condition, fatigue and form stand?"], ["Trail Shape", "Does my recent training cover what the race will demand?"]], caps: ["Condition · fatigue · form", "Trail-specific readiness score"] },
    session: { card: ["Sessions", "What did I do, and how did it go?"], caps: ["Sunday 27: 18.2 km · 820 m climbing", "Detected climbs", "Kilometre splits"] },
    decisions: { card: ["Decisions", "Why did this session change?"], caps: ["The decision journal", "Before / after · data · sources"] },
    kM: "AND THE REST", hM: "There's more.",
    more: [["Health", "How is my body coping?"], ["Nutrition", "Are my weight and intake on track?"], ["Reports", "What did the coach conclude?"], ["Performance", "What is my level, what can I aim for?"], ["Calendar", "Am I consistent?"]],
    kP: "ANYWHERE", hP: "In your pocket too.",
    desk: "Desktop", ph: "Phone",
    flows: ["SSH tunnel or reverse proxy + SSO", "Docker: workspace mounted read-only"],
  },
};

/* cadre commun du tour : capture 860 × 470 à gauche, fiche de la vue à droite */
const FX = 80, FY = 160, FW = 860, FH = 470, ASP = FW / (FH - 30);
const head = (k, h, t) => { kicker(k, seg(t, 0, 0.4)); headline(h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8)); };

/* items : [{name, box, padW, padT, a, hl: [boîtes], cap, card}] — a = début local ; fondu enchaîné + zoom lent */
function tour(t, d, items, cards, ka, nView) {
  let act = 0;
  items.forEach((it, i) => { if (t >= it.a) act = i; });
  let map = null;
  items.forEach((it, i) => {
    if (t < it.a && i > 0) return;
    const s = it.a, nxt = items[i + 1] ? items[i + 1].a : d;
    const al = (i === 0 ? ka : seg(t, s, s + 0.6));
    const z = inOut(seg(t, s, nxt + 0.4));
    const wide = cropTo(it.name, it.box, ASP, it.padW), tight = cropTo(it.name, it.box, ASP, it.padT);
    const cr = lerpRect(wide, tight, z);
    if (cr[0] < 240) { const dx = Math.min(240 - cr[0], 1440 - cr[2] - cr[0]); cr[0] += Math.max(dx, 0); }  // jamais la barre latérale
    const m = shot(it.name, FX, FY, FW, FH, { crop: cr, alpha: al });
    if (i === act) map = m;
  });
  const it = items[act], s = it.a;
  // surlignage + légende de l'élément courant (une seule légende à l'écran)
  if (map && it.hl) {
    const kh = seg(t, s + 0.9, s + 1.5);
    it.hl.forEach(b => { const r = map(b); if (r) highlight(r[0], r[1], r[2], r[3], kh); });
    const r = map(it.hl[0]);
    if (r && it.cap) {
      const ty = clamp(r[1] - 6, FY + 60, FY + FH - 40), tx = clamp(r[0] + r[2] / 2, FX + 140, FX + FW - 140);
      const cy = ty < FY + 100 ? ty + 70 : ty - 34;
      callout(it.cap, clamp(tx + 40, FX + 150, FX + FW - 150), clamp(cy, FY + 50, FY + FH - 24), tx, ty, kh, {});
    }
  }
  // fiche de la vue
  const drawCard = (c, a, idx) => {
    if (a <= 0) return;
    const x = 980, y = 200 + (1 - outCubic(a)) * 10;
    panel(x, y, 220, 270, { r: 18, alpha: a, fill: C.panel2, shadow: true });
    text(`${S.ofN} ${idx}/${nView}`, x + 20, y + 34, { size: 12, font: MONO, color: C.faint, alpha: a });
    text(c[0], x + 20, y + 78, { size: 24, weight: 800, font: SORA, color: C.accent, alpha: a, spacing: "-0.5px" });
    para(c[1], x + 20, y + 118, 180, { size: 17, weight: 500, alpha: a, lh: 25 });
  };
  const cur = cards[act], prev = act > 0 ? cards[act - 1] : null;
  if (prev && prev !== cur) { drawCard(prev, 1 - seg(t, s, s + 0.4), idxOf(prev)); drawCard(cur, seg(t, s + 0.2, s + 0.7), idxOf(cur)); }
  else drawCard(cur, ka, idxOf(cur));
  text(S.dash, FX + FW, FY + FH + 24, { size: 13, font: MONO, color: C.faint, align: "right", alpha: ka });
}
/* numéro de la fiche dans l'ordre du tour (« vue n/N ») */
const idxOf = c => [S.today.card, S.week.card, S.form.cards[0], S.form.cards[1], S.session.card, S.decisions.card].indexOf(c) + 1;
const N_VIEWS = 6; // aujourd'hui, semaine, forme, trail shape, séances, décisions

function sLaunch(t, d, cues) {
  head(S.k1, S.h1, t);
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 3.4), a2 = at(cues, 2, 7);
  const kt = outCubic(seg(t, 0.3, 0.9));
  const lines = [{ p: "$ ", s: "scripts/dashboard.sh", c: C.accent, w: 700, a: a0 + 0.3, b: a0 + 1.3 }];
  S.opts.forEach(([o, c], i) => lines.push({ s: `scripts/dashboard.sh ${o}  # ${c}`, c: C.soft, a: a1 + 1.2 + i * 0.5, b: a1 + 1.6 + i * 0.5 }));
  terminal(80, 180, 560, 300, t, lines, { alpha: kt, size: 13, lh: 34, title: "terminal" });
  // navigateur
  const kb = outCubic(seg(t, a0 + 1.4, a0 + 2.2));
  if (kb > 0) {
    const bx = 660 + (1 - kb) * 50;
    shot("aujourdhui", bx, 180, 540, 300, { alpha: kb, crop: cropTo("aujourdhui", [248, 100, 1008, 480], 540 / 270, 10), url: "127.0.0.1:8765" });
  }
  S.chips.forEach((c, i) => {
    const a = i === 0 ? a0 + 2.4 : i === 1 ? a1 + 0.2 : a2 - 0.2;
    const k = outBack(seg(t, a, a + 0.5));
    if (k > 0) pill(c, 80 + [0, 330, 760][i], 560, { alpha: clamp(k), size: 15, font: INTER, weight: 600 });
  });
  text(S.dash, 1200, 506, { size: 13, font: MONO, color: C.faint, align: "right", alpha: kb });
}

function sToday(t, d, cues) {
  head(S.kT, S.hT, t);
  const ka = outCubic(seg(t, 0.2, 0.8)), T = S.today;
  const n = d / 3;
  tour(t, d, [
    { name: "aujourdhui", box: [248, 140, 1008, 508], padW: 100, padT: 10, a: 0, hl: ["verdict"], cap: T.caps[0] },
    { name: "aujourdhui-sante", box: "triade", padW: 70, padT: 20, a: Math.max(2.8, at(cues, 1, 5) - 0.3), hl: ["hrv", "fc-repos", "readiness"], cap: T.caps[1] },
    { name: "aujourdhui-programme", box: "programme", padW: 80, padT: 20, a: Math.max(5.3, at(cues, 1, 5) + 2.3), hl: ["seuil-annule", "ef45"], cap: T.caps[2] },
  ], [T.card, T.card, T.card], ka, N_VIEWS);
}
function sWeek(t, d, cues) {
  head(S.kT, S.hT, t);
  const ka = outCubic(seg(t, 0.2, 0.8)), T = S.week;
  tour(t, d, [
    { name: "semaine", box: [248, 215, 1008, 271], padW: 60, padT: 10, a: 0, hl: ["seuil-annule", "cotes-deplacees"], cap: T.caps[0] },
    { name: "semaine-garde-fous", box: "regle-r7", padW: 200, padT: 90, a: Math.max(4.4, at(cues, 1, 5) - 0.6), hl: ["regle-r7"], cap: T.caps[1] },
  ], [T.card, T.card], ka, N_VIEWS);
}
function sForm(t, d, cues) {
  head(S.kT, S.hT, t);
  const ka = outCubic(seg(t, 0.2, 0.8)), T = S.form;
  tour(t, d, [
    { name: "forme", box: "courbe", padW: 40, padT: 6, a: 0, hl: ["courbe"], cap: T.caps[0] },
    { name: "trail-shape", box: "score", padW: 160, padT: 60, a: Math.max(4.2, at(cues, 1, 5) - 0.3), hl: ["score"], cap: T.caps[1] },
  ], [T.cards[0], T.cards[1]], ka, N_VIEWS);
}
function sSession(t, d, cues) {
  head(S.kT, S.hT, t);
  const ka = outCubic(seg(t, 0.2, 0.8)), T = S.session;
  const a1 = at(cues, 1, 6.5);
  tour(t, d, [
    { name: "seance", box: [248, 88, 1008, 330], padW: 20, padT: 0, a: 0, hl: ["titre"], cap: T.caps[0] },
    { name: "seance-montees", box: "montees", padW: 60, padT: 14, a: a1 - 0.3, hl: ["montees"], cap: T.caps[1] },
    { name: "seance-splits", box: [248, 80, 1008, 420], padW: 30, padT: 0, a: a1 + 1.5, hl: [[248, 140, 1008, 330]], cap: T.caps[2] },
  ], [T.card, T.card, T.card], ka, N_VIEWS);
}
function sDecisions(t, d, cues) {
  head(S.kT, S.hT, t);
  const ka = outCubic(seg(t, 0.2, 0.8)), T = S.decisions;
  tour(t, d, [
    { name: "decisions", box: "journal", padW: 100, padT: 40, a: 0, hl: ["bilan-matinal", "garde-fou"], cap: T.caps[0] },
    { name: "decision-detail", box: [248, 241, 1008, 620], padW: 20, padT: 0, a: Math.max(4.2, at(cues, 1, 5) - 0.6), hl: ["avant-apres"], cap: T.caps[1] },
  ], [T.card, T.card], ka, N_VIEWS);
}

function sMore(t, d, cues) {
  head(S.kM, S.hM, t);
  const a0 = at(cues, 0, 0.6);
  const order = [["sante", "hrv", 0], ["nutrition", "poids", 1], ["rapport", "rapport", 2], ["performance", "premier-bloc", 3], ["calendrier", "calendrier", 4]];
  const pos = [[80, 160], [460, 160], [840, 160], [270, 395], [650, 395]];
  const tw = 360, th = 170;
  order.forEach(([name, box, i]) => {
    const a = a0 + 1.0 + i * 0.85, k = outCubic(seg(t, a, a + 0.6));
    if (k <= 0) return;
    const [x, y0] = pos[i], y = y0 + (1 - k) * 16;
    const crop = cropTo(name, box, tw / th, 8);
    shot(name, x, y, tw, th, { chrome: false, crop, alpha: k, r: 12 });
    text(S.more[i][0], x, y + th + 26, { size: 18, weight: 700, font: SORA, color: C.accent, alpha: k });
    text(S.more[i][1], x, y + th + 48, { size: 14, color: C.soft, alpha: k });
  });
  const ke = seg(t, a0 + 6.2, a0 + 6.8);
  text(S.dash, 1200, 606, { size: 13, font: MONO, color: C.faint, align: "right", alpha: ke });
}

function sMobile(t, d, cues) {
  head(S.kP, S.hP, t);
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.5);
  // ordinateur
  const kd = outCubic(seg(t, 0.3, 0.9));
  shot("aujourdhui", 80, 180, 520, 300, { alpha: kd, crop: cropTo("aujourdhui", [248, 140, 1008, 507], 520 / 270, 20), url: "127.0.0.1:8765" });
  text(S.desk, 80, 510, { size: 14, font: MONO, color: C.faint, alpha: kd });
  // téléphones
  [["mobile-aujourdhui", 650, S.ph, 0], ["mobile-semaine", 940, "", 1]].forEach(([name, x, lab, i]) => {
    const a = a0 + 0.8 + i * 1.0, k = outCubic(seg(t, a, a + 0.7));
    if (k <= 0) return;
    const y = 150 + (1 - k) * 30, pw = 250, ph = 470;
    phone(x, y, pw, ph, (X, Y, w, h) => shot(name, X, Y, w, h, { chrome: false, shadow: false, stroke: false, crop: [0, 0, 390, 390 * h / w] }), { alpha: k });
  });
  text(S.ph, 650, 646 - 6, { size: 14, font: MONO, color: C.faint, alpha: kd, base: "alphabetic" });
  // chemins d'accès
  S.flows.forEach((f, i) => {
    const a = a1 + i * 1.4, k = outBack(seg(t, a, a + 0.5));
    if (k > 0) pill(f, 80, 560 + i * 44, { alpha: clamp(k), size: 14, font: INTER, weight: 600 });
  });
}

ARC.episode({
  n: 5, slug: "tableau-de-bord",
  strings: STR,
  shots: ["aujourdhui", "aujourdhui-sante", "aujourdhui-programme", "semaine", "semaine-garde-fous", "forme", "trail-shape", "seance", "seance-montees", "seance-splits", "decisions", "decision-detail", "sante", "nutrition", "rapport", "performance", "calendrier", "mobile-aujourdhui", "mobile-semaine"],
  scenes: { launch: sLaunch, today: sToday, week: sWeek, form: sForm, session: sSession, decisions: sDecisions, more: sMore, mobile: sMobile },
});
})();
