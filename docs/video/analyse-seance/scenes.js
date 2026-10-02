/* Le Sentier · étape 7 — « Disséquer une sortie » : du fichier FIT à la comparaison de sorties.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}] —
 * at(cues, i, repli) cale une animation sur la voix, quelle que soit la langue.
 * La sortie est celle de la bible de la série (Camille, dimanche 27 septembre 2026) ; les courbes sont
 * synthétiques (rng à graine fixe), jamais des données réelles. */
"use strict";
(() => {
const STR = {
  fr: {
    fit: { k: "01 · LE FICHIER FIT", h: "Une mesure par seconde.", day: "Dimanche 27 septembre · trail",
      chips: ["18,2 km", "820 m D+", "FC moy 142 bpm", "RPE 7", "Crête Pro (bleue)"],
      src: "Garmin Connect", mcp: "MCP · get_activity_fit_data", mcpWhy: "payload de plusieurs Mo", timeout: "timeout",
      dl: "download_fit.py --json", dlWhy: "garminconnect + jetons locaux · aucun mot de passe",
      out: ["activities/<id>.fit", "activities/fit/<id>.json"], outWhy: "échantillons en unités SI, jetables, jamais versionnés",
      streams: ["altitude", "allure", "FC", "cadence"], rate: "1 échantillon / s" },
    zones: { k: "02 · ZONES ET GAP", h: "Où la sortie s'est jouée.", zt: "Temps par zone de FC", method: "bornes : FC au seuil (172 bpm), 5 zones",
      names: ["Z1", "Z2", "Z3", "Z4", "Z5"], bounds: ["< 146", "146-155", "155-163", "163-172", "≥ 172"], min: "min",
      pt: "Allure et allure ajustée à la pente (GAP)", raw: "allure brute", gap: "GAP", fast: "plus rapide", slow: "plus lent", ax: "km",
      note: "Le GAP aplatit mentalement les côtes." },
    drift: { k: "03 · DÉRIVE CARDIAQUE", h: "Le découplage aérobie.", warm: "échauffement exclu", half: ["1ʳᵉ moitié", "2ᵉ moitié"],
      gap: "GAP", hr: "FC", ef: "EF", efDef: "EF = vitesse GAP / FC", dec: "découplage", ref: "repère 5 %", ax: "min",
      note: "Un repère issu d'un protocole contrôlé, pas une norme.", unit: "/km" },
    climbs: { k: "04 · MONTÉES ET DESCENTE", h: "Chaque montée a sa VAM.", cols: ["#", "km", "D+", "pente", "durée", "VAM"], vam: "VAM = D+ / durée, en m/h",
      dt: "Efficacité en descente", ds: "1,00 = référence plat", cls: ["-5 à -10 %", "-10 à -15 %", "-15 à -20 %"], hist: "vs précédent / meilleur : voir étape suivante" },
    durability: { k: "05 · DURABILITÉ ET RÉCUPÉRATION", h: "La fin de sortie, et le retour au calme.",
      thirds: ["1er tiers", "2e tiers", "dernier tiers"], warm: "échauffement exclu", fade: "ralentissement dernier vs 1er tiers", gap: "GAP", ef: "EF",
      read: "EF > GAP : la FC monte à allure presque égale.", hrr: "Récupération cardiaque (HRR)", hrrVal: "-24 bpm en 2 min", ax: "min après l'arrêt",
      ctx: "À lire face à des efforts équivalents, jamais seule.", missing: "Absente ? Mesure manquante, pas un signal." },
    energy: { k: "06 · LA DÉPENSE", h: "Garmin d'abord, le modèle en contrôle.", line: "Dépense : Garmin 1 380 kcal · modèle 1 436 kcal (+4 %)",
      g: "Garmin", m: "modèle", ref: "référence", ctl: "contrôle indépendant", band: "alerte au-delà de ±15 %", gauge: "écart modèle vs Garmin",
      notes: ["Modèle : RE3 (course) + Minetti (marche), échantillon par échantillon.", "Trail : le modèle est en général 3 à 5 % au-dessus de Garmin."],
      causes: "Écart > 15 % ? capteur FC optique · séance mal taguée · chaleur · poids périmé" },
    parts: { k: "07 · RÉPÉTITION PAR RÉPÉTITION", h: "L'analyse de portions.", ex: "Exemple : côtes 8 × 1 min",
      types: ["lignes droites", "montées", "sprints", "intervalles", "dernier km", "récupérations"],
      rep: "répétition", pace: "allure", hrmax: "FC max", cad: "cadence", sp: "vitesse", hr: "FC", ax: "min", pu: "/km" },
    compare: { k: "08 · LE MÊME PARCOURS", h: "Trois sorties, une progression.", course: "Boucle du Mont-Clair · 18,2 km · 820 m D+",
      dates: ["14 juin", "2 août", "27 septembre"], cols: ["sortie", "durée", "FC moy", "VAM montée 2", "vs précédent"], best: "meilleure",
      clock: "chrono", note: "Même ascension reconnue d'une sortie à l'autre (géométrie GPS, jamais exposée).", vamT: "VAM de la montée 2" },
  },
  en: {
    fit: { k: "01 · THE FIT FILE", h: "One measurement per second.", day: "Sunday, September 27 · trail",
      chips: ["18.2 km", "820 m gain", "avg HR 142 bpm", "RPE 7", "Crête Pro (blue)"],
      src: "Garmin Connect", mcp: "MCP · get_activity_fit_data", mcpWhy: "multi-MB payload", timeout: "timeout",
      dl: "download_fit.py --json", dlWhy: "garminconnect + local tokens · no password",
      out: ["activities/<id>.fit", "activities/fit/<id>.json"], outWhy: "SI-unit samples, disposable, never versioned",
      streams: ["elevation", "pace", "HR", "cadence"], rate: "1 sample / s" },
    zones: { k: "02 · ZONES AND GAP", h: "Where the run was decided.", zt: "Time per HR zone", method: "bounds: threshold HR (172 bpm), 5 zones",
      names: ["Z1", "Z2", "Z3", "Z4", "Z5"], bounds: ["< 146", "146-155", "155-163", "163-172", "≥ 172"], min: "min",
      pt: "Pace and grade-adjusted pace (GAP)", raw: "raw pace", gap: "GAP", fast: "faster", slow: "slower", ax: "km",
      note: "GAP flattens the climbs on paper." },
    drift: { k: "03 · HEART RATE DRIFT", h: "Aerobic decoupling.", warm: "warm-up excluded", half: ["1st half", "2nd half"],
      gap: "GAP", hr: "HR", ef: "EF", efDef: "EF = GAP speed / HR", dec: "decoupling", ref: "5% marker", ax: "min",
      note: "A marker from a controlled protocol, not a norm.", unit: "/km" },
    climbs: { k: "04 · CLIMBS AND DESCENT", h: "Every climb has its VAM.", cols: ["#", "km", "gain", "grade", "time", "VAM"], vam: "VAM = gain / time, in m/h",
      dt: "Downhill efficiency", ds: "1.00 = flat reference", cls: ["-5 to -10%", "-10 to -15%", "-15 to -20%"], hist: "vs previous / best: see next step" },
    durability: { k: "05 · DURABILITY AND RECOVERY", h: "The late run, and the cool-down.",
      thirds: ["1st third", "2nd third", "last third"], warm: "warm-up excluded", fade: "last third slowdown vs 1st", gap: "GAP", ef: "EF",
      read: "EF > GAP: HR rises at almost the same pace.", hrr: "Heart rate recovery (HRR)", hrrVal: "-24 bpm in 2 min", ax: "min after stopping",
      ctx: "Read against comparable efforts, never alone.", missing: "Missing? A missing measurement, not a signal." },
    energy: { k: "06 · ENERGY COST", h: "Garmin first, the model as a check.", line: "Energy: Garmin 1,380 kcal · model 1,436 kcal (+4%)",
      g: "Garmin", m: "model", ref: "reference", ctl: "independent check", band: "flag beyond ±15%", gauge: "model vs Garmin gap",
      notes: ["Model: RE3 (running) + Minetti (walking), sample by sample.", "Trail: the model usually sits 3 to 5% above Garmin."],
      causes: "Gap > 15%? optical HR sensor · mis-tagged session · heat · stale weight" },
    parts: { k: "07 · REP BY REP", h: "Segment analysis.", ex: "Example: hill reps 8 × 1 min",
      types: ["strides", "climbs", "sprints", "intervals", "last km", "recoveries"],
      rep: "rep", pace: "pace", hrmax: "max HR", cad: "cadence", sp: "speed", hr: "HR", ax: "min", pu: "/km" },
    compare: { k: "08 · SAME COURSE", h: "Three runs, one progression.", course: "Mont-Clair loop · 18.2 km · 820 m gain",
      dates: ["Jun 14", "Aug 2", "Sep 27"], cols: ["run", "time", "avg HR", "climb 2 VAM", "vs previous"], best: "best",
      clock: "clock", note: "Same ascent recognized from run to run (GPS geometry, never exposed).", vamT: "Climb 2 VAM" },
  },
};

/* ------------------------------ données de la sortie --------------------- */
const DIST = 18.2, DUR_MIN = 139;
const WP = [[0, 600], [1.9, 606], [5.1, 866], [6.6, 700], [7.0, 704], [9.9, 1014], [12.9, 800], [13.0, 800], [15.4, 980], [18.2, 604]];
const elevS = k => {
  let e = WP[WP.length - 1][1];
  for (let i = 0; i < WP.length - 1; i++) {
    const [a, ea] = WP[i], [b, eb] = WP[i + 1];
    if (k <= b) { const u = clamp((k - a) / (b - a)), s = u * u * (3 - 2 * u); e = lerp(ea, eb, s); break; }
  }
  return e + 5 * Math.sin(k * 5.3) + 3 * Math.sin(k * 11.7 + 1);
};
const gradeS = k => (elevS(Math.min(DIST, k + 0.15)) - elevS(Math.max(0, k - 0.15))) / ((Math.min(DIST, k + 0.15) - Math.max(0, k - 0.15)) * 10);
const paceG = g => g >= 0 ? 6 + 0.42 * g + 0.006 * g * g : 6 + 0.12 * g + 0.0045 * g * g;
const NS = 365;                                           // un point tous les 0,05 km
const NZ = (() => { const R = rng(71); return Array.from({ length: NS + 1 }, () => [R() + R() - 1, R() + R() - 1, R() + R() - 1]); })();
const at_ = k => clamp(Math.round(k / DIST * NS), 0, NS);
const paceRaw = k => paceG(gradeS(k)) * 1.04 + 0.35 * NZ[at_(k)][0];
const paceGap = k => 6.14 + 0.13 * (k / DIST) + 0.07 * NZ[at_(k)][1];
const hrAt = k => 127 + 2.4 * clamp(gradeS(k), -6, 11) + 6 * (k / DIST) + 3 * NZ[at_(k)][2];
const cadAt = k => 171 - 1.3 * Math.max(0, gradeS(k)) + 3 * NZ[at_(k)][1];
const CL = [[1.9, 5.1, 260, 26.5], [7.0, 9.9, 310, 32], [13.0, 15.4, 180, 20]];   // [début km, fin km, D+, durée min]
const vamOf = c => c[2] / (c[3] / 60);
const mmss = m => `${Math.floor(m)}:${String(Math.round((m - Math.floor(m)) * 60) % 60).padStart(2, "0")}`;
const hm = m => `${Math.floor(m / 60)} h ${String(Math.round(m % 60)).padStart(2, "0")}`;
const num = n => { const s = String(Math.round(n)); return LANG === "fr" ? s.replace(/\B(?=(\d{3})+(?!\d))/g, " ") : s.replace(/\B(?=(\d{3})+(?!\d))/g, ","); };
const dec = (x, n = 1) => (LANG === "fr" ? x.toFixed(n).replace(".", ",") : x.toFixed(n));
const ZCOL = ["#5fb8a0", C.accent, "#e5d25a", C.amber, C.red];
const ZMIN = [72, 35, 17, 11, 4];

/* Mini-profil de la sortie : sert de fil conducteur à plusieurs scènes. */
function profile(x, y, w, h, k, opt = {}) {
  const emin = 560, emax = 1060, X = d => x + d / DIST * w, Y = d => y + h - (elevS(d) - emin) / (emax - emin) * h;
  const pts = []; for (let d = 0; d <= DIST; d += 0.1) pts.push([X(d), Y(d)]);
  ctx.save(); ctx.globalAlpha *= opt.alpha ?? 1;
  ctx.beginPath(); ctx.moveTo(x, y + h); pts.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(x + w, y + h); ctx.closePath();
  const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, "rgba(30,77,59,0.65)"); g.addColorStop(1, "rgba(30,77,59,0.05)");
  ctx.fillStyle = g; ctx.fill(); ctx.restore();
  line(partial(pts, k), opt.color ?? C.soft, 2, opt.alpha ?? 1);
  return { X, Y };
}

/* ------------------------------ 1 · le fichier FIT ----------------------- */
function sFit(t, d, cues) {
  const s = S.fit, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.4);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  // carte de la sortie
  const kc = outCubic(seg(t, 0.3, 0.9));
  panel(80, 160, 1120, 62, { r: 16, alpha: kc });
  text(s.day, 104, 198, { size: 18, weight: 700, font: SORA, alpha: kc });
  let px = 450; s.chips.forEach((c, i) => { const k = outBack(seg(t, a0 + 0.3 + i * 0.25, a0 + 0.8 + i * 0.25)); if (k > 0) px += pill(c, px, 191, { size: 14, alpha: clamp(k), color: C.ink, fill: C.panel2, stroke: C.line }) + 10; });
  // le circuit : Garmin Connect -> MCP (timeout) / script local
  const kp = outCubic(seg(t, a1 - 1.2, a1 - 0.6));
  panel(80, 250, 460, 54, { r: 14, alpha: kp });
  text(s.src, 104, 284, { size: 18, weight: 700, font: SORA, alpha: kp });
  const km = outCubic(seg(t, a1 - 0.6, a1)), kx = outBack(seg(t, a1 + 0.6, a1 + 1.1));
  line([[200, 304], [200, 330]], C.faint, 1.5, km);
  panel(80, 330, 460, 78, { r: 14, alpha: km, fill: "rgba(240,122,95,0.06)", stroke: "rgba(240,122,95,0.45)" });
  text(s.mcp, 104, 362, { size: 15, font: MONO, weight: 600, alpha: km });
  text(s.mcpWhy, 104, 388, { size: 14, color: C.soft, alpha: km });
  if (kx > 0) pill("✕ " + s.timeout, 516, 369, { size: 14, align: "right", alpha: clamp(kx), color: C.red, stroke: C.red, fill: "rgba(13,20,16,0.8)" });
  const kd = outCubic(seg(t, a1 + 1.4, a1 + 2.0));
  line([[68, 277], [68, 469]], C.accent, 2, kd * 0.9); line([[68, 277], [80, 277]], C.accent, 2, kd * 0.9); line([[68, 469], [80, 469]], C.accent, 2, kd * 0.9);
  panel(80, 430, 460, 78, { r: 14, alpha: kd, fill: "rgba(163,230,53,0.07)", stroke: "rgba(163,230,53,0.5)" });
  text(s.dl, 104, 462, { size: 15, font: MONO, weight: 700, color: C.accent, alpha: kd });
  text(s.dlWhy, 104, 488, { size: 14, color: C.soft, alpha: kd });
  const ko = seg(t, a1 + 2.4, a1 + 3.0);
  s.out.forEach((o, i) => text(o, 104, 540 + i * 24, { size: 14, font: MONO, color: C.ink, alpha: ko }));
  text(s.outWhy, 104, 598, { size: 13, color: C.faint, alpha: ko });
  check(86, 535, 8, C.accent, ko, ko);
  // flux seconde par seconde
  const sx = 600, sw = 600, rows = 4, rh = 88, top = 252;
  const draw = seg(t, a1 + 2.0, d - 0.8);
  const fns = [
    k => elevS(k), k => paceRaw(k), k => hrAt(k), k => cadAt(k),
  ];
  const ranges = [[560, 1060], [4.5, 13], [118, 165], [140, 180]];
  const cols = [C.soft, C.teal, C.red, C.amber];
  const flip = [false, true, false, false];
  for (let r = 0; r < rows; r++) {
    const y = top + r * (rh + 8), ka = outCubic(seg(t, a1 + 1.8 + r * 0.25, a1 + 2.4 + r * 0.25));
    panel(sx, y, sw, rh, { r: 12, alpha: ka });
    text(s.streams[r], sx + 14, y + 22, { size: 13, font: MONO, color: C.faint, alpha: ka });
    const [lo, hi] = ranges[r], pts = [];
    for (let i = 0; i <= 300; i++) { const k = i / 300 * DIST, v = fns[r](k); let u = clamp((v - lo) / (hi - lo)); if (flip[r]) u = 1 - u; pts.push([sx + 12 + i / 300 * (sw - 24), y + rh - 10 - u * (rh - 34)]); }
    line(partial(pts, draw), cols[r], r === 0 ? 2 : 1.4, ka);
  }
  const hx = sx + 12 + draw * (sw - 24);
  if (draw > 0 && draw < 1) { line([[hx, top], [hx, top + rows * (rh + 8) - 8]], C.accent, 1.5, 0.7); }
  text(s.rate, sx + sw, 238, { size: 13, font: MONO, color: C.accent, align: "right", alpha: seg(t, a1 + 2.4, a1 + 3.0) });
}

