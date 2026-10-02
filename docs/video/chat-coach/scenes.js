/* Le Sentier · étape 4 — « Parler à son coach » : le chat du tableau de bord.
 * Moteur : ../engine/engine.js. Découpage et narration : script.json.
 * Captures réelles (../shots/) du backend `mock` rejouant docs/video/data/chat-scenario.fr.json.
 * Athlète et chiffres fictifs (bible de la série : Camille, mardi 29 septembre 2026). */
"use strict";
(() => {
const STR = {
  fr: {
    k1: "01 · UNE QUESTION", h1: "Écrire au coach.",
    q: "Je me sens vidé·e ce matin, je fais quand même mon seuil ?",
    chips: "ou un raccourci : /today /week /why /race /log",
    dash: "Tableau de bord · Coach",
    k2: "02 · LA TRACE", h2: "Chaque étape à découvert.",
    trace: "6 étapes : fichiers lus, outils appelés", table: "Les trois signaux du bilan matinal",
    k3: "03 · L'ACCORD", h3: "Rien n'est écrit sans vous.",
    needs: "Confirmation avant toute écriture", diff: "Avant / après", file: "Décision écrite dans planning/",
    apply: "Appliquer",
    k4: "04 · LA SUITE", h4: "Même conversation.",
    kept: "Sortie longue maintenue", early: "Créneau : tôt le matin, départ avant 9 h",
    k5: "05 · LA POLITIQUE", h5: "Ce que le coach peut faire.",
    pol: [["Lire le workspace, Garmin, Intervals.icu", "autorisé", "ok"],
          ["Écrire dans activities/ medical/ nutrition/ planning/ rapports/ gear/", "autorisé", "ok"],
          ["Écrire vers Garmin / Intervals.icu", "votre accord, à chaque fois", "ask"],
          ["Shell libre, autre dossier, autre site", "refusé", "no"]],
    polFile: "config/chat-policy.toml", polNote: "Une seule politique, quel que soit le fournisseur.",
    k6: "06 · LOCAL ET PLAFONNÉ", h6: "Rien ne sort, rien ne s'emballe.",
    chain: ["navigateur", "tableau de bord", "service de chat"], chainNote: "lecture seule · écoute sur 127.0.0.1 par défaut",
    turn: "par tour", day: "par jour", turnKey: "turn_budget_max_eur", dayKey: "daily_budget_eur",
    stop: "Plafond atteint : le chat le dit et n'appelle plus le modèle jusqu'au lendemain.",
    k7: "07 · SUR TÉLÉPHONE", h7: "Appliquer du pouce.",
    ntfyApp: "ntfy · Coach", ntfyTitle: "Approbation en attente", ntfyBody: "Mardi : seuil → EF 45 min",
    ntfyBtns: ["Ouvrir", "Appliquer", "Refuser"], ntfyNote: "Résumé du changement seulement, jamais de données de santé.",
    ntfyDelay: "après 60 s sans réponse (ntfy_delay_s)", ntfyOnce: "lien à usage unique · 30 min · sujet ntfy protégé",
    k8: "08 · QUEL MODÈLE", h8: "Une clé API, pas un abonnement.",
    cards: [["Claude", "Claude Agent SDK", "claude-sonnet-5-5", "≈ 30 € / mois type", "estimation"],
            ["OpenRouter", "serveur OpenCode", "deepseek/deepseek-v4.1-flash", "≈ 0,80 € / mois type", "coûts mesurés"]],
    demo: "Dans ces vidéos", demoNote: "Backend « mock » : réponses scriptées, aucun modèle, aucun coût.",
    mockCfg: ["# config/workspace.user.toml", "[chat]", 'backend = "mock"', 'mock_scenario = "docs/video/data/chat-scenario.fr.json"'],
    tab: "Tableau de bord · Coach (interface en français)",
  },
  en: {
    k1: "01 · ONE QUESTION", h1: "Write to the coach.",
    q: "Je me sens vidé·e ce matin, je fais quand même mon seuil ?",
    chips: "or a shortcut: /today /week /why /race /log",
    dash: "Dashboard · Coach (French UI)",
    k2: "02 · THE TRACE", h2: "Every step in the open.",
    trace: "6 steps: files read, tools called", table: "The three signals of the morning check",
    k3: "03 · YOUR SAY", h3: "Nothing is written without you.",
    needs: "Confirmation before any write", diff: "Before / after", file: "Decision written to planning/",
    apply: "Apply",
    k4: "04 · FOLLOW-UP", h4: "Same conversation.",
    kept: "Long run kept", early: "Slot: early morning, start before 9 am",
    k5: "05 · THE POLICY", h5: "What the coach may do.",
    pol: [["Read the workspace, Garmin, Intervals.icu", "allowed", "ok"],
          ["Write to activities/ medical/ nutrition/ planning/ rapports/ gear/", "allowed", "ok"],
          ["Write to Garmin / Intervals.icu", "your approval, every time", "ask"],
          ["Free shell, other folder, other site", "refused", "no"]],
    polFile: "config/chat-policy.toml", polNote: "One policy, whatever the provider.",
    k6: "06 · LOCAL AND CAPPED", h6: "Nothing leaves, nothing runs away.",
    chain: ["browser", "dashboard", "chat service"], chainNote: "read-only · listens on 127.0.0.1 by default",
    turn: "per turn", day: "per day", turnKey: "turn_budget_max_eur", dayKey: "daily_budget_eur",
    stop: "Cap reached: the chat says so and stops calling the model until tomorrow.",
    k7: "07 · ON YOUR PHONE", h7: "Approve with a thumb.",
    ntfyApp: "ntfy · Coach", ntfyTitle: "Approval pending", ntfyBody: "Tuesday: threshold → EF 45 min",
    ntfyBtns: ["Open", "Apply", "Refuse"], ntfyNote: "Summary of the change only, never any health data.",
    ntfyDelay: "after 60 s unanswered (ntfy_delay_s)", ntfyOnce: "single-use link · 30 min · protected ntfy topic",
    k8: "08 · WHICH MODEL", h8: "An API key, not a subscription.",
    cards: [["Claude", "Claude Agent SDK", "claude-sonnet-5-5", "≈ €30 / typical month", "estimate"],
            ["OpenRouter", "OpenCode server", "deepseek/deepseek-v4.1-flash", "≈ €0.80 / typical month", "measured costs"]],
    demo: "In these videos", demoNote: "“mock” backend: scripted replies, no model, no cost.",
    mockCfg: ["# config/workspace.user.toml", "[chat]", 'backend = "mock"', 'mock_scenario = "docs/video/data/chat-scenario.fr.json"'],
    tab: "Dashboard · Coach (French UI)",
  },
};

/* cadre de capture commun : 1000 × 470 (image 1000 × 440) */
const FX = 140, FY = 160, FW = 1000, FH = 470, ASPECT = FW / (FH - 30);
const cw = 1100, chh = cw / ASPECT;
const TOP = [240, 70, cw, chh], BOT = [240, 900 - chh, cw, chh];
const frame = (name, crop, alpha = 1) => shot(name, FX, FY, FW, FH, { crop, alpha });
const head = (k, h, t) => { kicker(k, seg(t, 0, 0.4)); headline(h, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8)); };
const lerpP = (a, b, k) => [lerp(a[0], b[0], k), lerp(a[1], b[1], k)];

/* ------------------------------ la question ------------------------------ */
function sAsk(t, d, cues) {
  head(S.k1, S.h1, t);
  const ka = outCubic(seg(t, 0.3, 0.9));
  const tq = at(cues, 1, 5.5) - 2.4, tc = Math.max(tq + 3.0, 4);
  const pan = inOut(seg(t, tq - 1.8, tq - 0.2));
  const crop1 = lerpRect(TOP, BOT, pan);
  const map = frame("chat-empty", crop1, ka);
  const fade = seg(t, tc + 0.3, tc + 1.1);
  const kq = seg(t, tq, tq + 2.4);
  if (ka > 0.5 && fade < 1) {
    ctx.save(); ctx.globalAlpha *= 1 - fade;
    const c = map([252, 811, 700, 38]);
    if (c) { rr(c[0], c[1], c[2], c[3], 8); ctx.fillStyle = "rgb(18,27,22)"; ctx.fill();
      const sx = c[3] / 38 * 1.0, size = 16 * (FW / cw);
      const tx = typed(S.q, kq);
      text(tx, c[0] + 5 * sx, c[1] + c[3] / 2 + 5, { size, color: C.ink });
      if (kq > 0 && kq < 1) { const w = measure(tx, size); ctx.fillStyle = C.accent; ctx.fillRect(c[0] + 5 * sx + w + 2, c[1] + c[3] / 2 - 9, 2, 18); } }
    ctx.restore();
    const chips = map([340, 778, 1, 1]);
    const kc = seg(t, tq - 0.2, tq + 0.5);
    if (chips && pan > 0.9) callout(S.chips, chips[0] + 330, chips[1] - 74, chips[0] + 60, chips[1] + 8, kc, { align: "center", size: 13 });
    const send = map([1061, 830, 1, 1]);
    if (send) {
      const k = outCubic(seg(t, tq + 2.2, tc));
      const from = [send[0] + 150, send[1] - 130], p = lerpP(from, [send[0], send[1]], k);
      if (t > tq + 1.2) cursor(p[0], p[1], { alpha: seg(t, tq + 1.2, tq + 1.8) * (1 - fade), click: seg(t, tc, tc + 0.5) });
    }
  }
  if (fade > 0) {
    const pan2 = inOut(seg(t, tc + 0.2, tc + 1.1));
    frame("chat-typing", lerpRect(BOT, TOP, pan2), fade);
  }
  text(S.dash, FX + FW, FY + FH + 24, { size: 13, font: MONO, color: C.faint, align: "right", alpha: ka });
}

/* ------------------------------- la réponse ------------------------------- */
function sAnswer(t, d, cues) {
  head(S.k2, S.h2, t);
  const ka = outCubic(seg(t, 0.2, 0.8));
  const a1 = at(cues, 1, 6);
  const trace = [288, 195, 672, 264], table = [288, 506, 672, 191];
  const cTrace = [240, 110, 860, 860 / ASPECT], cTable = [240, 360, 860, 860 / ASPECT];
  const pan = inOut(seg(t, a1 - 0.6, a1 + 1.0));
  const crop = lerpRect(cTrace, cTable, pan);
  const map = frame("chat-typing", crop, ka);
  // « streaming » : le bas de la conversation se découvre peu à peu
  const rev = seg(t, 0.5, 4.2);
  const yRev = lerp(150, 720, rev);
  const cov = map([240, yRev, 860, 900 - yRev]);
  if (cov && rev < 1 && ka > 0.9) { ctx.save(); ctx.beginPath(); ctx.rect(FX, FY + 30, FW, FH - 30); ctx.clip(); rr(cov[0], cov[1], cov[2], cov[3], 0); ctx.fillStyle = "rgb(12,19,15)"; ctx.fill(); ctx.restore(); }
  const bt = map(trace), bb = map(table);
  const kt = seg(t, 4.0, 4.7) * (1 - pan);
  if (bt && kt > 0) { highlight(bt[0], bt[1], bt[2], bt[3], kt); callout(S.trace, bt[0] + bt[2] - 120, bt[1] + bt[3] + 20, bt[0] + bt[2] - 140, bt[1] + bt[3] - 6, kt, { align: "center" }); }
  const kb = seg(t, a1 + 1.0, a1 + 1.8);
  if (bb && kb > 0) { highlight(bb[0], bb[1], bb[2], bb[3], kb); callout(S.table, bb[0] + bb[2] - 200, bb[1] + bb[3] - 40, bb[0] + bb[2] - 330, bb[1] + bb[3] - 40, kb, {}); }
  text(S.dash, FX + FW, FY + FH + 24, { size: 13, font: MONO, color: C.faint, align: "right", alpha: ka });
}

/* ------------------------------- l'approbation ---------------------------- */
function sApproval(t, d, cues) {
  head(S.k3, S.h3, t);
  const ka = outCubic(seg(t, 0.2, 0.8));
  const a1 = at(cues, 1, 6.5);
  const tcl = a1 + 1.4;
  const cA = [240, 380, 860, 860 / ASPECT];
  const mapA = frame("chat-approval", cA, ka);
  const fade = seg(t, tcl + 0.35, tcl + 0.95);
  const diff = mapA([305, 492, 638, 138]), card = mapA([288, 398, 672, 295]), ok = mapA([305, 643, 104, 35]);
  if (fade < 1) {
    ctx.save(); ctx.globalAlpha *= 1 - fade;
    if (diff) {
      const k1 = seg(t, at(cues, 0, 0.6) + 2.0, at(cues, 0, 0.6) + 2.8);
      callout(S.needs, card[0] + card[2] - 150, card[1] + 78, card[0] + card[2] - 330, card[1] + 78, k1, { color: C.amber, align: "center" });
      const k2 = seg(t, at(cues, 0, 0.6) + 5.0, at(cues, 0, 0.6) + 5.8);
      highlight(diff[0], diff[1], diff[2], diff[3], k2);
      if (k2 > 0) callout(S.diff, diff[0] + diff[2] - 70, diff[1] - 18, diff[0] + diff[2] - 200, diff[1] + 18, k2, {});
    }
    if (ok) {
      const kc = seg(t, tcl - 1.4, tcl - 0.2);
      const from = [ok[0] + 360, ok[1] - 170], p = lerpP(from, [ok[0] + ok[2] / 2, ok[1] + ok[3] / 2], inOut(kc));
      if (kc > 0) cursor(p[0], p[1], { alpha: clamp(kc * 3), click: seg(t, tcl, tcl + 0.5) });
    }
    ctx.restore();
  }
  if (fade > 0) {
    const cB = [240, 330, 860, 860 / ASPECT];
    const mapB = frame("chat-done", cB, fade);
    const f = mapB([366, 626, 346, 24]);
    const kf = seg(t, tcl + 1.4, tcl + 2.1);
    if (f && kf > 0) { highlight(f[0], f[1], f[2], f[3], kf); callout(S.file, f[0] + f[2] + 130, f[1] - 44, f[0] + f[2] - 40, f[1] + 4, kf, { align: "center" }); }
  }
  text(S.dash, FX + FW, FY + FH + 24, { size: 13, font: MONO, color: C.faint, align: "right", alpha: ka });
}

/* ------------------------------- et samedi ? ------------------------------ */
function sSamedi(t, d, cues) {
  head(S.k4, S.h4, t);
  const ka = outCubic(seg(t, 0.2, 0.8));
  const wide = [0, 40, 1440, 1440 / ASPECT], tight = [240, 340, 860, 860 / ASPECT];
  const crop = lerpRect(wide, tight, inOut(seg(t, 0.6, 2.6)));
  const map = frame("chat-samedi", crop, ka);
  const a0 = at(cues, 0, 0.6);
  const r = map([297, 533, 652, 150]);
  const k1 = seg(t, a0 + 2.6, a0 + 3.4);
  if (r && k1 > 0) { highlight(r[0], r[1], r[2], r[3] * 0.55, k1); callout(S.kept, r[0] + 520, r[1] - 40, r[0] + 400, r[1] + 20, k1, {}); }
  const k2 = seg(t, a0 + 5.0, a0 + 5.8);
  if (r && k2 > 0) callout(S.early, r[0] + 330, r[1] + r[3] + 28, r[0] + 330, r[1] + 62, k2, { color: C.teal });
  text(S.dash, FX + FW, FY + FH + 24, { size: 13, font: MONO, color: C.faint, align: "right", alpha: ka });
}

/* -------------------------------- la politique ---------------------------- */
function sRules(t, d, cues) {
  head(S.k5, S.h5, t);
  const col = { ok: C.accent, ask: C.amber, no: C.red };
  const kf = outCubic(seg(t, 0.3, 0.9));
  pill(S.polFile, 1200, 132, { align: "right", font: MONO, alpha: kf, size: 14 });
  S.pol.forEach(([lab, tag, kind], i) => {
    const a = i < 2 ? at(cues, 0, 0.6) + 1.4 + i * 1.8 : at(cues, 1, 6) + (i - 2) * 1.6;
    const k = outCubic(seg(t, a, a + 0.6));
    if (k <= 0) return;
    const y = 190 + i * 100, hot = kind === "ask" && t > a + 0.6;
    panel(80, y + (1 - k) * 14, 1120, 82, { r: 18, alpha: k, fill: hot ? "rgba(240,180,60,0.08)" : C.panel, stroke: hot ? C.amber : C.line, lw: hot ? 2 : 1 });
    dot(122, y + 41 + (1 - k) * 14, 9, col[kind], k);
    text(lab, 156, y + 49 + (1 - k) * 14, { size: 21, weight: 600, font: i === 1 ? MONO : INTER, alpha: k });
    pill(tag, 1170, y + 41 + (1 - k) * 14, { align: "right", color: col[kind], stroke: col[kind], fill: "rgba(13,20,16,0.6)", size: 15, alpha: k });
  });
  const kn = seg(t, at(cues, 1, 6) + 3.4, at(cues, 1, 6) + 4.0);
  text(S.polNote, 80, 618, { size: 16, color: C.soft, alpha: kn });
}

/* --------------------------- local, plafonné, budget ----------------------- */
function sBudget(t, d, cues) {
  head(S.k6, S.h6, t);
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5);
  // chaîne locale
  const kc = outCubic(seg(t, 0.4, 1.0));
  const nodes = S.chain, xs = [80, 330, 580], y = 220, w = 200, h = 78;
  nodes.forEach((n, i) => {
    const k = outCubic(seg(t, a0 + i * 0.7, a0 + 0.6 + i * 0.7));
    panel(xs[i], y + (1 - k) * 12, w, h, { r: 16, alpha: k, fill: i === 1 ? "rgba(30,77,59,0.6)" : C.panel, stroke: i === 1 ? C.accent : C.line });
    text(n, xs[i] + w / 2, y + 46 + (1 - k) * 12, { size: 18, weight: 700, font: SORA, align: "center", alpha: k });
    if (i < 2) arrow(xs[i] + w + 6, y + 39, xs[i + 1] - 6, y + 39, outCubic(seg(t, a0 + 0.5 + i * 0.7, a0 + 1.1 + i * 0.7)));
  });
  const kp = seg(t, a0 + 2.0, a0 + 2.8);
  text("127.0.0.1:8765", xs[1] + w / 2, y + h + 34, { size: 14, font: MONO, color: C.accent, align: "center", alpha: kp });
  text("127.0.0.1:8766", xs[2] + w / 2, y + h + 34, { size: 14, font: MONO, color: C.accent, align: "center", alpha: kp });
  text(S.chainNote, 80, y + h + 84, { size: 16, color: C.soft, alpha: kp });
  // plafonds
  const kb = outCubic(seg(t, a1 - 0.2, a1 + 0.5));
  const bars = [[S.turn, S.turnKey, "1 €"], [S.day, S.dayKey, "2 €"]];
  const bw = 440;
  bars.forEach(([lab, key, val], i) => {
    const bx = 80, by = 440 + i * 84;
    text(val, bx, by + 6, { size: 38, weight: 800, font: SORA, alpha: kb });
    text(lab, bx + measure(val, 38, 800, SORA) + 14, by + 6, { size: 18, color: C.soft, alpha: kb });
    text(key, bx + bw, by + 6, { size: 13, font: MONO, color: C.faint, align: "right", alpha: kb });
    ctx.save(); ctx.globalAlpha *= kb; rr(bx, by + 18, bw, 10, 5); ctx.fillStyle = C.line; ctx.fill(); ctx.restore();
    const fill = i === 1 ? bw * 0.02 * outCubic(seg(t, a1 + 0.4, a1 + 1.2)) : bw * 0.96 * inOut(seg(t, a1 + 0.6, a1 + 3.0));
    const hit = i === 0 && fill >= bw * 0.95;
    ctx.save(); ctx.globalAlpha *= kb; rr(bx, by + 18, Math.max(fill, 0.01), 10, 5); ctx.fillStyle = hit ? C.amber : C.accent; ctx.fill(); ctx.restore();
  });
  const ks = outBack(seg(t, a1 + 3.0, a1 + 3.6));
  if (ks > 0) pill(LANG === "fr" ? "plafond atteint" : "cap reached", 80 + bw, 410, { align: "right", alpha: clamp(ks), size: 13, color: C.amber, stroke: C.amber, fill: "rgba(240,180,60,0.1)" });
  // la vraie ligne de compteur de la page (capture)
  const kr = outCubic(seg(t, a1 + 0.2, a1 + 1.0));
  shot("chat-samedi", 560, 440, 640, 36, { chrome: false, crop: [470, 859, 640, 36], alpha: kr, r: 10 });
  const kk = seg(t, a1 + 3.0, a1 + 3.7);
  para(S.stop, 560, 512, 640, { size: 18, color: C.soft, alpha: kk });
}

