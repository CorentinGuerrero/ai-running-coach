#!/usr/bin/env python3
"""Débrief post-course : plan vs réalisé, par segment (#61, épopée #23).

## Pourquoi

Aucun concurrent ne débriefe une course contre son PROPRE plan. Ce module
compare un `race_plan` (#59, `scripts/arc_race_pacing.py`, champ `segments`,
identifiants `s01`, `s02`… stables) à l'activité RÉELLEMENT enregistrée pour
cette course, segment par segment : écart d'allure, dérive cumulée, fade de
fin de course (mesuré vs prévu), glucides/h réalisés vs visés, météo réelle
vs prévue si les deux sont connues, et temps de ravitaillement quand des
échantillons FIT (#42) permettent de détecter un arrêt — jamais une valeur
inventée.

`#59` a délibérément rendu la segmentation du plan DÉTERMINISTE pour un même
GPX et un même découpage, précisément pour que ce module puisse aligner un
segment mesuré après course avec le même segment du plan sans recalculer sa
propre segmentation — voir `scripts/arc_race_pacing.py::ASSUMPTIONS["segmentation"]`.

## Alignement plan / réalisé (voir `ASSUMPTIONS["alignment"]`)

Le plan et l'activité mesurent la même course avec deux appareils différents
(le GPX analysé pour construire le plan, la montre le jour J) : leur distance
totale mesurée diffère presque toujours un peu (bruit GPS, filtrage différent).
Comparer des DISTANCES CUMULÉES brutes déciderait donc, à tort, qu'un segment
« finit » avant ou après son vrai emplacement sur le parcours réel. La règle
retenue : les distances cumulées des splits de l'activité sont mises à
l'échelle PROPORTIONNELLEMENT (`plan_distance_m / activity_distance_m`) pour
que le total de l'activité coïncide EXACTEMENT avec le total du plan — jamais
le temps, qui reste la mesure de vérité — **sauf écart extrême**
(`DISTANCE_MISMATCH_NO_SCALE_PCT`, 10 %, voir `ASSUMPTIONS["truncated"]`),
signe probable d'un abandon ou d'un enregistrement tronqué plutôt que d'un
simple bruit GPS : la mise à l'échelle est alors abandonnée, seuls les
segments réellement couverts sont comparés. Le temps cumulé réel à la borne
de chaque segment du plan est ensuite obtenu par interpolation linéaire entre
les deux points de split (de l'activité, mis à l'échelle) qui l'encadrent —
voir `ASSUMPTIONS["resolution"]` pour ce que cette interpolation NE permet PAS
de conclure en dessous de la granularité des splits.

## Base de temps (`time_basis`, voir `ASSUMPTIONS["time_basis"]`)

Le contrat ne précise pas si `activity.splits[].duration_s` est un temps
ÉCOULÉ (inclut les arrêts) ou un temps CHRONO (mis en pause automatiquement,
Garmin « auto pause »). Ce module SUPPOSE un temps écoulé — l'hypothèse la
plus courante pour un lap Garmin sans auto-pause activée, et celle qui rend
la comparaison au plan cohérente (le plan ajoute, lui, le temps de ravito
prévu au segment qui l'atteint, voir `ASSUMPTIONS["aid_stations"]`). Le champ
`time_basis` du résultat rend cette hypothèse explicite plutôt que de la
laisser implicite dans le calcul. Une activité enregistrée avec auto-pause
sous-estimera alors le temps réellement écoulé aux ravitos — fournir `--fit`
(échantillons seconde par seconde, horodatés en temps réel) lève l'ambiguïté :
l'alignement se fait alors directement sur les échantillons, jamais sur les
splits km.

## Résolution insuffisante (`resolution`, voir `ASSUMPTIONS["resolution"]`)

Un segment du plan plus court que la granularité des données disponibles
(typiquement les splits kilométriques) ne peut pas recevoir un temps réel
FIABLE par simple interpolation linéaire — le partage du temps d'un même
kilomètre entre deux segments suppose une allure constante à l'intérieur de
ce kilomètre, une hypothèse qu'aucune donnée ne vérifie. Un tel segment est
marqué `"resolution": "low"` et EXCLU des `findings` (jamais de la sortie
elle-même — l'agent peut toujours le montrer, avec la réserve appropriée).
Fournir `--fit` (échantillons fins) lève cette limite pour la quasi-totalité
des segments d'un plan réel.

## Ce qui n'est JAMAIS inventé

- **Temps aux ravitos** : seulement si un fichier d'échantillons FIT (#42,
  `--fit`) est fourni ET qu'un arrêt y est détecté à proximité d'un ravito du
  plan. Sans `--fit`, la clé `aid_station_times` est absente du résultat —
  jamais une durée par défaut.
- **Glucides/h prévus** : aucun champ structuré du contrat ne porte
  aujourd'hui un objectif glucides/h de plan de course (le plan nutrition du
  stratège de course reste un fichier texte libre, voir `agents/course-strategist.md`
  ÉTAPE 5) — l'appelant (l'agent coach) passe l'objectif via `--carbs-target-g-h`
  s'il en connaît un (typiquement le plan nutrition écrit par l'athlète ou le
  stratège de course — **pas** le plafond `carbs_ceiling_g_h` de
  `scripts/arc_index.py fueling`, qui est une autre grandeur, voir
  `--carbs-ceiling-g-h`) ; sans lui, la comparaison glucides est omise (jamais
  une cible inventée).
- **Météo réelle vs prévue** : seulement si les DEUX fichiers `weather` (#
  prévu au moment du plan, réel du jour J) sont fournis explicitement
  (`--planned-weather`/`--actual-weather`) — le contrat ne conserve pas la
  météo utilisée par `arc_race_pacing.py` dans le bloc `race_plan` persisté.

## Conclusions (`findings`, voir `ASSUMPTIONS["findings"]`)

Règles simples, à seuils documentés, PROPOSÉES à l'athlète — jamais écrites
seules dans `planning/Runner_Profile.md` (fichier édité par l'athlète, voir
`skills/workspace-data-contract/SKILL.md`) : `suggested_profile_updates` reste
une liste de PROPOSITIONS que l'agent doit présenter, jamais appliquer
silencieusement.

Stdlib uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arc_contract as C  # noqa: E402
import arc_metrics as M  # noqa: E402
import arc_race_pacing as RP  # noqa: E402
import arc_samples as SA  # noqa: E402

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_SCENARIO = "realistic"

# Au-delà de cet écart (%) entre distance mesurée de l'activité et distance du
# plan, un avertissement est émis (la mise à l'échelle proportionnelle reste
# appliquée en dessous de DISTANCE_MISMATCH_NO_SCALE_PCT, voir
# ASSUMPTIONS["alignment"]) — approximation du projet, jamais une règle GPS
# vérifiable.
DISTANCE_MISMATCH_WARN_PCT = 3.0

# Au-delà de cet écart, la mise à l'échelle est ABANDONNÉE (revue de code,
# BLOQUANT) : un tel écart sent l'abandon ou l'enregistrement tronqué, pas le
# bruit GPS habituel — mettre à l'échelle grossirait ARTIFICIELLEMENT les
# segments non parcourus au lieu de les signaler comme non atteints. Voir
# ASSUMPTIONS["truncated"].
DISTANCE_MISMATCH_NO_SCALE_PCT = 10.0

# Fade (voir ASSUMPTIONS["fade"]) : même repère 1ère moitié / 2ᵉ moitié en
# DISTANCE que la définition usuelle du fade de course (contrairement au fade
# d'ENTRAÎNEMENT de `arc_durability`/`arc_race_pacing`, qui compare 1er et
# dernier TIERS d'une sortie longue) — un débrief de course compare la course
# entière, pas seulement sa fin.
FADE_HALF_FRACTION = 0.5

# Départ trop rapide (`ASSUMPTIONS["findings"]`) : approximation du projet,
# aucune source vérifiable ne fixe ces seuils précis pour CE calcul — ils
# encadrent un ordre de grandeur raisonnable (départ nettement plus vite que
# prévu, suivi d'un fade nettement supérieur à celui déjà anticipé par le plan).
FAST_START_DELTA_PCT_THRESHOLD = -5.0
FAST_START_FADE_EXCESS_PCT_THRESHOLD = 3.0
FAST_START_FRACTION = 1.0 / 3.0  # même repère « premier tiers » que arc_race_pacing (fade)

# Glucides (approximation du projet) : sous l'objectif de plus de cette marge
# relative, signalé comme sous-alimentation ; au-dessus du plafond connu
# (`--carbs-ceiling-g-h`, repris de `scripts/arc_index.py fueling`), signalé
# comme dépassement — jamais une preuve de trouble digestif, voir
# `arc_metrics.ASSUMPTIONS["fueling"]` (« toléré » = « ingéré sans incident
# signalé », jamais une mesure de tolérance).
CARBS_UNDER_TARGET_TOLERANCE_PCT = 15.0

# Détection d'arrêt sur échantillons FIT (#42) — approximation du projet,
# jamais une mesure GPS certifiée.
#
# Deux mécanismes, indépendants et cumulés (revue de code, BLOQUANT #4) :
# 1. `STOP_SPEED_MS_THRESHOLD`/`STOP_MIN_DURATION_S` : vitesse quasi nulle
#    soutenue — capte un arrêt enregistré NORMALEMENT (l'appareil continue
#    d'échantillonner pendant l'arrêt). **Attention** : une montée très raide
#    en marche rapide (power hiking) peut approcher ce seuil sans être un
#    arrêt — `AID_STATION_MATCH_RADIUS_M` limite le risque de faux positif à
#    la seule proximité immédiate d'un ravito du plan, jamais n'importe où sur
#    le parcours.
# 2. `STOP_DISTANCE_EPS_M` (détection par quasi-absence de distance
#    parcourue entre deux échantillons, quelle que soit la vitesse
#    rapportée) : capte en PLUS une auto-pause Garmin, où l'appareil peut ne
#    RIEN enregistrer pendant l'arrêt — le prochain échantillon reprend avec
#    un grand écart de `t_s` mais presque aucune distance supplémentaire.
STOP_SPEED_MS_THRESHOLD = 0.3
STOP_MIN_DURATION_S = 20.0
STOP_DISTANCE_EPS_M = 5.0
AID_STATION_MATCH_RADIUS_M = 400.0

# Résolution insuffisante (`ASSUMPTIONS["resolution"]`) : un segment est jugé
# fiable seulement si sa longueur atteint ce facteur fois le plus grand
# intervalle de données (splits ou échantillons) dans lequel une de ses deux
# bornes tombe SANS coïncider avec un point réel (voir `_boundary_span_m`) —
# approximation du projet, prudente par construction : mieux vaut exclure un
# segment fiable par excès de prudence qu'inventer un écart sur un segment qui
# ne l'est pas.
LOW_RESOLUTION_SPAN_FACTOR = 2.0
EXACT_BOUNDARY_TOLERANCE_M = 1.0

ASSUMPTIONS = {
    "alignment": (
        "Le plan (GPX analysé en amont) et l'activité réelle (montre le jour J) mesurent presque "
        "toujours des distances totales légèrement différentes pour le même parcours (bruit GPS, "
        "filtrage différent). Comparer des distances cumulées brutes déciderait à tort qu'un segment "
        "finit avant/après son vrai emplacement réel. Règle retenue : les distances cumulées des "
        "splits de l'activité sont mises à l'échelle PROPORTIONNELLEMENT — jamais le temps — par "
        "`plan_distance_m / activity_distance_m`, pour que le total de l'activité coïncide EXACTEMENT "
        "avec celui du plan, SAUF au-delà de `DISTANCE_MISMATCH_NO_SCALE_PCT` (10 %, voir "
        "ASSUMPTIONS['truncated']). Le temps cumulé réel à chaque borne de segment est ensuite "
        "interpolé LINÉAIREMENT entre les deux points de split encadrants (mis à l'échelle) — "
        "hypothèse d'allure constante à l'intérieur d'un même kilomètre de split, la plus fine "
        "granularité disponible dans le contrat (`activity.splits`), voir ASSUMPTIONS['resolution'] "
        "pour ce que cette hypothèse ne permet PAS de conclure. Un écart de distance au-delà de "
        "`DISTANCE_MISMATCH_WARN_PCT` (3 %) déclenche un avertissement (qualité GPS à vérifier), mais "
        "la mise à l'échelle est appliquée en dessous du seuil de troncature."
    ),
    "truncated": (
        "Au-delà de `DISTANCE_MISMATCH_NO_SCALE_PCT` (10 %), l'écart de distance ne ressemble plus à du "
        "bruit GPS mais à un abandon ou un enregistrement tronqué (montre arrêtée avant l'arrivée, "
        "activité coupée) — mettre quand même à l'échelle grossirait ARTIFICIELLEMENT les segments non "
        "réellement parcourus pour leur faire atteindre la distance du plan. La mise à l'échelle est "
        "alors abandonnée (`scale_factor: 1.0`) : chaque segment dont la borne de fin dépasse la "
        "distance RÉELLEMENT mesurée par l'activité est marqué `\"status\": \"not_reached\"` (aucun "
        "temps ni delta calculé pour lui), et un avertissement explicite est ajouté."
    ),
    "time_basis": (
        "Le contrat ne précise pas si `activity.splits[].duration_s` est un temps ÉCOULÉ (inclut les "
        "arrêts) ou un temps CHRONO (auto-pause Garmin, qui exclut les arrêts). Ce module suppose un "
        "temps écoulé (`time_basis: \"elapsed_assumed\"` dans le résultat) — cohérent avec le temps "
        "planifié, qui inclut lui-même l'arrêt ravito prévu dans le segment qui l'atteint (voir "
        "ASSUMPTIONS['aid_stations']). Une activité enregistrée avec auto-pause sous-estimera le temps "
        "réellement écoulé aux ravitos et biaisera la comparaison à la baisse sur les segments "
        "concernés — fournir `--fit` (échantillons horodatés en temps réel) lève l'ambiguïté en "
        "s'alignant directement sur eux plutôt que sur les splits."
    ),
    "resolution": (
        "Un segment du plan (#59, souvent plus court qu'un kilomètre de split) ne peut recevoir un "
        "temps réel FIABLE par interpolation linéaire que si au moins une de ses bornes coïncide avec "
        "un point de donnée réel (split ou échantillon) — sinon, le temps qui lui est attribué suppose "
        "une allure CONSTANTE à l'intérieur de l'intervalle qui l'encadre, une hypothèse qu'aucune "
        "donnée ne vérifie et qui peut inventer un écart entièrement artefactuel (ex. +16 %/-10 % entre "
        "deux segments adjacents d'un kilomètre couru à allure parfaitement régulière). Un segment est "
        "marqué `\"resolution\": \"low\"` dès que sa longueur est inférieure à "
        "`LOW_RESOLUTION_SPAN_FACTOR` (2×) fois le plus grand intervalle de données interpolé à l'une de "
        "ses bornes (`_boundary_span_m`, 0 si la borne coïncide avec un point réel à "
        "`EXACT_BOUNDARY_TOLERANCE_M` près) — jamais un simple seuil de distance absolue, pour qu'un "
        "segment dont les bornes tombent PAR CONSTRUCTION sur des points réels (ex. alignées sur les "
        "kilomètres) reste `\"high\"` quelle que soit sa longueur. Les segments `\"low\"` restent dans "
        "la sortie (jamais masqués) mais sont EXCLUS des `findings` — fournir `--fit` (résolution fine) "
        "lève cette limite pour la quasi-totalité des segments d'un plan réel."
    ),
    "fade": (
        "Compare la 1ère moitié à la 2ᵉ moitié de la DISTANCE TOTALE (pas le dernier tiers d'une sortie "
        "d'entraînement comme `arc_durability`/`arc_race_pacing` : un débrief de course compare la "
        "course entière). `fade_actual_pct`/`fade_planned_pct` : écart relatif de l'allure moyenne de la "
        "2ᵉ moitié par rapport à la 1ère (positif = ralentissement). `fade_vs_plan_pct` = fade réel moins "
        "fade déjà anticipé par le plan (temps planifiés PAR SEGMENT, arrêts ravito inclus comme "
        "`ASSUMPTIONS['aid_stations']`). Absent si un segment du plan n'a pas de `predicted_time_s` pour "
        "le scénario choisi (rien à comparer côté plan)."
    ),
    "aid_stations": (
        "#59 (`arc_race_pacing.compute_passages`) exclut le temps de ravito de `segments[].predicted_time_s` "
        "— il n'est ajouté qu'au CUMUL, au moment où la barrière du ravito est franchie. Comparer "
        "directement le temps de split ÉCOULÉ (qui, lui, inclut tout arrêt réel) au `predicted_time_s` "
        "brut du segment sous-estimerait donc systématiquement le plan sur tout segment contenant un "
        "ravito, produisant un faux `depart_trop_rapide` et un delta artificiellement positif. Ce module "
        "réplique la RÈGLE D'ASSIGNATION exacte de `compute_passages` (un ravito est ajouté au cumul dès "
        "que sa borne km est atteinte, jamais dupliqué) pour ajouter, au temps planifié du segment "
        "concerné, l'arrêt prévu (`stop_s` du ravito si fourni, sinon "
        "`arc_race_pacing.DEFAULT_AID_STATION_STOP_S`) — appliqué de façon cohérente aux temps de "
        "segment, aux totaux ET au fade planifié. Le total planifié ainsi obtenu (segments + arrêts) est "
        "comparé, à titre de garde-fou, au `scenarios` du plan persisté quand il existe : un écart "
        "notable est signalé (arrondi/segmentation different de celui utilisé pour écrire le plan), "
        "jamais une erreur bloquante (le plan lui-même arrondit à la minute par cumul, voir "
        "`arc_race_pacing.PASSAGE_ROUND_S`)."
    ),
    "findings": (
        "Règles simples à seuils documentés (approximation du projet, aucune littérature vérifiable ne "
        "fixe ces valeurs précises) : `depart_trop_rapide` si le delta PONDÉRÉ PAR LE RECOUVREMENT en "
        "distance avec le premier tiers de course (pas seulement les segments ENTIÈREMENT contenus dans "
        "ce tiers — un segment plus grossier qui déborde compte pour la part qu'il recouvre, revue de "
        "code #9) est sous `FAST_START_DELTA_PCT_THRESHOLD` (-5 %, départ nettement plus vite que prévu) "
        "ET que `fade_vs_plan_pct` dépasse `FAST_START_FADE_EXCESS_PCT_THRESHOLD` (+3 points, fade "
        "nettement supérieur à celui déjà anticipé) — les deux conditions ensemble, jamais l'une seule. "
        "Seuls les segments `resolution: \"high\"` entrent dans ce calcul (voir ASSUMPTIONS['resolution']). "
        "Glucides : `glucides_sous_objectif` si le débit réalisé est sous l'objectif de plus de "
        "`CARBS_UNDER_TARGET_TOLERANCE_PCT` (15 %) ; `glucides_au_dessus_plafond` si le débit réalisé "
        "dépasse le plafond connu (`--carbs-ceiling-g-h`) — jamais présenté comme un trouble digestif "
        "prouvé, seulement `sans incident signalé ailleurs`. Toujours un `ecart_temps_total` informatif, "
        "même sans écart notable. `suggested_profile_updates` reste une liste de PROPOSITIONS : l'agent "
        "doit les présenter à l'athlète, jamais les écrire seul dans `planning/Runner_Profile.md`."
    ),
}


class DebriefError(ValueError):
    """Donnée d'entrée manquante ou incohérente pour construire un débrief."""


