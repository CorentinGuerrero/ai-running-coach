/* Le Sentier · étape 9 — « Usure » : kilométrage des chaussures, alerte de seuil,
 * inspection photo, indices de foulée, foulée mesurée, kits et bilan de carrière.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}].
 * Athlète et chiffres fictifs (bible de la série : Camille, mardi 29 septembre 2026).
 * Helpers locaux : semelle stylisée (sole), vues du protocole photo, icônes d'équipement. */
"use strict";
(() => {
const BLUE = "#6aa7e0";

const STR = {
  fr: {
    k1: "01 · LE KILOMÉTRAGE", h1: "612 km sur 700.",
    pair: "Crête Pro (bleue)", thr: "seuil d'alerte 700 km", eta: "≈ 2 sem.", sun: "Dimanche 27 · 18,2 km",
    cap1: "Tableau de bord · la séance du dimanche 27", cap2: "Tableau de bord · Matériel",
    k2: "02 · LE SEUIL", h2: "Une seule fois.",
    sync1: "07:15", sync2: "14:15",
    r1: ["Séances : 1 nouvelle — trail 28 km / 910 m D+", "Sommeil : 7 h 20, score 78", "HRV : 58 ms — équilibrée (baseline 52-70)", "Readiness : 71", "Alerte : Chaussures : Crête Pro (bleue) a atteint son seuil (702 km)"],
    r2: ["Séances : à jour", "Alerte : aucune"], again: "même séance, même seuil : rien n'est répété", bySession: "le franchissement est identifié par la séance, pas par la date",
    k3: "03 · /INSPECTION", h3: "Cinq vues.", every: "≈ tous les 200 km · jamais imposée",
    cmd: "/inspection", reply: "Paire proposée : Crête Pro (bleue) — seuil franchi",
    rows: [["Les deux semelles, à plat", "gomme, crampons"], ["Le profil, à hauteur de semelle", "plis de la mousse"], ["L'arrière, sur surface plane", "inclinaison du talon"], ["La tige, vue de dessus", "déchirures, bout"], ["Une pièce dans le cadre", "l'échelle : sans elle, aucun mm"]],
    scaleTag: "échelle",
    k4: "04 · LE VERDICT", h4: "Quatre couleurs.",
    grid: [["green", "Bon état", "rien d'inquiétant"], ["yellow", "Usure visible", "à surveiller"], ["orange", "Usure avancée", "gomme lisse, mousse ridée"], ["red", "Fin de vie", "mousse ou plaque exposée"]],
    cmp: "vs 20 août : talon gauche « légère » → « modérée » (+170 km)", cap3: "Tableau de bord · Inspections de la paire",
    k5: "05 · LES INDICES", h5: "Un indice, pas un diagnostic.",
    left: "pied gauche", right: "pied droit", zone: "talon postéro-latéral", hint: "indice : attaque talon",
    cav: [["Zone d'usure → indice", "talon postéro-latéral → attaque talon (fréquent, normal)"], ["Un indice, jamais un diagnostic", "pile haute, rocker, mousses : l'usure est un signal faible"], ["Pas de mm sans échelle", "lug_depth_mm refusé sans scale_reference"], ["Jamais de changement de foulée sur photo", "asymétrie marquée ou douleur : kiné, analyse de foulée"]],
    k6: "06 · LA MESURE", h6: "La mesure prime.",
    meas: "Mesuré par la montre", guess: "Deviné d'après les photos",
    mrows: [["Temps de contact au sol", "242 ms"], ["Balance du temps de contact", "50,4 %"], ["Oscillation verticale", "8,1 cm"], ["Cadence (deux pieds)", "172 pas/min"]],
    chips: ["indice : attaque talon", "asymétrie légère — pied gauche plus usé"],
    bal: "Balance : écart à 50 %, jamais un pied", band: "±1 pt",
    dis: "Désaccord entre sources : jamais arbitré en silence — la mesure prime.", conf: "confiance faible sous 5 séances mesurées ou 3 inspections",
    unav: "indisponible",
    none: "Sans mesure (capteur sans balance, source intervals.icu) : « indisponible », jamais inventée.",
    k7: "07 · HORS CHAUSSURES", h7: "Des kits, des seuils.",
    kit: "kit : trail-long", items: ["Poche à eau 2 L", "Frontale Aube", "Bâtons Cime", "Couverture de survie"],
    cap4: "Tableau de bord · Équipement",
    syncT: "À la synchronisation", syncL: "Matériel : Bâtons Cime a atteint son seuil (800 km)", syncS: "km, h ou séances : une seule fois. Seuils en jours : tableau de bord, /week.",
    nightT: "Avant une sortie de nuit", nightL: "Frontale Aube : vérifier la batterie.", nightS: "un rappel, jamais un blocage",
    k8: "08 · BILAN DE CARRIÈRE", h8: "Une paire prend sa retraite.",
    old: "Vieille Grimpeuse", oldKm: "392 km", retired: "RETIRÉE",
    gc: "python3 scripts/arc_index.py gear-career --gear vieille-grimpeuse",
    gcOut: ["km · séances · période · courses", "meilleurs efforts · plus longue sortie · dernière inspection"],
    cap5: "Fiche d'une paire (ici la Crête Pro) · Tableau de bord",
  },
  en: {
    k1: "01 · THE KILOMETRES", h1: "612 km out of 700.",
    pair: "Crête Pro (bleue)", thr: "alert threshold 700 km", eta: "≈ 2 wk", sun: "Sunday 27 · 18.2 km",
    cap1: "Dashboard (French UI) · Sunday 27 run", cap2: "Dashboard (French UI) · Gear",
    k2: "02 · THE THRESHOLD", h2: "Once only.",
    sync1: "07:15", sync2: "14:15",
    r1: ["Sessions: 1 new — trail 28 km / 910 m gain", "Sleep: 7 h 20, score 78", "HRV: 58 ms — balanced (baseline 52-70)", "Readiness: 71", "Alert: Shoes: Crête Pro (bleue) reached its threshold (702 km)"],
    r2: ["Sessions: up to date", "Alert: none"], again: "same session, same threshold: nothing repeated", bySession: "the crossing is identified by the session, not by the date",
    k3: "03 · /INSPECTION", h3: "Five views.", every: "≈ every 200 km · never imposed",
    cmd: "/inspection", reply: "Suggested pair: Crête Pro (bleue) — threshold crossed",
    rows: [["Both soles, flat", "rubber, lugs"], ["The profile, at sole height", "foam creases"], ["The heel, on a flat surface", "heel tilt"], ["The upper, from above", "tears, toe box"], ["A coin in the frame", "the scale: no mm without it"]],
    scaleTag: "scale",
    k4: "04 · THE VERDICT", h4: "Four colours.",
    grid: [["green", "Good", "nothing to worry about"], ["yellow", "Visible wear", "keep an eye on it"], ["orange", "Advanced wear", "smooth rubber, wrinkled foam"], ["red", "End of life", "foam or plate showing"]],
    cmp: "vs Aug 20: left heel “light” → “moderate” (+170 km)", cap3: "Dashboard (French UI) · the pair's inspections",
    k5: "05 · THE HINTS", h5: "A hint, not a diagnosis.",
    left: "left foot", right: "right foot", zone: "posterolateral heel", hint: "hint: heel strike",
    cav: [["Wear zone → hint", "posterolateral heel → heel strike (common, normal)"], ["A hint, never a diagnosis", "tall stacks, rockers, foams: wear is a weak signal"], ["No mm without a scale", "lug_depth_mm is refused without scale_reference"], ["Never a stride change from a photo", "marked asymmetry or pain: physio, gait lab"]],
    k6: "06 · THE MEASUREMENT", h6: "Measurement wins.",
    meas: "Measured by the watch", guess: "Guessed from the photos",
    mrows: [["Ground contact time", "242 ms"], ["Contact time balance", "50.4 %"], ["Vertical oscillation", "8.1 cm"], ["Cadence (both feet)", "172 spm"]],
    chips: ["hint: heel strike", "light asymmetry — left foot more worn"],
    bal: "Balance: gap from 50 %, never a foot", band: "±1 pt",
    dis: "Sources disagree: never settled silently — the measurement wins.", conf: "low confidence under 5 measured runs or 3 inspections",
    unav: "unavailable",
    none: "No measurement (sensor without balance, intervals.icu source): “unavailable”, never made up.",
    k7: "07 · BEYOND SHOES", h7: "Kits, thresholds.",
    kit: "kit: trail-long", items: ["Water bladder 2 L", "Head torch Aube", "Poles Cime", "Survival blanket"],
    cap4: "Dashboard (French UI) · Equipment",
    syncT: "At sync time", syncL: "Gear: Poles Cime reached its threshold (800 km)", syncS: "km, hours or sessions: once only. Day thresholds: dashboard, /week.",
    nightT: "Before a night run", nightL: "Head torch Aube: check the battery.", nightS: "a reminder, never a blocker",
    k8: "08 · CAREER SUMMARY", h8: "A pair retires.",
    old: "Vieille Grimpeuse", oldKm: "392 km", retired: "RETIRED",
    gc: "python3 scripts/arc_index.py gear-career --gear vieille-grimpeuse",
    gcOut: ["km · sessions · period · races", "best efforts · longest run · last inspection"],
    cap5: "A pair's page (here the Crête Pro) · Dashboard (French UI)",
  },
};

/* ------------------------- dessins : semelle et vues ------------------------- */
function solePath() {
  ctx.beginPath();
  ctx.moveTo(2, 152);
  ctx.bezierCurveTo(-38, 152, -48, 128, -47, 100);
  ctx.bezierCurveTo(-46, 70, -28, 50, -26, 22);
  ctx.bezierCurveTo(-24, -10, -52, -35, -56, -78);
  ctx.bezierCurveTo(-60, -125, -40, -162, -4, -166);
  ctx.bezierCurveTo(30, -168, 62, -150, 64, -104);
  ctx.bezierCurveTo(66, -62, 48, -30, 48, 10);
  ctx.bezierCurveTo(48, 50, 56, 76, 54, 104);
  ctx.bezierCurveTo(52, 136, 36, 152, 2, 152);
  ctx.closePath();
}
/* Semelle vue de dessous. side = +1 (droite) / -1 (gauche, miroir). wear = [[x, y, r, "#rrggbb", alpha]]. */
function sole(cx, cy, s, side, o = {}) {
  ctx.save(); ctx.globalAlpha *= o.alpha ?? 1;
  ctx.translate(cx, cy); ctx.scale(s * side, s);
  solePath(); ctx.fillStyle = o.fill ?? "#18342a"; ctx.fill();
  ctx.save(); solePath(); ctx.clip();
  ctx.strokeStyle = o.lug ?? "#2b5444"; ctx.lineWidth = 6; ctx.lineCap = "round"; ctx.lineJoin = "round";
  for (let y = -150; y <= 150; y += 17) { ctx.beginPath(); ctx.moveTo(-64, y + 10); ctx.lineTo(0, y - 6); ctx.lineTo(64, y + 10); ctx.stroke(); }
  ctx.beginPath(); ctx.ellipse(12, 34, 14, 30, 0, 0, Math.PI * 2); ctx.fillStyle = "#142b22"; ctx.fill();
  (o.wear || []).forEach(([x, y, r, col, a]) => {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, col); g.addColorStop(1, col + "00");
    ctx.save(); ctx.globalAlpha *= a; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill(); ctx.restore();
  });
  ctx.restore();
  solePath(); ctx.strokeStyle = o.stroke ?? BLUE; ctx.lineWidth = 4; ctx.stroke();
  ctx.restore();
}
function soles(cx, cy, s, o = {}) {
  sole(cx - 62 * s, cy, s, -1, { ...o, wear: o.wearL });
  sole(cx + 62 * s, cy, s, 1, { ...o, wear: o.wearR });
}
function profileView(cx, cy, s, alpha = 1) {
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx, cy); ctx.scale(s, s);
  rr(-125, 44, 250, 24, 11); ctx.fillStyle = "#18342a"; ctx.fill();
  for (let x = -108; x <= 100; x += 14) { rr(x, 62, 8, 8, 2); ctx.fillStyle = "#2b5444"; ctx.fill(); }
  rr(-130, 10, 260, 38, 17); ctx.fillStyle = "#2d5f8a"; ctx.fill(); ctx.strokeStyle = BLUE; ctx.lineWidth = 3; ctx.stroke();
  ctx.strokeStyle = "#1d4466"; ctx.lineWidth = 2.5; ctx.lineCap = "round";
  for (let x = -96; x <= 96; x += 24) { ctx.beginPath(); ctx.moveTo(x, 17); ctx.quadraticCurveTo(x + 6, 29, x, 41); ctx.stroke(); }
  ctx.beginPath(); ctx.moveTo(-128, 12); ctx.lineTo(-122, -40); ctx.quadraticCurveTo(-118, -64, -90, -66);
  ctx.lineTo(-40, -60); ctx.quadraticCurveTo(-8, -44, 22, -52); ctx.quadraticCurveTo(84, -42, 120, -6); ctx.quadraticCurveTo(138, 4, 130, 12); ctx.closePath();
  ctx.fillStyle = "#1e4d3b"; ctx.fill(); ctx.strokeStyle = BLUE; ctx.stroke();
  ctx.strokeStyle = C.soft; ctx.lineWidth = 2; for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(-10 + i * 20, -44 + i * 5); ctx.lineTo(4 + i * 20, -36 + i * 5); ctx.stroke(); }
  ctx.restore();
}
function backView(cx, cy, s, alpha = 1) {
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx, cy); ctx.scale(s, s);
  line([[-170, 70], [170, 70]], C.faint, 2, 0.8, [6, 6]);
  [[-78, 3.5], [78, 0]].forEach(([x, tilt]) => {
    ctx.save(); ctx.translate(x, 70); ctx.rotate(tilt * Math.PI / 180);
    rr(-52, -22, 104, 22, 10); ctx.fillStyle = "#18342a"; ctx.fill();
    rr(-56, -52, 112, 34, 14); ctx.fillStyle = "#2d5f8a"; ctx.fill(); ctx.strokeStyle = BLUE; ctx.lineWidth = 3; ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-46, -52); ctx.quadraticCurveTo(-52, -108, -26, -116); ctx.quadraticCurveTo(0, -122, 26, -116); ctx.quadraticCurveTo(52, -108, 46, -52); ctx.closePath();
    ctx.fillStyle = "#1e4d3b"; ctx.fill(); ctx.stroke();
    ctx.restore();
  });
  ctx.restore();
}
function upperView(cx, cy, s, alpha = 1) {
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx, cy); ctx.scale(s, s);
  solePath(); ctx.fillStyle = "#1e4d3b"; ctx.fill();
  ctx.save(); solePath(); ctx.clip();
  ctx.fillStyle = "#2f6a52"; for (let y = -150; y < 150; y += 11) for (let x = -56; x < 60; x += 11) { ctx.beginPath(); ctx.arc(x + ((y / 11) & 1) * 5, y, 1.8, 0, Math.PI * 2); ctx.fill(); }
  rr(-22, -40, 54, 130, 24); ctx.fillStyle = "#18342a"; ctx.fill();
  ctx.strokeStyle = C.soft; ctx.lineWidth = 3; ctx.lineCap = "round";
  for (let i = 0; i < 6; i++) { const y = -18 + i * 17; ctx.beginPath(); ctx.moveTo(-22, y + 6); ctx.lineTo(0, y - 3); ctx.lineTo(22, y + 6); ctx.stroke(); }
  ctx.restore();
  solePath(); ctx.strokeStyle = BLUE; ctx.lineWidth = 4; ctx.stroke();
  ctx.restore();
}
function coin(cx, cy, r, alpha = 1) {
  ctx.save(); ctx.globalAlpha *= alpha;
  dot(cx, cy, r, "#c9b87a"); ring(cx, cy, r - 3, "#8f7f43", 2); ring(cx, cy, r * 0.5, "#8f7f43", 1.5);
  ctx.restore();
}
/* Cadre de visée : coins en accent. */
function viewfinder(x, y, w, h, k) {
  if (k <= 0) return;
  const L = 26;
  [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]].forEach(([px, py, sx, sy]) =>
    line([[px, py + sy * L], [px, py], [px + sx * L, py]], C.accent, 3, k));
}
/* Icônes d'équipement. */
function gearIcon(kind, cx, cy, s, col = C.soft) {
  ctx.save(); ctx.translate(cx, cy); ctx.scale(s, s); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 3; ctx.lineCap = "round"; ctx.lineJoin = "round";
  if (kind === 0) { // poche à eau
    rr(-16, -22, 32, 44, 9); ctx.stroke(); line([[-8, -10], [8, -10]], col, 2.5); ctx.beginPath(); ctx.moveTo(10, -22); ctx.quadraticCurveTo(22, -34, 22, -18); ctx.stroke(); dot(0, 10, 4, col);
  } else if (kind === 1) { // frontale
    ctx.beginPath(); ctx.arc(0, 0, 22, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke(); rr(-10, -16, 20, 16, 5); ctx.fillStyle = col; ctx.fill();
    for (let i = -1; i <= 1; i++) line([[i * 9, 6], [i * 13, 18]], C.amber, 2.5);
  } else if (kind === 2) { // bâtons
    line([[-14, 22], [8, -22]], col, 3); line([[8, 22], [-4, -22]], col, 3); ring(8, -22, 4, col, 2); ring(-4, -22, 4, col, 2);
  } else { // couverture
    rr(-18, -20, 36, 40, 4); ctx.stroke(); for (let i = 0; i < 3; i++) line([[-12, -8 + i * 9], [12, -2 + i * 9]], col, 1.8, 0.7);
  }
  ctx.restore();
}
const bounds = (km, a, b) => clamp((km - a) / (b - a));

/* ------------------------------ 01 · le kilométrage ------------------------------ */
function sOdometer(t, d, cues) {
  kicker(S.k1, seg(t, 0, 0.4)); headline(S.h1, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.8) + 1.4, a1 = at(cues, 1, 5);
  const km = lerp(593.8, 612, inOut(seg(t, a0, a0 + 2.0)));
  const x0 = 80, w = 1120, y0 = 218, h = 38;
  const kb = outCubic(seg(t, 0.3, 0.9));
  text(S.pair, x0, y0 - 16, { size: 18, weight: 700, font: SORA, alpha: kb });
  text(`${km.toFixed(1).replace(".", ",")} km`, x0 + 24 + measure(S.pair, 18, 700, SORA), y0 - 16, { size: 22, weight: 800, font: SORA, color: km >= 630 ? C.amber : C.accent, alpha: kb });
  panel(x0, y0, w, h, { r: 19, fill: "#0a120e", alpha: kb });
  ctx.save(); ctx.globalAlpha *= kb; rr(x0, y0, w, h, 19); ctx.clip();
  const g = ctx.createLinearGradient(x0, 0, x0 + w, 0); g.addColorStop(0, C.pine); g.addColorStop(1, C.accent);
  ctx.fillStyle = g; ctx.fillRect(x0, y0, w * km / 700, h); ctx.restore();
  // seuil
  line([[x0 + w - 1, y0 - 8], [x0 + w - 1, y0 + h + 8]], C.amber, 3, kb);
  text(S.thr, x0 + w, y0 - 16, { size: 13, font: MONO, color: C.amber, align: "right", alpha: kb });
  text("0", x0, y0 + h + 28, { size: 13, font: MONO, color: C.faint, alpha: kb });
  // la séance qui ajoute ses kilomètres
  const ks = outBack(seg(t, a0 - 0.3, a0 + 0.3));
  if (ks > 0 && t < a1 + 1.0) pill("+ " + S.sun, x0 + w * km / 700 - 8, y0 + h + 30, { align: "right", alpha: clamp(ks) * (1 - seg(t, a1 + 0.2, a1 + 0.9)), size: 13, color: C.ink, fill: C.panel, stroke: C.line });
  // prévision de retraite
  const ke = outBack(seg(t, a1 + 0.9, a1 + 1.5));
  if (ke > 0) pill(S.eta, x0 + w * 612 / 700 + 12, y0 + h + 30, { alpha: clamp(ke), size: 14, color: C.amber, fill: "rgba(240,180,60,0.1)", stroke: "rgba(240,180,60,0.5)" });
  // captures réelles : la séance, puis le tableau Matériel
  const fx = 80, fy = 305, fw = 1120, fh = 330;
  const k0 = outCubic(seg(t, 0.8, 1.5)), kx = inOut(seg(t, a1 - 0.3, a1 + 0.5));
  const cs = [248, 207, 1008, 270];
  if (kx < 1) {
    const m = shot("seance", fx, fy + (1 - k0) * 24, fw, fh, { alpha: k0 * (1 - kx), crop: cs });
    const b = m([858, 303, 142, 38]), b2 = m([1058, 303, 150, 56]);
    if (b) highlight(b[0], b[1], b[2], b[3], seg(t, a0 - 0.6, a0) * (1 - kx));
    if (b2) highlight(b2[0], b2[1], b2[2], b2[3], seg(t, a0 + 0.8, a0 + 1.4) * (1 - kx), C.teal);
    text(S.cap1, fx + fw, fy + fh + 22, { size: 13, font: MONO, color: C.faint, align: "right", alpha: k0 * (1 - kx) });
  }
  if (kx > 0) {
    const m = shot("materiel", fx, fy, fw, fh, { alpha: kx, crop: [248, 298, 1008, 273] });
    const b = m([620, 388, 118, 46]), b2 = m([836, 398, 300, 26]);
    if (b) highlight(b[0], b[1], b[2], b[3], seg(t, a1 + 0.2, a1 + 0.8));
    if (b2) highlight(b2[0], b2[1], b2[2], b2[3], seg(t, a1 + 1.0, a1 + 1.6), C.amber);
    text(S.cap2, fx + fw, fy + fh + 22, { size: 13, font: MONO, color: C.faint, align: "right", alpha: kx });
  }
}

/* -------------------------------- 02 · le seuil -------------------------------- */
function sAlert(t, d, cues) {
  kicker(S.k2, seg(t, 0, 0.4)); headline(S.h2, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6) + 0.5, a1 = at(cues, 1, 4.5), a2 = at(cues, 2, 7);
  const steps = [8, 18, 14, 22, 28];
  // barre zoomée sur 600–720 km
  const x0 = 80, w = 540, y0 = 250, h = 34, lo = 600, hi = 720;
  let km = 612; const times = steps.map((_, i) => a0 + i * 0.62);
  steps.forEach((s, i) => { km += s * inOut(seg(t, times[i], times[i] + 0.45)); });
  const kb = outCubic(seg(t, 0.3, 0.9));
  text(S.pair, x0, y0 - 44, { size: 18, weight: 700, font: SORA, alpha: kb });
  const over = km >= 700;
  text(`${Math.round(km)} km`, x0 + w, y0 - 40, { size: 28, weight: 800, font: SORA, align: "right", color: over ? C.red : km >= 630 ? C.amber : C.accent, alpha: kb });
  panel(x0, y0, w, h, { r: 17, fill: "#0a120e", alpha: kb });
  ctx.save(); ctx.globalAlpha *= kb; rr(x0, y0, w, h, 17); ctx.clip();
  const g = ctx.createLinearGradient(x0, 0, x0 + w, 0); g.addColorStop(0, C.pine); g.addColorStop(0.75, C.accent); g.addColorStop(1, C.red);
  ctx.fillStyle = g; ctx.fillRect(x0, y0, w * bounds(km, lo, hi), h); ctx.restore();
  const tx = x0 + w * bounds(700, lo, hi);
  line([[tx, y0 - 10], [tx, y0 + h + 10]], over ? C.red : C.amber, 3, kb);
  text(S.thr, tx, y0 + h + 32, { size: 13, font: MONO, color: over ? C.red : C.amber, align: "center", alpha: kb });
  // pastilles de séances
  steps.forEach((s, i) => {
    const k = outBack(seg(t, times[i], times[i] + 0.35)); if (k <= 0) return;
    pill(`+${s} km`, x0 + 52 + i * 106, y0 + 110, { alpha: clamp(k), size: 14, color: i === 4 ? C.red : C.ink, fill: C.panel, stroke: i === 4 ? C.red : C.line, align: "center" });
  });
  const kx = outCubic(seg(t, times[4] + 0.2, times[4] + 0.8));
  if (kx > 0) {
    panel(x0, 400, w, 150, { r: 18, fill: C.panel, stroke: "rgba(240,180,60,0.4)", alpha: kx });
    text("arc_index.py gear --activities <id>", x0 + 24, 438, { size: 14, font: MONO, color: C.accent, alpha: kx });
    text("crete-pro-bleue", x0 + 24, 474, { size: 15, font: MONO, color: C.soft, alpha: kx });
    text('"crossed_in_run": true', x0 + 24, 502, { size: 17, weight: 700, font: MONO, color: C.amber, alpha: kx });
    para(S.bySession, x0 + 24, 530, w - 48, { size: 14, color: C.soft, alpha: kx });
  }
  // notification 07:15 (ligne d'alerte surlignée)
  const nx = 660, nw = 540;
  const k1 = outCubic(seg(t, a1 - 0.3, a1 + 0.4));
  if (k1 > 0) {
    const ny = 170 + (1 - k1) * 26;
    panel(nx, ny, nw, 250, { r: 18, fill: C.panel2, alpha: k1, shadow: true });
    dot(nx + 28, ny + 28, 6, C.accent, k1); text("Sync Garmin", nx + 44, ny + 33, { size: 15, weight: 700, font: SORA, alpha: k1 });
    text(S.sync1, nx + nw - 22, ny + 33, { size: 13, font: MONO, color: C.faint, align: "right", alpha: k1 });
    let yy = ny + 62;
    S.r1.forEach((s, i) => {
      const ki = seg(t, a1 + 0.1 + i * 0.12, a1 + 0.4 + i * 0.12);
      const last = i === 4;
      const lines = wrap(s, nw - 44, 14, last ? 700 : 400, MONO);
      lines.forEach((l, j) => text(l, nx + 22, yy + j * 20, { size: 14, font: MONO, weight: last ? 700 : 400, color: last ? C.amber : C.soft, alpha: ki * k1 }));
      if (last) {
        const hk = seg(t, a1 + 0.9, a1 + 1.5);
        if (hk > 0) highlight(nx + 12, yy - 16, nw - 24, lines.length * 20 + 4, hk, C.amber);
      }
      yy += lines.length * 20 + 6;
    });
  }
  // second passage 14:15
  const k2 = outCubic(seg(t, a2 - 0.2, a2 + 0.5));
  if (k2 > 0) {
    const ny = 450 + (1 - k2) * 20;
    panel(nx, ny, nw, 118, { r: 18, fill: C.panel, alpha: k2 });
    dot(nx + 28, ny + 28, 6, C.faint, k2); text("Sync Garmin", nx + 44, ny + 33, { size: 15, weight: 700, font: SORA, color: C.soft, alpha: k2 });
    text(S.sync2, nx + nw - 22, ny + 33, { size: 13, font: MONO, color: C.faint, align: "right", alpha: k2 });
    S.r2.forEach((s, i) => text(s, nx + 22, ny + 64 + i * 22, { size: 14, font: MONO, color: i ? C.teal : C.faint, alpha: k2 }));
    text(S.again, nx + nw - 22, ny + 100, { size: 12, color: C.faint, align: "right", alpha: k2 });
  }
}

/* ------------------------------- 03 · cinq vues ------------------------------- */
function sProtocol(t, d, cues) {
  kicker(S.k3, seg(t, 0, 0.4)); headline(S.h3, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4), s2 = at(cues, 2, 8), e2 = atEnd(cues, 2, 14);
  const kp = outBack(seg(t, a0 + 0.2, a0 + 0.7));
  if (kp > 0) pill(S.every, 80, 176, { alpha: clamp(kp), size: 14 });
  // terminal /inspection
  const kt = outCubic(seg(t, a1 - 0.4, a1 + 0.2));
  terminal(80, 204, 480, 104, t, [
    { p: "> ", s: S.cmd, c: C.accent, w: 700, a: a1, b: a1 + 0.6 },
    { s: S.reply, c: C.soft, a: a1 + 0.9, b: a1 + 1.8 },
  ], { alpha: kt, size: 14, lh: 26, title: "Claude Code · coach" });
  // viseur : une vue par étape
  const vx = 80, vy = 328, vw = 480, vh = 292;
  const stepT = i => s2 + (e2 - s2) * 0.9 * (i / 5);
  let cur = -1; for (let i = 0; i < 5; i++) if (t >= stepT(i)) cur = i;
  const kv = outCubic(seg(t, 0.8, 1.4));
  panel(vx, vy, vw, vh, { r: 14, fill: "#0a120e", alpha: kv });
  viewfinder(vx + 10, vy + 10, vw - 20, vh - 20, kv);
  const shown = Math.max(cur, 0), kk = cur < 0 ? 1 : outCubic(seg(t, stepT(shown), stepT(shown) + 0.45));
  const cx = vx + vw / 2, cy = vy + vh / 2 + 4;
  ctx.save(); ctx.globalAlpha *= kv * kk;
  if (shown === 0 || shown === 4) {
    soles(cx - (shown === 4 ? 40 : 0), cy, 0.78);
    if (shown === 4) {
      coin(cx + 140, cy + 20, 26 * outBack(seg(t, stepT(4) + 0.1, stepT(4) + 0.5)));
      line([[cx + 112, cy + 66], [cx + 168, cy + 66]], C.accent, 2, seg(t, stepT(4) + 0.5, stepT(4) + 0.9));
      text(S.scaleTag, cx + 140, cy + 90, { size: 12, font: MONO, color: C.accent, align: "center", alpha: seg(t, stepT(4) + 0.6, stepT(4) + 1.0) });
    }
  } else if (shown === 1) profileView(cx, cy, 1.3);
  else if (shown === 2) backView(cx, cy + 10, 1.35);
  else upperView(cx, cy, 0.78);
  ctx.restore();
  // la liste
  S.rows.forEach(([lab, sub], i) => {
    const ry = 178 + i * 88, k = outCubic(seg(t, 0.6 + i * 0.1, 1.2 + i * 0.1));
    const on = i === cur, done = i < cur;
    panel(620, ry, 580, 74, { r: 16, fill: on ? "rgba(163,230,53,0.08)" : C.panel, stroke: on ? C.accent : C.line, lw: on ? 2 : 1, alpha: k });
    const ix = 666, iy = ry + 37;
    ctx.save(); ctx.globalAlpha *= k * (on || done ? 1 : 0.55);
    if (i === 0) soles(ix, iy, 0.14); else if (i === 1) profileView(ix, iy, 0.22); else if (i === 2) backView(ix, iy + 4, 0.26); else if (i === 3) upperView(ix, iy, 0.12); else coin(ix, iy, 15);
    ctx.restore();
    text(lab, 722, ry + 33, { size: 19, weight: 700, font: SORA, alpha: k, color: on || done ? C.ink : C.soft });
    text(sub, 722, ry + 56, { size: 14, color: C.faint, alpha: k });
    if (done) check(1166, ry + 37, 14, C.accent, seg(t, stepT(i + 1) - 0.2, stepT(i + 1) + 0.3) || 1, k);
  });
}

/* ------------------------------- 04 · le verdict ------------------------------- */
const COL = { green: C.teal, yellow: "#e8c547", orange: C.amber, red: C.red };
function sReading(t, d, cues) {
  kicker(S.k4, seg(t, 0, 0.4)); headline(S.h4, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5);
  const sel = seg(t, a0 + 2.4, a0 + 3.0);
  S.grid.forEach(([key, lab, sub], i) => {
    const k = outCubic(seg(t, a0 + 0.2 + i * 0.5, a0 + 0.8 + i * 0.5)), y = 178 + i * 100, on = i === 1 && sel > 0.5;
    const col = COL[key];
    panel(80, y, 360, 84, { r: 18, fill: on ? "rgba(232,197,71,0.10)" : C.panel, stroke: on ? col : C.line, lw: on ? 2 : 1, alpha: k * (i !== 1 && sel > 0.5 ? 0.45 : 1) });
    dot(126, y + 42, 18, col, k * (i !== 1 && sel > 0.5 ? 0.5 : 1)); dot(126, y + 42, 28, col, 0.12 * k * (on ? 1 : 0));
    text(lab, 168, y + 38, { size: 21, weight: 700, font: SORA, alpha: k });
    text(key, 168 + measure(lab, 21, 700, SORA) + 12, y + 38, { size: 12, font: MONO, color: C.faint, alpha: k });
    text(sub, 168, y + 62, { size: 14, color: C.soft, alpha: k });
  });
  // les deux inspections réelles
  const kf = outCubic(seg(t, a1 - 0.5, a1 + 0.2));
  if (kf <= 0) return;
  const fx = 480, fy = 172 + (1 - kf) * 24, fw = 720, fh = 436;
  const m = shot("inspections", fx, fy, fw, fh, { alpha: kf, crop: [262, 372, 822, 462] });
  const h1 = m([278, 384, 352, 32]), h2 = m([278, 420, 424, 26]), h3 = m([278, 622, 272, 30]), z = m([396, 440, 360, 56]);
  if (h1) highlight(h1[0], h1[1], h1[2], h1[3], seg(t, a1 + 0.5, a1 + 1.1));
  if (h2) highlight(h2[0], h2[1], h2[2], h2[3], seg(t, a1 + 1.5, a1 + 2.1), C.amber);
  if (h3) highlight(h3[0], h3[1], h3[2], h3[3], seg(t, a1 + 2.6, a1 + 3.2), C.teal);
  const kc = outBack(seg(t, a1 + 3.0, a1 + 3.6));
  if (kc > 0) pill(S.cmp, fx + fw / 2, 626, { align: "center", alpha: clamp(kc), size: 14, font: INTER, weight: 600, color: C.ink, fill: C.deep, stroke: C.accent });
  text(S.cap3, fx + fw, fy - 8, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kf });
}

