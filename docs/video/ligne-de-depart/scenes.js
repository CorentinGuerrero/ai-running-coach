/* Le Sentier · étape 1 — « Ligne de départ » : installation et premier démarrage.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}] —
 * at(cues, i, repli) cale une animation sur la voix, quelle que soit la langue.
 * Tout est fictif (athlète Camille) ; les commandes, options, noms de vérifications et
 * chemins sont ceux du dépôt (install.sh --help, docs/quickstart.md, scripts/coach_doctor.py). */
"use strict";
(() => {
const STR = {
  fr: {
    k1: "01 · TROIS LIGNES", h1: "À vos marques.",
    cmds: ["git clone https://github.com/mmornati/ai-running-coach.git", "cd ai-running-coach", "./install.sh"],
    rsg: ["À vos marques", "Prêts", "Partez !"],
    pre: ["macOS · Linux", "bash 3.2+", "curl", "git"],
    k2: "02 · L'INSTALLATEUR", h2: "Ce que fait install.sh.",
    items: [
      ["uv", "gestionnaire Python, installé si absent"],
      ["garmin-mcp + garmin-mcp-auth", "accès Garmin Connect"],
      ["Liste blanche d'outils", "GARMIN_ENABLED_TOOLS · ~151 → ~25 outils"],
      ["Configuration de l'IDE", "serveur MCP garmin en mode direct"],
      ["Dossiers de travail", "exclus du dépôt public (.gitignore)"],
    ],
    ides: [["Claude Code", ".claude/agents"], ["GitHub Copilot", ".github/agents"], ["OpenCode", ".opencode/agents"],
           ["Gemini CLI", ".gemini/commands"], ["Cursor", ".cursor/mcp.json"], ["Windsurf", ".windsurf/mcp_config.json"]],
    idesTitle: "6 IDE supportés",
    k3: "03 · À VOTRE CARTE", h3: "Le staff, la source, le workspace.",
    opts: [["--agents coach,nutritionist", "le staff que vous choisissez"], ["--no-medical", "tous les agents sauf le médecin"],
           ["--source intervals", "sans montre Garmin"], ["--workspace ~/mon-workspace", "vos données dans un dépôt privé"]],
    agents: ["coach", "medical", "nutritionist", "course-strategist"],
    noWatch: "COROS · Suunto · Polar · Apple", srcLab: "[data].source",
    engine: "moteur", engineSub: "dépôt public · ~/ai-running-coach", ws: "workspace", wsSub: "dépôt privé · ~/mon-workspace",
    wsDirs: "activities/ medical/ planning/ …", links: "liens", pull: "git pull = nouveautés",
    k4: "04 · GARMIN", h4: "Une seule authentification.",
    auth: ["uv run garmin-mcp-auth", "Email Garmin Connect : ", "Mot de passe : ", "Code MFA : ", "✓ Jetons enregistrés"],
    authNote: "saisie masquée",
    home: "Votre dossier personnel", homeFile: "garmin_tokens.json", valid: "valides ~6 mois",
    repo: "Le dépôt du projet", never: "identifiants : jamais stockés",
    k5: "05 · /COACH-SETUP", h5: "Un entretien, pas un formulaire.",
    q: ["Quel staff voulez-vous ?", "Quelle discipline principale ?", "Comment voulez-vous qu'on vous parle ?", "Garmin a trouvé ces valeurs — on les garde ?"],
    a: ["Les quatre", "Trail / ultra", "Encourageant", "Oui"],
    garminVals: "FC max 188 · FC repos 46 · FC seuil 172 bpm", garminSrc: "source : Garmin, moyennes et maxima observés",
    files: [["config/workspace.user.toml", "vos réglages · gitignoré"], ["planning/Runner_Profile.md", "profil : Camille, 36 ans, FC max 188"],
            ["planning/active_objective.md", "Trail des Crêtes · 42 km · 2 100 m D+"]],
    rerun: "Relancer ne remplace jamais une réponse.", titleChat: "Claude Code · /coach-setup",
    k6: "06 · /COACH-DOCTOR", h6: "Le diagnostic, en une commande.",
    docHead: "coach doctor — /home/camille/mon-workspace",
    checks: [
      ["ok", "garmin_token", "Tokens Garmin valides (176 jour(s) restants estimés)."],
      ["ok", "garmin_mcp", "commande « garmin-mcp » présente."],
      ["ok", "config_files", "Configuration TOML valide."],
      ["ok", "athlete_profile", "FC max et FC de repos renseignées dans le profil."],
      ["ok", "index_freshness", "Index .arc/coach.db à jour."],
      ["ok", "out_of_contract", "Aucun fichier hors contrat."],
      ["ok", "fit_reader", "Lecteur FIT (fitparse) présent."],
      ["info", "daily_sync_scheduled", "synchronisation Garmin manuelle uniquement."],
      ["info", "ntfy_configured", "Notifications désactivées."],
    ],
    docEnd: "Aucune vérification en échec.", docPills: ["ne modifie rien", "n'appelle pas Garmin par défaut"],
    k7: "07 · /TODAY", h7: "Votre première question.",
    todayQ: "/today",
    todayA: ["Aujourd'hui — à ajuster : seuil 5 × 6 min → EF 45 min", "Bilan matinal : HRV 38 ms · FC repos 52 bpm · readiness 34/100", "Créneau : soir 18 h-19 h · 19 °C · vent 10 km/h"],
    todayTags: ["la séance du jour", "le bilan matinal", "le créneau météo"],
    readOnly: "Lecture seule : n'écrit ni plan ni décision, ne pousse rien vers Garmin.",
  },
  en: {
    k1: "01 · THREE LINES", h1: "On your marks.",
    cmds: ["git clone https://github.com/mmornati/ai-running-coach.git", "cd ai-running-coach", "./install.sh"],
    rsg: ["On your marks", "Set", "Go!"],
    pre: ["macOS · Linux", "bash 3.2+", "curl", "git"],
    k2: "02 · THE INSTALLER", h2: "What install.sh does.",
    items: [
      ["uv", "Python manager, installed if missing"],
      ["garmin-mcp + garmin-mcp-auth", "Garmin Connect access"],
      ["Tool allow-list", "GARMIN_ENABLED_TOOLS · ~151 → ~25 tools"],
      ["IDE configuration", "garmin MCP server in direct mode"],
      ["Working folders", "kept out of the public repo (.gitignore)"],
    ],
    ides: [["Claude Code", ".claude/agents"], ["GitHub Copilot", ".github/agents"], ["OpenCode", ".opencode/agents"],
           ["Gemini CLI", ".gemini/commands"], ["Cursor", ".cursor/mcp.json"], ["Windsurf", ".windsurf/mcp_config.json"]],
    idesTitle: "6 supported IDEs",
    k3: "03 · YOUR WAY", h3: "Staff, source, workspace.",
    opts: [["--agents coach,nutritionist", "the staff you pick"], ["--no-medical", "every agent except the doctor"],
           ["--source intervals", "no Garmin watch"], ["--workspace ~/my-workspace", "your data in a private repo"]],
    agents: ["coach", "medical", "nutritionist", "course-strategist"],
    noWatch: "COROS · Suunto · Polar · Apple", srcLab: "[data].source",
    engine: "engine", engineSub: "public repo · ~/ai-running-coach", ws: "workspace", wsSub: "private repo · ~/my-workspace",
    wsDirs: "activities/ medical/ planning/ …", links: "links", pull: "git pull = what's new",
    k4: "04 · GARMIN", h4: "One sign-in.",
    auth: ["uv run garmin-mcp-auth", "Garmin Connect email: ", "Password: ", "MFA code: ", "✓ Tokens saved"],
    authNote: "input hidden",
    home: "Your home folder", homeFile: "garmin_tokens.json", valid: "valid for ~6 months",
    repo: "The project repository", never: "credentials: never stored",
    k5: "05 · /COACH-SETUP", h5: "An interview, not a form.",
    q: ["Which staff do you want?", "Which main discipline?", "How should we talk to you?", "Garmin found these values — keep them?"],
    a: ["All four", "Trail / ultra", "Encouraging", "Yes"],
    garminVals: "Max HR 188 · resting HR 46 · threshold HR 172 bpm", garminSrc: "source: Garmin, observed averages and maxima",
    files: [["config/workspace.user.toml", "your settings · gitignored"], ["planning/Runner_Profile.md", "profile: Camille, 36, max HR 188"],
            ["planning/active_objective.md", "Trail des Crêtes · 42 km · 2,100 m D+"]],
    rerun: "Running it again never overwrites an answer.", titleChat: "Claude Code · /coach-setup",
    k6: "06 · /COACH-DOCTOR", h6: "Diagnostics in one command.",
    docHead: "coach doctor — /home/camille/my-workspace",
    checks: [
      ["ok", "garmin_token", "Garmin tokens valid (176 day(s) left, estimated)."],
      ["ok", "garmin_mcp", "command “garmin-mcp” present."],
      ["ok", "config_files", "TOML configuration valid."],
      ["ok", "athlete_profile", "Max HR and resting HR filled in the profile."],
      ["ok", "index_freshness", "Index .arc/coach.db up to date."],
      ["ok", "out_of_contract", "No out-of-contract file."],
      ["ok", "fit_reader", "FIT reader (fitparse) present."],
      ["info", "daily_sync_scheduled", "manual Garmin sync only."],
      ["info", "ntfy_configured", "Notifications disabled."],
    ],
    docEnd: "No failing check.", docPills: ["changes nothing", "doesn't call Garmin by default"],
    k7: "07 · /TODAY", h7: "Your first question.",
    todayQ: "/today",
    todayA: ["Today — adjust: threshold 5 × 6 min → easy 45 min", "Morning check: HRV 38 ms · resting HR 52 bpm · readiness 34/100", "Window: evening 6-7 pm · 19 °C · wind 10 km/h"],
    todayTags: ["today's session", "the morning check", "the weather window"],
    readOnly: "Read-only: writes no plan or decision, pushes nothing to Garmin.",
  },
};

/* --------------------- 01 · blocs de départ + trois lignes ---------------- */
function startingBlock(x, y, k) {
  ctx.save(); ctx.globalAlpha *= k;
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 72, y); ctx.lineTo(x + 72, y - 28); ctx.lineTo(x + 22, y - 52); ctx.closePath();
  ctx.fillStyle = C.pine; ctx.fill(); ctx.strokeStyle = C.accent; ctx.lineWidth = 2; ctx.stroke();
  line([[x + 26, y - 46], [x + 72, y - 22]], C.accent, 4);
  ctx.restore();
}
function sBlocks(t, d, cues) {
  kicker(S.k1, seg(t, 0, 0.4));
  headline(S.h1, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.8), a1 = at(cues, 1, 5.4);
  const ts = [a0 + 0.4, a0 + 2.4, a0 + 3.8]; // début de frappe de chaque commande
  const dur = [1.6, 0.9, 0.8];
  const kt = outCubic(seg(t, 0.3, 0.9));
  const lines = S.cmds.map((s, i) => ({ p: "$ ", s, c: i === 2 ? C.accent : C.ink, w: i === 2 ? 700 : 400, a: ts[i], b: ts[i] + dur[i] }));
  terminal(80, 170, 840, 220, t, lines, { alpha: kt, size: 21, lh: 46, title: "bash" });
  // « à vos marques / prêts / partez » calé sur les commandes
  const act = t < ts[1] ? 0 : t < ts[2] ? 1 : 2;
  S.rsg.forEach((w, i) => {
    const on = t >= ts[i] && act === i, past = t >= ts[i];
    const k = outCubic(seg(t, ts[i] - 0.1, ts[i] + 0.4));
    const x = 970, y = 226 + i * 58;
    text(w.toUpperCase(), x, y, { size: i === 2 ? 36 : 28, weight: 800, font: SORA, color: on ? (i === 2 ? C.accent : C.amber) : C.faint, alpha: 0.25 + 0.75 * (past ? 1 : 0), spacing: "1px" });
    if (on) dot(x - 24, y - 11, 7, i === 2 ? C.accent : C.amber, k);
  });
  // piste, blocs, coureur
  const gy = 520;
  line([[80, gy], [1200, gy]], C.line, 2);
  for (let i = 0; i < 12; i++) line([[140 + i * 96, gy + 16], [176 + i * 96, gy + 16]], C.line, 2, 0.6);
  startingBlock(110, gy, outCubic(seg(t, 0.4, 1.0)));
  const go = ts[2] + 1.0;
  const run = inOut(seg(t, go, Math.min(d - 0.8, go + 3.6)));
  const crouch = t < ts[1] ? 0 : t < go ? 1 : 0;
  const rx = lerp(206, 1130, run), ry = gy - 26 - 8 * crouch - Math.abs(Math.sin(t * 9)) * 6 * seg(run, 0.02, 0.1);
  if (run > 0) for (let i = 1; i <= 8; i++) dot(rx - i * 16, ry + (i % 2 ? 2 : -1), 6 - i * 0.5, C.accent, 0.5 * (1 - i / 9) * seg(run, 0, 0.1));
  dot(rx, ry, 17, C.accent, outCubic(seg(t, 0.5, 1.0))); dot(rx, ry, 30, C.accent, 0.16);
  // prérequis
  S.pre.forEach((s, i) => {
    const k = outBack(seg(t, a1 + 0.2 + i * 0.4, a1 + 0.7 + i * 0.4));
    if (k > 0) pill(s, 80 + i * 210 + 90, 592, { alpha: clamp(k), size: 18, color: C.ink, fill: C.panel, stroke: C.line, align: "center" });
  });
}

/* ------------------- 02 · ce que fait l'installateur ---------------------- */
function sInstaller(t, d, cues) {
  kicker(S.k2, seg(t, 0, 0.4));
  headline(S.h2, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.8), a1 = at(cues, 1, 6);
  const starts = [a0 + 0.1, a0 + 1.5, a0 + 3.4, a1 + 0.2, a1 + 5.2];
  const kp = outCubic(seg(t, 0.3, 0.9));
  panel(80, 168, 640, 440, { alpha: kp });
  S.items.forEach(([name, sub], i) => {
    const y = 204 + i * 68, a = starts[i], k = outCubic(seg(t, a, a + 0.4));
    if (k <= 0) return;
    const done = seg(t, a + 0.5, a + 1.0);
    if (done < 1) { // spinner
      ctx.save(); ctx.globalAlpha *= k;
      ctx.beginPath(); ctx.arc(116, y + 18, 11, t * 7, t * 7 + 4.2); ctx.strokeStyle = C.accent; ctx.lineWidth = 3; ctx.lineCap = "round"; ctx.stroke();
      ctx.restore();
    } else dot(116, y + 18, 15, C.accent, 0.14 * k);
    check(116, y + 18, 15, C.accent, done, k);
    text(name, 148, y + 14, { size: 22, weight: 700, font: i < 2 ? MONO : SORA, alpha: k, color: done >= 1 ? C.ink : C.soft });
    text(sub, 148, y + 40, { size: 15, font: MONO, color: C.faint, alpha: k });
  });
  // dossiers de travail
  const dirs = ["activities", "medical", "nutrition", "planning", "rapports", "gear", "resources"];
  dirs.forEach((s, i) => {
    const a = starts[4] + 0.6 + i * 0.22, k = outBack(seg(t, a, a + 0.35));
    if (k <= 0) return;
    pill(s + "/", 108 + (i % 4) * 150 + 48, 556 + Math.floor(i / 4) * 40, { alpha: clamp(k), size: 14, color: C.soft, fill: C.panel2, stroke: C.line, align: "center", padX: 10 });
  });
  // les 6 IDE
  const kt = outCubic(seg(t, a1 - 0.2, a1 + 0.4));
  text(S.idesTitle.toUpperCase(), 770, 190, { size: 13, weight: 600, font: MONO, color: C.faint, spacing: "2px", alpha: kt });
  S.ides.forEach(([n, p], i) => {
    const a = a1 + 0.5 + i * 0.62, k = outBack(seg(t, a, a + 0.45));
    if (k <= 0) return;
    const x = 770 + (i % 2) * 226, y = 210 + Math.floor(i / 2) * 124 + (1 - clamp(k)) * 16;
    const glow = bump(t, a + 0.3, 0.5);
    panel(x, y, 210, 104, { r: 14, alpha: clamp(k), fill: C.panel2, stroke: glow > 0.2 ? C.accent : C.line, lw: glow > 0.2 ? 2 : 1 });
    dot(x + 24, y + 30, 8, C.accent, clamp(k) * 0.9);
    text(n, x + 42, y + 38, { size: 19, weight: 700, font: SORA, alpha: clamp(k) });
    const ps = Math.min(13.5, 13.5 * 176 / measure(p, 13.5, 400, MONO));  // le chemin tient dans la carte
    text(p, x + 18, y + 76, { size: ps, font: MONO, color: C.soft, alpha: clamp(k) });
  });
}

/* ------------------------- 03 · options (à la carte) ---------------------- */
function sOptions(t, d, cues) {
  kicker(S.k3, seg(t, 0, 0.4));
  headline(S.h3, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.8), a1 = at(cues, 1, 6.4), e1 = atEnd(cues, 1, a1 + 7);
  const b = [a0 + 0.1, a0 + (a1 - a0) * 0.5, a1 + 0.1, a1 + (e1 - a1) * 0.55];
  const act = t < b[1] ? 0 : t < b[2] ? 1 : t < b[3] ? 2 : 3;
  S.opts.forEach(([flag, sub], i) => {
    const k = outCubic(seg(t, 0.3 + i * 0.12, 0.9 + i * 0.12));
    const on = t >= b[0] && act === i, y = 180 + i * 100;
    panel(80, y, 560, 82, { r: 16, fill: on ? "rgba(163,230,53,0.07)" : C.panel, stroke: on ? C.accent : C.line, alpha: k, lw: on ? 2 : 1 });
    text(flag, 106, y + 38, { size: 21, weight: 700, font: MONO, color: on ? C.accent : C.ink, alpha: k });
    text(sub, 106, y + 64, { size: 16, color: C.soft, alpha: k });
  });
  // volet de droite : une vue par option
  const X = 690, Y = 180, Wd = 510, Hh = 382;
  const vis = i => { const lo = i === 0 ? 0 : b[i], hi = i === 3 ? 1e9 : b[i + 1]; return Math.min(seg(t, lo, lo + 0.35), 1 - seg(t, hi - 0.01, hi + 0.25)); };
  panel(X, Y, Wd, Hh, { alpha: outCubic(seg(t, 0.5, 1.1)) });
  // 0 / 1 : le staff
  const vs = Math.max(vis(0), vis(1));
  if (vs > 0) {
    S.agents.forEach((n, i) => {
      const y = Y + 36 + i * 80, on = (act === 0 ? [1, 0, 1, 0] : [1, 0, 1, 1])[i];
      const sw = seg(t, b[1], b[1] + 0.5);
      const shown = i === 3 ? (act >= 1 ? 1 : 0) : on;
      const alpha = vs * (shown ? 1 : 0.35);
      panel(X + 30, y, Wd - 60, 62, { r: 14, fill: shown ? C.panel2 : "#0f1913", stroke: shown ? "rgba(163,230,53,0.45)" : C.line, alpha: vs });
      dot(X + 62, y + 31, 9, shown ? C.accent : C.faint, alpha);
      text(n, X + 88, y + 39, { size: 22, weight: 700, font: MONO, color: shown ? C.ink : C.faint, alpha: vs });
      if (!shown) line([[X + 84, y + 31], [X + 88 + measure(n, 20, 700, MONO) + 6, y + 31]], C.red, 2, vs * 0.8);
      if (i === 1 && act === 1) text("--no-medical", X + Wd - 50, y + 38, { size: 13, font: MONO, color: C.red, align: "right", alpha: vs * sw });
    });
  }
  // 2 : la source
  const v2 = vis(2);
  if (v2 > 0) {
    const sw = seg(t, b[2] + 0.4, b[2] + 1.1);
    text(S.srcLab, X + 30, Y + 54, { size: 14, font: MONO, color: C.faint, alpha: v2 });
    panel(X + 30, Y + 80, 450, 64, { r: 32, fill: "#0a120e", alpha: v2 });
    const px = lerp(X + 36, X + 36 + 220, inOut(sw));
    panel(px, Y + 86, 218, 52, { r: 26, fill: "rgba(163,230,53,0.14)", stroke: C.accent, alpha: v2 });
    text("garmin", X + 36 + 109, Y + 119, { size: 19, weight: 700, font: MONO, color: sw < 0.5 ? C.accent : C.faint, align: "center", alpha: v2 });
    text("intervals", X + 256 + 109, Y + 119, { size: 19, weight: 700, font: MONO, color: sw >= 0.5 ? C.accent : C.faint, align: "center", alpha: v2 });
    para(S.noWatch, X + 30, Y + 200, 450, { size: 17, color: C.soft, alpha: v2 * seg(t, b[2] + 1.0, b[2] + 1.6) });
    text("intervals-icu-mcp", X + 30, Y + 250, { size: 15, font: MONO, color: C.faint, alpha: v2 * seg(t, b[2] + 1.3, b[2] + 1.9) });
  }
  // 3 : le workspace
  const v3 = vis(3);
  if (v3 > 0) {
    const k = seg(t, b[3] + 0.2, b[3] + 0.9);
    panel(X + 40, Y + 30, 430, 100, { r: 14, fill: C.panel2, alpha: v3 });
    text(S.engine, X + 62, Y + 66, { size: 20, weight: 700, font: SORA, alpha: v3 });
    text(S.engineSub, X + 62, Y + 96, { size: 13, font: MONO, color: C.faint, alpha: v3 });
    arrow(X + 255, Y + 140, X + 255, Y + 214, outCubic(k), C.accent, v3);
    text(S.links, X + 270, Y + 182, { size: 13, font: MONO, color: C.accent, alpha: v3 * k });
    panel(X + 40, Y + 224, 430, 118, { r: 14, fill: "rgba(163,230,53,0.06)", stroke: C.accent, alpha: v3 });
    text(S.ws, X + 62, Y + 262, { size: 20, weight: 700, font: SORA, alpha: v3 });
    text(S.wsSub, X + 62, Y + 290, { size: 13, font: MONO, color: C.faint, alpha: v3 });
    text(S.wsDirs, X + 62, Y + 318, { size: 13, font: MONO, color: C.soft, alpha: v3 });
    ctx.save(); ctx.globalAlpha *= v3;
    ctx.beginPath(); ctx.arc(X + 442, Y + 252, 8, Math.PI, 0); ctx.strokeStyle = C.accent; ctx.lineWidth = 2.5; ctx.stroke();
    rr(X + 432, Y + 252, 20, 16, 4); ctx.fillStyle = C.accent; ctx.fill(); ctx.restore();
  }
}

/* ---------------------- 04 · authentification Garmin ---------------------- */
function sGarmin(t, d, cues) {
  kicker(S.k4, seg(t, 0, 0.4));
  headline(S.h4, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.8), a1 = at(cues, 1, 4.4);
  const kt = outCubic(seg(t, 0.3, 0.9));
  const T = [a0 + 0.2, a0 + 1.2, a0 + 2.6, a0 + 3.8, a0 + 5.0];
  const dots = n => "•".repeat(n);
  const lines = [
    { p: "$ ", s: S.auth[0], c: C.ink, a: T[0], b: T[0] + 0.9 },
    { s: S.auth[1] + dots(14), c: C.soft, a: T[1], b: T[1] + 0.8 },
    { s: S.auth[2] + dots(11), c: C.soft, a: T[2], b: T[2] + 0.7 },
    { s: S.auth[3] + dots(6), c: C.soft, a: T[3], b: T[3] + 0.6 },
    { s: S.auth[4], c: C.accent, w: 700, a: T[4], b: T[4] + 0.6 },
  ];
  terminal(80, 180, 590, 310, t, lines, { alpha: kt, size: 18, lh: 48, title: "garmin-mcp-auth" });
  pill(S.authNote, 80 + 590 - 20, 520, { align: "right", size: 13, alpha: seg(t, T[1], T[1] + 0.5), color: C.amber, fill: "rgba(240,180,60,0.08)", stroke: "rgba(240,180,60,0.4)" });
  // dossier personnel : jetons
  const k1 = outCubic(seg(t, a1 - 0.2, a1 + 0.5));
  panel(720, 180, 480, 160, { fill: "rgba(163,230,53,0.06)", stroke: C.accent, alpha: k1 });
  text(S.home, 750, 226, { size: 20, weight: 700, font: SORA, alpha: k1 });
  text("~/.garminconnect/", 750, 262, { size: 19, font: MONO, color: C.accent, alpha: k1 });
  text(S.homeFile, 750, 294, { size: 16, font: MONO, color: C.soft, alpha: k1 });
  text(S.valid, 750, 322, { size: 16, color: C.faint, alpha: k1 });
  // anneau « ~6 mois »
  const kr = seg(t, a1 + 0.4, a1 + 1.8);
  ctx.save(); ctx.globalAlpha *= k1; ctx.lineCap = "round";
  ctx.beginPath(); ctx.arc(1120, 265, 34, 0, Math.PI * 2); ctx.strokeStyle = C.line; ctx.lineWidth = 8; ctx.stroke();
  ctx.beginPath(); ctx.arc(1120, 265, 34, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * 0.97 * outCubic(kr)); ctx.strokeStyle = C.accent; ctx.lineWidth = 8; ctx.stroke();
  ctx.restore();
  text("~6", 1120, 272, { size: 20, weight: 800, font: SORA, align: "center", alpha: k1 });
  text(LANG === "fr" ? "mois" : "mo.", 1120, 292, { size: 11, font: MONO, color: C.faint, align: "center", alpha: k1 });
  // dépôt du projet : jamais
  const a2 = a1 + 3.4;
  const k2 = outCubic(seg(t, a2, a2 + 0.5));
  panel(720, 370, 480, 120, { fill: "rgba(240,122,95,0.05)", stroke: "rgba(240,122,95,0.5)", alpha: k2 });
  text(S.repo, 750, 416, { size: 20, weight: 700, font: SORA, alpha: k2 });
  text(S.never, 750, 454, { size: 18, color: C.soft, alpha: k2 });
  const kx = seg(t, a2 + 0.5, a2 + 1.0);
  line([[1130, 396], [1130 + 28 * kx, 396 + 28 * kx]], C.red, 4, k2 * kx);
  line([[1158, 396], [1158 - 28 * kx, 396 + 28 * kx]], C.red, 4, k2 * kx);
  // le fil entre le terminal et le dossier personnel
  packets(670, 325, 730, 265, t, 3, 1.2, k1 * 0.9);
}

/* ----------------------------- 05 · /coach-setup --------------------------- */
function sSetup(t, d, cues) {
  kicker(S.k5, seg(t, 0, 0.4));
  headline(S.h5, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.8), a1 = at(cues, 1, 7.6), a2 = at(cues, 2, 10);
  const kp = outCubic(seg(t, 0.3, 0.9));
  panel(80, 170, 720, 424, { fill: "#0a120e", alpha: kp, shadow: true });
  ctx.save(); ctx.globalAlpha *= kp; rr(80, 170, 720, 34, [16, 16, 0, 0]); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
  [C.red, C.amber, C.accent].forEach((c, i) => dot(100 + i * 16, 187, 5, c, kp * 0.8));
  text(S.titleChat, 440, 192, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kp });
  const T = [a0 + 0.1, a0 + 2.0, a0 + 3.8, a1 + 0.2];
  S.q.forEach((q, i) => {
    const y = 222 + i * 86, k = outCubic(seg(t, T[i], T[i] + 0.4));
    if (k <= 0) return;
    text("coach", 106, y + 12, { size: 12, font: MONO, color: C.accent, alpha: k, spacing: "1px" });
    text(typed(q, seg(t, T[i], T[i] + 0.9)), 106, y + 38, { size: 20, weight: 600, alpha: k });
    const ka = outBack(seg(t, T[i] + 1.0, T[i] + 1.5));
    if (ka > 0) pill(S.a[i], 106, y + 66, { alpha: clamp(ka), size: 16, color: C.deep, fill: C.accent, stroke: C.accent });
    if (i === 3) {
      text(S.garminVals, 190, y + 71, { size: 15, font: MONO, color: C.soft, alpha: k * seg(t, T[i] + 0.9, T[i] + 1.4) });
      text(S.garminSrc, 106, y + 96, { size: 13, font: MONO, color: C.faint, alpha: k * seg(t, T[i] + 0.9, T[i] + 1.4) });
    }
  });
  // fichiers écrits
  S.files.forEach(([f, sub], i) => {
    const a = a2 + 0.2 + i * 1.1, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    const x = 840 + (1 - k) * 40, y = 190 + i * 128;
    panel(x, y, 360, 110, { r: 14, fill: C.panel2, stroke: i === 0 ? C.line : "rgba(163,230,53,0.4)", alpha: k, shadow: true });
    text(f, x + 20, y + 42, { size: 15, weight: 600, font: MONO, color: C.accent, alpha: k });
    para(sub, x + 20, y + 72, 320, { size: 17, color: C.soft, alpha: k });
  });
  const kr = outBack(seg(t, a2 + 3.6, a2 + 4.2));
  if (kr > 0) pill(S.rerun, 1200, 590, { align: "right", alpha: clamp(kr), size: 15, color: C.soft, fill: C.panel, stroke: C.line });
}

