# 📝 Skill : `/log` — saisie libre

> **Description** : Journal en une phrase — ravitaillement, hydratation, douleur, RPE — converti en blocs `arc` structurés, sans jamais inventer une valeur nutritionnelle.

## Quand l'utiliser

- L'athlète tape `/log` ou décrit en une phrase ce qu'il a mangé/bu pendant une séance, une douleur ressentie, ou son ressenti d'effort (RPE)
- Exemple : « 2 gels + 500 ml au km 15, genou gauche 3/10, RPE 7 »

## Fonctionnalités

- Extraction d'entités par le modèle (produit, quantité, zone douloureuse, score, RPE, position dans la séance)
- **Arithmétique et correspondance catalogue déterministes**, jamais faites par le modèle : `scripts/arc_log.py` fait la somme des glucides et convertit un produit cité en grammes via `resources/nutrition/catalogue-produits-*.md`
- Produit **inconnu** ou **ambigu** (plusieurs candidats dans le catalogue) → l'agent demande, ne devine jamais une valeur nutritionnelle
- Écriture au contrat, en fusionnant avec le fichier existant du jour (jamais d'écrasement) :
  - `carbs_g`, `fluid_intake_ml`, `rpe` → `activities/YYYY-MM-DD_<type>.md` (séance du jour, agent `coach`)
  - `pain` (`{location, score}`) → `medical/YYYY-MM-DD_health.md` (agent `medical` si activé, sinon `coach`)
  - Une douleur ≥ 7/10 déclenche une recommandation de consultation immédiate
- Une position déclarée (« au km 15 ») reste du texte libre sous le bloc — aucune clé du contrat ne la porte
- Confirmation en **une ligne** : ce qui a été écrit, où

## Script

`scripts/arc_log.py` — **stdlib uniquement**, aucune dépendance externe. Interface JSON en entrée (entités extraites par le modèle), JSON en sortie (macros calculées, correspondances, avertissements).

## Utilisation

```bash
echo '{"catalogue_paths": ["resources/nutrition/catalogue-produits-famille.md"],
       "nutrition_items": [{"product": "gel", "qty": "2"}],
       "fluid_entries": ["500 ml"],
       "pain": [{"location": "genou gauche", "score": "3"}],
       "rpe": "7"}' | python3 scripts/arc_log.py
```

## Fichier source

`skills/log/SKILL.md`
