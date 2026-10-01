// Sections du tableau de bord : UNE liste, partagée par index.html (app.js) et chat.html
// (chat.js) — la page Coach recopiait la sienne et ratait chaque nouvelle section.

export function navItems(settings) {
  const nutrition = settings?.agents?.includes("nutritionist");
  return [
    ["", "Aujourd'hui"], ["forme", "Forme & charge"], ["analyse", "Analyse"], ["sante", "Santé"], ["semaine", "Semaine"],
    ["seances", "Séances"], ["performance", "Performance"], ["materiel", "Matériel"], ["trail-shape", "Trail Shape"], ["calendrier", "Calendrier"],
    ["decisions", "Décisions"], ["rapports", "Rapports"], ...(nutrition ? [["nutrition", "Nutrition"]] : []),
    ["hypotheses", "Hypothèses"],
  ];
}