# ---------------------------------------------------------------------------
# Lecture des fichiers ```arc
# ---------------------------------------------------------------------------

def load_block(path: Path, *, expected_kind: str) -> dict:
    if not path.exists():
        raise DebriefError(f"fichier introuvable : {path}")
    text = path.read_text(encoding="utf-8")
    data = C.extract_block(text)
    if data is None:
        raise DebriefError(f"{path} : aucun bloc ```arc trouvé")
    kind = data.get("kind")
    if kind != expected_kind:
        raise DebriefError(f"{path} : kind={kind!r} trouvé, {expected_kind!r} attendu")
    return data


# ---------------------------------------------------------------------------
# Alignement distance/temps — depuis les splits km
# ---------------------------------------------------------------------------

# Tolérance (m) autour de `activity.distance_m` pour accepter la distance
# DÉDUITE du dernier split (revue de code, BLOQUANT #1) — un léger dépassement
# de 1000 m reste plausible (le dernier km peut être marginalement plus long
# que 1000 m sur un tracé bruité), un écart plus large sent une incohérence
# entre `distance_m` et le nombre de splits.
LAST_SPLIT_DISTANCE_TOLERANCE_M = 50.0


def build_actual_checkpoints(activity: dict, warnings: Optional[List[str]] = None) -> List[Tuple[float, float]]:
    """Points `(distance_m_cumulée, temps_s_cumulé)` de l'activité, un par split
    (voir `activity.splits`/`splits_cols`), triés par km croissant, avec `(0, 0)`
    en tête.

    `distance_m` du split s'il est renseigné (dernier split partiel). Sinon,
    pour le DERNIER split seulement, déduit de `activity.distance_m −
    1000·(n−1)` (même principe que `arc_metrics.best_efforts`, revue de code
    #1 BLOQUANT — compter systématiquement 1000 m produit un split final
    fantaisiste dès que la course ne fait pas un nombre entier de km, ce qui
    fausse ensuite toute la mise à l'échelle). Une distance déduite hors de
    `(0, 1000 + LAST_SPLIT_DISTANCE_TOLERANCE_M]` lève une erreur explicite
    (incohérence probable entre `distance_m` et le nombre de splits) plutôt
    que de fausser silencieusement l'alignement. Sans `activity.distance_m` du
    tout, replie sur 1000 m pour le dernier split et l'annonce dans
    `warnings` (jamais silencieux) si une liste y est passée.

    Lève `DebriefError` si l'activité n'a aucun split exploitable ou si un
    split n'a pas de `duration_s`."""
    rows = C.split_rows(activity)
    if not rows:
        raise DebriefError("activité sans splits (`splits`/`splits_cols`) : impossible d'aligner par segment")
    rows = sorted(rows, key=lambda r: r.get("km", 0))
    n = len(rows)
    activity_distance_m = activity.get("distance_m")
    checkpoints: List[Tuple[float, float]] = [(0.0, 0.0)]
    cum_d = cum_t = 0.0
    for i, row in enumerate(rows):
        duration = row.get("duration_s")
        if duration is None:
            raise DebriefError(f"split km={row.get('km')} sans duration_s")
        distance = row.get("distance_m")
        if distance is None:
            if i == n - 1 and activity_distance_m is not None:
                distance = activity_distance_m - 1000.0 * (n - 1)
                if not 0.0 < distance <= 1000.0 + LAST_SPLIT_DISTANCE_TOLERANCE_M:
                    raise DebriefError(
                        f"activity.distance_m ({activity_distance_m} m) incohérent avec {n} splits sans "
                        f"distance_m explicite : dernier split déduit à {distance:.0f} m, hors plage "
                        "plausible (0-1050 m) — vérifier le nombre de splits ou renseigner distance_m"
                    )
            else:
                distance = 1000.0
                if i == n - 1 and warnings is not None:
                    warnings.append(
                        "dernier split sans distance_m et activity.distance_m absent : 1000 m supposé par "
                        "défaut — potentiellement faux si la course ne fait pas un nombre entier de km."
                    )
        cum_d += float(distance)
        cum_t += float(duration)
        checkpoints.append((cum_d, cum_t))
    return checkpoints


