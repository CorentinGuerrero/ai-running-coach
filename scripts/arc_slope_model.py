#!/usr/bin/env python3
"""Modèle personnel pente -> allure (et FC), appris sur l'historique — #58,
épopée #23.

## Pourquoi (vs le GAP générique de #44)

Le GAP (`arc_gap.py`, #44) applique à TOUS les athlètes le même modèle de
laboratoire (Minetti et al. 2002) : allure ajustée = allure mesurée ×
coût(pente)/coût(plat). C'est une approximation raisonnable en l'absence de
données individuelles, mais un athlète réel a sa PROPRE courbe pente -> allure
(foulée, technique de descente, habitude du power-hiking en côte, etc.) — que
seule son historique de séances peut révéler. Ce module ajuste cette courbe
personnelle, classe de pente par classe de pente, et expose un repli propre
(le modèle générique de #44) là où l'historique ne suffit pas encore.

Sert de brique pure pour #59 (allures de course par segment, stratège de
course), #60 (cibles GAP des séances structurées) et #61 (débrief post-course) :
aucun de ces trois ne doit recalculer sa propre notion de « pente -> allure »,
ils consomment tous `predict_speed`.

## Paniers de pente

`GRADE_BINS` : paniers fins de `BIN_WIDTH` (2,5 points de pourcentage) de
`-BIN_MAX_ABS` à `+BIN_MAX_ABS` (30 %), plus deux paniers ouverts (« queues »)
au-delà — jamais un panier de largeur infinie au milieu de la plage étudiée
(qui mélangerait des pentes très différentes), mais des queues ouvertes pour
ne perdre aucun échantillon extrême. Alignés en largeur sur les classes de
montée/descente déjà utilisées par le tableau de bord (`arc_climb.
GRADE_CLASSES`, `arc_descent.DESCENT_GRADE_CLASSES`) mais BEAUCOUP plus fins :
ces classes-là servent à un affichage synthétique (5 à 6 classes), celle-ci
ajuste une courbe (une trentaine de paniers).

## Population — pourquoi une bande d'effort (« endurance » par défaut)

L'allure sur une pente donnée dépend énormément de l'effort fourni (un sprint
en côte n'a rien à voir avec une côte en endurance fondamentale) : mélanger
toutes les séances sans distinction ferait une moyenne sans signification
physiologique claire. Par défaut (`band="endurance"`), ce module restreint
les échantillons à ceux dont la FC est sous le seuil facile/modéré du modèle
de Seiler déjà résolu pour l'athlète (`arc_metrics.seiler_bounds`, #43) — la
« zone d'endurance » au sens le plus large (Z1+Z2 façon Karvonen, ou
équivalent LTHR/%FCmax selon la méthode active). `band="all"` lève cette
restriction (toutes les séances de la famille course à pied, tous efforts
confondus) : une seconde courbe, à lire comme « comment je bouge sur cette
pente, quel que soit l'effort », jamais comme une allure d'endurance. Sans
seuils FC résolus au profil, `band="endurance"` ne peut rien ajuster (aucune
séance n'est incluse) : `fit_slope_model` le signale par
`reason_code="no_hr_threshold"`, jamais un silence qui laisserait croire à un
manque de séances.

## Marche vs course sur les pentes raides — gardée, pas retirée

Un panier de forte pente montante est souvent dominé par de la marche/du
power-hiking : c'est une donnée réelle sur COMMENT l'athlète bouge sur cette
pente, pas un artefact à filtrer (contrairement à `arc_decoupling`/
`arc_durability`, qui EXCLUENT la marche de l'EF pour comparer des régimes
physiologiques homogènes — un objectif différent du nôtre : ici, on veut
l'allure REPRÉSENTATIVE de l'athlète sur cette pente, marche comprise). Le
panier expose donc `run_share` (part du temps couru, cadence >=
`arc_decoupling.WALKING_CADENCE_SPM` à défaut GAP/vitesse — même détection
que `arc_decoupling._is_walking`, réutilisée via ses constantes publiques,
jamais réinventée) : un consommateur qui a besoin d'une allure « en courant
uniquement » (ex. #60, cibles GAP d'une répétition de côte à courir) peut
alors décider d'écarter les paniers à `run_share` trop bas plutôt que de se
fier à une moyenne mêlant les deux régimes sans le savoir.

## Robustesse — médiane pondérée, pas la moyenne

Une moyenne arithmétique est tirée par les extrêmes (un unique passage très
lent dans un panier peu fréquenté suffit à la fausser) : ce module utilise la
MÉDIANE pondérée par le temps (`_weighted_percentile(..., 0.5)`), et
l'intervalle interquartile pondéré (`p25`/`p75`) comme approximation
d'intervalle de confiance — volontairement PAS un bootstrap (coûteux, un
tirage aléatoire supplémentaire à chaque réindexation d'un workspace de
centaines de séances) ni une erreur-type paramétrique (suppose une
distribution ± gaussienne des vitesses par panier, hypothèse jamais vérifiée
ici) : l'IQR pondéré est une mesure de dispersion robuste, bon marché,
directement interprétable (« la moitié des occurrences de ce panier tombent
entre telle et telle allure ») — documentée comme un REPÈRE, pas un
intervalle de confiance statistique au sens strict.

## Pondération par récence

Chaque SÉANCE (pas chaque échantillon) pèse `2 ** (-âge_jours /
HALF_LIFE_DAYS)` dans la médiane pondérée de chaque panier — une séance d'il
y a `HALF_LIFE_DAYS` jours pèse moitié moins qu'une séance d'aujourd'hui. Par
séance, pas par échantillon individuel : une longue sortie plate ne doit pas
« diluer » par son nombre d'échantillons le poids d'une séance plus courte
mais plus récente sur un panier de pente donné — le poids de récession est un
attribut de LA SÉANCE, le volume de temps dans le panier (poids secondaire,
multiplicatif) reste, lui, mesuré par échantillon.

## Coût — agrégation par activité, jamais par échantillon global

Avec des centaines de séances × des milliers d'échantillons de 5 s chacune,
regrouper TOUS les échantillons de TOUTES les séances dans une seule liste
avant de calculer une médiane globale serait couteux en mémoire ET inutile :
`activity_bin_summaries` réduit CHAQUE séance à, au plus, une valeur par
panier (moyenne pondérée par le temps DE CETTE séance) avant de combiner ces
résumés (un par séance par panier, un ordre de grandeur negligeable même sur
365 jours d'historique) — voir `arc_index.compute_metrics` pour l'appel
(réutilise `arc_gap.gap_sample_series` déjà calculée pour le GAP/le
découplage/la durabilité de la même activité, jamais un second calcul de
pente).

## Repli — modèle générique (Minetti, #44) quand l'historique manque

Un panier sans assez de données personnelles (`MIN_BIN_TIME_S`/
`MIN_BIN_ACTIVITIES`) retombe sur le modèle générique de #44 : allure prédite
= référence plate personnelle (médiane des paniers proches de 0 %, EUX-MÊMES
personnels ; à défaut, aucune prédiction générique n'est possible — voir
`reason_code="no_flat_reference"`) × coût(0)/coût(pente) — l'inverse de la
formule GAP (`arc_gap.gap_speed_ms`), puisqu'on VEUT ici l'allure brute
prédite à effort constant, pas l'allure ajustée à plat. `source: "generic"`
marque explicitement ce repli, jamais confondu avec une donnée personnelle.

## Lissage — léger, jamais forcé à la monotonie

Après le calcul par panier (personnel ou générique), un lissage à 3 points
(`SMOOTH_WEIGHTS`, 0,25/0,5/0,25, renormalisé aux bords) est appliqué sur la
suite ordonnée des vitesses prédites — pour atténuer le bruit d'échantillonnage
entre paniers voisins peu fréquentés, RIEN de plus : la monotonie n'est PAS
forcée (une descente peut légitimement ralentir au-delà d'un certain point,
voir `arc_gap.ASSUMPTIONS["model"]` sur le biais connu de Minetti en forte
descente) — forcer une courbe monotone effacerait ce signal réel. `source`
par panier reste celui du panier D'ORIGINE (personnel ou générique) même après
lissage : le lissage change la valeur affichée, jamais l'étiquette de
provenance.

## API réutilisable, pure (sans SQLite ni disque) — pour #59, #60, #61

- `grade_bin(grade)` : panier (`GRADE_BINS`) d'une pente (fraction signée).
- `activity_bin_summaries(series, band, easy_hr_bpm)` : résumé PAR PANIER
  d'UNE séance déjà augmentée par `arc_gap.gap_sample_series` (a `grade`,
  `speed_ms`, `hr_bpm`?, `cadence_spm`?) — la seule fonction qui touche aux
  échantillons individuels.
- `combine_activity_summaries(activities, as_of, half_life_days)` : combine
  les résumés de plusieurs séances (médiane pondérée par récence).
- `apply_fallback_and_smoothing(combined, ...)` : repli générique + lissage
  léger -> liste de paniers finis, prête à stocker/exposer.
- `fit_slope_model(activities, ...)` : bout en bout, pure (aucun accès
  disque/SQLite) — SEULE fonction que les tests du palier D appellent
  directement pour retrouver une courbe imposée (`tests/lib/synthetic.py`,
  `slope_factor_fn`).
- `predict_speed(grade, bins)` : accessseur PUR pour #59/#60/#61 —
  interpolation linéaire entre les vitesses des DEUX paniers dont le point
  milieu encadre `grade` (jamais une simple table de paliers) ; extrapolation
  PLATE (jamais polynomiale) au-delà des points milieux des paniers extrêmes.

Stdlib uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import bisect
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arc_decoupling as DC  # noqa: E402
import arc_gap as G  # noqa: E402

# Largeur d'un panier (fraction, 0,025 = 2,5 points de pourcentage) — dans la
# fourchette « 2 à 3 % » demandée par #58 : assez fin pour capter une vraie
# courbe pente -> allure, assez large pour qu'un panier de pente courante
# (proche du plat) accumule plusieurs séances rapidement.
BIN_WIDTH = 0.025

# Bornes des paniers fins (fraction) : au-delà, deux paniers ouverts (queues).
BIN_MAX_ABS = 0.30

# Fenêtre par défaut (mois) et demi-vie de la pondération par récence (jours) —
# voir docstring du module. 45 jours : une séance d'il y a 6 semaines pèse
# encore notablement, une d'il y a 6 mois presque plus rien — jugement
# d'ingénierie, pas calibré sur des données réelles.
DEFAULT_MONTHS = 6
DEFAULT_HALF_LIFE_DAYS = 45.0

# Seuils de suffisance d'un panier pour rester « personnel » plutôt que de
# retomber sur le générique : au moins 3 minutes de temps pondéré cumulé (tout
# poids de récence confondu) ET au moins 2 séances distinctes — un panier
# alimenté par une seule séance ne distingue pas "l'athlète sur cette pente"
# d'un "jour particulier" (fatigue, terrain inhabituel).
MIN_BIN_TIME_S = 180.0
MIN_BIN_ACTIVITIES = 2

# Lissage à 3 points (voir docstring « Lissage »).
SMOOTH_WEIGHTS = (0.25, 0.5, 0.25)

# Bande de pente considérée comme « la référence plate » pour le repli
# générique (voir `_flat_reference`) : les paniers dont le MILIEU tombe dans
# cette plage, personnels uniquement.
FLAT_REFERENCE_ABS = 0.0375  # un panier et demi de large de chaque côté de 0

BANDS = ("endurance", "all")


def _grade_bins() -> Tuple[Tuple[float, float, str], ...]:
    bins: List[Tuple[float, float, str]] = [(float("-inf"), -BIN_MAX_ABS, f"<{-BIN_MAX_ABS * 100:.0f}%")]
    n = round(2 * BIN_MAX_ABS / BIN_WIDTH)
    lo = -BIN_MAX_ABS
    for _ in range(n):
        hi = round(lo + BIN_WIDTH, 6)
        bins.append((lo, hi, f"{lo * 100:+.1f}/{hi * 100:+.1f}%"))
        lo = hi
    bins.append((BIN_MAX_ABS, float("inf"), f">{BIN_MAX_ABS * 100:.0f}%"))
    return tuple(bins)


GRADE_BINS: Tuple[Tuple[float, float, str], ...] = _grade_bins()

ASSUMPTIONS = {
    "grade_bins": (
        f"Paniers de pente de {BIN_WIDTH * 100:.1f} points de pourcentage entre "
        f"{-BIN_MAX_ABS * 100:.0f} % et {BIN_MAX_ABS * 100:.0f} %, plus deux paniers ouverts au-delà — voir "
        "GRADE_BINS. Beaucoup plus fins que les classes de montée/descente déjà affichées "
        "(arc_climb.GRADE_CLASSES, arc_descent.DESCENT_GRADE_CLASSES), qui servent un affichage synthétique, "
        "pas l'ajustement d'une courbe."
    ),
    "population": (
        "Par défaut (band='endurance'), seuls les échantillons sous le seuil facile/modéré du modèle de "
        "Seiler déjà résolu pour l'athlète (arc_metrics.seiler_bounds, #43) alimentent le modèle : mélanger "
        "tous les efforts sans distinction produirait une allure par pente sans signification physiologique "
        "claire. band='all' lève cette restriction (tous efforts, famille course à pied) — à lire comme « "
        "comment je bouge sur cette pente », jamais comme une allure d'endurance. Sans seuils FC résolus, "
        "band='endurance' ne peut ajuster aucun panier personnel (reason_code='no_hr_threshold')."
    ),
    "walking": (
        "La marche/le power-hiking sur les paniers de forte pente montante est GARDÉE, jamais filtrée : elle "
        "représente comment l'athlète bouge réellement sur cette pente. `run_share` (part du temps couru, "
        "détection identique à arc_decoupling._is_walking, réutilisée via ses constantes publiques) est "
        "exposée par panier pour qu'un consommateur qui a besoin d'une allure « en courant uniquement » "
        "(ex. #60) puisse écarter les paniers à run_share trop bas plutôt que de se fier à une moyenne "
        "mêlant les deux régimes sans le savoir."
    ),
    "robust_stats": (
        "Médiane pondérée par le temps (jamais la moyenne, sensible aux extrêmes) par panier, avec un "
        "intervalle interquartile pondéré (p25/p75) comme repère de dispersion — volontairement PAS un "
        "bootstrap (coûteux à chaque réindexation) ni une erreur-type paramétrique (suppose une "
        "distribution proche d'une gaussienne, jamais vérifiée) : à lire comme un repère de dispersion, pas "
        "un intervalle de confiance statistique au sens strict."
    ),
    "recency": (
        f"Chaque SÉANCE (pas chaque échantillon) pèse 2**(-âge_jours/{DEFAULT_HALF_LIFE_DAYS:.0f}) dans la "
        "médiane pondérée de chaque panier — demi-vie par défaut configurable. Le poids de récence est un "
        "attribut de la séance entière, jamais dilué par son volume d'échantillons dans le panier (mesuré "
        "séparément, par activité, avant combinaison — voir 'aggregation_cost')."
    ),
    "aggregation_cost": (
        "Chaque séance est réduite à, au plus, une valeur par panier (moyenne pondérée par le temps DE "
        "CETTE séance, `activity_bin_summaries`) AVANT combinaison entre séances — jamais un regroupement "
        "de tous les échantillons de toutes les séances en une seule liste géante avant de calculer une "
        "médiane globale, qui serait couteux en mémoire sur un historique de centaines de séances sans "
        "bénéfice de robustesse supplémentaire. Réutilise `arc_gap.gap_sample_series` déjà calculée pour le "
        "GAP/le découplage/la durabilité de la même activité (arc_index.compute_metrics) — jamais un second "
        "calcul de pente."
    ),
    "fallback": (
        "Un panier sans assez de données personnelles "
        f"(< {MIN_BIN_TIME_S:.0f} s de temps pondéré cumulé OU < {MIN_BIN_ACTIVITIES} séances distinctes) "
        "retombe sur le modèle générique de Minetti et al. 2002 (#44, `arc_gap.minetti_cost`) appliqué à la "
        "référence plate PERSONNELLE de l'athlète (médiane des paniers personnels proches de 0 %) : allure "
        "prédite = référence plate x coût(0)/coût(pente) — l'inverse de la formule GAP, puisqu'on veut ici "
        "l'allure brute prédite à effort constant, pas l'allure ajustée à plat. `source: 'generic'` marque "
        "ce repli. Sans référence plate personnelle du tout, aucune prédiction générique n'est possible "
        "(reason_code='no_flat_reference') : le modèle générique a lui-même besoin d'un point d'ancrage "
        "personnel, il n'invente jamais une vitesse plate par défaut."
    ),
    "smoothing": (
        f"Lissage à 3 points ({SMOOTH_WEIGHTS[0]:.2f}/{SMOOTH_WEIGHTS[1]:.2f}/{SMOOTH_WEIGHTS[2]:.2f}, "
        "renormalisé aux bords) appliqué sur la suite ordonnée des vitesses prédites (personnelles ou "
        "génériques) pour atténuer le bruit entre paniers voisins peu fréquentés — la monotonie n'est "
        "JAMAIS forcée (une descente peut légitimement re-ralentir au-delà d'un certain point, voir "
        "arc_gap.ASSUMPTIONS['model']). `source` par panier reste celui du panier d'origine même après "
        "lissage."
    ),
    "interpolation": (
        "`predict_speed` interpole linéairement entre les vitesses des DEUX paniers dont le POINT MILIEU "
        "encadre la pente demandée (jamais une simple table de paliers, qui produirait des discontinuités à "
        "chaque frontière de panier) ; au-delà du point milieu du panier extrême (queue ouverte), la valeur "
        "est prolongée à PLAT (jamais une extrapolation polynomiale hors de tout point mesuré). Le point "
        "milieu d'un panier ouvert est un point d'ancrage NOMINAL (une demi-largeur de panier au-delà de sa "
        "borne fermée), pas une pente réellement typique de la queue."
    ),
}


def grade_bin(grade: Optional[float]) -> Optional[str]:
    """Étiquette du panier (`GRADE_BINS`) contenant `grade` (fraction signée) ;
    `None` si `grade` est `None` (pente non calculable)."""
    if grade is None:
        return None
    for lo, hi, label in GRADE_BINS:
        if lo <= grade < hi:
            return label
    return GRADE_BINS[-1][2]


def _bin_mid(lo: float, hi: float) -> float:
    """Point milieu d'un panier — pour un panier ouvert (queue), une demi-largeur
    au-delà de sa borne fermée (ancrage NOMINAL, voir ASSUMPTIONS['interpolation'])."""
    if lo == float("-inf"):
        return hi - BIN_WIDTH / 2
    if hi == float("inf"):
        return lo + BIN_WIDTH / 2
    return (lo + hi) / 2.0


def _is_walking(sample: dict) -> bool:
    """Même détection que `arc_decoupling._is_walking` (réutilise ses
    constantes publiques `WALKING_CADENCE_SPM`/`WALKING_SPEED_MS`, jamais
    réinventée) : cadence préférée, GAP à défaut, vitesse brute en dernier
    recours."""
    cadence = sample.get("cadence_spm")
    if cadence is not None:
        return cadence < DC.WALKING_CADENCE_SPM
    gap_speed = sample.get("gap_speed_ms")
    if gap_speed is not None:
        return gap_speed < DC.WALKING_SPEED_MS
    speed = sample.get("speed_ms")
    return speed is not None and speed < DC.WALKING_SPEED_MS


def activity_bin_summaries(series: Sequence[dict], *, band: str = "endurance",
                            easy_hr_bpm: Optional[float] = None,
                            resolution_s: float = G.DEFAULT_RESOLUTION_S) -> Dict[str, dict]:
    """Résumé PAR PANIER d'une séance déjà augmentée par
    `arc_gap.gap_sample_series` (a `grade`, `speed_ms`, `hr_bpm`?,
    `cadence_spm`?). Échantillons à l'arrêt (`arc_gap.STOPPED_SPEED_MS`)
    toujours exclus. `band='endurance'` restreint en plus aux échantillons
    dont `hr_bpm < easy_hr_bpm` (voir ASSUMPTIONS['population']) ; sans
    `easy_hr_bpm` fourni, rend `{}` (rien à ajuster pour cette séance).

    Rend `{label: {"weighted_time_s", "speed_weighted_sum", "hr_weighted_time_s",
    "hr_weighted_sum", "n_samples", "walking_weighted_time_s"}}`."""
    if band == "endurance" and easy_hr_bpm is None:
        return {}
    ordered = sorted((s for s in series if s.get("t_s") is not None), key=lambda s: s["t_s"])
    n = len(ordered)
    out: Dict[str, dict] = {}
    for i, s in enumerate(ordered):
        speed = s.get("speed_ms")
        if speed is None or speed < G.STOPPED_SPEED_MS:
            continue
        if band == "endurance":
            hr = s.get("hr_bpm")
            if hr is None or hr >= easy_hr_bpm:
                continue
        label = grade_bin(s.get("grade"))
        if label is None:
            continue
        dt = ordered[i + 1]["t_s"] - s["t_s"] if i + 1 < n else resolution_s
        dt = max(0.0, min(dt, resolution_s))
        bucket = out.setdefault(label, {
            "weighted_time_s": 0.0, "speed_weighted_sum": 0.0,
            "hr_weighted_time_s": 0.0, "hr_weighted_sum": 0.0,
            "n_samples": 0, "walking_weighted_time_s": 0.0,
        })
        bucket["weighted_time_s"] += dt
        bucket["speed_weighted_sum"] += dt * speed
        bucket["n_samples"] += 1
        if _is_walking(s):
            bucket["walking_weighted_time_s"] += dt
        hr = s.get("hr_bpm")
        if hr is not None:
            bucket["hr_weighted_time_s"] += dt
            bucket["hr_weighted_sum"] += dt * hr
    return out


def _recency_weight(age_days: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (max(0.0, age_days) / half_life_days)


def _weighted_percentile(pairs: Sequence[Tuple[float, float]], p: float) -> Optional[float]:
    """Percentile pondéré (`p` dans [0, 1]) d'une liste de `(valeur, poids)` —
    poids strictement positifs uniquement. Méthode simple par cumul (pas
    d'interpolation entre deux valeurs adjacentes) : suffisant pour un repère
    de dispersion, voir ASSUMPTIONS['robust_stats']."""
    usable = sorted((v, w) for v, w in pairs if w > 0)
    if not usable:
        return None
    total = sum(w for _, w in usable)
    target = p * total
    cumulative = 0.0
    for v, w in usable:
        cumulative += w
        if cumulative >= target:
            return v
    return usable[-1][0]


def combine_activity_summaries(activities: Sequence[dict], *, as_of: str,
                                half_life_days: float = DEFAULT_HALF_LIFE_DAYS) -> Dict[str, dict]:
    """Combine les résumés PAR SÉANCE (`activity_bin_summaries`) en un résumé
    PAR PANIER, pondéré par récence (voir ASSUMPTIONS['recency']).

    `activities` : séquence de `{"activity_id", "date" (AAAA-MM-JJ), "bins": {...}}`.
    `as_of` : date de référence (AAAA-MM-JJ) pour l'âge de chaque séance.

    Rend `{label: {"speed_pairs": [(vitesse_moy_activité, poids)], "hr_pairs": [...],
    "n_samples", "effective_time_s", "n_activities", "run_share"}}` — pas encore le
    modèle final (voir `apply_fallback_and_smoothing`)."""
    from datetime import date as _date
    try:
        ref = _date.fromisoformat(as_of)
    except (TypeError, ValueError):
        ref = None
    per_bin: Dict[str, dict] = {}
    for act in activities:
        act_date = act.get("date")
        age_days = 0.0
        if ref is not None and act_date:
            try:
                age_days = (ref - _date.fromisoformat(act_date)).days
            except ValueError:
                age_days = 0.0
        weight = _recency_weight(age_days, half_life_days)
        for label, b in (act.get("bins") or {}).items():
            if b["weighted_time_s"] <= 0:
                continue
            agg = per_bin.setdefault(label, {
                "speed_pairs": [], "hr_pairs": [], "n_samples": 0,
                "effective_time_s": 0.0, "n_activities": 0, "walking_time_s": 0.0,
            })
            mean_speed = b["speed_weighted_sum"] / b["weighted_time_s"]
            agg["speed_pairs"].append((mean_speed, weight * b["weighted_time_s"]))
            if b["hr_weighted_time_s"] > 0:
                mean_hr = b["hr_weighted_sum"] / b["hr_weighted_time_s"]
                agg["hr_pairs"].append((mean_hr, weight * b["hr_weighted_time_s"]))
            agg["n_samples"] += b["n_samples"]
            agg["effective_time_s"] += b["weighted_time_s"]
            agg["walking_time_s"] += b["walking_weighted_time_s"]
            agg["n_activities"] += 1
    for agg in per_bin.values():
        agg["run_share"] = (
            1.0 - agg["walking_time_s"] / agg["effective_time_s"] if agg["effective_time_s"] > 0 else None)
    return per_bin


def _flat_reference(combined: Dict[str, dict]) -> Tuple[Optional[float], Optional[str]]:
    """Référence plate personnelle : médiane pondérée des paniers dont le point
    milieu tombe dans `[-FLAT_REFERENCE_ABS, FLAT_REFERENCE_ABS]`, personnels
    uniquement (voir ASSUMPTIONS['fallback']). `(None, None)` si aucun panier
    proche du plat n'a de données."""
    pairs: List[Tuple[float, float]] = []
    for lo, hi, label in GRADE_BINS:
        mid = _bin_mid(lo, hi)
        if abs(mid) > FLAT_REFERENCE_ABS:
            continue
        agg = combined.get(label)
        if agg and agg["effective_time_s"] >= MIN_BIN_TIME_S and agg["n_activities"] >= MIN_BIN_ACTIVITIES:
            pairs.extend(agg["speed_pairs"])
    if not pairs:
        return None, None
    return _weighted_percentile(pairs, 0.5), "personal"


def apply_fallback_and_smoothing(combined: Dict[str, dict], *,
                                  min_bin_time_s: float = MIN_BIN_TIME_S,
                                  min_activities: int = MIN_BIN_ACTIVITIES) -> dict:
    """Repli générique (Minetti) + lissage léger — voir ASSUMPTIONS['fallback']/
    ['smoothing']. Rend `{"bins": [...], "flat_reference_speed_ms", "reason",
    "reason_code"}` — `reason_code="no_flat_reference"` et `bins: []` si même le
    repli générique est impossible (aucune donnée plate personnelle du tout)."""
    flat_speed, flat_source = _flat_reference(combined)
    if flat_speed is None:
        return {
            "bins": [], "flat_reference_speed_ms": None,
            "reason": "aucune donnée personnelle proche du plat (référence indisponible pour le repli "
                      "générique lui-même)",
            "reason_code": "no_flat_reference",
        }
    raw: List[dict] = []
    for lo, hi, label in GRADE_BINS:
        mid = _bin_mid(lo, hi)
        agg = combined.get(label)
        if agg and agg["effective_time_s"] >= min_bin_time_s and agg["n_activities"] >= min_activities:
            speed = _weighted_percentile(agg["speed_pairs"], 0.5)
            raw.append({
                "grade_lo": lo, "grade_hi": hi, "grade_mid": mid, "label": label,
                "speed_ms": speed,
                "ci_low_speed_ms": _weighted_percentile(agg["speed_pairs"], 0.25),
                "ci_high_speed_ms": _weighted_percentile(agg["speed_pairs"], 0.75),
                "hr_bpm": _weighted_percentile(agg["hr_pairs"], 0.5) if agg["hr_pairs"] else None,
                "source": "personal",
                "n_samples": agg["n_samples"], "n_activities": agg["n_activities"],
                "effective_time_s": round(agg["effective_time_s"], 1),
                "run_share": agg["run_share"],
            })
        else:
            cost = G.minetti_cost(mid)
            speed = flat_speed * (G.MINETTI_FLAT_COST / cost) if cost else None
            raw.append({
                "grade_lo": lo, "grade_hi": hi, "grade_mid": mid, "label": label,
                "speed_ms": speed, "ci_low_speed_ms": None, "ci_high_speed_ms": None, "hr_bpm": None,
                "source": "generic", "n_samples": 0, "n_activities": 0, "effective_time_s": 0.0,
                "run_share": None,
            })
    # Lissage léger (ASSUMPTIONS['smoothing']) : ne touche que `speed_ms`, jamais
    # `source`/`hr_bpm`/`ci_*` (repère de provenance et de dispersion inchangés).
    speeds = [b["speed_ms"] for b in raw]
    smoothed = []
    w0, w1, w2 = SMOOTH_WEIGHTS
    for i, s in enumerate(speeds):
        if s is None:
            smoothed.append(None)
            continue
        parts = [(w1, s)]
        if i > 0 and speeds[i - 1] is not None:
            parts.append((w0, speeds[i - 1]))
        if i + 1 < len(speeds) and speeds[i + 1] is not None:
            parts.append((w2, speeds[i + 1]))
        total_w = sum(w for w, _ in parts)
        smoothed.append(sum(w * v for w, v in parts) / total_w if total_w else None)
    for b, s in zip(raw, smoothed):
        b["speed_ms"] = s
        b["pace_s_km"] = (1000.0 / s) if s else None
    return {"bins": raw, "flat_reference_speed_ms": flat_speed, "reason": None, "reason_code": None}


def _empty_result(band: str, months: int, half_life_days: float, as_of: Optional[str],
                   reason: str, reason_code: str) -> dict:
    return {
        "band": band, "months": months, "half_life_days": half_life_days, "as_of": as_of,
        "n_activities": 0, "bins": [], "flat_reference_speed_ms": None,
        "reason": reason, "reason_code": reason_code,
    }


def fit_from_activity_bins(activities: Sequence[dict], *, band: str = "endurance",
                            months: int = DEFAULT_MONTHS, half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
                            easy_hr_bpm: Optional[float] = None, as_of: Optional[str] = None) -> dict:
    """Comme `fit_slope_model`, mais `activities` porte des résumés PAR PANIER
    DÉJÀ CALCULÉS (`{"activity_id", "date", "bins": activity_bin_summaries(...)}`)
    plutôt que des séries brutes — le chemin bon marché emprunté par
    `arc_index.compute_metrics` (voir ASSUMPTIONS['aggregation_cost']) : chaque
    activité n'y est résumée qu'UNE fois, au fil de la boucle d'indexation
    principale, jamais une seconde fois ici. `fit_slope_model` (séries brutes)
    reste l'entrée à utiliser depuis des tests/scripts qui n'ont pas déjà ce
    résumé sous la main."""
    if band not in BANDS:
        return _empty_result(band, months, half_life_days, as_of,
                              f"bande « {band} » inconnue (attendu : {', '.join(BANDS)})", "unknown_band")
    if band == "endurance" and easy_hr_bpm is None:
        return _empty_result(
            band, months, half_life_days, as_of,
            "aucun seuil FC facile/modéré résolu pour l'athlète (profil sans FC max/repos/seuil "
            "renseignée) — le modèle 'endurance' ne peut restreindre aucun échantillon", "no_hr_threshold")
    dated = sorted((a["date"] for a in activities if a.get("date")))
    resolved_as_of = as_of or (dated[-1] if dated else None)
    if resolved_as_of is None:
        return _empty_result(band, months, half_life_days, None,
                              "aucune séance datée dans l'historique fourni", "no_data")
    from datetime import date as _date, timedelta as _timedelta
    ref = _date.fromisoformat(resolved_as_of)
    window_start = ref - _timedelta(days=round(months * 30.4375))  # mois moyen (365,25/12 j)
    per_activity = []
    for act in activities:
        act_date = act.get("date")
        if not act_date:
            continue
        try:
            if _date.fromisoformat(act_date) < window_start:
                continue
        except ValueError:
            continue
        bins = act.get("bins") or {}
        if bins:
            per_activity.append({"activity_id": act.get("activity_id"), "date": act_date, "bins": bins})
    if not per_activity:
        return _empty_result(
            band, months, half_life_days, resolved_as_of,
            f"aucune séance exploitable dans la fenêtre des {months} derniers mois pour la bande « {band} »",
            "no_data_in_window")
    combined = combine_activity_summaries(per_activity, as_of=resolved_as_of, half_life_days=half_life_days)
    result = apply_fallback_and_smoothing(combined)
    result.update({
        "band": band, "months": months, "half_life_days": half_life_days, "as_of": resolved_as_of,
        "n_activities": len(per_activity),
    })
    return result


def fit_slope_model(activities: Sequence[dict], *, band: str = "endurance",
                     months: int = DEFAULT_MONTHS, half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
                     easy_hr_bpm: Optional[float] = None, as_of: Optional[str] = None,
                     resolution_s: float = G.DEFAULT_RESOLUTION_S) -> dict:
    """Bout en bout, pure (aucun accès disque/SQLite) : `activities` est une
    séquence de `{"activity_id", "date" (AAAA-MM-JJ), "series"}` où `series`
    est déjà augmentée par `arc_gap.gap_sample_series` — voir
    `recompute_slope_model` (`arc_index.py`, CLI `slope-model --months`) pour
    comment cette liste est construite à partir d'un workspace réel, et
    `tests/data/test_slope_model.py` pour l'usage direct depuis des séances
    synthétiques (`tests/lib/synthetic.py`). `arc_index.compute_metrics`, lui,
    emprunte le chemin plus économique `fit_from_activity_bins` (voir
    ASSUMPTIONS['aggregation_cost']).

    `as_of` (défaut : date la plus récente de `activities`) borne la fenêtre de
    `months` mois ET sert de référence d'âge pour la pondération par récence.

    Rend `{"band", "months", "half_life_days", "as_of", "n_activities", "bins",
    "flat_reference_speed_ms", "reason", "reason_code"}` — TOUJOURS ce dict,
    jamais d'exception : une population vide rend `bins: []` avec une raison
    explicite plutôt qu'un plantage."""
    if band not in BANDS:
        return _empty_result(band, months, half_life_days, as_of,
                              f"bande « {band} » inconnue (attendu : {', '.join(BANDS)})", "unknown_band")
    if band == "endurance" and easy_hr_bpm is None:
        return _empty_result(
            band, months, half_life_days, as_of,
            "aucun seuil FC facile/modéré résolu pour l'athlète (profil sans FC max/repos/seuil "
            "renseignée) — le modèle 'endurance' ne peut restreindre aucun échantillon", "no_hr_threshold")
    with_bins = []
    for act in activities:
        bins = activity_bin_summaries(act.get("series") or [], band=band, easy_hr_bpm=easy_hr_bpm,
                                       resolution_s=resolution_s)
        with_bins.append({"activity_id": act.get("activity_id"), "date": act.get("date"), "bins": bins})
    return fit_from_activity_bins(with_bins, band=band, months=months, half_life_days=half_life_days,
                                   easy_hr_bpm=easy_hr_bpm, as_of=as_of)


def predict_speed(grade: Optional[float], bins: Sequence[dict]) -> dict:
    """Accesseur PUR pour #59/#60/#61 : `bins` est la liste `model["bins"]`
    rendue par `fit_slope_model` (ou relue depuis `slope_model_bin`, même
    forme). Interpolation linéaire entre les points milieux des deux paniers
    encadrant `grade` (voir ASSUMPTIONS['interpolation']) ; extrapolation
    plate au-delà. `grade=None` ou `bins` vide -> résultat sans vitesse,
    `reason_code` explicite, jamais d'exception."""
    if grade is None:
        return {"speed_ms": None, "pace_s_km": None, "hr_bpm": None, "source": None,
                "ci_low_speed_ms": None, "ci_high_speed_ms": None, "reason": "pente inconnue",
                "reason_code": "no_grade"}
    ordered = sorted(bins, key=lambda b: b["grade_mid"])
    if not ordered:
        return {"speed_ms": None, "pace_s_km": None, "hr_bpm": None, "source": None,
                "ci_low_speed_ms": None, "ci_high_speed_ms": None,
                "reason": "aucun panier disponible (modèle non ajusté)", "reason_code": "no_model"}
    mids = [b["grade_mid"] for b in ordered]
    if len(ordered) == 1 or grade <= mids[0]:
        lo_b = hi_b = ordered[0]
        frac = 0.0
    elif grade >= mids[-1]:
        lo_b = hi_b = ordered[-1]
        frac = 0.0
    else:
        idx = bisect.bisect_right(mids, grade)
        lo_b, hi_b = ordered[idx - 1], ordered[idx]
        span = hi_b["grade_mid"] - lo_b["grade_mid"]
        frac = (grade - lo_b["grade_mid"]) / span if span else 0.0

    def _interp(key: str) -> Optional[float]:
        lv, hv = lo_b.get(key), hi_b.get(key)
        if lv is None or hv is None:
            return lv if lv is not None else hv
        return lv + frac * (hv - lv)

    speed = _interp("speed_ms")
    # Pile sur le point milieu d'un panier (`frac` à 0 ou 1) : le résultat vient
    # ENTIÈREMENT de ce panier, jamais un mélange avec son voisin (revue de code) —
    # `source: "mixed"` ne doit signaler qu'une VRAIE interpolation entre deux
    # paniers de provenances différentes, pas un cas où l'un des deux ne pèse rien.
    if frac <= 0.0:
        source = lo_b["source"]
    elif frac >= 1.0:
        source = hi_b["source"]
    else:
        source = lo_b["source"] if lo_b["source"] == hi_b["source"] else "mixed"
    return {
        "speed_ms": speed, "pace_s_km": (1000.0 / speed) if speed else None,
        "hr_bpm": _interp("hr_bpm"), "source": source,
        "ci_low_speed_ms": _interp("ci_low_speed_ms"), "ci_high_speed_ms": _interp("ci_high_speed_ms"),
        "reason": None, "reason_code": None,
    }