/* ------------------------------ 2 · zones et GAP ------------------------- */
function sZones(t, d, cues) {
  const s = S.zones, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  // zones
  const kc = outCubic(seg(t, 0.3, 0.9));
  panel(80, 190, 540, 400, { r: 18, alpha: kc });
  text(s.zt, 104, 226, { size: 16, weight: 700, font: SORA, alpha: kc });
  const bx = 104, bw = 492, by = 258, tot = ZMIN.reduce((a, b) => a + b, 0);
  let acc = 0;
  ZMIN.forEach((m, i) => {
    const a = a0 + 0.6 + i * 0.35, k = outCubic(seg(t, a, a + 0.6));
    const w = m / tot * bw * k, x = bx + acc / tot * bw;
    ctx.save(); ctx.globalAlpha *= kc; rr(x, by, Math.max(0, w - 2), 46, 6); ctx.fillStyle = ZCOL[i]; ctx.fill(); ctx.restore();
    acc += m;
  });
  s.names.forEach((n, i) => {
    const a = a0 + 0.9 + i * 0.35, k = outCubic(seg(t, a, a + 0.6));
    const y = 342 + i * 40;
    dot(bx + 8, y - 5, 6, ZCOL[i], k);
    text(n, bx + 24, y, { size: 16, weight: 700, font: MONO, alpha: k });
    text(s.bounds[i], bx + 84, y, { size: 15, font: MONO, color: C.soft, alpha: k });
    text(`${ZMIN[i]} ${s.min}`, bx + 492, y, { size: 16, weight: 700, font: MONO, color: ZCOL[i], align: "right", alpha: k });
    ctx.save(); ctx.globalAlpha *= k * 0.5; rr(bx + 230, y - 14, 170 * ZMIN[i] / 72, 10, 5); ctx.fillStyle = ZCOL[i]; ctx.fill(); ctx.restore();
  });
  text(s.method, bx, 566, { size: 13, font: MONO, color: C.faint, alpha: seg(t, a0 + 2.6, a0 + 3.2) });
  // allure brute et GAP
  const px = 660, pw = 540, py = 190, ph = 400, x0 = px + 36, x1 = px + pw - 24, yb = py + ph - 70, yt = py + 84;
  const kp = outCubic(seg(t, 0.5, 1.1));
  panel(px, py, pw, ph, { r: 18, alpha: kp });
  text(s.pt, px + 24, py + 36, { size: 16, weight: 700, font: SORA, alpha: kp });
  const X = k => lerp(x0, x1, k / DIST), Y = p => lerp(yt, yb, (clamp(p, 4.5, 13) - 4.5) / 8.5);
  CL.forEach(c => { ctx.save(); ctx.globalAlpha *= kp; ctx.fillStyle = "rgba(163,230,53,0.07)"; ctx.fillRect(X(c[0]), yt - 10, X(c[1]) - X(c[0]), yb - yt + 20); ctx.restore(); });
  for (let k = 0; k <= 18; k += 3) text(String(k), X(k), yb + 24, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kp });
  text(s.ax, x1 + 4, yb + 24, { size: 12, font: MONO, color: C.faint, alpha: kp });
  text(s.fast, x0, yt - 14, { size: 12, font: MONO, color: C.faint, alpha: kp });
  text(s.slow, x0, yb - 8, { size: 12, font: MONO, color: C.faint, alpha: kp });
  const rawP = [], gapP = [];
  for (let i = 0; i <= 260; i++) { const k = i / 260 * DIST; rawP.push([X(k), Y(paceRaw(k))]); gapP.push([X(k), Y(paceGap(k))]); }
  line(partial(rawP, seg(t, a0 + 1.0, a0 + 3.4)), C.faint, 1.6, 0.95);
  line(partial(gapP, seg(t, a1 + 0.2, a1 + 2.6)), C.accent, 3.2);
  const kl = seg(t, a0 + 3.4, a0 + 4);
  line([[x0 + 160, py + 58], [x0 + 184, py + 58]], C.faint, 1.6, kl); text(s.raw, x0 + 194, py + 63, { size: 13, color: C.soft, alpha: kl });
  line([[x0 + 290, py + 58], [x0 + 314, py + 58]], C.accent, 3.2, kl); text(s.gap, x0 + 324, py + 63, { size: 13, weight: 700, color: C.accent, alpha: kl });
  para(s.note, px + 24, py + ph - 14, 480, { size: 14, color: C.soft, alpha: seg(t, a1 + 2.4, a1 + 3.2), lh: 20 });
}

