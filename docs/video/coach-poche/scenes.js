/* Le Sentier · étape 10 — « Le coach dans la poche » : machine coach, synchronisation
 * automatique (cron ou mode veille), notification push (ntfy), Remote Control et commandes
 * courtes, tableau de bord mobile, et ce qui n'est pas possible.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}].
 * Athlète et chiffres fictifs (bible de la série : Camille, mardi 29 septembre 2026).
 * Helpers locaux : machine, nuage Garmin, montre, défilement de conversation. */
"use strict";
(() => {
const STR = {
  fr: {
    k1: "01 · LA MACHINE COACH", h1: "Elle veille pendant que vous dormez.",
    box: "machine coach", always: "toujours allumée", chips: ["workspace/ (Markdown)", "~/.garminconnect", "garmin-mcp"],
    cloud: "Garmin Connect", cron: "cron · scripts/daily-sync.sh", syncing: "synchro",
    k2: "02 · LE MODE VEILLE", h2: "Zéro jeton tant que rien ne bouge.",
    modeL: "[sync].mode = \"watch\"", poll: "garmin_watch.py · toutes les 15 min · get_device_last_used", tokens: "jetons dépensés", zeroTok: "0 jeton · rien de neuf",
    chain: [["settle_min", "attendre 10 min : Garmin finit ses calculs"], ["daily-sync.sh", "--trigger morning,activity:<id>"], ["le coach", "se réveille, une seule fois"]],
    newer: "du neuf : sommeil ou séance absents du workspace",
    k3: "03 · SEULEMENT LE MANQUANT", h3: "Le coach complète, jamais plus.",
    files: [["2026-09-27", "activities/…_trail.md", "présent"], ["2026-09-28", "medical/…_health.md", "présent"], ["2026-09-29", "medical/…_health.md", "manquant → récupéré"]],
    resume: ["Séances : à jour", "Sommeil : 6 h 12", "HRV : 38 ms — basse (baseline 52-70)", "Readiness : 34", "Alerte : aucune"], resumeNote: "5 lignes maximum · extrait mot pour mot",
    k4: "04 · LA NOTIFICATION", h4: "Tout est là avant le café.",
    flow: ["daily-sync.sh", "notify.sh", "ntfy"], ntfyNote: ["gratuit, sans compte", "appli iOS / Android", "serveur public ou le vôtre"], setup: "scripts/setup-ntfy.sh", topic: "running-coach-xxxxxxxx",
    day: "mardi 29 septembre", phoneApp: "ntfy",
    k5: "05 · REMOTE CONTROL", h5: "Le coach répond au téléphone.",
    rc: "appli Claude → Code → AI Running Coach", rcSub: "Remote Control · abonnement Pro/Max · la session tourne sur la machine coach",
    chatHead: "AI Running Coach", live: "en ligne · machine coach",
    cmds: [["/today", "la séance du jour, le bilan, la météo"], ["/why", "la raison d'une décision, tirée du journal"], ["/week", "l'état de la semaine"], ["/race", "compte à rebours et préparation"]],
    msgs: [["/today", "Aujourd'hui — à ajuster : EF 45 min · soir 18-19 h, 19 °C"], ["/why", "Bilan matinal → alléger : HRV 38 ms sous la bande 52-70, FC de repos +6, readiness 34."], ["/week", "Semaine du 28 : mar EF 45' · jeu côtes 8×1' (garde-fou r7) · sam 2 h 30"], ["/race", "Trail des Crêtes · J-54 · 42 km, 2 100 m D+"]],
    never: "n'écrit jamais un plan, ne pousse rien vers Garmin",
    k6: "06 · LE TABLEAU DE BORD", h6: "Lisible en largeur téléphone.",
    caps: [["Aujourd'hui", "le verdict et sa raison"], ["Semaine", "les séances, jour par jour"], ["Coach", "la carte d'approbation : les écritures Garmin restent confirmées"]],
    access: "tunnel SSH ou reverse proxy · 127.0.0.1 par défaut", capNote: "Tableau de bord mobile (interface en français)",
    k7: "07 · SOYONS HONNÊTES", h7: "Ce qui n'est pas possible.",
    okT: "Possible", noT: "Pas possible, ou à valider",
    ok: ["Remote Control sur l'abonnement Pro/Max", "Synchro cron ou veille, sur l'abonnement", "Notification push ntfy", "Synchro sur OpenRouter : clé API, plafond quotidien"],
    no: [["Un front mobile maison sur votre abonnement", "Anthropic le bloque : seule une clé API, facturée au token, le permet (le chat du tableau de bord, en option)."], ["Des photos de chaussures depuis le téléphone", "Pas validé. Contournement : copier les photos dans gear/photos/, puis /inspection."], ["Une machine coach éteinte", "Plan B : routines cloud Claude, 5 par jour en Pro, 15 en Max."]],
  },
  en: {
    k1: "01 · THE COACH MACHINE", h1: "It keeps watch while you sleep.",
    box: "coach machine", always: "always on", chips: ["workspace/ (Markdown)", "~/.garminconnect", "garmin-mcp"],
    cloud: "Garmin Connect", cron: "cron · scripts/daily-sync.sh", syncing: "sync",
    k2: "02 · WATCH MODE", h2: "Zero tokens while nothing moves.",
    modeL: "[sync].mode = \"watch\"", poll: "garmin_watch.py · every 15 min · get_device_last_used", tokens: "tokens spent", zeroTok: "0 tokens · nothing new",
    chain: [["settle_min", "wait 10 min: Garmin finishes its maths"], ["daily-sync.sh", "--trigger morning,activity:<id>"], ["the coach", "wakes up, once"]],
    newer: "something new: sleep or a run missing from the workspace",
    k3: "03 · ONLY WHAT'S MISSING", h3: "The coach fills gaps, nothing more.",
    files: [["2026-09-27", "activities/…_trail.md", "present"], ["2026-09-28", "medical/…_health.md", "present"], ["2026-09-29", "medical/…_health.md", "missing → fetched"]],
    resume: ["Sessions: up to date", "Sleep: 6 h 12", "HRV: 38 ms — low (baseline 52-70)", "Readiness: 34", "Alert: none"], resumeNote: "5 lines at most · extracted word for word",
    k4: "04 · THE NOTIFICATION", h4: "All there before the coffee.",
    flow: ["daily-sync.sh", "notify.sh", "ntfy"], ntfyNote: ["free, no account", "iOS / Android app", "public server or your own"], setup: "scripts/setup-ntfy.sh", topic: "running-coach-xxxxxxxx",
    day: "Tuesday, September 29", phoneApp: "ntfy",
    k5: "05 · REMOTE CONTROL", h5: "The coach answers on your phone.",
    rc: "Claude app → Code → AI Running Coach", rcSub: "Remote Control · Pro/Max subscription · the session runs on the coach machine",
    chatHead: "AI Running Coach", live: "online · coach machine",
    cmds: [["/today", "today's session, the check, the weather"], ["/why", "the reason for a decision, from the log"], ["/week", "this week's status"], ["/race", "countdown and readiness"]],
    msgs: [["/today", "Today — adjust: easy 45 min · evening 6-7 pm, 19 °C"], ["/why", "Morning check → ease off: HRV 38 ms below the 52-70 band, resting HR +6, readiness 34."], ["/week", "Week of the 28th: Tue easy 45' · Thu hills 8×1' (guardrail r7) · Sat 2 h 30"], ["/race", "Trail des Crêtes · D-54 · 42 km, 2,100 m gain"]],
    never: "never writes a plan, never pushes to Garmin",
    k6: "06 · THE DASHBOARD", h6: "Readable at phone width.",
    caps: [["Today", "the verdict and its reason"], ["Week", "sessions, day by day"], ["Coach", "the approval card: Garmin writes stay confirmed"]],
    access: "SSH tunnel or reverse proxy · 127.0.0.1 by default", capNote: "Mobile dashboard (French UI)",
    k7: "07 · BEING HONEST", h7: "What is not possible.",
    okT: "Possible", noT: "Not possible, or to be validated",
    ok: ["Remote Control on a Pro/Max subscription", "Cron or watch sync, on the subscription", "ntfy push notification", "Sync on OpenRouter: API key, daily cap"],
    no: [["A home-made mobile front on your subscription", "Anthropic blocks it: only an API key, billed per token, allows it (the dashboard chat, optional)."], ["Shoe photos from the phone", "Not validated. Workaround: copy photos into gear/photos/, then /inspection."], ["A coach machine that is off", "Plan B: Claude cloud routines, 5 a day on Pro, 15 on Max."]],
  },
};

/* ------------------------------- dessins locaux ------------------------------- */
function cloud(cx, cy, s, col, alpha = 1) {
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx, cy); ctx.scale(s, s);
  ctx.fillStyle = col; ctx.beginPath(); ctx.arc(-26, 6, 20, 0, Math.PI * 2); ctx.arc(2, -8, 28, 0, Math.PI * 2); ctx.arc(30, 8, 20, 0, Math.PI * 2); ctx.fill();
  ctx.fillRect(-26, 6, 56, 20); ctx.restore();
}
function machine(x, y, w, h, t, alpha = 1, flash = 0) {
  ctx.save(); ctx.globalAlpha *= alpha;
  panel(x, y, w, h, { r: 16, fill: C.panel2, stroke: "#33463b", shadow: true });
  for (let i = 0; i < 5; i++) line([[x + w - 80 + i * 12, y + 22], [x + w - 80 + i * 12, y + h - 22]], C.line, 3);
  const pulse = 0.55 + 0.45 * Math.sin(t * 3);
  dot(x + 30, y + h / 2, 7, C.accent, 0.5 + 0.5 * pulse); dot(x + 30, y + h / 2, 14 + 8 * flash, C.accent, 0.12 + 0.3 * flash);
  ctx.restore();
}
function watchIcon(cx, cy, s, col = C.soft, alpha = 1) {
  ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx, cy); ctx.scale(s, s);
  rr(-9, -34, 18, 14, 4); ctx.fillStyle = col; ctx.fill(); rr(-9, 20, 18, 14, 4); ctx.fill();
  rr(-20, -22, 40, 44, 11); ctx.strokeStyle = col; ctx.lineWidth = 3.5; ctx.stroke();
  dot(0, 0, 4, C.accent); ctx.restore();
}