/* ----------------------------- 06 · /coach-doctor -------------------------- */
function sDoctor(t, d, cues) {
  kicker(S.k6, seg(t, 0, 0.4));
  headline(S.h6, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.8), a1 = at(cues, 1, 6.4);
  const kp = outCubic(seg(t, 0.3, 0.9));
  const X = 80, Y = 170, Wd = 1120, Hh = 458;
  panel(X, Y, Wd, Hh, { fill: "#0a120e", alpha: kp, shadow: true });
  ctx.save(); ctx.globalAlpha *= kp; rr(X, Y, Wd, 34, [16, 16, 0, 0]); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
  [C.red, C.amber, C.accent].forEach((c, i) => dot(X + 20 + i * 16, Y + 17, 5, c, kp * 0.8));
  text("python3 scripts/coach_doctor.py", X + Wd / 2, Y + 22, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kp });
  text(typed(S.docHead, seg(t, a0, a0 + 0.8)), X + 28, Y + 70, { size: 16, weight: 700, font: MONO, alpha: kp });
  S.checks.forEach(([st, id, msg], i) => {
    const a = a0 + 0.9 + i * 0.5, k = outCubic(seg(t, a, a + 0.3));
    if (k <= 0) return;
    const y = Y + 108 + i * 34 + (1 - k) * 8;
    const col = st === "ok" ? C.accent : C.teal;
    dot(X + 40, y - 5, 11, col, k * 0.16);
    if (st === "ok") check(X + 40, y - 4, 13, col, seg(t, a + 0.1, a + 0.45), k);
    else { text("i", X + 40, y + 1, { size: 15, weight: 700, font: MONO, color: col, align: "center", alpha: k }); }
    text(id, X + 72, y, { size: 17, weight: 700, font: MONO, alpha: k, color: st === "ok" ? C.ink : C.soft });
    text(msg, X + 340, y, { size: 16, font: MONO, color: st === "ok" ? C.soft : C.faint, alpha: k });
  });
  // verdict final
  const ke = outCubic(seg(t, a1 + 0.2, a1 + 0.8));
  if (ke > 0) {
    const y = Y + 108 + 9 * 34 + 8;
    line([[X + 28, y - 18], [X + Wd - 28, y - 18]], C.line, 1, ke);
    check(X + 40, y + 4, 15, C.accent, ke, ke);
    text(S.docEnd, X + 72, y + 10, { size: 18, weight: 700, font: MONO, color: C.accent, alpha: ke });
    let px = X + Wd - 28;
    for (let i = S.docPills.length - 1; i >= 0; i--) {
      const s = S.docPills[i];
      const w = pill(s, px, y + 4, { align: "right", size: 14, alpha: ke * seg(t, a1 + 0.6 + i * 0.3, a1 + 1.1 + i * 0.3), color: C.soft, fill: C.panel, stroke: C.line });
      px -= w + 12;
    }
  }
}

