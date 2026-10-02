/* Le Sentier · étape 12 — « Vos données, votre sentier » : le workspace privé, le contrat de données,
 * l'index jetable, le tableau de bord local, la source de données et la vie privée.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Chaque scène reçoit (t, d, cues) : temps local, durée, répliques [{s, e, text}].
 * Athlète et chiffres fictifs (bible de la série : Camille). Les sorties de commande montrées
 * (validation) viennent d'une vraie exécution de scripts/arc_index.py sur un workspace fictif. */
"use strict";
(() => {
/* Le manifeste des captures (shots/manifest.js) liste ses entrées dans un tableau « shots » ;
 * le moteur attend un objet indexé par nom : adaptateur idempotent. */
if (window.ARC_SHOTS && Array.isArray(window.ARC_SHOTS.shots)) {
  window.ARC_SHOTS = Object.fromEntries(window.ARC_SHOTS.shots.map(s => [s.name, s]));
}

const STR = {
  fr: {
    k1: "01 · UN DOSSIER À VOUS", h1: "Des fichiers. Chez vous.",
    engine: "moteur", engineSub: "dépôt public", engineItems: ["agents/", "skills/", "scripts/", "docs/"],
    ws: "workspace", wsSub: "votre dépôt privé",
    install: "./install.sh --workspace ~/mon-workspace",
    dirs: [["activities/", "séances", "2026-09-27_trail.md"], ["medical/", "sommeil · HRV · santé", "2026-09-29_health.md"], ["nutrition/", "apports déclarés", "2026-09-28_nutrition.md"],
           ["planning/", "plans · objectif · décisions", "Semaine_2026-09-28.md"], ["rapports/", "synthèses", "2026-09-27_rapport.md"], ["gear/", "inspections du matériel", "2026-09-24_…_inspection.md"]],
    ignored: "exclus du dépôt public (.gitignore)", versioned: "versionné dans votre dépôt privé",
    k2: "02 · LE CONTRAT DE DONNÉES", h2: "Un bloc, puis du texte.",
    file: "activities/2026-09-27_trail.md",
    md: ["# Trail du dimanche", "```arc", '{"arc": 1, "kind": "activity",', ' "date": "2026-09-27", "sport": "trail",', ' "distance_m": 18200, "duration_s": 7980,', ' "elevation_gain_m": 820, "avg_hr_bpm": 142}', "```", "", "Sortie régulière, bonnes sensations", "dans la montée."],
    co: ["clés en anglais, jamais traduites", "unités SI : mètres, secondes", "mesure absente = clé absente, jamais 0", "texte libre, dans la langue de vos documents"],
    val1: ["python3 scripts/arc_index.py --validate \\", "  activities/2026-09-27_trail.md", "ok: activities/2026-09-27_trail.md"],
    val2cap: "un bloc non conforme est refusé, avec la raison",
    val2: ['"distance_m": "18,2 km"   ← à corriger', "NON CONFORME: activities/…_trail.md", "  erreur : activity.distance_m : un nombre", "  (SI, sans unité) attendu, \"18,2 km\" trouvé"], exit1: "code de sortie 1",
    k3: "03 · L'INDEX", h3: "Jetable. Reconstructible.",
    files: "vos fichiers Markdown", truth: "source de vérité", db: ".arc/coach.db", dbSub: "SQLite · dérivé · ignoré par git",
    dash: "tableau de bord", rm: "rm -r .arc/", rebuild: "arc_index.py --rebuild", untouched: "fichiers intacts", rebuilt: "reconstruit depuis les fichiers",
    k4: "04 · EN LOCAL", h4: "Une commande. Lecture seule.",
    cmd: "scripts/dashboard.sh", uiNote: "Interface en français",
    dashPts: [["127.0.0.1", "n'écoute que sur votre machine"], ["lecture seule", "il montre ce qui est stocké"], ["rien à installer", "Python standard, ni npm ni build"], ["à jour tout seul", "un nouveau fichier : 30 s au plus"]],
    k5: "05 · VOTRE SOURCE", h5: "Garmin, ou Intervals.icu.",
    gTitle: "Garmin", gTag: "par défaut", gLines: ["garmin-mcp : activités, sommeil, HRV, readiness", "calendrier des séances, envoi des parcours"], gCfg: '[data].source = "garmin"',
    iTitle: "Intervals.icu", iTag: "--source intervals", iLines: ["pour COROS, Suunto, Polar, Apple…", "installé à la place de Garmin, pas en plus"], iCfg: '[data].source = "intervals"',
    limT: "Limites, dites telles quelles",
    lims: [["readiness", "indisponible — source intervals.icu"], ["récupération FC · splits au km", "absents, jamais inventés"], ["envoi de parcours", "analyse GPX locale seulement"]],
    k6: "06 · VIE PRIVÉE", h6: "Ce qui part. Ce qui reste.",
    mach: "Votre machine", machItems: ["workspace : vos fichiers Markdown", ".arc/ : l'index dérivé", "127.0.0.1 : le tableau de bord", "~/.garminconnect : vos jetons"],
    out1: ["Fournisseur du modèle de votre IDE", "les extraits que le modèle lit"], out2: ["Garmin Connect ou Intervals.icu", "synchronisation de vos séances"], out3: ["wttr.in", "prévisions : le nom du lieu"],
    pub: "dépôt public : aucune donnée personnelle",
    k7: "07 · RATTRAPAGE", h7: "Vos fichiers d'avant.",
    before: "avant", after: "après", oldMd: ["# Séance du 12 mai", "", "| Distance | 12,4 km |", "| Durée | 1 h 12 |"],
    newMd: ["# Séance du 12 mai", "```arc", '{"arc": 1, "kind": "activity", "date": "2026-05-12",', ' "sport": "trail", "distance_m": 12400,', ' "duration_s": 4320}', "```", "| Distance | 12,4 km |", "| Durée | 1 h 12 |"],
    outOf: "hors contrat", inOf: "au contrat", plan: "arc_index.py backfill-plan",
    bf: ["dix fichiers par passe, les plus récents d'abord", "tout le texte conservé", "aucune valeur inventée", "committez avant : relisez chaque changement"],
  },
  en: {
    k1: "01 · A FOLDER OF YOUR OWN", h1: "Files. On your machine.",
    engine: "engine", engineSub: "public repository", engineItems: ["agents/", "skills/", "scripts/", "docs/"],
    ws: "workspace", wsSub: "your private repository",
    install: "./install.sh --workspace ~/my-workspace",
    dirs: [["activities/", "sessions", "2026-09-27_trail.md"], ["medical/", "sleep · HRV · health", "2026-09-29_health.md"], ["nutrition/", "reported intake", "2026-09-28_nutrition.md"],
           ["planning/", "plans · goal · decisions", "Semaine_2026-09-28.md"], ["rapports/", "reports", "2026-09-27_rapport.md"], ["gear/", "gear inspections", "2026-09-24_…_inspection.md"]],
    ignored: "excluded from the public repo (.gitignore)", versioned: "versioned in your private repository",
    k2: "02 · THE DATA CONTRACT", h2: "A block, then prose.",
    file: "activities/2026-09-27_trail.md",
    md: ["# Sunday trail", "```arc", '{"arc": 1, "kind": "activity",', ' "date": "2026-09-27", "sport": "trail",', ' "distance_m": 18200, "duration_s": 7980,', ' "elevation_gain_m": 820, "avg_hr_bpm": 142}', "```", "", "Steady run, good feel on the climb.", ""],
    co: ["English keys, never translated", "SI units: metres, seconds", "missing measure = missing key, never 0", "free text, in your documents' language"],
    val1: ["python3 scripts/arc_index.py --validate \\", "  activities/2026-09-27_trail.md", "ok: activities/2026-09-27_trail.md"],
    val2cap: "a non-conforming block is refused, with the reason",
    val2: ['"distance_m": "18,2 km"   ← to fix', "NON CONFORME: activities/…_trail.md", "  erreur : activity.distance_m : un nombre", "  (SI, sans unité) attendu, \"18,2 km\" trouvé"], exit1: "exit code 1 (message in French)",
    k3: "03 · THE INDEX", h3: "Disposable. Rebuildable.",
    files: "your Markdown files", truth: "source of truth", db: ".arc/coach.db", dbSub: "SQLite · derived · ignored by git",
    dash: "dashboard", rm: "rm -r .arc/", rebuild: "arc_index.py --rebuild", untouched: "files untouched", rebuilt: "rebuilt from the files",
    k4: "04 · LOCAL", h4: "One command. Read-only.",
    cmd: "scripts/dashboard.sh", uiNote: "UI in French",
    dashPts: [["127.0.0.1", "listens on this machine only"], ["read-only", "it shows what is stored"], ["nothing to install", "standard Python, no npm, no build"], ["updates itself", "a new file shows up within 30 s"]],
    k5: "05 · YOUR SOURCE", h5: "Garmin, or Intervals.icu.",
    gTitle: "Garmin", gTag: "default", gLines: ["garmin-mcp: activities, sleep, HRV, readiness", "workout calendar, course upload"], gCfg: '[data].source = "garmin"',
    iTitle: "Intervals.icu", iTag: "--source intervals", iLines: ["for COROS, Suunto, Polar, Apple…", "installed instead of Garmin, not in addition"], iCfg: '[data].source = "intervals"',
    limT: "Limits, stated as they are",
    lims: [["readiness", "unavailable — Intervals.icu source"], ["recovery HR · per-km splits", "absent, never invented"], ["course upload", "local GPX analysis only"]],
    k6: "06 · PRIVACY", h6: "What leaves. What stays.",
    mach: "Your machine", machItems: ["workspace: your Markdown files", ".arc/: the derived index", "127.0.0.1: the dashboard", "~/.garminconnect: your tokens"],
    out1: ["Your IDE's model provider", "the excerpts the model reads"], out2: ["Garmin Connect or Intervals.icu", "syncing your sessions"], out3: ["wttr.in", "forecasts: the place name"],
    pub: "public repository: no personal data",
    k7: "07 · CATCH-UP", h7: "Your older files.",
    before: "before", after: "after", oldMd: ["# Session of May 12", "", "| Distance | 12.4 km |", "| Duration | 1 h 12 |"],
    newMd: ["# Session of May 12", "```arc", '{"arc": 1, "kind": "activity", "date": "2026-05-12",', ' "sport": "trail", "distance_m": 12400,', ' "duration_s": 4320}', "```", "| Distance | 12.4 km |", "| Duration | 1 h 12 |"],
    outOf: "off contract", inOf: "on contract", plan: "arc_index.py backfill-plan",
    bf: ["ten files per pass, most recent first", "all existing text kept", "no value invented", "commit first: review every change"],
  },
};

const mdColor = s => /^#/.test(s) ? C.ink : /^```/.test(s) ? C.faint : /^[{ ]/.test(s) ? C.accent : /^\|/.test(s) ? C.soft : C.soft;
const rowY = (top, i, lh = 30) => top + 62 + i * lh;

/* --------------------------- 1. le dossier, le dépôt ----------------------- */
function folderIcon(x, y, w, h, col, k) {
  ctx.save(); ctx.globalAlpha *= k;
  rr(x, y + 8, w, h - 8, 7); ctx.fillStyle = col; ctx.fill();
  rr(x, y, w * 0.4, 14, [6, 6, 0, 0]); ctx.fillStyle = col; ctx.fill();
  ctx.restore();
}
function sFolders(t, d, cues) {
  kicker(S.k1, seg(t, 0, 0.4));
  headline(S.h1, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 4.5);
  // moteur (public)
  const ke = outCubic(seg(t, 0.3, 0.9));
  panel(60, 190, 250, 330, { r: 18, fill: C.panel, alpha: ke });
  text(S.engine, 84, 232, { size: 22, weight: 800, font: SORA, alpha: ke });
  text(S.engineSub, 84, 256, { size: 13, font: MONO, color: C.faint, alpha: ke });
  S.engineItems.forEach((s, i) => {
    folderIcon(86, 292 + i * 52, 30, 24, "#2a3d33", ke);
    text(s, 130, 311 + i * 52, { size: 17, font: MONO, color: C.soft, alpha: ke });
  });
  // lien --workspace
  const kl = seg(t, a0 + 5.2, a0 + 6.2);
  arrow(316, 355, 398, 355, kl, C.accent);
  // workspace (privé)
  const kw = outCubic(seg(t, 0.6, 1.2));
  const wx = 410, wy = 190, ww = 800, wh = 330;
  panel(wx, wy, ww, wh, { r: 18, fill: "rgba(30,77,59,0.22)", stroke: "rgba(163,230,53,0.45)", alpha: kw, lw: 1.5 });
  text(S.ws, wx + 28, wy + 42, { size: 22, weight: 800, font: SORA, alpha: kw });
  text(S.wsSub, wx + 28, wy + 66, { size: 13, font: MONO, color: C.accent, alpha: kw });
  S.dirs.forEach(([name, what, ex], i) => {
    const col = i % 2, row = (i / 2) | 0;
    const x = wx + 28 + col * 380, y = wy + 90 + row * 74;
    const a = a0 + 0.6 + i * 0.7, k = outCubic(seg(t, a, a + 0.5));
    if (k <= 0) return;
    panel(x, y + (1 - k) * 10, 360, 62, { r: 12, fill: C.panel, alpha: k });
    folderIcon(x + 16, y + 17, 28, 24, C.accent, k);
    text(name, x + 58, y + 28 + (1 - k) * 10, { size: 17, weight: 700, font: MONO, alpha: k });
    text(what, x + 58, y + 50 + (1 - k) * 10, { size: 13, color: C.soft, alpha: k });
    text(ex, x + 348, y + 28 + (1 - k) * 10, { size: 10, font: MONO, color: C.faint, align: "right", alpha: k });
  });
  // commande d'installation
  const kc = outCubic(seg(t, a0 + 5.0, a0 + 5.6));
  text(S.install, wx + 28, wy + wh + 34, { size: 15, font: MONO, color: C.soft, alpha: kc });
  // exclusions et versionnement
  const kx = outBack(seg(t, a1, a1 + 0.5));
  if (kx > 0) {
    pill(S.ignored, 60, 612, { alpha: clamp(kx), size: 13, color: C.amber, fill: "rgba(240,180,60,0.1)", stroke: "rgba(240,180,60,0.5)" });
  }
  const kv = outBack(seg(t, a1 + 1.4, a1 + 1.9));
  if (kv > 0) {
    pill(S.versioned, wx + ww, 612, { align: "right", alpha: clamp(kv), size: 13 });
    for (let i = 0; i < 6; i++) { dot(wx + ww - 420 + i * 22, 612, 4, C.accent, clamp(kv) * 0.8); if (i) line([[wx + ww - 420 + (i - 1) * 22 + 4, 612], [wx + ww - 420 + i * 22 - 4, 612]], C.accent, 1.5, clamp(kv) * 0.6); }
  }
}

/* ---------------------------- 2. le bloc et sa validation ------------------ */
function sBlock(t, d, cues) {
  kicker(S.k2, seg(t, 0, 0.4));
  headline(S.h2, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 6), a2 = at(cues, 2, 8);
  const fx = 60, fy = 170, fw = 640, fh = 400;
  const k1 = outCubic(seg(t, 0.3, 0.9));
  const lines = S.md.map((s, i) => ({ s, c: mdColor(s), w: i === 0 ? 700 : 400, a: 0.9 + i * 0.3, b: 1.15 + i * 0.3 }));
  terminal(fx, fy, fw, fh, t, lines, { alpha: k1, size: 14, lh: 30, title: S.file });
  const px = fx + 22;
  const endX = i => px + measure(S.md[i], 14, 400, MONO) + 10;
  // le bloc s'illumine pendant la 1re réplique, le texte libre pendant la 2e
  const kb = seg(t, a0 + 0.6, a0 + 1.2) * (1 - seg(t, a1, a1 + 0.5));
  if (kb > 0) { ctx.save(); ctx.globalAlpha *= kb * 0.10; rr(fx + 12, rowY(fy, 2) - 22, fw - 24, 4 * 30 + 6, 8); ctx.fillStyle = C.accent; ctx.fill(); ctx.restore(); }
  const kf = seg(t, a1, a1 + 0.6) * (1 - seg(t, a2, a2 + 0.5));
  if (kf > 0) { ctx.save(); ctx.globalAlpha *= kf * 0.10; rr(fx + 12, rowY(fy, 8) - 22, fw - 24, 2 * 30 + 4, 8); ctx.fillStyle = C.teal; ctx.fill(); ctx.restore(); }
  // les annotations (pendant la 1re réplique), puis la validation
  const gone = 1 - seg(t, a2 - 0.2, a2 + 0.3);
  const targets = [[3, 3], [4, 4], [5, 5], [8, 8]];
  const tAt = [a0 + 1.2, a0 + 3.8, a0 + 6.4, a1 + 0.4];
  S.co.forEach((s, i) => {
    const k = seg(t, tAt[i], tAt[i] + 0.6) * gone;
    if (k <= 0) return;
    const [row] = targets[i], ty = rowY(fy, row) - 5;
    const y = [200, 262, 324, 386][i];
    callout(s, 730, y, endX(row), ty, k, { align: "left", size: 13, color: i === 3 ? C.teal : C.accent });
  });
  // validation
  const kv = outCubic(seg(t, a2, a2 + 0.5));
  if (kv > 0) {
    const l1 = [{ p: "$ ", s: S.val1[0], c: C.ink, a: a2 + 0.2, b: a2 + 0.9 }, { s: S.val1[1], c: C.ink, a: a2 + 0.9, b: a2 + 1.5 }, { s: S.val1[2], c: C.accent, a: a2 + 1.8, b: a2 + 2.3 }];
    terminal(730, 176, 490, 158, t, l1, { alpha: kv, size: 13, lh: 28 });
    const k2 = seg(t, a2 + 3.2, a2 + 3.8);
    if (k2 > 0) {
      text(S.val2cap, 730, 364, { size: 13, color: C.soft, alpha: k2 });
      const l2 = [{ s: S.val2[0], c: C.amber, a: a2 + 3.4, b: a2 + 4.0 }, { s: S.val2[1], c: C.red, a: a2 + 4.0, b: a2 + 4.5 }, { s: S.val2[2], c: C.soft, a: a2 + 4.5, b: a2 + 5.0 }, { s: S.val2[3], c: C.soft, a: a2 + 5.0, b: a2 + 5.5 }];
      terminal(730, 378, 490, 168, t, l2, { alpha: k2, size: 13, lh: 28 });
      text(S.exit1, 1208, 572, { size: 12, font: MONO, color: C.faint, align: "right", alpha: seg(t, a2 + 5.4, a2 + 5.9) });
    }
  }
}

/* --------------------------------- 3. l'index ------------------------------ */
function cylinder(cx, cy, w, h, col, alpha, o = {}) {
  ctx.save(); ctx.globalAlpha *= alpha;
  const ry = 16;
  rr(cx - w / 2, cy - h / 2 + ry, w, h - ry, 0); ctx.fillStyle = o.fill ?? C.panel2; ctx.fill();
  ctx.beginPath(); ctx.ellipse(cx, cy + h / 2, w / 2, ry, 0, 0, Math.PI); ctx.fillStyle = o.fill ?? C.panel2; ctx.fill();
  ctx.beginPath(); ctx.moveTo(cx - w / 2, cy - h / 2 + ry); ctx.lineTo(cx - w / 2, cy + h / 2); ctx.moveTo(cx + w / 2, cy - h / 2 + ry); ctx.lineTo(cx + w / 2, cy + h / 2);
  ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.stroke();
  ctx.beginPath(); ctx.ellipse(cx, cy + h / 2, w / 2, ry, 0, 0, Math.PI); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(cx, cy - h / 2 + ry, w / 2, ry, 0, 0, Math.PI * 2); ctx.fillStyle = o.top ?? C.panel; ctx.fill(); ctx.stroke();
  ctx.restore();
}
function sIndex(t, d, cues) {
  kicker(S.k3, seg(t, 0, 0.4));
  headline(S.h3, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 3.5);
  const cy = 330, fx = 80, dx = 640, wx = 920;
  // fichiers
  const kf = outCubic(seg(t, 0.3, 0.9));
  for (let i = 0; i < 4; i++) {
    const y = 210 + i * 58, k = outCubic(seg(t, 0.4 + i * 0.12, 0.9 + i * 0.12));
    panel(fx, y + (1 - k) * 10, 250, 46, { r: 10, fill: C.panel, alpha: k, stroke: seg(t, a1 + 3, a1 + 4) > 0 ? "rgba(163,230,53,0.4)" : C.line });
    text(["activities/…md", "medical/…md", "planning/…md", "rapports/…md"][i], fx + 18, y + 29 + (1 - k) * 10, { size: 14, font: MONO, color: C.soft, alpha: k });
  }
  text(S.files, fx, 470, { size: 13, font: MONO, color: C.faint, alpha: kf });
  pill(S.truth, fx, 508, { alpha: seg(t, a0 + 3.0, a0 + 3.6) + 0, size: 13 });
  // base dérivée
  const kd = outCubic(seg(t, a0 + 0.8, a0 + 1.5));
  const gone = seg(t, a1 + 0.6, a1 + 1.6), back = seg(t, a1 + 4.0, a1 + 5.0);
  const shown = gone < 1 ? kd * (1 - gone) : kd * back;
  if (gone > 0 && gone < 1) {
    // la base éclate en poussière
    const R = rng(7);
    for (let i = 0; i < 40; i++) { const ang = R() * Math.PI * 2, sp = 40 + R() * 120; dot(dx + Math.cos(ang) * sp * gone, cy + Math.sin(ang) * sp * gone * 0.8, 3 * (1 - gone), C.red, (1 - gone) * 0.9); }
  }
  if (shown > 0) cylinder(dx, cy, 170, 130, back > 0 ? C.accent : C.soft, shown);
  text(S.db, dx, cy + 110, { size: 17, weight: 700, font: MONO, align: "center", alpha: kd });
  text(S.dbSub, dx, cy + 134, { size: 12, font: MONO, color: C.faint, align: "center", alpha: kd });
  // flux fichiers -> base
  const kfl = seg(t, a0 + 0.6, a0 + 1.4);
  arrow(340, cy, 540, cy, kfl, C.faint);
  if (kfl >= 1 && (gone === 0 || back > 0)) packets(340, cy, 540, cy, t, 3, 1.4, 0.9);
  // base -> tableau de bord
  const kw = outCubic(seg(t, a0 + 1.6, a0 + 2.2));
  arrow(740, cy, 910, cy, seg(t, a0 + 1.6, a0 + 2.2), C.faint);
  panel(wx, cy - 70, 270, 150, { r: 16, fill: C.panel, alpha: kw });
  for (let i = 0; i < 3; i++) { line([[wx + 24, cy - 28 + i * 34], [wx + 24 + [200, 150, 180][i] * kw, cy - 28 + i * 34]], i === 0 ? C.accent : C.line, 6, kw * 0.8); }
  text(S.dash, wx + 135, cy + 110, { size: 15, color: C.soft, align: "center", alpha: kw });
  // suppression puis reconstruction
  const kr = seg(t, a1 + 0.2, a1 + 0.7);
  if (kr > 0 && back < 1) pill(S.rm, dx, 210, { align: "center", alpha: kr * (1 - seg(t, a1 + 1.8, a1 + 2.2)), size: 14, color: C.red, fill: "rgba(240,122,95,0.1)", stroke: "rgba(240,122,95,0.5)" });
  const kb = seg(t, a1 + 2.6, a1 + 3.2);
  if (kb > 0) pill(S.rebuild, dx, 210, { align: "center", alpha: kb, size: 14 });
  if (back > 0 && back < 1.0) { ctx.save(); ctx.globalAlpha *= 0.6; packets(340, cy, 540, cy, t, 4, 0.8, 1); ctx.restore(); }
  const ku = seg(t, a1 + 3.2, a1 + 4.0);
  text(S.untouched, fx + 250, 540, { size: 13, font: MONO, color: C.accent, align: "right", alpha: ku });
  text(S.rebuilt, dx, 530, { size: 14, color: C.accent, align: "center", alpha: seg(t, a1 + 4.8, a1 + 5.4) });
}

/* ------------------------------ 4. le tableau de bord ---------------------- */
function sDashboard(t, d, cues) {
  kicker(S.k4, seg(t, 0, 0.4));
  headline(S.h4, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5);
  const x = 60, y = 176, w = 740, h = 420;
  const ks = outCubic(seg(t, 0.4, 1.1));
  const sw = inOut(seg(t, a0 + 4.0, a0 + 4.8));
  const crop = n => { const m = shotMeta(n); return m ? [0, 0, m.width, Math.min(m.height, m.width * (h - 30) / w)] : undefined; };
  shot("aujourdhui", x + (1 - ks) * -50, y, w, h, { alpha: ks * (1 - sw), crop: crop("aujourdhui") });
  if (sw > 0) shot("forme", x, y, w, h, { alpha: sw, crop: crop("forme") });
  text(S.uiNote, x + w, y + h + 24, { size: 12, font: MONO, color: C.faint, align: "right", alpha: ks });
  // commande
  const kc = outCubic(seg(t, a0 + 0.6, a0 + 1.2));
  terminal(840, 176, 370, 104, t, [{ p: "$ ", s: S.cmd, c: C.accent, w: 700, a: a0 + 0.8, b: a0 + 1.6 }], { alpha: kc, size: 16, lh: 30 });
  // propriétés
  S.dashPts.forEach(([a, b], i) => {
    const at0 = a0 + 2.0 + i * 0.9, k = outCubic(seg(t, at0, at0 + 0.5));
    if (k <= 0) return;
    const yy = 304 + i * 76 + (1 - k) * 12;
    panel(840, yy, 370, 66, { r: 14, fill: C.panel, alpha: k });
    check(866, yy + 34, 14, C.accent, seg(t, at0 + 0.2, at0 + 0.7), k);
    text(a, 892, yy + 30, { size: 18, weight: 700, font: i === 0 ? MONO : SORA, alpha: k });
    text(b, 892, yy + 52, { size: 13, color: C.soft, alpha: k });
  });
}

/* ------------------------------ 5. votre source ----------------------------- */
function sSource(t, d, cues) {
  kicker(S.k5, seg(t, 0, 0.4));
  headline(S.h5, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 5);
  const sel = inOut(seg(t, a1 - 0.6, a1 + 0.2)); // 0 = Garmin, 1 = Intervals
  const cw = 560, ch = 215, y = 176;
  [[80, S.gTitle, S.gTag, S.gLines, S.gCfg, C.accent, 0], [640, S.iTitle, S.iTag, S.iLines, S.iCfg, C.teal, 1]].forEach(([x, title, tag, lines, cfg, col, i]) => {
    const k = outCubic(seg(t, 0.3 + i * 0.3, 0.9 + i * 0.3));
    const on = i === 0 ? 1 - sel : sel;
    panel(x, y + (1 - k) * 14, cw, ch, { r: 18, fill: on > 0.5 ? "rgba(163,230,53,0.06)" : C.panel, stroke: on > 0.5 ? col : C.line, alpha: k, lw: on > 0.5 ? 2 : 1, shadow: on > 0.5 });
    ring(x + 34, y + 44 + (1 - k) * 14, 12, on > 0.5 ? col : C.faint, 2, k);
    if (on > 0.5) dot(x + 34, y + 44 + (1 - k) * 14, 6, col, k);
    text(title, x + 62, y + 52 + (1 - k) * 14, { size: 26, weight: 800, font: SORA, alpha: k });
    pill(tag, x + cw - 24, y + 44 + (1 - k) * 14, { align: "right", alpha: k, size: 12, color: col, stroke: col, fill: "rgba(13,20,16,0.6)" });
    lines.forEach((s, j) => text(s, x + 34, y + 100 + j * 30 + (1 - k) * 14, { size: 16, color: C.soft, alpha: k }));
    text(cfg, x + 34, y + 180 + (1 - k) * 14, { size: 15, font: MONO, color: col, alpha: k });
  });
  // limites honnêtes
  const kl = outCubic(seg(t, a1 + 0.3, a1 + 0.9));
  text(S.limT.toUpperCase(), 80, 446, { size: 13, weight: 700, font: MONO, color: C.amber, alpha: kl, spacing: "2px" });
  S.lims.forEach(([a, b], i) => {
    const at0 = a1 + 0.6 + i * 0.8, k = outCubic(seg(t, at0, at0 + 0.5));
    if (k <= 0) return;
    const yy = 466 + i * 52;
    panel(80, yy + (1 - k) * 8, 1120, 42, { r: 12, fill: "rgba(240,180,60,0.06)", stroke: "rgba(240,180,60,0.3)", alpha: k });
    text("∅", 104, yy + 29 + (1 - k) * 8, { size: 20, font: MONO, color: C.amber, alpha: k });
    text(a, 140, yy + 28 + (1 - k) * 8, { size: 17, weight: 700, font: MONO, alpha: k });
    text(b, 1180, yy + 28 + (1 - k) * 8, { size: 16, color: C.soft, align: "right", alpha: k });
  });
}

/* ------------------------------- 6. vie privée ------------------------------ */
function sPrivacy(t, d, cues) {
  kicker(S.k6, seg(t, 0, 0.4));
  headline(S.h6, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 5);
  // votre machine
  const km = outCubic(seg(t, 0.3, 0.9));
  const mx = 60, my = 180, mw = 500, mh = 400;
  panel(mx, my, mw, mh, { r: 22, fill: "rgba(30,77,59,0.22)", stroke: "rgba(163,230,53,0.45)", alpha: km, lw: 1.5 });
  text(S.mach, mx + 28, my + 46, { size: 24, weight: 800, font: SORA, alpha: km });
  S.machItems.forEach((s, i) => {
    const k = outCubic(seg(t, a0 + 0.6 + i * 0.7, a0 + 1.1 + i * 0.7));
    if (k <= 0) return;
    const yy = my + 78 + i * 56;
    panel(mx + 24, yy + (1 - k) * 10, mw - 48, 44, { r: 12, fill: C.panel, alpha: k });
    check(mx + 50, yy + 24 + (1 - k) * 10, 12, C.accent, 1, k);
    text(s, mx + 76, yy + 28 + (1 - k) * 10, { size: 16, font: MONO, color: C.ink, alpha: k });
  });
  const kp = seg(t, a0 + 4.0, a0 + 4.6);
  line([[mx + 28, my + mh - 56], [mx + mw - 28, my + mh - 56]], C.line, 1, kp);
  text(S.pub, mx + 28, my + mh - 24, { size: 14, color: C.soft, alpha: kp });
  // ce qui sort
  const outs = [[S.out1, C.amber, a1 + 0.3], [S.out2, C.soft, a1 + 2.2], [S.out3, C.soft, a1 + 3.2]];
  outs.forEach(([[title, sub], col, a], i) => {
    const k = outCubic(seg(t, a, a + 0.6));
    const oy = 180 + i * 140, ox = 760, ow = 450, oh = 118;
    const ay = my + 78 + [0.4, 1.2, 2.2][i] * 56;
    if (k > 0) {
      arrow(mx + mw, ay, ox - 6, oy + oh / 2, k, col);
      if (k >= 1) packets(mx + mw, ay, ox - 6, oy + oh / 2, t, 3, 1.5, 0.9);
      panel(ox, oy + (1 - k) * 12, ow, oh, { r: 16, fill: i === 0 ? "rgba(240,180,60,0.08)" : C.panel, stroke: i === 0 ? C.amber : C.line, alpha: k, lw: i === 0 ? 2 : 1 });
      text(title, ox + 24, oy + 48 + (1 - k) * 12, { size: i === 0 ? 20 : 19, weight: 800, font: SORA, alpha: k });
      text(sub, ox + 24, oy + 80 + (1 - k) * 12, { size: 15, color: i === 0 ? C.amber : C.soft, alpha: k });
    }
  });
}

/* ------------------------------- 7. rattrapage ------------------------------ */
function sBackfill(t, d, cues) {
  kicker(S.k7, seg(t, 0, 0.4));
  headline(S.h7, seg(t, 0.1, 0.7));
  fictTag(seg(t, 0.3, 0.8));
  const a0 = at(cues, 0, 0.5);
  const k1 = outCubic(seg(t, 0.3, 0.9));
  const cmdK = outCubic(seg(t, a0 + 0.2, a0 + 0.8));
  text("$ " + S.plan, 80, 190, { size: 16, font: MONO, color: C.accent, alpha: cmdK });
  // avant
  const l1 = S.oldMd.map((s, i) => ({ s, c: mdColor(s), w: i === 0 ? 700 : 400, a: 0.6 + i * 0.3, b: 0.85 + i * 0.3 }));
  terminal(80, 214, 520, 250, t, l1, { alpha: k1, size: 14, lh: 30, title: S.before });
  const ko = outCubic(seg(t, 1.8, 2.4));
  pill(S.outOf, 580, 446, { align: "right", alpha: ko * (1 - seg(t, a0 + 3.6, a0 + 4.2)), size: 12, color: C.amber, fill: "rgba(240,180,60,0.1)", stroke: C.amber });
  // après
  const ka = outCubic(seg(t, a0 + 1.4, a0 + 2.0));
  const l2 = S.newMd.map((s, i) => ({ s, c: mdColor(s), w: i === 0 ? 700 : 400, a: a0 + 1.8 + i * 0.35, b: a0 + 2.1 + i * 0.35 }));
  arrow(606, 330, 664, 330, seg(t, a0 + 1.2, a0 + 1.9), C.accent);
  terminal(670, 214, 530, 250, t, l2, { alpha: ka, size: 13, lh: 29, title: S.after });
  const kb = seg(t, a0 + 2.4, a0 + 3.2) * (1 - seg(t, a0 + 5.2, a0 + 5.8));
  if (kb > 0) { ctx.save(); ctx.globalAlpha *= kb * 0.12; rr(682, 214 + 62 - 22 + 29, 506, 29 * 5 + 6, 8); ctx.fillStyle = C.accent; ctx.fill(); ctx.restore(); }
  pill(S.inOf, 1180, 446, { align: "right", alpha: seg(t, a0 + 4.6, a0 + 5.2), size: 12 });
  // règles
  S.bf.forEach((s, i) => {
    const at0 = a0 + 3.0 + i * 0.7, k = outCubic(seg(t, at0, at0 + 0.5));
    if (k <= 0) return;
    const x = 80 + (i % 2) * 560, y = 500 + ((i / 2) | 0) * 52;
    check(x + 12, y + 8, 12, C.accent, k, k);
    text(s, x + 36, y + 14, { size: 17, weight: 600, alpha: k });
  });
}

ARC.episode({
  n: 12, slug: "donnees",
  strings: STR,
  shots: ["aujourdhui", "forme"],
  scenes: { folders: sFolders, block: sBlock, index: sIndex, dashboard: sDashboard, source: sSource, privacy: sPrivacy, backfill: sBackfill },
});
})();