/* ------------------------------ 3 · découplage --------------------------- */
const EF1 = 161.5 / 138, EF2 = 159.8 / 142, DECOUP = (EF1 - EF2) / EF1 * 100;   // 3,8 %
function sDrift(t, d, cues) {
  const s = S.drift, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const x0 = 100, x1 = 760, yt = 210, yb = 400, kp = outCubic(seg(t, 0.3, 0.9));
  panel(60, 190, 740, 232, { r: 18, alpha: kp });
  const X = m => lerp(x0, x1, m / DUR_MIN), Y = (v, lo, hi) => lerp(yb - 12, yt + 30, (v - lo) / (hi - lo));
  // échauffement et moitiés
  ctx.save(); ctx.globalAlpha *= kp; ctx.fillStyle = "rgba(231,237,233,0.06)"; ctx.fillRect(X(0), yt, X(10) - X(0), yb - yt); ctx.restore();
  text(s.warm, X(0), yb + 17, { size: 11, font: MONO, color: C.faint, alpha: kp });
  const mid = (10 + DUR_MIN) / 2;
  line([[X(mid), yt], [X(mid), yb]], C.faint, 1, kp, [4, 5]);
  [[10, mid, 0], [mid, DUR_MIN, 1]].forEach(([a, b, i]) => {
    const ka = outCubic(seg(t, a0 + 1.0 + i * 0.8, a0 + 1.6 + i * 0.8));
    ctx.save(); ctx.globalAlpha *= ka * kp; ctx.fillStyle = i ? "rgba(240,180,60,0.07)" : "rgba(163,230,53,0.06)"; ctx.fillRect(X(a), yt + 26, X(b) - X(a), yb - yt - 26); ctx.restore();
    text(s.half[i], (X(a) + X(b)) / 2, yt + 46, { size: 13, font: MONO, weight: 600, color: i ? C.amber : C.accent, align: "center", alpha: ka });
  });
  const hrP = [], gapP = [];
  for (let i = 0; i <= 200; i++) { const m = i / 200 * DUR_MIN, k = m / DUR_MIN * DIST; hrP.push([X(m), Y(125 + 11 * (m / DUR_MIN) + 2.2 * NZ[at_(k)][2], 118, 160)]); gapP.push([X(m), Y(6.15 + 0.1 * (m / DUR_MIN) + 0.05 * NZ[at_(k)][1], 6.6, 5.9)]); }
  line(partial(gapP, seg(t, 0.8, a0 + 2.6)), C.teal, 2.5, 1);
  line(partial(hrP, seg(t, 1.0, a0 + 3.0)), C.red, 2.5, 1);
  text(s.gap, x1 + 6, gapP[200][1] + 5, { size: 13, weight: 700, color: C.teal, alpha: kp });
  text(s.hr, x1 + 6, hrP[200][1] + 5, { size: 13, weight: 700, color: C.red, alpha: kp });
  for (let m = 0; m <= 120; m += 30) text(String(m), X(m), yb + 6 + 14, { size: 11, font: MONO, color: C.faint, align: "center", alpha: kp * 0 });
  // cartes EF
  [[0, 138, 161.5, EF1], [1, 142, 159.8, EF2]].forEach(([i, hr, gap, ef]) => {
    const a = a0 + 3.2 + i * 0.8, k = outCubic(seg(t, a, a + 0.6));
    if (k <= 0) return;
    const x = 60 + i * 374, y = 446 + (1 - k) * 12;
    panel(x, y, 366, 118, { r: 16, alpha: k, stroke: i ? "rgba(240,180,60,0.4)" : "rgba(163,230,53,0.4)" });
    text(s.half[i], x + 20, y + 30, { size: 13, font: MONO, color: i ? C.amber : C.accent, alpha: k });
    text(`${s.gap} ${mmss(1000 / gap)} ${s.unit}`, x + 20, y + 62, { size: 17, weight: 600, alpha: k });
    text(`${s.hr} ${hr} bpm`, x + 20, y + 90, { size: 17, weight: 600, alpha: k });
    text(`${s.ef} ${dec(ef, 3)}`, x + 346, y + 80, { size: 30, weight: 800, font: SORA, align: "right", color: i ? C.amber : C.accent, alpha: k });
  });
  text(s.efDef, 60, 592, { size: 13, font: MONO, color: C.faint, alpha: seg(t, a0 + 4.2, a0 + 4.8) });
  // jauge
  const gx = 850, gw = 330, gy = 330;
  const kg = outCubic(seg(t, a1 - 1.0, a1 - 0.2));
  panel(830, 190, 370, 374, { r: 18, alpha: kg });
  text(s.dec, 856, 228, { size: 14, font: MONO, color: C.faint, alpha: kg });
  const v = DECOUP * outCubic(seg(t, a1 - 0.2, a1 + 1.4));
  text(`${dec(v)} %`, 856, 296, { size: 60, weight: 800, font: SORA, color: C.accent, alpha: kg, spacing: "-2px" });
  ctx.save(); ctx.globalAlpha *= kg; rr(gx, gy + 20, gw, 14, 7); ctx.fillStyle = C.line; ctx.fill();
  rr(gx, gy + 20, gw * 5 / 10, 14, [7, 0, 0, 7]); ctx.fillStyle = "rgba(163,230,53,0.35)"; ctx.fill();
  rr(gx + gw * 0.5, gy + 20, gw * 0.5, 14, [0, 7, 7, 0]); ctx.fillStyle = "rgba(240,180,60,0.3)"; ctx.fill(); ctx.restore();
  line([[gx + gw * 0.5, gy + 10], [gx + gw * 0.5, gy + 44]], C.ink, 2, kg);
  text(s.ref, gx + gw * 0.5, gy + 66, { size: 13, font: MONO, color: C.soft, align: "center", alpha: kg });
  text("0", gx, gy + 66, { size: 12, font: MONO, color: C.faint, alpha: kg }); text("10 %", gx + gw, gy + 66, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kg });
  dot(gx + gw * v / 10, gy + 27, 11, C.accent, kg); dot(gx + gw * v / 10, gy + 27, 18, C.accent, 0.2 * kg);
  para(s.note, 856, 450, 320, { size: 15, color: C.soft, alpha: seg(t, a1 + 1.4, a1 + 2.2) });
}