/* ------------------------------ 01 · la machine coach ------------------------------ */
function sNight(t, d, cues) {
  const s1 = at(cues, 1, 5), e1 = atEnd(cues, 1, 12);
  const T1 = s1 + (e1 - s1) * 0.6, T2 = e1 - 0.15;
  const hour = t < T1 ? 7.25 * inOut(seg(t, 0.8, T1)) : 7.25 + 7 * inOut(seg(t, T1 + 0.5, T2));
  // ciel : étoiles puis aube
  const dawn = seg(hour, 5, 7.4), day = seg(hour, 12, 14);
  const g = ctx.createLinearGradient(0, 0, 0, 640); g.addColorStop(0, "rgba(13,20,16,0)"); g.addColorStop(1, `rgba(240,180,60,${0.04 + 0.14 * dawn})`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, 640);
  const R = rng(10);
  for (let i = 0; i < 46; i++) { const x = R() * W, y = 60 + R() * 300, tw = 0.5 + 0.5 * Math.sin(t * 2 + i); dot(x, y, 1 + R() * 1.3, C.ink, (1 - dawn) * 0.5 * tw); }
  kicker(S.k1, seg(t, 0, 0.4)); headline(S.h1, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  // la machine
  const km = outBack(seg(t, 0.3, 1.0));
  const pulse = k => bump(t, k, 0.5);
  const flash = Math.max(pulse(T1 + 0.4), pulse(T2 + 0.4), 0);
  ctx.save(); ctx.translate(0, (1 - clamp(km)) * 30);
  machine(110, 214, 340, 124, t, clamp(km), flash);
  text(S.box, 280, 376, { size: 22, weight: 700, font: SORA, align: "center", alpha: clamp(km) });
  text(S.always, 280, 400, { size: 13, font: MONO, color: C.accent, align: "center", alpha: clamp(km) });
  ctx.restore();
  let cxp = 110;
  S.chips.forEach((c, i) => { const a = s1 + 0.2 + i * 0.5, k = outBack(seg(t, a, a + 0.4)); const w = measure(c, 13, 600, MONO) + 28; if (k > 0) pill(c, cxp, 448, { alpha: clamp(k), size: 13, color: C.ink, fill: C.deep, stroke: C.line }); cxp += w + 12; });
  // Garmin Connect
  const kc = outCubic(seg(t, 0.8, 1.4));
  cloud(930, 290, 1.3, "#22362c", kc);
  text(S.cloud, 930, 360, { size: 16, weight: 600, align: "center", color: C.soft, alpha: kc });
  watchIcon(1090, 290, 1.0, C.soft, kc);
  line([[1060, 290], [1010, 290]], C.faint, 2, kc * 0.7, [4, 5]);
  // paquets quand le cron déclenche
  [T1 + 0.2, T2 + 0.2].forEach(a => {
    const k = seg(t, a, a + 1.6);
    if (k > 0 && k < 1) { packets(850, 290, 460, 290, t, 4, 0.7, Math.sin(Math.PI * k)); pill(S.syncing, 655, 252, { size: 13, alpha: Math.sin(Math.PI * k) }); }
  });
  // frise 24 h
  const x0 = 80, x1 = 1200, y0 = 566, X = h => lerp(x0, x1, h / 24);
  const kf = outCubic(seg(t, 0.5, 1.2));
  line([[x0, y0], [x1, y0]], C.line, 3, kf);
  for (let h = 0; h <= 24; h += 3) { line([[X(h), y0 - 5], [X(h), y0 + 5]], C.faint, 1.5, kf); text(String(h).padStart(2, "0") + ":00", X(h), y0 + 26, { size: 11, font: MONO, color: C.faint, align: "center", alpha: kf }); }
  [[7.25, "07:15", T1], [14.25, "14:15", T2]].forEach(([h, lab, a]) => {
    const k = outBack(seg(t, a - 0.2, a + 0.3)); if (k <= 0) return;
    dot(X(h), y0, 9, C.accent, clamp(k)); text(lab, X(h), y0 - 22, { size: 16, weight: 700, font: MONO, color: C.accent, align: "center", alpha: clamp(k) });
    text(S.cron, X(h), y0 - 44, { size: 12, font: MONO, color: C.soft, align: "center", alpha: clamp(k) });
  });
  const hh = Math.floor(hour), mm = Math.floor((hour - hh) * 60);
  dot(X(hour), y0, 5, C.amber); dot(X(hour), y0, 12, C.amber, 0.22);
  text(`${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`, X(hour), y0 + 52, { size: 14, weight: 700, font: MONO, color: C.amber, align: "center", alpha: kf });
}

/* ------------------------------ 02 · le mode veille ------------------------------ */
function sWatch(t, d, cues) {
  kicker(S.k2, seg(t, 0, 0.4)); headline(S.h2, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 6), a2 = at(cues, 2, 9);
  const kt = outCubic(seg(t, 0.3, 0.9));
  pill(S.modeL, 80, 176, { alpha: kt, size: 14, font: MONO });
  // compteur de jetons
  const llm = seg(t, a2 + 2.2, a2 + 4.2);
  const tok = llm > 0.05;
  text(S.tokens, 1200, 168, { size: 13, font: MONO, color: C.faint, align: "right", alpha: kt });
  text(tok ? "> 0" : "0", 1200, 206, { size: 38, weight: 800, font: SORA, align: "right", color: tok ? C.amber : C.teal, alpha: kt });
  // sondages
  text(S.poll, 80, 262, { size: 13, font: MONO, color: C.soft, alpha: kt });
  const N = 24, x0 = 100, dx = 44.5, y0 = 316, ts = a0 + 0.4, te = a2 - 0.3, hitI = 18;
  for (let i = 0; i < N; i++) {
    const a = i < hitI ? lerp(ts, te, i / (hitI - 1)) : a2 + 0.3 + (i - hitI) * 0.25;
    const k = outBack(seg(t, a, a + 0.3)); if (k <= 0) continue;
    const x = x0 + i * dx, hit = i === hitI;
    if (i > hitI && t > a2 + 0.3) { dot(x, y0, 6, C.faint, 0.35 * clamp(k)); continue; }
    if (hit) { dot(x, y0, 12 * clamp(k), C.amber); dot(x, y0, 24, C.amber, 0.2); }
    else { dot(x, y0, 7 * clamp(k), C.teal, 0.85); ring(x, y0, 12 + 8 * (1 - clamp(k)), C.teal, 1.5, 0.35 * (1 - seg(t, a + 0.3, a + 1.1))); }
  }
  const kn = outCubic(seg(t, a1 - 0.2, a1 + 0.5));
  if (kn > 0) { pill(S.zeroTok, 600, 372, { align: "center", alpha: kn * (1 - seg(t, a2 + 0.2, a2 + 0.8)), size: 15, color: C.teal, fill: "rgba(95,184,160,0.08)", stroke: "rgba(95,184,160,0.45)", font: INTER }); }
  // du neuf
  const kw = outBack(seg(t, a2 + 0.2, a2 + 0.8));
  if (kw > 0) {
    const hx = x0 + hitI * dx;
    watchIcon(hx, 232 + 0, 0.7, C.amber, clamp(kw)); line([[hx, 256], [hx, 296]], C.amber, 2, clamp(kw), [3, 4]);
    para(S.newer, 600, 372, 520, { size: 16, weight: 600, color: C.amber, alpha: clamp(kw) });
  }
  // chaîne de déclenchement
  S.chain.forEach(([a, b], i) => {
    const at0 = a2 + 1.0 + i * 0.9, k = Math.max(outCubic(seg(t, at0, at0 + 0.5)), 0.28 * outCubic(seg(t, 1.0 + i * 0.2, 1.6 + i * 0.2)));
    const x = 80 + i * 380, y = 440, w = 340, hot = i === 2 && llm > 0;
    panel(x, y + (1 - k) * 16, w, 112, { r: 18, fill: hot ? "rgba(240,180,60,0.1)" : C.panel, stroke: hot ? C.amber : C.line, alpha: k });
    text(a, x + 24, y + 42 + (1 - k) * 16, { size: 18, weight: 700, font: MONO, color: hot ? C.amber : C.accent, alpha: k });
    para(b, x + 24, y + 70 + (1 - k) * 16, w - 48, { size: 14, color: C.soft, alpha: k });
    if (i < 2) arrow(x + w + 4, y + 56, x + w + 36, y + 56, seg(t, at0 + 0.3, at0 + 0.8), C.faint, k);
  });
}

/* ------------------------------ 03 · seulement le manquant ------------------------------ */
function sSync(t, d, cues) {
  kicker(S.k3, seg(t, 0, 0.4)); headline(S.h3, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 5.4);
  S.files.forEach(([date, file, st], i) => {
    const k = outCubic(seg(t, 0.5 + i * 0.4, 1.1 + i * 0.4)), y = 190 + i * 112, miss = i === 2;
    const fetch = miss ? seg(t, a0 + 2.0, a0 + 3.2) : 0;
    panel(80, y + (1 - k) * 18, 560, 94, { r: 18, fill: miss && fetch < 1 ? "rgba(240,180,60,0.07)" : C.panel, stroke: miss ? (fetch >= 1 ? C.accent : C.amber) : C.line, alpha: k, lw: miss ? 2 : 1 });
    text(date, 106, y + 38 + (1 - k) * 18, { size: 20, weight: 700, font: SORA, alpha: k });
    text(file, 106, y + 68 + (1 - k) * 18, { size: 14, font: MONO, color: C.soft, alpha: k });
    const label = miss ? (fetch >= 1 ? st.split(" → ")[1] : st.split(" → ")[0]) : st;
    text(label, 616, y + 46 + (1 - k) * 18, { size: 15, weight: 600, align: "right", color: miss && fetch < 1 ? C.amber : C.teal, alpha: k });
    if (!miss || fetch >= 1) check(578, y + 66 + (1 - k) * 18, 12, C.teal, miss ? seg(t, a0 + 3.2, a0 + 3.7) : seg(t, 0.9 + i * 0.4, 1.4 + i * 0.4), k);
    if (miss && fetch > 0 && fetch < 1) { const px = 106 + 400 * fetch; line([[106, y + 84], [px, y + 84]], C.amber, 3, 0.9); }
  });
  // le bloc resume
  const kr = outCubic(seg(t, a1 - 0.4, a1 + 0.2));
  const lines = [{ s: "```resume", c: C.faint, a: a1, b: a1 + 0.3 }];
  S.resume.forEach((s, i) => lines.push({ s, c: i === 4 ? C.accent : C.ink, a: a1 + 0.4 + i * 0.5, b: a1 + 0.8 + i * 0.5 }));
  lines.push({ s: "```", c: C.faint, a: a1 + 3.0 });
  terminal(690, 190, 510, 316, t, lines, { alpha: kr, size: 15, lh: 34, title: "résumé · notification" });
  const kn = outBack(seg(t, a1 + 3.0, a1 + 3.5));
  if (kn > 0) pill(S.resumeNote, 945, 540, { align: "center", alpha: clamp(kn), size: 13 });
}

/* ------------------------------ 04 · la notification ------------------------------ */
function sPush(t, d, cues) {
  kicker(S.k4, seg(t, 0, 0.4)); headline(S.h4, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 4.8);
  const kp = outCubic(seg(t, 0.3, 0.9));
  phone(110, 150, 320, 480, (x, y, w, h) => {
    const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, "#102319"); g.addColorStop(1, "#080f0b");
    ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
    text("07:32", x + w / 2, y + 112, { size: 58, weight: 700, font: SORA, align: "center" });
    text(S.day, x + w / 2, y + 142, { size: 14, color: C.soft, align: "center" });
    const kn = outBack(seg(t, a0 + 2.0, a0 + 2.7));
    if (kn > 0) {
      const ny = y + 190 + (1 - clamp(kn)) * -40, nh = 196;
      panel(x + 10, ny, w - 20, nh, { r: 18, fill: "rgba(24,42,33,0.96)", alpha: clamp(kn) });
      dot(x + 28, ny + 24, 6, C.accent, clamp(kn)); text(S.phoneApp + " · " + S.topic, x + 42, ny + 28, { size: 11, font: MONO, color: C.soft, alpha: clamp(kn) });
      S.resume.forEach((s, i) => text(s, x + 24, ny + 58 + i * 25, { size: 12, font: MONO, color: i === 4 ? C.accent : C.ink, alpha: clamp(kn) * seg(t, a0 + 2.3 + i * 0.15, a0 + 2.6 + i * 0.15) }));
    }
  }, { alpha: kp });
  // le chemin du résumé
  S.flow.forEach((f, i) => {
    const x = 520 + i * 230, y = 190, k = outCubic(seg(t, 0.8 + i * 0.4, 1.4 + i * 0.4));
    panel(x, y + (1 - k) * 14, 190, 70, { r: 16, alpha: k });
    text(f, x + 95, y + 42 + (1 - k) * 14, { size: 16, weight: 700, font: MONO, color: i === 2 ? C.accent : C.ink, align: "center", alpha: k });
    if (i < 2) { arrow(x + 194, y + 35, x + 224, y + 35, seg(t, 1.2 + i * 0.4, 1.7 + i * 0.4), C.faint, k); }
  });
  [0, 1].forEach(i => packets(520 + 230 * i + 194, 225, 520 + 230 * (i + 1) - 4, 225, t + i * 0.4, 2, 1.0, seg(t, a0 + 0.8, a0 + 1.3)));
  const kv = outCubic(seg(t, a1 - 0.2, a1 + 0.4));
  S.ntfyNote.forEach((s, i) => {
    const k = outCubic(seg(t, a1 + i * 0.5, a1 + 0.5 + i * 0.5)); if (k <= 0) return;
    const y = 330 + i * 76;
    panel(520, y + (1 - k) * 14, 680, 60, { r: 14, alpha: k });
    dot(550, y + 30 + (1 - k) * 14, 6, C.teal, k); text(s, 572, y + 37 + (1 - k) * 14, { size: 19, weight: 600, alpha: k });
  });
  const ks = outCubic(seg(t, a1 + 1.8, a1 + 2.4));
  if (ks > 0) pill(S.setup, 520, 580, { size: 14, alpha: ks });
}

