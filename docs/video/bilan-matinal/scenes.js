/* Le Sentier · étape 2 — « Le réveil du traileur » : le bilan matinal.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}] —
 * at(cues, i, repli) cale une animation sur la voix, quelle que soit la langue.
 * Athlète et chiffres fictifs (bible de la série : Camille, mardi 29 septembre 2026). */
"use strict";
(() => {
const STR = {
  fr: {
    day: "Mardi 29 septembre", plan: "Au programme", planVal: "Seuil · 5 × 6 min",
    n1: ["Sommeil", "6 h 12"], n2: ["HRV nocturne", "38 ms"], n3: ["Garmin", "synchronisé"],
    k2: "01 · LE TRIPTYQUE", h2: "Trois signaux. Jamais deux.",
    g: [["HRV nocturne", "ms", "bande perso 52-70"], ["FC de repos", "bpm", "médiane 7 j : 46"], ["Readiness", "/100", "faible sous 40"]],
    g3: ["3 nuits sous la bande", "+6 bpm", "faible"],
    nights: "7 dernières nuits",
    k3: "02 · LE VERDICT", h3: "Alléger.",
    was: "Mardi · Seuil 5 × 6 min", now: "Mardi · EF 45 min", nowSub: "endurance fondamentale · zone 2",
    moved: "Seuil reporté", slot: "Soir 18 h-19 h · 19 °C · vent 10 km/h", slotTag: "créneau optimal",
    lamps: ["Maintenir", "Alléger", "Repos"],
    k4: "03 · TRACÉ", h4: "Écrit noir sur blanc.",
    file: "planning/2026-09-29_decision_bilan-matinal.md",
    md: ["# Décision — bilan matinal", "```arc", '{"arc": 1, "kind": "decision",', ' "date": "2026-09-29",', ' "trigger": "morning_check",', ' "outcome": "applied",', ' "inputs": {"hrv_overnight_ms": 38, …},', ' "sources": ["medical/2026-09-29_health.md"]}', "```", "Seuil reporté : signaux à revoir."],
    dash: "Tableau de bord · Aujourd'hui",
    k5: "04 · /WHY", h5: "La raison, jamais inventée.",
    whyQ: "/why", whyA: [
      ["Mardi 29 · bilan matinal → alléger", C.ink, 700],
      ["• HRV 38 ms : sous la bande 52-70 depuis 3 nuits", C.soft, 400],
      ["• FC de repos 52 bpm : +6 vs médiane 7 j (46)", C.soft, 400],
      ["• Readiness 34/100 : faible", C.soft, 400],
      ["Sources : medical/2026-09-29_health.md", C.faint, 400],
      ["Décision : planning/2026-09-29_decision_bilan-matinal.md", C.faint, 400],
    ],
    k6: "05 · À VOTRE MESURE", h6: "Le bilan se règle.",
    lv: [["full", "HRV + FC de repos + readiness, avant toute décision", "défaut"],
         ["minimal", "Readiness seule, rapportée en une ligne", ""],
         ["off", "Aucune donnée santé : charge, historique, ressenti", ""]],
    never: "Jamais réactivé en douce à un niveau plus strict.",
  },
  en: {
    day: "Tuesday, September 29", plan: "On the plan", planVal: "Threshold · 5 × 6 min",
    n1: ["Sleep", "6 h 12"], n2: ["Overnight HRV", "38 ms"], n3: ["Garmin", "synced"],
    k2: "01 · THE TRIAD", h2: "Three signals. Never two.",
    g: [["Overnight HRV", "ms", "personal band 52-70"], ["Resting HR", "bpm", "7-day median: 46"], ["Readiness", "/100", "low below 40"]],
    g3: ["3 nights below band", "+6 bpm", "low"],
    nights: "last 7 nights",
    k3: "02 · THE VERDICT", h3: "Ease off.",
    was: "Tuesday · Threshold 5 × 6 min", now: "Tuesday · Easy 45 min", nowSub: "easy endurance · zone 2",
    moved: "Threshold postponed", slot: "Evening 6-7 pm · 19 °C · wind 10 km/h", slotTag: "best window",
    lamps: ["Keep", "Ease off", "Rest"],
    k4: "03 · TRACEABLE", h4: "Written down.",
    file: "planning/2026-09-29_decision_bilan-matinal.md",
    md: ["# Décision — bilan matinal", "```arc", '{"arc": 1, "kind": "decision",', ' "date": "2026-09-29",', ' "trigger": "morning_check",', ' "outcome": "applied",', ' "inputs": {"hrv_overnight_ms": 38, …},', ' "sources": ["medical/2026-09-29_health.md"]}', "```", "Seuil reporté : signaux à revoir."],
    dash: "Dashboard · Today (French UI)",
    k5: "04 · /WHY", h5: "The reason, never made up.",
    whyQ: "/why", whyA: [
      ["Tue 29 · morning check → ease off", C.ink, 700],
      ["• HRV 38 ms: below the 52-70 band for 3 nights", C.soft, 400],
      ["• Resting HR 52 bpm: +6 vs 7-day median (46)", C.soft, 400],
      ["• Readiness 34/100: low", C.soft, 400],
      ["Sources: medical/2026-09-29_health.md", C.faint, 400],
      ["Decision: planning/2026-09-29_decision_bilan-matinal.md", C.faint, 400],
    ],
    k6: "05 · YOUR CALL", h6: "The check is configurable.",
    lv: [["full", "HRV + resting HR + readiness, before any decision", "default"],
         ["minimal", "Readiness only, reported in one line", ""],
         ["off", "No health data: load, history, how you feel", ""]],
    never: "Never quietly switched back to a stricter level.",
  },
};

/* ---------------------------- 6 h 30 : l'aube ---------------------------- */
function sAlarm(t, d, cues) {
  // ciel d'aube qui s'éclaire
  const dawn = seg(t, 0, d);
  const g = ctx.createLinearGradient(0, 0, 0, 560);
  g.addColorStop(0, "rgba(13,20,16,0)"); g.addColorStop(1, `rgba(240,180,60,${0.05 + 0.13 * dawn})`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, 560);
  const sy = lerp(560, 420, outCubic(dawn));
  dot(930, sy, 70, C.amber, 0.18); dot(930, sy, 44, C.amber, 0.55);
  [[0.2, 470, 120, "#14271e"], [1.4, 520, 90, "#0f1c16"]].forEach(([ph, base, amp, col]) => {
    ctx.beginPath(); ctx.moveTo(0, H);
    for (let i = 0; i <= 160; i++) { const u = i / 160; ctx.lineTo(u * W, base - amp * ridge(u, ph)); }
    ctx.lineTo(W, H); ctx.closePath(); ctx.fillStyle = col; ctx.fill();
  });
  // montre
  const kw = outBack(seg(t, 0.2, 1.0));
  const cx = 330, cy = 320;
  ctx.save(); ctx.translate(cx, cy); ctx.scale(clamp(kw, 0, 1.2), clamp(kw, 0, 1.2));
  rr(-46, -168, 92, 60, 10); ctx.fillStyle = C.line; ctx.fill();
  rr(-46, 108, 92, 60, 10); ctx.fill();
  dot(0, 0, 130, "#33463b"); dot(0, 0, 118, "#050806");
  const pulse = 0.5 + 0.5 * Math.sin(t * 6);
  ctx.beginPath(); ctx.arc(0, 0, 108, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * seg(t, 0.6, 2.4) * 0.72);
  ctx.strokeStyle = C.accent; ctx.lineWidth = 5; ctx.lineCap = "round"; ctx.stroke();
  text("06:30", 0, 14, { size: 54, weight: 700, font: SORA, align: "center" });
  text(S.day, 0, 50, { size: 15, color: C.soft, align: "center" });
  if (t < at(cues, 1, 3.5)) ring(0, 0, 130 + 14 * pulse, C.amber, 2, 0.5 * (1 - seg(t, 2.6, 3.4)));
  ctx.restore();
  // notifications
  const items = [[S.plan, S.planVal, C.accent], S.n1.concat(C.soft), S.n2.concat(C.amber), S.n3.concat(C.teal)];
  items.forEach(([lab, val, col], i) => {
    const a = i === 0 ? at(cues, 0, 0.6) + 1.6 : at(cues, 1, 3.6) + (i - 1) * 0.45;
    const k = outCubic(seg(t, a, a + 0.6));
    if (k <= 0) return;
    const x = 600 + (1 - k) * 80, y = 170 + i * 92;
    panel(x, y, 470, 74, { r: 18, fill: i === 2 ? "rgba(240,180,60,0.10)" : C.panel2, stroke: i === 2 ? "rgba(240,180,60,0.5)" : C.line, alpha: k, shadow: true });
    dot(x + 30, y + 37, 6, col, k);
    text(lab, x + 50, y + 31, { size: 13, font: MONO, color: C.faint, alpha: k });
    text(val, x + 50, y + 56, { size: 21, weight: 700, font: SORA, alpha: k });
  });
}

/* ------------------------------ le triptyque ----------------------------- */
function gauge(cx, cy, r, v, band, k, color) {
  const a0 = Math.PI * 0.75, a1 = Math.PI * 2.25, A = u => lerp(a0, a1, u);
  ctx.save(); ctx.globalAlpha *= k; ctx.lineCap = "round";
  ctx.beginPath(); ctx.arc(cx, cy, r, a0, a1); ctx.strokeStyle = C.line; ctx.lineWidth = 12; ctx.stroke();
  ctx.beginPath(); ctx.arc(cx, cy, r, A(band[0]), A(band[1])); ctx.strokeStyle = "rgba(184,196,189,0.32)"; ctx.lineWidth = 12; ctx.stroke();
  const vv = v * outCubic(k);
  ctx.beginPath(); ctx.arc(cx, cy, r, a0, A(vv)); ctx.strokeStyle = color; ctx.lineWidth = 5; ctx.stroke();
  ctx.restore();
  dot(cx + r * Math.cos(A(vv)), cy + r * Math.sin(A(vv)), 9, color, k);
}
function sTriptych(t, d, cues) {
  kicker(S.k2, seg(t, 0, 0.4));
  headline(S.h2, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const vals = [38, 52, 34];
  const pos = [[38 - 20, 60, [32 / 60, 50 / 60]], [52 - 30, 40, [0.3, 0.55]], [34, 100, [0.55, 1]]];
  const warn = seg(t, at(cues, 1, 5), at(cues, 1, 5) + 0.6);
  for (let i = 0; i < 3; i++) {
    const x = 80 + i * 380, y = 190, w = 340, h = 370;
    const a = at(cues, 0, 0.6) + 2.0 + i * 1.3;
    const k = outCubic(seg(t, a - 1.0, a));
    if (k <= 0) continue;
    const hot = warn > 0;
    panel(x, y + (1 - k) * 20, w, h, { alpha: k, fill: hot ? "rgba(240,180,60,0.06)" : C.panel, stroke: hot ? `rgba(240,180,60,${0.25 + 0.3 * warn})` : C.line });
    const [lab, unit, note] = S.g[i];
    text(lab, x + 26, y + 44, { size: 18, weight: 700, font: SORA, alpha: k });
    const cx = x + w / 2, cy = y + 170;
    const [num, den, band] = pos[i];
    gauge(cx, cy, 92, num / den, band, seg(t, a - 0.6, a + 0.8), hot ? C.amber : C.accent);
    const shown = Math.round(vals[i] * outCubic(seg(t, a - 0.6, a + 0.8)));
    text(String(shown), cx, cy + 14, { size: 52, weight: 800, font: SORA, align: "center", alpha: k });
    text(unit, cx, cy + 42, { size: 14, font: MONO, color: C.soft, align: "center", alpha: k });
    text(note, cx, y + 300, { size: 14, font: MONO, color: C.faint, align: "center", alpha: k });
    text(S.g3[i], cx, y + 336, { size: 16, weight: 700, color: C.amber, align: "center", alpha: warn });
  }
  // nuits : 4 dans la bande, 3 sous la bande
  const kn = seg(t, at(cues, 1, 5) + 0.4, at(cues, 1, 5) + 1.4);
  if (kn > 0) {
    const nights = [61, 58, 64, 56, 45, 41, 38], x0 = 470, y0 = 612;
    text(S.nights, x0 - 20, y0 + 4, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kn });
    ctx.save(); ctx.globalAlpha *= kn; rr(x0, y0 - 34, 330, 29, 4); ctx.fillStyle = "rgba(184,196,189,0.16)"; ctx.fill(); ctx.restore();
    const pts = nights.map((v, i) => [x0 + 10 + i * 51.7, y0 - 10 - (v - 55) * 1.6]);
    line(partial(pts, kn), C.soft, 2, kn);
    pts.forEach(([px, py], i) => dot(px, py, 4.5, i >= 4 ? C.amber : C.soft, seg(kn, i / 7, i / 7 + 0.15)));
  }
}

/* ------------------------------- le verdict ------------------------------ */
function sVerdict(t, d, cues) {
  kicker(S.k3, seg(t, 0, 0.4));
  const kh = seg(t, at(cues, 0, 0.5), at(cues, 0, 0.5) + 0.5);
  text(S.h3, 80, 150 + (1 - outCubic(kh)) * 18, { size: 64, weight: 800, font: SORA, color: C.amber, alpha: kh, spacing: "-2px" });
  // feu tricolore
  const lx = 150, ly = 230;
  const kp = outCubic(seg(t, 0.2, 0.8));
  panel(lx - 50, ly, 100, 290, { r: 50, fill: "#0a120e", stroke: "#33463b", alpha: kp });
  const cols = [C.accent, C.amber, C.red];
  const on = seg(t, at(cues, 0, 0.5) - 0.3, at(cues, 0, 0.5) + 0.2);
  cols.forEach((c, i) => {
    const y = ly + 55 + i * 90;
    dot(lx, y, 34, c, kp * (i === 1 ? 0.15 + 0.85 * on : 0.12));
    if (i === 1 && on > 0) dot(lx, y, 52, c, 0.18 * on);
    text(S.lamps[i], lx + 70, y + 6, { size: 16, weight: i === 1 ? 700 : 400, color: i === 1 && on > 0.5 ? C.amber : C.faint, alpha: kp });
  });
  // la séance qui bascule
  const sx = 520, sy = 230, sw = 620, sh = 130;
  const a1 = at(cues, 1, 2.4);
  const flip = seg(t, a1 - 0.2, a1 + 0.6);
  const scaleY = Math.abs(Math.cos(Math.PI * flip));
  const after = flip > 0.5;
  const kc = outCubic(seg(t, 0.6, 1.2));
  ctx.save(); ctx.translate(0, sy + sh / 2); ctx.scale(1, Math.max(scaleY, 0.02)); ctx.translate(0, -(sy + sh / 2));
  panel(sx, sy, sw, sh, { r: 18, fill: after ? "rgba(30,77,59,0.9)" : C.panel2, stroke: after ? C.accent : C.line, alpha: kc, shadow: true });
  text(after ? S.now : S.was, sx + 30, sy + 58, { size: 28, weight: 700, font: SORA, alpha: kc });
  if (after) text(S.nowSub, sx + 30, sy + 94, { size: 16, color: C.soft, alpha: kc });
  else line([[sx + 30, sy + 50], [sx + 30 + (sw - 60) * seg(t, at(cues, 0, 0.5), at(cues, 0, 0.5) + 0.8), sy + 50]], C.amber, 3, kc * 0.9);
  ctx.restore();
  const km = outBack(seg(t, a1 + 0.9, a1 + 1.4));
  if (km > 0) pill(S.moved, sx, sy + sh + 40, { alpha: clamp(km), size: 16, color: C.ink, fill: C.panel, stroke: C.line });
  // créneau météo
  const ks = outCubic(seg(t, a1 + 2.2, a1 + 2.8));
  if (ks > 0) {
    panel(sx, 470, sw, 70, { r: 16, fill: C.panel, alpha: ks });
    dot(sx + 40, 505, 12, C.amber, ks);
    for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4 + t * 0.4; line([[sx + 40 + 17 * Math.cos(a), 505 + 17 * Math.sin(a)], [sx + 40 + 22 * Math.cos(a), 505 + 22 * Math.sin(a)]], C.amber, 2, ks); }
    text(S.slot, sx + 72, 511, { size: 18, weight: 600, alpha: ks });
    text(S.slotTag, sx + sw - 24, 511, { size: 13, font: MONO, color: C.accent, align: "right", alpha: ks });
  }
}

/* ---------------------------- tracé : fichier + tableau de bord ----------- */
function sTrace(t, d, cues) {
  kicker(S.k4, seg(t, 0, 0.4));
  headline(S.h4, seg(t, 0.1, 0.7));
  const kt = outCubic(seg(t, 0.3, 0.9));
  const lines = S.md.map((s, i) => ({ s, a: 0.9 + i * 0.35, b: 1.2 + i * 0.35, c: i === 0 ? C.ink : s.startsWith("```") ? C.faint : i === S.md.length - 1 ? C.soft : C.accent, w: i === 0 ? 700 : 400 }));
  terminal(80, 190, 500, 400, t, lines, { alpha: kt, size: 14, lh: 30, title: S.file.split("/")[1] });
  // tableau de bord réel (capture), zoom sur « Pourquoi aujourd'hui ? »
  const a1 = at(cues, 1, 3.5);
  const ks = outCubic(seg(t, a1 - 0.6, a1));
  if (ks <= 0) return;
  const x = 620, y = 176, w = 580, h = 430;
  const full = cropTo("aujourdhui", [0, 0, 1440, 1100], w / (h - 30), 0);
  const zoom = cropTo("aujourdhui", "pourquoi", w / (h - 30), 24) || full;
  const kz = inOut(seg(t, a1 + 0.8, a1 + 2.0));
  const map = shot("aujourdhui", x + (1 - ks) * 60, y, w, h, { alpha: ks, crop: full && zoom ? lerpRect(full, zoom, kz) : undefined });
  const b = map("pourquoi");
  if (b) highlight(b[0], b[1], b[2], b[3], seg(t, a1 + 2.0, a1 + 2.6));
  text(S.dash, x + w, y + h + 26, { size: 13, font: MONO, color: C.faint, align: "right", alpha: ks });
}

/* ----------------------------------- /why -------------------------------- */
function sWhy(t, d, cues) {
  kicker(S.k5, seg(t, 0, 0.4));
  headline(S.h5, seg(t, 0.1, 0.7));
  const k = outCubic(seg(t, 0.3, 0.9));
  const a0 = at(cues, 0, 0.6);
  const lines = [{ p: "> ", s: S.whyQ, c: C.accent, w: 700, a: a0 - 0.2, b: a0 + 0.4 }];
  S.whyA.forEach(([s, c, w], i) => lines.push({ s, c, w, a: a0 + 1.2 + i * 0.55, b: a0 + 1.6 + i * 0.55 }));
  terminal(160, 190, 960, 380, t, lines, { alpha: k, size: 19, lh: 44, title: "Claude Code · coach" });
  // « jamais inventé » : chaque chiffre renvoie à sa source
  const a1 = at(cues, 1, 5);
  const kv = outBack(seg(t, a1, a1 + 0.5));
  if (kv > 0) pill("✓ " + (LANG === "fr" ? "sources citées" : "sources quoted"), 1120, 620, { align: "right", alpha: clamp(kv), size: 16 });
}

/* ------------------------------- niveaux --------------------------------- */
function sLevels(t, d, cues) {
  kicker(S.k6, seg(t, 0, 0.4));
  headline(S.h6, seg(t, 0.1, 0.7));
  // le sélecteur parcourt full → minimal → off puis revient à full
  const a0 = at(cues, 0, 0.6);
  const steps = [a0 + 2.6, a0 + 3.4, a0 + 4.2, a0 + 5.6];
  const sel = t < steps[1] ? 0 : t < steps[2] ? 1 : t < steps[3] ? 2 : 0;
  S.lv.forEach(([key, desc, tag], i) => {
    const k = outCubic(seg(t, 0.4 + i * 0.25, 1.0 + i * 0.25));
    const y = 200 + i * 104;
    const on = t > steps[0] && sel === i;
    panel(80, y, 640, 84, { r: 18, fill: on ? "rgba(163,230,53,0.08)" : C.panel, stroke: on ? C.accent : C.line, alpha: k, lw: on ? 2 : 1 });
    ring(124, y + 42, 13, on ? C.accent : C.faint, 2, k);
    if (on) dot(124, y + 42, 7, C.accent, k);
    text(key, 156, y + 36, { size: 20, weight: 700, font: MONO, color: on ? C.accent : C.ink, alpha: k });
    text(desc, 156, y + 62, { size: 15, color: C.soft, alpha: k });
    if (tag) text(tag, 696, y + 36, { size: 12, font: MONO, color: C.faint, align: "right", alpha: k });
  });
  const kc = outCubic(seg(t, 1.0, 1.6));
  const val = ["full", "minimal", "off"][sel];
  terminal(780, 200, 420, 180, t, [
    { s: "# config/workspace.user.toml", c: C.faint },
    { s: "[health]", c: C.ink },
    { s: `morning_check = "${val}"`, c: C.accent },
  ], { alpha: kc, size: 16, lh: 32 });
  const a1 = at(cues, 1, 6);
  const kl = outBack(seg(t, a1, a1 + 0.6));
  if (kl > 0) {
    ctx.save(); ctx.globalAlpha *= clamp(kl);
    // cadenas
    const lx = 800, ly = 470;
    ctx.beginPath(); ctx.arc(lx, ly - 8, 11, Math.PI, 0); ctx.strokeStyle = C.accent; ctx.lineWidth = 3; ctx.stroke();
    rr(lx - 15, ly - 8, 30, 24, 5); ctx.fillStyle = C.accent; ctx.fill();
    ctx.restore();
    para(S.never, 830, 466, 370, { size: 17, weight: 600, alpha: clamp(kl) });
  }
}

ARC.episode({
  n: 2, slug: "bilan-matinal",
  strings: STR,
  shots: ["aujourdhui"],
  scenes: { alarm: sAlarm, triptych: sTriptych, verdict: sVerdict, trace: sTrace, why: sWhy, levels: sLevels },
});
})();