def _interpolate_cum_time(checkpoints: Sequence[Tuple[float, float]], target_m: float) -> float:
    """Temps cumulé (s) à `target_m` par interpolation linéaire entre les deux
    points de `checkpoints` (croissants, `(0, 0)` en tête) qui l'encadrent —
    voir `ASSUMPTIONS["alignment"]`. Clampé aux bornes si `target_m` déborde
    (ne devrait pas arriver après mise à l'échelle sur la distance totale du
    plan, sauf incohérence des données d'entrée)."""
    if target_m <= checkpoints[0][0]:
        return checkpoints[0][1]
    for i in range(1, len(checkpoints)):
        d0, t0 = checkpoints[i - 1]
        d1, t1 = checkpoints[i]
        if target_m <= d1 + 1e-9:
            if d1 - d0 <= 0:
                return t1
            frac = (target_m - d0) / (d1 - d0)
            return t0 + frac * (t1 - t0)
    return checkpoints[-1][1]


def _boundary_span_m(checkpoints: Sequence[Tuple[float, float]], target_m: float,
                      tol_m: float = EXACT_BOUNDARY_TOLERANCE_M) -> float:
    """0.0 si `target_m` coïncide avec un point de donnée réel (à `tol_m`
    près) — aucune interpolation n'a lieu, le temps est directement connu.
    Sinon, la largeur (m) de l'intervalle entre les deux points qui
    l'encadrent — la borne a été devinée par interpolation linéaire à
    l'intérieur de cet intervalle (voir `ASSUMPTIONS["resolution"]`)."""
    if target_m <= checkpoints[0][0] + tol_m:
        return 0.0
    for i in range(1, len(checkpoints)):
        d0, _ = checkpoints[i - 1]
        d1, _ = checkpoints[i]
        if target_m <= d1 + 1e-6:
            if abs(target_m - d0) <= tol_m or abs(target_m - d1) <= tol_m:
                return 0.0
            return d1 - d0
    return 0.0


