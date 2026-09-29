// Prototype de la vue « Coach » : réponses SCRIPTÉES, aucun appel réseau.
// Sert uniquement à valider le rendu (trace d'outils, streaming, carte de
// confirmation d'écriture Garmin) avant de brancher un vrai backend.
(() => {
  const $ = (s) => document.querySelector(s);
  const thread = $("#thread");
  const input = $("#composer-input");
  const form = $("#composer");
  const send = form.querySelector(".composer__send");
  const cost = $("#cost");
  let tokens = 18, eur = 0.04;

  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const scroll = () => { thread.scrollTop = thread.scrollHeight; };

  const SCRIPTS = [
    {
      match: /^\/log/i,
      steps: ["<code>arc_log.py</code> → 2 × Maurten Gel 100, 500 ml", "<code>write</code> activities/2026-09-29_trail.md"],
      text: [
        "Noté pour la sortie de ce matin : <strong>50 g de glucides</strong> et <strong>500 ml</strong> au km 15, RPE 7.",
        "Ça fait environ 42 g/h sur la partie active. Pour le 52 km, vise 60–70 g/h : on teste cette dose samedi.",
      ],
      files: ["activities/2026-09-29_trail.md"],
    },
    {
      match: /^\/week/i,
      steps: ["<code>read</code> planning/2026-W40_semaine.md", "<code>arc_index.py week</code>"],
      text: [
        "<strong>Semaine 40</strong> : 4 h 10 faites sur 9 h prévues, 1 250 m D+ sur 2 400.",
        "Il reste la sortie longue de samedi (3 h 30, 1 400 m D+), la pièce maîtresse du bloc. Tout le reste s'ajuste autour.",
      ],
    },
    {
      match: /.*/,
      steps: ["<code>read</code> planning/active_objective.md", "<code>read</code> rapports/2026-09-27_rapport.md"],
      text: [
        "Bonne question. D'après ton dernier rapport, ta tenue en descente reste le point faible (−11 % d'allure sur les pentes à −15 %).",
        "Je peux ajouter une séance de descente technique jeudi à la place des lignes droites. Tu veux que je la prépare ?",
      ],
    },
  ];

  function addUser(text) {
    const el = document.createElement("article");
    el.className = "msg msg--user";
    el.innerHTML = `<div class="msg__bubble">${esc(text)}</div>`;
    thread.appendChild(el);
    scroll();
  }

  function addCoach(script) {
    const el = document.createElement("article");
    el.className = "msg msg--coach";
    el.innerHTML = `<div class="msg__avatar" aria-hidden="true">C</div>
      <div class="msg__body">
        <details class="trace is-running"><summary><span class="trace__dot"></span><span class="trace__label">Le coach consulte le workspace…</span></summary><ol></ol></details>
        <div class="msg__text"></div>
      </div>`;
    thread.appendChild(el);
    scroll();
    const trace = el.querySelector(".trace"), list = trace.querySelector("ol"), body = el.querySelector(".msg__text");

    let i = 0;
    const nextStep = () => {
      if (i < script.steps.length) {
        list.insertAdjacentHTML("beforeend", `<li>${script.steps[i++]}</li>`);
        return setTimeout(nextStep, 450);
      }
      trace.classList.remove("is-running");
      trace.querySelector(".trace__label").textContent = `${script.steps.length} étape${script.steps.length > 1 ? "s" : ""}`;
      streamParagraphs(body, script.text, () => {
        if (script.files) {
          el.querySelector(".msg__body").insertAdjacentHTML("beforeend",
            `<div class="files"><span class="files__label">Fichier écrit</span>${script.files.map((f) => `<span class="file-chip">${f}</span>`).join("")}</div>`);
        }
        tokens += 3; eur += 0.01;
        cost.textContent = `≈ ${eur.toFixed(2).replace(".", ",")} € · ${tokens} k jetons (80 % en cache)`;
        send.disabled = false;
        scroll();
      });
    };
    setTimeout(nextStep, 300);
  }

  // Simule le streaming : les paragraphes arrivent mot à mot.
  function streamParagraphs(body, paras, done) {
    let p = 0;
    const nextPara = () => {
      if (p >= paras.length) return done();
      const el = document.createElement("p");
      el.className = "typing";
      body.appendChild(el);
      const words = paras[p++].split(" ");
      let w = 0;
      const tick = () => {
        el.innerHTML = words.slice(0, ++w).join(" ");
        scroll();
        if (w < words.length) setTimeout(tick, 28);
        else { el.classList.remove("typing"); setTimeout(nextPara, 120); }
      };
      tick();
    };
    nextPara();
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    input.value = "";
    input.style.height = "";
    send.disabled = true;
    addUser(text);
    addCoach(SCRIPTS.find((s) => s.match.test(text)));
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  });

  document.querySelectorAll(".quick__btn").forEach((b) => b.addEventListener("click", () => {
    input.value = b.dataset.cmd;
    input.focus();
    if (!b.dataset.cmd.endsWith(" ")) form.requestSubmit();
  }));

  // Carte de confirmation : simule l'écriture Garmin après approbation explicite.
  document.addEventListener("click", (e) => {
    const approve = e.target.closest("[data-approve]"), reject = e.target.closest("[data-reject]");
    if (!approve && !reject) return;
    const card = document.getElementById((approve || reject).dataset.approve || (approve || reject).dataset.reject);
    const btns = card.querySelector(".action__btns");
    if (approve) {
      btns.innerHTML = `<span class="action__result">✓ Appliqué · schedule_workouts vérifié dans le calendrier Garmin</span>`;
      card.classList.add("is-done");
      $("#ctx-session").textContent = "Endurance Z2 45 min + 4 LD";
      $("#ctx-status").innerHTML = `<span class="chip__dot"></span>modifiée`;
      $("#ctx-status").className = "chip chip--status-moved";
    } else {
      btns.innerHTML = `<span class="action__result action__result--rejected">Refusé · décision tracée comme <em>rejected_by_athlete</em></span>`;
    }
  });

  $("#backend").addEventListener("change", (e) => {
    cost.textContent = e.target.value === "claude"
      ? "≈ 0,04 € · 18 k jetons (82 % en cache)"
      : "≈ 0,05 € · 18 k jetons via OpenRouter (cache selon le modèle)";
  });

  scroll();
})();