/* ------------------------------ 05 · Remote Control ------------------------------ */
function sRemote(t, d, cues) {
  kicker(S.k5, seg(t, 0, 0.4)); headline(S.h5, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6), a1 = at(cues, 1, 6.2);
  const kp = outCubic(seg(t, 0.3, 0.9));
  const m0 = a1 + 0.2, gap = 1.45;
  phone(110, 150, 330, 480, (x, y, w, h) => {
    ctx.fillStyle = "#0a120e"; ctx.fillRect(x, y, w, h);
    ctx.fillStyle = C.panel2; ctx.fillRect(x, y, w, 84);
    dot(x + 24, y + 52, 5, C.accent, 0.6 + 0.4 * Math.sin(t * 4)); text(S.chatHead, x + 38, y + 57, { size: 14, weight: 700, font: SORA });
    text(S.live, x + 38, y + 74, { size: 11, font: MONO, color: C.accent });
    // conversation défilante
    const size = 13, lh = Math.round(size * 1.45), maxW = w - 50;
    const bh = s => wrap(s, maxW - 28, size).length * lh + 28 - (lh - size);
    const items = [];
    S.msgs.forEach(([q, a], i) => {
      const tq = m0 + i * gap, ta = tq + 0.55;
      if (t >= tq) items.push({ s: q, side: "me", a: tq, k: seg(t, tq, tq + 0.4) });
      if (t >= ta) items.push({ s: a, side: "coach", a: ta, k: seg(t, ta, ta + 0.7) });
    });
    let total = 0; items.forEach(it => { it.h = bh(it.s); total += it.h + 10; });
    const avail = h - 84 - 20, off = Math.max(0, total - avail);
    ctx.save(); rr(x, y + 84, w, h - 84, 0); ctx.clip();
    let yy = y + 84 + 12 - off;
    items.forEach(it => { bubble(it.s, x + 12, yy, w - 24 - 0, { size, side: it.side, k: it.k, alpha: clamp(it.k * 3), weight: it.side === "me" ? 700 : 400 }); yy += it.h + 10; });
    ctx.restore();
  }, { alpha: kp });
  // lien vers la machine coach
  const kr = outCubic(seg(t, a0 + 0.2, a0 + 0.9));
  panel(500, 160, 700, 98, { r: 18, alpha: kr });
  text(S.rc, 528, 198, { size: 19, weight: 700, font: SORA, alpha: kr });
  para(S.rcSub, 528, 226, 650, { size: 14, color: C.soft, alpha: kr });
  // les quatre commandes
  S.cmds.forEach(([c, desc], i) => {
    const tq = m0 + i * gap, k = outCubic(seg(t, tq, tq + 0.5)), on = t >= tq && t < tq + gap;
    const y = 284 + i * 70;
    panel(500, y + (1 - k) * 14, 700, 58, { r: 14, fill: on ? "rgba(163,230,53,0.08)" : C.panel, stroke: on ? C.accent : C.line, alpha: k, lw: on ? 2 : 1 });
    text(c, 526, y + 37 + (1 - k) * 14, { size: 20, weight: 700, font: MONO, color: C.accent, alpha: k });
    text(desc, 640, y + 36 + (1 - k) * 14, { size: 16, color: C.soft, alpha: k });
  });
  const kn = outBack(seg(t, m0 + 4 * gap + 0.2, m0 + 4 * gap + 0.8));
  if (kn > 0) pill(S.never, 500, 590, { size: 14, alpha: clamp(kn), color: C.ink, fill: C.deep, stroke: C.accent, font: INTER });
}