def segment_resolution(seg: dict, checkpoints: Sequence[Tuple[float, float]]) -> str:
    """`"high"`/`"low"` — voir `ASSUMPTIONS["resolution"]`."""
    km_start_m, km_end_m = seg["km_start"] * 1000.0, seg["km_end"] * 1000.0
    span = max(_boundary_span_m(checkpoints, km_start_m), _boundary_span_m(checkpoints, km_end_m))
    if span <= 0:
        return "high"
    return "low" if (km_end_m - km_start_m) < LOW_RESOLUTION_SPAN_FACTOR * span else "high"


def scale_checkpoints(checkpoints: Sequence[Tuple[float, float]], factor: float) -> List[Tuple[float, float]]:
    return [(d * factor, t) for d, t in checkpoints]


def _drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ---------------------------------------------------------------------------
# Ravitos (voir ASSUMPTIONS["aid_stations"])
# ---------------------------------------------------------------------------

def _planned_time_with_stops(segments: Sequence[dict], aid_stations: Sequence[dict],
                              scenario: str) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]:
    """Temps planifié PAR SEGMENT (`predicted_time_s[scenario]` + arrêt(s) de
    ravito qui l'atteignent, voir `ASSUMPTIONS["aid_stations"]`) et temps
    planifié CUMULÉ à la fin de chaque segment (arrêts compris), pleine
    précision (pas d'arrondi à la minute, contrairement à
    `arc_race_pacing.compute_passages`, pensé pour l'affichage). Même règle
    d'assignation de ravito que `compute_passages` : un ravito est ajouté au
    cumul dès que sa borne km est atteinte, jamais dupliqué. `None` pour un
    segment (et tous les suivants côté cumul) dès que `predicted_time_s` lui
    manque pour `scenario`."""
    aid_sorted = sorted((a for a in aid_stations if a.get("km") is not None), key=lambda a: a["km"])
    idx = 0
    cum = 0.0
    own: Dict[str, Optional[float]] = {}
    cumulative: Dict[str, Optional[float]] = {}
    broken = False
    for seg in segments:
        predicted = (seg.get("predicted_time_s") or {}).get(scenario)
        if predicted is None or broken:
            broken = True
            own[seg["id"]] = None
            cumulative[seg["id"]] = None
            continue
        stop_added = 0.0
        while idx < len(aid_sorted) and aid_sorted[idx]["km"] <= seg["km_end"] + 1e-9:
            stop_added += aid_sorted[idx].get("stop_s", RP.DEFAULT_AID_STATION_STOP_S)
            idx += 1
        own[seg["id"]] = predicted + stop_added
        cum += own[seg["id"]]
        cumulative[seg["id"]] = cum
    return own, cumulative


