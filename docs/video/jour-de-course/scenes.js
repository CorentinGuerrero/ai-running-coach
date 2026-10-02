/* Le Sentier · étape 6 — « La course, segment par segment » : du GPX au débrief.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}] —
 * at(cues, i, repli) cale une animation sur la voix, quelle que soit la langue.
 * Athlète, course et chiffres fictifs (bible de la série : Camille, Trail des Crêtes, 42 km / 2 100 m D+). */
"use strict";
(() => {
const STR = {
  fr: {
    gpx: { k: "01 · LE FICHIER", h: "Un GPX entre, un parcours sort.",
      file: "trail-des-cretes.gpx", cmd: "python3 skills/gpx-analysis/scripts/analyze_gpx.py trail-des-cretes.gpx",
      rows: [["Distance réelle", "42,2 km", "annoncé : 42 km"], ["D+ / D-", "+2 096 / -2 094 m", "annoncé : 2 100 m D+"], ["Type", "boucle", "départ = arrivée"], ["Montées significatives", "3", "approches plates rognées"]],
      raw: "trace brute", smooth: "lissage anti-bruit", gain: "m", ax: "km" },
    model: { k: "02 · VOTRE COURBE", h: "Votre pente, votre allure.",
      pers: "votre courbe", gen: "modèle générique", pts: "séances d'endurance passées",
      fast: "plus rapide", slow: "plus lent", xl: "pente (%)", sparse: "historique insuffisant : repli générique",
      prov: "provenance de chaque segment", note: "Allure d'endurance apprise sur l'historique, par classe de pente. Jamais un scénario plus précis que les données." },
    race: { k: "03 · TROIS SCÉNARIOS", h: "Chaque segment, sa propre allure.",
      scen: [["Sécurité", "6 h 40"], ["Réaliste", "6 h 05"], ["Ambitieux", "5 h 38"]], ravito: "Ravito", water: "point d'eau OSM", ax: "km",
      pace: "allure /km", seg: "segments par pente similaire", fix: "arrêts ravito inclus dans les temps de passage" },
    energy: { k: "04 · ÉNERGIE ET RAVITO", h: "La dépense, section par section.",
      ref: "apport : 60 g de glucides/h ≈ 240 kcal/h", avg: "dépense moyenne prévue", unit: "kcal/h", cum: "cumul sur la course", gap: "écart signalé",
      note: "Signalé, jamais à combler en totalité.", pack: "sac + flasques", ax: "kcal/h par segment" },
    gear: { k: "05 · MATÉRIEL", h: "Rien de nouveau le jour J.",
      cmd: "python3 scripts/arc_index.py equipment --race-plan",
      rows: [["Frontale", "ok", "ok", "trouvée dans l'inventaire"], ["Bâtons", "never_used", "jamais utilisé", "aucune séance ne le cite : à tester en sortie longue"],
             ["Veste imperméable", "category_match", "à vérifier", "seule la catégorie correspond : spécification à contrôler"],
             ["Couverture de survie", "missing", "manquant", "non retrouvé dans votre inventaire"], ["Poche à eau 2 L", "alert", "sous alerte", "entretien à faire avant le départ"]],
      foot: "Rapprochement textuel strict : rien n'est présumé possédé, rien n'est inventé." },
    watch: { k: "06 · MONTRE ET COMPTE À REBOURS", h: "Le parcours part sur la montre.",
      file: "course_trail-des-cretes.gpx", fileSub: "GPX enrichi · ravitos en waypoints", up: "upload_course", name: "Trail des Crêtes - Stratégie",
      ok: "GPX disponible dans Garmin Connect", garmin: "Garmin Connect", race: "/race",
      out: "Course — J-54 Trail des Crêtes, Trail Shape 90/100", comps: ["Volume hebdomadaire", "Plus longue sortie", "D+ max d'une séance", "Durabilité"],
      note: "Un indicateur parmi d'autres. /race n'écrit rien et ne pousse rien vers Garmin." },
    debrief: { k: "07 · APRÈS LA COURSE", h: "Plan contre réalisé.",
      tag: "Exemple illustratif, après la course", cmd: "python3 scripts/arc_race_debrief.py debrief", file: "rapports/2026-11-23_debrief_trail-des-cretes.md",
      pace: "écart d'allure vs plan", slower: "plus lent", faster: "plus rapide",
      cards: [["Ralentissement de fin de course", "prévu +3,0 % · mesuré +5,2 %"], ["Glucides", "52 g/h réalisés · 60 g/h visés"], ["Dérive cumulée", "+{m} min vs le plan réaliste"]],
      mono: "ids de segment stables : s01, s02…" },
  },
  en: {
    gpx: { k: "01 · THE FILE", h: "A GPX goes in, a course comes out.",
      file: "trail-des-cretes.gpx", cmd: "python3 skills/gpx-analysis/scripts/analyze_gpx.py trail-des-cretes.gpx",
      rows: [["Real distance", "42.2 km", "advertised: 42 km"], ["Gain / loss", "+2,096 / -2,094 m", "advertised: 2,100 m gain"], ["Type", "loop", "start = finish"], ["Significant climbs", "3", "flat run-ins trimmed"]],
      raw: "raw track", smooth: "noise smoothing", gain: "m", ax: "km" },
    model: { k: "02 · YOUR CURVE", h: "Your grade, your pace.",
      pers: "your curve", gen: "generic model", pts: "past endurance sessions",
      fast: "faster", slow: "slower", xl: "grade (%)", sparse: "not enough history: generic fallback",
      prov: "provenance of each segment", note: "Endurance pace learned from your history, grade class by grade class. Never a scenario more precise than the data." },
    race: { k: "03 · THREE SCENARIOS", h: "Every segment, its own pace.",
      scen: [["Safe", "6:40"], ["Realistic", "6:05"], ["Ambitious", "5:38"]], ravito: "Aid", water: "OSM water point", ax: "km",
      pace: "pace /km", seg: "segments of similar grade", fix: "aid-station stops included in the split times" },
    energy: { k: "04 · ENERGY AND FUEL", h: "Energy cost, section by section.",
      ref: "intake: 60 g carbs/h ≈ 240 kcal/h", avg: "planned average cost", unit: "kcal/h", cum: "running total", gap: "flagged gap",
      note: "Flagged, never to be filled in full.", pack: "pack + flasks", ax: "kcal/h per segment" },
    gear: { k: "05 · GEAR", h: "Nothing new on race day.",
      cmd: "python3 scripts/arc_index.py equipment --race-plan",
      rows: [["Headlamp", "ok", "ok", "found in the inventory"], ["Poles", "never_used", "never used", "no session mentions it: test it on a long run"],
             ["Waterproof jacket", "category_match", "to check", "only the category matches: check the specification"],
             ["Survival blanket", "missing", "missing", "not found in your inventory"], ["2 L water bladder", "alert", "past alert", "maintenance due before the start"]],
      foot: "Strict text matching: nothing is assumed owned, nothing is made up." },
    watch: { k: "06 · WATCH AND COUNTDOWN", h: "The course goes to the watch.",
      file: "course_trail-des-cretes.gpx", fileSub: "enriched GPX · aid stations as waypoints", up: "upload_course", name: "Trail des Crêtes - Stratégie",
      ok: "GPX available in Garmin Connect", garmin: "Garmin Connect", race: "/race",
      out: "Race — D-54 Trail des Crêtes, Trail Shape 90/100", comps: ["Weekly volume", "Longest run", "Max single-session gain", "Durability"],
      note: "One indicator among others. /race writes nothing and pushes nothing to Garmin." },
    debrief: { k: "07 · AFTER THE RACE", h: "Plan versus actual.",
      tag: "Illustrative example, after the race", cmd: "python3 scripts/arc_race_debrief.py debrief", file: "rapports/2026-11-23_debrief_trail-des-cretes.md",
      pace: "pace gap vs plan", slower: "slower", faster: "faster",
      cards: [["Late-race fade", "planned +3.0% · measured +5.2%"], ["Carbs", "52 g/h taken · 60 g/h targeted"], ["Cumulative drift", "+{m} min vs the realistic plan"]],
      mono: "stable segment ids: s01, s02…" },
  },
};

/* ------------------------------ données fictives ------------------------- */
/* Profil du Trail des Crêtes (altitude en m), le même que celui de la bande-annonce. */
const elev = k => 320 + 620 * bump(k, 9, 3.6) + 860 * bump(k, 21, 4.4) + 520 * bump(k, 33.5, 3.2) + 40 * Math.sin(k * 1.9) + 25 * Math.sin(k * 4.3 + 1);
const KM = 42, EMIN = 250, EMAX = 1250;
const AID = [12, 24, 34], WATER = [5, 17.5, 28, 38.5];
const CLIMBS = [[6.5, 11.5, 620], [16.5, 24.5, 860], [30.5, 36.5, 520]];
const num = n => { const s = String(Math.round(n)); return LANG === "fr" ? s.replace(/\B(?=(\d{3})+(?!\d))/g, " ") : s.replace(/\B(?=(\d{3})+(?!\d))/g, ","); };
const dec = (x, n = 1) => (LANG === "fr" ? x.toFixed(n).replace(".", ",") : x.toFixed(n));
const fmtPace = p => { let m = Math.floor(p), s = Math.round((p - m) * 60); if (s === 60) { m++; s = 0; } return `${m}:${String(s).padStart(2, "0")}`; };
/* Courbe personnelle (min/km en fonction de la pente en %) et courbe générique de repli. */
const pers = g => g >= 0 ? 6 + 0.42 * g + 0.006 * g * g : 6 + 0.12 * g + 0.0045 * g * g;
const gen = g => g >= 0 ? 6.3 + 0.37 * g + 0.008 * g * g : 6.1 + 0.09 * g + 0.0055 * g * g;
const gradeAt = k => (elev(Math.min(KM, k + 0.4)) - elev(Math.max(0, k - 0.4))) / 8;

/* Segments : bornes (km), pente moyenne, temps brut par intégration point par point (0,1 km). */
const B = [0, 4, 6.5, 11.5, 14, 16.5, 24.5, 27, 30.5, 36.5, 39, 42];
const SEG = B.slice(1).map((b, i) => {
  const a = B[i]; let raw = 0;
  for (let k = a + 0.05; k < b; k += 0.1) raw += pers(gradeAt(k)) * 0.1;
  return { a, b, dist: b - a, grade: (elev(b) - elev(a)) / ((b - a) * 10), raw };
});
const RAW_TOT = SEG.reduce((s, x) => s + x.raw, 0);
const SCEN_MIN = [400, 365, 338], STOPS_MIN = 9;
SEG.forEach(s => { s.t = SCEN_MIN.map(T => s.raw * (T - STOPS_MIN) / RAW_TOT); s.pace = s.t.map(t => t / s.dist); });
/* Dépense prévue (kcal/h) : plus haute en montée, plus basse en descente, recalée sur 520 kcal/h de moyenne. */
{
  const kh = SEG.map(s => 520 * (1 + 0.024 * clamp(s.grade, -12, 14)));
  const w = SEG.reduce((a, s, i) => a + kh[i] * s.t[1], 0), tt = SEG.reduce((a, s) => a + s.t[1], 0);
  const sc = 520 * tt / w;
  SEG.forEach((s, i) => { s.kh = kh[i] * sc; s.kcal = s.kh * s.t[1] / 60; });
}
const KCAL_TOT = SEG.reduce((a, s) => a + s.kcal, 0);
/* Débrief illustratif : écart d'allure réalisé vs plan (%, positif = plus lent). */
const DELTA = [-0.8, 0.4, 1.2, -0.3, 0.9, 1.8, 2.9, 4.6, 5.8, 6.4, 7.1];
const DRIFT_MIN = SEG.reduce((a, s, i) => a + s.t[1] * DELTA[i] / 100, 0);

/* Bruit d'altitude du GPX brut, et nuage de points « séances passées » (graine fixe). */
const RAWN = (() => { const R = rng(23); return Array.from({ length: 421 }, () => (R() + R() + R() - 1.5) * 18); })();
const PTS = (() => {
  const R = rng(58), out = [];
  while (out.length < 170) {
    const g = (R() + R() + R() - 1.5) * 24;
    if (Math.abs(g) > 21) continue;
    out.push([g, pers(g) * (1 + (R() + R() - 1) * 0.1)]);
  }
  return out;
})();

/* Frise discrète du bas : le coureur avance d'une scène à l'autre le long du profil. */
const ORDER = ["gpx", "model", "race", "energy", "gear", "watch", "debrief"];
function rail(t, d, id) {
  const idx = ORDER.indexOf(id), u = (idx + seg(t, 0, d)) / ORDER.length;
  const x0 = 80, x1 = 1200, yb = 626, hh = 22;
  const X = k => lerp(x0, x1, k / KM), Y = k => yb - hh * (elev(k) - EMIN) / (EMAX - EMIN);
  const pts = []; for (let k = 0; k <= KM; k += 0.4) pts.push([X(k), Y(k)]);
  line(pts, "rgba(231,237,233,0.2)", 1.5);
  line(pts.filter(p => p[0] <= X(u * KM)), C.accent, 2, 0.8);
  AID.forEach(k => dot(X(k), Y(k), 2.6, u * KM >= k ? C.accent : "rgba(231,237,233,0.4)"));
  dot(X(u * KM), Y(u * KM), 5, C.accent); dot(X(u * KM), Y(u * KM), 10, C.accent, 0.2);
}

/* ------------------------------ 1 · le fichier GPX ----------------------- */
function sGpx(t, d, cues) {
  const s = S.gpx, a1 = at(cues, 1, 3.5);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  // le fichier tombe
  const kf = outBack(seg(t, 0.4, 1.2));
  panel(80, 190 - (1 - clamp(kf, 0, 1.1)) * 140, 300, 96, { r: 16, fill: C.panel2, alpha: clamp(kf * 1.4), shadow: true });
  const fy = 190 - (1 - clamp(kf, 0, 1.1)) * 140;
  pill("GPX", 120, fy + 34, { size: 13, alpha: clamp(kf * 1.4), align: "center" });
  text(s.file, 100, fy + 74, { size: 15, weight: 600, font: MONO, alpha: clamp(kf * 1.4) });
  const w = [];
  for (let i = 0; i <= 40; i++) w.push([200 + i * 3.6, fy + 34 + 12 * Math.sin(i * 0.5) * Math.sin(i * 0.13 + 1)]);
  line(w, C.accent, 2, clamp(kf * 1.4) * 0.8);
  // commande
  const kc = outCubic(seg(t, 1.2, 1.8));
  para(s.cmd, 80, 322, 330, { size: 12, font: MONO, color: C.faint, alpha: kc });
  // chiffres mesurés
  s.rows.forEach(([lab, val, sub], i) => {
    const a = at(cues, 0, 0.6) + 1.2 + i * 0.7, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    const y = 372 + i * 58 + (1 - k) * 14;
    panel(80, y, 330, 50, { r: 12, alpha: k, fill: i === 2 ? "rgba(163,230,53,0.07)" : C.panel, stroke: i === 2 ? "rgba(163,230,53,0.4)" : C.line });
    text(lab, 96, y + 20, { size: 12, font: MONO, color: C.faint, alpha: k });
    text(val, 96, y + 41, { size: 18, weight: 700, font: SORA, alpha: k });
    text(sub, 396, y + 20, { size: 12, color: C.soft, align: "right", alpha: k });
  });
  // profil : trace brute puis lissée
  const x0 = 470, x1 = 1200, yb = 520, yt = 210;
  const X = k => lerp(x0, x1, k / KM), Y = e => lerp(yb, yt, (e - EMIN) / (EMAX - EMIN));
  const kp = outCubic(seg(t, 0.8, 1.4));
  panel(x0 - 30, 186, x1 - x0 + 60, 370, { r: 18, alpha: kp });
  for (let k = 0; k <= KM; k += 6) text(String(k), X(k), yb + 24, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kp });
  text(s.ax, x1 + 14, yb + 24, { size: 12, font: MONO, color: C.faint, alpha: kp });
  const ds = seg(t, a1 - 1.6, a1 + 0.6);     // le lissage
  const draw = seg(t, 1.0, 2.6);
  const rawPts = [], smPts = [];
  for (let i = 0; i <= 420; i++) { const k = i / 10; rawPts.push([X(k), Y(elev(k) + RAWN[i])]); smPts.push([X(k), Y(elev(k))]); }
  line(partial(rawPts, draw), C.faint, 1.2, 0.85 * (1 - 0.8 * ds));
  line(partial(smPts, ds), C.accent, 3, 1);
  // montées significatives
  CLIMBS.forEach(([a, b, g], i) => {
    const ca = a1 + 1.0 + i * 0.7, k = outCubic(seg(t, ca, ca + 0.5));
    if (k <= 0) return;
    ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = "rgba(163,230,53,0.12)"; ctx.fillRect(X(a), yt - 14, X(b) - X(a), yb - yt + 14);
    ctx.restore();
    line([[X(a), yt - 14], [X(a), yb]], "rgba(163,230,53,0.45)", 1, k); line([[X(b), yt - 14], [X(b), yb]], "rgba(163,230,53,0.45)", 1, k);
    text(`+${num(g)} ${s.gain}`, (X(a) + X(b)) / 2, yt - 22, { size: 14, weight: 700, font: MONO, color: C.accent, align: "center", alpha: k });
  });
  // légende
  const kl = seg(t, 1.6, 2.2);
  line([[x0 + 4, 214], [x0 + 32, 214]], C.faint, 1.5, kl); text(s.raw, x0 + 42, 219, { size: 13, color: C.soft, alpha: kl });
  line([[x0 + 4, 240], [x0 + 32, 240]], C.accent, 3, kl); text(s.smooth, x0 + 42, 245, { size: 13, color: C.soft, alpha: kl });
  rail(t, d, "gpx");
}

/* ------------------------------ 2 · votre courbe ------------------------- */
function sModel(t, d, cues) {
  const s = S.model, a1 = at(cues, 1, 5);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const x0 = 130, x1 = 820, y0 = 200, y1 = 560, G = 25;
  const X = g => lerp(x0, x1, (g + G) / (2 * G)), Y = p => lerp(y0, y1, (clamp(p, 4, 21) - 4) / 17);
  const kp = outCubic(seg(t, 0.3, 0.9));
  panel(x0 - 60, y0 - 24, x1 - x0 + 90, y1 - y0 + 70, { r: 18, alpha: kp });
  // zones à faible historique
  const ks = seg(t, a1 - 0.3, a1 + 0.6);
  [[-G, -20], [20, G]].forEach(([a, b]) => {
    ctx.save(); ctx.globalAlpha *= ks; ctx.fillStyle = "rgba(240,180,60,0.1)"; ctx.fillRect(X(a), y0, X(b) - X(a), y1 - y0); ctx.restore();
  });
  // axes
  [5, 10, 15, 20].forEach(p => { line([[x0, Y(p)], [x1, Y(p)]], "rgba(231,237,233,0.07)", 1, kp); text(`${p}:00`, x0 - 12, Y(p) + 4, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kp }); });
  [-20, -10, 0, 10, 20].forEach(g => { text(`${g > 0 ? "+" : ""}${g}`, X(g), y1 + 24, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kp }); line([[X(g), y0], [X(g), y1]], g === 0 ? "rgba(231,237,233,0.18)" : "rgba(231,237,233,0.05)", 1, kp); });
  text(s.xl, x1, y1 + 46, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kp });
  text(s.fast, x0 + 6, y0 - 8, { size: 12, font: MONO, color: C.faint, alpha: kp });
  text(s.slow, x0 + 6, y1 - 8, { size: 12, font: MONO, color: C.faint, alpha: kp });
  if (ks > 0) text(s.sparse, X(G) - 8, y0 + 22, { size: 12, color: C.amber, align: "right", alpha: ks });
  // nuage de points
  const n = Math.floor(PTS.length * outCubic(seg(t, 0.7, at(cues, 0, 0.6) + 3.4)));
  for (let i = 0; i < n; i++) dot(X(PTS[i][0]), Y(PTS[i][1]), 3.4, C.soft, 0.6);
  // courbe générique (pointillés) puis courbe personnelle
  const gp = [], pp = [];
  for (let g = -G; g <= G; g += 0.5) gp.push([X(g), Y(gen(g))]);
  for (let g = -20; g <= 20; g += 0.5) pp.push([X(g), Y(pers(g))]);
  line(partial(gp, seg(t, a1 - 0.2, a1 + 1.4)), C.amber, 2, 0.9, [6, 6]);
  line(partial(pp, inOut(seg(t, at(cues, 0, 0.6) + 3.0, at(cues, 0, 0.6) + 5.2))), C.accent, 3.5);
  // légende et provenance
  const lx = 880, kl = seg(t, 1.0, 1.6);
  dot(lx + 8, 232, 4, C.soft, kl * 0.8); text(s.pts, lx + 26, 237, { size: 15, color: C.soft, alpha: kl });
  line([[lx, 268], [lx + 18, 268]], C.accent, 3.5, kl); text(s.pers, lx + 26, 273, { size: 15, weight: 600, alpha: kl });
  line([[lx, 304], [lx + 18, 304]], C.amber, 2, kl, [5, 4]); text(s.gen, lx + 26, 309, { size: 15, color: C.soft, alpha: kl });
  const kv = outCubic(seg(t, a1 + 0.8, a1 + 1.6));
  text(s.prov, lx, 372, { size: 12, font: MONO, color: C.faint, alpha: kv });
  [["personal", C.accent], ["mixed", C.teal], ["generic", C.amber]].forEach(([nm, c], i) =>
    pill(nm, lx + (i ? [0, 106, 190][i] : 0), 408, { size: 14, alpha: kv, color: c, stroke: c, fill: "rgba(13,20,16,0.6)" }));
  para(s.note, lx, 470, 310, { size: 15, color: C.soft, alpha: seg(t, a1 + 1.4, a1 + 2.2) });
  rail(t, d, "model");
}