/* ------------------------------ 06 · le tableau de bord ------------------------------ */
function sViews(t, d, cues) {
  kicker(S.k6, seg(t, 0, 0.4)); headline(S.h6, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.6);
  const crop = [0, 0, 390, 828];
  const shots = ["mobile-aujourdhui", "mobile-semaine", "mobile-coach"];
  const hl = [[16, 173, 358, 136], [16, 285, 358, 280], [37, 558, 104, 36]];
  shots.forEach((n, i) => {
    const x = 90 + i * 270, y = 160, k = outCubic(seg(t, 0.4 + i * 0.25, 1.1 + i * 0.25));
    const on = t >= a0 + 0.8 + i * 2.2 && t < a0 + 0.8 + (i + 1) * 2.2 + (i === 2 ? 9 : 0);
    ctx.save(); ctx.translate(0, (1 - k) * 30);
    phone(x, y, 242, 470, (px, py, pw, ph) => {
      const m = shot(n, px, py, pw, ph, { chrome: false, r: 0, shadow: false, crop, alpha: 1 });
      const b = m(hl[i]);
      if (b && on) highlight(b[0], b[1], b[2], b[3], seg(t, a0 + 0.8 + i * 2.2, a0 + 1.4 + i * 2.2), i === 2 ? C.amber : C.accent);
    }, { alpha: k });
    ctx.restore();
  });
  S.caps.forEach(([a, b], i) => {
    const at0 = a0 + 0.8 + i * 2.2, k = outCubic(seg(t, at0, at0 + 0.5)); if (k <= 0) return;
    const y = 190 + i * 112;
    panel(920, y, 280, 96, { r: 16, fill: C.panel, stroke: i === 2 ? "rgba(240,180,60,0.5)" : C.line, alpha: k });
    text(a, 942, y + 36, { size: 20, weight: 700, font: SORA, alpha: k });
    para(b, 942, y + 62, 240, { size: 14, color: C.soft, alpha: k });
  });
  const ka = outCubic(seg(t, a0 + 5.2, a0 + 5.9));
  if (ka > 0) para(S.access, 920, 548, 280, { size: 13, font: MONO, color: C.faint, alpha: ka });
  text(S.capNote, 90 + 3 * 270 - 28, 650, { size: 12, font: MONO, color: C.faint, align: "right", alpha: outCubic(seg(t, 1.2, 1.8)) });
}