def detect_stops(samples: Sequence[dict], *,
                  speed_threshold_ms: float = STOP_SPEED_MS_THRESHOLD,
                  distance_eps_m: float = STOP_DISTANCE_EPS_M,
                  min_duration_s: float = STOP_MIN_DURATION_S) -> List[Tuple[float, float, float]]:
    """Rend une liste `(distance_m milieu, t_s début, durée_s)` pour chaque
    arrêt détecté dans `samples` (`t_s`/`distance_m`/`speed_ms` — format
    normalisé, voir `tests/README.md` section échantillons ; les échantillons
    sans `distance_m` OU `t_s` sont ignorés, jamais supposés à une valeur).
    Deux mécanismes indépendants, cumulés (voir `STOP_SPEED_MS_THRESHOLD`) :
    vitesse quasi nulle soutenue, ET quasi-absence de distance parcourue
    entre deux échantillons quelle que soit la vitesse rapportée (capte une
    auto-pause Garmin, qui peut ne rien enregistrer pendant l'arrêt)."""
    pts = sorted((s for s in samples if s.get("distance_m") is not None and s.get("t_s") is not None),
                 key=lambda s: s["t_s"])
    stops: List[Tuple[float, float, float]] = []

    # Mécanisme 1 : vitesse quasi nulle soutenue.
    with_speed = [s for s in pts if s.get("speed_ms") is not None]
    start = None
    for s in with_speed:
        if s["speed_ms"] < speed_threshold_ms:
            if start is None:
                start = s
        else:
            if start is not None:
                duration = s["t_s"] - start["t_s"]
                if duration >= min_duration_s:
                    mid_m = (start["distance_m"] + s["distance_m"]) / 2.0
                    stops.append((mid_m, start["t_s"], duration))
                start = None
    if start is not None and with_speed:
        last = with_speed[-1]
        duration = last["t_s"] - start["t_s"]
        if duration >= min_duration_s:
            stops.append((start["distance_m"], start["t_s"], duration))

    # Mécanisme 2 : quasi-absence de distance parcourue (auto-pause) — voir
    # docstring. Fonctionne même si `speed_ms` est absent.
    i, n = 0, len(pts)
    while i < n - 1:
        j = i + 1
        while j < n and (pts[j]["distance_m"] - pts[i]["distance_m"]) < distance_eps_m:
            j += 1
        duration = pts[j - 1]["t_s"] - pts[i]["t_s"]
        if duration >= min_duration_s:
            mid_m = (pts[i]["distance_m"] + pts[j - 1]["distance_m"]) / 2.0
            stops.append((mid_m, pts[i]["t_s"], duration))
        i = j if j > i + 1 else i + 1

    return stops


def aid_station_times(plan_aid_stations: Sequence[dict], samples: Sequence[dict],
                       *, sample_scale_factor: float = 1.0) -> List[dict]:
    """Associe à chaque ravito du plan (`{"km", "name", ...}`) l'arrêt détecté
    dans `samples` le plus proche (à moins de `AID_STATION_MATCH_RADIUS_M`,
    distance des échantillons mise à l'échelle par `sample_scale_factor` —
    même logique que les splits, voir `ASSUMPTIONS["alignment"]`). Un ravito
    sans arrêt détecté à proximité n'apparaît PAS dans le résultat (jamais une
    durée devinée)."""
    stops = detect_stops(samples)
    scaled_stops = [(m * sample_scale_factor, t, dur) for m, t, dur in stops]
    out = []
    for station in plan_aid_stations:
        km = station.get("km")
        if km is None:
            continue
        target_m = km * 1000.0
        best = None
        for mid_m, _t, dur in scaled_stops:
            if abs(mid_m - target_m) <= AID_STATION_MATCH_RADIUS_M and (best is None or dur > best):
                best = dur
        if best is not None:
            out.append({"km": km, "name": station.get("name"), "actual_stop_s": round(best, 1)})
    return out


# ---------------------------------------------------------------------------
# Échantillons FIT (#42) — normalisation et alignement fin
# ---------------------------------------------------------------------------

def build_checkpoints_from_samples(samples: Sequence[dict]) -> List[Tuple[float, float]]:
    """Points `(distance_m_cumulée, temps_s_cumulé)` depuis des échantillons
    déjà normalisés (`t_s`/`distance_m`, croissants), avec `(0, 0)` en tête —
    alignement à résolution fine (voir `ASSUMPTIONS["resolution"]`), en
    remplacement des splits km quand `--fit` est fourni. Les échantillons sans
    `distance_m` sont ignorés (jamais supposés). Lève `DebriefError` si aucun
    échantillon exploitable ne reste."""
    pts = sorted((s for s in samples if s.get("distance_m") is not None and s.get("t_s") is not None),
                 key=lambda s: s["t_s"])
    if not pts:
        raise DebriefError("échantillons FIT sans distance_m/t_s exploitables : impossible d'aligner dessus")
    t0 = pts[0]["t_s"]
    checkpoints: List[Tuple[float, float]] = [(0.0, 0.0)]
    d0 = pts[0]["distance_m"]
    for p in pts:
        checkpoints.append((max(0.0, p["distance_m"] - d0), max(0.0, p["t_s"] - t0)))
    return checkpoints