/* ------------------------------ 3 · trois scénarios ---------------------- */
function sRace(t, d, cues) {
  const s = S.race, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.6), a2 = at(cues, 2, 9);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const x0 = 80, x1 = 1200, yb = 430, yt = 250;
  const X = k => lerp(x0, x1, k / KM), Y = e => lerp(yb, yt, (e - EMIN) / (EMAX - EMIN));
  const p = inOut(seg(t, 0.5, 2.2));
  ctx.save(); ctx.beginPath(); ctx.moveTo(x0, yb);
  for (let k = 0; k <= KM * p; k += 0.1) ctx.lineTo(X(k), Y(elev(k)));
  ctx.lineTo(X(KM * p), yb); ctx.closePath();
  const g = ctx.createLinearGradient(0, yt, 0, yb); g.addColorStop(0, "rgba(30,77,59,0.7)"); g.addColorStop(1, "rgba(30,77,59,0.06)");
  ctx.fillStyle = g; ctx.fill(); ctx.restore();
  for (let k = 0; k < KM * p - 0.1; k += 0.25) {
    const sl = (elev(k + 0.25) - elev(k)) / 250;
    line([[X(k), Y(elev(k))], [X(Math.min(k + 0.25, KM * p)), Y(elev(Math.min(k + 0.25, KM * p)))]], sl > 0.08 ? C.accent : sl < -0.08 ? C.teal : C.soft, 2.5);
  }
  for (let k = 0; k <= KM; k += 6) text(String(k), X(k), yb + 20, { size: 12, font: MONO, color: C.faint, align: "center", alpha: seg(t, 0.6, 1.2) });
  text(s.ax, x1 + 24, yb + 20, { size: 12, font: MONO, color: C.faint, alpha: seg(t, 0.6, 1.2) });
  // segments : cadre et pastilles d'allure
  const sy = 486, sh = 50;
  const sc = clamp(Math.floor(Math.max(0, t - a1 - 0.2) / 1.9), 0, 2) ;   // scénario affiché
  const sw = clamp((t - a1 - 0.2) / 1.9 - sc, 0, 1);                       // fondu entre deux scénarios
  const runner = inOut(seg(t, a0 + 1.2, d - 0.8)) * KM;
  SEG.forEach((sg, i) => {
    const ka = outCubic(seg(t, a0 + 0.4 + i * 0.22, a0 + 0.9 + i * 0.22));
    if (ka <= 0) return;
    const xa = X(sg.a) + 1.5, wa = X(sg.b) - X(sg.a) - 3;
    const col = sg.grade > 3 ? C.accent : sg.grade < -3 ? C.teal : C.soft;
    const on = runner >= sg.a && runner < sg.b;
    line([[X(sg.a), Y(elev(sg.a))], [X(sg.a), sy]], "rgba(231,237,233,0.08)", 1, ka);
    panel(xa, sy, wa, sh, { r: 9, fill: on ? "rgba(163,230,53,0.14)" : C.panel, stroke: on ? C.accent : C.line, alpha: ka });
    const pc = sc === 0 && sw === 0 ? sg.pace[0] : sg.pace[sc] + (sg.pace[Math.min(2, sc + 1)] - sg.pace[sc]) * inOut(clamp(sw * 3 - 2));
    const pcv = t < a1 ? sg.pace[1] : pc;
    text(fmtPace(pcv), xa + wa / 2, sy + 22, { size: wa > 60 ? 15 : 13, weight: 700, font: MONO, color: on ? C.accent : C.ink, align: "center", alpha: ka });
    text("s" + String(i + 1).padStart(2, "0"), xa + wa / 2, sy + 40, { size: 11, font: MONO, color: col, align: "center", alpha: ka });
  });
  text(s.pace, x0, sy - 10, { size: 12, font: MONO, color: C.faint, alpha: seg(t, a0 + 0.6, a0 + 1.2) });
  text(s.seg, x1, sy - 10, { size: 12, font: MONO, color: C.faint, align: "right", alpha: seg(t, a0 + 0.6, a0 + 1.2) });
  // ravitos
  AID.forEach((k, i) => {
    const kr = outBack(seg(t, a2 + i * 0.45, a2 + 0.5 + i * 0.45));
    if (kr <= 0) return;
    const x = X(k), y = Y(elev(k));
    line([[x, y - 8], [x, yt - 22]], C.faint, 1, clamp(kr), [3, 4]);
    ctx.save(); ctx.globalAlpha = clamp(kr); ctx.beginPath(); ctx.moveTo(x, yt - 24); ctx.lineTo(x - 8 * kr, yt - 38); ctx.lineTo(x + 8 * kr, yt - 38); ctx.closePath(); ctx.fillStyle = C.accent; ctx.fill(); ctx.restore();
    text(`${s.ravito} km ${k}`, x, yt - 46, { size: 12, weight: 600, font: MONO, color: C.soft, align: "center", alpha: clamp(kr) });
  });
  // points d'eau OpenStreetMap
  WATER.forEach((k, i) => {
    const kw = outBack(seg(t, a2 + 1.6 + i * 0.25, a2 + 2.0 + i * 0.25));
    if (kw <= 0) return;
    const x = X(k), y = Y(elev(k)) - 10;
    ctx.save(); ctx.globalAlpha = clamp(kw); ctx.translate(x, y); ctx.scale(kw, kw);
    ctx.beginPath(); ctx.moveTo(0, -9); ctx.bezierCurveTo(7, 0, 7, 6, 0, 6); ctx.bezierCurveTo(-7, 6, -7, 0, 0, -9); ctx.fillStyle = C.teal; ctx.fill(); ctx.restore();
  });
  const kwl = seg(t, a2 + 2.4, a2 + 3.0);
  ctx.save(); ctx.globalAlpha *= kwl; ctx.beginPath(); ctx.moveTo(x1 - 150, 188); ctx.bezierCurveTo(x1 - 143, 197, x1 - 143, 203, x1 - 150, 203); ctx.bezierCurveTo(x1 - 157, 203, x1 - 157, 197, x1 - 150, 188); ctx.fillStyle = C.teal; ctx.fill(); ctx.restore();
  text(s.water, x1 - 134, 202, { size: 12, font: MONO, color: C.soft, alpha: kwl });
  // coureur
  if (t > a0 + 1.2) {
    const k = runner, e = elev(k);
    dot(X(k), Y(e), 13, C.accent, 0.25); dot(X(k), Y(e), 6.5, C.accent);
  }
  // scénarios
  const ky = 560; let px = 80;
  s.scen.forEach(([n, v], i) => {
    const ks = seg(t, a1 - 0.4 + i * 0.15, a1 + 0.2 + i * 0.15);
    const on = t > a1 + 0.2 && sc === i;
    const label = `${n}  ${v}`;
    const w = measure(label, 17, 700) + 38;
    panel(px, ky - 22, w, 44, { r: 22, fill: on ? "rgba(163,230,53,0.14)" : C.panel, stroke: on ? C.accent : C.line, alpha: ks, lw: on ? 2 : 1 });
    text(label, px + 19, ky + 6, { size: 17, weight: 700, color: on ? C.accent : C.ink, alpha: ks });
    px += w + 12;
  });
  text(s.fix, x1, ky + 5, { size: 12, font: MONO, color: C.faint, align: "right", alpha: seg(t, a1 + 1, a1 + 1.6) });
}

