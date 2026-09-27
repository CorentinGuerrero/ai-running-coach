# Skill : Intervals.icu

> **Description** : Création, mise à jour et dépannage d'événements Intervals.icu via les outils MCP réels du serveur retenu par le projet (`create_event`, `update_event`, `delete_event`, `bulk_create_events` — [`eddmann/intervals-icu-mcp`](https://github.com/eddmann/intervals-icu-mcp), voir [Configuration Intervals.icu](../intervals-setup.md)).

## Quand l'utiliser

- Créer, mettre à jour ou dépanner des **événements Intervals.icu**
- **Primaire** si `[data].source = "intervals"` (#68) — voir [Configuration Intervals.icu](../intervals-setup.md)
- **Secondaire sinon** (défaut) — uniquement si l'utilisateur le demande explicitement, le calendrier Garmin restant la destination primaire

## Contenu du skill

- **Pas de `workout_doc`** : `create_event`/`update_event` n'ont aucun paramètre structuré — les cibles (allure, FC, #60) s'écrivent en texte dans `description`
- **Pas d'upsert** : `update_event` exige un `event_id` déjà existant ; vérifier `get_calendar_events` avant chaque création pour éviter les doublons
- **Vérification post-push limitée** : `get_event` ne renvoie que id/date/name/category/description/type/metrics — jamais de structure de séance
- **Préservation de `start_date`** : ne pas écraser la date de début lors des mises à jour
- **Enveloppe de réponse** : `{"data": {...}, "metadata": {...}}` pour chaque outil

## Principes clés

- Intervals.icu est **primaire** si `[data].source = "intervals"`, **secondaire** sinon (le calendrier Garmin reste alors la destination PRIMAIRE)
- Toujours **vérifier après la mise à jour**, sur les seuls champs réellement renvoyés

## Fichier source

`skills/intervals-icu-best-practices/SKILL.md`