# ---------------------------------------------------------------------------
# Assemblage principal
# ---------------------------------------------------------------------------

def build_race_debrief(plan: dict, activity: dict, *,
                        scenario: str = DEFAULT_SCENARIO,
                        carbs_target_g_h: Optional[float] = None,
                        carbs_actual_g_h: Optional[float] = None,
                        carbs_ceiling_g_h: Optional[float] = None,
                        planned_weather: Optional[dict] = None,
                        actual_weather: Optional[dict] = None,
                        fit_samples: Optional[Sequence[dict]] = None) -> dict:
    """Assemble le débrief complet plan vs réalisé — pure (aucun accès disque),
    pour que la CLI et les tests partagent le même chemin de calcul.

    Lève `DebriefError` si le plan n'a pas de `segments` (#59 requis) ou si
    l'activité n'a pas de `splits` exploitables (sauf `fit_samples` fourni et
    exploitable, auquel cas l'alignement se fait dessus, jamais sur les
    splits)."""
    segments = sorted(plan.get("segments") or [], key=lambda s: s["km_start"])
    if not segments:
        raise DebriefError(
            "planning sans `segments` (#59, scripts/arc_race_pacing.py) : impossible de débriefer par "
            "segment — le plan doit avoir été construit à partir d'un GPX"
        )

    warnings: List[str] = []

    if activity.get("date") and plan.get("race_date") and activity["date"] != plan["race_date"]:
        warnings.append(
            f"date de l'activité ({activity['date']}) différente de la date de course du plan "
            f"({plan['race_date']}) — vérifier qu'il s'agit bien de la même course."
        )

    use_samples = fit_samples is not None and len(fit_samples) > 0
    if use_samples:
        checkpoints = build_checkpoints_from_samples(fit_samples)
        time_basis = "fit_samples"
    else:
        if fit_samples is not None and len(fit_samples) == 0:
            warnings.append(
                "--fit fourni mais aucun échantillon exploitable (distance_m/t_s manquants après "
                "normalisation) : alignement replié sur les splits km, aid_station_times omis."
            )
        checkpoints = build_actual_checkpoints(activity, warnings)
        time_basis = "elapsed_assumed"

    plan_total_m = segments[-1]["km_end"] * 1000.0
    actual_total_m = checkpoints[-1][0]
    if plan_total_m <= 0 or actual_total_m <= 0:
        raise DebriefError("distance totale du plan ou de l'activité nulle : rien à aligner")

    mismatch_pct = abs(actual_total_m - plan_total_m) / plan_total_m * 100.0
    truncated = mismatch_pct > DISTANCE_MISMATCH_NO_SCALE_PCT
    if truncated:
        scale_factor = 1.0
        warnings.append(
            f"distance mesurée de l'activité ({actual_total_m / 1000.0:.2f} km) et distance du plan "
            f"({plan_total_m / 1000.0:.2f} km) diffèrent de {mismatch_pct:.1f} % (> "
            f"{DISTANCE_MISMATCH_NO_SCALE_PCT:g} %) : probable abandon ou enregistrement tronqué — "
            "distances NON mises à l'échelle, seuls les segments réellement couverts sont comparés "
            "(voir ASSUMPTIONS['truncated'])."
        )
    else:
        scale_factor = plan_total_m / actual_total_m
        if mismatch_pct > DISTANCE_MISMATCH_WARN_PCT:
            warnings.append(
                f"distance mesurée de l'activité ({actual_total_m / 1000.0:.2f} km) et distance du plan "
                f"({plan_total_m / 1000.0:.2f} km) diffèrent de {mismatch_pct:.1f} % : les distances ont "
                "été mises à l'échelle proportionnellement (jamais le temps) pour s'aligner sur le "
                "référentiel du plan — voir ASSUMPTIONS['alignment']."
            )
    scaled_checkpoints = scale_checkpoints(checkpoints, scale_factor)
    covered_m = scaled_checkpoints[-1][0]

    aid_stations = plan.get("aid_stations") or []
    planned_own, planned_cumulative = _planned_time_with_stops(segments, aid_stations, scenario)

    segment_debriefs = []
    weighted_first_third_num = 0.0
    weighted_first_third_den = 0.0
    for seg in segments:
        km_start_m, km_end_m = seg["km_start"] * 1000.0, seg["km_end"] * 1000.0

        if truncated and km_end_m > covered_m + 1e-6:
            segment_debriefs.append({
                "id": seg["id"], "km_start": seg["km_start"], "km_end": seg["km_end"],
                "distance_m": seg.get("distance_m"), "status": "not_reached",
            })
            continue

        t_start = _interpolate_cum_time(scaled_checkpoints, km_start_m)
        t_end = _interpolate_cum_time(scaled_checkpoints, km_end_m)
        actual_time_s = t_end - t_start
        distance_km = (km_end_m - km_start_m) / 1000.0
        actual_pace_s_km = actual_time_s / distance_km if distance_km > 0 else None
        # Même fonction générique quelle que soit la source de données : des
        # échantillons FIT (fins) laissent presque tous les segments "high"
        # naturellement, sans traitement spécial (voir ASSUMPTIONS["resolution"]).
        resolution = segment_resolution(seg, scaled_checkpoints)

        planned = planned_own.get(seg["id"])
        planned_pace = (planned / distance_km) if planned is not None and distance_km > 0 else None

        entry = {
            "id": seg["id"], "km_start": seg["km_start"], "km_end": seg["km_end"],
            "distance_m": seg.get("distance_m"), "resolution": resolution,
            "actual_time_s": round(actual_time_s, 1),
            "actual_pace_s_km": round(actual_pace_s_km, 1) if actual_pace_s_km is not None else None,
            "planned_time_s": round(planned, 1) if planned is not None else None,
            "planned_pace_s_km": round(planned_pace, 1) if planned_pace is not None else None,
        }
        if planned is not None and planned > 0:
            delta_s = actual_time_s - planned
            entry["delta_s"] = round(delta_s, 1)
            entry["delta_pct"] = round(delta_s / planned * 100.0, 1)
            cum_planned = planned_cumulative.get(seg["id"])
            if cum_planned is not None:
                entry["cumulative_drift_s"] = round(t_end - cum_planned, 1)
            if resolution == "high":
                overlap_km = (min(km_end_m, plan_total_m * FAST_START_FRACTION) - km_start_m) / 1000.0
                if overlap_km > 0:
                    weighted_first_third_num += entry["delta_pct"] * overlap_km
                    weighted_first_third_den += overlap_km
        segment_debriefs.append(_drop_none(entry))

    total_actual_s = covered_m and _interpolate_cum_time(scaled_checkpoints, covered_m) or 0.0
    totals: Dict[str, float] = {"actual_time_s": round(total_actual_s, 1)}
    # Le temps planifié TOTAL (comparable à `total_actual_s`, à la distance
    # COUVERTE) n'a de sens que si le DERNIER segment réellement couvert (le
    # dernier tout court si la course n'est pas tronquée) a un cumul connu —
    # un trou de `predicted_time_s` plus tôt dans le plan rend tout ce qui
    # suit inconnu (`_planned_time_with_stops`), jamais une comparaison
    # partielle présentée comme complète.
    if truncated:
        last_covered = next((seg for seg in reversed(segments)
                              if seg["km_end"] * 1000.0 <= covered_m + 1e-6), None)
        last_cum_planned = planned_cumulative.get(last_covered["id"]) if last_covered else None
    else:
        last_cum_planned = planned_cumulative.get(segments[-1]["id"])

    if last_cum_planned is not None and not truncated:
        totals["planned_time_s"] = round(last_cum_planned, 1)
        totals["delta_s"] = round(total_actual_s - last_cum_planned, 1)
        totals["delta_pct"] = round(totals["delta_s"] / last_cum_planned * 100.0, 1)
        plan_scenario_time = (plan.get("scenarios") or {}).get(scenario)
        if plan_scenario_time:
            plan_mismatch_pct = abs(last_cum_planned - plan_scenario_time) / plan_scenario_time * 100.0
            if plan_mismatch_pct > 5.0:
                warnings.append(
                    f"le temps planifié recalculé (segments + arrêts ravito, {last_cum_planned:.0f} s) "
                    f"s'écarte de {plan_mismatch_pct:.1f} % du scénario {scenario!r} persisté dans le plan "
                    f"({plan_scenario_time:g} s) — plan potentiellement incohérent ou régénéré depuis."
                )
    elif last_cum_planned is not None:
        totals["planned_time_s_partial"] = round(last_cum_planned, 1)

    fade = _compute_fade(segments, scaled_checkpoints, plan_total_m, planned_cumulative, truncated, covered_m)

    carbs = {}
    resolved_actual_carbs = carbs_actual_g_h
    if resolved_actual_carbs is None:
        resolved_actual_carbs = M.carbs_per_hour_g(activity)
    if resolved_actual_carbs is not None:
        carbs["actual_g_h"] = round(resolved_actual_carbs, 1)
    if carbs_target_g_h is not None:
        carbs["planned_g_h"] = round(carbs_target_g_h, 1)
    if "actual_g_h" in carbs and "planned_g_h" in carbs and carbs["planned_g_h"]:
        carbs["delta_g_h"] = round(carbs["actual_g_h"] - carbs["planned_g_h"], 1)
        carbs["delta_pct"] = round(carbs["delta_g_h"] / carbs["planned_g_h"] * 100.0, 1)

    weather = {}
    if actual_weather:
        weather["actual"] = _weather_subset(actual_weather)
    if planned_weather:
        weather["planned"] = _weather_subset(planned_weather)

    aid_times = None
    if fit_samples is not None:
        if use_samples:
            aid_times = aid_station_times(aid_stations, fit_samples, sample_scale_factor=scale_factor)
        else:
            aid_times = []

    findings, suggested_profile_updates = _build_findings(
        weighted_first_third_num, weighted_first_third_den, fade,
        carbs, carbs_ceiling_g_h, totals,
    )

    result = {
        "race_name": plan.get("race_name"),
        "race_date": plan.get("race_date"),
        "scenario": scenario,
        "time_basis": time_basis,
        "segments": segment_debriefs,
        "totals": totals,
        "alignment": {
            "plan_distance_m": round(plan_total_m, 1),
            "actual_distance_m": round(actual_total_m, 1),
            "scale_factor": round(scale_factor, 4),
            "mismatch_pct": round(mismatch_pct, 2),
            "truncated": truncated,
        },
        "findings": findings,
        "suggested_profile_updates": suggested_profile_updates,
        "warnings": warnings,
    }
    if fade:
        result["fade"] = fade
    if carbs:
        result["carbs"] = carbs
    if weather:
        result["weather"] = weather
    if aid_times is not None:
        result["aid_station_times"] = aid_times
    return _drop_none(result)


