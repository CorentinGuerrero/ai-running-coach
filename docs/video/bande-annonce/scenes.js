/* Bande-annonce de la série « Le Sentier » : scènes dessinées (moteur : ../engine/engine.js).
 * Découpage et narration : script.json -> timing.js (scripts/video_narration.py). */
"use strict";
(() => {
const STR = {
  fr: {
    title: "ai-running-coach en 80 secondes", back: "Retour à la documentation",
    play: "Lecture", pause: "Pause", full: "Plein écran",
    note: "Chaque image est dessinée en JavaScript sur un canvas, à partir du seul temps écoulé : pas de fichier vidéo. Espace : lecture/pause, flèches : ±5 s. Paramètres d'URL : <code>?lang=en</code>, <code>?t=30</code>. Données d'exemple fictives. Version MP4 : <code>scripts/render_video.py</code>.",
    fict: "Données d'exemple fictives",
    tagline: "Votre staff d'entraînement trail, dans votre IDE.",
    badge: "open source · MIT · connecté à Garmin",
    k2: "01 · LE CONSTAT", h2a: "Votre montre mesure tout.", h2b: "Qui relie les points ?",
    chips: [["HRV nocturne", "38 ms"], ["Sommeil", "6 h 12"], ["FC de repos", "52 bpm"], ["Readiness", "34/100"],
            ["Allure", "6:05 /km"], ["D+ semaine", "1 240 m"], ["Parcours", "course.gpx"], ["Ravito", "2 gels + 500 ml"],
            ["Douleur", "genou G 3/10"], ["Météo", "27 °C"]],
    hub: "votre coach",
    k3: "02 · BRANCHÉ", h3: "Vos données, lues dans votre IDE.",
    watch: "Montre", gc: "Garmin Connect", gcSub: "activités · santé", mcp: "garmin-mcp", mcpSub: "liste blanche d'outils",
    ide: "Votre IDE", files: "Markdown",
    alt: "Pas de montre Garmin ? Intervals.icu en source primaire :", altCmd: "./install.sh --source intervals",
    k4: "03 · LE STAFF", h4: "Quatre spécialistes, un seul objectif.",
    agents: [["Coach", "Plan, analyse des séances, push Garmin", "« Prépare-moi un trail de 50 km en avril. »"],
             ["Stratège de course", "GPX, allures par segment, ravitos", "« Donne-moi un plan d'allures. »"],
             ["Médecin du sport", "HRV, sommeil, vigilance blessure", "« Suis-je prêt pour demain ? »"],
             ["Nutritionniste", "Macros, glucides/h, sudation", "« Que manger pendant la course ? »"]],
    staffNote: "Installez seulement ceux que vous voulez :", staffCmd: "./install.sh --agents coach,nutritionist",
    k5: "04 · CHAQUE MATIN", h5: "Le verdict, et sa raison.",
    check: "Bilan matinal",
    rows: [["HRV nocturne", "38 ms", "sous la bande 52-70 · 3 nuits"], ["FC de repos", "52 bpm", "+6 vs médiane 7 j"], ["Readiness", "34/100", "faible"]],
    meteo: "Soir 18 h-19 h · 19 °C · vent 10 km/h", slot: "créneau optimal",
    verdict: "Alléger", verdictTxt: "Seuil 5 × 6 min remplacé par 45 min d'endurance fondamentale.",
    why: "HRV sous votre bande depuis 3 nuits et FC de repos +6 bpm : le seuil attendra.",
    decision: "planning/2026-09-29_decision_bilan-matinal.md",
    level: "Réglable : full · minimal · off",
    k6: "05 · PRÉPARATION", h6: "Un plan qui sait dire non.",
    days: ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"],
    sess: ["Repos", "Seuil", "Côtes", "EF 45'", "Repos", "Sortie longue", "EF 50'"],
    sessSub: ["", "5 × 6'", "8 × 1'", "", "", "2 h 30 · 900 m", ""],
    gTitle: "7 garde-fous calculés",
    guards: ["Charge projetée (ACWR)", "Hausse du volume", "Hausse du D+", "Monotonie", "Qualité après verdict rouge", "Part de la sortie longue", "Qualité consécutive"],
    gWarn: "mardi + mercredi : deux séances de qualité", gFix: "côtes déplacées à jeudi",
    push: "Poussé au calendrier Garmin · vérifié après envoi",
    planNote: "Un second avis déterministe et testé, pas une intuition de LLM.",
    k7: "06 · JOUR J", h7: "Votre course, segment par segment.",
    sub7: "Allures tirées de votre propre modèle pente-allure.",
    raceTag: "Exemple fictif · 42 km · 2 100 m D+",
    ravito: "Ravito", scen: [["Sécurité", "6 h 40"], ["Réaliste", "6 h 05"], ["Ambitieux", "5 h 38"]],
    fuel: "60 g de glucides/h · ~520 kcal/h", upload: "Parcours et ravitos envoyés sur la montre",
    k8: "07 · TRAÇABLE", h8: "Tout reste chez vous, en Markdown.",
    mdName: "activities/2026-09-27_trail.md", mdTitle: "# Trail du dimanche", mdProse: "Montées bien gérées, FC stable.",
    db: "index SQLite", dbSub: "dérivé, jetable",
    dash: "Tableau de bord", fit: "Condition", fat: "Fatigue", form: "Forme",
    dashNote: "scripts/dashboard.sh · lecture seule · 127.0.0.1",
    k9: "08 · DANS LA POCHE", h9: "Le coach vous suit partout.",
    notifApp: "ai-running-coach · maintenant", notif1: "Sync Garmin : trail 18,2 km, 820 m D+", notif2: "HRV 61 ms · demain : repos",
    reply: ["Mardi · Seuil 5 × 6 min", "HRV 61 · FC 45 · readiness 72", "Créneau : 7 h-8 h, 14 °C"],
    cmds: [["/today", "séance du jour, bilan, créneau météo"], ["/why", "la raison d'une décision, jamais inventée"],
           ["/week", "réalisé face au prévu, garde-fous"], ["/race", "compte à rebours, Trail Shape, plan"],
           ["/log", "« 2 gels + 500 ml au km 15, RPE 7 »"]],
    pocketNote: "Sync automatique + notification push · Claude Code Remote Control",
    k10: "09 · C'EST PARTI", h10: "Prêt à courir plus malin ?",
    setup: "/coach-setup", setupSub: "un entretien court : staff, discipline, style, profil",
    ides: "Claude Code · GitHub Copilot · OpenCode · Gemini CLI · Cursor · Windsurf",
    disclaimer: "Outil d'aide à la préparation sportive : il ne remplace pas un avis médical.",
  },
  en: {
    title: "ai-running-coach in 80 seconds", back: "Back to the documentation",
    play: "Play", pause: "Pause", full: "Fullscreen",
    note: "Every frame is drawn in JavaScript on a canvas from elapsed time alone: there is no video file. Space: play/pause, arrows: ±5 s. URL parameters: <code>?lang=en</code>, <code>?t=30</code>. Fictional sample data. MP4 version: <code>scripts/render_video.py</code>.",
    fict: "Fictional sample data",
    tagline: "Your trail training staff, inside your IDE.",
    badge: "open source · MIT · connected to Garmin",
    k2: "01 · THE PROBLEM", h2a: "Your watch measures everything.", h2b: "Who connects the dots?",
    chips: [["Overnight HRV", "38 ms"], ["Sleep", "6 h 12"], ["Resting HR", "52 bpm"], ["Readiness", "34/100"],
            ["Pace", "6:05 /km"], ["Weekly gain", "1,240 m"], ["Course", "race.gpx"], ["Fuel", "2 gels + 500 ml"],
            ["Pain", "left knee 3/10"], ["Weather", "27 °C"]],
    hub: "your coach",
    k3: "02 · PLUGGED IN", h3: "Your data, read inside your IDE.",
    watch: "Watch", gc: "Garmin Connect", gcSub: "activities · health", mcp: "garmin-mcp", mcpSub: "allow-listed tools",
    ide: "Your IDE", files: "Markdown",
    alt: "No Garmin watch? Intervals.icu as primary source:", altCmd: "./install.sh --source intervals",
    k4: "03 · THE STAFF", h4: "Four specialists, one goal.",
    agents: [["Coach", "Plan, session analysis, Garmin push", "“Get me ready for a 50 km trail in April.”"],
             ["Race strategist", "GPX, per-segment pacing, aid stations", "“Give me a pacing plan.”"],
             ["Sports doctor", "HRV, sleep, injury watch", "“Am I ready for tomorrow?”"],
             ["Nutritionist", "Macros, carbs/h, sweat rate", "“What should I eat during the race?”"]],
    staffNote: "Install only the ones you want:", staffCmd: "./install.sh --agents coach,nutritionist",
    k5: "04 · EVERY MORNING", h5: "The verdict, and its reason.",
    check: "Morning check",
    rows: [["Overnight HRV", "38 ms", "below the 52-70 band · 3 nights"], ["Resting HR", "52 bpm", "+6 vs 7-day median"], ["Readiness", "34/100", "low"]],
    meteo: "Evening 6-7 pm · 19 °C · wind 10 km/h", slot: "best window",
    verdict: "Ease off", verdictTxt: "Threshold 5 × 6 min replaced by 45 min of easy running.",
    why: "HRV below your band for 3 nights and resting HR +6 bpm: threshold waits.",
    decision: "planning/2026-09-29_decision_bilan-matinal.md",
    level: "Configurable: full · minimal · off",
    k6: "05 · BUILDING UP", h6: "A plan that knows when to say no.",
    days: ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
    sess: ["Rest", "Threshold", "Hills", "Easy 45'", "Rest", "Long run", "Easy 50'"],
    sessSub: ["", "5 × 6'", "8 × 1'", "", "", "2 h 30 · 900 m", ""],
    gTitle: "7 computed guardrails",
    guards: ["Projected load (ACWR)", "Volume increase", "Elevation increase", "Monotony", "Quality after red verdict", "Long-run share", "Back-to-back quality"],
    gWarn: "Tuesday + Wednesday: two quality sessions", gFix: "hills moved to Thursday",
    push: "Pushed to the Garmin calendar · verified after sending",
    planNote: "A deterministic, tested second opinion, not an LLM hunch.",
    k7: "06 · RACE DAY", h7: "Your race, segment by segment.",
    sub7: "Paces drawn from your own grade-to-pace model.",
    raceTag: "Fictional example · 42 km · 2,100 m gain",
    ravito: "Aid", scen: [["Safe", "6 h 40"], ["Realistic", "6 h 05"], ["Ambitious", "5 h 38"]],
    fuel: "60 g carbs/h · ~520 kcal/h", upload: "Course and aid stations sent to the watch",
    k8: "07 · TRACEABLE", h8: "Everything stays yours, in Markdown.",
    mdName: "activities/2026-09-27_trail.md", mdTitle: "# Sunday trail", mdProse: "Climbs well paced, steady HR.",
    db: "SQLite index", dbSub: "derived, disposable",
    dash: "Dashboard", fit: "Fitness", fat: "Fatigue", form: "Form",
    dashNote: "scripts/dashboard.sh · read-only · 127.0.0.1",
    k9: "08 · IN YOUR POCKET", h9: "The coach follows you everywhere.",
    notifApp: "ai-running-coach · now", notif1: "Garmin sync: trail 18.2 km, 820 m gain", notif2: "HRV 61 ms · tomorrow: rest",
    reply: ["Tuesday · Threshold 5 × 6 min", "HRV 61 · HR 45 · readiness 72", "Window: 7-8 am, 14 °C"],
    cmds: [["/today", "today's session, check-in, weather window"], ["/why", "the reason for a decision, never made up"],
           ["/week", "done vs planned, guardrails"], ["/race", "countdown, Trail Shape, race plan"],
           ["/log", "“2 gels + 500 ml at km 15, RPE 7”"]],
    pocketNote: "Automatic sync + push notification · Claude Code Remote Control",
    k10: "09 · LET'S GO", h10: "Ready to run smarter?",
    setup: "/coach-setup", setupSub: "a short interview: staff, discipline, style, profile",
    ides: "Claude Code · GitHub Copilot · OpenCode · Gemini CLI · Cursor · Windsurf",
    disclaimer: "A training aid: it does not replace medical advice.",
  },
};

/* --------------------------------- scènes --------------------------------- */

function sIntro(t) {
  const p = inOut(seg(t, 0.1, 2.4));
  const base = 560, amp = 150, n = 240;
  // crête qui se dessine
  ctx.save();
  ctx.beginPath(); ctx.moveTo(0, H);
  for (let i = 0; i <= n * p; i++) { const u = i / n; ctx.lineTo(u * W, base - amp * ridge(u)); }
  ctx.lineTo(W * p, H); ctx.closePath();
  const g = ctx.createLinearGradient(0, base - amp, 0, H);
  g.addColorStop(0, "rgba(30,77,59,0.55)"); g.addColorStop(1, "rgba(15,42,31,0.05)");
  ctx.fillStyle = g; ctx.fill(); ctx.restore();
  const pts = [];
  for (let i = 0; i <= n * p; i++) { const u = i / n; pts.push([u * W, base - amp * ridge(u)]); }
  if (pts.length > 1) line(pts, C.accent, 2.5);
  if (p > 0 && p < 1) { const [x, y] = pts[pts.length - 1]; dot(x, y, 6, C.accent); dot(x, y, 14, C.accent, 0.2); }

  const k1 = outCubic(seg(t, 1.0, 2.0)), k2 = outCubic(seg(t, 1.8, 2.8)), k3 = outCubic(seg(t, 2.6, 3.4));
  // logo : triangle de montagne
  ctx.save(); ctx.globalAlpha = k1;
  ctx.beginPath(); ctx.moveTo(612, 206); ctx.lineTo(640, 166); ctx.lineTo(652, 182); ctx.lineTo(662, 170); ctx.lineTo(684, 206); ctx.closePath();
  ctx.fillStyle = C.accent; ctx.fill(); ctx.restore();
  text("ai-running-coach", W / 2, 288 + (1 - k1) * 22, { size: 80, weight: 800, font: SORA, align: "center", alpha: k1, spacing: "-2px" });
  text(S.tagline, W / 2, 340 + (1 - k2) * 12, { size: 27, weight: 600, font: SORA, align: "center", alpha: k2, color: C.soft });
  const bw = measure(S.badge, 15, 600, MONO) + 36;
  panel(W / 2 - bw / 2, 372, bw, 36, { r: 18, fill: "rgba(163,230,53,0.08)", stroke: "rgba(163,230,53,0.35)", alpha: k3 });
  text(S.badge, W / 2, 395, { size: 15, weight: 600, font: MONO, align: "center", color: C.accent, alpha: k3 });
}

const CHIP_POS = [[250, 270], [640, 262], [1030, 276], [170, 400], [1110, 402], [280, 560], [640, 604], [1000, 560], [420, 476], [860, 346]];
function sProblem(t) {
  kicker(S.k2, seg(t, 0, 0.4));
  headline(S.h2a, seg(t, 0.1, 0.7));
  const kq = seg(t, 3.6, 4.2);
  text(S.h2b, 80, 184 + (1 - outCubic(kq)) * 12, { size: 42, weight: 800, font: SORA, color: C.accent, alpha: kq, spacing: "-1px" });
  const hx = 640, hy = 430;
  const gather = inOut(seg(t, 5.6, 6.9));
  // liens vers le centre
  CHIP_POS.forEach(([x, y], i) => {
    const kl = outCubic(seg(t, 4.2 + i * 0.07, 5.0 + i * 0.07));
    if (kl > 0) line([[x, y], [lerp(x, hx, kl), lerp(y, hy, kl)]], C.accent, 1.5, 0.35 * (1 - gather));
  });
  S.chips.forEach(([lab, val], i) => {
    const k = outBack(seg(t, 0.5 + i * 0.22, 1.0 + i * 0.22));
    if (k <= 0) return;
    let [x, y] = CHIP_POS[i];
    x += Math.sin(t * 0.9 + i * 1.7) * 5; y += Math.cos(t * 0.8 + i * 1.1) * 4;
    x = lerp(x, hx, gather); y = lerp(y, hy, gather);
    const w = Math.max(measure(lab, 12, 400, MONO), measure(val, 19, 600)) + 36;
    ctx.save();
    ctx.translate(x, y); ctx.scale(k * (1 - gather * 0.6), k * (1 - gather * 0.6));
    ctx.globalAlpha *= clamp(k) * (1 - gather);
    panel(-w / 2, -30, w, 60, { r: 14, fill: C.panel2 });
    text(lab, -w / 2 + 18, -8, { size: 12, font: MONO, color: C.faint });
    text(val, -w / 2 + 18, 18, { size: 19, weight: 600 });
    ctx.restore();
  });
  const kh = outBack(seg(t, 4.6, 5.3));
  if (kh > 0) {
    dot(hx, hy, 62 * kh + gather * 16, C.pine);
    ctx.save(); ctx.beginPath(); ctx.arc(hx, hy, 62 * kh + gather * 16, 0, Math.PI * 2); ctx.strokeStyle = C.accent; ctx.lineWidth = 2; ctx.stroke(); ctx.restore();
    text(S.hub, hx, hy + 6, { size: 15, weight: 700, font: SORA, align: "center", alpha: clamp(kh) });
  }
}

function sArch(t) {
  kicker(S.k3, seg(t, 0, 0.4));
  headline(S.h3, seg(t, 0.1, 0.7));
  const y = 380;
  const ka = outCubic(seg(t, 0.5, 1.1)), kb = outCubic(seg(t, 1.0, 1.6)), kc = outCubic(seg(t, 1.5, 2.1)),
        kd = outCubic(seg(t, 2.0, 2.6)), ke = outCubic(seg(t, 2.6, 3.2));
  // montre
  ctx.save(); ctx.globalAlpha = ka;
  rr(118, y - 92, 44, 30, 6); ctx.fillStyle = C.line; ctx.fill();
  rr(118, y + 62, 44, 30, 6); ctx.fill();
  dot(140, y, 64, C.line); dot(140, y, 56, "#0a100d");
  ctx.beginPath(); ctx.arc(140, y, 50, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * 0.72 * seg(t, 0.8, 2)); ctx.strokeStyle = C.accent; ctx.lineWidth = 4; ctx.stroke();
  ctx.restore();
  text("58", 140, y + 6, { size: 30, weight: 700, font: SORA, align: "center", alpha: ka });
  text("HRV", 140, y + 26, { size: 11, font: MONO, align: "center", color: C.soft, alpha: ka });
  text(S.watch, 140, y + 122, { size: 17, weight: 700, font: SORA, align: "center", alpha: ka });
  // Garmin Connect
  panel(270, y - 48, 190, 96, { alpha: kb, fill: C.panel2 });
  text(S.gc, 365, y - 4, { size: 19, weight: 700, font: SORA, align: "center", alpha: kb });
  text(S.gcSub, 365, y + 22, { size: 13, font: MONO, align: "center", color: C.soft, alpha: kb });
  // garmin-mcp
  panel(510, y - 48, 190, 96, { alpha: kc, fill: C.panel2, stroke: "rgba(163,230,53,0.4)" });
  text(S.mcp, 605, y - 4, { size: 19, weight: 600, font: MONO, align: "center", color: C.accent, alpha: kc });
  text(S.mcpSub, 605, y + 22, { size: 13, align: "center", color: C.soft, alpha: kc });
  // IDE
  const ix = 750, iy = y - 130, iw = 270, ih = 260;
  panel(ix, iy, iw, ih, { alpha: kd, fill: "#0a120e" });
  ctx.save(); ctx.globalAlpha = kd;
  rr(ix, iy, iw, 34, [16, 16, 0, 0]); ctx.fillStyle = C.panel2; ctx.fill();
  ctx.restore();
  [C.red, C.amber, C.accent].forEach((c, i) => dot(ix + 20 + i * 16, iy + 17, 5, c, kd * 0.8));
  text(S.ide, ix + iw - 16, iy + 22, { size: 13, weight: 600, align: "right", color: C.soft, alpha: kd });
  const ides = ["Claude Code", "GitHub Copilot", "OpenCode", "Gemini CLI", "Cursor", "Windsurf"];
  const hi = Math.floor(Math.max(0, t - 3) / 0.7) % ides.length;
  ides.forEach((s, i) => {
    const k = outCubic(seg(t, 2.3 + i * 0.1, 2.8 + i * 0.1));
    const on = t > 3 && i === hi;
    if (on) panel(ix + 12, iy + 46 + i * 34, iw - 24, 28, { r: 8, fill: "rgba(163,230,53,0.12)", stroke: false, alpha: k });
    text((on ? "> " : "  ") + s, ix + 24, iy + 66 + i * 34, { size: 15, font: MONO, color: on ? C.accent : C.soft, alpha: k });
  });
  // fichiers Markdown
  ["planning/", "medical/", "activities/"].forEach((s, i) => {
    const fx = 1080 + i * 12, fy = y - 70 + i * 14;
    panel(fx, fy, 110, 130, { r: 10, fill: i === 2 ? C.panel2 : C.panel, alpha: ke });
    if (i === 2) {
      for (let l = 0; l < 5; l++) line([[fx + 14, fy + 46 + l * 14], [fx + 14 + (l % 2 ? 56 : 80), fy + 46 + l * 14]], C.line, 3, ke);
      text(".md", fx + 14, fy + 30, { size: 14, weight: 600, font: MONO, color: C.accent, alpha: ke });
    }
  });
  text(S.files, 1160, y + 122, { size: 17, weight: 700, font: SORA, align: "center", alpha: ke });
  text("activities/ · medical/ · planning/", 1160, y + 144, { size: 11, font: MONO, align: "center", color: C.faint, alpha: ke });
  // connecteurs + paquets
  const links = [[204, 270, kb], [460, 510, kc], [700, 750, kd], [1020, 1080, ke]];
  links.forEach(([a, b, k]) => {
    arrow(a + 6, y, b - 6, y, k, C.faint);
    if (k >= 1) packets(a + 10, y, b - 14, y, t, 2, 1.1);
  });
  // alternative Intervals.icu
  const kn = seg(t, 4.2, 4.9);
  const aw = measure(S.alt, 16);
  text(S.alt, 80, 610, { size: 16, color: C.soft, alpha: kn });
  text(S.altCmd, 80 + aw + 10, 610, { size: 15, font: MONO, color: C.accent, alpha: kn });
}

function sStaff(t) {
  kicker(S.k4, seg(t, 0, 0.4));
  headline(S.h4, seg(t, 0.1, 0.7));
  const cards = [[460, 190, 360, 128], [70, 430, 360, 150], [460, 430, 360, 150], [850, 430, 360, 150]];
  const kc = outCubic(seg(t, 0.5, 1.1));
  // lignes de délégation
  [1, 2, 3].forEach(i => {
    const [x, y, w] = cards[i];
    const k = outCubic(seg(t, 1.2 + i * 0.15, 1.8 + i * 0.15));
    const sx = 640, sy = 318, ex = x + w / 2, ey = 430;
    const mid = 374;
    const pts = [[sx, sy], [sx, mid], [ex, mid], [ex, ey]];
    // tracé progressif de la polyligne
    const L = [0, mid - sy, Math.abs(ex - sx), ey - mid];
    const tot = L.reduce((a, b) => a + b);
    let rem = tot * k; const out = [pts[0]];
    for (let j = 1; j < 4 && rem > 0; j++) {
      const f = Math.min(1, rem / (L[j] || 1));
      out.push([lerp(pts[j - 1][0], pts[j][0], f), lerp(pts[j - 1][1], pts[j][1], f)]);
      rem -= L[j];
    }
    line(out, C.faint, 1.5);
    if (k >= 1) {
      const q = ((t * 0.7) + i * 0.3) % 1;
      let d = q * tot, px = sx, py = sy;
      for (let j = 1; j < 4; j++) {
        if (d <= L[j]) { const f = d / (L[j] || 1); px = lerp(pts[j - 1][0], pts[j][0], f); py = lerp(pts[j - 1][1], pts[j][1], f); break; }
        d -= L[j];
      }
      dot(px, py, 3.5, C.accent, Math.sin(Math.PI * q));
    }
  });
  S.agents.forEach(([name, role, quote], i) => {
    const [x, y, w, h] = cards[i];
    const k = i === 0 ? kc : outCubic(seg(t, 1.6 + i * 0.25, 2.2 + i * 0.25));
    if (k <= 0) return;
    ctx.save(); ctx.translate(0, (1 - k) * 16); ctx.globalAlpha = k;
    panel(x, y, w, h, { fill: i === 0 ? C.pine : C.panel2, stroke: i === 0 ? "rgba(163,230,53,0.5)" : C.line });
    dot(x + 30, y + 34, 7, i === 0 ? C.accent : C.soft);
    text(name, x + 48, y + 41, { size: 22, weight: 700, font: SORA });
    text(role, x + 24, y + 72, { size: 15, color: C.soft });
    const kq = seg(t, 3.0 + i * 0.5, 4.2 + i * 0.5);
    const lines = wrap(quote, w - 48, 15);
    lines.forEach((l, j) => {
      const shown = typed(l, kq * lines.length - j);
      text(shown, x + 24, y + 104 + j * 22, { size: 15, color: C.ink });
    });
    ctx.restore();
  });
  const kn = seg(t, 5.0, 5.6);
  const aw = measure(S.staffNote, 16);
  text(S.staffNote, 80, 640, { size: 16, color: C.soft, alpha: kn });
  text(S.staffCmd, 80 + aw + 10, 640, { size: 15, font: MONO, color: C.accent, alpha: kn });
}

function gaugeRow(x, y, w, lab, val, note, pos, band, k, color) {
  text(lab, x, y, { size: 16, color: C.soft, alpha: k });
  text(val, x + 150, y, { size: 20, weight: 700, alpha: k });
  const bx = x + 260, bw = w - 260, by = y - 6;
  ctx.save(); ctx.globalAlpha = k;
  rr(bx, by - 3, bw, 6, 3); ctx.fillStyle = C.line; ctx.fill();
  rr(bx + bw * band[0], by - 6, bw * (band[1] - band[0]), 12, 6); ctx.fillStyle = "rgba(184,196,189,0.25)"; ctx.fill();
  ctx.restore();
  const px = bx + bw * lerp(0.5, pos, outCubic(k));
  dot(px, by, 7, color, k);
  text(note, bx, y + 26, { size: 13, color: C.faint, alpha: seg(k, 0.6, 1) });
}
function sMorning(t) {
  kicker(S.k5, seg(t, 0, 0.4));
  headline(S.h5, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const kp = outCubic(seg(t, 0.4, 1.0));
  panel(80, 190, 560, 390, { alpha: kp });
  text(S.check, 108, 232, { size: 20, weight: 700, font: SORA, alpha: kp });
  text("HRV + FC + readiness", 612, 232, { size: 12, font: MONO, color: C.faint, align: "right", alpha: kp });
  const vals = [[0.14, [0.45, 0.8]], [0.8, [0.25, 0.5]], [0.3, [0.55, 0.95]]];
  S.rows.forEach(([lab, val, note], i) => {
    const k = seg(t, 1.0 + i * 0.5, 1.8 + i * 0.5);
    gaugeRow(108, 290 + i * 78, 504, lab, val, note, vals[i][0], vals[i][1], k, C.amber);
  });
  const km = seg(t, 2.8, 3.4);
  line([[108, 508], [612, 508]], C.line, 1, km);
  dot(116, 540, 6, C.accent, km);
  text(S.meteo, 132, 546, { size: 15, alpha: km });
  text(S.slot, 612, 546, { size: 13, font: MONO, color: C.accent, align: "right", alpha: km });
  // verdict
  const kv = outBack(seg(t, 3.4, 4.1));
  if (kv > 0) {
    ctx.save(); ctx.translate(680 + (1 - clamp(kv)) * 30, 0); ctx.globalAlpha = clamp(kv);
    panel(0, 190, 520, 170, { fill: "rgba(240,180,60,0.08)", stroke: "rgba(240,180,60,0.45)" });
    dot(34, 238, 9, C.amber);
    text(S.verdict, 56, 250, { size: 34, weight: 800, font: SORA, spacing: "-1px" });
    wrap(S.verdictTxt, 470, 17).forEach((l, j) => text(l, 26, 294 + j * 26, { size: 17, color: C.soft }));
    ctx.restore();
  }
  // /why
  const kw = seg(t, 4.8, 5.2);
  panel(680, 390, 520, 190, { fill: "#0a120e", alpha: kw });
  text("> /why", 704, 428, { size: 17, weight: 600, font: MONO, color: C.accent, alpha: kw });
  const kt = seg(t, 5.4, 7.4);
  const wl = wrap(S.why, 472, 16);
  wl.forEach((l, j) => text(typed(l, kt * wl.length - j), 704, 462 + j * 24, { size: 16, alpha: kw }));
  text(S.decision, 704, 558, { size: 12, font: MONO, color: C.faint, alpha: seg(t, 7.4, 7.9) });
  text(S.level, 80, 630, { size: 15, font: MONO, color: C.soft, alpha: seg(t, 6, 6.6) });
}

function sPlan(t) {
  kicker(S.k6, seg(t, 0, 0.4));
  headline(S.h6, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const gx = 80, gw = 620, top = 200, bottom = 560, colW = gw / 7;
  const mins = [0, 60, 55, 45, 0, 150, 50];
  const kind = ["rest", "q", "q", "e", "rest", "long", "e"];
  const swap = inOut(seg(t, 5.0, 6.0));
  const pushed = seg(t, 7.2, 7.8);
  S.days.forEach((d, i) => text(d, gx + colW * i + colW / 2, bottom + 30, { size: 13, weight: 600, font: MONO, color: C.faint, align: "center", alpha: seg(t, 0.3, 0.8) }));
  line([[gx, bottom], [gx + gw, bottom]], C.line, 1, seg(t, 0.3, 0.8));
  for (let i = 0; i < 7; i++) {
    const k = outBack(seg(t, 0.6 + i * 0.12, 1.2 + i * 0.12));
    if (k <= 0) continue;
    let slot = i;
    let lift = 0;
    if (i === 2) { slot = lerp(2, 3, swap); lift = Math.sin(Math.PI * swap) * 50; }
    if (i === 3) { slot = lerp(3, 2, swap); }
    const x = gx + colW * slot + 8, w = colW - 16;
    const h = mins[i] ? (mins[i] / 150) * 300 * clamp(k, 0, 1.1) : 26;
    const y = bottom - h - 6 - lift;
    const warn = i <= 2 && i >= 1 && t > 3.9 && t < 6.2;
    const fill = kind[i] === "rest" ? "rgba(184,196,189,0.10)" : kind[i] === "q" ? "rgba(163,230,53,0.22)" : kind[i] === "long" ? "rgba(95,184,160,0.25)" : "rgba(30,77,59,0.9)";
    const stroke = warn ? C.amber : kind[i] === "q" ? "rgba(163,230,53,0.6)" : C.line;
    panel(x, y, w, h, { r: 10, fill, stroke, lw: warn ? 2 : 1 });
    const txtY = mins[i] ? y + 24 : y + 18;
    text(S.sess[i], x + w / 2, txtY, { size: mins[i] ? 13 : 12, weight: 700, align: "center", color: mins[i] ? C.ink : C.faint });
    if (S.sessSub[i]) S.sessSub[i].split(" · ").forEach((l, j) => text(l, x + w / 2, txtY + 18 + j * 14, { size: 11, font: MONO, align: "center", color: C.soft }));
    if (mins[i] && pushed > 0) { dot(x + w - 10, y + 10 - 4 * (1 - pushed), 9, C.accent, pushed); check(x + w - 10, y + 10, 9, C.deep, pushed); }
  }
  // garde-fous
  const px = 760, pw = 440;
  const kp = outCubic(seg(t, 1.2, 1.7));
  panel(px, top - 10, pw, 370, { alpha: kp });
  text(S.gTitle, px + 26, top + 28, { size: 19, weight: 700, font: SORA, alpha: kp });
  S.guards.forEach((g, i) => {
    const y = top + 72 + i * 40;
    const k = seg(t, 1.6 + i * 0.32, 1.9 + i * 0.32);
    const isR7 = i === 6;
    const warn = isR7 && t > 3.9 && t < 6.2;
    const ok = isR7 ? t >= 6.2 : true;
    text(`r${i + 1}`, px + 26, y, { size: 12, font: MONO, color: C.faint, alpha: kp });
    text(g, px + 62, y, { size: 16, color: warn ? C.amber : C.ink, alpha: kp });
    if (warn) {
      dot(px + pw - 34, y - 5, 10, C.amber, 0.9);
      text("!", px + pw - 34, y + 0.5, { size: 15, weight: 800, align: "center", color: C.deep });
    } else if (ok && k > 0) {
      dot(px + pw - 34, y - 5, 10, "rgba(163,230,53,0.18)", k);
      check(px + pw - 34, y - 5, 10, C.accent, isR7 ? seg(t, 6.2, 6.6) : k);
    }
  });
  const kw = seg(t, 3.9, 4.3) * (1 - seg(t, 6.0, 6.3));
  text(S.gWarn, px + 26, top + 350, { size: 14, color: C.amber, alpha: kw });
  text(S.gFix, px + 26, top + 350, { size: 14, color: C.accent, alpha: seg(t, 6.3, 6.7) * (1 - pushed) });
  text(S.push, px + 26, top + 350, { size: 14, weight: 600, color: C.accent, alpha: pushed });
  text(S.planNote, 80, 640, { size: 16, color: C.soft, alpha: seg(t, 8, 8.6) });
}

/* Profil fictif de 42 km (altitude en m). */
const elev = k => 320 + 620 * bump(k, 9, 3.6) + 860 * bump(k, 21, 4.4) + 520 * bump(k, 33.5, 3.2) + 40 * Math.sin(k * 1.9) + 25 * Math.sin(k * 4.3 + 1);
function sRace(t) {
  kicker(S.k7, seg(t, 0, 0.4));
  headline(S.h7, seg(t, 0.1, 0.7));
  text(S.sub7, 80, 172, { size: 18, color: C.soft, alpha: seg(t, 0.5, 1.1) });
  text(S.raceTag, W - 80, 86, { size: 12, font: MONO, color: C.faint, align: "right", alpha: seg(t, 0.3, 0.8) });
  const x0 = 80, x1 = 1200, yb = 500, yt = 250, K = 42;
  const emin = 250, emax = 1250;
  const X = k => lerp(x0, x1, k / K), Y = e => lerp(yb, yt, (e - emin) / (emax - emin));
  const p = inOut(seg(t, 0.6, 2.4));
  // aire
  ctx.save(); ctx.beginPath(); ctx.moveTo(x0, yb);
  for (let k = 0; k <= K * p; k += 0.1) ctx.lineTo(X(k), Y(elev(k)));
  ctx.lineTo(X(K * p), yb); ctx.closePath();
  const g = ctx.createLinearGradient(0, yt, 0, yb);
  g.addColorStop(0, "rgba(30,77,59,0.7)"); g.addColorStop(1, "rgba(30,77,59,0.08)");
  ctx.fillStyle = g; ctx.fill(); ctx.restore();
  // ligne colorée par pente
  for (let k = 0; k < K * p - 0.1; k += 0.25) {
    const sl = (elev(k + 0.25) - elev(k)) / 250;
    const c = sl > 0.08 ? C.accent : sl < -0.08 ? C.teal : C.soft;
    line([[X(k), Y(elev(k))], [X(Math.min(k + 0.25, K * p)), Y(elev(Math.min(k + 0.25, K * p)))]], c, 2.5);
  }
  // axe km
  const ka = seg(t, 0.6, 1.2);
  for (let k = 0; k <= K; k += 6) text(`${k}`, X(k), yb + 22, { size: 12, font: MONO, color: C.faint, align: "center", alpha: ka });
  text("km", x1 + 26, yb + 22, { size: 12, font: MONO, color: C.faint, alpha: ka });
  // ravitos
  [12, 24, 34].forEach((k, i) => {
    const kr = outBack(seg(t, 2.2 + i * 0.2, 2.7 + i * 0.2));
    if (kr <= 0) return;
    const x = X(k), y = Y(elev(k));
    line([[x, y - 8], [x, yt - 20]], C.faint, 1, clamp(kr), [3, 4]);
    ctx.save(); ctx.globalAlpha = clamp(kr); ctx.beginPath();
    ctx.moveTo(x, yt - 22); ctx.lineTo(x - 8 * kr, yt - 36); ctx.lineTo(x + 8 * kr, yt - 36); ctx.closePath();
    ctx.fillStyle = C.accent; ctx.fill(); ctx.restore();
    text(`${S.ravito} km ${k}`, x, yt - 44, { size: 12, weight: 600, font: MONO, align: "center", color: C.soft, alpha: clamp(kr) });
  });
  // coureur + info-bulle
  const kr = seg(t, 2.8, 8.2);
  if (kr > 0) {
    const k = K * inOut(kr) * 0.98 + 0.3;
    const e = elev(k), sl = (elev(k + 0.2) - elev(k - 0.2)) / 400;
    const pace = sl > 0 ? 6.0 + sl * 38 : 5.4 + sl * 6; // min/km, modèle pente-allure fictif
    const pm = Math.floor(pace), ps = Math.round((pace - pm) * 60) % 60;
    const x = X(k), y = Y(e);
    dot(x, y, 12, C.accent, 0.25); dot(x, y, 6, C.accent);
    const label = `km ${k.toFixed(1)} · ${sl >= 0 ? "+" : ""}${Math.round(sl * 100)} % · ${pm}:${String(ps).padStart(2, "0")} /km`;
    const lw = measure(label, 14, 600, MONO) + 24;
    const bx = clamp(x - lw / 2, x0, x1 - lw), by = y - 64;
    panel(bx, by, lw, 34, { r: 10, fill: C.deep, stroke: "rgba(163,230,53,0.5)" });
    text(label, bx + 12, by + 22, { size: 14, weight: 600, font: MONO, color: C.ink });
  }
  // scénarios
  const ks = seg(t, 3.2, 3.8);
  const hi = Math.floor(Math.max(0, t - 4.2) / 1.3) % 3;
  let sx = 80;
  S.scen.forEach(([n, v], i) => {
    const on = t > 4.2 && hi === i;
    const s = `${n}  ${v}`;
    const w = measure(s, 16, 600) + 34;
    panel(sx, 562, w, 42, { r: 21, fill: on ? "rgba(163,230,53,0.14)" : C.panel, stroke: on ? C.accent : C.line, alpha: ks });
    text(s, sx + 17, 589, { size: 16, weight: 600, color: on ? C.accent : C.ink, alpha: ks });
    sx += w + 12;
  });
  text(S.fuel, W - 80, 580, { size: 15, font: MONO, color: C.soft, align: "right", alpha: seg(t, 4.4, 5) });
  text(S.upload, W - 80, 604, { size: 14, color: C.faint, align: "right", alpha: seg(t, 5, 5.6) });
}

function sTrace(t) {
  kicker(S.k8, seg(t, 0, 0.4));
  headline(S.h8, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  // éditeur
  const ex = 80, ey = 190, ew = 470, eh = 400;
  const ke = outCubic(seg(t, 0.4, 1.0));
  panel(ex, ey, ew, eh, { fill: "#0a120e", alpha: ke });
  ctx.save(); ctx.globalAlpha = ke; rr(ex, ey, ew, 36, [16, 16, 0, 0]); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
  text(S.mdName, ex + 18, ey + 24, { size: 13, font: MONO, color: C.soft, alpha: ke });
  const md = [
    [S.mdTitle, C.ink, 700],
    ["```arc", C.faint, 400],
    ['{"arc": 1, "kind": "activity",', C.accent, 400],
    [' "date": "2026-09-27", "sport": "trail",', C.accent, 400],
    [' "distance_m": 18240,', C.accent, 400],
    [' "elevation_gain_m": 820,', C.accent, 400],
    [' "avg_hr_bpm": 142, "rpe": 7}', C.accent, 400],
    ["```", C.faint, 400],
    ["", C.ink, 400],
    [S.mdProse, C.soft, 400],
  ];
  const kt = seg(t, 1.0, 3.6);
  md.forEach(([s, c, w], i) => text(typed(s, kt * md.length - i), ex + 20, ey + 72 + i * 30, { size: 14, font: MONO, weight: w, color: c, alpha: ke }));
  // index SQLite (cylindre)
  const kd = outCubic(seg(t, 3.4, 4.0));
  const cx = 640, cy = 380;
  ctx.save(); ctx.globalAlpha = kd;
  ctx.beginPath(); ctx.ellipse(cx, cy - 50, 50, 14, 0, 0, Math.PI * 2); ctx.fillStyle = C.panel2; ctx.fill(); ctx.strokeStyle = C.line; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx - 50, cy - 50); ctx.lineTo(cx - 50, cy + 40); ctx.ellipse(cx, cy + 40, 50, 14, 0, Math.PI, 0, true); ctx.lineTo(cx + 50, cy - 50);
  ctx.ellipse(cx, cy - 50, 50, 14, 0, 0, Math.PI, false); ctx.closePath(); ctx.fillStyle = C.panel; ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(cx, cy - 50, 50, 14, 0, 0, Math.PI * 2); ctx.fillStyle = C.panel2; ctx.fill(); ctx.stroke();
  ctx.restore();
  text(S.db, cx, cy + 90, { size: 16, weight: 700, font: SORA, align: "center", alpha: kd });
  text(S.dbSub, cx, cy + 112, { size: 13, color: C.faint, align: "center", alpha: kd });
  arrow(556, cy, 584, cy, seg(t, 3.6, 4.0));
  if (t > 4) packets(556, cy, 580, cy, t, 1, 0.9);
  arrow(696, cy, 724, cy, seg(t, 4.2, 4.6));
  if (t > 4.6) packets(696, cy, 720, cy, t, 1, 0.9);
  // tableau de bord
  const dx = 730, dy = 190, dw = 470, dh = 400;
  const kb = outCubic(seg(t, 4.2, 4.8));
  panel(dx, dy, dw, dh, { fill: "#f6f4ef", stroke: false, alpha: kb });
  ctx.save(); ctx.globalAlpha = kb; rr(dx, dy, dw, 44, [16, 16, 0, 0]); ctx.fillStyle = C.deep; ctx.fill();
  ctx.beginPath(); ctx.moveTo(dx + 18, dy + 30); ctx.lineTo(dx + 26, dy + 18); ctx.lineTo(dx + 34, dy + 30); ctx.closePath(); ctx.fillStyle = C.accent; ctx.fill(); ctx.restore();
  text(S.dash, dx + 44, dy + 28, { size: 15, weight: 700, font: SORA, alpha: kb });
  const kpis = [[S.fit, "67", "#1c2b24"], [S.fat, "59", "#1c2b24"], [S.form, "+8", "#1e4d3b"]];
  kpis.forEach(([l, v, c], i) => {
    text(l, dx + 26 + i * 148, dy + 80, { size: 13, color: "#4a5a52", alpha: kb });
    text(v, dx + 26 + i * 148, dy + 112, { size: 28, weight: 700, font: SORA, color: c, alpha: kb });
  });
  const cx0 = dx + 26, cx1 = dx + dw - 26, cyT = dy + 150, cyB = dy + dh - 56;
  line([[cx0, cyB], [cx1, cyB]], "#d9d5ca", 1, kb);
  const kc = seg(t, 4.8, 7.0);
  // courbe de forme fictive : condition qui monte, fatigue en dents de scie hebdomadaires
  const fitness = u => 0.38 + 0.32 * u + 0.02 * Math.sin(u * 7);
  const fatigue = u => 0.4 + 0.3 * u + 0.09 * Math.sin(u * 2 * Math.PI * 6 + 1) - 0.12 * seg(u, 0.85, 1);
  const form = u => 0.3 + (fitness(u) - fatigue(u)) * 1.6;
  [[fitness, "#1e4d3b", 3], [fatigue, "#c07a1b", 2], [form, "#7da327", 2]].forEach(([f, c, lw]) => {
    const pts = [];
    for (let i = 0; i <= 80 * kc; i++) { const u = i / 80; pts.push([lerp(cx0, cx1, u), lerp(cyB, cyT, f(u))]); }
    if (pts.length > 1) line(pts, c, lw, kb);
  });
  [[S.fit, "#1e4d3b"], [S.fat, "#c07a1b"], [S.form, "#7da327"]].forEach(([l, c], i) => {
    const lx = cx0 + i * 120;
    line([[lx, cyB + 20], [lx + 16, cyB + 20]], c, 3, kb * seg(t, 5, 5.5));
    text(l, lx + 22, cyB + 25, { size: 12, color: "#4a5a52", alpha: kb * seg(t, 5, 5.5) });
  });
  text(S.dashNote, 80, 640, { size: 15, font: MONO, color: C.soft, alpha: seg(t, 6, 6.6) });
}

function sPocket(t) {
  // téléphone
  const px = 150, py = 120, pw = 290, ph = 520;
  const kp = outCubic(seg(t, 0.2, 0.9));
  ctx.save(); ctx.translate(0, (1 - kp) * 60); ctx.globalAlpha = kp;
  panel(px, py, pw, ph, { r: 42, fill: "#050806", stroke: "#33463b", lw: 3 });
  rr(px + pw / 2 - 45, py + 14, 90, 24, 12); ctx.fillStyle = "#000"; ctx.fill();
  text("07:02", px + 40, py + 32, { size: 13, weight: 600 });
  // notification
  const kn = outCubic(seg(t, 0.9, 1.5));
  ctx.save(); ctx.translate(0, (1 - kn) * -40); ctx.globalAlpha *= kn;
  panel(px + 14, py + 56, pw - 28, 98, { r: 18, fill: "#1a2821", stroke: false });
  ctx.beginPath(); ctx.moveTo(px + 30, py + 84); ctx.lineTo(px + 38, py + 72); ctx.lineTo(px + 46, py + 84); ctx.closePath(); ctx.fillStyle = C.accent; ctx.fill();
  text(S.notifApp, px + 56, py + 83, { size: 11, color: C.faint });
  text(S.notif1, px + 30, py + 112, { size: 13, weight: 600 });
  text(S.notif2, px + 30, py + 134, { size: 13, color: C.soft });
  ctx.restore();
  // conversation
  const ku = outBack(seg(t, 2.4, 2.9));
  if (ku > 0) {
    ctx.save(); ctx.globalAlpha *= clamp(ku);
    panel(px + pw - 110, py + 190, 90, 38, { r: 19, fill: C.accent, stroke: false });
    text("/today", px + pw - 65, py + 215, { size: 15, weight: 600, font: MONO, color: C.deep, align: "center" });
    ctx.restore();
  }
  const kr = seg(t, 3.1, 5.2);
  if (kr > 0) {
    panel(px + 18, py + 248, pw - 56, 118, { r: 18, fill: C.panel2, stroke: false });
    S.reply.forEach((l, j) => text(typed(l, kr * 3 - j), px + 34, py + 282 + j * 30, { size: 14, weight: j ? 400 : 700, color: j ? C.soft : C.ink }));
  }
  ctx.restore();
  // commandes
  text(S.k9, 520, 86, { size: 14, weight: 600, font: MONO, color: C.accent, alpha: seg(t, 0, 0.4), spacing: "2px" });
  text(S.h9, 520, 132 + (1 - outCubic(seg(t, 0.1, 0.7))) * 18, { size: 42, weight: 800, font: SORA, alpha: seg(t, 0.1, 0.7), spacing: "-1px" });
  S.cmds.forEach(([c, d], i) => {
    const k = outCubic(seg(t, 1.0 + i * 0.3, 1.6 + i * 0.3));
    const y = 230 + i * 70;
    const on = (i === 0 && t > 2.4 && t < 5.4);
    ctx.save(); ctx.translate((1 - k) * 30, 0);
    panel(520, y - 34, 680, 54, { r: 14, fill: on ? "rgba(163,230,53,0.1)" : C.panel, stroke: on ? C.accent : C.line, alpha: k });
    text(c, 546, y, { size: 19, weight: 600, font: MONO, color: C.accent, alpha: k });
    text(d, 650, y, { size: 17, color: C.soft, alpha: k });
    ctx.restore();
  });
  text(S.pocketNote, 520, 612, { size: 15, color: C.faint, alpha: seg(t, 4.8, 5.4) });
}

function sOutro(t) {
  kicker(S.k10, seg(t, 0, 0.4) * (1 - seg(t, 5.2, 5.8)));
  headline(S.h10, seg(t, 0.1, 0.7) * (1 - seg(t, 5.2, 5.8)));
  const fade = 1 - seg(t, 5.2, 5.8);
  const tx = 80, ty = 180, tw = 1120, th = 290;
  const kt = outCubic(seg(t, 0.4, 1.0)) * fade;
  panel(tx, ty, tw, th, { fill: "#0a120e", alpha: kt });
  const cmds = [
    ["$ ", "git clone https://github.com/mmornati/ai-running-coach.git", 0.9, 2.2],
    ["$ ", "cd ai-running-coach && ./install.sh", 2.3, 3.1],
  ];
  cmds.forEach(([p, c, a, b], i) => {
    const k = seg(t, a, b);
    text(p, tx + 28, ty + 56 + i * 40, { size: 18, font: MONO, color: C.faint, alpha: kt * (k > 0 ? 1 : 0) });
    text(typed(c, k), tx + 56, ty + 56 + i * 40, { size: 18, font: MONO, color: C.ink, alpha: kt });
  });
  const inst = ["uv", "garmin-mcp", "IDE", "workspace"];
  inst.forEach((s, i) => {
    const k = seg(t, 3.1 + i * 0.18, 3.3 + i * 0.18);
    const x = tx + 28 + i * 170;
    if (k > 0) { dot(x + 10, ty + 140, 10, "rgba(163,230,53,0.18)", k * fade); check(x + 10, ty + 140, 10, C.accent, k, fade); }
    text(s, x + 30, ty + 146, { size: 16, font: MONO, color: C.soft, alpha: k * fade });
  });
  const ks = seg(t, 3.9, 4.5);
  text("> " + S.setup, tx + 28, ty + 214, { size: 20, weight: 600, font: MONO, color: C.accent, alpha: ks * fade });
  text(S.setupSub, tx + 28, ty + 246, { size: 16, color: C.soft, alpha: ks * fade });
  // carte finale
  const kf = outCubic(seg(t, 5.6, 6.6));
  ctx.save(); ctx.globalAlpha = kf;
  ctx.beginPath(); ctx.moveTo(612, 216); ctx.lineTo(640, 176); ctx.lineTo(652, 192); ctx.lineTo(662, 180); ctx.lineTo(684, 216); ctx.closePath();
  ctx.fillStyle = C.accent; ctx.fill(); ctx.restore();
  text("ai-running-coach", W / 2, 300 + (1 - kf) * 16, { size: 68, weight: 800, font: SORA, align: "center", alpha: kf, spacing: "-2px" });
  text("github.com/mmornati/ai-running-coach", W / 2, 352, { size: 22, weight: 600, font: MONO, align: "center", color: C.accent, alpha: seg(t, 6.2, 6.8) });
  text(S.ides, W / 2, 410, { size: 16, align: "center", color: C.soft, alpha: seg(t, 6.6, 7.2) });
  text(S.disclaimer, W / 2, 640, { size: 14, align: "center", color: C.faint, alpha: seg(t, 7.0, 7.6) });
}

ARC.episode({
  n: 0, slug: "bande-annonce", root: "../", base: "bande-annonce/", shotsBase: "shots/",
  strings: STR,
  scenes: { intro: sIntro, problem: sProblem, arch: sArch, staff: sStaff, morning: sMorning,
            plan: sPlan, race: sRace, trace: sTrace, pocket: sPocket, outro: sOutro },
});
})();