/* ------------------------------ 4 · montées et descente ------------------ */
function sClimbs(t, d, cues) {
  const s = S.climbs, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const px = 80, pw = 1120, py = 166, ph = 118, kp = outCubic(seg(t, 0.3, 0.9));
  panel(px - 20, py - 12, pw + 40, ph + 46, { r: 18, alpha: kp });
  const P = profile(px, py, pw, ph, seg(t, 0.5, 1.8), { alpha: kp });
  for (let k = 0; k <= 18; k += 3) text(String(k), P.X(k), py + ph + 22, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kp });
  CL.forEach((c, i) => {
    const a = a0 + 0.8 + i * 1.1, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = "rgba(163,230,53,0.16)"; ctx.fillRect(P.X(c[0]), py - 4, P.X(c[1]) - P.X(c[0]), ph + 4); ctx.restore();
    const pts = []; for (let d2 = c[0]; d2 <= c[1]; d2 += 0.1) pts.push([P.X(d2), P.Y(d2)]);
    line(pts, C.accent, 3.5, k);
    dot((P.X(c[0]) + P.X(c[1])) / 2, py + 14, 11, C.accent, k); text(String(i + 1), (P.X(c[0]) + P.X(c[1])) / 2, py + 19, { size: 14, weight: 800, font: SORA, color: C.deep, align: "center", alpha: k });
  });
  // tableau des montées
  const tx = 80, ty = 382, cw = [50, 120, 100, 170, 100, 110];
  const kt = outCubic(seg(t, a0 + 0.6, a0 + 1.2));
  panel(tx - 20, ty - 38, 700, 236, { r: 18, alpha: kt });
  let cx = tx; s.cols.forEach((c, i) => { text(c, cx, ty - 8, { size: 12, font: MONO, color: C.faint, alpha: kt }); cx += cw[i]; });
  line([[tx, ty + 4], [tx + 640, ty + 4]], C.line, 1, kt);
  CL.forEach((c, i) => {
    const a = a0 + 1.4 + i * 1.1, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    const y = ty + 40 + i * 44, gr = c[2] / ((c[1] - c[0]) * 10);
    const vals = [String(i + 1), `${dec(c[0])}-${dec(c[1])}`, `+${c[2]} m`, `${dec(gr)} % · ${gr >= 10 ? "10-15" : "5-10"}`, mmss(c[3]).replace(":", "'") + '"', `${Math.round(vamOf(c))} m/h`];
    let x = tx;
    vals.forEach((v, j) => { text(v, x, y, { size: 15, weight: j === 5 ? 800 : 500, font: j === 0 ? SORA : MONO, color: j === 5 ? C.accent : C.ink, alpha: k }); x += cw[j]; });
  });
  text(s.vam, tx, ty + 192, { size: 13, font: MONO, color: C.faint, alpha: seg(t, a0 + 4.4, a0 + 5) });
  // efficacité en descente
  const dx = 800, kd = outCubic(seg(t, a1 - 0.6, a1 + 0.2));
  panel(dx - 20, ty - 38, 420, 236, { r: 18, alpha: kd });
  text(s.dt, dx, ty - 8, { size: 15, weight: 700, font: SORA, alpha: kd });
  text(s.ds, dx + 380, ty - 8, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kd });
  const eff = [1.06, 1.01, 0.93];
  s.cls.forEach((c, i) => {
    const a = a1 + 0.4 + i * 0.5, k = outCubic(seg(t, a, a + 0.6)), y = ty + 28 + i * 46;
    text(c, dx, y + 14, { size: 14, font: MONO, color: C.soft, alpha: k });
    const bx = dx + 130, bw = 190;
    line([[bx + bw * 0.5, y - 4], [bx + bw * 0.5, y + 24]], C.faint, 1, k, [3, 3]);
    ctx.save(); ctx.globalAlpha *= k; rr(bx, y + 3, bw * clamp(eff[i] / 2) * k, 18, 5); ctx.fillStyle = eff[i] >= 1 ? C.teal : C.amber; ctx.fill(); ctx.restore();
    text(dec(eff[i], 2), dx + 380, y + 18, { size: 16, weight: 700, font: MONO, align: "right", alpha: k });
  });
  text(s.hist, dx, ty + 192, { size: 12, font: MONO, color: C.faint, alpha: seg(t, a1 + 2.2, a1 + 2.8) });
}

