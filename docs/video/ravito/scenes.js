/* Le Sentier · étape 8 — « Ravito » : /log, une phrase libre transformée en données.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}] —
 * at(cues, i, repli) cale une animation sur la voix, quelle que soit la langue.
 * Athlète et chiffres fictifs (bible de la série : Camille). Les valeurs montrées
 * viennent d'une vraie exécution de scripts/arc_log.py sur un catalogue fictif. */
"use strict";
(() => {
const V = "#a99cf0"; // violet : « effort » (RPE)
const KIND_COLOR = { prod: C.accent, fluid: C.teal, pos: C.soft, pain: C.amber, rpe: V };

const STR = {
  fr: {
    prompt: "/log ",
    tokens: [["2 gels", "prod"], [" + ", ""], ["500 ml", "fluid"], [" ", ""], ["au km 15", "pos"], [", ", ""], ["genou gauche 3/10", "pain"], [", ", ""], ["RPE 7", "rpe"]],
    k1: "01 · UNE PHRASE", h1: "Une phrase. C'est tout.",
    chat: "Saisie libre · Claude Code",
    cards: [["PRODUIT", "gel × 2", "quantité « 2 »"], ["LIQUIDE", "500 ml", "unité reconnue"], ["POSITION", "km 15", "texte libre"], ["DOULEUR", "genou gauche", "score 3 / 10"], ["EFFORT", "RPE 7", "sur 10"]],
    modelTag: "MODÈLE · il extrait, sans convertir ni additionner",
    k2: "02 · QUI FAIT QUOI", h2: "Le modèle extrait. Le script calcule.",
    modelT: "entités extraites", modelL: [
      ["# texte brut, tel que dit", C.faint], ["nutrition_items:", C.ink], ['{"product":"gels","qty":"2"}', C.accent],
      ["fluid_entries:", C.ink], ['["500 ml"]', C.teal], ["pain:", C.ink], ['{"location":"genou gauche",', C.amber], [' "score":"3/10"}', C.amber], ['rpe: "7"', V]],
    scriptT: "scripts/arc_log.py", scriptSub: "Python stdlib · déterministe",
    cat: "resources/nutrition/catalogue-produits-camille.md", catCols: ["Produit", "Portion", "Glucides"],
    catRows: [["Gel Crête citron", "1 sachet", "25 g"], ["Barre Sentier", "1 barre", "28 g"], ["Barre Sommet", "1 barre", "30 g"]],
    match: "gels → Gel Crête citron", calc: "2 × 25 g = 50 g", fluid: "500 ml → 500 ml",
    resT: "résultat (JSON)", res: [["carbs_g", "50", C.accent], ["fluid_intake_ml", "500", C.teal], ["pain", "genou gauche · 3", C.amber], ["consult", "false", C.soft], ["rpe", "7", V]],
    never: "Jamais l'inverse.", rule: "Un modèle qui additionne peut inventer un chiffre plausible.",
    k3: "03 · UN DOUTE ? ON DEMANDE", h3: "Jamais d'invention.",
    askMe: "/log une barre + une purée maison au km 20", other: "autre exemple",
    amb: ["barre", "ambigu", "Barre Sentier · Barre Sommet"], unk: ["purée maison", "inconnu", "unknown_product · absent du catalogue"],
    askCoach: "Quelle barre : Sentier ou Sommet ? Et pour la purée, combien de glucides sur l'étiquette ?",
    nevers: ["Aucune valeur générique glissée à la place", "Aucun calcul à la main par le modèle"],
    does: ["carbs_g omis pour cette part, jamais deviné", "liquide, douleur, RPE écrits sans attendre", "la valeur donnée → le script refait tout le calcul"],
    k4: "04 · ÉCRIT AU CONTRAT", h4: "Chaque donnée à sa place.",
    f1: "activities/2026-09-27_trail.md", f2: "medical/2026-09-27_health.md",
    owner1: "écrit par le nutritionniste (sinon le coach)", owner2: "écrit par le médecin (sinon le coach)",
    act: ["# Trail du dimanche", "```arc", '{"arc": 1, "kind": "activity",', ' "date": "2026-09-27", "sport": "trail",', ' …,', ' "carbs_g": 50,', ' "fluid_intake_ml": 500,', ' "rpe": 7}', "```", "[/log 2026-09-27T…] 2 gels + 500 ml…", "Ravitaillement au km 15 : 2 gels, 500 ml."],
    hl: ["# Santé du dimanche", "```arc", '{"arc": 1, "kind": "health",', ' "date": "2026-09-27",', ' "pain": [{"location": "genou gauche",', '           "score": 3}]}', "```"],
    posNote: "← la position reste du texte libre", validate: "arc_index.py --validate  ✓",
    merge: "fusion · jamais d'écrasement", dup: "doublon détecté · rien compté deux fois",
    k5: "05 · LA DOULEUR", h5: "Un seuil, réglable.",
    scale: "douleur déclarée (0-10)", noted: "noté dans medical/…_health.md", consult: "consult: true", reco: "Recommandation de consulter",
    notAdvice: "Ne remplace pas un avis médical.",
    cfg: ["# config/workspace.toml", "[injury_risk]", "pain_consult_threshold = 7.0"], thr: "seuil",
    k6: "06 · VOTRE PLAFOND", h6: "Pas un chiffre générique.",
    chartT: "glucides par heure · sorties de plus de 90 min", runs: ["sortie 1", "sortie 2", "sortie 3", "sortie 4"],
    band: "repère générique 60-90 g/h", best: "meilleur débit : 56 g/h", ceil: "plafond : 56 + 10 = 66 g/h",
    sweatT: "TAUX DE SUDATION", w1: "avant 62,0 kg", w2: "après 61,2 kg", drank: "bu : 900 ml", dur: "durée totale 2 h 30 (pauses comprises)",
    sweatF: "((62,0 − 61,2) + 0,9) / 2,5 h", sweatR: "0,68 L/h", approx: "une approximation, jamais une mesure",
    tol: "« toléré » = avalé sans incident déclaré", few: "Moins de 3 sorties chiffrées : le coach le dit.",
    k7: "07 · LE JOUR J", h7: "Soixante grammes, sous le plafond.",
    race: "Trail des Crêtes · 42 km · 2 100 m D+", aid: ["km 12", "km 24", "km 34"], hourly: "60 g",
    planT: "Plan de ravitaillement", plan: [["glucides", "60 g/h"], ["plafond de Camille", "66 g/h"], ["dépense prévue", "≈ 520 kcal/h"]],
    enT: "Retour de séance", en: "Dépense : Garmin 1 380 kcal · modèle 1 430 kcal (+4 %)", enAlert: "alerte au-delà de 15 %",
    enRules: ["Garmin reste la référence", "le modèle n'est qu'un contrôle", "jamais additionné au total du jour"],
    mfp: "Pas de MyFitnessPal : vos apports sont vos déclarations.",
  },
  en: {
    prompt: "/log ",
    tokens: [["2 gels", "prod"], [" + ", ""], ["500 ml", "fluid"], [" ", ""], ["at km 15", "pos"], [", ", ""], ["left knee 3/10", "pain"], [", ", ""], ["RPE 7", "rpe"]],
    k1: "01 · ONE SENTENCE", h1: "One sentence. That's it.",
    chat: "Free-form entry · Claude Code",
    cards: [["PRODUCT", "gel × 2", "quantity “2”"], ["LIQUID", "500 ml", "unit recognised"], ["POSITION", "km 15", "free text"], ["PAIN", "left knee", "score 3 / 10"], ["EFFORT", "RPE 7", "out of 10"]],
    modelTag: "MODEL · it extracts, without converting or adding",
    k2: "02 · WHO DOES WHAT", h2: "The model extracts. The script computes.",
    modelT: "extracted entities", modelL: [
      ["# raw text, as said", C.faint], ["nutrition_items:", C.ink], ['{"product":"gels","qty":"2"}', C.accent],
      ["fluid_entries:", C.ink], ['["500 ml"]', C.teal], ["pain:", C.ink], ['{"location":"left knee",', C.amber], [' "score":"3/10"}', C.amber], ['rpe: "7"', V]],
    scriptT: "scripts/arc_log.py", scriptSub: "Python stdlib · deterministic",
    cat: "resources/nutrition/catalogue-produits-camille.md", catCols: ["Product", "Serving", "Carbs"],
    catRows: [["Gel Crête citron", "1 sachet", "25 g"], ["Barre Sentier", "1 bar", "28 g"], ["Barre Sommet", "1 bar", "30 g"]],
    match: "gels → Gel Crête citron", calc: "2 × 25 g = 50 g", fluid: "500 ml → 500 ml",
    resT: "result (JSON)", res: [["carbs_g", "50", C.accent], ["fluid_intake_ml", "500", C.teal], ["pain", "left knee · 3", C.amber], ["consult", "false", C.soft], ["rpe", "7", V]],
    never: "Never the reverse.", rule: "A model that adds up can invent a plausible number.",
    k3: "03 · IN DOUBT? ASK", h3: "Never made up.",
    askMe: "/log a bar + homemade purée at km 20", other: "another example",
    amb: ["bar", "ambiguous", "Barre Sentier · Barre Sommet"], unk: ["homemade purée", "unknown", "unknown_product · not in the catalogue"],
    askCoach: "Which bar: Sentier or Sommet? And for the purée, how many carbs on the label?",
    nevers: ["No generic value slipped in instead", "No hand arithmetic by the model"],
    does: ["carbs_g left out for that part, never guessed", "fluid, pain, RPE written without waiting", "the value you give → the script redoes the sum"],
    k4: "04 · WRITTEN TO THE CONTRACT", h4: "Everything in its place.",
    f1: "activities/2026-09-27_trail.md", f2: "medical/2026-09-27_health.md",
    owner1: "written by the nutritionist (else the coach)", owner2: "written by the medical agent (else the coach)",
    act: ["# Sunday trail", "```arc", '{"arc": 1, "kind": "activity",', ' "date": "2026-09-27", "sport": "trail",', ' …,', ' "carbs_g": 50,', ' "fluid_intake_ml": 500,', ' "rpe": 7}', "```", "[/log 2026-09-27T…] 2 gels + 500 ml…", "Fuel stop at km 15: 2 gels, 500 ml."],
    hl: ["# Sunday health", "```arc", '{"arc": 1, "kind": "health",', ' "date": "2026-09-27",', ' "pain": [{"location": "left knee",', '           "score": 3}]}', "```"],
    posNote: "← the position stays free text", validate: "arc_index.py --validate  ✓",
    merge: "merge · never overwritten", dup: "duplicate detected · nothing counted twice",
    k5: "05 · PAIN", h5: "One threshold, adjustable.",
    scale: "reported pain (0-10)", noted: "logged in medical/…_health.md", consult: "consult: true", reco: "Recommendation to consult",
    notAdvice: "Not a substitute for medical advice.",
    cfg: ["# config/workspace.toml", "[injury_risk]", "pain_consult_threshold = 7.0"], thr: "threshold",
    k6: "06 · YOUR CEILING", h6: "Not a generic number.",
    chartT: "carbs per hour · runs longer than 90 min", runs: ["run 1", "run 2", "run 3", "run 4"],
    band: "generic range 60-90 g/h", best: "best rate: 56 g/h", ceil: "ceiling: 56 + 10 = 66 g/h",
    sweatT: "SWEAT RATE", w1: "before 62.0 kg", w2: "after 61.2 kg", drank: "drunk: 900 ml", dur: "total time 2 h 30 (stops included)",
    sweatF: "((62.0 − 61.2) + 0.9) / 2.5 h", sweatR: "0.68 L/h", approx: "an approximation, never a measurement",
    tol: "“tolerated” = taken without a reported problem", few: "Fewer than 3 measured runs: the coach says so.",
    k7: "07 · RACE DAY", h7: "Sixty grams, under the ceiling.",
    race: "Trail des Crêtes · 42 km · 2,100 m gain", aid: ["km 12", "km 24", "km 34"], hourly: "60 g",
    planT: "Fuel plan", plan: [["carbs", "60 g/h"], ["Camille's ceiling", "66 g/h"], ["expected burn", "≈ 520 kcal/h"]],
    enT: "Session feedback", en: "Energy: Garmin 1,380 kcal · model 1,430 kcal (+4%)", enAlert: "flagged beyond 15%",
    enRules: ["Garmin stays the reference", "the model is only a cross-check", "never added to the day's total"],
    mfp: "No MyFitnessPal: your intake is what you report.",
  },
};

/* ------------------------------ petits outils ------------------------------ */
const chip = (s, x, y, col, o = {}) => pill(s, x, y, Object.assign({ color: col, fill: "rgba(13,20,16,0.7)", stroke: col, size: 12 }, o));
function okMark(x, y, k, col = C.accent) { check(x, y, 12, col, k); }

/* ------------------------------ 1. une phrase ------------------------------ */
function sSentence(t, d, cues) {
  kicker(S.k1, seg(t, 0, 0.4));
  headline(S.h1, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const x = 80, y = 180, w = 1120, h = 92;
  const kp = outCubic(seg(t, 0.2, 0.8));
  panel(x, y, w, h, { r: 18, fill: "#0a120e", alpha: kp, shadow: true });
  text(S.chat, x + 24, y + 26, { size: 12, font: MONO, color: C.faint, alpha: kp });
  const size = 28, full = S.tokens.map(a => a[0]).join("");
  const t0 = 0.7, k = seg(t, t0, t0 + 3.4);
  const n = Math.round(full.length * k);
  const bx = x + 28 + measure(S.prompt, size, 700, MONO), by = y + 66;
  text(S.prompt, x + 28, by, { size, weight: 700, font: MONO, color: C.accent, alpha: kp });
  // surlignage des entités (cue 1) : fond coloré sous le segment, puis texte
  const L0 = Math.max(4, atEnd(cues, 0, 8.7) - at(cues, 0, 0.5)), A0 = at(cues, 0, 0.5);
  const HF = [0.40, 0.52, 0.68, 0.80, 0.94]; // fraction de la phrase dite avant chaque entité
  const hAt = i => A0 + L0 * HF[i] - 0.3;
  let off = 0;
  const segs = [];
  S.tokens.forEach(([s, kind], i) => {
    const sx = bx + measure(full.slice(0, off), size, 400, MONO), sw = measure(s, size, 400, MONO);
    segs.push({ s, kind, sx, sw, off });
    off += s.length;
  });
  segs.filter(g => g.kind).forEach((g, i) => {
    const hk = outCubic(seg(t, hAt(i), hAt(i) + 0.4));
    if (hk <= 0) return;
    ctx.save(); ctx.globalAlpha *= hk * 0.22; rr(g.sx - 5, by - 26, g.sw + 10, 38, 8); ctx.fillStyle = KIND_COLOR[g.kind]; ctx.fill(); ctx.restore();
    ctx.save(); ctx.globalAlpha *= hk; line([[g.sx, by + 14], [g.sx + g.sw * hk, by + 14]], KIND_COLOR[g.kind], 3); ctx.restore();
  });
  segs.forEach(g => {
    const part = full.slice(g.off, g.off + g.s.length);
    const shown = part.slice(0, Math.max(0, Math.min(part.length, n - g.off)));
    const idx = segs.filter(q => q.kind).indexOf(g);
    const hk = g.kind ? seg(t, hAt(idx), hAt(idx) + 0.4) : 0;
    text(shown, g.sx, by, { size, font: MONO, color: g.kind && hk > 0.5 ? KIND_COLOR[g.kind] : C.ink, weight: 400 });
  });
  if (k < 1) { // curseur de saisie
    const cx = bx + measure(full.slice(0, n), size, 400, MONO) + 3;
    ctx.save(); ctx.fillStyle = C.accent; ctx.globalAlpha *= 0.5 + 0.5 * Math.sin(t * 9); ctx.fillRect(cx, by - 24, 14, 32); ctx.restore();
  }
  // cartes d'entités
  const cw = 212, gap = 15, cy = 380, ch = 150;
  segs.filter(g => g.kind).forEach((g, i) => {
    const a = hAt(i) + 0.2;
    const kk = outCubic(seg(t, a, a + 0.5));
    if (kk <= 0) return;
    const cx = 80 + i * (cw + gap), col = KIND_COLOR[g.kind];
    // trait de rappel depuis le segment
    const sx = g.sx + g.sw / 2;
    line(partial([[sx, by + 18], [sx, 320], [cx + cw / 2, 330], [cx + cw / 2, cy]], kk), col, 1.5, 0.7);
    panel(cx, cy + (1 - kk) * 18, cw, ch, { r: 16, fill: C.panel, stroke: col, alpha: kk, lw: 1.5 });
    const [lab, val, sub] = S.cards[i];
    text(lab, cx + 20, cy + 36 + (1 - kk) * 18, { size: 12, weight: 700, font: MONO, color: col, alpha: kk, spacing: "1.5px" });
    text(val, cx + 20, cy + 82 + (1 - kk) * 18, { size: measure(val, 26, 800, SORA) > cw - 36 ? 21 : 26, weight: 800, font: SORA, alpha: kk });
    text(sub, cx + 20, cy + 118 + (1 - kk) * 18, { size: 14, color: C.soft, alpha: kk });
  });
  const km = outCubic(seg(t, at(cues, 1, 9) + 0.2, at(cues, 1, 9) + 0.8));
  if (km > 0) pill(S.modelTag, 640, 590, { align: "center", alpha: km, size: 14, color: V, fill: "rgba(169,156,240,0.1)", stroke: "rgba(169,156,240,0.5)" });
}

/* --------------------- 2. le modèle extrait, le script calcule ------------- */
function sCompute(t, d, cues) {
  kicker(S.k2, seg(t, 0, 0.4));
  headline(S.h2, seg(t, 0.1, 0.7), 132, 38);
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 4.5), a2 = at(cues, 2, 9);
  const top = 176, H0 = 350;
  // modèle (à gauche)
  const k1 = outCubic(seg(t, 0.3, 0.9));
  const lines = S.modelL.map(([s, c], i) => ({ s, c, a: a0 + 0.2 + i * 0.28, b: a0 + 0.5 + i * 0.28 }));
  terminal(70, top, 340, H0, t, lines, { alpha: k1, size: 14, lh: 29, title: S.modelT });
  chip("MODÈLE".slice(0, LANG === "fr" ? 6 : 5), 372, top + 17, V, { align: "right", size: 10, h: 18, alpha: k1 });
  // script (au centre)
  const k2 = outCubic(seg(t, 0.5, 1.1));
  const cx = 450, cw = 380;
  panel(cx, top, cw, H0, { r: 16, fill: C.panel, alpha: k2, shadow: true, stroke: "rgba(163,230,53,0.35)" });
  text(S.scriptT, cx + 24, top + 36, { size: 17, weight: 700, font: MONO, color: C.accent, alpha: k2 });
  text(S.scriptSub, cx + 24, top + 58, { size: 12, font: MONO, color: C.faint, alpha: k2 });
  // catalogue
  const ty = top + 84, kc = seg(t, a1 - 0.6, a1);
  text(S.cat.split("/").pop(), cx + 24, ty, { size: 11, font: MONO, color: C.faint, alpha: kc });
  const cols = [cx + 24, cx + 200, cx + cw - 24];
  S.catCols.forEach((c, i) => text(c, cols[i], ty + 26, { size: 12, weight: 700, font: MONO, color: C.soft, align: i === 2 ? "right" : "left", alpha: kc }));
  const hit = outCubic(seg(t, a1 + 0.2, a1 + 0.8));
  S.catRows.forEach((r, i) => {
    const ry = ty + 40 + i * 34;
    if (i === 0 && hit > 0) { ctx.save(); ctx.globalAlpha *= hit * kc; rr(cx + 14, ry - 4, cw - 28, 30, 8); ctx.fillStyle = "rgba(163,230,53,0.14)"; ctx.fill(); ctx.strokeStyle = C.accent; ctx.lineWidth = 1.5; ctx.stroke(); ctx.restore(); }
    r.forEach((c, j) => text(c, cols[j], ry + 17, { size: 15, weight: i === 0 && hit > 0.5 ? 700 : 400, color: i === 0 && hit > 0.5 ? C.ink : C.soft, align: j === 2 ? "right" : "left", alpha: kc }));
  });
  const kcal = outCubic(seg(t, a1 + 1.0, a1 + 1.6));
  text(S.match, cx + 24, top + 252, { size: 15, font: MONO, color: C.soft, alpha: kcal });
  text(S.calc, cx + 24, top + 296, { size: 34, weight: 800, font: SORA, color: C.accent, alpha: kcal });
  text(S.fluid, cx + 24, top + 328, { size: 15, font: MONO, color: C.teal, alpha: kcal });
  // flux
  const kf = seg(t, a0 + 1.4, a0 + 2.2);
  arrow(412, top + 175, 448, top + 175, kf, C.faint);
  if (kf >= 1) packets(412, top + 175, 448, top + 175, t, 2, 1.0, 0.9);
  // résultat (à droite)
  const k3 = outCubic(seg(t, 0.7, 1.3));
  const rl = S.res.map(([key, val, c], i) => ({ s: `${key}: ${val}`, c, a: a1 + 1.6 + i * 0.35, b: a1 + 1.9 + i * 0.35 }));
  terminal(870, top, 340, H0, t, rl, { alpha: k3, size: 15, lh: 34, title: S.resT });
  const kf2 = seg(t, a1 + 1.2, a1 + 2.0);
  arrow(832, top + 175, 868, top + 175, kf2, C.accent);
  if (kf2 >= 1) packets(832, top + 175, 868, top + 175, t, 2, 1.0, 0.9);
  // la règle
  const kr = outCubic(seg(t, a2, a2 + 0.6));
  if (kr > 0) {
    text(S.never, 640, 576, { size: 30, weight: 800, font: SORA, color: C.accent, align: "center", alpha: kr });
    text(S.rule, 640, 608, { size: 16, color: C.soft, align: "center", alpha: kr });
  }
}

/* --------------------------- 3. jamais d'invention ------------------------- */
function sAsk(t, d, cues) {
  kicker(S.k3, seg(t, 0, 0.4));
  headline(S.h3, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 4);
  const lx = 80, lw = 560;
  chip(S.other, lx, 176, C.faint, { size: 11, h: 22, alpha: seg(t, 0.4, 0.9) });
  // saisie de l'athlète
  const k0 = outCubic(seg(t, 0.5, 1.0));
  bubble(S.askMe, lx, 200, lw, { side: "me", size: 17, alpha: k0, k: seg(t, 0.6, 1.8) });
  // verdicts du script
  [[S.amb, C.amber, a0 + 1.4], [S.unk, C.red, a0 + 2.2]].forEach(([[name, kind, sub], col, a], i) => {
    const k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    const y = 270 + i * 102 + (1 - k) * 14;
    panel(lx, y, lw, 88, { r: 14, fill: C.panel, stroke: col, alpha: k, lw: 1.5 });
    text(name, lx + 22, y + 36, { size: 22, weight: 800, font: SORA, alpha: k });
    chip(kind, lx + lw - 20, y + 30, col, { align: "right", size: 12, alpha: k });
    text(sub, lx + 22, y + 66, { size: 14, font: MONO, color: C.soft, alpha: k });
  });
  // la question du coach
  const kq = outCubic(seg(t, a1, a1 + 0.6));
  if (kq > 0) {
    text("COACH", lx, 502, { size: 12, weight: 700, font: MONO, color: C.faint, alpha: kq });
    bubble(S.askCoach, lx, 514, lw, { size: 17, alpha: kq, k: seg(t, a1 + 0.2, a1 + 1.8) });
  }
  // à droite : ce qui n'arrive jamais / ce qui arrive
  const rx = 700, rw = 500, kr = outCubic(seg(t, a1 + 0.6, a1 + 1.2));
  panel(rx, 200, rw, 380, { r: 18, fill: C.panel, alpha: kr });
  S.nevers.forEach((s, i) => {
    const y = 250 + i * 46, k = seg(t, a1 + 1.0 + i * 0.4, a1 + 1.5 + i * 0.4);
    line([[rx + 28, y - 8], [rx + 46, y + 10]], C.red, 3, k); line([[rx + 46, y - 8], [rx + 28, y + 10]], C.red, 3, k);
    text(s, rx + 64, y + 6, { size: 17, weight: 600, alpha: k });
  });
  line([[rx + 24, 350], [rx + rw - 24, 350]], C.line, 1, kr);
  S.does.forEach((s, i) => {
    const y = 396 + i * 56, k = seg(t, a1 + 2.2 + i * 0.5, a1 + 2.7 + i * 0.5);
    okMark(rx + 38, y, k);
    para(s, rx + 64, y + 5, rw - 100, { size: 17, color: C.ink, alpha: k });
  });
}

/* ---------------------------- 4. chaque donnée à sa place ------------------- */
function sFiles(t, d, cues) {
  kicker(S.k4, seg(t, 0, 0.4));
  headline(S.h4, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 4), a2 = at(cues, 2, 7);
  const colorOf = (s) => /^#/.test(s) ? C.ink : /^```/.test(s) ? C.faint : /carbs_g/.test(s) ? C.accent : /fluid/.test(s) ? C.teal : /"rpe"/.test(s) ? V : /pain|location|score/.test(s) ? C.amber : /^\[\/log/.test(s) ? C.faint : /^ …|^\{|^ "/.test(s) ? C.soft : C.soft;
  // fichier séance
  const k1 = outCubic(seg(t, 0.3, 0.9));
  const l1 = S.act.map((s, i) => ({ s, c: colorOf(s), w: i === 0 ? 700 : 400, a: 0.9 + i * 0.3, b: 1.15 + i * 0.3 }));
  // les trois clés de la séance s'allument avec la première réplique
  terminal(60, 176, 610, 400, t, l1, { alpha: k1, size: 14, lh: 29, title: S.f1 });
  text(S.owner1, 70, 600, { size: 13, font: MONO, color: C.faint, alpha: k1 });
  [5, 6, 7].forEach((row, i) => {
    const k = seg(t, a0 + 1.0 + i * 0.5, a0 + 1.5 + i * 0.5);
    if (k <= 0) return;
    const y = 176 + 62 + row * 29;
    ctx.save(); ctx.globalAlpha *= k * 0.18; rr(60 + 14, y - 21, 582, 28, 6); ctx.fillStyle = [C.accent, C.teal, V][i]; ctx.fill(); ctx.restore();
  });
  // fichier santé
  const k2 = outCubic(seg(t, a1 - 0.8, a1 - 0.2));
  const l2 = S.hl.map((s, i) => ({ s, c: colorOf(s), w: i === 0 ? 700 : 400, a: a1 + i * 0.3, b: a1 + 0.25 + i * 0.3 }));
  if (k2 > 0) {
    terminal(710, 176, 510, 268, t, l2, { alpha: k2, size: 14, lh: 29, title: S.f2 });
    text(S.owner2, 720, 468, { size: 13, font: MONO, color: C.faint, alpha: k2 });
    // flèche douleur
    const ky = seg(t, a1 + 0.2, a1 + 1.0);
    if (ky > 0) {
      ctx.save(); ctx.globalAlpha *= ky * 0.18; rr(724, 176 + 62 + 4 * 29 - 21, 482, 2 * 29 - 1, 6); ctx.fillStyle = C.amber; ctx.fill(); ctx.restore();
    }
  }
  // validation + garde-fous
  const kv = outCubic(seg(t, a2, a2 + 0.5));
  if (kv > 0) {
    pill(S.merge, 960, 516, { align: "center", alpha: kv, size: 14 });
    pill(S.dup, 960, 558, { align: "center", alpha: seg(t, a2 + 0.5, a2 + 1.0), size: 14 });
    text(S.validate, 960, 604, { size: 13, font: MONO, color: C.accent, align: "center", alpha: seg(t, a2 + 1.0, a2 + 1.5) });
  }
}

/* ------------------------------- 5. la douleur ------------------------------ */
function sPain(t, d, cues) {
  kicker(S.k5, seg(t, 0, 0.4));
  headline(S.h5, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 3.4);
  const x0 = 120, x1 = 1160, y = 300, step = (x1 - x0) / 10, THR = 7;
  const ks = outCubic(seg(t, 0.3, 0.9));
  text(S.scale, x0, y - 62, { size: 14, font: MONO, color: C.faint, alpha: ks });
  // piste
  panel(x0 - 10, y - 18, x1 - x0 + 20, 36, { r: 18, fill: C.panel, alpha: ks });
  const kz = seg(t, a1 + 0.9, a1 + 1.5);
  ctx.save(); ctx.globalAlpha *= ks; rr(x0 + THR * step - 2, y - 18, (10 - THR) * step + 12, 36, [0, 18, 18, 0]); ctx.fillStyle = `rgba(240,122,95,${0.12 + 0.28 * kz})`; ctx.fill(); ctx.restore();
  for (let i = 0; i <= 10; i++) {
    line([[x0 + i * step, y + 22], [x0 + i * step, y + 32]], C.faint, 1.5, ks);
    text(String(i), x0 + i * step, y + 56, { size: 16, font: MONO, color: i >= THR ? C.red : C.soft, align: "center", alpha: ks });
  }
  // seuil
  const kt = outCubic(seg(t, a0 + 0.8, a0 + 1.4));
  line([[x0 + THR * step, y - 70], [x0 + THR * step, y + 40]], C.red, 2.5, kt, [6, 5]);
  text(`${S.thr} ≥ 7`, x0 + THR * step, y - 82, { size: 15, weight: 700, font: MONO, color: C.red, align: "center", alpha: kt });
  // curseur : 3 puis 7
  const mv = inOut(seg(t, a1 + 0.1, a1 + 1.1));
  const v = mv <= 0 ? 3 * outCubic(seg(t, 0.5, 1.2)) : lerp(3, 7, mv);
  const mx = x0 + v * step, hot = v >= THR - 0.001 && mv >= 1;
  const col = hot ? C.red : C.accent;
  dot(mx, y, 22, col, 0.22); dot(mx, y, 13, col);
  text(String(Math.round(v)), mx, y - 30, { size: 26, weight: 800, font: SORA, color: col, align: "center" });
  // état « noté »
  const kn = outCubic(seg(t, a0 + 0.9, a0 + 1.4)) * (1 - seg(t, a1 + 0.2, a1 + 0.6));
  if (kn > 0) {
    panel(x0, 420, 500, 100, { r: 16, fill: C.panel, alpha: kn });
    check(x0 + 36, 470, 14, C.accent, 1, kn);
    text(S.noted, x0 + 64, 462, { size: 17, weight: 600, alpha: kn });
    text("consult: false", x0 + 64, 492, { size: 14, font: MONO, color: C.soft, alpha: kn });
  }
  // état « consulter »
  const kh = outBack(seg(t, a1 + 1.1, a1 + 1.7));
  if (kh > 0) {
    panel(x0, 420, 560, 130, { r: 16, fill: "rgba(240,122,95,0.1)", stroke: C.red, alpha: clamp(kh), lw: 1.5 });
    text(S.reco, x0 + 28, 470, { size: 24, weight: 800, font: SORA, color: C.red, alpha: clamp(kh) });
    text(S.consult, x0 + 28, 500, { size: 15, font: MONO, color: C.soft, alpha: clamp(kh) });
    text(S.notAdvice, x0 + 28, 528, { size: 14, color: C.faint, alpha: clamp(kh) });
  }
  // configuration
  const kc = outCubic(seg(t, a1 + 1.4, a1 + 2.0));
  terminal(760, 420, 400, 150, t, S.cfg.map((s, i) => ({ s, c: i === 0 ? C.faint : i === 1 ? C.ink : C.accent, a: a1 + 1.4 + i * 0.3, b: a1 + 1.7 + i * 0.3 })), { alpha: kc, size: 15, lh: 30 });
}

/* ------------------------------ 6. le plafond ------------------------------ */
function sCeiling(t, d, cues) {
  kicker(S.k6, seg(t, 0, 0.4));
  headline(S.h6, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 6);
  // graphique à barres
  const cx = 80, cy = 190, cw = 640, ch = 380, base = cy + ch - 56, top = cy + 60, gmax = 90;
  const gy = g => base - (g / gmax) * (base - top);
  const kc = outCubic(seg(t, 0.3, 0.9));
  panel(cx, cy, cw, ch, { r: 18, alpha: kc });
  text(S.chartT, cx + 24, cy + 34, { size: 14, font: MONO, color: C.soft, alpha: kc });
  // repère générique 60-90
  const kb = seg(t, 0.8, 1.4);
  ctx.save(); ctx.globalAlpha *= kb * kc; rr(cx + 24, gy(90), cw - 48, gy(60) - gy(90), 4); ctx.fillStyle = "rgba(184,196,189,0.10)"; ctx.fill(); ctx.restore();
  text(S.band, cx + cw - 36, gy(90) + 20, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kb * kc });
  line([[cx + 24, base], [cx + cw - 24, base]], C.line, 1.5, kc);
  const vals = [42, 48, 52, 56], bw = 78, gapx = 52;
  vals.forEach((v, i) => {
    const bx = cx + 64 + i * (bw + gapx), kk = outCubic(seg(t, a0 + 0.8 + i * 0.7, a0 + 1.5 + i * 0.7));
    const hh = (base - gy(v)) * kk, best = i === 3;
    rr(bx, base - hh, bw, hh, [8, 8, 0, 0]); ctx.save(); ctx.fillStyle = best ? C.accent : "rgba(163,230,53,0.35)"; ctx.fill(); ctx.restore();
    if (kk > 0.5) text(String(v), bx + bw / 2, base - hh - 10, { size: 17, weight: 700, font: MONO, color: best ? C.accent : C.soft, align: "center", alpha: seg(kk, 0.5, 1) });
    text(S.runs[i], bx + bw / 2, base + 26, { size: 13, font: MONO, color: C.faint, align: "center", alpha: kc });
  });
  text(S.best, cx + cw - 24, cy + 34, { size: 14, weight: 700, font: MONO, color: C.accent, align: "right", alpha: seg(t, a0 + 3.2, a0 + 3.8) });
  // plafond : +10
  const kp = outCubic(seg(t, a1 - 0.2, a1 + 0.7));
  if (kp > 0) {
    const bx = cx + 64 + 3 * (bw + gapx);
    rr(bx, gy(66), bw, gy(56) - gy(66), 0); ctx.save(); ctx.globalAlpha *= kp; ctx.setLineDash([5, 4]); ctx.strokeStyle = C.amber; ctx.lineWidth = 2; ctx.stroke(); ctx.restore();
    line([[cx + 40, gy(66)], [cx + cw - 40, gy(66)]], C.amber, 2, kp, [8, 6]);
    pill(S.ceil, cx + 60, gy(66) - 20, { align: "left", alpha: kp, size: 13, color: C.amber, fill: "rgba(240,180,60,0.12)", stroke: C.amber });
    
  }
  // sudation
  const sx = 770, sw = 430, kw = outCubic(seg(t, a1 + 0.8, a1 + 1.4));
  panel(sx, 190, sw, 380, { r: 18, fill: C.panel, alpha: kw, shadow: true });
  text(S.sweatT, sx + 26, 232, { size: 13, weight: 700, font: MONO, color: C.teal, alpha: kw, spacing: "2px" });
  [[S.w1, 0], [S.w2, 1], [S.drank, 2]].forEach(([s, i]) => {
    const k = seg(t, a1 + 1.2 + i * 0.4, a1 + 1.7 + i * 0.4);
    text(s, sx + 26, 282 + i * 36, { size: 20, weight: 600, font: SORA, alpha: k });
  });
  text(S.dur, sx + 26, 400, { size: 14, color: C.soft, alpha: seg(t, a1 + 2.4, a1 + 2.9) });
  const kf = seg(t, a1 + 2.8, a1 + 3.5);
  text(S.sweatF, sx + 26, 450, { size: 17, font: MONO, color: C.faint, alpha: kf });
  text(S.sweatR, sx + 26, 508, { size: 54, weight: 800, font: SORA, color: C.teal, alpha: outCubic(seg(t, a1 + 3.4, a1 + 4.0)) });
  text(S.approx, sx + 26, 545, { size: 13, color: C.faint, alpha: seg(t, a1 + 3.8, a1 + 4.3) });
  // honnêteté
  const kt = seg(t, a1 + 4.4, a1 + 5.0);
  text(S.tol, 80, 604, { size: 14, color: C.soft, alpha: kt });
  text(S.few, 80, 626, { size: 14, color: C.faint, alpha: kt });
}

/* -------------------------------- 7. le jour J ------------------------------ */
function sRace(t, d, cues) {
  kicker(S.k7, seg(t, 0, 0.4));
  headline(S.h7, seg(t, 0.1, 0.7), 132, 40);
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 5);
  // profil de course
  const x0 = 100, x1 = 1180, yb = 300, amp = 88, ph = 1.1;
  const kr = outCubic(seg(t, 0.3, 1.3));
  text(S.race, x0, 184, { size: 14, font: MONO, color: C.soft, alpha: kr });
  const prof = [];
  for (let i = 0; i <= 160; i++) { const u = i / 160; prof.push([lerp(x0, x1, u), yb - amp * ridge(u, ph)]); }
  const drawn = partial(prof, kr);
  line(drawn, C.soft, 2.5, 1);
  ctx.save(); ctx.globalAlpha *= 0.08 * kr; ctx.beginPath(); drawn.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  if (drawn.length) { ctx.lineTo(drawn[drawn.length - 1][0], yb + 28); ctx.lineTo(x0, yb + 28); } ctx.closePath(); ctx.fillStyle = C.accent; ctx.fill(); ctx.restore();
  const yAt = u => yb - amp * ridge(u, ph);
  [12, 24, 34].forEach((km, i) => {
    const u = km / 42, k = outBack(seg(t, a0 + 1.0 + i * 0.4, a0 + 1.5 + i * 0.4)), x = lerp(x0, x1, u);
    if (k <= 0) return;
    line([[x, yAt(u)], [x, yb + 28]], C.faint, 1.5, clamp(k), [4, 4]);
    dot(x, yAt(u), 7 * clamp(k), C.amber);
    text(S.aid[i], x, yb + 48, { size: 13, font: MONO, color: C.amber, align: "center", alpha: clamp(k) });
  });
  // un repère de 60 g toutes les heures (course d'environ 6 h)
  for (let h = 1; h <= 6; h++) {
    const u = (h * 60) / 365, k = outCubic(seg(t, a0 + 1.2 + h * 0.3, a0 + 1.6 + h * 0.3));
    if (k <= 0) continue;
    const x = lerp(x0, x1, u);
    dot(x, yAt(u), 5, C.accent, k);
    text(S.hourly, x, yAt(u) - 14, { size: 12, weight: 700, font: MONO, color: C.accent, align: "center", alpha: k });
  }
  // plan
  const kp = outCubic(seg(t, a0 + 2.6, a0 + 3.2));
  const px = 80, py = 386, pw = 440, ph2 = 212;
  panel(px, py, pw, ph2, { r: 16, fill: C.panel, alpha: kp });
  text(S.planT.toUpperCase(), px + 24, py + 36, { size: 12, weight: 700, font: MONO, color: C.accent, alpha: kp, spacing: "2px" });
  S.plan.forEach(([lab, val], i) => {
    const k = seg(t, a0 + 3.0 + i * 0.4, a0 + 3.5 + i * 0.4), y = py + 86 + i * 46;
    text(lab, px + 24, y, { size: 17, color: C.soft, alpha: k });
    text(val, px + pw - 24, y, { size: 22, weight: 800, font: SORA, color: i === 1 ? C.amber : C.ink, align: "right", alpha: k });
  });
  // retour de séance : dépense Garmin vs modèle
  const ke = outCubic(seg(t, a1, a1 + 0.6));
  const ex = 550, ew = 650;
  panel(ex, py, ew, ph2, { r: 16, fill: C.panel, alpha: ke });
  text(S.enT.toUpperCase(), ex + 24, py + 36, { size: 12, weight: 700, font: MONO, color: C.teal, alpha: ke, spacing: "2px" });
  const ety = seg(t, a1 + 0.3, a1 + 1.5);
  text(typed(S.en, ety), ex + 24, py + 74, { size: 17, weight: 600, font: MONO, alpha: ke });
  const gx = ex + 24, gw = ew - 48, gy2 = py + 98, mid = gx + gw / 2, sc = gw / 40;
  const kg = seg(t, a1 + 1.4, a1 + 2.0);
  ctx.save(); ctx.globalAlpha *= kg * ke; rr(gx, gy2, gw, 14, 7); ctx.fillStyle = C.line; ctx.fill();
  rr(mid - 15 * sc, gy2, 30 * sc, 14, 7); ctx.fillStyle = "rgba(163,230,53,0.28)"; ctx.fill(); ctx.restore();
  const dv = outCubic(seg(t, a1 + 1.6, a1 + 2.4)) * 4;
  dot(mid + dv * sc, gy2 + 7, 8, C.accent, kg * ke);
  text("+4 %", mid + dv * sc, gy2 - 10, { size: 12, weight: 700, font: MONO, color: C.accent, align: "center", alpha: kg * ke });
  text("−15 %", mid - 15 * sc, gy2 + 34, { size: 11, font: MONO, color: C.faint, align: "center", alpha: kg * ke });
  text("+15 %", mid + 15 * sc, gy2 + 34, { size: 11, font: MONO, color: C.faint, align: "center", alpha: kg * ke });
  text(S.enAlert, gx + gw, gy2 + 34, { size: 12, font: MONO, color: C.amber, align: "right", alpha: kg * ke });
  S.enRules.forEach((s, i) => {
    const k = seg(t, a1 + 2.6 + i * 0.5, a1 + 3.1 + i * 0.5);
    check(ex + 34, py + 146 + i * 22 - 4, 9, C.accent, k, k * ke);
    text(s, ex + 52, py + 146 + i * 22, { size: 14, color: C.soft, alpha: k * ke });
  });
  // pas de MyFitnessPal
  text(S.mfp, 640, 628, { size: 14, color: C.faint, align: "center", alpha: seg(t, a1 + 3.8, a1 + 4.4) });
}

ARC.episode({
  n: 8, slug: "ravito",
  strings: STR,
  shots: [],
  scenes: { sentence: sSentence, compute: sCompute, ask: sAsk, files: sFiles, pain: sPain, ceiling: sCeiling, race: sRace },
});
})();