def _weather_subset(weather: dict) -> dict:
    keys = ("temp_min_c", "temp_max_c", "feels_like_c", "humidity_pct", "wind_kmh", "category")
    return {k: weather[k] for k in keys if k in weather and weather[k] is not None}


def _compute_fade(segments: Sequence[dict], scaled_checkpoints: Sequence[Tuple[float, float]],
                   plan_total_m: float, planned_cumulative: Dict[str, Optional[float]],
                   truncated: bool, covered_m: float) -> dict:
    """Voir `ASSUMPTIONS["fade"]`. Rend un dict vide si les segments du plan
    n'ont pas tous un temps planifié connu (rien à comparer côté plan), ou si
    la course est tronquée (`ASSUMPTIONS["truncated"]` — comparer un fade sur
    une distance partielle n'a pas de sens)."""
    if truncated:
        return {}
    half_m = plan_total_m * FADE_HALF_FRACTION
    t_half_actual = _interpolate_cum_time(scaled_checkpoints, half_m)
    t_end_actual = scaled_checkpoints[-1][1]
    pace_first_half_actual = t_half_actual / (half_m / 1000.0) if half_m > 0 else None
    pace_second_half_actual = (
        (t_end_actual - t_half_actual) / (half_m / 1000.0) if half_m > 0 else None
    )
    fade: Dict[str, float] = {}
    if pace_first_half_actual and pace_first_half_actual > 0:
        fade["actual_pct"] = round(
            (pace_second_half_actual - pace_first_half_actual) / pace_first_half_actual * 100.0, 1)

    planned_checkpoints: List[Tuple[float, float]] = [(0.0, 0.0)]
    for seg in segments:
        cum = planned_cumulative.get(seg["id"])
        if cum is None:
            return _drop_none(fade) if "actual_pct" in fade else {}
        planned_checkpoints.append((seg["km_end"] * 1000.0, cum))

    t_half_planned = _interpolate_cum_time(planned_checkpoints, half_m)
    t_end_planned = planned_checkpoints[-1][1]
    pace_first_half_planned = t_half_planned / (half_m / 1000.0) if half_m > 0 else None
    pace_second_half_planned = (
        (t_end_planned - t_half_planned) / (half_m / 1000.0) if half_m > 0 else None
    )
    if pace_first_half_planned and pace_first_half_planned > 0:
        fade["planned_pct"] = round(
            (pace_second_half_planned - pace_first_half_planned) / pace_first_half_planned * 100.0, 1)
        if "actual_pct" in fade:
            fade["vs_plan_pct"] = round(fade["actual_pct"] - fade["planned_pct"], 1)
    return fade