/* ------------------------------- 05 · les indices ------------------------------- */
function sHints(t, d, cues) {
  kicker(S.k5, seg(t, 0, 0.4)); headline(S.h5, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6);
  const grow = outCubic(seg(t, a0 + 0.4, a0 + 2.4));
  const ks = outCubic(seg(t, 0.3, 0.9));
  const wl = [[40, 116, 38 * grow, "#f0b43c", 0.9]], wr = [[40, 116, 20 * grow, "#e8c547", 0.65]];
  soles(270, 372, 1.12, { alpha: ks, wearL: wl, wearR: wr });
  text(S.left, 270 - 62 * 1.12, 174, { size: 13, font: MONO, color: C.faint, align: "center", alpha: ks });
  text(S.right, 270 + 62 * 1.12, 174, { size: 13, font: MONO, color: C.faint, align: "center", alpha: ks });
  // repère sur la zone d'usure (pied gauche : côté extérieur = gauche à l'écran)
  const kc = seg(t, a0 + 1.6, a0 + 2.3);
  callout(S.zone, 80, 578, 270 - 62 * 1.12 - 40 * 1.12, 372 + 116 * 1.12, kc, { align: "left", size: 13 });
  const kh = outBack(seg(t, a0 + 2.4, a0 + 3.0));
  if (kh > 0) pill(S.hint, 270, 628, { align: "center", alpha: clamp(kh), size: 14, color: C.amber, fill: "rgba(240,180,60,0.1)", stroke: "rgba(240,180,60,0.5)" });
  // les quatre précautions, une par réplique
  S.cav.forEach(([title, sub], i) => {
    const a = at(cues, i, 2 + i * 2.2) - 0.15, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    const y = 172 + i * 112 + (1 - k) * 18;
    const icol = i === 0 ? C.accent : i === 1 ? C.amber : i === 2 ? C.teal : C.red;
    panel(540, y, 660, 96, { r: 18, fill: C.panel, stroke: i === 0 ? C.line : "rgba(255,255,255,0.05)", alpha: k });
    ctx.save(); ctx.globalAlpha *= k; rr(540, y, 6, 96, [18, 0, 0, 18]); ctx.fillStyle = icol; ctx.fill(); ctx.restore();
    const cx = 592, cy = y + 48;
    ctx.save(); ctx.globalAlpha *= k;
    if (i === 0) { ring(cx, cy, 15, icol, 3); dot(cx, cy, 5, icol); }
    else if (i === 1) { ctx.beginPath(); ctx.moveTo(cx, cy - 18); ctx.lineTo(cx + 18, cy + 14); ctx.lineTo(cx - 18, cy + 14); ctx.closePath(); ctx.strokeStyle = icol; ctx.lineWidth = 3; ctx.lineJoin = "round"; ctx.stroke(); text("!", cx, cy + 9, { size: 18, weight: 800, font: SORA, color: icol, align: "center" }); }
    else if (i === 2) { coin(cx, cy, 15); line([[cx - 26, cy + 24], [cx + 26, cy - 24]], C.red, 3); }
    else { line([[cx - 17, cy - 17], [cx + 17, cy + 17]], icol, 4); line([[cx + 17, cy - 17], [cx - 17, cy + 17]], icol, 4); }
    ctx.restore();
    text(title, 634, y + 40, { size: 21, weight: 700, font: SORA, alpha: k });
    para(sub, 634, y + 66, 540, { size: 15, color: C.soft, alpha: k, font: i === 2 ? MONO : INTER });
  });
}