/* ------------------------------ 5 · durabilité et HRR -------------------- */
const G1 = 163.0, G3 = 159.6, E1 = G1 / 138, E3 = G3 / 141.5;
const FADE_GAP = (G1 - G3) / G1 * 100, FADE_EF = (E1 - E3) / E1 * 100;
function sDurability(t, d, cues) {
  const s = S.durability, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5.4);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const kc = outCubic(seg(t, 0.3, 0.9));
  panel(60, 190, 620, 400, { r: 18, alpha: kc });
  // trois tiers sur le profil
  const P = profile(90, 222, 560, 90, seg(t, 0.4, 1.4), { alpha: kc });
  const t0 = 10 / DUR_MIN * DIST;
  ctx.save(); ctx.globalAlpha *= kc; ctx.fillStyle = "rgba(231,237,233,0.07)"; ctx.fillRect(P.X(0), 218, P.X(t0) - P.X(0), 98); ctx.restore();
  const edges = [t0, t0 + (DIST - t0) / 3, t0 + 2 * (DIST - t0) / 3, DIST];
  const tcol = [C.teal, C.soft, C.amber];
  s.thirds.forEach((n, i) => {
    const a = a0 + 0.8 + i * 0.7, k = outCubic(seg(t, a, a + 0.5));
    ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = tcol[i] + "22"; ctx.fillRect(P.X(edges[i]), 218, P.X(edges[i + 1]) - P.X(edges[i]), 98); ctx.restore();
    line([[P.X(edges[i]), 218], [P.X(edges[i]), 316]], tcol[i], 1.5, k);
    text(n, (P.X(edges[i]) + P.X(edges[i + 1])) / 2, 336, { size: 13, font: MONO, color: tcol[i], align: "center", alpha: k });
  });
  text(s.warm, P.X(0), 214, { size: 11, font: MONO, color: C.faint, alpha: kc * seg(t, a0 + 0.8, a0 + 1.4) });
  // fades
  text(s.fade, 90, 384, { size: 13, font: MONO, color: C.faint, alpha: seg(t, a0 + 3.0, a0 + 3.6) });
  [[s.gap, FADE_GAP, C.teal, G1, G3, true], [s.ef, FADE_EF, C.amber, E1, E3, false]].forEach(([n, f, c, v1, v3, isGap], i) => {
    const a = a0 + 3.2 + i * 0.8, k = outCubic(seg(t, a, a + 0.6));
    if (k <= 0) return;
    const y = 400 + i * 80;
    text(n, 90, y + 40, { size: 20, weight: 800, font: SORA, color: c, alpha: k });
    text(isGap ? `${mmss(1000 / v1)} → ${mmss(1000 / v3)} ${S.drift.unit}` : `${dec(v1, 3)} → ${dec(v3, 3)}`, 170, y + 38, { size: 16, font: MONO, color: C.soft, alpha: k });
    text(`+${dec(f * k)} %`, 640, y + 42, { size: 32, weight: 800, font: SORA, color: c, align: "right", alpha: k });
  });
  para(s.read, 90, 570, 520, { size: 14, color: C.soft, alpha: seg(t, a0 + 5.0, a0 + 5.8), lh: 20 });
  // HRR
  const hx = 710, hw = 490, kh = outCubic(seg(t, a1 - 0.8, a1));
  panel(hx, 190, hw, 400, { r: 18, alpha: kh });
  text(s.hrr, hx + 24, 228, { size: 16, weight: 700, font: SORA, alpha: kh });
  const x0 = hx + 50, x1 = hx + hw - 30, yt = 270, yb = 440;
  const X = m => lerp(x0, x1, m / 3), Y = v => lerp(yb, yt, (v - 120) / 36);
  [120, 140].forEach(v => { line([[x0, Y(v)], [x1, Y(v)]], "rgba(231,237,233,0.07)", 1, kh); text(String(v), x0 - 8, Y(v) + 4, { size: 11, font: MONO, color: C.faint, align: "right", alpha: kh }); });
  [0, 1, 2, 3].forEach(m => text(String(m), X(m), yb + 22, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kh }));
  text(s.ax, x1, yb + 42, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kh });
  const hp = []; for (let i = 0; i <= 90; i++) { const m = i / 30; hp.push([X(m), Y(126 + 24 * Math.exp(-m * 1.25 * (m < 2 ? 1 : 1)))]); }
  hp.forEach((p, i) => { const m = i / 30; p[1] = Y(125 + 25 * Math.exp(-m * 0.99)); });
  const dr = inOut(seg(t, a1, a1 + 2.2));
  line(partial(hp, dr), C.red, 3, 1);
  dot(hp[0][0], hp[0][1], 5, C.red, kh); text("150", hp[0][0] + 10, hp[0][1] - 8, { size: 13, font: MONO, color: C.soft, alpha: kh });
  const k2 = seg(t, a1 + 2.0, a1 + 2.6);
  if (k2 > 0) {
    const p2 = hp[60]; dot(p2[0], p2[1], 5, C.red, k2);
    line([[p2[0], hp[0][1]], [p2[0], p2[1]]], C.amber, 2, k2); line([[hp[0][0], hp[0][1]], [p2[0], hp[0][1]]], C.amber, 1.5, k2, [4, 4]);
    text("126", p2[0] + 10, p2[1] + 22, { size: 13, font: MONO, color: C.soft, alpha: k2 });
    pill("HRR " + s.hrrVal, hx + hw - 36, 312, { size: 15, align: "right", alpha: k2, color: C.amber, stroke: C.amber, fill: "rgba(13,20,16,0.8)" });
  }
  const kn = seg(t, a1 + 3.0, a1 + 3.8);
  para(s.ctx, hx + 24, 508, hw - 48, { size: 14, color: C.soft, alpha: kn, lh: 20 });
  para(s.missing, hx + 24, 560, hw - 48, { size: 13, color: C.faint, alpha: kn, lh: 18 });
}