/* ------------------------------ 4 · énergie ------------------------------ */
function sEnergy(t, d, cues) {
  const s = S.energy, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.4);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const x0 = 80, x1 = 860, yb = 540, yt = 215, V = 800;
  const X = k => lerp(x0, x1, k / KM), Y = v => lerp(yb, yt, v / V);
  const kp = outCubic(seg(t, 0.3, 0.9));
  panel(x0 - 30, yt - 30, x1 - x0 + 60, yb - yt + 76, { r: 18, alpha: kp });
  text(s.ax, x0, yt - 8, { size: 12, font: MONO, color: C.faint, alpha: kp });
  [200, 400, 600].forEach(v => { line([[x0, Y(v)], [x1, Y(v)]], "rgba(231,237,233,0.07)", 1, kp); text(String(v), x0 - 8, Y(v) + 4, { size: 11, font: MONO, color: C.faint, align: "right", alpha: kp * 0 }); });
  for (let k = 0; k <= KM; k += 6) text(String(k), X(k), yb + 22, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kp });
  const REF = 240;
  SEG.forEach((sg, i) => {
    const ka = outCubic(seg(t, a0 + 0.5 + i * 0.2, a0 + 1.1 + i * 0.2));
    if (ka <= 0) return;
    const xa = X(sg.a) + 2, wa = X(sg.b) - X(sg.a) - 4, top = Y(sg.kh * ka);
    ctx.save(); ctx.globalAlpha *= kp;
    rr(xa, top, wa, yb - top, 5); ctx.fillStyle = "rgba(30,77,59,0.85)"; ctx.fill();
    // l'écart entre la dépense et l'apport
    const kg = seg(t, a1 + 0.2, a1 + 1.4);
    if (kg > 0 && sg.kh > REF) { const gy = Y(REF); ctx.fillStyle = `rgba(240,180,60,${0.28 * kg})`; ctx.fillRect(xa, top, wa, gy - top); }
    ctx.restore();
    text(String(Math.round(sg.kh)), xa + wa / 2, top - 8, { size: wa > 56 ? 13 : 11, weight: 600, font: MONO, color: C.soft, align: "center", alpha: ka });
  });
  // apport
  const kr = outCubic(seg(t, a1 - 0.2, a1 + 0.6));
  line([[x0, Y(REF)], [x0 + (x1 - x0) * kr, Y(REF)]], C.accent, 2.5, 1);
  text(s.ref, x1 - 4, Y(REF) + 22, { size: 13, weight: 600, font: MONO, color: C.accent, align: "right", alpha: kr });
  // colonne de chiffres
  const cx = 920;
  const kc = outCubic(seg(t, a0 + 1.6, a0 + 2.4));
  panel(cx, 190, 280, 350, { r: 18, alpha: kc });
  text(s.avg, cx + 22, 226, { size: 12, font: MONO, color: C.faint, alpha: kc });
  text("≈ 520", cx + 22, 276, { size: 44, weight: 800, font: SORA, alpha: kc });
  text(s.unit, cx + 22, 304, { size: 14, font: MONO, color: C.soft, alpha: kc });
  const kcu = seg(t, a0 + 2.6, a0 + 3.4);
  text(s.cum, cx + 22, 350, { size: 12, font: MONO, color: C.faint, alpha: kcu });
  text(`≈ ${num(Math.round(KCAL_TOT / 10) * 10)} kcal`, cx + 22, 388, { size: 26, weight: 700, font: SORA, alpha: kcu });
  const kpk = outBack(seg(t, a0 + 3.0, a0 + 3.6));
  pill("--pack-kg", cx + 22, 436, { size: 14, alpha: clamp(kpk) });
  text(s.pack, cx + 22 + 106, 441, { size: 13, color: C.soft, alpha: clamp(kpk) });
  const kg = seg(t, a1 + 1.0, a1 + 1.8);
  if (kg > 0) {
    ctx.save(); ctx.globalAlpha *= kg; ctx.fillStyle = "rgba(240,180,60,0.28)"; ctx.fillRect(cx + 22, 478, 16, 16); ctx.restore();
    text(s.gap, cx + 46, 491, { size: 14, weight: 600, color: C.amber, alpha: kg });
    para(s.note, cx + 22, 514, 240, { size: 13, color: C.soft, alpha: kg, lh: 18 });
  }
  rail(t, d, "energy");
}