def _build_findings(first_third_num: float, first_third_den: float, fade: dict,
                     carbs: dict, carbs_ceiling_g_h: Optional[float],
                     totals: dict) -> Tuple[List[dict], List[dict]]:
    findings: List[dict] = []
    suggested: List[dict] = []

    if "delta_pct" in totals:
        findings.append({
            "code": "ecart_temps_total",
            "severity": "info",
            "message": f"Temps total réalisé {totals['delta_pct']:+.1f} % vs plan "
                       f"({'plus rapide' if totals['delta_pct'] < 0 else 'plus lent'} que prévu).",
        })

    if first_third_den > 0 and "vs_plan_pct" in fade:
        avg_first_third_pct = first_third_num / first_third_den
        if avg_first_third_pct <= FAST_START_DELTA_PCT_THRESHOLD and \
                fade["vs_plan_pct"] >= FAST_START_FADE_EXCESS_PCT_THRESHOLD:
            findings.append({
                "code": "depart_trop_rapide",
                "severity": "warning",
                "message": (
                    f"Premier tiers de course {abs(avg_first_third_pct):.1f} % plus rapide que le plan, "
                    f"suivi d'un fade {fade['vs_plan_pct']:+.1f} points au-delà de celui déjà anticipé "
                    "par le plan : probable lien de cause à effet."
                ),
            })
            suggested.append({
                "field": "Préférences de coaching",
                "suggestion": "Ajouter une consigne d'allure de départ plus prudente sur les prochaines "
                               "courses (tendance à partir trop vite observée sur ce débrief).",
                "rationale": "depart_trop_rapide",
                "status": "proposed",
            })

    actual_g_h, planned_g_h = carbs.get("actual_g_h"), carbs.get("planned_g_h")
    if actual_g_h is not None and planned_g_h:
        if actual_g_h < planned_g_h * (1 - CARBS_UNDER_TARGET_TOLERANCE_PCT / 100.0):
            findings.append({
                "code": "glucides_sous_objectif",
                "severity": "warning",
                "message": f"Glucides réalisés ({actual_g_h:g} g/h) sous l'objectif ({planned_g_h:g} g/h) "
                           f"de plus de {CARBS_UNDER_TARGET_TOLERANCE_PCT:g} %.",
            })
    if actual_g_h is not None and carbs_ceiling_g_h and actual_g_h > carbs_ceiling_g_h:
        findings.append({
            "code": "glucides_au_dessus_plafond",
            "severity": "info",
            "message": f"Glucides réalisés ({actual_g_h:g} g/h) au-dessus du plafond connu "
                       f"({carbs_ceiling_g_h:g} g/h) — sans incident signalé ailleurs, jamais une preuve "
                       "de tolérance digestive.",
        })
        suggested.append({
            "field": "objectif glucides/h (entraînement digestif, #41)",
            "suggestion": f"Envisager de relever le plafond glucides/h au-delà de {carbs_ceiling_g_h:g} g/h "
                          f"— {actual_g_h:g} g/h ingérés sans incident signalé sur cette course.",
            "rationale": "glucides_au_dessus_plafond",
            "status": "proposed",
        })

    return findings, suggested


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Débrief post-course : plan vs réalisé, par segment (#61).")
    ap.add_argument("command", choices=("debrief",), help="sous-commande (seule « debrief » existe)")
    ap.add_argument("--plan", required=True, type=Path, help="fichier plan de course (kind: race_plan)")
    ap.add_argument("--activity", required=True, type=Path, help="fichier activité de la course (kind: activity)")
    ap.add_argument("--scenario", choices=("safe", "realistic", "ambitious"), default=DEFAULT_SCENARIO,
                     help="scénario du plan utilisé comme référence (défaut realistic)")
    ap.add_argument("--carbs-target-g-h", type=float, dest="carbs_target_g_h",
                     help="objectif glucides/h du plan nutrition (aucun champ structuré ne le porte, #61)")
    ap.add_argument("--carbs-actual-g-h", type=float, dest="carbs_actual_g_h",
                     help="débit glucides/h réalisé, si connu autrement que par activity.carbs_g/duration_s")
    ap.add_argument("--carbs-ceiling-g-h", type=float, dest="carbs_ceiling_g_h",
                     help="plafond glucides/h connu (scripts/arc_index.py fueling, carbs_ceiling_g_h)")
    ap.add_argument("--planned-weather", type=Path, dest="planned_weather",
                     help="fichier météo (kind: weather) prévue au moment du plan")
    ap.add_argument("--actual-weather", type=Path, dest="actual_weather",
                     help="fichier météo (kind: weather) réelle du jour de course")
    ap.add_argument("--fit", type=Path, help="fichier d'échantillons FIT (#42) : aligne dessus et détecte les "
                                              "arrêts ravito, plutôt que sur les splits km")
    return ap


def _load_fit_samples(path: Optional[Path]) -> Optional[List[dict]]:
    """Charge et normalise (`arc_samples.normalise_records`, revue de code #4)
    un fichier d'échantillons FIT — accepte aussi bien le format déjà
    normalisé (`activities/fit/<id>.json`) que le format brut fitparse produit
    par `skills/fit-download/scripts/download_fit.py --json`. `None` si
    `path` est `None` ; une liste VIDE (jamais `None`) si le fichier existe
    mais qu'aucun échantillon exploitable n'en ressort — la distinction
    permet à l'appelant de le signaler plutôt que de se taire (voir
    `build_race_debrief`). Lève `DebriefError` sur un JSON illisible."""
    if path is None:
        return None
    if not path.exists():
        raise DebriefError(f"fichier FIT introuvable : {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DebriefError(f"fichier FIT {path} : JSON invalide ({exc})") from exc
    return SA.normalise_records(raw)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        plan = load_block(args.plan, expected_kind="race_plan")
        activity = load_block(args.activity, expected_kind="activity")
        planned_weather = load_block(args.planned_weather, expected_kind="weather") if args.planned_weather else None
        actual_weather = load_block(args.actual_weather, expected_kind="weather") if args.actual_weather else None
        fit_samples = _load_fit_samples(args.fit)
        debrief = build_race_debrief(
            plan, activity, scenario=args.scenario,
            carbs_target_g_h=args.carbs_target_g_h, carbs_actual_g_h=args.carbs_actual_g_h,
            carbs_ceiling_g_h=args.carbs_ceiling_g_h,
            planned_weather=planned_weather, actual_weather=actual_weather,
            fit_samples=fit_samples,
        )
    except DebriefError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(debrief, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