/* ------------------------------ 6 · dépense ------------------------------ */
const KG = 1380, KM_ = 1436, DEL = (KM_ / KG - 1) * 100;
function sEnergy(t, d, cues) {
  const s = S.energy, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  // la ligne du retour de séance
  const kt = outCubic(seg(t, 0.3, 0.9));
  terminal(80, 168, 1120, 96, t, [{ s: s.line, c: C.ink, w: 700, a: a0 + 0.2, b: a0 + 3.8 }], { alpha: kt, size: 22, lh: 40, title: "Claude Code · coach" });
  // deux barres
  const bx = 120, by = 300, bh = 206;
  panel(80, 290, 480, 300, { r: 18, alpha: kt });
  [[s.g, KG, C.accent, s.ref, 0], [s.m, KM_, C.teal, s.ctl, 1]].forEach(([n, v, c, sub, i]) => {
    const a = a0 + 1.2 + i * 0.9, k = outCubic(seg(t, a, a + 0.9)), x = bx + 20 + i * 220, h = (v / 1500) * bh * k;
    ctx.save(); ctx.globalAlpha *= kt; rr(x, by + 30 + bh - h, 140, h, 8); ctx.fillStyle = c; ctx.globalAlpha *= 0.85; ctx.fill(); ctx.restore();
    text(`${num(v * k)} kcal`, x + 70, by + 30 + bh - h - 12, { size: 20, weight: 800, font: SORA, align: "center", alpha: k });
    text(n, x + 70, by + 30 + bh + 22, { size: 16, weight: 700, align: "center", alpha: k });
    text(sub, x + 70, by + 30 + bh + 42, { size: 12, font: MONO, color: C.faint, align: "center", alpha: k });
  });
  // jauge d'écart
  const gx = 640, gw = 520, gy = 372, kg = outCubic(seg(t, a1 - 0.8, a1));
  panel(600, 290, 600, 300, { r: 18, alpha: kg });
  text(s.gauge, 630, 328, { size: 14, font: MONO, color: C.faint, alpha: kg });
  const X = v => gx + (v + 20) / 40 * gw;
  ctx.save(); ctx.globalAlpha *= kg; rr(gx, gy, gw, 18, 9); ctx.fillStyle = C.line; ctx.fill();
  ctx.fillStyle = "rgba(240,180,60,0.35)"; ctx.fillRect(gx + 2, gy, X(-15) - gx - 2, 18); ctx.fillRect(X(15), gy, gx + gw - X(15) - 2, 18);
  ctx.fillStyle = "rgba(163,230,53,0.22)"; ctx.fillRect(X(-15), gy, X(15) - X(-15), 18); ctx.restore();
  [-15, 0, 15].forEach(v => { line([[X(v), gy - 6], [X(v), gy + 24]], v === 0 ? C.ink : C.amber, 1.5, kg); text(`${v > 0 ? "+" : ""}${v} %`, X(v), gy + 44, { size: 12, font: MONO, color: C.soft, align: "center", alpha: kg }); });
  const dv = DEL * outCubic(seg(t, a1, a1 + 1.4));
  dot(X(dv), gy + 9, 12, C.accent, kg); dot(X(dv), gy + 9, 20, C.accent, 0.2 * kg);
  text(`+${dec(dv, 0)} %`, X(dv), gy - 22, { size: 22, weight: 800, font: SORA, color: C.accent, align: "center", alpha: kg });
  text(s.band, gx + gw, gy + 70, { size: 13, font: MONO, color: C.amber, align: "right", alpha: kg });
  s.notes.forEach((n, i) => para(n, 630, 470 + i * 44, 540, { size: 14, color: C.soft, alpha: seg(t, a1 + 1.4 + i * 0.6, a1 + 2.0 + i * 0.6), lh: 20 }));
  text(s.causes, 80, 622, { size: 13, color: C.faint, alpha: seg(t, a1 + 2.8, a1 + 3.5) });
}

