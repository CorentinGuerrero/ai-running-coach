/* Le Sentier · étape 11 — « Trois voix, une décision » : les styles de coaching.
 * Moteur : ../engine/engine.js (helpers globaux). Découpage et narration : script.json.
 * Le catalogue réel est config/coaching-styles.md (styles, intensités, verbosités, règle 7).
 * Fil rouge visuel : un bandeau « le fond » (la décision) qui ne bouge JAMAIS d'un pixel,
 * pendant que le texte autour change de ton, de fermeté et de longueur.
 * Athlète et chiffres fictifs (bible de la série : Camille, mardi 29 septembre 2026). */
"use strict";
(() => {
/* Une couleur par voix (ids réels du catalogue). Le verdict reste ambre, comme à l'étape 2. */
const VC = { bienveillant: "#5fb8a0", exigeant: "#f07a5f", factuel: "#7fb2f0", pedagogue: "#b79cf0" };

const STR = {
  fr: {
    day: "Mardi 29 septembre · J-54",
    core: { tag: "LE FOND · IDENTIQUE QUEL QUE SOIT LE STYLE", from: "Seuil 5 × 6 min", to: "EF 45 min · 18 h-19 h", verdict: "Alléger",
            nums: "HRV 38 ms · FC de repos 52 bpm (+6) · readiness 34/100", file: "planning/2026-09-29_decision_bilan-matinal.md" },
    lbl: ["les mesures", "le verdict", "le fichier"],
    k2: "01 · UNE DÉCISION", h2: "Même verdict. Quatre façons de le dire.",
    styles: [
      { id: "bienveillant", name: "Encourageant", dir: "Chaleureux. Valorise la régularité avant la performance. Explique le pourquoi." },
      { id: "exigeant", name: "Challengeant", dir: "Direct. Tient l'athlète à ses engagements. Ne console pas, ne dramatise pas." },
      { id: "factuel", name: "Sobre", dir: "Verdict d'abord, chiffres ensuite, rien d'autre. Le tableau plutôt que le paragraphe." },
      { id: "pedagogue", name: "Pédagogue", dir: "Développe la physiologie derrière chaque décision. Vise votre autonomie." },
    ],
    k3: "02 · TROIS VOIX",
    msg: [
      "Bonjour Camille. Trois nuits sous ta bande de HRV : ton corps te demande un peu de répit. Ce soir, 45 minutes d'endurance fondamentale, à l'aise, entre 18 h et 19 h. On remplace le seuil pour protéger ta régularité : elle se construit aussi en levant le pied.",
      "Camille. Le seuil de ce soir est remplacé : 45 minutes d'EF, 18 h-19 h, rien de plus. HRV à 38 ms, trois nuits sous la bande : ce n'est pas du bruit de capteur. La vraie question : qu'est-ce qui mange tes nuits cette semaine, travail, écrans, un verre le soir ? Règle ça avant la prochaine séance de qualité.",
    ],
    tab: ["Verdict : alléger", [["Séance", "Seuil 5×6' → EF 45'"], ["HRV", "38 ms · bande 52-70"], ["FC de repos", "52 bpm · +6"], ["Readiness", "34/100"], ["Créneau", "18-19 h · 19 °C"]]],
    foot: ["chaleureux · explique le pourquoi", "direct · pose la question qui dérange", "verdict d'abord · le tableau"],
    same: "même verdict · mêmes chiffres · même fichier",
    k4: "03 · FERMETÉ ET LONGUEUR",
    toml: ["[coaching]", "style", "intensity", "verbosity"],
    int: [["gentle", "Propose, n'impose pas. Toujours un repli."], ["balanced", "Recommande clairement, accepte la contradiction argumentée."], ["strong", "Tranche : « annulée », pas « tu pourrais envisager »."]],
    ver: [["brief", "3 à 5 lignes, verdict en premier."], ["standard", "Un paragraphe + les métriques clés."], ["detailed", "Analyse segment par segment."]],
    intMsg: [
      "Camille, je te propose de remplacer le seuil de ce soir par 45 minutes d'endurance fondamentale, entre 18 h et 19 h. Si tu préfères, repos complet : mais surtout pas plus dur.",
      "Camille, je recommande de remplacer le seuil de ce soir par 45 minutes d'endurance fondamentale, entre 18 h et 19 h. Dis-moi si un élément m'échappe : je t'écoute.",
      "Camille : seuil annulé. 45 minutes d'endurance fondamentale ce soir, entre 18 h et 19 h. Je ne rouvre pas ce point sans élément nouveau.",
    ],
    verMsg: [
      ["Verdict : alléger.", "Seuil 5×6' → EF 45', 18 h-19 h.", "HRV 38 ms · FC repos 52 bpm · readiness 34/100."],
      ["Trois nuits sous ta bande de HRV (38 ms, bande 52-70) et une FC de repos de 52 bpm, six battements au-dessus de ta médiane : on remplace le seuil par 45 minutes d'endurance fondamentale ce soir, entre 18 h et 19 h, 19 °C."],
      ["Signaux : HRV 38 ms, sous la bande 52-70 depuis 3 nuits ; FC de repos 52 bpm, +6 sur la médiane à 7 jours (46) ; readiness 34/100.",
       "Lecture : trois nuits d'affilée, ce n'est pas une nuit isolée : on ne l'attribue pas au hasard.",
       "Séance : EF 45 min en zone 2, le seuil 5 × 6 min est remplacé.",
       "Créneau : 18 h-19 h, 19 °C, vent 10 km/h."],
    ],
    k5: "04 · VOTRE PROFIL PRIME", h5: "Ce qu'un identifiant ne dit pas.",
    pfile: "planning/Runner_Profile.md",
    prof: ["## Préférences de coaching", "- **Ce qui me motive** : ma régularité sur la semaine", "- **Ce qui ne marche pas avec moi** : les bravos de façade", "- **Sujets à ne pas commenter spontanément** : mon poids", "- **Tolérance au risque** : prudent", "- **Quand me poser une question plutôt que supposer** :"],
    prec: ["Instruction du moment", "Exigence de la tâche", "Préférence du profil", "Ce catalogue"],
    precTag: "précédence · règle 5",
    before: "Catalogue : « Ton corps te demande du répit. Bravo, quelle belle constance ! »",
    after: "Profil appliqué : « Ton corps te demande du répit. Ta régularité de la semaine reste intacte : on remplace, on ne saute pas. »",
    k6: "05 · RÈGLE 7", h6: "Le ton change. Jamais le fond.",
    rule: "config/coaching-styles.md · règle 7",
    waves: ["bienveillant", "exigeant", "factuel"], wl: "le ton · varie", vl: "le verdict · fixe",
  },
  en: {
    day: "Tuesday, September 29 · D-54",
    core: { tag: "THE SUBSTANCE · THE SAME WHATEVER THE STYLE", from: "Threshold 5 × 6 min", to: "Easy 45 min · 6-7 pm", verdict: "Ease off",
            nums: "HRV 38 ms · resting HR 52 bpm (+6) · readiness 34/100", file: "planning/2026-09-29_decision_bilan-matinal.md" },
    lbl: ["the measurements", "the verdict", "the file"],
    k2: "01 · ONE DECISION", h2: "Same verdict. Four ways to say it.",
    styles: [
      { id: "bienveillant", name: "Encouraging", dir: "Warm. Values consistency before performance. Explains the why." },
      { id: "exigeant", name: "Challenging", dir: "Direct. Holds you to your commitments. Doesn't console, doesn't dramatise." },
      { id: "factuel", name: "Sober", dir: "Verdict first, figures next, nothing else. A table rather than a paragraph." },
      { id: "pedagogue", name: "Pedagogue", dir: "Spells out the physiology behind each decision. Aims at your autonomy." },
    ],
    k3: "02 · THREE VOICES",
    msg: [
      "Morning, Camille. Three nights below your HRV band: your body is asking for a little breathing room. Tonight, 45 minutes of easy running, relaxed, between 6 and 7 pm. We swap the threshold to protect your consistency, which is also built by knowing when to ease off.",
      "Camille. Tonight's threshold is replaced: 45 minutes easy, 6 to 7 pm, nothing more. HRV at 38 ms, three nights below your band: that's not sensor noise. The real question: what is eating your nights this week, work, screens, a late drink? Sort it before the next quality session.",
    ],
    tab: ["Verdict: ease off", [["Session", "Threshold 5×6' → Easy 45'"], ["HRV", "38 ms · band 52-70"], ["Resting HR", "52 bpm · +6"], ["Readiness", "34/100"], ["Slot", "6-7 pm · 19 °C"]]],
    foot: ["warm · explains the why", "direct · asks the awkward question", "verdict first · the table"],
    same: "same verdict · same numbers · same file",
    k4: "03 · FIRMNESS AND LENGTH",
    toml: ["[coaching]", "style", "intensity", "verbosity"],
    int: [["gentle", "Proposes, doesn't impose. Always a fallback."], ["balanced", "Recommends clearly, accepts a reasoned objection."], ["strong", "Decides: “cancelled”, not “you might consider”."]],
    ver: [["brief", "3 to 5 lines, verdict first."], ["standard", "A paragraph + the key metrics."], ["detailed", "Segment-by-segment analysis."]],
    intMsg: [
      "Camille, I suggest swapping tonight's threshold for 45 minutes of easy running, between 6 and 7 pm. If you'd rather, take a full rest: just nothing harder.",
      "Camille, I recommend swapping tonight's threshold for 45 minutes of easy running, between 6 and 7 pm. Tell me if I'm missing something: I'm listening.",
      "Camille: threshold cancelled. 45 minutes of easy running tonight, between 6 and 7 pm. I won't reopen this without new information.",
    ],
    verMsg: [
      ["Verdict: ease off.", "Threshold 5×6' → Easy 45', 6-7 pm.", "HRV 38 ms · resting HR 52 bpm · readiness 34/100."],
      ["Three nights below your HRV band (38 ms, band 52-70) and a resting HR of 52 bpm, six beats above your median: we swap the threshold for 45 minutes of easy running tonight, between 6 and 7 pm, 19 °C."],
      ["Signals: HRV 38 ms, below the 52-70 band for 3 nights; resting HR 52 bpm, +6 on the 7-day median (46); readiness 34/100.",
       "Reading: three nights in a row is not an isolated night: we don't write it off as chance.",
       "Session: easy 45 min in zone 2; the 5 × 6 min threshold is replaced.",
       "Slot: 6-7 pm, 19 °C, wind 10 km/h."],
    ],
    k5: "04 · YOUR PROFILE WINS", h5: "What an identifier can't say.",
    pfile: "planning/Runner_Profile.md",
    prof: ["## Coaching preferences", "- **What motivates me**: my consistency over the week", "- **What doesn't work with me**: hollow cheers", "- **Topics not to comment on**: my weight", "- **Risk tolerance**: cautious", "- **When to ask me rather than assume**:"],
    prec: ["Instruction of the moment", "Task requirement", "Profile preference", "This catalogue"],
    precTag: "precedence · rule 5",
    before: "Catalogue: “Your body is asking for a break. Well done, such great consistency!”",
    after: "Profile applied: “Your body is asking for a break. Your week's consistency stays intact: we swap, we don't skip.”",
    k6: "05 · RULE 7", h6: "Tone changes. Never the substance.",
    rule: "config/coaching-styles.md · rule 7",
    waves: ["bienveillant", "exigeant", "factuel"], wl: "tone · varies", vl: "verdict · fixed",
  },
};

const hexA = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
const AMBER_BG = "rgba(240,180,60,0.12)", AMBER_LN = "rgba(240,180,60,0.6)";

function padlock(x, y, s, color, alpha = 1) {
  ctx.save(); ctx.globalAlpha *= alpha;
  ctx.beginPath(); ctx.arc(x, y - 2 * s, 4.2 * s, Math.PI, 0); ctx.strokeStyle = color; ctx.lineWidth = 1.8 * s; ctx.stroke();
  rr(x - 6 * s, y - 2 * s, 12 * s, 9.5 * s, 2 * s); ctx.fillStyle = color; ctx.fill();
  ctx.restore();
}

/* LE bandeau « fond ». Même fonction, mêmes coordonnées dans toutes les scènes : il est
 * volontairement insensible au fondu de scène (globalAlpha remis à 1) pour ne jamais « respirer ». */
const CX = 80, CY = 100, CW = 1120, CH = 104;
function core(y, o = {}) {
  const a = o.alpha ?? 1, r1 = o.r1 ?? 1, r2 = o.r2 ?? 1, r3 = o.r3 ?? 1, c = S.core;
  ctx.save(); ctx.globalAlpha = 1;
  panel(CX, y, CW, CH, { r: 18, fill: C.panel2, stroke: AMBER_LN, lw: 1.5, alpha: a });
  padlock(CX + 32, y + 24, 1, C.amber, a);
  text(c.tag, CX + 50, y + 28, { size: 12, weight: 600, font: MONO, color: C.amber, spacing: "1.5px", alpha: a });
  // ligne 1 : la séance qui change
  const x1 = CX + 28, y1 = y + 66;
  text(c.from, x1, y1, { size: 22, weight: 600, font: SORA, color: C.faint, alpha: a * r1 });
  const w1 = measure(c.from, 22, 600, SORA);
  line([[x1, y1 - 8], [x1 + w1, y1 - 8]], C.faint, 2, a * r1);
  text("→", x1 + w1 + 16, y1, { size: 22, weight: 600, font: SORA, color: C.soft, alpha: a * r1 });
  text(c.to, x1 + w1 + 52, y1, { size: 22, weight: 800, font: SORA, alpha: a * r1 });
  // verdict
  pill(c.verdict, CX + CW - 28, y + 52, { align: "right", size: 20, font: SORA, weight: 800, color: C.amber, fill: AMBER_BG, stroke: AMBER_LN, padX: 22, h: 40, alpha: a * r1 });
  // ligne 2 : mesures + fichier
  text(c.nums, x1, y + 92, { size: 13, font: MONO, color: C.soft, alpha: a * r2 });
  text(c.file, CX + CW - 28, y + 92, { size: 12, font: MONO, color: C.faint, align: "right", alpha: a * r3 });
  if (o.glow) highlight(CX, y, CW, CH, o.glow, C.amber);
  ctx.restore();
}

/* ------------------------------- la décision ------------------------------- */
function sDecision(t, d, cues) {
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 5.9), a2 = at(cues, 2, 8.9);
  const ky = inOut(seg(t, a2 - 0.5, a2 + 0.6));
  const ytop = lerp(300, CY, ky);
  const fade = 1 - ky;
  kicker(S.k2, seg(t, 0, 0.4) * fade);
  headline(S.h2, seg(t, 0.1, 0.7) * fade, 140, 38);
  if (fade > 0) {
    pill(S.day, W / 2, 248, { size: 14, color: C.soft, fill: C.panel, stroke: C.line, alpha: seg(t, 0.2, 0.8) * fade });
  }
  // le bandeau se construit sur la voix
  core(ytop, { alpha: seg(t, 0.2, 0.7), r1: outCubic(seg(t, a0, a0 + 0.8)), r2: outCubic(seg(t, a1, a1 + 0.7)), r3: outCubic(seg(t, a1 + 0.9, a1 + 1.5)) });
  // légendes : mesures / verdict / fichier
  if (fade > 0) {
    const lk = [seg(t, a1 + 0.2, a1 + 0.8), seg(t, a0 + 0.9, a0 + 1.5), seg(t, a1 + 1.1, a1 + 1.7)];
    const tx = [CX + 160, CX + CW - 100, CX + CW - 200], yb = ytop + CH;
    S.lbl.forEach((s, i) => callout(s, tx[i] - (i === 2 ? 150 : 0), yb + 50, tx[i], yb + 2, lk[i] * fade, { size: 14, font: INTER }));
  }
  // les quatre voix du catalogue
  S.styles.forEach((st, i) => {
    const a = a2 + 0.5 + i * 0.75, k = outCubic(seg(t, a, a + 0.6));
    if (k <= 0) return;
    const w = 265, x = CX + i * (w + 20), y = 250 + (1 - k) * 24, h = 250, col = VC[st.id];
    panel(x, y, w, h, { r: 18, fill: C.panel, stroke: hexA(col, 0.55), alpha: k });
    ctx.save(); ctx.globalAlpha *= k; rr(x, y, w, 8, [18, 18, 0, 0]); ctx.fillStyle = col; ctx.fill(); ctx.restore();
    pill(st.id, x + 20, y + 44, { size: 13, color: col, fill: hexA(col, 0.12), stroke: hexA(col, 0.5), alpha: k });
    text(st.name, x + 20, y + 98, { size: 28, weight: 800, font: SORA, alpha: k, spacing: "-0.5px" });
    para(st.dir, x + 20, y + 134, w - 40, { size: 16, color: C.soft, alpha: k, lh: 24 });
  });
  const kt = seg(t, a2 + 3.2, a2 + 3.9);
  if (kt > 0) text('style = "bienveillant" | "exigeant" | "factuel" | "pedagogue"', W / 2, 552, { size: 15, font: MONO, color: C.accent, align: "center", alpha: kt });
}

/* -------------------------------- trois voix ------------------------------- */
function sVoices(t, d, cues) {
  kicker(S.k3, seg(t, 0, 0.4));
  core(CY);
  const starts = [at(cues, 0, 0.5), at(cues, 1, 4), at(cues, 2, 7.5)], a3 = at(cues, 3, 11.2);
  const ends = [starts[1], starts[2], a3 + 1.5];
  for (let i = 0; i < 3; i++) {
    const a = starts[i], k = outCubic(seg(t, a - 0.5, a + 0.1));
    if (k <= 0) continue;
    const x = CX + i * 380, w = 360, y = 232 + (1 - k) * 26, h = 388, id = S.styles[[0, 1, 2][i]].id, col = VC[id];
    const active = t >= a && (i === 2 || t < starts[i + 1]) && t < a3;
    panel(x, y, w, h, { r: 18, fill: C.panel, stroke: hexA(col, active ? 0.95 : 0.4), lw: active ? 2 : 1, alpha: k });
    ctx.save(); ctx.globalAlpha *= k; rr(x, y, w, 7, [18, 18, 0, 0]); ctx.fillStyle = col; ctx.fill(); ctx.restore();
    pill(id, x + 18, y + 38, { size: 13, color: col, fill: hexA(col, 0.12), stroke: hexA(col, 0.5), alpha: k });
    text(S.styles[i].name, x + w - 18, y + 43, { size: 18, weight: 800, font: SORA, align: "right", alpha: k });
    const typ = clamp((t - a) / (ends[i] - a));
    if (i < 2) {
      bubble(S.msg[i], x + 16, y + 68, w - 32, { size: 16, alpha: k, k: typ });
    } else {
      const [head, rows] = S.tab;
      text(typed(head, seg(t, a, a + 0.6)), x + 20, y + 100, { size: 20, weight: 800, font: SORA, color: col, alpha: k });
      rows.forEach(([lab, val], j) => {
        const ry = y + 134 + j * 46, rk = seg(t, a + 0.7 + j * 0.45, a + 1.2 + j * 0.45);
        line([[x + 20, ry - 12], [x + w - 20, ry - 12]], C.line, 1, k * rk);
        text(lab, x + 20, ry + 14, { size: 12, font: MONO, color: C.faint, alpha: k * rk });
        text(val, x + w - 20, ry + 14, { size: 15, weight: 600, align: "right", alpha: k * rk });
      });
    }
    dot(x + 24, y + h - 26, 4, col, k);
    text(S.foot[i], x + 38, y + h - 21, { size: 12, font: MONO, color: C.faint, alpha: k });
  }
  // « même verdict » : le bandeau s'illumine, il n'a pas bougé
  const kg = seg(t, a3 - 0.1, a3 + 0.5) * (1 - seg(t, d - 1.0, d - 0.3));
  core(CY, { glow: kg });
  if (kg > 0) text(S.same, W - 80, 86, { size: 13, weight: 600, font: MONO, color: C.amber, align: "right", spacing: "1.5px", alpha: kg });
}

/* ------------------------- fermeté (intensity) et longueur ------------------ */
function sKnobs(t, d, cues) {
  kicker(S.k4, seg(t, 0, 0.4));
  core(CY);
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 6.7), a2 = at(cues, 2, 13.3);
  const stepI = (a1 - a0 - 0.9) / 3, stepV = (a2 - a1 - 0.9) / 3;
  const iSteps = [0, 1, 2].map(i => a0 + 0.5 + i * stepI), vSteps = [0, 1, 2].map(i => a1 + 0.4 + i * stepV);
  const phase = t < a1 - 0.1 ? "int" : "ver";
  const idx = phase === "int" ? (t < iSteps[1] ? 0 : t < iSteps[2] ? 1 : 2) : (t < vSteps[1] ? 0 : t < vSteps[2] ? 1 : 2);
  const t0 = phase === "int" ? iSteps[idx] : vSteps[idx];
  // fichier de configuration (les trois lignes réelles de [coaching])
  const kc = outCubic(seg(t, 0.2, 0.8));
  const iv = idx, vals = { intensity: phase === "int" ? S.int[iv][0] : "balanced", verbosity: phase === "ver" ? S.ver[iv][0] : "standard" };
  if (t < iSteps[0]) { vals.intensity = "balanced"; }
  const col = VC.bienveillant;
  const kk = Math.max(kc, 0.0001);
  const lines = [
    { s: S.toml[0], c: C.faint },
    { s: `style     = "bienveillant"`, c: C.ink },
    { s: `intensity = "${vals.intensity}"`, c: phase === "int" && t >= iSteps[0] ? C.accent : C.ink, w: phase === "int" ? 700 : 400 },
    { s: `verbosity = "${vals.verbosity}"`, c: phase === "ver" ? C.accent : C.ink, w: phase === "ver" ? 700 : 400 },
  ];
  terminal(CX, 226, 360, 176, t, lines, { alpha: kk, size: 15, lh: 32, title: "config/workspace.user.toml" });
  // liste des valeurs du bouton courant, d'après le catalogue
  const list = phase === "int" ? S.int : S.ver;
  list.forEach(([id, eff], i) => {
    const y = 416 + i * 68, on = i === idx && (phase === "ver" || t >= iSteps[0]);
    panel(CX, y, 360, 60, { r: 12, fill: on ? "rgba(163,230,53,0.08)" : C.panel, stroke: on ? C.accent : C.line, lw: on ? 2 : 1, alpha: kc });
    text(id, CX + 16, y + 23, { size: 14, weight: 700, font: MONO, color: on ? C.accent : C.soft, alpha: kc });
    para(eff, CX + 16, y + 38, 330, { size: 12, color: C.faint, alpha: kc, lh: 14 });
  });
  // message : même verdict, longueur et fermeté variables
  const mx = 470, mw = 730, my = 226, mh = 394;
  panel(mx, my, mw, mh, { r: 18, fill: C.panel, stroke: hexA(col, 0.5), alpha: kc });
  ctx.save(); ctx.globalAlpha *= kc; rr(mx, my, mw, 7, [18, 18, 0, 0]); ctx.fillStyle = col; ctx.fill(); ctx.restore();
  pill("bienveillant", mx + 20, my + 38, { size: 13, color: col, fill: hexA(col, 0.12), stroke: hexA(col, 0.5), alpha: kc });
  const tag = phase === "int" ? `intensity · ${S.int[idx][0]}` : `verbosity · ${S.ver[idx][0]}`;
  if (phase === "ver" || t >= iSteps[0]) text(tag, mx + mw - 20, my + 43, { size: 14, weight: 700, font: MONO, color: C.accent, align: "right" });
  const typ = seg(t, t0, t0 + (phase === "int" ? 1.8 : 1.6));
  if (phase === "int" && t >= iSteps[0]) {
    para(S.intMsg[idx], mx + 26, my + 96, mw - 52, { size: 20, lh: 31, k: typ });
  } else if (phase === "ver") {
    const segs = S.verMsg[idx];
    let y = my + 96, n = 0;
    const total = segs.join("").length; let shown = typ * total;
    segs.forEach((s, j) => {
      const part = clamp(shown / s.length); shown -= s.length;
      if (part <= 0) return;
      const sz = idx === 0 ? 24 : idx === 1 ? 20 : 17, lh = idx === 0 ? 36 : idx === 1 ? 31 : 25;
      const h = para(s, mx + 26, y, mw - 52, { size: sz, lh, k: part, weight: idx === 0 && j === 0 ? 800 : 400, font: idx === 0 && j === 0 ? SORA : INTER, color: idx === 0 && j === 0 ? C.amber : C.ink });
      y += h + (idx === 2 ? 14 : 10); n++;
    });
    // jauge de longueur
    const lens = [0.22, 0.45, 1][idx];
    text("long.", mx + mw - 20, my + mh - 20, { size: 11, font: MONO, color: C.faint, align: "right" });
    rr(mx + mw - 170, my + mh - 30, 110, 8, 4); ctx.fillStyle = C.line; ctx.fill();
    rr(mx + mw - 170, my + mh - 30, 110 * lens, 8, 4); ctx.fillStyle = col; ctx.fill();
  }
}