/* ------------------------------ sur téléphone ----------------------------- */
function sPhone(t, d, cues) {
  head(S.k7, S.h7, t);
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5);
  const kp = outCubic(seg(t, 0.3, 0.9));
  const px = 150, py = 152 + (1 - kp) * 30, pw = 270, ph = 468;
  let map = null;
  phone(px, py, pw, ph, (x, y, w, h) => {
    map = shot("mobile-coach", x, y, w, h, { chrome: false, shadow: false, stroke: false, crop: [0, 844 - 390 * h / w, 390, 390 * h / w] });
  }, { alpha: kp });
  if (map) {
    const ap = map([37, 559, 104, 35]);
    const kh = seg(t, a0 + 2.4, a0 + 3.2);
    if (ap) {
      highlight(ap[0], ap[1], ap[2], ap[3], kh);
      const kc = inOut(seg(t, a0 + 3.0, a0 + 4.4));
      if (kc > 0 && kc < 1.01) cursor(lerp(ap[0] + 200, ap[0] + 55, kc), lerp(ap[1] + 120, ap[1] + 22, kc), { alpha: clamp(kc * 4), click: seg(t, a0 + 4.4, a0 + 5.0) });
    }
  }
  // notification ntfy
  const kn = outCubic(seg(t, a1 - 0.2, a1 + 0.6));
  if (kn > 0) {
    const nx = 560 + (1 - kn) * 60, ny = 200, nw = 640, nh = 200;
    panel(nx, ny, nw, nh, { r: 20, fill: C.panel2, alpha: kn, shadow: true });
    dot(nx + 36, ny + 38, 8, C.accent, kn);
    text(S.ntfyApp, nx + 56, ny + 43, { size: 14, font: MONO, color: C.faint, alpha: kn });
    text(S.ntfyTitle, nx + 30, ny + 86, { size: 24, weight: 700, font: SORA, alpha: kn });
    text(S.ntfyBody, nx + 30, ny + 120, { size: 19, color: C.soft, alpha: kn });
    let bx = nx + 30;
    S.ntfyBtns.forEach((b, i) => { bx += pill(b, bx, ny + 158, { size: 15, alpha: kn, color: i === 1 ? C.deep : C.ink, fill: i === 1 ? C.accent : C.panel, stroke: i === 1 ? C.accent : C.line }) + 12; });
    const k2 = seg(t, a1 + 1.4, a1 + 2.0);
    text(S.ntfyDelay, 560, 440, { size: 16, font: MONO, color: C.soft, alpha: k2 });
    text(S.ntfyOnce, 560, 474, { size: 16, font: MONO, color: C.soft, alpha: k2 });
    const k3 = seg(t, a1 + 2.8, a1 + 3.4);
    pill("✓ " + S.ntfyNote, 560, 540, { size: 15, font: INTER, weight: 600, alpha: k3 });
  }
}