/* ------------------------------ 7 · répétition par répétition ------------ */
const REP_T0 = 12, REP_ON = 1, REP_OFF = 1.5;   // min
const REP_PACE = [4.05, 4.04, 4.08, 4.07, 4.10, 4.12, 4.14, 4.18], REP_HR = [165, 168, 169, 171, 172, 173, 174, 174], REP_CAD = [184, 184, 183, 183, 182, 182, 181, 180];
function sParts(t, d, cues) {
  const s = S.parts, a0 = at(cues, 0, 0.6);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  let px = 80; s.types.forEach((c, i) => { const k = outBack(seg(t, 0.4 + i * 0.12, 0.9 + i * 0.12)); if (k > 0) px += pill(c, px, 176, { size: 14, alpha: clamp(k), color: C.ink, fill: C.panel2, stroke: C.line }) + 10; });
  text(S.parts.ex, 1200, 181, { size: 13, font: MONO, color: C.amber, align: "right", alpha: seg(t, 0.8, 1.4) });
  // trace
  const x0 = 100, x1 = 1180, yt = 220, yb = 400, TOT = 40, kp = outCubic(seg(t, 0.3, 0.9));
  panel(60, 204, 1160, 212, { r: 18, alpha: kp });
  const X = m => lerp(x0, x1, m / TOT);
  const R = rng(5);
  const spd = [], hr = [];
  for (let i = 0; i <= 400; i++) {
    const m = i / 400 * TOT; let v = 1000 / 6.6 / 60, h = 118 + 6 * (m / TOT);   // m/s environ ; allure 6:36 en trottinant
    let rep = -1;
    for (let r = 0; r < 8; r++) { const a = REP_T0 + r * (REP_ON + REP_OFF); if (m >= a && m < a + REP_ON) rep = r; }
    if (rep >= 0) { v = 1000 / REP_PACE[rep] / 60; }
    spd.push(v + (R() - 0.5) * 0.25); hr.push(h);
  }
  // FC lissée, montant pendant les répétitions
  let hh = 122; const hrS = [];
  for (let i = 0; i <= 400; i++) { const m = i / 400 * TOT; let tgt = 126; for (let r = 0; r < 8; r++) { const a = REP_T0 + r * (REP_ON + REP_OFF); if (m >= a && m < a + REP_ON + 0.3) tgt = REP_HR[r] - 4; } hh += (tgt - hh) * 0.09; hrS.push(hh); }
  const pts = spd.map((v, i) => [X(i / 400 * TOT), lerp(yb, yt + 28, clamp((v - 1.9) / (4.4 - 1.9)))]);
  const pts2 = hrS.map((v, i) => [X(i / 400 * TOT), lerp(yb, yt + 28, clamp((v - 110) / (180 - 110)))]);
  const draw = seg(t, 0.8, a0 + 3.2);
  line(partial(pts, draw), C.teal, 1.8); line(partial(pts2, draw), C.red, 2.2);
  text(s.sp, x0, yt + 20, { size: 12, font: MONO, color: C.teal, alpha: kp }); text(s.hr, x0 + 70, yt + 20, { size: 12, font: MONO, color: C.red, alpha: kp });
  [0, 10, 20, 30, 40].forEach(m => text(String(m), X(m), yb + 6 + 8, { size: 11, font: MONO, color: C.faint, align: "center", alpha: kp * 0 }));
  // répétitions détectées
  for (let r = 0; r < 8; r++) {
    const a = a0 + 3.4 + r * 0.45, k = outCubic(seg(t, a, a + 0.4)), m0 = REP_T0 + r * (REP_ON + REP_OFF);
    if (k <= 0) continue;
    ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = "rgba(163,230,53,0.2)"; ctx.fillRect(X(m0), yt + 6, X(m0 + REP_ON) - X(m0), yb - yt - 6); ctx.restore();
    text(String(r + 1), (X(m0) + X(m0 + REP_ON)) / 2, yt - 4, { size: 13, weight: 800, font: SORA, color: C.accent, align: "center", alpha: k });
  }
  // fiches
  const cw = (1120 - 7 * 8) / 8;
  for (let r = 0; r < 8; r++) {
    const a = a0 + 3.9 + r * 0.45, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) continue;
    const x = 80 + r * (cw + 8), y = 440 + (1 - k) * 12;
    panel(x, y, cw, 140, { r: 14, alpha: k, stroke: r === 7 ? "rgba(240,180,60,0.5)" : C.line });
    text(`${s.rep} ${r + 1}`, x + 14, y + 26, { size: 12, font: MONO, color: C.accent, alpha: k });
    text(mmss(REP_PACE[r]), x + 14, y + 62, { size: 22, weight: 800, font: SORA, alpha: k });
    text(s.pu, x + 14 + measure(mmss(REP_PACE[r]), 22, 800, SORA) + 4, y + 62, { size: 12, font: MONO, color: C.faint, alpha: k });
    text(`${s.hrmax} ${REP_HR[r]}`, x + 14, y + 94, { size: 14, font: MONO, color: C.soft, alpha: k });
    text(`${s.cad} ${REP_CAD[r]}`, x + 14, y + 118, { size: 14, font: MONO, color: C.soft, alpha: k });
  }
}