/* ------------------------------ 5 · matériel ----------------------------- */
function sGear(t, d, cues) {
  const s = S.gear, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 7);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const kc = outCubic(seg(t, 0.3, 0.9));
  panel(80, 168, 560, 38, { r: 10, fill: "#0a120e", alpha: kc });
  text("$ " + s.cmd, 96, 192, { size: 14, font: MONO, color: C.accent, alpha: kc });
  const col = { ok: C.accent, never_used: C.amber, category_match: C.amber, missing: C.red, alert: C.red };
  s.rows.forEach(([name, code, label, note], i) => {
    const a = a0 + 0.8 + i * 0.95, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    const y = 226 + i * 66 + (1 - k) * 14, c = col[code];
    panel(80, y, 1120, 56, { r: 14, alpha: k, fill: code === "ok" ? C.panel : "rgba(240,180,60,0.04)", stroke: code === "ok" ? C.line : c + "66" });
    text(name, 104, y + 35, { size: 20, weight: 700, font: SORA, alpha: k });
    pill(label, 480, y + 28, { size: 14, align: "center", color: c, stroke: c, fill: "rgba(13,20,16,0.7)", alpha: k });
    text(code, 560, y + 33, { size: 12, font: MONO, color: C.faint, alpha: k });
    text(note, 760, y + 33, { size: 15, color: C.soft, alpha: k });
    if (code === "ok") check(424, y + 28, 11, C.accent, seg(t, a + 0.2, a + 0.7), k);
  });
  const kf = seg(t, a1 - 0.4, a1 + 0.4);
  text(s.foot, 80, 584, { size: 15, color: C.soft, alpha: kf });
  rail(t, d, "gear");
}

