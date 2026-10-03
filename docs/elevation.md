# Correction altimétrique par MNT

> **Fonction optionnelle, désactivée par défaut (#176).** Aucune coordonnée ne quitte votre machine tant que vous ne l'avez pas demandé.

Le D+ alimente presque tout : GAP, modèle pente → allure, VAM, descente, durabilité, énergie, pacing de course, évaluation de parcours. Or l'altitude d'un GPX est bruitée (GPS seul) et celle d'un FIT dérive (baromètre) ; `scripts/arc_elevation.py` lisse le signal mais ne peut pas corriger un biais. La correction rééchantillonne la trace sur un **modèle numérique de terrain** (MNT) public.

## Sources de données

| Zone | Service | Données | Licence / attribution |
|---|---|---|---|
| France métropolitaine (boîte englobante approchée, Corse incluse) | [API d'altimétrie de la Géoplateforme](https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/calcul-altimetrique/) — `data.geopf.fr`, ressource `ign_rge_alti_wld`, sans clé | RGE ALTI®, pas de 1 m là où il est disponible | Licence Ouverte Etalab 2.0 — « Altitudes : IGN, RGE ALTI® via la Géoplateforme » |
| Ailleurs, et points que l'IGN ne couvre pas (`z = -99999`) | [Open-Meteo Elevation API](https://open-meteo.com/en/docs/elevation-api) — `api.open-meteo.com` | Copernicus DEM GLO-90 (pas de 90 m, altitudes entières) | Attribution obligatoire à Copernicus (DOI 10.5270/ESA-c5d3d65) et à Open-Meteo |

Limites de débit : IGN 5 requêtes/s par IP (documenté) — le module espace ses appels de 0,25 s ; Open-Meteo 100 coordonnées par requête, aucune limite de débit précisée par la page de documentation consultée (à vérifier avant un usage intensif, l'API gratuite est destinée à un usage non commercial). Les services ont été interrogés avec de vraies requêtes de 2 à 3 coordonnées publiques lors du développement ; les formes de réponse ci-dessus sont celles observées.

Les lignes d'attribution sont rendues avec chaque rapport (`analyze_gpx.py`, `arc_race_pacing.py`, `dem-check`) et doivent être reprises dans les fiches persistées.

## Vie privée — ce qui est envoyé

- **Uniquement des coordonnées** (latitude/longitude arrondies : 5 décimales IGN ≈ 1 m, 4 décimales Open-Meteo ≈ 11 m), par lots, **amincies** (un point tous les 50 m par défaut). Jamais d'identifiant, de date, de fréquence cardiaque, de nom de fichier ni de contenu du workspace. L'adresse IP de votre machine reste visible du fournisseur.
- **Parcours de course (GPX publiés)** : itinéraires publics, correction possible sur demande (`--dem`) ou en permanence avec `[elevation].dem = "auto"`.
- **Séances personnelles** : une trace d'activité révèle votre domicile. Elles ne sont interrogées qu'avec `[privacy].dem_for_activities = true`, et seulement par `arc_index.py dem-check`. Les **200 premiers et derniers mètres** ne sont jamais envoyés. Un GPX qui est l'enregistrement d'une de vos sorties n'est pas un « parcours public » : ne le passez pas à `--dem` sans y avoir réfléchi.
- Aucun envoi tant que les réglages sont à leur défaut.

## Réglages

```toml
[elevation]
dem = "off"        # "off" (défaut) | "auto" : corrige d'office les GPX de course
step_m = 50        # pas d'amincissement des coordonnées envoyées (5 à 500 m)
cache = true       # cache local <workspace>/.arc/dem-cache.json

[privacy]
dem_for_activities = false   # true = autorise `arc_index.py dem-check` sur une séance
```

À poser dans `config/workspace.user.toml` (voir [la configuration](configuration.md)). Une valeur invalide retombe sur le défaut prudent avec un avertissement.

## Utilisation

```bash
# Évaluation de parcours : le D+ MNT devient la référence, le D+ du fichier reste affiché
python3 skills/gpx-analysis/scripts/analyze_gpx.py --gpx course.gpx --dem

# Plan de course : les segments, les allures et l'énergie reposent sur l'altitude MNT
python3 scripts/arc_race_pacing.py plan --gpx course.gpx --dem ...

# Séance (opt-in [privacy].dem_for_activities) : comparaison seulement, rien n'est remplacé
python3 scripts/arc_index.py dem-check <garmin_activity_id | i<id intervals>>
```

`--no-dem` annule `[elevation].dem = "auto"` pour un appel. Exemple de rapport :

```text
## Correction altimétrique (MNT)
| | D+ fichier | D+ MNT (référence) | Écart |
| D+ | 1840 m | **1620 m** | -220 m (-12 %) |
```

### Pour une séance : proposer sans imposer

Le baromètre d'un FIT récent est souvent meilleur qu'un MNT (tunnels, ponts, galeries, arbres, maille de 90 m). `dem-check` rend donc **une comparaison** — D+ enregistré, D+ MNT, biais moyen (MNT − enregistré) — et **ne remplace ni n'écrit jamais** l'altitude enregistrée, ni dans l'index ni dans le Markdown. Un biais moyen persistant de plusieurs mètres signale un baromètre à recaler (calibration de la montre), pas un D+ à corriger après coup.

## Hors ligne et robustesse

- Réseau coupé, quota dépassé (HTTP 429/5xx : 3 essais, attente 1 s puis 2 s), réponse inattendue ou couverture < 80 % des points : **le comportement antérieur est conservé** (altitude du fichier), avec un avertissement explicite (`status = "unavailable"` dans `--json`). Jamais de valeur inventée.
- Cache local par fournisseur et coordonnée arrondie : un parcours déjà analysé ne refait aucun appel. Supprimez `.arc/dem-cache.json` pour le vider.

## Hypothèses et limites

Voir `scripts/arc_dem.py::ASSUMPTIONS` et `scripts/arc_elevation.py::ASSUMPTIONS["dem_series"]` :

- **Résolution** : un MNT donne l'altitude du terrain (RGE ALTI) ou de la surface (GLO-90 : cime des arbres et toits peuvent y entrer, erreur verticale de quelques mètres, pire en relief abrupt). Une crête étroite ou un fond de gorge plus fins que la maille sont lissés.
- **Erreur horizontale du GPS** : 5 à 10 m de décalage valent 1,5 à 3 m d'altitude sur 30 % de pente avec un MNT de 1 m.
- **Amincissement** : une ondulation plus courte que `step_m` n'est pas comptée ; le D+ MNT est une référence de terrain, pas un cumul brut de capteur. Il est calculé sans lissage ni seuil (série interpolée sans bruit), contrairement au D+ d'un GPX brut (lissage 3 points, seuil de 1 m).
- **Ponts, tunnels, galeries** : absents du MNT ; le parcours suit alors le sol.