/* ------------------------------ 8 · le même parcours --------------------- */
const RUNS = [{ m: 151, hr: 147, vam: 540, c: "#7d8e85" }, { m: 146, hr: 145, vam: 561, c: C.teal }, { m: 139, hr: 142, vam: 581, c: C.accent }];
function sCompare(t, d, cues) {
  const s = S.compare, a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 6);
  kicker(s.k, seg(t, 0, 0.4)); headline(s.h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  text(s.course, 80, 172, { size: 15, font: MONO, color: C.soft, alpha: seg(t, 0.4, 1.0) });
  // trois coureurs sur le même profil, au même chrono : une piste par sortie
  const px = 200, pw = 950, py = 190, ph = 70, kp = outCubic(seg(t, 0.3, 0.9));
  panel(60, 182, 1160, 190, { r: 18, alpha: kp });
  const P = profile(px, py + 4, pw, ph, seg(t, 0.4, 1.4), { alpha: kp });
  const rEnd = Math.min(a1 - 0.1, d - 3), el = 152 * seg(t, 1.0, rEnd);   // chrono (min)
  RUNS.forEach((r, i) => {
    const ly = py + ph + 22 + i * 24, k = clamp(el / r.m);
    line([[px, ly], [px + pw, ly]], "rgba(231,237,233,0.12)", 2, kp);
    line([[px, ly], [px + pw * k, ly]], r.c, 3, kp);
    dot(px + pw * k, ly, 7, r.c, kp); dot(px + pw * k, ly, 13, r.c, 0.22 * kp);
    text(s.dates[i], px - 14, ly + 4, { size: 12, font: MONO, color: r.c, align: "right", alpha: kp });
    if (el >= r.m) text(hm(r.m), px + pw + 12, ly + 4, { size: 13, font: MONO, weight: 700, color: r.c, alpha: clamp((el - r.m) / 4) });
  });
  text(`${s.clock} ${hm(Math.min(el, 152))}`, 1190, 210, { size: 15, weight: 700, font: MONO, color: C.soft, align: "right", alpha: kp });
  // tableau
  const tx = 80, ty = 424, cw = [170, 110, 110, 160, 150];
  const kt = outCubic(seg(t, rEnd - 0.6, rEnd + 0.2));
  panel(60, 392, 760, 196, { r: 18, alpha: kt });
  let cx = tx; s.cols.forEach((c, i) => { text(c, cx, ty, { size: 12, font: MONO, color: C.faint, alpha: kt }); cx += cw[i]; });
  line([[tx, ty + 12], [tx + 740, ty + 12]], C.line, 1, kt);
  RUNS.forEach((r, i) => {
    const a = rEnd - 0.2 + i * 0.5, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    const y = ty + 48 + i * 44, vs = i ? r.m - RUNS[i - 1].m : null;
    dot(tx + 5, y - 5, 6, r.c, k);
    const vals = [s.dates[i], hm(r.m), `${r.hr} bpm`, `${r.vam} m/h`, i ? `${vs} min` : "—"];
    let x = tx + 22;
    vals.forEach((v, j) => { text(v, j ? x - 22 : x, y, { size: 16, weight: j === 3 || i === 2 ? 700 : 500, font: j ? MONO : INTER, color: i === 2 && j > 0 ? C.accent : C.ink, alpha: k }); x += cw[j]; });
    if (i === 2) pill(s.best, tx + 622, y - 6, { size: 12, alpha: k });
  });
  // progression de la VAM
  const vx = 860, vw = 340, kv = outCubic(seg(t, a1 - 0.6, a1 + 0.2));
  panel(840, 392, 380, 196, { r: 18, alpha: kv });
  text(s.vamT, vx, 426, { size: 14, weight: 700, font: SORA, alpha: kv });
  const X = i => vx + 30 + i * (vw - 90) / 2, Y = v => lerp(536, 462, (v - 520) / 80);
  const vp = RUNS.map((r, i) => [X(i), Y(r.vam)]);
  line(partial(vp, seg(t, a1, a1 + 1.6)), C.accent, 3, 1);
  vp.forEach((p, i) => { const k = seg(t, a1 + i * 0.7, a1 + i * 0.7 + 0.4); dot(p[0], p[1], 6, RUNS[i].c, k); text(`${RUNS[i].vam}`, p[0], p[1] - 14, { size: 13, weight: 700, font: MONO, align: "center", alpha: k }); text(s.dates[i], p[0], 566, { size: 11, font: MONO, color: C.faint, align: "center", alpha: k }); });
  para(s.note, 80, 616, 1100, { size: 13, color: C.faint, alpha: seg(t, a1 + 2.0, a1 + 2.8), lh: 18 });
}

ARC.episode({
  n: 7, slug: "analyse-seance",
  strings: STR,
  shots: [],
  scenes: { fit: sFit, zones: sZones, drift: sDrift, climbs: sClimbs, durability: sDurability, energy: sEnergy, parts: sParts, compare: sCompare },
});
})();