/* ------------------------------- 06 · la mesure ------------------------------- */
function spark(x, y, w, h, seed, k, col) {
  const R = rng(seed), pts = []; let v = 0.5;
  for (let i = 0; i < 12; i++) { v = clamp(v + (R() - 0.5) * 0.4, 0.1, 0.9); pts.push([x + w * i / 11, y + h * (1 - v)]); }
  line(partial(pts, k), col, 2, 0.9);
}
function sMeasured(t, d, cues) {
  kicker(S.k6, seg(t, 0, 0.4)); headline(S.h6, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.5), a2 = at(cues, 2, 7.5);
  // gauche : mesuré
  const k0 = outCubic(seg(t, a0 + 0.1, a0 + 0.7));
  panel(80, 170, 560, 290, { r: 20, alpha: k0 });
  text(S.meas, 106, 210, { size: 14, weight: 600, font: MONO, color: C.accent, alpha: k0, spacing: "1px" });
  S.mrows.forEach(([lab, val], i) => {
    const k = outCubic(seg(t, a0 + 0.5 + i * 0.35, a0 + 1.0 + i * 0.35)), y = 250 + i * 52;
    text(lab, 106, y, { size: 16, color: C.soft, alpha: k });
    spark(380, y - 20, 90, 24, 40 + i, seg(t, a0 + 0.8 + i * 0.35, a0 + 1.8 + i * 0.35), C.teal);
    text("→", 496, y, { size: 18, color: C.faint, alpha: k, font: MONO });
    text(val, 616, y, { size: 19, weight: 700, font: SORA, align: "right", alpha: k });
  });
  // droite : deviné
  const k1 = outCubic(seg(t, a0 + 1.4, a0 + 2.0));
  panel(680, 170, 520, 150, { r: 20, alpha: k1, stroke: "rgba(240,180,60,0.35)" });
  text(S.guess, 706, 210, { size: 14, weight: 600, font: MONO, color: C.amber, alpha: k1, spacing: "1px" });
  let cx = 706;
  S.chips.forEach((s, i) => { const w = pill(s, cx, 262 + i * 0, { alpha: k1, size: 14, font: INTER, color: C.ink, fill: C.deep, stroke: "rgba(240,180,60,0.5)" }); if (i === 0) cx += w + 10; });
  // balance : écart à 50 %
  const k2 = outCubic(seg(t, a1 - 0.3, a1 + 0.4));
  if (k2 > 0) {
    panel(680, 340, 520, 120, { r: 20, alpha: k2 });
    text(S.bal, 706, 372, { size: 15, weight: 600, alpha: k2 });
    const bx = 706, bw = 468, by = 410;
    line([[bx, by], [bx + bw, by]], C.line, 6, k2);
    ctx.save(); ctx.globalAlpha *= k2; rr(bx + bw * 0.45, by - 9, bw * 0.1, 18, 4); ctx.fillStyle = "rgba(184,196,189,0.28)"; ctx.fill(); ctx.restore();
    line([[bx + bw / 2, by - 14], [bx + bw / 2, by + 14]], C.faint, 2, k2);
    text("50 %", bx + bw / 2, by + 34, { size: 12, font: MONO, color: C.faint, align: "center", alpha: k2 });
    text(S.band, bx + bw * 0.55 + 6, by - 14, { size: 11, font: MONO, color: C.faint, alpha: k2 });
    const px = bx + bw * (0.5 + 0.004 * 12 * outCubic(seg(t, a1 + 0.2, a1 + 1.2)) + 0.002 * Math.sin(t * 2));
    dot(px, by, 9, C.teal, k2);
  }
  // bas gauche : sans mesure
  const k3 = outCubic(seg(t, a2 - 0.2, a2 + 0.5));
  if (k3 > 0) {
    panel(80, 482, 560, 118, { r: 18, fill: C.panel, stroke: "rgba(184,196,189,0.4)", alpha: k3 });
    para(S.none, 106, 520, 510, { size: 17, weight: 600, color: C.soft, alpha: k3 });
    pill(S.unav, 106, 580, { size: 13, alpha: k3, color: C.faint, fill: "rgba(184,196,189,0.08)", stroke: "rgba(184,196,189,0.4)" });
  }
  // bas droite : la mesure prime
  const k4 = outCubic(seg(t, a0 + 3.0, a0 + 3.8));
  if (k4 > 0) {
    panel(680, 482, 520, 118, { r: 18, fill: "rgba(163,230,53,0.07)", stroke: C.accent, alpha: k4 });
    para(S.dis, 706, 518, 470, { size: 18, weight: 700, alpha: k4 });
    text(S.conf, 706, 580, { size: 13, font: MONO, color: C.faint, alpha: k4 });
  }
}