/* ------------------------------ 6 · montre + /race ----------------------- */
function sWatch(t, d, cues) {
  const s = S.watch, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.2);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  // fichier → Garmin Connect → montre
  const kf = outCubic(seg(t, 0.4, 1.0));
  panel(80, 190, 240, 74, { r: 14, fill: C.panel2, alpha: kf });
  pill("GPX", 118, 214, { size: 12, align: "center", alpha: kf }); text(s.file, 94, 246, { size: 12, font: MONO, alpha: kf });
  text(s.fileSub, 80, 284, { size: 12, color: C.faint, alpha: kf });
  const kt = outCubic(seg(t, a0 + 0.8, a0 + 1.6));
  arrow(326, 227, 400, 227, kt, C.faint);
  if (kt > 0.95) packets(326, 227, 400, 227, t, 2, 1.2, 0.9);
  panel(404, 190, 200, 74, { r: 14, fill: C.panel2, alpha: kt });
  text(s.garmin, 504, 222, { size: 15, weight: 700, font: SORA, align: "center", alpha: kt });
  text(s.up, 504, 246, { size: 13, font: MONO, color: C.accent, align: "center", alpha: kt });
  // montre
  const kw = outBack(seg(t, a0 + 1.8, a0 + 2.6)), cx = 250, cy = 440;
  if (kw > 0) {
    ctx.save(); ctx.translate(cx, cy); const sc = clamp(kw, 0, 1.05); ctx.scale(sc, sc);
    rr(-34, -138, 68, 44, 10); ctx.fillStyle = C.line; ctx.fill(); rr(-34, 94, 68, 44, 10); ctx.fill();
    dot(0, 0, 104, "#33463b"); dot(0, 0, 94, "#050806");
    // parcours sur l'écran : boucle
    const pts = []; for (let i = 0; i <= 80; i++) { const a = i / 80 * Math.PI * 2; pts.push([Math.cos(a) * 48 + 14 * Math.sin(a * 3), Math.sin(a) * 36 + 10 * Math.cos(a * 2)]); }
    line(pts, C.accent, 3, 1);
    [0.12, 0.38, 0.58].forEach((u, i) => { const q = pts[Math.round(u * 80)]; ctx.beginPath(); ctx.moveTo(q[0], q[1] - 12); ctx.lineTo(q[0] - 6, q[1] - 22); ctx.lineTo(q[0] + 6, q[1] - 22); ctx.closePath(); ctx.fillStyle = C.amber; ctx.fill(); });
    ctx.restore();
  }
  const kn = seg(t, a0 + 2.6, a0 + 3.2);
  text(s.name, 380, 420, { size: 16, weight: 600, alpha: kn });
  check(366, 456, 11, C.accent, seg(t, a0 + 3.2, a0 + 3.8), kn);
  para(s.ok, 384, 461, 230, { size: 14, color: C.soft, alpha: kn, lh: 20 });
  // /race
  const rx = 640, ry = 190, rw = 560;
  const kr = outCubic(seg(t, a1 - 0.6, a1 + 0.2));
  terminal(rx, ry, rw, 130, t, [
    { p: "> ", s: s.race, c: C.accent, w: 700, a: a1 - 0.3, b: a1 + 0.3 },
    { s: s.out, c: C.ink, w: 700, a: a1 + 0.7, b: a1 + 2.0 },
  ], { alpha: kr, size: 16, lh: 36, title: "Claude Code · coach" });
  const comp = [100, 73, 97, null];  // valeurs réelles du tableau de bord de Camille (capture trail-shape)
  s.comps.forEach((lab, i) => {
    const a = a1 + 2.4 + i * 0.3, k = outCubic(seg(t, a, a + 0.6));
    if (k <= 0) return;
    const y = 352 + i * 50;
    text(lab, rx, y + 5, { size: 15, color: C.soft, alpha: k });
    rr(rx + 230, y - 9, 250, 14, 7); ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = C.line; ctx.fill(); ctx.restore();
    if (comp[i] !== null) { ctx.save(); ctx.globalAlpha *= k; rr(rx + 230, y - 9, Math.max(2, 250 * comp[i] / 100 * k), 14, 7); ctx.fillStyle = comp[i] < 80 ? C.amber : C.accent; ctx.fill(); ctx.restore(); }
    text(comp[i] === null ? "—" : `${comp[i]} %`, rx + rw, y + 5, { size: 14, font: MONO, align: "right", alpha: k, color: comp[i] === null ? C.faint : C.ink });
  });
  para(s.note, rx, 566, 560, { size: 14, color: C.faint, alpha: seg(t, a1 + 4.2, a1 + 5), lh: 20 });
  rail(t, d, "watch");
}