/* -------------------------------- fournisseurs ---------------------------- */
function sBackends(t, d, cues) {
  head(S.k8, S.h8, t);
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 6);
  S.cards.forEach(([name, harness, model, cost, note], i) => {
    const k = outCubic(seg(t, a0 + 0.8 + i * 1.4, a0 + 1.5 + i * 1.4));
    const x = 80 + i * 570, y = 180 + (1 - k) * 14;
    panel(x, y, 550, 190, { r: 20, alpha: k });
    text(name, x + 30, y + 52, { size: 30, weight: 800, font: SORA, alpha: k });
    text(harness, x + 30, y + 84, { size: 16, color: C.soft, alpha: k });
    text(model, x + 30, y + 122, { size: 17, font: MONO, color: C.accent, alpha: k });
    text(cost, x + 30, y + 160, { size: 22, weight: 700, alpha: k });
    pill(note, x + 520, y + 154, { align: "right", size: 13, alpha: k, color: C.soft, stroke: C.line, fill: "transparent" });
  });
  const kd = outCubic(seg(t, a1 - 0.3, a1 + 0.5));
  if (kd > 0) {
    text(S.demo, 80, 428, { size: 14, weight: 600, font: MONO, color: C.amber, spacing: "2px", alpha: kd });
    const lines = S.mockCfg.map((s, i) => ({ s, c: i === 0 ? C.faint : i === 1 ? C.ink : C.accent, a: a1 + 0.2 + i * 0.5, b: a1 + 0.6 + i * 0.5 }));
    terminal(80, 444, 640, 180, t, lines, { alpha: kd, size: 14, lh: 26 });
    para(S.demoNote, 770, 490, 430, { size: 20, weight: 600, alpha: seg(t, a1 + 2.0, a1 + 2.8) });
  }
}

ARC.episode({
  n: 4, slug: "chat-coach",
  strings: STR,
  shots: ["chat-empty", "chat-typing", "chat-approval", "chat-done", "chat-samedi", "mobile-coach"],
  scenes: { ask: sAsk, answer: sAnswer, approval: sApproval, samedi: sSamedi, rules: sRules, budget: sBudget, phone: sPhone, backends: sBackends },
});
})();