/* ------------------------------ 07 · hors chaussures ------------------------------ */
function sKits(t, d, cues) {
  kicker(S.k7, seg(t, 0, 0.4)); headline(S.h7, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.5), a2 = at(cues, 2, 7);
  const kp = outBack(seg(t, 0.4, 0.9));
  if (kp > 0) pill(S.kit, 80, 176, { alpha: clamp(kp), size: 15 });
  const lit = [a0 + 2.0, a0 + 2.8, a0 + 3.6, a0 + 4.4];
  S.items.forEach((name, i) => {
    const k = outCubic(seg(t, 0.7 + i * 0.12, 1.3 + i * 0.12)), x = 80 + i * 285, y = 204, on = t > lit[i] && t < lit[i] + 1.2;
    panel(x, y, 262, 74, { r: 16, fill: on ? "rgba(163,230,53,0.08)" : C.panel, stroke: on ? C.accent : C.line, alpha: k, lw: on ? 2 : 1 });
    gearIcon(i, x + 38, y + 37, 0.9, on ? C.accent : C.soft);
    text(name, x + 72, y + 44, { size: 17, weight: 700, font: SORA, alpha: k });
  });
  const fx = 80, fy = 290, fw = 1120, fh = 224, kf = outCubic(seg(t, 0.9, 1.6));
  const cA = [248, 628, 1008, 153], cB = [248, 772, 1008, 153];
  const cr = lerpRect(cA, cB, inOut(seg(t, a2 - 0.8, a2 - 0.1)));
  const m = shot("materiel", fx, fy + (1 - kf) * 20, fw, fh, { alpha: kf, crop: cr });
  const hb = m([270, 640, 880, 56]), hf = m([270, 812, 880, 36]);
  if (hb) highlight(hb[0], hb[1], hb[2], hb[3], seg(t, a1 - 0.4, a1 + 0.2) * (1 - seg(t, a2 - 0.8, a2 - 0.3)));
  if (hf) highlight(hf[0], hf[1], hf[2], hf[3], seg(t, a2 - 0.1, a2 + 0.4), C.amber);
  text(S.cap4, fx + fw, fy + fh + 20, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kf });
  const card = (x, y, w, h, title, lineS, sub, k, col) => {
    if (k <= 0) return;
    const dy = (1 - k) * 18;
    panel(x, y + dy, w, h, { r: 18, fill: C.panel, stroke: col, alpha: k });
    text(title, x + 22, y + 32 + dy, { size: 13, weight: 600, font: MONO, color: col, alpha: k, spacing: "1px" });
    text(lineS, x + 22, y + 58 + dy, { size: 17, weight: 700, alpha: k });
    para(sub, x + 22, y + 80 + dy, w - 44, { size: 12, color: C.soft, alpha: k });
  };
  card(80, 534, 548, 96, S.syncT.toUpperCase(), S.syncL, S.syncS, outCubic(seg(t, a1 - 0.2, a1 + 0.5)), C.amber);
  card(652, 534, 548, 96, S.nightT.toUpperCase(), S.nightL, S.nightS, outCubic(seg(t, a2 - 0.2, a2 + 0.5)), C.accent);
}