/* --------------------------------- 07 · /today ----------------------------- */
function sToday(t, d, cues) {
  kicker(S.k7, seg(t, 0, 0.4));
  headline(S.h7, seg(t, 0.1, 0.7));
  const a0 = at(cues, 0, 0.8), a1 = at(cues, 1, 3.6);
  const kp = outCubic(seg(t, 0.3, 0.9));
  const X = 80, Y = 180, Wd = 1120, Hh = 340;
  panel(X, Y, Wd, Hh, { fill: "#0a120e", alpha: kp, shadow: true });
  ctx.save(); ctx.globalAlpha *= kp; rr(X, Y, Wd, 34, [16, 16, 0, 0]); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
  [C.red, C.amber, C.accent].forEach((c, i) => dot(X + 20 + i * 16, Y + 17, 5, c, kp * 0.8));
  text("Claude Code · coach", X + Wd / 2, Y + 22, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kp });
  text("> ", X + 28, Y + 80, { size: 24, font: MONO, color: C.faint, alpha: kp });
  const kq = seg(t, a0 + 0.1, a0 + 0.7);
  text(typed(S.todayQ, kq), X + 62, Y + 80, { size: 24, weight: 700, font: MONO, color: C.accent, alpha: kp });
  if (kq < 1 || t < a1) ctx.fillStyle = C.accent, ctx.fillRect(X + 62 + measure(typed(S.todayQ, kq), 24, 700, MONO) + 4, Y + 62, 12, 24 * (Math.sin(t * 8) > 0 ? 1 : 0.2));
  S.todayA.forEach((s, i) => {
    const a = a1 + 0.2 + i * 1.5, k = outCubic(seg(t, a, a + 0.45));
    if (k <= 0) return;
    const y = Y + 150 + i * 62;
    text(typed(s, seg(t, a, a + 0.9)), X + 62, y, { size: i === 0 ? 26 : 21, weight: i === 0 ? 700 : 400, font: i === 0 ? SORA : INTER, color: i === 0 ? C.amber : C.ink, alpha: k });
    pill(S.todayTags[i], X + Wd - 28, y - 6, { align: "right", size: 15, alpha: k * seg(t, a + 0.6, a + 1.0), color: C.soft, fill: C.panel, stroke: C.line });
  });
  const kr = outBack(seg(t, a1 + 5.2, a1 + 5.8));
  if (kr > 0) {
    const y = 580;
    ctx.save(); ctx.globalAlpha *= clamp(kr);
    rr(80, y - 24, 30, 24, 5); ctx.fillStyle = C.accent; ctx.fill();
    ctx.beginPath(); ctx.arc(95, y - 24, 9, Math.PI, 0); ctx.strokeStyle = C.accent; ctx.lineWidth = 3; ctx.stroke();
    ctx.restore();
    text(S.readOnly, 126, y - 4, { size: 20, weight: 600, alpha: clamp(kr) });
  }
}

ARC.episode({
  n: 1, slug: "ligne-de-depart",
  strings: STR,
  shots: [],
  scenes: { blocks: sBlocks, installer: sInstaller, options: sOptions, garmin: sGarmin, setup: sSetup, doctor: sDoctor, today: sToday },
});
})();