/* --------------------------------- profil ---------------------------------- */
function sProfile(t, d, cues) {
  kicker(S.k5, seg(t, 0, 0.4));
  core(CY);
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 6.2), a2 = at(cues, 2, 12.8);
  const kt = outCubic(seg(t, a0 - 0.2, a0 + 0.5));
  const lines = S.prof.map((s, i) => ({ s, a: a0 + 0.6 + i * (a1 - a0 - 0.6) / 6.5, b: a0 + 1.1 + i * (a1 - a0 - 0.6) / 6.5, c: i === 0 ? C.ink : C.soft, w: i === 0 ? 700 : 400 }));
  terminal(CX, 226, 600, 394, t, lines, { alpha: Math.max(kt, 0.0001), size: 15, lh: 46, title: S.pfile });
  // la ligne qui change le message : mise en évidence au moment où la phrase disparaît
  const kh = seg(t, a2 - 0.6, a2);
  if (kh > 0) highlight(CX + 16, 226 + 62 + 2 * 46 - 22, 568, 32, kh);
  // précédence (règle 5)
  const px = 710, pw = 490;
  const kp = outCubic(seg(t, a1 - 0.2, a1 + 0.5));
  if (kp > 0) {
    S.prec.forEach((s, i) => {
      const y = 226 + i * 38, hot = i >= 2, on = i === 2;
      const k = outCubic(seg(t, a1 + i * 0.2, a1 + 0.4 + i * 0.2));
      panel(px, y, pw, 32, { r: 10, fill: on ? "rgba(163,230,53,0.1)" : C.panel, stroke: on ? C.accent : C.line, lw: on ? 2 : 1, alpha: k });
      text(String(i + 1), px + 18, y + 22, { size: 13, weight: 700, font: MONO, color: hot ? C.accent : C.faint, alpha: k });
      text(s, px + 40, y + 22, { size: 15, weight: on ? 700 : 400, color: on ? C.ink : C.soft, alpha: k });
      if (i === 3) text(S.precTag, px + pw - 14, y + 22, { size: 11, font: MONO, color: C.faint, align: "right", alpha: k });
    });
  }
  // avant / après : la phrase de complaisance disparaît
  const kb = outCubic(seg(t, a2 - 0.6, a2 + 0.1));
  if (kb > 0) {
    const y = 396, col = VC.bienveillant;
    const sw = seg(t, a2 + 1.0, a2 + 1.9);
    panel(px, y, pw, 100, { r: 14, fill: C.panel2, stroke: C.line, alpha: kb * (1 - 0.55 * sw) });
    para(S.before, px + 18, y + 30, pw - 36, { size: 16, color: C.soft, alpha: kb * (1 - 0.55 * sw), lh: 23 });
    // trait barrant la félicitation
    if (sw > 0) line([[px + 18, y + 80], [px + 18 + (pw - 36) * outCubic(sw), y + 80]], C.red, 2, 0.9);
    const ka = outCubic(seg(t, a2 + 1.3, a2 + 2.0));
    if (ka > 0) {
      panel(px, y + 114, pw, 110, { r: 14, fill: hexA(col, 0.1), stroke: hexA(col, 0.7), lw: 1.5, alpha: ka });
      para(S.after, px + 18, y + 144, pw - 36, { size: 16, alpha: ka, lh: 23, k: ka });
    }
  }
}