/* ------------------------------ 7 · débrief ------------------------------ */
function sDebrief(t, d, cues) {
  const s = S.debrief, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.6);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7));
  pill(s.tag, W - 80, 86, { size: 12, align: "right", alpha: seg(t, 0.3, 0.8), color: C.amber, stroke: "rgba(240,180,60,0.5)", fill: "rgba(240,180,60,0.08)" });
  // commande
  const kc = outCubic(seg(t, 0.3, 0.9));
  panel(80, 168, 640, 36, { r: 10, fill: "#0a120e", alpha: kc });
  text("$ " + s.cmd, 96, 191, { size: 14, font: MONO, color: C.accent, alpha: kc });
  // écarts par segment
  const x0 = 80, x1 = 830, yz = 400, sc = 15, X = k => lerp(x0, x1, k / KM);
  panel(x0 - 20, 222, x1 - x0 + 40, 316, { r: 18, alpha: kc });
  line([[x0, yz], [x1, yz]], "rgba(231,237,233,0.3)", 1, kc);
  [-6, 6].forEach(v => { line([[x0, yz - v * sc], [x1, yz - v * sc]], "rgba(231,237,233,0.07)", 1, kc); });
  text(s.slower, x0, 246, { size: 12, font: MONO, color: C.amber, alpha: kc });
  text(s.faster, x0, 522, { size: 12, font: MONO, color: C.teal, alpha: kc });
  text(s.pace, x1, 246, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kc });
  SEG.forEach((sg, i) => {
    const a = a0 + 0.6 + i * 0.28, k = outCubic(seg(t, a, a + 0.5));
    const v = DELTA[i] * k, xa = X(sg.a) + 3, wa = X(sg.b) - X(sg.a) - 6;
    const c = DELTA[i] > 3 ? C.amber : DELTA[i] < 0 ? C.teal : C.soft;
    ctx.save(); ctx.globalAlpha *= kc; rr(xa, v >= 0 ? yz - v * sc : yz, wa, Math.max(2, Math.abs(v) * sc), 4); ctx.fillStyle = c; ctx.globalAlpha *= 0.85; ctx.fill(); ctx.restore();
    if (k > 0.6) text(`${DELTA[i] > 0 ? "+" : ""}${dec(DELTA[i])} %`, xa + wa / 2, v >= 0 ? yz - v * sc - 8 : yz + Math.abs(v) * sc + 17, { size: wa > 60 ? 12 : 10, font: MONO, color: C.soft, align: "center", alpha: kc * clamp(k * 2 - 1) });
    text("s" + String(i + 1).padStart(2, "0"), xa + wa / 2, 536 - 6, { size: 11, font: MONO, color: C.faint, align: "center", alpha: kc * k * 0 });
  });
  // ruban des segments sous le graphique
  SEG.forEach((sg, i) => text("s" + String(i + 1).padStart(2, "0"), (X(sg.a) + X(sg.b)) / 2, 508, { size: 11, font: MONO, color: C.faint, align: "center", alpha: kc * seg(t, a0 + 0.6, a0 + 1.2) }));
  // cartes
  const cx = 880;
  s.cards.forEach(([lab, val], i) => {
    const a = a1 + 0.2 + i * 0.8, k = outCubic(seg(t, a, a + 0.6));
    if (k <= 0) return;
    const y = 222 + i * 108 + (1 - k) * 14;
    panel(cx, y, 320, 94, { r: 16, alpha: k, fill: i === 0 ? "rgba(240,180,60,0.07)" : C.panel, stroke: i === 0 ? "rgba(240,180,60,0.4)" : C.line });
    text(lab, cx + 20, y + 34, { size: 13, font: MONO, color: C.faint, alpha: k });
    text(val.replace("{m}", String(Math.max(1, Math.round(DRIFT_MIN)))), cx + 20, y + 68, { size: 16, weight: 700, alpha: k });
  });
  const kf = seg(t, a1 + 2.6, a1 + 3.4);
  text(s.file, 80, 574, { size: 14, font: MONO, color: C.soft, alpha: kf });
  text(s.mono, 80, 598, { size: 12, font: MONO, color: C.faint, alpha: kf });
  rail(t, d, "debrief");
}

ARC.episode({
  n: 6, slug: "jour-de-course",
  strings: STR,
  shots: [],
  scenes: { gpx: sGpx, model: sModel, race: sRace, energy: sEnergy, gear: sGear, watch: sWatch, debrief: sDebrief },
});
})();
