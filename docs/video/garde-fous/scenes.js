/* Le Sentier · étape 3 — « Le plan qui sait dire non » : la semaine et ses sept garde-fous.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}] —
 * at(cues, i, repli) cale une animation sur la voix, quelle que soit la langue.
 * Noms de règles, seuils (config/workspace.toml [guardrails]), sévérités, messages et commandes :
 * ceux de docs/guardrails.md et de scripts/arc_guardrails.py. Les valeurs mesurées (1,18 ; +6,1 % ;
 * +4,8 % ; 1,6) sont fictives mais respectent ces seuils ; 39 % (R6) et la détection R7 (mardi +
 * mercredi) sont, eux, exactement ce que rend le moteur sur cette semaine. */
"use strict";
(() => {
const STR = {
  fr: {
    days: ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"], dates: ["28", "29", "30", "1", "2", "3", "4"],
    rest: "Repos",
    tue: "Seuil 5 × 6'", wed: "Côtes 8 × 1'", thu: "EF 45'", sat: "Sortie longue", sun: "EF 50'",
    d: { tue: "1 h 15", wed: "1 h 05", thu: "45 min", sat: "2 h 30", sun: "50 min" },
    dp: { tue: "120 m D+", wed: "80 m D+", thu: "40 m D+", sat: "900 m D+", sun: "160 m D+" },
    kinds: { q: "qualité", e: "facile", l: "longue" },
    k1: "01 · LE BROUILLON", h1: "Une semaine à valider.", weekFile: "planning/2026-09-28_semaine.md",
    second: "second avis",
    k2: "02 · CHARGE ET PROGRESSION", h2: "Quatre règles de charge.",
    r: [
      { id: "r1_acwr_projected", title: "Charge aiguë / chronique", sub: "projetée · maximum sur la semaine", val: "1,18", thr: "seuil 1,3" },
      { id: "r2_weekly_volume_jump", title: "Hausse du volume", sub: "6 h 25 vs moyenne 4 sem. : 6 h 03", val: "+6,1 %", thr: "seuil 10 %" },
      { id: "r3_weekly_elevation_jump", title: "Hausse du D+", sub: "1 300 m vs moyenne 4 sem. : 1 240 m", val: "+4,8 %", thr: "seuil 10 %" },
      { id: "r4_monotony_projected", title: "Monotonie de Foster", sub: "moyenne / écart-type, 7 jours", val: "1,6", thr: "seuil 2" },
    ],
    below: "sous le seuil", peak: "max. samedi", scale: ["moy. 4 sem.", "cette semaine"],
    k3: "03 · SANTÉ ET SORTIE LONGUE", h3: "Un qui bloque, un qui prévient.",
    r5: { id: "r5_quality_after_red", title: "Qualité après un verdict rouge", sub: "le jour même ou le lendemain", val: "0 séance", ok: "aucun verdict rouge" },
    r6: { id: "r6_long_run_share", title: "Part de la sortie longue", sub: "dans le volume hebdomadaire", val: "39 %", thr: "seuil 35 %", warn: "avertissement : on garde la sortie longue" },
    verdicts: "verdicts santé", sev: ["info", "warn", "block"], sevNote: "sévérité · seul R5 bloque par défaut",
    k4: "04 · QUALITÉ EN RAFALE", h4: "Deux séances dures de suite.",
    r7: { id: "r7_consecutive_quality", msg: "Séances de qualité le même jour ou sur deux jours consécutifs : 2026-09-29, 2026-09-30." },
    qdef: "qualité = tempo · threshold · vo2max · race", moveNote: "côtes ⇄ endurance", r7ok: "mardi et jeudi : plus de jours consécutifs",
    k5: "05 · TRAÇABILITÉ", h5: "Écrit noir sur blanc.",
    decFile: "planning/2026-09-28_decision_deplacement-cotes.md",
    dec: ["# Côtes déplacées à jeudi", "```arc", '{"arc": 1, "kind": "decision", "date": "2026-09-28",', ' "created_at": "2026-09-28T08:12:00+02:00",', ' "trigger": "guardrail", "outcome": "applied",', ' "summary": "Côtes déplacées de mercredi à jeudi.",', ' "rule_ids": ["r7_consecutive_quality"],', ' "before": {"date": "2026-09-30"},', ' "after": {"date": "2026-10-01"},', ' "session_ref": {"week": "planning/2026-09-28_semaine.md",', '                 "date": "2026-09-30"}}', "```", "Mardi seuil, mercredi côtes : alerte r7."],
    decTags: [["la règle", "r7_consecutive_quality"], ["l'avant", "mercredi 30 sept."], ["l'après", "jeudi 1er oct."]],
    validate: "arc_index.py --validate",
    k6: "06 · CIBLES PERSONNELLES", h6: "Jamais des bornes génériques.",
    tgCmd: "python3 scripts/arc_workout_targets.py targets --session planning/2026-09-28_semaine.md#2026-10-01",
    tg: [
      { day: "MAR", title: "Seuil 5 × 6'", zone: "Zone 4 · 163-172 bpm", pace: "pilotée par la FC", dp: "—" },
      { day: "MER", title: "EF 45'", zone: "Zone 2 · 146-155 bpm", pace: "6:10-6:32 /km (GAP)", dp: "—" },
      { day: "JEU", title: "Côtes 8 × 1'", zone: "Zone 5 · 172-188 bpm", pace: "—", dp: "≥ 9 m D+ / rép." },
    ],
    tgRows: ["zone cardiaque", "allure à plat", "D+ par côte"], tgNote: "Cible incalculable : retirée, et dite — jamais inventée.", lthr: "zones : FC au seuil 172 bpm",
    k7: "07 · CALENDRIER GARMIN", h7: "Pousser, puis relire.",
    steps: [["Garde-fous", "arc_guardrails.py check", "exit 0"], ["Rien en double", "get_scheduled_workouts", "calendrier lu d'abord"], ["Envoi", "schedule_workouts", "5 séances"], ["Vérification", "get_scheduled_workouts", "date · durée · nom"]],
    cal: "Calendrier Garmin Connect",
    tag: "Un second avis calculé, déterministe, testé.", tag2: "Pas une intuition de modèle.", tests: "tests/data/test_arc_guardrails.py",
  },
  en: {
    days: ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"], dates: ["28", "29", "30", "1", "2", "3", "4"],
    rest: "Rest",
    tue: "Threshold 5 × 6'", wed: "Hills 8 × 1'", thu: "Easy 45'", sat: "Long run", sun: "Easy 50'",
    d: { tue: "1 h 15", wed: "1 h 05", thu: "45 min", sat: "2 h 30", sun: "50 min" },
    dp: { tue: "120 m D+", wed: "80 m D+", thu: "40 m D+", sat: "900 m D+", sun: "160 m D+" },
    kinds: { q: "quality", e: "easy", l: "long" },
    k1: "01 · THE DRAFT", h1: "A week to validate.", weekFile: "planning/2026-09-28_semaine.md",
    second: "second opinion",
    k2: "02 · LOAD AND PROGRESSION", h2: "Four load rules.",
    r: [
      { id: "r1_acwr_projected", title: "Acute / chronic load", sub: "projected · weekly maximum", val: "1.18", thr: "threshold 1.3" },
      { id: "r2_weekly_volume_jump", title: "Volume increase", sub: "6 h 25 vs 4-week mean: 6 h 03", val: "+6.1 %", thr: "threshold 10 %" },
      { id: "r3_weekly_elevation_jump", title: "Elevation increase", sub: "1,300 m vs 4-week mean: 1,240 m", val: "+4.8 %", thr: "threshold 10 %" },
      { id: "r4_monotony_projected", title: "Foster monotony", sub: "mean / std deviation, 7 days", val: "1.6", thr: "threshold 2" },
    ],
    below: "below threshold", peak: "peak: Saturday", scale: ["4-wk mean", "this week"],
    k3: "03 · HEALTH AND LONG RUN", h3: "One blocks, one warns.",
    r5: { id: "r5_quality_after_red", title: "Quality after a red verdict", sub: "same day or the day after", val: "0 sessions", ok: "no red verdict" },
    r6: { id: "r6_long_run_share", title: "Long run share", sub: "of the weekly volume", val: "39 %", thr: "threshold 35 %", warn: "warning: we keep the long run" },
    verdicts: "health verdicts", sev: ["info", "warn", "block"], sevNote: "severity · only R5 blocks by default",
    k4: "04 · BACK-TO-BACK QUALITY", h4: "Two hard days in a row.",
    r7: { id: "r7_consecutive_quality", msg: "Quality sessions on the same day, or on consecutive days: 2026-09-29, 2026-09-30." },
    qdef: "quality = tempo · threshold · vo2max · race", moveNote: "hills ⇄ easy run", r7ok: "Tuesday and Thursday: not consecutive",
    k5: "05 · ON THE RECORD", h5: "Written down.",
    decFile: "planning/2026-09-28_decision_deplacement-cotes.md",
    dec: ["# Hills moved to Thursday", "```arc", '{"arc": 1, "kind": "decision", "date": "2026-09-28",', ' "created_at": "2026-09-28T08:12:00+02:00",', ' "trigger": "guardrail", "outcome": "applied",', ' "summary": "Hills moved from Wednesday to Thursday.",', ' "rule_ids": ["r7_consecutive_quality"],', ' "before": {"date": "2026-09-30"},', ' "after": {"date": "2026-10-01"},', ' "session_ref": {"week": "planning/2026-09-28_semaine.md",', '                 "date": "2026-09-30"}}', "```", "Threshold Tue, hills Wed: r7 warning."],
    decTags: [["the rule", "r7_consecutive_quality"], ["the before", "Wednesday, Sept 30"], ["the after", "Thursday, Oct 1"]],
    validate: "arc_index.py --validate",
    k6: "06 · PERSONAL TARGETS", h6: "Never generic bounds.",
    tgCmd: "python3 scripts/arc_workout_targets.py targets --session planning/2026-09-28_semaine.md#2026-10-01",
    tg: [
      { day: "TUE", title: "Threshold 5 × 6'", zone: "Zone 4 · 163-172 bpm", pace: "HR-driven", dp: "—" },
      { day: "WED", title: "Easy 45'", zone: "Zone 2 · 146-155 bpm", pace: "6:10-6:32 /km (GAP)", dp: "—" },
      { day: "THU", title: "Hills 8 × 1'", zone: "Zone 5 · 172-188 bpm", pace: "—", dp: "≥ 9 m D+ / rep" },
    ],
    tgRows: ["heart rate zone", "flat pace", "climb per hill"], tgNote: "Target not computable: dropped, and said so — never invented.", lthr: "zones: threshold HR 172 bpm",
    k7: "07 · GARMIN CALENDAR", h7: "Push, then read back.",
    steps: [["Guardrails", "arc_guardrails.py check", "exit 0"], ["No duplicates", "get_scheduled_workouts", "calendar read first"], ["Push", "schedule_workouts", "5 sessions"], ["Verification", "get_scheduled_workouts", "date · duration · name"]],
    cal: "Garmin Connect calendar",
    tag: "A computed, deterministic, tested second opinion.", tag2: "Not a model's hunch.", tests: "tests/data/test_arc_guardrails.py",
  },
};

/* ------------------------------ helpers locaux ----------------------------- */
// séances du brouillon : col = jour (0 = lundi) ; k : q (qualité), e (facile), l (longue)
const SESS = [
  { key: "tue", col: 1, k: "q" }, { key: "wed", col: 2, k: "q" }, { key: "thu", col: 3, k: "e" },
  { key: "sat", col: 5, k: "l" }, { key: "sun", col: 6, k: "e" },
];
const KCOL = { q: C.amber, e: C.teal, l: C.accent };
const SEVCOL = { info: C.teal, warn: C.amber, block: C.red };
function sevPill(sev, x, y, o = {}) {
  const c = SEVCOL[sev];
  return pill(sev, x, y, { size: o.size ?? 14, color: c, fill: `rgba(${sev === "block" ? "240,122,95" : sev === "warn" ? "240,180,60" : "95,184,160"},0.10)`, stroke: c, ...o });
}
/* Une carte de séance dans la grille hebdomadaire. col peut être fractionnaire (animation). */
function sessCard(s, col, x0, y, cw, ch, gap, o = {}) {
  const x = x0 + col * (cw + gap), a = o.alpha ?? 1, c = KCOL[s.k];
  const hot = o.hot ?? 0;
  panel(x, y, cw, ch, { r: 14, fill: hot > 0 ? `rgba(240,180,60,${0.06 + 0.1 * hot})` : C.panel2, stroke: hot > 0 ? C.amber : C.line, lw: 1 + hot, alpha: a, shadow: o.shadow });
  rr(x + 12, y + 12, 4, ch - 24, 2); ctx.save(); ctx.globalAlpha *= a; ctx.fillStyle = c; ctx.fill(); ctx.restore();
  let fs = o.tsize ?? 18; while (fs > 12 && measure(S[s.key], fs, 700, SORA) > cw - 38) fs -= 0.5;
  text(S[s.key], x + 26, y + 38, { size: fs, weight: 700, font: SORA, alpha: a });
  if (ch >= 110) {
    text(S.d[s.key], x + 26, y + 66, { size: 16, font: MONO, color: C.soft, alpha: a });
    text(S.dp[s.key], x + 26, y + 90, { size: 14, font: MONO, color: C.faint, alpha: a });
  }
  if (ch >= 140) text(S.kinds[s.k], x + 26, y + ch - 18, { size: 13, font: MONO, color: c, alpha: a, spacing: "1px" });
}
function strip(t, x0, y, cw, ch, gap, o = {}) {
  for (let i = 0; i < 7; i++) {
    const a = o.alpha?.(i) ?? 1;
    text(S.days[i], x0 + i * (cw + gap) + 4, y - 26, { size: 13, weight: 600, font: MONO, color: C.faint, alpha: a, spacing: "2px" });
    text(S.dates[i], x0 + i * (cw + gap) + cw - 4, y - 26, { size: 13, font: MONO, color: C.faint, align: "right", alpha: a });
    panel(x0 + i * (cw + gap), y, cw, ch, { r: 14, fill: "rgba(19,32,26,0.4)", stroke: C.line, alpha: a * 0.7 });
  }
}
const mm = (n, a, b) => clamp((n - a) / (b - a));

/* ------------------------------- 01 · brouillon ---------------------------- */
function sWeek(t, d, cues) {
  kicker(S.k1, seg(t, 0, 0.4));
  headline(S.h1, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.6), a2 = at(cues, 2, 7.6);
  const x0 = 84, y = 230, cw = 152, ch = 210, gap = 8;
  strip(t, x0, y, cw, ch, gap, { alpha: i => outCubic(seg(t, 0.3 + i * 0.06, 0.8 + i * 0.06)) });
  pill(S.weekFile, 1200, 122, { align: "right", size: 15, alpha: seg(t, 0.6, 1.2), color: C.soft, fill: C.panel, stroke: C.line });
  // repos
  [0, 4].forEach(i => text(S.rest, x0 + i * (cw + gap) + cw / 2, y + ch / 2 + 6, { size: 17, color: C.faint, align: "center", alpha: seg(t, 0.8, 1.4) }));
  // séances : mardi, mercredi, jeudi dès la 1re réplique ; samedi, dimanche à la 2e
  const times = { tue: a1 + 0.2, wed: a1 + 1.3, thu: a1 + 2.0, sat: a1 + 2.8, sun: a1 + 3.5 };
  SESS.forEach(s => {
    const a = times[s.key], k = outBack(seg(t, a, a + 0.5));
    if (k <= 0) return;
    sessCard(s, s.col, x0, y, cw, ch, gap, { alpha: clamp(k), shadow: true, tsize: s.key === "sat" ? 17 : 18 });
  });
  // le second avis
  const kc = outCubic(seg(t, a2, a2 + 0.6));
  if (kc > 0) {
    const ty = 500;
    const lines = [{ p: "$ ", s: `python3 scripts/arc_guardrails.py check --week ${S.weekFile}`, c: C.accent, a: a2 + 0.2, b: a2 + 1.8 }];
    terminal(84, ty - 20, 1112, 110, t, lines, { alpha: kc, size: 17, lh: 34, title: "bash" });
    const ks = outBack(seg(t, a2 + 1.9, a2 + 2.4));
    if (ks > 0) pill(S.second.toUpperCase(), 1196 - 20, ty + 70, { align: "right", alpha: clamp(ks), size: 14 });
    // balayage de lecture sur la semaine
    const sw = seg(t, a2 + 1.8, a2 + 3.6);
    if (sw > 0 && sw < 1) { ctx.save(); ctx.globalAlpha *= 0.5 * Math.sin(Math.PI * sw); const sx = x0 + sw * 1112; const g = ctx.createLinearGradient(sx - 60, 0, sx, 0); g.addColorStop(0, "rgba(163,230,53,0)"); g.addColorStop(1, "rgba(163,230,53,0.35)"); ctx.fillStyle = g; ctx.fillRect(sx - 60, y, 60, ch); ctx.restore(); }
  }
}

/* ---------------------- 02 · les quatre règles de charge ------------------- */
function meter(x, y, w, v, max, thr, k, col) {
  rr(x, y, w, 10, 5); ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = C.line; ctx.fill(); ctx.restore();
  rr(x, y, Math.max(10, w * clamp(v / max) * outCubic(k)), 10, 5); ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = col; ctx.fill(); ctx.restore();
  const tx = x + w * thr / max;
  line([[tx, y - 8], [tx, y + 18]], C.amber, 2, k);
}
function sLoad(t, d, cues) {
  kicker(S.k2, seg(t, 0, 0.4));
  headline(S.h2, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 7), a2 = at(cues, 2, 10.8);
  const starts = [a0 + 1.0, a1 + 0.1, a1 + 2.6, a2 + 0.1];
  const cw = 265, gap = 20, y = 178, ch = 420;
  S.r.forEach((r, i) => {
    const x = 80 + i * (cw + gap), a = starts[i], k = outCubic(seg(t, a - 0.3, a + 0.4));
    if (k <= 0) return;
    const vk = seg(t, a, a + 1.4), done = seg(t, a + 1.4, a + 1.9);
    panel(x, y + (1 - k) * 16, cw, ch, { alpha: k, shadow: true });
    text(r.id, x + 20, y + 34 + (1 - k) * 16, { size: 12, font: MONO, color: C.faint, alpha: k });
    text(r.title, x + 20, y + 66 + (1 - k) * 16, { size: 17, weight: 700, font: SORA, alpha: k });
    para(r.sub, x + 20, y + 92 + (1 - k) * 16, cw - 40, { size: 14, color: C.soft, alpha: k });
    const vy = y + 146;
    if (i === 0) { // courbe du ratio projeté, jour par jour
      const pts = [0.94, 1.02, 1.09, 1.08, 1.05, 1.18, 1.14].map((v, j) => [x + 24 + j * 36, vy + 90 - (v - 0.8) / 0.6 * 90]);
      const ty = vy + 90 - (1.3 - 0.8) / 0.6 * 90;
      line([[x + 20, ty], [x + cw - 20, ty]], C.amber, 1.5, k * 0.9, [5, 5]);
      text("1,3".replace(",", LANG === "fr" ? "," : "."), x + cw - 20, ty - 6, { size: 11, font: MONO, color: C.amber, align: "right", alpha: k });
      line(partial(pts, vk), C.accent, 3, k);
      pts.forEach(([px, py], j) => dot(px, py, j === 5 ? 6 : 3.5, j === 5 ? C.accent : C.soft, k * seg(vk, j / 7, j / 7 + 0.15)));
      text(S.peak, pts[5][0], pts[5][1] + 26, { size: 11, font: MONO, color: C.accent, align: "center", alpha: k * seg(vk, 0.8, 1) });
    } else if (i === 1 || i === 2) { // deux barres : moyenne 4 semaines vs cette semaine
      const ref = i === 1 ? 363 : 1240, cur = i === 1 ? 385 : 1300, max = ref * 1.14;
      const bh = 88, bx = [x + 44, x + 150];
      [[ref, C.faint, 0], [cur, C.accent, 1]].forEach(([v, c, j]) => {
        const h = bh * v / max * outCubic(vk);
        rr(bx[j], vy + bh - h + 8, 70, h, 6); ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = c; ctx.fill(); ctx.restore();
        text(S.scale[j], bx[j] + 35, vy + bh + 28, { size: 11, font: MONO, color: C.faint, align: "center", alpha: k });
      });
      const ty = vy + bh + 8 - bh * (ref * 1.1) / max;
      line([[x + 24, ty], [x + cw - 24, ty]], C.amber, 1.5, k * 0.9, [5, 5]);
      text("+10 %", x + cw - 24, ty - 6, { size: 11, font: MONO, color: C.amber, align: "right", alpha: k });
    } else { // monotonie : jauge linéaire
      const v = 1.6 * outCubic(vk);
      meter(x + 24, vy + 52, cw - 48, v, 3, 2, k, C.accent);
      text("0", x + 24, vy + 92, { size: 11, font: MONO, color: C.faint, alpha: k });
      text("3", x + cw - 24, vy + 92, { size: 11, font: MONO, color: C.faint, align: "right", alpha: k });
      text("2", x + 24 + (cw - 48) * 2 / 3, vy + 36, { size: 11, font: MONO, color: C.amber, align: "center", alpha: k });
    }
    // valeur, seuil, verdict
    text(r.val, x + 20, y + ch - 74, { size: 44, weight: 800, font: SORA, alpha: k, color: done > 0 ? C.accent : C.ink });
    text(r.thr, x + 22, y + ch - 50, { size: 14, font: MONO, color: C.amber, alpha: k });
    const kd = outBack(seg(t, a + 1.5, a + 2.0));
    if (kd > 0) { check(x + 36, y + ch - 20, 16, C.accent, kd, 1); text(S.below, x + 58, y + ch - 14, { size: 15, weight: 600, color: C.accent, alpha: clamp(kd) }); }
  });
}

/* --------------------------- 03 · santé + sortie longue -------------------- */
function sHealth(t, d, cues) {
  kicker(S.k3, seg(t, 0, 0.4));
  headline(S.h3, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 6.8);
  const y = 172, ch = 330, cw = 546;
  // R5 ---------------------------------------------------------------------
  const k5 = outCubic(seg(t, 0.4, 1.0));
  panel(80, y, cw, ch, { alpha: k5, shadow: true });
  text(S.r5.id, 104, y + 34, { size: 12, font: MONO, color: C.faint, alpha: k5 });
  text(S.r5.title, 104, y + 66, { size: 21, weight: 700, font: SORA, alpha: k5 });
  text(S.r5.sub, 104, y + 92, { size: 15, color: C.soft, alpha: k5 });
  const act5 = a0 + 0.6;
  S.days.forEach((dn, i) => {
    const px = 104 + i * 70 + 24, a = act5 + i * 0.18, k = outBack(seg(t, a, a + 0.35));
    text(dn, px, y + 140, { size: 12, font: MONO, color: C.faint, align: "center", alpha: k5 });
    if (k > 0) { dot(px, y + 176, 17, C.accent, 0.16 * clamp(k)); dot(px, y + 176, 9, C.accent, clamp(k)); }
    if ((i === 1 || i === 2) && k > 0) { text(S.kinds.q, px, y + 224, { size: 11, weight: 700, font: MONO, color: C.amber, align: "center", alpha: clamp(k) }); }
  });
  text(S.verdicts, 104, y + 262, { size: 13, font: MONO, color: C.faint, alpha: k5 });
  const kr = outBack(seg(t, a0 + 2.8, a0 + 3.4));
  if (kr > 0) { check(122, y + ch - 30, 18, C.accent, kr, 1); text(`${S.r5.val} · ${S.r5.ok}`, 146, y + ch - 24, { size: 17, weight: 600, color: C.accent, alpha: clamp(kr) }); }
  sevPill("block", 80 + cw - 24, y + 36, { align: "right", alpha: k5 * (0.5 + 0.5 * seg(t, a0 + 3.8, a0 + 4.4)) });
  // R6 ---------------------------------------------------------------------
  const x6 = 80 + cw + 28, k6 = outCubic(seg(t, a1 - 0.6, a1 + 0.1));
  if (k6 > 0) {
    panel(x6, y, cw, ch, { alpha: k6, shadow: true });
    text(S.r6.id, x6 + 24, y + 34, { size: 12, font: MONO, color: C.faint, alpha: k6 });
    text(S.r6.title, x6 + 24, y + 66, { size: 21, weight: 700, font: SORA, alpha: k6 });
    text(S.r6.sub, x6 + 24, y + 92, { size: 15, color: C.soft, alpha: k6 });
    // barre empilée du volume : 75 + 65 + 45 + 150 + 50 = 385 min
    const segs = [["tue", 75, C.amber], ["wed", 65, C.amber], ["thu", 45, C.teal], ["sat", 150, C.accent], ["sun", 50, C.teal]];
    const bx = x6 + 24, bw = cw - 48, by = y + 150, bh = 46;
    let cx = bx; const kb = seg(t, a1 + 0.2, a1 + 1.8);
    segs.forEach(([key, m, col], i) => {
      const w = bw * m / 385 * outCubic(kb);
      ctx.save(); ctx.globalAlpha *= k6 * (key === "sat" ? 1 : 0.55); ctx.fillStyle = col; rr(cx + 1, by, Math.max(w - 2, 0), bh, 6); ctx.fill(); ctx.restore();
      cx += w;
    });
    // repère 35 %
    const tx = bx + bw * 0.35; line([[tx, by - 12], [tx, by + bh + 12]], C.amber, 2, k6 * kb);
    text("35 %", tx, by - 18, { size: 12, font: MONO, color: C.amber, align: "center", alpha: k6 * kb });
    const lx = bx + bw * 150 / 385;
    text("2 h 30", bx + (bw * (75 + 65 + 45) / 385) + (bw * 150 / 385) / 2, by + bh + 28, { size: 14, font: MONO, color: C.accent, align: "center", alpha: k6 * kb });
    const shown = Math.round(39 * outCubic(seg(t, a1 + 0.4, a1 + 1.8)));
    text(shown + " %", x6 + 24, y + 268, { size: 54, weight: 800, font: SORA, color: C.amber, alpha: k6 });
    text(S.r6.thr, x6 + cw - 24, y + 262, { size: 15, font: MONO, color: C.amber, align: "right", alpha: k6 });
    sevPill("warn", x6 + cw - 24, y + 36, { align: "right", alpha: k6 * (0.5 + 0.5 * seg(t, a1 + 2.4, a1 + 3.0)) });
    const kw = outCubic(seg(t, a1 + 3.6, a1 + 4.2));
    text(S.r6.warn, x6 + 24, y + ch - 20, { size: 16, weight: 600, color: C.soft, alpha: k6 * kw });
  }
  // échelle de sévérité
  const ky = outCubic(seg(t, a0 + 4.2, a0 + 4.8));
  if (ky > 0) {
    const yy = 560, hot = t < a1 + 2.4 ? 2 : 1;
    S.sev.forEach((s, i) => {
      const on = i === hot;
      sevPill(s, 130 + i * 110, yy, { alpha: ky * (on ? 1 : 0.35), size: 15, align: "center" });
    });
    text(S.sevNote, 480, yy + 5, { size: 14, font: MONO, color: C.faint, alpha: ky });
  }
}

/* ------------------------ 04 · r7, la qualité en rafale -------------------- */
function sBack2Back(t, d, cues) {
  kicker(S.k4, seg(t, 0, 0.4));
  headline(S.h4, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 3.4), a2 = at(cues, 2, 5.9);
  const x0 = 84, y = 214, cw = 152, ch = 150, gap = 8;
  strip(t, x0, y, cw, ch, gap, { alpha: i => outCubic(seg(t, 0.3 + i * 0.05, 0.8 + i * 0.05)) });
  const mv = inOut(seg(t, a2 + 0.3, a2 + 1.8));
  const hot = outCubic(seg(t, a1 + 0.2, a1 + 0.8)) * (1 - seg(t, a2 + 0.3, a2 + 1.2));
  SESS.forEach((s, i) => {
    const k = outBack(seg(t, 0.6 + i * 0.12, 1.1 + i * 0.12));
    let col = s.col, lift = 0;
    if (s.key === "wed") { col = lerp(2, 3, mv); lift = -Math.sin(Math.PI * mv) * 40; }
    if (s.key === "thu") { col = lerp(3, 2, mv); lift = Math.sin(Math.PI * mv) * 40; }
    // après l'échange, mercredi devient facile (EF) et jeudi les côtes : on échange les titres
    const o = { alpha: clamp(k), hot: (s.key === "tue" || s.key === "wed") ? hot : 0, shadow: true };
    ctx.save(); ctx.translate(0, lift); sessCard(s, col, x0, y, cw, ch, gap, o); ctx.restore();
  });
  // lien « consécutives » entre mardi et mercredi
  if (hot > 0) {
    const ax = x0 + 1 * (cw + gap) + cw, bx = x0 + 2 * (cw + gap);
    line([[ax - 6, y + ch / 2], [bx + 6, y + ch / 2]], C.amber, 3, hot);
    text("Q → Q", (ax + bx) / 2, y + ch + 24, { size: 13, weight: 700, font: MONO, color: C.amber, align: "center", alpha: hot });
  }
  // carte de violation r7
  const kv = outCubic(seg(t, a1 + 0.9, a1 + 1.5)) * (1 - seg(t, a2 + 1.8, a2 + 2.3));
  if (kv > 0) {
    const vy = 424 + (1 - kv) * 18;
    panel(84, vy, 1112, 124, { fill: "rgba(240,180,60,0.07)", stroke: "rgba(240,180,60,0.55)", alpha: kv, shadow: true });
    text(S.r7.id, 112, vy + 38, { size: 17, weight: 700, font: MONO, color: C.amber, alpha: kv });
    sevPill("warn", 1170, vy + 32, { align: "right", alpha: kv });
    para(S.r7.msg, 112, vy + 76, 1040, { size: 20, alpha: kv });
  }
  // r7 résolu
  const ko = outBack(seg(t, a2 + 2.3, a2 + 2.9));
  if (ko > 0) {
    const vy = 424;
    panel(84, vy, 1112, 124, { fill: "rgba(163,230,53,0.06)", stroke: "rgba(163,230,53,0.5)", alpha: clamp(ko), shadow: true });
    check(124, vy + 46, 24, C.accent, ko, 1);
    text(S.r7.id, 164, vy + 52, { size: 20, weight: 700, font: MONO, color: C.accent, alpha: clamp(ko) });
    text(S.r7ok, 164, vy + 92, { size: 19, color: C.soft, alpha: clamp(ko) });
  }
  text(S.qdef, 84, 596, { size: 14, font: MONO, color: C.faint, alpha: seg(t, 1.2, 1.8) });
  const kn = seg(t, a2 + 0.3, a2 + 0.8) * (1 - seg(t, a2 + 2.0, a2 + 2.4));
  if (kn > 0) pill(S.moveNote, 1200, 122, { align: "right", alpha: kn, size: 15 });
}

/* ------------------------------- 05 · décision ----------------------------- */
function sTrace(t, d, cues) {
  kicker(S.k5, seg(t, 0, 0.4));
  headline(S.h5, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.6);
  const kt = outCubic(seg(t, 0.3, 0.9));
  const colors = [C.ink, C.faint, C.accent, C.accent, C.accent, C.accent, C.accent, C.accent, C.accent, C.accent, C.accent, C.faint, C.soft];
  const lines = S.dec.map((s, i) => ({ s, a: 0.8 + i * 0.28, b: 1.05 + i * 0.28, c: colors[i], w: i === 0 ? 700 : 400 }));
  const tx = 80, ty = 168, tw = 770, th = 460, lh = 31;
  terminal(tx, ty, tw, th, t, lines, { alpha: kt, size: 17, lh, title: S.decFile.split("/")[1] });
  // surlignage des lignes citées par la voix : règle, avant, après
  const rows = [6, 7, 8], st = [a0 + 2.4, a0 + 3.4, a0 + 4.2];
  rows.forEach((r, i) => {
    const k = seg(t, st[i], st[i] + 0.5);
    if (k <= 0) return;
    const yy = ty + 62 + r * lh - 19;
    ctx.save(); ctx.globalAlpha *= 0.9 * k; rr(tx + 12, yy, tw - 24, 28, 6); ctx.fillStyle = "rgba(163,230,53,0.10)"; ctx.fill(); ctx.strokeStyle = "rgba(163,230,53,0.6)"; ctx.lineWidth = 1.5; ctx.stroke(); ctx.restore();
  });
  // légende à droite
  S.decTags.forEach(([lab, val], i) => {
    const k = outCubic(seg(t, st[i], st[i] + 0.5));
    if (k <= 0) return;
    const x = 890 + (1 - k) * 30, y = 200 + i * 98;
    panel(x, y, 310, 80, { r: 14, fill: C.panel2, stroke: C.accent, alpha: k });
    text(lab.toUpperCase(), x + 20, y + 30, { size: 12, weight: 600, font: MONO, color: C.faint, alpha: k, spacing: "2px" });
    text(val, x + 20, y + 58, { size: i === 0 ? 16 : 20, weight: 700, font: i === 0 ? MONO : SORA, alpha: k });
    line([[x, y + 40], [tx + tw - 14, ty + 62 + rows[i] * lh - 6]], C.accent, 1.2, 0.5 * k);
  });
  // validation
  const kv = outBack(seg(t, a0 + 5.0, a0 + 5.6));
  if (kv > 0) {
    const y = 560;
    panel(890, y - 18, 310, 62, { r: 14, fill: "rgba(163,230,53,0.07)", stroke: "rgba(163,230,53,0.5)", alpha: clamp(kv) });
    check(916, y + 12, 16, C.accent, kv, 1);
    text(S.validate, 940, y + 18, { size: 14, weight: 600, font: MONO, color: C.accent, alpha: clamp(kv) });
  }
}

/* --------------------------- 06 · cibles personnelles ---------------------- */
function sTargets(t, d, cues) {
  kicker(S.k6, seg(t, 0, 0.4));
  headline(S.h6, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.6);
  const kc = outCubic(seg(t, 0.3, 0.9));
  terminal(80, 160, 1120, 88, t, [{ p: "$ ", s: S.tgCmd, c: C.accent, a: a0 + 0.3, b: a0 + 2.6 }], { alpha: kc, size: 15, lh: 30, title: "bash" });
  const cw = 360, gap = 20, y = 268, ch = 330;
  const zb = [[46, 146, "Z1"], [146, 155, "Z2"], [155, 163, "Z3"], [163, 172, "Z4"], [172, 188, "Z5"]];
  S.tg.forEach((g, i) => {
    const x = 80 + i * (cw + gap), a = a0 + 2.8 + i * 0.35, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    const wi = [3, 1, 4][i];
    panel(x, y + (1 - k) * 14, cw, ch, { alpha: k, shadow: true });
    text(g.day, x + 22, y + 34 + (1 - k) * 14, { size: 13, weight: 600, font: MONO, color: C.faint, alpha: k, spacing: "2px" });
    text(g.title, x + 22, y + 66 + (1 - k) * 14, { size: 22, weight: 700, font: SORA, alpha: k });
    // ligne 1 : zone cardiaque
    const r1 = seg(t, a1 + 0.2, a1 + 1.0);
    const zx = x + 22, zw = cw - 44, zy = y + 112;
    text(S.tgRows[0].toUpperCase(), zx, zy - 12, { size: 11, font: MONO, color: C.faint, alpha: k * r1, spacing: "1px" });
    zb.forEach(([lo, hi, n], j) => {
      const fx = zx + zw * (Math.max(lo, 110) - 110) / 78, fw = zw * (hi - Math.max(lo, 110)) / 78;
      ctx.save(); ctx.globalAlpha *= k * r1; rr(fx + 1, zy, fw - 2, 22, 3); ctx.fillStyle = j === wi ? C.accent : "#26382e"; ctx.fill(); ctx.restore();
    });
    text(g.zone, zx, zy + 50, { size: 19, weight: 700, font: MONO, color: C.accent, alpha: k * r1 });
    // ligne 2 : allure
    const r2 = seg(t, a1 + 1.8, a1 + 2.6);
    text(S.tgRows[1].toUpperCase(), zx, y + 202, { size: 11, font: MONO, color: C.faint, alpha: k * r2, spacing: "1px" });
    text(g.pace, zx, y + 230, { size: 19, weight: g.pace === "—" ? 400 : 700, font: MONO, color: g.pace === "—" ? C.faint : C.ink, alpha: k * r2 });
    // ligne 3 : D+
    const r3 = seg(t, a1 + 3.2, a1 + 4.0);
    text(S.tgRows[2].toUpperCase(), zx, y + 266, { size: 11, font: MONO, color: C.faint, alpha: k * r3, spacing: "1px" });
    text(g.dp, zx, y + 296, { size: 19, weight: g.dp === "—" ? 400 : 700, font: MONO, color: g.dp === "—" ? C.faint : C.ink, alpha: k * r3 });
  });
  text(S.lthr, 80, 626, { size: 13, font: MONO, color: C.faint, alpha: seg(t, a1 + 0.4, a1 + 1.0) });
  text(S.tgNote, 1200, 626, { size: 13, font: MONO, color: C.soft, align: "right", alpha: seg(t, a1 + 4.0, a1 + 4.6) });
}

/* --------------------------- 07 · push et vérification --------------------- */
function sPush(t, d, cues) {
  kicker(S.k7, seg(t, 0, 0.4));
  headline(S.h7, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5), a2 = at(cues, 2, 8.4);
  const cw = 265, gap = 20, y = 164, ch = 118;
  const st = [a0 + 0.3, a0 + 2.6, a0 + 3.6, a1 + 0.1];
  S.steps.forEach(([title, tool, res], i) => {
    const x = 80 + i * (cw + gap), k = outCubic(seg(t, st[i], st[i] + 0.5)), done = seg(t, st[i] + 0.7, st[i] + 1.2);
    if (k <= 0) return;
    panel(x, y + (1 - k) * 12, cw, ch, { alpha: k, fill: i === 3 && done > 0 ? "rgba(163,230,53,0.06)" : C.panel, stroke: done > 0 ? "rgba(163,230,53,0.5)" : C.line });
    text(String(i + 1), x + 20, y + 40 + (1 - k) * 12, { size: 26, weight: 800, font: SORA, color: C.accent, alpha: k });
    text(title, x + 52, y + 38 + (1 - k) * 12, { size: 21, weight: 700, font: SORA, alpha: k });
    text(tool, x + 20, y + 70 + (1 - k) * 12, { size: 14, font: MONO, color: C.soft, alpha: k });
    text(res, x + 44, y + 98 + (1 - k) * 12, { size: 14, font: MONO, color: C.accent, alpha: k * done });
    check(x + 26, y + 94, 12, C.accent, done, k);
    if (i < 3) arrow(x + cw + 2, y + ch / 2, x + cw + gap - 2, y + ch / 2, seg(t, st[i + 1] - 0.3, st[i + 1]), C.faint, 1);
  });
  // calendrier
  const cy = 318, cx0 = 80, cwid = 152, cgap = 8, chh = 150;
  const kc = outCubic(seg(t, a0 + 2.8, a0 + 3.4));
  text(S.cal.toUpperCase(), 80, cy - 14, { size: 12, weight: 600, font: MONO, color: C.faint, spacing: "2px", alpha: kc });
  const ev = [["tue", 1, "q"], ["wed", 2, "e"], ["thu", 3, "q"], ["sat", 5, "l"], ["sun", 6, "e"]];
  const titles = { tue: S.tue, wed: LANG === "fr" ? "EF 45'" : "Easy 45'", thu: LANG === "fr" ? "Côtes 8 × 1'" : "Hills 8 × 1'", sat: S.sat, sun: S.sun };
  const durs = { tue: S.d.tue, wed: S.d.thu, thu: S.d.wed, sat: S.d.sat, sun: S.d.sun };
  for (let i = 0; i < 7; i++) {
    const x = cx0 + i * (cwid + cgap);
    panel(x, cy, cwid, chh, { r: 12, fill: "rgba(19,32,26,0.4)", alpha: kc });
    text(S.days[i], x + 12, cy + 24, { size: 12, font: MONO, color: C.faint, alpha: kc });
  }
  ev.forEach(([key, col, kind], i) => {
    const a = st[2] + 0.4 + i * 0.28, k = outBack(seg(t, a, a + 0.4));
    if (k <= 0) return;
    const x = cx0 + col * (cwid + cgap), c = KCOL[kind];
    const dy = (1 - clamp(k)) * -26;
    panel(x + 8, cy + 38 + dy, cwid - 16, 92, { r: 10, fill: C.panel2, stroke: c, alpha: clamp(k) });
    text(titles[key], x + 18, cy + 68 + dy, { size: 17, weight: 700, font: SORA, alpha: clamp(k) });
    text(durs[key], x + 18, cy + 93 + dy, { size: 15, font: MONO, color: C.soft, alpha: clamp(k) });
    const v = seg(t, a1 + 0.8 + i * 0.4, a1 + 1.2 + i * 0.4);
    if (v > 0) { dot(x + cwid - 32, cy + 114 + dy, 11, C.accent, 0.18 * v); check(x + cwid - 32, cy + 114 + dy, 12, C.accent, v, 1); }
  });
  // la conclusion
  const kt = outCubic(seg(t, a2 - 0.2, a2 + 0.6));
  if (kt > 0) {
    const ty = 500 + (1 - kt) * 20;
    panel(80, ty, 1120, 112, { fill: "#0a120e", stroke: C.accent, lw: 2, alpha: kt, shadow: true });
    // bouclier
    ctx.save(); ctx.globalAlpha *= kt; ctx.translate(140, ty + 56);
    ctx.beginPath(); ctx.moveTo(0, -34); ctx.lineTo(28, -24); ctx.lineTo(28, 4); ctx.quadraticCurveTo(28, 24, 0, 36); ctx.quadraticCurveTo(-28, 24, -28, 4); ctx.lineTo(-28, -24); ctx.closePath();
    ctx.fillStyle = "rgba(163,230,53,0.14)"; ctx.fill(); ctx.strokeStyle = C.accent; ctx.lineWidth = 3; ctx.stroke(); ctx.restore();
    check(140, ty + 58, 24, C.accent, seg(t, a2 + 0.3, a2 + 0.9), kt);
    text(S.tag, 200, ty + 50, { size: 25, weight: 800, font: SORA, alpha: kt });
    text(S.tag2, 200, ty + 86, { size: 21, weight: 600, color: C.accent, alpha: kt * seg(t, a2 + 1.4, a2 + 2.0) });
    text(S.tests, 1176, ty + 92, { size: 13, font: MONO, color: C.faint, align: "right", alpha: kt * seg(t, a2 + 1.8, a2 + 2.4) });
  }
}

ARC.episode({
  n: 3, slug: "garde-fous",
  strings: STR,
  shots: [],
  scenes: { week: sWeek, load: sLoad, health: sHealth, back2back: sBack2Back, trace: sTrace, targets: sTargets, push: sPush },
});
})();