/* ------------------------------ 07 · ce qui n'est pas possible ------------------------------ */
function sLimits(t, d, cues) {
  kicker(S.k7, seg(t, 0, 0.4)); headline(S.h7, seg(t, 0.1, 0.7)); fictTag(seg(t, 0.3, 0.8));
  const kl = outCubic(seg(t, 0.3, 0.9));
  text(S.okT.toUpperCase(), 80, 186, { size: 13, weight: 600, font: MONO, color: C.teal, alpha: kl, spacing: "2px" });
  S.ok.forEach((s, i) => {
    const k = outCubic(seg(t, 0.6 + i * 0.35, 1.2 + i * 0.35)), y = 204 + i * 84;
    panel(80, y + (1 - k) * 14, 440, 70, { r: 16, alpha: k });
    check(112, y + 38 + (1 - k) * 14, 14, C.teal, seg(t, 0.9 + i * 0.35, 1.4 + i * 0.35), k);
    para(s, 142, y + 32 + (1 - k) * 14, 360, { size: 16, weight: 600, alpha: k });
  });
  text(S.noT.toUpperCase(), 580, 186, { size: 13, weight: 600, font: MONO, color: C.amber, alpha: kl, spacing: "2px" });
  S.no.forEach(([a, b], i) => {
    const at0 = at(cues, i, 1 + i * 3.5) - 0.1, k = outCubic(seg(t, at0, at0 + 0.5)); if (k <= 0) return;
    const y = 204 + i * 130, col = i === 1 ? C.amber : C.red;
    panel(580, y + (1 - k) * 16, 620, 114, { r: 18, fill: C.panel, stroke: col, alpha: k });
    ctx.save(); ctx.globalAlpha *= k;
    if (i === 1) { text("?", 614, y + 66, { size: 34, weight: 800, font: SORA, color: col, align: "center" }); }
    else { line([[602, y + 44], [626, y + 68]], col, 4); line([[626, y + 44], [602, y + 68]], col, 4); }
    ctx.restore();
    text(a, 660, y + 42 + (1 - k) * 16, { size: 19, weight: 700, font: SORA, alpha: k });
    para(b, 660, y + 70 + (1 - k) * 16, 520, { size: 14, color: C.soft, alpha: k });
  });
}

ARC.episode({
  n: 10, slug: "coach-poche",
  strings: STR,
  shots: ["mobile-aujourdhui", "mobile-semaine", "mobile-coach"],
  scenes: { night: sNight, watch: sWatch, sync: sSync, push: sPush, remote: sRemote, views: sViews, limits: sLimits },
});
})();