/* --------------------------------- règle 7 --------------------------------- */
function sRule(t, d, cues) {
  kicker(S.k6, seg(t, 0, 0.4));
  const a0 = at(cues, 0, 0.5), a1 = at(cues, 1, 5.5), a2 = at(cues, 2, 11.4);
  const out = 1 - seg(t, d - 0.45, d);
  core(CY, { alpha: out, glow: seg(t, a1 - 0.2, a1 + 0.5) * (1 - seg(t, a2 + 1.5, a2 + 2.2)) * out });
  // trois tons qui ondulent, un verdict qui reste droit
  const rows = [[S.waves[0], 0], [S.waves[1], 1], [S.waves[2], 2], ["verdict", 3]];
  const x0 = 300, x1 = 1200;
  rows.forEach(([id, i]) => {
    const y = 270 + i * 66, k = outCubic(seg(t, 0.5 + i * 0.3, 1.3 + i * 0.3));
    if (k <= 0) return;
    const col = i === 3 ? C.amber : VC[id];
    text(i === 3 ? S.core.verdict : id, CX, y + 5, { size: i === 3 ? 20 : 15, weight: i === 3 ? 800 : 600, font: i === 3 ? SORA : MONO, color: col, alpha: k });
    const pts = [];
    for (let j = 0; j <= 90; j++) {
      const u = j / 90, x = lerp(x0, x1, u), ph = t * (1.2 + i * 0.4);
      let v;
      if (i === 0) v = Math.sin(u * 14 - ph) * 15;                               // houle chaleureuse
      else if (i === 1) { const q = (((u * 11 - ph * 0.6) % 1) + 1) % 1; v = (q < 0.5 ? q * 4 - 1 : 3 - q * 4) * 17; } // zigzag net
      else if (i === 2) v = (((Math.floor(u * 9 - ph * 0.5) % 2) + 2) % 2 ? 7 : -7);        // créneaux sobres
      else v = 0;                                                                // le fond : droit
      const live = i === 3 ? 0 : 1;
      pts.push([x, y + v * live]);
    }
    line(partial(pts, k), col, i === 3 ? 4 : 2.5, i === 3 ? 1 : 0.9);
    if (i === 3) dot(x1, y, 7, C.amber, k);
  });
  text(S.wl, x1, 244, { size: 12, font: MONO, color: C.faint, align: "right", alpha: seg(t, 1.4, 2) });
  text(S.vl, x1, 508, { size: 12, font: MONO, color: C.amber, align: "right", alpha: seg(t, 2.2, 2.8) });
  const kh = outCubic(seg(t, a2 - 0.2, a2 + 0.7));
  text(S.h6, W / 2, 590, { size: 40, weight: 800, font: SORA, align: "center", alpha: kh * out, spacing: "-1px" });
  text(S.rule, W / 2, 624, { size: 14, font: MONO, color: C.accent, align: "center", alpha: seg(t, a2 + 0.5, a2 + 1.2) * out });
}

ARC.episode({
  n: 11, slug: "styles-coaching",
  strings: STR,
  shots: [],
  scenes: { decision: sDecision, voices: sVoices, knobs: sKnobs, profile: sProfile, rule: sRule },
});
})();