/* ------------------------------ 08 · bilan de carrière ------------------------------ */
function sCareer(t, d, cues) {
  kicker(S.k8, seg(t, 0, 0.4)); headline(S.h8, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4);
  const ks = outCubic(seg(t, 0.3, 0.9)), grey = inOut(seg(t, a0 + 0.2, a0 + 1.4));
  sole(230, 372, 0.95, 1, { alpha: ks, fill: grey > 0.5 ? "#1c2a24" : "#18342a", lug: grey > 0.5 ? "#2a3a33" : "#2b5444", stroke: grey > 0.5 ? "#55645c" : BLUE });
  text(S.old, 230, 560, { size: 22, weight: 800, font: SORA, align: "center", alpha: ks, color: grey > 0.5 ? C.soft : C.ink });
  text(S.oldKm, 230, 592, { size: 18, weight: 600, font: MONO, align: "center", color: C.faint, alpha: ks });
  const st = outBack(seg(t, a0 + 1.0, a0 + 1.6));
  if (st > 0) {
    ctx.save(); ctx.translate(230, 372); ctx.rotate(-0.35); ctx.scale(clamp(st, 0, 1.15), clamp(st, 0, 1.15)); ctx.globalAlpha *= clamp(st);
    rr(-98, -28, 196, 56, 8); ctx.strokeStyle = C.red; ctx.lineWidth = 4; ctx.stroke(); ctx.fillStyle = "rgba(15,28,22,0.55)"; ctx.fill();
    text(S.retired, 0, 12, { size: 32, weight: 800, font: SORA, color: C.red, align: "center", spacing: "4px" });
    ctx.restore();
  }
  const kt = outCubic(seg(t, a0 + 1.2, a0 + 1.9));
  terminal(430, 164, 770, 142, t, [
    { p: "$ ", s: S.gc, c: C.accent, a: a0 + 1.4, b: a0 + 3.0 },
    { s: S.gcOut[0], c: C.soft, a: a0 + 3.2, b: a0 + 3.8 },
    { s: S.gcOut[1], c: C.soft, a: a0 + 3.8, b: a0 + 4.4 },
  ], { alpha: kt, size: 14, lh: 28, title: "arc_index.py" });
  const kf = outCubic(seg(t, a1 - 0.5, a1 + 0.2));
  if (kf > 0) {
    const fx = 430, fy = 326, fw = 770, fh = 284;
    const m = shot("materiel-fiche", fx, fy + (1 - kf) * 20, fw, fh, { alpha: kf, crop: [248, 207, 1008, 326] });
    const hs = [[255, 222, 190, 60], [466, 222, 190, 60], [863, 222, 190, 60]];
    hs.forEach(([x, y, w, h], i) => { const b = m([x, y, w, h]); if (b) highlight(b[0], b[1], b[2], b[3], seg(t, a1 + 0.4 + i * 0.7, a1 + 1.0 + i * 0.7)); });
    text(S.cap5, fx + fw, fy + fh + 20, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kf });
  }
}

ARC.episode({
  n: 9, slug: "materiel",
  strings: STR,
  shots: ["materiel", "seance", "inspections", "materiel-fiche"],
  scenes: { odometer: sOdometer, alert: sAlert, protocol: sProtocol, reading: sReading, hints: sHints, measured: sMeasured, kits: sKits, career: sCareer },
});
})();
